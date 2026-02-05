# svd_tool/utils/helpers.py
"""
辅助函数模块
"""
import re
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET
from xml.dom import minidom
from typing import Union
from PyQt6.QtWidgets import QMessageBox


def show_message(parent, title: str, text: str, icon: str = 'info') -> None:
    """
    统一显示消息对话框。

    icon: 'info'|'warning'|'critical'|'about'
    """
    icon_map = {
        'info': QMessageBox.Icon.Information,
        'information': QMessageBox.Icon.Information,
        'warning': QMessageBox.Icon.Warning,
        'critical': QMessageBox.Icon.Critical,
    }

    if icon == 'about':
        QMessageBox.about(parent, title, text)
        return

    qicon = icon_map.get(icon, QMessageBox.Icon.Information)
    dlg = QMessageBox(parent)
    dlg.setWindowTitle(title)
    dlg.setText(text)
    dlg.setIcon(qicon)
    dlg.exec()


def ask_question(parent, title: str, text: str, buttons: Union[QMessageBox.StandardButton, int] = QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, default: Union[QMessageBox.StandardButton, None] = None):
    """
    统一显示带选项的询问对话框，返回用户选择的 StandardButton。
    """
    reply = QMessageBox.question(parent, title, text, buttons, default if default is not None else QMessageBox.StandardButton.No)
    return reply


def pretty_xml(xml_string: str, indent: str = "  ") -> str:
    """
    美化XML字符串
    
    Args:
        xml_string: XML字符串
        indent: 缩进字符
    
    Returns:
        美化后的XML字符串
    """
    try:
        # 解析XML
        dom = minidom.parseString(xml_string)
        
        # 美化输出
        pretty_xml_str = dom.toprettyxml(indent=indent)
        
        # 移除多余的空行
        lines = pretty_xml_str.split('\n')
        clean_lines = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped:
                clean_lines.append(line)
            elif i > 0 and i < len(lines) - 1:
                # 保留适当的空行
                prev_line = lines[i-1].strip()
                next_line = lines[i+1].strip()
                if prev_line and next_line:
                    clean_lines.append(line)
        
        return '\n'.join(clean_lines)
    
    except Exception as e:
        # 如果美化失败，返回原始字符串
        print(f"美化XML失败: {e}")
        return xml_string


def format_hex(value: Any, prefix: str = "0x") -> str:
    """
    格式化十六进制值
    
    Args:
        value: 要格式化的值
        prefix: 前缀
    
    Returns:
        格式化的十六进制字符串
    """
    if isinstance(value, str):
        # 如果已经是十六进制字符串
        if value.startswith(("0x", "0X")):
            return value
        try:
            # 尝试转换为整数
            int_value = int(value)
            return f"{prefix}{int_value:X}"
        except (ValueError, TypeError):
            return value
    
    elif isinstance(value, int):
        return f"{prefix}{value:X}"
    
    else:
        try:
            int_value = int(value)
            return f"{prefix}{int_value:X}"
        except (ValueError, TypeError):
            return str(value)


def parse_hex(value: str) -> int:
    """
    解析十六进制字符串
    
    Args:
        value: 十六进制字符串
    
    Returns:
        整数值
    """
    if not value:
        return 0
    
    # 移除空白字符
    value = value.strip()
    
    # 移除可能的0x前缀
    if value.startswith(("0x", "0X")):
        value = value[2:]
    
    try:
        return int(value, 16)
    except ValueError:
        # 如果不是十六进制，尝试十进制
        try:
            return int(value)
        except ValueError:
            return 0


def validate_c_name(name: str) -> bool:
    """
    验证C语言标识符名称
    
    Args:
        name: 要验证的名称
    
    Returns:
        是否有效
    """
    if not name:
        return False
    
    # C语言标识符规则：字母或下划线开头，只能包含字母、数字、下划线
    pattern = r'^[a-zA-Z_][a-zA-Z0-9_]*$'
    return bool(re.match(pattern, name))


def sanitize_description(desc: str) -> str:
    """
    清理描述文本
    
    Args:
        desc: 原始描述
    
    Returns:
        清理后的描述
    """
    if not desc:
        return ""
    
    # 移除多余的空白字符
    desc = re.sub(r'\s+', ' ', desc)
    
    # 移除特殊字符（保留基本标点）
    desc = re.sub(r'[^\w\s.,;:!?()\-/\'"]', '', desc)
    
    return desc.strip()


def deep_merge_dicts(dict1: Dict, dict2: Dict) -> Dict:
    """
    深度合并两个字典
    
    Args:
        dict1: 第一个字典
        dict2: 第二个字典
    
    Returns:
        合并后的字典
    """
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    
    return result


def find_item_by_name(items: List[Dict], name: str, key: str = "name") -> Optional[Dict]:
    """
    根据名称查找项目
    
    Args:
        items: 项目列表
        name: 要查找的名称
        key: 查找的键
    
    Returns:
        找到的项目或None
    """
    for item in items:
        if item.get(key) == name:
            return item
    return None


def calculate_bitmask(offset: int, width: int) -> int:
    """
    计算位掩码
    
    Args:
        offset: 起始位
        width: 位宽
    
    Returns:
        位掩码
    """
    if width == 0:
        return 0
    
    mask = (1 << width) - 1
    return mask << offset


def format_bit_range(offset: int, width: int) -> str:
    """
    格式化位范围
    
    Args:
        offset: 起始位
        width: 位宽
    
    Returns:
        格式化后的位范围字符串
    """
    if width == 1:
        return f"[{offset}]"
    else:
        return f"[{offset + width - 1}:{offset}]"


def get_unique_name(base_name: str, existing_names: List[str]) -> str:
    """
    获取唯一的名称
    
    Args:
        base_name: 基础名称
        existing_names: 已存在的名称列表
    
    Returns:
        唯一的名称
    """
    if base_name not in existing_names:
        return base_name
    
    # 添加数字后缀
    counter = 1
    while True:
        new_name = f"{base_name}_{counter}"
        if new_name not in existing_names:
            return new_name
        counter += 1