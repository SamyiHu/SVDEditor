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

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

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
    """
    sources: dict[str, str] = field(default_factory=dict)
    strategy: str = "single"
    primary_source: str = ""
    chip_name: str = ""


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
    """探测 Parser 包是否可导入（不触发其重依赖）。"""
    try:
        _ensure_parser_importable()
        import parser  # noqa: F401
        return True
    except Exception:
        return False


def _ensure_parser_importable() -> None:
    """确保 `import parser` 能找到外部 Parser 包。

    若已 pip install -e，则直接可用；否则把候选根目录加入 sys.path。
    Python 3.13+ 已移除 stdlib parser 模块，包名不冲突。
    """
    # 已在 sys.modules 或已可导入则跳过
    if "parser" in sys.modules:
        return
    import importlib.util
    if importlib.util.find_spec("parser") is not None:
        return
    # 兜底：把候选根加入 sys.path
    for root in _candidate_parser_roots():
        if os.path.isdir(os.path.join(root, "parser")):
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

    def _parse_source(self, registry, src: str, path: str) -> list:
        """解析单个来源。

        Word 来源优先用 TRMWordParser（针对 SC32/STM32 风格 TRM 三段式结构，
        含寄存器映射表 + 位域详表 + 归一化匹配，比 Parser 包原生 WordParser 准确得多）。
        若 TRM 解析拿到结果则用它；否则回退到 Parser 包原生 word 解析。
        Excel/PDF 走 Parser 包原生解析器。
        """
        from .trm_parser import TRMWordParser

        if src == "word":
            # 先试 TRM 解析器（pandoc→md 或 python-docx 回退）
            try:
                trm = TRMWordParser()
                if os.path.isdir(path):
                    periphs = trm.parse_dir(path)
                else:
                    periphs = trm.parse_file(path)
                if periphs:
                    return periphs
            except Exception as e:
                logger.warning(f"TRM 解析失败，回退到原生 word 解析: {e}")
            # 回退：Parser 包原生 WordParser
            periphs = registry.get_for_source(src).parse(path)
            from parser.quality_report import stamp_confidence
            stamp_confidence(periphs, "word")
            return periphs

        # Excel / PDF：原生解析器 + 置信度打标
        periphs = registry.get_for_source(src).parse(path)
        from parser.quality_report import stamp_confidence
        stamp_confidence(periphs, src)
        return periphs

    def parse_sync(self, request: ParseRequest) -> ParseResult:
        """执行解析。在 worker 线程内调用。"""
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

        # 2. 懒加载 Parser 包（捕获重依赖缺失）
        try:
            _ensure_parser_importable()
            from parser import default_registry, SourceFusion, FusionStrategy
            from parser.models import ChipData
            from parser.quality_report import stamp_confidence
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
        parse_errors: list[str] = []
        for src, path in request.sources.items():
            try:
                periphs = self._parse_source(registry, src, path)
                parsed[src] = periphs or []
                logger.info(f"解析 {src}（{path}）: {len(periphs or [])} 个外设")
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

        # 5. 装配 ChipData
        chip_name = request.chip_name.strip()
        if not chip_name:
            # 从第一个来源的路径推断设备名
            first_path = next(iter(request.sources.values()))
            chip_name = Path(first_path).stem or "UNKNOWN_DEVICE"
        result.chip_data = ChipData(chip_name=chip_name, peripherals=periphs or [])

        # 6. 置信度统计
        result.quality = _summarize_confidence(periphs or [])

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
