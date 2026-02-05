#!/usr/bin/env python3
"""
测试标签页添加问题
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QTabWidget, QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import QTimer

def test_simple_tab():
    app = QApplication(sys.argv)
    tab_widget = QTabWidget()
    tab = QWidget()
    layout = QVBoxLayout(tab)
    layout.addWidget(QLabel("测试标签页"))
    tab_widget.addTab(tab, "测试")
    print(f"简单测试: 标签页数量={tab_widget.count()}")
    # 显示
    tab_widget.show()
    QTimer.singleShot(500, app.quit)
    app.exec()

def test_layout_manager():
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
    widgets = lm.create_layout()
    tab_widget = widgets.get('tab_widget')
    print(f"布局管理器标签页控件: {tab_widget}")
    if tab_widget:
        print(f"初始标签页数量: {tab_widget.count()}")
        # 尝试直接调用create_basic_info_tab
        try:
            lm.create_basic_info_tab(tab_widget)
            print(f"调用后标签页数量: {tab_widget.count()}")
        except Exception as e:
            print(f"异常: {e}")
            import traceback
            traceback.print_exc()
    QTimer.singleShot(500, app.quit)
    app.exec()

if __name__ == "__main__":
    print("=== 简单测试 ===")
    test_simple_tab()
    print("\n=== 布局管理器测试 ===")
    test_layout_manager()