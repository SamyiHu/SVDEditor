"""
命令执行器
将 AI 返回的操作指令翻译为对 DeviceInfo 的直接操作
所有修改操作通过 CommandHistory 支持撤销
"""
import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger("AIAssistant.CommandExecutor")


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
                "message": f"未知操作: {operation}",
                "data": None
            }

        try:
            return handler(params)
        except Exception as e:
            logger.error(f"执行操作 {operation} 失败: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"操作执行失败: {str(e)}",
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
        """通知 UI 刷新"""
        state_manager = self.coordinator.get_component("state_manager")
        if state_manager:
            state_manager._notify_state_change()

        if peripheral_name:
            self.coordinator.notify_peripheral_updated(peripheral_name)

        # 刷新基本信息页面
        layout_manager = self.coordinator.get_component("layout_manager")
        if layout_manager and hasattr(layout_manager, 'update_basic_info'):
            try:
                layout_manager.update_basic_info(state_manager.device_info)
            except Exception:
                pass

    # ==================== 只读操作 ====================

    def _op_validate(self, params: Dict) -> Dict[str, Any]:
        """验证 SVD 数据"""
        device = self._get_device_info()
        if not device or not device.name:
            return {"success": False, "message": "没有打开的 SVD 文件", "data": None}

        try:
            from svd_tool.core.svd_schema_validator import SVDSchemaValidator
            validator = SVDSchemaValidator()
            results = validator.validate_all(device)
            summary = validator.get_summary()

            msg = f"验证完成: {summary.get('errors', 0)} 个错误, {summary.get('warnings', 0)} 个警告"
            return {"success": not summary.get("has_errors", True), "message": msg, "data": summary}
        except Exception as e:
            return {"success": False, "message": f"验证失败: {e}", "data": None}

    def _op_info(self, params: Dict) -> Dict[str, Any]:
        """获取设备信息统计"""
        device = self._get_device_info()
        if not device or not device.name:
            return {"success": False, "message": "没有打开的 SVD 文件", "data": None}

        info = {
            "device": device.name,
            "version": device.version,
            "vendor": device.vendor or "未指定",
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
            "peripheral_names": list(device.peripherals.keys()),
        }
        msg = (f"设备: {device.name} | "
               f"外设: {info['statistics']['peripherals']} | "
               f"寄存器: {info['statistics']['registers']} | "
               f"位域: {info['statistics']['fields']} | "
               f"中断: {info['statistics']['interrupts']}")
        return {"success": True, "message": msg, "data": info}

    def _op_search(self, params: Dict) -> Dict[str, Any]:
        """搜索外设/寄存器/位域"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": "没有打开的 SVD 文件", "data": None}

        keyword = params.get("keyword", "").lower()
        search_type = params.get("type", "all")
        if not keyword:
            return {"success": False, "message": "请提供搜索关键词", "data": None}

        results = []

        if search_type in ("all", "peripheral"):
            for name in device.peripherals:
                if keyword in name.lower():
                    results.append({"type": "peripheral", "name": name})

        if search_type in ("all", "register"):
            for pname, periph in device.peripherals.items():
                for rname in periph.registers:
                    if keyword in rname.lower():
                        results.append({"type": "register", "name": rname, "peripheral": pname})

        if search_type in ("all", "field"):
            for pname, periph in device.peripherals.items():
                for rname, reg in periph.registers.items():
                    for fname in reg.fields:
                        if keyword in fname.lower():
                            results.append({"type": "field", "name": fname, "peripheral": pname, "register": rname})

        msg = f"搜索 '{keyword}' 找到 {len(results)} 个结果"
        return {"success": True, "message": msg, "data": results}

    def _op_conflicts(self, params: Dict) -> Dict[str, Any]:
        """检测地址冲突"""
        device = self._get_device_info()
        if not device or not device.name:
            return {"success": False, "message": "没有打开的 SVD 文件", "data": None}

        try:
            from svd_tool.core.address_conflict_detector import AddressConflictDetector
            detector = AddressConflictDetector()
            conflicts = detector.detect_all(device)

            if not conflicts:
                return {"success": True, "message": "未检测到地址冲突", "data": []}

            conflict_list = []
            for c in conflicts[:20]:
                conflict_list.append({
                    "type": str(c.conflict_type) if hasattr(c, 'conflict_type') else "unknown",
                    "severity": str(c.severity) if hasattr(c, 'severity') else "unknown",
                    "message": c.message if hasattr(c, 'message') else str(c),
                })

            msg = f"检测到 {len(conflicts)} 个地址冲突"
            return {"success": True, "message": msg, "data": conflict_list}
        except Exception as e:
            return {"success": False, "message": f"冲突检测失败: {e}", "data": None}

    def _op_diff(self, params: Dict) -> Dict[str, Any]:
        """比较当前 SVD 与另一个文件或已打开的文档"""
        device = self._get_device_info()
        if not device or not device.name:
            return {"success": False, "message": "没有打开的 SVD 文件", "data": None}

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
                    return {"success": False, "message": "当前只有一个文件打开，无法比较。请打开第二个文件，或使用 file_path 参数指定文件路径。", "data": None}
                return {
                    "success": False,
                    "message": f"找不到匹配的文档。当前打开的文件：{', '.join(open_docs)}",
                    "data": {"open_documents": open_docs}
                }

        # 如果未从打开的文档获取到，则尝试文件路径
        if other_device is None:
            file_path = params.get("file_path", "") or params.get("file", "")
            if isinstance(file_path, str):
                file_path = file_path.strip()
            if not file_path:
                # 没有提供路径，也没有其他打开的文档
                return {"success": False, "message": "请提供要比较的文件路径（file_path）或文档名称（compare_with）。当前没有其他已打开的文件。", "data": None}

            import os
            if not os.path.isfile(file_path):
                return {"success": False, "message": f"文件不存在: {file_path}", "data": None}

            try:
                from svd_tool.core.svd_parser import SVDParser
                parser = SVDParser()
                other_device = parser.parse_file(file_path)
                other_name = os.path.basename(file_path)
            except Exception as e:
                return {"success": False, "message": f"解析文件失败: {e}", "data": None}

        try:
            from svd_tool.core.svd_differ import SVDDiffer

            differ = SVDDiffer()
            diffs = differ.diff(device, other_device)

            if not diffs:
                return {"success": True, "message": f"'{device.name}' 与 '{other_name}' 完全一致，没有差异", "data": []}

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
                "message": f"比较 '{device.name}' 与 '{other_name}'：发现 {total_changes} 处差异（{len(diffs)} 个外设级别差异）",
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
            return {"success": False, "message": f"比较失败: {e}", "data": None}

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
            return {"success": False, "message": "请至少指定外设名称", "data": None}

        device = self._get_device_info()
        if not device:
            return {"success": False, "message": "没有打开的 SVD 文件", "data": None}

        if peripheral not in device.peripherals:
            return {"success": False, "message": f"外设 '{peripheral}' 不存在", "data": None}

        # 切换到外设标签页
        layout_manager = self.coordinator.get_component("layout_manager")
        if layout_manager:
            tab_widget = layout_manager.widget_manager.get_widget("tab_widget")
            if tab_widget:
                # 找到外设标签页（通常是第2个，index=1）
                for i in range(tab_widget.count()):
                    if "外设" in tab_widget.tabText(i) or "Periph" in tab_widget.tabText(i):
                        tab_widget.setCurrentIndex(i)
                        break

        # 使用 PeripheralManager 的选择方法
        periph_manager = self.coordinator.get_component("peripheral_manager")
        if not periph_manager:
            return {"success": False, "message": "外设管理器不可用", "data": None}

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
            return {"success": False, "message": f"跳转失败: {e}", "data": None}

        return {"success": True, "message": f"已跳转到 {target_desc}", "data": {
            "peripheral": peripheral,
            "register": register or None,
            "field": field or None,
        }}

    # ==================== 修改操作 ====================

    def _op_update_device(self, params: Dict) -> Dict[str, Any]:
        """更新设备级属性（名称、版本、厂商、描述、作者等）"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": "没有打开的 SVD 文件", "data": None}

        # 合并 "updates" 字典和直接传入的字段
        direct_fields = {"name", "version", "vendor", "description", "author",
                         "license", "copyright", "svd_version"}
        updates = dict(params.get("updates", {}) or {})
        for key in direct_fields:
            if key in params:
                updates[key] = params[key]

        if not updates:
            return {"success": False, "message": "未指定更新内容", "data": None}

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
        return {"success": True, "message": f"已更新设备属性: {', '.join(updated)}", "data": {"updates": updated}}

    def _op_add_peripheral(self, params: Dict) -> Dict[str, Any]:
        """添加外设"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": "没有打开的 SVD 文件", "data": None}

        from svd_tool.core.data_model import Peripheral

        name = params.get("name", "").strip()
        if not name:
            return {"success": False, "message": "外设名称不能为空", "data": None}
        if name in device.peripherals:
            return {"success": False, "message": f"外设 '{name}' 已存在", "data": None}

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

        return {"success": True, "message": f"已添加外设 '{name}' (基地址: {base_address})", "data": {"name": name}}

    def _op_update_peripheral(self, params: Dict) -> Dict[str, Any]:
        """更新外设属性"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": "没有打开的 SVD 文件", "data": None}

        name = params.get("name", "").strip()
        if name not in device.peripherals:
            return {"success": False, "message": f"外设 '{name}' 不存在", "data": None}

        updates = params.get("updates", {})
        if not updates:
            return {"success": False, "message": "未指定更新内容", "data": None}

        periph = device.peripherals[name]
        old_values = {}
        updatable_fields = ["description", "base_address", "group_name", "display_name"]

        for key in updatable_fields:
            if key in updates:
                old_values[key] = getattr(periph, key, "")
                setattr(periph, key, updates[key])

        def undo():
            for key, val in old_values.items():
                setattr(periph, key, val)

        self._execute_undoable(f"AI: 更新外设 '{name}'", lambda: None, undo)
        self._notify_refresh(name)

        return {"success": True, "message": f"已更新外设 '{name}'", "data": {"name": name, "updates": list(updates.keys())}}

    def _op_remove_peripheral(self, params: Dict) -> Dict[str, Any]:
        """删除外设"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": "没有打开的 SVD 文件", "data": None}

        name = params.get("name", "").strip()
        if name not in device.peripherals:
            return {"success": False, "message": f"外设 '{name}' 不存在", "data": None}

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

        return {"success": True, "message": f"已删除外设 '{name}'", "data": {"name": name}}

    def _op_add_register(self, params: Dict) -> Dict[str, Any]:
        """添加寄存器"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": "没有打开的 SVD 文件", "data": None}

        from svd_tool.core.data_model import Register

        periph_name = params.get("peripheral", "").strip()
        if periph_name not in device.peripherals:
            return {"success": False, "message": f"外设 '{periph_name}' 不存在", "data": None}

        reg_name = params.get("name", "").strip()
        if not reg_name:
            return {"success": False, "message": "寄存器名称不能为空", "data": None}

        periph = device.peripherals[periph_name]
        if reg_name in periph.registers:
            return {"success": False, "message": f"寄存器 '{reg_name}' 已存在于 '{periph_name}'", "data": None}

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

        return {"success": True, "message": f"已添加寄存器 '{reg_name}' 到 '{periph_name}' (偏移: {reg.offset})", "data": {"name": reg_name}}

    def _op_update_register(self, params: Dict) -> Dict[str, Any]:
        """更新寄存器属性"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": "没有打开的 SVD 文件", "data": None}

        periph_name = params.get("peripheral", "").strip()
        reg_name = params.get("name", "").strip()
        updates = params.get("updates", {})

        if periph_name not in device.peripherals:
            return {"success": False, "message": f"外设 '{periph_name}' 不存在", "data": None}

        periph = device.peripherals[periph_name]
        if reg_name not in periph.registers:
            return {"success": False, "message": f"寄存器 '{reg_name}' 不存在于 '{periph_name}'", "data": None}

        if not updates:
            return {"success": False, "message": "未指定更新内容", "data": None}

        reg = periph.registers[reg_name]
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

        return {"success": True, "message": f"已更新寄存器 '{reg_name}'", "data": {"name": reg_name}}

    def _op_remove_register(self, params: Dict) -> Dict[str, Any]:
        """删除寄存器"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": "没有打开的 SVD 文件", "data": None}

        periph_name = params.get("peripheral", "").strip()
        reg_name = params.get("name", "").strip()

        if periph_name not in device.peripherals:
            return {"success": False, "message": f"外设 '{periph_name}' 不存在", "data": None}

        periph = device.peripherals[periph_name]
        if reg_name not in periph.registers:
            return {"success": False, "message": f"寄存器 '{reg_name}' 不存在", "data": None}

        import copy
        removed_copy = copy.deepcopy(periph.registers[reg_name])

        def execute():
            if reg_name in periph.registers:
                del periph.registers[reg_name]

        def undo():
            periph.registers[reg_name] = removed_copy

        self._execute_undoable(f"AI: 删除寄存器 '{reg_name}'", execute, undo)
        self._notify_refresh(periph_name)

        return {"success": True, "message": f"已删除寄存器 '{reg_name}' (从 '{periph_name}')", "data": {"name": reg_name}}

    def _op_add_field(self, params: Dict) -> Dict[str, Any]:
        """添加位域"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": "没有打开的 SVD 文件", "data": None}

        from svd_tool.core.data_model import Field

        periph_name = params.get("peripheral", "").strip()
        reg_name = params.get("register", "").strip()
        field_name = params.get("name", "").strip()

        if periph_name not in device.peripherals:
            return {"success": False, "message": f"外设 '{periph_name}' 不存在", "data": None}

        periph = device.peripherals[periph_name]
        if reg_name not in periph.registers:
            return {"success": False, "message": f"寄存器 '{reg_name}' 不存在", "data": None}

        reg = periph.registers[reg_name]
        if field_name in reg.fields:
            return {"success": False, "message": f"位域 '{field_name}' 已存在", "data": None}

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

        return {"success": True, "message": f"已添加位域 '{field_name}' [{bit_offset}:{bit_offset + bit_width - 1}] 到 '{reg_name}'", "data": {"name": field_name}}

    def _op_update_field(self, params: Dict) -> Dict[str, Any]:
        """更新位域属性"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": "没有打开的 SVD 文件", "data": None}

        periph_name = params.get("peripheral", "").strip()
        reg_name = params.get("register", "").strip()
        field_name = params.get("name", "").strip()
        updates = params.get("updates", {})

        if periph_name not in device.peripherals:
            return {"success": False, "message": f"外设 '{periph_name}' 不存在", "data": None}

        periph = device.peripherals[periph_name]
        if reg_name not in periph.registers:
            return {"success": False, "message": f"寄存器 '{reg_name}' 不存在", "data": None}

        reg = periph.registers[reg_name]
        if field_name not in reg.fields:
            return {"success": False, "message": f"位域 '{field_name}' 不存在", "data": None}

        if not updates:
            return {"success": False, "message": "未指定更新内容", "data": None}

        fld = reg.fields[field_name]
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

        return {"success": True, "message": f"已更新位域 '{field_name}'", "data": {"name": field_name}}

    def _op_remove_field(self, params: Dict) -> Dict[str, Any]:
        """删除位域"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": "没有打开的 SVD 文件", "data": None}

        periph_name = params.get("peripheral", "").strip()
        reg_name = params.get("register", "").strip()
        field_name = params.get("name", "").strip()

        if periph_name not in device.peripherals:
            return {"success": False, "message": f"外设 '{periph_name}' 不存在", "data": None}

        periph = device.peripherals[periph_name]
        if reg_name not in periph.registers:
            return {"success": False, "message": f"寄存器 '{reg_name}' 不存在", "data": None}

        reg = periph.registers[reg_name]
        if field_name not in reg.fields:
            return {"success": False, "message": f"位域 '{field_name}' 不存在", "data": None}

        import copy
        removed_copy = copy.deepcopy(reg.fields[field_name])

        def execute():
            if field_name in reg.fields:
                del reg.fields[field_name]

        def undo():
            reg.fields[field_name] = removed_copy

        self._execute_undoable(f"AI: 删除位域 '{field_name}'", execute, undo)
        self._notify_refresh(periph_name)

        return {"success": True, "message": f"已删除位域 '{field_name}' (从 '{reg_name}')", "data": {"name": field_name}}
