"""
AI 助手控制器
顶层协调器，管理后端、执行器、聊天记录和 UI 面板
"""
import json
import logging
import re
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal, QObject

from .config import AIConfig, AIConfigManager
from .backend import AIBackend, create_backend
from .command_executor import CommandExecutor
from .prompt_builder import PromptBuilder
from .chat_history import ChatHistory

logger = logging.getLogger("AIAssistant.Controller")


class _StreamingWorker(QThread):
    """流式 AI 响应工作线程"""
    chunk_received = pyqtSignal(str)
    stream_finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, backend: AIBackend, messages: list, config: AIConfig, use_stream: bool = True):
        super().__init__()
        self.backend = backend
        self.messages = messages
        self.config = config
        self.use_stream = use_stream

    def run(self):
        try:
            if self.use_stream:
                full_response = ""
                for chunk in self.backend.chat_stream(self.messages, self.config):
                    full_response += chunk
                    self.chunk_received.emit(chunk)
                self.stream_finished.emit(full_response)
            else:
                response = self.backend.chat(self.messages, self.config)
                self.stream_finished.emit(response)
        except ImportError as e:
            self.error_occurred.emit(str(e))
        except Exception as e:
            self.error_occurred.emit(f"请求失败: {str(e)}")


class AIAssistantController(QObject):
    """AI 助手顶层控制器"""

    def __init__(self, coordinator, main_window):
        super().__init__(parent=main_window)
        self.coordinator = coordinator
        self.main_window = main_window
        self.logger = logging.getLogger("AIAssistant.Controller")

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
        self._worker: Optional[_StreamingWorker] = None

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
        """发送用户消息

        Args:
            text: 用户输入的文本
        """
        if not text.strip():
            return

        if not self.config.is_configured():
            if self.panel:
                self.panel.append_system_message("请先在设置中配置 API Key。点击工具栏齿轮图标或菜单「工具 → AI 助手设置」。")
            return

        if not self.backend:
            self._init_backend()
            if not self.backend:
                if self.panel:
                    self.panel.append_system_message("AI 后端初始化失败，请检查设置。")
                return

        # 添加用户消息到历史
        self.chat_history.add_message("user", text)

        # 在面板显示用户消息
        if self.panel:
            self.panel.append_user_message(text)
            self.panel.set_streaming(True)

        # 构建完整消息列表
        messages = self._build_messages()

        # 初始化流式缓冲区
        self._streaming_buffer = ""

        # 启动工作线程
        self._worker = _StreamingWorker(
            self.backend,
            messages,
            self.config,
            self.config.enable_streaming
        )
        self._worker.chunk_received.connect(self._on_chunk_received)
        self._worker.stream_finished.connect(self._on_stream_finished)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.start()

    def _build_messages(self) -> list:
        """构建发送给 AI 的完整消息列表"""
        # 构建系统提示词（含当前 SVD 上下文）
        state_manager = self.coordinator.get_component("state_manager")
        device_info = state_manager.device_info if state_manager else None

        # 获取其他已打开的文档名称
        open_documents = None
        if hasattr(self.main_window, 'document_manager'):
            dm = self.main_window.document_manager
            active_id = dm.active_doc_id
            open_documents = [
                doc.display_name or doc.device_info.name or "未命名"
                for doc_id, doc in dm.get_all_documents().items()
                if doc_id != active_id
            ]
            if not open_documents:
                open_documents = None

        system_prompt = self.prompt_builder.build_system_prompt(device_info, open_documents)
        if self.config.system_prompt_extra:
            system_prompt += "\n\n" + self.config.system_prompt_extra

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.chat_history.get_messages_for_api())

        return messages

    def _on_chunk_received(self, chunk: str):
        """流式接收到一个文本块 — 累积并过滤 JSON 后显示"""
        if not hasattr(self, '_streaming_buffer'):
            self._streaming_buffer = ""
        self._streaming_buffer += chunk
        if self.panel:
            clean = self._clean_streaming_text(self._streaming_buffer)
            self.panel.set_streaming_text(clean)

    def _on_stream_finished(self, full_response: str):
        """流式响应完成"""
        if self.panel:
            self.panel.set_streaming(False)

        # 解析 AI 响应，提取动作和显示文本
        action_data = self._extract_json(full_response)
        display_text = self._extract_display_text(full_response, action_data)
        actions_taken = []

        # 执行动作
        if action_data and "actions" in action_data:
            for action in action_data.get("actions", []):
                result = self.executor.execute(action)
                actions_taken.append({
                    "operation": action.get("operation"),
                    "result": result
                })
                if self.panel:
                    self.panel.append_action_result(action.get("operation", ""), result)

            # 检查是否需要继续执行（多步骤任务）
            if action_data.get("continue"):
                self._schedule_continuation(action_data.get("continuation_prompt", ""))

        # 添加到历史（保存原始响应）
        self.chat_history.add_message("assistant", full_response, actions_taken)

        # 更新面板显示（干净的文本，不含 JSON）
        if self.panel:
            self.panel.finalize_assistant_message(display_text)

    def _on_error(self, error_msg: str):
        """请求出错"""
        if self.panel:
            self.panel.set_streaming(False)
            self.panel.append_system_message(f"错误: {error_msg}")

    def _clean_streaming_text(self, text: str) -> str:
        """实时去除流式文本中的 JSON 内容，仅保留用户可读的自然语言部分"""
        import re

        # 1. 移除已闭合的 ```json...``` 或 ```...``` 代码块
        cleaned = re.sub(r'```(?:json)?\s*\n.*?```', '', text, flags=re.DOTALL)

        # 2. 如果存在未闭合的 ``` 代码块开头（流式过程中），截断之
        unclosed = re.search(r'```(?:json)?\s*\n.*$', cleaned, re.DOTALL)
        if unclosed:
            cleaned = cleaned[:unclosed.start()]

        return cleaned.strip()

    def _extract_display_text(self, full_response: str, action_data: Optional[dict]) -> str:
        """从 AI 响应中提取用户可见的干净文本（不含 JSON）

        优先级：
        1. 如果有 action_data，取 explanation 字段
        2. 否则去掉 JSON 代码块，返回剩余自然语言部分
        """
        if action_data:
            explanation = action_data.get("explanation", "").strip()
            if explanation:
                return explanation

        # 没有 action_data 时，去掉 JSON 代码块
        import re
        cleaned = re.sub(r'```(?:json)?\s*\n?.*?```', '', full_response, flags=re.DOTALL).strip()
        if cleaned:
            return cleaned

        # 全是 JSON 没有自然语言时，生成简单描述
        if action_data:
            actions = action_data.get("actions", [])
            if actions:
                ops = [a.get("operation", "?") for a in actions]
                return f"正在执行: {', '.join(ops)}"

        return full_response.strip()

    def _schedule_continuation(self, continuation_prompt: str):
        """调度多步骤任务的下一步"""
        from PyQt6.QtCore import QTimer
        prompt = continuation_prompt or "继续执行任务"
        QTimer.singleShot(500, lambda: self.send_message(prompt))

    def _extract_json(self, text: str) -> Optional[dict]:
        """从文本中提取 JSON（支持 markdown 代码块和残缺 JSON 修复）"""
        # 尝试提取 ```json ... ``` 包裹的内容
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)```', text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            # 尝试从文本中找最外层 { ... }
            brace_match = re.search(r'\{.*\}', text, re.DOTALL)
            if brace_match:
                json_str = brace_match.group(0).strip()
            else:
                json_str = text.strip()

        # 第一次尝试：直接解析
        try:
            data = json.loads(json_str)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

        # 第二次尝试：修复常见的残缺 JSON
        repaired = self._try_repair_json(json_str)
        if repaired:
            try:
                data = json.loads(repaired)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

        return None

    def _try_repair_json(self, s: str) -> Optional[str]:
        """尝试修复常见的 AI 输出 JSON 问题"""
        if not s:
            return None

        # 去掉尾部不完整的内容：找到最后一个 } 并截断
        last_brace = s.rfind('}')
        if last_brace > 0:
            s = s[:last_brace + 1]

        # 补全未闭合的括号
        open_braces = s.count('{') - s.count('}')
        open_brackets = s.count('[') - s.count(']')
        if open_braces > 0:
            s += '}' * open_braces
        if open_brackets > 0:
            s += ']' * open_brackets

        # 修复缺少引号的 key:  word:  -> "word":
        s = re.sub(r'(?<=[\{,\[]) *\b(\w+)\b *:', r' "\1":', s)

        # 修复缺少引号的 value（简单字符串）: : value -> : "value"
        # 只处理紧跟在 : 后面、不是数字/布尔/null/"/{/[/ 的情况
        s = re.sub(r': *([^"\d\-\{\[\]tfn][^,\}\]\n]*?)([,\}\]])', r': "\1"\2', s)

        return s

    def clear_history(self):
        """清空聊天记录"""
        self.chat_history.clear()
        if self.panel:
            self.panel.clear_chat()

    def is_busy(self) -> bool:
        """是否正在处理请求"""
        return self._worker is not None and self._worker.isRunning()

    def shutdown(self):
        """关闭 AI 助手"""
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(3000)
