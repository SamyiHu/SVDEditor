"""
重构后的主窗口
使用组件化架构，提高可维护性
"""
import sys
import os
from typing import Dict, List, Optional, Any
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QTreeWidget,
    QTreeWidgetItem, QTabWidget, QSplitter, QMessageBox,
    QFileDialog, QMenu, QHeaderView, QSpinBox, QComboBox,
    QGroupBox, QToolBar, QStatusBar, QToolButton, QInputDialog, QAbstractItemView,
    QDockWidget, QTableWidget, QTableWidgetItem, QCheckBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
import logging
from datetime import datetime
from PyQt6.QtGui import (
    QColor, QBrush, QFont, QAction, QIcon, QKeySequence,
    QPainter, QPen, QPaintEvent, QPaintDevice
)

from ..core.data_model import DeviceInfo, Peripheral, Register, Field, Interrupt, CPUInfo
from ..core.svd_parser import SVDParser
from ..core.svd_generator import SVDGenerator
from ..core.command_history import CommandHistory, Command
from ..core.validators import Validator, ValidationError
from .tree_manager import TreeManager
from .dialog_factories import DialogFactory
from .widgets.visualization_widget import VisualizationWidget
from .widgets.address_map_widget import AddressMapWidget
from .widgets.bit_field_widget import BitFieldWidget

# 导入新组件
from .components.state_manager import StateManager
from .components.layout_manager import LayoutManager
from .components.peripheral_manager import PeripheralManager
from .components.menu_bar import MenuBarBuilder
from .components.toolbar import ToolBarBuilder

from ..utils.helpers import pretty_xml, format_hex
from ..utils.logger import Logger


class MainWindowRefactored(QMainWindow):
    """重构后的主窗口"""
    
    # 信号定义
    data_changed = pyqtSignal()
    selection_changed = pyqtSignal(str, str)  # (item_type, item_name)
    
    def __init__(self):
        super().__init__()
        
        # 初始化组件
        self.state_manager = StateManager()
        self.layout_manager = LayoutManager(self)
        self.peripheral_manager = PeripheralManager(self.state_manager, self.layout_manager)
        
        # 初始化其他组件
        self.command_history = CommandHistory()
        self.tree_manager = TreeManager()
        self.dialog_factory = DialogFactory(self)
        self.logger = Logger("svd_tool")
        
        # GUI 日志处理器
        self._gui_log_handler = None
        self.auto_save_error = True
        
        # 搜索相关
        self.search_results: List[Dict[str, Any]] = []
        self.current_search_index: int = -1
        
        self.init_ui()
        self.init_data()
        self.setup_signals()
        
        # 启用拖放功能
        self.enable_tree_drag_drop()
        
        # 应用样式
        self.apply_styles()
    
    def init_ui(self):
        """初始化UI"""
        import sys
        print(f"[DEBUG] init_ui开始，layout_manager={self.layout_manager}", file=sys.stderr)
        # 使用布局管理器创建UI
        widgets = self.layout_manager.create_layout()
        print(f"[DEBUG] create_layout返回，widgets keys={list(widgets.keys())}", file=sys.stderr)
        
        # 创建各个标签页
        tab_widget = widgets.get('tab_widget')
        print(f"[DEBUG] 获取tab_widget: {tab_widget}", file=sys.stderr)
        print(f"[DEBUG] tab_widget is None: {tab_widget is None}", file=sys.stderr)
        if tab_widget is not None:
            try:
                print(f"[DEBUG] 创建基本标签页", file=sys.stderr)
                self.layout_manager.create_basic_info_tab(tab_widget)
                print(f"[DEBUG] 创建外设标签页", file=sys.stderr)
                self.layout_manager.create_peripheral_tab(tab_widget)
                print(f"[DEBUG] 创建中断标签页", file=sys.stderr)
                self.layout_manager.create_interrupt_tab(tab_widget)
                print(f"[DEBUG] 创建预览标签页", file=sys.stderr)
                self.layout_manager.create_preview_tab(tab_widget)
            except Exception as e:
                print(f"[DEBUG] 创建标签页时发生异常: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
            
            # 设置默认标签页
            tab_widget.setCurrentIndex(0)
            print(f"[DEBUG] 标签页数量: {tab_widget.count()}", file=sys.stderr)
        else:
            print(f"[DEBUG] tab_widget 为 None，无法创建标签页", file=sys.stderr)
        
        # 连接外设管理器的信号
        self.peripheral_manager.peripheral_added.connect(self.on_peripheral_added)
        self.peripheral_manager.peripheral_updated.connect(self.on_peripheral_updated)
        self.peripheral_manager.peripheral_deleted.connect(self.on_peripheral_deleted)
        self.peripheral_manager.selection_changed.connect(self.on_selection_changed)
        
        # 连接UI按钮信号（必须在标签页创建后）
        self.peripheral_manager.connect_ui_signals()
        
        # 创建日志面板（默认隐藏）
        print(f"[DEBUG] 创建日志面板", file=sys.stderr)
        self.create_log_panel()
        print(f"[DEBUG] init_ui完成", file=sys.stderr)
        
        # 初始化中断表格（如果有数据）
        self._update_interrupt_table()
    
    def init_data(self):
        """初始化数据"""
        # 可以在这里加载默认数据或上次保存的数据
        pass
    
    def setup_signals(self):
        """设置信号连接"""
        # 连接搜索功能
        search_edit = self.layout_manager.get_widget('search_edit')
        if search_edit:
            search_edit.textChanged.connect(self.on_search_text_changed)
        
        search_prev_btn = self.layout_manager.get_widget('search_prev_btn')
        if search_prev_btn:
            search_prev_btn.clicked.connect(self.goto_prev_search)
        
        search_next_btn = self.layout_manager.get_widget('search_next_btn')
        if search_next_btn:
            search_next_btn.clicked.connect(self.goto_next_search)
        
        # 连接其他按钮
        generate_btn = self.layout_manager.get_widget('generate_btn')
        if generate_btn:
            generate_btn.clicked.connect(self.generate_svd)
        
        preview_btn = self.layout_manager.get_widget('preview_btn')
        if preview_btn:
            preview_btn.clicked.connect(self.preview_xml)
        
        export_btn = self.layout_manager.get_widget('export_btn')
        if export_btn:
            export_btn.clicked.connect(self.export_file)
        
        # 连接右键菜单
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if periph_tree and hasattr(self, 'peripheral_manager'):
            periph_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            periph_tree.customContextMenuRequested.connect(
                self.peripheral_manager.handle_tree_context_menu
            )
        
        # 连接可视化控件信号
        visualization_widget = self.layout_manager.get_widget('visualization_widget')
        if visualization_widget:
            visualization_widget.bit_field.field_clicked.connect(self.on_field_clicked)
            visualization_widget.address_map.register_clicked.connect(self.on_register_clicked)
        
        # 连接中断表格右键菜单和选择变化
        irq_table = self.layout_manager.get_widget('irq_table')
        if irq_table:
            irq_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            irq_table.customContextMenuRequested.connect(self.on_irq_context_menu)
            # 连接选择变化信号以更新按钮状态
            irq_table.itemSelectionChanged.connect(self.update_interrupt_buttons_state)
        
        # 连接位域表格双击编辑
        field_table = self.layout_manager.get_widget('field_table')
        if field_table:
            field_table.doubleClicked.connect(self.on_field_table_double_clicked)
        
        # 连接中断表格双击编辑
        irq_table = self.layout_manager.get_widget('irq_table')
        if irq_table:
            irq_table.doubleClicked.connect(self.on_irq_table_double_clicked)
        
        # 连接三个独立的添加按钮
        add_periph_btn = self.layout_manager.get_widget('add_periph_btn')
        if add_periph_btn:
            add_periph_btn.clicked.connect(self.add_peripheral)
        
        add_reg_btn = self.layout_manager.get_widget('add_reg_btn')
        if add_reg_btn:
            add_reg_btn.clicked.connect(self.add_register)
        
        add_field_btn = self.layout_manager.get_widget('add_field_btn')
        if add_field_btn:
            add_field_btn.clicked.connect(self.add_field)
        
        # 连接编辑按钮
        edit_periph_btn = self.layout_manager.get_widget('edit_periph_btn')
        if edit_periph_btn:
            edit_periph_btn.clicked.connect(self.on_edit_button_clicked)
        
        # 连接删除按钮
        delete_periph_btn = self.layout_manager.get_widget('delete_periph_btn')
        if delete_periph_btn:
            delete_periph_btn.clicked.connect(self.on_delete_button_clicked)
        
        # 连接中断按钮
        add_irq_btn = self.layout_manager.get_widget('add_irq_btn')
        if add_irq_btn:
            add_irq_btn.clicked.connect(self.add_interrupt)
        
        edit_irq_btn = self.layout_manager.get_widget('edit_irq_btn')
        if edit_irq_btn:
            edit_irq_btn.clicked.connect(lambda: self.edit_interrupt())
        
        delete_irq_btn = self.layout_manager.get_widget('delete_irq_btn')
        if delete_irq_btn:
            delete_irq_btn.clicked.connect(lambda: self.delete_interrupt())
    
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

    def add_peripheral(self):
        """添加外设（直接调用外设管理器的对话框）"""
        self.peripheral_manager.add_peripheral_dialog()

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
    
    def on_selection_changed(self, peripheral: str, register: str, field: str):
        """选择变更事件"""
        self.selection_changed.emit(
            'peripheral' if peripheral else 'register' if register else 'field',
            peripheral or register or field or ''
        )
        
        # 更新可视化控件
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
    
    def update_visualization(self, peripheral: str, register: str, field: str):
        """更新可视化控件显示"""
        visualization_widget = self.layout_manager.get_widget('visualization_widget')
        if not visualization_widget:
            return
            
        # 设置主窗口引用
        visualization_widget.main_window = self
        
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
                        visualization_widget.show_register(reg)
                        
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
    
    def update_data_stats(self):
        """更新数据统计"""
        stats = self.state_manager.get_data_stats()
        self.layout_manager.update_data_stats(stats)
    
    def on_field_clicked(self, field):
        """位域点击事件处理"""
        # 获取当前选择
        selection = self.state_manager.get_selection()
        peripheral = selection.get('peripheral')
        register = selection.get('register')
        
        if not peripheral or not register:
            return
            
        # 设置选择
        self.state_manager.set_selection(
            peripheral=peripheral,
            register=register,
            field=field.name if field else None
        )
        
        # 更新树控件中的选择
        if field and peripheral and register:
            # 在树中选中对应的位域
            periph_tree = self.layout_manager.get_widget('periph_tree')
            if periph_tree:
                # 查找外设项
                for i in range(periph_tree.topLevelItemCount()):
                    periph_item = periph_tree.topLevelItem(i)
                    if periph_item.text(0) == peripheral:
                        # 展开外设项
                        periph_item.setExpanded(True)
                        # 查找寄存器项
                        for j in range(periph_item.childCount()):
                            reg_item = periph_item.child(j)
                            if reg_item.text(0) == register:
                                # 展开寄存器项显示位域
                                reg_item.setExpanded(True)
                                # 查找位域项
                                for k in range(reg_item.childCount()):
                                    field_item = reg_item.child(k)
                                    if field_item.text(0) == field.name:
                                        # 选中位域项
                                        periph_tree.setCurrentItem(field_item)
                                        # 确保位域项可见
                                        periph_tree.scrollToItem(field_item)
                                        break
                                break
                        break
    
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
        """统一的删除按钮点击事件 - 根据当前选择智能删除"""
        # 获取当前选择
        selection = self.state_manager.get_selection()
        peripheral = selection.get('peripheral')
        register = selection.get('register')
        field = selection.get('field')
        
        # 根据选择决定删除什么
        if field and peripheral and register:
            # 删除位域
            self.delete_field(field)
        elif register and peripheral:
            # 删除寄存器
            self.delete_register(register)
        elif peripheral:
            # 删除外设
            self.peripheral_manager.delete_selected_peripheral()
        else:
            # 没有选择任何项目
            self.show_message("提示", "请先选择一个项目进行删除", "info")
    
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
            # 在树中选中对应的寄存器
            periph_tree = self.layout_manager.get_widget('periph_tree')
            if periph_tree:
                # 查找外设项
                for i in range(periph_tree.topLevelItemCount()):
                    periph_item = periph_tree.topLevelItem(i)
                    if periph_item.text(0) == peripheral:
                        # 展开外设项
                        periph_item.setExpanded(True)
                        # 查找寄存器项
                        for j in range(periph_item.childCount()):
                            reg_item = periph_item.child(j)
                            if reg_item.text(0) == register.name:
                                # 选中寄存器项
                                periph_tree.setCurrentItem(reg_item)
                                break
                        break
    
    # ===================== 搜索功能 =====================
    def on_search_text_changed(self, text: str):
        """搜索文本变更"""
        if not text.strip():
            self.clear_search_highlights()
            return
        
        self.perform_search(text)
    
    def perform_search(self, search_text: str):
        """执行搜索"""
        # 清空之前的结果
        self.search_results.clear()
        self.current_search_index = -1
        
        search_text_lower = search_text.lower()
        
        # 搜索外设树
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if periph_tree:
            self.search_in_tree(periph_tree, search_text_lower, 'periph')
        
        # 搜索中断表格
        irq_table = self.layout_manager.get_widget('irq_table')
        if irq_table:
            self.search_in_table(irq_table, search_text_lower, 'irq')
        
        # 更新UI
        self.update_search_ui()
    
    def search_in_tree(self, tree: QTreeWidget, search_text: str, tree_type: str):
        """在树中搜索"""
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            self._search_tree_item(item, search_text, tree_type)
    
    def _search_tree_item(self, item: QTreeWidgetItem, search_text: str, tree_type: str):
        """递归搜索树项"""
        # 检查当前项
        for col in range(item.columnCount()):
            if search_text in item.text(col).lower():
                self.search_results.append({"tree": tree_type, "item": item})
                break
        
        # 递归搜索子项
        for i in range(item.childCount()):
            child = item.child(i)
            self._search_tree_item(child, search_text, tree_type)
    
    def search_in_table(self, table: QTableWidget, search_text: str, table_type: str):
        """在表格中搜索"""
        for row in range(table.rowCount()):
            for col in range(table.columnCount()):
                item = table.item(row, col)
                if item and search_text in item.text().lower():
                    self.search_results.append({"table": table_type, "row": row, "col": col})
    
    def clear_search_highlights(self):
        """清除搜索高亮"""
        # 清除外设树高亮
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if periph_tree:
            self._clear_tree_highlights(periph_tree)
        
        # 清除中断表格高亮
        irq_table = self.layout_manager.get_widget('irq_table')
        if irq_table:
            self._clear_table_highlights(irq_table)
        
        # 清空结果
        self.search_results.clear()
        self.current_search_index = -1
        self.update_search_ui()
    
    def _clear_tree_highlights(self, tree: QTreeWidget):
        """清除树高亮"""
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            self._clear_tree_item_highlights(item)
    
    def _clear_tree_item_highlights(self, item: QTreeWidgetItem):
        """递归清除树项高亮"""
        for col in range(item.columnCount()):
            item.setBackground(col, QColor(255, 255, 255))  # 白色背景
        
        for i in range(item.childCount()):
            child = item.child(i)
            self._clear_tree_item_highlights(child)
    
    def _clear_table_highlights(self, table: QTableWidget):
        """清除表格高亮"""
        for row in range(table.rowCount()):
            for col in range(table.columnCount()):
                item = table.item(row, col)
                if item:
                    item.setBackground(QColor(255, 255, 255))  # 白色背景
    
    def update_search_ui(self):
        """更新搜索UI"""
        count = len(self.search_results)
        
        search_count_label = self.layout_manager.get_widget('search_count_label')
        if search_count_label:
            if count > 0:
                search_count_label.setText(f"找到 {count} 个结果")
            else:
                search_count_label.setText("")
        
        search_prev_btn = self.layout_manager.get_widget('search_prev_btn')
        search_next_btn = self.layout_manager.get_widget('search_next_btn')
        
        if search_prev_btn and search_next_btn:
            has_results = count > 0
            search_prev_btn.setEnabled(has_results)
            search_next_btn.setEnabled(has_results)
    
    def goto_prev_search(self):
        """跳转到上一个搜索结果"""
        if not self.search_results:
            return
        
        self.current_search_index -= 1
        if self.current_search_index < 0:
            self.current_search_index = len(self.search_results) - 1
        
        self.goto_search_result(self.current_search_index)
    
    def goto_next_search(self):
        """跳转到下一个搜索结果"""
        if not self.search_results:
            return
        
        self.current_search_index += 1
        if self.current_search_index >= len(self.search_results):
            self.current_search_index = 0
        
        self.goto_search_result(self.current_search_index)
    
    def highlight_current_search(self):
        """高亮当前搜索结果（与老版本一致）"""
        if not self.search_results or self.current_search_index < 0:
            return
        
        # 清除之前的高亮
        self.tree_manager.clear_highlights()
        
        # 清除中断表格的高亮
        irq_table = self.layout_manager.get_widget('irq_table')
        if irq_table:
            for row in range(irq_table.rowCount()):
                for col in range(irq_table.columnCount()):
                    item = irq_table.item(row, col)
                    if item:
                        item.setBackground(QColor(255, 255, 255))
        
        # 获取当前结果
        entry = self.search_results[self.current_search_index]
        
        # 高亮当前结果
        if 'tree' in entry:
            tree_type = entry['tree']
            item = entry['item']
            
            if tree_type == 'periph':
                # 切换到外设标签页
                tab_widget = self.layout_manager.get_widget('tab_widget')
                if tab_widget:
                    tab_widget.setCurrentIndex(1)  # 外设标签页索引
                
                # 高亮并展开父节点
                self.tree_manager.highlight_item(item)
                parent = item.parent()
                while parent:
                    parent.setExpanded(True)
                    parent = parent.parent()
        
        elif 'table' in entry:
            table_type = entry['table']
            row = entry['row']
            col = entry.get('col', 0)
            
            if table_type == 'irq':
                # 切换到中断标签页
                tab_widget = self.layout_manager.get_widget('tab_widget')
                if tab_widget:
                    tab_widget.setCurrentIndex(2)  # 中断标签页索引
                
                # 高亮表格行
                table = self.layout_manager.get_widget('irq_table')
                if table:
                    for c in range(table.columnCount()):
                        item = table.item(row, c)
                        if item:
                            item.setBackground(QColor(255, 255, 0))  # 黄色高亮
    
    def goto_search_result(self, index: int):
        """跳转到指定搜索结果"""
        if index < 0 or index >= len(self.search_results):
            return
        
        self.current_search_index = index
        entry = self.search_results[index]
        
        if 'tree' in entry:
            tree_type = entry['tree']
            item = entry['item']
            
            if tree_type == 'periph':
                tree = self.layout_manager.get_widget('periph_tree')
                if tree:
                    tree.scrollToItem(item)
                    tree.setCurrentItem(item)
                    item.setExpanded(True)
        
        elif 'table' in entry:
            table_type = entry['table']
            row = entry['row']
            
            if table_type == 'irq':
                table = self.layout_manager.get_widget('irq_table')
                if table:
                    table.scrollToItem(table.item(row, 0))
                    table.selectRow(row)
        
        # 高亮当前搜索结果
        self.highlight_current_search()
        
        # 更新搜索计数
        search_count_label = self.layout_manager.get_widget('search_count_label')
        if search_count_label:
            search_count_label.setText(f"{index + 1}/{len(self.search_results)}")
    
    # ===================== 文件操作 =====================
    def new_file(self):
        """新建文件"""
        # 检查未保存的更改
        if self.check_unsaved_changes():
            # 重置状态
            self.state_manager.reset()
            self.command_history.clear()
            
            # 更新UI
            self.peripheral_manager.update_peripheral_tree()
            self.update_data_stats()
            
            # 更新状态
            self.layout_manager.update_status("已创建新文件")
    
    def open_svd_file(self):
        """打开SVD文件"""
        # 检查未保存的更改
        if self.check_unsaved_changes():
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择SVD文件", "", "SVD文件 (*.svd);;XML文件 (*.xml)"
            )
            
            if file_path:
                try:
                    self.layout_manager.update_status("正在解析SVD文件...")
                    QApplication.processEvents()  # 更新UI
                    
                    # 解析文件
                    parser = SVDParser()
                    device_info = parser.parse_file(file_path)
                    
                    # 更新状态管理器
                    self.state_manager.device_info = device_info
                    self.state_manager.clear_selection()
                    self.command_history.clear()
                    
                    # 更新UI
                    self.peripheral_manager.update_peripheral_tree()
                    self.update_data_stats()
                    self._update_interrupt_table()
                    
                    # 更新基础信息
                    if hasattr(self.layout_manager, 'update_basic_info'):
                        self.layout_manager.update_basic_info(device_info)
                    
                    self.layout_manager.update_status(f"已加载: {os.path.basename(file_path)}")
                    
                    # 显示警告
                    if parser.warnings:
                        warning_msg = "\n".join(parser.warnings[:10])
                        if len(parser.warnings) > 10:
                            warning_msg += f"\n...还有{len(parser.warnings)-10}条警告"
                        QMessageBox.warning(self, "解析警告", warning_msg)
                    
                except Exception as e:
                    self.logger.error(f"文件加载失败: {str(e)}")
                    QMessageBox.critical(self, "加载错误", f"文件加载失败: {str(e)}")
    
    def save_svd_file(self):
        """保存SVD文件"""
        self.save_svd_file_impl(force_save_as=False)
    
    def save_svd_file_as(self):
        """另存为SVD文件"""
        self.save_svd_file_impl(force_save_as=True)
    
    def save_svd_file_impl(self, force_save_as=False):
        """保存SVD文件实现"""
        try:
            # 获取保存路径
            file_path = None
            if not force_save_as and hasattr(self, 'current_file_path') and self.current_file_path:
                file_path = self.current_file_path
            else:
                file_path, _ = QFileDialog.getSaveFileName(
                    self, "保存SVD文件", "", "SVD文件 (*.svd);;所有文件 (*.*)"
                )
            
            if not file_path:
                return
            
            # 生成SVD
            generator = SVDGenerator(self.state_manager.device_info)
            svd_xml = generator.generate()
            
            # 保存文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(svd_xml)
            
            # 更新状态
            self.current_file_path = file_path
            self.layout_manager.update_status(f"SVD文件已保存: {file_path}")
            QMessageBox.information(self, "保存成功", f"SVD文件已保存到:\n{file_path}")
            
        except Exception as e:
            self.logger.error(f"文件保存失败: {str(e)}")
            QMessageBox.critical(self, "保存错误", f"文件保存失败: {str(e)}")
    
    def check_unsaved_changes(self) -> bool:
        """检查未保存的更改"""
        # 这里可以添加检查逻辑
        # 暂时返回True表示可以继续
        return True
    
    def generate_svd(self):
        """生成SVD文件"""
        try:
            # 首先从UI更新设备信息
            self.update_device_info_from_ui()
            
            # 验证数据
            errors = self.state_manager.validate_device_info()
            if errors:
                QMessageBox.warning(self, "验证错误", "\n".join(errors))
                return
            
            # 生成SVD
            generator = SVDGenerator(self.state_manager.device_info)
            svd_xml = generator.generate()
            
            # 更新预览
            preview_edit = self.layout_manager.get_widget('preview_edit')
            if preview_edit:
                preview_edit.setPlainText(pretty_xml(svd_xml))
            
            self.logger.info("SVD生成成功")
            self.layout_manager.update_status("SVD生成成功")
            
        except Exception as e:
            self.logger.error(f"SVD生成失败: {str(e)}")
            QMessageBox.critical(self, "生成错误", f"SVD生成失败: {str(e)}")
    
    def preview_xml(self):
        """预览XML"""
        try:
            # 首先从UI更新设备信息
            self.update_device_info_from_ui()
            
            generator = SVDGenerator(self.state_manager.device_info)
            svd_xml = generator.generate()
            
            preview_edit = self.layout_manager.get_widget('preview_edit')
            if preview_edit:
                preview_edit.setPlainText(pretty_xml(svd_xml))
            
            self.logger.info("XML预览生成成功")
            
        except Exception as e:
            self.logger.error(f"XML预览失败: {str(e)}")
            QMessageBox.critical(self, "预览错误", f"XML预览失败: {str(e)}")
    
    def export_file(self):
        """导出文件"""
        try:
            # 获取保存路径
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存SVD文件", "", "SVD文件 (*.svd);;所有文件 (*.*)"
            )
            
            if not file_path:
                return
            
            # 首先从UI更新设备信息
            self.update_device_info_from_ui()
            
            # 生成SVD
            generator = SVDGenerator(self.state_manager.device_info)
            svd_xml = generator.generate()
            
            # 保存文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(svd_xml)
            
            self.logger.info(f"SVD文件已保存: {file_path}")
            QMessageBox.information(self, "保存成功", f"SVD文件已保存到:\n{file_path}")
            
        except Exception as e:
            self.logger.error(f"文件保存失败: {str(e)}")
            QMessageBox.critical(self, "保存错误", f"文件保存失败: {str(e)}")
    
    # ===================== 其他方法 =====================
    def enable_tree_drag_drop(self):
        """启用树拖放功能"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if periph_tree:
            periph_tree.setDragEnabled(True)
            periph_tree.setAcceptDrops(True)
            periph_tree.setDropIndicatorShown(True)
            periph_tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
            
            # 设置自定义拖放事件处理
            periph_tree.dropEvent = self.custom_drop_event
    
    def custom_drop_event(self, event):
        """自定义拖放事件处理 - 只允许外设之间的同级拖放"""
        # 获取树控件
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            event.ignore()
            return
            
        # 在拖放前保存源项目信息
        source_item = periph_tree.currentItem()
        if not source_item:
            event.ignore()
            return
            
        # 获取源项目信息（在拖放前保存）
        source_type = self.tree_manager.get_item_type(source_item)
        source_name = self.tree_manager.get_item_name(source_item)
        
        # 只允许外设拖放
        if source_type != "peripheral":
            event.ignore()
            return  # 不显示警告，直接忽略
            
        # 简单验证：只允许外设之间的同级拖放
        # 让Qt执行默认的拖放逻辑，然后我们再验证和修正
        
        # 执行拖放
        from PyQt6.QtWidgets import QTreeWidget
        QTreeWidget.dropEvent(periph_tree, event)
        
        # 拖放后验证并修正树结构
        self._validate_and_fix_tree_structure_after_drop(source_name)
    
    def _validate_and_fix_tree_structure_after_drop(self, moved_periph_name):
        """拖放后验证并修正树结构"""
        try:
            # 获取树控件
            periph_tree = self.layout_manager.get_widget('periph_tree')
            if not periph_tree:
                return
                
            # 检查树结构是否有效
            valid = True
            for i in range(periph_tree.topLevelItemCount()):
                item = periph_tree.topLevelItem(i)
                if item is None:
                    continue
                item_type = self.tree_manager.get_item_type(item)
                
                # 确保所有顶级项目都是外设
                if item_type != "peripheral":
                    valid = False
                    break
                
                # 检查外设下的项目是否有效
                for j in range(item.childCount()):
                    child = item.child(j)
                    if child is None:
                        continue
                    child_type = self.tree_manager.get_item_type(child)
                    if child_type != "register":
                        valid = False
                        break
                    
                    # 检查寄存器下的项目是否有效
                    for k in range(child.childCount()):
                        grandchild = child.child(k)
                        if grandchild is None:
                            continue
                        grandchild_type = self.tree_manager.get_item_type(grandchild)
                        if grandchild_type != "field":
                            valid = False
                            break
                    
                    if not valid:
                        break
                
                if not valid:
                    break
            
            if not valid:
                # 如果结构无效，恢复UI
                self.peripheral_manager.update_peripheral_tree()
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "拖放错误", "拖放操作导致无效的树结构，已恢复")
            else:
                # 更新数据模型
                self.update_data_model_from_tree()
                # 更新状态栏
                self.layout_manager.update_status(f"已调整外设顺序: {moved_periph_name}")
                
                # 延迟重新选中项目
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(50, lambda: self.peripheral_manager._select_peripheral_in_tree(moved_periph_name))
        
        except Exception as e:
            print(f"拖放后验证出错: {e}")
            # 出错时恢复
            self.peripheral_manager.update_peripheral_tree()
    
    def apply_styles(self):
        """应用样式"""
        # 这里可以添加样式设置
        pass
    
    # ===================== 撤销/重做功能 =====================
    def undo(self):
        """撤销操作"""
        self.state_manager.undo()
        self.update_data_stats()
    
    def redo(self):
        """重做操作"""
        self.state_manager.redo()
        self.update_data_stats()
    
    # ===================== 排序功能 =====================
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
                self.layout_manager.update_status("已按字母顺序排序")
                self.logger.info("按字母顺序排序完成")
            else:
                self.layout_manager.update_status("顺序未变化，无需排序")
                
        except Exception as e:
            self.logger.error(f"按字母排序失败: {str(e)}")
            QMessageBox.warning(self, "排序错误", f"按字母排序失败: {str(e)}")
    
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
                    self.layout_manager.update_status(f"已按偏移地址排序寄存器")
            elif selected_periph:
                # 排序外设
                changed = self.state_manager.sort_peripherals_by_address()
                if changed:
                    self.peripheral_manager.update_peripheral_tree()
                    self.layout_manager.update_status("已按基地址排序外设")
            else:
                # 默认排序外设
                changed = self.state_manager.sort_peripherals_by_address()
                if changed:
                    self.peripheral_manager.update_peripheral_tree()
                    self.layout_manager.update_status("已按基地址排序外设")
            
            # 恢复选中项
            if selected_periph:
                self.peripheral_manager.select_peripheral(selected_periph)
                if selected_register:
                    # 这里需要添加选择寄存器的功能
                    pass
            
            if changed:
                self.logger.info("按地址排序完成")
            else:
                self.layout_manager.update_status("顺序未变化，无需排序")
                
        except Exception as e:
            self.logger.error(f"按地址排序失败: {str(e)}")
            QMessageBox.warning(self, "排序错误", f"按地址排序失败: {str(e)}")
    
    def expand_all_tree(self):
        """展开所有树节点"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if periph_tree:
            periph_tree.expandAll()
            self.layout_manager.update_status("已展开所有树节点")
    
    def collapse_all_tree(self):
        """折叠所有树节点"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if periph_tree:
            periph_tree.collapseAll()
            self.layout_manager.update_status("已折叠所有树节点")
    
    def add_register(self):
        """添加寄存器"""
        # 检查是否有选中的外设
        current_peripheral = self.state_manager.get_current_peripheral()
        if not current_peripheral:
            QMessageBox.warning(self, "警告", "请先选择一个外设")
            return
        
        # 获取当前外设的寄存器列表
        existing_registers = []
        if current_peripheral in self.state_manager.device_info.peripherals:
            existing_registers = list(self.state_manager.device_info.peripherals[current_peripheral].registers.keys())
        
        self.dialog_factory.set_existing_registers(existing_registers)
        
        # 创建对话框
        dialog = self.dialog_factory.create_register_dialog()
        
        if dialog.exec():
            result = getattr(dialog, "result_data", None)
            if result is None:
                return
            
            # 创建寄存器对象
            from ..core.data_model import Register
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
            self.state_manager.add_register(current_peripheral, register)
            
            # 更新UI
            self.peripheral_manager.update_peripheral_tree()
            
            # 选中新添加的寄存器
            self.peripheral_manager.select_register(current_peripheral, register.name)
            
            # 更新状态
            self.layout_manager.update_status(f"已添加寄存器: {register.name}")
            self.logger.info(f"添加寄存器: {register.name}")
            
            # 发射数据变化信号
            self.data_changed.emit()
    
    def edit_register(self, reg_name: str = None):
        """编辑寄存器"""
        # 如果没有提供寄存器名，尝试从当前选择获取
        if reg_name is None:
            current_register = self.state_manager.get_current_register()
            if not current_register:
                QMessageBox.warning(self, "警告", "请先选择一个寄存器")
                return
            reg_name = current_register
        
        # 检查是否有选中的外设
        current_peripheral = self.state_manager.get_current_peripheral()
        if not current_peripheral:
            QMessageBox.warning(self, "警告", "请先选择一个外设")
            return
        
        # 检查寄存器是否存在
        if (current_peripheral not in self.state_manager.device_info.peripherals or
            reg_name not in self.state_manager.device_info.peripherals[current_peripheral].registers):
            QMessageBox.warning(self, "警告", f"寄存器 '{reg_name}' 不存在")
            return
        
        # 获取寄存器对象
        register = self.state_manager.device_info.peripherals[current_peripheral].registers[reg_name]
        
        # 获取当前外设的寄存器列表（排除当前寄存器）
        existing_registers = [
            name for name in self.state_manager.device_info.peripherals[current_peripheral].registers.keys()
            if name != reg_name
        ]
        self.dialog_factory.set_existing_registers(existing_registers)
        
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
            from ..core.data_model import Register
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
            
            # 更新UI
            self.peripheral_manager.update_peripheral_tree()
            
            # 选中更新后的寄存器
            self.peripheral_manager.select_register(current_peripheral, new_name)
            
            # 更新状态
            self.layout_manager.update_status(f"已更新寄存器: {new_name}")
            self.logger.info(f"编辑寄存器: {old_name} -> {new_name}")
            
            # 发射数据变化信号
            self.data_changed.emit()
    
    def delete_register(self, reg_name: str = None):
        """删除寄存器"""
        # 如果没有提供寄存器名，尝试从当前选择获取
        if reg_name is None:
            current_register = self.state_manager.get_current_register()
            if not current_register:
                QMessageBox.warning(self, "警告", "请先选择一个寄存器")
                return
            reg_name = current_register
        
        # 检查是否有选中的外设
        current_peripheral = self.state_manager.get_current_peripheral()
        if not current_peripheral:
            QMessageBox.warning(self, "警告", "请先选择一个外设")
            return
        
        # 检查寄存器是否存在
        if (current_peripheral not in self.state_manager.device_info.peripherals or
            reg_name not in self.state_manager.device_info.peripherals[current_peripheral].registers):
            QMessageBox.warning(self, "警告", f"寄存器 '{reg_name}' 不存在")
            return
        
        # 确认删除
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除寄存器 '{reg_name}' 吗？\n这将同时删除该寄存器下的所有位域。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # 使用StateManager删除寄存器
        self.state_manager.delete_register(current_peripheral, reg_name)
        
        # 更新UI
        self.peripheral_manager.update_peripheral_tree()
        
        # 清除寄存器选择
        self.state_manager.set_selection(register=None, field=None)
        
        # 更新状态
        self.layout_manager.update_status(f"已删除寄存器: {reg_name}")
        self.logger.info(f"删除寄存器: {reg_name}")
        
        # 发射数据变化信号
        self.data_changed.emit()
    
    def delete_multiple_registers(self, register_names: List[str] = None):
        """批量删除寄存器"""
        # 检查是否有选中的外设
        current_peripheral = self.state_manager.get_current_peripheral()
        if not current_peripheral:
            QMessageBox.warning(self, "警告", "请先选择一个外设")
            return
        
        # 如果没有提供寄存器名列表，尝试从当前选择获取
        if register_names is None:
            # 这里可以扩展为从树控件中获取多个选中的寄存器
            # 目前先使用当前选中的寄存器
            current_register = self.state_manager.get_current_register()
            if not current_register:
                QMessageBox.warning(self, "警告", "请先选择一个或多个寄存器")
                return
            register_names = [current_register]
        
        # 过滤掉不存在的寄存器
        valid_registers = []
        for reg_name in register_names:
            if (current_peripheral in self.state_manager.device_info.peripherals and
                reg_name in self.state_manager.device_info.peripherals[current_peripheral].registers):
                valid_registers.append(reg_name)
        
        if not valid_registers:
            QMessageBox.warning(self, "警告", "没有找到有效的寄存器")
            return
        
        # 确认删除
        if len(valid_registers) == 1:
            message = f"确定要删除寄存器 '{valid_registers[0]}' 吗？\n这将同时删除该寄存器下的所有位域。"
        else:
            message = f"确定要删除 {len(valid_registers)} 个寄存器吗？\n这将同时删除这些寄存器下的所有位域。\n\n寄存器列表: {', '.join(valid_registers[:5])}"
            if len(valid_registers) > 5:
                message += f" 等 {len(valid_registers)} 个寄存器"
        
        reply = QMessageBox.question(
            self, "确认批量删除",
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
        
        # 更新UI
        self.peripheral_manager.update_peripheral_tree()
        
        # 清除寄存器选择
        self.state_manager.set_selection(register=None, field=None)
        
        # 更新状态
        if deleted_count > 0:
            self.layout_manager.update_status(f"已批量删除 {deleted_count} 个寄存器")
            self.logger.info(f"批量删除 {deleted_count} 个寄存器")
        
        # 发射数据变化信号
        self.data_changed.emit()
    
    def add_field(self):
        """添加位域"""
        # 检查是否有选中的外设和寄存器
        current_peripheral = self.state_manager.get_current_peripheral()
        if not current_peripheral:
            QMessageBox.warning(self, "警告", "请先选择一个外设")
            return
        
        current_register = self.state_manager.get_current_register()
        if not current_register:
            QMessageBox.warning(self, "警告", "请先选择一个寄存器")
            return
        
        # 检查寄存器是否存在
        if (current_peripheral not in self.state_manager.device_info.peripherals or
            current_register not in self.state_manager.device_info.peripherals[current_peripheral].registers):
            QMessageBox.warning(self, "警告", f"寄存器 '{current_register}' 不存在")
            return
        
        # 创建对话框
        dialog = self.dialog_factory.create_field_dialog()
        
        if dialog.exec():
            result = getattr(dialog, "result_data", None)
            if result is None:
                return
            
            # 创建位域对象
            from ..core.data_model import Field
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
            self.layout_manager.update_status(f"已添加位域: {field.name}")
            self.logger.info(f"添加位域: {field.name}")
            
            # 发射数据变化信号
            self.data_changed.emit()
    
    def edit_field(self, field_name: str = None):
        """编辑位域"""
        # 如果没有提供位域名，尝试从当前选择获取
        if field_name is None:
            current_field = self.state_manager.get_current_field()
            if not current_field:
                QMessageBox.warning(self, "警告", "请先选择一个位域")
                return
            field_name = current_field
        
        # 检查是否有选中的外设和寄存器
        current_peripheral = self.state_manager.get_current_peripheral()
        if not current_peripheral:
            QMessageBox.warning(self, "警告", "请先选择一个外设")
            return
        
        current_register = self.state_manager.get_current_register()
        if not current_register:
            QMessageBox.warning(self, "警告", "请先选择一个寄存器")
            return
        
        # 检查位域是否存在
        if (current_peripheral not in self.state_manager.device_info.peripherals or
            current_register not in self.state_manager.device_info.peripherals[current_peripheral].registers or
            field_name not in self.state_manager.device_info.peripherals[current_peripheral].registers[current_register].fields):
            QMessageBox.warning(self, "警告", f"位域 '{field_name}' 不存在")
            return
        
        # 获取位域对象
        field = self.state_manager.device_info.peripherals[current_peripheral].registers[current_register].fields[field_name]
        
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
            from ..core.data_model import Field
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
            self.layout_manager.update_status(f"已更新位域: {new_name}")
            self.logger.info(f"编辑位域: {old_name} -> {new_name}")
            
            # 发射数据变化信号
            self.data_changed.emit()
    
    def delete_field(self, field_name: str = None):
        """删除位域"""
        # 如果没有提供位域名，尝试从当前选择获取
        if field_name is None:
            current_field = self.state_manager.get_current_field()
            if not current_field:
                QMessageBox.warning(self, "警告", "请先选择一个位域")
                return
            field_name = current_field
        
        # 检查是否有选中的外设和寄存器
        current_peripheral = self.state_manager.get_current_peripheral()
        if not current_peripheral:
            QMessageBox.warning(self, "警告", "请先选择一个外设")
            return
        
        current_register = self.state_manager.get_current_register()
        if not current_register:
            QMessageBox.warning(self, "警告", "请先选择一个寄存器")
            return
        
        # 检查位域是否存在
        if (current_peripheral not in self.state_manager.device_info.peripherals or
            current_register not in self.state_manager.device_info.peripherals[current_peripheral].registers or
            field_name not in self.state_manager.device_info.peripherals[current_peripheral].registers[current_register].fields):
            QMessageBox.warning(self, "警告", f"位域 '{field_name}' 不存在")
            return
        
        # 确认删除
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除位域 '{field_name}' 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # 使用StateManager删除位域
        self.state_manager.delete_field(current_peripheral, current_register, field_name)
        
        # 更新UI
        self.peripheral_manager.update_peripheral_tree()
        
        # 清除位域选择
        self.state_manager.set_selection(field=None)
        
        # 更新状态
        self.layout_manager.update_status(f"已删除位域: {field_name}")
        self.logger.info(f"删除位域: {field_name}")
        
        # 发射数据变化信号
        self.data_changed.emit()
    
    # ===================== 中断操作方法 =====================
    
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
            from ..core.data_model import Interrupt
            interrupt = Interrupt(
                name=result["name"],
                value=result["value"],  # 保持为int
                description=result["description"],
                peripheral=result["peripheral"]
            )
            
            # 使用StateManager添加中断
            self.state_manager.add_interrupt(interrupt)
            
            # 更新中断表格
            self._update_interrupt_table()
            
            # 更新状态
            self.layout_manager.update_status(f"已添加中断: {interrupt.name}")
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
                QMessageBox.warning(self, "警告", "中断表格未找到")
                return
                
            selected_rows = irq_table.selectedItems()
            if not selected_rows:
                QMessageBox.warning(self, "警告", "请先选择一个中断")
                return
                
            # 获取第一列（名称列）的文本
            interrupt_name = selected_rows[0].text()
        
        # 检查中断是否存在
        if interrupt_name not in self.state_manager.device_info.interrupts:
            QMessageBox.warning(self, "警告", f"中断 '{interrupt_name}' 不存在")
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
            from ..core.data_model import Interrupt
            updated_interrupt = Interrupt(
                name=new_name,
                value=result["value"],  # 保持为int
                description=result["description"],
                peripheral=result["peripheral"]
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
            self.layout_manager.update_status(f"已更新中断: {new_name}")
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
                QMessageBox.warning(self, "警告", "中断表格未找到")
                return
                
            selected_rows = irq_table.selectedItems()
            if not selected_rows:
                QMessageBox.warning(self, "警告", "请先选择一个中断")
                return
                
            # 获取第一列（名称列）的文本
            interrupt_name = selected_rows[0].text()
        
        # 检查中断是否存在
        if interrupt_name not in self.state_manager.device_info.interrupts:
            QMessageBox.warning(self, "警告", f"中断 '{interrupt_name}' 不存在")
            return
        
        # 确认删除
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除中断 '{interrupt_name}' 吗？",
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
        self.layout_manager.update_status(f"已删除中断: {interrupt_name}")
        self.logger.info(f"删除中断: {interrupt_name}")
        
        # 发射数据变化信号
        self.data_changed.emit()
    
    def _update_interrupt_table(self):
        """更新中断表格"""
        irq_table = self.layout_manager.widgets.get('irq_table')
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
            irq_table.setItem(i, 0, QTableWidgetItem(interrupt.name))
            irq_table.setItem(i, 1, QTableWidgetItem(str(interrupt.value)))
            irq_table.setItem(i, 2, QTableWidgetItem(interrupt.peripheral or ""))
            irq_table.setItem(i, 3, QTableWidgetItem(interrupt.description or ""))
    
    def on_irq_context_menu(self, pos):
        """中断表格右键菜单"""
        irq_table = self.layout_manager.widgets.get('irq_table')
        if not irq_table:
            return
        
        item = irq_table.itemAt(pos)
        if not item:
            return
        
        row = item.row()
        interrupt_name = irq_table.item(row, 0).text()
        
        # 创建右键菜单
        menu = QMenu()
        
        edit_action = menu.addAction("编辑中断")
        delete_action = menu.addAction("删除中断")
        
        # 执行菜单动作
        action = menu.exec(irq_table.mapToGlobal(pos))
        if action == edit_action:
            self.edit_interrupt(interrupt_name)
        elif action == delete_action:
            self.delete_interrupt(interrupt_name)

    # ===================== 日志面板相关 =====================
    class _LogSignalEmitter(QObject):
        append_text = pyqtSignal(str)

    def create_log_panel(self):
        """创建可切换的日志面板并绑定日志处理器"""
        # 如果日志面板已存在，直接返回
        if hasattr(self, 'log_dock') and self.log_dock:
            return
        
        # 日志停靠窗口
        self.log_dock = QDockWidget("日志", self)
        self.log_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.TopDockWidgetArea)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        
        # 使用容器放置操作按钮和文本区
        container = QWidget()
        container_layout = QVBoxLayout(container)
        
        # 顶部工具栏：按钮和复选框
        toolbar = QHBoxLayout()
        
        clear_btn = QPushButton("清空日志")
        clear_btn.clicked.connect(self.clear_log)
        toolbar.addWidget(clear_btn)
        
        save_btn = QPushButton("保存日志")
        save_btn.clicked.connect(self.save_log_to_file)
        toolbar.addWidget(save_btn)
        
        toolbar.addStretch()
        
        # 添加"显示Debug日志"复选框
        self.show_debug_checkbox = QCheckBox("显示Debug日志")
        self.show_debug_checkbox.setChecked(False)  # 默认不显示debug日志
        self.show_debug_checkbox.stateChanged.connect(self.on_debug_log_checkbox_changed)
        toolbar.addWidget(self.show_debug_checkbox)
        
        container_layout.addLayout(toolbar)
        container_layout.addWidget(self.log_text)
        self.log_dock.setWidget(container)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)
        self.log_dock.hide()

        # 日志信号和处理器
        self._log_emitter = MainWindowRefactored._LogSignalEmitter()
        self._log_emitter.append_text.connect(self._append_log_text)

        class GuiLogHandler(logging.Handler):
            def __init__(self, emitter, owner=None):
                super().__init__()
                self.emitter = emitter
                self.owner = owner
                self.setLevel(logging.DEBUG)

            def emit(self, record):
                try:
                    msg = self.format(record)
                    # 通过信号在主线程追加文本
                    self.emitter.append_text.emit(msg)

                    # 如果是错误级别且启用了自动保存，则把日志写入文件（包含当前面板内容）
                    try:
                        if (hasattr(self, 'owner') and self.owner is not None and
                                getattr(self.owner, 'auto_save_error', False) and
                                record.levelno >= logging.ERROR):
                            logs_dir = os.path.join(os.getcwd(), 'logs')
                            os.makedirs(logs_dir, exist_ok=True)
                            fname = datetime.now().strftime('svd_error_%Y%m%d_%H%M%S.log')
                            path = os.path.join(logs_dir, fname)
                            existing = ''
                            if hasattr(self.owner, 'log_text') and self.owner.log_text:
                                existing = self.owner.log_text.toPlainText()
                            with open(path, 'w', encoding='utf-8') as f:
                                f.write(existing + '\n' + msg)
                    except Exception:
                        pass  # 文件保存失败不影响主流程
                except Exception:
                    pass  # 日志显示失败不影响主流程

        self._gui_log_handler = GuiLogHandler(self._log_emitter, self)
        self.logger.logger.addHandler(self._gui_log_handler)
        
        # 创建日志面板后，在init_ui中调用
        self.logger.info("日志面板已创建")

    def _append_log_text(self, text: str):
        """在日志文本框中追加文本（线程安全）"""
        if hasattr(self, 'log_text') and self.log_text:
            self.log_text.append(text)
            # 自动滚动到底部
            scrollbar = self.log_text.verticalScrollBar()
            if scrollbar:
                scrollbar.setValue(scrollbar.maximum())

    def on_debug_log_checkbox_changed(self, state):
        """处理Debug日志复选框状态变化"""
        show_debug = (state == Qt.CheckState.Checked.value)
        # 更新日志记录器的控制台级别
        self.logger.enable_debug_logs(show_debug)
        # 更新GUI日志处理器的过滤级别
        if hasattr(self, '_gui_log_handler') and self._gui_log_handler is not None:
            if show_debug:
                self._gui_log_handler.setLevel(logging.DEBUG)
            else:
                self._gui_log_handler.setLevel(logging.INFO)
        # 更新状态显示
        status_msg = "Debug日志已启用" if show_debug else "Debug日志已禁用"
        self.layout_manager.update_status(status_msg)
        self.logger.info(status_msg)

    def clear_log(self):
        """清空日志面板内容"""
        try:
            if hasattr(self, 'log_text') and self.log_text:
                self.log_text.clear()
                self.layout_manager.update_status("日志已清空")
                self.logger.info("日志面板已清空")
        except Exception as e:
            self.logger.error(f"清空日志时出错: {str(e)}")

    def save_log_to_file(self):
        """手动保存当前日志到文件（弹出保存对话框）"""
        try:
            if not hasattr(self, 'log_text') or not self.log_text:
                QMessageBox.warning(self, "警告", "日志面板未创建")
                return
            
            log_content = self.log_text.toPlainText()
            if not log_content.strip():
                QMessageBox.warning(self, "警告", "日志内容为空")
                return
            
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存日志", "svd_log.txt", "文本文件 (*.txt);;所有文件 (*.*)"
            )
            
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(log_content)
                
                self.layout_manager.update_status(f"日志已保存到: {file_path}")
                self.logger.info(f"日志已保存到: {file_path}")
                QMessageBox.information(self, "成功", "日志保存成功")
                
        except Exception as e:
            self.logger.error(f"保存日志时出错: {str(e)}")
            QMessageBox.warning(self, "错误", f"保存日志时出错:\n{str(e)}")

    def toggle_log_panel(self, checked: bool):
        """切换日志面板显示/隐藏"""
        try:
            if not hasattr(self, 'log_dock') or not self.log_dock:
                # 如果日志面板不存在，先创建
                try:
                    self.create_log_panel()
                except Exception:
                    QMessageBox.warning(self, "错误", "创建日志面板失败")
                    return
            
            if checked:
                self.log_dock.show()
                self.layout_manager.update_status("日志面板已显示")
            else:
                self.log_dock.hide()
                self.layout_manager.update_status("日志面板已隐藏")
                
        except Exception as e:
            self.logger.error(f"切换日志面板时出错: {str(e)}")

    def validate_data(self):
        """验证数据"""
        try:
            # 使用StateManager的验证功能
            validation_result = self.state_manager.validate_and_get_summary()
            
            if validation_result['valid']:
                QMessageBox.information(self, "验证通过", "所有数据验证通过！")
                self.layout_manager.update_status("数据验证通过")
            else:
                # 构建错误消息
                error_count = validation_result['error_count']
                errors = validation_result['errors']
                
                error_message = f"数据验证失败，发现 {error_count} 个错误：\n\n"
                for i, error in enumerate(errors[:10], 1):  # 最多显示10个错误
                    error_message += f"{i}. {error}\n"
                
                if error_count > 10:
                    error_message += f"\n... 还有 {error_count - 10} 个错误未显示"
                
                QMessageBox.warning(self, "验证失败", error_message)
                self.layout_manager.update_status(f"数据验证失败，发现 {error_count} 个错误")
                
        except Exception as e:
            self.logger.error(f"验证过程中发生错误: {str(e)}")
            QMessageBox.warning(self, "验证错误", f"验证过程中发生错误:\n{str(e)}")
            self.layout_manager.update_status("验证过程出错")
    
    def show_about(self):
        """显示关于对话框"""
        about_text = """
        <h2>SVD工具 - 重构版</h2>
        <p>版本: 2.1 (重构架构)</p>
        <p>一个强大的SVD文件生成和解析工具</p>
        <p>功能特性:</p>
        <ul>
            <li>可视化编辑SVD文件</li>
            <li>支持外设、寄存器、位域三级结构</li>
            <li>支持中断配置</li>
            <li>支持撤消/重做操作</li>
            <li>支持搜索功能</li>
            <li>支持导入/导出SVD文件</li>
            <li>支持多种SVD版本(1.1, 1.3, 2.0)</li>
            <li>组件化架构，提高可维护性</li>
        </ul>
        <p>© 2025 SVD工具开发者@SamyiHu</p>
        """
        
        # 创建日志面板（如果不存在）
        if not hasattr(self, 'log_dock') or not self.log_dock:
            self.create_log_panel()
        
        QMessageBox.about(self, "关于SVD工具", about_text)
        self.logger.info("显示关于对话框")
    
    def move_item_up(self):
        """上移选中项目（只支持外设）"""
        try:
            # 使用PeripheralManager的移动功能
            if hasattr(self, 'peripheral_manager'):
                self.peripheral_manager.move_selected_peripheral_up()
            else:
                self.show_message("功能不可用", "外设管理器未初始化", 'warning')
        except Exception as e:
            self.logger.error(f"上移项目时出错: {str(e)}")
            self.show_message("操作失败", f"上移项目时发生错误: {str(e)}", 'error')
    
    def move_item_down(self):
        """下移选中项目（只支持外设）"""
        try:
            # 使用PeripheralManager的移动功能
            if hasattr(self, 'peripheral_manager'):
                self.peripheral_manager.move_selected_peripheral_down()
            else:
                self.show_message("功能不可用", "外设管理器未初始化", 'warning')
        except Exception as e:
            self.logger.error(f"下移项目时出错: {str(e)}")
            self.show_message("操作失败", f"下移项目时发生错误: {str(e)}", 'error')
    
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
        try:
            # 获取设备信息对象
            device_info = self.state_manager.device_info
            
            # 获取布局管理器中的控件
            layout = self.layout_manager
            
            # 更新基本信息
            ic_name_edit = layout.get_widget('ic_name_edit')
            if ic_name_edit:
                device_info.name = ic_name_edit.text().strip()
            
            ic_desc_edit = layout.get_widget('ic_desc_edit')
            if ic_desc_edit:
                device_info.description = ic_desc_edit.text().strip()
            
            version_edit = layout.get_widget('version_edit')
            if version_edit:
                device_info.version = version_edit.text().strip()
            
            svd_version_combo = layout.get_widget('svd_version_combo')
            if svd_version_combo:
                device_info.svd_version = svd_version_combo.currentText()
            
            # 更新CPU信息
            cpu_name_edit = layout.get_widget('cpu_name_edit')
            if cpu_name_edit:
                device_info.cpu.name = cpu_name_edit.text().strip()
            
            cpu_rev_edit = layout.get_widget('cpu_rev_edit')
            if cpu_rev_edit:
                device_info.cpu.revision = cpu_rev_edit.text().strip()
            
            endian_combo = layout.get_widget('endian_combo')
            if endian_combo:
                device_info.cpu.endian = endian_combo.currentText()
            
            mpu_combo = layout.get_widget('mpu_combo')
            if mpu_combo:
                mpu_text = mpu_combo.currentText()
                device_info.cpu.mpu_present = (mpu_text == "是")
            
            fpu_combo = layout.get_widget('fpu_combo')
            if fpu_combo:
                fpu_text = fpu_combo.currentText()
                device_info.cpu.fpu_present = (fpu_text == "是")
            
            nvic_prio_spin = layout.get_widget('nvic_prio_spin')
            if nvic_prio_spin:
                device_info.cpu.nvic_prio_bits = nvic_prio_spin.value()
            
            # 更新公司版权信息
            company_name_edit = layout.get_widget('company_name_edit')
            if company_name_edit:
                device_info.vendor = company_name_edit.text().strip()
            
            copyright_edit = layout.get_widget('copyright_edit')
            if copyright_edit:
                device_info.copyright = copyright_edit.text().strip()
            
            # 处理作者字段（考虑"不显示"复选框）
            author_edit = layout.get_widget('author_edit')
            author_checkbox = layout.get_widget('author_checkbox')
            if author_edit and author_checkbox:
                if author_checkbox.isChecked():
                    # 如果勾选了"不显示"，则清空作者字段
                    device_info.author = ""
                else:
                    device_info.author = author_edit.text().strip()
            elif author_edit:
                # 如果没有复选框，则直接获取文本
                device_info.author = author_edit.text().strip()
            
            # 处理许可证字段（考虑"不显示"选项）
            license_combo = layout.get_widget('license_combo')
            if license_combo:
                license_text = license_combo.currentText()
                if license_text == "不显示":
                    # 如果选择了"不显示"，则清空许可证字段
                    device_info.license = ""
                else:
                    device_info.license = license_text
            
            self.logger.debug("设备信息已从UI更新")
            
        except Exception as e:
            self.logger.error(f"更新设备信息时出错: {str(e)}")

    def update_data_model_from_tree(self):
        """从树控件更新数据模型"""
        self.logger.info("更新数据模型以反映树结构调整...")
        
        try:
            # 获取树控件
            periph_tree = self.layout_manager.get_widget('periph_tree')
            if not periph_tree:
                return
            
            # 临时保存原始数据，以防恢复需要
            device_info = self.state_manager.device_info
            original_peripherals = device_info.peripherals.copy()
            
            # 创建新的外设字典，按照树中的顺序
            new_peripherals = {}
            
            for i in range(periph_tree.topLevelItemCount()):
                periph_item = periph_tree.topLevelItem(i)
                if periph_item is None:
                    continue
                periph_name = self.tree_manager.get_item_name(periph_item)
                periph_type = self.tree_manager.get_item_type(periph_item)
                
                # 验证项目类型
                if periph_type != "peripheral":
                    self.logger.warning(f"发现非外设项目在顶级: {periph_name}")
                    continue
                    
                if periph_name in original_peripherals:
                    peripheral = original_peripherals[periph_name]
                    
                    # 更新寄存器的顺序
                    new_registers = {}
                    for j in range(periph_item.childCount()):
                        reg_item = periph_item.child(j)
                        if reg_item is None:
                            continue
                        reg_name = self.tree_manager.get_item_name(reg_item)
                        reg_type = self.tree_manager.get_item_type(reg_item)
                        
                        # 验证项目类型
                        if reg_type != "register":
                            self.logger.warning(f"在外设 {periph_name} 中发现非寄存器项目: {reg_name}")
                            continue
                            
                        if reg_name in peripheral.registers:
                            register = peripheral.registers[reg_name]
                            
                            # 更新位域的顺序
                            new_fields = {}
                            for k in range(reg_item.childCount()):
                                field_item = reg_item.child(k)
                                if field_item is None:
                                    continue
                                field_name = self.tree_manager.get_item_name(field_item)
                                field_type = self.tree_manager.get_item_type(field_item)
                                
                                # 验证项目类型
                                if field_type != "field":
                                    self.logger.warning(f"在寄存器 {reg_name} 中发现非位域项目: {field_name}")
                                    continue
                                    
                                if field_name in register.fields:
                                    new_fields[field_name] = register.fields[field_name]
                                else:
                                    self.logger.warning(f"位域 {field_name} 不在寄存器 {reg_name} 中")
                            
                            register.fields = new_fields
                            new_registers[reg_name] = register
                        else:
                            self.logger.warning(f"寄存器 {reg_name} 不在外设 {periph_name} 中")
                    
                    peripheral.registers = new_registers
                    new_peripherals[periph_name] = peripheral
                else:
                    self.logger.warning(f"外设 {periph_name} 不在数据模型中")
            
            # 更新设备信息
            device_info.peripherals = new_peripherals
            
            # 更新状态栏
            self.layout_manager.update_status("已调整外设顺序")
            
            # 触发数据变化通知
            self.state_manager._notify_state_change()
            
            self.logger.info("数据模型更新完成")
            
        except Exception as e:
            self.logger.error(f"更新数据模型时出错: {str(e)}")
            import traceback
            traceback.print_exc()

    def closeEvent(self, event):
        """关闭事件"""
        # 可以在这里添加保存确认逻辑
        event.accept()


def main():
    """主函数"""
    app = QApplication(sys.argv)
    window = MainWindowRefactored()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()