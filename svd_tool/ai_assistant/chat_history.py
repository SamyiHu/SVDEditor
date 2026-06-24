"""
聊天记录模型

支持 function-calling 的消息结构：
- assistant 消息可携带 tool_calls（模型发起的工具调用）
- tool 消息携带 tool_call_id（工具执行结果回灌）

裁剪采用"成组删除"：以"带 tool_calls 的 assistant 消息 + 其后所有 tool 结果消息"
为一个原子组，整体保留或删除，绝不拆散配对（否则 API 报 tool_call_id not found）。
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger("svd_tool.ai_assistant.ChatHistory")


@dataclass
class ChatMessage:
    """聊天消息（支持 function-calling 扩展字段）"""
    role: str  # "user", "assistant", "system", "tool"
    content: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    # 旧字段：存储已执行动作的元信息（兼容旧 UI 展示，不影响 API）
    actions: List[Dict[str, Any]] = field(default_factory=list)
    # function-calling 扩展字段（仅特定 role 使用）
    tool_calls: Optional[List[Dict[str, Any]]] = None  # assistant: [{id, name, arguments}]
    tool_call_id: Optional[str] = None  # tool: 对应的 tool_call id
    name: Optional[str] = None  # tool: 工具名（部分后端需要）

    def to_api_dict(self) -> Dict[str, Any]:
        """转换为 API 请求格式（透传完整结构）。

        各 Backend 在发请求前再转成对应 wire format（OpenAI 的 role=tool 多条消息 /
        Anthropic 的 role=user 内 tool_result block）。
        """
        d: Dict[str, Any] = {"role": self.role}
        # content 可为空字符串；OpenAI 对带 tool_calls 的 assistant 允许 content 为 None
        d["content"] = self.content if self.content is not None else ""
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.name:
            d["name"] = self.name
        return d


class ChatHistory:
    """会话聊天记录管理"""

    def __init__(self, max_messages: int = 50):
        self._messages: List[ChatMessage] = []
        self._max_messages = max_messages

    def add_message(self, role: str, content: str = "",
                    actions: Optional[List[Dict]] = None,
                    tool_calls: Optional[List[Dict[str, Any]]] = None,
                    tool_call_id: Optional[str] = None,
                    name: Optional[str] = None) -> ChatMessage:
        """添加消息（支持 function-calling 扩展字段）"""
        msg = ChatMessage(
            role=role,
            content=content,
            timestamp=datetime.now(),
            actions=actions or [],
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
            name=name,
        )
        self._messages.append(msg)
        self._trim_to_limit()
        return msg

    def _trim_to_limit(self):
        """成组裁剪：保证 tool_calls 与其 tool 结果不被拆散。

        将消息序列划分为"组"：
        - 普通消息（user/普通 assistant/system）各自成一组
        - "带 tool_calls 的 assistant + 其后连续的 tool 消息"合为一组（原子单位）
        超限时从最早的非 system 组开始整组删除。
        """
        while len(self._messages) > self._max_messages:
            # 划分组：返回每组的起止索引列表
            groups = self._compute_groups()
            # 找第一个含非 system 消息的组（保留开头的 system 组）
            removed = False
            for gi, (start, end) in enumerate(groups):
                # 跳过纯 system 组
                if all(self._messages[i].role == "system" for i in range(start, end + 1)):
                    continue
                # 整组删除 [start, end]
                del self._messages[start:end + 1]
                removed = True
                break
            if not removed:
                # 全是 system 或已无法删除，停止
                break

    def _compute_groups(self) -> List[tuple]:
        """计算消息分组。返回 [(start_idx, end_idx), ...]，覆盖全部消息。"""
        groups: List[tuple] = []
        i = 0
        n = len(self._messages)
        while i < n:
            msg = self._messages[i]
            if msg.role == "assistant" and msg.tool_calls:
                # 带工具调用：吞掉其后连续的 tool 消息
                start = i
                j = i + 1
                while j < n and self._messages[j].role == "tool":
                    j += 1
                groups.append((start, j - 1))
                i = j
            else:
                groups.append((i, i))
                i += 1
        return groups

    def get_messages_for_api(self) -> List[Dict[str, Any]]:
        """获取用于 API 调用的消息列表（透传完整结构）"""
        return [m.to_api_dict() for m in self._messages]

    def get_all_messages(self) -> List[ChatMessage]:
        """获取所有消息"""
        return list(self._messages)

    def clear(self):
        """清空聊天记录"""
        self._messages.clear()

    def __len__(self) -> int:
        return len(self._messages)
