"""
数据源集成核心层 — 把外部 Parser 包（Excel/Word/PDF 多源解析）接入 SVDEditor。

三层：
- parser_bridge:         线程封装地调用 Parser 包（单源 / 多源融合）
- chip_to_svd_converter: Parser 的 ChipData → 编辑器 DeviceInfo
- svd_verifier:          当前 SVD 与解析结果的结构化核对

Parser 包位于仓库同级目录 ../Parser，可 pip install -e ../Parser，
亦可由本层通过 sys.path 兜底自动发现（无需安装即可开发）。
"""
from .parser_bridge import (
    ParseRequest,
    ParseResult,
    ParserBridge,
    ParserUnavailableError,
    is_parser_available,
)
from .chip_to_svd_converter import (
    ChipToSvdConverter,
    ConversionIssue,
    ConversionReport,
)
from .svd_verifier import (
    SVDVerifier,
    VerifyItem,
    VerifySeverity,
    VerifyKind,
)

__all__ = [
    # bridge
    "ParseRequest", "ParseResult", "ParserBridge",
    "ParserUnavailableError", "is_parser_available",
    # converter
    "ChipToSvdConverter", "ConversionIssue", "ConversionReport",
    # verifier
    "SVDVerifier", "VerifyItem", "VerifySeverity", "VerifyKind",
]
