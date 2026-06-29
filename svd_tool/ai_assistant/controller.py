"""
AI 助手控制器
顶层协调器，管理后端、执行器、聊天记录和 UI 面板。

改造为真正的 function-calling 循环：用户消息 → AgentLoop（多轮工具调用）→ 最终文本回答。
工具结果回灌给 AI 继续推理，替代旧的"全文塞 system prompt + 文本里嵌 JSON 动作"机制。
"""
import logging
from typing import Optional

from PyQt6.QtCore import QObject

from .config import AIConfig, AIConfigManager
from .backend import AIBackend, create_backend
from .command_executor import CommandExecutor
from .prompt_builder import PromptBuilder
from .chat_history import ChatHistory
from .agent_loop import AgentLoop
from ..i18n.i18n import t

logger = logging.getLogger("svd_tool.ai_assistant.Controller")


class AIAssistantController(QObject):
    """AI 助手顶层控制器"""

    def __init__(self, coordinator, main_window):
        super().__init__(parent=main_window)
        self.coordinator = coordinator
        self.main_window = main_window
        self.logger = logging.getLogger("svd_tool.ai_assistant.Controller")

        # 加载配置
        self.config = AIConfigManager.load()

        # 初始化组件
        self.backend: Optional[AIBackend] = None
        self.executor = CommandExecutor(coordinator, main_window)
        self.prompt_builder = PromptBuilder()
        self.chat_history = ChatHistory(max_messages=self.config.max_history_messages)

        # UI 面板（延迟创建）
        self.panel = None

        # 工作线程
        self._worker: Optional[AgentLoop] = None

        # 初始化后端
        self._init_backend()

    def _init_backend(self):
        """初始化 AI 后端"""
        try:
            self.backend = create_backend(self.config.api_type)
        except Exception as e:
            self.logger.warning(f"初始化 AI 后端失败: {e}")
            self.backend = None

    def initialize(self):
        """初始化 UI 面板并停靠到主窗口"""
        from .widgets.chat_panel import AIChatPanel
        from PyQt6.QtCore import Qt

        self.panel = AIChatPanel(self, self.main_window)
        self.main_window.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea,
            self.panel
        )
        self.panel.hide()  # 默认隐藏

        # 注册到协调器
        self.coordinator.register_component('ai_assistant', self)

        self.logger.info("AI 助手模块初始化完成")

    def toggle_panel(self):
        """切换面板显示/隐藏"""
        if not self.panel:
            return
        if self.panel.isVisible():
            self.panel.hide()
        else:
            self.panel.show()
            self.panel.raise_()

    def show_settings(self):
        """显示配置对话框"""
        from .widgets.settings_dialog import AISettingsDialog

        dialog = AISettingsDialog(self.config, self.main_window)
        if dialog.exec():
            new_config = dialog.get_config()
            self.config = new_config
            AIConfigManager.save(new_config)

            # 重新初始化后端
            self._init_backend()
            self.chat_history = ChatHistory(max_messages=self.config.max_history_messages)

            # 更新面板显示
            if self.panel:
                self.panel.update_model_label()

            self.logger.info("AI 配置已更新")

    def send_message(self, text: str):
        """发送用户消息（从 UI 输入）"""
        if not text.strip():
            return

        if not self.config.is_configured():
            if self.panel:
                self.panel.append_system_message(t("ai.error.no_api_key_hint"))
            return

        if not self.backend:
            self._init_backend()
            if not self.backend:
                if self.panel:
                    self.panel.append_system_message(t("ai.error.backend_init_failed"))
                return

        # 添加用户消息到历史
        self.chat_history.add_message("user", text)

        # 在面板显示用户消息
        if self.panel:
            self.panel.append_user_message(text)

        # 启动 agent loop
        self._start_agent_loop()

    def _start_agent_loop(self):
        """启动 function-calling 主循环"""
        if not self.backend:
            self._init_backend()
            if not self.backend:
                return

        if self.panel:
            self.panel.set_streaming(True)

        # 构建完整消息列表
        messages = self._build_messages()

        # 上下文压缩提示：若本次请求压缩了历史 tool 结果，告知用户（可见性，#6）
        truncated = getattr(self, "_last_compact_count", 0)
        if truncated > 0 and self.panel:
            self.panel.append_system_message(t(
                "ai.compact_hint", n=truncated,
                default="ℹ 已自动压缩 {n} 条较早的工具结果，以控制上下文长度。"
            ))

        # 启动 AgentLoop（启用工具）
        self._worker = AgentLoop(
            backend=self.backend,
            messages=messages,
            config=self.config,
            executor=self.executor,
            use_stream=self.config.enable_streaming,
            enable_tools=True,
            parent=self,
        )
        self._worker.round_started.connect(self._on_round_started)
        self._worker.chunk_received.connect(self._on_chunk_received)
        self._worker.round_text_finished.connect(self._on_round_text_finished)
        self._worker.action_executed.connect(self._on_action_executed)
        self._worker.finished_loop.connect(self._on_loop_finished)
        self._worker.continuation_requested.connect(self._on_continuation_requested)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.start()

    def _build_messages(self) -> list:
        """构建发送给 AI 的完整消息列表"""
        # 构建系统提示词（含当前 SVD 上下文摘要）
        state_manager = self.coordinator.get_component("state_manager")
        device_info = state_manager.device_info if state_manager else None

        # 获取其他已打开的文档信息（含 doc_id 和 file_path，供 AI 跨文档操作）
        open_documents = None
        if hasattr(self.main_window, 'document_manager'):
            dm = self.main_window.document_manager
            active_id = dm.active_doc_id
            all_docs = dm.get_all_documents()
            # 当前活跃文档的信息
            active_doc = all_docs.get(active_id) if active_id else None
            active_doc_info = None
            if active_doc:
                active_doc_info = {
                    "doc_id": active_id,
                    "name": active_doc.display_name,
                    "file_path": active_doc.file_path or "",
                    "modified": active_doc.modified,
                }
            # 其他文档列表
            other_docs = []
            for doc_id, doc in all_docs.items():
                if doc_id != active_id:
                    other_docs.append({
                        "doc_id": doc_id,
                        "name": doc.display_name or doc.device_info.name or t("msg.unnamed"),
                        "file_path": doc.file_path or "",
                        "modified": doc.modified,
                    })
            if other_docs or active_doc_info:
                open_documents = {
                    "active": active_doc_info,
                    "others": other_docs,
                }

        system_prompt = self.prompt_builder.build_system_prompt(device_info, open_documents)
        if self.config.system_prompt_extra:
            system_prompt += "\n\n" + self.config.system_prompt_extra

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.chat_history.get_messages_for_api())

        # 防御：保证 assistant(tool_calls) 与 tool 消息一一配对。
        # 历史可能因旧的 bug/中断残留"悬空"的 tool_call（缺对应 tool 结果），
        # 直接发给 API 会触发 400 "tool_call ids did not have response messages"。
        messages = _sanitize_messages_for_api(messages)

        # 批量任务（如一次生成多个 SVD）会累积大量 tool 结果，导致上下文膨胀、
        # 推理变慢甚至超时。对较早的 tool 消息内容做裁剪（保留概要），最近若干轮保持完整。
        # 压缩配置来自 AIConfig（用户可见、可调）；记录被压缩条数供 _start_agent_loop 提示。
        messages, truncated = _compact_tool_results(
            messages,
            keep_full_groups=self.config.compact_keep_groups,
            max_tool_content_chars=self.config.compact_max_chars,
        )
        self._last_compact_count = truncated

        return messages

    # ==================== AgentLoop 信号处理 ====================

    def _on_round_started(self):
        """一轮开始：重置本轮状态（气泡延迟到首个非空 chunk 才创建，避免空气泡）。"""
        self._round_text_buffer = ""
        self._current_round_has_bubble = False

    def _on_chunk_received(self, chunk: str):
        """实时文本片段：首次非空时为本轮创建独立气泡，之后追加。"""
        if not self.panel:
            return
        # 本轮首个非空 chunk：新建气泡
        if not getattr(self, "_current_round_has_bubble", False) and chunk:
            self.panel.new_streaming_bubble()
            self._current_round_has_bubble = True
            self._round_text_buffer = ""
        if self._current_round_has_bubble:
            self._round_text_buffer += chunk
            self.panel.set_streaming_text(self._round_text_buffer)

    def _on_round_text_finished(self, text: str):
        """本轮文本收集完毕。

        无需额外操作：有文本的轮已在 chunk 阶段创建并填充了气泡；
        空文本轮没有气泡。后续的工具结果卡片会自然插到本气泡下方。
        """
        # 记录本轮最终文本（用于存历史），保留 _current_round_has_bubble 状态
        self._last_round_text = text

    def _on_action_executed(self, operation: str, result: dict):
        """工具执行完毕 —— 显示动作结果（插到最底，在本轮气泡之后）"""
        if self.panel:
            self.panel.append_action_result(operation, result)

    def _on_loop_finished(self, final_text: str, last_tool_calls: list, all_tool_results: list):
        """AgentLoop 完成 —— 存历史 + 结束流式（不再覆盖气泡内容）。

        每轮文本已在各自气泡显示，这里只负责：
        1. 把整个 agent 交互存入 chat_history（供下次请求上下文）
        2. 兜底处理最后一个气泡（若为空则移除）
        3. 恢复输入控件状态
        """
        # 存历史：assistant（最后一轮文本 + 工具调用）+ 所有工具结果
        if last_tool_calls:
            self.chat_history.add_message(
                "assistant", final_text,
                tool_calls=last_tool_calls,
            )
            for tr in all_tool_results:
                self.chat_history.add_message(
                    "tool", tr["content"],
                    tool_call_id=tr["tool_call_id"],
                    name=tr["name"],
                )
        else:
            self.chat_history.add_message("assistant", final_text)

        if self.panel:
            # 兜底：若最后一个气泡无内容则移除；否则保留（内容已在 chunk 阶段填充）
            self.panel.finalize_assistant_message(final_text)
            self.panel.end_streaming()

        # 清理本轮状态
        self._round_text_buffer = ""
        self._current_round_has_bubble = False

    def _on_continuation_requested(self, completed: int):
        """预算耗尽，工作线程在等用户决定是否继续（本槽在主线程执行）。

        弹出对话框让用户选择：继续（累加预算，从断点接着跑）/ 停止。
        决策通过 set_continuation_decision 回传，唤醒阻塞的工作线程。
        """
        from PyQt6.QtWidgets import QMessageBox

        parent = self.panel if (self.panel and self.panel.isVisible()) else self.main_window
        msg_box = QMessageBox(parent)
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setWindowTitle(t("ai.continue.title", default="继续运行？"))
        msg_box.setText(t(
            "ai.continue.text",
            default="AI 已完成 {n} 轮工具调用，仍未给出最终回答。\n是否继续让它接着做？",
            n=completed,
        ))
        continue_btn = msg_box.addButton(
            t("ai.continue.yes", default="继续"), QMessageBox.ButtonRole.AcceptRole)
        msg_box.addButton(
            t("ai.continue.no", default="停止"), QMessageBox.ButtonRole.RejectRole)
        msg_box.setDefaultButton(continue_btn)

        decision = "continue" if msg_box.exec() == QMessageBox.ButtonRole.AcceptRole else "stop"
        self.logger.info(f"用户续跑决策: {decision}（已完成 {completed} 轮）")
        self._worker.set_continuation_decision(decision)

    def _on_error(self, error_msg: str):
        """请求出错"""
        if self.panel:
            self.panel.finalize_assistant_message("")
            self.panel.end_streaming()
            self.panel.append_system_message(t("ai.error.prefix", error=error_msg))
        self._round_text_buffer = ""
        self._current_round_has_bubble = False

    def clear_history(self):
        """清空聊天记录"""
        self.chat_history.clear()
        if self.panel:
            self.panel.clear_chat()

    def is_busy(self) -> bool:
        """是否正在处理请求"""
        return self._worker is not None and self._worker.isRunning()

    def stop_generation(self):
        """停止当前 AI 生成"""
        if self._worker and self._worker.isRunning():
            self.logger.info("用户请求停止生成")
            self._worker.request_stop()
            self._worker.quit()
            self._worker.wait(2000)
            if self.panel:
                self.panel.finalize_assistant_message("")
                self.panel.end_streaming()

    def shutdown(self):
        """关闭 AI 助手"""
        if self._worker and self._worker.isRunning():
            self._worker.request_stop()
            self._worker.quit()
            self._worker.wait(3000)


def _sanitize_messages_for_api(messages: list) -> list:
    """清洗消息列表，保证 function-calling 协议合规。

    处理两类会导致 API 400 的问题：
    1. assistant 消息带 tool_calls，但其中某些 tool_call 缺少对应的 tool 结果消息
       → 删掉这些"悬空"的 tool_call 项；若全部悬空，把该 assistant 降级为纯文本。
    2. 孤立的 tool 消息（找不到其 tool_call_id 对应的 assistant）→ 删除。

    仅在发请求前用于 API 的副本，不改写 chat_history 本身。
    """
    # 第一遍：收集每个 tool_call_id 是否有 tool 消息响应
    answered_ids = {
        m.get("tool_call_id") for m in messages
        if m.get("role") == "tool" and m.get("tool_call_id")
    }

    out: list = []
    # 第二遍：逐条处理
    for m in messages:
        role = m.get("role")
        if role == "assistant" and m.get("tool_calls"):
            # 只保留有响应的 tool_call
            kept = [tc for tc in m["tool_calls"] if tc.get("id") in answered_ids]
            if not kept:
                # 全部悬空：降级为普通 assistant 文本消息
                logger.warning("清洗历史：assistant 的 tool_calls 全部无响应，降级为文本消息")
                out.append({"role": "assistant", "content": m.get("content") or ""})
            else:
                if len(kept) != len(m["tool_calls"]):
                    logger.warning(
                        f"清洗历史：丢弃 {len(m['tool_calls']) - len(kept)} 个无响应的 tool_call")
                new_m = dict(m)
                new_m["tool_calls"] = kept
                out.append(new_m)
        elif role == "tool":
            # 只保留 tool_call_id 存在于某 assistant.tool_calls 的 tool 消息
            tid = m.get("tool_call_id")
            if tid in _collect_tool_call_ids(messages):
                out.append(m)
            else:
                logger.warning(f"清洗历史：丢弃孤立的 tool 消息 (tool_call_id={tid})")
        else:
            out.append(m)
    return out


def _collect_tool_call_ids(messages: list) -> set:
    """收集所有 assistant.tool_calls 中出现的 tool_call id。"""
    ids = set()
    for m in messages:
        if m.get("role") == "assistant" and m.get("tool_calls"):
            for tc in m["tool_calls"]:
                if tc.get("id"):
                    ids.add(tc["id"])
    return ids


def _compact_tool_results(messages: list,
                          keep_full_groups: int = 6,
                          max_tool_content_chars: int = 400):
    """压缩较早的 tool 结果内容，控制上下文体积。

    批量任务（一次生成多个 SVD 文档）会让 messages 里堆积大量 tool 结果 JSON，
    使每次请求都携带全部历史，导致 DeepSeek 等后端推理变慢甚至超时。

    策略（只动 tool 消息的 content，不删消息、不破坏配对）：
    - 把消息序列按"组"划分（同 _compute_groups 的口径：带 tool_calls 的 assistant +
      其后的 tool 消息为一组）。system/普通消息各自成组。
    - 最近 keep_full_groups 组保持原样。
    - 较早组里的 tool 消息，若 content 超过 max_tool_content_chars，截断并标注，
      让模型仍能看到"这个工具调用过、大致结果"，但不必携带完整 JSON。
    - assistant 的 tool_calls（调用意图）始终完整保留——模型需要知道它做过什么。

    max_tool_content_chars=0 时禁用压缩（全量保留）。

    仅作用于发请求的副本，不改 chat_history。

    Returns:
        (压缩后的 messages, 被截断的 tool 消息条数)
    """
    if not messages:
        return messages, 0

    # 禁用压缩
    if max_tool_content_chars <= 0:
        return messages, 0

    # 划分组：[(start, end), ...]
    groups: list = []
    i = 0
    n = len(messages)
    while i < n:
        m = messages[i]
        if m.get("role") == "assistant" and m.get("tool_calls"):
            start = i
            j = i + 1
            while j < n and messages[j].get("role") == "tool":
                j += 1
            groups.append((start, j - 1))
            i = j
        else:
            groups.append((i, i))
            i += 1

    # 早于"最近 keep_full_groups 组"的才压缩
    if len(groups) <= keep_full_groups:
        return messages, 0
    cutoff = len(groups) - keep_full_groups  # 前 cutoff 组需要压缩

    out: list = []
    truncated = 0
    for gi, (start, end) in enumerate(groups):
        for idx in range(start, end + 1):
            m = messages[idx]
            if gi < cutoff and m.get("role") == "tool":
                content = m.get("content", "") or ""
                if len(content) > max_tool_content_chars:
                    new_m = dict(m)
                    new_m["content"] = (content[:max_tool_content_chars] +
                                        "\n...[已截断，仅保留概要]")
                    out.append(new_m)
                    truncated += 1
                    continue
            out.append(m)
    return out, truncated
