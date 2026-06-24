"""
命令执行器
将 AI 返回的操作指令翻译为对 DeviceInfo 的直接操作
所有修改操作通过 CommandHistory 支持撤销
"""
import logging
import re
from typing import Dict, Any, Optional

from ..i18n.i18n import t

logger = logging.getLogger("svd_tool.ai_assistant.CommandExecutor")


class CommandExecutor:
    """AI 操作执行器"""

    def __init__(self, coordinator, main_window=None):
        """
        Args:
            coordinator: 中央协调器，用于访问 StateManager 等
            main_window: 主窗口引用，用于访问 DocumentManager 等
        """
        self.coordinator = coordinator
        self.main_window = main_window
        self._operation_map = {
            "validate": self._op_validate,
            "info": self._op_info,
            "search": self._op_search,
            "conflicts": self._op_conflicts,
            "diff": self._op_diff,
            "jump": self._op_jump,
            # 片段查询工具（function-calling 专用，按需取 SVD 片段）
            "get_peripheral": self._op_get_peripheral,
            "get_register": self._op_get_register,
            "get_field": self._op_get_field,
            "list_interrupts": self._op_list_interrupts,
            "update_device": self._op_update_device,
            "add_peripheral": self._op_add_peripheral,
            "update_peripheral": self._op_update_peripheral,
            "remove_peripheral": self._op_remove_peripheral,
            "add_register": self._op_add_register,
            "update_register": self._op_update_register,
            "remove_register": self._op_remove_register,
            "add_field": self._op_add_field,
            "update_field": self._op_update_field,
            "remove_field": self._op_remove_field,
            # 多文档操作
            "switch_document": self._op_switch_document,
            "save_document": self._op_save_document,
            "batch_save": self._op_batch_save,
        }

    def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """执行一个操作

        Args:
            action: {"operation": "操作名", "params": {...}}

        Returns:
            {"success": bool, "message": str, "data": any}
        """
        operation = action.get("operation", "")
        params = action.get("params", {})

        handler = self._operation_map.get(operation)
        if not handler:
            return {
                "success": False,
                "message": t("ai.unknown_op", op=operation),
                "data": None
            }

        try:
            return handler(params)
        except Exception as e:
            logger.error(f"执行操作 {operation} 失败: {e}", exc_info=True)
            return {
                "success": False,
                "message": t("ai.op_failed", error=str(e)),
                "data": None
            }

    def _get_device_info(self):
        """获取当前 DeviceInfo"""
        state_manager = self.coordinator.get_component("state_manager")
        if state_manager:
            return state_manager.device_info
        return None

    def _execute_undoable(self, description: str, execute_fn, undo_fn):
        """执行可撤销的操作

        Args:
            description: 操作描述
            execute_fn: 执行函数
            undo_fn: 撤销函数
        """
        from svd_tool.core.command_history import Command

        state_manager = self.coordinator.get_component("state_manager")
        if state_manager and state_manager.command_history:
            cmd = Command(execute=execute_fn, undo=undo_fn, description=description)
            state_manager.command_history.execute(cmd)
        else:
            execute_fn()

    def _notify_refresh(self, peripheral_name: Optional[str] = None):
        """通知 UI 刷新。

        CommandExecutor 在 AgentLoop 工作线程里运行，而 state_manager 的
        _notify_state_change 内部会启动 QTimer、layout_manager 直接操作 QWidget。
        跨线程操作 GUI 对象（尤其 QTimer.start / QWidget）是未定义行为，批量任务下
        高频触发可能导致死锁或 Qt 告警刷屏。这里统一用 QTimer.singleShot(0, ...)
        把所有 GUI 相关调用派发回主线程执行。
        """
        from PyQt6.QtCore import QTimer

        def _do_refresh():
            try:
                state_manager = self.coordinator.get_component("state_manager")
                if state_manager:
                    state_manager._notify_state_change()

                if peripheral_name:
                    self.coordinator.notify_peripheral_updated(peripheral_name)

                # 刷新基本信息页面
                layout_manager = self.coordinator.get_component("layout_manager")
                if layout_manager and hasattr(layout_manager, 'update_basic_info') and state_manager:
                    try:
                        layout_manager.update_basic_info(state_manager.device_info)
                    except Exception:
                        pass
            except Exception:
                logger.debug("UI 刷新失败（可忽略）", exc_info=True)

        QTimer.singleShot(0, _do_refresh)

    # ==================== 只读操作 ====================

    def _op_validate(self, params: Dict) -> Dict[str, Any]:
        """验证 SVD 数据"""
        device = self._get_device_info()
        if not device or not device.name:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        try:
            from svd_tool.core.svd_schema_validator import SVDSchemaValidator
            validator = SVDSchemaValidator()
            results = validator.validate_all(device)
            summary = validator.get_summary()

            msg = t("ai.validate_done", errors=summary.get('errors', 0), warnings=summary.get('warnings', 0))
            return {"success": not summary.get("has_errors", True), "message": msg, "data": summary}
        except Exception as e:
            return {"success": False, "message": t("ai.validate_fail", error=str(e)), "data": None}

    def _op_info(self, params: Dict) -> Dict[str, Any]:
        """获取设备信息统计"""
        device = self._get_device_info()
        if not device or not device.name:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        info = {
            "device": device.name,
            "version": device.version,
            "vendor": device.vendor or t("ai.info_vendor"),
            "cpu": device.cpu.name,
            "size": device.size,
            "statistics": {
                "peripherals": len(device.peripherals),
                "registers": sum(len(p.registers) for p in device.peripherals.values()),
                "fields": sum(
                    len(r.fields)
                    for p in device.peripherals.values()
                    for r in p.registers.values()
                ),
                "interrupts": len(device.interrupts),
            },
            "peripheral_names": [
                f"{name} (derivedFrom={p.derived_from})" if p.derived_from else name
                for name, p in device.peripherals.items()
            ],
        }
        msg = t("ai.info_msg",
                name=device.name,
                periphs=info['statistics']['peripherals'],
                regs=info['statistics']['registers'],
                fields=info['statistics']['fields'],
                irqs=info['statistics']['interrupts'])
        return {"success": True, "message": msg, "data": info}

    def _op_search(self, params: Dict) -> Dict[str, Any]:
        """搜索外设/寄存器/位域（支持分页，避免大文件返回上千条）"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        keyword = params.get("keyword", "").lower()
        search_type = params.get("type", "all")
        if not keyword:
            return {"success": False, "message": t("ai.search_keyword_empty"), "data": None}

        # 分页参数：默认上限 50 条，防止巨型 SVD 单次返回过多
        try:
            limit = int(params.get("limit", 50))
        except (TypeError, ValueError):
            limit = 50
        try:
            offset = int(params.get("offset", 0))
        except (TypeError, ValueError):
            offset = 0
        limit = max(1, min(limit, 200))
        offset = max(0, offset)

        all_results = []

        if search_type in ("all", "peripheral"):
            for name, periph in device.peripherals.items():
                if keyword in name.lower():
                    entry = {"type": "peripheral", "name": name}
                    if periph.derived_from:
                        entry["derived_from"] = periph.derived_from
                    all_results.append(entry)

        if search_type in ("all", "register"):
            for pname, periph in device.peripherals.items():
                for rname in periph.registers:
                    if keyword in rname.lower():
                        all_results.append({"type": "register", "name": rname, "peripheral": pname})

        if search_type in ("all", "field"):
            for pname, periph in device.peripherals.items():
                for rname, reg in periph.registers.items():
                    for fname in reg.fields:
                        if keyword in fname.lower():
                            all_results.append({"type": "field", "name": fname, "peripheral": pname, "register": rname})

        total = len(all_results)
        page = all_results[offset:offset + limit]
        msg = t("ai.search_result", keyword=keyword, count=total)
        return {
            "success": True,
            "message": msg,
            "data": {
                "results": page,
                "total": total,
                "offset": offset,
                "limit": limit,
                "has_more": offset + limit < total,
            },
        }

    def _op_conflicts(self, params: Dict) -> Dict[str, Any]:
        """检测地址冲突"""
        device = self._get_device_info()
        if not device or not device.name:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        try:
            from svd_tool.core.address_conflict_detector import AddressConflictDetector
            detector = AddressConflictDetector()
            conflicts = detector.detect_all(device)

            if not conflicts:
                return {"success": True, "message": t("ai.conflicts_none"), "data": {"conflicts": [], "total": 0}}

            conflict_list = []
            for c in conflicts[:20]:
                conflict_list.append({
                    "type": str(c.conflict_type) if hasattr(c, 'conflict_type') else "unknown",
                    "severity": str(c.severity) if hasattr(c, 'severity') else "unknown",
                    "message": c.message if hasattr(c, 'message') else str(c),
                })

            msg = t("ai.conflicts_found", count=len(conflicts))
            return {
                "success": True,
                "message": msg,
                "data": {"conflicts": conflict_list, "total": len(conflicts), "shown": len(conflict_list)},
            }
        except Exception as e:
            return {"success": False, "message": t("ai.conflicts_fail", error=str(e)), "data": None}

    def _op_diff(self, params: Dict) -> Dict[str, Any]:
        """比较当前 SVD 与另一个文件或已打开的文档"""
        device = self._get_device_info()
        if not device or not device.name:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        other_device = None
        other_name = ""

        # 优先尝试从已打开的文档中获取
        compare_with = params.get("compare_with", "").strip()
        if compare_with or (not params.get("file_path") and not params.get("file")):
            other_device, other_name = self._resolve_other_device(compare_with)
            if other_device is None:
                # 返回错误，附带可用文档列表
                open_docs = self._get_open_documents_info()
                if not open_docs:
                    return {"success": False, "message": t("ai.diff_only_one"), "data": None}
                return {
                    "success": False,
                    "message": t("ai.diff_not_found", docs=', '.join(open_docs)),
                    "data": {"open_documents": open_docs}
                }

        # 如果未从打开的文档获取到，则尝试文件路径
        if other_device is None:
            file_path = params.get("file_path", "") or params.get("file", "")
            if isinstance(file_path, str):
                file_path = file_path.strip()
            if not file_path:
                # 没有提供路径，也没有其他打开的文档
                return {"success": False, "message": t("ai.diff_no_path"), "data": None}

            import os
            if not os.path.isfile(file_path):
                return {"success": False, "message": t("ai.diff_file_not_found", path=file_path), "data": None}

            try:
                from svd_tool.core.svd_parser import SVDParser
                parser = SVDParser()
                other_device = parser.parse_file(file_path)
                other_name = os.path.basename(file_path)
            except Exception as e:
                return {"success": False, "message": t("ai.diff_parse_fail", error=str(e)), "data": None}

        try:
            from svd_tool.core.svd_differ import SVDDiffer

            differ = SVDDiffer()
            diffs = differ.diff(device, other_device)

            if not diffs:
                return {"success": True, "message": t("ai.diff_identical", a=device.name, b=other_name), "data": []}

            summary = differ.generate_summary(diffs)
            diff_list = []
            total_changes = 0
            for d in diffs:
                count = d.count_changes
                total_changes += count
                diff_list.append({
                    "path": d.path,
                    "type": d.diff_type.name,
                    "changes": count,
                })

            result = {
                "success": True,
                "message": t("ai.diff_result", a=device.name, b=other_name, changes=total_changes, periphs=len(diffs)),
                "data": {
                    "source": device.name,
                    "target": other_name,
                    "total_changes": total_changes,
                    "peripheral_diffs": diff_list[:20],
                    "summary": summary[:2000] if summary else "",
                }
            }

            # 弹出可视化 diff 对话框让用户查看
            if self.main_window:
                from PyQt6.QtCore import QTimer
                dm = self.main_window.document_manager if hasattr(self.main_window, 'document_manager') else None
                QTimer.singleShot(100, lambda: self._show_diff_dialog(device, other_device, dm))

            return result
        except Exception as e:
            return {"success": False, "message": t("ai.diff_fail", error=str(e)), "data": None}

    def _show_diff_dialog(self, current_device, other_device, document_manager):
        """弹出 SVD 差异比较对话框让用户可视化查看差异"""
        try:
            from svd_tool.ui.dialogs.svd_diff_dialog import SVDDiffDialog
            from PyQt6.QtCore import Qt

            dialog = SVDDiffDialog(
                self.main_window, current_device,
                document_manager=document_manager
            )
            dialog.set_other_device(other_device)
            dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint)
            dialog.show()
            # 自动触发比较
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(200, dialog._do_compare)
        except Exception as e:
            logger.warning(f"弹出 diff 对话框失败: {e}")

    def _get_open_documents_info(self) -> list:
        """获取所有已打开文档的显示名称列表"""
        if not self.main_window or not hasattr(self.main_window, 'document_manager'):
            return []
        dm = self.main_window.document_manager
        return [doc.display_name for doc in dm.get_all_documents().values()]

    def _resolve_other_device(self, name_hint: str = ""):
        """从已打开的文档中找到另一个设备

        Args:
            name_hint: 可选的文档名称提示（支持模糊匹配）

        Returns:
            (device_info, display_name) 或 (None, "")
        """
        if not self.main_window or not hasattr(self.main_window, 'document_manager'):
            return None, ""

        dm = self.main_window.document_manager
        active_id = dm.active_doc_id
        all_docs = dm.get_all_documents()

        other_docs = {did: doc for did, doc in all_docs.items() if did != active_id}

        if not other_docs:
            return None, ""

        if not name_hint:
            # 没有指定名称，取第一个其他文档
            doc = list(other_docs.values())[0]
            return doc.device_info, doc.display_name

        # 模糊匹配名称
        name_lower = name_hint.lower()
        for doc in other_docs.values():
            if name_lower in doc.display_name.lower() or name_lower in (doc.device_info.name or "").lower():
                return doc.device_info, doc.display_name

        return None, ""

    def _op_jump(self, params: Dict) -> Dict[str, Any]:
        """跳转到指定外设/寄存器/位域"""
        peripheral = params.get("peripheral", "").strip()
        register = params.get("register", "").strip()
        field = params.get("field", "").strip()

        if not peripheral:
            return {"success": False, "message": t("ai.jump_hint"), "data": None}

        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        if peripheral not in device.peripherals:
            return {"success": False, "message": t("ai.periph_not_found", name=peripheral), "data": None}

        # 切换到外设标签页
        layout_manager = self.coordinator.get_component("layout_manager")
        if layout_manager:
            tab_widget = layout_manager.widget_manager.get_widget("tab_widget")
            if tab_widget:
                # 外设标签页固定在 index=1
                if tab_widget.count() > 1:
                    tab_widget.setCurrentIndex(1)

        # 使用 PeripheralManager 的选择方法
        periph_manager = self.coordinator.get_component("peripheral_manager")
        if not periph_manager:
            return {"success": False, "message": t("ai.periph_mgr_unavailable"), "data": None}

        target_desc = peripheral
        try:
            if field and register:
                periph_manager.select_field(peripheral, register, field)
                target_desc = f"{peripheral} > {register} > {field}"
            elif register:
                periph_manager.select_register(peripheral, register)
                target_desc = f"{peripheral} > {register}"
            else:
                periph_manager.select_peripheral(peripheral)
                target_desc = peripheral
        except Exception as e:
            return {"success": False, "message": t("ai.jump_fail", error=str(e)), "data": None}

        return {"success": True, "message": t("ai.jump_done", target=target_desc), "data": {
            "peripheral": peripheral,
            "register": register or None,
            "field": field or None,
        }}

    # ==================== 片段查询工具（function-calling 专用） ====================
    # 以下工具用于让 AI 按需取 SVD 片段，替代旧的"全文塞 system prompt"。
    # 设计原则：分层下发——get_peripheral 不含位域、get_register 不含 enumerated_values，
    # get_field 才返回完整位域（含枚举值）。避免单次返回过大。

    def _op_get_peripheral(self, params: Dict) -> Dict[str, Any]:
        """获取指定外设的元信息及寄存器列表（不含位域细节）。

        合并 clusters 内的寄存器（用 all_registers），并在每条标注 cluster 来源。
        """
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        name = params.get("name", "").strip()
        if name not in device.peripherals:
            return {"success": False, "message": t("ai.periph_not_found", name=name), "data": None}

        periph = device.peripherals[name]
        # all_registers 合并 clusters；同时记录每个寄存器是否来自 cluster
        reg_list = []
        for rname, reg in periph.registers.items():
            reg_list.append({
                "name": rname,
                "offset": reg.offset,
                "size": reg.size,
                "access": reg.access or "",
                "reset_value": reg.reset_value,
                "description": reg.description,
                "from_cluster": "",
            })
        for cname, cluster in periph.clusters.items():
            for rname, reg in cluster.all_registers().items():
                reg_list.append({
                    "name": rname,
                    "offset": reg.offset,
                    "size": reg.size,
                    "access": reg.access or "",
                    "reset_value": reg.reset_value,
                    "description": reg.description,
                    "from_cluster": cname,
                })

        data = {
            "name": periph.name,
            "base_address": periph.base_address,
            "description": periph.description,
            "group_name": periph.group_name,
            "derived_from": periph.derived_from or "",
            "register_count": len(reg_list),
            "registers": reg_list,
        }
        return {"success": True, "message": t("ai.get_periph_done", name=name, count=len(reg_list)), "data": data}

    def _op_get_register(self, params: Dict) -> Dict[str, Any]:
        """获取指定寄存器的元信息及位域列表（不含 enumerated_values）。"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        periph_name = params.get("peripheral", "").strip()
        reg_name = params.get("register", "").strip() or params.get("name", "").strip()
        if periph_name not in device.peripherals:
            return {"success": False, "message": t("ai.periph_not_found", name=periph_name), "data": None}

        periph = device.peripherals[periph_name]
        # 优先顶层 registers，找不到再查 clusters
        reg = periph.registers.get(reg_name)
        cluster_source = ""
        if reg is None:
            for cname, cluster in periph.clusters.items():
                regs = cluster.all_registers()
                if reg_name in regs:
                    reg = regs[reg_name]
                    cluster_source = cname
                    break
        if reg is None:
            return {"success": False, "message": t("ai.reg_not_found", name=reg_name), "data": None}

        field_list = []
        for fname, fld in reg.fields.items():
            field_list.append({
                "name": fname,
                "bit_offset": fld.bit_offset,
                "bit_width": fld.bit_width,
                "access": fld.access or "",
                "reset_value": fld.reset_value,
                "description": fld.description,
            })

        data = {
            "peripheral": periph_name,
            "name": reg.name,
            "offset": reg.offset,
            "size": reg.size,
            "access": reg.access or "",
            "reset_value": reg.reset_value,
            "reset_mask": getattr(reg, "reset_mask", ""),
            "description": reg.description,
            "derived_from": getattr(reg, "derived_from", "") or "",
            "from_cluster": cluster_source,
            "field_count": len(field_list),
            "fields": field_list,
        }
        return {"success": True, "message": t("ai.get_reg_done", periph=periph_name, name=reg_name, count=len(field_list)), "data": data}

    def _op_get_field(self, params: Dict) -> Dict[str, Any]:
        """获取单个位域的完整信息（含 enumerated_values）。"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        periph_name = params.get("peripheral", "").strip()
        reg_name = params.get("register", "").strip()
        field_name = params.get("field", "").strip() or params.get("name", "").strip()
        if periph_name not in device.peripherals:
            return {"success": False, "message": t("ai.periph_not_found", name=periph_name), "data": None}

        periph = device.peripherals[periph_name]
        reg = periph.registers.get(reg_name)
        if reg is None:
            for cluster in periph.clusters.values():
                regs = cluster.all_registers()
                if reg_name in regs:
                    reg = regs[reg_name]
                    break
        if reg is None:
            return {"success": False, "message": t("ai.reg_not_found", name=reg_name), "data": None}
        if field_name not in reg.fields:
            return {"success": False, "message": t("ai.field_not_found", name=field_name), "data": None}

        fld = reg.fields[field_name]
        data = {
            "peripheral": periph_name,
            "register": reg_name,
            "name": fld.name,
            "bit_offset": fld.bit_offset,
            "bit_width": fld.bit_width,
            "access": fld.access or "",
            "reset_value": fld.reset_value,
            "description": fld.description,
            "display_name": getattr(fld, "display_name", ""),
            "enumerated_values": getattr(fld, "enumerated_values", []),
        }
        return {"success": True, "message": t("ai.get_field_done", name=field_name), "data": data}

    def _op_list_interrupts(self, params: Dict) -> Dict[str, Any]:
        """列出设备的中断（名称/值/描述/关联外设）。"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        irq_list = []
        for name, irq in device.interrupts.items():
            irq_list.append({
                "name": name,
                "value": irq.value,
                "description": irq.description,
                "peripheral": irq.peripheral,
                "peripherals": irq.peripherals,
            })
        data = {"total": len(irq_list), "interrupts": irq_list}
        return {"success": True, "message": t("ai.list_irq_done", count=len(irq_list)), "data": data}

    # ==================== 修改操作 ====================

    def _op_update_device(self, params: Dict) -> Dict[str, Any]:
        """更新设备级属性（名称、版本、厂商、描述、作者等）"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        # 合并 "updates" 字典和直接传入的字段
        direct_fields = {"name", "version", "vendor", "description", "author",
                         "license", "copyright", "svd_version"}
        updates = dict(params.get("updates", {}) or {})
        for key in direct_fields:
            if key in params:
                updates[key] = params[key]

        if not updates:
            return {"success": False, "message": t("ai.no_updates"), "data": None}

        old_values = {}
        updatable_fields = ["name", "version", "vendor", "description", "author",
                            "license", "copyright", "svd_version"]

        for key in updatable_fields:
            if key in updates:
                old_values[key] = getattr(device, key, "")
                setattr(device, key, updates[key])

        def undo():
            for key, val in old_values.items():
                setattr(device, key, val)

        self._execute_undoable("AI: 更新设备信息", lambda: None, undo)
        self._notify_refresh()

        updated = list(updates.keys())
        return {"success": True, "message": t("ai.update_device_done", fields=', '.join(updated)), "data": {"updates": updated}}

    def _op_add_peripheral(self, params: Dict) -> Dict[str, Any]:
        """添加外设"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        from svd_tool.core.data_model import Peripheral

        name = params.get("name", "").strip()
        if not name:
            return {"success": False, "message": t("ai.periph_name_empty"), "data": None}
        if name in device.peripherals:
            return {"success": False, "message": t("ai.periph_exists", name=name), "data": None}

        base_address = params.get("base_address", "0x40000000")
        periph = Peripheral(
            name=name,
            base_address=base_address,
            description=params.get("description", ""),
            group_name=params.get("group_name", ""),
        )

        def execute():
            device.peripherals[name] = periph

        def undo():
            del device.peripherals[name]

        self._execute_undoable(f"AI: 添加外设 '{name}'", execute, undo)
        self._notify_refresh(name)

        return {"success": True, "message": t("ai.add_periph_done", name=name, addr=base_address), "data": {"name": name}}

    def _op_update_peripheral(self, params: Dict) -> Dict[str, Any]:
        """更新外设属性"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        name = params.get("name", "").strip()
        if name not in device.peripherals:
            return {"success": False, "message": t("ai.periph_not_found", name=name), "data": None}

        updates = params.get("updates", {})
        if not updates:
            return {"success": False, "message": t("ai.no_updates"), "data": None}

        periph = device.peripherals[name]
        new_name = str(updates.get("name", "")).strip()

        # 改名：复用 state_manager.rename_peripheral（已处理 dict-key 迁移、顺序保持、撤销）
        rename_done = False
        if new_name and new_name != name:
            state_manager = self.coordinator.get_component("state_manager")
            if state_manager and hasattr(state_manager, "rename_peripheral"):
                try:
                    state_manager.rename_peripheral(name, new_name)
                    rename_done = True
                except ValueError as e:
                    return {"success": False, "message": str(e), "data": None}
            else:
                # 兜底：state_manager 不可用时直接迁移（无撤销）
                if new_name in device.peripherals:
                    return {"success": False,
                            "message": t("ai.periph_exists", name=new_name), "data": None}
                order = list(device.peripherals.keys())
                old_periph = device.peripherals.pop(name)
                old_periph.name = new_name
                new_periphs = {}
                for k in order:
                    new_periphs[new_name if k == name else k] = device.peripherals.get(k, old_periph if k == name else None)
                device.peripherals.clear()
                device.peripherals.update({k: v for k, v in new_periphs.items() if v is not None})
                rename_done = True

        # 改名后，periph 引用仍有效（对象未变，仅 key 变了）；用新 name 定位
        effective_name = new_name if rename_done else name
        periph = device.peripherals[effective_name]

        # 其它可改属性（改名已单独处理，这里不动 name）
        old_values = {}
        updatable_fields = ["description", "base_address", "group_name", "display_name"]

        for key in updatable_fields:
            if key in updates:
                old_values[key] = getattr(periph, key, "")
                setattr(periph, key, updates[key])

        def undo():
            for key, val in old_values.items():
                setattr(periph, key, val)

        self._execute_undoable(f"AI: 更新外设 '{effective_name}'", lambda: None, undo)
        self._notify_refresh(effective_name)

        return {"success": True, "message": t("ai.update_periph_done", name=effective_name),
                "data": {"name": effective_name, "updates": list(updates.keys()), "renamed": rename_done}}

    def _op_remove_peripheral(self, params: Dict) -> Dict[str, Any]:
        """删除外设"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        name = params.get("name", "").strip()
        if name not in device.peripherals:
            return {"success": False, "message": t("ai.periph_not_found", name=name), "data": None}

        import copy
        removed = device.peripherals[name]
        removed_copy = copy.deepcopy(removed)

        def execute():
            if name in device.peripherals:
                del device.peripherals[name]

        def undo():
            device.peripherals[name] = removed_copy

        self._execute_undoable(f"AI: 删除外设 '{name}'", execute, undo)
        self._notify_refresh(name)

        return {"success": True, "message": t("ai.remove_periph_done", name=name), "data": {"name": name}}

    def _op_add_register(self, params: Dict) -> Dict[str, Any]:
        """添加寄存器"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        from svd_tool.core.data_model import Register

        periph_name = params.get("peripheral", "").strip()
        if periph_name not in device.peripherals:
            return {"success": False, "message": t("ai.periph_not_found", name=periph_name), "data": None}

        reg_name = params.get("name", "").strip()
        if not reg_name:
            return {"success": False, "message": t("ai.reg_name_empty"), "data": None}

        periph = device.peripherals[periph_name]
        if reg_name in periph.registers:
            return {"success": False, "message": t("ai.reg_exists", name=reg_name, periph=periph_name), "data": None}

        reg = Register(
            name=reg_name,
            offset=params.get("offset", "0x00"),
            description=params.get("description", ""),
            size=params.get("size", "0x20"),
            access=params.get("access"),
            reset_value=params.get("reset_value", "0x00000000"),
        )

        def execute():
            periph.registers[reg_name] = reg

        def undo():
            if reg_name in periph.registers:
                del periph.registers[reg_name]

        self._execute_undoable(f"AI: 添加寄存器 '{reg_name}' 到 '{periph_name}'", execute, undo)
        self._notify_refresh(periph_name)

        return {"success": True, "message": t("ai.add_reg_done", name=reg_name, periph=periph_name, offset=reg.offset), "data": {"name": reg_name}}

    def _op_update_register(self, params: Dict) -> Dict[str, Any]:
        """更新寄存器属性"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        periph_name = params.get("peripheral", "").strip()
        reg_name = params.get("name", "").strip()
        updates = params.get("updates", {})

        if periph_name not in device.peripherals:
            return {"success": False, "message": t("ai.periph_not_found", name=periph_name), "data": None}

        periph = device.peripherals[periph_name]
        if reg_name not in periph.registers:
            return {"success": False, "message": t("ai.reg_not_found", name=reg_name), "data": None}

        if not updates:
            return {"success": False, "message": t("ai.no_updates"), "data": None}

        reg = periph.registers[reg_name]
        new_name = str(updates.get("name", "")).strip()

        # 改名：需要同步迁移 dict key（registers 以 name 为 key），保持顺序并支持撤销。
        # 单纯 setattr(reg, "name", ...) 会导致 dict key 与对象 name 不一致，查找错乱。
        rename_done = False
        if new_name and new_name != reg_name:
            if new_name in periph.registers:
                return {"success": False,
                        "message": t("ai.reg_exists", name=new_name, periph=periph_name), "data": None}

            # 保存旧顺序，构造 execute/undo
            reg_order = list(periph.registers.keys())

            def _rename_execute():
                old_reg = periph.registers.pop(reg_name)
                old_reg.name = new_name
                # 重建 dict 保持顺序
                new_regs = {}
                for k in reg_order:
                    if k == reg_name:
                        new_regs[new_name] = old_reg
                    else:
                        new_regs[k] = periph.registers[k]
                # 清掉剩余（已 pop 的）再覆盖
                periph.registers.clear()
                periph.registers.update(new_regs)

            def _rename_undo():
                cur = periph.registers.pop(new_name)
                cur.name = reg_name
                restored = {}
                for k in reg_order:
                    if k == reg_name:
                        restored[reg_name] = cur
                    else:
                        restored[k] = periph.registers[k]
                periph.registers.clear()
                periph.registers.update(restored)

            self._execute_undoable(f"AI: 重命名寄存器 '{reg_name}' -> '{new_name}'",
                                   _rename_execute, _rename_undo)
            rename_done = True

        # 其它可改属性（改名已单独处理，这里不动 name）
        old_values = {}
        updatable_fields = ["description", "offset", "size", "access", "reset_value", "display_name"]

        for key in updatable_fields:
            if key in updates:
                old_values[key] = getattr(reg, key, "")
                setattr(reg, key, updates[key])

        def undo():
            for key, val in old_values.items():
                setattr(reg, key, val)

        self._execute_undoable(f"AI: 更新寄存器 '{reg_name}'", lambda: None, undo)
        self._notify_refresh(periph_name)

        result_name = new_name if rename_done else reg_name
        return {"success": True, "message": t("ai.update_reg_done", name=result_name),
                "data": {"name": result_name, "renamed": rename_done}}

    def _op_remove_register(self, params: Dict) -> Dict[str, Any]:
        """删除寄存器"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        periph_name = params.get("peripheral", "").strip()
        reg_name = params.get("name", "").strip()

        if periph_name not in device.peripherals:
            return {"success": False, "message": t("ai.periph_not_found", name=periph_name), "data": None}

        periph = device.peripherals[periph_name]
        if reg_name not in periph.registers:
            return {"success": False, "message": t("ai.reg_not_found", name=reg_name), "data": None}

        import copy
        removed_copy = copy.deepcopy(periph.registers[reg_name])

        def execute():
            if reg_name in periph.registers:
                del periph.registers[reg_name]

        def undo():
            periph.registers[reg_name] = removed_copy

        self._execute_undoable(f"AI: 删除寄存器 '{reg_name}'", execute, undo)
        self._notify_refresh(periph_name)

        return {"success": True, "message": t("ai.remove_reg_done", name=reg_name, periph=periph_name), "data": {"name": reg_name}}

    def _op_add_field(self, params: Dict) -> Dict[str, Any]:
        """添加位域"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        from svd_tool.core.data_model import Field

        periph_name = params.get("peripheral", "").strip()
        reg_name = params.get("register", "").strip()
        field_name = params.get("name", "").strip()

        if periph_name not in device.peripherals:
            return {"success": False, "message": t("ai.periph_not_found", name=periph_name), "data": None}

        periph = device.peripherals[periph_name]
        if reg_name not in periph.registers:
            return {"success": False, "message": t("ai.reg_not_found", name=reg_name), "data": None}

        reg = periph.registers[reg_name]
        if field_name in reg.fields:
            return {"success": False, "message": t("ai.field_exists", name=field_name), "data": None}

        bit_offset = int(params.get("bit_offset", 0))
        bit_width = int(params.get("bit_width", 1))

        fld = Field(
            name=field_name,
            bit_offset=bit_offset,
            bit_width=bit_width,
            description=params.get("description", ""),
            access=params.get("access"),
            reset_value=params.get("reset_value", "0x0"),
        )

        def execute():
            reg.fields[field_name] = fld

        def undo():
            if field_name in reg.fields:
                del reg.fields[field_name]

        self._execute_undoable(f"AI: 添加位域 '{field_name}' 到 '{reg_name}'", execute, undo)
        self._notify_refresh(periph_name)

        return {"success": True, "message": t("ai.add_field_done", name=field_name, start=bit_offset, end=bit_offset + bit_width - 1, reg=reg_name), "data": {"name": field_name}}

    def _op_update_field(self, params: Dict) -> Dict[str, Any]:
        """更新位域属性"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        periph_name = params.get("peripheral", "").strip()
        reg_name = params.get("register", "").strip()
        field_name = params.get("name", "").strip()
        updates = params.get("updates", {})

        if periph_name not in device.peripherals:
            return {"success": False, "message": t("ai.periph_not_found", name=periph_name), "data": None}

        periph = device.peripherals[periph_name]
        if reg_name not in periph.registers:
            return {"success": False, "message": t("ai.reg_not_found", name=reg_name), "data": None}

        reg = periph.registers[reg_name]
        if field_name not in reg.fields:
            return {"success": False, "message": t("ai.field_not_found", name=field_name), "data": None}

        if not updates:
            return {"success": False, "message": t("ai.no_updates"), "data": None}

        fld = reg.fields[field_name]
        new_name = str(updates.get("name", "")).strip()

        # 改名：同步迁移 dict key（fields 以 name 为 key），保持顺序并支持撤销。
        rename_done = False
        if new_name and new_name != field_name:
            if new_name in reg.fields:
                return {"success": False,
                        "message": t("ai.field_exists", name=new_name), "data": None}

            field_order = list(reg.fields.keys())

            def _rename_execute():
                old_fld = reg.fields.pop(field_name)
                old_fld.name = new_name
                new_fields = {}
                for k in field_order:
                    if k == field_name:
                        new_fields[new_name] = old_fld
                    else:
                        new_fields[k] = reg.fields[k]
                reg.fields.clear()
                reg.fields.update(new_fields)

            def _rename_undo():
                cur = reg.fields.pop(new_name)
                cur.name = field_name
                restored = {}
                for k in field_order:
                    if k == field_name:
                        restored[field_name] = cur
                    else:
                        restored[k] = reg.fields[k]
                reg.fields.clear()
                reg.fields.update(restored)

            self._execute_undoable(f"AI: 重命名位域 '{field_name}' -> '{new_name}'",
                                   _rename_execute, _rename_undo)
            rename_done = True

        # 其它可改属性（改名已单独处理，这里不动 name）
        old_values = {}
        updatable_fields = ["description", "bit_offset", "bit_width", "access", "reset_value", "display_name"]

        for key in updatable_fields:
            if key in updates:
                old_values[key] = getattr(fld, key, "")
                new_val = updates[key]
                if key in ("bit_offset", "bit_width"):
                    new_val = int(new_val)
                setattr(fld, key, new_val)

        def undo():
            for key, val in old_values.items():
                setattr(fld, key, val)

        self._execute_undoable(f"AI: 更新位域 '{field_name}'", lambda: None, undo)
        self._notify_refresh(periph_name)

        result_name = new_name if rename_done else field_name
        return {"success": True, "message": t("ai.update_field_done", name=result_name),
                "data": {"name": result_name, "renamed": rename_done}}

    def _op_remove_field(self, params: Dict) -> Dict[str, Any]:
        """删除位域"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        periph_name = params.get("peripheral", "").strip()
        reg_name = params.get("register", "").strip()
        field_name = params.get("name", "").strip()

        if periph_name not in device.peripherals:
            return {"success": False, "message": t("ai.periph_not_found", name=periph_name), "data": None}

        periph = device.peripherals[periph_name]
        if reg_name not in periph.registers:
            return {"success": False, "message": t("ai.reg_not_found", name=reg_name), "data": None}

        reg = periph.registers[reg_name]
        if field_name not in reg.fields:
            return {"success": False, "message": t("ai.field_not_found", name=field_name), "data": None}

        import copy
        removed_copy = copy.deepcopy(reg.fields[field_name])

        def execute():
            if field_name in reg.fields:
                del reg.fields[field_name]

        def undo():
            reg.fields[field_name] = removed_copy

        self._execute_undoable(f"AI: 删除位域 '{field_name}'", execute, undo)
        self._notify_refresh(periph_name)

        return {"success": True, "message": t("ai.remove_field_done", name=field_name, reg=reg_name), "data": {"name": field_name}}

    # ==================== 多文档操作 ====================

    def _op_switch_document(self, params: Dict) -> Dict[str, Any]:
        """切换到指定文档"""
        if not self.main_window or not hasattr(self.main_window, 'document_manager'):
            return {"success": False, "message": t("ai.doc_mgr_unavailable"), "data": None}

        dm = self.main_window.document_manager
        target = params.get("doc_id", "").strip()
        name_hint = params.get("name", "").strip()

        if not target and not name_hint:
            return {"success": False, "message": t("ai.doc_no_param"), "data": None}

        # 按 doc_id 查找
        if target and target in dm.get_all_documents():
            # 先保存当前文档状态
            if hasattr(self.main_window, '_save_current_document_state'):
                self.main_window._save_current_document_state()
            dm.switch_to(target)
            if hasattr(self.main_window, '_restore_document_state'):
                doc = dm.get_document(target)
                if doc:
                    self.main_window._restore_document_state(doc)
            doc = dm.get_document(target)
            return {"success": True, "message": t("ai.doc_switch_done", name=doc.display_name), "data": {"doc_id": target}}

        # 按名称模糊查找
        if name_hint:
            name_lower = name_hint.lower()
            for doc_id, doc in dm.get_all_documents().items():
                if name_lower in doc.display_name.lower() or name_lower in (doc.device_info.name or "").lower():
                    if hasattr(self.main_window, '_save_current_document_state'):
                        self.main_window._save_current_document_state()
                    dm.switch_to(doc_id)
                    if hasattr(self.main_window, '_restore_document_state'):
                        self.main_window._restore_document_state(doc)
                    return {"success": True, "message": t("ai.doc_switch_done", name=doc.display_name), "data": {"doc_id": doc_id}}

        return {"success": False, "message": t("ai.doc_not_found", hint=target or name_hint), "data": None}

    def _op_save_document(self, params: Dict) -> Dict[str, Any]:
        """保存指定文档（默认保存当前文档）"""
        if not self.main_window or not hasattr(self.main_window, 'document_manager'):
            return {"success": False, "message": t("ai.doc_mgr_unavailable"), "data": None}

        dm = self.main_window.document_manager
        target_id = params.get("doc_id", "").strip() or dm.active_doc_id

        if not target_id:
            return {"success": False, "message": t("ai.doc_no_save"), "data": None}

        doc = dm.get_document(target_id)
        if not doc:
            return {"success": False, "message": t("ai.doc_not_exist", id=target_id), "data": None}

        try:
            from svd_tool.core.svd_generator import SVDGenerator
            generator = SVDGenerator(doc.device_info, skip_derived_registers=getattr(self.main_window, 'skip_derived_registers', True))
            svd_xml = generator.generate()

            save_path = params.get("file_path", "").strip() or doc.file_path
            if not save_path:
                return {"success": False, "message": t("ai.doc_no_path", name=doc.display_name), "data": None}

            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(svd_xml)

            dm.save_document(target_id, file_path=save_path if params.get("file_path") else None)
            return {"success": True, "message": t("ai.doc_save_done", name=doc.display_name, path=save_path), "data": {"doc_id": target_id, "path": save_path}}
        except Exception as e:
            return {"success": False, "message": t("ai.doc_save_fail", error=str(e)), "data": None}

    def _op_batch_save(self, params: Dict) -> Dict[str, Any]:
        """批量保存文档

        params:
            paths: {doc_id: new_file_path} — 每个文档指定新路径（可选，指定后原文件不动）
            doc_ids: [doc_id, ...] — 指定要保存的文档
            all: true — 保存所有文档
        """
        if not self.main_window or not hasattr(self.main_window, 'document_manager'):
            return {"success": False, "message": t("ai.doc_mgr_unavailable"), "data": None}

        dm = self.main_window.document_manager
        paths = params.get("paths", {})
        target_ids = params.get("doc_ids", None)
        save_all = params.get("all", False)

        if save_all:
            docs_to_save = list(dm.get_all_documents().keys())
        elif target_ids:
            docs_to_save = target_ids
        else:
            docs_to_save = dm.get_modified_documents()

        if not docs_to_save:
            return {"success": True, "message": t("ai.doc_no_save"), "data": {"saved": [], "failed": []}}

        from svd_tool.core.svd_generator import SVDGenerator
        saved = []
        failed = []

        for doc_id in docs_to_save:
            doc = dm.get_document(doc_id)
            if not doc:
                failed.append({"doc_id": doc_id, "error": t("ai.doc_not_exist", id=doc_id)})
                continue
            new_path = paths.get(doc_id, "").strip() if paths else ""
            save_path = new_path or doc.file_path
            if not save_path:
                failed.append({"doc_id": doc_id, "name": doc.display_name, "error": t("ai.doc_no_path_batch")})
                continue
            try:
                generator = SVDGenerator(doc.device_info, skip_derived_registers=getattr(self.main_window, 'skip_derived_registers', True))
                svd_xml = generator.generate()
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write(svd_xml)
                # 有新路径时更新文档记录，否则只标记已保存
                dm.save_document(doc_id, file_path=new_path or None)
                saved.append({"doc_id": doc_id, "name": doc.display_name, "path": save_path})
            except Exception as e:
                failed.append({"doc_id": doc_id, "name": doc.display_name, "error": str(e)})

        msg = t("ai.doc_batch_done", saved=len(saved), failed=len(failed))
        return {"success": len(failed) == 0, "message": msg, "data": {"saved": saved, "failed": failed}}
