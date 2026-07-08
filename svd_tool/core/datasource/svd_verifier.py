"""
SVD 核对引擎 — 对比「当前编辑器 DeviceInfo」与「Parser 解析的 ChipData」。

按外设 → 寄存器 → 位域三层对齐，产出结构化差异项（VerifyItem），每项带：
- kind：差异类型（缺失/不符/地址/复位/访问/位宽）
- severity：严重度（error/warning/info）—— 低置信度的 mismatch 降为 warning
- confidence：来源侧置信度（high/medium/low/unknown）
- suggested：建议值字典，供核对面板「接受」时应用

对齐策略：
- 外设：按归一化名（数字→N）匹配，未匹配的记 missing
- 寄存器：先精确名匹配，再归一化名兜底
- 位域：按 (bit_offset, bit_width) 对齐（位号是最稳定主键）
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field as dc_field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("svd_tool.datasource.SVDVerifier")


class VerifyKind(str, Enum):
    """差异类型。"""
    PERIPH_MISSING_IN_SVD = "missing_in_svd"        # 源有、SVD 无
    PERIPH_MISSING_IN_SOURCE = "missing_in_source"  # SVD 有、源无
    REG_MISSING_IN_SVD = "reg_missing_in_svd"
    REG_MISSING_IN_SOURCE = "reg_missing_in_source"
    FIELD_MISSING_IN_SVD = "field_missing_in_svd"
    FIELD_MISSING_IN_SOURCE = "field_missing_in_source"
    ADDRESS_MISMATCH = "address"
    OFFSET_MISMATCH = "offset"
    RESET_MISMATCH = "reset"
    ACCESS_MISMATCH = "access"
    WIDTH_MISMATCH = "width"
    BASE_ADDR_MISMATCH = "base_address"


class VerifySeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class VerifyItem:
    """单个核对差异项。"""
    level: str                          # "peripheral"|"register"|"field"
    peripheral: str
    register: str = ""
    field: str = ""
    kind: str = ""                      # VerifyKind 值
    detail: str = ""
    severity: str = "info"             # VerifySeverity 值
    confidence: str = "unknown"        # 来源侧置信度
    svd_value: str = ""
    source_value: str = ""
    suggested: dict = dc_field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "level": self.level, "peripheral": self.peripheral,
            "register": self.register, "field": self.field,
            "kind": self.kind, "detail": self.detail,
            "severity": self.severity, "confidence": self.confidence,
            "svd_value": self.svd_value, "source_value": self.source_value,
            "suggested": self.suggested,
        }


class SVDVerifier:
    """核对引擎：DeviceInfo vs ChipData。"""

    def verify(self, svd_device: Any, chip_data: Any) -> list[VerifyItem]:
        """执行三层核对，返回差异项列表。

        Args:
            svd_device: 编辑器 DeviceInfo
            chip_data: parser.models.ChipData

        Returns:
            list[VerifyItem]，按 peripheral→register→field 排序
        """
        items: list[VerifyItem] = []

        if svd_device is None or chip_data is None:
            return items

        svd_periphs = getattr(svd_device, "peripherals", {}) or {}
        src_periphs = getattr(chip_data, "peripherals", []) or []

        # 外设层：按归一化名对齐
        svd_by_norm = {}
        for pname, p in svd_periphs.items():
            svd_by_norm.setdefault(_normalize_name(pname), []).append(pname)
        src_by_norm = {}
        for pblk in src_periphs:
            src_by_norm.setdefault(_normalize_name(pblk.name), []).append(pblk)

        all_norm = sorted(set(svd_by_norm) | set(src_by_norm))

        for norm in all_norm:
            svd_names = svd_by_norm.get(norm, [])
            src_blocks = src_by_norm.get(norm, [])

            if not svd_names:
                # 源有、SVD 无
                for pblk in src_blocks:
                    items.append(VerifyItem(
                        level="peripheral", peripheral=pblk.name,
                        kind=VerifyKind.PERIPH_MISSING_IN_SVD.value,
                        detail=f"SVD 中缺少外设 {pblk.name}（源中存在）",
                        severity=VerifySeverity.ERROR.value,
                        confidence=_periph_confidence(pblk),
                        source_value=pblk.base_address or "",
                        suggested=self._suggest_peripheral(pblk),
                    ))
                continue
            if not src_blocks:
                # SVD 有、源无
                for pname in svd_names:
                    items.append(VerifyItem(
                        level="peripheral", peripheral=pname,
                        kind=VerifyKind.PERIPH_MISSING_IN_SOURCE.value,
                        detail=f"数据手册中未见外设 {pname}（仅 SVD 中存在）",
                        severity=VerifySeverity.INFO.value,
                        confidence="unknown",
                    ))
                continue

            # 配对（取首个，多匹配时记 info）
            svd_periph = svd_periphs[svd_names[0]]
            src_periph = src_blocks[0]
            if len(svd_names) > 1 or len(src_blocks) > 1:
                items.append(VerifyItem(
                    level="peripheral", peripheral=svd_names[0],
                    kind="info", detail="同名外设存在多个匹配，按首个核对",
                    severity=VerifySeverity.INFO.value))

            self._verify_peripheral(svd_periph, src_periph, items)

        return items

    # ---------- 外设级核对 ----------

    def _verify_peripheral(self, svd_periph: Any, src_periph: Any, items: list[VerifyItem]) -> None:
        pname = getattr(svd_periph, "name", "") or getattr(src_periph, "name", "")

        # base_address
        svd_base = _norm_hex(getattr(svd_periph, "base_address", ""))
        src_base = _norm_hex(getattr(src_periph, "base_address", ""))
        if svd_base and src_base and svd_base != src_base:
            conf = _periph_confidence(src_periph)
            items.append(VerifyItem(
                level="peripheral", peripheral=pname,
                kind=VerifyKind.BASE_ADDR_MISMATCH.value,
                detail=f"基地址不符：SVD={svd_base} 源={src_base}",
                severity=_conf_severity(conf, default="warning"),
                confidence=conf,
                svd_value=svd_base, source_value=src_base,
                suggested={"base_address": src_base},
            ))

        # 寄存器层对齐
        svd_regs = getattr(svd_periph, "registers", {}) or {}
        src_regs = getattr(src_periph, "registers", []) or []
        self._verify_registers(pname, svd_regs, src_regs, items)

    # ---------- 寄存器级核对 ----------

    def _verify_registers(
        self, pname: str, svd_regs: dict, src_regs: list, items: list[VerifyItem],
    ) -> None:
        # SVD: name → Register；源: list[Register]
        svd_exact = set(svd_regs.keys())
        svd_norm_map = {}
        for rname, reg in svd_regs.items():
            svd_norm_map.setdefault(_normalize_name(rname), []).append((rname, reg))

        src_matched = set()
        for src_reg in src_regs:
            src_name = getattr(src_reg, "name", "") or ""
            matched_svd_name = None

            # 精确匹配
            if src_name in svd_exact:
                matched_svd_name = src_name
            else:
                # 归一化兜底
                cand = svd_norm_map.get(_normalize_name(src_name), [])
                if cand:
                    matched_svd_name = cand[0][0]

            if matched_svd_name is None:
                # 源有、SVD 无
                conf = getattr(src_reg, "confidence", "unknown") or "unknown"
                items.append(VerifyItem(
                    level="register", peripheral=pname, register=src_name,
                    kind=VerifyKind.REG_MISSING_IN_SVD.value,
                    detail=f"SVD 缺少寄存器 {src_name}（源中存在）",
                    severity=_conf_severity(conf, default="warning"),
                    confidence=conf,
                    source_value=getattr(src_reg, "address_offset", "") or "",
                    suggested=self._suggest_register(src_reg),
                ))
                continue

            src_matched.add(matched_svd_name)
            svd_reg = svd_regs[matched_svd_name]
            self._verify_one_register(pname, src_reg, matched_svd_name, svd_reg, items)

        # SVD 有、源无
        for rname in svd_exact - src_matched:
            items.append(VerifyItem(
                level="register", peripheral=pname, register=rname,
                kind=VerifyKind.REG_MISSING_IN_SOURCE.value,
                detail=f"数据手册中未见寄存器 {rname}",
                severity=VerifySeverity.INFO.value, confidence="unknown"))

    def _verify_one_register(
        self, pname: str, src_reg: Any, svd_name: str, svd_reg: Any, items: list[VerifyItem],
    ) -> None:
        conf = getattr(src_reg, "confidence", "unknown") or "unknown"

        # offset / absolute_address
        src_off = _norm_hex(getattr(src_reg, "address_offset", "") or "")
        src_abs = getattr(src_reg, "absolute_address", "") or ""
        svd_off = _norm_hex(getattr(svd_reg, "offset", "") or "")
        if src_off and svd_off and src_off != svd_off:
            # 若 offset 不同但 absolute_address 能对上，视为来源差异而非错误
            items.append(VerifyItem(
                level="register", peripheral=pname, register=svd_name,
                kind=VerifyKind.OFFSET_MISMATCH.value,
                detail=f"寄存器偏移不符：SVD={svd_off} 源={src_off}",
                severity=_conf_severity(conf, "warning"),
                confidence=conf,
                svd_value=svd_off, source_value=src_off,
                suggested={"offset": src_off},
            ))
        elif not svd_off and (src_off or src_abs):
            items.append(VerifyItem(
                level="register", peripheral=pname, register=svd_name,
                kind=VerifyKind.OFFSET_MISMATCH.value,
                detail=f"SVD 寄存器偏移为空，源={src_off or src_abs}",
                severity=_conf_severity(conf, "warning"),
                confidence=conf,
                source_value=src_off or src_abs,
                suggested={"offset": src_off or _norm_hex(src_abs)},
            ))

        # reset_value
        src_reset = _norm_hex(getattr(src_reg, "reset_value", "") or "")
        svd_reset = _norm_hex(getattr(svd_reg, "reset_value", "") or "")
        if src_reset and svd_reset and src_reset != svd_reset:
            items.append(VerifyItem(
                level="register", peripheral=pname, register=svd_name,
                kind=VerifyKind.RESET_MISMATCH.value,
                detail=f"复位值不符：SVD={svd_reset} 源={src_reset}",
                severity=_conf_severity(conf, "warning"),
                confidence=conf,
                svd_value=svd_reset, source_value=src_reset,
                suggested={"reset_value": src_reset},
            ))

        # 位域层
        svd_fields = getattr(svd_reg, "fields", {}) or {}
        src_fields = getattr(src_reg, "fields", []) or []
        self._verify_fields(pname, svd_name, svd_fields, src_fields, items)

    # ---------- 位域级核对 ----------

    def _verify_fields(
        self, pname: str, reg_name: str, svd_fields: dict, src_fields: list, items: list[VerifyItem],
    ) -> None:
        # SVD 位域：name → Field；同时建 (bit_offset, bit_width) → name 索引
        svd_by_pos = {}
        for fname, f in svd_fields.items():
            key = (int(getattr(f, "bit_offset", 0) or 0), max(int(getattr(f, "bit_width", 1) or 1), 1))
            svd_by_pos.setdefault(key, []).append(fname)

        svd_exact = set(svd_fields.keys())
        matched_svd = set()

        for src_f in src_fields:
            src_fname = getattr(src_f, "name", "") or ""
            src_pos = int(getattr(src_f, "bit_pos", 0) or 0)
            src_w = max(int(getattr(src_f, "bit_width", 1) or 1), 1)
            conf = getattr(src_f, "confidence", "unknown") or "unknown"

            matched = None
            if src_fname and src_fname in svd_exact:
                matched = src_fname
            else:
                cand = svd_by_pos.get((src_pos, src_w), [])
                if cand:
                    matched = cand[0]

            if matched is None:
                items.append(VerifyItem(
                    level="field", peripheral=pname, register=reg_name, field=src_fname or f"bit[{src_pos}]",
                    kind=VerifyKind.FIELD_MISSING_IN_SVD.value,
                    detail=f"SVD 缺少位域 {src_fname or 'bit'+str(src_pos)}（源中存在）",
                    severity=_conf_severity(conf, "warning"),
                    confidence=conf,
                    source_value=f"bit[{src_pos}:{src_pos+src_w-1}]",
                    suggested=self._suggest_field(src_f),
                ))
                continue

            matched_svd.add(matched)
            svd_f = svd_fields[matched]
            self._verify_one_field(pname, reg_name, matched, svd_f, src_f, items)

        for fname in svd_exact - matched_svd:
            items.append(VerifyItem(
                level="field", peripheral=pname, register=reg_name, field=fname,
                kind=VerifyKind.FIELD_MISSING_IN_SOURCE.value,
                detail=f"数据手册中未见位域 {fname}",
                severity=VerifySeverity.INFO.value, confidence="unknown"))

    def _verify_one_field(
        self, pname: str, reg_name: str, svd_fname: str, svd_f: Any, src_f: Any, items: list[VerifyItem],
    ) -> None:
        conf = getattr(src_f, "confidence", "unknown") or "unknown"
        src_w = max(int(getattr(src_f, "bit_width", 1) or 1), 1)
        svd_w = max(int(getattr(svd_f, "bit_width", 1) or 1), 1)
        if src_w != svd_w:
            items.append(VerifyItem(
                level="field", peripheral=pname, register=reg_name, field=svd_fname,
                kind=VerifyKind.WIDTH_MISMATCH.value,
                detail=f"位宽不符：SVD={svd_w} 源={src_w}",
                severity=_conf_severity(conf, "warning"),
                confidence=conf,
                svd_value=str(svd_w), source_value=str(src_w),
                suggested={"bit_width": src_w}))

        # access（源 RW/RO/WO vs SVD read-write/...）
        src_access = (getattr(src_f, "access", "") or "").upper()
        svd_access = (getattr(svd_f, "access", "") or "").lower()
        src_norm = _ACCESS_NORM.get(src_access, "")
        if src_norm and svd_access and src_norm != svd_access:
            items.append(VerifyItem(
                level="field", peripheral=pname, register=reg_name, field=svd_fname,
                kind=VerifyKind.ACCESS_MISMATCH.value,
                detail=f"访问权限不符：SVD={svd_access} 源={src_access}",
                severity=_conf_severity(conf, "warning"),
                confidence=conf,
                svd_value=svd_access, source_value=src_access,
                suggested={"access": src_norm}))

    # ---------- 建议值 ----------

    @staticmethod
    def _suggest_peripheral(pblk: Any) -> dict:
        return {
            "name": pblk.name,
            "base_address": _norm_hex(getattr(pblk, "base_address", "") or ""),
            "group_name": getattr(pblk, "bus", "") or "",
            "description": getattr(pblk, "description", "") or "",
        }

    @staticmethod
    def _suggest_register(reg: Any) -> dict:
        return {
            "name": reg.name,
            "offset": _norm_hex(getattr(reg, "address_offset", "") or ""),
            "reset_value": _norm_hex(getattr(reg, "reset_value", "") or ""),
            "description": getattr(reg, "description", "") or "",
        }

    @staticmethod
    def _suggest_field(f: Any) -> dict:
        return {
            "name": getattr(f, "name", "") or "",
            "bit_offset": int(getattr(f, "bit_pos", 0) or 0),
            "bit_width": max(int(getattr(f, "bit_width", 1) or 1), 1),
            "description": getattr(f, "description", "") or "",
        }


# ════════════════════════════════════════════════════
# 辅助函数
# ════════════════════════════════════════════════════

_ACCESS_NORM = {
    "RW": "read-write", "RO": "read-only", "WO": "write-only",
    "RW1": "read-write", "RO1": "read-only", "WO1": "write-only",
}


def _normalize_name(name: str) -> str:
    """名称归一化：数字→N、变量→N，便于通配符实例匹配模板。"""
    if not name:
        return ""
    n = name.upper().strip()
    n = re.sub(r"\d+", "N", n)
    n = re.sub(r"(?<=[A-Z])X(?![A-Z0-9])", "N", n)
    return n


def _norm_hex(s: str) -> str:
    if not s:
        return ""
    s = str(s).strip().upper().replace("_", "").replace(" ", "")
    if s.startswith("0X"):
        try:
            return f"0x{int(s[2:], 16):X}"
        except ValueError:
            return s
    if s.isdigit():
        return f"0x{int(s):X}"
    return s


def _periph_confidence(pblk: Any) -> str:
    """外设置信度：取其寄存器置信度的最高档。"""
    best = "unknown"
    order = {"unknown": 0, "missing": 1, "low": 2, "medium": 3, "high": 4}
    for r in getattr(pblk, "registers", []) or []:
        c = getattr(r, "confidence", "unknown") or "unknown"
        if order.get(c, 0) > order.get(best, 0):
            best = c
    return best


def _conf_severity(conf: str, default: str = "info") -> str:
    """置信度 → 严重度。低置信度的差异降为 warning（可能源错）。"""
    if conf == "high":
        return "error"
    if conf in ("medium",):
        return "warning"
    if conf in ("low", "missing"):
        return "warning"
    return default
