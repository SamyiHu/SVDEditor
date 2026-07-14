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
            raw_name = (pblk.name or "").strip()
            pname = self._normalize_periph_name(raw_name, getattr(pblk, "registers", []))
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
            device.peripherals[peripheral.name] = peripheral
            existing_periphs.add(peripheral.name)
            report.peripherals_added += 1
            report.registers_added += len(peripheral.registers)
            report.fields_added += sum(len(r.fields) for r in peripheral.registers.values())

        # 自动检测继承关系：结构相同的外设设 derivedFrom
        self._infer_derived_from(device, report)

        return device, report

    def prune_by_features(self, device: DeviceInfo, features: dict):
        """根据功能矩阵裁剪不存在的功能位域。

        features 来自 FeatureDetector.detect()。
        如 UART3~5 无 DMA → 删除含 'DMA' 的位域名（TXDMAEN, RXDMAEN）。
        """
        from .feature_detector import FeatureDetector
        fd = FeatureDetector()
        for pname, p in device.peripherals.items():
            # 提取外设前缀和实例号
            m = re.match(r'^([A-Za-z]+?)(\d+)$', pname)
            if not m:
                continue
            prefix, inst_str = m.group(1), int(m.group(2))
            missing = fd.missing_features(features, prefix, inst_str)
            if not missing:
                continue
            for feat in missing:
                # 特征关键词 → 应删除的位域
                kw = feat.upper()  # DMA, LIN
                for reg in p.registers.values():
                    to_remove = [fn for fn in reg.fields if kw in fn.upper()]
                    for fn in to_remove:
                        del reg.fields[fn]

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
        # 命名归一化：中文名 → 寄存器前缀推导的标准名（如"温度传感器"→"TS"）
        pname = self._normalize_periph_name(pblk.name, getattr(pblk, "registers", []))
        peripheral = Peripheral(
            name=pname,
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

        # 寄存器（同偏移地址的合并：模式寻址寄存器如 PDTA/RCAP@0x10 → PDTA_RCAP）
        src_regs = getattr(pblk, "registers", []) or []
        merged_groups = self._group_by_offset(src_regs)
        for group in merged_groups:
            if len(group) == 1:
                reg = self._convert_register(group[0], base_addr, report, pblk.name)
            else:
                reg = self._merge_mode_registers(group, base_addr, report, pblk.name)
            peripheral.registers[reg.name] = reg

        return peripheral

    def _group_by_offset(self, registers: list) -> list[list]:
        """把同偏移地址的寄存器分到一组（模式寻址寄存器）。

        保留原始顺序。不同偏移的各自成组。
        """
        groups: list[list] = []
        seen: dict[str, int] = {}  # offset_norm → group index
        for r in registers:
            off = self._norm_hex(getattr(r, "address_offset", "") or "")
            if off in seen:
                groups[seen[off]].append(r)
            else:
                seen[off] = len(groups)
                groups.append([r])
        return groups

    def _merge_mode_registers(self, group: list, periph_base: str,
                              report: ConversionReport, periph_name: str) -> Register:
        """合并同地址的模式寻址寄存器（如 PDTA@0x10 + RCAP@0x10 → PDTA_RCAP@0x10）。

        规则（对齐参考 SVD 风格）：
        - 名字：各寄存器名去掉公共前缀后用 _ 连接，如 TIM0_PDTA + TIM0_RCAP → TIM0_PDTA_RCAP
        - 描述：合并各描述，标注模式条件
        - 位域：全部保留
        - reset_value/size/access：取第一个
        """
        converted = [self._convert_register(r, periph_base, report, periph_name) for r in group]
        # 提取公共前缀（如 TIM0_）
        prefix = ""
        m0 = re.match(r'^([A-Z]+\d*_)', converted[0].name)
        if m0:
            cand = m0.group(1)
            if all(re.match(rf'^{re.escape(cand)}', r.name) for r in converted):
                prefix = cand
        # 短名连接
        short_names = []
        for r in converted:
            if prefix and r.name.startswith(prefix):
                short_names.append(r.name[len(prefix):])
            else:
                short_names.append(r.name)
        merged_name = prefix + "_".join(short_names)

        descs = [r.description for r in converted if r.description]
        merged_desc = " / ".join(descs) if descs else merged_name

        # 合并位域：同位置不同模式的位域合并为复合名（如 PDT+FCAP→PDT_FCAP）
        merged_fields: dict[tuple, Field] = {}
        for r in converted:
            for fn, f in r.fields.items():
                if fn in ('-', '—', ''):  # 跳过占位符
                    continue
                key = (f.bit_offset, f.bit_width)
                if key in merged_fields:
                    existing = merged_fields[key]
                    if fn not in existing.name:
                        existing.name = existing.name + '_' + fn
                else:
                    merged_fields[key] = f
        # 转成 name→Field 的普通 dict
        named_fields = {}
        for f in merged_fields.values():
            if f.name not in ('-', '—', ''):
                named_fields[f.name] = f

        first = converted[0]
        return Register(
            name=merged_name,
            offset=first.offset,
            description=merged_desc,
            display_name=merged_name,
            size=first.size,
            access=first.access,
            reset_value=first.reset_value,
            reset_mask=first.reset_mask,
            fields=named_fields,
        )

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
            access=self._translate_access(getattr(reg, "access", "") or ""),
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
        """寄存器位宽 → SVD size。ARM Cortex-M 寄存器统一 32 位（0x20）。"""
        return "0x20"

    @staticmethod
    def _normalize_periph_name(raw_name: str, registers: list) -> str:
        """外设命名归一化：中文名从寄存器前缀推导标准名。

        TRM 里有些外设以中文命名（如"温度传感器"），但寄存器全是 TS_ 前缀。
        根据寄存器名前缀的公共部分推断标准外设名。
        同时去掉中文括号/注释（如 PWM0_DTx（x = 0~7）→ PWM0_DTx）。
        """
        name = raw_name.strip()
        # 去中文括号及内容
        name = re.sub(r'[（(][^）)]*[\u4e00-\u9fff][^）)]*[）)]', '', name)
        name = re.sub(r'[（(][^）)]*[）)]', '', name)
        name = ''.join(c for c in name if c.isascii()).strip()
        # 如果清理后仍为空或不全是ASCII，从寄存器前缀推导
        if not name:
            name = ChipToSvdConverter._infer_name_from_registers(registers)
        # 清理后为空或过短，也从寄存器推
        if not name or (len(name) < 2 and registers):
            inferred = ChipToSvdConverter._infer_name_from_registers(registers)
            if inferred:
                name = inferred
        return name or raw_name

    @staticmethod
    def _infer_name_from_registers(registers: list) -> str:
        """从寄存器名称的公共前缀推断外设名。
        如 [TS_CFG, TS_STS] → TS；[DMA0_SADR, DMA0_DADR] → DMA0。
        """
        if not registers:
            return ""
        names = [getattr(r, 'name', '') or '' for r in registers]
        names = [n for n in names if n and '_' in n]
        if not names:
            return ""
        # 找最长公共前缀（到第一个 _ 之前或之后？）
        # 策略：如果有多个寄存器且前缀相同，取第一个寄存器 _ 之前的部分
        first = names[0]
        prefix = first.split('_')[0] if '_' in first else first
        # 验证所有寄存器都以此开头
        if all(n.startswith(prefix + '_') for n in names):
            return prefix
        # 否则尝试找公共前缀（逐字符）
        common = names[0]
        for n in names[1:]:
            while not n.startswith(common) and common:
                common = common[:-1]
        # 去掉末尾的 _ 残留
        common = common.rstrip('_')
        return common if len(common) >= 2 else ""

    def _reg_size_bytes(self, reg: Any) -> int:
        return 4  # ARM 32-bit registers

    def _infer_derived_from(self, device: DeviceInfo, report: ConversionReport):
        """自动检测继承关系：结构相同的外设设 derivedFrom。

        签名包含：寄存器数、各寄存器名/偏移/access/位域名/位域位号。
        排除列表：已知特殊外设（如UART2有LIN，不继承UART0）。
        """
        # 结构一致就继承，功能差异由 Datasheet 检测在裁剪阶段处理
        from collections import defaultdict
        groups: dict[tuple, list[str]] = defaultdict(list)
        for pname, p in device.peripherals.items():
            if p.derived_from:
                continue
            sig = self._peri_signature(pname, p)
            if sig:
                groups[sig].append(pname)
        for sig, names in groups.items():
            if len(names) <= 1:
                continue
            base = names[0]
            for pname in names[1:]:
                device.peripherals[pname].derived_from = base
                report.issues.append(ConversionIssue(
                    peripheral=pname, kind="derived_from", severity="info",
                    detail=f"自动继承 {base}"))

    def _peri_signature(self, pname: str, p: Peripheral) -> tuple:
        """外设结构签名：寄存器级 + 位域级，确保真正结构相同才继承。"""
        reg_sig = []  # [(去实例号名称, offset, access, 位域签名)]
        for rn, r in p.registers.items():
            stripped = re.sub(r'\d+', '', rn)
            # 位域签名
            field_sig = tuple(sorted(
                (fn, f.bit_offset, f.bit_width) for fn, f in r.fields.items()
            ))
            reg_sig.append((stripped, r.offset, r.access or '', field_sig))
        return tuple(sorted(reg_sig))

    @staticmethod
    def _translate_access(raw: str) -> Optional[str]:
        """TRM 中文访问类型 → SVD 标准。"""
        if not raw: return None
        r = raw.strip()
        if r in ('读/写', '读写', 'R/W', 'RW', 'rw', 'read-write'): return 'read-write'
        if r in ('只读', 'RO', 'ro', 'read-only'): return 'read-only'
        if r in ('只写', 'WO', 'wo', 'write-only'): return 'write-only'
        return r  # 原样返回（可能是英文）

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
