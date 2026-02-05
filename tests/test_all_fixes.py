#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试所有修复"""

import sys
import os
sys.path.append('.')

from PyQt6.QtWidgets import QApplication
from svd_tool.ui.main_window_refactored import MainWindowRefactored

def test_fixes():
    app = QApplication([])
    window = MainWindowRefactored()
    
    print("测试所有修复:")
    print("1. 检查树状图展开状态保存功能...")
    # 检查peripheral_manager中的_get_expanded_items方法
    if hasattr(window.peripheral_manager, '_get_expanded_items'):
        print("   [OK] peripheral_manager有_get_expanded_items方法")
    else:
        print("   [FAIL] peripheral_manager缺少_get_expanded_items方法")
    
    print("2. 检查寄存器树列标题...")
    reg_tree = window.layout_manager.get_widget('reg_tree')
    if reg_tree:
        headers = []
        for i in range(reg_tree.columnCount()):
            header = reg_tree.headerItem().text(i) if reg_tree.headerItem() else f"col{i}"
            headers.append(header)
        print(f"   寄存器树列标题: {headers}")
        if "描述" in headers:
            print("   [OK] 寄存器树包含'描述'列")
        else:
            print("   [FAIL] 寄存器树缺少'描述'列")
    
    print("3. 检查中断表格列顺序...")
    irq_table = window.layout_manager.get_widget('irq_table')
    if irq_table:
        headers = []
        for i in range(irq_table.columnCount()):
            header = irq_table.horizontalHeaderItem(i).text() if irq_table.horizontalHeaderItem(i) else f"col{i}"
            headers.append(header)
        print(f"   中断表格列标题: {headers}")
        # 检查列顺序：名称, 值, 外设, 描述
        if len(headers) >= 4 and headers[2] == "外设" and headers[3] == "描述":
            print("   [OK] 中断表格列顺序正确（外设在描述之前）")
        else:
            print("   [FAIL] 中断表格列顺序可能不正确")
    
    print("4. 检查update_data_model_from_tree方法...")
    if hasattr(window, 'update_data_model_from_tree'):
        print("   [OK] 主窗口有update_data_model_from_tree方法")
    else:
        print("   [FAIL] 主窗口缺少update_data_model_from_tree方法")
    
    print("5. 检查field_table按钮...")
    field_table = window.layout_manager.get_widget('field_table')
    if field_table:
        # 检查field_table的父组件是否有按钮
        parent = field_table.parent()
        button_count = 0
        if parent:
            for child in parent.children():
                if child.__class__.__name__ == 'QPushButton':
                    button_count += 1
        print(f"   field_table父组件有{button_count}个按钮")
        # field_table应该没有专门的工具栏按钮，但可能有寄存器工具栏按钮
        # 这是正常的
    
    print("\n所有测试完成。")
    app.quit()

if __name__ == "__main__":
    test_fixes()