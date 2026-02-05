#!/usr/bin/env python3
"""
GUI功能测试 - 测试实际交互功能
"""
import sys
import os
import time

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_gui_functional():
    """测试GUI功能"""
    print("=== GUI功能测试 ===")
    
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox, QMenu
        from PyQt6.QtCore import Qt, QTimer
        from svd_tool.ui.main_window_refactored import MainWindowRefactored
        
        print("[INFO] 创建QApplication实例...")
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        
        print("[INFO] 创建主窗口实例...")
        window = MainWindowRefactored()
        window.show()
        
        # 给窗口时间初始化
        app.processEvents()
        time.sleep(1)
        
        test_results = []
        
        # 测试1: 测试菜单栏功能
        print("\n[TEST 1] 测试菜单栏功能...")
        try:
            if hasattr(window, 'menuBar') and window.menuBar():
                menus = window.menuBar().findChildren(QMenu)
                if menus:
                    print(f"  [OK] 找到 {len(menus)} 个菜单")
                    test_results.append(("菜单栏", True))
                else:
                    print("  [WARN] 菜单栏存在但未找到子菜单")
                    test_results.append(("菜单栏", False))
            else:
                print("  [WARN] 菜单栏未找到")
                test_results.append(("菜单栏", False))
        except Exception as e:
            print(f"  [ERROR] 菜单栏测试失败: {e}")
            test_results.append(("菜单栏", False))
        
        # 测试2: 测试关于对话框
        print("\n[TEST 2] 测试关于对话框...")
        try:
            # 使用QTimer延迟执行，避免阻塞
            def show_about():
                try:
                    window.show_about()
                    print("  [OK] 关于对话框调用成功")
                    test_results.append(("关于对话框", True))
                except Exception as e:
                    print(f"  [ERROR] 关于对话框失败: {e}")
                    test_results.append(("关于对话框", False))
            
            QTimer.singleShot(100, show_about)
            app.processEvents()
            time.sleep(0.5)
            
        except Exception as e:
            print(f"  [ERROR] 关于对话框测试异常: {e}")
            test_results.append(("关于对话框", False))
        
        # 测试3: 测试消息系统
        print("\n[TEST 3] 测试消息系统...")
        try:
            # 测试信息消息
            def test_messages():
                try:
                    window.show_message("测试信息", "这是一个测试信息消息", "info")
                    print("  [OK] 信息消息测试通过")
                    
                    # 注意：警告和错误消息会创建模态对话框，可能会阻塞
                    # 在实际测试中可能需要特殊处理
                    test_results.append(("消息系统", True))
                except Exception as e:
                    print(f"  [ERROR] 消息系统测试失败: {e}")
                    test_results.append(("消息系统", False))
            
            QTimer.singleShot(200, test_messages)
            app.processEvents()
            time.sleep(0.5)
            
        except Exception as e:
            print(f"  [ERROR] 消息系统测试异常: {e}")
            test_results.append(("消息系统", False))
        
        # 测试4: 测试日志系统
        print("\n[TEST 4] 测试日志系统...")
        try:
            # 测试日志记录
            window.logger.info("GUI测试: 信息日志")
            window.logger.warning("GUI测试: 警告日志")
            window.logger.error("GUI测试: 错误日志")
            print("  [OK] 日志记录功能正常")
            
            # 测试日志面板切换
            if hasattr(window, 'toggle_log_panel'):
                window.toggle_log_panel(True)
                app.processEvents()
                time.sleep(0.2)
                
                window.toggle_log_panel(False)
                app.processEvents()
                time.sleep(0.2)
                print("  [OK] 日志面板切换功能正常")
            
            test_results.append(("日志系统", True))
            
        except Exception as e:
            print(f"  [ERROR] 日志系统测试失败: {e}")
            test_results.append(("日志系统", False))
        
        # 测试5: 测试搜索功能
        print("\n[TEST 5] 测试搜索功能...")
        try:
            if hasattr(window, 'on_search_text_changed'):
                # 模拟搜索文本变化
                window.on_search_text_changed("test")
                print("  [OK] 搜索功能调用成功")
                test_results.append(("搜索功能", True))
            else:
                print("  [WARN] 搜索功能未找到")
                test_results.append(("搜索功能", False))
        except Exception as e:
            print(f"  [ERROR] 搜索功能测试失败: {e}")
            test_results.append(("搜索功能", False))
        
        # 测试6: 测试数据验证
        print("\n[TEST 6] 测试数据验证...")
        try:
            if hasattr(window, 'validate_data'):
                window.validate_data()
                print("  [OK] 数据验证功能调用成功")
                test_results.append(("数据验证", True))
            else:
                print("  [WARN] 数据验证功能未找到")
                test_results.append(("数据验证", False))
        except Exception as e:
            print(f"  [ERROR] 数据验证测试失败: {e}")
            test_results.append(("数据验证", False))
        
        # 等待所有测试完成
        time.sleep(1)
        
        # 关闭窗口
        window.close()
        app.processEvents()
        
        # 统计结果
        print("\n=== GUI功能测试完成 ===")
        passed = sum(1 for _, success in test_results if success)
        total = len(test_results)
        
        print(f"测试通过率: {passed}/{total} ({passed/total*100:.1f}%)")
        
        print("\n详细结果:")
        for name, success in test_results:
            status = "✅ 通过" if success else "❌ 失败"
            print(f"  {status} {name}")
        
        return passed == total
        
    except Exception as e:
        print(f"\n[ERROR] GUI功能测试失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_gui_functional()
    sys.exit(0 if success else 1)