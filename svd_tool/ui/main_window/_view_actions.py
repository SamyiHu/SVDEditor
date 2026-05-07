from PyQt6.QtCore import Qt
from ...i18n.i18n import t


class ViewActionsMixin:

    def toggle_preview_window(self, checked: bool):
        """切换预览窗口显示/隐藏（与显示菜单的勾选状态同步）"""
        self.preview_manager.set_preview_visible(checked)
        self.logger.info(f"预览窗口{'已打开' if checked else '已关闭'}")

    def open_preview_window(self):
        """打开预览窗口（使用预览管理器）"""
        self.preview_manager.set_preview_visible(True)
        # 同步菜单勾选状态
        if hasattr(self, 'toggle_preview_action') and self.toggle_preview_action:
            self.toggle_preview_action.setChecked(True)
        self.logger.info("预览窗口已打开")

    def _on_preview_visibility_changed(self, visible: bool):
        """预览可见性变化时同步菜单勾选状态"""
        if hasattr(self, 'toggle_preview_action') and self.toggle_preview_action:
            self.toggle_preview_action.setChecked(visible)
        self.logger.info(f"预览可见性变化: {visible}")

    def _on_preview_window_closed(self):
        """预览窗口关闭事件"""
        self.logger.info("预览窗口已关闭")
        # 同步菜单勾选状态
        if hasattr(self, 'toggle_preview_action') and self.toggle_preview_action:
            self.toggle_preview_action.setChecked(False)

    def update_visualization(self, peripheral: str, register: str, field: str):
        """更新可视化控件显示"""
        visualization_widget = self.layout_manager.get_widget('visualization_widget')
        if not visualization_widget:
            return

        # 设置主窗口引用
        visualization_widget.main_window = self

        # 设置树状图引用
        tree_widget = self.layout_manager.get_widget('periph_tree')
        visualization_widget.tree_widget = tree_widget

        # 获取设备信息
        device_info = self.state_manager.device_info

        if peripheral:
            # 显示外设
            if peripheral in device_info.peripherals:
                periph = device_info.peripherals[peripheral]
                visualization_widget.show_peripheral(periph)

                if register:
                    # 显示寄存器
                    if register in periph.registers:
                        reg = periph.registers[register]
                        # 如果是继承外设，传递源外设名称
                        source_peripheral_name = periph.derived_from if periph.derived_from else None
                        visualization_widget.show_register(reg, source_peripheral_name)

                        if field:
                            # 显示位域
                            if field in reg.fields:
                                field_obj = reg.fields[field]
                                visualization_widget.show_field(field_obj)
                            else:
                                visualization_widget.show_field(None)
                        else:
                            visualization_widget.show_field(None)
                    else:
                        visualization_widget.show_register(None)
                else:
                    visualization_widget.show_register(None)
            else:
                visualization_widget.show_peripheral(None)
        else:
            # 没有选中外设，清空可视化
            visualization_widget.show_peripheral(None)

    def on_field_clicked(self, field):
        """位域点击事件处理（位域图 → 树 + 表格联动）"""
        # 获取当前选择
        selection = self.state_manager.get_selection()
        peripheral = selection.get('peripheral')
        register = selection.get('register')

        if not peripheral or not register:
            return

        field_name = field.name if field else None

        # 设置选择
        self.state_manager.set_selection(
            peripheral=peripheral,
            register=register,
            field=field_name
        )

        # 更新树控件中的选择
        if field and peripheral and register:
            self.peripheral_manager.select_field(peripheral, register, field.name)

            # 同步高亮位域表格中对应的行
            self._highlight_field_in_table(field_name)

    def _highlight_field_in_table(self, field_name: str):
        """在位域表格中高亮指定位域所在的行"""
        field_table = self.layout_manager.get_widget('field_table')
        if not field_table or not field_name:
            return

        # 阻塞信号避免循环触发
        field_table.blockSignals(True)

        for row in range(field_table.rowCount()):
            item = field_table.item(row, 0)
            if item and item.text() == field_name:
                field_table.selectRow(row)
                field_table.scrollToItem(item)
                break

        field_table.blockSignals(False)

    def on_compact_tree_changed(self, state):
        """紧凑模式复选框/开关状态变化 → 重建树"""
        checked = bool(state)
        self.logger.info(f"紧凑模式: {'启用' if checked else '禁用'}")

        # 紧凑模式变化需要完整重建（register 的 _has_children_hint 会变化）
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if periph_tree:
            model = periph_tree.model()
            from ..model.device_tree_model import DeviceTreeModel
            if isinstance(model, DeviceTreeModel):
                # 先保存展开状态（在 set_compact_mode 重置之前）
                expanded_paths = model.get_expanded_paths(periph_tree)
                if model.set_compact_mode(checked):
                    # 模式变化 → 恢复展开状态
                    if expanded_paths:
                        model.restore_expanded(periph_tree, expanded_paths)

        # 更新状态栏
        status = t("status.compact_mode_on") if checked else t("status.compact_mode_off")
        self.layout_manager.update_status(status)

    def expand_all_tree(self):
        """展开所有树节点"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if periph_tree:
            periph_tree.expandAll()
            self.layout_manager.update_status(t("status.tree_expanded"))

    def collapse_all_tree(self):
        """折叠所有树节点"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if periph_tree:
            periph_tree.collapseAll()
            self.layout_manager.update_status(t("status.tree_collapsed"))

    def _on_tree_item_expanded(self, index):
        """树节点展开时同步展开预览"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            return
        model = periph_tree.model()
        from ..model.device_tree_model import DeviceTreeModel
        if isinstance(model, DeviceTreeModel):
            item_name = model.data(index, DeviceTreeModel.NodeNameRole)
        else:
            return
        self.logger.debug(f"树节点展开: {item_name}")
        if self.preview_manager and self.preview_manager.preview_widget:
            self.preview_manager.preview_widget.sync_fold_from_tree(item_name, is_expanded=True)

    def _on_tree_item_collapsed(self, index):
        """树节点折叠时同步折叠预览"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            return
        model = periph_tree.model()
        from ..model.device_tree_model import DeviceTreeModel
        if isinstance(model, DeviceTreeModel):
            item_name = model.data(index, DeviceTreeModel.NodeNameRole)
        else:
            return
        self.logger.debug(f"树节点折叠: {item_name}")
        if self.preview_manager and self.preview_manager.preview_widget:
            self.preview_manager.preview_widget.sync_fold_from_tree(item_name, is_expanded=False)

    def toggle_left_panel(self):
        """切换左侧面板显示/隐藏"""
        self.layout_manager.toggle_left_panel()

    def toggle_bit_field_visibility(self, checked: bool):
        """切换位域图显示/隐藏"""
        try:
            visualization_widget = self.layout_manager.get_widget('visualization_widget')
            if visualization_widget and hasattr(visualization_widget, 'bit_field'):
                visualization_widget.bit_field.setVisible(not checked)
                self.logger.debug(f"位域图可见性: {not checked}")
        except Exception as e:
            self.logger.error(f"切换位域图可见性时出错: {str(e)}")

    def toggle_address_map_visibility(self, checked: bool):
        """切换地址映射图显示/隐藏"""
        try:
            visualization_widget = self.layout_manager.get_widget('visualization_widget')
            if visualization_widget and hasattr(visualization_widget, 'address_map'):
                visualization_widget.address_map.setVisible(not checked)
                self.logger.debug(f"地址映射图可见性: {not checked}")
        except Exception as e:
            self.logger.error(f"切换地址映射图可见性时出错: {str(e)}")
