#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget
app = QApplication(sys.argv)
window = QMainWindow()
central = QWidget()
window.setCentralWidget(central)
tab = QTabWidget(central)
print(f"tab is None: {tab is None}")
print(f"bool(tab): {bool(tab)}")
print(f"tab.__bool__: {tab.__bool__}")
print(f"tab.isWidgetType(): {tab.isWidgetType()}")
print(f"tab.objectName(): {tab.objectName()}")
print(f"tab.parent(): {tab.parent()}")
# 测试 if 条件
if tab:
    print("if tab: 为真")
else:
    print("if tab: 为假")
if tab is not None:
    print("if tab is not None: 为真")
else:
    print("if tab is not None: 为假")