# svd_tool/core/address_conflict_detector.py
"""
地址冲突实时检测器
在编辑时实时后台检测外设地址重叠和寄存器偏移重复

功能：
1. 外设地址范围重叠检测
2. 寄存器偏移地址重复检测（同一外设内）
3. 位域重叠检测（同一寄存器内）
4. 中断号重复检测
5. 冲突定位信息（双击可跳转到对应元素）
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .data_model import DeviceInfo, Peripheral, Register, Field
from .validation_utils import parse_hex, get_peripheral_address_range

logger = logging.getLogger("AddressConflictDetector")


class ConflictType(Enum):
    """冲突类型"""
    PERIPHERAL_ADDRESS_OVERLAP = "peripheral_address_overlap"     # 外设地址重叠
    PERIPHERAL_BASE_DUPLICATE = "peripheral_base_duplicate"       # 外设基地址重复
    REGISTER_OFFSET_DUPLICATE = "register_offset_duplicate"       # 寄存器偏移重复
    REGISTER_ADDRESS_OVERLAP = "register_address_overlap"         # 寄存器地址重叠
    FIELD_BIT_OVERLAP = "field_bit_overlap"                       # 位域位重叠
    INTERRUPT_VALUE_DUPLICATE = "interrupt_value_duplicate"       # 中断号重复


class ConflictSeverity(Enum):
    """冲突严重程度"""
    ERROR = "error"       # 必须修复
    WARNING = "warning"   # 建议修复


@dataclass
class ConflictItem:
    """单条冲突信息"""
    conflict_type: ConflictType
    severity: ConflictSeverity
    message: str
    location: str = ""                            # 格式: "peripheral.register.field"
    peripheral: Optional[str] = None
    register: Optional[str] = None
    field: Optional[str] = None
    interrupt: Optional[str] = None
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_type": self.conflict_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "location": self.location,
            "peripheral": self.peripheral,
            "register": self.register,
            "field": self.field,
            "interrupt": self.interrupt,
            "detail": self.detail,
        }


class AddressConflictDetector:
    """
    地址冲突实时检测器
    
    在数据模型变更时自动运行，检测：
    - 外设地址范围重叠
    - 寄存器偏移地址重复
    - 位域位重叠
    - 中断号重复
    """

    def __init__(self):
        self.conflicts: List[ConflictItem] = []
        self._callbacks: List = []  # List[Callable[[List[ConflictItem]], None]]

    def register_callback(self, callback):
        """注册冲突更新回调"""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def unregister_callback(self, callback):
        """注销冲突更新回调"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _notify_conflicts_updated(self):
        """通知冲突列表更新"""
        for cb in self._callbacks:
            try:
                cb(self.conflicts)
            except Exception as e:
                logger.error(f"冲突回调执行失败: {e}")

    def detect_all(self, device: DeviceInfo) -> List[ConflictItem]:
        """
        执行全部冲突检测

        Args:
            device: 设备信息数据模型

        Returns:
            冲突列表
        """
        self.conflicts.clear()

        if not device:
            self._notify_conflicts_updated()
            return self.conflicts

        # 1. 外设地址重叠检测
        self._detect_peripheral_conflicts(device)

        # 2. 寄存器偏移重复检测
        for pname, periph in device.peripherals.items():
            self._detect_register_conflicts(pname, periph)

        # 3. 位域重叠检测
        for pname, periph in device.peripherals.items():
            for rname, reg in periph.registers.items():
                self._detect_field_conflicts(pname, rname, reg)

        # 4. 中断号重复检测
        self._detect_interrupt_conflicts(device)

        logger.info(f"冲突检测完成: 发现 {len(self.conflicts)} 个冲突")
        self._notify_conflicts_updated()
        return self.conflicts

    def detect_peripheral(self, device: DeviceInfo, peripheral_name: str) -> List[ConflictItem]:
        """
        仅检测与指定外设相关的冲突（增量检测）

        Args:
            device: 设备信息
            peripheral_name: 外设名称

        Returns:
            与该外设相关的冲突列表
        """
        # 先移除该外设相关的旧冲突
        self.conflicts = [
            c for c in self.conflicts
            if c.peripheral != peripheral_name
        ]

        periph = device.peripherals.get(peripheral_name)
        if not periph:
            self._notify_conflicts_updated()
            return self.conflicts

        # 检测该外设与其他外设的地址重叠
        self._detect_single_peripheral_address_conflict(device, peripheral_name, periph)

        # 检测该外设内的寄存器冲突
        self._detect_register_conflicts(peripheral_name, periph)

        # 检测位域冲突
        for rname, reg in periph.registers.items():
            self._detect_field_conflicts(peripheral_name, rname, reg)

        self._notify_conflicts_updated()
        return self.conflicts

    # ==================== 外设级冲突检测 ====================

    def _get_periph_range(self, periph: Peripheral) -> Tuple[Optional[int], Optional[int]]:
        """获取外设地址范围 (start, end)"""
        return get_peripheral_address_range(periph)

    def _detect_peripheral_conflicts(self, device: DeviceInfo):
        """检测所有外设地址重叠"""
        periph_ranges: List[Tuple[str, int, int]] = []

        for name, periph in device.peripherals.items():
            start, end = self._get_periph_range(periph)
            if start is not None and end is not None:
                periph_ranges.append((name, start, end))

        # 检查重叠
        for i in range(len(periph_ranges)):
            for j in range(i + 1, len(periph_ranges)):
                name_i, start_i, end_i = periph_ranges[i]
                name_j, start_j, end_j = periph_ranges[j]
                if start_i <= end_j and start_j <= end_i:
                    self.conflicts.append(ConflictItem(
                        conflict_type=ConflictType.PERIPHERAL_ADDRESS_OVERLAP,
                        severity=ConflictSeverity.ERROR,
                        message=f"外设 '{name_i}' 与 '{name_j}' 地址范围重叠",
                        location=f"peripheral.{name_i}",
                        peripheral=name_i,
                        detail=f"0x{start_i:08X}-0x{end_i:08X} 与 0x{start_j:08X}-0x{end_j:08X} 重叠",
                    ))

        # 检查基地址完全相同
        base_map: Dict[int, List[str]] = {}
        for name, periph in device.peripherals.items():
            base = parse_hex(periph.base_address)
            if base is not None:
                if base not in base_map:
                    base_map[base] = []
                base_map[base].append(name)

        for base, names in base_map.items():
            if len(names) > 1:
                self.conflicts.append(ConflictItem(
                    conflict_type=ConflictType.PERIPHERAL_BASE_DUPLICATE,
                    severity=ConflictSeverity.ERROR,
                    message=f"多个外设使用相同基地址 0x{base:08X}: {', '.join(names)}",
                    location=f"peripheral.{names[0]}",
                    peripheral=names[0],
                    detail=f"涉及外设: {', '.join(names)}",
                ))

    def _detect_single_peripheral_address_conflict(self, device: DeviceInfo,
                                                     pname: str, periph: Peripheral):
        """检测单个外设与其他外设的地址重叠"""
        start_p, end_p = self._get_periph_range(periph)
        if start_p is None:
            return

        for name, other in device.peripherals.items():
            if name == pname:
                continue
            start_o, end_o = self._get_periph_range(other)
            if start_o is None or end_o is None:
                continue

            if start_p <= end_o and start_o <= end_p:
                self.conflicts.append(ConflictItem(
                    conflict_type=ConflictType.PERIPHERAL_ADDRESS_OVERLAP,
                    severity=ConflictSeverity.ERROR,
                    message=f"外设 '{pname}' 与 '{name}' 地址范围重叠",
                    location=f"peripheral.{pname}",
                    peripheral=pname,
                    detail=f"0x{start_p:08X}-0x{end_p:08X} 与 0x{start_o:08X}-0x{end_o:08X} 重叠",
                ))

    # ==================== 寄存器级冲突检测 ====================

    def _detect_register_conflicts(self, periph_name: str, periph: Peripheral):
        """检测外设内寄存器偏移重复"""
        if not periph.registers:
            return

        offset_map: Dict[int, List[str]] = {}  # offset -> [reg_names]

        for rname, reg in periph.registers.items():
            offset = parse_hex(reg.offset)
            if offset is not None:
                if offset not in offset_map:
                    offset_map[offset] = []
                offset_map[offset].append(rname)

        for offset, reg_names in offset_map.items():
            if len(reg_names) > 1:
                self.conflicts.append(ConflictItem(
                    conflict_type=ConflictType.REGISTER_OFFSET_DUPLICATE,
                    severity=ConflictSeverity.ERROR,
                    message=f"外设 '{periph_name}' 中寄存器 {', '.join(reg_names)} 偏移相同 (0x{offset:04X})",
                    location=f"peripheral.{periph_name}.register.{reg_names[0]}",
                    peripheral=periph_name,
                    register=reg_names[0],
                    detail=f"偏移 0x{offset:04X} 被以下寄存器共用: {', '.join(reg_names)}",
                ))

    # ==================== 位域级冲突检测 ====================

    def _detect_field_conflicts(self, periph_name: str, reg_name: str, reg: Register):
        """检测寄存器内位域位重叠"""
        if not reg.fields:
            return

        bit_occupancy: Dict[int, str] = {}  # bit_position -> field_name

        for fname, fld in reg.fields.items():
            try:
                bit_offset = int(fld.bit_offset)
                bit_width = int(fld.bit_width)
            except (ValueError, TypeError):
                continue

            if bit_width < 1:
                continue

            for bit in range(bit_offset, bit_offset + bit_width):
                if bit in bit_occupancy:
                    other_name = bit_occupancy[bit]
                    self.conflicts.append(ConflictItem(
                        conflict_type=ConflictType.FIELD_BIT_OVERLAP,
                        severity=ConflictSeverity.ERROR,
                        message=f"位域 '{fname}' 与 '{other_name}' 在 bit {bit} 重叠"
                               f" ({periph_name}.{reg_name})",
                        location=f"peripheral.{periph_name}.register.{reg_name}.field.{fname}",
                        peripheral=periph_name,
                        register=reg_name,
                        field=fname,
                        detail=f"bit {bit_offset}:{bit_offset + bit_width - 1} 与 "
                               f"{other_name} 在 bit {bit} 处重叠",
                    ))
                    break  # 每对只报告一次
                bit_occupancy[bit] = fname

    # ==================== 中断冲突检测 ====================

    def _detect_interrupt_conflicts(self, device: DeviceInfo):
        """检测中断号重复"""
        if not device.interrupts:
            return

        irq_map: Dict[int, List[str]] = {}
        for iname, irq in device.interrupts.items():
            try:
                val = int(irq.value)
            except (ValueError, TypeError):
                continue
            if val not in irq_map:
                irq_map[val] = []
            irq_map[val].append(iname)

        for val, names in irq_map.items():
            if len(names) > 1:
                self.conflicts.append(ConflictItem(
                    conflict_type=ConflictType.INTERRUPT_VALUE_DUPLICATE,
                    severity=ConflictSeverity.ERROR,
                    message=f"中断号 {val} 被多个中断使用: {', '.join(names)}",
                    location=f"interrupt.{names[0]}",
                    interrupt=names[0],
                    detail=f"中断号 {val} 被以下中断共用: {', '.join(names)}",
                ))

    # ==================== 查询接口 ====================

    def get_error_count(self) -> int:
        """获取错误数"""
        return sum(1 for c in self.conflicts if c.severity == ConflictSeverity.ERROR)

    def get_warning_count(self) -> int:
        """获取警告数"""
        return sum(1 for c in self.conflicts if c.severity == ConflictSeverity.WARNING)

    def has_conflicts(self) -> bool:
        """是否存在冲突"""
        return len(self.conflicts) > 0

    def get_peripheral_conflicts(self, periph_name: str) -> List[ConflictItem]:
        """获取与指定外设相关的冲突"""
        return [c for c in self.conflicts if c.peripheral == periph_name]

    def get_register_conflicts(self, periph_name: str, reg_name: str) -> List[ConflictItem]:
        """获取与指定寄存器相关的冲突"""
        return [c for c in self.conflicts
                if c.peripheral == periph_name and c.register == reg_name]

    def get_conflicts_by_type(self, conflict_type: ConflictType) -> List[ConflictItem]:
        """按类型获取冲突"""
        return [c for c in self.conflicts if c.conflict_type == conflict_type]

    def get_summary(self) -> Dict[str, Any]:
        """获取冲突摘要"""
        type_counts = {}
        for c in self.conflicts:
            key = c.conflict_type.value
            type_counts[key] = type_counts.get(key, 0) + 1

        return {
            "total": len(self.conflicts),
            "errors": self.get_error_count(),
            "warnings": self.get_warning_count(),
            "has_conflicts": self.has_conflicts(),
            "type_counts": type_counts,
        }