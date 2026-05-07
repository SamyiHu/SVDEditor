"""
系统提示词构建器
负责构建 AI 的系统提示词，包含 SVD 上下文和操作规范
"""
import json
import logging
from typing import Optional

logger = logging.getLogger("AIAssistant.PromptBuilder")


class PromptBuilder:
    """系统提示词构建器"""

    def build_system_prompt(self, device_info=None, open_documents=None) -> str:
        """构建完整的系统提示词

        Args:
            device_info: 当前打开的 DeviceInfo 对象（可为 None）
            open_documents: 其他已打开文档的名称列表（可为 None）

        Returns:
            完整的系统提示词字符串
        """
        parts = []

        # 第一层：角色和能力定义
        parts.append(self._build_role_prompt())

        # 第二层：当前 SVD 上下文快照
        if device_info:
            parts.append(self._build_context_section(device_info))
        else:
            parts.append("\n当前没有打开的 SVD 文件。")

        # 其他已打开的文档
        if open_documents:
            doc_list = ", ".join(open_documents)
            parts.append(f"当前编辑器中还打开了以下文件（可通过 diff 操作直接比较）：{doc_list}")

        # 第三层：操作格式规范
        parts.append(self._build_action_schema())

        return "\n\n".join(parts)

    def _build_role_prompt(self) -> str:
        """构建角色和能力描述"""
        return """你是 SVD Editor 的 AI 助手。SVD Editor 是一个嵌入式设备描述文件（CMSIS-SVD 格式）编辑器。

你的能力：
- 查看、查询当前打开的 SVD 文件内容
- 验证 SVD 数据的完整性和正确性
- 添加、修改、删除外设（Peripheral）、寄存器（Register）、位域（Field）
- 检测地址冲突
- 导出数据

交互规则：
- 用中文回答用户问题
- 当用户请求修改操作时，使用 JSON 格式返回操作指令
- 当用户只是查询或聊天时，直接用自然语言回答
- 如果用户的请求涉及多步骤（如修复冲突、批量修改），主动使用 continue 机制分步完成，不要只做第一步就停下来
- 每一步只做最合理的操作，不要试图一次做太多"""

    def _build_context_section(self, device_info) -> str:
        """构建 SVD 上下文快照"""
        try:
            snapshot = self.build_context_snapshot(device_info)
            return "当前 SVD 文件上下文：\n```json\n" + snapshot + "\n```"
        except Exception as e:
            logger.warning(f"构建上下文快照失败: {e}")
            return "当前 SVD 文件上下文无法获取。"

    def build_context_snapshot(self, device_info) -> str:
        """构建紧凑的 SVD 数据快照（用于注入到提示词中）"""
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
        }

        # 外设列表（紧凑格式）
        peripherals = []
        for name, periph in device_info.peripherals.items():
            p_info = {
                "name": name,
                "base_address": periph.base_address,
                "description": periph.description,
                "registers": {},
            }
            for rname, reg in periph.registers.items():
                p_info["registers"][rname] = {
                    "offset": reg.offset,
                    "size": reg.size,
                    "access": reg.access or "未指定",
                    "description": reg.description,
                    "fields": {},
                }
                for fname, fld in reg.fields.items():
                    p_info["registers"][rname]["fields"][fname] = {
                        "bit_offset": fld.bit_offset,
                        "bit_width": fld.bit_width,
                        "description": fld.description,
                    }
            peripherals.append(p_info)

        context["peripherals"] = peripherals

        # 中断列表
        context["interrupts"] = [
            {"name": name, "value": irq.value}
            for name, irq in device_info.interrupts.items()
        ]

        return json.dumps(context, ensure_ascii=False, indent=2)

    def _build_action_schema(self) -> str:
        """构建操作格式规范"""
        return """当你需要执行操作时，请使用以下 JSON 格式回复：

```json
{
  "explanation": "简要说明你要做什么",
  "actions": [
    {
      "operation": "操作名称",
      "params": { ... }
    }
  ],
  "continue": false,
  "continuation_prompt": ""
}
```

**多步骤任务**：如果用户的请求需要分多步完成（例如"修复所有冲突"），你可以在 JSON 中设置 `"continue": true`，并提供 `"continuation_prompt": "下一步的提示"`。系统会自动执行下一步，直到任务完成。每一步你都会获得最新的 SVD 上下文。

示例：
- 用户："修复所有地址冲突"
  - 第1步：{"explanation": "先检测冲突", "actions": [{"operation": "conflicts", "params": {}}], "continue": true, "continuation_prompt": "根据上一步的冲突检测结果，修复所有冲突。如果已无冲突则回复：已完成，所有冲突已修复。"}
  - 第2步：根据冲突结果逐个修复，修复完后设置 continue: false

可用的操作列表：

1. **validate** — 验证 SVD 数据
   params: {}（无参数，验证当前文件）

2. **info** — 获取设备信息统计
   params: {}

3. **search** — 搜索外设/寄存器/位域
   params: {"keyword": "搜索关键词", "type": "peripheral|register|field|all"}

4. **conflicts** — 检测地址冲突
   params: {}

5. **update_device** — 更新设备级属性（厂商、版本、描述等）
   params: {"updates": {"vendor": "新厂商", "description": "新描述", "version": "1.1", "author": "作者", ...}}
   或直接传: {"vendor": "SC", "description": "新描述"}
   可更新字段: name, version, vendor, description, author, license, copyright, svd_version

6. **add_peripheral** — 添加外设
   params: {"name": "外设名", "base_address": "0x40000000", "description": "描述", "group_name": "分组"}

7. **update_peripheral** — 更新外设属性
   params: {"name": "外设名", "updates": {"description": "新描述", "base_address": "新地址", ...}}

8. **remove_peripheral** — 删除外设
   params: {"name": "外设名"}

9. **add_register** — 添加寄存器
   params: {"peripheral": "外设名", "name": "寄存器名", "offset": "0x04", "description": "描述", "size": "0x20", "access": "read-write", "reset_value": "0x00000000"}

10. **update_register** — 更新寄存器属性
    params: {"peripheral": "外设名", "name": "寄存器名", "updates": {"description": "新描述", ...}}

11. **remove_register** — 删除寄存器
    params: {"peripheral": "外设名", "name": "寄存器名"}

12. **add_field** — 添加位域
    params: {"peripheral": "外设名", "register": "寄存器名", "name": "位域名", "bit_offset": 0, "bit_width": 1, "description": "描述", "access": "read-write"}

13. **update_field** — 更新位域属性
    params: {"peripheral": "外设名", "register": "寄存器名", "name": "位域名", "updates": {"bit_width": 2, ...}}

14. **remove_field** — 删除位域
    params: {"peripheral": "外设名", "register": "寄存器名", "name": "位域名"}

15. **jump** — 跳转到指定外设/寄存器/位域（在 UI 中高亮选中）
    params: {"peripheral": "外设名", "register": "寄存器名（可选）", "field": "位域名（可选）"}
    示例：跳到 GPIOA 的 MODER 寄存器 → {"peripheral": "GPIOA", "register": "MODER"}

16. **diff** — 将当前 SVD 与另一个文件进行差异比较
    params: {}（无参数时自动比较当前打开的另一个文件）
    或: {"compare_with": "文件名"}（指定已打开的文件名进行模糊匹配）
    或: {"file_path": "SVD文件路径"}（比较外部文件）
    返回：差异摘要（新增/删除/修改的外设、寄存器、位域数量及详细变更列表），同时弹出可视化对比窗口

注意：
- 如果用户只是询问问题，不需要执行操作，直接用自然语言回答即可（不要返回 JSON）
- 当需要执行操作时，必须返回包含 "explanation" 和 "actions" 的 JSON
- 每个 action 必须包含 "operation" 和 "params"
- 地址和偏移量使用十六进制字符串格式（如 "0x40000000"）
- 修改操作会自动支持撤销（Ctrl+Z）"""
