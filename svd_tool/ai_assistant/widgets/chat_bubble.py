"""
聊天消息气泡组件
"""
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6 import sip

from ...config.styles import get_style_scheme
from ...i18n.i18n import t


class ChatBubble(QFrame):
    """聊天消息气泡基类"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._create_layout()
        self._apply_style()

    def _create_layout(self):
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(8, 6, 8, 6)
        self._main_layout.setSpacing(2)

        # 角色标签
        self._role_label = QLabel()
        self._role_label.setFixedHeight(16)
        self._main_layout.addWidget(self._role_label)

        # 内容标签
        self._content_label = QLabel()
        self._content_label.setWordWrap(True)
        self._content_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._content_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self._main_layout.addWidget(self._content_label)

    def _apply_style(self):
        pass

    def set_content(self, text: str):
        if sip.isdeleted(self._content_label):
            return
        self._content_label.setText(text)

    def append_text(self, text: str):
        if sip.isdeleted(self._content_label):
            return
        current = self._content_label.text()
        self._content_label.setText(current + text)


class UserBubble(ChatBubble):
    """用户消息气泡 — 右对齐，accent 浅色背景"""

    def _apply_style(self):
        scheme = get_style_scheme()
        c = scheme.colors
        s = scheme.sizes

        self.setStyleSheet(f"""
            UserBubble {{
                background-color: {c.accent_light};
                border: 1px solid {c.accent};
                border-left: 3px solid {c.accent};
                border-radius: {s.radius_md};
                margin: 2px 4px 2px 40px;
            }}
        """)
        self._role_label.setText(t("ai.role_user", default="你"))
        self._role_label.setStyleSheet(f"color: {c.accent}; font-weight: bold; font-size: 9pt; border: none;")
        self._content_label.setStyleSheet(f"color: {c.text_primary}; border: none; font-size: 10pt;")


class AssistantBubble(ChatBubble):
    """AI 消息气泡 — 左对齐，surface 背景"""

    def _apply_style(self):
        scheme = get_style_scheme()
        c = scheme.colors
        s = scheme.sizes

        self.setStyleSheet(f"""
            AssistantBubble {{
                background-color: {c.surface};
                border: 1px solid {c.border_light};
                border-radius: {s.radius_md};
                margin: 2px 40px 2px 4px;
            }}
        """)
        self._role_label.setText("AI")
        self._role_label.setStyleSheet(f"color: {c.info}; font-weight: bold; font-size: 9pt; border: none;")
        self._content_label.setStyleSheet(f"color: {c.text_primary}; border: none; font-size: 10pt;")


class SystemBubble(ChatBubble):
    """系统消息 — 居中，小字"""

    def _create_layout(self):
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(12, 4, 12, 4)

        self._content_label = QLabel()
        self._content_label.setWordWrap(True)
        self._content_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._main_layout.addWidget(self._content_label)

    def _apply_style(self):
        scheme = get_style_scheme()
        c = scheme.colors

        self.setStyleSheet("SystemBubble { border: none; margin: 2px 20px; }")
        self._content_label.setStyleSheet(
            f"color: {c.text_secondary}; font-style: italic; font-size: 9pt; border: none;"
        )


class ActionResultBubble(QFrame):
    """操作结果卡片 — 缩进，左侧色条表示成功/失败"""

    def __init__(self, operation: str, result: dict, parent=None):
        super().__init__(parent)
        self._create_ui(operation, result)

    def _create_ui(self, operation: str, result: dict):
        scheme = get_style_scheme()
        c = scheme.colors
        s = scheme.sizes

        success = result.get("success", False)
        message = result.get("message", "")

        border_color = c.success if success else c.error
        bg_color = "#f0fff0" if success else "#fff0f0"
        if hasattr(c, '_ai_action_success_bg'):
            pass

        self.setStyleSheet(f"""
            ActionResultBubble {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-left: 3px solid {border_color};
                border-radius: {s.radius_sm};
                margin: 2px 40px 2px 24px;
                padding: 4px 8px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 4, 6, 4)
        layout.setSpacing(2)

        # 操作名称
        icon = "OK" if success else "FAIL"
        op_label = QLabel(f"[{icon}] {operation}")
        op_label.setStyleSheet(f"color: {border_color}; font-weight: bold; font-size: 9pt; border: none;")
        layout.addWidget(op_label)

        # 结果消息
        if message:
            msg_label = QLabel(message)
            msg_label.setWordWrap(True)
            msg_label.setStyleSheet(f"color: {c.text_primary}; font-size: 9pt; border: none;")
            layout.addWidget(msg_label)
