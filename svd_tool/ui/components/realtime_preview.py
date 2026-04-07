"""
实时SVD预览组件
提供实时XML预览和双向同步选择功能
支持折叠/展开、双向同步选择、可视化框选
"""
import re
import logging
from typing import Dict, Any, Optional, Tuple, List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QPlainTextEdit, QFrame, QLabel, QMessageBox, QTextEdit, QScrollBar
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRegularExpression, QMargins, QPoint, QRect
from PyQt6.QtGui import (
    QTextCursor, QTextCharFormat, QColor, QSyntaxHighlighter,
    QTextDocument, QFont, QTextBlockFormat, QMouseEvent, QPainter,
    QTextBlock, QPaintEvent, QPen, QBrush, QTextBlockUserData, QPalette
)

from ...core.svd_generator import SVDGenerator
from ...utils.helpers import pretty_xml
from ...i18n.i18n import t


class XMLHighlighter(QSyntaxHighlighter):
    """XML语法高亮器"""
    
    def __init__(self, document: QTextDocument):
        super().__init__(document)
        
        # 定义高亮规则
        self.highlighting_rules = []
        
        # XML标签
        tag_format = QTextCharFormat()
        tag_format.setForeground(QColor("#0000FF"))
        tag_format.setFontWeight(QFont.Weight.Bold)
        self.highlighting_rules.append((re.compile(r'<[^>]+>'), tag_format))
        
        # 属性名
        attr_format = QTextCharFormat()
        attr_format.setForeground(QColor("#FF00FF"))
        self.highlighting_rules.append((re.compile(r'\s\w+='), attr_format))
        
        # 属性值
        value_format = QTextCharFormat()
        value_format.setForeground(QColor("#FF0000"))
        self.highlighting_rules.append((re.compile(r'"[^"]*"'), value_format))
        
        # 注释
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#008000"))
        comment_format.setFontItalic(True)
        self.highlighting_rules.append((re.compile(r'<!--.*?-->', re.DOTALL), comment_format))
    
    def highlightBlock(self, text: str):
        """高亮文本块"""
        for pattern, format in self.highlighting_rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), format)


class HighlightedTextEdit(QPlainTextEdit):
    """支持高亮显示和折叠功能的文本编辑器"""
    
    # 信号定义
    fold_clicked = pyqtSignal(str, str, str, bool)  # (element_type, peripheral_name, element_name, is_expanded)
    element_clicked = pyqtSignal(str, str, str)  # (element_type, peripheral_name, element_name)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.folded_elements = set()  # {(element_type, peripheral_name, element_name)}
        self.element_line_ranges = {}  # {(element_type, peripheral_name, element_name): (start_line, end_line)}
        self.fold_markers = {}  # {line_number: (element_type, peripheral_name, element_name)}
        self.highlight_ranges = {}  # {(element_type, peripheral_name, element_name): (start_line, end_line)}
        
        # 多层级高亮支持
        self.highlight_keys = {
            'peripheral': None,  # 当前选中的外设
            'register': None,    # 当前选中的寄存器
            'field': None        # 当前选中的位域
        }
        self.current_highlight_key = None  # 当前高亮的元素key（用于兼容）
        self.setMouseTracking(True)
        
        # 元素层级结构（用于折叠块显示）
        self.element_hierarchy = {}  # {child_key: parent_key}
        self.element_children = {}  # {parent_key: [child_keys]}
        
        # 高亮颜色配置 - 更鲜明的颜色和边框
        self.highlight_colors = {
            'peripheral': QColor(255, 183, 77, 50),    # 暖橙色半透明背景
            'register': QColor(66, 165, 245, 50),      # 清新蓝色半透明背景
            'field': QColor(102, 187, 106, 50),        # 翠绿色半透明背景
            'interrupt': QColor(239, 154, 154, 50)     # 柔粉色半透明背景
        }
        # 高亮边框颜色 - 更深且不透明
        self.highlight_border_colors = {
            'peripheral': QColor(255, 152, 0, 180),    # 深橙色边框
            'register': QColor(33, 150, 243, 180),     # 深蓝色边框
            'field': QColor(76, 175, 80, 180),         # 深绿色边框
            'interrupt': QColor(239, 83, 80, 180)      # 深粉色边框
        }
        # 高亮标签颜色
        self.highlight_label_colors = {
            'peripheral': QColor(255, 152, 0),         # 橙色标签
            'register': QColor(33, 150, 243),          # 蓝色标签
            'field': QColor(76, 175, 80),              # 绿色标签
            'interrupt': QColor(239, 83, 80)           # 粉色标签
        }
    
    def set_folded_elements(self, folded_elements: set):
        """设置折叠元素集合"""
        self.folded_elements = folded_elements
        self._update_block_visibility()
    
    def _update_block_visibility(self):
        """根据折叠状态更新文本块的可见性"""
        doc = self.document()
        if not doc:
            return
        
        # 首先显示所有文本块
        block = doc.begin()
        while block.isValid():
            block.setVisible(True)
            block = block.next()
        
        # 隐藏被折叠的元素对应的文本块（保留前两行和最后一行）
        for key in self.folded_elements:
            if key in self.element_line_ranges:
                start_line, end_line = self.element_line_ranges[key]
                # 隐藏从 start_line + 2 到 end_line - 1 的所有文本块（保留前两行和最后一行）
                for line_num in range(start_line + 2, end_line):
                    block = doc.findBlockByNumber(line_num - 1)
                    if block.isValid():
                        block.setVisible(False)
        
        # 处理嵌套折叠：当外设被折叠时，隐藏其内部的所有寄存器和位域
        if hasattr(self, 'element_children'):
            for peripheral_key, children in self.element_children.items():
                if peripheral_key in self.folded_elements:
                    # 外设被折叠，隐藏其内部的所有子元素
                    for child_key in children:
                        if child_key in self.element_line_ranges:
                            child_start_line, child_end_line = self.element_line_ranges[child_key]
                            # 隐藏子元素的所有行
                            for line_num in range(child_start_line, child_end_line + 1):
                                block = doc.findBlockByNumber(line_num - 1)
                                if block.isValid():
                                    block.setVisible(False)
        
        # 重新计算文档布局
        doc.adjustSize()
        self.update()
    
    def set_element_line_ranges(self, element_line_ranges: dict):
        """设置元素行范围"""
        self.element_line_ranges = element_line_ranges
        self._update_block_visibility()
    
    def set_element_children(self, element_children: dict):
        """设置元素子级关系"""
        self.element_children = element_children
        self.update()
    
    def set_element_ranges(self, element_ranges: dict):
        """设置元素范围（用于折叠块绘制）"""
        self.element_ranges = element_ranges
        self.update()
    
    def set_fold_markers(self, fold_markers: dict):
        """设置折叠标记"""
        self.fold_markers = fold_markers
        self.update()
    
    def set_highlight_ranges(self, highlight_ranges: dict):
        """设置高亮范围"""
        self.highlight_ranges = highlight_ranges
        self.update()
    
    def set_current_highlight(self, element_type: str, peripheral_name: str, element_name: str):
        """设置当前高亮的元素"""
        key = (element_type, peripheral_name, element_name)
        
        # 根据元素类型清除其他类型的高亮键
        if element_type == 'field':
            # 选中位域，清除寄存器和外设的高亮键
            self.highlight_keys['register'] = None
            self.highlight_keys['peripheral'] = None
        elif element_type == 'register':
            # 选中寄存器，清除位域和外设的高亮键
            self.highlight_keys['field'] = None
            self.highlight_keys['peripheral'] = None
        elif element_type == 'peripheral':
            # 选中外设，清除位域和寄存器的高亮键
            self.highlight_keys['field'] = None
            self.highlight_keys['register'] = None
        
        # 更新多层级高亮
        if element_type in self.highlight_keys:
            self.highlight_keys[element_type] = key
        
        # 更新当前高亮键（用于兼容）
        self.current_highlight_key = key
        
        # 注意：滚动由外部 _jump_to_line() 统一处理（带动画），
        # 这里不执行 centerCursor() 避免冲突
        
        self.update()
    
    def set_highlight_by_type(self, element_type: str, key: tuple):
        """根据元素类型设置高亮"""
        if element_type in self.highlight_keys:
            self.highlight_keys[element_type] = key
        self.update()
    
    def clear_highlight_by_type(self, element_type: str):
        """清除指定类型的高亮"""
        if element_type in self.highlight_keys:
            self.highlight_keys[element_type] = None
        self.update()
    
    def clear_highlight(self):
        """清除高亮"""
        self.current_highlight_key = None
        # 清除所有类型的高亮键
        self.highlight_keys['peripheral'] = None
        self.highlight_keys['register'] = None
        self.highlight_keys['field'] = None
        self.update()
    
    def mousePressEvent(self, event: QMouseEvent):
        """处理鼠标点击事件"""
        # 检查是否点击了折叠标记区域
        cursor = self.cursorForPosition(event.pos())
        line_num = cursor.blockNumber() + 1
        
        # 检查是否点击了外设块区域
        if hasattr(self, 'element_children') and hasattr(self, 'element_ranges'):
            for peripheral_key, children in self.element_children.items():
                if not children:
                    continue
                
                if peripheral_key not in self.element_ranges:
                    continue
                
                start_line, end_line = self.element_ranges[peripheral_key]
                
                # 获取外设块的起始和结束位置
                start_block = self.document().findBlockByNumber(start_line - 1)
                end_block = self.document().findBlockByNumber(end_line - 1)
                
                if not start_block.isValid() or not end_block.isValid():
                    continue
                
                start_rect = self.blockBoundingGeometry(start_block).translated(self.contentOffset())
                end_rect = self.blockBoundingGeometry(end_block).translated(self.contentOffset())
                
                # 计算外设块的位置
                block_x = int(start_rect.left())
                block_y = int(start_rect.top())
                block_width = int(self.viewport().width() - start_rect.left())
                block_height = int(end_rect.bottom() - start_rect.top())
                
                # 检查点击是否在外设块内
                click_x = event.pos().x()
                click_y = event.pos().y()
                
                if (block_x <= click_x <= block_x + block_width and
                    block_y <= click_y <= block_y + block_height):
                    element_type, peripheral_name, _ = peripheral_key
                    
                    # 切换外设折叠状态
                    if peripheral_key in self.folded_elements:
                        self.folded_elements.remove(peripheral_key)
                        is_expanded = True
                    else:
                        self.folded_elements.add(peripheral_key)
                        is_expanded = False
                    
                    # 发射信号
                    self.fold_clicked.emit(element_type, peripheral_name, peripheral_name, is_expanded)
                    
                    # 更新文本块可见性
                    self._update_block_visibility()
                    return
                
                # 检查是否点击了寄存器块区域
                if peripheral_key not in self.folded_elements:  # 外设未折叠
                    for register_key in children:
                        if register_key[0] != 'register':
                            continue
                        
                        if register_key not in self.element_ranges:
                            continue
                        
                        reg_start_line, reg_end_line = self.element_ranges[register_key]
                        
                        # 获取寄存器块的起始和结束位置
                        reg_start_block = self.document().findBlockByNumber(reg_start_line - 1)
                        reg_end_block = self.document().findBlockByNumber(reg_end_line - 1)
                        
                        if not reg_start_block.isValid() or not reg_end_block.isValid():
                            continue
                        
                        reg_start_rect = self.blockBoundingGeometry(reg_start_block).translated(self.contentOffset())
                        reg_end_rect = self.blockBoundingGeometry(reg_end_block).translated(self.contentOffset())
                        
                        # 计算寄存器块的位置（缩进20像素）
                        reg_block_x = int(reg_start_rect.left()) + 20
                        reg_block_y = int(reg_start_rect.top())
                        reg_block_width = int(self.viewport().width() - reg_start_rect.left() - 20)
                        reg_block_height = int(reg_end_rect.bottom() - reg_start_rect.top())
                        
                        # 检查点击是否在寄存器块内
                        if (reg_block_x <= click_x <= reg_block_x + reg_block_width and
                            reg_block_y <= click_y <= reg_block_y + reg_block_height):
                            element_type, peripheral_name, reg_name = register_key
                            
                            # 切换寄存器折叠状态
                            if register_key in self.folded_elements:
                                self.folded_elements.remove(register_key)
                                is_expanded = True
                            else:
                                self.folded_elements.add(register_key)
                                is_expanded = False
                            
                            # 发射信号
                            self.fold_clicked.emit(element_type, peripheral_name, reg_name, is_expanded)
                            
                            # 更新文本块可见性
                            self._update_block_visibility()
                            return
        
        # 检查是否点击了折叠标记区域（左侧箭头）
        if line_num in self.fold_markers:
            element_type, peripheral_name, element_name = self.fold_markers[line_num]
            if element_type in ['peripheral', 'register']:
                # 计算点击位置是否在折叠标记区域
                block = self.document().findBlockByNumber(line_num - 1)
                if block.isValid():
                    block_rect = self.blockBoundingGeometry(block).translated(self.contentOffset())
                    marker_x = 10
                    marker_y = int(block_rect.top() + block_rect.height() / 2)
                    marker_size = 16
                    
                    # 检查点击是否在标记区域内
                    if (abs(event.pos().x() - marker_x) < marker_size and
                        abs(event.pos().y() - marker_y) < marker_size):
                        key = (element_type, peripheral_name, element_name)
                        
                        # 切换外设折叠状态
                        if key in self.folded_elements:
                            self.folded_elements.remove(key)
                            is_expanded = True
                        else:
                            self.folded_elements.add(key)
                            is_expanded = False
                        
                        # 发射信号
                        self.fold_clicked.emit(element_type, peripheral_name, element_name, is_expanded)
                        
                        # 更新文本块可见性
                        self._update_block_visibility()
                        return
        
        # 检查是否点击了高亮区域
        if self.current_highlight_key and self.current_highlight_key in self.element_line_ranges:
            start_line, end_line = self.element_line_ranges[self.current_highlight_key]
            if start_line <= line_num <= end_line:
                element_type, peripheral_name, element_name = self.current_highlight_key
                self.element_clicked.emit(element_type, peripheral_name, element_name)
                return
        
        # 调用父类方法处理其他点击
        super().mousePressEvent(event)
    
    def paintEvent(self, event: QPaintEvent):
        """绘制折叠标记和高亮区域
        
        采用优先级策略（field > register > peripheral），只高亮最内层的元素，
        避免颜色叠加导致的可读性问题。
        """
        # 先调用父类的绘制
        super().paintEvent(event)
        
        # 获取可见区域
        visible_rect = event.rect()
        
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 使用 CompositionMode 避免影响鼠标点击事件
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        
        # 优先级策略：field > register > peripheral
        # 只高亮最内层的元素，避免颜色叠加
        priority_order = ['field', 'register', 'peripheral']
        selected_element = None
        selected_type = None
        
        for element_type in priority_order:
            key = self.highlight_keys.get(element_type)
            if key and key in self.element_line_ranges:
                selected_element = key
                selected_type = element_type
                break  # 找到最高优先级的元素后立即停止
        
        # 只绘制选中的元素
        if selected_element and selected_type:
            start_line, end_line = self.element_line_ranges[selected_element]
            
            # 获取颜色
            color = self.highlight_colors.get(selected_type, QColor(255, 255, 0, 80))
            
            # 绘制高亮背景
            start_block = self.document().findBlockByNumber(start_line - 1)
            end_block = self.document().findBlockByNumber(end_line - 1)
            
            if start_block.isValid() and end_block.isValid():
                start_rect = self.blockBoundingGeometry(start_block).translated(self.contentOffset())
                end_rect = self.blockBoundingGeometry(end_block).translated(self.contentOffset())
                
                # 检查是否在可见区域内
                if not visible_rect.intersects(QRect(int(start_rect.left()), int(start_rect.top()),
                                                   int(end_rect.right() - start_rect.left()),
                                                   int(end_rect.bottom() - start_rect.top()))):
                    pass  # 不在可见区域，跳过绘制
                else:
                    # 添加缝隙间距
                    gap = 4  # 缝隙大小
                    left = int(start_rect.left())
                    top = int(start_rect.top()) - gap
                    width = int(self.viewport().width() - start_rect.left())
                    height = int(end_rect.bottom() - start_rect.top()) + gap * 2
                    
                    # 计算高亮区域（添加缝隙）
                    highlight_rect = QRect(left, top, width, height)
                    
                    # 绘制圆角矩形背景（使用渐变效果）
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(color))
                    painter.drawRoundedRect(highlight_rect, 6, 6)
                    
                    # 绘制左侧色条（装饰线）
                    label_color = self.highlight_label_colors.get(selected_type, QColor("#FF9800"))
                    bar_rect = QRect(highlight_rect.left(), highlight_rect.top() + 2, 4, highlight_rect.height() - 4)
                    painter.setBrush(QBrush(label_color))
                    painter.drawRoundedRect(bar_rect, 2, 2)
                    
                    # 绘制边框（使用对应类型的边框颜色）
                    border_color = self.highlight_border_colors.get(selected_type, QColor(200, 200, 200, 150))
                    painter.setPen(QPen(border_color, 1.5))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRoundedRect(highlight_rect, 6, 6)
                    
                    # 在右上角绘制选中名称标签
                    element_type_key, peripheral_name, element_name = selected_element
                    # 使用更友好的显示名称
                    type_labels = {'peripheral': 'P', 'register': 'R', 'field': 'F', 'interrupt': 'I'}
                    type_label = type_labels.get(selected_type, '?')
                    name_text = f"[{type_label}] {element_name}"
                    
                    font = painter.font()
                    font.setBold(True)
                    font.setPointSize(9)
                    painter.setFont(font)
                    
                    # 计算文本位置（右上角）
                    text_rect = painter.fontMetrics().boundingRect(name_text)
                    text_x = highlight_rect.right() - text_rect.width() - 12
                    text_y = highlight_rect.top() + text_rect.height() + 4
                    
                    # 绘制标签背景（使用对应的标签颜色作为背景）
                    bg_rect = QRect(text_x - 6, text_y - text_rect.height() - 3,
                                   text_rect.width() + 12, text_rect.height() + 6)
                    painter.setPen(Qt.PenStyle.NoPen)
                    # 半透明白色背景
                    painter.setBrush(QColor(255, 255, 255, 220))
                    painter.drawRoundedRect(bg_rect, 3, 3)
                    
                    # 绘制标签左侧色点
                    dot_rect = QRect(text_x - 3, bg_rect.top() + 3, 4, bg_rect.height() - 6)
                    painter.setBrush(QBrush(label_color))
                    painter.drawRoundedRect(dot_rect, 2, 2)
                    
                    # 绘制文本（使用标签颜色）
                    painter.setPen(label_color)
                    painter.drawText(text_x + 4, text_y, name_text)
        
        # 绘制折叠标记（只绘制箭头，不绘制块）
        if hasattr(self, 'fold_markers'):
            self._draw_fold_markers(painter, visible_rect)
    
    def _draw_fold_markers(self, painter: QPainter, visible_rect: QRect):
        """绘制折叠标记（只绘制箭头，不绘制块）"""
        for line_num, (element_type, peripheral_name, element_name) in self.fold_markers.items():
            key = (element_type, peripheral_name, element_name)
            is_folded = key in self.folded_elements
            
            # 如果是寄存器或位域，检查其所属外设是否被折叠
            if element_type in ['register', 'field']:
                peripheral_key = ('peripheral', peripheral_name, peripheral_name)
                if peripheral_key in self.folded_elements:
                    # 外设已折叠，不绘制内部元素的折叠箭头
                    continue
            
            # 获取行的位置
            block = self.document().findBlockByNumber(line_num - 1)
            if not block.isValid():
                continue
            
            # 计算标记位置
            block_rect = self.blockBoundingGeometry(block).translated(self.contentOffset())
            
            # 检查是否在可见区域内（将QRectF转换为QRect）
            block_rect_int = QRect(int(block_rect.x()), int(block_rect.y()),
                                 int(block_rect.width()), int(block_rect.height()))
            if not visible_rect.intersects(block_rect_int):
                continue
            
            x = 10  # 左边距
            y = int(block_rect.top() + block_rect.height() / 2)
            
            # 绘制箭头
            self._draw_arrow(painter, x, y, is_folded)
            
            # 如果元素被折叠，绘制省略号
            if is_folded and key in self.element_line_ranges:
                start_line, end_line = self.element_line_ranges[key]
                # 只在元素有足够多行时才绘制省略号
                if end_line - start_line > 2:
                    # 获取第二行和最后一行的位置
                    second_block = self.document().findBlockByNumber(start_line)  # 第二行（索引从0开始）
                    last_block = self.document().findBlockByNumber(end_line - 1)  # 最后一行
                    
                    if second_block.isValid() and last_block.isValid():
                        second_rect = self.blockBoundingGeometry(second_block).translated(self.contentOffset())
                        last_rect = self.blockBoundingGeometry(last_block).translated(self.contentOffset())
                        
                        # 计算省略号位置（在第二行和最后一行之间）
                        ellipsis_y = int((second_rect.bottom() + last_rect.top()) / 2)
                        ellipsis_x = 30  # 左边距（在箭头后面）
                        
                        # 绘制省略号
                        painter.setPen(QPen(QColor("#999999"), 2))
                        for i in range(3):
                            painter.drawPoint(ellipsis_x + i * 8, ellipsis_y)
    
    def _draw_arrow(self, painter: QPainter, x: int, y: int, is_folded: bool):
        """绘制箭头"""
        size = 8
        painter.setPen(QPen(QColor("#666666"), 1))
        painter.setBrush(QBrush(QColor("#666666")))
        
        if is_folded:
            # 绘制向右的箭头（折叠状态）
            points = [
                QPoint(x - size//2, y - size//2),
                QPoint(x + size//2, y),
                QPoint(x - size//2, y + size//2)
            ]
        else:
            # 绘制向下的箭头（展开状态）
            points = [
                QPoint(x - size//2, y - size//2),
                QPoint(x + size//2, y - size//2),
                QPoint(x, y + size//2)
            ]
        
        painter.drawPolygon(*points)


class RealtimePreviewWidget(QWidget):
    """实时SVD预览组件"""
    
    # 信号定义
    element_selected = pyqtSignal(str, str, str)  # (element_type, peripheral_name, element_name)
    xml_edited = pyqtSignal(str)  # XML被编辑时发射
    
    def __init__(self, state_manager, coordinator=None, parent=None):
        """
        初始化实时预览组件
        
        Args:
            state_manager: 状态管理器
            coordinator: 协调器（可选）
            parent: 父部件（可选）
        """
        super().__init__(parent)
        self.state_manager = state_manager
        self.coordinator = coordinator
        self.logger = logging.getLogger("RealtimePreviewWidget")
        
        # 当前选中的元素信息
        self.current_selection = {
            'type': None,  # 'peripheral', 'register', 'field', 'interrupt'
            'peripheral': None,
            'register': None,
            'field': None,
            'interrupt': None
        }
        
        # XML行号映射（用于快速定位）
        self.line_map = {}  # {line_number: (element_type, peripheral_name, element_name)}
        
        # 元素范围映射（用于框选）
        self.element_ranges = {}  # {(element_type, peripheral_name, element_name): (start_line, end_line)}
        
        # 元素层级结构（用于折叠块显示）
        self.element_hierarchy = {}  # {child_key: parent_key}
        self.element_children = {}  # {parent_key: [child_keys]}
        
        # 折叠状态
        self.folded_elements = set()  # {(element_type, peripheral_name, element_name)}
        
        # 防抖定时器（避免频繁更新）
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self._update_preview)
        self.update_delay = 500  # 500ms延迟
        
        # 编辑防抖定时器
        self.edit_timer = QTimer()
        self.edit_timer.setSingleShot(True)
        self.edit_timer.timeout.connect(self._on_edit_timeout)
        self.edit_delay = 1000  # 1秒延迟
        
        # 标志：防止程序更新文本时触发编辑处理（避免循环）
        self._is_updating = False
        
        # 初始化UI
        self.init_ui()
        
        # 不在这里调用 show()，因为这个部件应该作为子部件显示
        # 而不是作为独立窗口显示
        # self.show()
        
        # 注册状态变化回调
        if self.state_manager:
            self.state_manager.register_state_change_callback(self.on_state_changed)
            self.state_manager.register_selection_change_callback(self.on_selection_changed)
        
        # 注册协调器事件
        if self.coordinator:
            self.coordinator.device_info_updated.connect(self.on_device_info_updated)
            self.coordinator.selection_changed.connect(self.on_coordinator_selection_changed)
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(5, 2, 5, 2)
        
        # 保存按钮（保存编辑的XML到设备信息）
        save_btn = QPushButton(t("button.save"))
        save_btn.clicked.connect(self.save_edited_xml)
        toolbar.addWidget(save_btn)
        
        # 跳转到选中按钮
        jump_btn = QPushButton(t("button.jump_to_selection"))
        jump_btn.clicked.connect(self.jump_to_selection)
        toolbar.addWidget(jump_btn)
        
        toolbar.addStretch()
        
        layout.addLayout(toolbar)
        
        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)
        
        # 预览文本编辑器（使用HighlightedTextEdit以支持高亮和折叠功能）
        self.preview_edit = HighlightedTextEdit()
        self.preview_edit.setReadOnly(False)  # 改为可编辑
        # self.preview_edit.show()  # 确保编辑器可见
        
        # 设置字体
        font = QFont("Consolas, 'Courier New', monospace")
        font.setPointSize(10)
        self.preview_edit.setFont(font)
        self.preview_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        
        # 设置样式
        self.preview_edit.setStyleSheet("""
            QPlainTextEdit {
                background-color: #ffffff;
                color: #000000;
                selection-background-color: #d1e9ff;
                selection-color: #000000;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 4px;
            }
            QPlainTextEdit:focus {
                border: 1px solid #90c8ff;
            }
        """)
        
        # 连接选择变化信号
        self.preview_edit.selectionChanged.connect(self.on_preview_selection_changed)
        # 连接文本变化信号
        self.preview_edit.textChanged.connect(self.on_text_changed)
        # 连接折叠点击信号
        self.preview_edit.fold_clicked.connect(self.on_fold_clicked)
        # 连接元素点击信号 - 连接到element_selected信号
        self.preview_edit.element_clicked.connect(self.on_element_clicked)
        
        layout.addWidget(self.preview_edit)
        
        # 添加语法高亮（在添加到布局后）
        doc = self.preview_edit.document()
        if doc:
            self.highlighter = XMLHighlighter(doc)
        
        # 状态栏
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666; font-size: 9pt;")
        layout.addWidget(self.status_label)
    
    def refresh_preview(self, immediate: bool = False):
        """刷新预览
        
        Args:
            immediate: 是否立即刷新（不使用防抖）
        """
        self.logger.debug(f"refresh_preview 被调用，immediate={immediate}")
        self.logger.debug(f"preview_edit 存在={hasattr(self, 'preview_edit')}, preview_edit={self.preview_edit if hasattr(self, 'preview_edit') else 'N/A'}")
        if hasattr(self, 'preview_edit') and self.preview_edit:
            self.logger.debug(f"preview_edit 可见={self.preview_edit.isVisible()}, 文本长度={len(self.preview_edit.toPlainText())}")
        self.logger.debug(f"refresh_preview called, immediate={immediate}")
        if immediate:
            # 立即刷新
            self.logger.debug("立即刷新预览")
            self._update_preview()
        else:
            # 使用防抖
            self.logger.debug("使用防抖刷新预览")
            self.update_timer.start(self.update_delay)
    
    def _force_update_preview(self):
        """强制更新预览内容（忽略窗口可见性检查）"""
        try:
            # 检查预览编辑器是否仍然有效
            if not hasattr(self, 'preview_edit') or self.preview_edit is None:
                self.logger.debug("预览编辑器不存在，跳过更新")
                return
            
            self.logger.info("=== _force_update_preview 开始 ===")
            
            # 检查device_info
            if not self.state_manager.device_info:
                self.logger.warning("device_info为空，无法生成SVD")
                return
            
            self.logger.info(f"device_info 存在，外设数量: {len(self.state_manager.device_info.peripherals)}")
            
            # 生成SVD XML
            generator = SVDGenerator(self.state_manager.device_info)
            svd_xml = generator.generate(pretty_print=False)  # 不美化，我们自己处理
            
            self.logger.info(f"生成的原始XML长度: {len(svd_xml)} 字符")
            
            # 美化XML
            pretty_svd = pretty_xml(svd_xml)
            self.logger.info(f"美化后的XML长度: {len(pretty_svd)} 字符")
            
            # 更新文本
            self.preview_edit.setPlainText(pretty_svd)
            
            # 重建行号映射和折叠标记
            self._build_line_map(pretty_svd)
            self.logger.info(f"_build_line_map 完成，element_ranges 数量: {len(self.element_ranges)}")
            
            # 更新高亮编辑器的数据
            self.preview_edit.set_folded_elements(self.folded_elements)
            self.preview_edit.set_element_line_ranges(self.element_ranges)
            self.preview_edit.set_element_children(self.element_children)
            self.preview_edit.set_element_ranges(self.element_ranges)
            self.preview_edit.set_fold_markers(self._build_fold_markers())
            self.preview_edit.set_highlight_ranges(self.element_ranges)
            
            self.logger.info("=== _force_update_preview 完成 ===")
            
            # 更新状态
            try:
                doc = self.preview_edit.document()
                if doc:
                    line_count = doc.blockCount()
                    self.status_label.setText(f"{t('status.lines')}: {line_count}")
                    self.logger.debug(f"预览更新完成，共 {line_count} 行")
                    self.logger.debug(f"元素范围映射: {len(self.element_ranges)} 个元素")
            except RuntimeError:
                # 对象已被删除，跳过状态更新
                self.logger.debug("状态标签已被删除，跳过更新")
            
        except RuntimeError as e:
            # Qt对象已被删除
            self.logger.warning(f"Qt对象已被删除: {e}")
        except Exception as e:
            self.logger.error(f"更新预览失败: {e}")
            import traceback
            self.logger.error(f"错误详情: {traceback.format_exc()}")
            try:
                self.status_label.setText(f"{t('status.error')}: {str(e)}")
            except RuntimeError:
                # 状态标签也已被删除
                pass
    
    def _update_preview(self):
        """更新预览内容（内部方法）"""
        self.logger.debug("_update_preview 被调用")
        try:
            # 检查预览编辑器是否仍然有效
            if not hasattr(self, 'preview_edit') or self.preview_edit is None:
                self.logger.debug("预览编辑器不存在，跳过更新")
                return
            
            # 检查Qt对象是否已被删除
            try:
                _ = self.preview_edit.isVisible()
            except RuntimeError:
                self.logger.debug("preview_edit对象已被删除，跳过更新")
                return
            
            # 获取设备信息
            device_info = self.state_manager.device_info
            if not device_info:
                self.logger.debug("设备信息为空，无法更新预览")
                return
            
            self.logger.debug("开始更新预览内容...")
            
            # 设置更新标志，防止触发编辑处理
            self._is_updating = True
            
            # 生成SVD XML
            generator = SVDGenerator(device_info)
            svd_xml = generator.generate(pretty_print=False)  # 不美化，我们自己处理
            
            # 美化XML
            pretty_svd = pretty_xml(svd_xml)
            
            # 保存当前选择位置
            try:
                current_cursor = self.preview_edit.textCursor()
                current_position = current_cursor.position()
            except RuntimeError:
                # 对象已被删除，跳过位置恢复
                current_position = 0
            
            # 更新文本
            self.logger.debug(f"准备设置预览文本，长度={len(pretty_svd)}")
            self.preview_edit.setPlainText(pretty_svd)
            self.logger.debug("预览文本已设置")
            
            # 重建行号映射和折叠标记
            self._build_line_map(pretty_svd)
            
            # 更新高亮编辑器的数据
            self.preview_edit.set_folded_elements(self.folded_elements)
            self.preview_edit.set_element_line_ranges(self.element_ranges)
            self.preview_edit.set_element_children(self.element_children)
            self.preview_edit.set_element_ranges(self.element_ranges)
            self.preview_edit.set_fold_markers(self._build_fold_markers())
            self.preview_edit.set_highlight_ranges(self.element_ranges)
            
            # 恢复选择位置
            if current_position > 0 and current_position < len(pretty_svd):
                new_cursor = QTextCursor(self.preview_edit.document())
                new_cursor.setPosition(current_position)
                self.preview_edit.setTextCursor(new_cursor)
            
            # 重新应用当前高亮
            if self.current_selection.get('type'):
                self._apply_highlight()
            
            # 更新状态
            try:
                doc = self.preview_edit.document()
                if doc:
                    line_count = doc.blockCount()
                    self.status_label.setText(f"{t('status.lines')}: {line_count}")
                    self.logger.debug(f"预览更新完成，共 {line_count} 行")
                    self.logger.debug(f"元素范围映射: {len(self.element_ranges)} 个元素")
            except RuntimeError:
                # 对象已被删除，跳过状态更新
                self.logger.debug("状态标签已被删除，跳过更新")
            
        except RuntimeError as e:
            # Qt对象已被删除
            self.logger.warning(f"Qt对象已被删除: {e}")
        except Exception as e:
            self.logger.error(f"更新预览失败: {e}")
            import traceback
            self.logger.error(f"错误详情: {traceback.format_exc()}")
            try:
                self.status_label.setText(f"{t('status.error')}: {str(e)}")
            except RuntimeError:
                # 状态标签也已被删除
                pass
        finally:
            # 清除更新标志
            self._is_updating = False
    
    def _build_fold_markers(self) -> Dict[int, Tuple[str, str, str]]:
        """构建折叠标记映射"""
        fold_markers = {}
        # 为每个可折叠的元素添加标记
        for (element_type, peripheral_name, element_name), (start_line, end_line) in self.element_ranges.items():
            # 只在外设和寄存器的开始行添加标记
            if element_type in ['peripheral', 'register']:
                fold_markers[start_line] = (element_type, peripheral_name, element_name)
        return fold_markers
    
    def on_fold_clicked(self, element_type: str, peripheral_name: str, element_name: str, is_expanded: bool):
        """折叠点击处理"""
        self.logger.debug(f"on_fold_clicked 被调用，element_type={element_type}, peripheral_name={peripheral_name}, element_name={element_name}, is_expanded={is_expanded}")
        key = (element_type, peripheral_name, element_name)
        
        if is_expanded:
            # 展开：从折叠集合中移除
            if key in self.folded_elements:
                self.folded_elements.remove(key)
            self.logger.debug(f"展开元素: {element_type} - {element_name}")
        else:
            # 折叠：添加到折叠集合
            self.folded_elements.add(key)
            self.logger.debug(f"折叠元素: {element_type} - {element_name}")
        
        # 重新渲染
        self.logger.debug("调用 _apply_folding")
        self._apply_folding()
    
    def sync_fold_from_tree(self, item_name: str, is_expanded: bool):
        """
        从树状图同步折叠/展开状态到预览
        
        Args:
            item_name: 项目名称（外设名或寄存器名）
            is_expanded: True=展开, False=折叠
        """
        self.logger.debug(f"sync_fold_from_tree: item_name={item_name}, is_expanded={is_expanded}")
        
        # 尝试匹配外设
        peripheral_key = ('peripheral', item_name, item_name)
        if peripheral_key in self.element_ranges:
            if is_expanded:
                self.folded_elements.discard(peripheral_key)
            else:
                self.folded_elements.add(peripheral_key)
            self._apply_folding()
            self.logger.debug(f"同步外设折叠状态: {item_name} -> {'展开' if is_expanded else '折叠'}")
            return
        
        # 尝试匹配寄存器（需要找到所属外设）
        for key in self.element_ranges:
            if key[0] == 'register' and key[2] == item_name:
                if is_expanded:
                    self.folded_elements.discard(key)
                else:
                    self.folded_elements.add(key)
                self._apply_folding()
                self.logger.debug(f"同步寄存器折叠状态: {item_name} -> {'展开' if is_expanded else '折叠'}")
                return
        
        self.logger.debug(f"sync_fold_from_tree: 未找到匹配元素 {item_name}")
    
    def collapse_peripheral_in_preview(self, peripheral_name: str):
        """折叠预览中指定外设"""
        key = ('peripheral', peripheral_name, peripheral_name)
        if key in self.element_ranges:
            self.folded_elements.add(key)
            self._apply_folding()
    
    def expand_peripheral_in_preview(self, peripheral_name: str):
        """展开预览中指定外设"""
        key = ('peripheral', peripheral_name, peripheral_name)
        self.folded_elements.discard(key)
        self._apply_folding()
    
    def _draw_fold_blocks(self, painter: QPainter):
        """绘制折叠块（类似代码编辑器的折叠块）"""
        # 遍历所有外设
        for peripheral_key, children in self.element_children.items():
            if not children:
                continue
            
            element_type, peripheral_name, _ = peripheral_key
            if peripheral_key not in self.element_ranges:
                continue
            
            start_line, end_line = self.element_ranges[peripheral_key]
            
            # 获取外设块的起始和结束位置
            start_block = self.preview_edit.document().findBlockByNumber(start_line - 1)
            end_block = self.preview_edit.document().findBlockByNumber(end_line - 1)
            
            if not start_block.isValid() or not end_block.isValid():
                continue
            
            start_rect = self.preview_edit.blockBoundingGeometry(start_block).translated(self.preview_edit.contentOffset())
            end_rect = self.preview_edit.blockBoundingGeometry(end_block).translated(self.preview_edit.contentOffset())
            
            # 计算外设块的位置
            block_x = int(start_rect.left())
            block_y = int(start_rect.top())
            block_width = int(self.preview_edit.viewport().width() - start_rect.left())
            block_height = int(end_rect.bottom() - start_rect.top())
            
            # 检查外设是否被折叠
            is_folded = peripheral_key in self.folded_elements
            
            # 绘制外设块背景
            if is_folded:
                # 折叠状态：只显示前两行
                color = QColor(255, 200, 100, 80)  # 浅橙色
            else:
                # 展开状态：显示整个块
                color = QColor(255, 220, 180, 80)  # 浅黄色
            
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawRoundedRect(block_x, block_y, block_width, block_height, 8, 8)
            
            # 绘制外设块边框
            border_color = QColor(color)
            border_color.setAlpha(150)
            painter.setPen(QPen(border_color, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(block_x, block_y, block_width, block_height, 8, 8)
            
            # 绘制外设名称
            painter.setPen(QColor("#333333"))
            font = painter.font()
            font.setBold(True)
            font.setPointSize(10)
            painter.setFont(font)
            name_text = peripheral_name
            text_rect = painter.fontMetrics().boundingRect(name_text)
            text_x = block_x + 10
            text_y = block_y + text_rect.height() + 5
            painter.drawText(text_x, text_y, name_text)
            
            # 如果外设被折叠，绘制省略号
            if is_folded:
                ellipsis_y = block_y + block_height // 2
                painter.setPen(QPen(QColor("#999999"), 1))
                painter.drawText(block_x + 10, ellipsis_y, "...")
            
            # 如果外设未折叠，绘制连接线和寄存器块
            if not is_folded:
                # 绘制外设到寄存器的连接线
                line_x = block_x + 10
                line_start_y = block_y + block_height
                line_end_y = block_y + block_height + 10
                painter.setPen(QPen(QColor("#CCCCCC"), 1))
                painter.drawLine(line_x, line_start_y, line_x, line_end_y)
                
                for register_key in children:
                    if register_key[0] != 'register':
                        continue
                    
                    if register_key not in self.element_ranges:
                        continue
                    
                    reg_start_line, reg_end_line = self.element_ranges[register_key]
                    
                    # 获取寄存器块的起始和结束位置
                    reg_start_block = self.preview_edit.document().findBlockByNumber(reg_start_line - 1)
                    reg_end_block = self.preview_edit.document().findBlockByNumber(reg_end_line - 1)
                    
                    if not reg_start_block.isValid() or not reg_end_block.isValid():
                        continue
                    
                    reg_start_rect = self.preview_edit.blockBoundingGeometry(reg_start_block).translated(self.preview_edit.contentOffset())
                    reg_end_rect = self.preview_edit.blockBoundingGeometry(reg_end_block).translated(self.preview_edit.contentOffset())
                    
                    # 计算寄存器块的位置（缩进20像素）
                    reg_block_x = int(reg_start_rect.left()) + 20
                    reg_block_y = int(reg_start_rect.top())
                    reg_block_width = int(self.preview_edit.viewport().width() - reg_start_rect.left() - 20)
                    reg_block_height = int(reg_end_rect.bottom() - reg_start_rect.top())
                    
                    # 绘制外设到寄存器的水平连接线
                    painter.setPen(QPen(QColor("#CCCCCC"), 1))
                    painter.drawLine(line_x, line_end_y, reg_block_x + 10, line_end_y)
                    painter.drawLine(reg_block_x + 10, line_end_y, reg_block_x + 10, reg_block_y)
                    
                    # 检查寄存器是否被折叠
                    reg_is_folded = register_key in self.folded_elements
                    
                    # 绘制寄存器块背景
                    if reg_is_folded:
                        # 折叠状态：只显示前两行
                        reg_color = QColor(100, 200, 255, 80)  # 浅蓝色
                    else:
                        # 展开状态：显示整个块
                        reg_color = QColor(180, 220, 255, 80)  # 浅蓝色
                    
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(reg_color))
                    painter.drawRoundedRect(reg_block_x, reg_block_y, reg_block_width, reg_block_height, 6, 6)
                    
                    # 绘制寄存器块边框
                    reg_border_color = QColor(reg_color)
                    reg_border_color.setAlpha(150)
                    painter.setPen(QPen(reg_border_color, 2))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRoundedRect(reg_block_x, reg_block_y, reg_block_width, reg_block_height, 6, 6)
                    
                    # 绘制寄存器名称
                    painter.setPen(QColor("#333333"))
                    font = painter.font()
                    font.setBold(True)
                    font.setPointSize(9)
                    painter.setFont(font)
                    _, _, reg_name = register_key
                    reg_text_rect = painter.fontMetrics().boundingRect(reg_name)
                    reg_text_x = reg_block_x + 10
                    reg_text_y = reg_block_y + reg_text_rect.height() + 5
                    painter.drawText(reg_text_x, reg_text_y, reg_name)
                    
                    # 如果寄存器被折叠，绘制省略号
                    if reg_is_folded:
                        reg_ellipsis_y = reg_block_y + reg_block_height // 2
                        painter.setPen(QPen(QColor("#999999"), 1))
                        painter.drawText(reg_block_x + 10, reg_ellipsis_y, "...")
                    
                    # 如果寄存器未折叠且有子元素，绘制连接线和位域块
                    if not reg_is_folded and register_key in self.element_children:
                        # 绘制寄存器到位域的连接线
                        reg_line_x = reg_block_x + 10
                        reg_line_start_y = reg_block_y + reg_block_height
                        reg_line_end_y = reg_block_y + reg_block_height + 10
                        painter.setPen(QPen(QColor("#CCCCCC"), 1))
                        painter.drawLine(reg_line_x, reg_line_start_y, reg_line_x, reg_line_end_y)
                        
                        for field_key in self.element_children[register_key]:
                            if field_key[0] != 'field':
                                continue
                            
                            if field_key not in self.element_ranges:
                                continue
                            
                            field_start_line, field_end_line = self.element_ranges[field_key]
                            
                            # 获取位域块的起始和结束位置
                            field_start_block = self.preview_edit.document().findBlockByNumber(field_start_line - 1)
                            field_end_block = self.preview_edit.document().findBlockByNumber(field_end_line - 1)
                            
                            if not field_start_block.isValid() or not field_end_block.isValid():
                                continue
                            
                            field_start_rect = self.preview_edit.blockBoundingGeometry(field_start_block).translated(self.preview_edit.contentOffset())
                            field_end_rect = self.preview_edit.blockBoundingGeometry(field_end_block).translated(self.preview_edit.contentOffset())
                            
                            # 计算位域块的位置（缩进40像素）
                            field_block_x = int(field_start_rect.left()) + 40
                            field_block_y = int(field_start_rect.top())
                            field_block_width = int(self.preview_edit.viewport().width() - field_start_rect.left() - 40)
                            field_block_height = int(field_end_rect.bottom() - field_start_rect.top())
                            
                            # 绘制寄存器到位域的水平连接线
                            painter.setPen(QPen(QColor("#CCCCCC"), 1))
                            painter.drawLine(reg_line_x, reg_line_end_y, field_block_x + 10, reg_line_end_y)
                            painter.drawLine(field_block_x + 10, reg_line_end_y, field_block_x + 10, field_block_y)
                            
                            # 绘制位域块背景
                            field_color = QColor(100, 255, 100, 80)  # 浅绿色
                            
                            painter.setPen(Qt.PenStyle.NoPen)
                            painter.setBrush(QBrush(field_color))
                            painter.drawRoundedRect(field_block_x, field_block_y, field_block_width, field_block_height, 4, 4)
                            
                            # 绘制位域块边框
                            field_border_color = QColor(field_color)
                            field_border_color.setAlpha(150)
                            painter.setPen(QPen(field_border_color, 1))
                            painter.setBrush(Qt.BrushStyle.NoBrush)
                            painter.drawRoundedRect(field_block_x, field_block_y, field_block_width, field_block_height, 4, 4)
                            
                            # 绘制位域名称
                            painter.setPen(QColor("#333333"))
                            font = painter.font()
                            font.setPointSize(8)
                            painter.setFont(font)
                            _, _, field_name = field_key
                            field_text_rect = painter.fontMetrics().boundingRect(field_name)
                            field_text_x = field_block_x + 10
                            field_text_y = field_block_y + field_text_rect.height() + 5
                            painter.drawText(field_text_x, field_text_y, field_name)
    
    def on_element_clicked(self, element_type: str, peripheral_name: str, element_name: str):
        """元素点击处理"""
        self.logger.debug(f"点击元素: {element_type} - {element_name}")
        # 发射选择信号
        self.element_selected.emit(element_type, peripheral_name, element_name)
    
    def _apply_folding(self):
        """应用折叠效果"""
        self.logger.debug(f"_apply_folding 被调用，folded_elements数量={len(self.folded_elements)}")
        # 更新高亮编辑器的数据
        self.preview_edit.set_folded_elements(self.folded_elements)
        self.preview_edit.update()
        self.logger.debug("_apply_folding 完成")
    
    def _build_line_map(self, xml_text: str):
        """构建行号映射和元素范围映射"""
        self.logger.info("=== 开始构建行号映射 ===")
        self.logger.info(f"XML文本长度: {len(xml_text)} 字符")
        
        self.line_map.clear()
        self.element_ranges.clear()
        self.element_hierarchy.clear()
        self.element_children.clear()
        lines = xml_text.split('\n')
        self.logger.info(f"XML行数: {len(lines)}")
        
        # 用于跟踪元素范围
        element_stack = []  # [(element_type, peripheral_name, element_name, start_line)]
        
        current_peripheral = None
        current_register = None
        current_field = None
        current_interrupt = None
        
        # 用于跟踪正在解析的元素
        pending_peripheral_name = None
        pending_register_name = None
        pending_field_name = None
        
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # 检测外设开始 - 新的XML格式: <peripheral> 或 <peripheral derivedFrom="...">
            if stripped == '<peripheral>' or stripped.startswith('<peripheral derivedFrom='):
                # 外设开始，但还不知道名称
                pending_peripheral_name = None
                element_stack.append(('peripheral', None, None, line_num))
                continue
            
            # 检测外设名称 - 在<peripheral>标签内
            if pending_peripheral_name is None and element_stack and element_stack[-1][0] == 'peripheral':
                name_match = re.search(r'<name>([^<]+)</name>', stripped)
                if name_match:
                    pending_peripheral_name = name_match.group(1)
                    current_peripheral = pending_peripheral_name
                    # 更新栈中的元素
                    if element_stack:
                        elem_type, _, _, start_line = element_stack[-1]
                        element_stack[-1] = (elem_type, current_peripheral, current_peripheral, start_line)
                    self.line_map[line_num] = ('peripheral', current_peripheral, current_peripheral)
                    continue
            
            # 检测外设结束
            if stripped == '</peripheral>':
                if element_stack and element_stack[-1][0] == 'peripheral':
                    elem_type, periph_name, elem_name, start_line = element_stack.pop()
                    if periph_name:  # 只有在外设名称已确定的情况下才添加到element_ranges
                        self.element_ranges[(elem_type, periph_name, elem_name)] = (start_line, line_num)
                        
                        # 构建层级结构
                        peripheral_key = (elem_type, periph_name, elem_name)
                        if peripheral_key not in self.element_children:
                            self.element_children[peripheral_key] = []
                # 重置当前外设
                current_peripheral = None
                pending_peripheral_name = None
                current_register = None
                pending_register_name = None
                current_field = None
                pending_field_name = None
                continue
            
            # 检测寄存器开始 - 新的XML格式: <register>
            if stripped == '<register>':
                # 寄存器开始，但还不知道名称
                pending_register_name = None
                element_stack.append(('register', current_peripheral, None, line_num))
                continue
            
            # 检测寄存器名称 - 在<register>标签内
            if pending_register_name is None and element_stack and element_stack[-1][0] == 'register':
                name_match = re.search(r'<name>([^<]+)</name>', stripped)
                if name_match:
                    pending_register_name = name_match.group(1)
                    current_register = pending_register_name
                    # 更新栈中的元素
                    if element_stack:
                        elem_type, periph_name, _, start_line = element_stack[-1]
                        element_stack[-1] = (elem_type, periph_name, current_register, start_line)
                    if current_peripheral:
                        self.line_map[line_num] = ('register', current_peripheral, current_register)
                    continue
            
            # 检测寄存器结束
            if stripped == '</register>':
                if element_stack and element_stack[-1][0] == 'register':
                    elem_type, periph_name, reg_name, start_line = element_stack.pop()
                    if periph_name and reg_name:  # 只有在名称已确定的情况下才添加到element_ranges
                        self.element_ranges[(elem_type, periph_name, reg_name)] = (start_line, line_num)
                        
                        # 构建层级结构
                        register_key = (elem_type, periph_name, reg_name)
                        peripheral_key = ('peripheral', periph_name, periph_name)
                        if peripheral_key in self.element_children:
                            if register_key not in self.element_children[peripheral_key]:
                                self.element_children[peripheral_key].append(register_key)
                # 重置当前寄存器
                current_register = None
                pending_register_name = None
                current_field = None
                pending_field_name = None
                continue
            
            # 检测位域开始 - 新的XML格式: <field>
            if stripped == '<field>':
                # 位域开始，但还不知道名称
                pending_field_name = None
                element_stack.append(('field', current_peripheral, None, line_num))
                continue
            
            # 检测位域名称 - 在<field>标签内
            if pending_field_name is None and element_stack and element_stack[-1][0] == 'field':
                name_match = re.search(r'<name>([^<]+)</name>', stripped)
                if name_match:
                    pending_field_name = name_match.group(1)
                    current_field = pending_field_name
                    # 更新栈中的元素
                    if element_stack:
                        elem_type, periph_name, _, start_line = element_stack[-1]
                        element_stack[-1] = (elem_type, periph_name, current_field, start_line)
                    if current_peripheral and current_register:
                        self.line_map[line_num] = ('field', current_peripheral, f"{current_register}.{current_field}")
                    continue
            
            # 检测位域结束
            if stripped == '</field>':
                if element_stack and element_stack[-1][0] == 'field':
                    elem_type, periph_name, field_name, start_line = element_stack.pop()
                    if periph_name and field_name and current_register:  # 只有在名称已确定的情况下才添加到element_ranges
                        self.element_ranges[(elem_type, periph_name, f"{current_register}.{field_name}")] = (start_line, line_num)
                        
                        # 构建层级结构
                        field_key = (elem_type, periph_name, f"{current_register}.{field_name}")
                        register_key = ('register', periph_name, current_register)
                        if register_key in self.element_children:
                            if field_key not in self.element_children[register_key]:
                                self.element_children[register_key].append(field_key)
                # 重置当前位域
                current_field = None
                pending_field_name = None
                continue
            
            # 检测寄存器开始
            register_match = re.search(r'<register\s+name="([^"]+)"', stripped)
            if register_match:
                # 如果没有当前外设，尝试从element_stack中获取
                if not current_peripheral and element_stack:
                    for item in reversed(element_stack):
                        if item[0] == 'peripheral':
                            current_peripheral = item[1]
                            break
                
                if current_peripheral:
                    current_register = register_match.group(1)
                    self.line_map[line_num] = ('register', current_peripheral, current_register)
                    element_stack.append(('register', current_peripheral, current_register, line_num))
                    self.logger.debug(f"行 {line_num}: 检测到寄存器开始 - {current_peripheral}.{current_register}")
                continue
            
            # 检测寄存器结束
            if stripped == '</register>':
                if element_stack and element_stack[-1][0] == 'register':
                    elem_type, periph_name, elem_name, start_line = element_stack.pop()
                    self.element_ranges[(elem_type, periph_name, elem_name)] = (start_line, line_num)
                # 不要重置current_register，因为位域可能还在寄存器内部
                # current_register = None
                current_field = None
                continue
            
            # 检测位域开始
            field_match = re.search(r'<field\s+name="([^"]+)"', stripped)
            if field_match:
                # 如果没有当前寄存器，尝试从element_stack中获取
                if not current_register and element_stack:
                    for item in reversed(element_stack):
                        if item[0] == 'register':
                            current_register = item[2]
                            current_peripheral = item[1]
                            break
                
                if current_register and current_peripheral:
                    current_field = field_match.group(1)
                    self.line_map[line_num] = ('field', current_peripheral, f"{current_register}.{current_field}")
                    element_stack.append(('field', current_peripheral, f"{current_register}.{current_field}", line_num))
                    self.logger.debug(f"行 {line_num}: 检测到位域开始 - {current_peripheral}.{current_register}.{current_field}")
                continue
            
            # 检测位域结束
            if stripped == '</field>':
                if element_stack and element_stack[-1][0] == 'field':
                    elem_type, periph_name, elem_name, start_line = element_stack.pop()
                    self.element_ranges[(elem_type, periph_name, elem_name)] = (start_line, line_num)
                current_field = None
                continue
            
            # 检测中断开始
            interrupt_match = re.search(r'<interrupt>\s*<name>([^<]+)</name>', stripped)
            if interrupt_match and current_peripheral:
                current_interrupt = interrupt_match.group(1)
                self.line_map[line_num] = ('interrupt', current_peripheral, current_interrupt)
                element_stack.append(('interrupt', current_peripheral, current_interrupt, line_num))
                continue
            
            # 检测中断结束
            if stripped == '</interrupt>':
                if element_stack and element_stack[-1][0] == 'interrupt':
                    elem_type, periph_name, elem_name, start_line = element_stack.pop()
                    self.element_ranges[(elem_type, periph_name, elem_name)] = (start_line, line_num)
                current_interrupt = None
                continue
        
        self.logger.info(f"=== 构建行号映射完成 ===")
        self.logger.info(f"line_map 数量: {len(self.line_map)}")
        self.logger.info(f"element_ranges 数量: {len(self.element_ranges)}")
        if self.element_ranges:
            self.logger.info(f"element_ranges 中的所有keys: {list(self.element_ranges.keys())}")
        
        # 设置默认折叠：折叠所有外设
        self._set_default_folding()
    
    def _set_default_folding(self):
        """设置默认折叠：折叠所有外设和寄存器"""
        # 只在第一次加载时设置默认折叠
        if not hasattr(self, '_default_folding_set'):
            self._default_folding_set = True
            
            # 将所有外设和寄存器添加到折叠集合
            for key in self.element_ranges:
                element_type, peripheral_name, element_name = key
                if element_type in ['peripheral', 'register']:
                    self.folded_elements.add(key)
            
            folded_peripherals = len([k for k in self.folded_elements if k[0] == 'peripheral'])
            folded_registers = len([k for k in self.folded_elements if k[0] == 'register'])
            self.logger.info(f"设置默认折叠，折叠了 {folded_peripherals} 个外设和 {folded_registers} 个寄存器")
    
    def on_state_changed(self):
        """状态变化回调"""
        self.refresh_preview(immediate=True)
    
    def on_device_info_updated(self, device_info):
        """设备信息更新回调"""
        self.logger.debug(f"on_device_info_updated 被调用，device_info={device_info.name if device_info else 'None'}")
        self.refresh_preview(immediate=True)
    
    def on_selection_changed(self):
        """选择变化回调（来自状态管理器）"""
        try:
            # 检查对象是否仍然有效
            if not hasattr(self, 'preview_edit') or self.preview_edit is None:
                self.logger.debug("preview_edit 不存在，跳过选择变化处理")
                return
            
            # 检查 Qt 对象是否已被删除
            try:
                _ = self.preview_edit.isVisible()
            except RuntimeError:
                self.logger.debug("preview_edit 对象已被删除，跳过选择变化处理")
                return
            
            selection = self.state_manager.get_selection()
            self.highlight_element(selection)
        except RuntimeError as e:
            self.logger.warning(f"Qt对象已被删除: {e}")
        except Exception as e:
            self.logger.error(f"处理选择变化时出错: {e}")
    
    def on_coordinator_selection_changed(self, selection: Dict[str, Any]):
        """选择变化回调（来自协调器）"""
        try:
            # 检查对象是否仍然有效
            if not hasattr(self, 'preview_edit') or self.preview_edit is None:
                self.logger.debug("preview_edit 不存在，跳过选择变化处理")
                return
            
            # 检查 Qt 对象是否已被删除
            try:
                _ = self.preview_edit.isVisible()
            except RuntimeError:
                self.logger.debug("preview_edit 对象已被删除，跳过选择变化处理")
                return
            
            self.highlight_element(selection)
        except RuntimeError as e:
            self.logger.warning(f"Qt对象已被删除: {e}")
        except Exception as e:
            self.logger.error(f"处理选择变化时出错: {e}")
    
    def highlight_element(self, selection: Dict[str, Any]):
        """高亮显示指定元素"""
        try:
            # 检查对象是否仍然有效
            if not hasattr(self, 'preview_edit') or self.preview_edit is None:
                self.logger.debug("preview_edit 不存在，跳过高亮元素")
                return
            
            # 检查 Qt 对象是否已被删除
            try:
                _ = self.preview_edit.isVisible()
            except RuntimeError:
                self.logger.debug("preview_edit 对象已被删除，跳过高亮元素")
                return
            
            self.logger.info("=== highlight_element 被调用 ===")
            self.logger.info(f"选择信息: {selection}")
            
            if not selection:
                self.logger.debug("选择信息为空，无法高亮")
                return
            
            self.logger.debug(f"高亮元素: {selection}")
            
            # 如果element_ranges为空，先更新预览（即使窗口不可见）
            if not self.element_ranges:
                self.logger.info("element_ranges为空，调用 _force_update_preview()")
                # 强制更新预览，忽略窗口可见性检查
                self._force_update_preview()
                # 检查更新后element_ranges是否仍然为空
                if not self.element_ranges:
                    self.logger.warning("更新预览后element_ranges仍然为空，无法跳转")
                    return
            else:
                self.logger.info(f"element_ranges 不为空，共 {len(self.element_ranges)} 个元素")
            
            # 更新当前选择
            self.current_selection = selection
            
            element_type = selection.get('type')
            peripheral = selection.get('peripheral')
            register = selection.get('register')
            field = selection.get('field')
            interrupt = selection.get('interrupt')
            
            # 确定元素名称
            element_name = None
            if element_type == 'peripheral':
                element_name = peripheral
            elif element_type == 'register':
                element_name = register
            elif element_type == 'field':
                element_name = f"{register}.{field}"
            elif element_type == 'interrupt':
                element_name = interrupt
            
            if element_name and peripheral and element_type:
                # 自动展开父级元素
                self._auto_expand_for_element(element_type, peripheral, element_name)
                
                # 应用高亮
                self._apply_highlight()
                
                # 跳转到元素
                self._jump_to_element(element_type, peripheral, element_name)
            else:
                # 回退到行高亮
                line_num = self._find_line_for_selection(selection)
                if line_num:
                    self._jump_to_line(line_num)
        except RuntimeError as e:
            self.logger.warning(f"Qt对象已被删除: {e}")
        except Exception as e:
            self.logger.error(f"高亮元素时出错: {e}")
    
    def _auto_expand_for_element(self, element_type: str, peripheral_name: str, element_name: str):
        """自动展开父级元素"""
        try:
            # 检查对象是否仍然有效
            if not hasattr(self, 'preview_edit') or self.preview_edit is None:
                self.logger.debug("preview_edit 不存在，跳过自动展开")
                return
            
            # 检查 Qt 对象是否已被删除
            try:
                _ = self.preview_edit.isVisible()
            except RuntimeError:
                self.logger.debug("preview_edit 对象已被删除，跳过自动展开")
                return
            
            # 如果选中的是寄存器，确保外设是展开的
            if element_type in ['register', 'field', 'interrupt']:
                peripheral_key = ('peripheral', peripheral_name, peripheral_name)
                if peripheral_key in self.folded_elements:
                    self.folded_elements.remove(peripheral_key)
                    self.logger.debug(f"自动展开外设: {peripheral_name}")
            
            # 如果选中的是位域，确保寄存器是展开的
            if element_type == 'field':
                # 从element_name中提取寄存器名
                if '.' in element_name:
                    register_name = element_name.split('.')[0]
                    register_key = ('register', peripheral_name, register_name)
                    if register_key in self.folded_elements:
                        self.folded_elements.remove(register_key)
                        self.logger.debug(f"自动展开寄存器: {register_name}")
            
            # 更新折叠编辑器的数据
            self.preview_edit.set_folded_elements(self.folded_elements)
        except RuntimeError as e:
            self.logger.warning(f"Qt对象已被删除: {e}")
        except Exception as e:
            self.logger.error(f"自动展开元素时出错: {e}")
    
    def _apply_highlight(self):
        """应用高亮显示"""
        try:
            # 检查对象是否仍然有效
            if not hasattr(self, 'preview_edit') or self.preview_edit is None:
                self.logger.debug("preview_edit 不存在，跳过高亮应用")
                return
            
            # 检查 Qt 对象是否已被删除
            try:
                _ = self.preview_edit.isVisible()
            except RuntimeError:
                self.logger.debug("preview_edit 对象已被删除，跳过高亮应用")
                return
            
            element_type = self.current_selection.get('type')
            peripheral = self.current_selection.get('peripheral')
            register = self.current_selection.get('register')
            field = self.current_selection.get('field')
            interrupt = self.current_selection.get('interrupt')
            
            # 确定元素名称
            element_name = None
            if element_type == 'peripheral':
                element_name = peripheral
            elif element_type == 'register':
                element_name = register
            elif element_type == 'field':
                element_name = f"{register}.{field}"
            elif element_type == 'interrupt':
                element_name = interrupt
            
            self.logger.debug(f"应用高亮: type={element_type}, peripheral={peripheral}, element_name={element_name}")
            
            if element_name and peripheral and element_type:
                # 设置当前高亮
                self.preview_edit.set_current_highlight(element_type, peripheral, element_name)
                
                # 更新状态栏
                try:
                    self.status_label.setText(
                        f"{t('status.selected')}: {element_type} - {element_name}"
                    )
                except RuntimeError:
                    # 状态标签也已被删除
                    pass
                self.logger.debug(f"高亮已应用: {element_type} - {element_name}")
            else:
                # 清除高亮
                self.preview_edit.clear_highlight()
                self.logger.debug("已清除高亮")
        except RuntimeError as e:
            self.logger.warning(f"Qt对象已被删除: {e}")
        except Exception as e:
            self.logger.error(f"应用高亮时出错: {e}")
    
    def _find_line_for_selection(self, selection: Dict[str, Any]) -> Optional[int]:
        """根据选择信息查找对应的行号"""
        element_type = selection.get('type')
        peripheral = selection.get('peripheral')
        register = selection.get('register')
        field = selection.get('field')
        interrupt = selection.get('interrupt')
        
        # 遍历行号映射
        for line_num, (elem_type, periph_name, elem_name) in self.line_map.items():
            if elem_type == element_type and periph_name == peripheral:
                if element_type == 'peripheral':
                    return line_num
                elif element_type == 'register' and elem_name == register:
                    return line_num
                elif element_type == 'field' and elem_name == f"{register}.{field}":
                    return line_num
                elif element_type == 'interrupt' and elem_name == interrupt:
                    return line_num
        
        return None
    
    def _jump_to_element(self, element_type: str, peripheral_name: str, element_name: str):
        """跳转到指定元素"""
        key = (element_type, peripheral_name, element_name)
        self.logger.info(f"尝试跳转到元素: key={key}")
        self.logger.info(f"element_ranges 中的所有keys: {list(self.element_ranges.keys())[:5]}...")  # 只显示前5个
        
        if key not in self.element_ranges:
            self.logger.warning(f"key {key} 不在 element_ranges 中，无法跳转")
            return
        
        start_line, end_line = self.element_ranges[key]
        self.logger.info(f"找到元素，跳转到行 {start_line}")
        self._jump_to_line(start_line)
    
    def _jump_to_line(self, line_num: int):
        """跳转到指定行（带平滑滚动动画和居中）"""
        self.logger.info(f"跳转到行 {line_num}")
        
        # 保存当前滚动位置
        scrollbar = self.preview_edit.verticalScrollBar()
        old_value = scrollbar.value()
        
        # 设置光标到目标行
        cursor = QTextCursor(self.preview_edit.document())
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        cursor.movePosition(QTextCursor.MoveOperation.NextBlock, QTextCursor.MoveMode.MoveAnchor, line_num - 1)
        self.preview_edit.setTextCursor(cursor)
        
        # 临时居中光标以获取目标滚动位置
        self.preview_edit.centerCursor()
        target_value = scrollbar.value()
        
        # 如果位置没变，无需动画
        if abs(old_value - target_value) < 5:
            self.logger.info(f"已跳转到行 {line_num}，位置不变")
            return
        
        # 先滚回原位，然后用动画平滑滚动到目标位置
        scrollbar.setValue(old_value)
        self._animate_scroll_to(target_value)
        
        self.logger.info(f"已跳转到行 {line_num}，从 {old_value} 滚动到 {target_value}")
    
    def _animate_scroll_to(self, target_value: int):
        """平滑滚动到目标位置"""
        try:
            from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
            scrollbar = self.preview_edit.verticalScrollBar()
            current_value = scrollbar.value()
            
            # 如果距离很近，直接跳转
            if abs(current_value - target_value) < 5:
                scrollbar.setValue(target_value)
                return
            
            # 创建滚动动画
            if not hasattr(self, '_scroll_animation'):
                self._scroll_animation = QPropertyAnimation(scrollbar, b"value")
                self._scroll_animation.setDuration(300)  # 300ms
                self._scroll_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            
            # 停止之前的动画
            self._scroll_animation.stop()
            
            # 设置动画参数
            self._scroll_animation.setStartValue(current_value)
            self._scroll_animation.setEndValue(target_value)
            
            # 启动动画
            self._scroll_animation.start()
        except Exception as e:
            self.logger.warning(f"滚动动画失败，直接跳转: {e}")
            self.preview_edit.verticalScrollBar().setValue(target_value)
    
    def on_text_changed(self):
        """文本变化回调"""
        # 如果正在程序更新文本，则不处理（避免循环）
        if self._is_updating:
            return
        # 不再自动触发编辑处理，用户需要点击保存按钮
        self.status_label.setText(t("status.edited_not_saved"))
    
    def save_edited_xml(self):
        """保存编辑后的XML到设备信息（支持撤销）"""
        # 获取编辑后的XML
        edited_xml = self.preview_edit.toPlainText()
        
        try:
            # 尝试解析编辑后的XML
            from ...core.svd_parser import SVDParser
            parser = SVDParser()
            new_device_info = parser.parse_string(edited_xml)
            
            # 更新状态管理器的设备信息（支持撤销）
            if self.state_manager:
                # 保存旧的设备信息快照
                old_snapshot = self.state_manager.get_device_state_snapshot()
                
                # 创建执行函数
                def execute():
                    self.state_manager.device_info = new_device_info
                    
                    # 通知设备信息已更新
                    if self.coordinator:
                        self.coordinator.notify_device_info_updated(new_device_info)
                    
                    # 手动触发状态变更，更新树状图
                    # 通过coordinator获取peripheral_manager来更新
                    if self.coordinator:
                        peripheral_manager = self.coordinator.get_peripheral_manager()
                        if peripheral_manager:
                            peripheral_manager.update_peripheral_tree()
                
                # 创建撤销函数
                def undo():
                    self.state_manager.restore_device_state(old_snapshot)
                    
                    # 通知设备信息已更新
                    if self.coordinator:
                        self.coordinator.notify_device_info_updated(self.state_manager.device_info)
                    
                    # 手动触发状态变更，更新树状图
                    if self.coordinator:
                        peripheral_manager = self.coordinator.get_peripheral_manager()
                        if peripheral_manager:
                            peripheral_manager.update_peripheral_tree()
                
                # 创建命令并执行
                from ...core.command_history import Command
                command = Command(
                    execute=execute,
                    undo=undo,
                    description=t("cmd.save_edited_xml")
                )
                self.state_manager.execute_command(command)
            
            # 更新状态栏
            self.status_label.setText(t("status.xml_saved"))
            self.logger.debug("XML已保存并同步到树状图")
            
        except Exception as e:
            # 解析失败，显示错误信息
            self.status_label.setText(f"{t('status.xml_parse_error')}: {str(e)}")
            self.logger.warning(f"XML解析失败: {e}")
            import traceback
            self.logger.error(f"错误详情: {traceback.format_exc()}")
            # 显示错误对话框
            QMessageBox.warning(self, t("error.title"), f"{t('status.xml_parse_error')}: {str(e)}")
        
        # 发射编辑信号（用于其他用途）
        self.xml_edited.emit(edited_xml)
    
    def _on_edit_timeout(self):
        """编辑超时处理"""
        # 获取编辑后的XML
        edited_xml = self.preview_edit.toPlainText()
        
        try:
            # 尝试解析编辑后的XML
            from ...core.svd_parser import SVDParser
            parser = SVDParser()
            new_device_info = parser.parse_string(edited_xml)
            
            # 更新状态管理器的设备信息
            if self.state_manager:
                self.state_manager.device_info = new_device_info
                
                # 通知设备信息已更新
                if self.coordinator:
                    self.coordinator.notify_device_info_updated(new_device_info)
            
            # 更新状态栏
            self.status_label.setText(f"{t('status.xml_edited')}")
            self.logger.debug("XML已编辑并同步到树状图")
            
        except Exception as e:
            # 解析失败，只发射编辑信号
            self.xml_edited.emit(edited_xml)
            self.status_label.setText(f"{t('status.xml_edited')} (解析失败)")
            self.logger.warning(f"XML解析失败: {e}")
        
        # 发射编辑信号（用于其他用途）
        self.xml_edited.emit(edited_xml)
    
    def on_preview_selection_changed(self):
        """预览窗口选择变化"""
        cursor = self.preview_edit.textCursor()
        
        # 检查是否有选中的文本
        if cursor.hasSelection():
            # 获取选中的起始和结束位置
            start_pos = cursor.selectionStart()
            end_pos = cursor.selectionEnd()
            
            # 获取起始和结束的行号
            start_cursor = QTextCursor(self.preview_edit.document())
            start_cursor.setPosition(start_pos)
            start_line = start_cursor.blockNumber() + 1
            
            end_cursor = QTextCursor(self.preview_edit.document())
            end_cursor.setPosition(end_pos)
            end_line = end_cursor.blockNumber() + 1
            
            # 查找选中的元素
            selected_element = None
            for (element_type, peripheral_name, element_name), (elem_start, elem_end) in self.element_ranges.items():
                # 检查元素范围是否与选择范围重叠
                if not (elem_end < start_line or elem_start > end_line):
                    selected_element = (element_type, peripheral_name, element_name)
                    break
            
            if selected_element:
                element_type, peripheral_name, element_name = selected_element
                
                # 发射选择信号
                self.element_selected.emit(element_type, peripheral_name, element_name)
                
                # 更新状态栏
                self.status_label.setText(
                    f"{t('status.selected')}: {element_type} - {element_name}"
                )
                return
        
        # 如果没有选中文本，使用光标所在行
        line_num = cursor.blockNumber() + 1  # 行号从1开始
        
        # 查找对应的元素
        element_info = self.line_map.get(line_num)
        
        if element_info:
            element_type, peripheral_name, element_name = element_info
            
            # 发射选择信号
            self.element_selected.emit(element_type, peripheral_name, element_name)
            
            # 更新状态栏
            self.status_label.setText(
                f"{t('status.selected')}: {element_type} - {element_name}"
            )
    
    def jump_to_selection(self):
        """跳转到当前选中的元素"""
        self.logger.info("=== jump_to_selection 被调用 ===")
        self.logger.info(f"element_ranges 数量: {len(self.element_ranges)}")
        if self.element_ranges:
            self.logger.info(f"element_ranges 中的所有keys: {list(self.element_ranges.keys())}")
        
        # 如果element_ranges为空，先更新预览
        if not self.element_ranges:
            self.logger.info("element_ranges为空，调用 _force_update_preview()")
            self._force_update_preview()
            self.logger.info(f"更新后 element_ranges 数量: {len(self.element_ranges)}")
            if self.element_ranges:
                self.logger.info(f"更新后 element_ranges 中的所有keys: {list(self.element_ranges.keys())}")
        
        selection = self.state_manager.get_selection()
        self.logger.info(f"当前选择: {selection}")
        if selection:
            self.highlight_element(selection)
        else:
            self.logger.warning("没有选择信息，无法跳转")
    
    def get_selected_element(self) -> Optional[Tuple[str, str, str]]:
        """获取当前选中的元素"""
        cursor = self.preview_edit.textCursor()
        line_num = cursor.blockNumber() + 1  # 行号从1开始
        
        element_info = self.line_map.get(line_num)
        if element_info:
            return element_info
        
        return None
    
    def cleanup(self):
        """清理资源，注销回调"""
        self.logger.debug("开始清理 RealtimePreviewWidget 资源")
        
        # 停止定时器
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
        if hasattr(self, 'edit_timer'):
            self.edit_timer.stop()
        
        # 注销状态管理器回调
        if self.state_manager:
            try:
                self.state_manager.unregister_state_change_callback(self.on_state_changed)
                self.state_manager.unregister_selection_change_callback(self.on_selection_changed)
                self.logger.debug("已注销状态管理器回调")
            except Exception as e:
                self.logger.warning(f"注销状态管理器回调时出错: {e}")
        
        # 断开协调器信号
        if self.coordinator:
            try:
                self.coordinator.device_info_updated.disconnect(self.on_device_info_updated)
                self.coordinator.selection_changed.disconnect(self.on_coordinator_selection_changed)
                self.logger.debug("已断开协调器信号")
            except Exception as e:
                self.logger.warning(f"断开协调器信号时出错: {e}")
        
        self.logger.debug("RealtimePreviewWidget 资源清理完成")
