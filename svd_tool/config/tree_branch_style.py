"""
树形控件分支箭头样式 - 使用 QProxyStyle 绘制线条 chevron 箭头
矢量绘制，在任何 DPI 下都清晰锐利
"""
from PyQt6.QtWidgets import QProxyStyle
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtCore import Qt, QPointF, QRectF


def draw_chevron(painter: QPainter, rect: QRectF, is_open: bool,
                 color: QColor):
    """在给定 rect 中心绘制 chevron 箭头（> 折叠 / v 展开）。
    提取为模块级函数，供 QProxyStyle.drawPrimitive 和 DeviceTreeView.paintEvent
    复用——后者用于解决"选中行箭头被 item:selected 背景覆盖"的问题
    （QSS 下 Qt 对选中行的 branch 不调 proxy style，需 paintEvent 补画）。
    """
    cx = rect.x() + rect.width() / 2.0
    cy = rect.y() + rect.height() / 2.0
    sz = min(rect.width(), rect.height()) / 6.0
    if sz < 2.0:
        sz = 2.0
    pen_width = max(1.0, sz / 3.0)

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(color, pen_width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if is_open:
        # 展开状态：向下 chevron v
        painter.drawLine(QPointF(cx - sz, cy - sz * 0.4), QPointF(cx, cy + sz * 0.6))
        painter.drawLine(QPointF(cx, cy + sz * 0.6), QPointF(cx + sz, cy - sz * 0.4))
    else:
        # 折叠状态：向右 chevron >
        painter.drawLine(QPointF(cx - sz * 0.4, cy - sz), QPointF(cx + sz * 0.6, cy))
        painter.drawLine(QPointF(cx + sz * 0.6, cy), QPointF(cx - sz * 0.4, cy + sz))

    painter.restore()


def selected_chevron_color() -> QColor:
    """选中态 chevron 颜色：跟随当前主题的 selected_text。
    该色在亮色/深色主题下都已在选中背景上保证可读对比度。
    """
    try:
        from svd_tool.config.styles import get_style_scheme
        return QColor(get_style_scheme().colors.selected_text)
    except Exception:
        return QColor("#1A1A1A")


class TreeBranchStyle(QProxyStyle):
    """自定义树形分支样式 - 绘制线条 chevron 箭头（> 和 v）"""

    def drawPrimitive(self, element, option, painter, widget):
        """重写原始绘制方法。
        注意：QSS 含 QTreeView::branch 规则时，Qt 对选中行的 branch 不调用本方法
        （走 QSS 路径），故选中行箭头由 DeviceTreeView.paintEvent 用 draw_chevron 补画。
        本方法仍负责绘制非选中行的箭头。
        """
        from PyQt6.QtWidgets import QStyle
        
        if element == QStyle.PrimitiveElement.PE_IndicatorBranch:
            state = option.state
            has_children = state & QStyle.StateFlag.State_Children
            is_open = state & QStyle.StateFlag.State_Open
            
            if has_children:
                if painter is None:
                    super().drawPrimitive(element, option, painter, widget)
                    return
                # 选颜色
                if state & QStyle.StateFlag.State_Selected:
                    color = selected_chevron_color()
                elif state & QStyle.StateFlag.State_MouseOver:
                    color = QColor("#333333")
                else:
                    color = QColor("#595959")
                draw_chevron(painter, option.rect, bool(is_open), color)
                return

        super().drawPrimitive(element, option, painter, widget)


# 全局单例
_tree_branch_style = None


def get_tree_branch_style():
    """获取树形分支样式单例"""
    global _tree_branch_style
    if _tree_branch_style is None:
        _tree_branch_style = TreeBranchStyle()
    return _tree_branch_style


def apply_tree_branch_style(tree_widget):
    """为树控件应用分支箭头样式"""
    style = get_tree_branch_style()
    tree_widget.setStyle(style)