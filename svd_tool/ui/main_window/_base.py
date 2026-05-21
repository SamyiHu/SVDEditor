"""
重构后的主窗口 - Mixin 组合入口
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

from ...core.data_model import DeviceInfo, Peripheral, Register, Field, Interrupt, CPUInfo
from ...core.svd_parser import SVDParser
from ...core.svd_generator import SVDGenerator
from ...core.command_history import CommandHistory, Command
from ...core.validators import Validator, ValidationError
from ..tree_manager import TreeManager
from ..dialog_factories import DialogFactory
from ..widgets.visualization_widget import VisualizationWidget
from ..widgets.address_map_widget import AddressMapWidget
from ..widgets.bit_field_widget import BitFieldWidget

# 组件
from ..components.state_manager import StateManager
from ..components.layout_manager import LayoutManager
from ..components.peripheral_manager import PeripheralManager
from ..components.menu_bar import MenuBarBuilder
from ..components.toolbar import ToolBarBuilder
from ..components.preview_manager import PreviewManager
from ..managers.file_operations import FileOperations
from ..managers.device_info_manager import DeviceInfoManager
from ..managers.search_manager import SearchManager
from ..managers.batch_operations_manager import BatchOperationsManager
from ..coordinator import Coordinator
from ...i18n.i18n import I18nManager, get_i18n_manager, set_i18n_manager, t

from ...utils.helpers import pretty_xml
from ...utils.logger import Logger
from ...core.chain_rules import ChainRulesEngine
from ...core.address_conflict_detector import AddressConflictDetector, ConflictType, ConflictSeverity
from ...core.document_manager import DocumentManager, DocumentState

# Mixin 导入
from ._file_actions import FileActionsMixin
from ._edit_actions import EditActionsMixin
from ._document_actions import DocumentActionsMixin
from ._view_actions import ViewActionsMixin
from ._tool_actions import ToolActionsMixin
from ._settings_actions import SettingsActionsMixin
from ._event_handlers import EventHandlersMixin


class MainWindowRefactored(
    FileActionsMixin,
    EditActionsMixin,
    DocumentActionsMixin,
    ViewActionsMixin,
    ToolActionsMixin,
    SettingsActionsMixin,
    EventHandlersMixin,
    QMainWindow
):
    """重构后的主窗口 - 使用 Mixin 组合模式拆分职责"""

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

        # 继承外设不写入寄存器开关（默认开启）
        self.skip_derived_registers = True
        self.state_manager.skip_derived_registers = True
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

        # 初始化 AI 助手（可选依赖，未安装时不影响其他功能）
        self.ai_assistant = None
        try:
            from ...ai_assistant import create_ai_assistant
            self.ai_assistant = create_ai_assistant(self.coordinator, self)
            # 延迟初始化 UI（在 init_ui 之后）
        except ImportError:
            pass
        except Exception as e:
            self.logger.warning(f"AI 助手初始化失败（非致命）: {e}")

        self.init_ui()
        self.logger.debug(f"init_ui完成，窗口大小: {self.size()}")

        # 初始化 AI 助手 UI（必须在 init_ui 之后，因为需要主窗口已创建）
        if self.ai_assistant is not None:
            try:
                self.ai_assistant.initialize()
            except Exception as e:
                self.logger.warning(f"AI 助手 UI 初始化失败（非致命）: {e}")
                self.ai_assistant = None

        self.init_data()
        self.setup_signals()

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
                # 创建预览标签页（占位）
                self.layout_manager.create_preview_tab(tab_widget)
                # 设置预览管理器（注入预览组件到标签页）
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

        # 连接文档管理器的所有关闭信号
        self.document_manager.all_documents_closed.connect(self._on_all_documents_closed_show_welcome)

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
            welcome_page.files_dropped.connect(self._on_files_dropped)

        # 连接搜索功能（使用search_manager）
        self.search_manager.connect_search_signals()

        # 连接预览标签页的导出按钮
        if self.preview_manager and self.preview_manager.preview_widget:
            export_btn = getattr(self.preview_manager.preview_widget, '_export_btn', None)
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
            periph_tree.collapsed.connect(self._on_tree_item_collapsed)
            periph_tree.expanded.connect(self._on_tree_item_expanded)

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

        # 统一文本控件的右键菜单风格
        self._install_styled_context_menus()

        # 基本信息→预览实时同步
        self._basic_info_updating = False
        self._connect_basic_info_signals()

    @staticmethod
    def _show_styled_text_menu(widget, pos):
        """为文本控件创建统一风格的右键菜单"""
        from ...utils.context_menu_filter import _build_text_menu
        menu = _build_text_menu(widget)
        if menu.actions():
            menu.exec(widget.mapToGlobal(pos))

    def _install_styled_context_menus(self):
        """为所有文本输入控件安装统一风格的右键菜单"""
        from PyQt6.QtWidgets import QLineEdit, QPlainTextEdit, QTextEdit

        # 基本信息页的 QLineEdit 控件
        line_edit_keys = [
            'ic_name_edit', 'ic_desc_edit', 'version_edit',
            'cpu_name_edit', 'cpu_rev_edit',
            'company_name_edit', 'copyright_edit', 'author_edit'
        ]
        for key in line_edit_keys:
            w = self.layout_manager.get_widget(key)
            if w and isinstance(w, QLineEdit):
                w.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                w.customContextMenuRequested.connect(
                    lambda pos, _w=w: self._show_styled_text_menu(_w, pos))

        # SVD 预览编辑器
        if self.preview_manager and self.preview_manager.preview_widget:
            pe = getattr(self.preview_manager.preview_widget, 'preview_edit', None)
            if pe and isinstance(pe, (QPlainTextEdit, QTextEdit)):
                pe.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                pe.customContextMenuRequested.connect(
                    lambda pos, _w=pe: self._show_styled_text_menu(_w, pos))

        # 编辑对话框中的描述字段等（通过全局事件过滤处理 QPlainTextEdit/QTextEdit）
        from ...utils.context_menu_filter import install_text_context_menu_filter
        install_text_context_menu_filter(self)

    # ==================== 基本信息实时同步 ====================

    def _connect_basic_info_signals(self):
        """连接基本信息页控件的变更信号"""
        # QLineEdit: textEdited 只在用户输入时触发（不含 setText）
        for key in ('ic_name_edit', 'ic_desc_edit', 'version_edit',
                     'cpu_name_edit', 'cpu_rev_edit',
                     'company_name_edit', 'copyright_edit', 'author_edit'):
            w = self.layout_manager.get_widget(key)
            if w:
                w.textEdited.connect(self._on_basic_info_edited)

        # QComboBox
        for key in ('svd_version_combo', 'endian_combo', 'license_combo'):
            w = self.layout_manager.get_widget(key)
            if w:
                w.currentTextChanged.connect(self._on_basic_info_edited)

        # ToggleSwitch / QCheckBox
        for key in ('mpu_combo', 'fpu_combo'):
            w = self.layout_manager.get_widget(key)
            if w:
                if hasattr(w, 'stateChanged'):
                    w.stateChanged.connect(self._on_basic_info_edited)
                elif hasattr(w, 'toggled'):
                    w.toggled.connect(self._on_basic_info_edited)

        # SpinBox
        for key in ('nvic_prio_spin',):
            w = self.layout_manager.get_widget(key)
            if w:
                w.valueChanged.connect(self._on_basic_info_edited)

    # ===================== 地址冲突实时检测 =====================
    def _setup_conflict_detection(self):
        """设置冲突检测（在数据变更时自动触发）"""
        # 注册状态变更回调
        self.state_manager.register_state_change_callback(self._on_data_changed_detect_conflicts)
        # 注册冲突回调
        self.conflict_detector.register_callback(self._on_conflicts_updated)

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
