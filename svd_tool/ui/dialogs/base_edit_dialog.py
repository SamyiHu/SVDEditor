"""
基础编辑对话框
提供通用的表单布局、验证和数据收集功能
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QDialogButtonBox, QFormLayout,
    QWidget, QScrollArea, QMessageBox
)
from PyQt6.QtCore import Qt


class BaseEditDialog(QDialog):
    """基础编辑对话框，提供表单布局和标准按钮"""

    def __init__(self, parent=None, title: str = ""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(450)
        self.result_data = None

        # 主布局
        self._main_layout = QVBoxLayout(self)

        # 创建滚动区域（支持长表单）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # 表单容器
        self._form_container = QWidget()
        self._form_layout = QFormLayout(self._form_container)
        self._form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._form_layout.setSpacing(8)

        scroll.setWidget(self._form_container)
        self._main_layout.addWidget(scroll)

        # 子类在此添加表单项
        self.setup_form()

        # 标准按钮（确定/取消）
        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._button_box.accepted.connect(self._on_accept)
        self._button_box.rejected.connect(self.reject)
        self._main_layout.addWidget(self._button_box)

    def setup_form(self):
        """子类重写此方法添加表单项"""
        pass

    def add_form_row(self, label_text: str, widget: QWidget):
        """添加一行表单（标签 + 控件）"""
        label = QLabel(label_text)
        self._form_layout.addRow(label, widget)

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