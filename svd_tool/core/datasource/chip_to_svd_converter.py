"""
ChipData → DeviceInfo 转换器。

把 Parser 包（parser.models.ChipData）解析出的外设/寄存器/位域，
转换为 SVDEditor 的 DeviceInfo 数据模型，复用 DeviceInfo.from_dict() 往返约定。

映射核心：
    PeripheralBlock → Peripheral（base_address / group_name←bus）
    Register        → Register（offset，必要时由 absolute_address 推算）
    BitField        → Field（access 枚举翻译 RW→read-write）
    InterruptDefinition → Interrupt（Parser 当前通常不填，空则跳过）

两种模式：
- 全新（target=None）：返回新 DeviceInfo
- 并入（target≠None）：复制 target，逐外设加入；同名/地址冲突的外设跳过并记入 report
"""
from __future__ import annotations

import copy
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from ..data_model import (
    DeviceInfo, Peripheral, Register, Field, Interrupt, CPUInfo,
)

logger = logging.getLogger("svd_tool.datasource.ChipToSvdConverter")


# ════════════════════════════════════════════════════
# 转换报告
# ════════════════════════════════════════════════════

@dataclass
class ConversionIssue:
    """转换中的问题项（跳过/推算/冲突）。"""
    peripheral: str
    kind: str            # "skipped_peripheral"|"offset_inferred"|"low_confidence"|"addr_conflict"
    register: str = ""
    field: str = ""
    detail: str = ""
    severity: str = "info"   # "info"|"warning"


@dataclass
class ConversionReport:
    """转换结果报告。"""
    issues: list[ConversionIssue] = field(default_factory=list)
    peripherals_added: int = 0
    peripherals_skipped: int = 0
    registers_added: int = 0
    fields_added: int = 0
    interrupts_added: int = 0

    def to_dict(self) -> dict:
        return {
            "peripherals_added": self.peripherals_added,
            "peripherals_skipped": self.peripherals_skipped,
            "registers_added": self.registers_added,
            "fields_added": self.fields_added,
            "interrupts_added": self.interrupts_added,
            "issues": [
                {"peripheral": i.peripheral, "register": i.register, "field": i.field,
                 "kind": i.kind, "detail": i.detail, "severity": i.severity}
                for i in self.issues
            ],
        }


# ════════════════════════════════════════════════════
# 转换器
# ════════════════════════════════════════════════════

# 内核名归一化：解析出的 "Cortex-M0+" / "Cortex-M3" → SVD 常用 "CM0+" / "CM3"
_CORE_ALIASES = {
    "cortex-m0": "CM0",
    "cortex-m0+": "CM0+",
    "cortex-m0plus": "CM0+",
    "cortex-m1": "CM1",
    "cortex-m3": "CM3",
    "cortex-m4": "CM4",
    "cortex-m7": "CM7",
    "cortex-m23": "CM23",
    "cortex-m33": "CM33",
    "cortex-m55": "CM55",
    "cortex-m85": "CM85",
}

# 访问类型映射：Parser 的 RW/RO/WO → SVD read-write/read-only/write-only
_ACCESS_MAP = {
    "RW": "read-write",
    "RO": "read-only",
    "WO": "write-only",
    "RW1": "read-write",
    "RO1": "read-only",
    "WO1": "write-only",
}


class ChipToSvdConverter:
    """把 Parser 的 ChipData 转为编辑器的 DeviceInfo。"""

    def convert(
        self,
        chip_data: Any,
        target: Optional[DeviceInfo] = None,
        merge: bool = False,
    ) -> tuple[DeviceInfo, ConversionReport]:
        """执行转换。

        Args:
            chip_data: parser.models.ChipData
            target: 并入模式下的目标 DeviceInfo；为 None 时新建。
            merge: True 时把外设并入 target（冲突跳过）；False 时忽略 target 新建。

        Returns:
            (DeviceInfo, ConversionReport)
        """
        report = ConversionReport()

        if merge and target is not None:
            device = copy.deepcopy(target)
        else:
            device = self._build_new_device(chip_data)

        # 顶层属性（仅在新建时设；并入模式不动既有设备名）
        if not merge:
            device.name = (chip_data.chip_name or device.name or "UNKNOWN_DEVICE").strip()
            self._apply_core(device, getattr(chip_data, "core", "") or "")

        # 中断（Parser 当前通常不填，有空则导入）
        for irq_def in getattr(chip_data, "interrupts", []) or []:
            if irq_def.irq_number is None:
                continue
            self._add_interrupt(device, irq_def, report)

        # 外设
        existing_periphs = set(device.peripherals.keys())
        for pblk in getattr(chip_data, "peripherals", []) or []:
            pname = (pblk.name or "").strip()
            if not pname:
                report.issues.append(ConversionIssue(
                    peripheral="(unnamed)", kind="skipped_peripheral",
                    detail="外设名为空，跳过", severity="warning"))
                report.peripherals_skipped += 1
                continue
            if pname in existing_periphs:
                report.issues.append(ConversionIssue(
                    peripheral=pname, kind="skipped_peripheral",
                    detail="并入模式下外设已存在，跳以免覆盖", severity="warning"))
                report.peripherals_skipped += 1
                continue
            peripheral = self._convert_peripheral(pblk, report)
            device.peripherals[pname] = peripheral
            existing_periphs.add(pname)
            report.peripherals_added += 1
            report.registers_added += len(peripheral.registers)
            report.fields_added += sum(len(r.fields) for r in peripheral.registers.values())

        return device, report

    # ---------- 设备级 ----------

    def _build_new_device(self, chip_data: Any) -> DeviceInfo:
        device = DeviceInfo()
        device.name = (getattr(chip_data, "chip_name", "") or "UNKNOWN_DEVICE").strip()
        return device

    def _apply_core(self, device: DeviceInfo, core_raw: str) -> None:
        """归一化内核名并写入 CPUInfo。"""
        core_raw = (core_raw or "").strip()
        if not core_raw:
            return
        key = core_raw.lower().replace(" ", "")
        cpu_name = _CORE_ALIASES.get(key, core_raw)
        # 部分信息按内核推断默认值
        if cpu_name.startswith("CM"):
            device.cpu = CPUInfo(name=cpu_name, revision="r0p1")
            if cpu_name in ("CM4", "CM7"):
                device.cpu.fpu_present = True

    # ---------- 外设级 ----------

    def _convert_peripheral(self, pblk: Any, report: ConversionReport) -> Peripheral:
        base_addr = self._norm_hex(getattr(pblk, "base_address", "") or "0x40000000")
        peripheral = Peripheral(
            name=pblk.name,
            base_address=base_addr,
            description=getattr(pblk, "description", "") or "",
            group_name=(getattr(pblk, "bus", "") or ""),
            registers={},
        )
        # address_block.size：按寄存器最大 offset+size 估算
        max_end = 0
        reg_step = 4  # 默认寄存器步长（字节）
        for r in getattr(pblk, "registers", []) or []:
            offset_int = self._parse_hex_int(r.address_offset)
            if offset_int is not None and offset_int >= max_end:
                max_end = offset_int
                reg_step = max(reg_step, self._reg_size_bytes(r))
        block_size = max(max_end + reg_step, 0x4)
        peripheral.address_block = {
            "offset": "0x0",
            "size": f"0x{block_size:X}",
            "usage": "registers",
        }

        # 寄存器
        for r in getattr(pblk, "registers", []) or []:
            reg = self._convert_register(r, base_addr, report, pblk.name)
            peripheral.registers[reg.name] = reg

        return peripheral

    # ---------- 寄存器级 ----------

    def _convert_register(
        self, reg: Any, periph_base: str, report: ConversionReport, periph_name: str,
    ) -> Register:
        # offset 优先；缺失时由 absolute_address 推算
        offset_str = self._norm_hex(getattr(reg, "address_offset", "") or "")
        if not offset_str:
            abs_addr = self._parse_hex_int(getattr(reg, "absolute_address", ""))
            base_int = self._parse_hex_int(periph_base)
            if abs_addr is not None and base_int is not None and abs_addr >= base_int:
                offset_str = f"0x{abs_addr - base_int:X}"
            else:
                offset_str = "0x0"
                report.issues.append(ConversionIssue(
                    peripheral=periph_name, register=getattr(reg, "name", ""),
                    kind="offset_inferred", severity="warning",
                    detail="缺少偏移/绝对地址，置为 0x0"))

        size_hex = self._reg_size_hex(reg)
        reset_val = self._norm_hex(getattr(reg, "reset_value", "") or "0x00000000")

        svd_reg = Register(
            name=reg.name,
            offset=offset_str,
            description=getattr(reg, "description", "") or "",
            size=size_hex,
            access=None,           # 寄存器级 access 通常由字段继承，留空
            reset_value=reset_val,
            reset_mask="0xFFFFFFFF",
            fields={},
        )

        for f in getattr(reg, "fields", []) or []:
            field_obj = self._convert_field(f, report, periph_name, reg.name)
            if field_obj.name and field_obj.name not in svd_reg.fields:
                svd_reg.fields[field_obj.name] = field_obj

        return svd_reg

    # ---------- 位域级 ----------

    def _convert_field(
        self, f: Any, report: ConversionReport, periph_name: str, reg_name: str,
    ) -> Field:
        access = _ACCESS_MAP.get((getattr(f, "access", "") or "RW").upper(), None)
        enum_values = self._convert_enum(getattr(f, "enum_values", {}) or {})
        bit_offset = int(getattr(f, "bit_pos", 0) or 0)
        bit_width = max(int(getattr(f, "bit_width", 1) or 1), 1)

        # 低置信度提示
        conf = (getattr(f, "confidence", "unknown") or "unknown")
        if conf in ("low", "missing"):
            report.issues.append(ConversionIssue(
                peripheral=periph_name, register=reg_name, field=getattr(f, "name", ""),
                kind="low_confidence", severity="warning",
                detail=f"位域置信度={conf}"))

        return Field(
            name=(getattr(f, "name", "") or "").strip(),
            description=getattr(f, "description", "") or "",
            bit_offset=bit_offset,
            bit_width=bit_width,
            access=access,
            reset_value="0x0",
            enumerated_values=enum_values,
        )

    # ---------- 中断级 ----------

    def _add_interrupt(self, device: DeviceInfo, irq_def: Any, report: ConversionReport) -> None:
        name = (getattr(irq_def, "name", "") or "").strip()
        if not name:
            return
        if name in device.interrupts:
            return
        try:
            value = int(getattr(irq_def, "irq_number", -1))
        except (TypeError, ValueError):
            return
        device.interrupts[name] = Interrupt(
            name=name,
            value=value,
            description=getattr(irq_def, "description", "") or "",
        )
        report.interrupts_added += 1

    # ---------- 数值/格式归一化 ----------

    @staticmethod
    def _norm_hex(s: str) -> str:
        """归一化十六进制字符串：确保 0x 前缀、大写、去空白。空值保留空。"""
        if not s:
            return ""
        s = str(s).strip()
        if not s:
            return ""
        # 已是 0x 形式 → 统一大小写
        m = re.match(r"^(0x)?([0-9a-fA-F_]+)$", s)
        if m:
            digits = m.group(2).replace("_", "")
            try:
                n = int(digits, 16)
                return f"0x{n:X}"
            except ValueError:
                pass
        # 纯十进制
        if s.isdigit():
            return f"0x{int(s):X}"
        return s

    @staticmethod
    def _parse_hex_int(s: str) -> Optional[int]:
        """解析十六进制/十进制字符串为 int，失败返回 None。"""
        if s is None:
            return None
        s = str(s).strip()
        if not s:
            return None
        try:
            if s.lower().startswith("0x"):
                return int(s, 16)
            return int(s, 10)
        except ValueError:
            return None

    def _reg_size_hex(self, reg: Any) -> str:
        """寄存器位宽 → SVD size（十六进制字节数）。"""
        max_bit = 0
        for f in getattr(reg, "fields", []) or []:
            end = int(getattr(f, "bit_pos", 0) or 0) + max(int(getattr(f, "bit_width", 1) or 1), 1)
            if end > max_bit:
                max_bit = end
        bits = max_bit if max_bit > 0 else 32
        # 向上取整到字节边界
        bytes_n = ((bits + 7) // 8)
        # 常见寄存器宽度：8/16/32 位 → 1/2/4 字节
        if bytes_n <= 1:
            bytes_n = 1
        elif bytes_n <= 2:
            bytes_n = 2
        else:
            bytes_n = 4
        return f"0x{bytes_n * 8:X}"   # SVD size 字段用位数表示（如 0x20=32）

    def _reg_size_bytes(self, reg: Any) -> int:
        size_hex = self._reg_size_hex(reg)
        n = self._parse_hex_int(size_hex)
        return (n // 8) if n else 4

    @staticmethod
    def _convert_enum(enum_values: Any) -> list[dict[str, str]]:
        """Parser 的 enum_values (dict{value: meaning}) → SVD list[{name,value,description}]。

        Parser 用数字字符串做 key（如 {"0": "disable", "1": "enable"}）。
        SVD 习惯每个枚举值有 name（VALUE_DISABLE 之类）。
        """
        out: list[dict[str, str]] = []
        if not enum_values:
            return out
        if isinstance(enum_values, dict):
            items = enum_values.items()
        elif isinstance(enum_values, list):
            items = [(str(i), v) for i, v in enumerate(enum_values)]
        else:
            return out
        for val, meaning in items:
            val_str = str(val).strip()
            meaning_str = str(meaning).strip()
            if not val_str and not meaning_str:
                continue
            name = ChipToSvdConverter._enum_name(meaning_str, val_str)
            out.append({
                "name": name,
                "value": val_str,
                "description": meaning_str,
            })
        return out

    @staticmethod
    def _enum_name(meaning: str, value: str) -> str:
        """从含义生成大写下划线枚举名（VALUE_<含义>）。"""
        cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fa5]+", "_", meaning).strip("_").upper()
        cleaned = re.sub(r"_+", "_", cleaned)
        if not cleaned:
            cleaned = f"VALUE_{value}"
        return cleaned[:32] if len(cleaned) > 32 else cleaned
