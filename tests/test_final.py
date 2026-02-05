#!/usr/bin/env python3
"""
最终图形修复测试
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
        self.setWindowTitle("最终图形修复测试")
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
        
        # 创建测试位域 - 测试各种宽度
        # 1位宽度：位3（应该显示"3-4"）
        field1 = Field(
            name="BIT3",
            bit_offset=3,
            bit_width=1,
            description="Single bit field"
        )
        
        # 2位宽度：位8-9（应该显示"8-10"）
        field2 = Field(
            name="BITS8_9",
            bit_offset=8,
            bit_width=2,
            description="Two-bit field"
        )
        
        # 4位宽度：位16-19（应该显示"16-20"）
        field3 = Field(
            name="BITS16_19",
            bit_offset=16,
            bit_width=4,
            description="Four-bit field"
        )
        
        # 8位宽度：位24-31（应该显示"24-32"）
        field4 = Field(
            name="BITS24_31",
            bit_offset=24,
            bit_width=8,
            description="Eight-bit field"
        )
        
        # 添加到数据结构
        register.fields = {
            field1.name: field1,
            field2.name: field2,
            field3.name: field3,
            field4.name: field4
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
            
            print("=== 最终图形修复测试 ===")
            print("\n修复总结：")
            print("1. 外设地址映射图：高度增加至220-260像素，确保地址范围完整显示")
            print("2. 寄存器位域图：")
            print("   - 坐标轴标注：0,8,16,24,32（0-32系统）")
            print("   - 位域区间标注：显示实际占据的区间（如'3-4'而不是'3'）")
            print("   - 无需避让：坐标轴和位域标注同时显示")
            print("\n测试位域数据：")
            for field in register.fields.values():
                actual_end = field.bit_offset + field.bit_width
                print(f"  {field.name}: 位{field.bit_offset}，宽度{field.bit_width}")
                print(f"    实际占据区间: {field.bit_offset}-{actual_end}")
                print(f"    期望标注: '{field.bit_offset}-{actual_end}'")

def main():
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    
    print("\n测试窗口已显示，请检查：")
    print("1. 外设地址映射图是否完整显示（无截断）")
    print("2. 寄存器位域图坐标轴是否标注0,8,16,24,32")
    print("3. 位域标注是否正确显示实际区间：")
    print("   - BIT3(位3) 应显示 '3-4'")
    print("   - BITS8_9(位8-9) 应显示 '8-10'")
    print("   - BITS16_19(位16-19) 应显示 '16-20'")
    print("   - BITS24_31(位24-31) 应显示 '24-32'")
    print("\n按Ctrl+C退出测试")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()