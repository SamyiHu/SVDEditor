"""
EditActionsMixin - 编辑操作相关的方法
从 main_window_refactored.py 中提取的编辑、删除、排序、撤销/重做方法
"""
from typing import List

from PyQt6.QtWidgets import QMessageBox

from ...core.data_model import Register, Field, Interrupt
from ...core.command_history import Command
from ...i18n.i18n import t


class EditActionsMixin:
    """编辑操作混入类 - 提供所有编辑、删除、排序、撤销/重做方法"""

    def add_peripheral(self):
        """添加外设（直接调用外设管理器的对话框）"""
        self.peripheral_manager.add_peripheral_dialog()

    def add_register(self):
        """添加寄存器"""
        # 检查是否有选中的外设
        current_peripheral = self.state_manager.get_current_peripheral()
        if not current_peripheral:
            QMessageBox.warning(self, t("message.warning"), t("msg.select_peripheral_first"))
            return

        # 获取当前外设的寄存器列表和数据
        existing_registers = []
        existing_regs_data = {}
        if current_peripheral in self.state_manager.device_info.peripherals:
            periph = self.state_manager.device_info.peripherals[current_peripheral]
            existing_registers = list(periph.registers.keys())
            existing_regs_data = periph.registers

        self.dialog_factory.set_existing_registers(existing_regs_data)

        # 创建对话框
        dialog = self.dialog_factory.create_register_dialog()

        if dialog.exec():
            result = getattr(dialog, "result_data", None)
            if result is None:
                return

            # 创建寄存器对象
            from ...core.data_model import Register
            register = Register(
                name=result["name"],
                offset=result["offset"],
                description=result["description"],
                display_name=result["display_name"],
                access=result["access"],
                reset_value=result["reset_value"],
                size=result["size"]
            )

            # 使用StateManager添加寄存器
            # 注意：add_register 内部通过 execute_command -> _notify_state_change -> on_state_changed -> update_peripheral_tree
            self.state_manager.add_register(current_peripheral, register)

            # 选中新添加的寄存器
            self.peripheral_manager.select_register(current_peripheral, register.name)

            # 更新状态
            self.layout_manager.update_status(t("status.register_added", name=register.name))
            self.logger.info(f"添加寄存器: {register.name}")

            # 发射数据变化信号
            self.data_changed.emit()

    def edit_register(self, reg_name: str = None):
        """编辑寄存器"""
        # 如果没有提供寄存器名，尝试从当前选择获取
        if reg_name is None:
            current_register = self.state_manager.get_current_register()
            if not current_register:
                QMessageBox.warning(self, t("message.warning"), t("msg.select_register_first"))
                return
            reg_name = current_register

        # 检查是否有选中的外设
        current_peripheral = self.state_manager.get_current_peripheral()
        if not current_peripheral:
            QMessageBox.warning(self, t("message.warning"), t("msg.select_peripheral_first"))
            return

        # 检查寄存器是否存在
        if (current_peripheral not in self.state_manager.device_info.peripherals or
            reg_name not in self.state_manager.device_info.peripherals[current_peripheral].registers):
            QMessageBox.warning(self, t("message.warning"), t("msg.register_not_exist", name=reg_name))
            return

        # 获取寄存器对象
        register = self.state_manager.device_info.peripherals[current_peripheral].registers[reg_name]

        # 获取当前外设的寄存器数据（用于偏移冲突检测）
        periph_obj = self.state_manager.device_info.peripherals[current_peripheral]
        self.dialog_factory.set_existing_registers(periph_obj.registers)

        # 创建对话框
        dialog = self.dialog_factory.create_register_dialog(register, is_edit=True)

        if dialog.exec():
            result = getattr(dialog, "result_data", None)
            if result is None:
                return

            # 保存旧数据
            old_register = register
            old_name = reg_name
            new_name = result["name"]

            # 检查名称是否已更改
            name_changed = old_name != new_name

            # 创建更新后的寄存器对象
            from ...core.data_model import Register
            updated_register = Register(
                name=new_name,
                offset=result["offset"],
                description=result["description"],
                display_name=result["display_name"],
                access=result["access"],
                reset_value=result["reset_value"],
                size=result["size"],
                fields=old_register.fields.copy() if hasattr(old_register, 'fields') else {}
            )

            # 使用StateManager更新寄存器
            if name_changed:
                # 先删除旧的，再添加新的
                self.state_manager.delete_register(current_peripheral, old_name)
                self.state_manager.add_register(current_peripheral, updated_register)
            else:
                # 直接更新
                self.state_manager.update_register(current_peripheral, old_name, updated_register)

            # 注意：state_manager 操作内部已通过 _notify_state_change 触发树重建
            # 选中更新后的寄存器
            self.peripheral_manager.select_register(current_peripheral, new_name)

            # 更新状态
            self.layout_manager.update_status(t("status.register_updated", name=new_name))
            self.logger.info(f"编辑寄存器: {old_name} -> {new_name}")

            # 发射数据变化信号
            self.data_changed.emit()

    def delete_register(self, reg_name: str = None):
        """删除寄存器"""
        # 如果没有提供寄存器名，尝试从当前选择获取
        if reg_name is None:
            current_register = self.state_manager.get_current_register()
            if not current_register:
                QMessageBox.warning(self, t("message.warning"), t("msg.select_register_first"))
                return
            reg_name = current_register

        # 检查是否有选中的外设
        current_peripheral = self.state_manager.get_current_peripheral()
        if not current_peripheral:
            QMessageBox.warning(self, t("message.warning"), t("msg.select_peripheral_first"))
            return

        # 检查寄存器是否存在
        if (current_peripheral not in self.state_manager.device_info.peripherals or
            reg_name not in self.state_manager.device_info.peripherals[current_peripheral].registers):
            QMessageBox.warning(self, t("message.warning"), t("msg.register_not_exist", name=reg_name))
            return

        # 确认删除
        reply = QMessageBox.question(
            self, t("msg.confirm_delete"),
            t("msg.confirm_delete_register", name=reg_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # 暂停通知，防止删除过程中多次重建树
        self.state_manager.pause_notifications()

        try:
            # 使用StateManager删除寄存器
            self.state_manager.delete_register(current_peripheral, reg_name)
        finally:
            # 恢复通知，触发一次统一的树重建
            self.state_manager.resume_notifications()

        # 清除寄存器选择
        self.state_manager.set_selection(register=None, field=None)

        # 更新状态
        self.layout_manager.update_status(t("status.register_deleted", name=reg_name))
        self.logger.info(f"删除寄存器: {reg_name}")

        # 发射数据变化信号
        self.data_changed.emit()

    def delete_multiple_registers(self, register_names: List[str] = None):
        """批量删除寄存器"""
        # 检查是否有选中的外设
        current_peripheral = self.state_manager.get_current_peripheral()
        if not current_peripheral:
            QMessageBox.warning(self, t("message.warning"), t("msg.select_peripheral_first"))
            return

        # 如果没有提供寄存器名列表，尝试从当前选择获取
        if register_names is None:
            # 这里可以扩展为从树控件中获取多个选中的寄存器
            # 目前先使用当前选中的寄存器
            current_register = self.state_manager.get_current_register()
            if not current_register:
                QMessageBox.warning(self, t("message.warning"), t("msg.select_registers_first"))
                return
            register_names = [current_register]

        # 过滤掉不存在的寄存器
        valid_registers = []
        for reg_name in register_names:
            if (current_peripheral in self.state_manager.device_info.peripherals and
                reg_name in self.state_manager.device_info.peripherals[current_peripheral].registers):
                valid_registers.append(reg_name)

        if not valid_registers:
            QMessageBox.warning(self, t("message.warning"), t("msg.no_valid_registers"))
            return

        # 确认删除
        if len(valid_registers) == 1:
            message = t("msg.confirm_delete_register", name=valid_registers[0])
        else:
            message = t("msg.confirm_delete_multiple_registers", count=len(valid_registers))

        reply = QMessageBox.question(
            self, t("msg.confirm_batch_delete"),
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # 批量删除寄存器
        deleted_count = 0
        for reg_name in valid_registers:
            try:
                self.state_manager.delete_register(current_peripheral, reg_name)
                deleted_count += 1
            except Exception as e:
                self.logger.error(f"删除寄存器 '{reg_name}' 失败: {str(e)}")

        # 注意：每次 delete_register 内部已通过 _notify_state_change 触发树重建
        # 不需要再次调用 update_peripheral_tree()

        # 清除寄存器选择
        self.state_manager.set_selection(register=None, field=None)

        # 更新状态
        if deleted_count > 0:
            self.layout_manager.update_status(t("status.registers_batch_deleted", count=deleted_count))
            self.logger.info(f"批量删除 {deleted_count} 个寄存器")

        # 发射数据变化信号
        self.data_changed.emit()

    def add_field(self):
        """添加位域"""
        # 检查是否有选中的外设和寄存器
        current_peripheral = self.state_manager.get_current_peripheral()
        if not current_peripheral:
            QMessageBox.warning(self, t("message.warning"), t("msg.select_peripheral_first"))
            return

        current_register = self.state_manager.get_current_register()
        if not current_register:
            QMessageBox.warning(self, t("message.warning"), t("msg.select_register_first"))
            return

        # 检查寄存器是否存在
        if (current_peripheral not in self.state_manager.device_info.peripherals or
            current_register not in self.state_manager.device_info.peripherals[current_peripheral].registers):
            QMessageBox.warning(self, t("message.warning"), t("msg.register_not_exist", name=current_register))
            return

        # 设置当前寄存器的位域数据（用于位范围冲突检测）
        current_register_obj = self.state_manager.device_info.peripherals[current_peripheral].registers[current_register]
        self.dialog_factory.set_existing_fields(current_register_obj.fields)

        # 创建对话框
        dialog = self.dialog_factory.create_field_dialog()

        if dialog.exec():
            result = getattr(dialog, "result_data", None)
            if result is None:
                return

            # 创建位域对象
            from ...core.data_model import Field
            field = Field(
                name=result["name"],
                bit_offset=int(result["offset"]),
                bit_width=int(result["width"]),
                description=result["description"],
                display_name=result["display_name"],
                access=result["access"],
                reset_value=result["reset_value"]
            )

            # 使用StateManager添加位域
            self.state_manager.add_field(current_peripheral, current_register, field)

            # 更新UI
            self.peripheral_manager.update_peripheral_tree()

            # 选中新添加的位域
            self.peripheral_manager.select_field(current_peripheral, current_register, field.name)

            # 更新状态
            self.layout_manager.update_status(t("status.field_added", name=field.name))
            self.logger.info(f"添加位域: {field.name}")

            # 发射数据变化信号
            self.data_changed.emit()

    def edit_field(self, field_name: str = None):
        """编辑位域"""
        # 如果没有提供位域名，尝试从当前选择获取
        if field_name is None:
            current_field = self.state_manager.get_current_field()
            if not current_field:
                QMessageBox.warning(self, t("message.warning"), t("msg.select_field_first"))
                return
            field_name = current_field

        # 检查是否有选中的外设和寄存器
        current_peripheral = self.state_manager.get_current_peripheral()
        if not current_peripheral:
            QMessageBox.warning(self, t("message.warning"), t("msg.select_peripheral_first"))
            return

        current_register = self.state_manager.get_current_register()
        if not current_register:
            QMessageBox.warning(self, t("message.warning"), t("msg.select_register_first"))
            return

        # 检查位域是否存在
        if (current_peripheral not in self.state_manager.device_info.peripherals or
            current_register not in self.state_manager.device_info.peripherals[current_peripheral].registers or
            field_name not in self.state_manager.device_info.peripherals[current_peripheral].registers[current_register].fields):
            QMessageBox.warning(self, t("message.warning"), t("msg.field_not_exist", name=field_name))
            return

        # 获取位域对象
        field = self.state_manager.device_info.peripherals[current_peripheral].registers[current_register].fields[field_name]

        # 设置当前寄存器的位域数据（用于位范围冲突检测）
        register_obj = self.state_manager.device_info.peripherals[current_peripheral].registers[current_register]
        self.dialog_factory.set_existing_fields(register_obj.fields)

        # 创建对话框
        dialog = self.dialog_factory.create_field_dialog(field, is_edit=True)

        if dialog.exec():
            result = getattr(dialog, "result_data", None)
            if result is None:
                return

            # 保存旧数据
            old_field = field
            old_name = field_name
            new_name = result["name"]

            # 检查名称是否已更改
            name_changed = old_name != new_name

            # 创建更新后的位域对象
            from ...core.data_model import Field
            updated_field = Field(
                name=new_name,
                bit_offset=int(result["offset"]),
                bit_width=int(result["width"]),
                description=result["description"],
                display_name=result["display_name"],
                access=result["access"],
                reset_value=result["reset_value"]
            )

            # 使用StateManager更新位域
            if name_changed:
                # 先删除旧的，再添加新的
                self.state_manager.delete_field(current_peripheral, current_register, old_name)
                self.state_manager.add_field(current_peripheral, current_register, updated_field)
            else:
                # 直接更新
                self.state_manager.update_field(current_peripheral, current_register, old_name, updated_field)

            # 更新UI
            self.peripheral_manager.update_peripheral_tree()

            # 选中更新后的位域
            self.peripheral_manager.select_field(current_peripheral, current_register, new_name)

            # 更新状态
            self.layout_manager.update_status(t("status.field_updated", name=new_name))
            self.logger.info(f"编辑位域: {old_name} -> {new_name}")

            # 发射数据变化信号
            self.data_changed.emit()

    def delete_field(self, field_name: str = None):
        """删除位域"""
        # 如果没有提供位域名，尝试从当前选择获取
        if field_name is None:
            current_field = self.state_manager.get_current_field()
            if not current_field:
                QMessageBox.warning(self, t("message.warning"), t("msg.select_field_first"))
                return
            field_name = current_field

        # 检查是否有选中的外设和寄存器
        current_peripheral = self.state_manager.get_current_peripheral()
        if not current_peripheral:
            QMessageBox.warning(self, t("message.warning"), t("msg.select_peripheral_first"))
            return

        current_register = self.state_manager.get_current_register()
        if not current_register:
            QMessageBox.warning(self, t("message.warning"), t("msg.select_register_first"))
            return

        # 检查位域是否存在
        if (current_peripheral not in self.state_manager.device_info.peripherals or
            current_register not in self.state_manager.device_info.peripherals[current_peripheral].registers or
            field_name not in self.state_manager.device_info.peripherals[current_peripheral].registers[current_register].fields):
            QMessageBox.warning(self, t("message.warning"), t("msg.field_not_exist", name=field_name))
            return

        # 确认删除
        reply = QMessageBox.question(
            self, t("msg.confirm_delete"),
            t("msg.confirm_delete_field", name=field_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # 暂停通知，防止删除和连锁操作过程中多次重建树
        self.state_manager.pause_notifications()

        try:
            # 使用StateManager删除位域
            self.state_manager.delete_field(current_peripheral, current_register, field_name)

            # 执行连锁操作
            chain_results = self.chain_rules_engine.execute_chain(
                self.state_manager.device_info, "field",
                current_peripheral, current_register, field_name, "delete")
            chain_messages = []
            for r in chain_results:
                if r['success']:
                    chain_messages.append(r['message'])
                    self.logger.info(f"连锁操作: {r['message']}")
        finally:
            # 恢复通知，触发一次统一的树重建
            self.state_manager.resume_notifications()

        # 清除位域选择
        self.state_manager.set_selection(field=None)

        # 更新状态
        status_msg = t("status.field_deleted", name=field_name)
        if chain_messages:
            status_msg += " " + t("status.chain_items", count=len(chain_messages))
        self.layout_manager.update_status(status_msg)
        self.logger.info(f"Deleted field: {field_name}")

        # 显示连锁结果
        if chain_messages:
            QMessageBox.information(self, t("msg.chain_operation", default="连锁操作"),
                t("msg.chain_result", default="已同步删除以下关联项:\n") + "\n".join(chain_messages))

        # 发射数据变化信号
        self.data_changed.emit()

    def move_field_up_down(self, field_name: str, direction: str = "up"):
        """上移或下移位域（在同一个寄存器内调整顺序）

        Args:
            field_name: 位域名称
            direction: "up" 或 "down"
        """
        try:
            selection = self.state_manager.get_selection()
            periph_name = selection.get('peripheral')
            reg_name = selection.get('register')

            if not periph_name or not reg_name:
                # 尝试从树控件获取上下文
                periph_tree = self.layout_manager.get_widget('periph_tree')
                if not periph_tree:
                    return
                from ..model.device_tree_model import DeviceTreeModel
                model = periph_tree.model()
                if not isinstance(model, DeviceTreeModel):
                    return
                current_index = periph_tree.currentIndex()
                if not current_index.isValid():
                    return
                item_type = model.data(current_index, DeviceTreeModel.NodeTypeRole)
                if item_type != "field":
                    return
                periph_name = model.get_peripheral_name(current_index)
                reg_name = model.get_register_name(current_index)

            peripheral = self.state_manager.device_info.peripherals.get(periph_name)
            if not peripheral:
                return
            register = peripheral.registers.get(reg_name)
            if not register:
                return

            field_names = list(register.fields.keys())
            if field_name not in field_names:
                return

            current_idx = field_names.index(field_name)

            if direction == "up" and current_idx <= 0:
                self.layout_manager.update_status(t("status.field_at_top", name=field_name))
                return
            elif direction == "down" and current_idx >= len(field_names) - 1:
                self.layout_manager.update_status(t("status.field_at_bottom", name=field_name))
                return

            # 计算交换后的顺序
            new_field_names = field_names[:]
            swap_idx = current_idx - 1 if direction == "up" else current_idx + 1
            new_field_names[current_idx], new_field_names[swap_idx] = new_field_names[swap_idx], new_field_names[current_idx]

            captured_old = field_names[:]
            captured_new = new_field_names[:]
            captured_periph = periph_name
            captured_reg = reg_name
            state_mgr = self.state_manager

            def execute_reorder():
                """重做：应用新顺序"""
                reg = state_mgr.device_info.peripherals.get(captured_periph, {}).registers.get(captured_reg)
                if reg is None:
                    return False
                old_fields = reg.fields
                reg.fields = {name: old_fields[name] for name in captured_new if name in old_fields}
                state_mgr._notify_state_change()
                return True

            def undo_reorder():
                """撤销：恢复旧顺序"""
                reg = state_mgr.device_info.peripherals.get(captured_periph, {}).registers.get(captured_reg)
                if reg is None:
                    return False
                old_fields = reg.fields
                reg.fields = {name: old_fields[name] for name in captured_old if name in old_fields}
                state_mgr._notify_state_change()
                return True

            from svd_tool.core.command_history import Command
            command = Command(
                execute=execute_reorder,
                undo=undo_reorder,
                description=f"{'上移' if direction == 'up' else '下移'}位域: {field_name}"
            )
            result = self.state_manager.execute_command(command)

            if result:
                # 延迟选中位域
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(50, lambda: self.peripheral_manager.select_field(periph_name, reg_name, field_name))
                self.layout_manager.update_status(t("status.field_moved_up" if direction == "up" else "status.field_moved_down", name=field_name))
            else:
                self.layout_manager.update_status(t("status.field_at_top" if direction == "up" else "status.field_at_bottom", name=field_name))

        except Exception as e:
            self.logger.error(f"移动位域失败: {str(e)}")

    def add_interrupt(self):
        """添加中断"""
        # 获取外设列表
        periph_list = list(self.state_manager.device_info.peripherals.keys())

        # 创建中断对话框
        dialog = self.dialog_factory.create_interrupt_dialog(
            interrupt=None,
            peripherals=periph_list,
            is_edit=False
        )

        if dialog.exec():
            result = getattr(dialog, "result_data", None)
            if result is None:
                return

            # 创建中断对象
            from ...core.data_model import Interrupt
            peripherals = result.get("peripherals", [result["peripheral"]] if result.get("peripheral") else [])
            interrupt = Interrupt(
                name=result["name"],
                value=result["value"],  # 保持为int
                description=result["description"],
                peripheral=result["peripheral"],
                peripherals=peripherals
            )

            # 使用StateManager添加中断
            self.state_manager.add_interrupt(interrupt)

            # 更新中断表格
            self._update_interrupt_table()

            # 更新状态
            self.layout_manager.update_status(t("status.interrupt_added", name=interrupt.name))
            self.logger.info(f"添加中断: {interrupt.name}")

            # 发射数据变化信号
            self.data_changed.emit()

    def edit_interrupt(self, interrupt_name: str = None):
        """编辑中断"""
        # 如果没有提供中断名，尝试从当前选择获取
        if interrupt_name is None:
            # 获取中断表格当前选中的行
            irq_table = self.layout_manager.get_widget('irq_table')
            if not irq_table:
                QMessageBox.warning(self, t("message.warning"), t("msg.interrupt_table_not_found"))
                return

            selected_rows = irq_table.selectedItems()
            if not selected_rows:
                QMessageBox.warning(self, t("message.warning"), t("msg.select_interrupt_first"))
                return

            # 获取第一列（名称列）的文本
            interrupt_name = selected_rows[0].text()

        # 检查中断是否存在
        if interrupt_name not in self.state_manager.device_info.interrupts:
            QMessageBox.warning(self, t("message.warning"), t("msg.interrupt_not_exist", name=interrupt_name))
            return

        # 获取中断对象
        interrupt = self.state_manager.device_info.interrupts[interrupt_name]

        # 获取外设列表
        periph_list = list(self.state_manager.device_info.peripherals.keys())

        # 创建中断对话框
        dialog = self.dialog_factory.create_interrupt_dialog(
            interrupt=interrupt,
            peripherals=periph_list,
            is_edit=True
        )

        if dialog.exec():
            result = getattr(dialog, "result_data", None)
            if result is None:
                return

            # 检查名称是否更改
            old_name = interrupt_name
            new_name = result["name"]
            name_changed = old_name != new_name

            # 创建更新后的中断对象
            from ...core.data_model import Interrupt
            updated_peripherals = result.get("peripherals", [result["peripheral"]] if result.get("peripheral") else [])
            updated_interrupt = Interrupt(
                name=new_name,
                value=result["value"],  # 保持为int
                description=result["description"],
                peripheral=result["peripheral"],
                peripherals=updated_peripherals
            )

            # 使用StateManager更新中断
            if name_changed:
                # 先删除旧的，再添加新的
                self.state_manager.delete_interrupt(old_name)
                self.state_manager.add_interrupt(updated_interrupt)
            else:
                # 直接更新
                self.state_manager.update_interrupt(old_name, updated_interrupt)

            # 更新中断表格
            self._update_interrupt_table()

            # 更新状态
            self.layout_manager.update_status(t("status.interrupt_updated", name=new_name))
            self.logger.info(f"编辑中断: {old_name} -> {new_name}")

            # 发射数据变化信号
            self.data_changed.emit()

    def delete_interrupt(self, interrupt_name: str = None):
        """删除中断"""
        # 如果没有提供中断名，尝试从当前选择获取
        if interrupt_name is None:
            # 获取中断表格当前选中的行
            irq_table = self.layout_manager.get_widget('irq_table')
            if not irq_table:
                QMessageBox.warning(self, t("message.warning"), t("msg.interrupt_table_not_found"))
                return

            selected_rows = irq_table.selectedItems()
            if not selected_rows:
                QMessageBox.warning(self, t("message.warning"), t("msg.select_interrupt_first"))
                return

            # 获取第一列（名称列）的文本
            interrupt_name = selected_rows[0].text()

        # 检查中断是否存在
        if interrupt_name not in self.state_manager.device_info.interrupts:
            QMessageBox.warning(self, t("message.warning"), t("msg.interrupt_not_exist", name=interrupt_name))
            return

        # 确认删除
        reply = QMessageBox.question(
            self, t("msg.confirm_delete"),
            t("msg.confirm_delete_interrupt", name=interrupt_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # 使用StateManager删除中断
        self.state_manager.delete_interrupt(interrupt_name)

        # 更新中断表格
        self._update_interrupt_table()

        # 更新状态
        self.layout_manager.update_status(t("status.interrupt_deleted", name=interrupt_name))
        self.logger.info(f"删除中断: {interrupt_name}")

        # 发射数据变化信号
        self.data_changed.emit()

    def _update_interrupt_table(self):
        """更新中断表格"""
        irq_table = self.layout_manager.get_widget('irq_table')
        if not irq_table:
            return

        # 清空表格
        irq_table.setRowCount(0)

        # 获取所有中断
        interrupts = self.state_manager.device_info.interrupts

        # 按中断值排序
        sorted_interrupts = sorted(interrupts.values(), key=lambda x: x.value)

        # 填充表格（列顺序：名称、值、外设、描述）
        for i, interrupt in enumerate(sorted_interrupts):
            irq_table.insertRow(i)
            from PyQt6.QtWidgets import QTableWidgetItem
            irq_table.setItem(i, 0, QTableWidgetItem(interrupt.name))
            irq_table.setItem(i, 1, QTableWidgetItem(str(interrupt.value)))
            # 显示所有关联外设（逗号分隔）
            periph_display = ", ".join(interrupt.peripherals) if interrupt.peripherals else (interrupt.peripheral or "")
            irq_table.setItem(i, 2, QTableWidgetItem(periph_display))
            irq_table.setItem(i, 3, QTableWidgetItem(interrupt.description or ""))

    def on_add_button_clicked(self):
        """统一的添加按钮点击事件 - 根据当前选择智能添加"""
        # 获取当前选择
        selection = self.state_manager.get_selection()
        peripheral = selection.get('peripheral')
        register = selection.get('register')
        field = selection.get('field')

        # 根据选择决定添加什么
        if not peripheral:
            # 没有选中外设，添加外设
            self.peripheral_manager.add_peripheral_dialog()
        elif peripheral and not register:
            # 选中了外设但没有选中寄存器，添加寄存器
            self.add_register()
        elif peripheral and register:
            # 选中了外设和寄存器，添加位域
            self.add_field()

    def on_edit_button_clicked(self):
        """统一的编辑按钮点击事件 - 根据当前选择智能编辑"""
        # 获取当前选择
        selection = self.state_manager.get_selection()
        peripheral = selection.get('peripheral')
        register = selection.get('register')
        field = selection.get('field')

        # 根据选择决定编辑什么
        if field and peripheral and register:
            # 编辑位域
            self.edit_field(field)
        elif register and peripheral:
            # 编辑寄存器
            self.edit_register(register)
        elif peripheral:
            # 编辑外设
            self.peripheral_manager.edit_peripheral(peripheral)
        else:
            # 没有选择任何项目
            self.show_message("提示", "请先选择一个项目进行编辑", "info")

    def on_delete_button_clicked(self):
        """统一的删除按钮点击事件 - 支持多选批量删除"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            return

        from ..model.device_tree_model import DeviceTreeModel
        model = periph_tree.model()
        if not isinstance(model, DeviceTreeModel):
            return

        selected = periph_tree.selectionModel().selectedIndexes()
        if not selected:
            self.show_message(t("message.warning", default="提示"),
                              t("msg.select_item_first", default="请先选择要删除的项目"), "info")
            return

        # 多选批量删除
        if len(selected) > 1:
            self._batch_delete_selected(selected)
            return

        # 单选删除
        index = selected[0]
        item_type = model.data(index, DeviceTreeModel.NodeTypeRole)
        item_name = model.data(index, DeviceTreeModel.NodeNameRole)

        if item_type == "field":
            periph_name = model.get_peripheral_name(index)
            reg_name = model.get_register_name(index)
            if periph_name and reg_name:
                self.state_manager.set_selection(
                    peripheral=periph_name, register=reg_name, field=item_name)
            self.delete_field(item_name)
        elif item_type == "register":
            periph_name = model.get_peripheral_name(index)
            if periph_name:
                self.state_manager.set_selection(
                    peripheral=periph_name, register=item_name)
            self.delete_register(item_name)
        elif item_type == "peripheral":
            self.peripheral_manager.delete_selected_peripheral()

    def _batch_delete_selected(self, items: list):
        """批量删除选中的项目"""
        from ..model.device_tree_model import DeviceTreeModel
        # ===== 第一步：先收集所有待删除项的信息（在树被重建之前） =====
        to_delete_periphs = []
        to_delete_regs = []  # (periph, reg)
        to_delete_fields = []  # (periph, reg, field)

        periph_tree = self.layout_manager.get_widget('periph_tree')
        model = periph_tree.model() if periph_tree else None

        for item in items:
            if isinstance(model, DeviceTreeModel):
                # item is QModelIndex
                item_type = model.data(item, DeviceTreeModel.NodeTypeRole)
                item_name = model.data(item, DeviceTreeModel.NodeNameRole)

                if item_type == "peripheral":
                    to_delete_periphs.append(item_name)
                elif item_type == "register":
                    periph_name = model.get_peripheral_name(item)
                    if periph_name:
                        to_delete_regs.append((periph_name, item_name))
                elif item_type == "field":
                    periph_name = model.get_peripheral_name(item)
                    reg_name = model.get_register_name(item)
                    if periph_name and reg_name:
                        to_delete_fields.append((periph_name, reg_name, item_name))
            else:
                # 兼容旧 QTreeWidgetItem
                from PyQt6.QtCore import Qt
                item_type = item.data(0, Qt.ItemDataRole.UserRole)
                item_name = item.data(0, Qt.ItemDataRole.UserRole + 1)

                if item_type == "peripheral":
                    to_delete_periphs.append(item_name)
                elif item_type == "register":
                    periph_item = item.parent()
                    if periph_item:
                        periph_name = periph_item.data(0, Qt.ItemDataRole.UserRole + 1)
                        to_delete_regs.append((periph_name, item_name))
                elif item_type == "field":
                    reg_item = item.parent()
                    periph_item = reg_item.parent() if reg_item else None
                    if reg_item and periph_item:
                        periph_name = periph_item.data(0, Qt.ItemDataRole.UserRole + 1)
                        reg_name = reg_item.data(0, Qt.ItemDataRole.UserRole + 1)
                        to_delete_fields.append((periph_name, reg_name, item_name))

        total = len(to_delete_periphs) + len(to_delete_regs) + len(to_delete_fields)
        if total == 0:
            return

        # 构建确认消息
        msg_parts = []
        if to_delete_periphs:
            msg_parts.append(f"外设: {', '.join(to_delete_periphs)}")
        if to_delete_regs:
            reg_names = [f"{p}.{r}" for p, r in to_delete_regs]
            msg_parts.append(f"寄存器: {', '.join(reg_names)}")
        if to_delete_fields:
            field_names = [f"{p}.{r}.{f}" for p, r, f in to_delete_fields]
            msg_parts.append(f"位域: {', '.join(field_names)}")

        confirm_msg = f"确定要删除以下 {total} 个项目吗？\n\n" + "\n".join(msg_parts)

        reply = QMessageBox.question(
            self, "批量删除确认",
            confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # ===== 第二步：暂停状态通知，防止每次删除都重建树 =====
        self.state_manager.pause_notifications()

        deleted_count = 0
        chain_messages = []

        try:
            # 删除位域（先删位域，再删寄存器，最后删外设，避免依赖问题）
            for periph, reg, field_name in to_delete_fields:
                try:
                    # 先执行连锁规则（在数据还完整时）
                    chain_results = self.chain_rules_engine.execute_chain(
                        self.state_manager.device_info, "field", periph, reg, field_name, "delete")
                    for r in chain_results:
                        if r['success']:
                            chain_messages.append(r['message'])
                    # 再删除位域本身
                    self.state_manager.delete_field(periph, reg, field_name)
                    deleted_count += 1
                except Exception as e:
                    self.logger.error(f"批量删除位域 {periph}.{reg}.{field_name} 失败: {e}")

            # 删除寄存器
            for periph, reg_name in to_delete_regs:
                try:
                    self.state_manager.delete_register(periph, reg_name)
                    deleted_count += 1
                except Exception as e:
                    self.logger.error(f"批量删除寄存器 {periph}.{reg_name} 失败: {e}")

            # 删除外设
            for periph_name in to_delete_periphs:
                try:
                    self.state_manager.delete_peripheral(periph_name)
                    deleted_count += 1
                except Exception as e:
                    self.logger.error(f"批量删除外设 {periph_name} 失败: {e}")

        finally:
            # ===== 第三步：恢复通知并统一刷新UI =====
            # update_peripheral_tree 内部已处理 blockSignals
            self.state_manager.resume_notifications()

        # 清除选择
        self.state_manager.set_selection(peripheral=None, register=None, field=None)
        self.update_data_stats()

        status_msg = t("status.batch_deleted", count=deleted_count)
        if chain_messages:
            status_msg += " " + t("status.chain_items", count=len(chain_messages))
        self.layout_manager.update_status(status_msg)
        self.logger.info(f"Batch delete complete: {deleted_count} items")

        # 显示连锁结果
        if chain_messages:
            QMessageBox.information(self, t("msg.chain_operation"),
                t("msg.chain_result") + "\n".join(chain_messages))

        self.data_changed.emit()

    def sort_fields_by_offset(self, field_name: str = None):
        """将当前寄存器中的位域按位偏移排序

        Args:
            field_name: 当前选中的位域名（用于定位寄存器），可为None
        """
        try:
            selection = self.state_manager.get_selection()
            periph_name = selection.get('peripheral')
            reg_name = selection.get('register')

            if not periph_name or not reg_name:
                # 尝试从树控件获取上下文
                periph_tree = self.layout_manager.get_widget('periph_tree')
                if not periph_tree:
                    return
                from ..model.device_tree_model import DeviceTreeModel
                tree_model = periph_tree.model()
                if not isinstance(tree_model, DeviceTreeModel):
                    return
                current_index = periph_tree.currentIndex()
                if not current_index.isValid():
                    return
                item_type = tree_model.data(current_index, DeviceTreeModel.NodeTypeRole)
                if item_type not in ("field", "register"):
                    return
                periph_name = tree_model.get_peripheral_name(current_index)
                reg_name = tree_model.get_register_name(current_index)

            peripheral = self.state_manager.device_info.peripherals.get(periph_name)
            if not peripheral:
                return
            register = peripheral.registers.get(reg_name)
            if not register:
                return

            # 保存旧顺序
            old_field_names = list(register.fields.keys())
            # 按bit_offset降序排序（高位在前）
            new_field_names = [
                name for name, _ in sorted(
                    register.fields.items(),
                    key=lambda x: x[1].bit_offset,
                    reverse=True
                )
            ]

            if old_field_names == new_field_names:
                self.layout_manager.update_status(t("status.field_already_sorted"))
                return

            captured_old = old_field_names[:]
            captured_new = new_field_names[:]
            captured_periph = periph_name
            captured_reg = reg_name
            state_mgr = self.state_manager

            def execute_sort():
                reg = state_mgr.device_info.peripherals.get(captured_periph, {}).registers.get(captured_reg)
                if reg is None:
                    return False
                old_fields = reg.fields
                reg.fields = {name: old_fields[name] for name in captured_new if name in old_fields}
                state_mgr._notify_state_change()
                return True

            def undo_sort():
                reg = state_mgr.device_info.peripherals.get(captured_periph, {}).registers.get(captured_reg)
                if reg is None:
                    return False
                old_fields = reg.fields
                reg.fields = {name: old_fields[name] for name in captured_old if name in old_fields}
                state_mgr._notify_state_change()
                return True

            from svd_tool.core.command_history import Command
            command = Command(
                execute=execute_sort,
                undo=undo_sort,
                description=f"按位偏移排序位域: {periph_name}/{reg_name}"
            )
            self.state_manager.execute_command(command)
            self.layout_manager.update_status(t("status.sort_field_offset", name=reg_name))

        except Exception as e:
            self.logger.error(f"按位偏移排序位域失败: {str(e)}")

    def sort_items_alphabetically(self):
        """按字母顺序排序"""
        try:
            # 保存当前选中项
            selected_periph = self.state_manager.current_peripheral
            selected_register = self.state_manager.current_register

            # 执行排序
            changed = self.state_manager.sort_peripherals_alphabetically()

            if changed:
                # 更新UI
                self.peripheral_manager.update_peripheral_tree()

                # 恢复选中项
                if selected_periph:
                    self.peripheral_manager.select_peripheral(selected_periph)

                # 更新状态
                self.layout_manager.update_status(t("status.sort_alpha"))
                self.logger.info("按字母顺序排序完成")
            else:
                self.layout_manager.update_status(t("status.no_change_sort"))

        except Exception as e:
            self.logger.error(f"按字母排序失败: {str(e)}")
            QMessageBox.warning(self, t("msg.sort_error"), t("msg.sort_alphabetically_failed", error=str(e)))

    def sort_items_by_address(self):
        """按地址/偏移排序"""
        try:
            # 保存当前选中项
            selected_periph = self.state_manager.current_peripheral
            selected_register = self.state_manager.current_register

            # 根据当前选择决定排序类型
            if selected_register:
                # 排序寄存器
                changed = self.state_manager.sort_registers_by_address(selected_periph)
                if changed:
                    self.peripheral_manager.update_peripheral_tree()
                    self.layout_manager.update_status(t("status.sort_register_offset"))
            elif selected_periph:
                # 排序外设
                changed = self.state_manager.sort_peripherals_by_address()
                if changed:
                    self.peripheral_manager.update_peripheral_tree()
                    self.layout_manager.update_status(t("status.sort_address"))
            else:
                # 默认排序外设
                changed = self.state_manager.sort_peripherals_by_address()
                if changed:
                    self.peripheral_manager.update_peripheral_tree()
                    self.layout_manager.update_status(t("status.sort_address"))

            # 恢复选中项
            if selected_periph:
                self.peripheral_manager.select_peripheral(selected_periph)
                if selected_register:
                    # 这里需要添加选择寄存器的功能
                    pass

            if changed:
                self.logger.info("按地址排序完成")
            else:
                self.layout_manager.update_status(t("status.no_change_sort"))

        except Exception as e:
            self.logger.error(f"按地址排序失败: {str(e)}")
            QMessageBox.warning(self, t("msg.sort_error"), t("msg.sort_by_address_failed", error=str(e)))

    def undo(self):
        """撤销操作"""
        if not self.state_manager.command_history.can_undo():
            self.logger.debug("没有可撤销的操作")
            return

        self.state_manager.undo()

        # 刷新UI
        self.peripheral_manager.update_peripheral_tree()
        self.preview_manager.refresh_preview(immediate=True)
        self.update_data_stats()
        self._update_interrupt_table()

        # 恢复选中状态到树控件
        selection = self.state_manager.get_selection()
        periph = selection.get('peripheral')
        reg = selection.get('register')
        field_name = selection.get('field')
        if field_name and reg and periph:
            self.peripheral_manager.select_field(periph, reg, field_name)
        elif reg and periph:
            self.peripheral_manager.select_register(periph, reg)
        elif periph:
            self.peripheral_manager._select_peripheral_in_tree(periph)

        self.layout_manager.update_status(t("status.undo_success", default="已撤销"))
        self.logger.info("撤销操作完成")

    def redo(self):
        """重做操作"""
        if not self.state_manager.command_history.can_redo():
            self.logger.debug("没有可重做的操作")
            return

        self.state_manager.redo()

        # 刷新UI
        self.peripheral_manager.update_peripheral_tree()
        self.preview_manager.refresh_preview(immediate=True)
        self.update_data_stats()
        self._update_interrupt_table()
        self.layout_manager.update_status(t("status.redo_success", default="已重做"))
        self.logger.info("重做操作完成")

    def move_item_up(self):
        """上移选中项目（只支持外设）"""
        try:
            # 使用PeripheralManager的移动功能
            if hasattr(self, 'peripheral_manager'):
                self.peripheral_manager.move_selected_peripheral_up()
            else:
                self.show_message(t("msg.func_unavailable"), t("msg.peripheral_mgr_not_init"), 'warning')
        except Exception as e:
            self.logger.error(f"上移项目时出错: {str(e)}")
            self.show_message(t("msg.operation_failed"), t("msg.move_up_error", error=str(e)), 'error')

    def move_item_down(self):
        """下移选中项目（只支持外设）"""
        try:
            # 使用PeripheralManager的移动功能
            if hasattr(self, 'peripheral_manager'):
                self.peripheral_manager.move_selected_peripheral_down()
            else:
                self.show_message(t("msg.func_unavailable"), t("msg.peripheral_mgr_not_init"), 'warning')
        except Exception as e:
            self.logger.error(f"下移项目时出错: {str(e)}")
            self.show_message(t("msg.operation_failed"), t("msg.move_down_error", error=str(e)), 'error')
