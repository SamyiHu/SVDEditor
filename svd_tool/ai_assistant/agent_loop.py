"""
Function-calling 主循环（QThread）

职责：驱动 AI 与工具之间的多轮交互。
  请求 → 收集事件（text 实时显示 / tool_call 执行）→ 把 assistant(含 tool_calls) +
  tool 结果追加到 messages → 若有 tool_call 则继续下一轮，否则结束。

替代旧的"伪工具调用"机制（AI 在文本里返回 JSON、controller 解析后一次性执行、
结果不回灌）。现在工具结果会回灌给 AI，AI 据此继续推理直到给出最终文本回答。
"""
import json
import logging

from PyQt6.QtCore import QThread, pyqtSignal

from .config import AIConfig
from .backend import AIBackend
from .command_executor import CommandExecutor
from .tool_defs import dispatch as tool_dispatch

logger = logging.getLogger("AIAssistant.AgentLoop")

# 防失控：单次用户请求最多允许的工具调用轮数
_MAX_ITERATIONS = 12


class AgentLoop(QThread):
    """function-calling 主循环工作线程"""

    # 一轮开始（controller 据此重置"本轮气泡"状态）
    round_started = pyqtSignal()
    # 实时文本片段（累积显示到当前轮气泡）
    chunk_received = pyqtSignal(str)
    # 一轮文本收集完毕（携带本轮完整文本），在执行工具调用之前发出。
    # controller 据此判断"本轮有没有文本气泡"；空文本则不会有气泡。
    round_text_finished = pyqtSignal(str)
    # 一个工具被执行（operation, result_dict）—— 驱动 UI 显示动作结果
    action_executed = pyqtSignal(str, dict)
    # 整个循环完成：final_text(最后一轮文本，用于存历史), assistant_tool_calls, tool_results
    finished_loop = pyqtSignal(str, list, list)
    # 出错
    error_occurred = pyqtSignal(str)

    def __init__(self, backend: AIBackend, messages: list, config: AIConfig,
                 executor: CommandExecutor, use_stream: bool = True,
                 enable_tools: bool = True, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.messages = list(messages)  # 工作副本，循环中会追加 tool 消息
        self.config = config
        self.executor = executor
        self.use_stream = use_stream
        self.enable_tools = enable_tools
        self._stop_requested = False

    def request_stop(self):
        """请求停止（由外部调用，循环会在当前轮结束后退出）"""
        self._stop_requested = True

    def run(self):
        try:
            self._run_loop()
        except ImportError as e:
            self.error_occurred.emit(str(e))
        except Exception as e:
            logger.exception("AgentLoop 异常")
            self.error_occurred.emit(str(e))

    def _run_loop(self):
        """主循环：反复请求直到模型不再调用工具"""
        # tools 参数：第一次传工具定义；后续轮也传（让模型可继续调用）
        tools_arg = True if self.enable_tools else None

        last_text = ""
        last_tool_calls: list = []
        all_tool_results: list = []  # [{tool_call_id, name, content}]

        for iteration in range(_MAX_ITERATIONS):
            if self._stop_requested:
                break

            # 本轮开始：通知 controller 重置"本轮气泡"状态
            self.round_started.emit()

            # 收集本轮事件
            round_text_parts: list = []
            round_tool_calls: list = []

            try:
                for ev in self.backend.chat_stream(self.messages, self.config, tools=tools_arg):
                    if self._stop_requested:
                        break
                    etype = ev.get("type")
                    if etype == "text":
                        text = ev.get("text", "")
                        round_text_parts.append(text)
                        self.chunk_received.emit(text)
                    elif etype == "tool_call":
                        round_tool_calls.append({
                            "id": ev["id"],
                            "name": ev["name"],
                            "arguments": ev.get("arguments", {}),
                        })
                    # done 事件：无需处理，循环自然结束
            except Exception as e:
                self.error_occurred.emit(str(e))
                return

            round_text = "".join(round_text_parts).strip()
            last_text = round_text
            last_tool_calls = round_tool_calls

            # 本轮文本收集完毕（在执行工具前发出，让 controller 确认本轮气泡状态）
            self.round_text_finished.emit(round_text)

            if not round_tool_calls:
                # 本轮无工具调用 → 对话完成
                break

            # 把本轮 assistant 消息（含 tool_calls）追加到 messages
            self.messages.append({
                "role": "assistant",
                "content": round_text,
                "tool_calls": round_tool_calls,
            })

            # 执行每个工具调用，追加 tool 结果消息
            for tc in round_tool_calls:
                if self._stop_requested:
                    break
                name = tc["name"]
                params = tc.get("arguments", {}) or {}
                result = tool_dispatch(name, params, self.executor)
                # UI 反馈
                self.action_executed.emit(name, result)
                # 回灌内容：紧凑 JSON（含 success/message/data）
                try:
                    result_str = json.dumps(result, ensure_ascii=False)
                except (TypeError, ValueError):
                    result_str = json.dumps({"success": result.get("success", False),
                                             "message": str(result.get("message", ""))}, ensure_ascii=False)
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": name,
                    "content": result_str,
                })
                all_tool_results.append({
                    "tool_call_id": tc["id"],
                    "name": name,
                    "content": result_str,
                    "operation": name,
                })
        else:
            # 达到最大轮数仍未结束
            logger.warning(f"AgentLoop 达到最大轮数 {_MAX_ITERATIONS}，强制停止")

        # 结束：发出最终文本 + 用于存历史的 tool_calls/tool_results
        self.finished_loop.emit(last_text, last_tool_calls, all_tool_results)
