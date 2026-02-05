# svd_tool/core/validators.py
import re
from typing import Union, Optional, Tuple
from .constants import ACCESS_OPTIONS


class ValidationError(Exception):
    """验证错误异常"""
    pass


class Validator:
    """验证器基类"""
    
    @staticmethod
    def validate_hex(value: str, field_name: str = "值") -> str:
        """验证十六进制值"""
        if not value:
            raise ValidationError(f"{field_name}不能为空")
        
        value = value.strip()
        # 移除可能的0x前缀后再检查
        clean_value = value[2:] if value.startswith("0x") else value
        
        if not clean_value:
            raise ValidationError(f"{field_name}不能为空")
        
        try:
            int(clean_value, 16)
        except ValueError:
            raise ValidationError(f"{field_name}必须是有效的十六进制数")
        
        return value
    
    @staticmethod
    def validate_decimal(value: str, field_name: str = "值") -> int:
        """验证十进制值"""
        if not value:
            raise ValidationError(f"{field_name}不能为空")
        
        try:
            return int(value)
        except ValueError:
            raise ValidationError(f"{field_name}必须是有效的数字")
    
    @staticmethod
    def validate_name(name: str, field_name: str = "名称") -> str:
        """验证名称"""
        if not name or not name.strip():
            raise ValidationError(f"{field_name}不能为空")
        
        name = name.strip()
        # 检查是否包含非法字符
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
            raise ValidationError(f"{field_name}只能包含字母、数字和下划线，且不能以数字开头")
        
        return name
    
    @staticmethod
    def validate_access(access: str) -> Optional[str]:
        """验证访问权限"""
        if not access or access == "无":
            return None
        
        if access not in [opt for opt in ACCESS_OPTIONS if opt != "无"]:
            raise ValidationError(f"访问权限必须是: {', '.join(ACCESS_OPTIONS[1:])}")
        
        return access
    
    @staticmethod
    def validate_bit_range(offset: int, width: int, max_bits: int = 32) -> Tuple[int, int]:
        """验证位域范围"""
        if offset < 0 or offset >= max_bits:
            raise ValidationError(f"起始位必须在0-{max_bits-1}之间")
        
        if width < 1 or width > max_bits:
            raise ValidationError(f"位宽必须在1-{max_bits}之间")
        
        if offset + width > max_bits:
            raise ValidationError(f"位域范围{offset}-{offset+width-1}超出{max_bits}位寄存器")
        
        return offset, width
    
    @staticmethod
    def validate_irq_number(irq_num: int) -> int:
        """验证中断号"""
        if irq_num < 0 or irq_num > 255:
            raise ValidationError("中断号必须在0-255之间")
        return irq_num
    
    @classmethod
    def validate_peripheral(cls, data: dict) -> dict:
        """验证外设数据"""
        validated = {}
        
        # 验证名称
        validated['name'] = cls.validate_name(data.get('name', ''), "外设名")
        
        # 验证基地址
        validated['base_address'] = cls.validate_hex(
            data.get('base_address', ''), "基地址"
        )
        
        # 验证描述
        validated['description'] = data.get('description', '').strip() or validated['name']
        
        # 验证显示名称
        validated['display_name'] = data.get('display_name', '').strip()
        
        # 验证组名
        validated['group_name'] = data.get('group_name', '').strip() or validated['name']
        
        # 验证继承属性
        validated['derived_from'] = data.get('derived_from', '').strip()
        
        # 验证地址块
        address_block = data.get('address_block', {})
        validated['address_block'] = {
            'offset': cls.validate_hex(
                address_block.get('offset', '0x0'), "地址块偏移"
            ),
            'size': cls.validate_hex(
                address_block.get('size', '0x14'), "地址块大小"
            ),
            'usage': address_block.get('usage', 'registers')
        }
        
        return validated
    
    @classmethod
    def validate_register(cls, data: dict) -> dict:
        """验证寄存器数据"""
        validated = {}
        
        # 验证名称
        validated['name'] = cls.validate_name(data.get('name', ''), "寄存器名")
        
        # 验证偏移地址
        validated['offset'] = cls.validate_hex(
            data.get('offset', ''), "偏移地址"
        )
        
        # 验证描述
        validated['description'] = data.get('description', '').strip() or validated['name']
        
        # 验证显示名称
        validated['display_name'] = data.get('display_name', '').strip()
        
        # 验证访问权限
        validated['access'] = cls.validate_access(data.get('access', ''))
        
        # 验证复位值
        validated['reset_value'] = cls.validate_hex(
            data.get('reset_value', '0x00000000'), "复位值"
        )
        
        # 验证大小
        validated['size'] = cls.validate_hex(
            data.get('size', '0x20'), "寄存器大小"
        )
        
        return validated
    
    @classmethod
    def validate_field(cls, data: dict) -> dict:
        """验证位域数据"""
        validated = {}
        
        # 验证名称
        validated['name'] = cls.validate_name(data.get('name', ''), "位域名")
        
        # 验证起始位和位宽
        offset = cls.validate_decimal(str(data.get('offset', 0)), "起始位")
        width = cls.validate_decimal(str(data.get('width', 1)), "位宽")
        validated['offset'], validated['width'] = cls.validate_bit_range(offset, width)
        
        # 验证描述
        validated['description'] = data.get('description', '').strip() or validated['name']
        
        # 验证显示名称
        validated['display_name'] = data.get('display_name', '').strip()
        
        # 验证访问权限
        validated['access'] = cls.validate_access(data.get('access', ''))
        
        # 验证复位值
        validated['reset_value'] = cls.validate_hex(
            data.get('reset_value', '0x0'), "位域复位值"
        )
        
        return validated
    
    @classmethod
    def validate_interrupt(cls, data: dict) -> dict:
        """验证中断数据"""
        validated = {}
        
        # 验证名称
        validated['name'] = cls.validate_name(data.get('name', ''), "中断名")
        
        # 验证中断号
        validated['value'] = cls.validate_irq_number(data.get('value', 0))
        
        # 验证描述
        validated['description'] = data.get('description', '').strip()
        
        # 验证关联外设
        validated['peripheral'] = data.get('peripheral', '').strip()
        if not validated['peripheral']:
            raise ValidationError("关联外设不能为空")
        
        return validated