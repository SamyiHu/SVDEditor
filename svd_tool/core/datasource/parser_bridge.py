"""
Parser 桥接层 — 线程安全地调用外部 Parser 包。

Parser 包（位于仓库同级目录 ../Parser）是纯 Python 库，无 CLI、无 SVD 输出。
本模块负责：
1. 懒加载 Parser 包（缺库时给出友好错误，不影响编辑器主体启动）
2. 自动发现 Parser 包路径（pip install -e 优先；否则 sys.path 兜底）
3. 把单源/多源解析封装为 ParseRequest → ParseResult，供 DatasourceManager 在后台线程调用

设计要点：
- import parser 只在真正调用 parse 时发生（lazy），避免冷启动变慢 + 缺库时不影响主进程
- 所有 Parser 依赖（openpyxl/pdfplumber/pymupdf/python-docx）的缺失都被捕获并转成
  ParserUnavailableError，由上层 UI 弹出「需安装 pymupdf」之类的提示
- 解析是 CPU/IO 密集型，parse_sync 必须在 worker 线程内调用，绝不在 GUI 线程
"""
from __future__ import annotations

import copy
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Optional

from .correction_store import (
    CONFIRMED, IGNORED, MACHINE, REJECTED,
    CorrectionStore, file_fingerprint,
)

logger = logging.getLogger("svd_tool.datasource.ParserBridge")


# ════════════════════════════════════════════════════
# 异常
# ════════════════════════════════════════════════════

class ParserUnavailableError(RuntimeError):
    """Parser 包或其依赖（openpyxl/pdfplumber/pymupdf/python-docx）不可用。"""

    def __init__(self, message: str, missing_deps: Optional[list[str]] = None):
        super().__init__(message)
        self.missing_deps = missing_deps or []


# ════════════════════════════════════════════════════
# 数据传输对象
# ════════════════════════════════════════════════════

@dataclass
class ParseRequest:
    """解析请求（单源或多源融合）。

    sources: {来源名: 文件或目录路径}，来源名为 "excel"/"word"/"pdf"。
             单源（len==1）直接走该源；多源按 strategy 融合。
    strategy: "single"（取 primary_source 直通，多源时按权重兜底）
              或 "fusion"（置信度加权融合）
    primary_source: strategy=single 时指定主源；多源时用于全空兜底
    chip_name: 顶层设备名（写入 ChipData.chip_name，留空则从文件名推断）
    header_path: 可选 CMSIS H 文件。给出后启用「H 主控 + TRM 补充」模式：
              H 提供外设实例/命名/寄存器/位域骨架，TRM 只补充描述、
              复位值、访问类型与位域语义（见 header_trm_fusion）。
    """
    sources: dict[str, str] = field(default_factory=dict)
    strategy: str = "single"
    primary_source: str = ""
    chip_name: str = ""
    correction_path: str = ""   # 空则在主来源旁生成 *.svd-corrections.json
    header_path: str = ""


@dataclass
class ParseResult:
    """解析结果。chip_data 为 None 表示失败，errors 记录原因。"""
    chip_data: Any = None          # parser.models.ChipData（避免类型硬依赖）
    fusion_report: Any = None      # parser.source_fusion.FusionReport 或 None
    quality: dict = field(default_factory=dict)   # confidence 分布统计
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    strategy: str = "single"
    primary_source: str = ""
    diagnostics: list[dict] = field(default_factory=list)
    provenance: list[dict] = field(default_factory=list)
    correction_store: Optional[CorrectionStore] = None
    correction_path: str = ""
    correction_candidates: list[Any] = field(default_factory=list)
    source_files: list[dict] = field(default_factory=list)
    extracted_chip_data: Any = None
    extracted_snapshot: dict = field(default_factory=dict)
    event_log_path: str = ""
    resolved_model_path: str = ""
    # —— H 文件链路（header_path 给出时填充）——
    fusion_mode: str = ""                      # "header_master_trm_supplement" 或 ""
    header_model: Any = None                   # header_parser.HeaderModel
    header_fusion: Any = None                  # HeaderTrmFusionResult
    header_coverage: dict = field(default_factory=dict)   # H↔TRM 融合覆盖率

    @property
    def ok(self) -> bool:
        return self.chip_data is not None and not self.errors


# ════════════════════════════════════════════════════
# Parser 包定位
# ════════════════════════════════════════════════════

def _candidate_parser_roots() -> list[str]:
    """候选 Parser 包根目录（包含 parser/ 子目录的父目录）。

    优先级：
    1. 环境变量 SVDEDITOR_PARSER_PATH（显式覆盖）
    2. 仓库同级 ../Parser
    3. 开发期仓库相对路径（处理 PyInstaller 冻结场景）
    """
    roots: list[str] = []
    env = os.environ.get("SVDEDITOR_PARSER_PATH", "")
    if env:
        roots.append(env)
    # 本文件: svd_tool/core/datasource/parser_bridge.py
    here = Path(__file__).resolve()
    repo_root = here.parents[3]              # SVDEditor-github/
    roots.append(str(repo_root.parent / "Parser"))   # ../Parser
    return roots


def is_parser_available() -> bool:
    """探测 reg_core 包是否可导入（不触发其重依赖）。"""
    try:
        _ensure_parser_importable()
        import reg_core  # noqa: F401
        return True
    except Exception:
        return False


def _ensure_parser_importable() -> None:
    """确保 `import reg_core` 能找到外部 Parser 包。

    Parser 包已从 `parser` 改名为 `reg_core`。
    若已 pip install -e，则直接可用；否则把候选根目录加入 sys.path。
    """
    if "reg_core" in sys.modules:
        return
    import importlib.util
    if importlib.util.find_spec("reg_core") is not None:
        return
    # 兜底：把候选根加入 sys.path
    for root in _candidate_parser_roots():
        if os.path.isdir(os.path.join(root, "reg_core")):
            if root not in sys.path:
                sys.path.insert(0, root)
            return


# ════════════════════════════════════════════════════
# 桥接主体
# ════════════════════════════════════════════════════

class ParserBridge:
    """线程安全的 Parser 调用封装。

    用法（在 worker 线程内）：
        bridge = ParserBridge()
        result = bridge.parse_sync(request)
    所有方法均同步阻塞，不做线程调度——调度由 DatasourceManager 负责。
    """

    # 已知来源 → Parser 注册表中的 source 名
    _VALID_SOURCES = ("excel", "word", "pdf")

    def __init__(self) -> None:
        self._diagnostics: list[dict] = []
        self._last_parsed_interrupts: list[Any] = []

    def _collect_parser_diagnostics(self, parser: Any, path: str, parser_name: str) -> None:
        """保留 TrmWordParser.last_mismatches 等解析侧审计信息，不再静默丢弃。"""
        for attr in ("last_mismatches", "last_errors", "last_warnings", "last_issues", "diagnostics"):
            value = getattr(parser, attr, None)
            if not value:
                continue
            if isinstance(value, dict):
                value = [value]
            try:
                iterator = list(value)
            except TypeError:
                iterator = [{"message": str(value)}]
            for item in iterator:
                if isinstance(item, dict):
                    payload = dict(item)
                else:
                    payload = {"message": str(item)}
                payload.setdefault("code", attr)
                payload.setdefault("severity", "warning" if attr != "last_errors" else "error")
                payload["parser"] = parser_name
                payload["source_file"] = str(Path(path).resolve())
                self._diagnostics.append(payload)

    def _capture_interrupts(self, parser: Any) -> None:
        self._last_parsed_interrupts = list(
            getattr(parser, "last_interrupts", []) or [])

    def _parse_source(self, registry, src: str, path: str) -> list:
        """解析单个来源。

        Word 来源优先用 reg_core 的 TrmWordParser（直接读 docx 表格，
        四类表格分类 REGMAP/REGSUM/FIELDDETAIL/BITMAP，准确率最高）。
        失败回退到我们的 trm_parser（pandoc→md 路径）。
        Excel/PDF 走 reg_core 原生解析器。
        """
        self._last_parsed_interrupts = []
        if src == "word":
            # 优先：reg_core TrmWordParser（python-docx 直接读，支持 th 标签）
            try:
                from reg_core.parsers.trm_word_parser import TrmWordParser
                from pathlib import Path
                trm = TrmWordParser()
                periphs = trm.parse(Path(path))
                self._collect_parser_diagnostics(trm, path, "reg_core.TrmWordParser")
                self._capture_interrupts(trm)
                if periphs:
                    from reg_core.quality_report import stamp_confidence
                    stamp_confidence(periphs, "word")
                    return periphs
            except Exception as e:
                logger.warning(f"reg_core TrmWordParser 失败，回退到我们的 trm_parser: {e}")
            # 回退：我们的 pandoc 路径
            try:
                from .trm_parser import TRMWordParser
                trm = TRMWordParser()
                self._collect_parser_diagnostics(trm, path, "svd_tool.TRMWordParser")
                if os.path.isdir(path):
                    periphs = trm.parse_dir(path)
                else:
                    periphs = trm.parse_file(path)
                self._capture_interrupts(trm)
                if periphs:
                    return periphs
            except Exception as e:
                logger.warning(f"trm_parser 也失败，回退到原生 WordParser: {e}")
            # 最终回退：reg_core 原生 WordParser
            word_parser = registry.get_for_source(src)
            periphs = word_parser.parse(path)
            self._collect_parser_diagnostics(word_parser, path, f"reg_core.{src}Parser")
            self._capture_interrupts(word_parser)
            from reg_core.quality_report import stamp_confidence
            stamp_confidence(periphs, "word")
            return periphs

        # Excel / PDF：原生解析器 + 置信度打标
        source_parser = registry.get_for_source(src)
        periphs = source_parser.parse(path)
        self._collect_parser_diagnostics(source_parser, path, f"reg_core.{src}Parser")
        self._capture_interrupts(source_parser)
        from reg_core.quality_report import stamp_confidence
        stamp_confidence(periphs, src)
        return periphs

    def parse_sync(self, request: ParseRequest) -> ParseResult:
        """执行解析。在 worker 线程内调用。"""
        self._diagnostics = []
        result = ParseResult(
            strategy=request.strategy,
            primary_source=request.primary_source,
        )

        # 1. 校验请求
        if not request.sources:
            result.errors.append("未指定任何数据源（Excel/Word/PDF）")
            return result
        invalid = [s for s in request.sources if s not in self._VALID_SOURCES]
        if invalid:
            result.errors.append(f"未知数据源类型: {invalid}（应为 {list(self._VALID_SOURCES)}）")
            return result
        for src, path in request.sources.items():
            if not path or not os.path.exists(path):
                result.errors.append(f"{src} 来源路径不存在: {path}")
                return result
        if request.header_path and not os.path.exists(request.header_path):
            result.errors.append(f"header_path 不存在: {request.header_path}")
            return result

        # 2. 懒加载 Parser 包（捕获重依赖缺失）
        try:
            _ensure_parser_importable()
            from reg_core import default_registry, SourceFusion, FusionStrategy
            from reg_core.models import ChipData
            from reg_core.quality_report import stamp_confidence
        except ParserUnavailableError:
            raise
        except Exception as e:
            missing = _detect_missing_deps(e)
            if missing:
                raise ParserUnavailableError(
                    f"Parser 依赖缺失: {', '.join(missing)}。请运行: pip install {' '.join(missing)}",
                    missing_deps=missing,
                ) from e
            raise ParserUnavailableError(f"Parser 包加载失败: {e}") from e

        # 3. 逐源解析
        registry = default_registry()
        parsed: dict[str, list] = {}   # {source: list[PeripheralBlock]}
        parsed_interrupts: dict[str, list] = {}
        parse_errors: list[str] = []
        for src, path in request.sources.items():
            try:
                periphs = self._parse_source(registry, src, path)
                parsed[src] = periphs or []
                parsed_interrupts[src] = list(self._last_parsed_interrupts or [])
                logger.info(f"解析 {src}（{path}）: {len(periphs or [])} 个外设 / "
                            f"{len(parsed_interrupts[src])} 个中断")
            except Exception as e:
                msg = f"解析 {src} 失败（{path}）: {e}"
                logger.exception(msg)
                parse_errors.append(msg)

        # 全部失败才算失败；部分失败则警告继续
        if not parsed:
            result.errors.extend(parse_errors)
            return result
        if parse_errors:
            result.warnings.extend(parse_errors)

        # 4. 单源直通 或 多源融合
        strategy = request.strategy or "single"
        try:
            if len(parsed) == 1 or strategy == "single":
                periphs, fusion_report = SourceFusion().fuse(
                    parsed,
                    strategy=FusionStrategy.SINGLE,
                    primary_source=request.primary_source or next(iter(parsed)),
                )
                result.strategy = "single"
            else:
                periphs, fusion_report = SourceFusion().fuse(
                    parsed,
                    strategy=FusionStrategy.FUSION,
                    primary_source=request.primary_source or None,
                )
                result.strategy = "fusion"
        except Exception as e:
            logger.exception("融合阶段失败")
            result.errors.append(f"多源融合失败: {e}")
            return result

        result.fusion_report = fusion_report
        result.diagnostics.extend(self._diagnostics)

        # 4.5 H 主控 + TRM 补充（header_path 给出时启用；不作为普通多源融合）
        interrupts: list = []
        header_model = None
        if request.header_path:
            from .header_parser import HeaderParser
            from .header_trm_fusion import HeaderTrmFusion
            try:
                header_model = HeaderParser().parse_file(request.header_path)
            except Exception as exc:
                logger.exception("H 文件解析失败")
                result.errors.append(f"H 文件解析失败（{request.header_path}）: {exc}")
                return result
            if not header_model.peripherals:
                result.errors.append(
                    f"H 文件未解析到任何外设实例: {request.header_path}")
                return result
            fusion = HeaderTrmFusion(
                header_path=str(Path(request.header_path).resolve()),
            ).fuse(
                header_model,
                trm_peripherals=periphs or [],
                trm_interrupts=_merge_interrupts(
                    parsed_interrupts, request.primary_source or ""),
            )
            periphs = fusion.peripherals
            interrupts = fusion.interrupts
            result.fusion_mode = "header_master_trm_supplement"
            result.header_model = header_model
            result.header_fusion = fusion
            result.header_coverage = dict(fusion.coverage)
            trm_only = fusion.coverage.get("trm_only_items", [])
            if trm_only:
                result.warnings.append(
                    f"TRM 中 {len(trm_only)} 个外设未在 H 中找到归属，"
                    f"已进入 header_coverage.trm_only_items 待人工处置: "
                    + ", ".join(item["peripheral"] for item in trm_only[:10]))

        # 5. 装配 ChipData
        chip_name = request.chip_name.strip()
        if not chip_name:
            # 从第一个来源的路径推断设备名
            first_path = next(iter(request.sources.values()))
            chip_name = Path(first_path).stem or "UNKNOWN_DEVICE"
        source_files = [file_fingerprint(path) for path in request.sources.values()]
        if header_model is not None:
            source_files.append(file_fingerprint(request.header_path))
        result.source_files = source_files
        periphs = _stamp_multi_source_semantics(periphs or [], parsed)
        if not interrupts:
            interrupts = _merge_interrupts(
                parsed_interrupts, request.primary_source or "")
        result.chip_data = ChipData(
            chip_name=chip_name,
            peripherals=periphs or [],
            interrupts=interrupts,
            diagnostics=result.diagnostics,
            source_files=source_files,
        )
        # 快照先于人工 Overlay 固化，保证机器解析原值不可变。
        result.extracted_chip_data = copy.deepcopy(result.chip_data)

        # 6. 同一 TRM 的 sidecar 自动加载、同步与重放
        primary_path = (
            request.sources.get("word")
            or request.sources.get("pdf")
            or request.sources.get("excel")
            or next(iter(request.sources.values()))
        )
        try:
            correction_store = CorrectionStore.for_sources(
                request.sources, request.correction_path or None)
            result.correction_store = correction_store
            result.correction_path = str(correction_store.path)
            result.event_log_path = str(correction_store.event_log_path)
            result.extracted_snapshot = correction_store.ensure_snapshot(
                result.extracted_chip_data, source_files)
            if correction_store.load_error:
                result.warnings.append(
                    f"纠错 sidecar 无法读取，未覆盖原文件: {correction_store.load_error}")
            else:
                result.correction_candidates = correction_store.sync_candidates(
                    result.chip_data, primary_path)
                applied = correction_store.apply_to_chip_data(
                    result.chip_data, result.correction_candidates)
                result.quality["manual_corrections_reapplied"] = applied
                resolved_path = correction_store.write_resolved_model(
                    result.chip_data)
                result.resolved_model_path = str(resolved_path)
        except Exception as exc:
            logger.exception("纠错 sidecar 处理失败")
            result.warnings.append(f"纠错 sidecar 处理失败: {exc}")

        result.provenance = _collect_provenance(result.chip_data)

        # 7. 三类语义分开统计；source weight 不作为准确率
        result.quality = {**_summarize_confidence(periphs or []), **result.quality}
        result.quality.update(_summarize_review_semantics(result.chip_data, result.correction_store))
        if result.fusion_mode:
            result.quality["fusion_mode"] = result.fusion_mode
            result.quality["header_peripherals"] = result.header_coverage.get(
                "header_peripherals", 0)
            result.quality["trm_supplement_percent"] = result.header_coverage.get(
                "trm_supplement_percent", 0.0)
            result.quality["unresolved_header_items"] = result.header_coverage.get(
                "unresolved_header_items", 0)

        return result


# ════════════════════════════════════════════════════
# 辅助
# ════════════════════════════════════════════════════

# Parser 的重依赖模块名 → pip 包名
_DEP_MAP = {
    "openpyxl": "openpyxl",
    "pdfplumber": "pdfplumber",
    "fitz": "pymupdf",
    "docx": "python-docx",
    "yaml": "pyyaml",
}


def _detect_missing_deps(exc: Exception) -> list[str]:
    """从 ImportError/ModuleNotFoundError 提取缺失的 pip 包名。"""
    missing: list[str] = []
    msg = str(exc)
    for mod_name, pip_name in _DEP_MAP.items():
        if mod_name in msg or mod_name in type(exc).__name__:
            if pip_name not in missing:
                missing.append(pip_name)
    # 直接的 ModuleNotFoundError：尝试取模块名映射
    if not missing and isinstance(exc, ModuleNotFoundError):
        name = getattr(exc, "name", "") or ""
        if name in _DEP_MAP:
            missing.append(_DEP_MAP[name])
    return missing


def _review_entity_items(peripherals: list) -> Iterator[tuple[Any, str, str]]:
    for pblk in peripherals or []:
        yield pblk, "peripheral", _display_name(getattr(pblk, "name", ""))
        for reg in getattr(pblk, "registers", []) or []:
            rpath = "/".join(x for x in (
                _display_name(getattr(pblk, "name", "")),
                _display_name(getattr(reg, "name", "")),
            ) if x)
            yield reg, "register", rpath
            for fld in getattr(reg, "fields", []) or []:
                fpath = "/".join(x for x in (
                    rpath, _display_name(getattr(fld, "name", ""))
                ) if x)
                yield fld, "field", fpath


def _display_name(value: Any) -> str:
    return str(value or "")


def _review_properties(level: str) -> tuple[str, ...]:
    if level == "peripheral":
        return ("name", "base_address", "description")
    if level == "register":
        return ("name", "address_offset", "reset_value", "access", "description")
    return ("name", "bit_pos", "bit_width", "access", "description")


def _with_semantics(entity: Any, **values: Any) -> Any:
    update = dict(values)
    model_copy = getattr(entity, "model_copy", None)
    if callable(model_copy):
        return model_copy(update=update)
    clone = copy.copy(entity)
    for key, value in update.items():
        try:
            setattr(clone, key, value)
        except Exception:
            pass
    return clone


def _stamp_multi_source_semantics(
    fused: list, parsed: dict[str, list],
) -> list:
    """按属性计算多源一致度，独立于来源权重和解析完整度。"""
    source_indexes: dict[str, dict[str, Any]] = {}
    for source_name, peripherals in parsed.items():
        for entity, _level, path in _review_entity_items(peripherals):
            source_indexes.setdefault(path, {})[source_name] = entity

    def semantics(entity: Any, level: str, path: str) -> dict:
        matches = source_indexes.get(path, {})
        source_values: dict[str, list[Any]] = {}
        conflict = False
        for prop in _review_properties(level):
            values = [
                {"source": source_name, "value": getattr(source_entity, prop, "")}
                for source_name, source_entity in sorted(matches.items())
            ]
            source_values[prop] = values
            if len({str(item.get("value", "")) for item in values}) > 1:
                conflict = True
        agreement = "single_source"
        if len(matches) > 1:
            agreement = "conflict" if conflict else "consistent"
        return {
            "semantic_path": path,
            "multi_source_agreement": agreement,
            "source_values": source_values,
        }

    out = []
    for pblk in fused or []:
        pname = _display_name(getattr(pblk, "name", ""))
        new_regs = []
        for reg in getattr(pblk, "registers", []) or []:
            rname = _display_name(getattr(reg, "name", ""))
            rpath = "/".join(x for x in (pname, rname) if x)
            new_fields = []
            for fld in getattr(reg, "fields", []) or []:
                fname = _display_name(getattr(fld, "name", ""))
                fpath = "/".join(x for x in (rpath, fname) if x)
                new_fields.append(_with_semantics(
                    fld, **semantics(fld, "field", fpath)))
            new_regs.append(_with_semantics(
                reg,
                fields=new_fields,
                **semantics(reg, "register", rpath),
            ))
        out.append(_with_semantics(
            pblk,
            registers=new_regs,
            **semantics(pblk, "peripheral", pname),
        ))
    return out


def _merge_interrupts(
    parsed: dict[str, list], primary_source: str,
) -> list:
    """按 IRQ/系统异常向量合并中断；主源优先，别名保留。"""
    ordered = sorted(
        parsed.items(),
        key=lambda item: (item[0] != primary_source, item[0]),
    )
    merged: dict[tuple, Any] = {}
    aliases: dict[tuple, list[str]] = {}
    for _source, interrupts in ordered:
        for irq in interrupts or []:
            irq_number = int(getattr(irq, "irq_number", -1))
            name = str(getattr(irq, "name", "") or "")
            key = ("irq", irq_number) if irq_number >= 0 else ("vector", str(getattr(irq, "vector_number", "")))
            if key not in merged:
                merged[key] = irq
                aliases[key] = list(getattr(irq, "aliases", []) or [name])
            else:
                for alias in getattr(irq, "aliases", []) or [name]:
                    if alias and alias not in aliases[key]:
                        aliases[key].append(alias)
    out = []
    for key, irq in merged.items():
        names = aliases[key]
        update = {
            "aliases": names,
            "semantic_path": f"interrupt/{getattr(irq, 'name', '')}",
            "multi_source_agreement": "consistent" if len(parsed) > 1 else "single_source",
        }
        model_copy = getattr(irq, "model_copy", None)
        out.append(model_copy(update=update) if callable(model_copy) else irq)
    out.sort(key=lambda x: (int(getattr(x, "irq_number", -1)), str(getattr(x, "name", ""))))
    return out


def _collect_provenance(chip_data: Any) -> list[dict]:
    out: list[dict] = []
    for irq in getattr(chip_data, "interrupts", []) or []:
        ref = dict(getattr(irq, "source_ref", {}) or {})
        if ref:
            out.append({
                "level": "interrupt",
                "peripheral": "",
                "path": getattr(irq, "name", ""),
                **ref,
            })

    for pblk in getattr(chip_data, "peripherals", []) or []:
        refs = [("peripheral", pblk, "")]
        for reg in getattr(pblk, "registers", []) or []:
            refs.append(("register", reg, reg.name))
            for fld in getattr(reg, "fields", []) or []:
                refs.append(("field", fld, f"{reg.name}.{fld.name}"))
        for level, entity, path in refs:
            ref = dict(getattr(entity, "source_ref", {}) or {})
            if ref:
                out.append({
                    "level": level,
                    "peripheral": getattr(pblk, "name", ""),
                    "path": path,
                    **ref,
                })
    return out


def _summarize_review_semantics(chip_data: Any, store: Optional[CorrectionStore]) -> dict:
    from .correction_store import parse_completeness
    completeness: dict[str, int] = {"complete": 0, "partial": 0, "incomplete": 0, "unknown": 0}
    authority: dict[str, int] = {}
    for irq in getattr(chip_data, "interrupts", []) or []:
        entities = [(irq, "interrupt")]
        for entity, level in entities:
            value = getattr(entity, "parse_completeness", "") or parse_completeness(entity, level)
            completeness[value] = completeness.get(value, 0) + 1
            auth = getattr(entity, "source_authority", "") or "machine_extracted"
            authority[auth] = authority.get(auth, 0) + 1
    for pblk in getattr(chip_data, "peripherals", []) or []:
        entities = [(pblk, "peripheral")]
        for reg in getattr(pblk, "registers", []) or []:
            entities.append((reg, "register"))
            for fld in getattr(reg, "fields", []) or []:
                entities.append((fld, "field"))
        for entity, level in entities:
            value = getattr(entity, "parse_completeness", "") or parse_completeness(entity, level)
            completeness[value] = completeness.get(value, 0) + 1
            auth = getattr(entity, "source_authority", "") or "machine_extracted"
            authority[auth] = authority.get(auth, 0) + 1
    summary = store.summary() if store else {
        MACHINE: 0, CONFIRMED: 0, REJECTED: 0, IGNORED: 0,
    }
    return {
        "source_authority": authority,
        "parse_completeness": completeness,
        "manual_confirmation": {
            "pending": summary.get(MACHINE, 0),
            "confirmed": summary.get(CONFIRMED, 0),
            "rejected": summary.get(REJECTED, 0),
            "ignored": summary.get(IGNORED, 0),
        },
    }


def _summarize_confidence(peripherals: list) -> dict:
    """统计外设/寄存器/位域的置信度分布。"""
    levels = ("high", "medium", "low", "missing", "unknown")
    field_conf = {lv: 0 for lv in levels}
    reg_conf = {lv: 0 for lv in levels}
    for periph in peripherals or []:
        for reg in periph.registers or []:
            rc = (getattr(reg, "confidence", "unknown") or "unknown")
            if rc in reg_conf:
                reg_conf[rc] += 1
            for f in reg.fields or []:
                fc = (getattr(f, "confidence", "unknown") or "unknown")
                if fc in field_conf:
                    field_conf[fc] += 1
    return {
        "peripherals": len(peripherals or []),
        "registers": sum(reg_conf.values()),
        "fields": sum(field_conf.values()),
        "field_confidence": field_conf,
        "register_confidence": reg_conf,
    }
