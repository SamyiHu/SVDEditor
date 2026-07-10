"""
Datasheet 引脚分布表解析器 — 从「管脚资源列表」提取各封装的外设裁剪清单。

输入：Datasheet .docx（含「管脚资源列表」表格：每行一个引脚，列含
      3 个封装的引脚号 + GPIO名 + 各外设复用功能）。
输出：PackageTrimSpec —— 每个封装该删哪些外设/实例/位域。

裁剪规则（已与用户确认）：
1. 外设级：某外设列在某封装完全无引脚引出（含括号重映射）→ 删整个外设
2. 实例级：外设实例（UART1/TIM5）默认+重映射都无引出 → 删该实例
3. ADC 位域：AINx bit[0:19] 按封装最大 AIN 号收窄位宽（方式A）
4. LCD SEGR：SEG数量 = 保留的 SEGR 寄存器数（1:1）
5. 括号功能（如 (RxD2)）算引脚重映射，也算可用，不触发删除
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("svd_tool.datasource.PinoutParser")


# ════════════════════════════════════════════════════
# 裁剪清单数据结构
# ════════════════════════════════════════════════════

@dataclass
class PackageTrimSpec:
    """单个封装的裁剪规格。

    所有列表都是「相对母体（完整版）要删除/收窄的部分」。
    生成器据此从母体 SVD 裁剪出该封装的 SVD。
    """
    package_name: str                        # 如 "LQFP48" / "LQFP64" / "LQFP80"
    pin_count: int = 0                       # 引脚数
    # 规则1：整个外设删除（外设名匹配，如 "CMP"、"OP"）
    remove_peripherals: list[str] = field(default_factory=list)
    # 规则2：实例级删除（外设名前缀 → 要删的实例号列表）
    #   如 {"UART": [1,2]} 表示删 UART1、UART2
    #   匹配逻辑：外设名以 prefix 开头且后跟这些数字
    remove_instances: dict[str, list[int]] = field(default_factory=dict)
    # 规则3：ADC 位域收窄（外设名 → {寄存器名: {位域名: 新位宽}}）
    #   如 {"ADC": {"ADC_CFG": {"AINx": 14}}}  # 48脚 AIN0~13
    trim_fields: dict[str, dict[str, dict[str, int]]] = field(default_factory=dict)
    # 规则4：寄存器数组裁剪（外设名 → 保留的寄存器数）
    #   如 {"SEGR": 28}  # 48脚只保留 SEGR0~27
    trim_register_arrays: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "package_name": self.package_name,
            "pin_count": self.pin_count,
            "remove_peripherals": self.remove_peripherals,
            "remove_instances": self.remove_instances,
            "trim_fields": self.trim_fields,
            "trim_register_arrays": self.trim_register_arrays,
        }


@dataclass
class TrimAnalysisResult:
    """整份 Datasheet 的裁剪分析结果（多个封装）。"""
    packages: list[PackageTrimSpec] = field(default_factory=list)
    # 母体 = 引脚最全的封装（通常是最大封装）
    master_package: str = ""
    warnings: list[str] = field(default_factory=list)

    def get_package(self, name: str) -> Optional[PackageTrimSpec]:
        for p in self.packages:
            if p.package_name == name:
                return p
        return None


# ════════════════════════════════════════════════════
# 解析器
# ════════════════════════════════════════════════════

# 引脚表识别：表头含封装名 + GPIO + 外设列关键词
_PACKAGE_HEADER_KEYWORDS = ("LQFP", "QFN")
_PERIPH_COL_KEYWORDS = ("GPIO", "UART", "ADC", "PWM", "CMP", "OP", "LCD", "TWI", "SPI")


class DatasheetPinoutParser:
    """从 Datasheet docx 解析引脚表，输出各封装裁剪清单。

    优先用 pandoc→md 解析（与 TRM 解析器一致），回退 python-docx。
    """

    def parse_file(self, docx_path: str) -> TrimAnalysisResult:
        """解析 Datasheet，返回裁剪分析结果。"""
        result = TrimAnalysisResult()

        # 提取引脚表（python-docx 直接读，引脚表结构规整）
        try:
            rows, header = self._extract_pin_table_docx(docx_path)
        except Exception as e:
            logger.warning(f"python-docx 解析引脚表失败: {e}")
            result.warnings.append(f"无法提取引脚表: {e}")
            return result

        if not rows or not header:
            result.warnings.append("未找到「管脚资源列表」表格")
            return result

        return self._analyze(rows, header)

    # ---------- 引脚表提取 ----------

    def _extract_pin_table_docx(self, docx_path: str) -> tuple[list[list[str]], list[str]]:
        """用 python-docx 找到「管脚资源列表」表格并提取。

        Returns:
            (rows, header)：rows 为数据行（每行单元格文本列表），header 为表头行。
        """
        from docx import Document
        from docx.table import Table
        from docx.oxml.ns import qn

        doc = Document(docx_path)
        body = list(doc.element.body.iterchildren())

        # 找「管脚资源列表」段落
        target = "管脚资源列表"
        idx = None
        for i, e in enumerate(body):
            if e.tag == qn('w:p'):
                txt = "".join(t.text or "" for t in e.iter(qn('w:t')))
                if target in txt:
                    idx = i
                    break
        if idx is None:
            return [], []

        # 找其后的引脚表（大表：行数>30、列数>=10、表头含封装名）
        for j in range(idx + 1, min(idx + 120, len(body))):
            if body[j].tag == qn('w:tbl'):
                tbl = Table(body[j], doc)
                if len(tbl.rows) < 30 or len(tbl.columns) < 10:
                    continue
                rows = [[c.text.strip() for c in row.cells] for row in tbl.rows]
                header_text = " ".join(rows[0])
                if any(k in header_text for k in _PACKAGE_HEADER_KEYWORDS):
                    return rows[1:], rows[0]  # 去掉表头

        return [], []

    # ---------- 分析逻辑 ----------

    def _analyze(self, rows: list[list[str]], header: list[str]) -> TrimAnalysisResult:
        """根据引脚表数据 + 表头，分析各封装裁剪清单。"""
        result = TrimAnalysisResult()

        # 识别封装列（前几列是封装引脚号）
        pkg_cols = self._find_package_columns(header)
        if not pkg_cols:
            result.warnings.append("未识别到封装列（LQFP/QFN）")
            return result

        # 母体 = 引脚数最多的封装
        pkg_pin_counts = {}
        for pname, col in pkg_cols.items():
            count = sum(1 for row in rows if row[col] not in ("-", "", "—"))
            pkg_pin_counts[pname] = count
        result.master_package = max(pkg_pin_counts, key=pkg_pin_counts.get)

        # 识别各外设列
        periph_cols = self._find_periph_columns(header)

        # 对每个非母体封装，生成裁剪清单
        master_col = pkg_cols[result.master_package]
        for pname, col in pkg_cols.items():
            if pname == result.master_package:
                # 母体不裁剪（空清单）
                result.packages.append(PackageTrimSpec(
                    package_name=pname, pin_count=pkg_pin_counts[pname]))
                continue

            spec = self._build_trim_spec(
                pname, col, master_col, rows, periph_cols, pkg_pin_counts[pname])
            result.packages.append(spec)

        return result

    def _find_package_columns(self, header: list[str]) -> dict[str, int]:
        """识别封装列：表头含 LQFP/QFN + 数字 的列。返回 {封装名: 列索引}。"""
        pkgs = {}
        for i, cell in enumerate(header[:6]):  # 封装列通常在前 6 列
            cell_clean = cell.replace("\n", " ").strip()
            # 匹配 LQFP48 / QFN48 / LQFP64 等
            m = re.search(r'(LQFP|QFN)\s*(\d+)', cell_clean, re.IGNORECASE)
            if m:
                pin = m.group(2)
                name = f"{m.group(1).upper()}{pin}"
                if name not in pkgs:  # 同封装（LQFP48/QFN48）取首个
                    pkgs[name] = i
        return pkgs

    def _find_periph_columns(self, header: list[str]) -> dict[str, int]:
        """识别外设功能列。返回 {规范化列名: 列索引}。"""
        periph_cols = {}
        for i, cell in enumerate(header):
            c = cell.replace("\n", " ").strip().upper()
            # 直接匹配已知外设名
            for kw in ("GPIO", "UART", "TWI", "SPI", "LCD", "ADC",
                       "PWM", "CMP", "OP", "INT", "TK"):
                if c == kw or (kw in c and kw not in ("PWM",)):
                    periph_cols.setdefault(kw, i)
                    break
            # PWM 特殊：可能有 "PWM-8" 和 "PWM" 两列，取主 "PWM"
            if "PWM" in c and "PWM" not in periph_cols:
                periph_cols["PWM"] = i
        return periph_cols

    def _build_trim_spec(
        self, pkg_name: str, pkg_col: int, master_col: int,
        rows: list[list[str]], periph_cols: dict[str, int], pin_count: int,
    ) -> PackageTrimSpec:
        """为单个封装构建裁剪清单。"""
        spec = PackageTrimSpec(package_name=pkg_name, pin_count=pin_count)

        # ── 规则1：外设级（完全无引出 → 删整个外设）──
        # CMP、OP 这类：在某封装引脚表里该列全空
        for periph, ci in periph_cols.items():
            if periph in ("GPIO", "INT"):  # 这两个不按外设删
                continue
            pkg_has = any(
                row[pkg_col] not in ("-", "", "—") and ci < len(row)
                and row[ci] and row[ci] != "-"
                for row in rows
            )
            master_has = any(
                row[master_col] not in ("-", "", "—") and ci < len(row)
                and row[ci] and row[ci] != "-"
                for row in rows
            )
            # 母体有、本封装完全没有 → 删
            if master_has and not pkg_has:
                spec.remove_peripherals.append(periph)

        # ── 规则2：实例级（UART/TIM 等编号实例）──
        # 提取母体和本封装各有哪些实例号
        instance_periphs = {
            "UART": r"(?:RxD|TxD|SCIO|SCCLK)(\d)",
            "TIM": r"T(\d)PWM",
        }
        for prefix, pattern in instance_periphs.items():
            ci = periph_cols.get("PWM" if prefix == "TIM" else prefix)
            if ci is None:
                continue
            master_insts = self._extract_instances(rows, master_col, ci, pattern)
            pkg_insts = self._extract_instances(rows, pkg_col, ci, pattern)
            missing = sorted(master_insts - pkg_insts)
            if missing:
                spec.remove_instances[prefix] = missing

        # ── 规则3：ADC 位域收窄 ──
        adc_ci = periph_cols.get("ADC")
        if adc_ci is not None:
            master_ains = self._extract_instances(rows, master_col, adc_ci, r"AIN(\d+)")
            pkg_ains = self._extract_instances(rows, pkg_col, adc_ci, r"AIN(\d+)")
            if pkg_ains and master_ains:
                max_ain = max(pkg_ains)
                master_max = max(master_ains)
                if max_ain < master_max:
                    # 位宽 = max_ain + 1（AIN0~max_ain 共 max_ain+1 位）
                    spec.trim_fields["ADC"] = {
                        "ADC_CFG": {"AINx": max_ain + 1}
                    }

        # ── 规则4：LCD SEGR 寄存器裁剪 ──
        lcd_ci = periph_cols.get("LCD")
        if lcd_ci is not None:
            master_segs = self._extract_instances(rows, master_col, lcd_ci, r"SEG(\d+)")
            pkg_segs = self._extract_instances(rows, pkg_col, lcd_ci, r"SEG(\d+)")
            if pkg_segs and master_segs:
                # SEG 数量 = 保留的 SEGR 寄存器数（1:1）
                # 母体 SEG 数应等于 SEGR 寄存器总数
                spec.trim_register_arrays["SEGR"] = len(pkg_segs)

        return spec

    def _extract_instances(self, rows: list[list[str]], pkg_col: int,
                           func_col: int, pattern: str) -> set[int]:
        """提取某封装在某外设列的实例号集合。

        括号功能（重映射）也算：去掉括号后用同一正则匹配。
        """
        insts: set[int] = set()
        for row in rows:
            if pkg_col >= len(row) or row[pkg_col] in ("-", "", "—"):
                continue
            if func_col >= len(row):
                continue
            val = row[func_col]
            if not val or val == "-":
                continue
            # 括号内的也算（重映射），直接用正则匹配整个值（正则会忽略括号）
            for m in re.findall(pattern, val):
                try:
                    insts.add(int(m))
                except ValueError:
                    pass
        return insts
