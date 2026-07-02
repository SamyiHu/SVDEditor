"""带差异标记的垂直滚动条。

在 SVD 对比的"原始 XML 对比"视图中使用：滚动条上叠加差异色块标记
（增/删/改不同色），点击标记可跳转到对应差异行。

设计要点：
- 继承 QScrollBar，重写 paintEvent：先 super().paintEvent 保留原生外观，
  再用 QPainter 叠加色块标记。这样滑块、滑道、QSS 样式全部保留，只多画标记。
- 行号→像素映射用 QStyle.subControlRect 取滑道(SC_ScrollBarGroove)矩形，
  保证标记与滑块在同一坐标系（缩放/换主题都能对齐）。
- 点击命中标记发 marker_clicked(line_index) 信号，由对话框决定如何跳转
  （通常平滑滚动到该行）。
"""
from typing import List, Tuple, Optional

from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QScrollBar, QStyle, QStyleOptionSlider


class DiffMarkerScrollBar(QScrollBar):
    """垂直滚动条，叠加差异色块标记，点击标记可跳转。"""

    # 点击某标记时发出，携带对应的行号(从 0 起)
    marker_clicked = pyqtSignal(int)

    # 各类差异的颜色（与对话框 _line_bg_color 的配色呼应）
    _COLORS = {
        "added":    QColor(0x4c, 0xaf, 0x50),   # 绿
        "removed":  QColor(0xe5, 0x39, 0x35),   # 红
        "modified": QColor(0xfb, 0x8c, 0x00),   # 橙黄
        "sep":      QColor(0xb0, 0xb0, 0xb0),   # 灰(分隔)
    }

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Vertical, parent)
        self._markers: List[Tuple[int, str]] = []  # [(line_index, category)]
        self._total_lines: int = 0  # 文档总行数，用于行→像素映射
        self._click_tolerance: int = 6  # 点击命中容差(像素)

    def set_markers(self, markers: List[Tuple[int, str]], total_lines: int = 0) -> None:
        """设置差异标记。

        Args:
            markers: [(line_index, category)]，line_index 从 0 起；
                     category ∈ {"added","removed","modified","sep"}
            total_lines: 文档总行数；<=0 时用滚动条 maximum+pageStep 估算。
        """
        self._markers = list(markers) if markers else []
        self._total_lines = max(total_lines, 0)
        self.update()

    def clear_markers(self) -> None:
        self._markers = []
        self._total_lines = 0
        self.update()

    # ------------------------------------------------------------------
    # 行号 ↔ 像素 映射
    # ------------------------------------------------------------------

    def _groove_rect(self) -> QRect:
        """取滑道(Groove)矩形——滑块在其中移动的区域。"""
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        # subControlRect 需要 style()，QScrollBar 自带 style()
        rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_ScrollBar, opt,
            QStyle.SubControl.SC_ScrollBarGroove, self)
        return rect

    def _line_to_y(self, line_index: int, groove: QRect) -> float:
        """行号 → 滑道内的像素 y（中心）。"""
        total = self._effective_total()
        if total <= 1:
            return groove.top()
        frac = line_index / float(total - 1) if total > 1 else 0.0
        return groove.top() + frac * groove.height()

    def _effective_total(self) -> int:
        """有效的总行数：优先用显式传入的，否则用滚动条范围估算。"""
        if self._total_lines and self._total_lines > 0:
            return self._total_lines
        # 滚动条 value 范围 [0, maximum]，pageStep 是可见页大小，
        # 文档总行数 ≈ maximum + pageStep
        return self.maximum() + self.pageStep() + 1

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        """先画原生滚动条，再叠加差异标记色块。"""
        super().paintEvent(event)

        if not self._markers:
            return

        groove = self._groove_rect()
        if groove.height() < 4:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setPen(Qt.PenStyle.NoPen)

        # 标记画在滑道右侧约 1/3 宽度内，不挡住滑块整体（滑块居中偏左占主要空间）。
        # 用较细的色条（宽 4px，高 3px），紧贴滑道右边缘。
        bar_w = max(4, min(8, groove.width() // 3))
        bar_h = 3
        x = groove.right() - bar_w + 1  # 贴右边缘

        for line_idx, category in self._markers:
            color = self._COLORS.get(category)
            if color is None:
                continue
            y = self._line_to_y(line_idx, groove)
            rect = QRect(int(x), int(y - bar_h / 2), bar_w, bar_h)
            # 限制在滑道范围内
            if rect.top() < groove.top():
                rect.moveTop(groove.top())
            if rect.bottom() > groove.bottom():
                rect.moveBottom(groove.bottom())
            painter.setBrush(color)
            painter.drawRect(rect)

        painter.end()

    # ------------------------------------------------------------------
    # 点击命中 → 跳转
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        """点击命中标记则发 marker_clicked，否则正常处理（拖滑块等）。

        优先级：滑块拖动 > 标记跳转。若点击落在滑块(handle)上，绝不劫持为跳转，
        保证滑块随时可拖动，避免"点红色标记却误触跳转、失去滑动能力"的冲突。
        """
        if event.button() == Qt.MouseButton.LeftButton and self._markers:
            # 先排除滑块区域：点滑块就交给父类处理拖动
            if not self._is_on_handle(event.position().toPoint()):
                hit = self._marker_at(event.position().toPoint())
                if hit is not None:
                    self.marker_clicked.emit(hit)
                    event.accept()
                    return
        super().mousePressEvent(event)

    def _is_on_handle(self, pos: QPoint) -> bool:
        """判断点是否落在滑块(handle)上。用 QStyle 取 SC_ScrollBarSlider 矩形。"""
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        handle = self.style().subControlRect(
            QStyle.ComplexControl.CC_ScrollBar, opt,
            QStyle.SubControl.SC_ScrollBarSlider, self)
        return handle.contains(pos)

    def _marker_at(self, pos: QPoint) -> Optional[int]:
        """找到鼠标位置命中的标记对应的行号（容差内）。无则 None。"""
        groove = self._groove_rect()
        bar_w = max(4, min(8, groove.width() // 3))
        x = groove.right() - bar_w + 1
        # 只在标记条水平范围内才判定（让用户仍可点滑块本身）
        if not (x - self._click_tolerance <= pos.x() <= x + bar_w + self._click_tolerance):
            return None

        total = self._effective_total()
        if total <= 1:
            return None
        # pos.y → 行号
        if groove.height() <= 0:
            return None
        frac = (pos.y() - groove.top()) / float(groove.height())
        frac = max(0.0, min(1.0, frac))
        target_line = int(round(frac * (total - 1)))

        # 找最近的、在垂直容差内的标记
        best = None
        best_dy = None
        tol_y = max(self._click_tolerance, 8)
        for line_idx, category in self._markers:
            my = self._line_to_y(line_idx, groove)
            dy = abs(my - pos.y())
            if dy <= tol_y and (best_dy is None or dy < best_dy):
                best_dy = dy
                best = line_idx
        return best
