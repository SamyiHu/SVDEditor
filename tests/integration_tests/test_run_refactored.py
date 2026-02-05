#!/usr/bin/env python3
"""
测试运行新架构
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    print("=== 测试新架构导入 ===")
    
    # 测试导入组件
    from svd_tool.ui.components.state_manager import StateManager
    print("[OK] StateManager 导入成功")
    
    from svd_tool.ui.components.layout_manager import LayoutManager
    print("[OK] LayoutManager 导入成功")
    
    from svd_tool.ui.components.peripheral_manager import PeripheralManager
    print("[OK] PeripheralManager 导入成功")
    
    from svd_tool.ui.components.menu_bar import MenuBarBuilder
    print("[OK] MenuBarBuilder 导入成功")
    
    from svd_tool.ui.components.toolbar import ToolBarBuilder
    print("[OK] ToolBarBuilder 导入成功")
    
    # 测试导入主窗口
    from svd_tool.ui.main_window_refactored import MainWindowRefactored
    print("[OK] MainWindowRefactored 导入成功")
    
    # 测试组件创建
    print("\n=== 测试组件创建 ===")
    
    # 创建模拟的主窗口用于测试
    class MockMainWindow:
        def __init__(self):
            self.tree_manager = None
    
    # 测试状态管理器
    state = StateManager()
    print("[OK] StateManager 创建成功")
    
    # 测试布局管理器（需要主窗口参数）
    mock_window = MockMainWindow()
    layout = LayoutManager(mock_window)
    print("[OK] LayoutManager 创建成功")
    
    # 测试外设管理器
    peripheral = PeripheralManager(state, layout)
    print("[OK] PeripheralManager 创建成功")
    
    print("\n=== 新架构测试通过 ===")
    print("你可以通过以下方式运行新架构：")
    print("1. 直接运行: python svd_tool/ui/main_window_refactored.py")
    print("2. 修改 main.py 中的导入")
    print("3. 创建新的启动脚本")
    
except Exception as e:
    print(f"\n[FAIL] 测试失败: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()