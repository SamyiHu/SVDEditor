"""
树形控件分支箭头样式 - 使用 QProxyStyle 绘制线条 chevron 箭头
矢量绘制，在任何 DPI 下都清晰锐利
"""
from PyQt6.QtWidgets import QProxyStyle
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtCore import Qt, QPointF


class TreeBranchStyle(QProxyStyle):
    """自定义树形分支样式 - 绘制线条 chevron 箭头（> 和 v）"""
    
    def drawPrimitive(self, element, option, painter, widget):
        """重写原始绘制方法"""
        from PyQt6.QtWidgets import QStyle
        
        if element == QStyle.PrimitiveElement.PE_IndicatorBranch:
            state = option.state
            has_children = state & QStyle.StateFlag.State_Children
            is_open = state & QStyle.StateFlag.State_Open
            
            if has_children:
                rect = option.rect
                
                # 根据状态选择颜色
                if state & QStyle.StateFlag.State_Selected:
                    color = QColor("#4A90D9")
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