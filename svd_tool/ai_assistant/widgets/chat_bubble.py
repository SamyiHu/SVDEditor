"""
聊天消息气泡组件

AssistantBubble 使用 QTextBrowser 渲染 Markdown（标题/粗体/代码/列表/表格/链接），
其余气泡（User/System/ActionResult）保持纯文本 QLabel。
"""
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QSizePolicy,
    QTextBrowser
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor
from PyQt6 import sip

from ...config.styles import get_style_scheme
from ...i18n.i18n import t


class ChatBubble(QFrame):
    """聊天消息气泡基类"""

    # 子类可覆盖：是否启用 Markdown 渲染
    _markdown_enabled: bool = False

    def __init__(self, parent=None):
        super().__init__(parent)
        self._accumulated_text: str = ""  # 流式累积文本（仅 Markdown 渲染时用）
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

        # 内容控件（子类可覆盖 _create_content_widget 选择 QLabel 或 QTextBrowser）
        self._content_widget = self._create_content_widget()
        self._main_layout.addWidget(self._content_widget)

    def _create_content_widget(self):
        """创建内容控件。基类默认用 QLabel（纯文本）。子类可覆盖。"""
        label = QLabel()
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        return label

    def _apply_style(self):
        pass

    def set_content(self, text: str):
        """设置内容。基类用纯文本；子类可覆盖为 Markdown 渲染。"""
        if sip.isdeleted(self._content_widget):
            return
        self._accumulated_text = text
        self._content_widget.setText(text)

    def append_text(self, text: str):
        """追加文本（流式）。基类直接拼接纯文本。"""
        if sip.isdeleted(self._content_widget):
            return
        self._accumulated_text += text
        current = self._content_widget.text() if hasattr(self._content_widget, 'text') else ""
        self._content_widget.setText(current + text)


class _MarkdownTextBrowser(QTextBrowser):
    """支持 Markdown 渲染、高度自适应、透明背景的文本浏览器。

    用于 AssistantBubble：渲染 AI 回复的 Markdown，且高度跟随内容
    （不出现内部滚动条，由外层聊天滚动区负责滚动）。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dpi_adjusted_h = 0
        self._ready: bool = False  # 构造期间忽略 documentSize 信号，避免布局重入崩溃
        self.setOpenExternalLinks(True)  # 链接可点击
        self.setReadOnly(True)
        # 去掉内部滚动条：内容高度由 documentSize 信号驱动 setFixedHeight
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # 透明背景，让气泡的 surface 背景透出
        self.setStyleSheet("QTextBrowser { background: transparent; border: none; }")
        self.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
        # 尺寸策略：水平受限（由气泡宽度约束），垂直自适应
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        # 去掉默认边距，让内容贴紧气泡内边距
        self.setContentsMargins(0, 0, 0, 0)
        # 文档边距
        doc = self.document()
        doc.setDocumentMargin(4)

        # 监听文档尺寸变化，动态调整自身高度
        doc.documentLayout().documentSizeChanged.connect(self._on_doc_size_changed)
        self._ready = True  # 构造完成，允许响应信号

    def _on_doc_size_changed(self, size: QSize):
        """文档布局尺寸变化时，把控件高度设为文档内容高度（避免内部滚动条）。"""
        if sip.isdeleted(self) or not self._ready:
            return
        h = int(size.height()) + 2  # +2 容差，避免末行被裁
        if h != self._dpi_adjusted_h and h > 0:
            self._dpi_adjusted_h = h
            # 用 setFixedHeight 代替 min/max，避免触发布局抖动；延迟到下一个事件循环
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._set_fixed_height(h))

    def _set_fixed_height(self, h: int):
        """安全地设置固定高度（控件可能已被销毁）。"""
        if sip.isdeleted(self):
            return
        self.setFixedHeight(h)


class AssistantBubble(ChatBubble):
    """AI 消息气泡 — 左对齐，surface 背景，渲染 Markdown"""

    _markdown_enabled: bool = True

    def _create_content_widget(self):
        browser = _MarkdownTextBrowser()
        # CSS：Qt 把行内 `code` 渲染成 <span style="font-family:monospace">（不是 <code> 标签），
        # 行内代码自动获得等宽字体（视觉可辨识）；代码块（```）用 <pre>，可设背景框。
        browser.document().setDefaultStyleSheet(
            "pre {"
            "  background-color: rgba(128,128,128,0.18);"
            "  padding: 8px; border-radius: 4px;"
            "}"
            "a { color: #4a9eff; }"
        )
        return browser

    def set_content(self, text: str):
        """渲染 Markdown（全文解析）。"""
        if sip.isdeleted(self._content_widget):
            return
        self._accumulated_text = text
        self._content_widget.setMarkdown(text)

    def append_text(self, text: str):
        """流式追加：累积全文后重新渲染 Markdown（Markdown 是全文解析，无法逐块拼接）。"""
        if sip.isdeleted(self._content_widget):
            return
        self._accumulated_text += text
        self._content_widget.setMarkdown(self._accumulated_text)

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
        # 文字颜色通过 QTextCharFormat 全局设置，确保 Markdown 渲染后正文用主题色
        # c.text_primary 是十六进制字符串，需转 QColor
        self._content_widget.setTextColor(QColor(c.text_primary))
        self._content_widget.setFont(QFont("", -1, QFont.Weight.Normal))


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
        self._content_widget.setStyleSheet(f"color: {c.text_primary}; border: none; font-size: 10pt;")


class SystemBubble(ChatBubble):
    """系统消息 — 居中，小字"""

    def _create_layout(self):
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(12, 4, 12, 4)

        self._content_widget = QLabel()
        self._content_widget.setWordWrap(True)
        self._content_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._main_layout.addWidget(self._content_widget)

    def _apply_style(self):
        scheme = get_style_scheme()
        c = scheme.colors

        self.setStyleSheet("SystemBubble { border: none; margin: 2px 20px; }")
        self._content_widget.setStyleSheet(
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
