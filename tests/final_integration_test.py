#!/usr/bin/env python3
"""
最终集成测试：验证重构版主窗口的完整启动流程
"""
import sys
import os
import traceback

# 设置正确的项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_component_imports():
    """测试所有组件导入"""
    print("=== 测试组件导入 ===")
    modules = [
        ("StateManager", "svd_tool.ui.components.state_manager"),
        ("LayoutManager", "svd_tool.ui.components.layout_manager"),
        ("PeripheralManager", "svd_tool.ui.components.peripheral_manager"),
        ("MenuBarBuilder", "svd_tool.ui.components.menu_bar"),
        ("ToolBarBuilder", "svd_tool.ui.components.toolbar"),
        ("MainWindowRefactored", "svd_tool.ui.main_window_refactored"),
        ("VisualizationWidget", "svd_tool.ui.widgets.visualization_widget"),
        ("AddressMapWidget", "svd_tool.ui.widgets.address_map_widget"),
        ("BitFieldWidget", "svd_tool.ui.widgets.bit_field_widget"),
    ]
    
    for name, module_path in modules:
        try:
            __import__(module_path)
            print(f"[OK] {name} 导入成功")
        except Exception as e:
            print(f"[FAIL] {name} 导入失败: {e}")
            return False
    return True

def test_window_creation():
    """测试窗口创建（不显示）"""
    print("\n=== 测试窗口创建 ===")
    try:
        from PyQt6.QtWidgets import QApplication
        from svd_tool.ui.main_window_refactored import MainWindowRefactored
        
        # 创建QApplication实例（必须存在）
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建窗口
        window = MainWindowRefactored()
        print("[OK] MainWindowRefactored 创建成功")
        
        # 检查核心组件
        if hasattr(window, 'layout_manager'):
            print("[OK] 布局管理器存在")
        if hasattr(window, 'state_manager'):
            print("[OK] 状态管理器存在")
        if hasattr(window, 'peripheral_manager'):
            print("[OK] 外设管理器存在")
        
        # 检查标签页
        lm = window.layout_manager
        tab_widget = lm.get_widget('tab_widget')
        if tab_widget:
            print(f"[OK] 标签页控件存在，数量: {tab_widget.count()}")
        else:
            print("[WARN] 标签页控件不存在")
        
        return True
    except Exception as e:
        print(f"[FAIL] 窗口创建失败: {e}")
        traceback.print_exc()
        return False

def test_data_model():
    """测试数据模型"""
    print("\n=== 测试数据模型 ===")
    try:
        from svd_tool.core.data_model import DeviceInfo, Peripheral, Register, Field
        print("[OK] 数据模型导入成功")
        
        # 创建示例对象
        device = DeviceInfo()
        peripheral = Peripheral("TEST", 0x40000000, "测试外设")
        register = Register("CTRL", 0x00, 32, "控制寄存器")
        field = Field("ENABLE", 0, 1, "使能位")
        
        print("[OK] 数据对象创建成功")
        return True
    except Exception as e:
        print(f"[FAIL] 数据模型测试失败: {e}")
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("开始最终集成测试...")
    print(f"项目根目录: {project_root}")
    
    # 执行测试
    tests = [
        ("组件导入", test_component_imports),
        ("数据模型", test_data_model),
        ("窗口创建", test_window_creation),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name}测试 ---")
        if test_func():
            passed += 1
        else:
            print(f"{test_name}测试失败")
    
    print(f"\n=== 测试结果 ===")
    print(f"通过: {passed}/{total}")
    
    if passed == total:
        print("[SUCCESS] 所有测试通过！重构迁移完成。")
        return True
    else:
        print("[FAILURE] 部分测试失败，需要进一步检查。")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)