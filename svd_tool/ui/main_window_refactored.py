"""
重构后的主窗口
使用组件化架构，提高可维护性
"""
import sys
import os
import copy
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
from .components.preview_manager import PreviewManager
from .managers.file_operations import FileOperations
from .managers.device_info_manager import DeviceInfoManager
from .managers.search_manager import SearchManager
from .managers.batch_operations_manager import BatchOperationsManager
from .coordinator import Coordinator
from ..i18n.i18n import I18nManager, get_i18n_manager, set_i18n_manager, t

from ..utils.helpers import pretty_xml, format_hex
from ..utils.logger import Logger
from ..core.chain_rules import ChainRulesEngine
from ..core.address_conflict_detector import AddressConflictDetector, ConflictType, ConflictSeverity
from ..core.document_manager import DocumentManager, DocumentState


class MainWindowRefactored(QMainWindow):
    """重构后的主窗口"""
    
    # 信号定义
    data_changed = pyqtSignal()
    selection_changed = pyqtSignal(str, str)  # (item_type, item_name)
    
    def __init__(self):
        import sys
        super().__init__()
        # 初始化日志（必须在其他组件之前）
        self.logger = Logger("svd_tool")
        # 在调用父类构造函数之后设置窗口属性，防止窗口在初始化时显示
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.logger.debug(f"__init__开始，窗口大小: {self.size()}")
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, False)
        
        # 初始化协调器
        self.coordinator = Coordinator()
        
        
        # 初始化国际化管理器
        self.i18n_manager = I18nManager()
        set_i18n_manager(self.i18n_manager)
        
        # 初始化组件
        self.state_manager = StateManager()
        self.layout_manager = LayoutManager(self)
        self.peripheral_manager = PeripheralManager(self.state_manager, self.layout_manager)
        
        # 注意：不再创建独立的 command_history，使用 state_manager.command_history
        self.tree_manager = TreeManager()
        self.dialog_factory = DialogFactory(self)
        
        # 初始化文件操作管理器
        self.file_operations = FileOperations(self.state_manager, self.layout_manager)
        self.device_info_manager = DeviceInfoManager(coordinator=self.coordinator)
        
        # 初始化预览管理器
        self.preview_manager = PreviewManager(self, self.state_manager, self.coordinator)
        # 连接预览可见性变化信号，同步菜单勾选状态
        self.preview_manager.preview_visibility_changed.connect(self._on_preview_visibility_changed)
        
        # 初始化搜索管理器
        self.search_manager = SearchManager(coordinator=self.coordinator)
        
        # 预览窗口（延迟创建，保留兼容性）
        self.preview_window = None
        
        # 注册组件到协调器
        self.coordinator.register_component('state_manager', self.state_manager)
        self.coordinator.register_component('layout_manager', self.layout_manager)
        self.coordinator.register_component('peripheral_manager', self.peripheral_manager)
        self.coordinator.register_component('device_info_manager', self.device_info_manager)
        self.coordinator.register_component('file_operations', self.file_operations)
        self.coordinator.register_component('preview_manager', self.preview_manager)
        self.coordinator.register_component('search_manager', self.search_manager)
        
        # 初始化连锁规则引擎
        self.chain_rules_engine = ChainRulesEngine()
        # 自动加载项目根目录下的 chain_rules.json
        _chain_rules_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'chain_rules.json')
        if os.path.exists(_chain_rules_path):
            self.chain_rules_engine.set_rule_file(_chain_rules_path)
            self.logger.info(f"已加载连锁规则文件: {_chain_rules_path} ({len(self.chain_rules_engine.rules)}条规则)")
        
        # GUI 日志处理器
        self._gui_log_handler = None
        self.auto_save_error = True
        
        # 初始化地址冲突检测器
        self.conflict_detector = AddressConflictDetector()
        
        # 初始化多文档管理器
        self.document_manager = DocumentManager(self)
        
        self.init_ui()
        self.logger.debug(f"init_ui完成，窗口大小: {self.size()}")
        self.init_data()
        self.setup_signals()
        
        # 启用拖放功能
        self.enable_tree_drag_drop()
        
        # 应用样式
        self.apply_styles()
        self.logger.debug(f"__init__完成，窗口大小: {self.size()}")
    
    def init_ui(self):
        """初始化UI"""
        self.logger.debug(f"init_ui开始，layout_manager={self.layout_manager}，窗口大小: {self.size()}")
        # 使用布局管理器创建UI
        widgets = self.layout_manager.create_layout()
        self.logger.debug(f"create_layout返回，widgets keys={list(widgets.keys())}")
        
        # 获取主分割器和标签页
        main_splitter = widgets.get('main_splitter')
        tab_widget = widgets.get('tab_widget')
        self.logger.debug(f"获取tab_widget: {tab_widget}")
        self.logger.debug(f"获取main_splitter: {main_splitter}")
        self.logger.debug(f"tab_widget is None: {tab_widget is None}")
        if tab_widget is not None:
            try:
                self.logger.debug("创建基本标签页")
                self.layout_manager.create_basic_info_tab(tab_widget)
                self.logger.debug("创建外设标签页")
                self.layout_manager.create_peripheral_tab(tab_widget)
                self.logger.debug("创建中断标签页")
                self.layout_manager.create_interrupt_tab(tab_widget)
                # 设置预览管理器（支持多种显示模式）
                self.logger.debug("设置预览管理器")
                self.preview_manager.setup_preview_modes(tab_widget, main_splitter)
                self.logger.debug("预览管理器设置完成")
            except Exception as e:
                self.logger.error(f"创建标签页时发生异常: {e}")
                self.logger.exception("Traceback:")
            
            # 设置默认标签页
            tab_widget.setCurrentIndex(0)
            self.logger.debug(f"标签页数量: {tab_widget.count()}")
        else:
            self.logger.debug("tab_widget 为 None，无法创建标签页")
        
        # 连接外设管理器的信号
        self.peripheral_manager.peripheral_added.connect(self.on_peripheral_added)
        self.peripheral_manager.peripheral_updated.connect(self.on_peripheral_updated)
        self.peripheral_manager.peripheral_deleted.connect(self.on_peripheral_deleted)
        self.peripheral_manager.selection_changed.connect(self.on_selection_changed)
        
        # 连接UI按钮信号（必须在标签页创建后）
        self.peripheral_manager.connect_ui_signals()
        
        # 创建日志面板（默认隐藏）
        self.logger.debug(f"创建日志面板，窗口大小: {self.size()}")
        self.create_log_panel()
        self.logger.debug(f"init_ui完成，窗口大小: {self.size()}")
        
        # 初始化中断表格（如果有数据）
        self._update_interrupt_table()
        
        # 设置多文档标签栏
        self.layout_manager.setup_document_tab_bar(self.document_manager)
        tab_bar = self.layout_manager.get_document_tab_bar()
        if tab_bar:
            tab_bar.tab_clicked.connect(self._on_document_tab_clicked)
            tab_bar.tab_close_requested.connect(self._on_document_tab_close)
            tab_bar.close_others_requested.connect(self._on_close_others)
            tab_bar.close_all_requested.connect(self._on_close_all)
            tab_bar.new_tab_requested.connect(self.new_file)
            # 比较标签信号
            tab_bar.diff_tab_clicked.connect(self._on_diff_tab_clicked)
            tab_bar.diff_tab_close_requested.connect(self._on_diff_tab_close)
        
        # 比较视图存储: diff_id -> DiffViewWidget
        self._diff_views = {}
        self._active_diff_id = None
        
        # 连接文档管理器的所有关闭信号
        self.document_manager.all_documents_closed.connect(self._on_all_documents_closed_show_welcome)
    
    def _save_current_document_state(self):
        """保存当前文档的UI状态到DocumentManager"""
        doc = self.document_manager.active_document
        if not doc:
            return
        
        # 保存选择状态
        selection = self.state_manager.get_selection()
        doc.selection = selection.copy()
        
        # 保存树展开状态
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if periph_tree:
            expanded_periphs = {}
            expanded_regs = {}
            for i in range(periph_tree.topLevelItemCount()):
                periph_item = periph_tree.topLevelItem(i)
                periph_name = periph_item.text(0)
                expanded_periphs[periph_name] = periph_item.isExpanded()
                for j in range(periph_item.childCount()):
                    reg_item = periph_item.child(j)
                    reg_key = f"{periph_name}/{reg_item.text(0)}"
                    expanded_regs[reg_key] = reg_item.isExpanded()
            doc.tree_expanded_periphs = expanded_periphs
            doc.tree_expanded_regs = expanded_regs
        
        # 保存当前标签页索引
        tab_widget = self.layout_manager.get_widget('tab_widget')
        if tab_widget:
            doc.current_tab_index = tab_widget.currentIndex()
        
        # 保存中断表滚动位置
        irq_table = self.layout_manager.get_widget('irq_table')
        if irq_table:
            doc.irq_table_scroll = irq_table.verticalScrollBar().value()
        
        # 仅在数据被修改时才深拷贝（大幅减少切换文档时的开销）
        if doc.modified or doc.device_info is None:
            doc.device_info = copy.deepcopy(self.state_manager.device_info)
        else:
            # 未修改时直接引用（文档切换时不会修改 device_info）
            doc.device_info = self.state_manager.device_info
        
        # 保存命令历史（每个文档独立维护撤销/重做栈）
        doc.command_history = self.state_manager.command_history
        
        # 保存预览器折叠状态和选中状态
        if self.preview_manager and self.preview_manager.preview_widget:
            pw = self.preview_manager.preview_widget
            doc.preview_folded_elements = set(pw.folded_elements)
            if hasattr(pw, 'current_selection'):
                doc.preview_selection = dict(pw.current_selection)
    
    def _restore_document_state(self, doc: 'DocumentState'):
        """从DocumentState恢复文档的UI状态（优化：减少不必要的UI刷新）"""
        if not doc:
            return
        
        # 暂停通知，避免恢复过程中多次触发UI刷新
        self.state_manager.pause_notifications()
        
        try:
            # 恢复设备数据
            # 如果文档未修改，doc.device_info 就是 state_manager 原来的引用，可以直接使用
            # 如果文档已修改，doc.device_info 是之前保存时的深拷贝，需要再拷贝一份保证隔离
            if doc.modified:
                self.state_manager.device_info = copy.deepcopy(doc.device_info)
            else:
                # 未修改时直接使用引用（_save_current_document_state 保证了数据一致性）
                self.state_manager.device_info = doc.device_info
            
            # 恢复命令历史（每个文档独立维护撤销/重做栈）
            if doc.command_history is not None:
                self.state_manager.command_history = doc.command_history
            
            self.state_manager.clear_selection()
            
            # 恢复树（单次重建，不保留旧文档的展开状态）
            self.peripheral_manager.update_peripheral_tree(preserve_expanded=False)
            
            # 恢复树展开状态
            periph_tree = self.layout_manager.get_widget('periph_tree')
            if periph_tree:
                periph_tree.blockSignals(True)
                for i in range(periph_tree.topLevelItemCount()):
                    periph_item = periph_tree.topLevelItem(i)
                    periph_name = periph_item.text(0)
                    if doc.tree_expanded_periphs.get(periph_name, False):
                        periph_item.setExpanded(True)
                    for j in range(periph_item.childCount()):
                        reg_item = periph_item.child(j)
                        reg_key = f"{periph_name}/{reg_item.text(0)}"
                        if doc.tree_expanded_regs.get(reg_key, False):
                            reg_item.setExpanded(True)
                periph_tree.blockSignals(False)
            
            # 恢复选择
            if doc.selection:
                sel = doc.selection
                self.state_manager.set_selection(
                    peripheral=sel.get('peripheral'),
                    register=sel.get('register'),
                    field=sel.get('field'),
                    element_type=sel.get('element_type')
                )
                # 在树中选中对应项
                if sel.get('peripheral'):
                    self.peripheral_manager.select_peripheral(sel['peripheral'])
                    if sel.get('register'):
                        self.peripheral_manager.select_register(sel['peripheral'], sel['register'])
            
            # 恢复标签页索引
            tab_widget = self.layout_manager.get_widget('tab_widget')
            if tab_widget and doc.current_tab_index < tab_widget.count():
                tab_widget.setCurrentIndex(doc.current_tab_index)
            
            # 恢复中断表滚动位置
            irq_table = self.layout_manager.get_widget('irq_table')
            if irq_table:
                irq_table.verticalScrollBar().setValue(doc.irq_table_scroll)
            
            # 批量更新UI（只刷新一次）
            self.update_data_stats()
            self._update_interrupt_table()
            if hasattr(self.layout_manager, 'update_basic_info'):
                self.layout_manager.update_basic_info(doc.device_info)
            
            self.update_visualization(
                (doc.selection or {}).get('peripheral') or '',
                (doc.selection or {}).get('register') or '',
                (doc.selection or {}).get('field') or ''
            )
            
            # 恢复预览器状态（折叠状态和选中状态）
            if self.preview_manager and self.preview_manager.preview_widget:
                pw = self.preview_manager.preview_widget
                # 恢复折叠状态
                pw.folded_elements = set(doc.preview_folded_elements)
                # 恢复选中状态
                if hasattr(pw, 'current_selection'):
                    pw.current_selection = dict(doc.preview_selection)
                # 清除预览高亮，避免残留
                if hasattr(pw, 'preview_edit') and pw.preview_edit:
                    pw.preview_edit.clear_highlight()
                # 刷新预览内容（使用新文档的数据）
                pw.refresh_preview(immediate=True)
                # 如果有选中状态，重新应用高亮
                if doc.preview_selection.get('type') and hasattr(pw, '_apply_highlight'):
                    pw._apply_highlight()
                    pw.jump_to_selection()
        finally:
            # 恢复通知前，标记跳过下一次树重建（避免 resume_notifications 触发的
            # on_state_changed 再次重建树——我们在上面已经重建过了）
            self.peripheral_manager._skip_next_tree_rebuild = True
            self.state_manager.resume_notifications()
        
        # 重新应用树选中状态
        if doc and doc.selection:
            sel = doc.selection
            periph = sel.get('peripheral')
            reg = sel.get('register')
            if periph:
                if reg:
                    self.peripheral_manager.select_register(periph, reg)
                else:
                    self.peripheral_manager.select_peripheral(periph)
    
    def _on_document_tab_clicked(self, doc_id: str):
        """文档标签点击 - 切换文档（保存旧状态，恢复新状态）"""
        # 如果点击的是当前活动文档，且没有在对比视图中，忽略
        if doc_id == self.document_manager.active_doc_id and self._active_diff_id is None:
            return
        
        # 保存当前文档状态
        self._save_current_document_state()
        
        # 清除活动diff ID（切换到文档模式）
        self._active_diff_id = None
        
        # 切换文档
        self.document_manager.switch_to(doc_id)
        doc = self.document_manager.get_document(doc_id)
        if doc:
            self._restore_document_state(doc)
        
        # 确保editor_stack显示正常编辑器（页面0）
        editor_stack = self.layout_manager.get_widget('editor_stack')
        if editor_stack:
            editor_stack.setCurrentIndex(0)
    
    def _on_document_tab_close(self, doc_id: str):
        """文档标签关闭请求"""
        doc = self.document_manager.get_document(doc_id)
        if doc and doc.modified:
            reply = QMessageBox.question(self, "关闭文档",
                f"文档 '{doc.display_name}' 有未保存的修改，确定关闭吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.document_manager.close_document(doc_id)
    
    def _on_close_others(self, keep_doc_id: str):
        """关闭其他文档"""
        # 先保存当前文档状态
        self._save_current_document_state()
        
        for doc_id in self.document_manager.document_ids[:]:
            if doc_id != keep_doc_id:
                self.document_manager.close_document(doc_id)
        
        # 确保留下的文档被激活并恢复其状态
        doc = self.document_manager.get_document(keep_doc_id)
        if doc:
            if self.document_manager.active_doc_id != keep_doc_id:
                self.document_manager.switch_to(keep_doc_id)
            self._restore_document_state(doc)
    
    def _on_close_all(self):
        """关闭所有文档"""
        # 保存当前文档状态
        self._save_current_document_state()
        self.document_manager.clear_all()
    
    def _on_all_documents_closed_show_welcome(self):
        """所有文档关闭时，切换回欢迎页"""
        self.layout_manager.show_welcome()
        self.layout_manager.update_status("所有文档已关闭")
    
    def init_data(self):
        """初始化数据"""
        # 可以在这里加载默认数据或上次保存的数据
        pass
    
    def setup_signals(self):
        """设置信号连接"""
        # ===== 欢迎页信号连接 =====
        welcome_page = self.layout_manager.get_widget('welcome_page')
        if welcome_page:
            welcome_page.new_file_requested.connect(self.new_file)
            welcome_page.open_file_requested.connect(self.open_svd_file)
            welcome_page.open_recent_requested.connect(self._open_recent_file)
        
        # 连接搜索功能（使用search_manager）
        self.search_manager.connect_search_signals()
        
        # 连接其他按钮
        generate_btn = self.layout_manager.get_widget('generate_btn')
        if generate_btn:
            generate_btn.clicked.connect(self.generate_svd)
        
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
            # 连接树折叠/展开信号到预览同步
            periph_tree.itemCollapsed.connect(self._on_tree_item_collapsed)
            periph_tree.itemExpanded.connect(self._on_tree_item_expanded)
        
        # 连接可视化控件信号
        visualization_widget = self.layout_manager.get_widget('visualization_widget')
        if visualization_widget:
            self.logger.debug(f"visualization_widget type: {type(visualization_widget)}")
            self.logger.debug(f"visualization_widget has jump_to_peripheral: {hasattr(visualization_widget, 'jump_to_peripheral')}")
            self.logger.debug(f"on_jump_to_peripheral method: {self.on_jump_to_peripheral}")
            self.logger.debug(f"visualization_widget.jump_to_peripheral: {visualization_widget.jump_to_peripheral}")
            
            # 设置 main_window 引用
            visualization_widget.main_window = self
            self.logger.debug("Set visualization_widget.main_window")
            
            visualization_widget.bit_field.field_clicked.connect(self.on_field_clicked)
            visualization_widget.address_map.register_clicked.connect(self.on_register_clicked)
            if hasattr(visualization_widget, 'jump_to_peripheral'):
                self.logger.debug("Connecting jump_to_peripheral signal...")
                visualization_widget.jump_to_peripheral.connect(self.on_jump_to_peripheral)
                self.logger.debug("jump_to_peripheral signal connected")
                self.logger.debug(f"Signal receivers: {visualization_widget.jump_to_peripheral}")
            else:
                self.logger.debug("jump_to_peripheral signal NOT found")
        
        # 连接中断表格右键菜单和选择变化
        irq_table = self.layout_manager.get_widget('irq_table')
        if irq_table:
            irq_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            irq_table.customContextMenuRequested.connect(self.on_irq_context_menu)
            # 连接选择变化信号以更新按钮状态
            irq_table.itemSelectionChanged.connect(self.update_interrupt_buttons_state)
        
        # 连接位域表格双击编辑 + 选择联动
        field_table = self.layout_manager.get_widget('field_table')
        if field_table:
            field_table.doubleClicked.connect(self.on_field_table_double_clicked)
            # 位域表格行选择 → 高亮位域图
            field_table.itemSelectionChanged.connect(self.on_field_table_selection_changed)
        
        # 连接紧凑模式复选框
        compact_tree_cb = self.layout_manager.get_widget('compact_tree_cb')
        if compact_tree_cb:
            compact_tree_cb.stateChanged.connect(self.on_compact_tree_changed)
        
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
        
        # 设置地址冲突实时检测
        self._setup_conflict_detection()
    
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
    
    def _on_main_window_selection_changed(self, item_type: str, item_name: str):
        """主窗口选择变化时更新预览"""
        # 使用预览管理器更新预览
        selection = self.state_manager.get_selection()
        self.preview_manager.highlight_element(selection)
    
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
    
    def update_data_stats(self):
        """更新数据统计"""
        stats = self.state_manager.get_data_stats()
        self.layout_manager.update_data_stats(stats)
    
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
            periph_tree = self.layout_manager.get_widget('periph_tree')
            if periph_tree:
                # 紧凑模式下树中没有位域节点，只选中寄存器
                compact = self.peripheral_manager.is_compact_tree()
                
                # 查找外设项
                for i in range(periph_tree.topLevelItemCount()):
                    periph_item = periph_tree.topLevelItem(i)
                    if periph_item.text(0) == peripheral:
                        periph_item.setExpanded(True)
                        # 查找寄存器项
                        for j in range(periph_item.childCount()):
                            reg_item = periph_item.child(j)
                            if reg_item.text(0) == register:
                                if compact:
                                    # 紧凑模式：选中寄存器即可
                                    periph_tree.setCurrentItem(reg_item)
                                    periph_tree.scrollToItem(reg_item)
                                else:
                                    # 完整模式：展开并选到位域
                                    reg_item.setExpanded(True)
                                    for k in range(reg_item.childCount()):
                                        field_item = reg_item.child(k)
                                        if field_item.text(0) == field.name:
                                            periph_tree.setCurrentItem(field_item)
                                            periph_tree.scrollToItem(field_item)
                                            break
                                break
                        break
            
            # 同步高亮位域表格中对应的行
            self._highlight_field_in_table(field_name)
    
    def on_field_table_selection_changed(self):
        """位域表格行选择变化 → 高亮位域图 + 更新状态"""
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
        """紧凑模式复选框状态变化 → 重建树"""
        from PyQt6.QtCore import Qt
        checked = (state == Qt.CheckState.Checked.value)
        self.logger.info(f"紧凑模式: {'启用' if checked else '禁用'}")
        
        # 重建树（保留展开状态）
        self.peripheral_manager.update_peripheral_tree(preserve_expanded=True)
        
        # 更新状态栏
        status = "紧凑模式已启用（树状图只显示到寄存器级别）" if checked else "完整模式（树状图显示所有级别）"
        self.layout_manager.update_status(status)
    
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
        """统一的删除按钮点击事件 - 支持多选批量删除"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            return
        
        selected = periph_tree.selectedItems()
        if not selected:
            self.show_message(t("message.warning", default="提示"), 
                              t("msg.select_item_first", default="请先选择要删除的项目"), "info")
            return
        
        # 多选批量删除
        if len(selected) > 1:
            self._batch_delete_selected(selected)
            return
        
        # 单选删除
        item = selected[0]
        item_type = self.tree_manager.get_item_type(item)
        item_name = self.tree_manager.get_item_name(item)
        
        if item_type == "field":
            # 获取外设和寄存器名
            reg_item = item.parent()
            periph_item = reg_item.parent() if reg_item else None
            if reg_item and periph_item:
                self.state_manager.set_selection(
                    peripheral=self.tree_manager.get_item_name(periph_item),
                    register=self.tree_manager.get_item_name(reg_item),
                    field=item_name
                )
            self.delete_field(item_name)
        elif item_type == "register":
            periph_item = item.parent()
            if periph_item:
                self.state_manager.set_selection(
                    peripheral=self.tree_manager.get_item_name(periph_item),
                    register=item_name
                )
            self.delete_register(item_name)
        elif item_type == "peripheral":
            self.peripheral_manager.delete_selected_peripheral()
    
    def _batch_delete_selected(self, items: list):
        """批量删除选中的项目"""
        # ===== 第一步：先收集所有待删除项的信息（在树被重建之前） =====
        to_delete_periphs = []
        to_delete_regs = []  # (periph, reg)
        to_delete_fields = []  # (periph, reg, field)
        
        for item in items:
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
        
        status_msg = f"已批量删除 {deleted_count} 个项目"
        if chain_messages:
            status_msg += f" (连锁: {len(chain_messages)}项)"
        self.layout_manager.update_status(status_msg)
        self.logger.info(f"批量删除完成: {deleted_count} 个项目")
        
        # 显示连锁结果
        if chain_messages:
            QMessageBox.information(self, "连锁操作",
                "已同步删除以下关联项:\n" + "\n".join(chain_messages))
        
        self.data_changed.emit()
    
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
    
    def on_jump_to_peripheral(self, peripheral_name: str):
        """跳转到外设事件处理（用于继承外设的跳转）"""
        self.logger.debug(f"===== on_jump_to_peripheral called with: {peripheral_name} =====")
        # 更新状态管理器的选择状态
        self.state_manager.set_selection(peripheral=peripheral_name)
        
        # 更新可视化控件
        self.update_visualization(peripheral_name, '', '')
        self.logger.debug("===== on_jump_to_peripheral completed =====")
    
    # ===================== 文件操作 =====================
    def new_file(self):
        """新建文件 - 使用向导引导创建"""
        from .dialogs.new_svd_wizard import NewSVDWizard
        from ..core.data_model import DeviceInfo, CPUInfo
        
        wizard = NewSVDWizard(self)
        if wizard.exec() == NewSVDWizard.DialogCode.Accepted:
            # 先保存当前文档状态（确保数据隔离）
            self._save_current_document_state()
            
            # 从向导获取数据
            chip_name = wizard.field("chip_name") or ""
            vendor = wizard.field("vendor") or ""
            version = wizard.field("version") or "1.0"
            description = wizard.field("description") or ""
            series = wizard.field("series") or ""
            copyright_text = wizard.field("copyright") or ""
            cpu_type = wizard.field("cpu_type") or "CM4"
            cpu_revision = wizard.field("cpu_revision") or "r0p0"
            endian = wizard.field("endian") or "little"
            width = int(wizard.field("width") or 32)
            reset_value = wizard.field("reset_value") or "0x00000000"
            reset_mask = wizard.field("reset_mask") or "0xFFFFFFFF"
            access = wizard.field("access") or "read-write"
            
            # 创建 CPUInfo
            cpu_info = CPUInfo(name=cpu_type)
            cpu_info.revision = cpu_revision
            cpu_info.endian = endian
            cpu_info.mpu_present = 1
            cpu_info.fpu_present = 1
            cpu_info.nvic_prio_bits = 4
            cpu_info.vendor_systick_config = 0
            
            # 创建 DeviceInfo
            device_info = DeviceInfo(name=chip_name)
            device_info.vendor = vendor
            device_info.version = version
            device_info.description = description
            device_info.cpu = cpu_info
            device_info.width = width
            device_info.reset_value = reset_value
            device_info.reset_mask = reset_mask
            
            # 暂停通知，防止旧文档的树展开状态泄漏到新文档
            self.state_manager.pause_notifications()
            
            try:
                # 更新状态管理器
                self.state_manager.device_info = device_info
                self.state_manager.clear_selection()
                self.state_manager.command_history.clear()
                
                # 重置预览器状态（新文档不应该继承旧文档的选中/折叠状态）
                if self.preview_manager and self.preview_manager.preview_widget:
                    pw = self.preview_manager.preview_widget
                    pw.folded_elements = set()
                    pw.current_selection = {
                        'type': None, 'peripheral': None, 'register': None,
                        'field': None, 'interrupt': None
                    }
                    if hasattr(pw, 'preview_edit') and pw.preview_edit:
                        pw.preview_edit.clear_highlight()
                
                # 更新UI（不保留旧文档的展开状态）
                self.peripheral_manager.update_peripheral_tree(preserve_expanded=False)
                self.update_data_stats()
                self._update_interrupt_table()
            finally:
                # 恢复通知（此时树已正确重建，不会泄漏展开状态）
                self.state_manager.resume_notifications()
            
            if hasattr(self.layout_manager, 'update_basic_info'):
                self.layout_manager.update_basic_info(device_info)
            
            self.layout_manager.update_status(f"已创建新文件: {chip_name}")
            
            # 注册到文档管理器
            try:
                self.document_manager.open_document(
                    device_info, file_path=None, display_name=chip_name or "未命名")
            except Exception as e:
                self.logger.warning(f"注册文档到DocumentManager失败: {e}")
            
            # 切换到编辑器视图
            self.layout_manager.show_editor()
        else:
            # 用户取消向导，创建空白文件
            self.file_operations.new_file()
            self.layout_manager.show_editor()

    def _open_recent_file(self, file_path: str):
        """从欢迎页打开最近文件"""
        if os.path.exists(file_path):
            try:
                self._load_svd_from_path(file_path)
                self.layout_manager.show_editor()
                self.layout_manager.add_recent_file(file_path)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法打开文件:\n{e}")

    def _load_svd_from_path(self, file_path: str):
        """从指定路径加载SVD文件"""
        # 先保存当前文档状态（确保数据隔离）
        self._save_current_document_state()
        
        parser = SVDParser()
        device_info = parser.parse(file_path)
        
        # 暂停通知，防止旧文档的树展开状态泄漏到新文档
        self.state_manager.pause_notifications()
        
        try:
            self.state_manager.device_info = device_info
            self.state_manager.clear_selection()
            self.state_manager.command_history.clear()
            
            # 重置预览器状态（新打开的文件不应该继承旧文件的选中/折叠状态）
            if self.preview_manager and self.preview_manager.preview_widget:
                pw = self.preview_manager.preview_widget
                pw.folded_elements = set()
                pw.current_selection = {
                    'type': None, 'peripheral': None, 'register': None,
                    'field': None, 'interrupt': None
                }
                if hasattr(pw, 'preview_edit') and pw.preview_edit:
                    pw.preview_edit.clear_highlight()
            
            # 更新UI（不保留旧文档的展开状态）
            self.peripheral_manager.update_peripheral_tree(preserve_expanded=False)
            self.update_data_stats()
            self._update_interrupt_table()
        finally:
            # 恢复通知（此时树已正确重建，不会泄漏展开状态）
            self.state_manager.resume_notifications()
        
        if hasattr(self.layout_manager, 'update_basic_info'):
            self.layout_manager.update_basic_info(device_info)
        self.layout_manager.update_status(f"已打开: {os.path.basename(file_path)}")

    def save_svd_file(self):
        """保存SVD文件"""
        self.file_operations.save_svd_file()

    def save_svd_file_as(self):
        """另存为SVD文件"""
        self.file_operations.save_svd_file_as()

    def check_unsaved_changes(self) -> bool:
        """检查未保存的更改"""
        return self.file_operations.check_unsaved_changes()

    def generate_svd(self):
        """生成SVD文件"""
        self.file_operations.generate_svd()

    def preview_xml(self):
        """预览XML"""
        self.file_operations.preview_xml()

    def export_file(self):
        """导出文件"""
        self.file_operations.export_file()

    def validate_data(self):
        """验证 SVD 数据（CMSIS-SVD Schema 完整验证）"""
        self.file_operations.validate_svd()

    def export_document(self, format_type: str = "markdown"):
        """导出文档（CSV/Markdown/HTML）"""
        self.file_operations.export_document(format_type)
    
    def export_header_file(self):
        """导出C语言头文件"""
        from ..core.header_generator import HeaderGenerator
        
        if not self.state_manager.device_info or not self.state_manager.device_info.peripherals:
            QMessageBox.warning(self, "提示", "请先加载或创建SVD数据")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出C头文件", 
            f"{self.state_manager.device_info.name or 'device'}.h",
            "C头文件 (*.h);;所有文件 (*.*)"
        )
        
        if file_path:
            generator = HeaderGenerator(self.state_manager.device_info)
            if generator.save_to_file(file_path):
                QMessageBox.information(self, "导出成功", f"C头文件已保存到:\n{file_path}")
                self.layout_manager.update_status(f"头文件已导出: {file_path}")
            else:
                QMessageBox.critical(self, "导出失败", "头文件生成失败")

    def show_advanced_search(self):
        """显示高级搜索对话框"""
        self.search_manager.show_advanced_search_dialog(self)

    def show_goto_address(self):
        """显示跳转到地址对话框"""
        self.search_manager.show_goto_address_dialog(self)

    def show_batch_modify(self):
        """显示批量修改属性对话框"""
        mgr = BatchOperationsManager(self.state_manager, self.coordinator)
        mgr.operation_completed.connect(lambda desc, n: self._on_batch_completed(desc, n))
        mgr.show_batch_modify_dialog(self)

    def show_batch_generate(self):
        """显示批量生成寄存器对话框"""
        mgr = BatchOperationsManager(self.state_manager, self.coordinator)
        mgr.operation_completed.connect(lambda desc, n: self._on_batch_completed(desc, n))
        mgr.show_batch_generate_dialog(self)

    def show_batch_clone(self):
        """显示批量克隆寄存器对话框"""
        mgr = BatchOperationsManager(self.state_manager, self.coordinator)
        mgr.operation_completed.connect(lambda desc, n: self._on_batch_completed(desc, n))
        mgr.show_batch_clone_dialog(self)

    def _on_batch_completed(self, desc: str, count: int):
        """批量操作完成后的 UI 刷新"""
        self.peripheral_manager.update_peripheral_tree()
        self.update_data_stats()
        self.layout_manager.update_status(desc)
        self.logger.info(desc)

    def show_svd_diff(self):
        """显示 SVD 差异比较（支持多标签页联动，结果在标签页中展示）"""
        # 检查是否打开了多个文档，可以自动比较
        doc_ids = self.document_manager.document_ids
        if len(doc_ids) >= 2:
            # 多文档打开：提供选择比较两个已打开文档的选项
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QDialogButtonBox
            
            select_dialog = QDialog(self)
            select_dialog.setWindowTitle("SVD 文件比较")
            select_dialog.setMinimumWidth(450)
            layout = QVBoxLayout(select_dialog)
            
            layout.addWidget(QLabel("检测到已打开多个文档，可以直接比较："))
            
            # 文档A选择
            layout.addWidget(QLabel("文档 A（基准）："))
            combo_a = QComboBox()
            for doc_id in doc_ids:
                doc = self.document_manager.get_document(doc_id)
                if doc:
                    combo_a.addItem(doc.display_name or "未命名", doc_id)
            combo_a.setCurrentIndex(0)
            layout.addWidget(combo_a)
            
            # 文档B选择
            layout.addWidget(QLabel("文档 B（比较）："))
            combo_b = QComboBox()
            for doc_id in doc_ids:
                doc = self.document_manager.get_document(doc_id)
                if doc:
                    combo_b.addItem(doc.display_name or "未命名", doc_id)
            combo_b.setCurrentIndex(min(1, combo_b.count() - 1))
            layout.addWidget(combo_b)
            
            # 按钮组（使用自定义result值：1=标签页显示, 2=弹窗显示）
            btn_box = QDialogButtonBox()
            compare_tab_btn = QPushButton("比较并在标签页显示")
            compare_tab_btn.clicked.connect(lambda: select_dialog.done(1))
            compare_dialog_btn = QPushButton("比较(弹窗)")
            compare_dialog_btn.clicked.connect(lambda: select_dialog.done(2))
            browse_btn = QPushButton("从文件选择...")
            browse_btn.clicked.connect(lambda: select_dialog.done(0))
            btn_box.addButton(compare_tab_btn, QDialogButtonBox.ButtonRole.AcceptRole)
            btn_box.addButton(compare_dialog_btn, QDialogButtonBox.ButtonRole.ActionRole)
            btn_box.addButton(browse_btn, QDialogButtonBox.ButtonRole.RejectRole)
            layout.addWidget(btn_box)
            
            result = select_dialog.exec()
            
            if result == 1:
                # 在标签页中显示比较结果
                doc_a_id = combo_a.currentData()
                doc_b_id = combo_b.currentData()
                
                if doc_a_id == doc_b_id:
                    QMessageBox.warning(self, "提示", "请选择两个不同的文档进行比较")
                    return
                
                doc_a = self.document_manager.get_document(doc_a_id)
                doc_b = self.document_manager.get_document(doc_b_id)
                
                if doc_a and doc_b:
                    self._show_diff_in_tab(doc_a.device_info, doc_b.device_info,
                                           doc_a.display_name, doc_b.display_name)
                return
            elif result == 2:
                # 在弹窗中显示
                doc_a_id = combo_a.currentData()
                doc_b_id = combo_b.currentData()
                
                if doc_a_id == doc_b_id:
                    QMessageBox.warning(self, "提示", "请选择两个不同的文档进行比较")
                    return
                
                doc_a = self.document_manager.get_document(doc_a_id)
                doc_b = self.document_manager.get_document(doc_b_id)
                
                if doc_a and doc_b:
                    from .dialogs.svd_diff_dialog import SVDDiffDialog
                    dialog = SVDDiffDialog(self, current_device=doc_a.device_info)
                    dialog.other_device = doc_b.device_info
                    name_b = doc_b.display_name or "未命名"
                    n_periphs = len(doc_b.device_info.peripherals) if doc_b.device_info else 0
                    dialog.file_label.setText(f"比较文件: {name_b} ({n_periphs} 外设)")
                    dialog.file_label.setStyleSheet("color: black;")
                    dialog.compare_btn.setEnabled(True)
                    dialog.setWindowTitle(f"SVD 比较: {doc_a.display_name} vs {name_b}")
                    dialog.exec()
                return
        
        # 单文档或无文档：使用文件选择后标签页显示
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择要比较的SVD文件", "", "SVD文件 (*.svd);;XML文件 (*.xml)")
        if file_path:
            try:
                parser = SVDParser()
                other_device = parser.parse_file(file_path)
                other_name = os.path.basename(file_path)
                current_name = "当前文档"
                doc = self.document_manager.active_document
                if doc:
                    current_name = doc.display_name or "当前文档"
                self._show_diff_in_tab(
                    self.state_manager.device_info, other_device,
                    current_name, other_name)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法加载比较文件:\n{e}")
    
    def _show_diff_in_tab(self, device_a, device_b, name_a="文档A", name_b="文档B"):
        """在主内容区域显示SVD差异比较结果（不创建次级标签页）"""
        from .widgets.diff_view_widget import DiffViewWidget
        
        # 创建差异视图组件
        diff_view = DiffViewWidget(self)
        diff_view.set_diff_data(device_a, device_b, name_a, name_b)
        
        # 在顶部文档标签栏中添加比较标签（与SVD文档同级）
        tab_bar = self.layout_manager.get_document_tab_bar()
        diff_name = f"{name_a} vs {name_b}"
        diff_id = None
        if tab_bar:
            diff_id = tab_bar.add_diff_tab(diff_name)
            self._diff_views[diff_id] = diff_view
        
        # 将差异视图添加到主分割器的编辑区域（不使用tab_widget的次级标签）
        # 先确保编辑器视图可见（不是欢迎页）
        self.layout_manager.show_editor()
        
        editor_stack = self.layout_manager.get_widget('editor_stack')
        self.logger.info(f"editor_stack found: {editor_stack is not None}")
        if editor_stack:
            editor_stack.addWidget(diff_view)
            editor_stack.setCurrentWidget(diff_view)
            self.logger.info(f"diff_view added to editor_stack, index={editor_stack.indexOf(diff_view)}")
        else:
            # 回退方案：如果editor_stack不存在，直接替换中央区域
            central = self.centralWidget()
            if central:
                main_layout = central.layout()
                if main_layout:
                    # 隐藏当前编辑器内容，显示diff_view
                    diff_view.setParent(central)
                    main_layout.addWidget(diff_view)
                    diff_view.show()
        
        self._active_diff_id = diff_id
        
        # 统计信息
        summary = ""
        if hasattr(diff_view, '_differ') and diff_view._differ:
            summary = diff_view._differ.generate_summary(diff_view._diffs)
        total = summary.count('\n') if summary else 0
        
        self.layout_manager.update_status(f"SVD比较完成: {diff_name}")
    
    def _on_diff_tab_clicked(self, diff_id: str):
        """比较标签被点击 - 显示对应的比较结果"""
        if diff_id not in self._diff_views:
            return
        
        # 保存当前文档状态
        if self.document_manager.active_doc_id:
            self._save_current_document_state()
        
        diff_view = self._diff_views[diff_id]
        
        # 在editor_stack中显示diff_view
        editor_stack = self.layout_manager.get_widget('editor_stack')
        if editor_stack:
            editor_stack.setCurrentWidget(diff_view)
        
        self._active_diff_id = diff_id
        
        # 确保编辑器视图可见
        self.layout_manager.show_editor()
    
    def _on_diff_tab_close(self, diff_id: str):
        """比较标签被关闭"""
        if diff_id not in self._diff_views:
            return
        
        diff_view = self._diff_views.pop(diff_id)
        
        # 从editor_stack中移除
        editor_stack = self.layout_manager.get_widget('editor_stack')
        if editor_stack:
            idx = editor_stack.indexOf(diff_view)
            if idx >= 0:
                editor_stack.removeWidget(diff_view)
        
        diff_view.deleteLater()
        
        # 从标签栏移除
        tab_bar = self.layout_manager.get_document_tab_bar()
        if tab_bar:
            tab_bar.remove_diff_tab(diff_id)
        
        if self._active_diff_id == diff_id:
            self._active_diff_id = None
            # 切换回最后活动的文档
            if self.document_manager.document_ids:
                last_id = self.document_manager.active_doc_id or self.document_manager.document_ids[-1]
                self._on_document_tab_clicked(last_id)
    
    def _diff_has_type(self, item, diff_type):
        """递归检查差异类型"""
        from ..core.svd_differ import DiffType
        if item.diff_type == diff_type:
            return True
        return any(self._diff_has_type(c, diff_type) for c in item.children)
    
    def _populate_diff_tree(self, parent, items, 
                            color_added, color_removed, color_modified,
                            color_added_text, color_removed_text, color_modified_text):
        """递归填充差异树"""
        from ..core.svd_differ import DiffType
        
        for item in items:
            tree_item = QTreeWidgetItem()
            path_parts = item.path.rsplit('.', 1)
            display_name = path_parts[-1] if len(path_parts) > 1 else item.path
            tree_item.setText(0, display_name)
            
            type_text = {
                DiffType.ADDED: "新增 [+]",
                DiffType.REMOVED: "删除 [-]",
                DiffType.MODIFIED: "修改 [~]",
                DiffType.UNCHANGED: "",
            }.get(item.diff_type, "")
            tree_item.setText(1, type_text)
            
            old_str = str(item.old_value) if item.old_value is not None else ""
            new_str = str(item.new_value) if item.new_value is not None else ""
            if len(old_str) > 100: old_str = old_str[:97] + "..."
            if len(new_str) > 100: new_str = new_str[:97] + "..."
            tree_item.setText(2, old_str)
            tree_item.setText(3, new_str)
            
            if item.diff_type == DiffType.ADDED:
                bg, fg = color_added, color_added_text
            elif item.diff_type == DiffType.REMOVED:
                bg, fg = color_removed, color_removed_text
            elif item.diff_type == DiffType.MODIFIED:
                bg, fg = color_modified, color_modified_text
            else:
                bg = fg = None
            
            if bg and fg:
                for col in range(4):
                    tree_item.setBackground(col, QBrush(bg))
                    tree_item.setForeground(col, QBrush(fg))
            
            tree_item.setToolTip(0, item.path)
            
            if item.children:
                self._populate_diff_tree(tree_item, item.children,
                                          color_added, color_removed, color_modified,
                                          color_added_text, color_removed_text, color_modified_text)
            
            parent.addChild(tree_item)
        
        if isinstance(parent, QTreeWidgetItem):
            parent.setExpanded(True)
    
    def show_svd_merge(self):
        """显示 SVD 导入合并对话框（非模态，不阻塞主窗口）"""
        from .dialogs.svd_merge_dialog import SVDMergeDialog
        if not self.state_manager.device_info:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "提示", "请先打开或新建一个 SVD 文件")
            return
        
        # 保存引用防止被垃圾回收
        self._merge_dialog = SVDMergeDialog(self, self.state_manager.device_info)
        self._merge_dialog.merge_completed.connect(self._on_merge_completed)
        self._merge_dialog.finished.connect(lambda: self._cleanup_merge_dialog())
        self._merge_dialog.setWindowFlags(
            self._merge_dialog.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint
        )
        self._merge_dialog.show()
    
    def _cleanup_merge_dialog(self):
        """清理合并对话框引用"""
        if hasattr(self, '_merge_dialog'):
            self._merge_dialog = None
    
    def _on_merge_completed(self, merged_device):
        """合并完成后的回调"""
        from PyQt6.QtWidgets import QApplication
        
        # 更新状态管理器
        self.state_manager.device_info = merged_device
        self.state_manager.clear_selection()
        
        # 通知状态变更
        self.state_manager._notify_state_change()
        
        # 发射事件
        if hasattr(self, 'coordinator') and self.coordinator:
            self.coordinator.emit_event("device_info_updated", merged_device)
        
        # 刷新 UI
        self.peripheral_manager.update_peripheral_tree()
        self.update_data_stats()
        self._update_interrupt_table()
        
        # 更新预览
        if self.preview_manager:
            self.preview_manager.refresh_preview(immediate=True)
        
        # 更新基础信息
        if hasattr(self.layout_manager, 'update_basic_info'):
            self.layout_manager.update_basic_info(merged_device)
        
        self.layout_manager.update_status("SVD 导入合并完成")
        self.logger.info("SVD 导入合并完成")

    def open_svd_file(self):
        """打开SVD文件（支持多选）"""
        # 检查未保存的更改
        if self.check_unsaved_changes():
            file_paths, _ = QFileDialog.getOpenFileNames(
                self, "选择SVD文件", "", "SVD文件 (*.svd);;XML文件 (*.xml)"
            )
            
            if file_paths:
                for file_path in file_paths:
                    try:
                        # 先保存当前文档状态（确保数据隔离）
                        self._save_current_document_state()
                        
                        self.layout_manager.update_status(f"正在解析SVD文件: {os.path.basename(file_path)}...")
                        QApplication.processEvents()  # 更新UI
                        
                        # 解析文件
                        parser = SVDParser()
                        device_info = parser.parse_file(file_path)
                        
                        # 暂停通知，防止旧文档的树展开状态泄漏到新文档
                        self.state_manager.pause_notifications()
                        
                        try:
                            # 更新状态管理器
                            self.state_manager.device_info = device_info
                            self.state_manager.clear_selection()
                            self.state_manager.command_history.clear()
                            
                            # 重置预览器状态（新打开的文件不应该继承旧文件的选中/折叠状态）
                            if self.preview_manager and self.preview_manager.preview_widget:
                                pw = self.preview_manager.preview_widget
                                pw.folded_elements = set()
                                pw.current_selection = {
                                    'type': None, 'peripheral': None, 'register': None,
                                    'field': None, 'interrupt': None
                                }
                                if hasattr(pw, 'preview_edit') and pw.preview_edit:
                                    pw.preview_edit.clear_highlight()
                            
                            # 更新UI（不保留旧文档的展开状态）
                            self.peripheral_manager.update_peripheral_tree(preserve_expanded=False)
                            self.update_data_stats()
                            self._update_interrupt_table()
                        finally:
                            # 恢复通知（此时树已正确重建，不会泄漏展开状态）
                            self.state_manager.resume_notifications()
                        
                        # 发射文件加载信号（触发实时预览刷新）
                        if hasattr(self, 'coordinator') and self.coordinator:
                            self.logger.debug("调用coordinator.emit_event(device_info_updated)")
                            self.coordinator.emit_event("device_info_updated", device_info)
                        
                        # 更新基础信息
                        if hasattr(self.layout_manager, 'update_basic_info'):
                            self.layout_manager.update_basic_info(device_info)
                        
                        self.layout_manager.update_status(f"已加载: {os.path.basename(file_path)}")
                        
                        # 注册到文档管理器
                        try:
                            self.document_manager.open_document(
                                device_info, file_path=file_path)
                        except Exception as e:
                            self.logger.warning(f"注册文档到DocumentManager失败: {e}")
                        
                        # 切换到编辑器视图
                        self.layout_manager.show_editor()
                        self.layout_manager.add_recent_file(file_path)
                        
                        # 显示警告
                        if parser.warnings:
                            warning_msg = "\n".join(parser.warnings[:10])
                            if len(parser.warnings) > 10:
                                warning_msg += t("msg.more_warnings", count=len(parser.warnings)-10)
                            QMessageBox.warning(self, t("msg.parse_warning"), warning_msg)
                    
                    except Exception as e:
                        self.logger.error(f"文件加载失败: {str(e)}")
                        QMessageBox.critical(self, t("msg.load_error"), t("msg.file_load_failed_detail", error=str(e)))
                
                # 多文件加载完成后更新状态
                if len(file_paths) > 1:
                    self.layout_manager.update_status(f"已加载 {len(file_paths)} 个SVD文件")
    
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
            
            # 保存前先从UI更新设备信息（包括公司、版权、协议等基本信息）
            self.update_device_info_from_ui()
            
            # 生成SVD
            generator = SVDGenerator(self.state_manager.device_info)
            svd_xml = generator.generate()
            
            # 保存文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(svd_xml)
            
            # 更新状态
            self.current_file_path = file_path
            self.layout_manager.update_status(f"SVD文件已保存: {file_path}")
            QMessageBox.information(self, t("msg.save_success"), t("msg.svd_file_saved", path=file_path))
            
        except Exception as e:
            self.logger.error(f"文件保存失败: {str(e)}")
            QMessageBox.critical(self, t("msg.save_error"), t("msg.file_save_failed_detail", error=str(e)))
    
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
                QMessageBox.warning(self, t("msg.validation_error"), "\n".join(errors))
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
            QMessageBox.critical(self, t("msg.generate_error"), t("msg.svd_generate_failed", error=str(e)))
    
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
            QMessageBox.critical(self, t("msg.preview_error"), t("msg.xml_preview_failed", error=str(e)))
    
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
            QMessageBox.information(self, t("msg.save_success"), t("msg.svd_file_saved", path=file_path))
            
        except Exception as e:
            self.logger.error(f"文件保存失败: {str(e)}")
            QMessageBox.critical(self, t("msg.save_error"), t("msg.file_save_failed_detail", error=str(e)))
    
    # ===================== 树折叠/展开同步预览 =====================
    def _on_tree_item_collapsed(self, item: QTreeWidgetItem):
        """树节点折叠时同步折叠预览"""
        item_name = item.text(0)
        self.logger.debug(f"树节点折叠: {item_name}")
        if self.preview_manager and self.preview_manager.preview_widget:
            self.preview_manager.preview_widget.sync_fold_from_tree(item_name, is_expanded=False)
    
    def _on_tree_item_expanded(self, item: QTreeWidgetItem):
        """树节点展开时同步展开预览"""
        item_name = item.text(0)
        self.logger.debug(f"树节点展开: {item_name}")
        if self.preview_manager and self.preview_manager.preview_widget:
            self.preview_manager.preview_widget.sync_fold_from_tree(item_name, is_expanded=True)
    
    # ===================== 其他方法 =====================
    def enable_tree_drag_drop(self):
        """启用树拖放功能"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if periph_tree:
            periph_tree.setDragEnabled(True)
            periph_tree.setAcceptDrops(True)
            periph_tree.setDropIndicatorShown(True)  # 启用默认drop indicator
            periph_tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
            
            # 设置自定义拖放事件处理
            periph_tree.dragEnterEvent = self.custom_drag_enter_event
            periph_tree.dragMoveEvent = self.custom_drag_move_event
            periph_tree.dropEvent = self.custom_drop_event
    
    def custom_drag_enter_event(self, event):
        """自定义拖拽进入事件 - 允许外设之间和位域之间的拖放"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            event.ignore()
            return
        
        source_item = periph_tree.currentItem()
        if not source_item:
            event.ignore()
            return
        
        source_type = self.tree_manager.get_item_type(source_item)
        # 允许外设和位域拖放
        if source_type not in ("peripheral", "field"):
            event.ignore()
            return
        
        event.accept()
    
    def custom_drag_move_event(self, event):
        """自定义拖拽移动事件 - 实时验证拖放目标"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            event.ignore()
            return
        
        source_item = periph_tree.currentItem()
        if not source_item:
            event.ignore()
            return
        
        source_type = self.tree_manager.get_item_type(source_item)
        
        # 外设拖放验证
        if source_type == "peripheral":
            target_index = periph_tree.indexAt(event.position().toPoint())
            if not target_index.isValid():
                event.accept()
                return
            target_item = periph_tree.itemFromIndex(target_index)
            if not target_item:
                event.ignore()
                return
            target_type = self.tree_manager.get_item_type(target_item)
            if target_type != "peripheral":
                event.ignore()
                return
            event.accept()
        
        # 位域拖放验证：只允许在同一寄存器内拖放
        elif source_type == "field":
            target_index = periph_tree.indexAt(event.position().toPoint())
            if not target_index.isValid():
                event.ignore()
                return
            target_item = periph_tree.itemFromIndex(target_index)
            if not target_item:
                event.ignore()
                return
            target_type = self.tree_manager.get_item_type(target_item)
            # 目标必须是位域或寄存器（允许放在寄存器的空白区域）
            if target_type not in ("field", "register"):
                event.ignore()
                return
            # 如果目标是位域，检查是否同一寄存器
            if target_type == "field":
                source_parent = source_item.parent()
                target_parent = target_item.parent()
                if source_parent is not target_parent:
                    event.ignore()
                    return
            elif target_type == "register":
                # 拖到寄存器上，检查是否是源位域的父寄存器
                source_parent = source_item.parent()
                if source_parent is not target_item:
                    event.ignore()
                    return
            event.accept()
        
        else:
            event.ignore()
    
    def custom_drop_event(self, event):
        """自定义拖放事件处理 - 支持外设之间和位域之间的拖放"""
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if not periph_tree:
            event.ignore()
            return
        
        source_item = periph_tree.currentItem()
        if not source_item:
            event.ignore()
            return
        
        source_type = self.tree_manager.get_item_type(source_item)
        source_name = self.tree_manager.get_item_name(source_item)
        
        # ===== 位域拖放处理 =====
        if source_type == "field":
            self._handle_field_drop(event, periph_tree, source_item, source_name)
            return
        
        # ===== 外设拖放处理 =====
        if source_type != "peripheral":
            event.ignore()
            return
        
        # 获取目标位置
        target_index = periph_tree.indexAt(event.position().toPoint())
        if target_index.isValid():
            target_item = periph_tree.itemFromIndex(target_index)
            if target_item:
                target_type = self.tree_manager.get_item_type(target_item)
                if target_type != "peripheral":
                    event.ignore()
                    return
                target_name = self.tree_manager.get_item_name(target_item)
        else:
            event.ignore()
            return
        
        if source_name == target_name:
            event.ignore()
            return
        
        # 保存拖放前的外设顺序（用于撤销）
        old_order = list(self.state_manager.device_info.peripherals.keys())
        
        # 保存展开状态
        expanded_paths = self.peripheral_manager._get_expanded_items(periph_tree)
        
        # 执行拖放（使用Qt默认行为移动树节点）
        from PyQt6.QtWidgets import QTreeWidget
        QTreeWidget.dropEvent(periph_tree, event)
        
        # 拖放后验证并修正树结构
        self._validate_and_fix_tree_structure_after_drop(source_name)
        
        # 恢复展开状态
        periph_tree_block = periph_tree.blockSignals(True)
        for i in range(periph_tree.topLevelItemCount()):
            item = periph_tree.topLevelItem(i)
            if item and item.text(0) in expanded_paths:
                item.setExpanded(True)
            for j in range(item.childCount() if item else 0):
                child = item.child(j)
                child_path = f"{item.text(0)}/{child.text(0)}" if item else ""
                if child and child_path in expanded_paths:
                    child.setExpanded(True)
        periph_tree.blockSignals(periph_tree_block)
        
        # 记录拖放操作到命令历史（支持撤销）
        new_order = list(self.state_manager.device_info.peripherals.keys())
        if old_order != new_order:
            captured_old_order = old_order[:]
            captured_new_order = new_order[:]
            state_mgr = self.state_manager
            
            def execute_reorder():
                peripherals = state_mgr.device_info.peripherals
                reordered = {name: peripherals[name] for name in captured_new_order if name in peripherals}
                state_mgr.device_info.peripherals = reordered
                state_mgr._notify_state_change()
                return True
            
            def undo_reorder():
                peripherals = state_mgr.device_info.peripherals
                reordered = {name: peripherals[name] for name in captured_old_order if name in peripherals}
                state_mgr.device_info.peripherals = reordered
                state_mgr._notify_state_change()
                return True
            
            from ..core.command_history import Command
            command = Command(
                execute=execute_reorder,
                undo=undo_reorder,
                description=f"拖放调整外设顺序: {source_name}"
            )
            state_mgr.command_history.history.append(command)
            state_mgr.command_history.current_index = len(state_mgr.command_history.history) - 1
            state_mgr.command_history.redo_stack.clear()
    
    def _handle_field_drop(self, event, periph_tree, source_item, source_name):
        """处理位域拖放事件"""
        target_index = periph_tree.indexAt(event.position().toPoint())
        if not target_index.isValid():
            event.ignore()
            return
        
        target_item = periph_tree.itemFromIndex(target_index)
        if not target_item:
            event.ignore()
            return
        
        target_type = self.tree_manager.get_item_type(target_item)
        
        # 确定目标位域和父寄存器
        reg_item = source_item.parent()
        if not reg_item:
            event.ignore()
            return
        periph_item = reg_item.parent()
        if not periph_item:
            event.ignore()
            return
        
        periph_name = self.tree_manager.get_item_name(periph_item)
        reg_name = self.tree_manager.get_item_name(reg_item)
        
        # 确定目标位域名称和目标位置
        target_field_name = None
        if target_type == "field":
            target_parent = target_item.parent()
            if target_parent is not reg_item:
                event.ignore()
                return
            target_field_name = self.tree_manager.get_item_name(target_item)
        elif target_type == "register":
            if target_item is not reg_item:
                event.ignore()
                return
            # 拖到寄存器末尾
        else:
            event.ignore()
            return
        
        # 获取当前位域顺序
        register = self.state_manager.device_info.peripherals.get(periph_name, {}).registers.get(reg_name)
        if not register:
            event.ignore()
            return
        
        old_field_names = list(register.fields.keys())
        if source_name not in old_field_names:
            event.ignore()
            return
        
        # 执行Qt默认的拖放（移动树节点）
        from PyQt6.QtWidgets import QTreeWidget
        QTreeWidget.dropEvent(periph_tree, event)
        
        # 从树中读取新的位域顺序
        new_field_names = []
        for k in range(reg_item.childCount()):
            child = reg_item.child(k)
            child_type = self.tree_manager.get_item_type(child)
            child_name = self.tree_manager.get_item_name(child)
            if child_type == "field" and child_name in old_field_names:
                new_field_names.append(child_name)
        
        # 如果顺序没变，不记录
        if new_field_names == old_field_names or not new_field_names:
            return
        
        # 记录到命令历史
        captured_old = old_field_names[:]
        captured_new = new_field_names[:]
        captured_periph = periph_name
        captured_reg = reg_name
        state_mgr = self.state_manager
        
        def execute_field_reorder():
            reg = state_mgr.device_info.peripherals.get(captured_periph, {}).registers.get(captured_reg)
            if reg is None:
                return False
            old_fields = reg.fields
            reg.fields = {name: old_fields[name] for name in captured_new if name in old_fields}
            state_mgr._notify_state_change()
            return True
        
        def undo_field_reorder():
            reg = state_mgr.device_info.peripherals.get(captured_periph, {}).registers.get(captured_reg)
            if reg is None:
                return False
            old_fields = reg.fields
            reg.fields = {name: old_fields[name] for name in captured_old if name in old_fields}
            state_mgr._notify_state_change()
            return True
        
        from ..core.command_history import Command
        command = Command(
            execute=execute_field_reorder,
            undo=undo_field_reorder,
            description=f"拖放调整位域顺序: {source_name}"
        )
        state_mgr.command_history.history.append(command)
        state_mgr.command_history.current_index = len(state_mgr.command_history.history) - 1
        state_mgr.command_history.redo_stack.clear()
        
        self.layout_manager.update_status(f"已调整位域顺序: {source_name}")
    
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
                QMessageBox.warning(self, t("msg.drag_drop_error"), t("msg.drag_drop_invalid_structure"))
            else:
                # 更新数据模型
                self.update_data_model_from_tree()
                # 更新状态栏
                self.layout_manager.update_status(f"已调整外设顺序: {moved_periph_name}")
                
                # 延迟重新选中项目
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(50, lambda: self.peripheral_manager._select_peripheral_in_tree(moved_periph_name))
        
        except Exception as e:
            self.logger.error(f"拖放后验证出错: {e}")
            # 出错时恢复
            self.peripheral_manager.update_peripheral_tree()
    
    def apply_styles(self):
        """应用样式"""
        from ..config.styles import get_current_stylesheet
        self.setStyleSheet(get_current_stylesheet())
    
    def toggle_dark_mode(self, checked: bool):
        """切换深色模式"""
        from ..config.styles import set_dark_mode, get_current_stylesheet
        set_dark_mode(checked)
        self.setStyleSheet(get_current_stylesheet())
        
        # 更新可视化控件背景
        visualization_widget = self.layout_manager.get_widget('visualization_widget')
        if visualization_widget:
            visualization_widget.update()
        
        status = "深色模式已启用" if checked else "浅色模式已启用"
        self.layout_manager.update_status(status)
    
    # ===================== 撤销/重做功能 =====================
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
    
    # ===================== 排序功能 =====================
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
                current_item = periph_tree.currentItem()
                if not current_item:
                    return
                item_type = self.tree_manager.get_item_type(current_item)
                if item_type != "field":
                    return
                reg_item = current_item.parent()
                if not reg_item:
                    return
                periph_item = reg_item.parent()
                if not periph_item:
                    return
                periph_name = self.tree_manager.get_item_name(periph_item)
                reg_name = self.tree_manager.get_item_name(reg_item)
            
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
                self.layout_manager.update_status(f"位域 '{field_name}' 已在最上方")
                return
            elif direction == "down" and current_idx >= len(field_names) - 1:
                self.layout_manager.update_status(f"位域 '{field_name}' 已在最下方")
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
                self.layout_manager.update_status(f"已{'上移' if direction == 'up' else '下移'}位域: {field_name}")
            else:
                self.layout_manager.update_status(f"位域 '{field_name}' 已在最{'上方' if direction == 'up' else '下方'}")
                
        except Exception as e:
            self.logger.error(f"移动位域失败: {str(e)}")
    
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
                current_item = periph_tree.currentItem()
                if not current_item:
                    return
                item_type = self.tree_manager.get_item_type(current_item)
                if item_type == "field":
                    reg_item = current_item.parent()
                elif item_type == "register":
                    reg_item = current_item
                else:
                    return
                if not reg_item:
                    return
                periph_item = reg_item.parent()
                if not periph_item:
                    return
                periph_name = self.tree_manager.get_item_name(periph_item)
                reg_name = self.tree_manager.get_item_name(reg_item)
            
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
                self.layout_manager.update_status("位域已按位偏移排序，无需调整")
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
            self.layout_manager.update_status(f"已按位偏移排序 {reg_name} 的位域")
            
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
                self.layout_manager.update_status("已按字母顺序排序")
                self.logger.info("按字母顺序排序完成")
            else:
                self.layout_manager.update_status("顺序未变化，无需排序")
                
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
            QMessageBox.warning(self, t("msg.sort_error"), t("msg.sort_by_address_failed", error=str(e)))
    
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
            # 注意：add_register 内部通过 execute_command → _notify_state_change → on_state_changed → update_peripheral_tree
            self.state_manager.add_register(current_peripheral, register)
            
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
            
            # 注意：state_manager 操作内部已通过 _notify_state_change 触发树重建
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
        self.layout_manager.update_status(f"已删除寄存器: {reg_name}")
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
            self.layout_manager.update_status(f"已批量删除 {deleted_count} 个寄存器")
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
        status_msg = f"已删除位域: {field_name}"
        if chain_messages:
            status_msg += f" (连锁: {len(chain_messages)}项)"
        self.layout_manager.update_status(status_msg)
        self.logger.info(f"删除位域: {field_name}")
        
        # 显示连锁结果
        if chain_messages:
            QMessageBox.information(self, t("msg.chain_operation", default="连锁操作"),
                t("msg.chain_result", default="已同步删除以下关联项:\n") + "\n".join(chain_messages))
        
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
            from ..core.data_model import Interrupt
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
        self.layout_manager.update_status(f"已删除中断: {interrupt_name}")
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
            irq_table.setItem(i, 0, QTableWidgetItem(interrupt.name))
            irq_table.setItem(i, 1, QTableWidgetItem(str(interrupt.value)))
            # 显示所有关联外设（逗号分隔）
            periph_display = ", ".join(interrupt.peripherals) if interrupt.peripherals else (interrupt.peripheral or "")
            irq_table.setItem(i, 2, QTableWidgetItem(periph_display))
            irq_table.setItem(i, 3, QTableWidgetItem(interrupt.description or ""))
    
    def _refresh_all_data(self):
        """重新填充所有数据到新创建的控件中"""
        # 更新基础信息标签页
        if hasattr(self, 'device_info_manager'):
            self.device_info_manager.update_ui_from_device_info(self.state_manager.device_info)
        
        # 更新外设树
        if hasattr(self, 'peripheral_manager'):
            self.peripheral_manager.update_peripheral_tree()
        
        # 更新中断表格
        self._update_interrupt_table()
        
        # 更新可视化控件（使用当前选择）
        selection = self.state_manager.get_selection()
        self.update_visualization(
            selection.get('peripheral') or '',
            selection.get('register') or '',
            selection.get('field') or ''
        )
        
        # 更新位域表格
        if selection.get('register') and selection.get('peripheral'):
            device_info = self.state_manager.device_info
            if (selection['peripheral'] in device_info.peripherals and
                selection['register'] in device_info.peripherals[selection['peripheral']].registers):
                reg_obj = device_info.peripherals[selection['peripheral']].registers[selection['register']]
                self.layout_manager.update_field_table(selection['peripheral'], selection['register'], reg_obj)
            else:
                self.layout_manager.update_field_table()
        else:
            self.layout_manager.update_field_table()
        
        # 更新位域图（触发重绘以更新语言）
        visualization_widget = self.layout_manager.get_widget('visualization_widget')
        if visualization_widget and hasattr(visualization_widget, 'bit_field'):
            visualization_widget.bit_field.update()
    
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
        menu = QMenu()
        
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
        
        # 添加"禁用调试日志"复选框
        self.disable_debug_checkbox = QCheckBox("禁用调试日志")
        self.disable_debug_checkbox.setChecked(False)  # 默认不禁用调试日志
        self.disable_debug_checkbox.stateChanged.connect(self.on_disable_debug_checkbox_changed)
        toolbar.addWidget(self.disable_debug_checkbox)
        
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
                # 初始级别设置为INFO，避免大量DEBUG日志阻塞UI线程
                self.setLevel(logging.INFO)

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
        # 将GUI日志处理器添加到根logger，这样所有logger的日志都会显示在日志面板中
        root_logger = logging.getLogger()
        root_logger.addHandler(self._gui_log_handler)
        
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

    def on_disable_debug_checkbox_changed(self, state):
        """处理禁用调试日志复选框状态变化"""
        from svd_tool.utils.debug_logger import set_debug_enabled
        disable_debug = (state == Qt.CheckState.Checked.value)
        # 更新调试日志开关
        set_debug_enabled(not disable_debug)
        # 更新状态显示
        status_msg = "调试日志已禁用" if disable_debug else "调试日志已启用"
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
                QMessageBox.warning(self, t("message.warning"), t("msg.log_panel_not_created"))
                return
            
            log_content = self.log_text.toPlainText()
            if not log_content.strip():
                QMessageBox.warning(self, t("message.warning"), t("msg.log_content_empty"))
                return
            
            file_path, _ = QFileDialog.getSaveFileName(
                self, t("msg.save_success"), "svd_log.txt", "文本文件 (*.txt);;所有文件 (*.*)"
            )
            
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(log_content)
                
                self.layout_manager.update_status(f"日志已保存到: {file_path}")
                self.logger.info(f"日志已保存到: {file_path}")
                QMessageBox.information(self, t("message.success"), t("msg.log_save_success"))
            
        except Exception as e:
            self.logger.error(f"保存日志时出错: {str(e)}")
            QMessageBox.warning(self, t("message.error"), t("msg.save_log_error_detail", error=str(e)))

    def toggle_log_panel(self, checked: bool):
        """切换日志面板显示/隐藏"""
        try:
            if not hasattr(self, 'log_dock') or not self.log_dock:
                # 如果日志面板不存在，先创建
                try:
                    self.create_log_panel()
                except Exception:
                    QMessageBox.warning(self, t("message.error"), t("msg.create_log_panel_error"))
                    return
            
            if checked:
                self.log_dock.show()
                self.layout_manager.update_status("日志面板已显示")
            else:
                self.log_dock.hide()
                self.layout_manager.update_status("日志面板已隐藏")
                
        except Exception as e:
            self.logger.error(f"切换日志面板时出错: {str(e)}")
    
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
    
    def show_chain_rules_dialog(self):
        """显示连锁规则编辑对话框"""
        from ..core.chain_rules import ChainRule, ChainAction
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
            QLineEdit, QPushButton, QListWidget, QListWidgetItem, QComboBox,
            QCheckBox, QTextEdit, QGroupBox, QFormLayout, QSplitter, QWidget)
        
        dialog = QDialog(self)
        dialog.setWindowTitle(t("dialog.chain_rules", default="连锁规则编辑"))
        dialog.setMinimumSize(700, 500)
        layout = QVBoxLayout(dialog)
        
        # 全局启用开关
        enable_cb = QCheckBox(t("label.chain_enabled", default="启用连锁操作"))
        enable_cb.setChecked(self.chain_rules_engine.enabled)
        layout.addWidget(enable_cb)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：规则列表
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel(t("label.rules_list", default="规则列表")))
        rules_list = QListWidget()
        for i, rule in enumerate(self.chain_rules_engine.rules):
            item = QListWidgetItem(f"{'✓' if rule.enabled else '✗'} {rule.name}")
            rules_list.addItem(item)
        left_layout.addWidget(rules_list)
        
        btn_layout = QHBoxLayout()
        add_rule_btn = QPushButton(t("button.add", default="添加"))
        del_rule_btn = QPushButton(t("button.delete", default="删除"))
        batch_gen_btn = QPushButton(t("button.batch_generate", default="⚡批量生成"))
        batch_gen_btn.setToolTip(t("tooltip.batch_generate", 
            default="根据模板批量生成规则，例如为每个引脚PA0-15生成连锁规则"))
        btn_layout.addWidget(add_rule_btn)
        btn_layout.addWidget(del_rule_btn)
        btn_layout.addWidget(batch_gen_btn)
        left_layout.addLayout(btn_layout)
        splitter.addWidget(left)
        
        # 右侧：规则详情
        right = QWidget()
        right_layout = QVBoxLayout(right)
        
        form = QFormLayout()
        name_edit = QLineEdit()
        form.addRow(t("label.rule_name", default="规则名称:"), name_edit)
        
        source_type_combo = QComboBox()
        source_type_combo.addItems(["peripheral", "register", "field"])
        form.addRow(t("label.source_type", default="源类型:"), source_type_combo)
        
        source_periph = QLineEdit()
        source_periph.setPlaceholderText(t("placeholder.wildcard_hint", default="* 表示通配符，如 GPIO*"))
        form.addRow(t("label.source_peripheral", default="源外设:"), source_periph)
        
        source_reg = QLineEdit()
        source_reg.setPlaceholderText(t("placeholder.no_limit", default="留空表示不限"))
        form.addRow(t("label.source_register", default="源寄存器:"), source_reg)
        
        source_field = QLineEdit()
        source_field.setPlaceholderText(t("placeholder.no_limit", default="留空表示不限"))
        form.addRow(t("label.source_field", default="源位域:"), source_field)
        
        enabled_cb = QCheckBox(t("label.enabled", default="启用"))
        enabled_cb.setChecked(True)
        form.addRow(enabled_cb)
        
        right_layout.addLayout(form)
        
        # 动作列表
        right_layout.addWidget(QLabel(t("label.actions", default="连锁动作:")))
        actions_text = QTextEdit()
        actions_text.setPlaceholderText(
            t("placeholder.chain_actions",
              default="每行一个动作，格式：目标外设,目标寄存器,目标位域,动作类型\n"
                      "例如：PBCON,MODE0,MODE0,delete\n"
                      "支持变量：$PERIPHERAL, $REGISTER, $FIELD"))
        actions_text.setMaximumHeight(150)
        right_layout.addWidget(actions_text)
        
        right_layout.addStretch()
        splitter.addWidget(right)
        splitter.setSizes([250, 450])
        layout.addWidget(splitter)
        
        # 按钮
        btn_box = QHBoxLayout()
        save_btn = QPushButton(t("button.save", default="保存"))
        cancel_btn = QPushButton(t("button.cancel", default="取消"))
        btn_box.addStretch()
        btn_box.addWidget(save_btn)
        btn_box.addWidget(cancel_btn)
        layout.addLayout(btn_box)
        
        # 选择规则时加载详情
        def on_rule_selected():
            row = rules_list.currentRow()
            if 0 <= row < len(self.chain_rules_engine.rules):
                rule = self.chain_rules_engine.rules[row]
                name_edit.setText(rule.name)
                source_type_combo.setCurrentText(rule.source_type)
                source_periph.setText(rule.source_peripheral)
                source_reg.setText(rule.source_register)
                source_field.setText(rule.source_field)
                enabled_cb.setChecked(rule.enabled)
                actions_lines = []
                for a in rule.actions:
                    actions_lines.append(f"{a.target_peripheral},{a.target_register},{a.target_field},{a.action}")
                actions_text.setPlainText("\n".join(actions_lines))
        
        rules_list.currentRowChanged.connect(on_rule_selected)
        
        # 添加规则
        def add_rule():
            rule = ChainRule(name=t("label.new_rule", default="新规则"))
            self.chain_rules_engine.add_rule(rule)
            rules_list.addItem(f"✓ {rule.name}")
            rules_list.setCurrentRow(rules_list.count() - 1)
        
        add_rule_btn.clicked.connect(add_rule)
        
        # 删除规则
        def del_rule():
            row = rules_list.currentRow()
            if 0 <= row < len(self.chain_rules_engine.rules):
                self.chain_rules_engine.remove_rule(row)
                rules_list.takeItem(row)
        
        del_rule_btn.clicked.connect(del_rule)
        
        # 批量生成规则
        def batch_generate():
            """批量生成连锁规则"""
            from PyQt6.QtWidgets import (QDialog as BatchDialog, QVBoxLayout as BatchVLayout,
                QHBoxLayout as BatchHLayout, QLabel as BatchLabel, QLineEdit as BatchLineEdit,
                QPushButton as BatchBtn, QSpinBox as BatchSpin, QGroupBox as BatchGroup,
                QFormLayout as BatchForm, QListWidget as BatchList, QCheckBox as BatchCheck,
                QDialogButtonBox)
            
            batch_dlg = BatchDialog(dialog)
            batch_dlg.setWindowTitle(t("dialog.batch_generate_rules", default="⚡批量生成连锁规则"))
            batch_dlg.setMinimumSize(550, 500)
            batch_lay = BatchVLayout(batch_dlg)
            
            # === 模板选择 ===
            tpl_group = BatchGroup(t("label.template", default="模板"))
            tpl_lay = BatchForm(tpl_group)
            
            tpl_combo = QComboBox()
            tpl_combo.addItems([
                t("tpl.gpio_pin", default="GPIO引脚 → 配置/上下拉/电平寄存器"),
                t("tpl.custom", default="自定义模板"),
            ])
            tpl_lay.addRow(t("label.template_type", default="模板类型:"), tpl_combo)
            batch_lay.addWidget(tpl_group)
            
            # === 参数设置 ===
            param_group = BatchGroup(t("label.params", default="参数"))
            param_form = BatchForm(param_group)
            
            # GPIO端口前缀
            port_prefix_edit = BatchLineEdit("PA,PB,PC,PD,PE")
            port_prefix_edit.setToolTip(t("tooltip.port_prefix", default="逗号分隔的端口前缀列表"))
            param_form.addRow(t("label.port_prefix", default="端口前缀:"), port_prefix_edit)
            
            # 引脚范围
            pin_range_widget = QWidget()
            pin_range_lay = BatchHLayout(pin_range_widget)
            pin_range_lay.setContentsMargins(0, 0, 0, 0)
            pin_start_spin = BatchSpin()
            pin_start_spin.setRange(0, 31)
            pin_start_spin.setValue(0)
            pin_end_spin = BatchSpin()
            pin_end_spin.setRange(0, 31)
            pin_end_spin.setValue(15)
            pin_range_lay.addWidget(pin_start_spin)
            pin_range_lay.addWidget(BatchLabel("-"))
            pin_range_lay.addWidget(pin_end_spin)
            param_form.addRow(t("label.pin_range", default="引脚范围:"), pin_range_widget)
            
            # 目标配置寄存器后缀
            config_reg_edit = BatchLineEdit("CON")
            param_form.addRow(t("label.config_reg", default="配置寄存器后缀:"), config_reg_edit)
            config_field_edit = BatchLineEdit("MODE")
            param_form.addRow(t("label.config_field", default="配置位域前缀:"), config_field_edit)
            
            # 目标上下拉寄存器
            pull_reg_edit = BatchLineEdit("PH")
            param_form.addRow(t("label.pull_reg", default="上下拉寄存器后缀:"), pull_reg_edit)
            pull_field_edit = BatchLineEdit("PUPD")
            param_form.addRow(t("label.pull_field", default="上下拉位域前缀:"), pull_field_edit)
            
            # 目标电平寄存器
            level_reg_edit = BatchLineEdit("VEV")
            param_form.addRow(t("label.level_reg", default="电平寄存器后缀:"), level_reg_edit)
            level_field_edit = BatchLineEdit("LEV")
            param_form.addRow(t("label.level_field", default="电平位域前缀:"), level_field_edit)
            
            batch_lay.addWidget(param_group)
            
            # === 预览 ===
            preview_group = BatchGroup(t("label.preview", default="预览（将生成的规则）"))
            preview_lay = BatchVLayout(preview_group)
            preview_list = BatchList()
            preview_lay.addWidget(preview_list)
            batch_lay.addWidget(preview_group)
            
            count_label = BatchLabel("")
            batch_lay.addWidget(count_label)
            
            def refresh_preview():
                preview_list.clear()
                prefixes = [p.strip() for p in port_prefix_edit.text().split(",") if p.strip()]
                start_pin = pin_start_spin.value()
                end_pin = pin_end_spin.value()
                rules_count = 0
                
                for prefix in prefixes:
                    for pin in range(start_pin, end_pin + 1):
                        name = f"{prefix}{pin}"
                        port = prefix  # PA, PB, etc.
                        con_reg = f"{port}{config_reg_edit.text()}"
                        ph_reg = f"{port}{pull_reg_edit.text()}"
                        vev_reg = f"{port}{level_reg_edit.text()}"
                        mode_field = f"{config_field_edit.text()}{pin}"
                        pupd_field = f"{pull_field_edit.text()}{pin}"
                        lev_field = f"{level_field_edit.text()}{pin}"
                        
                        preview_list.addItem(
                            f"✓ 删除 {name} → 删除 {con_reg}.{mode_field}, {ph_reg}.{pupd_field}, {vev_reg}.{lev_field}")
                        rules_count += 1
                
                count_label.setText(t("label.total_rules", default=f"共 {rules_count} 条规则"))
            
            # 连接信号实时预览
            port_prefix_edit.textChanged.connect(refresh_preview)
            pin_start_spin.valueChanged.connect(refresh_preview)
            pin_end_spin.valueChanged.connect(refresh_preview)
            config_reg_edit.textChanged.connect(refresh_preview)
            config_field_edit.textChanged.connect(refresh_preview)
            pull_reg_edit.textChanged.connect(refresh_preview)
            pull_field_edit.textChanged.connect(refresh_preview)
            level_reg_edit.textChanged.connect(refresh_preview)
            level_field_edit.textChanged.connect(refresh_preview)
            
            refresh_preview()
            
            # 按钮
            btn_box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            btn_box.accepted.connect(batch_dlg.accept)
            btn_box.rejected.connect(batch_dlg.reject)
            batch_lay.addWidget(btn_box)
            
            if batch_dlg.exec() == BatchDialog.DialogCode.Accepted:
                # 生成规则
                prefixes = [p.strip() for p in port_prefix_edit.text().split(",") if p.strip()]
                start_pin = pin_start_spin.value()
                end_pin = pin_end_spin.value()
                generated = 0
                
                for prefix in prefixes:
                    for pin in range(start_pin, end_pin + 1):
                        name = f"{prefix}{pin}"
                        port = prefix
                        con_reg = f"{port}{config_reg_edit.text()}"
                        ph_reg = f"{port}{pull_reg_edit.text()}"
                        vev_reg = f"{port}{level_reg_edit.text()}"
                        mode_field = f"{config_field_edit.text()}{pin}"
                        pupd_field = f"{pull_field_edit.text()}{pin}"
                        lev_field = f"{level_field_edit.text()}{pin}"
                        
                        rule = ChainRule(
                            name=f"删除{name}时连锁删除配置",
                            enabled=True,
                            source_type="field",
                            source_peripheral="GPIO*",
                            source_register="*" + name,
                            source_field=name,
                            trigger="delete",
                            actions=[
                                ChainAction(target_peripheral="*", target_register=con_reg,
                                           target_field=mode_field, action="delete",
                                           description=f"删除{con_reg}.{mode_field}"),
                                ChainAction(target_peripheral="*", target_register=ph_reg,
                                           target_field=pupd_field, action="delete",
                                           description=f"删除{ph_reg}.{pupd_field}"),
                                ChainAction(target_peripheral="*", target_register=vev_reg,
                                           target_field=lev_field, action="delete",
                                           description=f"删除{vev_reg}.{lev_field}"),
                            ]
                        )
                        self.chain_rules_engine.add_rule(rule)
                        rules_list.addItem(f"✓ {rule.name}")
                        generated += 1
                
                self.chain_rules_engine.save_rules()
                QMessageBox.information(dialog,
                    t("msg.batch_gen_complete", default="批量生成完成"),
                    t("msg.batch_gen_result", default=f"已生成 {generated} 条连锁规则"))
        
        batch_gen_btn.clicked.connect(batch_generate)
        
        # 保存
        def save():
            row = rules_list.currentRow()
            if 0 <= row < len(self.chain_rules_engine.rules):
                # 解析动作
                actions = []
                for line in actions_text.toPlainText().strip().split("\n"):
                    if not line.strip():
                        continue
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 2:
                        action = ChainAction(
                            target_peripheral=parts[0],
                            target_register=parts[1],
                            target_field=parts[2] if len(parts) > 2 else "",
                            action=parts[3] if len(parts) > 3 else "delete"
                        )
                        actions.append(action)
                
                rule = ChainRule(
                    name=name_edit.text() or t("label.unnamed", default="未命名"),
                    enabled=enabled_cb.isChecked(),
                    source_type=source_type_combo.currentText(),
                    source_peripheral=source_periph.text(),
                    source_register=source_reg.text(),
                    source_field=source_field.text(),
                    actions=actions
                )
                self.chain_rules_engine.update_rule(row, rule)
                rules_list.item(row).setText(
                    f"{'✓' if rule.enabled else '✗'} {rule.name}")
            
            self.chain_rules_engine.enabled = enable_cb.isChecked()
            self.chain_rules_engine.save_rules()
            dialog.accept()
        
        save_btn.clicked.connect(save)
        cancel_btn.clicked.connect(dialog.reject)
        
        dialog.exec()

    def set_language(self, locale: str):
        """设置语言"""
        if hasattr(self, 'i18n_manager') and self.i18n_manager:
            self.i18n_manager.set_locale(locale)
            language_name = "中文" if locale == "zh_CN" else "English"
            self.layout_manager.update_status(t("msg.language_changed", language=language_name))
            self.logger.info(f"语言已切换为: {language_name}")
            
            # 重新创建菜单栏以更新文本
            self._recreate_menu_bar()
            
            # 重新创建工具栏以更新文本
            self._recreate_toolbar()
            
            # 更新搜索相关文本
            self._update_search_ui()
            
            # 重新创建标签页以更新文本（但保留数据）
            self._recreate_tabs()
    
    def _recreate_toolbar(self):
        """重新创建工具栏以更新语言"""
        # 删除所有现有工具栏
        toolbars = self.findChildren(QToolBar)
        for toolbar in toolbars:
            self.removeToolBar(toolbar)
        
        # 重新创建工具栏
        from .components.toolbar import ToolBarBuilder
        toolbar_builder = ToolBarBuilder(self, self)
        toolbar_builder.create()
    
    def _recreate_menu_bar(self):
        """重新创建菜单栏以更新语言"""
        # 清除现有菜单栏
        menubar = self.menuBar()
        if menubar:
            menubar.clear()
        
        # 重新创建菜单栏
        from .components.menu_bar import MenuBarBuilder
        menu_builder = MenuBarBuilder(self, self)
        menu_builder.create()
    
    def _update_search_ui(self):
        """更新搜索相关的UI文本"""
        # 更新搜索标签
        search_label = self.layout_manager.get_widget('search_label')
        if search_label:
            search_label.setText(t("search.label"))
        
        # 更新搜索框占位符
        search_edit = self.layout_manager.get_widget('search_edit')
        if search_edit:
            search_edit.setPlaceholderText(t("search.placeholder"))
        
        # 更新搜索按钮文本
        search_prev_btn = self.layout_manager.get_widget('search_prev_btn')
        if search_prev_btn:
            search_prev_btn.setText(t("search.prev"))
        
        search_next_btn = self.layout_manager.get_widget('search_next_btn')
        if search_next_btn:
            search_next_btn.setText(t("search.next"))
    
    def _update_tab_titles(self):
        """更新标签页标题（不重新创建标签页）"""
        tab_widget = self.layout_manager.get_widget('tab_widget')
        if not tab_widget:
            return
        
        # 更新标签页标题
        tab_widget.setTabText(0, t("tab.basic_info"))
        tab_widget.setTabText(1, t("tab.peripherals"))
        tab_widget.setTabText(2, t("tab.interrupts"))
        tab_widget.setTabText(3, t("tab.preview"))
    
    def _recreate_tabs(self):
        """重新创建标签页以更新语言"""
        # 获取标签页控件
        tab_widget = self.layout_manager.get_widget('tab_widget')
        if not tab_widget:
            return
        
        # 保存当前选中的标签页索引
        current_index = tab_widget.currentIndex()
        
        # 保存当前状态快照（包括设备信息和选中状态）
        state_snapshot = self.state_manager.get_device_state_snapshot()
        
        # 清理 realtime_preview 资源（在删除标签页之前）
        realtime_preview = self.layout_manager.get_widget('realtime_preview')
        if realtime_preview and hasattr(realtime_preview, 'cleanup'):
            try:
                realtime_preview.cleanup()
            except Exception as e:
                import logging
                logging.warning(f"清理 realtime_preview 时出错: {e}")
        
        # 清除所有标签页
        while tab_widget.count() > 0:
            tab_widget.removeTab(0)
        
        # 重新创建标签页
        self.layout_manager.create_basic_info_tab(tab_widget)
        self.layout_manager.create_peripheral_tab(tab_widget)
        self.layout_manager.create_interrupt_tab(tab_widget)
        
        # 重新连接UI信号（重要：重新创建标签页后必须重新连接信号）
        self.peripheral_manager.connect_ui_signals()
        self.setup_signals()
        
        # 重新连接中断表格右键菜单
        irq_table = self.layout_manager.get_widget('irq_table')
        if irq_table:
            irq_table.customContextMenuRequested.disconnect()
            irq_table.customContextMenuRequested.connect(self.on_irq_context_menu)
        
        # 恢复状态快照（包括设备信息和选中状态）
        self.state_manager.restore_device_state(state_snapshot)
        
        # 刷新UI以显示恢复的数据
        # 直接传递设备信息，避免通过coordinator获取
        self.device_info_manager.update_ui_from_device_info(self.state_manager.device_info)
        self.peripheral_manager.update_peripheral_tree()
        self._update_interrupt_table()
        
        # 恢复之前选中的标签页
        if current_index >= 0 and current_index < tab_widget.count():
            tab_widget.setCurrentIndex(current_index)
        
        # 重新填充数据到新创建的控件中
        self._refresh_all_data()
    
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
        self.device_info_manager.update_device_info_from_ui()

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

    # ===================== 地址冲突实时检测 =====================
    def _setup_conflict_detection(self):
        """设置冲突检测（在数据变更时自动触发）"""
        # 注册状态变更回调
        self.state_manager.register_state_change_callback(self._on_data_changed_detect_conflicts)
        # 注册冲突回调
        self.conflict_detector.register_callback(self._on_conflicts_updated)

    def _on_data_changed_detect_conflicts(self):
        """数据变更时执行冲突检测"""
        if hasattr(self, 'conflict_detector') and hasattr(self, 'state_manager'):
            try:
                self.conflict_detector.detect_all(self.state_manager.device_info)
            except Exception as e:
                self.logger.error(f"冲突检测失败: {e}")

    def _on_conflicts_updated(self, conflicts):
        """冲突列表更新时的回调"""
        try:
            summary = self.conflict_detector.get_summary()
            error_count = summary.get('errors', 0)

            # 更新状态栏
            if error_count > 0:
                self.layout_manager.update_status(
                    f"⚠ 检测到 {error_count} 个地址冲突"
                )
            elif hasattr(self, 'layout_manager'):
                pass  # 不覆盖其他状态消息

        except Exception as e:
            self.logger.error(f"冲突回调处理失败: {e}")

    def show_address_conflicts(self):
        """显示地址冲突检测面板"""
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
            QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox)

        # 运行检测
        self.conflict_detector.detect_all(self.state_manager.device_info)
        conflicts = self.conflict_detector.conflicts

        dialog = QDialog(self)
        dialog.setWindowTitle("地址冲突检测")
        dialog.setMinimumSize(800, 500)
        layout = QVBoxLayout(dialog)

        # 摘要
        summary = self.conflict_detector.get_summary()
        summary_label = QLabel(
            f"检测完成：共 {summary['total']} 个冲突 "
            f"({summary['errors']} 错误, {summary['warnings']} 警告)"
        )
        if summary['errors'] > 0:
            summary_label.setStyleSheet("color: red; font-weight: bold; font-size: 14px;")
        else:
            summary_label.setStyleSheet("color: green; font-weight: bold; font-size: 14px;")
        layout.addWidget(summary_label)

        # 冲突表格
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["严重程度", "类型", "位置", "消息", "详情"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setRowCount(len(conflicts))

        for row, c in enumerate(conflicts):
            severity_item = QTableWidgetItem("🔴 错误" if c.severity == ConflictSeverity.ERROR else "🟡 警告")
            type_map = {
                ConflictType.PERIPHERAL_ADDRESS_OVERLAP: "外设地址重叠",
                ConflictType.PERIPHERAL_BASE_DUPLICATE: "外设基地址重复",
                ConflictType.REGISTER_OFFSET_DUPLICATE: "寄存器偏移重复",
                ConflictType.FIELD_BIT_OVERLAP: "位域位重叠",
                ConflictType.INTERRUPT_VALUE_DUPLICATE: "中断号重复",
            }
            table.setItem(row, 0, severity_item)
            table.setItem(row, 1, QTableWidgetItem(type_map.get(c.conflict_type, str(c.conflict_type))))
            table.setItem(row, 2, QTableWidgetItem(c.location))
            table.setItem(row, 3, QTableWidgetItem(c.message))
            table.setItem(row, 4, QTableWidgetItem(c.detail))

        layout.addWidget(table)

        # 按钮
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("刷新检测")
        refresh_btn.clicked.connect(lambda: (
            self.conflict_detector.detect_all(self.state_manager.device_info),
            dialog.accept(),
            self.show_address_conflicts()
        ))
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(refresh_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        dialog.exec()

    def closeEvent(self, event):
        """关闭事件 - 保存窗口偏好设置"""
        # 保存窗口几何信息到配置
        if hasattr(self, 'layout_manager'):
            self.layout_manager.save_window_geometry()
        event.accept()


def main():
    """主函数"""
    app = QApplication(sys.argv)
    window = MainWindowRefactored()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()