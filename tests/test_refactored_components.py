#!/usr/bin/env python3
"""
测试重构后的组件
验证组件化架构是否正常工作
"""
import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def test_state_manager():
    """测试状态管理器"""
    print("测试状态管理器...")
    try:
        from svd_tool.ui.components.state_manager import StateManager
        from svd_tool.core.data_model import Peripheral, Register, Field
        
        state_manager = StateManager()
        
        # 测试基本功能
        assert state_manager.device_info is not None
        assert state_manager.command_history is not None
        
        # 测试外设操作
        peripheral = Peripheral(
            name="TEST_PERIPH",
            base_address="0x40000000",
            description="测试外设"
        )
        
        state_manager.add_peripheral(peripheral)
        assert "TEST_PERIPH" in state_manager.device_info.peripherals
        
        # 测试寄存器操作
        register = Register(
            name="TEST_REG",
            offset="0x0",
            description="测试寄存器"
        )
        
        state_manager.add_register("TEST_PERIPH", register)
        assert "TEST_REG" in state_manager.device_info.peripherals["TEST_PERIPH"].registers
        
        # 测试位域操作
        field = Field(
            name="TEST_FIELD",
            description="测试位域",
            bit_offset=0,
            bit_width=1
        )
        
        state_manager.add_field("TEST_PERIPH", "TEST_REG", field)
        assert "TEST_FIELD" in state_manager.device_info.peripherals["TEST_PERIPH"].registers["TEST_REG"].fields
        
        # 测试数据统计
        stats = state_manager.get_data_stats()
        assert stats['peripherals'] == 1
        assert stats['registers'] == 1
        assert stats['fields'] == 1
        
        print("[OK] 状态管理器测试通过")
        return True
        
    except Exception as e:
        print(f"[FAIL] 状态管理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_layout_manager():
    """测试布局管理器"""
    print("测试布局管理器...")
    try:
        from PyQt6.QtWidgets import QApplication
        from svd_tool.ui.components.layout_manager import LayoutManager
        
        # 创建QApplication实例（需要GUI环境）
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        
        # 创建主窗口
        from PyQt6.QtWidgets import QMainWindow
        main_window = QMainWindow()
        
        # 测试布局管理器
        layout_manager = LayoutManager(main_window)
        widgets = layout_manager.create_layout()
        
        assert 'tab_widget' in widgets
        assert 'status_bar' in widgets
        
        print("✓ 布局管理器测试通过")
        return True
        
    except Exception as e:
        print(f"✗ 布局管理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_peripheral_manager():
    """测试外设管理器"""
    print("测试外设管理器...")
    try:
        from PyQt6.QtWidgets import QApplication
        from svd_tool.ui.components.state_manager import StateManager
        from svd_tool.ui.components.layout_manager import LayoutManager
        from svd_tool.ui.components.peripheral_manager import PeripheralManager
        
        # 创建QApplication实例
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        
        # 创建主窗口
        from PyQt6.QtWidgets import QMainWindow
        main_window = QMainWindow()
        
        # 创建状态管理器和布局管理器
        state_manager = StateManager()
        layout_manager = LayoutManager(main_window)
        
        # 创建外设管理器
        peripheral_manager = PeripheralManager(state_manager, layout_manager)
        
        assert peripheral_manager.state_manager == state_manager
        assert peripheral_manager.layout_manager == layout_manager
        
        print("✓ 外设管理器测试通过")
        return True
        
    except Exception as e:
        print(f"✗ 外设管理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_component_imports():
    """测试组件导入"""
    print("测试组件导入...")
    try:
        # 测试所有组件的导入
        from svd_tool.ui.components import menu_bar
        from svd_tool.ui.components import toolbar
        from svd_tool.ui.components import state_manager
        from svd_tool.ui.components import layout_manager
        from svd_tool.ui.components import peripheral_manager
        
        print("[OK] 所有组件导入成功")
        return True
        
    except Exception as e:
        print(f"[FAIL] 组件导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_refactored_main_window():
    """测试重构后的主窗口"""
    print("测试重构后的主窗口...")
    try:
        # 测试导入
        from svd_tool.ui.main_window_refactored import MainWindowRefactored
        
        print("✓ 重构后的主窗口导入成功")
        
        # 检查类定义
        assert hasattr(MainWindowRefactored, 'state_manager')
        assert hasattr(MainWindowRefactored, 'layout_manager')
        assert hasattr(MainWindowRefactored, 'peripheral_manager')
        
        print("✓ 重构后的主窗口类定义正确")
        return True
        
    except Exception as e:
        print(f"✗ 重构后的主窗口测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("=" * 60)
    print("开始测试重构后的组件")
    print("=" * 60)
    
    results = []
    
    # 运行测试
    results.append(("组件导入", test_component_imports()))
    results.append(("状态管理器", test_state_manager()))
    results.append(("布局管理器", test_layout_manager()))
    results.append(("外设管理器", test_peripheral_manager()))
    results.append(("重构主窗口", test_refactored_main_window()))
    
    # 输出结果
    print("\n" + "=" * 60)
    print("测试结果汇总:")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"{test_name:20} {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("所有测试通过！组件化重构成功。")
        print("\n重构成果总结:")
        print("1. 创建了状态管理组件 (StateManager)")
        print("2. 创建了UI布局组件 (LayoutManager)")
        print("3. 创建了外设管理组件 (PeripheralManager)")
        print("4. 重构了主窗口 (MainWindowRefactored)")
        print("5. 添加了MIT开源许可证")
        print("6. 提高了代码可维护性和模块化程度")
    else:
        print("部分测试失败，需要进一步调试。")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)