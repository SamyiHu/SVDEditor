#!/usr/bin/env python3
"""
测试图形修复效果
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt

# 导入主窗口类
from svd_tool.ui.main_window_refactored import MainWindowRefactored as MainWindow

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("图形修复测试")
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
        
        # 创建测试位域 - 特别创建会与坐标轴重叠的位域
        field1 = Field(
            name="MODER0",
            bit_offset=0,  # 与坐标轴位0重叠
            bit_width=2,
            description="Port x mode bits"
        )
        
        field2 = Field(
            name="MODER8",
            bit_offset=8,  # 与坐标轴位8重叠
            bit_width=4,
            description="Port x mode bits"
        )
        
        field3 = Field(
            name="MODER16",
            bit_offset=16,  # 与坐标轴位16重叠
            bit_width=4,
            description="Port x mode bits"
        )
        
        field4 = Field(
            name="MODER24",
            bit_offset=24,  # 与坐标轴位24重叠
            bit_width=4,
            description="Port x mode bits"
        )
        
        field5 = Field(
            name="MODER30",
            bit_offset=30,  # 不与坐标轴重叠
            bit_width=2,
            description="Port x mode bits"
        )
        
        # 添加到数据结构
        register.fields = {
            field1.name: field1,
            field2.name: field2,
            field3.name: field3,
            field4.name: field4,
            field5.name: field5
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
            
            print("=== 图形修复测试 ===")
            print("问题1修复: 外设地址映射图高度增加 (220-260)")
            print("问题2修复: 位域标注与坐标轴标注智能避让")
            print("\n测试数据:")
            print(f"外设: {peripheral.name}, 基地址: {peripheral.base_address}")
            print(f"寄存器: {register.name}, 偏移: {register.offset}")
            print("位域 (特意创建与坐标轴重叠的):")
            for field in register.fields.values():
                print(f"  {field.name}: 位{field.bit_offset}-{field.bit_offset+field.bit_width-1}")

def main():
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    
    print("\n窗口已显示，请检查:")
    print("1. 外设地址映射图是否完整显示（地址范围文本不应被截断）")
    print("2. 寄存器位域图中，位0、8、16、24的标注是否与坐标轴标注重叠")
    print("   期望: 位域标注优先显示，坐标轴标注在重叠位置不显示")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()