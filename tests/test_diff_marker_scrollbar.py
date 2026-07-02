"""DiffMarkerScrollBar 单元测试：行→像素映射、点击命中检测、信号发射。

不依赖 GUI 显示（QApplication offscreen），验证核心逻辑正确性。
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint, QPointF, QEvent
from PyQt6.QtGui import QMouseEvent

from svd_tool.ui.widgets.diff_marker_scrollbar import DiffMarkerScrollBar

app = QApplication.instance() or QApplication(sys.argv)


def test_set_and_clear_markers():
    sb = DiffMarkerScrollBar()
    sb.setRange(0, 100)
    sb.setPageStep(20)
    sb.resize(20, 400)
    sb.set_markers([(0, 'added'), (50, 'modified'), (100, 'removed')], total_lines=100)
    assert len(sb._markers) == 3
    assert sb._total_lines == 100
    sb.clear_markers()
    assert sb._markers == []
    assert sb._total_lines == 0


def test_line_to_pixel_mapping_monotonic_and_boundary():
    sb = DiffMarkerScrollBar()
    sb.setRange(0, 100)
    sb.setPageStep(20)
    sb.resize(20, 400)
    sb.set_markers([(0, 'm'), (50, 'm'), (99, 'm')], total_lines=100)
    groove = sb._groove_rect()
    y0 = sb._line_to_y(0, groove)
    y99 = sb._line_to_y(99, groove)
    assert abs(y0 - groove.top()) < 2, "首行应接近 groove 顶部"
    assert abs(y99 - groove.bottom()) < 2, "末行应接近 groove 底部"
    assert sb._line_to_y(10, groove) <= sb._line_to_y(50, groove) <= sb._line_to_y(90, groove)


def test_effective_total_fallback():
    sb = DiffMarkerScrollBar()
    sb.setRange(0, 80)
    sb.setPageStep(20)
    sb._total_lines = 0
    # 未显式给 total_lines 时用 maximum+pageStep+1 估算
    assert sb._effective_total() == 101


def test_marker_hit_detection():
    sb = DiffMarkerScrollBar()
    sb.setRange(0, 99)
    sb.setPageStep(1)
    sb.resize(20, 400)
    sb.set_markers([(10, 'modified'), (90, 'added')], total_lines=100)
    g = sb._groove_rect()
    x_hit = g.right() - 2
    # 命中两个标记
    assert sb._marker_at(QPoint(int(x_hit), int(sb._line_to_y(10, g)))) == 10
    assert sb._marker_at(QPoint(int(x_hit), int(sb._line_to_y(90, g)))) == 90
    # 中点(50行)远离两标记（容差8px内才命中）
    y50 = sb._line_to_y(50, g)
    d10 = abs(sb._line_to_y(10, g) - y50)
    d90 = abs(sb._line_to_y(90, g) - y50)
    if d10 > 8 and d90 > 8:
        assert sb._marker_at(QPoint(int(x_hit), int(y50))) is None


def test_marker_clicked_signal():
    sb = DiffMarkerScrollBar()
    sb.setRange(0, 99)
    sb.setPageStep(1)
    sb.resize(20, 400)
    sb.set_markers([(10, 'modified')], total_lines=100)
    fired = []
    sb.marker_clicked.connect(lambda ln: fired.append(ln))
    g = sb._groove_rect()
    x_hit = g.right() - 2
    y10 = sb._line_to_y(10, g)
    ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(x_hit, y10), QPointF(x_hit, y10),
                     Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    sb.mousePressEvent(ev)
    assert fired == [10]


if __name__ == "__main__":
    test_set_and_clear_markers()
    test_line_to_pixel_mapping_monotonic_and_boundary()
    test_effective_total_fallback()
    test_marker_hit_detection()
    test_marker_clicked_signal()
    print("ALL DiffMarkerScrollBar TESTS PASSED")
