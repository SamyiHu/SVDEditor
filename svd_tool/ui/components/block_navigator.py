"""
块导航器组件 - 提供块元素的快速导航和跳转功能
"""
import logging
from typing import Dict, Any, Optional, List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTreeWidget, QTreeWidgetItem, QLabel, QFrame,
    QLineEdit, QComboBox, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon

from ...core.block_manager import BlockManager, BlockType, BlockInfo
from ...i18n.i18n import t


class BlockNavigatorWidget(QWidget):
    """块导航器组件 - 提供块元素的快速导航和跳转功能"""
    
    # 信号定义
    block_selected = pyqtSignal(str)  # (block_key)
    peripheral_selected = pyqtSignal(str)  # (peripheral_name)
    register_selected = pyqtSignal(str, str)  # (peripheral_name, register_name)
    field_selected = pyqtSignal(str, str, str)  # (peripheral_name, register_name, field_name)
    
    def __init__(self, block_manager: BlockManager, parent=None):
        """
        初始化块导航器
        
        Args:
            block_manager: 块管理器
            parent: 父窗口
        """
        super().__init__(parent)
        self.block_manager = block_manager
        self.logger = logging.getLogger("BlockNavigatorWidget")
        
        # 当前选中的块
        self.current_block_key: Optional[str] = None
        
        # 初始化UI
        self.init_ui()
        
        # 构建树形结构
        self.build_tree()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 工具栏
        toolbar = QHBoxLayout()
        
        # 搜索框
        self.search_label = QLabel(t("label.search") + ":")
        toolbar.addWidget(self.search_label)
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(t("placeholder.search_blocks"))
        self.search_edit.textChanged.connect(self.on_search_text_changed)
        toolbar.addWidget(self.search_edit)
        
        # 清除搜索按钮
        clear_btn = QPushButton(t("button.clear"))
        clear_btn.clicked.connect(self.clear_search)
        toolbar.addWidget(clear_btn)
        
        layout.addLayout(toolbar)
        
        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)
        
        # 块树形视图
        self.block_tree = QTreeWidget()
        self.block_tree.setHeaderLabels([t("label.name"), t("label.type")])
        self.block_tree.setColumnWidth(0, 200)
        self.block_tree.setColumnWidth(1, 80)
        self.block_tree.setAlternatingRowColors(True)
        self.block_tree.itemClicked.connect(self.on_item_clicked)
        self.block_tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.block_tree)
        
        # 状态栏
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666; font-size: 9pt;")
        layout.addWidget(self.status_label)
    
    def build_tree(self):
        """构建块树形结构"""
        self.block_tree.clear()
        
        # 获取所有块
        blocks = self.block_manager.blocks
        
        # 按外设分组
        peripheral_items = {}  # {peripheral_name: tree_item}
        
        for block_key, block in blocks.items():
            if block.block_type == BlockType.DEVICE:
                # 设备块（根节点）
                device_item = QTreeWidgetItem(self.block_tree)
                device_item.setText(0, block.display_name)
                device_item.setText(1, t("type.device"))
                device_item.setData(0, Qt.ItemDataRole.UserRole, block_key)
                device_item.setExpanded(True)
                
            elif block.block_type == BlockType.PERIPHERAL:
                # 外设块
                periph_item = QTreeWidgetItem(self.block_tree)
                periph_item.setText(0, block.display_name)
                periph_item.setText(1, t("type.peripheral"))
                periph_item.setData(0, Qt.ItemDataRole.UserRole, block_key)
                periph_item.setExpanded(False)
                peripheral_items[block.peripheral_name] = periph_item
                
            elif block.block_type == BlockType.REGISTER:
                # 寄存器块
                periph_item = peripheral_items.get(block.peripheral_name)
                if periph_item:
                    reg_item = QTreeWidgetItem(periph_item)
                    reg_item.setText(0, block.display_name)
                    reg_item.setText(1, t("type.register"))
                    reg_item.setData(0, Qt.ItemDataRole.UserRole, block_key)
                    
            elif block.block_type == BlockType.FIELD:
                # 位域块
                periph_item = peripheral_items.get(block.peripheral_name)
                if periph_item:
                    # 查找对应的寄存器项
                    for i in range(periph_item.childCount()):
                        reg_item = periph_item.child(i)
                        reg_key = reg_item.data(0, Qt.ItemDataRole.UserRole)
                        if reg_key and reg_key.startswith(f"register:{block.peripheral_name}:"):
                            field_item = QTreeWidgetItem(reg_item)
                            field_item.setText(0, block.display_name)
                            field_item.setText(1, t("type.field"))
                            field_item.setData(0, Qt.ItemDataRole.UserRole, block_key)
                            break
        
        # 更新状态
        stats = self.block_manager.get_statistics()
        self.status_label.setText(
            f"{t('status.total_blocks')}: {stats['total_blocks']} | "
            f"{t('status.loaded_blocks')}: {stats['loaded_blocks']}"
        )
        
        self.logger.debug(f"块树构建完成，共 {len(blocks)} 个块")
    
    def on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """项点击处理"""
        block_key = item.data(0, Qt.ItemDataRole.UserRole)
        if block_key:
            self.current_block_key = block_key
            self.block_selected.emit(block_key)
            
            # 根据块类型发射相应的信号
            block = self.block_manager.get_block(block_key)
            if block:
                if block.block_type == BlockType.PERIPHERAL:
                    self.peripheral_selected.emit(block.peripheral_name)
                elif block.block_type == BlockType.REGISTER:
                    self.register_selected.emit(block.peripheral_name, block.register_name)
                elif block.block_type == BlockType.FIELD:
                    self.field_selected.emit(block.peripheral_name, block.register_name, block.field_name)
    
    def on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """项双击处理 - 导航到块"""
        block_key = item.data(0, Qt.ItemDataRole.UserRole)
        if block_key:
            self.navigate_to_block(block_key)
    
    def navigate_to_block(self, block_key: str):
        """
        导航到指定块
        
        Args:
            block_key: 块的key
        """
        block = self.block_manager.navigate_to(block_key)
        if block:
            self.current_block_key = block_key
            self.block_selected.emit(block_key)
            
            # 在树中选中对应的项
            self.select_tree_item(block_key)
            
            # 展开父节点
            self.expand_parent_items(block_key)
            
            self.logger.debug(f"导航到块: {block_key}")
    
    def select_tree_item(self, block_key: str):
        """
        在树中选中对应的项
        
        Args:
            block_key: 块的key
        """
        # 遍历树查找对应的项
        iterator = self.block_tree
        while iterator:
            item = iterator.currentItem()
            if item:
                item_key = item.data(0, Qt.ItemDataRole.UserRole)
                if item_key == block_key:
                    self.block_tree.setCurrentItem(item)
                    return
            
            iterator = iterator.next()
    
    def expand_parent_items(self, block_key: str):
        """
        展开父节点
        
        Args:
            block_key: 块的key
        """
        block = self.block_manager.get_block(block_key)
        if not block or not block.parent_key:
            return
        
        # 递归展开父节点
        self.expand_parent_items(block.parent_key)
        
        # 查找并展开父节点项
        iterator = self.block_tree
        while iterator:
            item = iterator.currentItem()
            if item:
                item_key = item.data(0, Qt.ItemDataRole.UserRole)
                if item_key == block.parent_key:
                    item.setExpanded(True)
                    return
            
            iterator = iterator.next()
    
    def on_search_text_changed(self, text: str):
        """搜索文本变化"""
        if not text:
            # 清除搜索时显示所有项
            self.show_all_items()
            return
        
        # 隐藏不匹配的项
        self.filter_items(text.lower())
    
    def filter_items(self, search_text: str):
        """
        过滤项
        
        Args:
            search_text: 搜索文本（小写）
        """
        iterator = self.block_tree
        while iterator:
            item = iterator.currentItem()
            if item:
                item_text = item.text(0).lower()
                if search_text in item_text:
                    item.setHidden(False)
                    # 展开父节点
                    parent = item.parent()
                    while parent:
                        parent.setHidden(False)
                        parent.setExpanded(True)
                        parent = parent.parent()
                else:
                    item.setHidden(True)
            
            iterator = iterator.next()
    
    def show_all_items(self):
        """显示所有项"""
        iterator = self.block_tree
        while iterator:
            item = iterator.currentItem()
            if item:
                item.setHidden(False)
            
            iterator = iterator.next()
    
    def clear_search(self):
        """清除搜索"""
        self.search_edit.clear()
        self.show_all_items()
    
    def refresh_tree(self):
        """刷新树形结构"""
        self.build_tree()
    
    def get_selected_block_key(self) -> Optional[str]:
        """
        获取当前选中的块key
        
        Returns:
            块的key，如果没有选中则返回None
        """
        item = self.block_tree.currentItem()
        if item:
            return item.data(0, Qt.ItemDataRole.UserRole)
        return None
    
    def expand_all(self):
        """展开所有项"""
        self.block_tree.expandAll()
    
    def collapse_all(self):
        """折叠所有项"""
        self.block_tree.collapseAll()
    
    def navigate_to_peripheral(self, peripheral_name: str):
        """
        导航到外设
        
        Args:
            peripheral_name: 外设名称
        """
        block_key = f"peripheral:{peripheral_name}"
        self.navigate_to_block(block_key)
    
    def navigate_to_register(self, peripheral_name: str, register_name: str):
        """
        导航到寄存器
        
        Args:
            peripheral_name: 外设名称
            register_name: 寄存器名称
        """
        block_key = f"register:{peripheral_name}:{register_name}"
        self.navigate_to_block(block_key)
    
    def navigate_to_field(self, peripheral_name: str, register_name: str, field_name: str):
        """
        导航到位域
        
        Args:
            peripheral_name: 外设名称
            register_name: 寄存器名称
            field_name: 位域名称
        """
        block_key = f"field:{peripheral_name}:{register_name}:{field_name}"
        self.navigate_to_block(block_key)
    
    def update_status(self):
        """更新状态栏"""
        stats = self.block_manager.get_statistics()
        self.status_label.setText(
            f"{t('status.total_blocks')}: {stats['total_blocks']} | "
            f"{t('status.loaded_blocks')}: {stats['loaded_blocks']} | "
            f"{t('status.visible_blocks')}: {stats['visible_blocks']}"
        )
