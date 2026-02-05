#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试矩形右边没封口问题的修复
模拟WDTCFG寄存器：只有3位，但寄存器大小为32位（0x20）
"""

import sys
import os
sys.path.insert(0, '.')

from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PyQt6.QtGui import QPainter, QPen, QColor, QFont
from PyQt6.QtCore import Qt, QRect

from svd_tool.core.data_model import Peripheral, Register, Field

class TestWidget(QWidget):
    """测试矩形绘制的小部件"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("矩形绘制测试")
        self.setGeometry(100, 100, 800, 400)
        
        # 创建一个模拟的外设
        self.peripheral = Peripheral(
            name="TEST_PERIPH",
            description="测试外设",
            base_address="0x40000000",
            address_block={"offset": "0x0", "size": "0x1000"},
            registers=[]
        )
        
        # 创建模拟的寄存器
        self.registers = [
            Register(
                name="WDTCFG",
                description="看门狗配置寄存器",
                offset="0x0",
                size="0x20",  # 32位
                access="read-write",
                reset_value="0x00000000",
                fields=[
                    Field(
                        name="WEN",
                        description="看门狗使能",
                        bit_offset="0",
                        bit_width="1",
                        access="read-write"
                    ),
                    Field(
                        name="WPERIOD",
                        description="看门狗周期",
                        bit_offset="1",
                        bit_width="2",
                        access="read-write"
                    )
                ]
            ),
            Register(
                name="CTRL",
                description="控制寄存器",
                offset="0x4",
                size="0x20",  # 32位
                access="read-write",
                reset_value="0x00000000",
                fields=[]
            )
        ]
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 模拟AddressMapWidget中的绘制逻辑
        width = 700  # 绘图区域宽度
        height = 70  # 绘图区域高度
        y_offset = 40
        
        try:
            base_addr = int(self.peripheral.base_address, 16)
            block_size = int(self.peripheral.address_block['size'], 16)
            
            # 绘制地址轴
            painter.setPen(QPen(QColor(0, 0, 0), 1))
            axis_y = y_offset + height - 10
            painter.drawLine(10, axis_y, 10 + width, axis_y)
            
            # 绘制地址范围
            addr_text = f"0x{base_addr:08X} - 0x{base_addr + block_size - 1:08X}"
            painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            painter.drawText(10, axis_y + 35, addr_text)
            
            # 绘制寄存器条
            for i, reg in enumerate(self.registers):
                try:
                    offset = int(reg.offset, 16)
                    addr = base_addr + offset
                    
                    # 计算在宽度中的位置
                    pos = (offset / block_size) * width if block_size > 0 else 0
                    
                    # 寄存器大小可能是位宽（如0x20表示32位），需要转换为字节
                    size_bits = int(reg.size, 16)
                    size_bytes = size_bits // 8  # 转换为字节
                    if size_bytes == 0:
                        size_bytes = 1
                    
                    reg_width_px = (size_bytes / block_size) * width
                    
                    # 确保矩形宽度足够大
                    min_width = 8
                    reg_width_px = max(min_width, reg_width_px)
                    
                    # 矩形坐标
                    rect_x = 10 + pos
                    rect_y = y_offset
                    rect_width = reg_width_px
                    rect_height = height - 20
                    
                    # 打印调试信息
                    print(f"[TEST] Register '{reg.name}':")
                    print(f"  offset={offset}, size={reg.size} bits, size_bytes={size_bytes}")
                    print(f"  pos={pos:.2f}, reg_width_px={reg_width_px:.2f}")
                    print(f"  rect_x={rect_x:.2f}, rect_width={rect_width:.2f}")
                    print(f"  rect_right={rect_x + rect_width:.2f}")
                    
                    # 检查矩形是否闭合
                    if rect_width < 1:
                        print(f"  WARNING: Rectangle width too small: {rect_width}")
                    
                    # 绘制矩形
                    painter.setPen(QPen(QColor(100, 100, 255), 2))
                    painter.setBrush(QColor(200, 200, 255, 180))
                    painter.drawRect(int(rect_x), int(rect_y), int(rect_width), int(rect_height))
                    
                    # 绘制寄存器名称
                    painter.setPen(QPen(QColor(0, 0, 0), 1))
                    painter.setFont(QFont("Arial", 9))
                    painter.drawText(int(rect_x) + 2, int(rect_y) + 12, reg.name)
                    
                    # 绘制大小信息
                    size_text = f"{reg.size} bits ({size_bytes} bytes)"
                    painter.drawText(int(rect_x) + 2, int(rect_y) + 24, size_text)
                    
                except (ValueError, AttributeError) as e:
                    print(f"[TEST] Error drawing register {reg.name}: {e}")
                    continue
                    
        except (ValueError, AttributeError) as e:
            print(f"[TEST] Error in paintEvent: {e}")
            painter.drawText(10, y_offset + 30, "无法解析地址数据")

def main():
    app = QApplication(sys.argv)
    widget = TestWidget()
    widget.show()
    
    print("=" * 60)
    print("测试矩形右边没封口问题的修复")
    print("模拟WDTCFG寄存器：只有3位，但寄存器大小为32位（0x20）")
    print("=" * 60)
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()