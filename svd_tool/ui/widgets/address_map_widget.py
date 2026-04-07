"""
外设地址映射图控件
从main_window.py中提取的独立组件
"""
from PyQt6.QtWidgets import QWidget, QToolTip
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QRectF
from PyQt6.QtGui import (QColor, QBrush, QFont, QPainter, QPen, QPaintEvent,
                          QLinearGradient, QRadialGradient, QFontMetrics)
import logging
from ...i18n.i18n import t


class AddressMapWidget(QWidget):
    """外设地址映射图控件"""
    # 定义信号
    register_clicked = pyqtSignal(object)  # 发射寄存器对象
    
    # 颜色方案
    COLORS = {
        'bg': QColor(250, 250, 252),
        'header_bg': QColor(41, 98, 255),
        'header_text': QColor(255, 255, 255),
        'axis_line': QColor(180, 180, 190),
        'axis_text': QColor(100, 100, 110),
        'register_normal': QColor(66, 133, 244),
        'register_hover': QColor(100, 165, 255),
        'register_selected': QColor(255, 152, 0),
        'register_text': QColor(255, 255, 255),
        'register_text_dark': QColor(50, 50, 60),
        'grid_line': QColor(230, 230, 235),
        'tooltip_bg': QColor(50, 50, 55, 230),
        'tooltip_text': QColor(255, 255, 255),
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(160)
        self.peripheral = None
        self.registers = []
        self.register_rects = {}  # 寄存器名 -> QRect
        self.selected_register_name = None
        self.hovered_register_name = None
        self.setMouseTracking(True)
        self.use_uniform_width = True
        
    def set_peripheral(self, peripheral):
        """设置外设数据"""
        self.peripheral = peripheral
        if peripheral:
            self.registers = list(peripheral.registers.values())
        else:
            self.registers = []
        self.register_rects.clear()
        self.selected_register_name = None
        self.update()
        
    def set_selected_register(self, register_name):
        """设置选中的寄存器"""
        self.selected_register_name = register_name
        self.update()
    
    def set_uniform_width_mode(self, enabled: bool):
        """设置是否使用均匀宽度模式"""
        self.use_uniform_width = enabled
        self.update()
    
    def _draw_rounded_rect(self, painter, x, y, w, h, radius=4):
        """绘制圆角矩形路径"""
        from PyQt6.QtGui import QPainterPath
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, y, w, h), radius, radius)
        return path
    
    def paintEvent(self, event: QPaintEvent):
        """绘制地址映射图"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 绘制整体背景
        painter.fillRect(event.rect(), self.COLORS['bg'])
        
        if not self.peripheral:
            painter.setPen(QPen(self.COLORS['axis_text']))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(event.rect(), Qt.AlignmentFlag.AlignCenter, t("label.no_peripheral_data"))
            return
        
        margin_left = 45
        margin_right = 45
        margin_top = 8
        available_width = self.width() - margin_left - margin_right
        
        # 绘制标题栏
        header_height = 28
        header_rect = QRectF(margin_left, margin_top, available_width, header_height)
        header_path = self._draw_rounded_rect(painter, margin_left, margin_top, 
                                                available_width, header_height, 6)
        # 只有顶部圆角的标题栏
        from PyQt6.QtGui import QPainterPath
        header_path = QPainterPath()
        header_path.addRoundedRect(QRectF(margin_left, margin_top, available_width, header_height), 6, 6)
        grad = QLinearGradient(margin_left, margin_top, margin_left + available_width, margin_top)
        grad.setColorAt(0, QColor(41, 98, 255))
        grad.setColorAt(1, QColor(66, 133, 244))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawPath(header_path)
        
        # 标题文字
        painter.setPen(QPen(self.COLORS['header_text']))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        title = t("label.peripheral_address_map", name=self.peripheral.name)
        painter.drawText(QRect(margin_left + 10, margin_top + 2, available_width - 20, header_height),
                        Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, title)
        
        # 地址范围文本
        try:
            base_addr = int(self.peripheral.base_address, 16) if self.peripheral.base_address.startswith('0x') else int(self.peripheral.base_address)
            block_size = int(self.peripheral.address_block['size'], 16) if self.peripheral.address_block['size'].startswith('0x') else int(self.peripheral.address_block['size'])
            
            addr_text = t("label.address_range", start=base_addr, end=base_addr + block_size - 1)
            painter.setPen(QPen(QColor(200, 210, 230)))
            painter.setFont(QFont("Consolas", 8))
            fm = QFontMetrics(painter.font())
            addr_width = fm.horizontalAdvance(addr_text)
            painter.drawText(QRect(self.width() - margin_right - addr_width - 15, margin_top + 2, 
                                   addr_width + 10, header_height),
                           Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, addr_text)
        except (ValueError, AttributeError, TypeError):
            pass
        
        # 绘制寄存器区域
        content_y = margin_top + header_height + 2
        content_height = 50
        bar_height = 24
        
        reg_count = len(self.registers)
        if reg_count == 0:
            painter.setPen(QPen(self.COLORS['axis_text']))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(QRect(margin_left, content_y, available_width, content_height),
                           Qt.AlignmentFlag.AlignCenter, t("label.no_register_data"))
            return
        
        # 底部地址轴
        axis_y = content_y + content_height - 5
        
        try:
            base_addr = int(self.peripheral.base_address, 16) if self.peripheral.base_address.startswith('0x') else int(self.peripheral.base_address)
            block_size = int(self.peripheral.address_block['size'], 16) if self.peripheral.address_block['size'].startswith('0x') else int(self.peripheral.address_block['size'])
            
            # 绘制浅色网格线
            painter.setPen(QPen(self.COLORS['grid_line'], 1, Qt.PenStyle.DashLine))
            for i in range(5):
                gx = margin_left + (available_width * i // 4)
                painter.drawLine(gx, content_y + 4, gx, axis_y)
            
            # 绘制地址轴
            painter.setPen(QPen(self.COLORS['axis_line'], 1))
            painter.drawLine(margin_left, axis_y, margin_left + available_width, axis_y)
            
            # 轴刻度标签
            painter.setFont(QFont("Consolas", 7))
            painter.setPen(QPen(self.COLORS['axis_text']))
            for i in range(5):
                tick_x = margin_left + (available_width * i // 4)
                tick_addr = base_addr + (block_size * i // 4)
                painter.drawLine(tick_x, axis_y, tick_x, axis_y + 4)
                addr_label = f"0x{tick_addr:08X}"
                addr_label_width = painter.fontMetrics().horizontalAdvance(addr_label)
                painter.drawText(tick_x - addr_label_width // 2, axis_y + 14, addr_label)
            
            # 绘制寄存器条
            simplify_display = reg_count > 20
            
            for i, reg in enumerate(self.registers):
                try:
                    offset = int(reg.offset, 16) if reg.offset.startswith('0x') else int(reg.offset)
                    
                    if self.use_uniform_width:
                        reg_width_px = available_width / reg_count
                        pos = i * reg_width_px
                    else:
                        pos = (offset / block_size) * available_width if block_size > 0 else 0
                        size_bits = int(reg.size, 16) if reg.size.startswith('0x') else int(reg.size)
                        size_bytes = max(size_bits // 8, 1)
                        reg_width_px = (size_bytes / block_size) * available_width
                    
                    # 最小宽度和间距
                    min_width = 12
                    gap = 1  # 寄存器之间的间距
                    reg_width_px = max(min_width, reg_width_px - gap)
                    
                    rect_x = margin_left + pos + gap // 2
                    rect_y = content_y + 8
                    rect_width = reg_width_px
                    rect_height = bar_height
                    
                    is_selected = (reg.name == self.selected_register_name)
                    is_hovered = (reg.name == self.hovered_register_name)
                    
                    # 绘制寄存器块（圆角矩形）
                    bar_path = QPainterPath()
                    bar_path.addRoundedRect(QRectF(rect_x, rect_y, rect_width, rect_height), 4, 4)
                    
                    if is_selected:
                        # 选中：暖橙色渐变
                        grad = QLinearGradient(rect_x, rect_y, rect_x, rect_y + rect_height)
                        grad.setColorAt(0, QColor(255, 167, 38))
                        grad.setColorAt(1, QColor(245, 124, 0))
                        painter.setBrush(QBrush(grad))
                        painter.setPen(QPen(QColor(230, 81, 0), 2))
                    elif is_hovered:
                        # 悬停：浅蓝渐变
                        grad = QLinearGradient(rect_x, rect_y, rect_x, rect_y + rect_height)
                        grad.setColorAt(0, QColor(100, 181, 246))
                        grad.setColorAt(1, QColor(66, 165, 245))
                        painter.setBrush(QBrush(grad))
                        painter.setPen(QPen(QColor(30, 136, 229), 1.5))
                    else:
                        # 普通：蓝色渐变
                        grad = QLinearGradient(rect_x, rect_y, rect_x, rect_y + rect_height)
                        grad.setColorAt(0, QColor(66, 133, 244))
                        grad.setColorAt(1, QColor(48, 112, 220))
                        painter.setBrush(QBrush(grad))
                        painter.setPen(QPen(QColor(30, 80, 180), 1))
                    
                    painter.drawPath(bar_path)
                    
                    # 存储矩形区域
                    self.register_rects[reg.name] = (int(rect_x), int(rect_y), int(rect_width), int(rect_height))
                    
                    # 绘制寄存器名称
                    painter.setPen(QPen(self.COLORS['register_text']))
                    
                    force_show = is_selected or is_hovered
                    
                    if simplify_display:
                        if force_show or rect_width > 40 or i % 5 == 0:
                            self._draw_register_label(painter, reg.name, rect_x, rect_y, 
                                                      rect_width, rect_height, force_show)
                    else:
                        if rect_width > 30 or force_show:
                            self._draw_register_label(painter, reg.name, rect_x, rect_y,
                                                      rect_width, rect_height, force_show)
                        
                except (ValueError, AttributeError):
                    continue
                    
        except (ValueError, AttributeError):
            painter.setPen(QPen(QColor(200, 50, 50)))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(QRect(margin_left, content_y, available_width, content_height),
                           Qt.AlignmentFlag.AlignCenter, t("label.cannot_parse_address_data"))
    
    def _draw_register_label(self, painter, name, x, y, w, h, force=False):
        """绘制寄存器名称标签"""
        painter.setFont(QFont("Segoe UI", 8))
        fm = QFontMetrics(painter.font())
        text_width = fm.horizontalAdvance(name)
        
        if text_width <= w - 4:
            # 名称可以在块内显示
            painter.setPen(QPen(self.COLORS['register_text']))
            text_rect = QRect(int(x), int(y), int(w), int(h))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, name)
        elif force and w > 15:
            # 强制显示但宽度不够，显示在块下方
            painter.setPen(QPen(self.COLORS['register_text_dark']))
            # 截断名称
            elided = fm.elidedText(name, Qt.TextElideMode.ElideRight, int(w) - 2)
            text_rect = QRect(int(x), int(y), int(w), int(h))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, elided)
        elif w > 20:
            # 显示缩写
            painter.setPen(QPen(self.COLORS['register_text']))
            abbrev = name[:3] + ".." if len(name) > 3 else name
            text_rect = QRect(int(x), int(y), int(w), int(h))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, abbrev)
    
    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if not self.peripheral or not self.registers:
            return
            
        pos = event.pos()
        for reg in self.registers:
            if reg.name in self.register_rects:
                x, y, w, h = self.register_rects[reg.name]
                if x <= pos.x() <= x + w and y <= pos.y() <= y + h:
                    self.register_clicked.emit(reg)
                    return
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if not self.peripheral or not self.registers:
            return
            
        pos = event.pos()
        old_hover = self.hovered_register_name
        
        self.hovered_register_name = None
        for reg in self.registers:
            if reg.name in self.register_rects:
                x, y, w, h = self.register_rects[reg.name]
                if x <= pos.x() <= x + w and y <= pos.y() <= y + h:
                    self.hovered_register_name = reg.name
                    # 显示tooltip
                    try:
                        offset = reg.offset if reg.offset else "?"
                        size = reg.size if reg.size else "?"
                        desc = reg.description if reg.description else ""
                        tip = f"<b>{reg.name}</b><br>Offset: {offset}<br>Size: {size}"
                        if desc:
                            tip += f"<br>{desc}"
                        QToolTip.showText(event.globalPosition().toPoint(), tip, self)
                    except Exception:
                        pass
                    break
        
        if old_hover != self.hovered_register_name:
            self.update()
        
        if not self.hovered_register_name:
            QToolTip.hideText()
        
        super().mouseMoveEvent(event)
    
    def leaveEvent(self, event):
        """鼠标离开事件"""
        if self.hovered_register_name:
            self.hovered_register_name = None
            self.update()
        QToolTip.hideText()
        super().leaveEvent(event)