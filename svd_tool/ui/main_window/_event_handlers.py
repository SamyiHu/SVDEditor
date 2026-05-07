"""
EventHandlersMixin - 事件处理相关的方法
从 main_window_refactored.py 中提取的事件处理器方法
"""
from PyQt6.QtWidgets import QMessageBox, QMenu


class EventHandlersMixin:
    """事件处理混入类 - 提供所有事件处理方法"""

    def on_peripheral_added(self, periph_name: str):
        """外设添加事件"""
        self.logger.info(f"外设 '{periph_name}' 已添加")
        self.update_data_stats()

    def on_peripheral_updated(self, periph_name: str):
        """外设更新事件"""
        self.logger.info(f"外设 '{periph_name}' 已更新")
        self.update_data_stats()

    def on_peripheral_deleted(self, periph_name: str):
        """外设删除事件"""
        self.logger.info(f"外设 '{periph_name}' 已删除")
        self.update_data_stats()

    def on_register_clicked(self, register):
        """寄存器点击事件处理"""
        # 获取当前选择
        selection = self.state_manager.get_selection()
        peripheral = selection.get('peripheral')

        if not peripheral:
            return

        # 设置选择
        self.state_manager.set_selection(
            peripheral=peripheral,
            register=register.name if register else None,
            field=None
        )

        # 更新树控件中的选择
        if register and peripheral:
            self.peripheral_manager.select_register(peripheral, register.name)

    def on_jump_to_peripheral(self, peripheral_name: str):
        """跳转到外设事件处理（用于继承外设的跳转）"""
        self.logger.debug(f"===== on_jump_to_peripheral called with: {peripheral_name} =====")
        # 更新状态管理器的选择状态
        self.state_manager.set_selection(peripheral=peripheral_name)

        # 更新可视化控件
        self.update_visualization(peripheral_name, '', '')
        self.logger.debug("===== on_jump_to_peripheral completed =====")

    def on_field_table_double_clicked(self, index):
        """位域表格双击事件处理 - 打开编辑界面"""
        from PyQt6.QtCore import QModelIndex

        if not index.isValid():
            return

        # 获取当前选择
        selection = self.state_manager.get_selection()
        peripheral = selection.get('peripheral')
        register = selection.get('register')

        if not peripheral or not register:
            return

        # 获取表格和行号
        field_table = self.layout_manager.get_widget('field_table')
        if not field_table:
            return

        row = index.row()

        # 获取位域名称（第一列）
        field_name_item = field_table.item(row, 0)
        if not field_name_item:
            return

        field_name = field_name_item.text()

        # 调用编辑位域方法
        self.edit_field(field_name)

    def on_irq_table_double_clicked(self, index):
        """中断表格双击事件处理 - 打开编辑界面"""
        from PyQt6.QtCore import QModelIndex

        if not index.isValid():
            return

        # 获取表格和行号
        irq_table = self.layout_manager.get_widget('irq_table')
        if not irq_table:
            return

        row = index.row()

        # 获取中断名称（第一列）
        interrupt_name_item = irq_table.item(row, 0)
        if not interrupt_name_item:
            return

        interrupt_name = interrupt_name_item.text()

        # 调用编辑中断方法
        self.edit_interrupt(interrupt_name)

    def on_irq_context_menu(self, pos):
        """中断表格右键菜单"""
        irq_table = self.layout_manager.get_widget('irq_table')
        if not irq_table:
            return

        item = irq_table.itemAt(pos)
        if not item:
            return

        row = item.row()
        interrupt_name = irq_table.item(row, 0).text()

        # 创建右键菜单
        from ...i18n.i18n import t
        menu = QMenu(self)

        edit_action = menu.addAction(t("menu.edit_interrupt"))
        edit_action.setData("edit_interrupt")
        delete_action = menu.addAction(t("menu.delete_interrupt"))
        delete_action.setData("delete_interrupt")

        # 执行菜单动作
        action = menu.exec(irq_table.mapToGlobal(pos))
        if action:
            action_data = action.data()
            if action_data == "edit_interrupt":
                self.edit_interrupt(interrupt_name)
            elif action_data == "delete_interrupt":
                self.delete_interrupt(interrupt_name)

    def on_selection_changed(self, peripheral: str, register: str, field: str):
        """选择变更事件"""
        self.selection_changed.emit(
            'peripheral' if peripheral else 'register' if register else 'field',
            peripheral or register or field or ''
        )

        # StateManager 已有 30ms 防抖，这里直接更新可视化控件
        self.update_visualization(peripheral, register, field)

        # 更新位域表格
        if register and peripheral:
            # 获取寄存器对象
            device_info = self.state_manager.device_info
            if (peripheral in device_info.peripherals and
                register in device_info.peripherals[peripheral].registers):
                reg_obj = device_info.peripherals[peripheral].registers[register]
                self.layout_manager.update_field_table(peripheral, register, reg_obj)
            else:
                # 清空表格
                self.layout_manager.update_field_table()
        else:
            # 清空表格
            self.layout_manager.update_field_table()

    def on_field_table_selection_changed(self):
        """位域表格行选择变化 -> 高亮位域图 + 更新状态"""
        field_table = self.layout_manager.get_widget('field_table')
        if not field_table:
            return

        selected_rows = field_table.selectionModel().selectedRows()
        if not selected_rows:
            return

        row = selected_rows[0].row()
        field_name_item = field_table.item(row, 0)
        if not field_name_item:
            return

        field_name = field_name_item.text()

        # 获取当前选择（外设和寄存器）
        selection = self.state_manager.get_selection()
        peripheral = selection.get('peripheral')
        register = selection.get('register')

        if not peripheral or not register:
            return

        # 更新状态管理器选择（不触发树重建）
        self.state_manager.set_selection(
            peripheral=peripheral,
            register=register,
            field=field_name
        )

        # 高亮位域图中对应的位域
        visualization_widget = self.layout_manager.get_widget('visualization_widget')
        if visualization_widget and hasattr(visualization_widget, 'bit_field'):
            device_info = self.state_manager.device_info
            if (peripheral in device_info.peripherals and
                register in device_info.peripherals[peripheral].registers and
                field_name in device_info.peripherals[peripheral].registers[register].fields):
                field_obj = device_info.peripherals[peripheral].registers[register].fields[field_name]
                visualization_widget.bit_field.highlight_field(field_name)

    def _on_main_window_selection_changed(self, item_type: str, item_name: str):
        """主窗口选择变化时更新预览"""
        # 使用预览管理器更新预览
        selection = self.state_manager.get_selection()
        self.preview_manager.highlight_element(selection)

    def on_preview_element_selected(self, element_type: str, peripheral_name: str, element_name: str):
        """预览窗口元素选择事件处理

        Args:
            element_type: 元素类型 ('peripheral', 'register', 'field', 'interrupt')
            peripheral_name: 外设名称
            element_name: 元素名称
        """
        # 解析element_name
        register_name = None
        field_name = None

        if element_type == 'register':
            register_name = element_name
        elif element_type == 'field':
            # element_name格式为 "register.field"
            if '.' in element_name:
                register_name, field_name = element_name.split('.', 1)
            else:
                register_name = element_name
        elif element_type == 'interrupt':
            # 中断不需要特殊处理
            pass

        # 更新状态管理器的选择（包含类型信息）
        self.state_manager.set_selection(
            peripheral=peripheral_name,
            register=register_name,
            field=field_name,
            element_type=element_type
        )

        # 在树状图中选中对应的元素（双向同步）
        if hasattr(self, 'peripheral_manager'):
            if element_type == 'peripheral' and peripheral_name:
                self.peripheral_manager.select_peripheral(peripheral_name)
            elif element_type == 'register' and peripheral_name and register_name:
                self.peripheral_manager.select_register(peripheral_name, register_name)
            elif element_type == 'field' and peripheral_name and register_name and field_name:
                self.peripheral_manager.select_field(peripheral_name, register_name, field_name)

        # 更新可视化控件
        self.update_visualization(
            peripheral_name or '',
            register_name or '',
            field_name or ''
        )

        # 更新位域表格
        if register_name and peripheral_name:
            device_info = self.state_manager.device_info
            if (peripheral_name in device_info.peripherals and
                register_name in device_info.peripherals[peripheral_name].registers):
                reg_obj = device_info.peripherals[peripheral_name].registers[register_name]
                self.layout_manager.update_field_table(peripheral_name, register_name, reg_obj)
            else:
                self.layout_manager.update_field_table()
        else:
            self.layout_manager.update_field_table()

    def _on_basic_info_edited(self, _=None):
        """基本信息被用户编辑时 -> 回写到 state_manager.device_info -> 刷新预览"""
        if self._basic_info_updating:
            return
        di = self.state_manager.device_info
        if not di:
            return

        # 读取控件值 -> 回写 device_info
        w = self.layout_manager.get_widget
        _text = lambda k: w(k).text().strip() if w(k) else None
        _check = lambda k: w(k).isChecked() if w(k) and hasattr(w(k), 'isChecked') else None
        _combo = lambda k: w(k).currentText() if w(k) else None
        _value = lambda k: w(k).value() if w(k) else None

        name = _text('ic_name_edit')
        if name is not None:
            di.name = name
        desc = _text('ic_desc_edit')
        if desc is not None:
            di.description = desc
        ver = _text('version_edit')
        if ver is not None:
            di.version = ver
        sv = _combo('svd_version_combo')
        if sv is not None:
            di.svd_version = sv
        cpu_name = _text('cpu_name_edit')
        if cpu_name is not None:
            di.cpu.name = cpu_name
        cpu_rev = _text('cpu_rev_edit')
        if cpu_rev is not None:
            di.cpu.revision = cpu_rev
        endian = _combo('endian_combo')
        if endian is not None:
            di.cpu.endian = endian
        mpu = _check('mpu_combo')
        if mpu is not None:
            di.cpu.mpu_present = mpu
        fpu = _check('fpu_combo')
        if fpu is not None:
            di.cpu.fpu_present = fpu
        nvic = _value('nvic_prio_spin')
        if nvic is not None:
            di.cpu.nvic_prio_bits = nvic
        vendor = _text('company_name_edit')
        if vendor is not None:
            di.vendor = vendor
        cp = _text('copyright_edit')
        if cp is not None:
            di.copyright = cp
        author = _text('author_edit')
        if author is not None:
            di.author = author
        lic = _combo('license_combo')
        if lic is not None:
            from ...i18n.i18n import t
            di.license = "" if lic == t("license.do_not_display") else lic

        # 标记修改
        self.document_manager.mark_modified()

        # 刷新预览
        if hasattr(self, 'coordinator') and self.coordinator:
            self.coordinator.emit_event("device_info_updated", di)
        if self.preview_manager and self.preview_manager.preview_widget:
            self.preview_manager.preview_widget.refresh_preview()

    def update_interrupt_buttons_state(self):
        """更新中断按钮状态（根据表格选择）"""
        irq_table = self.layout_manager.get_widget('irq_table')
        edit_irq_btn = self.layout_manager.get_widget('edit_irq_btn')
        delete_irq_btn = self.layout_manager.get_widget('delete_irq_btn')

        if not irq_table or not edit_irq_btn or not delete_irq_btn:
            return

        # 检查是否有选中的行
        has_selection = len(irq_table.selectedItems()) > 0

        # 更新按钮状态
        edit_irq_btn.setEnabled(has_selection)
        delete_irq_btn.setEnabled(has_selection)

    def show_message(self, title: str, text: str, icon: str = 'info'):
        """统一消息弹窗接口：icon in ['info','warning','error']"""
        try:
            if icon == 'info':
                QMessageBox.information(self, title, text)
            elif icon == 'warning':
                QMessageBox.warning(self, title, text)
            else:
                QMessageBox.critical(self, title, text)
        except Exception as e:
            self.logger.error(f"显示消息时出错: {str(e)}")
            # 出错时使用默认的消息框
            QMessageBox.information(self, title, text)

    def update_device_info_from_ui(self):
        """从UI更新设备信息"""
        self.device_info_manager.update_device_info_from_ui()

    def update_data_model_from_tree(self):
        """从树控件更新数据模型（已由 DeviceTreeModel 直接维护，无需手动同步）"""
        pass
