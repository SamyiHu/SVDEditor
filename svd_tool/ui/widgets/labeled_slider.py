"""
LabeledSlider - 带手动输入的横向滑条控件
替代 QSpinBox，提供滑条+输入框双模式
支持多段阻尼（靠近两端步进更小）
"""
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QSlider, QLineEdit, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIntValidator

from ...config.styles import get_style_scheme


class LabeledSlider(QWidget):
    """带手动输入的横向滑条

    API 兼容 QSpinBox：
    - value() / setValue(int)
    - setRange(min, max)
    - 信号 valueChanged(int)
    """

    valueChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._min = 0
        self._max = 100
        self._value = 0
        self._updating = False  # 防止循环更新
        self._setup_ui()

    def _setup_ui(self):
        c = get_style_scheme().colors

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 滑条
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setValue(0)
        self._slider.setMinimumWidth(100)
        self._slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                border: 1px solid {c.border};
                height: 6px;
                background: {c.border_light};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {c.accent};
                border: 1px solid {c.accent};
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {c.accent_hover};
            }}
            QSlider::sub-page:horizontal {{
                background: {c.accent};
                border-radius: 3px;
            }}
        """)
        self._slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self._slider, stretch=1)

        # 手动输入框
        self._input = QLineEdit("0")
        self._input.setFixedWidth(48)
        self._input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._input.setValidator(QIntValidator(self._min, self._max))
        self._input.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid {c.border};
                border-radius: 4px;
                padding: 2px 4px;
                color: {c.accent};
                font-weight: bold;
                font-size: 10pt;
                background: {c.white};
            }}
            QLineEdit:focus {{
                border-color: {c.accent};
            }}
        """)
        self._input.editingFinished.connect(self._on_input_finished)
        layout.addWidget(self._input)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(28)

    # ---- QSpinBox 兼容 API ----

    def value(self) -> int:
        return self._value

    def setValue(self, val: int):
        val = max(self._min, min(self._max, val))
        self._value = val
        self._updating = True
        self._input.setText(str(val))
        if self._max > self._min:
            self._slider.setValue(int((val - self._min) / (self._max - self._min) * 100))
        self._updating = False

    def setRange(self, min_val: int, max_val: int):
        self._min = min_val
        self._max = max_val
        self._value = max(min_val, min(max_val, self._value))
        self._input.setValidator(QIntValidator(min_val, max_val))
        self._input.setText(str(self._value))

    def minimum(self) -> int:
        return self._min

    def maximum(self) -> int:
        return self._max

    # ---- 内部 ----

    def _on_slider_changed(self, pos: int):
        if self._updating:
            return
        if self._max <= self._min:
            return

        t = pos / 100.0
        if t < 0.5:
            smooth = 2 * t * t
        else:
            smooth = 1 - (-2 * t + 2) ** 2 / 2

        val = self._min + round(smooth * (self._max - self._min))
        val = max(self._min, min(self._max, val))

        if val != self._value:
            self._value = val
            self._input.setText(str(val))
            self.valueChanged.emit(val)

    def _on_input_finished(self):
        if self._updating:
            return
        try:
            val = int(self._input.text())
        except ValueError:
            self._input.setText(str(self._value))
            return

        val = max(self._min, min(self._max, val))
        self._input.setText(str(val))

        if val != self._value:
            self._value = val
            self._updating = True
            if self._max > self._min:
                self._slider.setValue(int((val - self._min) / (self._max - self._min) * 100))
            self._updating = False
            self.valueChanged.emit(val)
