"""
树形控件分支箭头样式 - 使用 QProxyStyle 绘制线条 chevron 箭头
矢量绘制，在任何 DPI 下都清晰锐利
"""
from PyQt6.QtWidgets import QProxyStyle
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtCore import Qt, QPointF


class TreeBranchStyle(QProxyStyle):
    """自定义树形分支样式 - 绘制线条 chevron 箭头（> 和 v）"""

    def _selected_chevron_color(self) -> QColor:
        """选中态 chevron 颜色：跟随当前主题的 selected_text。
        该色在亮色/深色主题下都已在选中背景上保证可读对比度。
        取不到主题时回退到深色（在浅蓝选中底上仍清晰）。
        """
        try:
            from svd_tool.config.styles import get_style_scheme
            hex_color = get_style_scheme().colors.selected_text
            return QColor(hex_color)
        except Exception:
            return QColor("#1A1A1A")

    def drawPrimitive(self, element, option, painter, widget):
        """重写原始绘制方法"""
        from PyQt6.QtWidgets import QStyle
        
        if element == QStyle.PrimitiveElement.PE_IndicatorBranch:
            state = option.state
            has_children = state & QStyle.StateFlag.State_Children
            is_open = state & QStyle.StateFlag.State_Open
            
            if has_children:
                rect = option.rect
                
                # 根据状态选择颜色。
                # 关键：选中态不能硬编码蓝色——选中行有自己的背景色（亮色浅蓝、
                # 深色深蓝 #264F78），蓝色箭头会在选中背景上融入而"消失"。
                # 改为读取当前主题的 selected_text（亮色 #1A1A1A / 深色 #FFFFFF），
                # 它本就是为保证在选中背景上可读而设计的对比色。
                if state & QStyle.StateFlag.State_Selected:
                    color = self._selected_chevron_color()
                elif state & QStyle.StateFlag.State_MouseOver:
                    color = QColor("#333333")
                else:
                    color = QColor("#595959")
                
                # 计算中心点（对齐到 0.5 像素，使线条更锐利）
                cx = rect.x() + rect.width() / 2.0
                cy = rect.y() + rect.height() / 2.0
                
                # chevron 尺寸（根据分支区域自适应）
                sz = min(rect.width(), rect.height()) / 6.0
                if sz < 2.0:
                    sz = 2.0
                
                pen_width = max(1.0, sz / 3.0)
                
                if painter is None:
                    super().drawPrimitive(element, option, painter, widget)
                    return
                
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