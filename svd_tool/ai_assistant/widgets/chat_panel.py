"""
AI 聊天面板 — QDockWidget
"""
from PyQt6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QPlainTextEdit, QScrollArea, QLabel,
    QSizePolicy, QToolButton
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QKeyEvent
from PyQt6 import sip

from ...config.styles import get_style_scheme
from ...i18n.i18n import t
from .chat_bubble import UserBubble, AssistantBubble, SystemBubble, ActionResultBubble


class _ChatInputEdit(QPlainTextEdit):
    """聊天输入框 — Enter 发送, Shift+Enter 换行"""

    send_requested = pyqtSignal()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.insertPlainText("\n")
            else:
                self.send_requested.emit()
                return
        else:
            super().keyPressEvent(event)


class AIChatPanel(QDockWidget):
    """AI 助手聊天面板（可停靠）"""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._current_assistant_bubble = None
        self._setup_ui()

    def _setup_ui(self):
        """构建面板 UI"""
        scheme = get_style_scheme()
        c = scheme.colors
        f = scheme.fonts
        s = scheme.sizes

        # DockWidget 基本设置
        self.setWindowTitle(t("ai.title", default="AI 助手"))
        self.setMinimumWidth(320)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable
        )

        # 中央容器
        container = QWidget()
        self.setWidget(container)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 工具栏
        toolbar = self._create_toolbar()
        main_layout.addWidget(toolbar)

        # 消息区域
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {c.background};
                border: none;
            }}
        """)

        self._messages_container = QWidget()
        self._messages_layout = QVBoxLayout(self._messages_container)
        self._messages_layout.setContentsMargins(4, 4, 4, 4)
        self._messages_layout.setSpacing(6)
        self._messages_layout.addStretch()

        self._scroll_area.setWidget(self._messages_container)
        main_layout.addWidget(self._scroll_area, 1)

        # 输入区域
        input_area = self._create_input_area()
        main_layout.addWidget(input_area)

        # 应用样式
        self._apply_styles()

        # 显示欢迎消息（以 AI 气泡样式呈现）
        self._show_welcome()

    def _show_welcome(self):
        """显示欢迎消息气泡"""
        self._welcome_bubble = AssistantBubble()
        self._welcome_bubble.set_content(
            t("ai.welcome", default="你好！我可以帮你查看、修改和验证 SVD 数据。请随时提问。")
        )
        self._insert_bubble(self._welcome_bubble)

    def _create_toolbar(self) -> QWidget:
        """创建顶部工具栏"""
        scheme = get_style_scheme()
        c = scheme.colors

        toolbar = QWidget()
        toolbar.setFixedHeight(36)
        toolbar.setStyleSheet(f"""
            QWidget {{
                background-color: {c.surface};
                border-bottom: 1px solid {c.border_light};
            }}
        """)

        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(4)

        # 模型标签
        self._model_label = QLabel(self.controller.config.model)
        self._model_label.setStyleSheet(f"color: {c.text_secondary}; font-size: 9pt; border: none;")
        layout.addWidget(self._model_label)

        layout.addStretch()

        # 清空按钮
        self._clear_btn = QToolButton()
        self._clear_btn.setText(t("ai.clear", default="清空"))
        self._clear_btn.setStyleSheet(f"""
            QToolButton {{
                background: transparent;
                color: {c.text_secondary};
                border: none;
                padding: 2px 6px;
                font-size: 9pt;
            }}
            QToolButton:hover {{
                color: {c.text_primary};
                background-color: {c.hover};
                border-radius: 4px;
            }}
        """)
        self._clear_btn.clicked.connect(lambda: self.controller.clear_history())
        layout.addWidget(self._clear_btn)

        # 设置按钮
        self._settings_btn = QToolButton()
        self._settings_btn.setText("⚙")
        self._settings_btn.setToolTip(t("ai.settings.title", default="AI 助手设置"))
        self._settings_btn.setStyleSheet(f"""
            QToolButton {{
                background: transparent;
                color: {c.text_secondary};
                border: none;
                padding: 2px 6px;
                font-size: 14pt;
            }}
            QToolButton:hover {{
                color: {c.accent};
                background-color: {c.hover};
                border-radius: 4px;
            }}
        """)
        self._settings_btn.clicked.connect(lambda: self.controller.show_settings())
        layout.addWidget(self._settings_btn)

        return toolbar

    def _create_input_area(self) -> QWidget:
        """创建底部输入区域"""
        scheme = get_style_scheme()
        c = scheme.colors
        s = scheme.sizes

        container = QWidget()
        container.setStyleSheet(f"""
            QWidget {{
                background-color: {c.surface};
                border-top: 1px solid {c.border_light};
            }}
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 4, 6, 6)
        layout.setSpacing(4)

        # 输入框
        self._input_edit = _ChatInputEdit()
        self._input_edit.setPlaceholderText(t("ai.placeholder", default="输入您的问题或指令..."))
        self._input_edit.setMaximumHeight(80)
        self._input_edit.send_requested.connect(self._on_send)
        self._input_edit.setStyleSheet(f"""
            QPlainTextEdit {{
                border: 1px solid {c.border};
                border-radius: {s.radius_md};
                padding: 4px 8px;
                background-color: {c.white};
                font-size: 10pt;
            }}
            QPlainTextEdit:focus {{
                border-color: {c.accent};
            }}
        """)

        layout.addWidget(self._input_edit)

        # 发送按钮行
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        btn_layout.addStretch()

        # 停止按钮（仅在 AI 响应时可见）
        self._stop_btn = QPushButton(t("ai.stop", default="停止"))
        self._stop_btn.setFixedSize(70, 28)
        self._stop_btn.setVisible(False)
        self._stop_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.error};
                color: {c.text_white};
                border: none;
                border-radius: {s.radius_sm};
                font-weight: bold;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: #d9363e;
            }}
        """)
        self._stop_btn.clicked.connect(self._on_stop)
        btn_layout.addWidget(self._stop_btn)

        self._send_btn = QPushButton(t("ai.send", default="发送"))
        self._send_btn.setFixedSize(70, 28)
        self._send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.accent};
                color: {c.text_white};
                border: none;
                border-radius: {s.radius_sm};
                font-weight: bold;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: {c.accent_hover};
            }}
            QPushButton:pressed {{
                background-color: {c.accent_pressed};
            }}
            QPushButton:disabled {{
                background-color: {c.gray};
            }}
        """)
        self._send_btn.clicked.connect(self._on_send)
        btn_layout.addWidget(self._send_btn)

        layout.addLayout(btn_layout)

        return container

    def _on_send(self):
        """发送消息"""
        if self.controller.is_busy():
            return

        text = self._input_edit.toPlainText().strip()
        if not text:
            return

        self._input_edit.clear()
        self.controller.send_message(text)

    def _on_stop(self):
        """停止 AI 响应"""
        if self.controller.is_busy():
            self.controller.stop_generation()

    def _apply_styles(self):
        """应用面板样式"""
        scheme = get_style_scheme()
        c = scheme.colors

        self.setStyleSheet(f"""
            QDockWidget {{
                color: {c.text_primary};
            }}
            QDockWidget::title {{
                background-color: {c.header_background};
                padding: 6px 8px;
                border-bottom: 1px solid {c.border_light};
            }}
        """)

    # ==================== 消息管理 ====================

    def append_user_message(self, text: str):
        """添加用户消息"""
        bubble = UserBubble()
        bubble.set_content(text)
        self._insert_bubble(bubble)

    def append_assistant_message(self, text: str):
        """添加 AI 消息"""
        bubble = AssistantBubble()
        bubble.set_content(text)
        self._insert_bubble(bubble)

    def append_system_message(self, text: str):
        """添加系统消息"""
        bubble = SystemBubble()
        bubble.set_content(text)
        self._insert_bubble(bubble)

    def append_action_result(self, operation: str, result: dict):
        """添加操作结果"""
        bubble = ActionResultBubble(operation, result)
        self._insert_bubble(bubble)

    def set_streaming(self, active: bool):
        """设置流式状态"""
        self._send_btn.setEnabled(not active)
        self._input_edit.setEnabled(not active)
        self._stop_btn.setVisible(active)

        if active:
            # 创建新的 AI 气泡用于流式追加
            self._current_assistant_bubble = AssistantBubble()
            self._current_assistant_bubble.set_content("")
            self._insert_bubble(self._current_assistant_bubble)
        # 注意：不在这里清空 _current_assistant_bubble，由 finalize_assistant_message 负责

    def _is_bubble_alive(self, bubble) -> bool:
        """检查气泡的 C++ 对象是否仍然存活"""
        return bubble is not None and not sip.isdeleted(bubble)

    def update_streaming_text(self, chunk: str):
        """更新流式文本（追加模式）"""
        if self._is_bubble_alive(self._current_assistant_bubble):
            self._current_assistant_bubble.append_text(chunk)
            self._scroll_to_bottom()

    def set_streaming_text(self, text: str):
        """设置流式文本（替换模式，用于过滤后的文本）"""
        if self._is_bubble_alive(self._current_assistant_bubble):
            self._current_assistant_bubble.set_content(text)
            self._scroll_to_bottom()

    def finalize_assistant_message(self, display_text: str):
        """最终确定助手消息（流式完成后）

        Args:
            display_text: 已经过滤掉 JSON 的纯文本，可直接显示
        """
        if self._is_bubble_alive(self._current_assistant_bubble):
            if display_text and display_text.strip():
                self._current_assistant_bubble.set_content(display_text)
            else:
                # 空消息：从布局中移除气泡，避免显示空白
                self._messages_layout.removeWidget(self._current_assistant_bubble)
                self._current_assistant_bubble.deleteLater()
            self._current_assistant_bubble = None

    def clear_chat(self):
        """清空聊天"""
        # 移除所有气泡
        while self._messages_layout.count() > 1:
            item = self._messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 显示欢迎消息
        self._show_welcome()

    def refresh_ui(self):
        """刷新面板文本（语言切换时调用）"""
        # 更新 DockWidget 标题
        self.setWindowTitle(t("ai.title"))

        # 更新欢迎消息气泡
        if hasattr(self, '_welcome_bubble') and self._welcome_bubble:
            self._welcome_bubble.set_content(t("ai.welcome"))

        # 更新输入框占位符
        if hasattr(self, '_input_edit'):
            self._input_edit.setPlaceholderText(t("ai.placeholder"))

        # 更新发送按钮
        if hasattr(self, '_send_btn'):
            self._send_btn.setText(t("ai.send"))

        # 更新工具栏按钮（保存引用以避免文本匹配）
        if hasattr(self, '_clear_btn'):
            self._clear_btn.setText(t("ai.clear"))
        if hasattr(self, '_settings_btn'):
            self._settings_btn.setToolTip(t("ai.settings.title"))

        # 更新停止按钮
        if hasattr(self, '_stop_btn'):
            self._stop_btn.setText(t("ai.stop"))

    def update_model_label(self):
        """更新模型标签"""
        if self._model_label:
            self._model_label.setText(self.controller.config.model)

    def _insert_bubble(self, bubble: QWidget):
        """在 stretch 之前插入气泡"""
        count = self._messages_layout.count()
        # stretch 在最后，在它之前插入
        self._messages_layout.insertWidget(count - 1, bubble)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        """滚动到底部"""
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(50, lambda: self._scroll_area.verticalScrollBar().setValue(
            self._scroll_area.verticalScrollBar().maximum()
        ))
