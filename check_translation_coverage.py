#!/usr/bin/env python3
"""
翻译覆盖度检查脚本
检查代码中使用的翻译键是否在翻译文件中存在
"""
import os
import re
import json
from pathlib import Path
from typing import Set, Dict, Tuple

def extract_translation_keys_from_code(code_dir: str) -> Set[str]:
    """从代码中提取所有翻译键"""
    translation_keys = set()
    
    # 翻译键的有效前缀
    valid_prefixes = [
        'menu.', 'button.', 'label.', 'msg.', 'error.',
        'status.', 'tooltip.', 'placeholder.', 'value.',
        'license.', 'access.', 'unit.', 'preview_mode.',
        'search_type.', 'load_mode.', 'type.', 'cmd.',
        'warning.', 'tab.', 'message.', 'search.'
    ]
    
    # 构建正则表达式模式 - 匹配 t("key") 或 t('key')
    pattern = r't\(["\']([a-zA-Z_][a-zA-Z0-9_.]*?)["\']'
    
    # 遍历所有Python文件
    for root, dirs, files in os.walk(code_dir):
        # 跳过__pycache__和测试目录
        dirs[:] = [d for d in dirs if d not in ['__pycache__', 'tests', 'gui_tests', 'unit_tests', 'integration_tests']]
        
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 匹配 t("key") 或 t('key') 模式
                    matches = re.findall(pattern, content)
                    # 过滤出有效前缀的键
                    for match in matches:
                        for prefix in valid_prefixes:
                            if match.startswith(prefix):
                                translation_keys.add(match)
                                break
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
    
    return translation_keys

def load_translation_file(file_path: str) -> Dict[str, str]:
    """加载翻译文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def check_coverage(code_keys: Set[str], translation_file: str) -> Tuple[Set[str], Set[str]]:
    """检查翻译覆盖度"""
    translations = load_translation_file(translation_file)
    translation_keys = set(translations.keys())
    
    # 找出代码中使用但翻译文件中不存在的键
    missing_keys = code_keys - translation_keys
    
    # 找出翻译文件中存在但代码中未使用的键
    unused_keys = translation_keys - code_keys
    
    return missing_keys, unused_keys

def compare_translations(zh_file: str, en_file: str) -> Tuple[Set[str], Set[str]]:
    """比较中英文翻译文件"""
    zh_translations = load_translation_file(zh_file)
    en_translations = load_translation_file(en_file)
    
    zh_keys = set(zh_translations.keys())
    en_keys = set(en_translations.keys())
    
    # 中文有但英文没有的键
    zh_only = zh_keys - en_keys
    
    # 英文有但中文没有的键
    en_only = en_keys - zh_keys
    
    return zh_only, en_only

def main():
    """主函数"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    code_dir = os.path.join(script_dir, 'svd_tool')
    i18n_dir = os.path.join(script_dir, 'svd_tool', 'i18n')
    
    zh_file = os.path.join(i18n_dir, 'zh_CN.json')
    en_file = os.path.join(i18n_dir, 'en_US.json')
    
    print("=" * 80)
    print("翻译覆盖度检查")
    print("=" * 80)
    
    # 1. 提取代码中的翻译键
    print("\n1. 扫描代码中的翻译键...")
    code_keys = extract_translation_keys_from_code(code_dir)
    print(f"   找到 {len(code_keys)} 个翻译键")
    
    # 2. 检查中文翻译覆盖度
    print("\n2. 检查中文翻译覆盖度...")
    zh_missing, zh_unused = check_coverage(code_keys, zh_file)
    print(f"   中文翻译文件包含 {len(load_translation_file(zh_file))} 个键")
    print(f"   缺失的翻译键: {len(zh_missing)} 个")
    if zh_missing:
        print("   缺失的键:")
        for key in sorted(zh_missing):
            print(f"     - {key}")
    print(f"   未使用的翻译键: {len(zh_unused)} 个")
    if zh_unused:
        print("   未使用的键:")
        for key in sorted(zh_unused):
            print(f"     - {key}")
    
    # 3. 检查英文翻译覆盖度
    print("\n3. 检查英文翻译覆盖度...")
    en_missing, en_unused = check_coverage(code_keys, en_file)
    print(f"   英文翻译文件包含 {len(load_translation_file(en_file))} 个键")
    print(f"   缺失的翻译键: {len(en_missing)} 个")
    if en_missing:
        print("   缺失的键:")
        for key in sorted(en_missing):
            print(f"     - {key}")
    print(f"   未使用的翻译键: {len(en_unused)} 个")
    if en_unused:
        print("   未使用的键:")
        for key in sorted(en_unused):
            print(f"     - {key}")
    
    # 4. 比较中英文翻译文件
    print("\n4. 比较中英文翻译文件...")
    zh_only, en_only = compare_translations(zh_file, en_file)
    print(f"   中文独有的键: {len(zh_only)} 个")
    if zh_only:
        print("   中文独有的键:")
        for key in sorted(zh_only):
            print(f"     - {key}")
    print(f"   英文独有的键: {len(en_only)} 个")
    if en_only:
        print("   英文独有的键:")
        for key in sorted(en_only):
            print(f"     - {key}")
    
    # 5. 总结
    print("\n" + "=" * 80)
    print("总结")
    print("=" * 80)
    zh_coverage = len(code_keys - set(load_translation_file(zh_file).keys()))
    en_coverage = len(code_keys - set(load_translation_file(en_file).keys()))
    print(f"代码中使用的翻译键总数: {len(code_keys)}")
    print(f"中文翻译缺失: {zh_coverage} 个")
    print(f"英文翻译缺失: {en_coverage} 个")
    print(f"中英文不一致: {len(zh_only) + len(en_only)} 个")
    
    if zh_missing or en_missing or zh_only or en_only:
        print("\n⚠️  发现问题，需要补充翻译！")
        return 1
    else:
        print("\n✅ 所有翻译键都已覆盖！")
        return 0

if __name__ == '__main__':
    exit(main())
