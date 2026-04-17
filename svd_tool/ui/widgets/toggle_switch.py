"""
ToggleSwitch - iOS 风格滑动开关控件
替代 QCheckBox，提供更现代的视觉效果
"""
from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, pyqtProperty, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QColor, QFont, QFontMetrics


class ToggleSwitch(QWidget):
    """iOS 风格滑动开关

    API 兼容 QCheckBox：
    - setChecked(bool) / isChecked()
    - 信号 toggled(bool), stateChanged(int)
    - 支持标签文字（绘制在开关右侧）
    """

    toggled = pyqtSignal(bool)
    stateChanged = pyqtSignal(int)

    # 尺寸参数
    TRACK_WIDTH = 36
    TRACK_HEIGHT = 20
    HANDLE_MARGIN = 2
    HANDLE_SIZE = 16

    def __init__(self, label: str = "", parent=None):
        super().__init__(parent)
        self._checked = False
        self._label = label
        self._handle_pos_val = 0.0

        self._track_color_off = QColor(189, 189, 189)
        self._track_color_on = QColor(74, 144, 217)
        self._handle_color = QColor(255, 255, 255)

        # 计算带标签时的宽度
        if self._label:
            fm = QFontMetrics(QFont("Microsoft YaHei", 9))
            text_w = fm.horizontalAdvance(self._label)
            total_w = self.TRACK_WIDTH + 6 + text_w + 4
        else:
            total_w = self.TRACK_WIDTH

        self.setFixedSize(total_w, self.TRACK_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # ---- Qt 动画属性（必须用 pyqtProperty） ----

    @pyqtProperty(float)
    def handlePos(self) -> float:
        return self._handle_pos_val

    @handlePos.setter
    def handlePos(self, pos: float):
        self._handle_pos_val = pos
        self.update()

    # ---- QCheckBox 兼容 API ----

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool, animate: bool = False):
        if self._checked != checked:
            self._checked = checked
            if animate:
                self._start_animation(1.0 if checked else 0.0)
            else:
                self._handle_pos_val = 1.0 if checked else 0.0
            self.toggled.emit(checked)
            self.stateChanged.emit(1 if checked else 0)
            self.update()

    def checkState(self):
        return Qt.CheckState.Checked if self._checked else Qt.CheckState.Unchecked

    def setCheckState(self, state):
        self.setChecked(state == Qt.CheckState.Checked)

    def text(self) -> str:
        return self._label

    # ---- 内部方法 ----

    def _start_animation(self, target: float):
        # 持有引用防止 GC，动画结束后自动清理
        self._anim = QPropertyAnimation(self, b"handlePos")
        self._anim.setDuration(120)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim.setStartValue(self._handle_pos_val)
        self._anim.setEndValue(target)
        self._anim.start()

    # ---- 事件 ----

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._checked = not self._checked
            self._start_animation(1.0 if self._checked else 0.0)
            self.toggled.emit(self._checked)
            self.stateChanged.emit(1 if self._checked else 0)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.TRACK_WIDTH
        h = self.TRACK_HEIGHT
        r = h / 2

        # 轨道背景
        track_color = self._track_color_on if self._checked else self._track_color_off
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(QRectF(0, 0, w, h), r, r)

        # 滑块
        margin = self.HANDLE_MARGIN
        handle_d = self.HANDLE_SIZE
        x_range = w - 2 * margin - handle_d
        handle_x = margin + self._handle_pos_val * x_range

        # 阴影
        painter.setBrush(QColor(0, 0, 0, 30))
        painter.drawRoundedRect(
            QRectF(handle_x + 1, margin + 1, handle_d, handle_d),
            handle_d / 2, handle_d / 2)
        # 本体
        painter.setBrush(self._handle_color)
        painter.drawRoundedRect(
            QRectF(handle_x, margin, handle_d, handle_d),
            handle_d / 2, handle_d / 2)

        # 标签文字
        if self._label:
            painter.setPen(QColor(90, 90, 90))
            painter.setFont(QFont("Microsoft YaHei", 9))
            text_x = w + 6
            text_y = h / 2 + 3  # 垂直居中
            painter.drawText(int(text_x), int(text_y), self._label)

        painter.end()
