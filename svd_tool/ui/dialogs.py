# svd_tool/ui/dialogs.py (完整修复版本)

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QDialogButtonBox,
    QComboBox, QSpinBox, QTextEdit, QMessageBox,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal

from ..core.validators import Validator, ValidationError


class BaseEditDialog(QDialog):
    """基础编辑对话框 - 简化版本"""
    
    def __init__(self, parent=None, title="编辑"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.result_data = None
        
        # 创建主布局
        self.main_layout = QVBoxLayout(self)
        
        # 表单区域
        self.form_widget = QWidget()
        self.form_layout = QVBoxLayout(self.form_widget)
        self.main_layout.addWidget(self.form_widget)
        
        # 按钮区域
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.on_accept)
        self.button_box.rejected.connect(self.reject)
        self.main_layout.addWidget(self.button_box)
        
        # 子类应该重写此方法来添加表单内容
        self.setup_form()
    
    def setup_form(self):
        """设置表单内容 - 子类必须重写此方法"""
        pass
    
    def on_accept(self):
        """接受按钮点击事件"""
        try:
            self.validate_input()
            self.collect_data()
            self.accept()
        except ValidationError as e:
            QMessageBox.warning(self, "输入错误", str(e))
        except Exception as e:
            QMessageBox.critical(self, "错误", f"发生未知错误: {str(e)}")
    
    def validate_input(self):
        """验证输入"""
        raise NotImplementedError("子类必须实现validate_input方法")
    
    def collect_data(self):
        """收集数据"""
        raise NotImplementedError("子类必须实现collect_data方法")
    
    def add_form_row(self, label_text, widget):
        """添加表单行"""
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        
        label = QLabel(label_text)
        label.setMinimumWidth(100)
        row_layout.addWidget(label)
        row_layout.addWidget(widget)
        row_layout.addStretch()
        
        self.form_layout.addWidget(row_widget)