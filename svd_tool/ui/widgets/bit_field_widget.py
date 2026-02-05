"""
寄存器位域图控件
从main_window.py中提取的独立组件
"""
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QFont, QPainter, QPen, QPaintEvent
import logging


class BitFieldWidget(QWidget):
    """寄存器位域图控件"""
    # 定义信号
    field_clicked = pyqtSignal(object)  # 发射字段对象
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)  # 增加高度以减少拥挤
        self.setMaximumHeight(250)
        self.register = None
        self.fields = []
        self.field_rects = {}  # 字段名 -> QRect
        self.selected_field_name = None  # 当前选中的位域名称
        self.hovered_field_name = None  # 鼠标悬停的位域名称
        self.setMouseTracking(True)  # 启用鼠标跟踪
        
    def set_register(self, register):
        """设置寄存器数据"""
        self.register = register
        if register:
            self.fields = list(register.fields.values())
        else:
            self.fields = []
        self.field_rects.clear()
        self.selected_field_name = None  # 重置选中状态
        self.update()
        
    def set_selected_field(self, field_name):
        """设置选中的位域"""
        self.selected_field_name = field_name
        self.update()
        
    def paintEvent(self, event: QPaintEvent):
        """绘制位域图"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 背景
        painter.fillRect(event.rect(), QColor(255, 255, 255))
        
        if not self.register:
            painter.drawText(event.rect(), Qt.AlignmentFlag.AlignCenter, "无寄存器数据")
            return
            
        # 绘制标题（更紧凑）
        painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        painter.drawText(10, 18, f"寄存器位域: {self.register.name} (32位)")
        
        # 计算绘图区域
        width = self.width() - 20
        bit_width = 32
        y_offset = 35  # 上移
        
        # 绘制位标尺
        painter.setPen(QPen(QColor(0, 0, 0), 1))
        ruler_y = y_offset + 60
        painter.drawLine(10, ruler_y, 10 + width, ruler_y)
        
        # 绘制位编号（每8位显示一次，减少拥挤）
        # 先收集所有需要标注的位置
        bit_labels = {}
        # 标注0, 8, 16, 24, 32（而不是31），这样每个位占据一个完整的单位区间
        for i in range(0, 33, 8):  # 0到32，步长为8
            # 计算位置：i/32 * width
            x = 10 + (i / 32) * width
            painter.drawLine(int(x), ruler_y, int(x), ruler_y + 10)
            bit_labels[i] = x
        
        # 绘制位域
        field_annotations = {}  # 记录每个位置是否有位域标注
        self.field_rects.clear()  # 清除旧的矩形
        
        for field in self.fields:
            try:
                start = field.bit_offset
                bit_width_val = field.bit_width
                
                # 使用0-32坐标系统：位域占据[start, start+bit_width_val]区间
                x1 = 10 + (start / 32) * width
                x2 = 10 + ((start + bit_width_val) / 32) * width
                field_width = x2 - x1
                
                # 颜色根据位域位置变化
                hue = (start * 10) % 360
                color = QColor.fromHsv(int(hue), 180, 230)
                
                # 在位标尺上绘制位域范围标记（绿色竖线）
                painter.setPen(QPen(QColor(0, 150, 0), 2))
                # 起点竖线
                painter.drawLine(int(x1), ruler_y - 8, int(x1), ruler_y + 8)
                # 终点竖线
                painter.drawLine(int(x2), ruler_y - 8, int(x2), ruler_y + 8)
                
                # 记录位域标注位置（用于避免与坐标轴标注重叠）
                field_annotations[start] = x1
                # 对于结束位置，使用start+bit_width_val-1（实际的结束位）
                end_bit = start + bit_width_val - 1
                field_annotations[end_bit] = x2
                
                # 绘制位域矩形（在位标尺上方）
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(QColor(0, 0, 0), 1))
                rect_y = ruler_y - 45
                rect_height = 30
                painter.drawRect(int(x1), rect_y, int(field_width), rect_height)
                
                # 存储矩形区域用于点击检测
                self.field_rects[field.name] = (int(x1), rect_y, int(field_width), rect_height)
                
                # 在位域矩形内部只显示名称，不显示范围（范围已标注在位标尺上）
                painter.setPen(QPen(QColor(0, 0, 0), 1))
                if field_width > 25:  # 宽度足够显示名称
                    painter.setFont(QFont("Arial", 9))
                    painter.drawText(int(x1) + 2, rect_y + 18, field.name)
                else:  # 太窄则不显示任何内容
                    pass
                
            except (ValueError, AttributeError):
                continue
        
        # 简单直接的标注方案：坐标轴和位域区间同时显示，不需要避让
        # 1. 先绘制坐标轴主刻度（0,8,16,24,32）
        painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        painter.setPen(QPen(QColor(0, 0, 0), 1))
        for bit_pos, x in bit_labels.items():
            painter.drawText(int(x) - 8, ruler_y + 25, str(bit_pos))
        
        # 2. 绘制位域矩形和标注
        for field in self.fields:
            try:
                start = field.bit_offset
                bit_width_val = field.bit_width
                
                # 使用0-32坐标系统：位域占据[start, start+bit_width_val]区间
                x1 = 10 + (start / 32) * width
                x2 = 10 + ((start + bit_width_val) / 32) * width
                field_width = x2 - x1
                
                # 计算矩形位置
                rect_y = ruler_y - 45
                rect_height = 30
                
                # 绘制位域矩形
                hue = (start * 10) % 360
                color = QColor.fromHsv(int(hue), 200, 240)  # 提高饱和度和亮度，增加对比度
                
                # 检查是否为选中的位域
                is_selected = (field.name == self.selected_field_name)
                # 检查是否为悬停的位域
                is_hovered = (field.name == self.hovered_field_name)
                
                if is_selected:
                    # 高亮选中位域：使用更深的颜色和更粗的边框
                    color = QColor.fromHsv(int(hue), 240, 220)  # 更高饱和度，稍暗
                    painter.setBrush(QBrush(color))
                    painter.setPen(QPen(QColor(255, 0, 0), 4))  # 红色边框，4像素宽（增加）
                elif is_hovered:
                    # 悬停效果：使用更亮的颜色
                    color = QColor.fromHsv(int(hue), 220, 250)  # 更亮
                    painter.setBrush(QBrush(color))
                    painter.setPen(QPen(QColor(0, 100, 255), 3))  # 蓝色边框，3像素宽（增加）
                else:
                    painter.setBrush(QBrush(color))
                    painter.setPen(QPen(QColor(0, 0, 0), 2))  # 普通黑色边框，2像素宽（增加）
                
                painter.drawRect(int(x1), rect_y, int(field_width), rect_height)
                
                # 存储矩形区域用于点击检测
                self.field_rects[field.name] = (int(x1), rect_y, int(field_width), rect_height)
                
                # 在位域矩形内部显示名称（如果空间足够或悬停/选中）
                force_show_name = is_selected or is_hovered
                if field_width > 25 or force_show_name:
                    painter.setPen(QPen(QColor(0, 0, 0), 1))
                    painter.setFont(QFont("Arial", 9))
                    
                    # 简单显示：根据宽度显示完整名称或缩写
                    if field_width > 40 or force_show_name:
                        # 空间足够或强制显示：显示完整名称（左对齐）
                        painter.drawText(int(x1) + 2, rect_y + 18, field.name)
                    elif field_width > 20:
                        # 中等空间：显示缩写（前3个字符）
                        abbrev = field.name[:3] + "..." if len(field.name) > 3 else field.name
                        painter.drawText(int(x1) + 2, rect_y + 18, abbrev)
                    else:
                        # 空间太小：显示超短缩写
                        abbrev = field.name[:2] + "." if len(field.name) > 2 else field.name
                        painter.drawText(int(x1) + 2, rect_y + 18, abbrev)
                
                # 在位域矩形上方标注实际占据的区间
                # 对于1位宽度：显示"3-4"而不是"3"
                # 对于多位宽度：显示"3-6"（如果占据位3,4,5）
                annotation_y = ruler_y - 55  # 矩形上方
                painter.setFont(QFont("Arial", 8))
                painter.setPen(QPen(QColor(0, 100, 0), 1))
                
                # 计算实际占据的区间
                actual_start = start
                actual_end = start + bit_width_val  # 注意：不是start+bit_width_val-1
                
                if bit_width_val == 1:
                    # 1位宽度：显示"3-4"
                    annotation_text = f"{actual_start}-{actual_end}"
                else:
                    # 多位宽度：显示"3-6"（对于3位宽度）
                    annotation_text = f"{actual_start}-{actual_end}"
                
                # 居中显示标注
                center_x = (x1 + x2) / 2
                text_width_px = len(annotation_text) * 5  # 估算文本宽度
                painter.drawText(int(center_x - text_width_px/2), annotation_y, annotation_text)
                
            except (ValueError, AttributeError):
                continue
    
    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if not self.register or not self.fields:
            return
            
        pos = event.pos()
        # print(f"[DEBUG] BitFieldWidget mouse press at ({pos.x()}, {pos.y()})")
        # 检查点击了哪个字段矩形
        for field in self.fields:
            if field.name in self.field_rects:
                x, y, w, h = self.field_rects[field.name]
                if x <= pos.x() <= x + w and y <= pos.y() <= y + h:
                    # print(f"[DEBUG] Field '{field.name}' clicked")
                    # 发射信号
                    self.field_clicked.emit(field)
                    return
        # print("[DEBUG] No field clicked")
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件 - 显示悬停tooltip"""
        if not self.register or not self.fields:
            return
            
        pos = event.pos()
        old_hover = self.hovered_field_name
        
        # 检查鼠标在哪个字段矩形上
        self.hovered_field_name = None
        for field in self.fields:
            if field.name in self.field_rects:
                x, y, w, h = self.field_rects[field.name]
                if x <= pos.x() <= x + w and y <= pos.y() <= y + h:
                    self.hovered_field_name = field.name
                    break
        
        # 如果悬停状态改变，更新显示
        if old_hover != self.hovered_field_name:
            self.update()
        
        super().mouseMoveEvent(event)
    
    def leaveEvent(self, event):
        """鼠标离开事件 - 清除悬停状态"""
        if self.hovered_field_name:
            self.hovered_field_name = None
            self.update()
        super().leaveEvent(event)