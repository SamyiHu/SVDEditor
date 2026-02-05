#!/usr/bin/env python3
"""
测试图形问题诊断脚本
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QFont, QPainter, QPen, QPaintEvent

# 导入主窗口类
from svd_tool.ui.main_window_refactored import MainWindowRefactored as MainWindow

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("图形问题测试")
        self.setGeometry(100, 100, 800, 600)
        
        # 创建测试用的外设和寄存器数据
        from svd_tool.core.data_model import DeviceInfo, Peripheral, Register, Field
        
        # 创建设备信息
        self.device_info = DeviceInfo()
        self.device_info.name = "TestDevice"
        self.device_info.version = "1.0"
        
        # 创建测试外设
        peripheral = Peripheral(
            name="GPIOA",
            base_address="0x40020000",
            description="General Purpose I/O A"
        )
        peripheral.address_block = {"offset": "0x0", "size": "0x400"}
        
        # 创建测试寄存器
        register = Register(
            name="MODER",
            offset="0x0",
            description="Mode register"
        )
        register.size = "0x20"
        register.reset_value = "0x00000000"
        
        # 创建测试位域
        field1 = Field(
            name="MODER0",
            bit_offset=0,
            bit_width=2,
            description="Port x mode bits"
        )
        field1.reset_value = "0x0"
        
        field2 = Field(
            name="MODER1",
            bit_offset=2,
            bit_width=2,
            description="Port x mode bits"
        )
        field2.reset_value = "0x0"
        
        field3 = Field(
            name="MODER15",
            bit_offset=30,
            bit_width=2,
            description="Port x mode bits"
        )
        field3.reset_value = "0x0"
        
        # 添加到数据结构
        register.fields = {
            field1.name: field1,
            field2.name: field2,
            field3.name: field3
        }
        
        peripheral.registers = {
            register.name: register
        }
        
        self.device_info.peripherals = {
            peripheral.name: peripheral
        }
        
        # 创建主窗口实例
        self.main_window = MainWindow()
        self.main_window.device_info = self.device_info
        
        # 获取可视化控件
        if hasattr(self.main_window, 'visualization_widget'):
            self.viz_widget = self.main_window.visualization_widget
            
            # 设置中心部件
            central_widget = QWidget()
            layout = QVBoxLayout(central_widget)
            layout.addWidget(self.viz_widget)
            self.setCentralWidget(central_widget)
            
            # 显示测试数据
            self.viz_widget.show_peripheral_and_register(peripheral, register)
            
            # 打印尺寸信息
            print(f"AddressMapWidget 尺寸: {self.viz_widget.address_map.width()}x{self.viz_widget.address_map.height()}")
            print(f"BitFieldWidget 尺寸: {self.viz_widget.bit_field.width()}x{self.viz_widget.bit_field.height()}")
            
            # 打印位域信息
            print(f"\n位域数据:")
            for field in register.fields.values():
                print(f"  {field.name}: 起始位={field.bit_offset}, 宽度={field.bit_width}")

def main():
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    
    # 打印诊断信息
    print("=== 图形问题诊断 ===")
    print("问题1: 外设地址映射图大小露出来了")
    print("问题2: 寄存器位域图坐标轴重叠")
    print("\n正在显示测试窗口...")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()