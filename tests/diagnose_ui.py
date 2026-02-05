#!/usr/bin/env python3
"""
诊断重构版UI问题
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QWidget, QTabWidget, QLabel
from PyQt6.QtCore import QTimer
import traceback

def print_widget_tree(widget, indent=0):
    """打印控件树"""
    prefix = '  ' * indent
    cls = widget.__class__.__name__
    name = widget.objectName() or ''
    visible = widget.isVisible()
    enabled = widget.isEnabled()
    geometry = widget.geometry()
    size = geometry.width(), geometry.height()
    print(f"{prefix}{cls} '{name}' visible={visible} enabled={enabled} size={size}")
    if isinstance(widget, QTabWidget):
        print(f"{prefix}  标签页数量: {widget.count()}")
        for i in range(widget.count()):
            tab_text = widget.tabText(i)
            tab_widget = widget.widget(i)
            print(f"{prefix}    标签页{i}: '{tab_text}' 控件: {tab_widget}")
    # 递归子控件
    for child in widget.children():
        if isinstance(child, QWidget):
            print_widget_tree(child, indent + 1)

def main():
    try:
        app = QApplication(sys.argv)
        from svd_tool.ui.main_window_refactored import MainWindowRefactored
        print("创建窗口...")
        window = MainWindowRefactored()
        print("窗口创建完成")
        
        # 立即处理事件以确保布局完成
        QApplication.processEvents()
        
        # 检查窗口属性
        print(f"窗口标题: {window.windowTitle()}")
        print(f"窗口大小: {window.size().width()}x{window.size().height()}")
        
        # 检查中央部件
        central = window.centralWidget()
        print(f"中央部件: {central}")
        if central:
            print(f"中央部件布局: {central.layout()}")
        
        # 检查布局管理器
        lm = window.layout_manager
        print(f"布局管理器: {lm}")
        
        # 检查标签页控件
        tab_widget = lm.get_widget('tab_widget')
        print(f"标签页控件: {tab_widget}")
        if tab_widget:
            print(f"标签页数量: {tab_widget.count()}")
            for i in range(tab_widget.count()):
                print(f"  标签页{i}: '{tab_widget.tabText(i)}'")
        else:
            print("标签页控件不存在！")
        
        # 检查外设树
        periph_tree = lm.get_widget('periph_tree')
        print(f"外设树: {periph_tree}")
        
        # 检查日志面板
        if hasattr(window, 'log_dock'):
            print(f"日志面板: {window.log_dock}")
            print(f"日志面板是否可见: {window.log_dock.isVisible()}")
        else:
            print("日志面板属性不存在")
        
        # 打印完整控件树
        print("\n=== 控件树 ===")
        print_widget_tree(window)
        
        # 显示窗口
        window.show()
        QApplication.processEvents()
        
        # 延迟退出
        QTimer.singleShot(1000, app.quit)
        ret = app.exec()
        print(f"应用退出: {ret}")
        return 0
    except Exception as e:
        print(f"异常: {e}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())