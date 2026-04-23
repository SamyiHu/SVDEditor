"""
基础编辑对话框
提供通用的表单布局、验证和数据收集功能
带右侧 SVD XML 实时预览（含语法高亮）
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QDialogButtonBox, QFormLayout,
    QWidget, QScrollArea, QMessageBox, QSplitter,
    QPlainTextEdit
)
from PyQt6.QtCore import Qt, QTimer, QRegularExpression
from PyQt6.QtGui import (
    QFont, QSyntaxHighlighter, QTextCharFormat,
    QColor
)


class XMLSyntaxHighlighter(QSyntaxHighlighter):
    """XML 语法高亮器"""

    def __init__(self, document):
        super().__init__(document)

        # 标签名
        tag_fmt = QTextCharFormat()
        tag_fmt.setForeground(QColor("#1565C0"))  # 蓝色
        tag_fmt.setFontWeight(QFont.Weight.Bold)
        self._rules = []

        # <tagname ...> 和 </tagname>
        self._rules.append((QRegularExpression(r"</?[a-zA-Z_][\w\-.]*"), tag_fmt))

        # 属性名
        attr_fmt = QTextCharFormat()
        attr_fmt.setForeground(QColor("#C62828"))  # 暗红
        self._rules.append((QRegularExpression(r'\b[a-zA-Z_][\w\-]*(?==)'), attr_fmt))

        # 属性值
        val_fmt = QTextCharFormat()
        val_fmt.setForeground(QColor("#2E7D32"))  # 深绿
        self._rules.append((QRegularExpression(r'"[^"]*"'), val_fmt))

        # XML 注释
        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor("#9E9E9E"))
        comment_fmt.setFontItalic(True)
        self._rules.append((QRegularExpression(r"<!--[\s\S]*?-->"), comment_fmt))

        # 尖括号
        bracket_fmt = QTextCharFormat()
        bracket_fmt.setForeground(QColor("#1565C0"))
        self._rules.append((QRegularExpression(r"[<>]"), bracket_fmt))

    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            match = pattern.match(text)
            while match.hasMatch():
                start = match.capturedStart()
                length = match.capturedLength()
                self.setFormat(start, length, fmt)
                # 继续搜索后续匹配
                match = pattern.match(text, start + length)


class BaseEditDialog(QDialog):
    """基础编辑对话框，左表单 + 右SVD预览"""

    def __init__(self, parent=None, title: str = ""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(780)
        self.result_data = None
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(200)
        self._preview_timer.timeout.connect(self._do_update_preview)

        # 主布局
        self._main_layout = QVBoxLayout(self)

        # 水平分割器：左表单 + 右预览
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # === 左侧：表单滚动区域 ===
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(350)

        self._form_container = QWidget()
        self._form_layout = QFormLayout(self._form_container)
        self._form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._form_layout.setSpacing(8)

        scroll.setWidget(self._form_container)
        self._splitter.addWidget(scroll)

        # === 右侧：SVD XML 预览 ===
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(4, 4, 4, 4)
        preview_layout.setSpacing(4)

        preview_label = QLabel("SVD Preview")
        preview_label.setStyleSheet("color: #888; font-size: 10px; padding: 0; margin: 0;")
        preview_layout.addWidget(preview_label)

        self._preview_edit = QPlainTextEdit()
        self._preview_edit.setReadOnly(True)
        self._preview_edit.setFont(QFont("Consolas, 'Courier New', monospace", 9))
        self._preview_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._preview_edit.setStyleSheet("""
            QPlainTextEdit {
                background-color: #FFFFFF;
                color: #333333;
                border: 1px solid #DDD;
                border-radius: 4px;
                padding: 4px;
                selection-background-color: #E3F2FD;
            }
        """)
        self._preview_edit.setPlaceholderText("No preview available")
        preview_layout.addWidget(self._preview_edit)

        # XML 语法高亮
        self._highlighter = XMLSyntaxHighlighter(self._preview_edit.document())

        self._splitter.addWidget(preview_widget)
        self._splitter.setSizes([420, 340])

        self._main_layout.addWidget(self._splitter)

        # 子类在此添加表单项
        self.setup_form()

        # 标准按钮（确定/取消）
        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._button_box.accepted.connect(self._on_accept)
        self._button_box.rejected.connect(self.reject)
        self._main_layout.addWidget(self._button_box)

        # 初始刷新预览
        self.update_preview()

        # 延迟调整高度以适应所有表单项
        QTimer.singleShot(0, self._adjust_height)

    def _adjust_height(self):
        """根据表单内容自动调整对话框高度，并居中于父窗口"""
        self._form_container.adjustSize()
        form_height = self._form_container.sizeHint().height()
        button_height = self._button_box.sizeHint().height()
        margins = self._main_layout.contentsMargins().top() + self._main_layout.contentsMargins().bottom()
        total = form_height + button_height + margins + 20
        h = min(total, 650)
        self.setMinimumHeight(h)
        self.resize(self.width(), h)
        # 居中于父窗口
        if self.parent():
            parent_geo = self.parent().geometry()
            x = parent_geo.center().x() - self.width() // 2
            y = parent_geo.center().y() - h // 2
            self.move(x, y)

    def setup_form(self):
        """子类重写此方法添加表单项"""
        pass

    def add_form_row(self, label_text: str, widget: QWidget):
        """添加一行表单（标签 + 控件）"""
        label = QLabel(label_text)
        self._form_layout.addRow(label, widget)

    # ==================== 冲突样式辅助方法 ====================

    _CONFLICT_STYLE = "border: 2px solid #E53935; border-radius: 6px; background-color: #FFF0F0;"
    _NORMAL_STYLE = ""

    def _set_conflict_style(self, widget, conflict_msg: str):
        """为控件设置冲突样式（红色边框 + tooltip）"""
        widget.setStyleSheet(self._CONFLICT_STYLE)
        widget.setToolTip(conflict_msg)

    def _clear_conflict_style(self, widget):
        """清除控件的冲突样式"""
        widget.setStyleSheet(self._NORMAL_STYLE)
        widget.setToolTip("")

    def _on_accept(self):
        """确定按钮点击处理"""
        try:
            self.validate_input()
            self.collect_data()
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "验证错误", str(e))

    def validate_input(self):
        """子类重写此方法进行输入验证"""
        pass

    def collect_data(self):
        """子类重写此方法收集表单数据"""
        pass

    def load_data(self, data):
        """子类重写此方法加载已有数据"""
        pass

    # ==================== SVD 预览相关 ====================

    def update_preview(self):
        """请求刷新预览（防抖 200ms）"""
        self._preview_timer.start()

    def _do_update_preview(self):
        """实际执行预览刷新"""
        xml = self._generate_preview_xml()
        if xml:
            self._preview_edit.setPlainText(xml)
        else:
            self._preview_edit.clear()

    def _generate_preview_xml(self) -> str:
        """子类重写此方法，返回当前编辑元素的 XML 字符串"""
        return ""

    def _connect_preview_signal(self, widget):
        """连接控件信号到预览刷新（便捷方法）"""
        if hasattr(widget, 'textChanged'):
            widget.textChanged.connect(self.update_preview)
        elif hasattr(widget, 'textEdited'):
            widget.textEdited.connect(self.update_preview)
        elif hasattr(widget, 'valueChanged'):
            widget.valueChanged.connect(self.update_preview)
        elif hasattr(widget, 'currentTextChanged'):
            widget.currentTextChanged.connect(self.update_preview)
        elif hasattr(widget, 'stateChanged'):
            widget.stateChanged.connect(self.update_preview)
        elif hasattr(widget, 'toggled'):
            widget.toggled.connect(self.update_preview)
