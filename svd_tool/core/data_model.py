# svd_tool/core/data_model.py
import copy
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
    xml_start_line: int = 0  # XML起始行号
    xml_end_line: int = 0  # XML结束行号
    enumerated_values: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        # 只移除None值，保留空字符串（空字符串是有意义的默认值）
        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> 'Field':
        """从字典创建 Field 实例"""
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            display_name=data.get("display_name", ""),
            bit_offset=int(data.get("bit_offset", 0)),
            bit_width=int(data.get("bit_width", 1)),
            access=data.get("access"),
            reset_value=data.get("reset_value", "0x0"),
            xml_start_line=int(data.get("xml_start_line", 0)),
            xml_end_line=int(data.get("xml_end_line", 0)),
            enumerated_values=data.get("enumerated_values", []),
        )

    def __deepcopy__(self, memo):
        """快速深拷贝（避免copy.deepcopy的通用开销）"""
        return Field(
            name=self.name,
            description=self.description,
            display_name=self.display_name,
            bit_offset=self.bit_offset,
            bit_width=self.bit_width,
            access=self.access,
            reset_value=self.reset_value,
            xml_start_line=self.xml_start_line,
            xml_end_line=self.xml_end_line,
            enumerated_values=[dict(ev) for ev in self.enumerated_values],
        )


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
    derived_from: str = ""  # derivedFrom 属性（寄存器级继承）
    xml_start_line: int = 0  # XML起始行号
    xml_end_line: int = 0  # XML结束行号


    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['fields'] = {name: field.to_dict() for name, field in self.fields.items()}
        # 只移除None值，保留空字符串（空字符串是有意义的默认值）
        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> 'Register':
        """从字典创建 Register 实例"""
        fields_data = data.get("fields", {})
        fields = {}
        if isinstance(fields_data, dict):
            for fname, fdata in fields_data.items():
                if isinstance(fdata, dict):
                    fields[fname] = Field.from_dict(fdata)
        elif isinstance(fields_data, list):
            for fdata in fields_data:
                if isinstance(fdata, dict):
                    f = Field.from_dict(fdata)
                    fields[f.name] = f
        return cls(
            name=data.get("name", ""),
            offset=data.get("offset", "0x0"),
            description=data.get("description", ""),
            display_name=data.get("display_name", ""),
            size=data.get("size", "0x20"),
            access=data.get("access"),
            reset_value=data.get("reset_value", "0x00000000"),
            reset_mask=data.get("reset_mask", "0xFFFFFFFF"),
            fields=fields,
            derived_from=data.get("derived_from", ""),
        )

    def __deepcopy__(self, memo):
        """快速深拷贝"""
        return Register(
            name=self.name,
            offset=self.offset,
            description=self.description,
            display_name=self.display_name,
            size=self.size,
            access=self.access,
            reset_value=self.reset_value,
            reset_mask=self.reset_mask,
            fields={k: copy.deepcopy(v, memo) for k, v in self.fields.items()},
            derived_from=self.derived_from,
            xml_start_line=self.xml_start_line,
            xml_end_line=self.xml_end_line,
        )


@dataclass
class Cluster:
    """寄存器簇数据模型（CMSIS-SVD cluster 元素）"""
    name: str
    description: str = ""
    display_name: str = ""
    address_offset: str = "0x0"  # 相对外设基地址的偏移
    size: str = "0x20"
    access: Optional[str] = None
    reset_value: str = "0x00000000"
    reset_mask: str = "0xFFFFFFFF"
    registers: Dict[str, 'Register'] = field(default_factory=dict)
    clusters: Dict[str, 'Cluster'] = field(default_factory=dict)  # 支持嵌套簇
    # dim 信息（用于寄存器簇数组）
    dim: Optional[int] = None
    dim_increment: str = "0x0"
    dim_index: List[str] = field(default_factory=list)
    derived_from: str = ""
    xml_start_line: int = 0
    xml_end_line: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['registers'] = {name: reg.to_dict() for name, reg in self.registers.items()}
        data['clusters'] = {name: cl.to_dict() for name, cl in self.clusters.items()}
        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> 'Cluster':
        """从字典创建 Cluster 实例"""
        regs_data = data.get("registers", {})
        registers = {}
        if isinstance(regs_data, dict):
            for rname, rdata in regs_data.items():
                if isinstance(rdata, dict):
                    registers[rname] = Register.from_dict(rdata)
        clusters_data = data.get("clusters", {})
        clusters = {}
        if isinstance(clusters_data, dict):
            for cname, cdata in clusters_data.items():
                if isinstance(cdata, dict):
                    clusters[cname] = Cluster.from_dict(cdata)
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            display_name=data.get("display_name", ""),
            address_offset=data.get("address_offset", "0x0"),
            size=data.get("size", "0x20"),
            access=data.get("access"),
            reset_value=data.get("reset_value", "0x00000000"),
            reset_mask=data.get("reset_mask", "0xFFFFFFFF"),
            registers=registers,
            clusters=clusters,
            dim=data.get("dim"),
            dim_increment=data.get("dim_increment", "0x0"),
            dim_index=data.get("dim_index", []),
            derived_from=data.get("derived_from", ""),
        )

    def __deepcopy__(self, memo):
        """快速深拷贝"""
        return Cluster(
            name=self.name,
            description=self.description,
            display_name=self.display_name,
            address_offset=self.address_offset,
            size=self.size,
            access=self.access,
            reset_value=self.reset_value,
            reset_mask=self.reset_mask,
            registers={k: copy.deepcopy(v, memo) for k, v in self.registers.items()},
            clusters={k: copy.deepcopy(v, memo) for k, v in self.clusters.items()},
            dim=self.dim,
            dim_increment=self.dim_increment,
            dim_index=list(self.dim_index),
            derived_from=self.derived_from,
            xml_start_line=self.xml_start_line,
            xml_end_line=self.xml_end_line,
        )

    def all_registers(self) -> Dict[str, 'Register']:
        """获取所有寄存器（包括子簇中的）"""
        result = dict(self.registers)
        for cl in self.clusters.values():
            result.update(cl.all_registers())
        return result


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
    clusters: Dict[str, Cluster] = field(default_factory=dict)  # 寄存器簇
    interrupts: List[Dict[str, Any]] = field(default_factory=list)
    xml_start_line: int = 0  # XML起始行号
    xml_end_line: int = 0  # XML结束行号
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['registers'] = {name: reg.to_dict() for name, reg in self.registers.items()}
        data['clusters'] = {name: cl.to_dict() for name, cl in self.clusters.items()}
        # 只移除None值，保留空字符串（空字符串是有意义的默认值）
        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> 'Peripheral':
        """从字典创建 Peripheral 实例"""
        regs_data = data.get("registers", {})
        registers = {}
        if isinstance(regs_data, dict):
            for rname, rdata in regs_data.items():
                if isinstance(rdata, dict):
                    registers[rname] = Register.from_dict(rdata)
        elif isinstance(regs_data, list):
            for rdata in regs_data:
                if isinstance(rdata, dict):
                    r = Register.from_dict(rdata)
                    registers[r.name] = r
        clusters_data = data.get("clusters", {})
        clusters = {}
        if isinstance(clusters_data, dict):
            for cname, cdata in clusters_data.items():
                if isinstance(cdata, dict):
                    clusters[cname] = Cluster.from_dict(cdata)
        default_addr_block = {"offset": "0x0", "size": "0x14", "usage": "registers"}
        addr_block = data.get("address_block", default_addr_block) or default_addr_block
        return cls(
            name=data.get("name", ""),
            base_address=data.get("base_address", "0x0"),
            description=data.get("description", ""),
            display_name=data.get("display_name", ""),
            group_name=data.get("group_name", ""),
            derived_from=data.get("derived_from", ""),
            address_block=addr_block,
            registers=registers,
            clusters=clusters,
            interrupts=data.get("interrupts", []),
        )

    def __deepcopy__(self, memo):
        """快速深拷贝"""
        new_addr_block = dict(self.address_block) if self.address_block else {"offset": "0x0", "size": "0x14", "usage": "registers"}
        return Peripheral(
            name=self.name,
            base_address=self.base_address,
            description=self.description,
            display_name=self.display_name,
            group_name=self.group_name,
            derived_from=self.derived_from,
            address_block=new_addr_block,
            registers={k: copy.deepcopy(v, memo) for k, v in self.registers.items()},
            clusters={k: copy.deepcopy(v, memo) for k, v in self.clusters.items()},
            interrupts=[dict(irq) for irq in self.interrupts],
            xml_start_line=self.xml_start_line,
            xml_end_line=self.xml_end_line,
        )

    def all_registers(self) -> Dict[str, Register]:
        """获取所有寄存器（包括簇中的）"""
        result = dict(self.registers)
        for cl in self.clusters.values():
            result.update(cl.all_registers())
        return result


@dataclass
class Interrupt:
    """中断数据模型"""
    name: str
    value: int
    description: str = ""
    peripheral: str = ""  # 保留兼容性，指向第一个关联外设
    peripherals: List[str] = field(default_factory=list)  # 支持多外设共用中断

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        # 只移除None值，保留空字符串（空字符串是有意义的默认值）
        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> 'Interrupt':
        """从字典创建 Interrupt 实例"""
        return cls(
            name=data.get("name", ""),
            value=int(data.get("value", 0)),
            description=data.get("description", ""),
            peripheral=data.get("peripheral", ""),
            peripherals=data.get("peripherals", []),
        )

    def __deepcopy__(self, memo):
        """快速深拷贝"""
        return Interrupt(
            name=self.name,
            value=self.value,
            description=self.description,
            peripheral=self.peripheral,
            peripherals=list(self.peripherals),
        )


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

    @classmethod
    def from_dict(cls, data: dict) -> 'CPUInfo':
        """从字典创建 CPUInfo 实例"""
        return cls(
            name=data.get("name", "CM0+"),
            revision=data.get("revision", "r0p1"),
            endian=data.get("endian", "little"),
            mpu_present=bool(data.get("mpu_present", True)),
            fpu_present=bool(data.get("fpu_present", False)),
            nvic_prio_bits=int(data.get("nvic_prio_bits", 4)),
            vendor_systick_config=bool(data.get("vendor_systick_config", False)),
        )

    def __deepcopy__(self, memo):
        """快速深拷贝"""
        return CPUInfo(
            name=self.name,
            revision=self.revision,
            endian=self.endian,
            mpu_present=self.mpu_present,
            fpu_present=self.fpu_present,
            nvic_prio_bits=self.nvic_prio_bits,
            vendor_systick_config=self.vendor_systick_config,
        )


@dataclass
class DeviceInfo:
    """设备信息模型"""
    name: str = ""
    version: str = "1.0"
    description: str = ""
    vendor: str = ""  # 厂商字段，从SVD文件或用户新建向导中填充
    copyright: str = ""  # 版权字段
    author: str = ""  # 作者字段
    license: str = ""  # 许可证字段
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

    @classmethod
    def from_dict(cls, data: dict) -> 'DeviceInfo':
        """从字典创建 DeviceInfo 实例（完整反序列化）"""
        cpu = CPUInfo.from_dict(data.get("cpu", {}))
        # 解析外设
        peripherals = {}
        periph_data = data.get("peripherals", {})
        if isinstance(periph_data, dict):
            for pname, pdata in periph_data.items():
                if isinstance(pdata, dict):
                    peripherals[pname] = Peripheral.from_dict(pdata)
        elif isinstance(periph_data, list):
            for pdata in periph_data:
                if isinstance(pdata, dict):
                    p = Peripheral.from_dict(pdata)
                    peripherals[p.name] = p
        # 解析中断
        interrupts = {}
        irq_data = data.get("interrupts", {})
        if isinstance(irq_data, dict):
            for iname, idata in irq_data.items():
                if isinstance(idata, dict):
                    interrupts[iname] = Interrupt.from_dict(idata)
        elif isinstance(irq_data, list):
            for idata in irq_data:
                if isinstance(idata, dict):
                    irq = Interrupt.from_dict(idata)
                    interrupts[irq.name] = irq
        return cls(
            name=data.get("name", ""),
            version=data.get("version", "1.0"),
            description=data.get("description", ""),
            vendor=data.get("vendor", ""),
            copyright=data.get("copyright", ""),
            author=data.get("author", ""),
            license=data.get("license", ""),
            cpu=cpu,
            address_unit_bits=int(data.get("address_unit_bits", 8)),
            width=int(data.get("width", 32)),
            size=data.get("size", "0x20"),
            reset_value=data.get("reset_value", "0x0"),
            reset_mask=data.get("reset_mask", "0xFFFFFFFF"),
            peripherals=peripherals,
            interrupts=interrupts,
            svd_version=data.get("svd_version", "1.3"),
        )