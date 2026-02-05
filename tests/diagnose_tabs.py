#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from svd_tool.ui.components.layout_manager import LayoutManager

class MockWindow:
    def setWindowTitle(self, title): pass
    def setGeometry(self, *args): pass
    def setCentralWidget(self, w): pass
    def setStatusBar(self, sb): pass
    def menuBar(self): return None
    def setMenuBar(self, mb): pass
    def statusBar(self): return None

app = QApplication(sys.argv)
window = MockWindow()
lm = LayoutManager(window)
print("开始create_layout")
widgets = lm.create_layout()
print(f"返回的widgets键: {list(widgets.keys())}")
tab_widget = widgets.get('tab_widget')
print(f"tab_widget: {tab_widget}")
if tab_widget:
    print(f"tab_widget类型: {type(tab_widget)}")
    print(f"标签页数量: {tab_widget.count()}")
    # 尝试添加标签页
    try:
        lm.create_basic_info_tab(tab_widget)
        print(f"添加后标签页数量: {tab_widget.count()}")
    except Exception as e:
        print(f"添加标签页异常: {e}")
        import traceback
        traceback.print_exc()
else:
    print("错误：未找到tab_widget")

# 检查layout_manager内部的widgets
print(f"lm.widgets键: {list(lm.widgets.keys())}")
print(f"lm.widgets['tab_widget']存在: {'tab_widget' in lm.widgets}")

# 测试get_widget
print(f"get_widget('tab_widget'): {lm.get_widget('tab_widget')}")

app.quit()