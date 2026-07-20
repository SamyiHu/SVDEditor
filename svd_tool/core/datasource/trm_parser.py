"""
TRM（技术参考手册）Word 文档解析器。

针对 SC32L14T/14G 等国产 MCU TRM 的三段式结构：
  1. 寄存器映射表：含 "XXX基地址：0x..." 行 + 后续表格行 | REG | offset | 读写 | 说明 | 复位值 | 上电初始 |
     → 提取外设（基地址）+ 寄存器（名/偏移/访问/复位值）
  2. 位域详表：在 #### 寄存器标题之后，表头 | 位编号 | 位符号 | 说明 |
     → 提取位域（位范围/符号/说明）
  3. 归一化匹配：寄存器名归一化（PWM0_DTx → PWMn_DTn）后与位域标题匹配

两条解析路径：
  - 主路径（推荐，最准）：docx → pandoc → markdown → 正则。pandoc 对 Word 表格转 md 忠实。
  - 回退路径（无 pandoc）：python-docx 直接读表格。覆盖寄存器映射表 + 位域详表。

输出：parser.models.PeripheralBlock / Register / BitField（与 Parser 包模型一致）。

设计依据：参考用户已验证跑通的 gen_svd_excel.py 脚本逻辑。
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("svd_tool.datasource.TRMParser")


# ════════════════════════════════════════════════════
# 正则与常量（与 gen_svd_excel.py 保持一致）
# ════════════════════════════════════════════════════

# 外设基地址行：例如 "RCC基地址：0x40021000" / "| GPIOA基地址: 0x40010800"
_BASE_ADDR_RE = re.compile(r'(.+?)基地址[：:]\s*(0x[0-9A-Fa-f_]+)')

# 寄存器名：大写字母+下划线/数字（长度≥2）
_REG_NAME_RE = re.compile(r'\b([A-Z][A-Z0-9_]{1,})\b')

# 标题中的寄存器名（含字母小写变体，如 ADC_CON）
_REG_NAME_HDR_RE = re.compile(r'[A-Z][A-Za-z0-9_]{1,}')

# 表格分隔行（全是 |:-= 空白）
_SEP_LINE_RE = re.compile(r'^[\s\|:\-=+]+$')

# HTML 单元格：pandoc 把带合并单元格的 docx 表格转成 HTML <td>...</td>
_TD_RE = re.compile(r'<td[^>]*>(.*?)</td>', re.IGNORECASE | re.DOTALL)
# HTML 标签清理
_TAG_RE = re.compile(r'<[^>]+>')

# 跳过的位域占位名
_SKIP_FIELD_NAMES = {
    "", "-", "—", "--", "/", "reserved", "reserve", "rsvd", "rsv", "rv",
    "保留", "未使用", "未定义", "保留位", "nc",
}


def _normalize_reg(name: str) -> str:
    """寄存器名归一化：数字→n、小写x变量→n、端口字母(PX/PA..)→n。

    使通配符实例（PWM0_DTx）能匹配模板（PWMn_DTn）。
    """
    if not name:
        return ""
    r = name.upper().strip()
    r = re.sub(r'\d+', 'N', r)                          # 数字 → N
    r = re.sub(r'(?<=[A-Z])X(?![A-Z0-9])', 'N', r)      # 大写X变量 → N
    r = re.sub(r'(?<=P)[XABCDE](?=[A-Z_]|$)', 'n', r)   # 端口字母 PX→Pn
    return r


def _norm_hex(s: str) -> str:
    """归一化十六进制：去下划线、补 0x、大写。"""
    if not s:
        return ""
    s = str(s).strip().replace("_", "").replace(" ", "")
    if not s:
        return ""
    if s[:2].lower() == "0x":
        try:
            return f"0x{int(s[2:], 16):X}"
        except ValueError:
            return s
    if s.isdigit():
        return f"0x{int(s):X}"
    return s


def _parse_bit_range(raw: str) -> Optional[tuple[int, int]]:
    """解析位范围 → (lo, hi)。支持 15:0 / 15~0 / 7 / [7:4]。

    返回 (最低位, 最高位)；失败返回 None。
    """
    if not raw:
        return None
    br = raw.replace("\\~", "~").replace("~", ":").strip()
    # [7:4] / 7:4
    m = re.match(r'\[?\s*(\d{1,2})\s*[:：]\s*(\d{1,2})\s*\]?', br)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return (min(a, b), max(a, b))
    # 21~20 → 上面已替换为 21:20
    m = re.match(r'\[?\s*(\d{1,2})\s*\]?', br)
    if m:
        v = int(m.group(1))
        return (v, v)
    return None


def _extract_cells(line: str) -> tuple[list[str], bool]:
    """从一行中提取表格单元格。

    支持两种格式：
    - markdown 管道表：| a | b | c |  → ['a','b','c']
    - HTML 表格：<td>a</td><td>b</td> → ['a','b']

    Returns:
        (cells, is_html)：cells 为去空后的单元格文本列表；is_html 标记是否为 HTML 格式。
        非表格行返回 ([], False)。
    """
    # HTML 格式优先（pandoc 对含合并单元格的表回退到 HTML）
    if "<td" in line.lower():
        tds = _TD_RE.findall(line)
        cells = []
        for td in tds:
            txt = _TAG_RE.sub('', td).strip()
            cells.append(txt)
        return cells, True
    # markdown 管道表
    if line.strip().startswith("|"):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        cells = [c for c in cells if c != ""]
        return cells, False
    return [], False


def _is_table_row(line: str) -> bool:
    """该行是否为表格数据行（markdown 或 HTML）。"""
    s = line.strip()
    if not s:
        return False
    if "<td" in s.lower():
        return True
    return s.startswith("|")


def _extract_html_row_lines(md_text: str) -> list[str]:
    """把 HTML 表格的多个 <td> 行合并为逻辑行。

    pandoc 输出 HTML 表格时，每个 <td> 常独占一行（或多行）。
    把连续的 <tr>...</tr> 之间的内容按 <tr> 切分成逻辑行，每个 <tr> 内的所有 <td> 合并。
    返回处理后的行列表，每行是一个完整表格行（HTML 或 markdown 原样）。
    """
    out: list[str] = []
    # 用 <tr> 作为逻辑行边界，把 <tr> 与下一个 </tr> 之间的所有文本压成一行
    # 非 HTML 行原样保留
    buf: list[str] = []
    in_tr = False
    for raw in md_text.splitlines():
        low = raw.lower()
        if "<tr" in low:
            in_tr = True
            buf = [raw]
        elif "</tr>" in low:
            buf.append(raw)
            out.append(" ".join(b.strip() for b in buf))
            buf = []
            in_tr = False
        elif in_tr:
            buf.append(raw)
        else:
            out.append(raw)
    if buf:
        out.append(" ".join(b.strip() for b in buf))
    return out


# ════════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════════

def _parse_section_instances(section_title: str):
    """解析 ## 章节标题的实例号列表。
    "UART0/1/3/4/5寄存器" → {0,1,3,4,5}; "UART2寄存器" → {2}; "存储" → None
    """
    import re
    m = re.search(r'([A-Z][A-Za-z]*)\s*([\d/\-,～~]+)', section_title)
    if not m:
        return None
    nums_str = m.group(2)
    insts = set()
    for part in re.split(r'[/,\-～~]', nums_str):
        part = part.strip()
        if part.isdigit():
            insts.add(int(part))
        rng = re.match(r'(\d+)\s*[～~\-]\s*(\d+)', part)
        if rng:
            insts.update(range(int(rng.group(1)), int(rng.group(2)) + 1))
    return insts if insts else None


def _reg_instance_in_set(reg_name, inst_set):
    """寄存器名中的实例号是否在集合中。
    UART0_CON → {0,1,3,4,5} → True; IAP_KEY → True
    """
    import re
    nums = re.findall(r'\d+', reg_name)
    if not nums:
        return True
    return int(nums[0]) in inst_set
class TRMWordParser:
    """TRM Word 文档解析器。

    优先用 pandoc 把 docx 转 markdown 再正则解析（与已验证脚本一致，最准）；
    若 pandoc 不可用，回退到 python-docx 直接解析表格。
    """

    def parse_file(self, docx_path: str) -> list:
        """解析单个 docx，返回 list[PeripheralBlock]。

        返回的元素是 parser.models.PeripheralBlock（延迟 import 避免硬依赖）。
        """
        docx_path = str(docx_path)
        if not os.path.isfile(docx_path):
            return []

        # 主路径：pandoc → md
        md_text = self._docx_to_markdown(docx_path)
        if md_text:
            peripherals, registers, bitfields = self._parse_markdown(md_text)
        else:
            # 回退：python-docx
            peripherals, registers, bitfields = self._parse_docx_direct(docx_path)

        if not peripherals and not registers:
            return []

        # 寄存器↔位域归一化匹配
        self._match_bitfields(registers, bitfields)

        return self._assemble(peripherals, registers)

    def parse_dir(self, dir_path: str) -> list:
        """解析目录下所有 docx，合并结果。"""
        result = []
        for f in sorted(Path(dir_path).glob("*.docx")):
            result.extend(self.parse_file(str(f)))
        return result

    # ════════════════════════════════════════════════════
    # 路径 1：pandoc → markdown → 正则（与 gen_svd_excel.py 一致）
    # ════════════════════════════════════════════════════

    def _docx_to_markdown(self, docx_path: str) -> Optional[str]:
        """用 pandoc 把 docx 转 markdown。pandoc 不可用时返回 None。"""
        pandoc = shutil.which("pandoc")
        if not pandoc:
            logger.info("pandoc 不可用，TRM 解析回退到 python-docx 直接读表格")
            return None
        try:
            proc = subprocess.run(
                [pandoc, "--track-changes=all", docx_path, "-t", "gfm"],
                capture_output=True, text=True, encoding="utf-8",
                timeout=120,
            )
            if proc.returncode != 0:
                logger.warning(f"pandoc 转换失败 (rc={proc.returncode}): {proc.stderr[:200]}")
                return None
            return proc.stdout
        except subprocess.TimeoutExpired:
            logger.warning("pandoc 转换超时（>120s）")
            return None
        except Exception as e:
            logger.warning(f"pandoc 调用异常: {e}")
            return None

    def _parse_markdown(self, md_text: str) -> tuple[list, list, list]:
        """解析 markdown 文本，返回 (peripherals, registers, bitfields)。

        同时支持 pandoc 的两种输出：
        - markdown 管道表（| a | b |）—— 简单表格
        - HTML 表格（<td>a</td>）—— 含合并单元格的复杂表格（pandoc 对 gfm 回退到 HTML）

        先用 _extract_html_row_lines 把 HTML 表格的多行 <td> 按 <tr> 合并成逻辑行，
        再统一用 _extract_cells 取单元格，使后续逻辑与格式无关。
        """
        # 预处理：合并 HTML 表格行
        lines = _extract_html_row_lines(md_text)
        total = len(lines)
        peripherals: list[dict] = []
        registers: list[dict] = []
        bitfields: list[dict] = []
        current_chapter = ""
        current_reg_header = ""

        # ── 第 1 遍：外设 + 寄存器（寄存器映射表）──
        i = 0
        while i < total:
            line = lines[i].strip()
            # 跟踪章节标题
            if line.startswith("# ") and "目录" not in line:
                current_chapter = re.sub(r'\{.*?\}', '', line[2:]).strip()

            m = _BASE_ADDR_RE.search(line)
            if m:
                # 外设名清洗：去 HTML 标签残留
                peri_name = _TAG_RE.sub('', m.group(1)).strip().lstrip("| ").strip()
                base_addr = m.group(2).strip()
                if not any(p["base_addr"] == base_addr and p["name"] == peri_name for p in peripherals):
                    peripherals.append({"name": peri_name, "base_addr": base_addr, "chapter": current_chapter})

                # 向前扫描收集该外设寄存器
                j = i + 1
                while j < total:
                    jline = lines[j].strip()
                    if _BASE_ADDR_RE.search(jline) or jline.startswith("#"):
                        break
                    # 表格数据行（HTML 或 markdown）
                    if not _is_table_row(jline):
                        j += 1
                        continue
                    cells, _is_html = _extract_cells(jline)
                    if len(cells) < 2:
                        j += 1
                        continue
                    if "0x" not in " ".join(cells):
                        j += 1
                        continue
                    reg_name = cells[0]
                    if reg_name in ("寄存器", "register", "") or "偏移" in reg_name:
                        j += 1
                        continue
                    if not re.match(r'^[A-Za-z][A-Za-z0-9_]*', reg_name):
                        j += 1
                        continue
                    # offset 在 cells 中找第一个 0x 开头的小值
                    offset = ""
                    for c in cells[1:]:
                        if re.match(r'^0x[0-9A-Fa-f_]+$', c):
                            offset = c
                            break
                    if not offset:
                        j += 1
                        continue
                    # 其余列按位置取（访问/说明/复位值），容忍列数变化
                    rest = [c for c in cells[1:] if c != offset]
                    access = rest[0] if len(rest) > 0 else ""
                    desc = rest[1] if len(rest) > 1 else ""
                    reset = rest[2] if len(rest) > 2 else ""
                    abs_addr = self._compute_abs_addr(base_addr, offset)
                    registers.append({
                        "peripheral": peri_name, "base_addr": base_addr,
                        "name": reg_name, "offset": offset, "abs_addr": abs_addr,
                        "access": access, "desc": desc, "reset": reset,
                        "chapter": current_chapter,
                    })
                    j += 1
                i = j
                continue
            i += 1

        # 寄存器去重
        seen = set()
        unique_regs = []
        for r in registers:
            key = (r["peripheral"], r["base_addr"], r["name"], r["offset"])
            if key not in seen:
                seen.add(key)
                unique_regs.append(r)

        # ── 残余扫描：无归属外设的寄存器（无"基地址"行的章节，如 OPT）──
        # 先收集已有寄存器名用于去重
        captured_names = {r["name"] for r in unique_regs}
        orphan_regs = self._collect_orphan_registers(lines, captured_names)
        if orphan_regs:
            # 按章节分组
            chapters: dict[str, list] = {}
            for orr in orphan_regs:
                ch = orr.get("chapter", "Other") or "Other"
                if ch not in chapters:
                    chapters[ch] = []
                chapters[ch].append(orr)
            for ch, oregs in chapters.items():
                if not oregs:
                    continue
                pname = self._chapter_to_periph_name(ch, oregs)
                # 基址：全部绝对地址的最小值向下取整到 0x10 边界
                base = self._infer_base_from_registers(oregs)
                for orr in oregs:
                    abs_addr = orr.get("abs_addr", "") or orr.get("offset", "")
                    # 计算相对偏移 = 绝对地址 - 基址
                    rel_offset = self._compute_rel_offset(abs_addr, base)
                    key = (pname, base, orr["name"], rel_offset)
                    if key not in seen:
                        seen.add(key)
                        if pname not in [p["name"] for p in peripherals]:
                            peripherals.append({"name": pname, "base_addr": base, "chapter": ch})
                        unique_regs.append({
                            "peripheral": pname, "base_addr": base,
                            "name": orr["name"], "offset": rel_offset,
                            "abs_addr": abs_addr,
                            "access": orr.get("access", ""), "desc": orr.get("desc", ""),
                            "reset": orr.get("reset", ""), "chapter": ch,
                        })

        # ── 第 2 遍：位域（#### 寄存器标题 + 位域详表）──
        i = 0
        current_section_insts = None  # ## 章节的实例号集合
        # 寄存器详情表里读到的 access（比映射表准），用于覆盖
        access_override: dict[str, str] = {}
        current_reg_header = ""
        while i < total:
            line = lines[i].strip()
            if line.startswith("#### "):
                current_reg_header = re.sub(r'\{.*?\}', '', line[5:]).strip()
                hdr_matches = _REG_NAME_HDR_RE.findall(current_reg_header)
                if not any("_" in m for m in hdr_matches):
                    for k in range(i + 1, min(i + 12, total)):
                        kline = lines[k].strip()
                        tbl_matches = re.findall(r'[A-Z][A-Z0-9_]{3,}', kline)
                        if tbl_matches:
                            best = max(tbl_matches, key=len)
                            if "_" in best:
                                current_reg_header += " " + best
                                break

            # 寄存器详情表（非位域表）：| REG | 读/写 | 说明 | 复位值 |
            # 比寄存器映射表更准确（如 SYST_CALIB 这里标只读，映射表标读/写）
            is_reg_detail = _is_table_row(line) and "寄存器" in line and "读/写" in line and "说明" in line
            if is_reg_detail:
                j = i + 1
                while j < total:
                    jline = lines[j].rstrip()
                    if _SEP_LINE_RE.match(jline) or not jline.strip():
                        j += 1; continue
                    if not _is_table_row(jline):
                        break
                    cells, _ = _extract_cells(jline)
                    if len(cells) >= 4 and re.match(r'^[A-Z]', cells[0]):
                        reg_name = cells[0]
                        acc = cells[1] if len(cells) > 1 else ""
                        if acc and acc != '读/写':
                            access_override[reg_name] = acc
                    j += 1
                i = j
                continue

            # 位域表头：含「位编号」+「位符号」
            line_text = _TAG_RE.sub('', line) if "<td" in line.lower() else line
            is_bf_header = "位编号" in line_text and "位符号" in line_text
            if is_bf_header:
                j = i + 1
                while j < total:
                    jline = lines[j].rstrip()
                    if _SEP_LINE_RE.match(jline) or not jline.strip():
                        j += 1
                        continue
                    jline_text = _TAG_RE.sub('', jline) if "<td" in jline.lower() else jline
                    if "位编号" in jline_text and "位符号" in jline_text:
                        break
                    if jline_text.strip().startswith("#"):
                        break
                    if not _is_table_row(jline):
                        # 空格对齐格式（无 | 也无 <td>）：按 2+ 空格分
                        cells = re.split(r'\s{2,}', jline_text.strip())
                        cells = [c.strip() for c in cells if c.strip()]
                    else:
                        cells, _ = _extract_cells(jline)

                    if len(cells) >= 3:
                        bit_range_raw = cells[0]
                        bit_symbol = cells[1]
                        if bit_range_raw in ("位编号", "") or _SEP_LINE_RE.match(bit_range_raw):
                            j += 1
                            continue
                        hdr_matches = _REG_NAME_HDR_RE.findall(current_reg_header)
                        if hdr_matches:
                            underscored = [m for m in hdr_matches if "_" in m]
                            matched_reg = max(underscored, key=len) if underscored else max(hdr_matches, key=len)
                        else:
                            matched_reg = ""
                        rng = _parse_bit_range(bit_range_raw)
                        lo, hi = rng if rng else (None, None)
                        bitfields.append({
                            "reg_header": current_reg_header,
                            "matched_reg": matched_reg,
                            "bit_range": bit_range_raw,
                            "lo": lo, "hi": hi,
                            "symbol": bit_symbol.replace("\\[", "[").replace("\\]", "]"),
                            "desc": cells[2],
                        })
                    j += 1
                i = j
                continue
            i += 1

        # 应用寄存器详情表的 access 覆盖（比映射表准）
        for r in unique_regs:
            if r["name"] in access_override:
                r["access"] = access_override[r["name"]]

        return peripherals, unique_regs, bitfields

    # ════════════════════════════════════════════════════
    # 路径 2：python-docx 直接解析（pandoc 不可用时的回退）
    # ════════════════════════════════════════════════════

    def _parse_docx_direct(self, docx_path: str) -> tuple[list, list, list]:
        """无 pandoc 时，用 python-docx 直接读表格。

        同样识别：寄存器映射表（含"基地址"行 + |REG|offset|...|）+ 位域详表（|位编号|位符号|说明|）。
        """
        try:
            from docx import Document
            from docx.table import Table
            from docx.oxml.ns import qn
        except ImportError:
            logger.warning("python-docx 未安装，无法回退解析 TRM")
            return [], [], []

        doc = Document(docx_path)
        body_elems = list(doc.element.body.iterchildren())

        peripherals: list[dict] = []
        registers: list[dict] = []
        bitfields: list[dict] = []
        current_peri: dict = None   # 当前正在收集寄存器的外设 {name, base_addr, chapter}
        current_reg_header = ""

        # 遍历 body 元素（段落 w:p 与表格 w:tbl 交替）
        for elem in body_elems:
            if elem.tag == qn('w:p'):
                text = self._para_text(elem)
                # 外设基地址行
                m = _BASE_ADDR_RE.search(text)
                if m:
                    peri_name = m.group(1).strip().lstrip("| ").strip()
                    base_addr = m.group(2).strip()
                    if not any(p["base_addr"] == base_addr and p["name"] == peri_name for p in peripherals):
                        peripherals.append({"name": peri_name, "base_addr": base_addr, "chapter": ""})
                    current_peri = {"name": peri_name, "base_addr": base_addr}
                # 寄存器标题（soc1-4 之类样式，或含寄存器名模式）→ 记录为当前位域表归属
                reg_matches = _REG_NAME_HDR_RE.findall(text)
                if reg_matches and any("_" in x for x in reg_matches):
                    underscored = [x for x in reg_matches if "_" in x]
                    current_reg_header = max(underscored, key=len) if underscored else current_reg_header

            elif elem.tag == qn('w:tbl'):
                tbl = Table(elem, doc)
                rows = [[c.text.strip() for c in row.cells] for row in tbl.rows]
                if not rows:
                    continue

                # 判断是否为「寄存器映射表」：首行含"寄存器"+"偏移"或"复位"
                header = " ".join(rows[0])
                is_reg_map = any(k in header for k in ("寄存器", "register")) and \
                             any(k in header for k in ("偏移", "offset", "复位", "reset", "地址", "addr"))
                # 判断是否为「位域详表」：首行含"位编号"+"位符号"
                is_bf_table = "位编号" in header and "位符号" in header

                if is_reg_map:
                    # 寄存器映射表：每行一个寄存器
                    for row in rows[1:]:
                        if len(row) < 2:
                            continue
                        reg_name = row[0]
                        if reg_name in ("寄存器", "register", ""):
                            continue
                        if not re.match(r'^[A-Za-z][A-Za-z0-9_]*', reg_name):
                            continue
                        offset = next((c for c in row[1:] if re.match(r'^0x[0-9A-Fa-f_]+', c)), "")
                        if not offset:
                            continue
                        # 访问/说明/复位值按列位置取（容忍列数变化）
                        access = ""
                        desc = ""
                        reset = ""
                        if current_peri:
                            base = current_peri["base_addr"]
                        elif peripherals:
                            base = peripherals[-1]["base_addr"]
                        else:
                            base = "0x40000000"
                        # 尝试按表头列名定位
                        hdr_cells = rows[0]
                        for ci, hc in enumerate(hdr_cells):
                            if ci < len(row):
                                if any(k in hc for k in ("读写", "访问", "access", "类型")):
                                    access = row[ci]
                                elif any(k in hc for k in ("说明", "描述", "desc")):
                                    desc = row[ci]
                                elif any(k in hc for k in ("复位", "reset", "默认")):
                                    reset = row[ci]
                        registers.append({
                            "peripheral": current_peri["name"] if current_peri else (peripherals[-1]["name"] if peripherals else "Unknown"),
                            "base_addr": base,
                            "name": reg_name, "offset": offset,
                            "abs_addr": self._compute_abs_addr(base, offset),
                            "access": access, "desc": desc, "reset": reset,
                            "chapter": "",
                        })

                elif is_bf_table:
                    # 位域详表：每行一个位域
                    # 定位列
                    hdr_cells = rows[0]
                    bit_col = next((ci for ci, hc in enumerate(hdr_cells) if any(k in hc for k in ("位编号", "bit", "位"))), 0)
                    sym_col = next((ci for ci, hc in enumerate(hdr_cells) if any(k in hc for k in ("位符号", "符号", "symbol", "名称"))), 1)
                    desc_col = next((ci for ci, hc in enumerate(hdr_cells) if any(k in hc for k in ("说明", "描述", "desc"))), 2)
                    for row in rows[1:]:
                        if len(row) <= max(bit_col, sym_col, desc_col):
                            continue
                        bit_range_raw = row[bit_col]
                        symbol = row[sym_col]
                        if symbol.strip().lower() in _SKIP_FIELD_NAMES or not symbol.strip():
                            continue
                        rng = _parse_bit_range(bit_range_raw)
                        lo, hi = rng if rng else (None, None)
                        bitfields.append({
                            "reg_header": current_reg_header,
                            "matched_reg": current_reg_header,
                            "bit_range": bit_range_raw,
                            "lo": lo, "hi": hi,
                            "symbol": symbol,
                            "desc": row[desc_col] if desc_col < len(row) else "",
                        })

        return peripherals, registers, bitfields

    @staticmethod
    def _para_text(para_elem) -> str:
        """提取 w:p 元素的纯文本。"""
        from docx.oxml.ns import qn
        return "".join(t.text or "" for t in para_elem.iter(qn('w:t')))

    # ════════════════════════════════════════════════════
    # 寄存器 ↔ 位域 匹配（归一化）
    # ════════════════════════════════════════════════════

    def _match_bitfields(self, registers: list[dict], bitfields: list[dict]):
        """把位域挂到正确的寄存器上。

        匹配策略（修复归一化误并 APB0_CFG/APB1_CFG 的 bug）：
        1. 精确名匹配优先：位域标题里提取的寄存器名 == 寄存器映射表里的实例名
           （如 "APB0_CFG" 位域表 → APB0_CFG 寄存器，绝不混入 APB1_CFG）
        2. 归一化兜底：仅当精确名无匹配时（标题用了通配符 UARTn_CON），
           才按归一化匹配。但若归一化桶里有多个不同实例，把位域挂到
           「标题能确定的那个实例」或全部实例（通配符场景）。

        registers[i]['bitfields'] = [匹配到的位域]
        """
        # 寄存器名索引
        reg_by_name: dict[str, list[dict]] = {}
        for reg in registers:
            reg_by_name.setdefault(reg["name"], []).append(reg)
        # 归一化索引：norm → [reg_name, ...]（记录不同的实例名）
        norm_to_names: dict[str, list[str]] = {}
        for rname in reg_by_name:
            norm_to_names.setdefault(_normalize_reg(rname), [])
            if rname not in norm_to_names[_normalize_reg(rname)]:
                norm_to_names[_normalize_reg(rname)].append(rname)

        # 初始化每个寄存器的位域列表
        for reg in registers:
            reg["bitfields"] = []

        # 位域按精确 matched_reg 分组（同一条位域表的位域归一组）
        # bf["matched_reg"] 是位域表标题里提取的寄存器名
        # 关键：同一位域表的多个位域必须挂到同一个寄存器，不能拆散
        bf_groups: dict[str, list[dict]] = {}  # matched_reg → [位域]
        for bf in bitfields:
            key = bf["matched_reg"]
            bf_groups.setdefault(key, []).append(bf)

        for matched_reg, bfs in bf_groups.items():
            # 策略1：精确名匹配
            if matched_reg in reg_by_name:
                candidates = reg_by_name[matched_reg]
                # 按章节实例号过滤
                sec = bfs[0].get("section_insts") if bfs else None
                if sec is not None:
                    candidates = [r for r in candidates if _reg_instance_in_set(r["name"], sec)]
                for reg in candidates:
                    reg["bitfields"].extend(bfs)
                continue
            # 策略2：归一化兜底（标题用了通配符，如 UARTn_CON）
            norm = _normalize_reg(matched_reg)
            candidate_names = norm_to_names.get(norm, [])
            sec = bfs[0].get("section_insts") if bfs else None
            if sec is not None:
                candidate_names = [cn for cn in candidate_names if _reg_instance_in_set(cn, sec)]
            if len(candidate_names) == 1:
                for reg in reg_by_name[candidate_names[0]]:
                    reg["bitfields"].extend(bfs)
            elif len(candidate_names) > 1:
                for cname in candidate_names:
                    for reg in reg_by_name[cname]:
                        reg["bitfields"].extend(bfs)

    # ════════════════════════════════════════════════════
    # 残余寄存器收集（无"基地址"行的外设）
    # ════════════════════════════════════════════════════

    def _collect_orphan_registers(self, lines: list[str], already_captured: set) -> list[dict]:
        """收集不在任何"基地址"块内的寄存器表行，且此前未被捕获。
        如 OPT（选项字节区域）的 OPINX/OPREG 直接写绝对地址。
        跳过间接寻址（含@的）和已捕获的重复项。
        """
        orphans: list[dict] = []
        chapter = ""
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("# ") and "目录" not in line:
                chapter = _TAG_RE.sub('', line[2:]).strip()
            elif line.startswith("## ") and "目录" not in line:
                # 二级标题也跟踪（如 "## 选项字节区域（Customer Option）"）
                new_ch = _TAG_RE.sub('', line[3:]).strip()
                if new_ch:
                    chapter = new_ch
            # 跳过已有"基地址"的块
            if _BASE_ADDR_RE.search(line):
                j = i + 1
                while j < len(lines):
                    jl = lines[j].strip()
                    if _BASE_ADDR_RE.search(jl) or jl.startswith("#"):
                        break
                    j += 1
                i = j - 1
            elif _is_table_row(line) and "0x" in line:
                cells, _ = _extract_cells(line)
                if len(cells) < 2:
                    i += 1; continue
                reg_name = cells[0].strip()
                reg_name = re.sub(r'@\s*0x[0-9A-Fa-f]+', '', reg_name).strip()
                if reg_name in ("寄存器", "register", "") or not re.match(r'^[A-Za-z][A-Za-z0-9_]*', reg_name):
                    i += 1; continue
                if reg_name in already_captured:
                    i += 1; continue
                # 只收集有 0x4xxxxxxx 范围绝对地址的行
                addr = ""
                all_text = " ".join(cells)
                if '@' in all_text:
                    i += 1; continue  # 跳过间接寻址
                for c in cells[1:]:
                    m = re.match(r'^(0x[0-9A-Fa-f_]+)$', c.strip())
                    if m:
                        try:
                            val = int(m.group(1).replace('_', ''), 16)
                            if val >= 0x40000000:
                                addr = m.group(1); break
                        except ValueError: pass
                if not addr:
                    i += 1; continue
                orphans.append({
                    "name": reg_name, "offset": addr, "abs_addr": addr,
                    "chapter": chapter, "desc": "", "access": "", "reset": "",
                })
                already_captured.add(reg_name)
            i += 1
        return orphans

    def _chapter_to_periph_name(self, chapter: str, oregs: list[dict]) -> str:
        """从章节标题和寄存器名推外设名。"""
        # 特殊：章节含 Option → OPT（选项字节）
        if re.search(r'option', chapter, re.IGNORECASE):
            return "OPT"
        # 优先用寄存器名前缀（如 OPINX/OPREG → OP，但注意和已有外设不冲突）
        names = [r["name"] for r in oregs if r.get("name")]
        if names:
            common = names[0]
            for n in names[1:]:
                while not n.startswith(common) and common:
                    common = common[:-1]
            common = common.rstrip('_')
            if len(common) >= 2:
                # 若推断结果和已有外设同名但基址不同，用章节名
                return common
        m = re.search(r'[（(]([^）)]*)[）)]', chapter)
        if m:
            eng = m.group(1)
            abbr = ''.join(w[0].upper() for w in eng.split() if w)
            if abbr: return abbr
        return chapter.split()[0] if chapter else "Other"

    def _infer_base_from_registers(self, oregs: list[dict]) -> str:
        """从残余寄存器推断基地址：取最小绝对地址作为基址。"""
        min_addr = None
        for orr in oregs:
            abs_str = orr.get("abs_addr", "") or orr.get("offset", "")
            try:
                addr = int(abs_str.replace('_', ''), 16)
                if min_addr is None or addr < min_addr:
                    min_addr = addr
            except (ValueError, AttributeError):
                continue
        return f"0x{min_addr:08X}" if min_addr else ""

    @staticmethod
    def _compute_rel_offset(abs_addr: str, base_str: str) -> str:
        """绝对地址 → 相对偏移 = abs - base。"""
        try:
            a = int(abs_addr.replace('_', '').replace('0x', ''), 16)
            b = int(base_str.replace('_', '').replace('0x', ''), 16)
            return f"0x{a - b:X}"
        except (ValueError, AttributeError):
            return abs_addr

    # ════════════════════════════════════════════════════
    # 组装成模型对象
    # ════════════════════════════════════════════════════

    def _assemble(self, peripherals: list[dict], registers: list[dict]) -> list:
        """把中间 dict 组装成 PeripheralBlock 列表（延迟 import 模型）。"""
        from reg_core.models import PeripheralBlock, Register, BitField

        # 按外设分组寄存器
        peri_groups: dict[str, list[dict]] = {}
        peri_meta: dict[str, dict] = {}
        order: list[str] = []
        for r in registers:
            key = r["peripheral"]
            if key not in peri_groups:
                peri_groups[key] = []
                order.append(key)
            peri_groups[key].append(r)

        # 补全外设元信息（寄存器里有但 peripherals 列表没记的）
        for p in peripherals:
            if p["name"] not in peri_meta:
                peri_meta[p["name"]] = p

        result: list[PeripheralBlock] = []
        # 先按已发现外设顺序
        seen = set()
        for pname in order:
            if pname in seen:
                continue
            seen.add(pname)
            meta = peri_meta.get(pname, {})
            regs = peri_groups.get(pname, [])
            pblock = PeripheralBlock(
                name=pname,
                base_address=_norm_hex(meta.get("base_addr", "")),
                description=meta.get("chapter", ""),
                registers=[self._to_register(r) for r in regs],
            )
            result.append(pblock)
        # 没有寄存器但出现在 peripherals 列表的外设（空壳，一般不发生）
        for p in peripherals:
            if p["name"] not in seen:
                seen.add(p["name"])
                result.append(PeripheralBlock(
                    name=p["name"],
                    base_address=_norm_hex(p.get("base_addr", "")),
                    description=p.get("chapter", ""),
                    registers=[],
                ))
        return result

    def _to_register(self, reg_dict: dict) -> Any:
        """中间 dict → Register + BitField。"""
        from reg_core.models import Register, BitField
        fields: list[BitField] = []
        for bf in reg_dict.get("bitfields", []):
            lo, hi = bf.get("lo"), bf.get("hi")
            if lo is None or hi is None:
                continue
            width = hi - lo + 1
            name = bf["symbol"].strip()
            if name.lower() in _SKIP_FIELD_NAMES:
                continue
            # 清洗位域名：去掉位宽后缀 [x:0]
            name = re.sub(r'\[.*?\]', '', name).strip()
            if not name:
                continue
            fields.append(BitField(
                name=name,
                bit_pos=lo,
                bit_width=width,
                description=bf.get("desc", "").strip(),
                access=self._norm_access(reg_dict.get("access", "")),
                confidence="high",
            ))
        return Register(
            name=reg_dict["name"],
            address_offset=_norm_hex(reg_dict.get("offset", "")),
            absolute_address=_norm_hex(reg_dict.get("abs_addr", "")),
            reset_value=_norm_hex(reg_dict.get("reset", "")) or "0x00000000",
            description=reg_dict.get("desc", "").strip(),
            access=self._norm_access(reg_dict.get("access", "")),
            fields=fields,
            confidence="high",
        )

    @staticmethod
    def _norm_access(raw: str) -> str:
        raw = (raw or "").strip().lower()
        if any(k in raw for k in ("rw", "读写", "r/w", "read/write")):
            return "RW"
        if any(k in raw for k in ("ro", "只读", "read only")):
            return "RO"
        if any(k in raw for k in ("wo", "只写", "write only")):
            return "WO"
        return "RW"

    @staticmethod
    def _compute_abs_addr(base: str, offset: str) -> str:
        """计算 绝对地址 = 基地址 + 偏移。"""
        try:
            b = int(base.replace("_", ""), 16)
            o = int(offset.replace("_", "").replace("0x", "", 1), 16)
            return f"0x{b + o:08X}"
        except (ValueError, AttributeError):
            return ""
