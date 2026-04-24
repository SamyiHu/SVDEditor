"""
外设管理组件
负责处理外设的添加、编辑、删除等UI交互逻辑
"""
from typing import Optional, Dict, Any, List
from PyQt6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QMessageBox, QInputDialog,
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QComboBox, QSpinBox, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QModelIndex

from svd_tool.core.data_model import Peripheral, Register, Field
from .state_manager import StateManager
from svd_tool.core.constants import NODE_TYPES
from ...i18n.i18n import t
from ..model.device_tree_model import DeviceTreeModel
from ..widgets.device_tree_view import DeviceTreeView


class PeripheralManager(QObject):
    """外设管理器"""
    
    # 信号定义
    peripheral_added = pyqtSignal(str)  # 外设名称
    peripheral_updated = pyqtSignal(str)  # 外设名称
    peripheral_deleted = pyqtSignal(str)  # 外设名称
    selection_changed = pyqtSignal(str, str, str)  # peripheral, register, field
    
    def __init__(self, state_manager: StateManager, layout_manager):
        """
        初始化外设管理器
        
        Args:
            state_manager: 状态管理器实例
            layout_manager: 布局管理器实例
        """
        super().__init__()
        self.state_manager = state_manager
        self.layout_manager = layout_manager
        
        # 复制/粘贴缓冲区
        self.copied_peripheral_data = None
        self.copied_register_data = None
        self.copied_field_data = None
        
        # 注册状态变更回调
        self.state_manager.register_state_change_callback(self.on_state_changed)
        self.state_manager.register_selection_change_callback(self.on_selection_changed)
        
        # 标记：跳过下一次 on_state_changed 中的树重建（用于文档切换优化）
        self._skip_next_tree_rebuild = False

        # 连接UI信号
        self.connect_ui_signals()
    
    def connect_ui_signals(self):
        """连接UI信号"""
        periph_tree = self.layout_manager.get_widget('periph_tree')

        if periph_tree and isinstance(periph_tree, DeviceTreeView):
            # 创建并设置 model
            model = DeviceTreeModel(self.state_manager.device_info)
            periph_tree.setModel(model)

            periph_tree.selectionModel().selectionChanged.connect(
                self.on_periph_tree_selection_changed)
            periph_tree.doubleClicked.connect(self.on_periph_tree_double_clicked)
            periph_tree.expanded.connect(self._on_item_expanded)
    
    def on_state_changed(self):
        """状态变更时的处理"""
        # 如果标记跳过（文档切换时已在 _restore_document_state 中手动重建过树），
        # 则只更新 UI 状态，不重建树
        if self._skip_next_tree_rebuild:
            self._skip_next_tree_rebuild = False
            self.update_ui_state()
            return
        self.update_peripheral_tree()
        self.update_ui_state()
    
    def on_selection_changed(self):
        """选择变更时的处理"""
        self.update_ui_state()
    
    def on_periph_tree_selection_changed(self):
        """外设树选择变更"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            return

        model = periph_tree.model()
        if not isinstance(model, DeviceTreeModel):
            return

        selected = periph_tree.selectionModel().selectedIndexes()
        if not selected:
            self.state_manager.set_selection()
            self.selection_changed.emit(None, None, None)
            return

        index = selected[0]
        node_type = model.data(index, DeviceTreeModel.NodeTypeRole)
        node_name = model.data(index, DeviceTreeModel.NodeNameRole)

        if node_type == 'peripheral':
            periph_name = node_name
            self.state_manager.set_selection(peripheral=periph_name, element_type='peripheral')
            self.selection_changed.emit(periph_name, None, None)
        elif node_type == 'register':
            periph_name = model.get_peripheral_name(index)
            reg_name = node_name
            self.state_manager.set_selection(peripheral=periph_name, register=reg_name, element_type='register')
            self.selection_changed.emit(periph_name, reg_name, None)
        elif node_type == 'field':
            periph_name = model.get_peripheral_name(index)
            reg_name = model.get_register_name(index)
            field_name = node_name
            self.state_manager.set_selection(peripheral=periph_name, register=reg_name, field=field_name, element_type='field')
            self.selection_changed.emit(periph_name, reg_name, field_name)
    
    def on_periph_tree_double_clicked(self, index: QModelIndex):
        """外设树双击事件"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        model = periph_tree.model() if periph_tree else None
        if not isinstance(model, DeviceTreeModel):
            return

        node_type = model.data(index, DeviceTreeModel.NodeTypeRole)
        node_name = model.data(index, DeviceTreeModel.NodeNameRole)

        if node_type == 'peripheral':
            self.edit_peripheral(node_name)
        elif node_type == 'register':
            periph_name = model.get_peripheral_name(index)
            self.state_manager.set_selection(peripheral=periph_name, register=node_name)
            if hasattr(self.layout_manager, 'main_window'):
                self.layout_manager.main_window.edit_register(node_name)
        elif node_type == 'field':
            periph_name = model.get_peripheral_name(index)
            reg_name = model.get_register_name(index)
            self.state_manager.set_selection(peripheral=periph_name, register=reg_name, field=node_name)
            if hasattr(self.layout_manager, 'main_window'):
                self.layout_manager.main_window.edit_field(node_name)
    
    def is_compact_tree(self) -> bool:
        """检查是否为紧凑模式（只显示到寄存器级别）"""
        compact_tree_cb = self.layout_manager.get_widget('compact_tree_cb')
        return compact_tree_cb is not None and compact_tree_cb.isChecked()
    
    def update_peripheral_tree(self, preserve_expanded=True):
        """更新外设树（通过 DeviceTreeModel）

        Args:
            preserve_expanded: 是否保留当前展开状态。
                True: 正常编辑操作，保留展开状态。
                False: 文档切换时使用，不保留旧文档的展开状态。
        """
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            return

        model = periph_tree.model()
        if not isinstance(model, DeviceTreeModel):
            return

        if not preserve_expanded:
            # 文档切换：强制完整重建
            model.set_device_info(self.state_manager.device_info)
            return

        # 检查外设列表结构是否变化（名称/顺序）
        current_order = model.get_peripheral_order()
        new_order = list(self.state_manager.device_info.peripherals.keys())

        if current_order == new_order and not model.is_structure_stale():
            # 结构未变（只改了数据值）→ 仅刷新显示数据，保留所有展开/fetched 状态
            # 先更新 model 内部的 device_info 引用，确保数据查找使用最新数据
            model._device_info = self.state_manager.device_info
            model.refresh_data()
        else:
            # 结构变化（增删/重排外设）→ 完整重建，但保留展开状态
            expanded_paths = model.get_expanded_paths(periph_tree)
            model.set_device_info(self.state_manager.device_info)
            if expanded_paths:
                model.restore_expanded(periph_tree, expanded_paths)

    def _get_expanded_items(self, tree):
        """获取当前展开的项目路径（兼容 QTreeWidget 和 QTreeView）"""
        model = tree.model()
        if isinstance(model, DeviceTreeModel):
            return model.get_expanded_paths(tree)
        # 向后兼容（block_navigator 等仍使用 QTreeWidget）
        expanded = []
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            if item.isExpanded():
                expanded.append(item.text(0))
        return expanded

    def _on_item_expanded(self, index: QModelIndex):
        """懒加载：展开节点时触发 model 的 fetchMore"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            return
        model = periph_tree.model()
        if isinstance(model, DeviceTreeModel) and model.canFetchMore(index):
            model.fetchMore(index)

    def update_ui_state(self):
        """更新UI状态（按钮启用/禁用）"""
        # 获取当前选择
        selection = self.state_manager.get_selection()
        has_periph_selected = selection['peripheral'] is not None
        has_register_selected = selection['register'] is not None
        has_field_selected = selection['field'] is not None
        has_any_selection = has_periph_selected or has_register_selected or has_field_selected
        
        # 更新按钮状态
        edit_periph_btn = self.layout_manager.get_widget('edit_periph_btn')
        delete_periph_btn = self.layout_manager.get_widget('delete_periph_btn')
        add_reg_btn = self.layout_manager.get_widget('add_reg_btn')
        add_field_btn = self.layout_manager.get_widget('add_field_btn')
        
        # 编辑和删除按钮：只要有选择就启用
        if edit_periph_btn:
            edit_periph_btn.setEnabled(has_any_selection)
        
        if delete_periph_btn:
            delete_periph_btn.setEnabled(has_any_selection)
        
        # 添加寄存器按钮：选中外设时启用
        if add_reg_btn:
            add_reg_btn.setEnabled(has_periph_selected)
        
        # 添加位域按钮：选中寄存器时启用
        if add_field_btn:
            add_field_btn.setEnabled(has_register_selected)
    
    def add_peripheral_dialog(self):
        """显示添加外设对话框"""
        from svd_tool.ui.dialog_factories import DialogFactory
        
        dialog_factory = DialogFactory(self.layout_manager.main_window)
        # 传递完整外设字典（用于继承关系选择 + 地址冲突检测）
        dialog_factory.set_existing_peripherals(self.state_manager.device_info.peripherals)
        dialog = dialog_factory.create_peripheral_dialog()
        
        if dialog.exec():
            result = getattr(dialog, "result_data", None)
            if result is None:
                return
            
            # 创建外设对象
            from svd_tool.core.data_model import Peripheral
            peripheral = Peripheral(
                name=result["name"],
                base_address=result["base_address"],
                description=result["description"],
                display_name=result["display_name"],
                group_name=result["group_name"],
                derived_from=result["derived_from"],
                address_block=result["address_block"]
            )
            
            # 检查名称是否已存在
            if peripheral.name in self.state_manager.device_info.peripherals:
                QMessageBox.warning(
                    self.layout_manager.main_window,
                    t("warn.title"),
                    t("warn.periph_exists", name=peripheral.name)
                )
                return

            # 添加到状态管理器
            # 注意：add_peripheral 内部通过 execute_command → _notify_state_change → on_state_changed → update_peripheral_tree
            # 不需要在这里再次调用 update_peripheral_tree()（避免双重树重建）
            self.state_manager.add_peripheral(peripheral)
            self.peripheral_added.emit(peripheral.name)
            
            # 选中新添加的外设
            self.state_manager.set_selection(peripheral=peripheral.name)
    
    def edit_selected_peripheral(self):
        """编辑选中的外设"""
        selection = self.state_manager.get_selection()
        periph_name = selection['peripheral']
        
        if periph_name:
            self.edit_peripheral(periph_name)
    
    def edit_peripheral(self, periph_name: str):
        """编辑指定外设"""
        from svd_tool.ui.dialog_factories import DialogFactory
        from svd_tool.core.data_model import Peripheral
        
        # 获取外设数据
        peripheral = self.state_manager.device_info.peripherals.get(periph_name)
        if not peripheral:
            return
        
        dialog_factory = DialogFactory(self.layout_manager.main_window)
        # 传递完整外设字典（用于继承关系选择 + 地址冲突检测）
        dialog_factory.set_existing_peripherals(self.state_manager.device_info.peripherals)
        dialog = dialog_factory.create_peripheral_dialog(peripheral, is_edit=True)
        
        if dialog.exec():
            result = getattr(dialog, "result_data", None)
            if result is None:
                return
            
            # 创建更新后的外设对象
            updated_peripheral = Peripheral(
                name=result["name"],
                base_address=result["base_address"],
                description=result["description"],
                display_name=result["display_name"],
                group_name=result["group_name"],
                derived_from=result["derived_from"],
                address_block=result["address_block"],
                registers=peripheral.registers.copy(),
                interrupts=peripheral.interrupts.copy()
            )
            
            # 如果名称改变，需要检查是否冲突
            if updated_peripheral.name != periph_name:
                if updated_peripheral.name in self.state_manager.device_info.peripherals:
                    QMessageBox.warning(
                        self.layout_manager.main_window,
                        t("warn.title"),
                        t("warn.periph_exists", name=updated_peripheral.name)
                    )
                    return
                
                # 使用 rename_peripheral 方法（保持位置，支持撤销）
                try:
                    self.state_manager.rename_peripheral(periph_name, updated_peripheral.name)
                    # 更新外设的其他属性
                    self.state_manager.update_peripheral(updated_peripheral.name, updated_peripheral)
                except ValueError as e:
                    QMessageBox.warning(
                        self.layout_manager.main_window,
                        t("warn.title"),
                        str(e)
                    )
                    return
                
                # 更新选择
                self.state_manager.set_selection(peripheral=updated_peripheral.name)
            else:
                # 直接更新
                self.state_manager.update_peripheral(periph_name, updated_peripheral)
            
            self.peripheral_updated.emit(updated_peripheral.name)
            
            # 注意：update_peripheral/rename_peripheral 内部已通过 _notify_state_change 触发树重建
            # 不需要在这里再次调用 update_peripheral_tree()（避免双重树重建）
    
    def delete_selected_peripheral(self):
        """删除选中的外设"""
        selection = self.state_manager.get_selection()
        periph_name = selection['peripheral']
        
        if not periph_name:
            return
        
        # 确认对话框
        reply = QMessageBox.question(
            self.layout_manager.main_window,
            t("msg.confirm_delete"),
            t("dialog.confirm_delete_periph", name=periph_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 暂停通知，防止删除过程中多次重建树
            self.state_manager.pause_notifications()
            try:
                self.state_manager.delete_peripheral(periph_name)
            finally:
                self.state_manager.resume_notifications()
            
            self.peripheral_deleted.emit(periph_name)
    
    def get_peripheral_info(self, periph_name: str) -> Optional[Dict[str, Any]]:
        """获取外设信息"""
        peripheral = self.state_manager.device_info.peripherals.get(periph_name)
        if not peripheral:
            return None
        
        # 统计寄存器数量
        register_count = len(peripheral.registers)
        
        # 统计位域数量
        field_count = 0
        for register in peripheral.registers.values():
            field_count += len(register.fields)
        
        return {
            'name': peripheral.name,
            'base_address': peripheral.base_address,
            'description': peripheral.description,
            'registers': register_count,
            'fields': field_count
        }
    
    def validate_peripheral(self, periph_name: str) -> List[str]:
        """验证外设数据，返回错误列表"""
        errors = []
        peripheral = self.state_manager.device_info.peripherals.get(periph_name)
        
        if not peripheral:
            errors.append(t("validation.periph_not_exist", name=periph_name))
            return errors
        
        # 检查基本字段
        if not peripheral.name:
            errors.append(t("validation.periph_name_empty"))

        if not peripheral.base_address:
            errors.append(t("validation.periph_base_empty", default="外设基地址不能为空"))

        # 检查寄存器
        for reg_name, register in peripheral.registers.items():
            if not reg_name:
                errors.append(t("validation.reg_name_empty", name=periph_name))

            # 检查位域
            for field_name, field in register.fields.items():
                if not field_name:
                    errors.append(t("validation.field_name_empty", name=reg_name))
        
        return errors
    
    def handle_tree_context_menu(self, pos):
        """处理树控件右键菜单"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            return

        # 获取点击位置对应的 QModelIndex
        index = periph_tree.indexAt(pos)
        if not index.isValid():
            return

        model = periph_tree.model()
        if not isinstance(model, DeviceTreeModel):
            return

        main_window = self.layout_manager.main_window
        if not hasattr(main_window, 'tree_manager'):
            return

        item_type = model.data(index, DeviceTreeModel.NodeTypeRole)
        item_name = model.data(index, DeviceTreeModel.NodeNameRole)

        # 创建右键菜单（传 node_type 和 node_name）
        menu = main_window.tree_manager.create_context_menu(
            item_type, item_name, parent=periph_tree)

        # 执行菜单动作
        action = menu.exec(periph_tree.mapToGlobal(pos))
        if action:
            action_data = action.data()

            if action_data == "edit_peripheral":
                self.edit_peripheral(item_name)
            elif action_data == "delete_peripheral":
                selected = periph_tree.selectionModel().selectedIndexes()
                if len(selected) > 1:
                    main_window._batch_delete_selected(selected)
                else:
                    self.delete_selected_peripheral()
            elif action_data == "add_register":
                if hasattr(main_window, 'add_register'):
                    self.state_manager.set_selection(peripheral=item_name)
                    main_window.add_register()
            elif action_data == "edit_register":
                if hasattr(main_window, 'edit_register'):
                    main_window.edit_register(item_name)
            elif action_data == "delete_register":
                selected = periph_tree.selectionModel().selectedIndexes()
                if len(selected) > 1:
                    main_window._batch_delete_selected(selected)
                elif hasattr(main_window, 'delete_register'):
                    main_window.delete_register(item_name)
            elif action_data == "add_field":
                if hasattr(main_window, 'add_field'):
                    reg_name = item_name
                    periph_name = model.get_peripheral_name(index)
                    if periph_name:
                        self.state_manager.set_selection(
                            peripheral=periph_name, register=reg_name)
                        main_window.add_field()
            elif action_data == "edit_field":
                if hasattr(main_window, 'edit_field'):
                    main_window.edit_field(item_name)
            elif action_data == "delete_field":
                selected = periph_tree.selectionModel().selectedIndexes()
                if len(selected) > 1:
                    main_window._batch_delete_selected(selected)
                elif hasattr(main_window, 'delete_field'):
                    main_window.delete_field(item_name)
            elif action_data == "sort_alphabetically":
                if hasattr(main_window, 'sort_items_alphabetically'):
                    main_window.sort_items_alphabetically()
            elif action_data == "move_field_up":
                if hasattr(main_window, 'move_field_up_down'):
                    main_window.move_field_up_down(item_name, direction="up")
            elif action_data == "move_field_down":
                if hasattr(main_window, 'move_field_up_down'):
                    main_window.move_field_up_down(item_name, direction="down")
            elif action_data == "sort_fields_by_offset":
                if hasattr(main_window, 'sort_fields_by_offset'):
                    main_window.sort_fields_by_offset(item_name)
            elif action_data == "copy_peripheral":
                self.copy_peripheral(item_name)
            elif action_data == "paste_peripheral":
                self.paste_peripheral()
            elif action_data == "copy_register":
                if item_type == NODE_TYPES["REGISTER"]:
                    periph_name = model.get_peripheral_name(index)
                    if periph_name:
                        self.copy_register(periph_name, item_name)
            elif action_data == "paste_register":
                if item_type == NODE_TYPES["REGISTER"]:
                    periph_name = model.get_peripheral_name(index)
                    if periph_name:
                        self.paste_register(periph_name)
                elif item_type == NODE_TYPES["PERIPHERAL"]:
                    self.paste_register(item_name)
            elif action_data == "copy_field":
                if item_type == NODE_TYPES["FIELD"]:
                    periph_name = model.get_peripheral_name(index)
                    reg_name = model.get_register_name(index)
                    if periph_name and reg_name:
                        self.copy_field(periph_name, reg_name, item_name)
            elif action_data == "paste_field":
                if item_type == NODE_TYPES["FIELD"]:
                    periph_name = model.get_peripheral_name(index)
                    reg_name = model.get_register_name(index)
                    if periph_name and reg_name:
                        self.paste_field(periph_name, reg_name)
                elif item_type == NODE_TYPES["REGISTER"]:
                    periph_name = model.get_peripheral_name(index)
                    reg_name = item_name
                    if periph_name:
                        self.paste_field(periph_name, reg_name)
            elif action_data == "move_up":
                self.move_selected_peripheral_up()
            elif action_data == "move_down":
                self.move_selected_peripheral_down()
    
    def move_selected_peripheral_up(self):
        """上移选中的外设"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            return

        selected = periph_tree.selectionModel().selectedIndexes()
        if not selected:
            QMessageBox.warning(
                self.layout_manager.main_window,
                t("dialog.op_hint"),
                t("msg.select_peripheral_first")
            )
            return

        model = periph_tree.model()
        if not isinstance(model, DeviceTreeModel):
            return

        index = selected[0]
        node_type = model.data(index, DeviceTreeModel.NodeTypeRole)
        if node_type != "peripheral":
            QMessageBox.warning(
                self.layout_manager.main_window,
                t("dialog.op_limit"),
                t("warn.periph_only_move_up")
            )
            return

        periph_name = model.data(index, DeviceTreeModel.NodeNameRole)
        source_row = index.row()
        if source_row <= 0:
            QMessageBox.information(
                self.layout_manager.main_window,
                t("dialog.op_hint"),
                t("warn.periph_at_top")
            )
            return

        # 保存旧顺序
        old_order = model.get_peripheral_order()
        target_row = source_row - 1

        # 执行移动
        model.move_peripheral(source_row, target_row)

        # 记录 undo/redo
        new_order = model.get_peripheral_order()
        self._record_move_command(old_order, new_order, periph_name)

        # 重新选中
        new_idx = model.find_index_by_path(periph_name)
        if new_idx.isValid():
            periph_tree.setCurrentIndex(new_idx)

        main_window = self.layout_manager.main_window
        if hasattr(main_window, 'status_label'):
            main_window.status_label.setText(t("status.periph_moved_up", name=periph_name))

    def move_selected_peripheral_down(self):
        """下移选中的外设"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            return

        selected = periph_tree.selectionModel().selectedIndexes()
        if not selected:
            QMessageBox.warning(
                self.layout_manager.main_window,
                t("dialog.op_hint"),
                t("msg.select_peripheral_first")
            )
            return

        model = periph_tree.model()
        if not isinstance(model, DeviceTreeModel):
            return

        index = selected[0]
        node_type = model.data(index, DeviceTreeModel.NodeTypeRole)
        if node_type != "peripheral":
            QMessageBox.warning(
                self.layout_manager.main_window,
                t("dialog.op_limit"),
                t("warn.periph_only_move_down")
            )
            return

        periph_name = model.data(index, DeviceTreeModel.NodeNameRole)
        source_row = index.row()
        if source_row >= model.rowCount() - 1:
            QMessageBox.information(
                self.layout_manager.main_window,
                t("dialog.op_hint"),
                t("warn.periph_at_bottom")
            )
            return

        old_order = model.get_peripheral_order()
        target_row = source_row + 2  # move down: target_row > source_row

        model.move_peripheral(source_row, target_row)

        new_order = model.get_peripheral_order()
        self._record_move_command(old_order, new_order, periph_name)

        new_idx = model.find_index_by_path(periph_name)
        if new_idx.isValid():
            periph_tree.setCurrentIndex(new_idx)

        main_window = self.layout_manager.main_window
        if hasattr(main_window, 'status_label'):
            main_window.status_label.setText(t("status.periph_moved_down", name=periph_name))

    def _record_move_command(self, old_order: list, new_order: list, periph_name: str):
        """记录外设移动的 undo/redo 命令"""
        if old_order == new_order:
            return
        from ...core.command_history import Command
        captured_old = old_order[:]
        captured_new = new_order[:]
        state_mgr = self.state_manager

        def execute_reorder():
            peripherals = state_mgr.device_info.peripherals
            reordered = {name: peripherals[name]
                         for name in captured_new if name in peripherals}
            state_mgr.device_info.peripherals = reordered
            state_mgr._notify_state_change()
            return True

        def undo_reorder():
            peripherals = state_mgr.device_info.peripherals
            reordered = {name: peripherals[name]
                         for name in captured_old if name in peripherals}
            state_mgr.device_info.peripherals = reordered
            state_mgr._notify_state_change()
            return True

        command = Command(
            execute=execute_reorder,
            undo=undo_reorder,
            description=t("cmd.move_periph_up", name=periph_name)
        )
        state_mgr.command_history.history.append(command)
        state_mgr.command_history.current_index = len(state_mgr.command_history.history) - 1
        state_mgr.command_history.redo_stack.clear()
    
    def _select_peripheral_in_tree(self, periph_name: str):
        """在树中选中指定外设（不改变展开状态）"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            return
        model = periph_tree.model()
        if not isinstance(model, DeviceTreeModel):
            return

        periph_tree.blockSignals(True)
        idx = model.find_index_by_path(periph_name)
        if idx.isValid():
            periph_tree.setCurrentIndex(idx)
        periph_tree.blockSignals(False)

    def select_peripheral(self, periph_name: str):
        """选中指定外设（公开方法）"""
        self._select_peripheral_in_tree(periph_name)
        self.state_manager.set_selection(peripheral=periph_name, element_type='peripheral')

    def select_register(self, periph_name: str, reg_name: str):
        """选中指定寄存器"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            return
        model = periph_tree.model()
        if not isinstance(model, DeviceTreeModel):
            return

        periph_tree.blockSignals(True)
        try:
            path = f"{periph_name}/{reg_name}"
            idx = model.find_index_by_path(path)
            if idx.isValid():
                # 确保父外设展开
                parent_idx = model.parent(idx)
                periph_tree.setExpanded(parent_idx, True)
                periph_tree.setCurrentIndex(idx)
        finally:
            periph_tree.blockSignals(False)

        self.state_manager.set_selection(peripheral=periph_name, register=reg_name, element_type='register')
        self.selection_changed.emit(periph_name, reg_name, None)

    def select_field(self, periph_name: str, reg_name: str, field_name: str):
        """选中指定位域"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            return
        model = periph_tree.model()
        if not isinstance(model, DeviceTreeModel):
            return

        periph_tree.blockSignals(True)
        try:
            path = f"{periph_name}/{reg_name}/{field_name}"
            idx = model.find_index_by_path(path)
            if idx.isValid():
                # 确保父寄存器和祖父外设展开
                reg_idx = model.parent(idx)
                periph_idx = model.parent(reg_idx)
                periph_tree.setExpanded(periph_idx, True)
                periph_tree.setExpanded(reg_idx, True)
                periph_tree.setCurrentIndex(idx)
        finally:
            periph_tree.blockSignals(False)

        self.state_manager.set_selection(peripheral=periph_name, register=reg_name, field=field_name, element_type='field')
        self.selection_changed.emit(periph_name, reg_name, field_name)

    def export_peripheral(self, periph_name: str) -> Dict[str, Any]:
        """导出外设数据为字典"""
        peripheral = self.state_manager.device_info.peripherals.get(periph_name)
        if not peripheral:
            return {}
        
        return peripheral.to_dict()
    
    def import_peripheral(self, data: Dict[str, Any]):
        """从字典导入外设数据"""
        try:
            peripheral = Peripheral(
                name=data.get('name', ''),
                base_address=data.get('base_address', '0x0'),
                description=data.get('description', ''),
                registers={}
            )
            
            # 导入寄存器
            registers_data = data.get('registers', {})
            for reg_name, reg_data in registers_data.items():
                register = Register(
                    name=reg_data.get('name', reg_name),
                    offset=reg_data.get('offset', '0x0'),
                    description=reg_data.get('description', ''),
                    size=reg_data.get('size', '0x20'),
                    access=reg_data.get('access'),
                    reset_value=reg_data.get('reset_value', '0x00000000'),
                    reset_mask=reg_data.get('reset_mask', '0xFFFFFFFF'),
                    fields={}
                )
                
                # 导入位域
                fields_data = reg_data.get('fields', {})
                for field_name, field_data in fields_data.items():
                    field = Field(
                        name=field_data.get('name', field_name),
                        description=field_data.get('description', ''),
                        display_name=field_data.get('display_name', ''),
                        bit_offset=field_data.get('bit_offset', 0),
                        bit_width=field_data.get('bit_width', 1),
                        access=field_data.get('access'),
                        reset_value=field_data.get('reset_value', '0x0')
                    )
                    register.fields[field.name] = field
                
                peripheral.registers[register.name] = register
            
            # 添加到状态管理器
            self.state_manager.add_peripheral(peripheral)
            self.peripheral_added.emit(peripheral.name)
            
        except Exception as e:
            QMessageBox.critical(
                self.layout_manager.main_window,
                t("dialog.import_error"),
                t("dialog.import_periph_error", error=str(e))
            )
    
    def copy_peripheral(self, periph_name: str):
        """复制外设数据到缓冲区"""
        try:
            # 导出外设数据
            data = self.export_peripheral(periph_name)
            if data:
                self.copied_peripheral_data = data
                # 显示状态消息
                main_window = self.layout_manager.main_window
                if hasattr(main_window, 'status_label'):
                    main_window.status_label.setText(t("status.periph_copied", name=periph_name))
                # 不再显示弹窗，避免干扰
                # QMessageBox.information(
                #     main_window,
                #     "复制成功",
                #     f"外设 '{periph_name}' 已复制到剪贴板"
                # )
        except Exception as e:
            QMessageBox.critical(
                self.layout_manager.main_window,
                t("msg.copy_error"),
                t("status.copy_periph_error", error=str(e))
            )
    
    def paste_peripheral(self):
        """从缓冲区粘贴外设"""
        if not self.copied_peripheral_data:
            QMessageBox.warning(
                self.layout_manager.main_window,
                "粘贴失败",
                "剪贴板中没有外设数据"
            )
            return
        
        try:
            # 生成新的外设名称（避免重复）
            original_name = self.copied_peripheral_data.get('name', '')
            base_name = original_name
            counter = 1
            new_name = base_name
            
            while new_name in self.state_manager.device_info.peripherals:
                new_name = f"{base_name}_{counter}"
                counter += 1
            
            # 修改数据中的名称
            data = self.copied_peripheral_data.copy()
            data['name'] = new_name
            
            # 导入外设
            self.import_peripheral(data)
            
            # 显示状态消息
            main_window = self.layout_manager.main_window
            if hasattr(main_window, 'status_label'):
                main_window.status_label.setText(t("status.periph_pasted", name=new_name))

        except Exception as e:
            QMessageBox.critical(
                self.layout_manager.main_window,
                t("msg.paste_error"),
                t("status.paste_periph_error", error=str(e))
            )

    def copy_register(self, periph_name: str, reg_name: str):
        """复制寄存器数据到缓冲区"""
        try:
            # 获取外设
            peripheral = self.state_manager.device_info.peripherals.get(periph_name)
            if not peripheral:
                QMessageBox.warning(
                    self.layout_manager.main_window,
                    "复制失败",
                    f"外设 '{periph_name}' 不存在"
                )
                return
            
            # 获取寄存器
            register = peripheral.registers.get(reg_name)
            if not register:
                QMessageBox.warning(
                    self.layout_manager.main_window,
                    "复制失败",
                    f"寄存器 '{reg_name}' 不存在"
                )
                return
            
            # 导出寄存器数据
            data = register.to_dict()
            if data:
                self.copied_register_data = data
                self.copied_register_peripheral = periph_name  # 保存所属外设名称
                # 显示状态消息（仅状态栏）
                main_window = self.layout_manager.main_window
                if hasattr(main_window, 'status_label'):
                    main_window.status_label.setText(t("status.reg_copied", name=reg_name))
                # 不显示弹窗
        except Exception as e:
            QMessageBox.critical(
                self.layout_manager.main_window,
                t("msg.copy_error"),
                t("status.copy_reg_error", error=str(e))
            )

    def paste_register(self, periph_name: str):
        """从缓冲区粘贴寄存器到指定外设"""
        if not self.copied_register_data:
            QMessageBox.warning(
                self.layout_manager.main_window,
                "粘贴失败",
                "剪贴板中没有寄存器数据"
            )
            return
        
        try:
            # 检查目标外设是否存在
            if periph_name not in self.state_manager.device_info.peripherals:
                QMessageBox.warning(
                    self.layout_manager.main_window,
                    "粘贴失败",
                    f"目标外设 '{periph_name}' 不存在"
                )
                return
            
            # 生成新的寄存器名称（避免重复）
            original_name = self.copied_register_data.get('name', '')
            base_name = original_name
            counter = 1
            new_name = base_name
            
            peripheral = self.state_manager.device_info.peripherals[periph_name]
            while new_name in peripheral.registers:
                new_name = f"{base_name}_{counter}"
                counter += 1
            
            # 修改数据中的名称
            data = self.copied_register_data.copy()
            data['name'] = new_name
            
            # 创建寄存器对象
            # 注意：Register 已经在文件顶部导入
            register = Register(
                name=data.get('name', ''),
                offset=data.get('offset', '0x0'),
                description=data.get('description', ''),
                display_name=data.get('display_name', ''),
                access=data.get('access'),
                reset_value=data.get('reset_value', '0x00000000'),
                size=data.get('size', '0x20'),
                fields={}
            )
            
            # 导入位域
            fields_data = data.get('fields', {})
            for field_name, field_data in fields_data.items():
                # 注意：Field 已经在文件顶部导入
                field = Field(
                    name=field_data.get('name', field_name),
                    description=field_data.get('description', ''),
                    display_name=field_data.get('display_name', ''),
                    bit_offset=field_data.get('bit_offset', 0),
                    bit_width=field_data.get('bit_width', 1),
                    access=field_data.get('access'),
                    reset_value=field_data.get('reset_value', '0x0')
                )
                register.fields[field.name] = field
            
            # 使用StateManager添加寄存器
            # 注意：add_register 内部通过 execute_command → _notify_state_change → on_state_changed → update_peripheral_tree
            self.state_manager.add_register(periph_name, register)
            
            # 显示状态消息
            main_window = self.layout_manager.main_window
            if hasattr(main_window, 'status_label'):
                main_window.status_label.setText(t("status.reg_pasted", name=new_name))

        except Exception as e:
            QMessageBox.critical(
                self.layout_manager.main_window,
                t("msg.paste_error"),
                t("status.paste_reg_error", error=str(e))
            )

    def copy_field(self, periph_name: str, reg_name: str, field_name: str):
        """复制位域数据到缓冲区"""
        try:
            # 获取外设
            peripheral = self.state_manager.device_info.peripherals.get(periph_name)
            if not peripheral:
                QMessageBox.warning(
                    self.layout_manager.main_window,
                    "复制失败",
                    f"外设 '{periph_name}' 不存在"
                )
                return
            
            # 获取寄存器
            register = peripheral.registers.get(reg_name)
            if not register:
                QMessageBox.warning(
                    self.layout_manager.main_window,
                    "复制失败",
                    f"寄存器 '{reg_name}' 不存在"
                )
                return
            
            # 获取位域
            field = register.fields.get(field_name)
            if not field:
                QMessageBox.warning(
                    self.layout_manager.main_window,
                    "复制失败",
                    f"位域 '{field_name}' 不存在"
                )
                return
            
            # 导出位域数据
            data = field.to_dict()
            if data:
                self.copied_field_data = data
                self.copied_field_peripheral = periph_name
                self.copied_field_register = reg_name
                # 显示状态消息（仅状态栏）
                main_window = self.layout_manager.main_window
                if hasattr(main_window, 'status_label'):
                    main_window.status_label.setText(t("status.field_copied", name=field_name))
                # 不显示弹窗
        except Exception as e:
            QMessageBox.critical(
                self.layout_manager.main_window,
                t("msg.copy_error"),
                t("status.copy_field_error", error=str(e))
            )

    def paste_field(self, periph_name: str, reg_name: str):
        """从缓冲区粘贴位域到指定寄存器"""
        if not self.copied_field_data:
            QMessageBox.warning(
                self.layout_manager.main_window,
                "粘贴失败",
                "剪贴板中没有位域数据"
            )
            return
        
        try:
            # 检查目标外设和寄存器是否存在
            if periph_name not in self.state_manager.device_info.peripherals:
                QMessageBox.warning(
                    self.layout_manager.main_window,
                    "粘贴失败",
                    f"目标外设 '{periph_name}' 不存在"
                )
                return
            
            peripheral = self.state_manager.device_info.peripherals[periph_name]
            if reg_name not in peripheral.registers:
                QMessageBox.warning(
                    self.layout_manager.main_window,
                    "粘贴失败",
                    f"目标寄存器 '{reg_name}' 不存在"
                )
                return
            
            # 生成新的位域名称（避免重复）
            original_name = self.copied_field_data.get('name', '')
            base_name = original_name
            counter = 1
            new_name = base_name
            
            register = peripheral.registers[reg_name]
            while new_name in register.fields:
                new_name = f"{base_name}_{counter}"
                counter += 1
            
            # 修改数据中的名称
            data = self.copied_field_data.copy()
            data['name'] = new_name
            
            # 创建位域对象
            # 注意：Field 已经在文件顶部导入
            field = Field(
                name=data.get('name', ''),
                description=data.get('description', ''),
                display_name=data.get('display_name', ''),
                bit_offset=data.get('bit_offset', 0),
                bit_width=data.get('bit_width', 1),
                access=data.get('access'),
                reset_value=data.get('reset_value', '0x0')
            )
            
            # 使用StateManager添加位域
            # 注意：add_field 内部通过 execute_command → _notify_state_change → on_state_changed → update_peripheral_tree
            self.state_manager.add_field(periph_name, reg_name, field)
            
            # 显示状态消息
            main_window = self.layout_manager.main_window
            if hasattr(main_window, 'status_label'):
                main_window.status_label.setText(t("status.field_pasted", name=new_name))

        except Exception as e:
            QMessageBox.critical(
                self.layout_manager.main_window,
                t("msg.paste_error"),
                t("status.paste_field_error", error=str(e))
            )