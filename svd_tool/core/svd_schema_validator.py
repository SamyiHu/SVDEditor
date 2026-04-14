# svd_tool/core/svd_schema_validator.py
"""
CMSIS-SVD Schema 完整验证器
基于 ARM CMSIS-SVD 规范，对 SVD 数据模型进行全方位验证

验证项包括：
1. 位域重叠检测（两个位域占了同一位）
2. 寄存器地址重叠检测（两个寄存器偏移相同）
3. 外设地址重叠检测（两个外设地址范围重叠）
4. 必需字段完整性检查
5. access 枚举值合法性
6. size 合法值检查
7. 位域范围是否超出寄存器宽度
8. derivedFrom 引用是否存在
9. 中断号是否重复
10. 名称重复检测
11. 十六进制格式验证
"""
import logging
from typing import List, Dict, Any, Tuple, Optional
from enum import Enum

from .data_model import DeviceInfo, Peripheral, Register, Field, Interrupt, CPUInfo

logger = logging.getLogger("SVDSchemaValidator")


class Severity(Enum):
    """验证结果严重程度"""
    ERROR = "error"       # 错误：必须修复，否则下游工具可能失败
    WARNING = "warning"   # 警告：建议修复
    INFO = "info"         # 信息：供参考


class ValidationItem:
    """单条验证结果"""
    def __init__(self, severity: Severity, category: str, message: str,
                 location: str = "", suggestion: str = ""):
        self.severity = severity
        self.category = category
        self.message = message
        self.location = location
        self.suggestion = suggestion

    def __repr__(self):
        loc = f" [{self.location}]" if self.location else ""
        return f"[{self.severity.value.upper()}] {self.category}{loc}: {self.message}"

    def to_dict(self) -> Dict[str, str]:
        return {
            "severity": self.severity.value,
            "category": self.category,
            "message": self.message,
            "location": self.location,
            "suggestion": self.suggestion
        }


class SVDSchemaValidator:
    """CMSIS-SVD Schema 完整验证器"""

    # CMSIS-SVD 规范允许的 access 值
    VALID_ACCESS_VALUES = {"read-write", "read-only", "write-only", "writeOnce", "read-writeOnce"}

    # CMSIS-SVD 规范允许的 size 值（位为单位）
    VALID_SIZE_VALUES = {8: "0x08", 16: "0x10", 32: "0x20", 64: "0x40"}

    # CPU 名称合法性
    VALID_CPU_NAMES = {
        "CM0", "CM0PLUS", "CM0+", "CM1", "SC000", "CM3", "SC300",
        "CM4", "CM4_FP", "CM7", "CM7_FP", "CM7_SP", "CM7_DP",
        "CM23", "CM23_NS", "CM33", "CM33_NS", "CM33_FP", "CM33_FP_NS",
        "CM35P", "CM35P_NS", "CM35P_FP", "CM35P_FP_NS",
        "CM55", "CM55_NS", "CM55_FP", "CM55_FP_NS",
        "CM85", "CM85_NS", "CM85_FP", "CM85_FP_NS",
        "CA5", "CA7", "CA8", "CA9", "CA15", "CA17", "CA53", "CA57",
        "CA72", "other"
    }

    # endian 合法值
    VALID_ENDIAN_VALUES = {"little", "big", "selectable"}

    def __init__(self):
        self.results: List[ValidationItem] = []

    def clear(self):
        """清空验证结果"""
        self.results.clear()

    def _add_error(self, category: str, message: str, location: str = "", suggestion: str = ""):
        self.results.append(ValidationItem(Severity.ERROR, category, message, location, suggestion))

    def _add_warning(self, category: str, message: str, location: str = "", suggestion: str = ""):
        self.results.append(ValidationItem(Severity.WARNING, category, message, location, suggestion))

    def _add_info(self, category: str, message: str, location: str = "", suggestion: str = ""):
        self.results.append(ValidationItem(Severity.INFO, category, message, location, suggestion))

    @staticmethod
    def _parse_hex(value) -> Optional[int]:
        """解析十六进制或十进制数值字符串，失败返回 None
        
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
            # 尝试十进制解析
            return int(s)
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _parse_int(value) -> Optional[int]:
        """解析整数值，失败返回 None"""
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    # ==================== 设备级验证 ====================

    def validate_device(self, device: DeviceInfo):
        """验证设备级信息"""
        # 必需字段
        if not device.name or not device.name.strip():
            self._add_error("设备信息", "设备名称(name)不能为空", "device.name",
                           "请在基础信息标签页填写芯片型号名称")
        elif not device.name.replace('_', '').isalnum():
            self._add_warning("设备信息", f"设备名称 '{device.name}' 包含特殊字符，建议只使用字母、数字和下划线",
                             "device.name")

        if not device.version or not device.version.strip():
            self._add_warning("设备信息", "版本号(version)未设置", "device.version",
                             "建议设置版本号，如 '1.0' 或 'V0.1'")

        # CPU 信息验证
        self._validate_cpu(device.cpu)

        # size 和 resetValue 一致性
        default_size = self._parse_hex(device.size)
        if default_size is not None:
            valid_sizes = self.VALID_SIZE_VALUES.keys()
            if default_size not in valid_sizes:
                self._add_error("设备信息",
                               f"默认寄存器大小 {device.size} 不合法，CMSIS-SVD 规范要求: 8(0x08), 16(0x10), 32(0x20), 64(0x40)",
                               "device.size")

    def _validate_cpu(self, cpu: CPUInfo):
        """验证 CPU 信息"""
        if not cpu.name or not cpu.name.strip():
            self._add_error("CPU信息", "CPU 名称不能为空", "cpu.name")
        elif cpu.name not in self.VALID_CPU_NAMES:
            self._add_warning("CPU信息",
                             f"CPU 名称 '{cpu.name}' 不在标准 CMSIS CPU 列表中",
                             "cpu.name",
                             "标准值: CM0, CM0+, CM3, CM4, CM4_FP, CM7 等")

        if cpu.endian not in self.VALID_ENDIAN_VALUES:
            self._add_error("CPU信息",
                           f"端序(endian) '{cpu.endian}' 不合法，应为: little, big, selectable",
                           "cpu.endian")

        if cpu.nvic_prio_bits < 1 or cpu.nvic_prio_bits > 8:
            self._add_warning("CPU信息",
                             f"NVIC 优先级位数 {cpu.nvic_prio_bits} 超出常规范围(1-8)",
                             "cpu.nvicPrioBits")

    # ==================== 外设级验证 ====================

    def validate_peripherals(self, device: DeviceInfo):
        """验证所有外设"""
        if not device.peripherals:
            self._add_warning("外设", "设备没有任何外设定义", "device.peripherals")
            return

        periph_names = list(device.peripherals.keys())

        # 检查外设名称重复（字典本身不允许，但检查大小写不敏感的重复）
        name_lower_map: Dict[str, str] = {}
        for name in periph_names:
            lower = name.lower()
            if lower in name_lower_map:
                self._add_error("外设名称",
                               f"外设名称 '{name}' 与 '{name_lower_map[lower]}' 大小写不同但可能冲突",
                               f"peripheral.{name}")
            name_lower_map[lower] = name

        # 检查 derivedFrom 引用
        for name, periph in device.peripherals.items():
            if periph.derived_from:
                if periph.derived_from not in device.peripherals:
                    self._add_error("继承引用",
                                   f"外设 '{name}' 的 derivedFrom='{periph.derived_from}' 不存在",
                                   f"peripheral.{name}.derivedFrom",
                                   f"请确认 '{periph.derived_from}' 外设已定义")

        # 收集所有外设地址范围，检查重叠
        periph_ranges: List[Tuple[str, int, int]] = []  # (name, base_addr, end_addr)
        for name, periph in device.peripherals.items():
            base_addr = self._parse_hex(periph.base_address)
            if base_addr is None:
                self._add_error("外设地址",
                               f"外设 '{name}' 的基地址 '{periph.base_address}' 不是有效的十六进制数",
                               f"peripheral.{name}.baseAddress")
                continue

            # 计算地址范围
            addr_block = periph.address_block
            block_offset = self._parse_hex(addr_block.get("offset", "0x0")) or 0
            block_size = self._parse_hex(addr_block.get("size", "0x0")) or 0
            start = base_addr + block_offset
            end = start + block_size - 1 if block_size > 0 else start
            periph_ranges.append((name, start, end))

            # 验证单个外设
            self._validate_peripheral(name, periph)

        # 检查外设地址重叠
        for i in range(len(periph_ranges)):
            for j in range(i + 1, len(periph_ranges)):
                name_i, start_i, end_i = periph_ranges[i]
                name_j, start_j, end_j = periph_ranges[j]
                # 重叠条件：start_i <= end_j and start_j <= end_i
                if start_i <= end_j and start_j <= end_i:
                    self._add_error("地址重叠",
                                   f"外设 '{name_i}' (0x{start_i:08X}-0x{end_i:08X}) 与 "
                                   f"'{name_j}' (0x{start_j:08X}-0x{end_j:08X}) 地址范围重叠",
                                   f"peripheral.{name_i} / peripheral.{name_j}",
                                   "请检查 baseAddress 和 addressBlock 配置")

    def _validate_peripheral(self, name: str, periph: Peripheral):
        """验证单个外设"""
        # 必需字段
        if not periph.name or not periph.name.strip():
            self._add_error("外设信息", f"外设(index={name})的 name 字段为空",
                           f"peripheral.{name}.name")

        if not periph.base_address or not str(periph.base_address).strip():
            self._add_error("外设信息", f"外设 '{name}' 缺少基地址(baseAddress)",
                           f"peripheral.{name}.baseAddress")

        # 验证寄存器
        if not periph.registers:
            self._add_warning("外设信息", f"外设 '{name}' 没有任何寄存器定义",
                             f"peripheral.{name}.registers")
        else:
            self._validate_registers(name, periph)

    # ==================== 寄存器级验证 ====================

    def _validate_registers(self, periph_name: str, periph: Peripheral):
        """验证外设内所有寄存器"""
        # 检查寄存器偏移地址重复
        offset_map: Dict[str, List[str]] = {}  # offset -> [reg_names]
        reg_size = self._parse_hex(periph.registers[next(iter(periph.registers))].size) if periph.registers else 32

        for reg_name, reg in periph.registers.items():
            # 必需字段检查
            if not reg.name or not reg.name.strip():
                self._add_error("寄存器信息",
                               f"外设 '{periph_name}' 中有寄存器 name 为空",
                               f"peripheral.{periph_name}.register.{reg_name}")

            # 偏移地址验证
            offset = self._parse_hex(reg.offset)
            if offset is None:
                self._add_error("寄存器偏移",
                               f"寄存器 '{periph_name}.{reg_name}' 的偏移地址 '{reg.offset}' 不是有效的十六进制数",
                               f"peripheral.{periph_name}.register.{reg_name}.addressOffset")
            else:
                offset_key = f"0x{offset:04X}"
                if offset_key not in offset_map:
                    offset_map[offset_key] = []
                offset_map[offset_key].append(reg_name)

            # size 验证
            reg_size_val = self._parse_hex(reg.size)
            if reg_size_val is not None:
                if reg_size_val not in self.VALID_SIZE_VALUES:
                    self._add_error("寄存器大小",
                                   f"寄存器 '{periph_name}.{reg_name}' 的 size={reg.size} 不合法，"
                                   f"CMSIS-SVD 规范要求: 8(0x08), 16(0x10), 32(0x20), 64(0x40)",
                                   f"peripheral.{periph_name}.register.{reg_name}.size")

            # access 验证
            if reg.access and reg.access not in self.VALID_ACCESS_VALUES:
                self._add_error("访问权限",
                               f"寄存器 '{periph_name}.{reg_name}' 的 access='{reg.access}' 不合法，"
                               f"应为: {', '.join(sorted(self.VALID_ACCESS_VALUES))}",
                               f"peripheral.{periph_name}.register.{reg_name}.access")

            # resetValue 与 size 一致性
            if reg_size_val is not None:
                reset_val = self._parse_hex(reg.reset_value)
                if reset_val is not None:
                    max_val = (1 << reg_size_val) - 1
                    if reset_val > max_val:
                        self._add_error("复位值",
                                       f"寄存器 '{periph_name}.{reg_name}' 的 resetValue=0x{reset_val:X} "
                                       f"超出 size={reg_size_val} 位范围 (最大 0x{max_val:X})",
                                       f"peripheral.{periph_name}.register.{reg_name}.resetValue")

            # 验证位域
            if reg.fields:
                self._validate_fields(periph_name, reg_name, reg)

        # 报告偏移地址重复
        for offset_key, reg_names in offset_map.items():
            if len(reg_names) > 1:
                self._add_error("地址重叠",
                               f"外设 '{periph_name}' 中寄存器 {', '.join(reg_names)} 的偏移地址相同 ({offset_key})",
                               f"peripheral.{periph_name}.register.{'+'.join(reg_names)}",
                               "寄存器偏移地址在同一外设内必须唯一")

    # ==================== 位域级验证 ====================

    def _validate_fields(self, periph_name: str, reg_name: str, reg: Register):
        """验证寄存器内所有位域"""
        reg_size = self._parse_hex(reg.size)
        if reg_size is None:
            reg_size = 32  # 默认32位

        # 收集位域占用范围，用于重叠检测
        bit_occupancy: Dict[int, str] = {}  # bit_position -> field_name

        for field_name, fld in reg.fields.items():
            location = f"peripheral.{periph_name}.register.{reg_name}.field.{field_name}"

            # 必需字段
            if not fld.name or not fld.name.strip():
                self._add_error("位域信息",
                               f"位域 '{periph_name}.{reg_name}.(unnamed)' name 为空",
                               location)
                continue

            # 位偏移和位宽验证
            bit_offset = self._parse_int(fld.bit_offset)
            bit_width = self._parse_int(fld.bit_width)

            if bit_offset is None:
                self._add_error("位域偏移",
                               f"位域 '{periph_name}.{reg_name}.{field_name}' 的 bitOffset 无效: {fld.bit_offset}",
                               location)
                continue

            if bit_width is None or bit_width < 1:
                self._add_error("位域宽度",
                               f"位域 '{periph_name}.{reg_name}.{field_name}' 的 bitWidth 无效: {fld.bit_width}",
                               location)
                continue

            # 位域范围检查
            if bit_offset < 0:
                self._add_error("位域范围",
                               f"位域 '{periph_name}.{reg_name}.{field_name}' 的 bitOffset={bit_offset} 不能为负数",
                               location)
                continue

            if bit_offset + bit_width > reg_size:
                self._add_error("位域范围",
                               f"位域 '{periph_name}.{reg_name}.{field_name}' 的范围 [{bit_offset}:{bit_offset+bit_width-1}] "
                               f"超出寄存器宽度 {reg_size} 位",
                               location,
                               f"bitOffset + bitWidth 不能超过 {reg_size}")
                continue

            # 位域重叠检测
            for bit in range(bit_offset, bit_offset + bit_width):
                if bit in bit_occupancy:
                    self._add_error("位域重叠",
                                   f"位域 '{field_name}' 与 '{bit_occupancy[bit]}' 在 bit {bit} 处重叠 "
                                   f"(寄存器 {periph_name}.{reg_name})",
                                   location,
                                   "同一寄存器内的位域不能占据相同的位")
                    break  # 只报告一次重叠（避免大量重复消息）
                bit_occupancy[bit] = field_name

            # access 验证
            if fld.access and fld.access not in self.VALID_ACCESS_VALUES:
                self._add_error("访问权限",
                               f"位域 '{periph_name}.{reg_name}.{field_name}' 的 access='{fld.access}' 不合法",
                               location)

            # resetValue 范围检查
            reset_val = self._parse_hex(fld.reset_value)
            if reset_val is not None and bit_width > 0:
                max_val = (1 << bit_width) - 1
                if reset_val > max_val:
                    self._add_error("位域复位值",
                                   f"位域 '{periph_name}.{reg_name}.{field_name}' 的 resetValue=0x{reset_val:X} "
                                   f"超出 {bit_width} 位范围 (最大 0x{max_val:X})",
                                   location)

        # 检查位域间隙（可选，作为信息提示）
        if reg.fields and reg_size <= 64:  # 只对合理大小的寄存器检查
            covered_bits = set()
            for fld in reg.fields.values():
                bit_offset = self._parse_int(fld.bit_offset) or 0
                bit_width = self._parse_int(fld.bit_width) or 0
                for bit in range(bit_offset, bit_offset + bit_width):
                    covered_bits.add(bit)

            if len(covered_bits) > 0 and len(covered_bits) < reg_size:
                uncovered = reg_size - len(covered_bits)
                if uncovered > 4:  # 只在间隙较大时提示
                    self._add_info("位域间隙",
                                  f"寄存器 '{periph_name}.{reg_name}' 有 {uncovered}/{reg_size} 位未被位域覆盖",
                                  f"peripheral.{periph_name}.register.{reg_name}")

    # ==================== 中断验证 ====================

    def validate_interrupts(self, device: DeviceInfo):
        """验证所有中断"""
        if not device.interrupts:
            return

        # 检查中断号重复
        irq_value_map: Dict[int, List[str]] = {}  # irq_number -> [interrupt_names]
        for irq_name, irq in device.interrupts.items():
            if not irq.name or not irq.name.strip():
                self._add_error("中断信息", f"存在未命名的中断 (irq={irq.value})",
                               "interrupts")
                continue

            irq_val = self._parse_int(irq.value)
            if irq_val is None:
                self._add_error("中断号",
                               f"中断 '{irq.name}' 的中断号无效: {irq.value}",
                               f"interrupt.{irq.name}.value")
                continue

            if irq_val < 0:
                self._add_error("中断号",
                               f"中断 '{irq.name}' 的中断号 {irq_val} 不能为负数",
                               f"interrupt.{irq.name}.value")

            if irq_val not in irq_value_map:
                irq_value_map[irq_val] = []
            irq_value_map[irq_val].append(irq.name)

            # 检查关联外设是否存在
            if irq.peripherals:
                for p_name in irq.peripherals:
                    if p_name not in device.peripherals:
                        self._add_warning("中断关联",
                                         f"中断 '{irq.name}' 关联的外设 '{p_name}' 不存在",
                                         f"interrupt.{irq.name}",
                                         f"请确认外设 '{p_name}' 是否已定义")

        # 报告中断号重复
        for irq_val, irq_names in irq_value_map.items():
            if len(irq_names) > 1:
                self._add_error("中断号重复",
                               f"中断号 {irq_val} 被多个中断使用: {', '.join(irq_names)}",
                               f"interrupt.{'+'.join(irq_names)}",
                               "每个中断应有唯一的中断号")

    # ==================== 主验证入口 ====================

    def validate_all(self, device: DeviceInfo) -> List[ValidationItem]:
        """
        执行完整的 CMSIS-SVD Schema 验证

        Args:
            device: 设备信息数据模型

        Returns:
            验证结果列表
        """
        self.clear()

        logger.info("开始 CMSIS-SVD Schema 完整验证...")

        # 1. 设备级验证
        self.validate_device(device)

        # 2. 外设级验证（包含寄存器和位域）
        self.validate_peripherals(device)

        # 3. 中断验证
        self.validate_interrupts(device)

        # 汇总
        error_count = sum(1 for r in self.results if r.severity == Severity.ERROR)
        warning_count = sum(1 for r in self.results if r.severity == Severity.WARNING)
        info_count = sum(1 for r in self.results if r.severity == Severity.INFO)

        logger.info(f"验证完成: {error_count} 错误, {warning_count} 警告, {info_count} 信息")

        return self.results

    def get_errors(self) -> List[ValidationItem]:
        """只获取错误级别的结果"""
        return [r for r in self.results if r.severity == Severity.ERROR]

    def get_warnings(self) -> List[ValidationItem]:
        """只获取警告级别的结果"""
        return [r for r in self.results if r.severity == Severity.WARNING]

    def has_errors(self) -> bool:
        """是否存在错误"""
        return any(r.severity == Severity.ERROR for r in self.results)

    def get_summary(self) -> Dict[str, Any]:
        """获取验证摘要"""
        errors = self.get_errors()
        warnings = self.get_warnings()
        infos = [r for r in self.results if r.severity == Severity.INFO]

        # 按类别分组统计
        categories: Dict[str, int] = {}
        for r in self.results:
            categories[r.category] = categories.get(r.category, 0) + 1

        return {
            "total": len(self.results),
            "errors": len(errors),
            "warnings": len(warnings),
            "infos": len(infos),
            "has_errors": len(errors) > 0,
            "categories": categories,
            "results": [r.to_dict() for r in self.results]
        }

    # ==================== 实时冲突检测（用于编辑对话框） ====================

    @staticmethod
    def check_peripheral_address_conflict(
        new_name: str, new_base_addr: str, new_addr_block: Dict[str, str],
        existing_peripherals: Dict[str, 'Peripheral'],
        exclude_name: str = ""
    ) -> Optional[str]:
        """
        检查外设地址是否与现有外设冲突（用于编辑对话框实时检测）

        Args:
            new_name: 新外设名称
            new_base_addr: 新外设基地址（十六进制字符串）
            new_addr_block: 新外设地址块 {"offset": ..., "size": ...}
            existing_peripherals: 现有外设字典 {name: Peripheral}
            exclude_name: 排除的外设名（编辑时排除自身）

        Returns:
            冲突描述字符串，无冲突返回 None
        """
        base = SVDSchemaValidator._parse_hex(new_base_addr)
        if base is None:
            return None  # 无效地址由其他验证处理

        block_offset = SVDSchemaValidator._parse_hex(new_addr_block.get("offset", "0x0")) or 0
        block_size = SVDSchemaValidator._parse_hex(new_addr_block.get("size", "0x0")) or 0
        new_start = base + block_offset
        new_end = new_start + block_size - 1 if block_size > 0 else new_start

        for name, periph in existing_peripherals.items():
            if name == exclude_name:
                continue

            exist_base = SVDSchemaValidator._parse_hex(periph.base_address)
            if exist_base is None:
                continue

            exist_block = periph.address_block
            exist_offset = SVDSchemaValidator._parse_hex(exist_block.get("offset", "0x0")) or 0
            exist_size = SVDSchemaValidator._parse_hex(exist_block.get("size", "0x0")) or 0
            exist_start = exist_base + exist_offset
            exist_end = exist_start + exist_size - 1 if exist_size > 0 else exist_start

            # 检查重叠
            if new_start <= exist_end and exist_start <= new_end:
                return (
                    f"地址冲突：与外设 '{name}' (0x{exist_start:08X}-0x{exist_end:08X}) 地址范围重叠"
                )

        return None

    @staticmethod
    def check_register_offset_conflict(
        new_name: str, new_offset: str,
        existing_registers: Dict[str, 'Register'],
        exclude_name: str = ""
    ) -> Optional[str]:
        """
        检查寄存器偏移是否与同外设内其他寄存器冲突

        Args:
            new_name: 新寄存器名称
            new_offset: 新寄存器偏移地址（十六进制字符串）
            existing_registers: 同外设内现有寄存器字典 {name: Register}
            exclude_name: 排除的寄存器名（编辑时排除自身）

        Returns:
            冲突描述字符串，无冲突返回 None
        """
        offset = SVDSchemaValidator._parse_hex(new_offset)
        if offset is None:
            return None

        for name, reg in existing_registers.items():
            if name == exclude_name:
                continue

            exist_offset = SVDSchemaValidator._parse_hex(reg.offset)
            if exist_offset is None:
                continue

            if offset == exist_offset:
                return f"偏移地址冲突：与寄存器 '{name}' 的偏移地址 (0x{exist_offset:04X}) 相同"

        return None

    @staticmethod
    def check_field_bit_conflict(
        new_name: str, new_bit_offset: int, new_bit_width: int,
        existing_fields: Dict[str, 'Field'],
        exclude_name: str = ""
    ) -> Optional[str]:
        """
        检查位域是否与同寄存器内其他位域的位范围冲突

        Args:
            new_name: 新位域名称
            new_bit_offset: 新位域起始位
            new_bit_width: 新位域位宽
            existing_fields: 同寄存器内现有位域字典 {name: Field}
            exclude_name: 排除的位域名（编辑时排除自身）

        Returns:
            冲突描述字符串，无冲突返回 None
        """
        if new_bit_width < 1:
            return None

        new_end = new_bit_offset + new_bit_width - 1

        for name, fld in existing_fields.items():
            if name == exclude_name:
                continue

            exist_offset = fld.bit_offset if isinstance(fld.bit_offset, int) else None
            exist_width = fld.bit_width if isinstance(fld.bit_width, int) else None
            if exist_offset is None or exist_width is None:
                try:
                    exist_offset = int(fld.bit_offset)
                    exist_width = int(fld.bit_width)
                except (ValueError, TypeError):
                    continue

            exist_end = exist_offset + exist_width - 1

            # 检查位范围重叠
            if new_bit_offset <= exist_end and exist_offset <= new_end:
                return (
                    f"位域冲突：与位域 '{name}' [{exist_offset}:{exist_end}] 在位范围上重叠"
                )

        return None

    def format_results_text(self, max_items: int = 50) -> str:
        """格式化验证结果为可读文本"""
        if not self.results:
            return "✅ 验证通过，未发现任何问题。"

        lines = []
        errors = self.get_errors()
        warnings = self.get_warnings()
        infos = [r for r in self.results if r.severity == Severity.INFO]

        lines.append(f"验证结果: {len(errors)} 错误, {len(warnings)} 警告, {len(infos)} 信息")
        lines.append("=" * 60)

        # 错误
        if errors:
            lines.append("")
            lines.append(f"🔴 错误 ({len(errors)}):")
            for i, item in enumerate(errors[:max_items]):
                loc = f" [{item.location}]" if item.location else ""
                lines.append(f"  {i+1}. {item.category}{loc}: {item.message}")
                if item.suggestion:
                    lines.append(f"     💡 {item.suggestion}")

        # 警告
        if warnings:
            lines.append("")
            lines.append(f"🟡 警告 ({len(warnings)}):")
            for i, item in enumerate(warnings[:max_items]):
                loc = f" [{item.location}]" if item.location else ""
                lines.append(f"  {i+1}. {item.category}{loc}: {item.message}")
                if item.suggestion:
                    lines.append(f"     💡 {item.suggestion}")

        # 信息（精简显示）
        if infos:
            lines.append("")
            lines.append(f"ℹ️ 信息 ({len(infos)}):")
            for i, item in enumerate(infos[:10]):
                loc = f" [{item.location}]" if item.location else ""
                lines.append(f"  {i+1}. {item.category}{loc}: {item.message}")
            if len(infos) > 10:
                lines.append(f"  ... 还有 {len(infos) - 10} 条信息")

        remaining = len(self.results) - max_items
        if remaining > 0:
            lines.append("")
            lines.append(f"... 共 {len(self.results)} 条结果，已显示前 {max_items} 条")

        return "\n".join(lines)