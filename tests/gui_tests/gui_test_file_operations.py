#!/usr/bin/env python3
"""
GUI文件操作功能测试
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_file_operations():
    """测试文件操作功能"""
    print("=== GUI文件操作功能测试 ===")
    
    try:
        from PyQt6.QtWidgets import QApplication
        from svd_tool.ui.main_window_refactored import MainWindowRefactored
        
        print("[INFO] 创建QApplication实例...")
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        
        print("[INFO] 创建主窗口实例...")
        window = MainWindowRefactored()
        
        test_results = []
        
        # 检查文件操作方法
        print("\n[TEST] 检查文件操作方法...")
        file_methods = [
            ('new_file', '新建文件'),
            ('open_svd_file', '打开SVD文件'),
            ('save_svd_file_impl', '保存SVD文件'),
            ('check_unsaved_changes', '检查未保存更改'),
            ('generate_svd', '生成SVD'),
            ('preview_xml', '预览XML'),
            ('export_file', '导出文件'),
        ]
        
        for method_name, desc in file_methods:
            if hasattr(window, method_name):
                print(f"  [OK] {desc}方法存在")
                test_results.append((desc, True))
            else:
                print(f"  [WARN] {desc}方法缺失")
                test_results.append((desc, False))
        
        # 测试基本文件操作（不实际执行，只检查函数调用）
        print("\n[TEST] 测试基本文件操作调用...")
        try:
            # 测试新建文件（不实际创建文件）
            if hasattr(window, 'new_file'):
                # 只检查函数是否存在，不实际调用以避免副作用
                print("  [OK] 新建文件功能可用")
            else:
                print("  [WARN] 新建文件功能不可用")
        except Exception as e:
            print(f"  [ERROR] 新建文件测试失败: {e}")
        
        # 检查SVD生成功能
        print("\n[TEST] 检查SVD生成功能...")
        try:
            if hasattr(window, 'generate_svd'):
                # 检查函数签名
                import inspect
                sig = inspect.signature(window.generate_svd)
                print(f"  [OK] SVD生成函数签名: {sig}")
            else:
                print("  [WARN] SVD生成功能缺失")
        except Exception as e:
            print(f"  [ERROR] SVD生成检查失败: {e}")
        
        # 统计结果
        print("\n=== 文件操作功能测试完成 ===")
        passed = sum(1 for _, success in test_results if success)
        total = len(test_results)
        
        print(f"方法存在率: {passed}/{total} ({passed/total*100:.1f}%)")
        
        if passed == total:
            print("[SUCCESS] 所有文件操作方法都存在")
            return True
        else:
            print("[WARNING] 部分文件操作方法缺失")
            return False
            
    except Exception as e:
        print(f"\n[ERROR] 文件操作测试失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_file_operations()
    sys.exit(0 if success else 1)