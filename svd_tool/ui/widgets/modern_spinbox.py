"""
ModernSpinBox - 现代风格的数字调整控件
继承 QSpinBox，通过全局样式美化，API 完全兼容
"""
from PyQt6.QtWidgets import QSpinBox
from PyQt6.QtCore import Qt


class ModernSpinBox(QSpinBox):
    """现代风格 SpinBox

    API 完全兼容 QSpinBox，无需修改调用代码。
    样式由全局样式表统一控制，这里只设置默认行为。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumWidth(70)
        self.setMinimumHeight(28)
