# svd_tool/core/data_model.py
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from enum import Enum


class AccessType(Enum):
    READ_WRITE = "read-write"
    READ_ONLY = "read-only"
    WRITE_ONLY = "write-only"
    WRITE_ONCE = "writeOnce"
    READ_WRITE_ONCE = "read-writeOnce"


@dataclass
class Field:
    """位域数据模型"""
    name: str
    description: str = ""
    display_name: str = ""
    bit_offset: int = 0
    bit_width: int = 1
    access: Optional[str] = None
    reset_value: str = "0x0"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        # 移除空值
        return {k: v for k, v in data.items() if v is not None and v != ""}


@dataclass
class Register:
    """寄存器数据模型"""
    name: str
    offset: str
    description: str = ""
    display_name: str = ""
    size: str = "0x20"
    access: Optional[str] = None
    reset_value: str = "0x00000000"
    reset_mask: str = "0xFFFFFFFF"
    fields: Dict[str, Field] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['fields'] = {name: field.to_dict() for name, field in self.fields.items()}
        # 移除空值
        return {k: v for k, v in data.items() if v is not None and v != ""}


@dataclass
class Peripheral:
    """外设数据模型"""
    name: str
    base_address: str
    description: str = ""
    display_name: str = ""
    group_name: str = ""
    derived_from: str = ""
    address_block: Dict[str, str] = field(default_factory=lambda: {
        "offset": "0x0",
        "size": "0x14",
        "usage": "registers"
    })
    registers: Dict[str, Register] = field(default_factory=dict)
    interrupts: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['registers'] = {name: reg.to_dict() for name, reg in self.registers.items()}
        # 移除空值
        return {k: v for k, v in data.items() if v is not None and v != ""}


@dataclass
class Interrupt:
    """中断数据模型"""
    name: str
    value: int
    description: str = ""
    peripheral: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        # 移除空值
        return {k: v for k, v in data.items() if v is not None and v != ""}


@dataclass
class CPUInfo:
    """CPU信息模型"""
    name: str = "CM0+"
    revision: str = "r0p1"
    endian: str = "little"
    mpu_present: bool = True
    fpu_present: bool = False
    nvic_prio_bits: int = 4
    vendor_systick_config: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class DeviceInfo:
    """设备信息模型"""
    name: str = ""
    version: str = "1.0"
    description: str = ""
    vendor: str = "SinOneMicroelectronics"  # 新增厂商字段
    copyright: str = "Copyright (c) 2024 SinOneMicroelectronics."  # 新增版权字段
    author: str = "SVD Tool Team"  # 新增作者字段
    license: str = "Apache-2.0"  # 新增许可证字段
    cpu: CPUInfo = field(default_factory=CPUInfo)
    address_unit_bits: int = 8
    width: int = 32
    size: str = "0x20"
    reset_value: str = "0x0"
    reset_mask: str = "0xFFFFFFFF"
    peripherals: Dict[str, Peripheral] = field(default_factory=dict)
    interrupts: Dict[str, Interrupt] = field(default_factory=dict)
    svd_version: str = "1.3"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为完整字典"""
        data = asdict(self)
        data['cpu'] = self.cpu.to_dict()
        data['peripherals'] = {name: periph.to_dict() for name, periph in self.peripherals.items()}
        data['interrupts'] = {name: irq.to_dict() for name, irq in self.interrupts.items()}
        return data