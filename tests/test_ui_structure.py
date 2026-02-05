#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试UI结构，查找外设映射图表格"""

import sys
import os
sys.path.append('.')

from PyQt6.QtWidgets import QApplication
from svd_tool.ui.main_window_refactored import MainWindowRefactored

def test_ui_structure():
    app = QApplication([])
    window = MainWindowRefactored()
    
    # 打印窗口组件列表
    print("窗口组件列表:")
    if hasattr(window, 'layout_manager') and hasattr(window.layout_manager, 'widgets'):
        for name, widget in window.layout_manager.widgets.items():
            print(f"  {name}: {type(widget).__name__}")
    
    # 查找所有表格
    print("\n查找所有表格:")
    def find_tables(widget, depth=0, path=""):
        indent = "  " * depth
        widget_type = type(widget).__name__
        
        # 检查是否是表格
        if widget_type in ['QTableWidget', 'QTableView']:
            print(f"{indent}{path}/{widget_type}")
            if hasattr(widget, 'horizontalHeader'):
                header = widget.horizontalHeader()
                if header:
                    labels = []
                    for i in range(widget.columnCount()):
                        label = header.model().headerData(i, 1)  # 1 for horizontal
                        labels.append(str(label) if label else f"col{i}")
                    print(f"{indent}  列: {labels}")
        
        # 递归检查子组件
        if hasattr(widget, 'children'):
            for i, child in enumerate(widget.children()):
                child_path = f"{path}/{widget_type}[{i}]"
                find_tables(child, depth+1, child_path)
    
    # 从主窗口开始查找
    find_tables(window, 0, "MainWindow")
    
    app.quit()

if __name__ == "__main__":
    test_ui_structure()