#!/usr/bin/env python3
"""
测试我们修复的问题：
1. 按钮功能异常 - 智能按钮处理
2. 统一选择的视觉效果 - CSS样式
3. 中断编辑和删除按钮无效 - 获取选中中断的逻辑
4. 寄存器大小不能更改 - 移除setReadOnly(True)
"""

import sys
import os
sys.path.insert(0, '.')

def test_register_size_editable():
    """测试寄存器大小是否可编辑"""
    print("=== 测试寄存器大小是否可编辑 ===")
    
    try:
        from svd_tool.ui.dialog_factories import RegisterEditDialog
        from PyQt6.QtWidgets import QApplication
        
        # 创建应用实例（不显示）
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建对话框
        dialog = RegisterEditDialog()
        
        # 检查大小编辑框
        size_edit = dialog.size_edit
        is_readonly = size_edit.isReadOnly()
        default_value = size_edit.text()
        placeholder = size_edit.placeholderText()
        
        print(f"大小编辑框是否只读: {is_readonly}")
        print(f"大小编辑框默认值: {default_value}")
        print(f"大小编辑框占位符: {placeholder}")
        
        if is_readonly:
            print("[FAIL] 失败: 大小编辑框仍然是只读的")
            return False
        else:
            print("[OK] 成功: 大小编辑框现在是可编辑的")
            return True
            
    except Exception as e:
        print(f"❌ 测试失败，出现异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_button_methods_exist():
    """测试智能按钮方法是否存在"""
    print("\n=== 测试智能按钮方法是否存在 ===")
    
    try:
        from svd_tool.ui.main_window_refactored import MainWindowRefactored
        
        # 检查方法是否存在
        methods_to_check = [
            'on_add_button_clicked',
            'on_edit_button_clicked', 
            'on_delete_button_clicked'
        ]
        
        all_exist = True
        for method_name in methods_to_check:
            if hasattr(MainWindowRefactored, method_name):
                print(f"[OK] {method_name} 方法存在")
            else:
                print(f"[FAIL] {method_name} 方法不存在")
                all_exist = False
        
        return all_exist
        
    except Exception as e:
        print(f"[ERROR] 测试失败，出现异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_interrupt_methods_updated():
    """测试中断方法是否已更新"""
    print("\n=== 测试中断方法是否已更新 ===")
    
    try:
        # 读取文件内容检查
        with open('svd_tool/ui/main_window_refactored.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查edit_interrupt方法是否包含获取选中中断的逻辑
        if 'irq_table = self.layout_manager.get_widget' in content and 'selected_rows = irq_table.selectedItems()' in content:
            print("[OK] edit_interrupt 方法已更新，包含获取选中中断的逻辑")
            edit_updated = True
        else:
            print("[FAIL] edit_interrupt 方法未正确更新")
            edit_updated = False
        
        # 检查delete_interrupt方法是否包含获取选中中断的逻辑
        if 'if interrupt_name is None:' in content and 'interrupt_name = selected_rows[0].text()' in content:
            print("[OK] delete_interrupt 方法已更新，包含获取选中中断的逻辑")
            delete_updated = True
        else:
            print("[FAIL] delete_interrupt 方法未正确更新")
            delete_updated = False
        
        return edit_updated and delete_updated
        
    except Exception as e:
        print(f"[ERROR] 测试失败，出现异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_css_styles_unified():
    """测试CSS样式是否统一"""
    print("\n=== 测试CSS样式是否统一 ===")
    
    try:
        # 读取layout_manager.py文件检查CSS样式
        with open('svd_tool/ui/components/layout_manager.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否使用了统一的选中颜色 #d1e9ff
        if '#d1e9ff' in content:
            print("[OK] CSS样式使用了统一的选中颜色 #d1e9ff")
            color_unified = True
        else:
            print("[FAIL] CSS样式未使用统一的选中颜色")
            color_unified = False
        
        # 检查是否有统一的样式设置
        if 'background-color: #d1e9ff' in content:
            print("[OK] CSS样式设置了统一的选中背景色 #d1e9ff")
            style_unified = True
        else:
            print("[FAIL] CSS样式未设置统一的选中背景色")
            style_unified = False
        
        return color_unified and style_unified
        
    except Exception as e:
        print(f"[ERROR] 测试失败，出现异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """运行所有测试"""
    print("开始测试所有修复...")
    print("=" * 50)
    
    tests = [
        test_register_size_editable,
        test_button_methods_exist,
        test_interrupt_methods_updated,
        test_css_styles_unified
    ]
    
    results = []
    for test_func in tests:
        result = test_func()
        results.append(result)
        print("-" * 50)
    
    # 汇总结果
    print("\n" + "=" * 50)
    print("测试结果汇总:")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    for i, (test_func, result) in enumerate(zip(tests, results), 1):
        status = "[PASS] 通过" if result else "[FAIL] 失败"
        print(f"{i}. {test_func.__name__}: {status}")
    
    print(f"\n总计: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("[SUCCESS] 所有测试通过！所有修复都已成功应用。")
        return 0
    else:
        print("[WARNING] 部分测试失败，请检查相关修复。")
        return 1

if __name__ == '__main__':
    sys.exit(main())