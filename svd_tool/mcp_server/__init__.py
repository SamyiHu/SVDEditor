"""SVDEditor MCP Server 包。

把 SVD 编辑能力以标准 MCP 工具暴露给外部 AI 客户端（设计见 docs/MCP_DESIGN.md）。
依赖 mcp SDK（pip install mcp），未安装时给出明确提示。
"""
try:
    from .server import main, mcp  # noqa: F401
except ImportError as _e:  # pragma: no cover
    raise ImportError(
        "MCP Server 需要 mcp 依赖：pip install mcp（或 pip install -e .[mcp]）"
    ) from _e
