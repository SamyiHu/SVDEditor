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
    
    def on_state_changed(self):
        """状态变更时的处理"""
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
            self.state_manager.set_selection(peripheral=periph_name)
            self.selection_changed.emit(periph_name, None, None)
        elif item_type == 'register':
            # 寄存器被选中，需要获取父外设
            periph_name = item.parent().text(0) if item.parent() else None
            reg_name = item.text(0)
            self.state_manager.set_selection(peripheral=periph_name, register=reg_name)
            self.selection_changed.emit(periph_name, reg_name, None)
        elif item_type == 'field':
            # 位域被选中，需要获取父外设和寄存器
            reg_item = item.parent() if item.parent() else None
            periph_item = reg_item.parent() if reg_item else None
            periph_name = periph_item.text(0) if periph_item else None
            reg_name = reg_item.text(0) if reg_item else None
            field_name = item.text(0)
            self.state_manager.set_selection(peripheral=periph_name, register=reg_name, field=field_name)
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
    
    def update_peripheral_tree(self):
        """更新外设树"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            return
        
        # 保存当前展开状态
        expanded_paths = self._get_expanded_items(periph_tree)
        
        periph_tree.clear()
        
        # 创建项目映射，便于后续查找
        item_map = {}  # 路径 -> 项目
        
        # 添加外设
        for periph_name, peripheral in self.state_manager.device_info.peripherals.items():
            periph_item = QTreeWidgetItem(periph_tree)
            periph_item.setText(0, periph_name)
            periph_item.setText(1, peripheral.base_address)
            periph_item.setText(2, peripheral.description)
            periph_item.setData(0, Qt.ItemDataRole.UserRole, 'peripheral')
            periph_item.setData(0, Qt.ItemDataRole.UserRole + 1, periph_name)  # 设置名称数据
            
            # 保存到映射
            item_map[periph_name] = periph_item
            
            # 添加寄存器子项
            for reg_name, register in peripheral.registers.items():
                reg_item = QTreeWidgetItem(periph_item)
                reg_item.setText(0, reg_name)
                reg_item.setText(1, register.offset)
                reg_item.setText(2, register.description)  # 改为描述
                reg_item.setText(3, register.access or "")
                reg_item.setText(4, register.reset_value)
                reg_item.setData(0, Qt.ItemDataRole.UserRole, 'register')
                reg_item.setData(0, Qt.ItemDataRole.UserRole + 1, reg_name)  # 设置名称数据
                
                # 保存到映射
                reg_path = f"{periph_name}/{reg_name}"
                item_map[reg_path] = reg_item
                
                # 添加位域子项
                for field_name, field in register.fields.items():
                    field_item = QTreeWidgetItem(reg_item)
                    field_item.setText(0, field_name)
                    field_item.setText(1, str(field.bit_offset))
                    field_item.setText(2, str(field.bit_width))
                    field_item.setText(3, field.access or "")
                    field_item.setText(4, field.reset_value)
                    field_item.setText(5, field.description)
                    field_item.setData(0, Qt.ItemDataRole.UserRole, 'field')
                    field_item.setData(0, Qt.ItemDataRole.UserRole + 1, field_name)  # 设置名称数据
        
        # 恢复展开状态
        for path in expanded_paths:
            if path in item_map:
                item = item_map[path]
                item.setExpanded(True)
                
                # 如果这是一个寄存器路径，还需要确保其父外设也是展开的
                if '/' in path:
                    periph_name = path.split('/')[0]
                    if periph_name in item_map:
                        item_map[periph_name].setExpanded(True)
    
    def _get_expanded_items(self, tree: QTreeWidget):
        """获取当前展开的项目名称（包括外设和寄存器）"""
        expanded = []
        
        def traverse(item, path=""):
            if not item:
                return
            
            # 构建项目路径（例如："外设A/寄存器B"）
            item_name = item.text(0)
            current_path = f"{path}/{item_name}" if path else item_name
            
            if item.isExpanded():
                expanded.append(current_path)
            
            # 递归遍历子项
            for i in range(item.childCount()):
                child = item.child(i)
                traverse(child, current_path)
        
        # 遍历顶级项目（外设）
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            traverse(item)
        
        return expanded
    
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
                    "警告",
                    f"外设 '{peripheral.name}' 已存在！"
                )
                return
            
            # 添加到状态管理器
            self.state_manager.add_peripheral(peripheral)
            self.peripheral_added.emit(peripheral.name)
            
            # 更新UI
            self.update_peripheral_tree()
            
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
                        "警告",
                        f"外设 '{updated_peripheral.name}' 已存在！"
                    )
                    return
                
                # 删除旧的外设，添加新的
                self.state_manager.delete_peripheral(periph_name)
                self.state_manager.add_peripheral(updated_peripheral)
                
                # 更新选择
                self.state_manager.set_selection(peripheral=updated_peripheral.name)
            else:
                # 直接更新
                self.state_manager.update_peripheral(periph_name, updated_peripheral)
            
            self.peripheral_updated.emit(updated_peripheral.name)
            
            # 更新UI
            self.update_peripheral_tree()
    
    def delete_selected_peripheral(self):
        """删除选中的外设"""
        selection = self.state_manager.get_selection()
        periph_name = selection['peripheral']
        
        if not periph_name:
            return
        
        # 确认对话框
        reply = QMessageBox.question(
            self.layout_manager.main_window,
            "确认删除",
            f"确定要删除外设 '{periph_name}' 及其所有寄存器和位域吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.state_manager.delete_peripheral(periph_name)
            self.peripheral_deleted.emit(periph_name)
            
            # 更新UI
            self.update_peripheral_tree()
    
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
            errors.append(f"外设 '{periph_name}' 不存在")
            return errors
        
        # 检查基本字段
        if not peripheral.name:
            errors.append("外设名称不能为空")
        
        if not peripheral.base_address:
            errors.append("外设基地址不能为空")
        
        # 检查寄存器
        for reg_name, register in peripheral.registers.items():
            if not reg_name:
                errors.append(f"外设 '{periph_name}' 中的寄存器名称不能为空")
            
            # 检查位域
            for field_name, field in register.fields.items():
                if not field_name:
                    errors.append(f"寄存器 '{reg_name}' 中的位域名称不能为空")
        
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
        menu = main_window.tree_manager.create_context_menu(item)
        
        # 执行菜单动作
        action = menu.exec(periph_tree.mapToGlobal(pos))
        if action:
            action_text = action.text()
            item_type = main_window.tree_manager.get_item_type(item)
            item_name = main_window.tree_manager.get_item_name(item)
            
            # 根据动作类型执行相应操作
            if action_text == "编辑外设":
                self.edit_peripheral(item_name)
            elif action_text == "删除外设":
                self.delete_selected_peripheral()
            elif action_text == "添加寄存器":
                # 调用主窗口的添加寄存器功能
                if hasattr(main_window, 'add_register'):
                    # 设置当前选择为此外设
                    self.state_manager.set_selection(peripheral=item_name)
                    main_window.add_register()
            elif action_text == "编辑寄存器":
                # 调用主窗口的编辑寄存器功能
                if hasattr(main_window, 'edit_register'):
                    main_window.edit_register(item_name)
            elif action_text == "删除寄存器":
                # 调用主窗口的删除寄存器功能
                if hasattr(main_window, 'delete_register'):
                    main_window.delete_register(item_name)
            elif action_text == "添加位域":
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
            elif action_text == "编辑位域":
                # 调用主窗口的编辑位域功能
                if hasattr(main_window, 'edit_field'):
                    main_window.edit_field(item_name)
            elif action_text == "删除位域":
                # 调用主窗口的删除位域功能
                if hasattr(main_window, 'delete_field'):
                    main_window.delete_field(item_name)
            elif action_text == "按字母排序":
                # 调用主窗口的排序功能
                if hasattr(main_window, 'sort_items_alphabetically'):
                    main_window.sort_items_alphabetically()
            elif action_text == "复制外设":
                # 复制外设数据
                self.copy_peripheral(item_name)
            elif action_text == "粘贴外设":
                # 粘贴外设数据
                self.paste_peripheral()
            elif action_text == "复制寄存器":
                # 复制寄存器数据，需要获取外设名称
                if item_type == NODE_TYPES["REGISTER"]:
                    parent_item = item.parent()
                    if parent_item:
                        periph_name = main_window.tree_manager.get_item_name(parent_item)
                        self.copy_register(periph_name, item_name)
            elif action_text == "粘贴寄存器":
                # 粘贴寄存器数据，需要获取外设名称
                if item_type == NODE_TYPES["REGISTER"]:
                    parent_item = item.parent()
                    if parent_item:
                        periph_name = main_window.tree_manager.get_item_name(parent_item)
                        self.paste_register(periph_name)
                elif item_type == NODE_TYPES["PERIPHERAL"]:
                    # 在所选外设中粘贴寄存器
                    self.paste_register(item_name)
            elif action_text == "复制位域":
                # 复制位域数据，需要获取外设名称和寄存器名称
                if item_type == NODE_TYPES["FIELD"]:
                    reg_item = item.parent()
                    if reg_item:
                        periph_item = reg_item.parent()
                        if periph_item:
                            periph_name = main_window.tree_manager.get_item_name(periph_item)
                            reg_name = main_window.tree_manager.get_item_name(reg_item)
                            self.copy_field(periph_name, reg_name, item_name)
            elif action_text == "粘贴位域":
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
            elif action_text == "上移":
                # 调用移动功能
                self.move_selected_peripheral_up()
            elif action_text == "下移":
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
                "操作提示",
                "请先选中一个外设"
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
                "操作限制",
                "只支持外设的上移操作"
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
            description=f"上移外设: {periph_name}"
        )
        
        # 通过StateManager执行命令（支持撤销）
        moved = self.state_manager.execute_command(command)
        
        if moved:
            # 更新UI
            self.update_peripheral_tree()
            # 重新选中该项目
            self._select_peripheral_in_tree(periph_name)
            # 显示状态消息
            if hasattr(main_window, 'status_label'):
                main_window.status_label.setText(f"已上移外设: {periph_name}")
        else:
            QMessageBox.information(
                self.layout_manager.main_window,
                "操作提示",
                "外设已在最上方，无法上移"
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
                "操作提示",
                "请先选中一个外设"
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
                "操作限制",
                "只支持外设的下移操作"
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
            description=f"下移外设: {periph_name}"
        )
        
        # 通过StateManager执行命令（支持撤销）
        moved = self.state_manager.execute_command(command)
        
        if moved:
            # 更新UI
            self.update_peripheral_tree()
            # 重新选中该项目
            self._select_peripheral_in_tree(periph_name)
            # 显示状态消息
            if hasattr(main_window, 'status_label'):
                main_window.status_label.setText(f"已下移外设: {periph_name}")
        else:
            QMessageBox.information(
                self.layout_manager.main_window,
                "操作提示",
                "外设已在最下方，无法下移"
            )
    
    def _select_peripheral_in_tree(self, periph_name: str):
        """在树中选中指定外设"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            return
        
        # 遍历树查找外设项目
        for i in range(periph_tree.topLevelItemCount()):
            item = periph_tree.topLevelItem(i)
            if item.text(0) == periph_name:
                periph_tree.setCurrentItem(item)
                break
    
    def select_peripheral(self, periph_name: str):
        """选中指定外设（公开方法）"""
        self._select_peripheral_in_tree(periph_name)
        # 更新状态管理器的当前选中
        self.state_manager.current_peripheral = periph_name
        self.state_manager.current_register = None
        self.state_manager.current_field = None
        self.state_manager._notify_selection_change()
    
    def select_register(self, periph_name: str, reg_name: str):
        """选中指定寄存器"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            return
        
        # 查找外设项目
        for i in range(periph_tree.topLevelItemCount()):
            periph_item = periph_tree.topLevelItem(i)
            if periph_item.text(0) == periph_name:
                # 查找寄存器项目
                for j in range(periph_item.childCount()):
                    reg_item = periph_item.child(j)
                    if reg_item.text(0) == reg_name:
                        periph_tree.setCurrentItem(reg_item)
                        # 更新状态管理器的当前选中
                        self.state_manager.current_peripheral = periph_name
                        self.state_manager.current_register = reg_name
                        self.state_manager.current_field = None
                        self.state_manager._notify_selection_change()
                        return
                break
    
    def select_field(self, periph_name: str, reg_name: str, field_name: str):
        """选中指定位域"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            return
        
        # 查找外设项目
        for i in range(periph_tree.topLevelItemCount()):
            periph_item = periph_tree.topLevelItem(i)
            if periph_item.text(0) == periph_name:
                # 查找寄存器项目
                for j in range(periph_item.childCount()):
                    reg_item = periph_item.child(j)
                    if reg_item.text(0) == reg_name:
                        # 查找位域项目
                        for k in range(reg_item.childCount()):
                            field_item = reg_item.child(k)
                            if field_item.text(0) == field_name:
                                periph_tree.setCurrentItem(field_item)
                                # 更新状态管理器的当前选中
                                self.state_manager.current_peripheral = periph_name
                                self.state_manager.current_register = reg_name
                                self.state_manager.current_field = field_name
                                self.state_manager._notify_selection_change()
                                return
                        break
                break
    
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
                "导入错误",
                f"导入外设数据时发生错误: {str(e)}"
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
                    main_window.status_label.setText(f"已复制外设: {periph_name}")
                # 不再显示弹窗，避免干扰
                # QMessageBox.information(
                #     main_window,
                #     "复制成功",
                #     f"外设 '{periph_name}' 已复制到剪贴板"
                # )
        except Exception as e:
            QMessageBox.critical(
                self.layout_manager.main_window,
                "复制错误",
                f"复制外设时发生错误: {str(e)}"
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
                main_window.status_label.setText(f"已粘贴外设: {new_name}")
                
        except Exception as e:
            QMessageBox.critical(
                self.layout_manager.main_window,
                "粘贴错误",
                f"粘贴外设时发生错误: {str(e)}"
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
                    main_window.status_label.setText(f"已复制寄存器: {reg_name}")
                # 不显示弹窗
        except Exception as e:
            QMessageBox.critical(
                self.layout_manager.main_window,
                "复制错误",
                f"复制寄存器时发生错误: {str(e)}"
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
            self.state_manager.add_register(periph_name, register)
            
            # 更新UI
            self.update_peripheral_tree()
            
            # 显示状态消息
            main_window = self.layout_manager.main_window
            if hasattr(main_window, 'status_label'):
                main_window.status_label.setText(f"已粘贴寄存器: {new_name}")
                
        except Exception as e:
            QMessageBox.critical(
                self.layout_manager.main_window,
                "粘贴错误",
                f"粘贴寄存器时发生错误: {str(e)}"
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
                    main_window.status_label.setText(f"已复制位域: {field_name}")
                # 不显示弹窗
        except Exception as e:
            QMessageBox.critical(
                self.layout_manager.main_window,
                "复制错误",
                f"复制位域时发生错误: {str(e)}"
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
            self.state_manager.add_field(periph_name, reg_name, field)
            
            # 更新UI
            self.update_peripheral_tree()
            
            # 显示状态消息
            main_window = self.layout_manager.main_window
            if hasattr(main_window, 'status_label'):
                main_window.status_label.setText(f"已粘贴位域: {new_name}")
                
        except Exception as e:
            QMessageBox.critical(
                self.layout_manager.main_window,
                "粘贴错误",
                f"粘贴位域时发生错误: {str(e)}"
            )