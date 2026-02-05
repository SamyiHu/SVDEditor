#!/usr/bin/env python3
"""
GUI基本功能测试 - 启动重构版主窗口
"""
import sys
import os
import time

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_gui_launch():
    """测试GUI启动"""
    print("=== GUI基本功能测试 ===")
    print("[INFO] 导入必要的模块...")
    
    try:
        from PyQt6.QtWidgets import QApplication
        from svd_tool.ui.main_window_refactored import MainWindowRefactored
        
        print("[INFO] 创建QApplication实例...")
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        
        print("[INFO] 创建主窗口实例...")
        window = MainWindowRefactored()
        
        # 检查窗口属性
        print("\n[TEST] 检查窗口基本属性...")
        checks = [
            ("窗口标题", hasattr(window, 'windowTitle'), window.windowTitle() if hasattr(window, 'windowTitle') else "N/A"),
            ("状态管理器", hasattr(window, 'state_manager'), "存在" if hasattr(window, 'state_manager') else "缺失"),
            ("布局管理器", hasattr(window, 'layout_manager'), "存在" if hasattr(window, 'layout_manager') else "缺失"),
            ("外设管理器", hasattr(window, 'peripheral_manager'), "存在" if hasattr(window, 'peripheral_manager') else "缺失"),
            ("日志系统", hasattr(window, 'logger'), "存在" if hasattr(window, 'logger') else "缺失"),
            ("菜单栏", hasattr(window, 'menuBar'), "存在" if hasattr(window, 'menuBar') else "缺失"),
            ("工具栏", hasattr(window, 'toolbar'), "存在" if hasattr(window, 'toolbar') else "缺失"),
        ]
        
        all_ok = True
        for name, check, value in checks:
            if check:
                print(f"  [OK] {name}: {value}")
            else:
                print(f"  [FAIL] {name}: 缺失")
                all_ok = False
        
        # 检查UI组件
        print("\n[TEST] 检查UI组件...")
        ui_checks = [
            ("中心部件", window.centralWidget() is not None, "存在" if window.centralWidget() is not None else "缺失"),
            ("标签页控件", hasattr(window, 'tab_widget'), "存在" if hasattr(window, 'tab_widget') else "缺失"),
            ("树控件", hasattr(window, 'periph_tree'), "存在" if hasattr(window, 'periph_tree') else "缺失"),
            ("搜索框", hasattr(window, 'search_edit'), "存在" if hasattr(window, 'search_edit') else "缺失"),
            ("状态栏", window.statusBar() is not None, "存在" if window.statusBar() is not None else "缺失"),
        ]
        
        for name, check, value in ui_checks:
            if check:
                print(f"  [OK] {name}: {value}")
            else:
                print(f"  [WARN] {name}: {value}")
        
        # 显示窗口（短暂显示）
        print("\n[INFO] 显示窗口（3秒）...")
        window.show()
        
        # 处理事件
        app.processEvents()
        time.sleep(3)
        
        # 关闭窗口
        print("[INFO] 关闭窗口...")
        window.close()
        
        print("\n=== GUI启动测试完成 ===")
        if all_ok:
            print("[SUCCESS] 所有基本检查通过")
            return True
        else:
            print("[WARNING] 部分检查未通过")
            return False
            
    except Exception as e:
        print(f"\n[ERROR] GUI启动测试失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_gui_launch()
    sys.exit(0 if success else 1)