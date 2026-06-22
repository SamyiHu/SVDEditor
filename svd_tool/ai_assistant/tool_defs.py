"""
Function-calling 工具定义注册表

集中定义所有暴露给 AI 的工具 schema（与具体 API 协议无关的内部统一结构），
并提供向 OpenAI / Anthropic 两种 wire format 的转换，以及工具分发执行。

内部工具结构（每项）：
{
  "name": str,
  "description": str,
  "parameters": <JSON Schema dict>,   # OpenAI 风格的 parameters
  "category": "read" | "write" | "ui",  # 用于决定结果如何回灌
}

工具的执行复用 CommandExecutor.execute(action) -> {success, message, data}。
"""
import logging
from typing import Any, Dict, List

logger = logging.getLogger("AIAssistant.ToolDefs")


# ==================== 工具 schema 定义 ====================

def _build_tool_catalog() -> List[Dict[str, Any]]:
    """构建工具目录。每次调用返回新副本，避免外部误改共享状态。"""
    return [
        # ---------- 只读查询工具（结果回灌 AI，供其推理） ----------
        {
            "name": "info",
            "description": "获取当前 SVD 文件的设备信息和统计摘要（外设/寄存器/位域/中断数量、外设名列表）。无需参数。",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            "category": "read",
        },
        {
            "name": "search",
            "description": "按关键词搜索外设/寄存器/位域的名字。返回匹配项列表（仅名字和所属层级，不含属性细节）。用于定位。结果分页。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "搜索关键词（不区分大小写，子串匹配）"},
                    "type": {"type": "string", "enum": ["peripheral", "register", "field", "all"],
                             "description": "限定搜索的层级，默认 all"},
                    "limit": {"type": "integer", "description": "单页返回上限，默认 50，最大 200", "default": 50},
                    "offset": {"type": "integer", "description": "分页偏移，默认 0", "default": 0},
                },
                "required": ["keyword"],
            },
            "category": "read",
        },
        {
            "name": "get_peripheral",
            "description": "获取指定外设的元信息和寄存器列表（寄存器名/偏移/位宽/访问权限/复位值/描述，不含位域）。合并寄存器簇内的寄存器。需要细节时用 get_register。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "外设名"},
                },
                "required": ["name"],
            },
            "category": "read",
        },
        {
            "name": "get_register",
            "description": "获取指定寄存器的元信息和位域列表（位域名/位偏移/位宽/访问权限/描述，不含枚举值）。需要枚举值细节时用 get_field。",
            "parameters": {
                "type": "object",
                "properties": {
                    "peripheral": {"type": "string", "description": "外设名"},
                    "register": {"type": "string", "description": "寄存器名"},
                },
                "required": ["peripheral", "register"],
            },
            "category": "read",
        },
        {
            "name": "get_field",
            "description": "获取单个位域的完整信息（含 enumerated_values 枚举值定义）。仅在需要枚举值细节时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "peripheral": {"type": "string", "description": "外设名"},
                    "register": {"type": "string", "description": "寄存器名"},
                    "field": {"type": "string", "description": "位域名"},
                },
                "required": ["peripheral", "register", "field"],
            },
            "category": "read",
        },
        {
            "name": "list_interrupts",
            "description": "列出设备所有中断（名称/中断号/描述/关联外设）。无需参数。",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            "category": "read",
        },
        {
            "name": "conflicts",
            "description": "检测当前 SVD 的地址冲突。返回冲突列表（最多 20 条）和总数。无需参数。",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            "category": "read",
        },
        {
            "name": "validate",
            "description": "验证当前 SVD 数据的完整性和正确性，返回错误/警告统计。无需参数。",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            "category": "read",
        },
        # ---------- 写操作工具（结果紧凑回灌 AI） ----------
        {
            "name": "update_device",
            "description": "更新设备级属性（厂商/版本/描述/作者等）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "updates": {"type": "object", "description": "要更新的字段键值对，可用键: name, version, vendor, description, author, license, copyright, svd_version"},
                },
            },
            "category": "write",
        },
        {
            "name": "add_peripheral",
            "description": "添加一个外设。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "base_address": {"type": "string", "description": "十六进制地址，如 0x40000000"},
                    "description": {"type": "string"},
                    "group_name": {"type": "string"},
                },
                "required": ["name"],
            },
            "category": "write",
        },
        {
            "name": "update_peripheral",
            "description": "更新外设属性（描述/基地址/分组等）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "updates": {"type": "object"},
                },
                "required": ["name"],
            },
            "category": "write",
        },
        {
            "name": "remove_peripheral",
            "description": "删除一个外设。",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
            "category": "write",
        },
        {
            "name": "add_register",
            "description": "在指定外设下添加一个寄存器。",
            "parameters": {
                "type": "object",
                "properties": {
                    "peripheral": {"type": "string"},
                    "name": {"type": "string"},
                    "offset": {"type": "string", "description": "十六进制偏移，如 0x04"},
                    "description": {"type": "string"},
                    "size": {"type": "string"},
                    "access": {"type": "string"},
                    "reset_value": {"type": "string"},
                },
                "required": ["peripheral", "name"],
            },
            "category": "write",
        },
        {
            "name": "update_register",
            "description": "更新寄存器属性。",
            "parameters": {
                "type": "object",
                "properties": {
                    "peripheral": {"type": "string"},
                    "name": {"type": "string"},
                    "updates": {"type": "object"},
                },
                "required": ["peripheral", "name"],
            },
            "category": "write",
        },
        {
            "name": "remove_register",
            "description": "删除一个寄存器。",
            "parameters": {
                "type": "object",
                "properties": {
                    "peripheral": {"type": "string"},
                    "name": {"type": "string"},
                },
                "required": ["peripheral", "name"],
            },
            "category": "write",
        },
        {
            "name": "add_field",
            "description": "在指定寄存器下添加一个位域。",
            "parameters": {
                "type": "object",
                "properties": {
                    "peripheral": {"type": "string"},
                    "register": {"type": "string"},
                    "name": {"type": "string"},
                    "bit_offset": {"type": "integer"},
                    "bit_width": {"type": "integer"},
                    "description": {"type": "string"},
                    "access": {"type": "string"},
                },
                "required": ["peripheral", "register", "name"],
            },
            "category": "write",
        },
        {
            "name": "update_field",
            "description": "更新位域属性。",
            "parameters": {
                "type": "object",
                "properties": {
                    "peripheral": {"type": "string"},
                    "register": {"type": "string"},
                    "name": {"type": "string"},
                    "updates": {"type": "object"},
                },
                "required": ["peripheral", "register", "name"],
            },
            "category": "write",
        },
        {
            "name": "remove_field",
            "description": "删除一个位域。",
            "parameters": {
                "type": "object",
                "properties": {
                    "peripheral": {"type": "string"},
                    "register": {"type": "string"},
                    "name": {"type": "string"},
                },
                "required": ["peripheral", "register", "name"],
            },
            "category": "write",
        },
        # ---------- UI 副作用工具（回灌极简确认） ----------
        {
            "name": "jump",
            "description": "在 UI 中跳转并高亮选中指定外设/寄存器/位域。",
            "parameters": {
                "type": "object",
                "properties": {
                    "peripheral": {"type": "string"},
                    "register": {"type": "string", "description": "可选"},
                    "field": {"type": "string", "description": "可选"},
                },
                "required": ["peripheral"],
            },
            "category": "ui",
        },
        {
            "name": "diff",
            "description": "将当前 SVD 与另一个已打开文档或外部文件做差异比较，并弹出可视化对比窗口。",
            "parameters": {
                "type": "object",
                "properties": {
                    "compare_with": {"type": "string", "description": "已打开文档名（模糊匹配）"},
                    "file_path": {"type": "string", "description": "外部 SVD 文件路径"},
                },
            },
            "category": "ui",
        },
        {
            "name": "switch_document",
            "description": "切换到另一个已打开的文档。",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string"},
                    "name": {"type": "string", "description": "文档名（模糊匹配）"},
                },
            },
            "category": "ui",
        },
        {
            "name": "save_document",
            "description": "保存文档（默认当前文档到原路径）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string"},
                    "file_path": {"type": "string", "description": "另存为新路径（不指定则存原路径）"},
                },
            },
            "category": "ui",
        },
        {
            "name": "batch_save",
            "description": "批量保存多个文档。",
            "parameters": {
                "type": "object",
                "properties": {
                    "all": {"type": "boolean", "description": "保存所有文档"},
                    "doc_ids": {"type": "array", "items": {"type": "string"}},
                    "paths": {"type": "object", "description": "{doc_id: 新路径}，指定后原文件不动"},
                },
            },
            "category": "ui",
        },
    ]


# 模块级缓存：构建一次即可（schema 是只读的）
_CATALOG: List[Dict[str, Any]] = _build_tool_catalog()
_BY_NAME: Dict[str, Dict[str, Any]] = {t["name"]: t for t in _CATALOG}


def get_tool_names() -> List[str]:
    """所有工具名（按注册顺序）。"""
    return [t["name"] for t in _CATALOG]


def get_tool_category(name: str) -> str:
    """获取工具类别（read/write/ui），未知工具返回 read。"""
    return _BY_NAME.get(name, {}).get("category", "read")


# ==================== 协议转换 ====================

def to_openai_tools() -> List[Dict[str, Any]]:
    """转换为 OpenAI Chat Completions 的 tools 参数格式。

    结构：[{type:"function", function:{name, description, parameters}}]
    """
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            },
        }
        for t in _CATALOG
    ]


def to_anthropic_tools() -> List[Dict[str, Any]]:
    """转换为 Anthropic Messages 的 tools 参数格式。

    结构：[{name, description, input_schema}]（注意是 input_schema，不是 parameters）
    """
    return [
        {
            "name": t["name"],
            "description": t["description"],
            "input_schema": t["parameters"],
        }
        for t in _CATALOG
    ]


# ==================== 工具分发执行 ====================

def dispatch(name: str, params: Dict[str, Any], executor) -> Dict[str, Any]:
    """执行指定工具，复用 CommandExecutor.execute。

    Args:
        name: 工具名（operation 名）
        params: 工具参数
        executor: CommandExecutor 实例

    Returns:
        {"success": bool, "message": str, "data": any}
        执行器原有返回格式，agent_loop 据此构造回灌给 AI 的 tool 消息。
    """
    if name not in _BY_NAME:
        return {
            "success": False,
            "message": f"未知工具: {name}",
            "data": None,
        }
    action = {"operation": name, "params": params or {}}
    try:
        return executor.execute(action)
    except Exception as e:
        logger.error(f"工具 {name} 执行异常: {e}", exc_info=True)
        return {"success": False, "message": f"工具执行异常: {e}", "data": None}
