"""
AI 后端抽象层
支持 OpenAI 兼容协议 和 Anthropic Claude API，含 function-calling（tool use）。

抽象层返回事件流（StreamEvent），而非纯文本，以表达"模型要调工具"这一状态：
- {"type": "text", "text": str}        文本片段（实时显示）
- {"type": "tool_call", "id": str, "name": str, "arguments": dict}  工具调用请求
- {"type": "done"}                      本轮响应结束

内部消息统一格式（各 Backend 在发请求前转成对应 wire format）：
- assistant 消息可同时含 content(文本) + tool_calls([{id,name,arguments(dict)}])
- tool 消息含 tool_call_id + name + content(结果文本)
"""
import json
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Iterator, Optional

from .config import AIConfig

logger = logging.getLogger("AIAssistant.Backend")


class AIBackend(ABC):
    """AI 后端抽象接口（支持 function-calling 事件流）"""

    @abstractmethod
    def chat_stream(self, messages: List[Dict[str, Any]], config: AIConfig,
                    tools: Optional[List[Dict[str, Any]]] = None) -> Iterator[Dict[str, Any]]:
        """流式聊天，逐个 yield StreamEvent。

        Args:
            messages: 内部统一格式的消息列表（含 system/user/assistant/tool）
            config: AI 配置
            tools: 工具定义（内部统一格式 [{name, description, parameters}]），
                   None 表示不启用工具
        Yields:
            StreamEvent: {"type": "text"|"tool_call"|"done", ...}
        """
        ...

    def chat(self, messages: List[Dict[str, Any]], config: AIConfig,
             tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """非流式聊天，一次性返回完整结果。

        默认实现：消费 chat_stream 事件流，聚合为结构化结果。
        子类可覆盖以直接走非流式 API。

        Returns:
            {"content": str, "tool_calls": [{id,name,arguments}]}
        """
        text_parts: List[str] = []
        tool_calls: List[Dict[str, Any]] = []
        for ev in self.chat_stream(messages, config, tools):
            if ev["type"] == "text":
                text_parts.append(ev["text"])
            elif ev["type"] == "tool_call":
                tool_calls.append({"id": ev["id"], "name": ev["name"], "arguments": ev["arguments"]})
        return {"content": "".join(text_parts), "tool_calls": tool_calls}


class OpenAICompatibleBackend(AIBackend):
    """OpenAI 兼容协议后端（支持 OpenAI、DeepSeek、Ollama、vLLM 等）"""

    def _get_client(self, config: AIConfig):
        """懒加载 openai 客户端"""
        try:
            import openai
        except ImportError:
            raise ImportError("未安装 openai 库。请运行: pip install openai")
        return openai.OpenAI(
            api_key=config.api_key,
            base_url=config.api_base_url,
            timeout=config.request_timeout,
        )

    def chat_stream(self, messages: List[Dict[str, Any]], config: AIConfig,
                    tools: Optional[List[Dict[str, Any]]] = None) -> Iterator[Dict[str, Any]]:
        """流式聊天（OpenAI Chat Completions）"""
        client = self._get_client(config)

        # 转换内部消息为 OpenAI wire format
        api_messages = _to_openai_messages(messages)

        kwargs: Dict[str, Any] = {
            "model": config.model,
            "messages": api_messages,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "stream": True,
        }
        # 工具定义转换 + tool_choice
        if tools:
            from .tool_defs import to_openai_tools as _to_openai_tools
            kwargs["tools"] = _to_openai_tools()
            kwargs["tool_choice"] = "auto"

        stream = client.chat.completions.create(**kwargs)

        # 聚合 tool_calls delta（按 index 兜底，兼容 Ollama/vLLM 的 index/id 缺失）
        accumulated: Dict[int, Dict[str, Any]] = {}

        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            # 文本片段
            if delta.content:
                yield {"type": "text", "text": delta.content}

            # 工具调用片段
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index if tc.index is not None else 0
                    slot = accumulated.setdefault(idx, {"id": None, "name": None, "arguments": ""})
                    if tc.id:
                        slot["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            slot["name"] = tc.function.name
                        if tc.function.arguments:
                            slot["arguments"] += tc.function.arguments

        # 流结束后，把聚合的 tool_calls 作为事件发出（注意：不靠 finish_reason 判定，
        # 因为部分兼容端点会把 tool_calls 的 finish_reason 误报为 stop）
        for idx in sorted(accumulated.keys()):
            slot = accumulated[idx]
            if slot["id"] and slot["name"]:
                args_str = slot["arguments"]
                try:
                    args = json.loads(args_str) if args_str else {}
                except json.JSONDecodeError:
                    logger.warning(f"tool_call 参数 JSON 解析失败: {args_str}")
                    args = {}
                yield {"type": "tool_call", "id": slot["id"], "name": slot["name"], "arguments": args}

        yield {"type": "done"}


class AnthropicBackend(AIBackend):
    """Anthropic Claude API 后端"""

    def _get_client(self, config: AIConfig):
        """懒加载 anthropic 客户端"""
        try:
            import anthropic
        except ImportError:
            raise ImportError("未安装 anthropic 库。请运行: pip install anthropic")
        return anthropic.Anthropic(
            api_key=config.api_key,
            base_url=config.api_base_url if config.api_base_url != "https://api.openai.com/v1" else None,
            timeout=config.request_timeout,
        )

    def chat_stream(self, messages: List[Dict[str, Any]], config: AIConfig,
                    tools: Optional[List[Dict[str, Any]]] = None) -> Iterator[Dict[str, Any]]:
        """流式聊天（Anthropic Messages，用原始事件流拿 tool_use）"""
        client = self._get_client(config)

        # 分离 system 消息，其余转 Anthropic wire format
        system_msg = ""
        api_messages: List[Dict[str, Any]] = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m.get("content", "") or ""
            else:
                api_messages.append(_to_anthropic_message(m))
        # 合并连续的 tool_result，避免连续多条 user 消息被 API 拒绝
        api_messages = _merge_anthropic_tool_results(api_messages)

        kwargs: Dict[str, Any] = {
            "model": config.model,
            "max_tokens": config.max_tokens,
            "messages": api_messages,
        }
        if system_msg:
            kwargs["system"] = system_msg
        if tools:
            from .tool_defs import to_anthropic_tools as _to_anthropic_tools
            kwargs["tools"] = _to_anthropic_tools()
            kwargs["tool_choice"] = {"type": "auto"}

        # 用原始事件流（text_stream 拿不到 tool_use）
        import anthropic
        tool_inputs: Dict[int, Dict[str, Any]] = {}

        with client.messages.stream(**kwargs) as stream:
            for event in stream:
                etype = getattr(event, "type", "")
                if etype == "content_block_start":
                    block = getattr(event, "content_block", None)
                    btype = getattr(block, "type", "") if block else ""
                    if btype == "tool_use":
                        tool_inputs[event.index] = {
                            "id": getattr(block, "id", None),
                            "name": getattr(block, "name", None),
                            "args_str": "",
                        }
                elif etype == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    dtype = getattr(delta, "type", "") if delta else ""
                    if dtype == "text_delta":
                        yield {"type": "text", "text": delta.text}
                    elif dtype == "input_json_delta":
                        slot = tool_inputs.get(event.index)
                        if slot is not None:
                            slot["args_str"] += getattr(delta, "partial_json", "")
                elif etype == "content_block_stop":
                    slot = tool_inputs.get(event.index)
                    if slot is not None and slot["id"] and slot["name"]:
                        try:
                            args = json.loads(slot["args_str"]) if slot["args_str"] else {}
                        except json.JSONDecodeError:
                            logger.warning(f"tool_use 参数 JSON 解析失败: {slot['args_str']}")
                            args = {}
                        yield {"type": "tool_call", "id": slot["id"], "name": slot["name"], "arguments": args}

        yield {"type": "done"}


# ==================== 消息格式转换（内部统一格式 → 各协议 wire format） ====================

def _to_openai_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """内部统一格式 → OpenAI Chat Completions wire format。

    转换规则：
    - assistant 带 tool_calls：输出 {role:assistant, content:文本或None, tool_calls:[{id,type,function:{name,arguments(JSON字符串)}}]}
    - tool 消息：输出 {role:tool, tool_call_id, content}
    - 其余：{role, content}
    """
    out: List[Dict[str, Any]] = []
    for m in messages:
        role = m["role"]
        if role == "assistant" and m.get("tool_calls"):
            item: Dict[str, Any] = {"role": "assistant"}
            content = m.get("content") or ""
            item["content"] = content if content else None
            oai_tool_calls = []
            for tc in m["tool_calls"]:
                args = tc.get("arguments", {})
                oai_tool_calls.append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(args, ensure_ascii=False) if not isinstance(args, str) else args,
                    },
                })
            item["tool_calls"] = oai_tool_calls
            out.append(item)
        elif role == "tool":
            out.append({
                "role": "tool",
                "tool_call_id": m.get("tool_call_id", ""),
                "content": m.get("content", ""),
            })
        else:
            out.append({"role": role, "content": m.get("content", "")})
    return out


def _to_anthropic_message(m: Dict[str, Any]) -> Dict[str, Any]:
    """内部统一格式 → Anthropic Messages wire format。

    转换规则：
    - assistant 带 tool_calls：content 用 block 数组 [text?, tool_use...]
    - tool 消息：转成 role=user 内含 tool_result block（同组的多个 tool 消息应合并进一条 user，
      这里单条转；agent_loop 保证连续 tool 消息的处理见 _merge_anthropic_tool_results）
    - user/assistant 纯文本：{role, content:文本}
    """
    role = m["role"]
    content = m.get("content") or ""

    if role == "assistant" and m.get("tool_calls"):
        blocks: List[Dict[str, Any]] = []
        if content:
            blocks.append({"type": "text", "text": content})
        for tc in m["tool_calls"]:
            blocks.append({
                "type": "tool_use",
                "id": tc["id"],
                "name": tc["name"],
                "input": tc.get("arguments", {}) if isinstance(tc.get("arguments"), dict) else {},
            })
        return {"role": "assistant", "content": blocks}

    if role == "tool":
        # tool 消息转 user + tool_result block
        return {
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": m.get("tool_call_id", ""),
                "content": content,
            }],
        }

    return {"role": role, "content": content}


def _merge_anthropic_tool_results(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """合并连续的 tool 消息为单条 Anthropic user 消息（多 tool_result block）。

    Anthropic 要求一条 user 消息内可含多个 tool_result block；若逐条转会出现
    连续多条 user 消息，部分场景下 API 会拒绝。此函数在转换后做合并。
    """
    out: List[Dict[str, Any]] = []
    i = 0
    while i < len(messages):
        m = messages[i]
        if m["role"] == "user" and isinstance(m.get("content"), list) and \
                m["content"] and m["content"][0].get("type") == "tool_result":
            # 收集连续的同类消息
            merged_blocks: List[Dict[str, Any]] = []
            while i < len(messages) and messages[i]["role"] == "user" and \
                    isinstance(messages[i].get("content"), list) and \
                    messages[i]["content"] and messages[i]["content"][0].get("type") == "tool_result":
                merged_blocks.extend(messages[i]["content"])
                i += 1
            out.append({"role": "user", "content": merged_blocks})
        else:
            out.append(m)
            i += 1
    return out


def create_backend(api_type: str) -> AIBackend:
    """根据 API 类型创建后端实例"""
    if api_type == "anthropic":
        return AnthropicBackend()
    return OpenAICompatibleBackend()
