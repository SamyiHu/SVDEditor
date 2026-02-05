#!/usr/bin/env python3
"""
简单测试新架构导入
"""
import sys
import os

# 添加项目路径（向上两级到项目根目录）
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

try:
    print("Testing new architecture import...")
    
    # 测试导入组件
    from svd_tool.ui.components.state_manager import StateManager
    print("StateManager import OK")
    
    from svd_tool.ui.components.layout_manager import LayoutManager
    print("LayoutManager import OK")
    
    from svd_tool.ui.components.peripheral_manager import PeripheralManager
    print("PeripheralManager import OK")
    
    from svd_tool.ui.components.menu_bar import MenuBarBuilder
    print("MenuBarBuilder import OK")
    
    from svd_tool.ui.components.toolbar import ToolBarBuilder
    print("ToolBarBuilder import OK")
    
    # 测试导入主窗口
    from svd_tool.ui.main_window_refactored import MainWindowRefactored
    print("MainWindowRefactored import OK")
    
    # 测试组件创建
    print("\nTesting component creation...")
    
    # 创建模拟的主窗口用于测试
    class MockMainWindow:
        def __init__(self):
            self.tree_manager = None
    
    # 测试状态管理器
    state = StateManager()
    print("StateManager created")
    
    # 测试布局管理器（需要主窗口参数）
    mock_window = MockMainWindow()
    layout = LayoutManager(mock_window)
    print("LayoutManager created")
    
    # 测试外设管理器
    peripheral = PeripheralManager(state, layout)
    print("PeripheralManager created")
    
    print("\n=== New architecture test PASSED ===")
    print("You can run the new architecture by:")
    print("1. Direct run: python svd_tool/ui/main_window_refactored.py")
    print("2. Modify main.py import")
    print("3. Create new launch script")
    
except Exception as e:
    print(f"\nTest FAILED: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()