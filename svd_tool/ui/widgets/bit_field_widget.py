"""
寄存器位域图控件
从main_window.py中提取的独立组件

改进版：
- 位域名称完整显示（窄位域使用斜线连接的外部标签）
- 32位完整标尺
- 颜色方案更清晰
- 保留位用灰色标注
- 悬停时显示详细信息
"""
from PyQt6.QtWidgets import QWidget, QToolTip
from PyQt6.QtCore import Qt, pyqtSignal, QRect
from PyQt6.QtGui import QColor, QBrush, QFont, QPainter, QPen, QPaintEvent, QFontMetrics
import logging
from ...i18n.i18n import t
from ...utils.logger import get_logger

logger = get_logger("bit_field_widget")


class BitFieldWidget(QWidget):
    """寄存器位域图控件"""
    # 定义信号
    field_clicked = pyqtSignal(object)  # 发射字段对象
    jump_to_source_peripheral = pyqtSignal(str)  # 跳转到源外设
    
    # 预定义颜色调色板（避免颜色重复）
    FIELD_COLORS = [
        QColor(70, 130, 180),    # 钢蓝
        QColor(60, 179, 113),    # 中海绿
        QColor(205, 133, 63),    # 秘鲁色
        QColor(147, 112, 219),   # 中紫
        QColor(220, 88, 88),     # 浅红
        QColor(72, 175, 150),    # 青绿
        QColor(180, 130, 200),   # 淡紫
        QColor(140, 180, 80),    # 黄绿
        QColor(200, 150, 100),   # 棕褐
        QColor(100, 160, 200),   # 天蓝
        QColor(190, 120, 130),   # 玫瑰
        QColor(120, 180, 160),   # 薄荷
        QColor(170, 140, 100),   # 驼色
        QColor(130, 130, 190),   # 蓝紫
        QColor(160, 190, 130),   # 草绿
        QColor(200, 170, 140),   # 杏色
    ]
    
    RESERVED_COLOR = QColor(220, 220, 220)  # 保留位颜色
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.register = None
        self.fields = []
        self.field_rects = {}  # 字段名 -> QRect
        self.selected_field_name = None
        self.hovered_field_name = None
        self.source_peripheral_name = None
        self.setMouseTracking(True)
        
        # 布局参数
        self._margin_left = 30
        self._margin_right = 30
        self._margin_top = 35
        self._margin_bottom = 80  # 底部留空给外部标签
        self._bit_area_y = 60     # 位域矩形区域的Y坐标
        self._bit_area_height = 36  # 位域矩形高度（增大以容纳名称+位范围）
        self._ruler_y = 60        # 标尺Y坐标
        self._label_area_y = 100  # 位编号标注区域
    
    def set_register(self, register, source_peripheral_name=None):
        """设置寄存器数据"""
        self.register = register
        if source_peripheral_name is not None and source_peripheral_name != "":
            self.source_peripheral_name = source_peripheral_name
        else:
            self.source_peripheral_name = None
        if register:
            self.fields = list(register.fields.values())
        else:
            self.fields = []
        self.field_rects.clear()
        self.selected_field_name = None
        self._update_minimum_height()
        self.update()
    
    def _update_minimum_height(self):
        """根据内容更新最小高度"""
        if not self.fields:
            self.setMinimumHeight(120)
            return
        # 检查是否有需要外部标签的窄位域
        has_narrow_fields = any(
            self._get_field_pixel_width(f) < 50 for f in self.fields
        )
        if has_narrow_fields:
            self.setMinimumHeight(220)
        else:
            self.setMinimumHeight(170)
    
    def _get_field_pixel_width(self, field):
        """估算位域的像素宽度"""
        width = self.width() - self._margin_left - self._margin_right
        if width <= 0:
            width = 600
        return (field.bit_width / 32) * width
    
    def set_source_peripheral(self, source_peripheral_name):
        """设置源外设名称"""
        self.source_peripheral_name = source_peripheral_name
        self.update()
    
    def set_selected_field(self, field_name):
        """设置选中的位域"""
        self.selected_field_name = field_name
        self.update()
    
    def _get_field_color(self, index: int) -> QColor:
        """获取位域颜色"""
        return self.FIELD_COLORS[index % len(self.FIELD_COLORS)]
    
    def _get_bit_x(self, bit: float) -> float:
        """获取指定位的X坐标"""
        width = self.width() - self._margin_left - self._margin_right
        return self._margin_left + (bit / 32) * width
    
    def paintEvent(self, event: QPaintEvent):
        """绘制位域图"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 绘制背景
        painter.fillRect(event.rect(), QColor(250, 250, 252))
        
        # 如果没有寄存器但有源外设名称，显示继承信息
        if not self.register and self.source_peripheral_name:
            self._paint_derived_info(painter, event.rect())
            painter.end()
            return
        
        if not self.register:
            painter.setFont(QFont("Arial", 11))
            painter.setPen(QColor(150, 150, 150))
            painter.drawText(event.rect(), Qt.AlignmentFlag.AlignCenter, t("label.no_register_data"))
            painter.end()
            return
        
        # 绘制标题
        self._paint_title(painter)
        
        # 绘制完整的32位背景条
        self._paint_register_bar(painter)
        
        # 绘制保留位区域
        self._paint_reserved_bits(painter)
        
        # 绘制位域矩形
        self._paint_fields(painter)
        
        # 绘制位标尺
        self._paint_ruler(painter)
        
        # 绘制外部标签（用于窄位域）
        self._paint_external_labels(painter)
        
        painter.end()
    
    def _paint_derived_info(self, painter: QPainter, rect: QRect):
        """绘制继承信息"""
        center_x = rect.x() + rect.width() // 2
        center_y = rect.y() + rect.height() // 2
        
        # 绘制外框
        box_rect = QRect(center_x - 180, center_y - 50, 360, 100)
        painter.setPen(QPen(QColor(180, 180, 200), 2))
        painter.setBrush(QColor(245, 245, 250))
        painter.drawRoundedRect(box_rect, 10, 10)
        
        # 绘制继承信息
        painter.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        painter.setPen(QColor(80, 80, 120))
        text = f"{t('label.derived_from')}: {self.source_peripheral_name}"
        text_rect = painter.fontMetrics().boundingRect(text)
        painter.drawText(center_x - text_rect.width() // 2, center_y - 10, text)
        
        # 绘制提示文本
        painter.setFont(QFont("Arial", 10))
        painter.setPen(QColor(100, 100, 180))
        hint_text = t("label.click_to_jump")
        hint_rect = painter.fontMetrics().boundingRect(hint_text)
        painter.drawText(center_x - hint_rect.width() // 2, center_y + 20, hint_text)
    
    def _paint_title(self, painter: QPainter):
        """绘制标题"""
        painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        painter.setPen(QColor(60, 60, 80))
        title_text = t("label.register_bit_field_32bit", name=self.register.name)
        
        if self.source_peripheral_name:
            title_text += f" ({t('label.from_source')}: {self.source_peripheral_name})"
        
        painter.drawText(self._margin_left, 22, title_text)
    
    def _paint_register_bar(self, painter: QPainter):
        """绘制完整的32位寄存器背景条"""
        x1 = self._get_bit_x(0)
        x2 = self._get_bit_x(32)
        bar_width = x2 - x1
        
        # 绘制背景条
        painter.setPen(QPen(QColor(180, 180, 190), 1))
        painter.setBrush(QColor(240, 240, 245))
        painter.drawRect(int(x1), self._bit_area_y, int(bar_width), self._bit_area_height)
        
        # 绘制每个位的分隔线（浅色）
        painter.setPen(QPen(QColor(210, 210, 215), 1, Qt.PenStyle.DotLine))
        for bit in range(1, 32):
            x = self._get_bit_x(bit)
            painter.drawLine(int(x), self._bit_area_y, int(x), self._bit_area_y + self._bit_area_height)
    
    def _paint_reserved_bits(self, painter: QPainter):
        """绘制保留位区域（未被位域占用的位）"""
        # 收集已占用的位
        occupied = [False] * 32
        for field in self.fields:
            try:
                start = field.bit_offset
                width = field.bit_width
                for i in range(start, min(start + width, 32)):
                    occupied[i] = True
            except (ValueError, AttributeError):
                continue
        
        # 绘制未占用的连续区域
        x1 = self._get_bit_x(0)
        x2 = self._get_bit_x(32)
        
        # 找出所有保留位区间
        reserved_ranges = []
        start_bit = None
        for bit in range(32):
            if not occupied[bit]:
                if start_bit is None:
                    start_bit = bit
            else:
                if start_bit is not None:
                    reserved_ranges.append((start_bit, bit))
                    start_bit = None
        if start_bit is not None:
            reserved_ranges.append((start_bit, 32))
        
        # 绘制保留位
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(230, 230, 235, 150))
        for rs, re in reserved_ranges:
            rx1 = self._get_bit_x(rs)
            rx2 = self._get_bit_x(re)
            painter.drawRect(int(rx1), self._bit_area_y, int(rx2 - rx1), self._bit_area_height)
    
    def _paint_fields(self, painter: QPainter):
        """绘制位域矩形"""
        self.field_rects.clear()
        
        for idx, field in enumerate(self.fields):
            try:
                start = field.bit_offset
                bit_width_val = field.bit_width
                
                x1 = self._get_bit_x(start)
                x2 = self._get_bit_x(start + bit_width_val)
                field_width = x2 - x1
                
                # 获取颜色
                base_color = self._get_field_color(idx)
                
                # 判断状态
                is_selected = (field.name == self.selected_field_name)
                is_hovered = (field.name == self.hovered_field_name)
                
                # 根据状态调整颜色和边框
                if is_selected:
                    color = base_color.darker(110)
                    border_pen = QPen(QColor(255, 80, 80), 3)
                elif is_hovered:
                    color = base_color.lighter(115)
                    border_pen = QPen(QColor(50, 120, 220), 2)
                else:
                    color = base_color
                    border_pen = QPen(color.darker(150), 1)
                
                # 绘制位域矩形
                painter.setBrush(QBrush(color))
                painter.setPen(border_pen)
                
                rect_x = int(x1)
                rect_y = self._bit_area_y
                rect_w = max(int(field_width), 2)  # 最小宽度2像素
                rect_h = self._bit_area_height
                
                painter.drawRect(rect_x, rect_y, rect_w, rect_h)
                
                # 存储矩形区域
                self.field_rects[field.name] = (rect_x, rect_y, rect_w, rect_h)
                
                # 在位域矩形内部显示名称和位范围
                fm = QFontMetrics(QFont("Arial", 9))
                name_text = field.name
                name_width = fm.horizontalAdvance(name_text)
                
                painter.setPen(QPen(Qt.GlobalColor.white if color.lightness() < 180 else Qt.GlobalColor.black, 1))
                
                # 位范围文本
                bit_range = f"[{start}:{start + bit_width_val - 1}]"
                range_fm = QFontMetrics(QFont("Arial", 7))
                range_width = range_fm.horizontalAdvance(bit_range)
                
                # 判断是否能完整显示名称+位范围
                total_needed = max(name_width, range_width) + 8
                
                if field_width >= total_needed and field_width >= 40:
                    # 空间足够，居中显示名称和位范围（名称上方，位范围下方）
                    painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
                    text_x = rect_x + (rect_w - name_width) // 2
                    text_y = rect_y + rect_h // 2 - 2
                    painter.drawText(text_x, text_y, name_text)
                    
                    # 位范围显示在名称下方
                    painter.setFont(QFont("Arial", 7))
                    painter.setPen(QPen(
                        QColor(255, 255, 255, 200) if color.lightness() < 180 else QColor(80, 80, 80, 200), 1))
                    range_x = rect_x + (rect_w - range_width) // 2
                    range_y = text_y + range_fm.height()
                    painter.drawText(range_x, range_y, bit_range)
                elif field_width >= name_width + 8:
                    # 空间只够显示名称
                    painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
                    text_x = rect_x + (rect_w - name_width) // 2
                    text_y = rect_y + rect_h // 2 + fm.ascent() // 2 - 1
                    painter.drawText(text_x, text_y, name_text)
                elif field_width >= 20:
                    # 空间有限，使用小字体
                    painter.setFont(QFont("Arial", 7, QFont.Weight.Bold))
                    small_fm = QFontMetrics(QFont("Arial", 7, QFont.Weight.Bold))
                    small_name_width = small_fm.horizontalAdvance(name_text)
                    if field_width >= small_name_width + 4:
                        text_x = rect_x + (rect_w - small_name_width) // 2
                        text_y = rect_y + rect_h // 2 + small_fm.ascent() // 2 - 1
                        painter.drawText(text_x, text_y, name_text)
                    else:
                        # 显示首字母
                        abbrev = name_text[0]
                        painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
                        painter.drawText(rect_x + rect_w // 2 - 4, rect_y + rect_h // 2 + 4, abbrev)
                # 太窄的位域名称将在外部标签中显示
                
            except (ValueError, AttributeError):
                continue
    
    def _paint_ruler(self, painter: QPainter):
        """绘制位标尺"""
        x1 = self._get_bit_x(0)
        x2 = self._get_bit_x(32)
        ruler_y = self._bit_area_y + self._bit_area_height + 5
        
        # 绘制标尺线
        painter.setPen(QPen(QColor(100, 100, 110), 1))
        painter.drawLine(int(x1), ruler_y, int(x2), ruler_y)
        
        # 绘制刻度和编号
        painter.setFont(QFont("Arial", 8))
        painter.setPen(QColor(80, 80, 90))
        
        for bit in range(0, 33, 4):  # 每4位一个刻度
            x = self._get_bit_x(bit)
            
            # 长刻度
            if bit % 8 == 0:
                painter.drawLine(int(x), ruler_y, int(x), ruler_y + 8)
                # 显示编号
                text = str(bit)
                fm = painter.fontMetrics()
                text_width = fm.horizontalAdvance(text)
                painter.drawText(int(x) - text_width // 2, ruler_y + 20, text)
            else:
                # 短刻度
                painter.drawLine(int(x), ruler_y, int(x), ruler_y + 5)
    
    def _paint_external_labels(self, painter: QPainter):
        """绘制外部标签（用于窄位域）"""
        label_y_base = self._bit_area_y + self._bit_area_height + 30
        
        # 收集需要外部标签的位域
        labels_needed = []
        for idx, field in enumerate(self.fields):
            try:
                start = field.bit_offset
                bit_width_val = field.bit_width
                
                x1 = self._get_bit_x(start)
                x2 = self._get_bit_x(start + bit_width_val)
                field_width = x2 - x1
                
                # 窄位域或名字显示不下的位域需要外部标签
                fm = QFontMetrics(QFont("Arial", 8))
                name_width = fm.horizontalAdvance(field.name)
                
                if field_width < name_width + 4 or field_width < 30:
                    center_x = (x1 + x2) / 2
                    bit_range_text = f"[{start}:{start + bit_width_val - 1}]"
                    labels_needed.append({
                        'field': field,
                        'center_x': center_x,
                        'x1': x1,
                        'x2': x2,
                        'bit_range': bit_range_text,
                        'color': self._get_field_color(idx),
                        'index': idx
                    })
            except (ValueError, AttributeError):
                continue
        
        if not labels_needed:
            return
        
        # 绘制连接线和标签
        painter.setFont(QFont("Arial", 8))
        used_y_positions = []  # 避免标签重叠
        
        for label_info in labels_needed:
            field = label_info['field']
            center_x = label_info['center_x']
            bit_range = label_info['bit_range']
            color = label_info['color']
            
            is_selected = (field.name == self.selected_field_name)
            is_hovered = (field.name == self.hovered_field_name)
            
            # 确定标签Y位置（避免重叠）
            label_y = label_y_base
            label_text = f"{field.name} {bit_range}"
            fm = painter.fontMetrics()
            label_width = fm.horizontalAdvance(label_text)
            
            # 检查是否与已有标签重叠
            for existing_x, existing_w, existing_y in used_y_positions:
                if (abs(center_x - existing_x) < (label_width + existing_w) / 2 + 10 and
                    abs(label_y - existing_y) < 15):
                    label_y = existing_y + 16  # 错开
            
            # 绘制连接线（从位域底部到标签）
            line_color = QColor(color)
            if is_selected:
                line_color = QColor(255, 80, 80)
            elif is_hovered:
                line_color = QColor(50, 120, 220)
            
            painter.setPen(QPen(line_color, 1, Qt.PenStyle.DashLine))
            connect_x = int(center_x)
            connect_from_y = self._bit_area_y + self._bit_area_height
            connect_to_y = int(label_y - 2)
            painter.drawLine(connect_x, connect_from_y, connect_x, connect_to_y)
            
            # 绘制标签背景
            bg_rect = QRect(int(center_x - label_width / 2 - 4), int(label_y - 10),
                           int(label_width + 8), 14)
            
            if is_selected:
                painter.setBrush(QColor(255, 230, 230))
                painter.setPen(QPen(QColor(255, 80, 80), 1))
            elif is_hovered:
                painter.setBrush(QColor(230, 240, 255))
                painter.setPen(QPen(QColor(50, 120, 220), 1))
            else:
                painter.setBrush(QColor(255, 255, 255, 220))
                painter.setPen(QPen(color.darker(130), 1))
            
            painter.drawRoundedRect(bg_rect, 3, 3)
            
            # 绘制标签文字
            if is_selected:
                painter.setPen(QColor(200, 50, 50))
            elif is_hovered:
                painter.setPen(QColor(30, 80, 180))
            else:
                painter.setPen(QColor(60, 60, 70))
            
            painter.setFont(QFont("Arial", 8))
            painter.drawText(int(center_x - label_width / 2), int(label_y), label_text)
            
            # 记录已用位置
            used_y_positions.append((center_x, label_width, label_y))
    
    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if not self.register and self.source_peripheral_name:
            self.jump_to_source_peripheral.emit(self.source_peripheral_name)
            return
        
        if not self.register or not self.fields:
            return
        
        pos = event.pos()
        for field in self.fields:
            if field.name in self.field_rects:
                x, y, w, h = self.field_rects[field.name]
                if x <= pos.x() <= x + w and y <= pos.y() <= y + h:
                    self.field_clicked.emit(field)
                    return
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件 - 显示悬停tooltip"""
        if not self.register or not self.fields:
            return
        
        pos = event.pos()
        old_hover = self.hovered_field_name
        
        self.hovered_field_name = None
        for field in self.fields:
            if field.name in self.field_rects:
                x, y, w, h = self.field_rects[field.name]
                if x <= pos.x() <= x + w and y <= pos.y() <= y + h:
                    self.hovered_field_name = field.name
                    # 显示详细tooltip
                    tooltip = f"<b>{field.name}</b><br>"
                    tooltip += f"位范围: [{field.bit_offset}:{field.bit_offset + field.bit_width - 1}]<br>"
                    tooltip += f"位宽: {field.bit_width}<br>"
                    if hasattr(field, 'description') and field.description:
                        tooltip += f"描述: {field.description}<br>"
                    if hasattr(field, 'access') and field.access:
                        tooltip += f"访问: {field.access}"
                    QToolTip.showText(event.globalPosition().toPoint(), tooltip, self)
                    break
        
        if old_hover != self.hovered_field_name:
            self.update()
        
        if not self.hovered_field_name:
            QToolTip.hideText()
        
        super().mouseMoveEvent(event)
    
    def leaveEvent(self, event):
        """鼠标离开事件"""
        if self.hovered_field_name:
            self.hovered_field_name = None
            self.update()
        QToolTip.hideText()
        super().leaveEvent(event)