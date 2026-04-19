#!/usr/bin/env python3
"""
SVDEditor CLI 模块
提供命令行接口，支持：验证、导出、生成、比较、信息查看、合并、头文件生成、冲突检测、外设提取
可集成到 CI/CD 流水线中

用法:
    python -m svd_tool.cli validate <input.svd> [--json] [--strict]
    python -m svd_tool.cli export <input.svd> --format csv|markdown|html [--output <file>] [--peripheral <name>]
    python -m svd_tool.cli generate <input.svd> --output <output.svd>
    python -m svd_tool.cli diff <old.svd> <new.svd> [--output <file>] [--json]
    python -m svd_tool.cli info <input.svd> [--json]
    python -m svd_tool.cli merge <target.svd> <source.svd> [--strategy source|target] [-o output]
    python -m svd_tool.cli header <input.svd> [--style upper_case|camel_case] [--prefix PREFIX] [-o output.h]
    python -m svd_tool.cli conflicts <input.svd> [--json] [--strict]
    python -m svd_tool.cli extract <input.svd> --peripherals GPIOA,GPIOB [-o output.svd]
"""
import argparse
import json
import logging
import os
import sys
import time
from typing import Optional

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from svd_tool.core.svd_parser import SVDParser
from svd_tool.core.svd_generator import SVDGenerator
from svd_tool.core.svd_schema_validator import SVDSchemaValidator, Severity
from svd_tool.core.svd_exporter import SVDExporter
from svd_tool.core.svd_differ import SVDDiffer
from svd_tool.core.svd_merger import SVDMerger, MergeAction
from svd_tool.core.header_generator import HeaderGenerator
from svd_tool.core.address_conflict_detector import AddressConflictDetector


# ==================== 工具函数 ====================

def _setup_logging(verbose: bool = False):
    """配置日志"""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="[%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )


def _load_svd(file_path: str):
    """加载并解析 SVD 文件，返回 DeviceInfo"""
    if not os.path.isfile(file_path):
        print(f"错误: 文件不存在: {file_path}", file=sys.stderr)
        sys.exit(1)

    try:
        parser = SVDParser()
        device = parser.parse_file(file_path)
        return device, parser
    except Exception as e:
        print(f"错误: 解析 SVD 文件失败: {e}", file=sys.stderr)
        sys.exit(1)


def _output_json(data: dict, output_path: Optional[str] = None):
    """输出 JSON 数据"""
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"JSON 已输出到: {output_path}")
    else:
        print(text)


# ==================== 子命令实现 ====================

def cmd_validate(args):
    """验证 SVD 文件的 CMSIS-SVD Schema 完整性"""
    device, parser = _load_svd(args.input)

    if parser.warnings:
        print(f"解析警告 ({len(parser.warnings)} 条):")
        for w in parser.warnings[:10]:
            print(f"  ⚠ {w}")
        if len(parser.warnings) > 10:
            print(f"  ... 还有 {len(parser.warnings) - 10} 条警告")
        print()

    validator = SVDSchemaValidator()
    results = validator.validate_all(device)
    summary = validator.get_summary()

    if args.json:
        _output_json(summary, args.output)
        # JSON 模式下，如果有错误则返回非零退出码
        if summary["has_errors"]:
            sys.exit(1)
        return

    # 文本模式输出
    print(validator.format_results_text(max_items=100))

    if args.strict and summary["warnings"] > 0:
        print()
        print(f"⚠ 严格模式: 存在 {summary['warnings']} 条警告")
        sys.exit(1)

    if summary["has_errors"]:
        sys.exit(1)


def cmd_export(args):
    """导出 SVD 数据为 CSV/Markdown/HTML 文档"""
    device, parser = _load_svd(args.input)

    fmt = args.format.lower()
    exporter = SVDExporter(device)

    # 确定输出路径
    output_path = args.output
    if not output_path:
        base_name = os.path.splitext(args.input)[0]
        ext_map = {"csv": ".csv", "markdown": ".md", "html": ".html"}
        output_path = base_name + ext_map.get(fmt, f".{fmt}")

    # 执行导出
    peripheral_name = args.peripheral

    if fmt == "csv":
        if args.summary_only:
            success = exporter.export_register_summary_csv(output_path)
        else:
            success = exporter.export_csv(output_path, peripheral_name)
    elif fmt in ("markdown", "md"):
        success = exporter.export_markdown(output_path, peripheral_name)
    elif fmt == "html":
        success = exporter.export_html(output_path, peripheral_name)
    else:
        print(f"错误: 不支持的导出格式: {fmt}", file=sys.stderr)
        print("支持的格式: csv, markdown, html", file=sys.stderr)
        sys.exit(1)

    if success:
        print(f"✅ 导出成功: {output_path} (格式: {fmt})")
    else:
        print(f"❌ 导出失败", file=sys.stderr)
        sys.exit(1)


def cmd_generate(args):
    """重新生成 SVD XML 文件"""
    device, parser = _load_svd(args.input)

    output_path = args.output
    if not output_path:
        base_name = os.path.splitext(args.input)[0]
        output_path = base_name + "_generated.svd"

    generator = SVDGenerator(device)
    xml_str = generator.generate(pretty_print=True)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(xml_str)
        print(f"✅ SVD 文件已生成: {output_path}")

        # 输出基本统计
        periph_count = len(device.peripherals)
        reg_count = sum(len(p.registers) for p in device.peripherals.values())
        field_count = sum(
            len(r.fields)
            for p in device.peripherals.values()
            for r in p.registers.values()
        )
        print(f"   外设: {periph_count}, 寄存器: {reg_count}, 位域: {field_count}")
    except Exception as e:
        print(f"❌ 写入文件失败: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_diff(args):
    """比较两个 SVD 文件的差异"""
    device_old, parser_old = _load_svd(args.old)
    device_new, parser_new = _load_svd(args.new)

    differ = SVDDiffer()
    differ.ignore_description = args.ignore_description
    differ.ignore_display_name = args.ignore_display_name
    differ.ignore_reset_value = args.ignore_reset_value

    diffs = differ.diff(device_old, device_new)

    if args.json:
        result = {
            "old_file": args.old,
            "new_file": args.new,
            "changes": [d.to_dict() for d in diffs],
            "total_changes": sum(d.count_changes for d in diffs),
        }
        _output_json(result, args.output)
        if result["total_changes"] > 0 and args.strict:
            sys.exit(1)
        return

    # 文本模式
    if not diffs:
        print("✅ 两个 SVD 文件完全一致，没有差异。")
        return

    summary_text = differ.generate_summary(diffs)
    print(summary_text)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(summary_text)
        print(f"差异报告已保存到: {args.output}")

    if args.strict:
        total = sum(d.count_changes for d in diffs)
        if total > 0:
            sys.exit(1)


def cmd_info(args):
    """显示 SVD 文件的基本信息和统计"""
    device, parser = _load_svd(args.input)

    # 统计
    periph_count = len(device.peripherals)
    reg_count = sum(len(p.registers) for p in device.peripherals.values())
    field_count = sum(
        len(r.fields)
        for p in device.peripherals.values()
        for r in p.registers.values()
    )
    cluster_count = sum(
        len(p.clusters) for p in device.peripherals.values()
    )
    irq_count = len(device.interrupts)

    info = {
        "file": os.path.abspath(args.input),
        "device": {
            "name": device.name,
            "version": device.version,
            "vendor": device.vendor,
            "description": device.description,
            "svd_version": device.svd_version,
            "cpu": device.cpu.name,
            "size": device.size,
        },
        "statistics": {
            "peripherals": periph_count,
            "registers": reg_count,
            "fields": field_count,
            "clusters": cluster_count,
            "interrupts": irq_count,
        },
        "peripherals_detail": [],
    }

    for name, periph in device.peripherals.items():
        p_info = {
            "name": name,
            "base_address": periph.base_address,
            "registers": len(periph.registers),
            "fields": sum(len(r.fields) for r in periph.registers.values()),
            "clusters": len(periph.clusters),
            "interrupts": len(periph.interrupts),
            "derived_from": periph.derived_from or None,
        }
        info["peripherals_detail"].append(p_info)

    if args.json:
        _output_json(info, args.output)
        return

    # 文本模式 - 友好的表格输出
    d = device
    print(f"╔══════════════════════════════════════════════════╗")
    print(f"║  SVD 文件信息                                    ║")
    print(f"╚══════════════════════════════════════════════════╝")
    print()
    print(f"  文件:       {info['file']}")
    print(f"  设备名称:   {d.name}")
    print(f"  版本:       {d.version}")
    print(f"  厂商:       {d.vendor or '-'}")
    print(f"  SVD版本:    {d.svd_version}")
    print(f"  CPU:        {d.cpu.name} (revision {d.cpu.revision})")
    print(f"  默认大小:   {d.size} 位")
    print()
    print(f"  ┌─ 统计 ────────────────────────────────────┐")
    print(f"  │  外设:   {periph_count:>6}                          │")
    print(f"  │  寄存器: {reg_count:>6}                          │")
    print(f"  │  位域:   {field_count:>6}                          │")
    print(f"  │  簇:     {cluster_count:>6}                          │")
    print(f"  │  中断:   {irq_count:>6}                          │")
    print(f"  └───────────────────────────────────────────┘")
    print()

    if periph_count > 0:
        print(f"  {'外设名称':<20} {'基地址':<14} {'寄存器':>6} {'位域':>6} {'簇':>4} {'继承':<15}")
        print(f"  {'─' * 20} {'─' * 14} {'─' * 6} {'─' * 6} {'─' * 4} {'─' * 15}")
        for p in info["peripherals_detail"]:
            derived = p["derived_from"] or "-"
            print(f"  {p['name']:<20} {p['base_address']:<14} {p['registers']:>6} {p['fields']:>6} {p['clusters']:>4} {derived:<15}")


# ==================== 新增子命令 ====================

def cmd_merge(args):
    """合并两个 SVD 文件"""
    device_target, _ = _load_svd(args.target)
    device_source, _ = _load_svd(args.source)

    merger = SVDMerger()
    merge_items = merger.analyze(device_target, device_source)

    if not merge_items:
        print("✅ 两个 SVD 文件结构一致，无需合并。")
        return

    # 策略处理
    strategy = args.strategy
    for item in merge_items:
        if item.action == MergeAction.NO_ACTION:
            if strategy == "source":
                item.action = MergeAction.USE_SOURCE
            elif strategy == "target":
                item.action = MergeAction.USE_TARGET
            elif strategy == "prefer-new":
                item.action = MergeAction.USE_SOURCE

    # 执行合并
    merged_device, stats = merger.execute_merge(device_target, merge_items)

    # 输出合并统计
    if args.json:
        result = {
            "target": os.path.abspath(args.target),
            "source": os.path.abspath(args.source),
            "total_items": len(merge_items),
            "stats": stats,
            "items": [
                {
                    "path": item.path,
                    "level": item.level,
                    "action": item.action.value if hasattr(item.action, 'value') else str(item.action),
                }
                for item in merge_items
            ],
        }
        _output_json(result, args.output)
    else:
        print(f"合并分析: 发现 {len(merge_items)} 个差异项")
        print(f"  使用源(新): {stats.get('use_source', 0)}")
        print(f"  使用目标(旧): {stats.get('use_target', 0)}")
        print(f"  跳过: {stats.get('skip', 0)}")
        print()

        for item in merge_items[:50]:
            action_str = item.action.value if hasattr(item.action, 'value') else str(item.action)
            print(f"  [{action_str}] {item.path}")
        if len(merge_items) > 50:
            print(f"  ... 还有 {len(merge_items) - 50} 项")

    # 保存合并结果
    output_path = args.output if args.output else None
    if not output_path:
        base_name = os.path.splitext(args.target)[0]
        output_path = base_name + "_merged.svd"

    generator = SVDGenerator(merged_device)
    xml_str = generator.generate(pretty_print=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(xml_str)
    print(f"\n✅ 合并结果已保存到: {output_path}")


def cmd_header(args):
    """生成 C 头文件"""
    device, _ = _load_svd(args.input)

    style = args.style or "upper_case"
    prefix = args.prefix or ""

    generator = HeaderGenerator(device)
    header_content = generator.generate(style=style, prefix=prefix)

    output_path = args.output
    if not output_path:
        base_name = os.path.splitext(args.input)[0]
        output_path = base_name + ".h"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header_content)

    periph_count = len(device.peripherals)
    reg_count = sum(len(p.registers) for p in device.peripherals.values())
    print(f"✅ C 头文件已生成: {output_path}")
    print(f"   设备: {device.name}, 外设: {periph_count}, 寄存器: {reg_count}")
    print(f"   命名风格: {style}, 前缀: {prefix or '(无)'}")


def cmd_conflicts(args):
    """检测地址冲突"""
    device, _ = _load_svd(args.input)

    detector = AddressConflictDetector()
    conflicts = detector.detect_all(device)
    summary = detector.get_summary()

    if args.json:
        from svd_tool.core.address_conflict_detector import ConflictSeverity
        result = {
            "file": os.path.abspath(args.input),
            "summary": summary,
            "conflicts": [
                {
                    "severity": c.severity.value if hasattr(c.severity, 'value') else str(c.severity),
                    "type": c.conflict_type.value if hasattr(c.conflict_type, 'value') else str(c.conflict_type),
                    "location": c.location,
                    "message": c.message,
                    "detail": c.detail,
                }
                for c in conflicts
            ],
        }
        _output_json(result, args.output)
        if summary["errors"] > 0:
            sys.exit(1)
        return

    # 文本模式
    if not conflicts:
        print("✅ 未检测到地址冲突。")
        return

    print(f"⚠ 检测到 {summary['total']} 个冲突 ({summary['errors']} 错误, {summary['warnings']} 警告)")
    print()

    type_labels = {
        "peripheral_address_overlap": "外设地址重叠",
        "peripheral_base_duplicate": "外设基地址重复",
        "register_offset_duplicate": "寄存器偏移重复",
        "register_address_overlap": "寄存器地址重叠",
        "field_bit_overlap": "位域位重叠",
        "interrupt_value_duplicate": "中断号重复",
    }

    for c in conflicts:
        sev_icon = "🔴" if "ERROR" in str(c.severity) else "🟡"
        ctype = c.conflict_type.value if hasattr(c.conflict_type, 'value') else str(c.conflict_type)
        type_label = type_labels.get(ctype, ctype)
        print(f"  {sev_icon} [{type_label}] {c.location}")
        print(f"     {c.message}")
        if c.detail:
            print(f"     详情: {c.detail}")
        print()

    if args.strict and summary["errors"] > 0:
        sys.exit(1)


def cmd_extract(args):
    """从 SVD 文件中提取指定外设"""
    device, _ = _load_svd(args.input)

    periph_names = [n.strip() for n in args.peripherals.split(",") if n.strip()]

    missing = [n for n in periph_names if n not in device.peripherals]
    if missing:
        print(f"❌ 外设不存在: {', '.join(missing)}", file=sys.stderr)
        available = sorted(device.peripherals.keys())
        print(f"   可用外设: {', '.join(available[:20])}", file=sys.stderr)
        if len(available) > 20:
            print(f"   ... 还有 {len(available) - 20} 个", file=sys.stderr)
        sys.exit(1)

    # 创建只包含指定外设的新 DeviceInfo
    from svd_tool.core.data_model import DeviceInfo
    import copy

    new_device = copy.deepcopy(device)
    new_device.peripherals = {
        name: new_device.peripherals[name]
        for name in periph_names
        if name in new_device.peripherals
    }

    # 输出
    output_path = args.output
    if not output_path:
        base_name = os.path.splitext(args.input)[0]
        periph_suffix = "_".join(periph_names[:3])
        if len(periph_names) > 3:
            periph_suffix += f"_+{len(periph_names) - 3}"
        output_path = f"{base_name}_{periph_suffix}.svd"

    generator = SVDGenerator(new_device)
    xml_str = generator.generate(pretty_print=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(xml_str)

    reg_count = sum(len(p.registers) for p in new_device.peripherals.values())
    field_count = sum(
        len(r.fields)
        for p in new_device.peripherals.values()
        for r in p.registers.values()
    )
    print(f"✅ 已提取 {len(periph_names)} 个外设到: {output_path}")
    print(f"   外设: {', '.join(periph_names)}")
    print(f"   寄存器: {reg_count}, 位域: {field_count}")


# ==================== 参数解析 ====================

def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器"""
    main_parser = argparse.ArgumentParser(
        prog="svd-editor",
        description="SVDEditor 命令行工具 — CMSIS-SVD 验证、导出、生成、比较、合并、冲突检测",
        epilog="示例:\n"
               "  svd-editor validate chip.svd\n"
               "  svd-editor export chip.svd --format markdown -o registers.md\n"
               "  svd-editor diff chip_v1.svd chip_v2.svd\n"
               "  svd-editor generate chip.svd -o output.svd\n"
               "  svd-editor info chip.svd --json\n"
               "  svd-editor merge chip_v1.svd chip_v2.svd --strategy source\n"
               "  svd-editor header chip.svd --style upper_case -o device.h\n"
               "  svd-editor conflicts chip.svd --json\n"
               "  svd-editor extract chip.svd --peripherals GPIOA,GPIOB -o gpio.svd\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    main_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="显示详细日志输出",
    )

    subparsers = main_parser.add_subparsers(dest="command", help="可用子命令")

    # ---------- validate ----------
    p_validate = subparsers.add_parser(
        "validate",
        help="验证 SVD 文件的 CMSIS-SVD Schema 完整性",
        description="对 SVD 文件执行完整验证：位域重叠、地址冲突、必需字段、枚举值合法性等",
    )
    p_validate.add_argument("input", help="输入 SVD 文件路径")
    p_validate.add_argument("--json", action="store_true", help="以 JSON 格式输出验证结果")
    p_validate.add_argument("--strict", action="store_true", help="严格模式：有警告也返回非零退出码")
    p_validate.add_argument("-o", "--output", help="将 JSON 结果保存到指定文件")

    # ---------- export ----------
    p_export = subparsers.add_parser(
        "export",
        help="导出 SVD 数据为 CSV/Markdown/HTML 文档",
        description="将 SVD 数据导出为寄存器描述文档，用于 Datasheet / Reference Manual / Wiki",
    )
    p_export.add_argument("input", help="输入 SVD 文件路径")
    p_export.add_argument(
        "-f", "--format",
        required=True,
        choices=["csv", "markdown", "html"],
        help="导出格式",
    )
    p_export.add_argument("-o", "--output", help="输出文件路径（默认自动生成）")
    p_export.add_argument("-p", "--peripheral", help="只导出指定外设（默认导出全部）")
    p_export.add_argument(
        "--summary-only",
        action="store_true",
        help="仅导出寄存器汇总（CSV格式时有效，不含位域详情）",
    )

    # ---------- generate ----------
    p_generate = subparsers.add_parser(
        "generate",
        help="重新生成 SVD XML 文件",
        description="解析 SVD 文件后重新生成，用于格式化和规范化",
    )
    p_generate.add_argument("input", help="输入 SVD 文件路径")
    p_generate.add_argument("-o", "--output", help="输出文件路径（默认: <input>_generated.svd）")

    # ---------- diff ----------
    p_diff = subparsers.add_parser(
        "diff",
        help="比较两个 SVD 文件的差异",
        description="对比两个 SVD 文件的结构差异，输出新增/删除/修改的寄存器、位域等",
    )
    p_diff.add_argument("old", help="旧版 SVD 文件路径")
    p_diff.add_argument("new", help="新版 SVD 文件路径")
    p_diff.add_argument("-o", "--output", help="将差异报告保存到指定文件")
    p_diff.add_argument("--json", action="store_true", help="以 JSON 格式输出差异")
    p_diff.add_argument("--strict", action="store_true", help="严格模式：有差异则返回非零退出码")
    p_diff.add_argument("--ignore-description", action="store_true", help="比较时忽略描述字段")
    p_diff.add_argument("--ignore-display-name", action="store_true", help="比较时忽略显示名称")
    p_diff.add_argument("--ignore-reset-value", action="store_true", help="比较时忽略复位值")

    # ---------- info ----------
    p_info = subparsers.add_parser(
        "info",
        help="显示 SVD 文件基本信息和统计",
        description="显示设备信息、外设/寄存器/位域数量统计、各外设详情",
    )
    p_info.add_argument("input", help="输入 SVD 文件路径")
    p_info.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    p_info.add_argument("-o", "--output", help="将 JSON 结果保存到指定文件")

    # ---------- merge ----------
    p_merge = subparsers.add_parser(
        "merge",
        help="合并两个 SVD 文件",
        description="将源 SVD 文件的内容合并到目标 SVD 中，支持多种合并策略",
    )
    p_merge.add_argument("target", help="目标 SVD 文件路径")
    p_merge.add_argument("source", help="源 SVD 文件路径")
    p_merge.add_argument(
        "-s", "--strategy",
        choices=["source", "target", "prefer-new"],
        default="source",
        help="冲突解决策略（默认: source，使用源文件的新值）",
    )
    p_merge.add_argument("-o", "--output", help="合并结果输出路径（默认: <target>_merged.svd）")
    p_merge.add_argument("--json", action="store_true", help="以 JSON 格式输出合并详情")

    # ---------- header ----------
    p_header = subparsers.add_parser(
        "header",
        help="生成 C 头文件",
        description="从 SVD 文件生成 C 语言头文件，包含寄存器地址宏和位域定义",
    )
    p_header.add_argument("input", help="输入 SVD 文件路径")
    p_header.add_argument(
        "--style",
        choices=["upper_case", "camel_case"],
        default="upper_case",
        help="命名风格（默认: upper_case）",
    )
    p_header.add_argument("--prefix", help="自定义宏前缀（如: CHIP_）")
    p_header.add_argument("-o", "--output", help="输出头文件路径（默认: <input>.h）")

    # ---------- conflicts ----------
    p_conflicts = subparsers.add_parser(
        "conflicts",
        help="检测 SVD 文件中的地址冲突",
        description="检测外设地址重叠、寄存器偏移重复、位域位重叠、中断号重复等冲突",
    )
    p_conflicts.add_argument("input", help="输入 SVD 文件路径")
    p_conflicts.add_argument("--json", action="store_true", help="以 JSON 格式输出冲突详情")
    p_conflicts.add_argument("--strict", action="store_true", help="严格模式：有冲突则返回非零退出码")
    p_conflicts.add_argument("-o", "--output", help="将 JSON 结果保存到指定文件")

    # ---------- extract ----------
    p_extract = subparsers.add_parser(
        "extract",
        help="从 SVD 文件中提取指定外设",
        description="提取指定外设及其寄存器、位域，生成新的 SVD 文件",
    )
    p_extract.add_argument("input", help="输入 SVD 文件路径")
    p_extract.add_argument(
        "-p", "--peripherals",
        required=True,
        help="要提取的外设名称，逗号分隔（如: GPIOA,GPIOB,GPIOC）",
    )
    p_extract.add_argument("-o", "--output", help="输出文件路径（默认自动生成）")

    return main_parser


def run_cli(argv=None):
    """CLI 入口函数，供外部调用"""
    parser = build_parser()
    args = parser.parse_args(argv)

    _setup_logging(getattr(args, "verbose", False))

    if not args.command:
        parser.print_help()
        sys.exit(0)

    cmd_map = {
        "validate": cmd_validate,
        "export": cmd_export,
        "generate": cmd_generate,
        "diff": cmd_diff,
        "info": cmd_info,
        "merge": cmd_merge,
        "header": cmd_header,
        "conflicts": cmd_conflicts,
        "extract": cmd_extract,
    }

    handler = cmd_map.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


# ==================== 主入口 ====================

def main():
    """CLI 主入口"""
    run_cli()


if __name__ == "__main__":
    main()
