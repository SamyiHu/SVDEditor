# svd_tool/core/validators.py
import re
from typing import Union, Optional, Tuple
from .constants import ACCESS_OPTIONS
from ..i18n.i18n import t


class ValidationError(Exception):
    """验证错误异常"""
    pass


class Validator:
    """验证器基类"""
    
    @staticmethod
    def validate_hex(value: str, field_name: str = None) -> str:
        """验证十六进制值"""
        if field_name is None:
            field_name = t("validator.base_address")
        if not value:
            raise ValidationError(t("validator.not_empty", field=field_name))

        value = value.strip()
        # 移除可能的0x前缀后再检查
        clean_value = value[2:] if value.startswith("0x") else value

        if not clean_value:
            raise ValidationError(t("validator.not_empty", field=field_name))

        try:
            int(clean_value, 16)
        except ValueError:
            raise ValidationError(t("validator.invalid_hex", field=field_name))

        return value

    @staticmethod
    def validate_decimal(value: str, field_name: str = None) -> int:
        """验证十进制值"""
        if field_name is None:
            field_name = t("validator.bit_offset")
        if not value:
            raise ValidationError(t("validator.not_empty", field=field_name))

        try:
            return int(value)
        except ValueError:
            raise ValidationError(t("validator.invalid_number", field=field_name))

    @staticmethod
    def validate_name(name: str, field_name: str = None) -> str:
        """验证名称"""
        if field_name is None:
            field_name = t("validator.field_name")
        if not name or not name.strip():
            raise ValidationError(t("validator.not_empty", field=field_name))

        name = name.strip()
        # 检查是否包含非法字符
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
            raise ValidationError(t("validator.invalid_name", field=field_name))

        return name

    @staticmethod
    def validate_access(access: str) -> Optional[str]:
        """验证访问权限"""
        if not access or access == "none":
            return None

        if access not in [opt for opt in ACCESS_OPTIONS if opt != "none"]:
            raise ValidationError(t("validator.invalid_access", valid=", ".join(ACCESS_OPTIONS[1:])))

        return access

    @staticmethod
    def validate_bit_range(offset: int, width: int, max_bits: int = 32) -> Tuple[int, int]:
        """验证位域范围"""
        if offset < 0 or offset >= max_bits:
            raise ValidationError(t("validator.bit_offset_range", max=max_bits-1))

        if width < 1 or width > max_bits:
            raise ValidationError(t("validator.bit_width_range", max=max_bits))

        if offset + width > max_bits:
            raise ValidationError(t("validator.bit_range_overflow", offset=offset, end=offset+width-1, max=max_bits))

        return offset, width

    @staticmethod
    def validate_irq_number(irq_num: int) -> int:
        """验证中断号"""
        if irq_num < 0 or irq_num > 255:
            raise ValidationError(t("validator.irq_range"))
        return irq_num
    
    @classmethod
    def validate_peripheral(cls, data: dict) -> dict:
        """验证外设数据"""
        validated = {}
        
        # 验证名称
        validated['name'] = cls.validate_name(data.get('name', ''), t("validator.periph_name"))

        # 验证基地址
        validated['base_address'] = cls.validate_hex(
            data.get('base_address', ''), t("validator.base_address")
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
                address_block.get('offset', '0x0'), t("validator.offset_address")
            ),
            'size': cls.validate_hex(
                address_block.get('size', '0x14'), t("validator.reg_size")
            ),
            'usage': address_block.get('usage', 'registers')
        }
        
        return validated
    
    @classmethod
    def validate_register(cls, data: dict) -> dict:
        """验证寄存器数据"""
        validated = {}
        
        # 验证名称
        validated['name'] = cls.validate_name(data.get('name', ''), t("validator.reg_name"))

        # 验证偏移地址
        validated['offset'] = cls.validate_hex(
            data.get('offset', ''), t("validator.offset_address")
        )
        
        # 验证描述
        validated['description'] = data.get('description', '').strip() or validated['name']
        
        # 验证显示名称
        validated['display_name'] = data.get('display_name', '').strip()
        
        # 验证访问权限
        validated['access'] = cls.validate_access(data.get('access', ''))
        
        # 验证复位值
        validated['reset_value'] = cls.validate_hex(
            data.get('reset_value', '0x00000000'), t("validator.reset_value")
        )

        # 验证大小
        validated['size'] = cls.validate_hex(
            data.get('size', '0x20'), t("validator.reg_size")
        )
        
        return validated
    
    @classmethod
    def validate_field(cls, data: dict) -> dict:
        """验证位域数据"""
        validated = {}
        
        # 验证名称
        validated['name'] = cls.validate_name(data.get('name', ''), t("validator.field_name"))

        # 验证起始位和位宽
        offset = cls.validate_decimal(str(data.get('offset', 0)), t("validator.bit_offset"))
        width = cls.validate_decimal(str(data.get('width', 1)), t("validator.bit_width"))
        validated['offset'], validated['width'] = cls.validate_bit_range(offset, width)
        
        # 验证描述
        validated['description'] = data.get('description', '').strip() or validated['name']
        
        # 验证显示名称
        validated['display_name'] = data.get('display_name', '').strip()
        
        # 验证访问权限
        validated['access'] = cls.validate_access(data.get('access', ''))
        
        # 验证复位值
        validated['reset_value'] = cls.validate_hex(
            data.get('reset_value', '0x0'), t("validator.field_reset")
        )
        
        return validated
    
    @classmethod
    def validate_interrupt(cls, data: dict) -> dict:
        """验证中断数据"""
        validated = {}
        
        # 验证名称
        validated['name'] = cls.validate_name(data.get('name', ''), t("validator.irq_name"))
        
        # 验证中断号
        validated['value'] = cls.validate_irq_number(data.get('value', 0))
        
        # 验证描述
        validated['description'] = data.get('description', '').strip()
        
        # 验证关联外设
        validated['peripheral'] = data.get('peripheral', '').strip()
        if not validated['peripheral']:
            raise ValidationError(t("validator.assoc_periph_empty"))
        
        return validated