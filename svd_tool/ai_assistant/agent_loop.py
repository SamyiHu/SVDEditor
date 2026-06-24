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

from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition

from .config import AIConfig
from .backend import AIBackend
from .command_executor import CommandExecutor
from .tool_defs import dispatch as tool_dispatch

logger = logging.getLogger("svd_tool.ai_assistant.AgentLoop")

# 防失控：单次"预算"内的工具调用轮数。批量任务（如一次生成多个 SVD 文档）
# 单条消息可能需要 20~40+ 轮，达此预算时不直接截断，而是问用户是否继续；
# 选择继续则累加预算并从断点接着跑（复用已回灌的工具结果）。
# 同时通过 chat_history 裁剪 + controller 的 _compact_tool_results 控制上下文膨胀。
_ITER_BUDGET = 30
# 用户每次选"继续"时追加的预算轮数
_ITER_BUDGET_INCREMENT = 30


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
    # 到达预算上限，请求用户决定是否继续（携带已完成的轮数）。
    # controller 据此弹框；用户的选择通过 set_continuation_decision() 回传。
    continuation_requested = pyqtSignal(int)
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
        # 用户续跑决策同步：工作线程在预算耗尽时阻塞等待 controller 的回传
        self._cont_mutex = QMutex()
        self._cont_cond = QWaitCondition()
        self._cont_decision: str = ""  # "continue" / "stop" / ""（未决定）

    def request_stop(self):
        """请求停止（由外部调用，循环会在当前轮结束后退出）。

        同时唤醒可能在等待续跑决策的循环，避免死锁。
        """
        self._stop_requested = True
        # 若此刻正阻塞在"等待用户续跑决策"，立即唤醒并按停止处理
        self._cont_mutex.lock()
        try:
            self._cont_decision = "stop"
            self._cont_cond.wakeAll()
        finally:
            self._cont_mutex.unlock()

    def set_continuation_decision(self, decision: str):
        """回传用户的续跑决策（由 controller 在主线程调用）。

        Args:
            decision: "continue" 累加预算继续；"stop" 停止生成
        """
        self._cont_mutex.lock()
        try:
            self._cont_decision = decision
            self._cont_cond.wakeAll()
        finally:
            self._cont_mutex.unlock()

    def run(self):
        try:
            self._run_loop()
        except ImportError as e:
            self.error_occurred.emit(str(e))
        except Exception as e:
            logger.exception("AgentLoop 异常")
            self.error_occurred.emit(str(e))

    def _run_loop(self):
        """主循环：反复请求直到模型不再调用工具，或用户在预算耗尽时选择停止。

        到达预算上限时不直接截断，而是发 continuation_requested 信号阻塞等待
        用户决定；选"继续"则累加预算并从断点接着跑（messages 工作副本里已有
        上一批 tool 结果，自然续上），选"停止"则按停止流程结束。
        """
        # tools 参数：第一次传工具定义；后续轮也传（让模型可继续调用）
        tools_arg = True if self.enable_tools else None

        last_text = ""
        last_tool_calls: list = []
        all_tool_results: list = []  # [{tool_call_id, name, content}]

        iteration = 0
        budget = _ITER_BUDGET  # 当前可用预算（可被用户"继续"累加）
        truncated_by_budget = False

        while iteration < budget:
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

            iteration += 1
            round_text = "".join(round_text_parts).strip()
            last_text = round_text

            # 收集阶段若被停止或流式中断，本轮 tool_call 可能残缺（缺 id/name）。
            # 过滤掉无效项；若已请求停止则整轮丢弃，避免把不完整的 tool_calls 写入历史。
            valid_tool_calls = [tc for tc in round_tool_calls
                                if tc.get("id") and tc.get("name")]
            if self._stop_requested:
                valid_tool_calls = []
            last_tool_calls = valid_tool_calls

            # 本轮文本收集完毕（在执行工具前发出，让 controller 确认本轮气泡状态）
            self.round_text_finished.emit(round_text)

            if not valid_tool_calls:
                # 本轮无（有效）工具调用 → 对话完成
                break

            # 把本轮 assistant 消息（含 tool_calls）追加到 messages
            self.messages.append({
                "role": "assistant",
                "content": round_text,
                "tool_calls": valid_tool_calls,
            })

            # 执行每个工具调用，追加 tool 结果消息。
            # 关键：即使用户已请求停止，也必须为本轮每个 tool_call 都补一条 tool 结果，
            # 否则 assistant(tool_calls) 与 tool 消息无法一一配对，下一次请求会被 API
            # 以 400 "tool_call ids did not have response messages" 拒绝。
            for tc in valid_tool_calls:
                name = tc["name"]
                params = tc.get("arguments", {}) or {}
                if self._stop_requested:
                    # 停止后不再真正执行工具，补"已取消"结果以维持配对
                    result = {"success": False,
                              "message": "用户已停止生成，工具调用未执行", "data": None}
                else:
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

            # 预算耗尽：询问用户是否继续，而不是静默截断。
            if iteration >= budget and not self._stop_requested:
                decision = self._ask_continuation(iteration)
                if decision == "continue":
                    budget += _ITER_BUDGET_INCREMENT
                    logger.info(f"用户选择继续，预算累加至 {budget}，已执行 {iteration} 轮")
                else:
                    truncated_by_budget = True
                    break

        if truncated_by_budget:
            hint = (f"⏹ 已完成 {iteration} 轮工具调用后用户选择停止。"
                    f"未完成的部分，可发送\"继续\"让我接着做。")
            last_text = (last_text + "\n\n" + hint).strip() if last_text else hint
            logger.warning(f"AgentLoop 在用户选择下停止，已完成 {iteration} 轮")

        # 结束：发出最终文本 + 用于存历史的 tool_calls/tool_results。
        # 截断/停止时：最后完整执行的那一轮的 tool_calls 与 tool_results 已配对，
        # 不会产生悬空历史。仅当收集阶段异常退出时 last_tool_calls 才可能不完整，
        # 那种情况由 controller 的 _sanitize_messages_for_api 兜底。
        self.finished_loop.emit(last_text, last_tool_calls, all_tool_results)

    def _ask_continuation(self, completed: int) -> str:
        """预算耗尽时阻塞等待用户决定是否继续。

        通过 continuation_requested 信号通知 controller（主线程）弹框询问，
        本工作线程用 QWaitCondition 阻塞，直到 controller 调用
        set_continuation_decision() 或 request_stop() 唤醒。

        Returns:
            "continue" 或 "stop"
        """
        self.continuation_requested.emit(completed)
        self._cont_mutex.lock()
        try:
            if self._cont_decision == "":
                self._cont_cond.wait(self._cont_mutex)
            decision = self._cont_decision or "stop"
            # 消费决策，重置以便下次询问复用
            self._cont_decision = ""
        finally:
            self._cont_mutex.unlock()
        return decision
