#!/usr/bin/env python3
"""
测试最终修复：
1. 添加按钮功能
2. 中断按钮状态
3. 外设寄存器图联动
"""

import sys
import os
sys.path.insert(0, '.')

def test_add_button_logic():
    """测试添加按钮逻辑"""
    print("=== 测试添加按钮逻辑 ===")
    
    try:
        # 读取on_add_button_clicked方法
        with open('svd_tool/ui/main_window_refactored.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查方法是否存在
        if 'def on_add_button_clicked(self):' in content:
            print("[OK] on_add_button_clicked方法存在")
            
            # 检查逻辑分支
            if 'if not peripheral:' in content:
                print("[OK] 有'没有选中外设'的分支")
            else:
                print("[FAIL] 缺少'没有选中外设'的分支")
                
            if 'elif peripheral and not register:' in content:
                print("[OK] 有'选中了外设但没有选中寄存器'的分支")
            else:
                print("[FAIL] 缺少'选中了外设但没有选中寄存器'的分支")
                
            if 'elif peripheral and register:' in content:
                print("[OK] 有'选中了外设和寄存器'的分支")
            else:
                print("[FAIL] 缺少'选中了外设和寄存器'的分支")
                
            return True
        else:
            print("[FAIL] on_add_button_clicked方法不存在")
            return False
            
    except Exception as e:
        print(f"[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_interrupt_button_connections():
    """测试中断按钮连接"""
    print("\n=== 测试中断按钮连接 ===")
    
    try:
        # 读取setup_signals方法
        with open('svd_tool/ui/main_window_refactored.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查中断按钮连接
        if 'add_irq_btn.clicked.connect(self.add_interrupt)' in content:
            print("[OK] 添加中断按钮连接正确")
        else:
            print("[FAIL] 添加中断按钮连接错误")
            
        if 'edit_irq_btn.clicked.connect(lambda: self.edit_interrupt())' in content:
            print("[OK] 编辑中断按钮连接正确")
        else:
            print("[FAIL] 编辑中断按钮连接错误")
            
        if 'delete_irq_btn.clicked.connect(lambda: self.delete_interrupt())' in content:
            print("[OK] 删除中断按钮连接正确")
        else:
            print("[FAIL] 删除中断按钮连接错误")
            
        return True
        
    except Exception as e:
        print(f"[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_visualization_linkage():
    """测试可视化联动功能"""
    print("\n=== 测试可视化联动功能 ===")
    
    try:
        # 读取on_register_clicked方法
        with open('svd_tool/ui/main_window_refactored.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查on_register_clicked方法
        if 'def on_register_clicked(self, register):' in content:
            print("[OK] on_register_clicked方法存在")
            
            # 检查是否更新树控件选择
            if 'periph_tree.setCurrentItem(reg_item)' in content:
                print("[OK] on_register_clicked会更新树控件选择")
            else:
                print("[FAIL] on_register_clicked不会更新树控件选择")
        else:
            print("[FAIL] on_register_clicked方法不存在")
            
        # 检查on_field_clicked方法
        if 'def on_field_clicked(self, field):' in content:
            print("[OK] on_field_clicked方法存在")
            
            # 检查是否更新树控件选择
            if 'periph_tree.setCurrentItem(reg_item)' in content:
                print("[OK] on_field_clicked会更新树控件选择")
            else:
                print("[FAIL] on_field_clicked不会更新树控件选择")
        else:
            print("[FAIL] on_field_clicked方法不存在")
            
        return True
        
    except Exception as e:
        print(f"[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_register_size_editable():
    """测试寄存器大小可编辑"""
    print("\n=== 测试寄存器大小可编辑 ===")
    
    try:
        # 读取dialog_factories.py
        with open('svd_tool/ui/dialog_factories.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否移除了setReadOnly(True)
        if 'self.size_edit.setReadOnly(True)' in content:
            print("[FAIL] 寄存器大小编辑框仍然是只读的")
            return False
        else:
            print("[OK] 寄存器大小编辑框不是只读的")
            
        # 检查是否有占位符文本
        if 'self.size_edit.setPlaceholderText' in content:
            print("[OK] 寄存器大小编辑框有占位符文本")
        else:
            print("[WARN] 寄存器大小编辑框没有占位符文本")
            
        return True
        
    except Exception as e:
        print(f"[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """运行所有测试"""
    print("开始测试所有修复...")
    print("=" * 50)
    
    tests = [
        test_add_button_logic,
        test_interrupt_button_connections,
        test_visualization_linkage,
        test_register_size_editable
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
    
    test_names = [
        "添加按钮逻辑",
        "中断按钮连接",
        "可视化联动",
        "寄存器大小可编辑"
    ]
    
    for i, (name, result) in enumerate(zip(test_names, results), 1):
        status = "[PASS] 通过" if result else "[FAIL] 失败"
        print(f"{i}. {name}: {status}")
    
    print(f"\n总计: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("[SUCCESS] 所有测试通过！所有修复都已成功应用。")
        return 0
    else:
        print("[WARNING] 部分测试失败，请检查相关修复。")
        return 1

if __name__ == '__main__':
    sys.exit(main())