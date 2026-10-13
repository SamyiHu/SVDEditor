"""HeaderParser 单元测试 — 最小 H 文本，不依赖外部真实文件。

覆盖：基地址表达式、外设实例、寄存器成员、数组、偏移推断/注释、
位域（含跨实例挂载）、IRQ、raw_text/line_number 与 unresolved 不静默丢弃。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from svd_tool.core.datasource.header_parser import (
    HeaderParser, _safe_sum_expression,
)
from svd_tool.core.datasource.header_trm_fusion import HeaderTrmFusion
from svd_tool.core.datasource.header_coverage import (
    build_header_svd_coverage, coverage_to_markdown,
)


MINI_HEADER = r"""
#ifndef MINI_H
#define MINI_H

typedef enum
{
  RESET_IRQn = -14,   /*!< system reset */
  UART0_IRQn = 7,     /*!< UART0 interrupt */
  TIMER0_IRQn = 15,   /*!< TIMER0 interrupt */
} IRQn_Type;

#define PERIPH_BASE           (0x40000000UL)
#define APB0PERIPH_BASE       (PERIPH_BASE+0x20000)
#define AHBPERIPH_BASE        (PERIPH_BASE)
/* 词边界：AHBPERIPH_BASE 不得被 PERIPH_BASE 替换破坏 */
#define WDT_BASE              (AHBPERIPH_BASE +(0x00000330UL))
#define UART0_BASE            (APB0PERIPH_BASE +(0x00000020UL))
#define UART1_BASE            (APB0PERIPH_BASE +(0x00000080UL))
#define BAD_BASE              (UNKNOWN_BASE +(0x10UL))

typedef struct
{
  __IO uint32_t UART_CON;   /*!< UART Config register,  Address offset: 0x00 */
  __IO uint32_t UART_STS;   /*!< UART Status register,   Address offset: 0x04 */
  __IO uint32_t RESERVED;   /*!< Reserved,               Address offset: 0x08 */
  __IO uint32_t UART_DATA;  /*!< no offset comment here */
  __IO uint32_t UART_IDE;   /*!< UART Int/Dma enable,    Address offset: 0x10 */
} UART_TypeDef;

typedef struct
{
  __IO uint32_t WDT_CON;    /*!< WDT Control, Address offset: 0x00 */
  __IO uint32_t RESERVED0[3]; /*!< Reserved,  Address offset: 0x04 */
  __IO uint32_t WDT_CFG;    /*!< WDT Config,  Address offset: 0x10 */
} WDT_TypeDef;

#define UART0 ((UART_TypeDef *) UART0_BASE)
#define UART1 ((UART_TypeDef *) UART1_BASE)
#define WDT   ((WDT_TypeDef *) WDT_BASE)

#define UART_CON_RXEN_Pos          (6U)
#define UART_CON_RXEN_Msk          (0x1UL << UART_CON_RXEN_Pos)
#define UART_CON_PERSCALER_Pos     (4U)
#define UART_CON_PERSCALER_Msk     (0x3UL << UART_CON_PERSCALER_Pos)
#define UART_STS_PERR_Pos          (0U)
#define UART_STS_PERR_Msk          (0x1UL << UART_STS_PERR_Pos)
#define WDT_CON_EN_Pos             (7U)
#define WDT_CON_EN_Msk             (0x1UL << WDT_CON_EN_Pos)
#define ORPHAN_X_Y_Pos             (0U)
#define ORPHAN_X_Y_Msk             (0x1UL << ORPHAN_X_Y_Pos)

#endif
"""


def _model():
    return HeaderParser().parse_text(MINI_HEADER, path="<mini.h>")


# ── 表达式求值 ──

def test_safe_sum_basic_and_nested():
    syms = {"PERIPH_BASE": 0x40000000, "AHBPERIPH_BASE": 0x40000000}
    assert _safe_sum_expression("(0x40000000UL)", syms) == 0x40000000
    assert _safe_sum_expression("PERIPH_BASE+0x20000", syms) == 0x40020000
    assert _safe_sum_expression("AHBPERIPH_BASE +(0x330UL)", syms) == 0x40000330
    assert _safe_sum_expression("(PERIPH_BASE + (0x20UL))", syms) == 0x40000020


def test_safe_sum_word_boundary():
    """AHBPERIPH_BASE 含 PERIPH_BASE 子串，替换必须按词边界。"""
    syms = {"PERIPH_BASE": 0x40000000}
    assert _safe_sum_expression("AHBPERIPH_BASE", syms) is None  # 未知符号不可求值
    syms["AHBPERIPH_BASE"] = 0x40000000
    assert _safe_sum_expression("AHBPERIPH_BASE+0x330", syms) == 0x40000330


def test_safe_sum_rejects_dangerous():
    syms = {"A": 1}
    assert _safe_sum_expression("0x10*2", syms) is None      # 乘法不支持
    assert _safe_sum_expression("(1UL << 5)", syms) is None  # 移位不支持
    assert _safe_sum_expression("UNKNOWN+1", syms) is None   # 未知符号
    assert _safe_sum_expression("(((((1)))))", syms) is None # 括号过深
    assert _safe_sum_expression("__import__('os')", syms) is None


# ── 基地址 / 实例 ──

def test_base_addresses_resolved():
    m = _model()
    uart0 = next(p for p in m.peripherals if p.name == "UART0")
    assert uart0.base_address == 0x40020020
    wdt = next(p for p in m.peripherals if p.name == "WDT")
    assert wdt.base_address == 0x40000330
    assert uart0.type_name == "UART"
    assert uart0.line_number > 0 and "UART0_BASE" in uart0.raw_text


def test_unresolved_base_recorded():
    m = _model()
    bad = [u for u in m.unresolved if u["name"] == "BAD_BASE"]
    assert len(bad) == 1
    assert bad[0]["kind"] == "base_address"
    assert bad[0]["line"] > 0 and "UNKNOWN_BASE" in bad[0]["raw_text"]


# ── 寄存器成员 / 数组 / 偏移 ──

def test_registers_offset_comment_and_inference():
    m = _model()
    uart0 = next(p for p in m.peripherals if p.name == "UART0")
    names = [r.name for r in uart0.registers]
    assert names == ["UART_CON", "UART_STS", "UART_DATA", "UART_IDE"]
    by_name = {r.name: r for r in uart0.registers}
    assert by_name["UART_CON"].offset == 0x00
    assert by_name["UART_STS"].offset == 0x04
    # RESERVED 被跳过但推进游标：无注释的 UART_DATA 按 4 字节顺序推断到 0x0C
    assert by_name["UART_DATA"].offset == 0x0C
    assert by_name["UART_DATA"].offset_source == "inferred"
    assert by_name["UART_IDE"].offset == 0x10  # 注释优先


def test_reserved_array_advances_cursor():
    m = _model()
    wdt = next(p for p in m.peripherals if p.name == "WDT")
    names = [r.name for r in wdt.registers]
    assert "RESERVED0" not in names
    by_name = {r.name: r for r in wdt.registers}
    assert by_name["WDT_CFG"].offset == 0x10  # RESERVED0[3] = 0x0C 推进


def test_register_provenance():
    m = _model()
    uart0 = next(p for p in m.peripherals if p.name == "UART0")
    reg = next(r for r in uart0.registers if r.name == "UART_CON")
    assert reg.line_number > 0
    assert "UART_CON" in reg.raw_text
    assert reg.semantic_path == "UART0/UART_CON"


# ── 位域 ──

def test_bitfields_mounted_per_instance():
    m = _model()
    for periph_name in ("UART0", "UART1"):
        p = next(x for x in m.peripherals if x.name == periph_name)
        con = next(r for r in p.registers if r.name == "UART_CON")
        fields = {f.name: f for f in con.fields}
        assert "RXEN" in fields
        assert fields["RXEN"].bit_offset == 6
        assert fields["RXEN"].bit_width == 1
        assert "PERSCALER" in fields
        assert fields["PERSCALER"].bit_width == 2   # 0x3UL << 4
        assert fields["RXEN"].peripheral == periph_name
        assert fields["RXEN"].line_number > 0
        assert "_Msk" in fields["RXEN"].raw_text


def test_orphan_bitfield_in_unresolved():
    m = _model()
    orphan = [u for u in m.unresolved if u["name"] == "ORPHAN_X_Y"]
    assert len(orphan) == 1
    assert orphan[0]["kind"] == "bitfield_no_register"
    assert orphan[0]["line"] > 0


# ── IRQ ──

def test_irqs_with_line_and_raw():
    m = _model()
    assert len(m.interrupts) == 3
    by_name = {i.name: i for i in m.interrupts}
    assert by_name["RESET"].irq_number == -14
    assert by_name["UART0"].irq_number == 7
    assert by_name["TIMER0"].irq_number == 15
    assert by_name["UART0"].description  # 注释描述被保留
    assert by_name["UART0"].line_number > 0
    assert "UART0_IRQn" in by_name["UART0"].raw_text


# ── 汇总 ──

def test_model_summary_counts():
    m = _model()
    assert m.peripheral_names == {"UART0", "UART1", "WDT"}
    assert m.count_registers() == 4 * 2 + 2
    assert m.count_fields() == 3 * 2 + 1
    # unresolved 有数量且每条含 kind/name/line/raw_text
    assert m.unresolved
    for u in m.unresolved:
        assert {"kind", "name", "line", "raw_text"} <= set(u)


# ════════════════════════════════════════════════════
# H 主控 + TRM 补充融合（stub TRM，不依赖 reg_core）
# ════════════════════════════════════════════════════

class _TrmField:
    def __init__(self, name, bit_pos, bit_width=1, access="RW", description=""):
        self.name = name
        self.bit_pos = bit_pos
        self.bit_width = bit_width
        self.access = access
        self.description = description
        self.source_ref = {"table_index": 3, "row_number": 9, "raw_text": "TRM field row"}


class _TrmRegister:
    def __init__(self, name, address_offset="0x00", reset_value="0x00000000",
                 access="RW", description="", fields=None):
        self.name = name
        self.address_offset = address_offset
        self.reset_value = reset_value
        self.access = access
        self.description = description
        self.fields = fields or []
        self.source_ref = {"table_index": 2, "row_number": 4, "raw_text": "TRM reg row"}


class _TrmPeripheral:
    def __init__(self, name, base_address="", bus="", description="", registers=None):
        self.name = name
        self.base_address = base_address
        self.bus = bus
        self.description = description
        self.registers = registers or []
        self.source_ref = {"section": "5.2 UART", "raw_text": "UART基地址：0x40020020"}


_TRM_PERIPHERALS = [
    # 模板名 UART（无实例号）——应通过 root 匹配挂到 H 的 UART0/UART1
    _TrmPeripheral(
        name="UART", base_address="0x40020020", bus="APB0", description="通用异步收发器",
        registers=[
            _TrmRegister(
                name="UART_CON", address_offset="0x00", reset_value="0x00000000",
                description="配置寄存器（TRM）", access="RW",
                fields=[
                    _TrmField("RXEN", 6, 1, "RW", "接收使能"),
                    _TrmField("PSC", 4, 2, "RW", "分频"),   # 名称不同但位号相同
                ]),
            _TrmRegister(name="UART_STS", address_offset="0x04",
                         reset_value="0x000000C0", description="状态寄存器（TRM）"),
        ]),
    # TRM 独有：H 中不存在 → 不得静默丢弃
    _TrmPeripheral(name="CAN0", base_address="0x40025000",
                   registers=[_TrmRegister(name="CAN_CON")]),
]

_TRM_INTERRUPTS = [
    type("TrmIrq", (), {"name": "UART0", "irq_number": 7,
                        "description": "UART0 全局中断", "source_ref": {}})(),
]


def _fusion():
    m = _model()
    return HeaderTrmFusion(header_path="<mini.h>").fuse(
        m, trm_peripherals=_TRM_PERIPHERALS, trm_interrupts=_TRM_INTERRUPTS)


def test_fusion_header_is_skeleton():
    fused = _fusion()
    # H 的 3 个实例全部保留；结构（寄存器/位域）数量与 H 一致
    assert [p.name for p in fused.peripherals] == ["UART0", "UART1", "WDT"]
    uart0 = fused.peripherals[0]
    assert [r.name for r in uart0.registers] == [
        "UART_CON", "UART_STS", "UART_DATA", "UART_IDE"]
    con = uart0.registers[0]
    assert {f.name for f in con.fields} == {"RXEN", "PERSCALER"}


def test_fusion_trm_supplements_metadata():
    fused = _fusion()
    uart0 = fused.peripherals[0]
    con = next(r for r in uart0.registers if r.name == "UART_CON")
    assert con.description == "配置寄存器（TRM）"      # TRM 描述
    assert con.reset_value == "0x00000000"
    assert con.access == "RW"
    rxen = next(f for f in con.fields if f.name == "RXEN")
    assert rxen.description == "接收使能"
    # 位域优先 bit_offset+bit_width：PSC(4,2) 匹配到 H 的 PERSCALER(4,2)
    psc = next(f for f in con.fields if f.name == "PERSCALER")
    assert psc.description == "分频"
    ref = psc.source_ref
    assert ref["match_reason"] == "bit_position"
    assert 0 < ref["match_score"] < 1


def test_fusion_provenance_header_line_and_trm_ref():
    fused = _fusion()
    uart0 = fused.peripherals[0]
    con = next(r for r in uart0.registers if r.name == "UART_CON")
    ref = con.source_ref
    # 每条融合记录都能看到 H 原始行与 TRM 原文
    assert ref["header_line"] > 0
    assert "UART_CON" in ref["header_raw_text"]
    assert ref["trm_ref"]["raw_text"] == "TRM reg row"
    assert ref["source_file"] == "<mini.h>"
    assert uart0.source_authority == "header_anchor"


def test_fusion_trm_only_not_dropped():
    fused = _fusion()
    coverage = fused.coverage
    trm_only = [item["peripheral"] for item in coverage["trm_only_items"]]
    assert "CAN0" in trm_only
    assert coverage["header_peripherals"] == 3
    assert coverage["trm_peripherals"] == 2
    assert coverage["trm_peripherals_matched"] == 1
    assert coverage["unresolved_header_items"] == len(_model().unresolved)


def test_fusion_interrupts_h_master():
    fused = _fusion()
    assert len(fused.interrupts) == 3
    by_name = {i.name: i for i in fused.interrupts}
    assert by_name["UART0"].description  # H 注释优先/TRM 补充
    assert by_name["UART0"].source_ref["match_reason"] == "irq_number"


# ════════════════════════════════════════════════════
# H ↔ SVD 覆盖率（stub DeviceInfo）
# ════════════════════════════════════════════════════

class _SvdField:
    def __init__(self, name, bit_offset, bit_width=1):
        self.name = name
        self.bit_offset = bit_offset
        self.bit_width = bit_width


class _SvdRegister:
    def __init__(self, name, offset, fields=None):
        self.name = name
        self.offset = offset
        self.fields = {f.name: f for f in (fields or [])}


class _SvdPeripheral:
    def __init__(self, name, base_address, registers):
        self.name = name
        self.base_address = base_address
        self.registers = {r.name: r for r in registers}


class _SvdDevice:
    def __init__(self, peripherals):
        self.peripherals = {p.name: p for p in peripherals}


def _svd():
    return _SvdDevice([
        _SvdPeripheral("UART0", "0x40020020", [
            _SvdRegister("UART_CON", "0x0", [
                _SvdField("RXEN", 6, 1), _SvdField("PERSCALER", 4, 2)]),
            _SvdRegister("UART_STS", "0x4"),
        ]),
        _SvdPeripheral("UART1", "0x40020080", [
            _SvdRegister("UART_CON", "0x0"),
        ]),
        _SvdPeripheral("EXTRA", "0x50000000", [
            _SvdRegister("EXTRA_CON", "0x0"),
        ]),
    ])


def test_coverage_report_structure():
    report = build_header_svd_coverage(
        _model(), _svd(), trm_supplement_percent=66.6)
    assert report["peripherals_in_header"] == 3
    assert report["peripherals_in_svd"] == 3
    assert "UART0" in report["matched_peripherals"]
    assert "UART1" in report["matched_peripherals"]
    unmatched_h = [p["peripheral"] for p in report["unmatched_header_peripherals"]]
    assert unmatched_h == ["WDT"]
    unmatched_s = [p["peripheral"] for p in report["unmatched_svd_peripherals"]]
    assert "EXTRA" in unmatched_s
    assert report["registers_matched"] == 3      # UART0×2 + UART1×1
    assert report["registers_in_header"] == 10
    # UART0.UART_CON 的 RXEN/PERSCALER 命中位号+位宽；其余寄存器 SVD 无字段
    assert report["fields_matched"] == 2
    assert report["header_coverage_percent"] == 30.0
    assert report["trm_supplement_percent"] == 66.6


def test_coverage_diffs_detail_kinds():
    report = build_header_svd_coverage(_model(), _svd())
    kinds = report["diff_counts"]
    assert kinds.get("peripheral_missing_in_svd", 0) == 1      # WDT
    assert kinds.get("peripheral_missing_in_header", 0) == 1   # EXTRA
    # UART_STS 的 PERR 位域在 SVD 中缺失
    assert kinds.get("field_missing_in_svd", 0) >= 1
    # WDT(2) + UART1 的 STS/DATA/IDE（SVD 仅 CON）整体缺失
    assert kinds.get("register_missing_in_svd", 0) == 5
    # UART1 的寄存器在 SVD 有但 H 位域多出的部分
    assert report["diffs"]
    for item in report["diffs"]:
        assert {"kind", "peripheral", "detail"} <= set(item)


def test_coverage_markdown_renders():
    report = build_header_svd_coverage(_model(), _svd())
    md = coverage_to_markdown(report)
    assert "H ↔ SVD 覆盖率报告" in md
    assert "header_coverage_percent" in md
    assert "WDT" in md
    assert "EXTRA" in md
