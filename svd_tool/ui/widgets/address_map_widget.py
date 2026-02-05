"""
外设地址映射图控件
从main_window.py中提取的独立组件
"""
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QBrush, QFont, QPainter, QPen, QPaintEvent
import logging


class AddressMapWidget(QWidget):
    """外设地址映射图控件"""
    # 定义信号
    register_clicked = pyqtSignal(object)  # 发射寄存器对象
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(220)  # 增加高度确保地址范围完全可见
        self.setMaximumHeight(260)
        self.peripheral = None
        self.registers = []
        self.register_rects = {}  # 寄存器名 -> QRect
        self.selected_register_name = None  # 当前选中的寄存器名称
        self.hovered_register_name = None  # 鼠标悬停的寄存器名称
        self.setMouseTracking(True)  # 启用鼠标跟踪
        self.use_uniform_width = True  # 新增：是否使用均匀宽度（按寄存器个数划分）
        
    def set_peripheral(self, peripheral):
        """设置外设数据"""
        self.peripheral = peripheral
        if peripheral:
            self.registers = list(peripheral.registers.values())
        else:
            self.registers = []
        self.register_rects.clear()
        self.selected_register_name = None  # 重置选中状态
        self.update()
        
    def set_selected_register(self, register_name):
        """设置选中的寄存器"""
        self.selected_register_name = register_name
        self.update()
    
    def set_uniform_width_mode(self, enabled: bool):
        """设置是否使用均匀宽度模式（按寄存器个数划分）"""
        self.use_uniform_width = enabled
        self.update()
        
    def paintEvent(self, event: QPaintEvent):
        """绘制地址映射图"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 背景
        painter.fillRect(event.rect(), QColor(255, 255, 255))
        
        if not self.peripheral:
            painter.drawText(event.rect(), Qt.AlignmentFlag.AlignCenter, "无外设数据")
            return
            
        # 绘制标题
        painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        painter.drawText(10, 20, f"外设地址映射: {self.peripheral.name}")
        
        # 计算绘图区域
        width = self.width() - 20
        height = 70  # 绘图区域高度
        y_offset = 40
        
        # 如果有基地址和地址块大小
        try:
            base_addr = int(self.peripheral.base_address, 16) if self.peripheral.base_address.startswith('0x') else int(self.peripheral.base_address)
            block_size = int(self.peripheral.address_block['size'], 16) if self.peripheral.address_block['size'].startswith('0x') else int(self.peripheral.address_block['size'])
            
            # 绘制地址轴
            painter.setPen(QPen(QColor(0, 0, 0), 1))
            axis_y = y_offset + height - 10  # 轴位置
            painter.drawLine(10, axis_y, 10 + width, axis_y)
            
            # 绘制地址范围（在轴下方，与轴保持足够距离）
            addr_text = f"0x{base_addr:08X} - 0x{base_addr + block_size - 1:08X}"
            painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            painter.drawText(10, axis_y + 35, addr_text)
            
            # 判断寄存器数量，决定显示方式
            reg_count = len(self.registers)
            simplify_display = reg_count > 20  # 超过20个寄存器时简化显示
            
            # 绘制寄存器条
            for i, reg in enumerate(self.registers):
                try:
                    offset = int(reg.offset, 16) if reg.offset.startswith('0x') else int(reg.offset)
                    addr = base_addr + offset
                    
                    # 根据显示模式计算位置和宽度
                    if self.use_uniform_width:
                        # 模式1：按照寄存器个数均匀划分宽度
                        reg_count = len(self.registers)
                        if reg_count > 0:
                            # 每个寄存器占据相同的宽度
                            reg_width_px = width / reg_count
                            # 位置按照索引顺序排列
                            pos = i * reg_width_px
                        else:
                            reg_width_px = 0
                            pos = 0
                    else:
                        # 模式2：按照实际地址大小计算（原始逻辑）
                        # 计算在宽度中的位置
                        pos = (offset / block_size) * width if block_size > 0 else 0
                        
                        # 寄存器大小可能是位宽（如0x20表示32位），需要转换为字节
                        # SVD中的size通常表示位宽，地址映射需要字节宽度
                        size_bits = int(reg.size, 16) if reg.size.startswith('0x') else int(reg.size)
                        size_bytes = size_bits // 8  # 转换为字节
                        if size_bytes == 0:
                            size_bytes = 1  # 至少1字节
                        
                        reg_width_px = (size_bytes / block_size) * width
                    
                    # 确保矩形宽度足够大，以便边框能够正确绘制
                    # 最小宽度为8像素，确保边框可见
                    min_width = 8
                    reg_width_px = max(min_width, reg_width_px)
                    
                    # 绘制寄存器矩形
                    rect_x = 10 + pos
                    rect_y = axis_y - 35  # 在轴上方，与地址范围文本保持距离
                    rect_width = max(min_width, reg_width_px)
                    rect_height = 22
                    
                    # 调试信息：打印矩形尺寸（已禁用）
                    # print(f"[DEBUG] Register '{reg.name}': offset={offset}, size={reg.size} bits, size_bytes={size_bytes}, reg_width_px={reg_width_px:.2f}, rect_width={rect_width:.2f}")
                    
                    # 检查是否为选中的寄存器
                    is_selected = (reg.name == self.selected_register_name)
                    # 检查是否为悬停的寄存器
                    is_hovered = (reg.name == self.hovered_register_name)
                    
                    if is_selected:
                        # 高亮选中寄存器：使用更明显的颜色和更粗的边框
                        painter.setBrush(QBrush(QColor(255, 180, 60, 240)))  # 更亮的橙色，减少透明度
                        painter.setPen(QPen(QColor(255, 0, 0), 4))  # 红色边框，4像素宽，更明显
                    elif is_hovered:
                        # 悬停效果：使用更明显的颜色
                        painter.setBrush(QBrush(QColor(120, 180, 255, 220)))  # 更亮的蓝色，减少透明度
                        painter.setPen(QPen(QColor(0, 80, 255), 3))  # 蓝色边框，3像素宽
                    else:
                        # 普通寄存器：增加对比度，减少透明度，加粗边框
                        painter.setBrush(QBrush(QColor(80, 130, 255, 200)))  # 更深的蓝色，减少透明度
                        painter.setPen(QPen(QColor(0, 0, 150), 2))  # 更深的蓝色边框，2像素宽
                    
                    # 绘制矩形
                    painter.drawRect(int(rect_x), rect_y, int(rect_width), rect_height)
                    
                    # 存储矩形区域用于点击检测
                    self.register_rects[reg.name] = (int(rect_x), rect_y, int(rect_width), rect_height)
                    
                    # 寄存器名称和大小（字体更大）
                    painter.setFont(QFont("Arial", 9))
                    
                    # 如果寄存器被悬停或选中，强制显示完整名称
                    force_show_name = is_selected or is_hovered
                    
                    if simplify_display:
                        # 简化显示：只显示每第5个寄存器的名称，或者矩形宽度足够时，或者强制显示
                        if force_show_name or rect_width > 40 or i % 5 == 0:
                            # 简单显示：根据宽度显示完整名称或缩写
                            if rect_width > 40 or force_show_name:
                                # 宽度足够：显示完整名称（左对齐）
                                painter.drawText(int(rect_x) + 2, rect_y + 12, reg.name)
                            elif rect_width > 25:
                                # 中等宽度：显示缩写
                                abbrev = reg.name[:3] + "..." if len(reg.name) > 3 else reg.name
                                painter.drawText(int(rect_x) + 2, rect_y + 12, abbrev)
                            else:
                                # 太窄：显示超短缩写
                                abbrev = reg.name[:2] + "." if len(reg.name) > 2 else reg.name
                                painter.drawText(int(rect_x) + 2, rect_y + 12, abbrev)
                        # 否则不显示名称
                    else:
                        # 正常显示
                        if rect_width > 35 or force_show_name:
                            # 显示名称和大小
                            size_text = f"{reg.size}"
                            painter.drawText(int(rect_x) + 2, rect_y + 12, reg.name)
                            painter.drawText(int(rect_x) + 2, rect_y + 24, size_text)
                        else:
                            # 空间不够只显示名称或缩写
                            if rect_width > 20:
                                # 显示缩写
                                abbrev = reg.name[:3] + "..." if len(reg.name) > 3 else reg.name
                                painter.drawText(int(rect_x) + 2, rect_y + 12, abbrev)
                            else:
                                # 太窄：显示超短缩写
                                abbrev = reg.name[:2] + "." if len(reg.name) > 2 else reg.name
                                painter.drawText(int(rect_x) + 2, rect_y + 12, abbrev)
                    
                except (ValueError, AttributeError):
                    continue
                    
        except (ValueError, AttributeError):
            painter.drawText(10, y_offset + 30, "无法解析地址数据")
    
    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if not self.peripheral or not self.registers:
            # print(f"[DEBUG] No peripheral or registers to click")
            return
            
        pos = event.pos()
        # print(f"[DEBUG] AddressMapWidget mouse press at ({pos.x()}, {pos.y()})")
        # print(f"[DEBUG] Total registers: {len(self.registers)}, Rect entries: {len(self.register_rects)}")
        
        # 检查点击了哪个寄存器矩形
        for reg in self.registers:
            if reg.name in self.register_rects:
                x, y, w, h = self.register_rects[reg.name]
                # 打印矩形信息用于调试（已禁用）
                # print(f"[DEBUG] Checking register '{reg.name}' at rect ({x}, {y}, {w}, {h})")
                if x <= pos.x() <= x + w and y <= pos.y() <= y + h:
                    # print(f"[DEBUG] Register '{reg.name}' clicked - hit!")
                    # 发射信号
                    self.register_clicked.emit(reg)
                    return
            else:
                # print(f"[DEBUG] Register '{reg.name}' not in register_rects")
                pass
        
        # print("[DEBUG] No register clicked")
        # 打印所有矩形位置供参考（已禁用）
        # print(f"[DEBUG] All register rects: {self.register_rects}")
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件 - 显示悬停tooltip"""
        if not self.peripheral or not self.registers:
            return
            
        pos = event.pos()
        old_hover = self.hovered_register_name
        
        # 检查鼠标在哪个寄存器矩形上
        self.hovered_register_name = None
        for reg in self.registers:
            if reg.name in self.register_rects:
                x, y, w, h = self.register_rects[reg.name]
                if x <= pos.x() <= x + w and y <= pos.y() <= y + h:
                    self.hovered_register_name = reg.name
                    break
        
        # 如果悬停状态改变，更新显示
        if old_hover != self.hovered_register_name:
            self.update()
        
        super().mouseMoveEvent(event)
    
    def leaveEvent(self, event):
        """鼠标离开事件 - 清除悬停状态"""
        if self.hovered_register_name:
            self.hovered_register_name = None
            self.update()
        super().leaveEvent(event)