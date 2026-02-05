#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查main_window_refactored.py中是否存在update_data_model_from_tree方法"""

import re

with open('svd_tool/ui/main_window_refactored.py', 'r', encoding='utf-8') as f:
    content = f.read()
    
# 搜索方法定义
pattern = r'def\s+update_data_model_from_tree\s*\('
matches = re.findall(pattern, content)

if matches:
    print(f"找到方法: {matches[0]}")
else:
    print("未找到update_data_model_from_tree方法")
    
# 搜索方法调用
pattern2 = r'\.update_data_model_from_tree\s*\('
matches2 = re.findall(pattern2, content)
if matches2:
    print(f"找到方法调用: {len(matches2)}处")
    for i, match in enumerate(matches2):
        # 获取上下文
        start = max(0, content.find(match) - 50)
        end = min(len(content), content.find(match) + 50)
        print(f"  调用{i+1}: ...{content[start:end]}...")