#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QMainWindow
from svd_tool.ui.components.layout_manager import LayoutManager

app = QApplication(sys.argv)
window = QMainWindow()
lm = LayoutManager(window)
print("开始create_layout")
try:
    widgets = lm.create_layout()
    print(f"返回的widgets键: {list(widgets.keys())}")
    tab_widget = widgets.get('tab_widget')
    print(f"tab_widget: {tab_widget}")
    if tab_widget is not None:
        print(f"标签页数量: {tab_widget.count()}")
        # 直接调用添加标签页
        print("调用create_basic_info_tab")
        lm.create_basic_info_tab(tab_widget)
        print(f"调用后标签页数量: {tab_widget.count()}")
        print("调用create_peripheral_tab")
        lm.create_peripheral_tab(tab_widget)
        print(f"调用后标签页数量: {tab_widget.count()}")
        print("调用create_interrupt_tab")
        lm.create_interrupt_tab(tab_widget)
        print(f"调用后标签页数量: {tab_widget.count()}")
        print("调用create_preview_tab")
        lm.create_preview_tab(tab_widget)
        print(f"调用后标签页数量: {tab_widget.count()}")
    else:
        print("错误：未找到tab_widget")
except Exception as e:
    print(f"异常: {e}")
    import traceback
    traceback.print_exc()

# 显示窗口
window.show()
# 短暂运行后退出
from PyQt6.QtCore import QTimer
QTimer.singleShot(500, app.quit)
app.exec()