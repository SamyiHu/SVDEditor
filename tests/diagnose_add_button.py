#!/usr/bin/env python3
"""
诊断添加按钮问题
"""

import sys
sys.path.insert(0, '.')

def test_state_manager_selection():
    """测试状态管理器的选择功能"""
    print("=== 测试状态管理器的选择功能 ===")
    
    try:
        from svd_tool.ui.components.state_manager import StateManager
        
        # 创建StateManager实例
        state_manager = StateManager()
        
        # 测试设置和获取选择
        state_manager.set_selection("WDT", None, None)
        selection = state_manager.get_selection()
        
        print(f"设置选择: peripheral='WDT', register=None, field=None")
        print(f"获取选择: {selection}")
        
        peripheral = selection.get('peripheral')
        register = selection.get('register')
        field = selection.get('field')
        
        print(f"peripheral: {peripheral}")
        print(f"register: {register}")
        print(f"field: {field}")
        
        # 测试on_add_button_clicked的逻辑
        print("\n=== 测试on_add_button_clicked逻辑 ===")
        if not peripheral:
            print("逻辑: 没有选中外设，添加外设")
        elif peripheral and not register:
            print("逻辑: 选中了外设但没有选中寄存器，添加寄存器")
        elif peripheral and register:
            print("逻辑: 选中了外设和寄存器，添加位域")
            
        return True
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_add_register_method():
    """测试add_register方法"""
    print("\n=== 测试add_register方法 ===")
    
    try:
        # 读取add_register方法代码
        with open('svd_tool/ui/main_window_refactored.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 查找add_register方法
        import re
        add_register_pattern = r'def add_register\(self\):(.*?)(?=\n    def |\n\n)'
        match = re.search(add_register_pattern, content, re.DOTALL)
        
        if match:
            method_code = match.group(1)
            print("找到add_register方法")
            
            # 检查关键逻辑
            if 'current_peripheral = self.state_manager.get_current_peripheral()' in method_code:
                print("[OK] 使用get_current_peripheral()获取当前外设")
            else:
                print("[FAIL] 未使用get_current_peripheral()")
                
            if 'QMessageBox.warning.*请先选择一个外设' in method_code:
                print("[OK] 有'请先选择一个外设'的警告")
            else:
                print("[FAIL] 没有'请先选择一个外设'的警告")
                
            return True
        else:
            print("✗ 未找到add_register方法")
            return False
            
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """运行诊断"""
    print("开始诊断添加按钮问题...")
    print("=" * 50)
    
    test1 = test_state_manager_selection()
    test2 = test_add_register_method()
    
    print("\n" + "=" * 50)
    print("诊断结果:")
    print(f"1. 状态管理器选择测试: {'通过' if test1 else '失败'}")
    print(f"2. add_register方法测试: {'通过' if test2 else '失败'}")
    
    if test1 and test2:
        print("\n可能的问题:")
        print("1. StateManager的选择可能没有正确更新")
        print("2. 可能是按钮信号连接错误")
        print("3. 可能是WDT外设不存在于device_info中")
        print("\n建议:")
        print("1. 检查PeripheralManager是否正确更新StateManager")
        print("2. 检查按钮信号是否正确连接")
        print("3. 添加调试日志查看实际的选择状态")
    else:
        print("\n测试失败，需要进一步调查")
    
    return 0 if test1 and test2 else 1

if __name__ == '__main__':
    sys.exit(main())