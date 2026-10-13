"""H ↔ SVD 对应与覆盖率报告。

以 H 文件（外设命名权威锚点）为基准，对照当前 SVD（编辑器 DeviceInfo 或
SVDParser 解析结果），输出：
- 外设/寄存器/位域三层的 matched / unmatched 清单；
- header_coverage_percent（H 结构被 SVD 覆盖的比例，寄存器粒度为主指标）；
- trm_supplement_percent（H 骨架中获得 TRM 元数据补充的比例，来自融合层）；
- 逐项差异（外设名不同、寄存器缺失、偏移不同、位域缺失等）。

匹配规则与 header_trm_fusion 一致：外设精确名 → 前缀去实例号；
寄存器精确名 → 外设前缀剥离归一化；位域 (bit_offset, bit_width) → 名称。
"""
from __future__ import annotations

from typing import Any, Optional

from .header_parser import (
    HeaderModel, normalize_identifier, peripheral_root,
)


def _register_key(name: str, peripheral: str) -> str:
    from .svd_verifier import canonical_register_name
    return canonical_register_name(name, peripheral)


def _hex(value) -> int:
    try:
        text = str(value).strip().lower()
        if text.startswith("0x"):
            return int(text, 16)
        return int(text)
    except (ValueError, TypeError):
        return None


class HeaderSvdCoverage:
    """H 模型 ↔ SVD 设备的对照器。"""

    def __init__(self, header_model: HeaderModel, svd_device: Any):
        self.model = header_model
        self.svd = svd_device
        self.svd_periphs: dict[str, Any] = dict(
            getattr(svd_device, "peripherals", {}) or {})

    # ---------- 对外 ----------

    def build(self, trm_supplement_percent: Optional[float] = None) -> dict:
        diffs: list[dict] = []
        matched_periphs: list[str] = []
        unmatched_header: list[dict] = []
        unmatched_svd: list[dict] = []
        registers_matched = 0
        registers_total = 0
        fields_matched = 0
        fields_total = 0

        matched_svd_names: set[str] = set()
        for hperiph in self.model.peripherals:
            registers_total += len(hperiph.registers)
            fields_total += sum(len(r.fields) for r in hperiph.registers)
            pair = self._match_peripheral(hperiph.name)
            if pair is None:
                unmatched_header.append({
                    "peripheral": hperiph.name,
                    "base_address": f"0x{hperiph.base_address:X}",
                    "registers": len(hperiph.registers),
                })
                diffs.append({
                    "kind": "peripheral_missing_in_svd",
                    "peripheral": hperiph.name,
                    "detail": f"SVD 缺少外设 {hperiph.name}"
                              f"（H 基地址 0x{hperiph.base_address:X}）",
                    "header_line": hperiph.line_number,
                })
                continue
            svd_name, svd_periph = pair
            matched_svd_names.add(svd_name)
            matched_periphs.append(hperiph.name)
            if svd_name != hperiph.name:
                diffs.append({
                    "kind": "peripheral_name_diff",
                    "peripheral": hperiph.name,
                    "svd_peripheral": svd_name,
                    "detail": f"外设名不同：H={hperiph.name} SVD={svd_name}",
                })
            r_matched, f_matched = self._compare_registers(
                hperiph, svd_name, svd_periph, diffs)
            registers_matched += r_matched
            fields_matched += f_matched

        for svd_name in self.svd_periphs:
            if svd_name not in matched_svd_names and not self._claimed_by_root(svd_name):
                unmatched_svd.append({
                    "peripheral": svd_name,
                    "registers": len(getattr(self.svd_periphs[svd_name], "registers", {}) or {}),
                })
                diffs.append({
                    "kind": "peripheral_missing_in_header",
                    "peripheral": svd_name,
                    "detail": f"H 文件未见外设 {svd_name}（仅 SVD 存在）",
                })

        supplement = trm_supplement_percent
        if supplement is None:
            supplement = self._infer_supplement_percent()
        header_peripherals = len(self.model.peripherals)
        return {
            "mode": "header_vs_svd",
            "peripherals_in_header": header_peripherals,
            "peripherals_in_svd": len(self.svd_periphs),
            "matched_peripherals": matched_periphs,
            "unmatched_header_peripherals": unmatched_header,
            "unmatched_svd_peripherals": unmatched_svd,
            "registers_in_header": registers_total,
            "registers_matched": registers_matched,
            "fields_in_header": fields_total,
            "fields_matched": fields_matched,
            "header_coverage_percent": round(
                100.0 * registers_matched / registers_total, 2) if registers_total else 0.0,
            "peripheral_coverage_percent": round(
                100.0 * len(matched_periphs) / header_peripherals, 2) if header_peripherals else 0.0,
            "field_coverage_percent": round(
                100.0 * fields_matched / fields_total, 2) if fields_total else 0.0,
            "trm_supplement_percent": supplement,
            "unresolved_header_items": len(self.model.unresolved),
            "diffs": diffs,
            "diff_counts": _count_kinds(diffs),
        }

    # ---------- 匹配 ----------

    def _match_peripheral(self, header_name: str):
        if header_name in self.svd_periphs:
            return header_name, self.svd_periphs[header_name]
        root = peripheral_root(header_name)
        if root and root != header_name:
            for svd_name in self.svd_periphs:
                if svd_name == root or peripheral_root(svd_name) == root:
                    return svd_name, self.svd_periphs[svd_name]
        # 3) 下划线不敏感（RCC_AHB ↔ RCCAHB）：同外设不同拼写
        squashed = (root or header_name).replace("_", "")
        if squashed:
            for svd_name in self.svd_periphs:
                if peripheral_root(svd_name).replace("_", "") == squashed:
                    return svd_name, self.svd_periphs[svd_name]
        return None

    def _claimed_by_root(self, svd_name: str) -> bool:
        """SVD 外设虽非精确名匹配，但已作为某 H 外设的 root/去下划线匹配目标。"""
        svd_root = peripheral_root(svd_name)
        svd_squashed = svd_root.replace("_", "")
        for hperiph in self.model.peripherals:
            if svd_name == hperiph.name:
                return True
            root_h = peripheral_root(hperiph.name)
            if root_h and root_h != hperiph.name and peripheral_root(svd_name) == root_h:
                return True
            if root_h and root_h.replace("_", "") == svd_squashed:
                return True
        return False

    def _compare_registers(self, hperiph, svd_name: str, svd_periph, diffs: list[dict]):
        svd_regs: dict = dict(getattr(svd_periph, "registers", {}) or {})
        matched_svd_regs: set[str] = set()
        r_matched = 0
        f_matched = 0

        def match_reg(hreg):
            if hreg.name in svd_regs:
                return hreg.name, "exact_name"
            target = _register_key(hreg.name, hperiph.name)
            for svd_reg_name in svd_regs:
                if _register_key(svd_reg_name, svd_name) == target:
                    return svd_reg_name, "peripheral_prefix"
            return None, "unmatched"

        for hreg in hperiph.registers:
            svd_reg_name, reason = match_reg(hreg)
            if svd_reg_name is None:
                diffs.append({
                    "kind": "register_missing_in_svd",
                    "peripheral": hperiph.name,
                    "register": hreg.name,
                    "detail": f"SVD 缺少寄存器 {hperiph.name}/{hreg.name}"
                              f"（H 偏移 0x{hreg.offset:X}）",
                    "header_line": hreg.line_number,
                    "match_reason": reason,
                })
                continue
            matched_svd_regs.add(svd_reg_name)
            r_matched += 1
            if svd_reg_name != hreg.name:
                diffs.append({
                    "kind": "register_name_diff",
                    "peripheral": hperiph.name,
                    "register": hreg.name,
                    "svd_register": svd_reg_name,
                    "detail": f"寄存器名不同：H={hreg.name} SVD={svd_reg_name}",
                    "match_reason": reason,
                })
            svd_reg = svd_regs[svd_reg_name]
            f_matched += self._compare_fields(
                hperiph.name, hreg, svd_name, svd_reg_name, svd_reg, diffs)

        for svd_reg_name in svd_regs:
            if svd_reg_name in matched_svd_regs:
                continue
            diffs.append({
                "kind": "register_missing_in_header",
                "peripheral": svd_name,
                "register": svd_reg_name,
                "detail": f"H 文件未见寄存器 {svd_name}/{svd_reg_name}"
                          f"（仅 SVD 存在，offset={getattr(svd_regs[svd_reg_name], 'offset', '')}）",
            })
        return r_matched, f_matched

    def _compare_fields(self, hperiph_name, hreg, svd_pname, svd_rname, svd_reg, diffs: list[dict]):
        svd_fields: dict = dict(getattr(svd_reg, "fields", {}) or {})
        if not hreg.fields:
            return 0
        by_pos: dict[tuple[int, int], list[str]] = {}
        for fname, fld in svd_fields.items():
            pos = int(getattr(fld, "bit_offset", 0) or 0)
            width = max(int(getattr(fld, "bit_width", 1) or 1), 1)
            by_pos.setdefault((pos, width), []).append(fname)
        matched_svd_fields: set[str] = set()
        matched = 0

        for hfld in hreg.fields:
            hit = None
            reason = "unmatched"
            candidates = by_pos.get((hfld.bit_offset, max(hfld.bit_width, 1)), [])
            if candidates:
                for cand in candidates:
                    if cand not in matched_svd_fields:
                        hit = cand
                        reason = "bit_position"
                        break
            if hit is None and hfld.name in svd_fields and hfld.name not in matched_svd_fields:
                hit = hfld.name
                reason = "exact_name"
            if hit is None:
                diffs.append({
                    "kind": "field_missing_in_svd",
                    "peripheral": hperiph_name,
                    "register": hreg.name,
                    "field": hfld.name,
                    "detail": f"SVD 缺少位域 {hperiph_name}/{hreg.name}/{hfld.name}"
                              f"（H bit[{hfld.bit_offset}:{hfld.bit_offset + hfld.bit_width - 1}]）",
                    "header_line": hfld.line_number,
                    "match_reason": reason,
                })
                continue
            matched_svd_fields.add(hit)
            matched += 1
            if hit != hfld.name:
                diffs.append({
                    "kind": "field_name_diff",
                    "peripheral": hperiph_name,
                    "register": hreg.name,
                    "field": hfld.name,
                    "svd_field": hit,
                    "detail": f"位域名不同：H={hfld.name} SVD={hit}（bit {hfld.bit_offset}）",
                    "match_reason": reason,
                })

        for fname in svd_fields:
            if fname not in matched_svd_fields:
                diffs.append({
                    "kind": "field_missing_in_header",
                    "peripheral": svd_pname,
                    "register": svd_rname,
                    "field": fname,
                    "detail": f"H 文件未见位域 {svd_pname}/{svd_rname}/{fname}（仅 SVD 存在）",
                })
        return matched

    # ---------- 偏移/基地址核对（附加入 diffs） ----------

    def check_addresses(self, report: dict) -> dict:
        """对外设基地址与寄存器偏移做数值核对，追加到已有报告。"""
        diffs: list[dict] = report.get("diffs", [])
        for hperiph in self.model.peripherals:
            pair = self._match_peripheral(hperiph.name)
            if pair is None:
                continue
            svd_name, svd_periph = pair
            svd_base = _hex(getattr(svd_periph, "base_address", ""))
            if svd_base is not None and svd_base != hperiph.base_address:
                diffs.append({
                    "kind": "base_address_mismatch",
                    "peripheral": hperiph.name,
                    "detail": (f"基地址不符：H=0x{hperiph.base_address:X}"
                               f" SVD={getattr(svd_periph, 'base_address', '')}"),
                })
            svd_regs = getattr(svd_periph, "registers", {}) or {}
            for hreg in hperiph.registers:
                svd_reg = svd_regs.get(hreg.name)
                if svd_reg is None:
                    continue
                svd_off = _hex(getattr(svd_reg, "offset", ""))
                if svd_off is not None and svd_off != hreg.offset:
                    diffs.append({
                        "kind": "offset_mismatch",
                        "peripheral": hperiph.name,
                        "register": hreg.name,
                        "detail": (f"寄存器偏移不符：H=0x{hreg.offset:X}"
                                   f" SVD={getattr(svd_reg, 'offset', '')}"),
                        "header_line": hreg.line_number,
                    })
        report["diffs"] = diffs
        report["diff_counts"] = _count_kinds(diffs)
        return report

    # ---------- TRM 补充率（融合层未显式给出时按 source_ref 推断） ----------

    def _infer_supplement_percent(self) -> float:
        """无融合层结果时的兜底：纯 H 模型不含 TRM 元数据，补充率为 0。

        真实值由 build(trm_supplement_percent=...) 从 HeaderTrmFusion 覆盖率传入。
        """
        return 0.0


def _count_kinds(diffs: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in diffs:
        counts[item["kind"]] = counts.get(item["kind"], 0) + 1
    return counts


def build_header_svd_coverage(
    header_model: HeaderModel,
    svd_device: Any,
    trm_supplement_percent: Optional[float] = None,
) -> dict:
    """便捷入口：构建覆盖率报告（含地址核对）。"""
    coverage = HeaderSvdCoverage(header_model, svd_device)
    report = coverage.build(trm_supplement_percent)
    return coverage.check_addresses(report)


def coverage_to_markdown(report: dict) -> str:
    """把覆盖率报告渲染为 Markdown。"""
    lines = [
        "# H ↔ SVD 覆盖率报告",
        "",
        f"- 模式：{report.get('mode', '')}",
        f"- H 外设数：{report.get('peripherals_in_header', 0)}"
        f" / SVD 外设数：{report.get('peripherals_in_svd', 0)}"
        f" / 匹配：{len(report.get('matched_peripherals', []))}",
        f"- 寄存器：匹配 {report.get('registers_matched', 0)}"
        f" / H 总数 {report.get('registers_in_header', 0)}",
        f"- 位域：匹配 {report.get('fields_matched', 0)}"
        f" / H 总数 {report.get('fields_in_header', 0)}",
        f"- header_coverage_percent：{report.get('header_coverage_percent', 0)}%",
        f"- trm_supplement_percent：{report.get('trm_supplement_percent', 0)}%",
        f"- 未解析 H 条目：{report.get('unresolved_header_items', 0)}",
        "",
    ]
    unmatched_h = report.get("unmatched_header_peripherals", [])
    if unmatched_h:
        lines.append("## H 有、SVD 无的外设")
        lines += [f"- {p['peripheral']}（{p['registers']} 个寄存器，{p['base_address']}）"
                  for p in unmatched_h]
        lines.append("")
    unmatched_s = report.get("unmatched_svd_peripherals", [])
    if unmatched_s:
        lines.append("## SVD 有、H 无的外设")
        lines += [f"- {p['peripheral']}（{p['registers']} 个寄存器）" for p in unmatched_s]
        lines.append("")
    counts = report.get("diff_counts", {})
    if counts:
        lines.append("## 差异统计")
        lines += [f"- {kind}: {count}" for kind, count in sorted(counts.items())]
        lines.append("")
    diffs = report.get("diffs", [])
    if diffs:
        lines.append("## 差异明细（前 200 条）")
        lines.append("| 类型 | 外设 | 寄存器 | 位域 | 说明 | H 行号 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for item in diffs[:200]:
            lines.append("| {} | {} | {} | {} | {} | {} |".format(
                item.get("kind", ""), item.get("peripheral", ""),
                item.get("register", "") or item.get("svd_register", ""),
                item.get("field", "") or item.get("svd_field", ""),
                item.get("detail", ""), item.get("header_line", "") or "-"))
    return "\n".join(lines)
