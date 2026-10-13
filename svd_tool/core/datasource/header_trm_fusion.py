"""H ↔ TRM 融合层 — H 主控（结构骨架）+ TRM 补充（寄存器元数据）。

不同于普通多源融合（SourceFusion 的置信度加权）：这里 H 文件是外设命名与
结构（实例、寄存器成员、位域）的权威锚点，TRM 只补充描述、复位值、访问
类型和位域语义。H 中不存在的 TRM 条目不会静默丢弃，而是进入
coverage["trm_only_items"] 队列供人工审阅。

匹配规则（外设 → 寄存器 → 位域，逐层收窄）：
- 外设：先精确名（UART0），再前缀去实例号（UART ↔ UART0/UART1/...）；
- 寄存器：先精确名，再外设前缀剥离归一化（canonical_register_name）；
- 位域：优先 bit_offset + bit_width，其次名称。

每个融合后的 H 项在 source_ref 中记录：
- header_line / header_raw_text / header_path：H 原始行定位；
- trm_ref：TRM 侧 source_ref（描述/复位值来源）；
- match_reason / match_score：本次匹配依据。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from .header_parser import (
    HeaderModel, HeaderPeripheral, HeaderRegister,
    normalize_identifier, peripheral_root, register_root,
)


# ════════════════════════════════════════════════════
# 模型工厂：优先 reg_core.models（pydantic），缺库时退化为本地等价 dataclass
# ════════════════════════════════════════════════════

class _FallbackField:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _FallbackModel:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _load_model_factory():
    try:
        from reg_core import models as reg_models
        return (
            reg_models.PeripheralBlock,
            reg_models.Register,
            reg_models.BitField,
            reg_models.InterruptDefinition,
        )
    except Exception:
        return _FallbackModel, _FallbackModel, _FallbackModel, _FallbackModel


def _norm_hex(value: int) -> str:
    return f"0x{value:X}"


def _register_match_key(name: str, peripheral: str) -> str:
    from .svd_verifier import canonical_register_name
    return canonical_register_name(name, peripheral)


@dataclass
class FusionMatch:
    match_reason: str
    match_score: float
    trm_ref: dict = field(default_factory=dict)
    trm_name: str = ""
    trm_block: Any = None


@dataclass
class HeaderTrmFusionResult:
    peripherals: list = field(default_factory=list)      # PeripheralBlock 兼容对象
    interrupts: list = field(default_factory=list)       # InterruptDefinition 兼容对象
    coverage: dict = field(default_factory=dict)         # 覆盖率与 trm_only 队列
    match_stats: dict = field(default_factory=dict)      # match_reason 计数


class HeaderTrmFusion:
    """H 骨架 + TRM 元数据融合。"""

    def __init__(self, header_path: str = ""):
        self.header_path = header_path
        (
            self.PeripheralBlockCls,
            self.RegisterCls,
            self.BitFieldCls,
            self.InterruptCls,
        ) = _load_model_factory()
        self.match_reasons: dict[str, int] = {}

    # ---------- 对外入口 ----------

    def fuse(
        self,
        header_model: HeaderModel,
        trm_peripherals: Optional[list] = None,
        trm_interrupts: Optional[list] = None,
    ) -> HeaderTrmFusionResult:
        trm_peripherals = trm_peripherals or []
        trm_interrupts = trm_interrupts or []
        used_trm: set[str] = set()   # 已被 H 吸收的 TRM 外设名
        peripherals: list = []

        for hperiph in header_model.peripherals:
            peripherals.append(self._fuse_peripheral(hperiph, trm_peripherals, used_trm))

        interrupts = self._fuse_interrupts(header_model, trm_interrupts)

        coverage = self._build_coverage(
            header_model, peripherals, trm_peripherals, used_trm)
        return HeaderTrmFusionResult(
            peripherals=peripherals,
            interrupts=interrupts,
            coverage=coverage,
            match_stats=dict(self.match_reasons),
        )

    # ---------- 外设层 ----------

    def _fuse_peripheral(self, hperiph: HeaderPeripheral, trm_peripherals: list,
                         used_trm: set[str]):
        match = self._match_peripheral(hperiph, trm_peripherals)
        if match is not None:
            used_trm.add(match.trm_name)
        trm_block = match.trm_block if match else None

        base = _norm_hex(hperiph.base_address)
        source_ref = {
            "source_file": self.header_path or hperiph.path,
            "line_number": hperiph.line_number,
            "raw_text": hperiph.raw_text,
            "header_line": hperiph.line_number,
            "header_raw_text": hperiph.raw_text,
            "match_reason": match.match_reason if match else "header_only",
            "match_score": match.match_score if match else 0.0,
        }
        if match and match.trm_ref:
            source_ref["trm_ref"] = match.trm_ref

        description = ""
        bus = ""
        if trm_block is not None:
            description = str(getattr(trm_block, "description", "") or "")
            bus = str(getattr(trm_block, "bus", "") or "")
            trm_base = str(getattr(trm_block, "base_address", "") or "")
            if trm_base and _hex_equal(trm_base, base) is False:
                source_ref["trm_base_conflict"] = trm_base
        registers = [
            self._fuse_register(hreg, trm_block, source_ref)
            for hreg in hperiph.registers
        ]
        return self.PeripheralBlockCls(
            name=hperiph.name,
            bus=bus,
            base_address=base,
            description=description or f"{hperiph.name} peripheral ({hperiph.type_name}_TypeDef)",
            registers=registers,
            source_ref=source_ref,
            source_authority="header_anchor",
            aliases=[],
            multi_source_agreement="consistent" if trm_block is not None else "single_source",
        )

    def _match_peripheral(self, hperiph: HeaderPeripheral, trm_peripherals: list) -> Optional[FusionMatch]:
        name = hperiph.name
        # 1) 精确外设名
        for blk in trm_peripherals:
            if normalize_identifier(str(getattr(blk, "name", ""))) == name:
                return self._periph_match(blk, "exact_name", 1.0)
        # 2) 前缀去掉实例号（TRM 的 UART 模板 ↔ H 的 UART0 实例）
        root = peripheral_root(name)
        if root and root != name:
            for blk in trm_peripherals:
                trm_name = normalize_identifier(str(getattr(blk, "name", "")))
                if trm_name == root or peripheral_root(trm_name) == root:
                    return self._periph_match(blk, "peripheral_root", 0.8)
        # 3) 下划线不敏感（RCC_AHB ↔ RCCAHB）
        squashed = (root or name).replace("_", "")
        if squashed:
            for blk in trm_peripherals:
                trm_name = normalize_identifier(str(getattr(blk, "name", "")))
                if peripheral_root(trm_name).replace("_", "") == squashed:
                    return self._periph_match(blk, "squashed_name", 0.7)
        return None

    def _periph_match(self, blk: Any, reason: str, score: float) -> FusionMatch:
        self.match_reasons[reason] = self.match_reasons.get(reason, 0) + 1
        return FusionMatch(
            match_reason=reason,
            match_score=score,
            trm_ref=dict(getattr(blk, "source_ref", {}) or {}),
            trm_name=normalize_identifier(str(getattr(blk, "name", ""))),
            trm_block=blk,
        )

    # ---------- 寄存器层 ----------

    def _fuse_register(self, hreg: HeaderRegister, trm_block: Optional[Any],
                       peripheral_ref: dict):
        match = None
        if trm_block is not None:
            match = self._match_register(hreg, trm_block)
        trm_reg = match.trm_block if match else None

        offset = _norm_hex(hreg.offset)
        source_ref = dict(peripheral_ref)
        source_ref.update({
            "line_number": hreg.line_number,
            "raw_text": hreg.raw_text,
            "header_line": hreg.line_number,
            "header_raw_text": hreg.raw_text,
            "match_reason": match.match_reason if match else "header_only",
            "match_score": match.match_score if match else 0.0,
        })
        if match and match.trm_ref:
            source_ref["trm_ref"] = match.trm_ref

        description = hreg.description
        reset_value = ""
        access = ""
        if trm_reg is not None:
            description = str(getattr(trm_reg, "description", "") or "") or description
            reset_value = str(getattr(trm_reg, "reset_value", "") or "")
            access = str(getattr(trm_reg, "access", "") or "")
            trm_offset = str(getattr(trm_reg, "address_offset", "") or "")
            if trm_offset and not _hex_equal(trm_offset, offset):
                source_ref["trm_offset_conflict"] = trm_offset
        fields = [
            self._fuse_field(hfld, trm_reg, source_ref)
            for hfld in hreg.fields
        ]
        return self.RegisterCls(
            name=hreg.name,
            address_offset=offset,
            absolute_address="",
            reset_value=reset_value,
            description=description,
            access=access,
            fields=fields,
            source_ref=source_ref,
            source_authority="header_anchor",
            aliases=[hreg.name] if hreg.array_length else [],
        )

    def _match_register(self, hreg: HeaderRegister, trm_block: Any) -> Optional[FusionMatch]:
        pname = normalize_identifier(str(getattr(trm_block, "name", "")))
        # 1) 精确名
        for reg in getattr(trm_block, "registers", []) or []:
            if normalize_identifier(str(getattr(reg, "name", ""))) == hreg.name:
                return self._reg_match(reg, pname, "exact_name", 1.0)
        # 2) 外设前缀剥离归一化
        target = _register_match_key(hreg.name, pname)
        for reg in getattr(trm_block, "registers", []) or []:
            trm_name = normalize_identifier(str(getattr(reg, "name", "")))
            if _register_match_key(trm_name, pname) == target:
                return self._reg_match(reg, pname, "peripheral_prefix", 0.8)
        return None

    def _reg_match(self, reg: Any, pname: str, reason: str, score: float) -> FusionMatch:
        self.match_reasons[f"register/{reason}"] = (
            self.match_reasons.get(f"register/{reason}", 0) + 1)
        return FusionMatch(
            match_reason=reason,
            match_score=score,
            trm_ref=dict(getattr(reg, "source_ref", {}) or {}),
            trm_name=f"{pname}/{getattr(reg, 'name', '')}",
            trm_block=reg,
        )

    # ---------- 位域层 ----------

    def _fuse_field(self, hfld: Any, trm_reg: Optional[Any], register_ref: dict):
        match = None
        if trm_reg is not None:
            match = self._match_field(hfld, trm_reg)
        trm_field = match.trm_block if match else None

        source_ref = dict(register_ref)
        source_ref.update({
            "line_number": hfld.line_number,
            "raw_text": hfld.raw_text,
            "header_line": hfld.line_number,
            "header_raw_text": hfld.raw_text,
            "match_reason": match.match_reason if match else "header_only",
            "match_score": match.match_score if match else 0.0,
        })
        if match and match.trm_ref:
            source_ref["trm_ref"] = match.trm_ref

        description = ""
        access = ""
        if trm_field is not None:
            description = str(getattr(trm_field, "description", "") or "")
            access = str(getattr(trm_field, "access", "") or "")
        return self.BitFieldCls(
            name=hfld.name,
            bit_pos=hfld.bit_offset,
            bit_width=hfld.bit_width,
            mask_hex=_norm_hex(hfld.mask) if getattr(hfld, "mask", 0) else "",
            description=description,
            access=access or "RW",
            source_ref=source_ref,
            source_authority="header_anchor",
        )

    def _match_field(self, hfld: Any, trm_reg: Any) -> Optional[FusionMatch]:
        trm_fields = getattr(trm_reg, "fields", []) or []
        # 1) bit_offset + bit_width
        for fld in trm_fields:
            pos = int(getattr(fld, "bit_pos", -1) or -1)
            width = int(getattr(fld, "bit_width", 0) or 0)
            if pos == hfld.bit_offset and width == hfld.bit_width:
                return self._field_match(fld, "bit_position", 0.9)
        # 2) 名称
        for fld in trm_fields:
            if normalize_identifier(str(getattr(fld, "name", ""))) == normalize_identifier(hfld.name):
                return self._field_match(fld, "exact_name", 0.7)
        return None

    def _field_match(self, fld: Any, reason: str, score: float) -> FusionMatch:
        self.match_reasons[f"field/{reason}"] = (
            self.match_reasons.get(f"field/{reason}", 0) + 1)
        return FusionMatch(
            match_reason=reason,
            match_score=score,
            trm_ref=dict(getattr(fld, "source_ref", {}) or {}),
            trm_name=str(getattr(fld, "name", "")),
            trm_block=fld,
        )

    # ---------- 中断层 ----------

    def _fuse_interrupts(self, header_model: HeaderModel, trm_interrupts: list) -> list:
        trm_by_number = {
            int(getattr(irq, "irq_number", -999)): irq for irq in trm_interrupts
        }
        trm_by_name = {
            normalize_identifier(str(getattr(irq, "name", ""))): irq
            for irq in trm_interrupts
        }
        out = []
        for hirq in header_model.interrupts:
            trm_irq = trm_by_number.get(hirq.irq_number)
            if trm_irq is not None:
                reason = "irq_number"
            else:
                trm_irq = trm_by_name.get(normalize_identifier(hirq.name))
                reason = "exact_name" if trm_irq is not None else "header_only"
            if trm_irq is not None:
                self.match_reasons[f"interrupt/{reason}"] = (
                    self.match_reasons.get(f"interrupt/{reason}", 0) + 1)
            description = hirq.description
            if trm_irq is not None and not description:
                description = str(getattr(trm_irq, "description", "") or "")
            source_ref = {
                "source_file": self.header_path or header_model.path,
                "line_number": hirq.line_number,
                "raw_text": hirq.raw_text,
                "header_line": hirq.line_number,
                "header_raw_text": hirq.raw_text,
                "match_reason": reason,
                "match_score": 0.9 if trm_irq is not None else 0.0,
            }
            if trm_irq is not None:
                source_ref["trm_ref"] = dict(getattr(trm_irq, "source_ref", {}) or {})
            out.append(self.InterruptCls(
                name=hirq.name,
                irq_number=hirq.irq_number,
                description=description,
                source_ref=source_ref,
                source_authority="header_anchor",
                aliases=[],
            ))
        return out

    # ---------- 覆盖率 ----------

    def _build_coverage(self, header_model: HeaderModel, fused: list,
                        trm_peripherals: list, used_trm: set[str]) -> dict:
        trm_only = []
        for blk in trm_peripherals:
            name = normalize_identifier(str(getattr(blk, "name", "")))
            if name in used_trm:
                continue
            registers = [
                {"name": str(getattr(reg, "name", "")),
                 "offset": str(getattr(reg, "address_offset", "") or "")}
                for reg in getattr(blk, "registers", []) or []
            ]
            trm_only.append({
                "peripheral": name,
                "base_address": str(getattr(blk, "base_address", "") or ""),
                "registers": registers,
                "source_ref": dict(getattr(blk, "source_ref", {}) or {}),
            })

        header_regs = sum(len(p.registers) for p in header_model.peripherals)
        regs_with_trm = sum(
            1 for p in fused for r in getattr(p, "registers", []) or []
            if (getattr(r, "source_ref", {}) or {}).get("match_reason") not in (None, "header_only"))
        trm_regs_total = sum(
            len(getattr(blk, "registers", []) or []) for blk in trm_peripherals)
        return {
            "mode": "header_master_trm_supplement",
            "header_peripherals": len(header_model.peripherals),
            "trm_peripherals": len(trm_peripherals),
            "trm_peripherals_matched": len(used_trm),
            "header_registers": header_regs,
            "header_registers_with_trm_metadata": regs_with_trm,
            "trm_registers_total": trm_regs_total,
            "trm_supplement_percent": round(
                100.0 * regs_with_trm / header_regs, 2) if header_regs else 0.0,
            "unresolved_header_items": len(header_model.unresolved),
            # TRM 有、H 无 —— 不静默丢弃，等待人工处置
            "trm_only_items": trm_only,
        }


def _hex_equal(a: str, b: str) -> bool:
    def to_int(value: str):
        try:
            return int(str(value).strip(), 16 if str(value).strip().lower().startswith("0x") else 10)
        except ValueError:
            return None
    ia, ib = to_int(a), to_int(b)
    if ia is None or ib is None:
        return True   # 无法比较时不判冲突
    return ia == ib
