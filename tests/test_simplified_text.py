#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试简化后的文字显示逻辑
"""

def test_text_display_logic():
    """测试文字显示逻辑"""
    print("测试简化后的文字显示逻辑")
    print("=" * 50)
    
    # 模拟不同宽度下的显示策略
    test_cases = [
        {"width": 50, "name": "CONTROL_REGISTER", "expected": "完整名称"},
        {"width": 45, "name": "STATUS_REG", "expected": "完整名称"},
        {"width": 40, "name": "CONFIG", "expected": "完整名称（强制显示）"},
        {"width": 35, "name": "DATA_BUFFER_LONG_NAME", "expected": "缩写（前3字符）"},
        {"width": 30, "name": "TX_FIFO", "expected": "缩写（前3字符）"},
        {"width": 25, "name": "RX", "expected": "缩写（前3字符）"},
        {"width": 20, "name": "INT_EN", "expected": "超短缩写（前2字符）"},
        {"width": 15, "name": "CLK", "expected": "超短缩写（前2字符）"},
    ]
    
    print("宽度策略：")
    print("- 宽度 > 40px: 显示完整名称")
    print("- 宽度 20-40px: 显示缩写（前3字符 + ...）")
    print("- 宽度 < 20px: 显示超短缩写（前2字符 + .）")
    print()
    
    for case in test_cases:
        width = case["width"]
        name = case["name"]
        
        if width > 40:
            display = name
        elif width > 20:
            if len(name) > 3:
                display = name[:3] + "..."
            else:
                display = name
        else:
            if len(name) > 2:
                display = name[:2] + "."
            else:
                display = name
        
        print(f"宽度: {width:3d}px, 名称: {name:20s} -> 显示: {display}")
    
    print()
    print("简化后的优点：")
    print("1. 逻辑简单，易于理解")
    print("2. 左对齐显示，避免复杂的居中计算")
    print("3. 不尝试在矩形上方显示，避免布局混乱")
    print("4. 依赖左侧树视图显示完整名称，图形中只显示标识")
    
    print()
    print("测试完成！文字显示已简化为缩写方案。")

if __name__ == "__main__":
    test_text_display_logic()