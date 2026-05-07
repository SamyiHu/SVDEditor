# svd_tool/core/validation_utils.py
"""
共享验证工具函数

供 AddressConflictDetector 和 SVDSchemaValidator 共用，
消除两个验证器之间的重复代码。
"""
from typing import Optional, Dict, List, Tuple

from .data_model import Peripheral, Register, Field


def parse_hex(value) -> Optional[int]:
    """
    解析十六进制或十进制数值字符串，失败返回 None

    SVD 文件中的数值可能是:
    - 十六进制: "0x20", "0x00000000"
    - 十进制: "32", "8"
    """
    if value is None:
        return None
    try:
        s = str(value).strip()
        if not s:
            return None
        s_lower = s.lower()
        if s_lower.startswith("0x"):
            return int(s_lower, 16)
        return int(s)
    except (ValueError, AttributeError):
        return None


def parse_int(value) -> Optional[int]:
    """解析整数值，失败返回 None"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def get_peripheral_address_range(periph: Peripheral) -> Tuple[Optional[int], Optional[int]]:
    """
    获取外设地址范围 (start, end)

    Args:
        periph: 外设数据模型

    Returns:
        (start, end) 元组，解析失败返回 (None, None)
    """
    base = parse_hex(periph.base_address)
    if base is None:
        return None, None
    block = periph.address_block
    block_offset = parse_hex(block.get('offset', '0x0')) or 0
    block_size = parse_hex(block.get('size', '0x0')) or 0
    start = base + block_offset
    end = start + block_size - 1 if block_size > 0 else start
    return start, end
