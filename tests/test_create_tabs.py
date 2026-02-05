#!/usr/bin/env python3
"""
测试创建标签页
"""
import sys
import traceback
sys.path.insert(0, '.')
sys.stderr = sys.stdout

from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtCore import QTimer
import logging
logging.basicConfig(level=logging.DEBUG)

app = QApplication(sys.argv)
window = QMainWindow()

from svd_tool.ui.components.layout_manager import LayoutManager
lm = LayoutManager(window)
widgets = lm.create_layout()
tab_widget = widgets.get('tab_widget')
print(f'1. 初始标签页数量: {tab_widget.count()}')

# 测试create_basic_info_tab
print('\\n2. 调用create_basic_info_tab')
try:
    result = lm.create_basic_info_tab(tab_widget)
    print(f'成功: {result}')
except Exception as e:
    print(f'失败: {e}')
    traceback.print_exc()
print(f'标签页数量: {tab_widget.count()}')

# 测试create_peripheral_tab
print('\\n3. 调用create_peripheral_tab')
try:
    result = lm.create_peripheral_tab(tab_widget)
    print(f'成功: {result}')
except Exception as e:
    print(f'失败: {e}')
    traceback.print_exc()
print(f'标签页数量: {tab_widget.count()}')

# 测试create_interrupt_tab
print('\\n4. 调用create_interrupt_tab')
try:
    result = lm.create_interrupt_tab(tab_widget)
    print(f'成功: {result}')
except Exception as e:
    print(f'失败: {e}')
    traceback.print_exc()
print(f'标签页数量: {tab_widget.count()}')

# 显示窗口
window.show()
QTimer.singleShot(1000, app.quit)
app.exec()