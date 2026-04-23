# svd_tool/ui/tree_manager.py
from PyQt6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QMenu, QHeaderView, QLabel, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QPoint
from PyQt6.QtGui import QColor, QBrush, QFont, QDrag, QPalette

from ..core.data_model import DeviceInfo, Peripheral, Register, Field
from ..core.constants import NODE_TYPES, COLORS
from ..i18n.i18n import t
from ..config.icons import get_icon
from ..config.tree_branch_style import apply_tree_branch_style


class TreeManager:
    """树管理器"""
    
    def __init__(self):
        self.highlighted_items = []
        self.drag_start_pos = None
        self.placeholder_item = None  # 占位符项
        self.placeholder_tree = None  # 占位符所属的树控件
        self.placeholder_original_text = None  # 占位符的原始文本
        self.placeholder_original_detail = None  # 占位符的原始详细信息
    
    def create_tree_widget(self) -> QTreeWidget:
        """创建树控件"""
        tree = QTreeWidget()
        tree.setHeaderLabels([t("label.tree_name"), t("label.tree_detail")])
        
        # 性能优化：统一行高，避免 Qt 逐行计算高度
        tree.setUniformRowHeights(True)
        
        # 设置列宽策略
        header = tree.header()
        # 使用 Interactive 模式避免 ResizeToContents 遍历所有节点计算宽度
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.resizeSection(0, 200)  # 默认列宽
        
        # 设置字体
        font = QFont()
        font.setPointSize(9)
        tree.setFont(font)
        
        # 启用右键菜单
        tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

         # 启用拖放
        tree.setDragEnabled(True)  # 允许拖动
        tree.setAcceptDrops(True)  # 允许放置
        tree.setDropIndicatorShown(True)  # 显示放置指示器
        tree.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)  # 内部移动

        # 设置选择模式（支持 Ctrl/Shift 多选）
        tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        
        # 应用自定义分支箭头样式
        apply_tree_branch_style(tree)
        
        return tree
    
    def update_tree(self, tree: QTreeWidget, device_info: DeviceInfo, sort_by_name: bool = False):
        """更新树控件 — 增量更新模式
        
        对比现有树节点与 device_info 中的数据：
        - 新增的外设/寄存器/位域 → 插入
        - 已删除的外设/寄存器/位域 → 移除
        - 已存在的 → 原地更新文本和数据
        这样可以保留展开/折叠状态和选中状态，避免全量重建导致的闪烁。
        """
        # 构建期望的外设名有序列表
        if sort_by_name:
            periph_list = sorted(device_info.peripherals.items(), key=lambda x: x[0])
        else:
            periph_list = list(device_info.peripherals.items())

        # ---- 第一步：同步顶层外设节点 ----
        existing_names = set()
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            existing_names.add(self.get_item_name(item))

        desired_names = [name for name, _ in periph_list]
        desired_set = set(desired_names)

        # 删除不再存在的外设节点
        i = 0
        while i < tree.topLevelItemCount():
            item = tree.topLevelItem(i)
            if self.get_item_name(item) not in desired_set:
                tree.takeTopLevelItem(i)
            else:
                i += 1

        # 构建 "名称 -> topLevelItem index" 映射
        name_to_index = {}
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            name_to_index[self.get_item_name(item)] = i

        # 按目标顺序逐个确保位置正确，并更新/插入
        for seq, (periph_name, peripheral) in enumerate(periph_list):
            if periph_name in name_to_index:
                # 已存在 → 更新文本
                idx = name_to_index[periph_name]
                periph_item = tree.topLevelItem(idx)
                self._update_peripheral_item(periph_item, peripheral)
                # 如果位置不对，移动
                if idx != seq:
                    tree.takeTopLevelItem(idx)
                    tree.insertTopLevelItem(seq, periph_item)
            else:
                # 新增
                periph_item = self.create_peripheral_item(peripheral)
                tree.insertTopLevelItem(seq, periph_item)

            # 获取最终的外设节点
            periph_item = tree.topLevelItem(seq)

            # ---- 第二步：同步该外设下的寄存器节点 ----
            sorted_registers = sorted(
                peripheral.registers.items(),
                key=lambda x: int(x[1].offset, 16) if x[1].offset.lower().startswith('0x') else int(x[1].offset)
            )
            self._sync_children(periph_item, sorted_registers,
                                lambda reg: self.create_register_item(reg),
                                lambda item, reg: self._update_register_item(item, reg),
                                NODE_TYPES["REGISTER"])

            # ---- 第三步：同步每个寄存器下的位域节点 ----
            for ri in range(periph_item.childCount()):
                reg_item = periph_item.child(ri)
                reg_name = self.get_item_name(reg_item)
                if reg_name in peripheral.registers:
                    register = peripheral.registers[reg_name]
                    sorted_fields = sorted(
                        register.fields.items(),
                        key=lambda x: x[1].bit_offset
                    )
                    self._sync_children(reg_item, sorted_fields,
                                        lambda f: self.create_field_item(f),
                                        lambda item, f: self._update_field_item(item, f),
                                        NODE_TYPES["FIELD"])

    def _sync_children(self, parent_item, sorted_items, create_fn, update_fn, node_type):
        """通用增量同步子节点 — O(n) 复杂度
        
        使用名称→索引映射表代替线性查找，将每个子节点的定位从 O(n) 降为 O(1)，
        整体复杂度从 O(n²) 降为 O(n)。
        
        Args:
            parent_item: 父节点
            sorted_items: [(name, data_obj), ...] 有序列表
            create_fn:    创建新节点的工厂函数
            update_fn:    更新已有节点的函数 (item, data_obj) -> None
            node_type:    节点类型常量
        """
        desired_set = {name for name, _ in sorted_items}

        # 删除不存在的子节点
        ci = 0
        while ci < parent_item.childCount():
            child = parent_item.child(ci)
            if self.get_item_name(child) not in desired_set:
                parent_item.takeChild(ci)
            else:
                ci += 1

        # 构建 名称→(索引, 节点) 映射表（O(n)），避免后续线性查找
        name_to_item = {}
        for ci in range(parent_item.childCount()):
            child = parent_item.child(ci)
            name_to_item[self.get_item_name(child)] = (ci, child)

        # 按目标顺序逐个确保位置正确（每步 O(1) 查找，整体 O(n)）
        for seq, (item_name, data_obj) in enumerate(sorted_items):
            entry = name_to_item.get(item_name)
            if entry is not None:
                existing_idx, existing_child = entry
                # 更新节点内容
                update_fn(existing_child, data_obj)
                # 如果位置不对，移动到正确位置
                if existing_idx != seq:
                    parent_item.takeChild(existing_idx)
                    parent_item.insertChild(seq, existing_child)
                    # 移动后重建映射表（索引已变化）
                    name_to_item.clear()
                    for ci in range(parent_item.childCount()):
                        child = parent_item.child(ci)
                        name_to_item[self.get_item_name(child)] = (ci, child)
            else:
                # 插入新节点
                new_item = create_fn(data_obj)
                parent_item.insertChild(seq, new_item)
                # 插入后重建映射表
                name_to_item.clear()
                for ci in range(parent_item.childCount()):
                    child = parent_item.child(ci)
                    name_to_item[self.get_item_name(child)] = (ci, child)

    def _update_peripheral_item(self, item: QTreeWidgetItem, peripheral: Peripheral):
        """原地更新外设节点文本"""
        item.setText(0, peripheral.name)
        item.setIcon(0, get_icon("tree_peripheral"))
        detail_text = t("label.base_address_prefix") + str(peripheral.base_address)
        if peripheral.derived_from:
            detail_text += " | " + t("label.derived_from") + ": " + peripheral.derived_from
        item.setText(1, detail_text)
        item.setData(0, Qt.ItemDataRole.UserRole + 1, peripheral.name)

    def _update_register_item(self, item: QTreeWidgetItem, register: Register):
        """原地更新寄存器节点文本"""
        item.setText(0, register.name)
        item.setIcon(0, get_icon("tree_register"))
        item.setText(1, t("label.offset_prefix") + str(register.offset))
        item.setData(0, Qt.ItemDataRole.UserRole + 1, register.name)

    def _update_field_item(self, item: QTreeWidgetItem, field: Field):
        """原地更新位域节点文本"""
        item.setText(0, field.name)
        item.setIcon(0, get_icon("tree_field"))
        item.setText(1, t("label.bit_range", start=field.bit_offset, width=field.bit_width))
        item.setData(0, Qt.ItemDataRole.UserRole + 1, field.name)

    def get_expanded_items(self, tree: QTreeWidget):
        """获取当前展开的项目"""
        expanded = []
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            if item.isExpanded():
                item_name = self.get_item_name(item)
                expanded.append(item_name)
        return expanded
    
    def create_peripheral_item(self, peripheral: Peripheral) -> QTreeWidgetItem:
        """创建外设节点"""
        item = QTreeWidgetItem()
        item.setText(0, peripheral.name)
        item.setIcon(0, get_icon("tree_peripheral"))
        
        # 构建详细信息文本：基地址 + 继承关系
        detail_text = t("label.base_address_prefix") + str(peripheral.base_address)
        if peripheral.derived_from:
            detail_text += " | " + t("label.derived_from") + ": " + peripheral.derived_from
        item.setText(1, detail_text)
        
        # ... 详细信息设置 ...
        
        item.setData(0, Qt.ItemDataRole.UserRole, NODE_TYPES["PERIPHERAL"])
        item.setData(0, Qt.ItemDataRole.UserRole + 1, peripheral.name)

        # 外设可以拖动，但不能接受其他外设的放置（防止外设嵌套）
        item.setFlags(
            item.flags() |
            Qt.ItemFlag.ItemIsDragEnabled
        )
        
        return item

    def create_register_item(self, register: Register) -> QTreeWidgetItem:
        """创建寄存器节点"""
        item = QTreeWidgetItem()
        item.setText(0, register.name)
        item.setIcon(0, get_icon("tree_register"))
        item.setText(1, t("label.offset_prefix") + str(register.offset))
        
        # ... 详细信息设置 ...
        
        item.setData(0, Qt.ItemDataRole.UserRole, NODE_TYPES["REGISTER"])
        item.setData(0, Qt.ItemDataRole.UserRole + 1, register.name)

         # 寄存器不能拖动，也不能接受放置（按照地址固定排序）
        # 移除拖放标志
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled & ~Qt.ItemFlag.ItemIsDropEnabled)
        
        return item

    def create_field_item(self, field: Field) -> QTreeWidgetItem:
        """创建位域节点"""
        item = QTreeWidgetItem()
        item.setText(0, field.name)
        item.setIcon(0, get_icon("tree_field"))
        item.setText(1, t("label.bit_range", start=field.bit_offset, width=field.bit_width))
        
        # ... 详细信息设置 ...
        
        item.setData(0, Qt.ItemDataRole.UserRole, NODE_TYPES["FIELD"])
        item.setData(0, Qt.ItemDataRole.UserRole + 1, field.name)

        # 位域可以拖动，但只允许在同级寄存器内拖放排序
        item.setFlags(
            item.flags() |
            Qt.ItemFlag.ItemIsDragEnabled
        )
        
        return item
    
    def get_item_type(self, item: QTreeWidgetItem) -> str:
        """获取节点类型"""
        return item.data(0, Qt.ItemDataRole.UserRole)
    
    def get_item_name(self, item: QTreeWidgetItem) -> str:
        """获取节点名称"""
        return item.data(0, Qt.ItemDataRole.UserRole + 1)
    
    def highlight_item(self, item: QTreeWidgetItem):
        """高亮节点"""
        # 清除之前的高亮
        self.clear_highlights()
        
        # 高亮当前节点
        item.setBackground(0, QBrush(QColor(COLORS["highlight"])))
        item.setBackground(1, QBrush(QColor(COLORS["highlight"])))
        self.highlighted_items.append(item)
    
    def clear_highlights(self):
        """清除所有高亮"""
        for item in self.highlighted_items:
            item.setBackground(0, QBrush(QColor(255, 255, 255)))
            item.setBackground(1, QBrush(QColor(255, 255, 255)))
        
        self.highlighted_items.clear()
    
    def show_insert_indicator(self, tree: QTreeWidget, target_item: QTreeWidgetItem, position: str = "below"):
        """显示插入指示器 - 使用占位符挤开其他项
        
        Args:
            tree: 树控件
            target_item: 目标项
            position: 插入位置 ("above" 或 "below")
        """
        # 如果占位符已经存在，先清除
        if self.placeholder_item:
            self.clear_insert_indicator(tree)
        
        # 创建占位符项
        placeholder = QTreeWidgetItem()
        placeholder.setText(0, "┌──────────────┐")
        placeholder.setText(1, "│  放置到这里  │")
        
        # 设置样式（半透明）
        placeholder.setForeground(0, QBrush(QColor(100, 100, 100, 150)))  # 灰色文字
        placeholder.setForeground(1, QBrush(QColor(100, 100, 100, 150)))
        placeholder.setBackground(0, QBrush(QColor(200, 200, 200, 100)))  # 浅灰色背景
        placeholder.setBackground(1, QBrush(QColor(200, 200, 200, 100)))
        # 设置flags：只读，不可选择，不接受拖放
        placeholder.setFlags(Qt.ItemFlag.ItemIsEnabled | ~Qt.ItemFlag.ItemIsDropEnabled)
        
        # 获取目标项的索引
        parent = target_item.parent()
        if parent is None:
            # 顶级项
            index = tree.indexOfTopLevelItem(target_item)
            if position == "above":
                tree.insertTopLevelItem(index, placeholder)
            else:  # below
                tree.insertTopLevelItem(index + 1, placeholder)
        else:
            # 子项（外设不应该有子项，但为了完整性）
            index = parent.indexOfChild(target_item)
            if position == "above":
                parent.insertChild(index, placeholder)
            else:  # below
                parent.insertChild(index + 1, placeholder)
        
        # 保存占位符
        self.placeholder_item = placeholder
        self.placeholder_tree = tree
    
    def turn_item_to_placeholder(self, item: QTreeWidgetItem):
        """把项变成占位符
        
        Args:
            item: 要变成占位符的项
        """
        # 保存原始文本
        self.placeholder_original_text = item.text(0)
        self.placeholder_original_detail = item.text(1)
        
        # 修改为占位符样式
        item.setText(0, "┌──────────────┐")
        item.setText(1, "│  放置到这里  │")
        item.setForeground(0, QBrush(QColor(100, 100, 100, 150)))  # 灰色文字
        item.setForeground(1, QBrush(QColor(100, 100, 100, 150)))
        item.setBackground(0, QBrush(QColor(200, 200, 200, 100)))  # 浅灰色背景
        item.setBackground(1, QBrush(QColor(200, 200, 200, 100)))
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | ~Qt.ItemFlag.ItemIsDropEnabled)
        
        # 保存占位符
        self.placeholder_item = item
    
    def restore_placeholder_to_item(self, item: QTreeWidgetItem):
        """把占位符恢复成原来的项
        
        Args:
            item: 要恢复的占位符项
        """
        # 恢复原始文本
        if self.placeholder_original_text is not None:
            item.setText(0, self.placeholder_original_text)
        if self.placeholder_original_detail is not None:
            item.setText(1, self.placeholder_original_detail)
        
        # 恢复原始样式
        item.setForeground(0, QBrush(QColor(0, 0, 0)))  # 黑色文字
        item.setForeground(1, QBrush(QColor(0, 0, 0)))
        item.setBackground(0, QBrush(QColor(255, 255, 255)))  # 白色背景
        item.setBackground(1, QBrush(QColor(255, 255, 255)))
        # 恢复原始flags：允许拖动，不允许放置
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled)
        
        # 清除占位符信息
        self.placeholder_item = None
        self.placeholder_original_text = None
        self.placeholder_original_detail = None
    
    def clear_insert_indicator(self, tree: QTreeWidget):
        """清除插入指示器"""
        if self.placeholder_item:
            # 获取占位符的父级
            parent = self.placeholder_item.parent()
            
            # 获取占位符的索引
            if parent is None:
                # 顶级项
                index = tree.indexOfTopLevelItem(self.placeholder_item)
                if index >= 0:
                    tree.takeTopLevelItem(index)
            else:
                # 子项
                index = parent.indexOfChild(self.placeholder_item)
                if index >= 0:
                    parent.takeChild(index)
            
            self.placeholder_item = None
            self.placeholder_tree = None
    
    def create_context_menu(self, item: QTreeWidgetItem, parent=None) -> QMenu:
        """创建右键菜单"""
        menu = QMenu(parent)
        
        item_type = self.get_item_type(item)
        
        if item_type == NODE_TYPES["PERIPHERAL"]:
            action = menu.addAction(t("menu.edit_peripheral"))
            action.setData("edit_peripheral")
            action = menu.addAction(t("menu.delete_peripheral"))
            action.setData("delete_peripheral")
            menu.addSeparator()
            action = menu.addAction(t("menu.copy_peripheral"))
            action.setData("copy_peripheral")
            action = menu.addAction(t("menu.paste_peripheral"))
            action.setData("paste_peripheral")
            menu.addSeparator()
            action = menu.addAction(t("menu.add_register"))
            action.setData("add_register")
            menu.addSeparator()
            action = menu.addAction(t("menu.sort_alphabetically"))
            action.setData("sort_alphabetically")
            menu.addSeparator()
            action = menu.addAction(t("button.move_up"))
            action.setData("move_up")
            action = menu.addAction(t("button.move_down"))
            action.setData("move_down")
            # menu.addAction("按地址排序寄存器")
        
        elif item_type == NODE_TYPES["REGISTER"]:
            action = menu.addAction(t("menu.edit_register"))
            action.setData("edit_register")
            action = menu.addAction(t("menu.delete_register"))
            action.setData("delete_register")
            menu.addSeparator()
            action = menu.addAction(t("menu.copy_register"))
            action.setData("copy_register")
            action = menu.addAction(t("menu.paste_register"))
            action.setData("paste_register")
            menu.addSeparator()
            action = menu.addAction(t("menu.add_field"))
            action.setData("add_field")
            # menu.addSeparator()
            # menu.addAction("按字母排序子项")
            # menu.addAction("按起始位排序位域")  # 修复：改为位域排序
        
        elif item_type == NODE_TYPES["FIELD"]:
            action = menu.addAction(t("menu.edit_field"))
            action.setData("edit_field")
            action = menu.addAction(t("menu.delete_field"))
            action.setData("delete_field")
            menu.addSeparator()
            action = menu.addAction(t("menu.copy_field"))
            action.setData("copy_field")
            action = menu.addAction(t("menu.paste_field"))
            action.setData("paste_field")
            menu.addSeparator()
            action = menu.addAction(t("button.move_up"))
            action.setData("move_field_up")
            action = menu.addAction(t("button.move_down"))
            action.setData("move_field_down")
            menu.addSeparator()
            action = menu.addAction(t("menu.sort_by_bit_offset", default="按位偏移排序"))
            action.setData("sort_fields_by_offset")
        
        return menu
