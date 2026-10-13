"""SVDEditor MCP Server — 让外部 AI 客户端（ZCode / Claude Desktop / Cursor 等）
通过 MCP 直接查询、编辑、校验、导出 SVD 文件。

按 docs/MCP_DESIGN.md 的分阶段计划：
- 当前为 Phase 1（Headless）：文件级操作，不依赖 PyQt；编辑只进内存，
  svd_save_document 显式落盘（自动 .bak 备份）
- Phase 2 的 GUI Bridge 模式（实时联动 / 截图 / 跳转）规划中，届时工具语义不变

启动方式：
    python run.py --mcp          # 源码运行
    python -m svd_tool.mcp_server
    svd-editor-mcp               # pip install 后的 console_script
"""
from __future__ import annotations

import logging
import sys
from typing import Any, Dict, List, Optional

try:  # mcp>=2：FastMCP 更名为 MCPServer
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP

from .headless_workspace import HeadlessWorkspace

logger = logging.getLogger("svd_tool.mcp_server")

mcp: FastMCP = FastMCP(
    "svd-editor",
    instructions=(
        "SVDEditor MCP —— CMSIS-SVD 文件编辑器。\n"
        "典型工作流：svd_open 打开 .svd → svd_device_info 看整体 → svd_get_peripheral/"
        "svd_get_register/svd_get_field 分层查细节 → 增删改 → svd_validate 与 svd_conflicts "
        "校验 → svd_save_document 落盘（覆盖前自动 .bak 备份）。\n"
        "约定：地址/偏移/复位值等统一用十六进制字符串（如 \"0x40000000\"）；"
        "多文档用 doc_id 区分，不传则作用于活跃文档；编辑只进内存，保存后才写文件。"
    ),
)

ws = HeadlessWorkspace()


# ════════════════════════════════════════════════════
# 文档管理
# ════════════════════════════════════════════════════

@mcp.tool()
def svd_open(path: str, doc_id: str = "") -> dict:
    """打开一个 SVD 文件到工作区（解析为内存文档）。返回 doc_id，后续操作用它引用。

    Args:
        path: SVD 文件路径（建议绝对路径）
        doc_id: 可选自定义文档 ID；默认用文件名去扩展名
    """
    return ws.open_document(path, doc_id=doc_id or None)


@mcp.tool()
def svd_list_documents() -> dict:
    """列出工作区已打开的所有文档（doc_id、设备名、文件路径、是否有未保存修改、活跃标记）。"""
    return ws.list_documents()


@mcp.tool()
def svd_switch_document(doc_id: str) -> dict:
    """切换活跃文档（之后不带 doc_id 参数的操作都作用于它）。"""
    return ws.switch_document(doc_id)


@mcp.tool()
def svd_close_document(doc_id: str = "") -> dict:
    """关闭文档（未保存的修改将被丢弃，关闭前请先 svd_save_document）。"""
    return ws.close_document(doc_id=doc_id or None)


@mcp.tool()
def svd_save_document(doc_id: str = "", path: str = "") -> dict:
    """把文档保存为 SVD XML 文件。覆盖已存在文件前自动生成 .bak 备份。

    Args:
        doc_id: 要保存的文档；默认活跃文档
        path: 目标路径；默认保存回原文件路径
    """
    return ws.save_document(doc_id=doc_id or None, path=path or None)


@mcp.tool()
def svd_regenerate_xml(doc_id: str = "") -> dict:
    """按标准格式重新生成整份 SVD XML 文本（不落盘），可直接查看/复制。"""
    return ws.regenerate_xml(doc_id=doc_id or None)


# ════════════════════════════════════════════════════
# 查询（分层获取，控制上下文长度）
# ════════════════════════════════════════════════════

@mcp.tool()
def svd_device_info(doc_id: str = "") -> dict:
    """设备摘要：名称/版本/厂商/CPU + 外设/寄存器/位域/中断统计 + 外设名与基地址列表。
    建议先调这个看整体，再逐层 get 细节。"""
    return ws.device_info(doc_id=doc_id or None)


@mcp.tool()
def svd_search(keyword: str, type: str = "all", limit: int = 50, offset: int = 0,
               doc_id: str = "") -> dict:
    """按名字搜索外设/寄存器/位域，支持分页（大文件防爆上下文）。

    Args:
        keyword: 关键词（子串匹配，不区分大小写）
        type: 范围 all / peripheral / register / field
        limit: 单页条数（1-200，默认 50）；offset: 偏移
    """
    return ws.search(keyword, search_type=type, limit=limit, offset=offset,
                     doc_id=doc_id or None)


@mcp.tool()
def svd_get_peripheral(name: str, doc_id: str = "") -> dict:
    """外设详情：基地址/描述/derivedFrom + 寄存器列表（含 cluster 来源，不含位域细节）。"""
    return ws.get_peripheral(name, doc_id=doc_id or None)


@mcp.tool()
def svd_get_register(peripheral: str, register: str, doc_id: str = "") -> dict:
    """寄存器详情：偏移/位宽/访问/复位值 + 位域列表（不含枚举值细节）。"""
    return ws.get_register(peripheral, register, doc_id=doc_id or None)


@mcp.tool()
def svd_get_field(peripheral: str, register: str, field: str, doc_id: str = "") -> dict:
    """位域完整详情：bit 偏移/位宽/访问/复位值/描述/枚举值。"""
    return ws.get_field(peripheral, register, field, doc_id=doc_id or None)


@mcp.tool()
def svd_list_interrupts(doc_id: str = "") -> dict:
    """列出设备全部中断（名称、IRQ 号、描述、关联外设）。"""
    return ws.list_interrupts(doc_id=doc_id or None)


# ════════════════════════════════════════════════════
# 编辑（内存操作，svd_save_document 才落盘）
# ════════════════════════════════════════════════════

@mcp.tool()
def svd_update_device(updates: Dict[str, Any], doc_id: str = "") -> dict:
    """更新设备级属性。updates 支持 name/version/vendor/description/author/license/copyright/svd_version。"""
    return ws.update_device(updates, doc_id=doc_id or None)


@mcp.tool()
def svd_add_peripheral(name: str, base_address: str = "0x40000000",
                       description: str = "", group_name: str = "", doc_id: str = "") -> dict:
    """添加外设（名称 + 基地址，十六进制字符串如 0x40010000）。"""
    return ws.add_peripheral(name, base_address=base_address, description=description,
                             group_name=group_name, doc_id=doc_id or None)


@mcp.tool()
def svd_update_peripheral(name: str, updates: Dict[str, Any], doc_id: str = "") -> dict:
    """更新外设属性。updates 支持 name（改名）/base_address/description/group_name/display_name/derived_from。"""
    return ws.update_peripheral(name, updates, doc_id=doc_id or None)


@mcp.tool()
def svd_remove_peripheral(name: str, doc_id: str = "") -> dict:
    """删除外设（连同其寄存器与位域）。"""
    return ws.remove_peripheral(name, doc_id=doc_id or None)


@mcp.tool()
def svd_add_register(peripheral: str, name: str, offset: str = "0x00",
                     description: str = "", size: str = "0x20", access: str = "",
                     reset_value: str = "0x00000000", doc_id: str = "") -> dict:
    """向外设添加寄存器。offset/size/reset_value 用十六进制字符串；access 如 read-write（可空）。"""
    return ws.add_register(peripheral, name, offset=offset, description=description,
                           size=size, access=access or None, reset_value=reset_value,
                           doc_id=doc_id or None)


@mcp.tool()
def svd_update_register(peripheral: str, name: str, updates: Dict[str, Any],
                        doc_id: str = "") -> dict:
    """更新寄存器属性。updates 支持 name/offset/size/access/reset_value/reset_mask/description/
    display_name/derived_from/dim/dim_increment/dim_index（dim 数组三件套）。"""
    return ws.update_register(peripheral, name, updates, doc_id=doc_id or None)


@mcp.tool()
def svd_remove_register(peripheral: str, name: str, doc_id: str = "") -> dict:
    """删除指定寄存器。"""
    return ws.remove_register(peripheral, name, doc_id=doc_id or None)


@mcp.tool()
def svd_add_field(peripheral: str, register: str, name: str, bit_offset: int = 0,
                  bit_width: int = 1, description: str = "", access: str = "",
                  reset_value: str = "0x0", doc_id: str = "") -> dict:
    """向寄存器添加位域（bit 偏移与位宽用十进制整数）。"""
    return ws.add_field(peripheral, register, name, bit_offset=bit_offset,
                        bit_width=bit_width, description=description,
                        access=access or None, reset_value=reset_value,
                        doc_id=doc_id or None)


@mcp.tool()
def svd_update_field(peripheral: str, register: str, name: str,
                     updates: Dict[str, Any], doc_id: str = "") -> dict:
    """更新位域属性。updates 支持 name/bit_offset/bit_width/access/reset_value/description/
    display_name/enumerated_values。"""
    return ws.update_field(peripheral, register, name, updates, doc_id=doc_id or None)


@mcp.tool()
def svd_remove_field(peripheral: str, register: str, name: str, doc_id: str = "") -> dict:
    """删除指定位域。"""
    return ws.remove_field(peripheral, register, name, doc_id=doc_id or None)


@mcp.tool()
def svd_add_interrupt(name: str, value: int, description: str = "",
                      peripherals: Optional[List[str]] = None, doc_id: str = "") -> dict:
    """添加中断（name + IRQ 号 value，十进制整数；peripherals 为关联外设名列表）。"""
    return ws.add_interrupt(name, value, description=description,
                            peripherals=peripherals, doc_id=doc_id or None)


@mcp.tool()
def svd_update_interrupt(name: str, updates: Dict[str, Any], doc_id: str = "") -> dict:
    """更新中断。updates 支持 name/value/description/peripherals。"""
    return ws.update_interrupt(name, updates, doc_id=doc_id or None)


@mcp.tool()
def svd_remove_interrupt(name: str, doc_id: str = "") -> dict:
    """删除中断。"""
    return ws.remove_interrupt(name, doc_id=doc_id or None)


# ════════════════════════════════════════════════════
# 校验与对比
# ════════════════════════════════════════════════════

@mcp.tool()
def svd_validate(doc_id: str = "") -> dict:
    """CMSIS-SVD 规范校验（必需字段、位域重叠、derivedFrom 引用、addressBlock 等），返回错误/警告明细。"""
    return ws.validate(doc_id=doc_id or None)


@mcp.tool()
def svd_conflicts(doc_id: str = "") -> dict:
    """地址冲突检测（外设地址重叠、寄存器偏移重复、位域冲突）。"""
    return ws.conflicts(doc_id=doc_id or None)


@mcp.tool()
def svd_diff(doc_a: str, doc_b: str, peripheral: str = "") -> dict:
    """对比两个已打开文档的结构差异（外设/寄存器/位域级）；指定 peripheral 则只对比该外设。"""
    return ws.diff(doc_a, doc_b, peripheral=peripheral or None)


# ════════════════════════════════════════════════════
# 输出
# ════════════════════════════════════════════════════

@mcp.tool()
def svd_export(format: str, out_path: str = "", peripheral: str = "", doc_id: str = "") -> dict:
    """导出寄存器文档。format: csv / markdown / html；out_path 省略时导出到当前目录默认文件名。"""
    return ws.export(format, out_path=out_path or None, peripheral=peripheral or None,
                     doc_id=doc_id or None)


@mcp.tool()
def svd_generate_header(out_path: str = "", style: str = "upper_case", prefix: str = "",
                        cmsis: bool = False, doc_id: str = "") -> dict:
    """从 SVD 生成 C 头文件（寄存器地址宏 + 位域掩码）。cmsis=True 生成 CMSIS 风格。
    不给 out_path 时仅返回预览。"""
    return ws.generate_header(out_path=out_path or None, style=style, prefix=prefix,
                              cmsis=cmsis, doc_id=doc_id or None)


# ════════════════════════════════════════════════════
# 入口
# ════════════════════════════════════════════════════

def _redirect_logging_to_stderr() -> None:
    """MCP stdio 模式下 stdout 属于协议流，任何日志处理器都不得写入 stdout。

    svd_tool 的 LoggerManager 默认把 INFO 级日志打到 stdout（GUI 场景正常），
    这里把现存所有指向 stdout 的 StreamHandler 重定向到 stderr。
    """
    import logging

    candidates = [logging.getLogger()]
    candidates += [
        logging.getLogger(name)
        for name, obj in logging.Logger.manager.loggerDict.items()
        if isinstance(obj, logging.Logger)
    ]
    for lg in candidates:
        for h in list(lg.handlers):
            if isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is sys.stdout:
                h.stream = sys.stderr


def main() -> None:
    """stdio 模式启动（MCP 客户端标准拉起方式）。"""
    if sys.platform == "win32":
        # Windows 控制台默认 GBK，防中文日志乱码
        for name in ("stdout", "stderr"):
            stream = getattr(sys, name, None)
            if stream and hasattr(stream, "reconfigure"):
                try:
                    stream.reconfigure(encoding="utf-8")
                except Exception:  # noqa: BLE001
                    pass
    _redirect_logging_to_stderr()
    logger.info("svd-editor MCP server 启动（stdio, headless）")
    mcp.run()  # 默认 stdio transport


if __name__ == "__main__":
    main()
