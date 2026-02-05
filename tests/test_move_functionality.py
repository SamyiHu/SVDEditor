#!/usr/bin/env python3
"""
测试移动外设功能
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from svd_tool.core.data_model import Peripheral, Register, Field, DeviceInfo
from svd_tool.ui.components.state_manager import StateManager

def test_move_peripheral():
    """测试移动外设功能"""
    print("=== 测试移动外设功能 ===")
    
    # 创建状态管理器
    state_manager = StateManager()
    
    # 创建设备信息
    device_info = DeviceInfo(
        name="TestDevice",
        description="Test Device",
        peripherals={}
    )
    state_manager.device_info = device_info
    
    # 添加几个外设
    peripherals = []
    for i in range(3):
        periph = Peripheral(
            name=f"PERIPH_{i}",
            base_address=f"0x{1000 + i*1000:08X}",
            description=f"Peripheral {i}",
            registers={}
        )
        state_manager.add_peripheral(periph)
        peripherals.append(periph.name)
    
    print(f"初始外设顺序: {list(state_manager.device_info.peripherals.keys())}")
    
    # 测试上移中间的外设
    print("\n1. 测试上移 PERIPH_1")
    success = state_manager.move_peripheral_up("PERIPH_1")
    print(f"   上移结果: {success}")
    print(f"   当前顺序: {list(state_manager.device_info.peripherals.keys())}")
    
    # 测试上移已经在最上面的外设
    print("\n2. 测试上移 PERIPH_0 (已经在最上面)")
    success = state_manager.move_peripheral_up("PERIPH_0")
    print(f"   上移结果: {success}")
    print(f"   当前顺序: {list(state_manager.device_info.peripherals.keys())}")
    
    # 测试下移
    print("\n3. 测试下移 PERIPH_0")
    success = state_manager.move_peripheral_down("PERIPH_0")
    print(f"   下移结果: {success}")
    print(f"   当前顺序: {list(state_manager.device_info.peripherals.keys())}")
    
    # 测试下移已经在最下面的外设
    print("\n4. 测试下移 PERIPH_2 (已经在最下面)")
    success = state_manager.move_peripheral_down("PERIPH_2")
    print(f"   下移结果: {success} (预期: False，因为已经在最下面)")
    print(f"   最终顺序: {list(state_manager.device_info.peripherals.keys())}")
    
    # 验证顺序是否正确
    expected_order = ["PERIPH_1", "PERIPH_0", "PERIPH_2"]
    actual_order = list(state_manager.device_info.peripherals.keys())
    
    if actual_order == expected_order:
        print(f"\n[PASS] 测试通过! 外设顺序正确: {actual_order}")
        return True
    else:
        print(f"\n[FAIL] 测试失败! 期望顺序: {expected_order}, 实际顺序: {actual_order}")
        return False

def test_copy_paste_functionality():
    """测试复制粘贴功能"""
    print("\n=== 测试复制粘贴功能 ===")
    
    # 创建状态管理器
    state_manager = StateManager()
    
    # 创建设备信息
    device_info = DeviceInfo(
        name="TestDevice",
        description="Test Device",
        peripherals={}
    )
    state_manager.device_info = device_info
    
    # 添加一个外设
    periph = Peripheral(
        name="SOURCE_PERIPH",
        base_address="0x40000000",
        description="Source Peripheral",
        registers={}
    )
    state_manager.add_peripheral(periph)
    
    print(f"初始外设: {list(state_manager.device_info.peripherals.keys())}")
    
    # 测试导出功能
    from svd_tool.ui.components.peripheral_manager import PeripheralManager
    
    # 创建PeripheralManager（需要模拟layout_manager）
    class MockLayoutManager:
        def __init__(self):
            self.main_window = None
            self.widgets = {}
        
        def get_widget(self, name):
            return self.widgets.get(name)
    
    layout_manager = MockLayoutManager()
    peripheral_manager = PeripheralManager(state_manager, layout_manager)
    
    # 测试导出
    print("\n1. 测试导出外设")
    data = peripheral_manager.export_peripheral("SOURCE_PERIPH")
    if data:
        print(f"   导出成功，外设名称: {data.get('name')}")
        print(f"   基地址: {data.get('base_address')}")
        print(f"   描述: {data.get('description')}")
    else:
        print("   导出失败!")
        return False
    
    # 测试导入（复制）
    print("\n2. 测试导入外设（复制）")
    # 修改名称以避免冲突
    data['name'] = "COPIED_PERIPH"
    data['base_address'] = "0x40001000"
    
    try:
        peripheral_manager.import_peripheral(data)
        print(f"   导入成功!")
        print(f"   当前外设: {list(state_manager.device_info.peripherals.keys())}")
        
        # 验证是否添加成功
        if "COPIED_PERIPH" in state_manager.device_info.peripherals:
            print("   [OK] 复制的外设已成功添加")
            return True
        else:
            print("   [FAIL] 复制的外设未添加")
            return False
    except Exception as e:
        print(f"   导入失败: {e}")
        return False

if __name__ == "__main__":
    print("开始测试移动和复制粘贴功能...")
    
    move_success = test_move_peripheral()
    copy_success = test_copy_paste_functionality()
    
    if move_success and copy_success:
        print("\n[SUCCESS] 所有测试通过!")
        sys.exit(0)
    else:
        print("\n[FAILURE] 部分测试失败!")
        sys.exit(1)