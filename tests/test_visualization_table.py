#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试可视化控件相关的表格"""

import sys
import os
sys.path.append('.')

from PyQt6.QtWidgets import QApplication
from svd_tool.ui.main_window_refactored import MainWindowRefactored

def test_visualization_tables():
    app = QApplication([])
    window = MainWindowRefactored()
    
    # 获取可视化控件
    visualization_widget = window.layout_manager.get_widget('visualization_widget')
    if visualization_widget:
        print(f"可视化控件类型: {type(visualization_widget).__name__}")
        
        # 检查可视化控件的父组件
        parent = visualization_widget.parent()
        if parent:
            print(f"父组件: {type(parent).__name__}")
            
            # 检查父组件的所有子组件
            print("\n父组件的子组件:")
            for i, child in enumerate(parent.children()):
                child_type = type(child).__name__
                print(f"  [{i}] {child_type}")
                
                # 如果是表格，打印详细信息
                if child_type in ['QTableWidget', 'QTableView']:
                    print(f"     表格位于可视化控件的: {'上方' if parent.children().index(child) < parent.children().index(visualization_widget) else '下方'}")
    
    # 检查field_table
    field_table = window.layout_manager.get_widget('field_table')
    if field_table:
        print(f"\nfield_table存在: {type(field_table).__name__}")
        print(f"  列数: {field_table.columnCount()}")
        print(f"  行数: {field_table.rowCount()}")
        
        # 检查是否有按钮
        parent = field_table.parent()
        if parent:
            print(f"  field_table父组件: {type(parent).__name__}")
            print(f"  父组件的子组件:")
            for i, child in enumerate(parent.children()):
                child_type = type(child).__name__
                if child_type == 'QPushButton':
                    print(f"    按钮: {child.text() if child.text() else '无文本'}")
    
    app.quit()

if __name__ == "__main__":
    test_visualization_tables()