#!/usr/bin/env python3
"""
分析main_window.py的结构，验证重构假设
"""
import ast
import sys
from pathlib import Path

def analyze_main_window(file_path):
    """分析main_window.py的结构"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        print(f"语法错误: {e}")
        return
    
    # 统计信息
    total_lines = len(content.split('\n'))
    print(f"文件总行数: {total_lines}")
    
    # 查找MainWindow类
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'MainWindow':
            print(f"\n找到MainWindow类:")
            print(f"  类起始行: {node.lineno}")
            print(f"  类方法数量: {len([n for n in node.body if isinstance(n, ast.FunctionDef)])}")
            
            # 统计内部类
            inner_classes = [n for n in node.body if isinstance(n, ast.ClassDef)]
            print(f"  内部类数量: {len(inner_classes)}")
            for cls in inner_classes:
                print(f"    - {cls.name} (行 {cls.lineno})")
            
            # 统计方法行数
            methods = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    method_name = item.name
                    method_lines = item.end_lineno - item.lineno + 1 if hasattr(item, 'end_lineno') else '未知'
                    methods.append((method_name, method_lines))
            
            # 按行数排序
            methods.sort(key=lambda x: x[1] if isinstance(x[1], int) else 0, reverse=True)
            print(f"\n  前10个最长的方法:")
            for i, (name, lines) in enumerate(methods[:10]):
                print(f"    {i+1}. {name}: {lines} 行")
            
            # 统计代码行数分布
            code_lines = sum(1 for line in content.split('\n') if line.strip() and not line.strip().startswith('#'))
            comment_lines = sum(1 for line in content.split('\n') if line.strip().startswith('#'))
            blank_lines = sum(1 for line in content.split('\n') if not line.strip())
            
            print(f"\n  代码统计:")
            print(f"    代码行: {code_lines}")
            print(f"    注释行: {comment_lines}")
            print(f"    空行: {blank_lines}")
            
            # 识别功能区域
            print(f"\n  功能区域识别:")
            regions = {}
            current_region = "其他"
            for line in content.split('\n'):
                if '# =====================' in line:
                    current_region = line.strip('# = ')
                    regions[current_region] = regions.get(current_region, 0) + 1
                elif line.strip().startswith('def ') and current_region != "其他":
                    regions[current_region] = regions.get(current_region, 0) + 1
            
            for region, count in regions.items():
                print(f"    {region}: {count} 个方法")

if __name__ == "__main__":
    file_path = Path("svd_tool/ui/main_window.py")
    if file_path.exists():
        analyze_main_window(file_path)
    else:
        print(f"文件不存在: {file_path}")