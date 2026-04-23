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
from PyQt6.QtCore import Qt, pyqtSignal, QObject

from svd_tool.core.data_model import Peripheral, Register, Field
from .state_manager import StateManager
from svd_tool.core.constants import NODE_TYPES
from ...i18n.i18n import t


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

        # 名称→QTreeWidgetItem 缓存（避免 select_* 方法线性遍历整棵树）
        self._tree_item_cache = {}  # path -> QTreeWidgetItem

        # 懒加载状态追踪
        self._populated_peripherals = set()  # 已加载寄存器的外设名
        self._populated_registers = set()    # 已加载位域的寄存器路径 "periph/reg"
        self._dummy_child_key = "__dummy__"  # 占位子项标识
        
        # 连接UI信号
        self.connect_ui_signals()
    
    def connect_ui_signals(self):
        """连接UI信号"""
        # 获取UI控件
        # 注意：所有按钮（添加、编辑、删除）都在 main_window_refactored.py 的 setup_signals() 中连接
        # 这里只连接树控件的信号
        periph_tree = self.layout_manager.get_widget('periph_tree')
        
        if periph_tree:
            periph_tree.itemSelectionChanged.connect(self.on_periph_tree_selection_changed)
            periph_tree.itemDoubleClicked.connect(self.on_periph_tree_double_clicked)
            periph_tree.itemExpanded.connect(self._on_item_expanded)
    
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
        
        selected_items = periph_tree.selectedItems()
        
        if not selected_items:
            # 清除选择
            self.state_manager.set_selection()
            self.selection_changed.emit(None, None, None)
            return
        
        item = selected_items[0]
        item_type = item.data(0, Qt.ItemDataRole.UserRole)
        
        if item_type == 'peripheral':
            periph_name = item.text(0)
            self.state_manager.set_selection(peripheral=periph_name, element_type='peripheral')
            self.selection_changed.emit(periph_name, None, None)
        elif item_type == 'register':
            # 寄存器被选中，需要获取父外设
            periph_name = item.parent().text(0) if item.parent() else None
            reg_name = item.text(0)
            self.state_manager.set_selection(peripheral=periph_name, register=reg_name, element_type='register')
            self.selection_changed.emit(periph_name, reg_name, None)
        elif item_type == 'field':
            # 位域被选中，需要获取父外设和寄存器
            reg_item = item.parent() if item.parent() else None
            periph_item = reg_item.parent() if reg_item else None
            periph_name = periph_item.text(0) if periph_item else None
            reg_name = reg_item.text(0) if reg_item else None
            field_name = item.text(0)
            self.state_manager.set_selection(peripheral=periph_name, register=reg_name, field=field_name, element_type='field')
            self.selection_changed.emit(periph_name, reg_name, field_name)
    
    def on_periph_tree_double_clicked(self, item, column):
        """外设树双击事件"""
        item_type = item.data(0, Qt.ItemDataRole.UserRole)
        item_name = item.text(0)
        
        if item_type == 'peripheral':
            # 双击外设：编辑外设
            self.edit_peripheral(item_name)
        elif item_type == 'register':
            # 双击寄存器：编辑寄存器
            # 需要获取外设名称（父节点）
            parent = item.parent()
            if parent:
                periph_name = parent.text(0)
                self.state_manager.set_selection(peripheral=periph_name, register=item_name)
                # 调用主窗口的编辑寄存器方法
                if hasattr(self.layout_manager, 'main_window'):
                    self.layout_manager.main_window.edit_register(item_name)
        elif item_type == 'field':
            # 双击位域：编辑位域
            # 需要获取外设和寄存器名称（父节点和祖父节点）
            register_item = item.parent()
            if register_item:
                periph_item = register_item.parent()
                if periph_item:
                    periph_name = periph_item.text(0)
                    reg_name = register_item.text(0)
                    self.state_manager.set_selection(peripheral=periph_name, register=reg_name, field=item_name)
                    # 调用主窗口的编辑位域方法
                    if hasattr(self.layout_manager, 'main_window'):
                        self.layout_manager.main_window.edit_field(item_name)
    
    def is_compact_tree(self) -> bool:
        """检查是否为紧凑模式（只显示到寄存器级别）"""
        compact_tree_cb = self.layout_manager.get_widget('compact_tree_cb')
        return compact_tree_cb is not None and compact_tree_cb.isChecked()
    
    def update_peripheral_tree(self, preserve_expanded=True):
        """更新外设树（懒加载模式：只创建外设级别节点）

        Args:
            preserve_expanded: 是否保留当前展开状态。
                True: 正常编辑操作，保留展开状态。
                False: 文档切换时使用，不保留旧文档的展开状态。
        """
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            return

        compact = self.is_compact_tree()

        # 重置懒加载状态
        self._populated_peripherals.clear()
        self._populated_registers.clear()

        periph_tree.blockSignals(True)
        periph_tree.setUpdatesEnabled(False)

        try:
            expanded_paths = self._get_expanded_items(periph_tree) if preserve_expanded else []

            periph_tree.clear()
            periph_tree.setHeaderLabels([t("label.name_column"), t("label.offset_column"), t("label.description_column"), t("label.access_column"), t("label.reset_value_column")])

            item_map = {}

            # 只创建外设级别节点 + 占位子项
            for periph_name, peripheral in self.state_manager.device_info.peripherals.items():
                periph_item = QTreeWidgetItem(periph_tree)
                periph_item.setText(0, periph_name)
                periph_item.setText(1, peripheral.base_address)
                periph_item.setText(2, peripheral.description)
                periph_item.setData(0, Qt.ItemDataRole.UserRole, 'peripheral')
                periph_item.setData(0, Qt.ItemDataRole.UserRole + 1, periph_name)

                item_map[periph_name] = periph_item

                # 添加占位子项（显示展开箭头）
                dummy = QTreeWidgetItem(periph_item)
                dummy.setText(0, "")
                dummy.setData(0, Qt.ItemDataRole.UserRole, self._dummy_child_key)

                # 如果之前展开过，立即加载子节点并恢复展开状态
                if periph_name in expanded_paths:
                    self._populate_peripheral_children(periph_item, periph_name, compact)
                    self._populated_peripherals.add(periph_name)
                    periph_item.setExpanded(True)

                    # 恢复之前展开的寄存器
                    for path in expanded_paths:
                        if path.startswith(periph_name + "/"):
                            reg_name = path.split("/")[1]
                            for j in range(periph_item.childCount()):
                                reg_child = periph_item.child(j)
                                if reg_child.text(0) == reg_name:
                                    if not compact:
                                        reg_path = f"{periph_name}/{reg_name}"
                                        self._populate_register_children(reg_child, periph_name, reg_name)
                                        self._populated_registers.add(reg_path)
                                    reg_child.setExpanded(True)
                                    break

            self._tree_item_cache = item_map
        finally:
            periph_tree.setUpdatesEnabled(True)
            periph_tree.blockSignals(False)
    
    def _get_expanded_items(self, tree: QTreeWidget):
        """获取当前展开的项目名称（包括外设和寄存器）
        
        注意：Qt中折叠父节点不会改变子节点的isExpanded状态，
        所以只遍历已展开节点的子节点，避免捕获隐藏的展开状态。
        """
        expanded = []
        
        def traverse(item, path=""):
            if not item:
                return
            
            # 构建项目路径（例如："外设A/寄存器B"）
            item_name = item.text(0)
            current_path = f"{path}/{item_name}" if path else item_name
            
            if item.isExpanded():
                expanded.append(current_path)
                
                # 只有当前项展开时才遍历子项
                # （折叠的父节点下，子节点的isExpanded状态不可靠）
                for i in range(item.childCount()):
                    child = item.child(i)
                    traverse(child, current_path)
        
        # 遍历顶级项目（外设）
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            traverse(item)
        
        return expanded

    def _on_item_expanded(self, item):
        """懒加载：展开节点时加载子项"""
        item_type = item.data(0, Qt.ItemDataRole.UserRole)
        compact = self.is_compact_tree()

        if item_type == 'peripheral':
            periph_name = item.data(0, Qt.ItemDataRole.UserRole + 1)
            if periph_name and periph_name not in self._populated_peripherals:
                self._populate_peripheral_children(item, periph_name, compact)
                self._populated_peripherals.add(periph_name)

        elif item_type == 'register' and not compact:
            reg_name = item.data(0, Qt.ItemDataRole.UserRole + 1)
            periph_item = item.parent()
            if periph_item:
                periph_name = periph_item.data(0, Qt.ItemDataRole.UserRole + 1)
                if periph_name:
                    reg_path = f"{periph_name}/{reg_name}"
                    if reg_path not in self._populated_registers:
                        self._populate_register_children(item, periph_name, reg_name)
                        self._populated_registers.add(reg_path)

    def _populate_peripheral_children(self, periph_item, periph_name, compact=None):
        """懒加载：填充外设的寄存器子节点"""
        peripheral = self.state_manager.device_info.peripherals.get(periph_name)
        if not peripheral:
            return

        # 移除占位子项
        to_remove = []
        for i in range(periph_item.childCount()):
            child = periph_item.child(i)
            if child.data(0, Qt.ItemDataRole.UserRole) == self._dummy_child_key:
                to_remove.append(child)
        for child in to_remove:
            periph_item.removeChild(child)

        if compact is None:
            compact = self.is_compact_tree()

        for reg_name, register in peripheral.registers.items():
            reg_item = QTreeWidgetItem(periph_item)
            reg_item.setText(0, reg_name)
            reg_item.setText(1, register.offset)
            reg_item.setText(2, register.description)
            reg_item.setText(3, register.access or "")
            reg_item.setText(4, register.reset_value)
            reg_item.setData(0, Qt.ItemDataRole.UserRole, 'register')
            reg_item.setData(0, Qt.ItemDataRole.UserRole + 1, reg_name)

            reg_path = f"{periph_name}/{reg_name}"
            self._tree_item_cache[reg_path] = reg_item

            if not compact:
                # 添加占位子项显示展开箭头
                dummy = QTreeWidgetItem(reg_item)
                dummy.setText(0, "")
                dummy.setData(0, Qt.ItemDataRole.UserRole, self._dummy_child_key)

    def _populate_register_children(self, reg_item, periph_name, reg_name):
        """懒加载：填充寄存器的位域子节点"""
        peripheral = self.state_manager.device_info.peripherals.get(periph_name)
        if not peripheral:
            return
        register = peripheral.registers.get(reg_name)
        if not register:
            return

        # 移除占位子项
        to_remove = []
        for i in range(reg_item.childCount()):
            child = reg_item.child(i)
            if child.data(0, Qt.ItemDataRole.UserRole) == self._dummy_child_key:
                to_remove.append(child)
        for child in to_remove:
            reg_item.removeChild(child)

        for field_name, field in register.fields.items():
            field_item = QTreeWidgetItem(reg_item)
            field_item.setText(0, field_name)
            field_item.setText(1, f"[{field.bit_offset}:{field.bit_offset + field.bit_width - 1}]")
            field_item.setText(2, field.description or "")
            field_item.setText(3, field.access or "")
            field_item.setText(4, field.reset_value)
            field_item.setData(0, Qt.ItemDataRole.UserRole, 'field')
            field_item.setData(0, Qt.ItemDataRole.UserRole + 1, field_name)

            field_path = f"{periph_name}/{reg_name}/{field_name}"
            self._tree_item_cache[field_path] = field_item

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
        # 获取树控件
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            return
        
        # 获取点击的项目
        item = periph_tree.itemAt(pos)
        if not item:
            return
        
        # 获取TreeManager（需要从主窗口获取）
        main_window = self.layout_manager.main_window
        if not hasattr(main_window, 'tree_manager'):
            return
        
        # 创建右键菜单
        menu = main_window.tree_manager.create_context_menu(item, parent=periph_tree)
        
        # 执行菜单动作
        action = menu.exec(periph_tree.mapToGlobal(pos))
        if action:
            action_data = action.data()
            item_type = main_window.tree_manager.get_item_type(item)
            item_name = main_window.tree_manager.get_item_name(item)
            
            # 根据动作类型执行相应操作
            if action_data == "edit_peripheral":
                self.edit_peripheral(item_name)
            elif action_data == "delete_peripheral":
                # 支持多选批量删除
                selected = periph_tree.selectedItems()
                if len(selected) > 1:
                    main_window._batch_delete_selected(selected)
                else:
                    self.delete_selected_peripheral()
            elif action_data == "add_register":
                # 调用主窗口的添加寄存器功能
                if hasattr(main_window, 'add_register'):
                    # 设置当前选择为此外设
                    self.state_manager.set_selection(peripheral=item_name)
                    main_window.add_register()
            elif action_data == "edit_register":
                # 调用主窗口的编辑寄存器功能
                if hasattr(main_window, 'edit_register'):
                    main_window.edit_register(item_name)
            elif action_data == "delete_register":
                # 支持多选批量删除
                selected = periph_tree.selectedItems()
                if len(selected) > 1:
                    main_window._batch_delete_selected(selected)
                elif hasattr(main_window, 'delete_register'):
                    main_window.delete_register(item_name)
            elif action_data == "add_field":
                # 调用主窗口的添加位域功能
                if hasattr(main_window, 'add_field'):
                    # 需要获取寄存器名称和外设名称
                    reg_name = item_name
                    # 获取父外设名称
                    parent_item = item.parent()
                    if parent_item:
                        periph_name = main_window.tree_manager.get_item_name(parent_item)
                        # 设置当前选择
                        self.state_manager.set_selection(
                            peripheral=periph_name,
                            register=reg_name
                        )
                        main_window.add_field()
            elif action_data == "edit_field":
                # 调用主窗口的编辑位域功能
                if hasattr(main_window, 'edit_field'):
                    main_window.edit_field(item_name)
            elif action_data == "delete_field":
                # 支持多选批量删除
                selected = periph_tree.selectedItems()
                if len(selected) > 1:
                    main_window._batch_delete_selected(selected)
                elif hasattr(main_window, 'delete_field'):
                    main_window.delete_field(item_name)
            elif action_data == "sort_alphabetically":
                # 调用主窗口的排序功能
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
                # 复制外设数据
                self.copy_peripheral(item_name)
            elif action_data == "paste_peripheral":
                # 粘贴外设数据
                self.paste_peripheral()
            elif action_data == "copy_register":
                # 复制寄存器数据，需要获取外设名称
                if item_type == NODE_TYPES["REGISTER"]:
                    parent_item = item.parent()
                    if parent_item:
                        periph_name = main_window.tree_manager.get_item_name(parent_item)
                        self.copy_register(periph_name, item_name)
            elif action_data == "paste_register":
                # 粘贴寄存器数据，需要获取外设名称
                if item_type == NODE_TYPES["REGISTER"]:
                    parent_item = item.parent()
                    if parent_item:
                        periph_name = main_window.tree_manager.get_item_name(parent_item)
                        self.paste_register(periph_name)
                elif item_type == NODE_TYPES["PERIPHERAL"]:
                    # 在所选外设中粘贴寄存器
                    self.paste_register(item_name)
            elif action_data == "copy_field":
                # 复制位域数据，需要获取外设名称和寄存器名称
                if item_type == NODE_TYPES["FIELD"]:
                    reg_item = item.parent()
                    if reg_item:
                        periph_item = reg_item.parent()
                        if periph_item:
                            periph_name = main_window.tree_manager.get_item_name(periph_item)
                            reg_name = main_window.tree_manager.get_item_name(reg_item)
                            self.copy_field(periph_name, reg_name, item_name)
            elif action_data == "paste_field":
                # 粘贴位域数据，需要获取外设名称和寄存器名称
                if item_type == NODE_TYPES["FIELD"]:
                    reg_item = item.parent()
                    if reg_item:
                        periph_item = reg_item.parent()
                        if periph_item:
                            periph_name = main_window.tree_manager.get_item_name(periph_item)
                            reg_name = main_window.tree_manager.get_item_name(reg_item)
                            self.paste_field(periph_name, reg_name)
                elif item_type == NODE_TYPES["REGISTER"]:
                    # 在所选寄存器中粘贴位域
                    periph_item = item.parent()
                    if periph_item:
                        periph_name = main_window.tree_manager.get_item_name(periph_item)
                        reg_name = item_name
                        self.paste_field(periph_name, reg_name)
            elif action_data == "move_up":
                # 调用移动功能
                self.move_selected_peripheral_up()
            elif action_data == "move_down":
                # 调用移动功能
                self.move_selected_peripheral_down()
    
    def move_selected_peripheral_up(self):
        """上移选中的外设"""
        # 获取树控件
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            return
        
        # 获取选中的项目
        selected_items = periph_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(
                self.layout_manager.main_window,
                t("dialog.op_hint"),
                t("msg.select_peripheral_first")
            )
            return

        item = selected_items[0]

        # 获取TreeManager（需要从主窗口获取）
        main_window = self.layout_manager.main_window
        if not hasattr(main_window, 'tree_manager'):
            return

        # 检查项目类型
        item_type = main_window.tree_manager.get_item_type(item)
        if item_type != "peripheral":
            QMessageBox.warning(
                self.layout_manager.main_window,
                t("dialog.op_limit"),
                t("warn.periph_only_move_up")
            )
            return
        
        # 获取外设名称
        periph_name = main_window.tree_manager.get_item_name(item)
        
        # 创建移动命令
        from ...core.command_history import Command
        
        # 保存当前外设顺序的快照
        periph_names = list(self.state_manager.device_info.peripherals.keys())
        current_index = periph_names.index(periph_name)
        
        # 创建执行函数
        def execute_move_up():
            return self.state_manager.move_peripheral_up(periph_name)
        
        # 创建撤销函数（下移回来）
        def undo_move_up():
            # 实际上，撤销上移就是下移
            # 但我们需要更精确的撤销：恢复到原来的位置
            # 简单实现：直接调用下移
            return self.state_manager.move_peripheral_down(periph_name)
        
        # 创建命令对象
        command = Command(
            execute=execute_move_up,
            undo=undo_move_up,
            description=t("cmd.move_periph_up", name=periph_name)
        )

        # 通过StateManager执行命令（支持撤销）
        # 注意：execute_command 内部会触发 _notify_state_change -> on_state_changed -> update_peripheral_tree
        # 所以这里不需要再次调用 update_peripheral_tree()
        moved = self.state_manager.execute_command(command)

        if moved:
            # 重新选中该项目（延迟执行，等树重建完成）
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(50, lambda: self._select_peripheral_in_tree(periph_name))
            # 显示状态消息
            if hasattr(main_window, 'status_label'):
                main_window.status_label.setText(t("status.periph_moved_up", name=periph_name))
        else:
            QMessageBox.information(
                self.layout_manager.main_window,
                t("dialog.op_hint"),
                t("warn.periph_at_top")
            )
    
    def move_selected_peripheral_down(self):
        """下移选中的外设"""
        # 获取树控件
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            return
        
        # 获取选中的项目
        selected_items = periph_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(
                self.layout_manager.main_window,
                t("dialog.op_hint"),
                t("msg.select_peripheral_first")
            )
            return

        item = selected_items[0]

        # 获取TreeManager（需要从主窗口获取）
        main_window = self.layout_manager.main_window
        if not hasattr(main_window, 'tree_manager'):
            return

        # 检查项目类型
        item_type = main_window.tree_manager.get_item_type(item)
        if item_type != "peripheral":
            QMessageBox.warning(
                self.layout_manager.main_window,
                t("dialog.op_limit"),
                t("warn.periph_only_move_down")
            )
            return
        
        # 获取外设名称
        periph_name = main_window.tree_manager.get_item_name(item)
        
        # 创建移动命令
        from ...core.command_history import Command
        
        # 保存当前外设顺序的快照
        periph_names = list(self.state_manager.device_info.peripherals.keys())
        current_index = periph_names.index(periph_name)
        
        # 创建执行函数
        def execute_move_down():
            return self.state_manager.move_peripheral_down(periph_name)
        
        # 创建撤销函数（上移回来）
        def undo_move_down():
            # 撤销下移就是上移
            return self.state_manager.move_peripheral_up(periph_name)
        
        # 创建命令对象
        command = Command(
            execute=execute_move_down,
            undo=undo_move_down,
            description=t("cmd.move_periph_down", name=periph_name)
        )

        # 通过StateManager执行命令（支持撤销）
        # 注意：execute_command 内部会触发 _notify_state_change -> on_state_changed -> update_peripheral_tree
        # 所以这里不需要再次调用 update_peripheral_tree()
        moved = self.state_manager.execute_command(command)

        if moved:
            # 重新选中该项目（延迟执行，等树重建完成）
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(50, lambda: self._select_peripheral_in_tree(periph_name))
            # 显示状态消息
            if hasattr(main_window, 'status_label'):
                main_window.status_label.setText(t("status.periph_moved_down", name=periph_name))
        else:
            QMessageBox.information(
                self.layout_manager.main_window,
                t("dialog.op_hint"),
                t("warn.periph_at_bottom")
            )
    
    def _select_peripheral_in_tree(self, periph_name: str):
        """在树中选中指定外设（不改变展开状态）— 使用缓存 O(1) 查找"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            return
        
        # 阻塞信号，避免选中触发不必要的状态变更
        periph_tree.blockSignals(True)
        
        # 优先使用缓存查找（O(1)），回退到线性遍历（O(n)）
        item = self._tree_item_cache.get(periph_name)
        if item:
            periph_tree.setCurrentItem(item)
        else:
            # 缓存未命中，遍历树查找
            for i in range(periph_tree.topLevelItemCount()):
                tree_item = periph_tree.topLevelItem(i)
                if tree_item.text(0) == periph_name:
                    periph_tree.setCurrentItem(tree_item)
                    break
        
        periph_tree.blockSignals(False)
    
    def select_peripheral(self, periph_name: str):
        """选中指定外设（公开方法）"""
        self._select_peripheral_in_tree(periph_name)
        # 更新状态管理器的当前选中
        self.state_manager.set_selection(peripheral=periph_name, element_type='peripheral')
    
    def select_register(self, periph_name: str, reg_name: str):
        """选中指定寄存器 — 使用缓存 O(1) 查找，支持懒加载"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            return

        # 确保父外设已懒加载寄存器子节点
        if periph_name not in self._populated_peripherals:
            periph_item = self._tree_item_cache.get(periph_name)
            if periph_item:
                self._populate_peripheral_children(periph_item, periph_name)
                self._populated_peripherals.add(periph_name)

        # 阻塞信号，避免 setCurrentItem 触发 itemSelectionChanged 导致双重通知
        periph_tree.blockSignals(True)

        try:
            # 使用缓存查找寄存器节点（O(1)）
            reg_path = f"{periph_name}/{reg_name}"
            reg_item = self._tree_item_cache.get(reg_path)
            if reg_item:
                # 确保父外设展开
                periph_item = reg_item.parent()
                if periph_item:
                    periph_item.setExpanded(True)
                reg_item.setExpanded(True)
                periph_tree.setCurrentItem(reg_item)
            else:
                # 缓存未命中，回退到线性遍历
                for i in range(periph_tree.topLevelItemCount()):
                    periph_item = periph_tree.topLevelItem(i)
                    if periph_item.text(0) == periph_name:
                        periph_item.setExpanded(True)
                        for j in range(periph_item.childCount()):
                            tree_reg_item = periph_item.child(j)
                            if tree_reg_item.text(0) == reg_name:
                                tree_reg_item.setExpanded(True)
                                periph_tree.setCurrentItem(tree_reg_item)
                                break
                        break
        finally:
            periph_tree.blockSignals(False)
        
        # 手动更新状态管理器并发射信号（只通知一次）
        self.state_manager.set_selection(peripheral=periph_name, register=reg_name, element_type='register')
        self.selection_changed.emit(periph_name, reg_name, None)
    
    def select_field(self, periph_name: str, reg_name: str, field_name: str):
        """选中指定位域 — 使用缓存 O(1) 查找，支持懒加载"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            return

        # 确保父外设已懒加载寄存器子节点
        if periph_name not in self._populated_peripherals:
            periph_item = self._tree_item_cache.get(periph_name)
            if periph_item:
                self._populate_peripheral_children(periph_item, periph_name)
                self._populated_peripherals.add(periph_name)

        # 确保寄存器已懒加载位域子节点
        reg_path = f"{periph_name}/{reg_name}"
        if reg_path not in self._populated_registers:
            reg_item = self._tree_item_cache.get(reg_path)
            if reg_item:
                self._populate_register_children(reg_item, periph_name, reg_name)
                self._populated_registers.add(reg_path)

        # 阻塞信号，避免 setCurrentItem 触发 itemSelectionChanged 导致双重通知
        periph_tree.blockSignals(True)
        
        try:
            # 使用缓存查找位域节点（O(1)）
            field_path = f"{periph_name}/{reg_name}/{field_name}"
            field_item = self._tree_item_cache.get(field_path)
            if field_item:
                # 确保父寄存器和祖父外设展开
                reg_item = field_item.parent()
                if reg_item:
                    reg_item.setExpanded(True)
                    periph_item = reg_item.parent()
                    if periph_item:
                        periph_item.setExpanded(True)
                periph_tree.setCurrentItem(field_item)
            else:
                # 缓存未命中，回退到线性遍历
                for i in range(periph_tree.topLevelItemCount()):
                    periph_item = periph_tree.topLevelItem(i)
                    if periph_item.text(0) == periph_name:
                        periph_item.setExpanded(True)
                        for j in range(periph_item.childCount()):
                            tree_reg_item = periph_item.child(j)
                            if tree_reg_item.text(0) == reg_name:
                                tree_reg_item.setExpanded(True)
                                for k in range(tree_reg_item.childCount()):
                                    tree_field_item = tree_reg_item.child(k)
                                    if tree_field_item.text(0) == field_name:
                                        periph_tree.setCurrentItem(tree_field_item)
                                        break
                                break
                        break
        finally:
            periph_tree.blockSignals(False)
        
        # 手动更新状态管理器并发射信号（只通知一次）
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