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

from .correction_store import parse_completeness, source_authority_label

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
    source_authority: str = ""
    parse_completeness: str = "unknown"
    manual_confirmation: str = "pending"
    source_ref: dict = dc_field(default_factory=dict)
    manual_value: str = ""
    multi_source_agreement: str = "single_source"
    match_reason: str = "unmatched"
    match_score: float = 0.0
    object_id: str = ""
    semantic_path: str = ""
    aliases: list[str] = dc_field(default_factory=list)

    def to_dict_key(self) -> tuple:
        return (self.level, self.peripheral, self.register, self.field, self.kind)

    def to_dict(self) -> dict:
        return {
            "level": self.level, "peripheral": self.peripheral,
            "register": self.register, "field": self.field,
            "kind": self.kind, "detail": self.detail,
            "severity": self.severity, "confidence": self.confidence,
            "svd_value": self.svd_value, "source_value": self.source_value,
            "suggested": self.suggested,
            "source_authority": self.source_authority,
            "parse_completeness": self.parse_completeness,
            "manual_confirmation": self.manual_confirmation,
            "source_ref": self.source_ref,
            "manual_value": self.manual_value,
            "multi_source_agreement": self.multi_source_agreement,
            "match_reason": self.match_reason,
            "match_score": self.match_score,
            "object_id": self.object_id,
            "semantic_path": self.semantic_path,
            "aliases": self.aliases,
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
        # 外设层对齐：用精确名匹配（外设实例名不同即不同外设，如 UART0≠UART1）。
        # 注意：不能用 _normalize_name（数字→N），否则 UART0/UART1/UART2 会被归并成
        # 同一个 UARTN，导致删除其中一个后核对器认为"还有数据"而不报缺失。
        # 归一化匹配只用于寄存器级（同一外设内的寄存器模板 PWM0_DTx→PWMn_DTn）。
        svd_names_exact = set(svd_periphs.keys())
        src_names_exact = {pblk.name for pblk in src_periphs}
        svd_periph_map = {pname: pblk for pname, pblk in svd_periphs.items()}
        src_periph_map = {pblk.name: pblk for pblk in src_periphs}

        all_names = sorted(svd_names_exact | src_names_exact)

        for pname in all_names:
            in_svd = pname in svd_names_exact
            in_src = pname in src_names_exact

            if in_src and not in_svd:
                # 源有、SVD 无
                pblk = src_periph_map[pname]
                items.append(VerifyItem(
                    level="peripheral", peripheral=pname,
                    kind=VerifyKind.PERIPH_MISSING_IN_SVD.value,
                    detail=f"SVD 中缺少外设 {pname}（源中存在）",
                    severity=VerifySeverity.ERROR.value,
                    confidence=_periph_confidence(pblk),
                    source_value=pblk.base_address or "",
                    suggested=self._suggest_peripheral(pblk),
                ))
                continue
            if in_svd and not in_src:
                # SVD 有、源无
                items.append(VerifyItem(
                    level="peripheral", peripheral=pname,
                    kind=VerifyKind.PERIPH_MISSING_IN_SOURCE.value,
                    detail=f"数据手册中未见外设 {pname}（仅 SVD 中存在）",
                    severity=VerifySeverity.INFO.value,
                    confidence="unknown",
                ))
                continue

            # 两边都有：配对核对内部
            svd_periph = svd_periph_map[pname]
            src_periph = src_periph_map[pname]

            self._verify_peripheral(svd_periph, src_periph, items)

        self._enrich_review_semantics(items, svd_device, chip_data)
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

        svd_canon_map = {}
        for rname, reg in svd_regs.items():
            svd_canon_map.setdefault(
                canonical_register_name(rname, pname), []).append((rname, reg))

        src_matched = set()
        for src_reg in src_regs:
            src_name = getattr(src_reg, "name", "") or ""
            matched_svd_name = None
            match_reason = "unmatched"
            match_score = 0.0

            # 精确匹配
            if src_name in svd_exact:
                matched_svd_name = src_name
                match_reason = "exact_name"
                match_score = 1.0
            else:
                # 模板归一化兜底（UARTn_CON ↔ UARTN_CON）
                cand = svd_norm_map.get(_normalize_name(src_name), [])
                if cand:
                    matched_svd_name = cand[0][0]
                    match_reason = "template_name"
                    match_score = 0.9
            if matched_svd_name is None:
                # 同外设前缀归一化（ADC/ADC_STS ↔ STS，CRC/CRC_CON ↔ CON）
                cand = svd_canon_map.get(canonical_register_name(src_name, pname), [])
                cand = [item for item in cand if item[0] not in src_matched]
                if cand:
                    matched_svd_name = cand[0][0]
                    match_reason = "peripheral_prefix"
                    match_score = 0.8

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
            before = len(items)
            self._verify_one_register(pname, src_reg, matched_svd_name, svd_reg, items)
            for item in items[before:]:
                item.match_reason = match_reason
                item.match_score = match_score

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
            match_reason = "unmatched"
            match_score = 0.0
            if src_fname and src_fname in svd_exact:
                matched = src_fname
                match_reason = "exact_name"
                match_score = 1.0
            else:
                cand = svd_by_pos.get((src_pos, src_w), [])
                if cand:
                    matched = cand[0]
                    match_reason = "bit_position"
                    match_score = 0.75

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
            before = len(items)
            self._verify_one_field(pname, reg_name, matched, svd_f, src_f, items)
            for item in items[before:]:
                item.match_reason = match_reason
                item.match_score = match_score

        for fname in svd_exact - matched_svd:
            items.append(VerifyItem(
                level="field", peripheral=pname, register=reg_name, field=fname,
                kind=VerifyKind.FIELD_MISSING_IN_SOURCE.value,
                detail=f"数据手册中未见位域 {fname}",
                severity=VerifySeverity.INFO.value, confidence="unknown"))

    @staticmethod
    def _enrich_review_semantics(
        items: list[VerifyItem], svd_device: Any, chip_data: Any,
    ) -> None:
        """补齐三类独立语义；不把 confidence/source weight 解释为准确率。"""
        source_entities = {}
        for pblk in getattr(chip_data, "peripherals", []) or []:
            pname = getattr(pblk, "name", "")
            source_entities[("peripheral", pname, "", "")] = pblk
            for reg in getattr(pblk, "registers", []) or []:
                rname = getattr(reg, "name", "")
                source_entities[("register", pname, rname, "")] = reg
                for fld in getattr(reg, "fields", []) or []:
                    source_entities[("field", pname, rname, getattr(fld, "name", ""))] = fld

        for item in items:
            key = (item.level, item.peripheral, item.register, item.field)
            entity = source_entities.get(key)
            if entity is None and item.level == "register":
                for (level, pname, rname, fname), candidate in source_entities.items():
                    if (level == "register" and pname == item.peripheral
                            and canonical_register_name(rname, pname)
                            == canonical_register_name(item.register, pname)):
                        entity = candidate
                        break
            if entity is None:
                item.source_authority = "svd_only" if item.kind == "missing_in_source" else "unmatched"
                item.parse_completeness = "unknown"
                item.manual_confirmation = "not_applicable"
                continue
            ref = dict(getattr(entity, "source_ref", {}) or {})
            source_file = ref.get("source_file", "")
            item.source_ref = ref
            item.source_authority = (
                getattr(entity, "source_authority", "")
                or source_authority_label(source_file)
            )
            item.parse_completeness = (
                getattr(entity, "parse_completeness", "")
                or parse_completeness(entity, item.level)
            )
            item.manual_confirmation = (
                getattr(entity, "manual_status", "") or "pending"
            ).replace("machine_extracted", "pending")
            item.multi_source_agreement = (
                getattr(entity, "multi_source_agreement", "") or "single_source"
            )
            item.object_id = getattr(entity, "object_id", "") or ""
            item.semantic_path = getattr(entity, "semantic_path", "") or ""
            item.aliases = list(getattr(entity, "aliases", []) or [])

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


def canonical_register_name(name: str, peripheral: str = "") -> str:
    """同外设内寄存器名归一化。

    只移除与外设名同源的前缀，避免 ADC_STS 与 CRC_STS 之类的跨模块误配：
    - ADC + ADC_STS -> STS
    - CRC + CRC_CON -> CON
    - ADC0 + ADC_STS -> STS
    - UART0 + UART0_CON -> CON
    - BTM + BTM_CON / BTMCON -> CON
    """
    raw = (name or "").upper().strip()
    raw = raw.split("@", 1)[0]
    raw = re.sub(r"[^A-Z0-9_]+", "", raw)
    if not raw:
        return ""
    p = re.sub(r"[^A-Z0-9]+", "", (peripheral or "").upper())
    p_base = re.sub(r"\d+$", "", p)
    suffix = raw
    if p_base and len(raw) > len(p_base):
        # 处理 ADC_STS、ADC0_STS、BTMCON 三种前缀写法。
        prefix_re = re.compile(r"^" + re.escape(p_base) + r"(?:\d+)?(?:_?)(.+)$")
        match = prefix_re.match(raw)
        if match and match.group(1):
            suffix = match.group(1)
    suffix = suffix.strip("_")
    suffix = re.sub(r"\d+", "N", suffix)
    return suffix or re.sub(r"\d+", "N", raw)


def normalize_register_name(name: str, peripheral: str = "") -> str:
    """公开测试入口：返回寄存器匹配键。"""
    return canonical_register_name(name, peripheral)


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
