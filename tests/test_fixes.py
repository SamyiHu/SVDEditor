#!/usr/bin/env python3
"""
测试修复的问题
"""
import sys
import os
sys.path.insert(0, '.')

from PyQt6.QtWidgets import QApplication
from svd_tool.ui.main_window_refactored import MainWindowRefactored

def test_window_creation():
    """测试窗口创建"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    print("创建主窗口...")
    window = MainWindowRefactored()
    print("主窗口创建成功")
    
    # 检查组件
    print("检查组件...")
    
    # 检查布局管理器
    if hasattr(window, 'layout_manager'):
        print("[OK] 布局管理器存在")
        
        # 检查外设树
        periph_tree = window.layout_manager.get_widget('periph_tree')
        if periph_tree:
            print("[OK] 外设树存在")
        else:
            print("[FAIL] 外设树不存在")
            
        # 检查位域表格
        field_table = window.layout_manager.get_widget('field_table')
        if field_table:
            print("[OK] 位域表格存在")
            # 检查表格是否可编辑
            triggers = field_table.editTriggers()
            if triggers:
                print("[OK] 位域表格可编辑")
            else:
                print("[FAIL] 位域表格不可编辑")
        else:
            print("[FAIL] 位域表格不存在")
            
        # 检查按钮是否被移除
        add_field_btn = window.layout_manager.get_widget('add_field_btn')
        if add_field_btn:
            print("[FAIL] 添加位域按钮仍然存在（应该被移除）")
        else:
            print("[OK] 添加位域按钮已移除")
    else:
        print("[FAIL] 布局管理器不存在")
    
    # 检查外设管理器
    if hasattr(window, 'peripheral_manager'):
        print("[OK] 外设管理器存在")
        
        # 检查复制粘贴缓冲区
        if hasattr(window.peripheral_manager, 'copied_peripheral_data'):
            print("[OK] 复制粘贴缓冲区存在")
    else:
        print("[FAIL] 外设管理器不存在")
    
    # 检查状态管理器
    if hasattr(window, 'state_manager'):
        print("[OK] 状态管理器存在")
        
        # 检查设备信息
        if hasattr(window.state_manager, 'device_info'):
            print("[OK] 设备信息存在")
    else:
        print("[FAIL] 状态管理器不存在")
    
    print("\n测试完成！")
    
    # 不显示窗口，只测试创建
    window.close()
    return True

if __name__ == "__main__":
    try:
        success = test_window_creation()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)