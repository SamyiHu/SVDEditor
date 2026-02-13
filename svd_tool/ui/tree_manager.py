# svd_tool/ui/tree_manager.py
from PyQt6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QMenu, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData
from PyQt6.QtGui import QColor, QBrush, QFont, QDrag

from ..core.data_model import DeviceInfo, Peripheral, Register, Field
from ..core.constants import NODE_TYPES, COLORS
from ..i18n.i18n import t


class TreeManager:
    """树管理器"""
    
    def __init__(self):
        self.highlighted_items = []
        self.drag_start_pos = None
    
    def create_tree_widget(self) -> QTreeWidget:
        """创建树控件"""
        tree = QTreeWidget()
        tree.setHeaderLabels([t("label.tree_name"), t("label.tree_detail")])
        
        # 设置列宽策略
        header = tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        
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

        # 设置选择模式
        tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        
        return tree
    
    def update_tree(self, tree: QTreeWidget, device_info: DeviceInfo, sort_by_name: bool = False):
        """更新树控件"""
        
        expanded_items = self.get_expanded_items(tree)# 保存当前展开状态
        tree.clear()
        
         # 根据参数决定是否排序
        if sort_by_name:
            peripherals = sorted(device_info.peripherals.items(), key=lambda x: x[0])
        else:
            # 保持原有顺序（按照字典插入顺序，在Python 3.7+中是有序的）
            peripherals = device_info.peripherals.items()
        
        for periph_name, peripheral in peripherals:
            periph_item = self.create_peripheral_item(peripheral)
            tree.addTopLevelItem(periph_item)
            
            # 按照偏移地址排序寄存器
            sorted_registers = sorted(
                peripheral.registers.items(),
                key=lambda x: int(x[1].offset, 16) if x[1].offset.lower().startswith('0x') else int(x[1].offset)
            )
            
            # 添加寄存器
            for reg_name, register in sorted_registers:
                reg_item = self.create_register_item(register)
                periph_item.addChild(reg_item)

                # 按照起始位排序位域
                sorted_fields = sorted(
                    register.fields.items(),
                    key=lambda x: x[1].bit_offset
                )
                
                # 添加位域
                for field_name, field in sorted_fields:
                    field_item = self.create_field_item(field)
                    reg_item.addChild(field_item)
                    
            # 恢复展开状态
            if periph_name in expanded_items:
                periph_item.setExpanded(True)

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
        
        # 构建详细信息文本：基地址 + 继承关系
        detail_text = t("label.base_address_prefix") + str(peripheral.base_address)
        if peripheral.derived_from:
            detail_text += " | " + t("label.derived_from") + ": " + peripheral.derived_from
        item.setText(1, detail_text)
        
        # ... 详细信息设置 ...
        
        item.setData(0, Qt.ItemDataRole.UserRole, NODE_TYPES["PERIPHERAL"])
        item.setData(0, Qt.ItemDataRole.UserRole + 1, peripheral.name)

        # 外设可以拖动，并且可以接受同级（外设）的放置
        item.setFlags(
            item.flags() |
            Qt.ItemFlag.ItemIsDragEnabled |
            Qt.ItemFlag.ItemIsDropEnabled
        )
        
        return item

    def create_register_item(self, register: Register) -> QTreeWidgetItem:
        """创建寄存器节点"""
        item = QTreeWidgetItem()
        item.setText(0, register.name)
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
        item.setText(1, t("label.bit_range", start=field.bit_offset, width=field.bit_width))
        
        # ... 详细信息设置 ...
        
        item.setData(0, Qt.ItemDataRole.UserRole, NODE_TYPES["FIELD"])
        item.setData(0, Qt.ItemDataRole.UserRole + 1, field.name)
        
        # 位域不能拖动，也不能接受放置
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled & ~Qt.ItemFlag.ItemIsDropEnabled)
        
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
    
    def create_context_menu(self, item: QTreeWidgetItem) -> QMenu:
        """创建右键菜单"""
        menu = QMenu()
        
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
            # menu.addSeparator()
            # menu.addAction("按起始位排序")  # 为位域添加排序选项
        
        return menu
