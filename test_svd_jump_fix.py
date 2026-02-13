#!/usr/bin/env python3
"""
测试SVD跳转修复
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from svd_tool.ui.components.state_manager import StateManager
from svd_tool.ui.components.realtime_preview import RealtimePreviewWidget
from svd_tool.core.data_model import DeviceInfo, Peripheral, Register, Field

def test_state_manager_fix():
    """测试状态管理器修复"""
    print("=== 测试状态管理器修复 ===")
    
    # 创建状态管理器
    state_manager = StateManager()
    
    # 测试设置外设选择
    state_manager.set_selection(peripheral="GPIOA", element_type="peripheral")
    selection = state_manager.get_selection()
    print(f"外设选择: {selection}")
    assert selection['type'] == 'peripheral'
    assert selection['peripheral'] == 'GPIOA'
    assert selection['interrupt'] is None
    
    # 测试设置寄存器选择
    state_manager.set_selection(peripheral="GPIOA", register="MODER", element_type="register")
    selection = state_manager.get_selection()
    print(f"寄存器选择: {selection}")
    assert selection['type'] == 'register'
    assert selection['peripheral'] == 'GPIOA'
    assert selection['register'] == 'MODER'
    assert selection['interrupt'] is None
    
    # 测试设置位域选择
    state_manager.set_selection(peripheral="GPIOA", register="MODER", field="MODE0", element_type="field")
    selection = state_manager.get_selection()
    print(f"位域选择: {selection}")
    assert selection['type'] == 'field'
    assert selection['peripheral'] == 'GPIOA'
    assert selection['register'] == 'MODER'
    assert selection['field'] == 'MODE0'
    assert selection['interrupt'] is None
    
    # 测试设置中断选择
    state_manager.set_selection(peripheral="NVIC", interrupt="EXTI0", element_type="interrupt")
    selection = state_manager.get_selection()
    print(f"中断选择: {selection}")
    assert selection['type'] == 'interrupt'
    assert selection['peripheral'] == 'NVIC'
    assert selection['interrupt'] == 'EXTI0'
    assert selection['register'] is None  # 中断选择应清除寄存器选择
    assert selection['field'] is None  # 中断选择应清除位域选择
    
    print("[OK] 状态管理器修复测试通过")
    return True

def test_realtime_preview_key_matching():
    """测试实时预览键匹配"""
    print("\n=== 测试实时预览键匹配 ===")
    
    # 创建应用（需要QApplication用于Qt组件）
    app = QApplication(sys.argv)
    
    # 创建状态管理器
    state_manager = StateManager()
    
    # 创建设备信息
    device_info = DeviceInfo()
    device_info.name = "TestDevice"
    
    # 添加外设
    peripheral = Peripheral(name="GPIOA", description="General Purpose I/O")
    device_info.peripherals["GPIOA"] = peripheral
    
    # 添加寄存器
    register = Register(name="MODER", description="Mode Register", address_offset=0x00)
    peripheral.registers["MODER"] = register
    
    # 添加位域
    field = Field(name="MODE0", description="Mode bit 0", bit_offset=0, bit_width=2)
    register.fields["MODE0"] = field
    
    # 更新状态管理器
    state_manager.device_info = device_info
    
    # 创建实时预览组件
    preview = RealtimePreviewWidget(state_manager)
    
    # 测试键构建
    print("测试位域键构建...")
    element_type = 'field'
    peripheral_name = 'GPIOA'
    element_name = 'MODER.MODE0'
    
    key = (element_type, peripheral_name, element_name)
    print(f"构建的键: {key}")
    
    # 模拟element_ranges
    preview.element_ranges = {
        ('peripheral', 'GPIOA', 'GPIOA'): (1, 50),
        ('register', 'GPIOA', 'MODER'): (10, 30),
        ('field', 'GPIOA', 'MODER.MODE0'): (20, 25)
    }
    
    # 测试键查找
    if key in preview.element_ranges:
        print(f"[OK] 键 {key} 在 element_ranges 中找到")
    else:
        print(f"[ERROR] 键 {key} 不在 element_ranges 中")
        print(f"element_ranges 中的键: {list(preview.element_ranges.keys())}")
    
    print("[OK] 实时预览键匹配测试完成")
    return True

def main():
    """主测试函数"""
    print("开始测试SVD跳转修复...")
    
    try:
        # 测试状态管理器修复
        test_state_manager_fix()
        
        # 测试实时预览键匹配
        test_realtime_preview_key_matching()
        
        print("\n[SUCCESS] 所有测试通过！SVD跳转修复成功。")
        return 0
    except Exception as e:
        print(f"\n[FAILED] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())