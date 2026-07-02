"""
系统提示词构建器
负责构建 AI 的系统提示词，包含 SVD 上下文摘要和工具使用说明。

改造后：默认只发"设备信息 + 统计 + 外设名列表"的轻量摘要，
细节由 AI 通过 function-calling 工具按需获取（替代旧的全文注入）。
"""
import json
import logging
from typing import Optional

from ..i18n.i18n import get_i18n_manager, t

logger = logging.getLogger("svd_tool.ai_assistant.PromptBuilder")


class PromptBuilder:
    """系统提示词构建器"""

    def build_system_prompt(self, device_info=None, open_documents=None) -> str:
        """构建完整的系统提示词"""
        parts = []

        # 第一层：角色和能力定义
        parts.append(self._build_role_prompt())

        # 第二层：当前 SVD 上下文摘要（轻量，不含寄存器/位域细节）
        if device_info:
            parts.append(self._build_context_section(device_info))
        else:
            parts.append(t("ai.prompt.no_file", default="\n当前没有打开的 SVD 文件。"))

        # 其他已打开的文档
        if open_documents:
            if isinstance(open_documents, dict):
                active = open_documents.get("active")
                others = open_documents.get("others", [])
                if active:
                    parts.append(t("ai.prompt.active_doc", default="当前活跃文档") + f": {active['name']} (doc_id: {active['doc_id']}, {t('ai.prompt.path', default='路径')}: {active.get('file_path', t('ai.prompt.none', default='无'))})")
                if others:
                    doc_lines = []
                    for d in others:
                        modified = f" [{t('ai.prompt.modified', default='已修改')}]" if d.get("modified") else ""
                        doc_lines.append(f"  - {d['name']} (doc_id: {d['doc_id']}, {t('ai.prompt.path', default='路径')}: {d.get('file_path', t('ai.prompt.none', default='无'))}{modified})")
                    parts.append(t("ai.prompt.other_docs", default="其他已打开的文档") + ":\n" + "\n".join(doc_lines))
            else:
                # 兼容旧格式
                doc_list = ", ".join(open_documents)
                parts.append(t("ai.prompt.other_files", default="当前编辑器中还打开了以下文件（可通过 diff 操作直接比较）：") + f" {doc_list}")

        # 第三层：工具使用说明（替代旧的 JSON 动作格式规范）
        parts.append(self._build_tool_guidance())

        return "\n\n".join(parts)

    def _build_role_prompt(self) -> str:
        """构建角色和能力描述"""
        # 检测当前 UI 语言，决定 AI 回复语言
        i18n_mgr = get_i18n_manager()
        locale = i18n_mgr.locale if i18n_mgr else "zh_CN"
        lang_instruction = "- Respond in English" if locale.startswith("en") else "- 用中文回答用户问题"

        return f"""你是 SVD Editor 的 AI 助手。SVD Editor 是一个嵌入式设备描述文件（CMSIS-SVD 格式）编辑器。

你的能力：
- 查看、查询当前打开的 SVD 文件内容
- 验证 SVD 数据的完整性和正确性
- 添加、修改、删除外设（Peripheral）、寄存器（Register）、位域（Field）
- 检测地址冲突
- 导出数据

交互规则：
{lang_instruction}
- 你可以通过调用工具来查询 SVD 详情或执行修改操作，工具的具体定义见请求的 tools 参数
- 需要信息时，先调用查询工具（如 search/get_peripheral/get_register）获取，再回答
- 需要修改时，调用对应的写操作工具；执行后工具会返回结果，据结果判断是否成功、是否需要继续
- 如果用户只是闲聊或询问你已掌握的信息（如设备摘要），直接用自然语言回答，不必调用工具
- 涉及多步骤的任务（如修复所有冲突），可以连续调用多个工具分步完成，每步根据上一步的工具结果决定下一步"""

    def _build_context_section(self, device_info) -> str:
        """构建 SVD 上下文摘要（轻量）"""
        try:
            snapshot = self.build_context_snapshot(device_info)
            return t("ai.prompt.context_label", default="当前 SVD 文件上下文：") + "\n```json\n" + snapshot + "\n```"
        except Exception as e:
            logger.warning(f"构建上下文摘要失败: {e}")
            return t("ai.prompt.context_fail", default="当前 SVD 文件上下文无法获取。")

    def build_context_snapshot(self, device_info) -> str:
        """构建轻量的 SVD 数据摘要（设备信息 + 统计 + 外设名列表）。

        注意：不再展开寄存器/位域细节。需要细节时 AI 应调用 get_peripheral /
        get_register / get_field 工具按需获取，大幅减少 token 消耗。
        """
        if not device_info:
            return "{}"

        context = {
            "device": {
                "name": device_info.name,
                "version": device_info.version,
                "vendor": device_info.vendor,
                "description": device_info.description,
                "author": device_info.author,
                "copyright": device_info.copyright,
                "license": device_info.license,
                "cpu": device_info.cpu.name,
                "size": device_info.size,
                "svd_version": device_info.svd_version,
            },
            "statistics": {
                "peripherals": len(device_info.peripherals),
                "registers": sum(len(p.registers) for p in device_info.peripherals.values()),
                "fields": sum(
                    len(r.fields)
                    for p in device_info.peripherals.values()
                    for r in p.registers.values()
                ),
                "interrupts": len(device_info.interrupts),
            },
            # 外设名列表（含 base_address 和 derivedFrom 标记，不含寄存器/位域）
            "peripherals": [
                {
                    "name": name,
                    "base_address": periph.base_address,
                    "derived_from": periph.derived_from or None,
                }
                for name, periph in device_info.peripherals.items()
            ],
        }

        return json.dumps(context, ensure_ascii=False, indent=2)

    def _build_tool_guidance(self) -> str:
        """构建工具使用说明（替代旧的 JSON 动作格式规范）"""
        return """你可以通过调用工具来查询和修改 SVD 文件。工具的完整定义（名称、参数、说明）见每次请求的 tools 参数。

常用工具速览：
- 查询类：info（设备摘要）、search（按名字搜索）、get_peripheral（外设寄存器列表）、get_register（寄存器位域列表）、get_field（位域详情含枚举值）、list_interrupts（中断列表）、conflicts（地址冲突）、validate（校验）
- 修改类：update_device、add/update/remove_peripheral、add/update/remove_register、add/update/remove_field
- 界面类：jump（跳转高亮）、diff（差异比较）、open_document（打开新文件载入编辑器）、switch_document（切换已打开文档）、save_document、batch_save

使用建议：
- 信息分层获取：先用 info 看整体，再用 get_peripheral 看某外设的寄存器，需要时才用 get_register 看位域、get_field 看枚举值，避免一次取过多数据
- 地址和偏移量使用十六进制字符串（如 "0x40000000"）
- 修改操作支持撤销（Ctrl+Z）"""
