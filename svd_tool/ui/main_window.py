# svd_tool/ui/main_window.py
import sys
import os
from typing import Dict, List, Optional, cast
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QTreeWidget,
    QTreeWidgetItem, QTabWidget, QSplitter, QMessageBox,
    QFileDialog, QMenu, QHeaderView, QSpinBox, QComboBox,
    QGroupBox, QToolBar, QStatusBar, QToolButton, QInputDialog, QAbstractItemView,
    QDockWidget
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
from .components.menu_bar import MenuBarBuilder
from .components.toolbar import ToolBarBuilder
from ..utils.helpers import pretty_xml, format_hex
from ..utils.logger import Logger



class MainWindow(QMainWindow):
    """主窗口"""
    
    # 信号定义
    data_changed = pyqtSignal()
    selection_changed = pyqtSignal(str, str)  # (item_type, item_name)
    
    def __init__(self):
        super().__init__()
        self.device_info = DeviceInfo()
        self.command_history = CommandHistory()
        self.tree_manager = TreeManager()
        self.dialog_factory = DialogFactory(self)
        self.logger = Logger("svd_tool")
        # GUI 日志处理器（会在 create_log_panel 中绑定）
        self._gui_log_handler = None
        # 是否在发生错误时自动保存日志
        self.auto_save_error = True
        
        # 当前选中项
        self.current_peripheral: Optional[str] = None
        self.current_register: Optional[str] = None
        self.current_field: Optional[str] = None
        
        # 搜索相关
        self.search_results: List[QTreeWidgetItem] = []
        self.current_search_index: int = -1
        
        self.init_ui()
        self.init_data()
        self.setup_signals()

        # 启用拖放功能 - 添加这一行
        self.enable_tree_drag_drop()
        
        # 应用样式
        self.apply_styles()
    
    # ===================== 状态快照方法 =====================
    def _get_device_state_snapshot(self):
        """获取设备状态快照（用于撤销）"""
        import copy
        
        # 创建深拷贝的状态快照
        snapshot = {
            'device_info': {
                'name': self.device_info.name,
                'version': self.device_info.version,
                'description': self.device_info.description,
                'svd_version': self.device_info.svd_version,
                'peripherals': copy.deepcopy(self.device_info.peripherals),
                'interrupts': copy.deepcopy(self.device_info.interrupts),
                'cpu': copy.deepcopy(self.device_info.cpu),
            },
            'selection': {
                'peripheral': self.current_peripheral,
                'register': self.current_register,
                'field': self.current_field
            }
        }
        
        return snapshot

    def _restore_device_state(self, snapshot):
        """恢复设备状态"""
        import copy
        
        if not snapshot:
            return
        
        # 恢复设备信息
        if 'device_info' in snapshot:
            device_data = snapshot['device_info']
            self.device_info.name = device_data.get('name', '')
            self.device_info.version = device_data.get('version', '1.0')
            self.device_info.description = device_data.get('description', '')
            self.device_info.svd_version = device_data.get('svd_version', '1.3')
            
            # 恢复外设
            if 'peripherals' in device_data:
                self.device_info.peripherals = copy.deepcopy(device_data['peripherals'])
            
            # 恢复中断
            if 'interrupts' in device_data:
                self.device_info.interrupts = copy.deepcopy(device_data['interrupts'])
            
            # 恢复CPU信息
            if 'cpu' in device_data:
                self.device_info.cpu = copy.deepcopy(device_data['cpu'])
        
        # 恢复选中状态
        if 'selection' in snapshot:
            selection = snapshot['selection']
            self.current_peripheral = selection.get('peripheral')
            self.current_register = selection.get('register')
            self.current_field = selection.get('field')
        
        # 更新UI
        self.update_ui_from_device_info(sort_by_name=False)

    # ===================== UI初始化方法 =====================
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("SVD工具 - 专业版")
        self.setGeometry(100, 100, 1600, 900)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 创建菜单栏（使用组件）
        menu_builder = MenuBarBuilder(self, self)
        menu_builder.create()
        
        # 创建工具栏（使用组件）
        toolbar_builder = ToolBarBuilder(self, self)
        toolbar_builder.create()
        
        # 创建状态栏
        self.create_status_bar()
        
        # 搜索栏
        self.create_search_bar(main_layout)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # 创建各个标签页
        self.create_basic_info_tab()
        self.create_peripheral_tab()
        self.create_interrupt_tab()
        self.create_preview_tab()
        
        # 设置默认标签页
        self.tab_widget.setCurrentIndex(0)

    
    
    def create_status_bar(self):
        """创建状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # 状态标签
        self.status_label = QLabel("就绪")
        self.status_bar.addWidget(self.status_label)
        
        # 数据统计标签
        self.data_stats_label = QLabel("")
        self.status_bar.addPermanentWidget(self.data_stats_label)
        
        # 更新数据统计
        self.update_data_stats()
    
    def create_search_bar(self, parent_layout):
        """创建搜索栏"""
        search_layout = QHBoxLayout()
        
        search_label = QLabel("搜索:")
        search_layout.addWidget(search_label)
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索外设/寄存器/位域...")
        self.search_edit.textChanged.connect(self.on_search_text_changed)
        search_layout.addWidget(self.search_edit)
        
        self.search_prev_btn = QPushButton("上一个")
        self.search_prev_btn.clicked.connect(self.goto_prev_search)
        self.search_prev_btn.setEnabled(False)
        search_layout.addWidget(self.search_prev_btn)
        
        self.search_next_btn = QPushButton("下一个")
        self.search_next_btn.clicked.connect(self.goto_next_search)
        self.search_next_btn.setEnabled(False)
        search_layout.addWidget(self.search_next_btn)
        
        self.search_count_label = QLabel("")
        search_layout.addWidget(self.search_count_label)
        
        search_layout.addStretch()
        parent_layout.addLayout(search_layout)
    
    def create_basic_info_tab(self):
        """创建基础信息标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 基本信息组
        basic_group = QGroupBox("基本信息")
        basic_layout = QHBoxLayout(basic_group)
        
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()
        
        # 左侧表单
        left_layout.addWidget(QLabel("IC型号:"))
        self.ic_name_edit = QLineEdit()
        self.ic_name_edit.setPlaceholderText("例如: STM32F103C8")
        left_layout.addWidget(self.ic_name_edit)
        
        left_layout.addWidget(QLabel("厂商:"))
        self.vendor_edit = QLineEdit()
        self.vendor_edit.setPlaceholderText("例如: STMicroelectronics")
        left_layout.addWidget(self.vendor_edit)
        
        left_layout.addWidget(QLabel("设备版本:"))
        self.device_version_edit = QLineEdit()
        self.device_version_edit.setText("1.0")
        left_layout.addWidget(self.device_version_edit)
        
        # 右侧表单
        right_layout.addWidget(QLabel("内核:"))
        self.core_edit = QLineEdit()
        self.core_edit.setText("CM0+")
        right_layout.addWidget(self.core_edit)
        
        right_layout.addWidget(QLabel("CPU版本:"))
        self.cpu_revision_edit = QLineEdit()
        self.cpu_revision_edit.setText("r0p1")
        right_layout.addWidget(self.cpu_revision_edit)
        
        right_layout.addWidget(QLabel("SVD版本:"))
        self.svd_version_combo = QComboBox()
        self.svd_version_combo.addItems(["1.1", "1.3", "2.0"])
        self.svd_version_combo.setCurrentText("1.3")
        right_layout.addWidget(self.svd_version_combo)
        
        basic_layout.addLayout(left_layout)
        basic_layout.addLayout(right_layout)
        layout.addWidget(basic_group)
        
        # CPU高级配置组
        cpu_group = QGroupBox("CPU高级配置")
        cpu_layout = QHBoxLayout(cpu_group)
        
        cpu_layout.addWidget(QLabel("NVIC优先级位数:"))
        self.nvic_prio_spin = QSpinBox()
        self.nvic_prio_spin.setRange(0, 8)
        self.nvic_prio_spin.setValue(4)
        cpu_layout.addWidget(self.nvic_prio_spin)
        
        cpu_layout.addWidget(QLabel("字节序:"))
        self.endian_combo = QComboBox()
        self.endian_combo.addItems(["little", "big"])
        cpu_layout.addWidget(self.endian_combo)
        
        layout.addWidget(cpu_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        apply_btn = QPushButton("应用配置")
        apply_btn.clicked.connect(self.apply_basic_config)
        button_layout.addWidget(apply_btn)
        
        reset_btn = QPushButton("重置")
        reset_btn.clicked.connect(self.reset_basic_config)
        button_layout.addWidget(reset_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        layout.addStretch()
        self.tab_widget.addTab(tab, "基础信息")
    
    def create_peripheral_tab(self):
        """创建外设标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 按钮栏
        button_layout = QHBoxLayout()
        
        self.add_periph_btn_main = QPushButton("添加外设")
        self.add_periph_btn_main.clicked.connect(self.add_peripheral)
        self.add_periph_btn_main.setObjectName('btnAddPeriph')
        button_layout.addWidget(self.add_periph_btn_main)
        
        self.add_reg_btn_main = QPushButton("添加寄存器")
        self.add_reg_btn_main.clicked.connect(self.add_register)
        self.add_reg_btn_main.setObjectName('btnAddReg')
        self.add_reg_btn_main.setEnabled(False)
        button_layout.addWidget(self.add_reg_btn_main)
        
        self.add_field_btn_main = QPushButton("添加位域")
        self.add_field_btn_main.clicked.connect(self.add_field)
        self.add_field_btn_main.setObjectName('btnAddField')
        self.add_field_btn_main.setEnabled(False)
        button_layout.addWidget(self.add_field_btn_main)
        
        delete_btn = QPushButton("删除选中")
        delete_btn.clicked.connect(self.delete_selected)
        delete_btn.setObjectName('btnDelete')
        button_layout.addWidget(delete_btn)

        # 排序与移动控件（放在外设子页面）
        sort_menu = QToolButton(self)
        sort_menu.setText("排序")
        sort_menu.setObjectName('btnSort')
        sort_menu.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        sort_actions_menu = QMenu(self)
        sort_alpha_action = QAction("按字母排序", self)
        sort_alpha_action.triggered.connect(self.sort_items_alphabetically)
        sort_actions_menu.addAction(sort_alpha_action)
        sort_addr_action = QAction("按地址排序", self)
        sort_addr_action.triggered.connect(self.sort_items_by_address)
        sort_actions_menu.addAction(sort_addr_action)

        sort_menu.setMenu(sort_actions_menu)
        button_layout.addWidget(sort_menu)

        move_up_btn = QPushButton("上移")
        move_up_btn.clicked.connect(self.move_item_up)
        move_up_btn.setObjectName('btnMoveUp')
        button_layout.addWidget(move_up_btn)

        move_down_btn = QPushButton("下移")
        move_down_btn.clicked.connect(self.move_item_down)
        move_down_btn.setObjectName('btnMoveDown')
        button_layout.addWidget(move_down_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # 左侧：树控件
        self.tree_widget = self.tree_manager.create_tree_widget()
        self.tree_widget.setMinimumWidth(300)  # 减小宽度
        splitter.addWidget(self.tree_widget)
        
        # 右侧：详细信息
        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(2, 2, 2, 2)
        detail_layout.setSpacing(4)
        
        # 标题标签（更紧凑）
        self.detail_label = QLabel("选中项目以查看详细信息")
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_label.setStyleSheet("font-size: 12px; color: #666; padding: 2px;")
        detail_layout.addWidget(self.detail_label)
        
        # 可视化控件替换原来的文本详情
        self.visualization_widget = VisualizationWidget()
        self.visualization_widget.main_window = self  # 设置主窗口引用
        self.visualization_widget.setMinimumHeight(250)  # 增加高度
        detail_layout.addWidget(self.visualization_widget)
        
        self.detail_table = QTreeWidget()
        self.detail_table.setHeaderLabels(["属性", "值"])
        self.detail_table.setColumnWidth(0, 150)
        detail_layout.addWidget(self.detail_table)
        
        splitter.addWidget(detail_widget)
        
        # 设置分割比例（左侧更窄）
        splitter.setSizes([500, 700])
        
        self.tab_widget.addTab(tab, "外设寄存器")
    
    def create_interrupt_tab(self):
        """创建中断标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 添加中断表单
        irq_form_layout = QHBoxLayout()
        
        irq_form_layout.addWidget(QLabel("中断名:"))
        self.irq_name_edit = QLineEdit()
        self.irq_name_edit.setPlaceholderText("例如: USART1_IRQ")
        irq_form_layout.addWidget(self.irq_name_edit)
        
        irq_form_layout.addWidget(QLabel("中断号:"))
        self.irq_value_spin = QSpinBox()
        self.irq_value_spin.setRange(0, 255)
        irq_form_layout.addWidget(self.irq_value_spin)
        
        irq_form_layout.addWidget(QLabel("关联外设:"))
        self.irq_periph_combo = QComboBox()
        irq_form_layout.addWidget(self.irq_periph_combo)
        
        add_irq_btn = QPushButton("添加中断")
        add_irq_btn.clicked.connect(self.add_interrupt)
        add_irq_btn.setObjectName('btnAddIrq')
        # add_irq_btn.setStyleSheet("background-color: #4CAF50; color: white; padding:4px 8px; border-radius:4px;")
        irq_form_layout.addWidget(add_irq_btn)
        
        layout.addLayout(irq_form_layout)
        
        # 中断列表
        self.irq_tree = QTreeWidget()
        self.irq_tree.setHeaderLabels(["中断名", "中断号", "关联外设", "描述"])
        header = self.irq_tree.header()
        if header is not None:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.irq_tree)
        
        self.tab_widget.addTab(tab, "中断配置")
    
    def create_preview_tab(self):
        """创建预览标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 按钮栏
        preview_btn_layout = QHBoxLayout()
        
        # 预览页不再提供单独的“生成预览”按钮（使用工具栏的“生成SVD”）
        
        save_preview_btn = QPushButton("保存到文件")
        save_preview_btn.clicked.connect(self.save_svd_file)
        save_preview_btn.setObjectName('btnSavePreview')
        preview_btn_layout.addWidget(save_preview_btn)
        
        copy_preview_btn = QPushButton("复制到剪贴板")
        copy_preview_btn.clicked.connect(self.copy_preview_to_clipboard)
        preview_btn_layout.addWidget(copy_preview_btn)

        clear_preview_btn = QPushButton("清除预览")
        clear_preview_btn.clicked.connect(self.clear_preview)
        preview_btn_layout.addWidget(clear_preview_btn)
        
        preview_btn_layout.addStretch()
        layout.addLayout(preview_btn_layout)
        
        # 预览文本框
        self.preview_edit = QTextEdit()
        self.preview_edit.setReadOnly(True)
        self.preview_edit.setFont(QFont("Consolas", 10))
        # 禁用自动换行以保持 XML 排版
        try:
            from PyQt6.QtGui import QTextOption
            self.preview_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        except Exception:
            pass
        layout.addWidget(self.preview_edit)
        
        self.tab_widget.addTab(tab, "SVD预览")
    
    def init_data(self):
        """初始化数据"""
        # 更新对话框工厂的现有项目
        self.update_dialog_factory()
    
    def on_field_clicked(self, field):
        """位域点击事件处理"""
        # print(f"[DEBUG] Field clicked: {field.name}, current_peripheral={self.current_peripheral}, current_register={self.current_register}")
        if not self.current_peripheral or not self.current_register:
            # print("[DEBUG] Missing current peripheral or register")
            return
        
        # 查找对应的树项目并选中
        periph_item = self.find_tree_item_by_name(self.current_peripheral, "peripheral")
        if periph_item:
            periph_item.setExpanded(True)
            reg_item = self.find_tree_item_by_name(self.current_register, "register", periph_item)
            if reg_item:
                reg_item.setExpanded(True)
                field_item = self.find_tree_item_by_name(field.name, "field", reg_item)
                if field_item:
                    self.tree_widget.setCurrentItem(field_item)
                    self.tree_widget.scrollToItem(field_item)
                    # print(f"[DEBUG] Selected field item: {field.name}")
                else:
                    # print(f"[DEBUG] Field item not found: {field.name}")
                    pass
            else:
                # print(f"[DEBUG] Register item not found: {self.current_register}")
                pass
        else:
            # print(f"[DEBUG] Peripheral item not found: {self.current_peripheral}")
            pass
    
    def on_register_clicked(self, register):
        """寄存器点击事件处理"""
        # print(f"[DEBUG] Register clicked: {register.name}, current_peripheral={self.current_peripheral}")
        if not self.current_peripheral:
            # print("[DEBUG] Missing current peripheral")
            return
        
        # 检查当前外设是否是继承类型
        current_periph_name = self.current_peripheral
        if current_periph_name in self.device_info.peripherals:
            current_periph = self.device_info.peripherals[current_periph_name]
            
            # 如果当前外设是继承类型，跳转到父类外设
            if current_periph.derived_from:
                base_periph_name = current_periph.derived_from
                # print(f"[DEBUG] Current peripheral is derived from {base_periph_name}, jumping to parent")
                
                # 在树中查找父类外设
                base_periph_item = self.find_tree_item_by_name(base_periph_name, "peripheral")
                if base_periph_item:
                    base_periph_item.setExpanded(True)
                    # 在父类外设中查找寄存器
                    reg_item = self.find_tree_item_by_name(register.name, "register", base_periph_item)
                    if reg_item:
                        self.tree_widget.setCurrentItem(reg_item)
                        self.tree_widget.scrollToItem(reg_item)
                        # print(f"[DEBUG] Selected parent register item: {register.name} in {base_periph_name}")
                        return
                    else:
                        # print(f"[DEBUG] Register item not found in parent: {register.name}")
                        pass
                else:
                    # print(f"[DEBUG] Parent peripheral item not found: {base_periph_name}")
                    pass
        
        # 如果不是继承类型或父类查找失败，使用原来的逻辑
        # 查找对应的树项目并选中
        periph_item = self.find_tree_item_by_name(self.current_peripheral, "peripheral")
        if periph_item:
            periph_item.setExpanded(True)
            reg_item = self.find_tree_item_by_name(register.name, "register", periph_item)
            if reg_item:
                self.tree_widget.setCurrentItem(reg_item)
                self.tree_widget.scrollToItem(reg_item)
                # print(f"[DEBUG] Selected register item: {register.name}")
            else:
                # print(f"[DEBUG] Register item not found: {register.name}")
                pass
        else:
            # print(f"[DEBUG] Peripheral item not found: {self.current_peripheral}")
            pass
    
    def setup_signals(self):
        """设置信号连接"""
        # 树控件信号
        self.tree_widget.itemSelectionChanged.connect(self.on_tree_selection_changed)
        self.tree_widget.customContextMenuRequested.connect(self.on_tree_context_menu)
        self.tree_widget.itemDoubleClicked.connect(self.on_tree_item_double_clicked)
        
        # 中断树信号
        self.irq_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.irq_tree.customContextMenuRequested.connect(self.on_irq_context_menu)
        
        # 数据变化信号
        self.data_changed.connect(self.update_data_stats)
        self.data_changed.connect(self.update_irq_periph_combo)
        
        # 可视化控件信号
        if hasattr(self, 'visualization_widget'):
            self.visualization_widget.bit_field.field_clicked.connect(self.on_field_clicked)
            self.visualization_widget.address_map.register_clicked.connect(self.on_register_clicked)
    
    def apply_styles(self):
        """应用样式"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QTreeWidget {
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: white;
            }
            QTextEdit {
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: white;
            }
            QLineEdit {
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 3px;
                background-color: white;
            }
                                         
            QMenuBar::item {
                padding: 3px 10px;  
                color: #333;        
            }
            QMenuBar::item:selected {  
                background-color: #d0d0d0;  
                border-radius: 3px;         
            }

            QPushButton, QToolButton {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px 8px;
                background-color: #e0e0e0;
                min-height: 26px;
                margin: 2px;
            }
                           
            QPushButton:hover, QToolButton:hover {
                background-color: #cfcfcf;
            }
            QPushButton:pressed, QToolButton:pressed {
                background-color: #bfbfbf;
            }
            
            QToolButton {
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 5px 10px;
                background-color: #e0e0e0;
            }
            QToolBar { padding: 2px; spacing: 4px; }
            QToolBar QToolButton { min-width: 36px; min-height: 26px; padding: 1px 1px; }              

            QToolButton:hover {
                background-color: #d0d0d0;
            }
            QToolButton:pressed {
                background-color: #c0c0c0;
            }
            /* 特定按钮配色（使用 objectName 统一管理） */
            QPushButton#btnAddPeriph, QPushButton#btnAddReg, QPushButton#btnAddField, QPushButton#btnDelete,
            QToolButton#btnSort, QPushButton#btnMoveUp, QPushButton#btnMoveDown, QPushButton#btnSavePreview, 
            QPushButton#btnAddIrq {
                min-height: 28px;
                padding: 4px 10px;
                color: white;
            }
            QPushButton#btnAddPeriph { background-color: #4CAF50; }
            QPushButton#btnAddPeriph:hover { background-color: #45a049; }
            QPushButton#btnAddPeriph:pressed { background-color: #3a8a40; }

            QPushButton#btnAddReg { background-color: #2196F3; }
            QPushButton#btnAddReg:hover { background-color: #1e88e5; }
            QPushButton#btnAddReg:pressed { background-color: #1976d2; }

            QPushButton#btnAddField { background-color: #9C27B0; }
            QPushButton#btnAddField:hover { background-color: #8e24aa; }
            QPushButton#btnAddField:pressed { background-color: #7b1fa2; }

            QPushButton#btnDelete { background-color: #F44336; }
            QPushButton#btnDelete:hover { background-color: #e53935; }
            QPushButton#btnDelete:pressed { background-color: #d32f2f; }

            QToolButton#btnSort { background-color: #9e9e9e; color: white; }
            QToolButton#btnSort:hover { background-color: #8e8e8e; }
            QToolButton#btnSort:pressed { background-color: #7e7e7e; }

            QPushButton#btnMoveUp, QPushButton#btnMoveDown { background-color: #e0e0e0; color: #333; }
            QPushButton#btnMoveUp:hover, QPushButton#btnMoveDown:hover { background-color: #d5d5d5; }
            QPushButton#btnMoveUp:pressed, QPushButton#btnMoveDown:pressed { background-color: #c9c9c9; }
                           
            QPushButton#btnSavePreview { background-color: #2196F3; }
            QPushButton#btnSavePreview:hover { background-color : #1e88e5; }
            QPushButton#btnSavePreview:pressed { background-color : #1976d2; }
                           
            QPushButton#btnAddIrq { background-color: #4CAF50; }
            QPushButton#btnAddIrq:hover { background-color: #45a049; }
            QPushButton#btnAddIrq:pressed { background-color: #3a8a40; }
                           

            QToolButton#generateSvdBtn { min-height: 28px;
                padding: 1px 1px;
                color: white; }              
            QToolButton#generateSvdBtn { background-color: #4CAF50; }
            QToolButton#generateSvdBtn:hover { background-color: #45a049; }
            QToolButton#generateSvdBtn:pressed { background-color: #3a8a40; }
                                          
        """)

        # # 使用对象名为生成按钮提供更醒目的配色
        # try:
        #     # 让生成按钮尺寸合理，padding 更小
        #     self.findChild(QToolButton, 'generateSvdBtn').setStyleSheet('background-color: #4CAF50; color: white; padding: 4px 8px; border-radius:4px; font-size:11px;')
        # except Exception:
        #     pass

        #额外调整：确保工具栏按钮样式不会裁剪背景
        try:
            self.setStyleSheet(self.styleSheet() + "\nQToolBar { padding: 1px; }\n")
        except Exception:
            pass
    
    # ===================== 核心功能方法 =====================
    
    def new_file(self):
        """新建文件"""
        if self.check_unsaved_changes():
            self.device_info = DeviceInfo()
            self.command_history.clear()
            self.update_ui_from_device_info(sort_by_name=True)
            self.status_label.setText("已创建新文件")
    
    def open_svd_file(self):
        """打开SVD文件"""
        if self.check_unsaved_changes():
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择SVD文件", "", "SVD Files (*.svd);;XML Files (*.xml)"
            )
            
            if file_path:
                try:
                    self.status_label.setText("正在解析SVD文件...")
                    QApplication.processEvents()  # 更新UI
                    
                    parser = SVDParser()
                    self.device_info = parser.parse_file(file_path)
                    self.command_history.clear()


                    # 临时禁用拖放相关的自动更新
                    model = self.tree_widget.model()
                    if model is not None and hasattr(model, 'rowsMoved'):
                        try:
                            model.rowsMoved.disconnect()
                        except Exception:
                            pass

                    self.update_ui_from_device_info(sort_by_name=False)
                    self.status_label.setText(f"已加载: {os.path.basename(file_path)}")

                    # 重新连接信号
                    model = self.tree_widget.model()
                    if model is not None and hasattr(model, 'rowsMoved'):
                        try:
                            model.rowsMoved.connect(self.on_tree_rows_moved)
                        except Exception:
                            pass
                    
                    if parser.warnings:
                        warning_msg = "\n".join(parser.warnings[:10])  # 只显示前10条警告
                        if len(parser.warnings) > 10:
                            warning_msg += f"\n...还有{len(parser.warnings)-10}条警告"
                        self.show_message("警告", f"解析过程中发现以下警告:\n\n{warning_msg}", icon='warning')
                    
                except Exception as e:
                    self.logger.error(f"解析SVD文件失败: {str(e)}")
                    self.show_message("错误", f"解析SVD文件失败:\n{str(e)}", icon='error')
                    self.status_label.setText("打开文件失败")
    
    def save_svd_file(self):
        """保存SVD文件"""
        self.save_svd_file_impl()
    
    def save_svd_file_as(self):
        """另存为SVD文件"""
        self.save_svd_file_impl(force_save_as=True)
    
    def save_svd_file_impl(self, force_save_as=False):
        """保存SVD文件实现"""
        # 更新设备信息
        self.update_device_info_from_ui()
        
        # 检查必要信息
        if not self.device_info.name:
            self.show_message("警告", "请先设置IC型号", icon='warning')
            return
        
        # 生成SVD内容
        try:
            generator = SVDGenerator(self.device_info)
            svd_content = generator.generate()
            
            # 询问保存路径
            default_name = f"{self.device_info.name}.svd"
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存SVD文件", default_name, "SVD Files (*.svd)"
            )
            
            if file_path:
                # 确保文件扩展名
                if not file_path.endswith('.svd'):
                    file_path += '.svd'
                
                # 写入文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(svd_content)
                
                self.status_label.setText(f"已保存: {os.path.basename(file_path)}")
                self.show_message("提示", f"SVD文件已保存:\n{file_path}", icon='info')
        
        except Exception as e:
            self.logger.error(f"保存SVD文件失败: {str(e)}")
            self.show_message("错误", f"保存SVD文件失败:\n{str(e)}", icon='error')
    
    def check_unsaved_changes(self) -> bool:
        """检查未保存的更改"""
        # 这里可以添加检查是否有未保存的更改的逻辑
        # 目前总是返回True
        return True
    
    def update_device_info_from_ui(self):
        """从UI更新设备信息"""
        self.device_info.name = self.ic_name_edit.text().strip()
        self.device_info.version = self.device_version_edit.text().strip()
        self.device_info.description = self.device_info.name  # 使用IC型号作为描述
        
        # CPU信息
        self.device_info.cpu.name = self.core_edit.text().strip()
        self.device_info.cpu.revision = self.cpu_revision_edit.text().strip()
        self.device_info.cpu.endian = self.endian_combo.currentText()
        self.device_info.cpu.nvic_prio_bits = self.nvic_prio_spin.value()
        
        # SVD版本
        self.device_info.svd_version = self.svd_version_combo.currentText()
    
    def update_ui_from_device_info(self, sort_by_name: bool = True):
        """从设备信息更新UI"""
        self.ic_name_edit.setText(self.device_info.name)
        self.device_version_edit.setText(self.device_info.version)
        self.core_edit.setText(self.device_info.cpu.name)
        self.cpu_revision_edit.setText(self.device_info.cpu.revision)
        self.endian_combo.setCurrentText(self.device_info.cpu.endian)
        self.nvic_prio_spin.setValue(self.device_info.cpu.nvic_prio_bits)
        self.svd_version_combo.setCurrentText(self.device_info.svd_version)
        
        # 更新树控件
        self.tree_manager.update_tree(self.tree_widget, self.device_info, sort_by_name)
        
        # 更新中断列表
        self.update_irq_tree()
        
        # 更新中断外设下拉框
        self.update_irq_periph_combo()
        
        # 更新对话框工厂
        self.update_dialog_factory()
        
        # 清除选中项
        self.clear_selection()
    
    def update_dialog_factory(self):
        """更新对话框工厂"""
        peripherals = list(self.device_info.peripherals.keys())
        self.dialog_factory.set_existing_peripherals(peripherals)
    
    def update_irq_tree(self):
        """更新中断树"""
        self.irq_tree.clear()
        
        # 收集所有中断
        all_interrupts = []
        for periph_name, peripheral in self.device_info.peripherals.items():
            for interrupt in peripheral.interrupts:
                item = QTreeWidgetItem(self.irq_tree)
                item.setText(0, interrupt["name"])
                item.setText(1, str(interrupt["value"]))
                item.setText(2, interrupt["peripheral"])
                item.setText(3, interrupt.get("description", ""))
                
                # 存储中断数据
                item.setData(0, Qt.ItemDataRole.UserRole, interrupt)
    
    def update_irq_periph_combo(self):
        """更新中断外设下拉框"""
        self.irq_periph_combo.clear()
        for periph_name in self.device_info.peripherals.keys():
            self.irq_periph_combo.addItem(periph_name)
    
    def update_data_stats(self):
        """更新数据统计"""
        periph_count = len(self.device_info.peripherals)
        reg_count = sum(len(p.registers) for p in self.device_info.peripherals.values())
        field_count = sum(len(r.fields) for p in self.device_info.peripherals.values() for r in p.registers.values())
        
        stats_text = f"外设: {periph_count} | 寄存器: {reg_count} | 位域: {field_count}"
        self.data_stats_label.setText(stats_text)
    
    def apply_basic_config(self):
        """应用基础配置"""
        try:
            # 验证输入
            if not self.ic_name_edit.text().strip():
                raise ValidationError("IC型号不能为空")
            
            self.update_device_info_from_ui()
            self.status_label.setText("配置已应用")
            
        except ValidationError as e:
            self.show_message("警告", str(e), icon='warning')
    
    def reset_basic_config(self):
        """重置基础配置"""
        self.device_version_edit.setText("1.0")
        self.core_edit.setText("CM0+")
        self.cpu_revision_edit.setText("r0p1")
        self.nvic_prio_spin.setValue(4)
        self.endian_combo.setCurrentText("little")
        self.svd_version_combo.setCurrentText("1.3")
        self.status_label.setText("配置已重置")
    
    # ===================== 树控件相关方法 =====================
    
    def on_tree_selection_changed(self):
        """树选择变化事件"""
        selected_items = self.tree_widget.selectedItems()
        if not selected_items:
            self.clear_selection()
            return
        
        item = selected_items[0]
        item_type = self.tree_manager.get_item_type(item)
        item_name = self.tree_manager.get_item_name(item)
        
        # 更新当前选中项
        if item_type == "peripheral":
            self.current_peripheral = item_name
            self.current_register = None
            self.current_field = None

            # 更新按钮状态
            self.add_reg_btn_main.setEnabled(True)
            if hasattr(self, 'add_reg_btn_toolbar'):
                self.add_reg_btn_toolbar.setEnabled(True)
            self.add_field_btn_main.setEnabled(False)
            
            # 更新详细信息
            self.show_peripheral_details(item_name)
            
        elif item_type == "register":
            parent = item.parent()
            if parent:
                self.current_peripheral = self.tree_manager.get_item_name(parent)
                self.current_register = item_name
                self.current_field = None
                
                # 更新按钮状态
                self.add_reg_btn_main.setEnabled(False)
                if hasattr(self, 'add_reg_btn_toolbar'):
                    self.add_reg_btn_toolbar.setEnabled(False)
                self.add_field_btn_main.setEnabled(True)
                
                # 更新详细信息
                self.show_register_details(item_name)
        
        elif item_type == "field":
            parent = item.parent()
            if parent:
                grandparent = parent.parent()
                if grandparent:
                    self.current_peripheral = self.tree_manager.get_item_name(grandparent)
                    self.current_register = self.tree_manager.get_item_name(parent)
                    self.current_field = item_name
                    
                    # 更新按钮状态
                    self.add_reg_btn_main.setEnabled(False)
                    if hasattr(self, 'add_reg_btn_toolbar'):
                        self.add_reg_btn_toolbar.setEnabled(False)
                    self.add_field_btn_main.setEnabled(False)
                    
                    # 更新详细信息
                    self.show_field_details(item_name)
        
        # 发射选择变化信号
        self.selection_changed.emit(item_type, item_name)
    
    def clear_selection(self):
        """清除选中状态"""
        # 清除选中项前，先检查它们是否还存在
        try:
            if (self.current_peripheral and
                self.current_peripheral in self.device_info.peripherals):
                # 外设存在，检查寄存器
                peripheral = self.device_info.peripherals[self.current_peripheral]
                if (self.current_register and
                    self.current_register not in peripheral.registers):
                    self.current_register = None
                    self.current_field = None
            else:
                # 外设不存在，清除所有选择
                self.current_peripheral = None
                self.current_register = None
                self.current_field = None
        except Exception as e:
            print(f"清除选择时出错: {e}")
            self.current_peripheral = None
            self.current_register = None
            self.current_field = None
        
        self.add_reg_btn_main.setEnabled(False)
        if hasattr(self, 'add_reg_btn_toolbar'):
            self.add_reg_btn_toolbar.setEnabled(False)
        self.add_field_btn_main.setEnabled(False)
        
        self.detail_label.setText("选中项目以查看详细信息")
        # 清除可视化控件
        if hasattr(self, 'visualization_widget'):
            self.visualization_widget.show_peripheral(None)
        self.detail_table.clear()
    
    def show_peripheral_details(self, periph_name: str):
        """显示外设详细信息"""
        if periph_name not in self.device_info.peripherals:
            return
        
        peripheral = self.device_info.peripherals[periph_name]
        
        self.detail_label.setText(f"外设: {periph_name}")
        
        # 可视化控件显示外设地址映射
        if hasattr(self, 'visualization_widget'):
            self.visualization_widget.show_peripheral(peripheral)
        
        # 属性表格
        self.detail_table.clear()
        self.add_table_item("属性", "值")
        self.add_table_item("名称", periph_name)
        self.add_table_item("基地址", peripheral.base_address)
        self.add_table_item("描述", peripheral.description)
        if peripheral.display_name:
            self.add_table_item("显示名称", peripheral.display_name)
        self.add_table_item("组名", peripheral.group_name)
        if peripheral.derived_from:
            self.add_table_item("继承自", peripheral.derived_from)
        self.add_table_item("地址块偏移", peripheral.address_block['offset'])
        self.add_table_item("地址块大小", peripheral.address_block['size'])
        self.add_table_item("寄存器数量", str(len(peripheral.registers)))
        self.add_table_item("中断数量", str(len(peripheral.interrupts)))
    
    def show_register_details(self, reg_name: str):
        """显示寄存器详细信息"""
        if not self.current_peripheral or reg_name not in self.device_info.peripherals[self.current_peripheral].registers:
            return
        
        register = self.device_info.peripherals[self.current_peripheral].registers[reg_name]
        
        self.detail_label.setText(f"寄存器: {reg_name} (外设: {self.current_peripheral})")
        
        # 同时显示外设映射和寄存器位域图
        if hasattr(self, 'visualization_widget'):
            peripheral = self.device_info.peripherals[self.current_peripheral]
            self.visualization_widget.show_peripheral_and_register(peripheral, register)
        
        # 属性表格
        self.detail_table.clear()
        self.add_table_item("属性", "值")
        self.add_table_item("名称", reg_name)
        self.add_table_item("偏移地址", register.offset)
        self.add_table_item("描述", register.description)
        if register.display_name:
            self.add_table_item("显示名称", register.display_name)
        self.add_table_item("访问权限", register.access or "未设置")
        self.add_table_item("复位值", register.reset_value)
        self.add_table_item("大小", register.size)
        self.add_table_item("位域数量", str(len(register.fields)))
    
    def show_field_details(self, field_name: str):
        """显示位域详细信息"""
        if (not self.current_peripheral or
            not self.current_register or
            field_name not in self.device_info.peripherals[self.current_peripheral].registers[self.current_register].fields):
            return
        
        field = self.device_info.peripherals[self.current_peripheral].registers[self.current_register].fields[field_name]
        
        self.detail_label.setText(f"位域: {field_name}")
        
        # 可视化控件显示位域（暂无特殊可视化，清空）
        if hasattr(self, 'visualization_widget'):
            self.visualization_widget.show_field(field)
        
        # 属性表格
        self.detail_table.clear()
        self.add_table_item("属性", "值")
        self.add_table_item("名称", field_name)
        self.add_table_item("起始位", str(field.bit_offset))
        self.add_table_item("位宽", str(field.bit_width))
        self.add_table_item("描述", field.description)
        if field.display_name:
            self.add_table_item("显示名称", field.display_name)
        self.add_table_item("访问权限", field.access or "未设置")
        self.add_table_item("复位值", field.reset_value)
        self.add_table_item("位范围", f"[{field.bit_offset + field.bit_width - 1}:{field.bit_offset}]")
    
    def add_table_item(self, key: str, value: str):
        """向详情表格添加项目"""
        item = QTreeWidgetItem(self.detail_table)
        item.setText(0, key)
        item.setText(1, value)
    
    def on_tree_context_menu(self, pos):
        """树控件右键菜单"""
        item = self.tree_widget.itemAt(pos)
        if not item:
            return
        
        # 创建右键菜单
        menu = self.tree_manager.create_context_menu(item)
        
        # 执行菜单动作
        action = menu.exec(self.tree_widget.mapToGlobal(pos))
        if action:
            action_text = action.text()
            item_type = self.tree_manager.get_item_type(item)
            item_name = self.tree_manager.get_item_name(item)
            
            if action_text == "编辑外设":
                self.edit_peripheral(item_name)
            elif action_text == "删除外设":
                self.delete_peripheral(item_name)
            elif action_text == "添加寄存器":
                self.add_register()
            elif action_text == "编辑寄存器":
                self.edit_register(item_name)
            elif action_text == "删除寄存器":
                self.delete_register(item_name)
            elif action_text == "添加位域":
                self.add_field()
            elif action_text == "编辑位域":
                self.edit_field(item_name)
            elif action_text == "删除位域":
                self.delete_field(item_name)

    
    def on_tree_item_double_clicked(self, item, column):
        """树项目双击事件"""
        item_type = self.tree_manager.get_item_type(item)
        item_name = self.tree_manager.get_item_name(item)
        
        if item_type == "peripheral":
            self.edit_peripheral(item_name)
        elif item_type == "register":
            self.edit_register(item_name)
        elif item_type == "field":
            self.edit_field(item_name)


     # ===================== 外设/寄存器/位域操作方法 =====================
    
    def add_peripheral(self):
        """添加外设"""
        # 更新对话框工厂
        self.update_dialog_factory()
        
        # 创建对话框
        dialog = self.dialog_factory.create_peripheral_dialog()

        if dialog.exec():
            result = getattr(dialog, "result_data", None)
            if result is None:
                return
            
            # 创建外设对象
            peripheral = Peripheral(
                name=result["name"],
                base_address=result["base_address"],
                description=result["description"],
                display_name=result["display_name"],
                group_name=result["group_name"],
                derived_from=result["derived_from"],
                address_block=result["address_block"]
            )
            
            # 添加到设备信息
            self.device_info.peripherals[peripheral.name] = peripheral
            
            # 创建命令
            def execute():
                self.device_info.peripherals[peripheral.name] = peripheral
                self.update_ui_from_device_info(sort_by_name=False)
                self.tree_widget.setCurrentItem(
                    self.find_tree_item_by_name(peripheral.name, "peripheral")
                )
                self.status_label.setText(f"已添加外设: {peripheral.name}")
            
            def undo():
                del self.device_info.peripherals[peripheral.name]
                self.update_ui_from_device_info(sort_by_name=False)
                self.status_label.setText(f"已撤消添加外设: {peripheral.name}")
            
            command = Command(
                execute=execute,
                undo=undo,
                description=f"添加外设: {peripheral.name}"
            )
            
            # 执行命令
            self.command_history.execute(command)
            
            # 发射数据变化信号
            self.data_changed.emit()
    
    def edit_peripheral(self, periph_name: str):
        """编辑外设"""
        if periph_name not in self.device_info.peripherals:
            self.show_message("警告", f"外设 {periph_name} 不存在", icon='warning')
            return
        
        peripheral = self.device_info.peripherals[periph_name]
        
        # 更新对话框工厂
        self.update_dialog_factory()
        
        # 创建对话框
        dialog = self.dialog_factory.create_peripheral_dialog(peripheral, is_edit=True)

        if dialog.exec():
            result = getattr(dialog, "result_data", None)
            if result is None:
                return
            
            # 保存旧数据
            old_peripheral = peripheral
            old_name = periph_name
            new_name = result["name"]
            
            # 检查名称是否已更改
            name_changed = old_name != new_name
            
            # 创建更新后的外设对象
            updated_peripheral = Peripheral(
                name=new_name,
                base_address=result["base_address"],
                description=result["description"],
                display_name=result["display_name"],
                group_name=result["group_name"],
                derived_from=result["derived_from"],
                address_block=result["address_block"],
                registers=old_peripheral.registers.copy(),
                interrupts=old_peripheral.interrupts.copy()
            )
            
            # 创建命令
            def execute():
                # 用相同位置替换键，保留顺序
                from collections import OrderedDict
                items = list(self.device_info.peripherals.items())
                new_peripherals = OrderedDict()
                for name, per in items:
                    if name == old_name:
                        new_peripherals[new_name] = updated_peripheral
                    else:
                        new_peripherals[name] = per

                # 如果原字典中没有 old_name（极端情况），确保添加
                if old_name not in new_peripherals and new_name not in new_peripherals:
                    new_peripherals[new_name] = updated_peripheral

                self.device_info.peripherals = new_peripherals

                # 更新中断中的关联外设
                if name_changed:
                    for interrupt in updated_peripheral.interrupts:
                        interrupt["peripheral"] = new_name

                self.update_ui_from_device_info(sort_by_name=False)
                self.tree_widget.setCurrentItem(
                    self.find_tree_item_by_name(new_name, "peripheral")
                )
                self.status_label.setText(f"已更新外设: {new_name}")
            
            def undo():
                # 将 new_name 替换回 old_name，保留顺序
                from collections import OrderedDict
                items = list(self.device_info.peripherals.items())
                restored = OrderedDict()
                for name, per in items:
                    if name == new_name:
                        restored[old_name] = old_peripheral
                    else:
                        restored[name] = per

                # 如果 new_name 不在当前字典（极端情况），确保恢复旧项
                if new_name not in restored and old_name not in restored:
                    restored[old_name] = old_peripheral

                self.device_info.peripherals = restored

                # 恢复中断中的关联外设
                if name_changed:
                    for interrupt in old_peripheral.interrupts:
                        interrupt["peripheral"] = old_name

                self.update_ui_from_device_info(sort_by_name=False)
                self.tree_widget.setCurrentItem(
                    self.find_tree_item_by_name(old_name, "peripheral")
                )
                self.status_label.setText(f"已撤消编辑外设: {old_name}")
            
            command = Command(
                execute=execute,
                undo=undo,
                description=f"编辑外设: {old_name} -> {new_name}"
            )
            
            # 执行命令
            self.command_history.execute(command)
            
            # 发射数据变化信号
            self.data_changed.emit()
    
    def delete_peripheral(self, periph_name: str):
        """删除外设"""
        if periph_name not in self.device_info.peripherals:
            self.show_message("警告", f"外设 {periph_name} 不存在", icon='warning')
            return
        
        # 确认删除
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除外设 '{periph_name}' 吗？\n这将同时删除该外设下的所有寄存器和中断。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # 保存旧数据
        old_peripheral = self.device_info.peripherals[periph_name]
        
        # 创建命令
        def execute():
            del self.device_info.peripherals[periph_name]
            self.update_ui_from_device_info(sort_by_name=False)
            self.clear_selection()
            self.status_label.setText(f"已删除外设: {periph_name}")
        
        def undo():
            self.device_info.peripherals[periph_name] = old_peripheral
            self.update_ui_from_device_info(sort_by_name=False)
            self.tree_widget.setCurrentItem(
                self.find_tree_item_by_name(periph_name, "peripheral")
            )
            self.status_label.setText(f"已撤消删除外设: {periph_name}")
        
        command = Command(
            execute=execute,
            undo=undo,
            description=f"删除外设: {periph_name}"
        )
        
        # 执行命令
        self.command_history.execute(command)
        
        # 发射数据变化信号
        self.data_changed.emit()
    
    def add_register(self):
        """添加寄存器"""
        if not self.current_peripheral:
            self.show_message("警告", "请先选择一个外设", icon='warning')
            return
        
        # 获取当前外设的寄存器列表
        existing_registers = list(self.device_info.peripherals[self.current_peripheral].registers.keys())
        self.dialog_factory.set_existing_registers(existing_registers)
        
        # 创建对话框
        dialog = self.dialog_factory.create_register_dialog()

        if dialog.exec():
            result = getattr(dialog, "result_data", None)
            if result is None:
                return
            
            # 创建寄存器对象
            register = Register(
                name=result["name"],
                offset=result["offset"],
                description=result["description"],
                display_name=result["display_name"],
                access=result["access"],
                reset_value=result["reset_value"],
                size=result["size"]
            )
            
            # 添加到当前外设
            periph_name = self.current_peripheral
            
            # 创建命令
            def execute():
                self.device_info.peripherals[periph_name].registers[register.name] = register
                self.update_ui_from_device_info(sort_by_name=False)
                
                # 找到并选中新添加的寄存器
                periph_item = self.find_tree_item_by_name(periph_name, "peripheral")
                if periph_item:
                    periph_item.setExpanded(True)
                    reg_item = self.find_tree_item_by_name(register.name, "register", periph_item)
                    if reg_item:
                        self.tree_widget.setCurrentItem(reg_item)
                
                self.status_label.setText(f"已添加寄存器: {register.name}")
            
            def undo():
                del self.device_info.peripherals[periph_name].registers[register.name]
                self.update_ui_from_device_info(sort_by_name=False)
                self.tree_widget.setCurrentItem(
                    self.find_tree_item_by_name(periph_name, "peripheral")
                )
                self.status_label.setText(f"已撤消添加寄存器: {register.name}")
            
            command = Command(
                execute=execute,
                undo=undo,
                description=f"添加寄存器: {register.name}"
            )
            
            # 执行命令
            self.command_history.execute(command)
            
            # 发射数据变化信号
            self.data_changed.emit()
    
    def edit_register(self, reg_name: str):
        """编辑寄存器"""
        if not self.current_peripheral:
            self.show_message("警告", "请先选择一个外设", icon='warning')
            return
        
        if reg_name not in self.device_info.peripherals[self.current_peripheral].registers:
            self.show_message("警告", f"寄存器 {reg_name} 不存在", icon='warning')
            return
        
        periph_name = self.current_peripheral
        register = self.device_info.peripherals[periph_name].registers[reg_name]
        
        # 获取当前外设的寄存器列表（排除当前寄存器）
        existing_registers = [
            name for name in self.device_info.peripherals[periph_name].registers.keys()
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
            updated_register = Register(
                name=new_name,
                offset=result["offset"],
                description=result["description"],
                display_name=result["display_name"],
                access=result["access"],
                reset_value=result["reset_value"],
                size=result["size"],
                fields=old_register.fields.copy()
            )
            
            # 创建命令
            def execute():
                # 删除旧的寄存器
                del self.device_info.peripherals[periph_name].registers[old_name]
                
                # 添加新的寄存器
                self.device_info.peripherals[periph_name].registers[new_name] = updated_register
                
                self.update_ui_from_device_info(sort_by_name=False)
                
                # 找到并选中更新后的寄存器
                periph_item = self.find_tree_item_by_name(periph_name, "peripheral")
                if periph_item:
                    periph_item.setExpanded(True)
                    reg_item = self.find_tree_item_by_name(new_name, "register", periph_item)
                    if reg_item:
                        self.tree_widget.setCurrentItem(reg_item)
                
                self.status_label.setText(f"已更新寄存器: {new_name}")
            
            def undo():
                # 删除新的寄存器
                del self.device_info.peripherals[periph_name].registers[new_name]
                
                # 恢复旧的寄存器
                self.device_info.peripherals[periph_name].registers[old_name] = old_register
                
                self.update_ui_from_device_info(sort_by_name=False)
                
                # 找到并选中原来的寄存器
                periph_item = self.find_tree_item_by_name(periph_name, "peripheral")
                if periph_item:
                    periph_item.setExpanded(True)
                    reg_item = self.find_tree_item_by_name(old_name, "register", periph_item)
                    if reg_item:
                        self.tree_widget.setCurrentItem(reg_item)
                
                self.status_label.setText(f"已撤消编辑寄存器: {old_name}")
            
            command = Command(
                execute=execute,
                undo=undo,
                description=f"编辑寄存器: {old_name} -> {new_name}"
            )
            
            # 执行命令
            self.command_history.execute(command)
            
            # 发射数据变化信号
            self.data_changed.emit()
    
    def delete_register(self, reg_name: str):
        """删除寄存器"""
        if not self.current_peripheral:
            self.show_message("警告", "请先选择一个外设", icon='warning')
            return
        
        if reg_name not in self.device_info.peripherals[self.current_peripheral].registers:
            self.show_message("警告", f"寄存器 {reg_name} 不存在", icon='warning')
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
        
        periph_name = self.current_peripheral
        
        # 保存旧数据
        old_register = self.device_info.peripherals[periph_name].registers[reg_name]
        
        # 创建命令
        def execute():
            del self.device_info.peripherals[periph_name].registers[reg_name]
            self.update_ui_from_device_info(sort_by_name=False)
            self.tree_widget.setCurrentItem(
                self.find_tree_item_by_name(periph_name, "peripheral")
            )
            self.status_label.setText(f"已删除寄存器: {reg_name}")
        
        def undo():
            self.device_info.peripherals[periph_name].registers[reg_name] = old_register
            self.update_ui_from_device_info(sort_by_name=False)
            
            # 找到并选中恢复的寄存器
            periph_item = self.find_tree_item_by_name(periph_name, "peripheral")
            if periph_item:
                periph_item.setExpanded(True)
                reg_item = self.find_tree_item_by_name(reg_name, "register", periph_item)
                if reg_item:
                    self.tree_widget.setCurrentItem(reg_item)
            
            self.status_label.setText(f"已撤消删除寄存器: {reg_name}")
        
        command = Command(
            execute=execute,
            undo=undo,
            description=f"删除寄存器: {reg_name}"
        )
        
        # 执行命令
        self.command_history.execute(command)
        
        # 发射数据变化信号
        self.data_changed.emit()
    
    def add_field(self):
        """添加位域"""
        if not self.current_peripheral or not self.current_register:
            self.show_message("警告", "请先选择一个寄存器", icon='warning')
            return
        
        periph_name = self.current_peripheral
        reg_name = self.current_register
        
        # 获取当前寄存器的位域列表
        existing_fields = list(self.device_info.peripherals[periph_name].registers[reg_name].fields.keys())
        
        # 创建对话框
        dialog = self.dialog_factory.create_field_dialog()

        if dialog.exec():
            result = getattr(dialog, "result_data", None)
            if result is None:
                return
            
            # 创建位域对象
            field = Field(
                name=result["name"],
                bit_offset=result["offset"],
                bit_width=result["width"],
                description=result["description"],
                display_name=result["display_name"],
                access=result["access"],
                reset_value=result["reset_value"]
            )
            
            # 创建命令
            def execute():
                self.device_info.peripherals[periph_name].registers[reg_name].fields[field.name] = field
                self.update_ui_from_device_info(sort_by_name=False)
                
                # 找到并选中新添加的位域
                periph_item = self.find_tree_item_by_name(periph_name, "peripheral")
                if periph_item:
                    periph_item.setExpanded(True)
                    reg_item = self.find_tree_item_by_name(reg_name, "register", periph_item)
                    if reg_item:
                        reg_item.setExpanded(True)
                        field_item = self.find_tree_item_by_name(field.name, "field", reg_item)
                        if field_item:
                            self.tree_widget.setCurrentItem(field_item)
                
                self.status_label.setText(f"已添加位域: {field.name}")
            
            def undo():
                del self.device_info.peripherals[periph_name].registers[reg_name].fields[field.name]
                self.update_ui_from_device_info(sort_by_name=False)
                
                # 找到并选中寄存器
                periph_item = self.find_tree_item_by_name(periph_name, "peripheral")
                if periph_item:
                    periph_item.setExpanded(True)
                    reg_item = self.find_tree_item_by_name(reg_name, "register", periph_item)
                    if reg_item:
                        self.tree_widget.setCurrentItem(reg_item)
                
                self.status_label.setText(f"已撤消添加位域: {field.name}")
            
            command = Command(
                execute=execute,
                undo=undo,
                description=f"添加位域: {field.name}"
            )
            
            # 执行命令
            self.command_history.execute(command)
            
            # 发射数据变化信号
            self.data_changed.emit()
    
    def edit_field(self, field_name: str):
        """编辑位域"""
        if not self.current_peripheral or not self.current_register:
            self.show_message("警告", "请先选择一个寄存器", icon='warning')
            return
        
        periph_name = self.current_peripheral
        reg_name = self.current_register
        
        if field_name not in self.device_info.peripherals[periph_name].registers[reg_name].fields:
            self.show_message("警告", f"位域 {field_name} 不存在", icon='warning')
            return
        
        field = self.device_info.peripherals[periph_name].registers[reg_name].fields[field_name]
        
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
            updated_field = Field(
                name=new_name,
                bit_offset=result["offset"],
                bit_width=result["width"],
                description=result["description"],
                display_name=result["display_name"],
                access=result["access"],
                reset_value=result["reset_value"]
            )
            
            # 创建命令
            def execute():
                # 删除旧的位域
                del self.device_info.peripherals[periph_name].registers[reg_name].fields[old_name]
                
                # 添加新的位域
                self.device_info.peripherals[periph_name].registers[reg_name].fields[new_name] = updated_field
                
                self.update_ui_from_device_info(sort_by_name=False)
                
                # 找到并选中更新后的位域
                periph_item = self.find_tree_item_by_name(periph_name, "peripheral")
                if periph_item:
                    periph_item.setExpanded(True)
                    reg_item = self.find_tree_item_by_name(reg_name, "register", periph_item)
                    if reg_item:
                        reg_item.setExpanded(True)
                        field_item = self.find_tree_item_by_name(new_name, "field", reg_item)
                        if field_item:
                            self.tree_widget.setCurrentItem(field_item)
                
                self.status_label.setText(f"已更新位域: {new_name}")
            
            def undo():
                # 删除新的位域
                del self.device_info.peripherals[periph_name].registers[reg_name].fields[new_name]
                
                # 恢复旧的位域
                self.device_info.peripherals[periph_name].registers[reg_name].fields[old_name] = old_field
                
                self.update_ui_from_device_info(sort_by_name=False)
                
                # 找到并选中原来的位域
                periph_item = self.find_tree_item_by_name(periph_name, "peripheral")
                if periph_item:
                    periph_item.setExpanded(True)
                    reg_item = self.find_tree_item_by_name(reg_name, "register", periph_item)
                    if reg_item:
                        reg_item.setExpanded(True)
                        field_item = self.find_tree_item_by_name(old_name, "field", reg_item)
                        if field_item:
                            self.tree_widget.setCurrentItem(field_item)
                
                self.status_label.setText(f"已撤消编辑位域: {old_name}")
            
            command = Command(
                execute=execute,
                undo=undo,
                description=f"编辑位域: {old_name} -> {new_name}"
            )
            
            # 执行命令
            self.command_history.execute(command)
            
            # 发射数据变化信号
            self.data_changed.emit()
    
    def delete_field(self, field_name: str):
        """删除位域"""
        if not self.current_peripheral or not self.current_register:
            self.show_message("警告", "请先选择一个寄存器", icon='warning')
            return
        
        periph_name = self.current_peripheral
        reg_name = self.current_register
        
        if field_name not in self.device_info.peripherals[periph_name].registers[reg_name].fields:
            self.show_message("警告", f"位域 {field_name} 不存在", icon='warning')
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
        
        # 保存旧数据
        old_field = self.device_info.peripherals[periph_name].registers[reg_name].fields[field_name]
        
        # 创建命令
        def execute():
            del self.device_info.peripherals[periph_name].registers[reg_name].fields[field_name]
            self.update_ui_from_device_info(sort_by_name=False)
            
            # 找到并选中寄存器
            periph_item = self.find_tree_item_by_name(periph_name, "peripheral")
            if periph_item:
                periph_item.setExpanded(True)
                reg_item = self.find_tree_item_by_name(reg_name, "register", periph_item)
                if reg_item:
                    self.tree_widget.setCurrentItem(reg_item)
            
            self.status_label.setText(f"已删除位域: {field_name}")
        
        def undo():
            self.device_info.peripherals[periph_name].registers[reg_name].fields[field_name] = old_field
            self.update_ui_from_device_info(sort_by_name=False)
            
            # 找到并选中恢复的位域
            periph_item = self.find_tree_item_by_name(periph_name, "peripheral")
            if periph_item:
                periph_item.setExpanded(True)
                reg_item = self.find_tree_item_by_name(reg_name, "register", periph_item)
                if reg_item:
                    reg_item.setExpanded(True)
                    field_item = self.find_tree_item_by_name(field_name, "field", reg_item)
                    if field_item:
                        self.tree_widget.setCurrentItem(field_item)
            
            self.status_label.setText(f"已撤消删除位域: {field_name}")
        
        command = Command(
            execute=execute,
            undo=undo,
            description=f"删除位域: {field_name}"
        )
        
        # 执行命令
        self.command_history.execute(command)
        
        # 发射数据变化信号
        self.data_changed.emit()
    
    def delete_selected(self):
        """删除选中项"""
        selected_items = self.tree_widget.selectedItems()
        if not selected_items:
            return
        
        item = selected_items[0]
        item_type = self.tree_manager.get_item_type(item)
        item_name = self.tree_manager.get_item_name(item)
        
        if item_type == "peripheral":
            self.delete_peripheral(item_name)
        elif item_type == "register":
            self.delete_register(item_name)
        elif item_type == "field":
            self.delete_field(item_name)
    
    # ===================== 中断操作方法 =====================
    
    def add_interrupt(self):
        """添加中断"""
        # 获取输入
        irq_name = self.irq_name_edit.text().strip()
        irq_value = self.irq_value_spin.value()
        periph_name = self.irq_periph_combo.currentText()
        
        # 验证输入
        try:
            Validator.validate_name(irq_name, "中断名")
            Validator.validate_irq_number(irq_value)
            
            if not periph_name:
                raise ValidationError("必须选择关联外设")
            
            # 检查中断名是否已存在
            for periph in self.device_info.peripherals.values():
                for interrupt in periph.interrupts:
                    if interrupt["name"] == irq_name:
                        raise ValidationError(f"中断名 '{irq_name}' 已存在")
            
        except ValidationError as e:
            self.show_message("警告", str(e), icon='warning')
            return
        
        # 创建中断数据
        interrupt_data = {
            "name": irq_name,
            "value": irq_value,
            "description": "",
            "peripheral": periph_name
        }
        
        # 创建命令
        def execute():
            self.device_info.peripherals[periph_name].interrupts.append(interrupt_data)
            self.update_irq_tree()
            self.irq_name_edit.clear()
            self.irq_value_spin.setValue(0)
            self.status_label.setText(f"已添加中断: {irq_name}")
        
        def undo():
            # 从外设的中断列表中删除
            for i, irq in enumerate(self.device_info.peripherals[periph_name].interrupts):
                if irq["name"] == irq_name:
                    self.device_info.peripherals[periph_name].interrupts.pop(i)
                    break
            self.update_irq_tree()
            self.status_label.setText(f"已撤消添加中断: {irq_name}")
        
        command = Command(
            execute=execute,
            undo=undo,
            description=f"添加中断: {irq_name}"
        )
        
        # 执行命令
        self.command_history.execute(command)
        
        # 发射数据变化信号
        self.data_changed.emit()
    
    def on_irq_context_menu(self, pos):
        """中断树右键菜单"""
        item = self.irq_tree.itemAt(pos)
        if not item:
            return
        
        # 获取中断数据
        interrupt_data = item.data(0, Qt.ItemDataRole.UserRole)
        if not interrupt_data:
            return
        
        # 创建右键菜单
        menu = QMenu()
        
        edit_action = menu.addAction("编辑中断")
        delete_action = menu.addAction("删除中断")
        
        # 执行菜单动作
        action = menu.exec(self.irq_tree.mapToGlobal(pos))
        if action == edit_action:
            self.edit_interrupt(interrupt_data)
        elif action == delete_action:
            self.delete_interrupt(interrupt_data)
    
    def edit_interrupt(self, interrupt_data: dict):
        """编辑中断"""
        periph_list = list(self.device_info.peripherals.keys())
        dialog = self.dialog_factory.create_interrupt_dialog(
            Interrupt(**interrupt_data), periph_list, is_edit=True
        )

        if dialog.exec():
            result = getattr(dialog, "result_data", None)
            if result is None:
                return
            
            # 保存旧数据
            old_name = interrupt_data["name"]
            old_periph = interrupt_data["peripheral"]
            new_name = result["name"]
            new_periph = result["peripheral"]
            
            # 检查是否更改了外设
            periph_changed = old_periph != new_periph
            
            # 创建命令
            def execute():
                # 从旧外设中删除中断
                for i, irq in enumerate(self.device_info.peripherals[old_periph].interrupts):
                    if irq["name"] == old_name:
                        self.device_info.peripherals[old_periph].interrupts.pop(i)
                        break
                
                # 添加到新外设
                updated_interrupt = {
                    "name": new_name,
                    "value": result["value"],
                    "description": result["description"],
                    "peripheral": new_periph
                }
                self.device_info.peripherals[new_periph].interrupts.append(updated_interrupt)
                
                self.update_irq_tree()
                self.status_label.setText(f"已更新中断: {new_name}")
            
            def undo():
                # 从新外设中删除中断
                for i, irq in enumerate(self.device_info.peripherals[new_periph].interrupts):
                    if irq["name"] == new_name:
                        self.device_info.peripherals[new_periph].interrupts.pop(i)
                        break
                
                # 恢复到旧外设
                original_interrupt = {
                    "name": old_name,
                    "value": interrupt_data["value"],
                    "description": interrupt_data.get("description", ""),
                    "peripheral": old_periph
                }
                self.device_info.peripherals[old_periph].interrupts.append(original_interrupt)
                
                self.update_irq_tree()
                self.status_label.setText(f"已撤消编辑中断: {old_name}")
            
            command = Command(
                execute=execute,
                undo=undo,
                description=f"编辑中断: {old_name}"
            )
            
            # 执行命令
            self.command_history.execute(command)
            
            # 发射数据变化信号
            self.data_changed.emit()
    
    def delete_interrupt(self, interrupt_data: dict):
        """删除中断"""
        irq_name = interrupt_data["name"]
        periph_name = interrupt_data["peripheral"]
        
        # 确认删除
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除中断 '{irq_name}' 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # 创建命令
        def execute():
            # 查找并删除中断
            for i, irq in enumerate(self.device_info.peripherals[periph_name].interrupts):
                if irq["name"] == irq_name:
                    self.device_info.peripherals[periph_name].interrupts.pop(i)
                    break
            
            self.update_irq_tree()
            self.status_label.setText(f"已删除中断: {irq_name}")
        
        def undo():
            # 恢复中断
            self.device_info.peripherals[periph_name].interrupts.append(interrupt_data)
            self.update_irq_tree()
            self.status_label.setText(f"已撤消删除中断: {irq_name}")
        
        command = Command(
            execute=execute,
            undo=undo,
            description=f"删除中断: {irq_name}"
        )
        
        # 执行命令
        self.command_history.execute(command)
        
        # 发射数据变化信号
        self.data_changed.emit()
    
    # ===================== 搜索功能 =====================
    
    def on_search_text_changed(self, text):
        """搜索文本变化事件"""
        search_text = text.strip().lower()
        
        if not search_text:
            # 清除高亮
            self.tree_manager.clear_highlights()
            self.search_results.clear()
            self.current_search_index = -1
            self.search_count_label.setText("")
            self.search_prev_btn.setEnabled(False)
            self.search_next_btn.setEnabled(False)
            return
        
        # 执行搜索（同时在外设树和中断列表中搜索）
        self.search_results = []
        # 搜索外设/寄存器/位域树
        self.search_tree_items(self.tree_widget.invisibleRootItem(), search_text)
        # 搜索中断列表
        self.search_irq_items(search_text)
        
        # 更新搜索状态
        count = len(self.search_results)
        if count > 0:
            self.current_search_index = 0
            self.highlight_current_search()
            self.search_count_label.setText(f"{self.current_search_index + 1}/{count}")
            self.search_prev_btn.setEnabled(count > 1)
            self.search_next_btn.setEnabled(count > 1)
        else:
            self.current_search_index = -1
            self.search_count_label.setText("无结果")
            self.search_prev_btn.setEnabled(False)
            self.search_next_btn.setEnabled(False)
    
    def search_tree_items(self, parent_item, search_text):
        """递归搜索树项目"""
        for i in range(parent_item.childCount()):
            item = parent_item.child(i)
            if item is None:
                continue

            # 检查项目名称是否匹配
            item_name = item.text(0).lower()
            if search_text in item_name:
                # 标记为在外设树中找到
                self.search_results.append({"tree": "periph", "item": item})

            # 递归搜索子项目
            if item.childCount() > 0:
                self.search_tree_items(item, search_text)

    def search_irq_items(self, search_text):
        """在中断列表中搜索"""
        if not hasattr(self, 'irq_tree') or self.irq_tree is None:
            return

        for i in range(self.irq_tree.topLevelItemCount()):
            item = self.irq_tree.topLevelItem(i)
            if item is None:
                continue

            # 在所有列中搜索
            match_found = False
            for col in range(self.irq_tree.columnCount()):
                text = (item.text(col) or "").lower()
                if search_text in text:
                    match_found = True
                    break

            if match_found:
                self.search_results.append({"tree": "irq", "item": item})
    
    def goto_prev_search(self):
        """跳转到上一个搜索结果"""
        if not self.search_results or len(self.search_results) <= 1:
            return
        
        self.current_search_index = (self.current_search_index - 1) % len(self.search_results)
        self.highlight_current_search()
        self.search_count_label.setText(f"{self.current_search_index + 1}/{len(self.search_results)}")
    
    def goto_next_search(self):
        """跳转到下一个搜索结果"""
        if not self.search_results or len(self.search_results) <= 1:
            return
        
        self.current_search_index = (self.current_search_index + 1) % len(self.search_results)
        self.highlight_current_search()
        self.search_count_label.setText(f"{self.current_search_index + 1}/{len(self.search_results)}")
    
    def highlight_current_search(self):
        """高亮当前搜索结果"""
        if not self.search_results or self.current_search_index < 0:
            return
        # 清除之前的高亮（清理两处）
        self.tree_manager.clear_highlights()
        # 也清除 irq_tree 上次的高亮（背景还原）
        try:
            for i in range(self.irq_tree.topLevelItemCount()):
                it = self.irq_tree.topLevelItem(i)
                if it is not None:
                    it.setBackground(0, QBrush(QColor(255, 255, 255)))
                    it.setBackground(1, QBrush(QColor(255, 255, 255)))
                    if self.irq_tree.columnCount() > 2:
                        it.setBackground(2, QBrush(QColor(255, 255, 255)))
        except Exception:
            pass

        # 高亮当前结果
        entry = self.search_results[self.current_search_index]
        tree_type = entry.get("tree")
        item = entry.get("item")

        if tree_type == "periph":
            # 切换到外设标签页
            try:
                self.tab_widget.setCurrentIndex(1)
            except Exception:
                pass

            # 高亮并展开父节点
            self.tree_manager.highlight_item(item)
            parent = item.parent()
            while parent:
                parent.setExpanded(True)
                parent = parent.parent()

            # 滚动到并选中该项目
            self.tree_widget.scrollToItem(item)
            self.tree_widget.setCurrentItem(item)

        elif tree_type == "irq":
            # 切换到中断标签页
            try:
                self.tab_widget.setCurrentIndex(2)
            except Exception:
                pass

            # 高亮该中断行
            try:
                item.setBackground(0, QBrush(QColor(255, 255, 153)))
                item.setBackground(1, QBrush(QColor(255, 255, 153)))
            except Exception:
                pass

            # 滚动并选中中断项
            try:
                self.irq_tree.scrollToItem(item)
                self.irq_tree.setCurrentItem(item)
            except Exception:
                pass
    
    # ===================== 辅助方法 =====================

    def select_item_after_drop(self, item_name):
        """拖放后重新选中项目"""
        item = self.find_tree_item_by_name(item_name, "peripheral")
        if item:
            self.tree_widget.setCurrentItem(item)
            self.tree_widget.scrollToItem(item)
    
    def find_tree_item_by_name(self, name: str, item_type: Optional[str], 
                              parent_item: Optional[QTreeWidgetItem] = None) -> Optional[QTreeWidgetItem]:
        """根据名称和类型查找树项目"""
        # 如果调用方未指定 item_type，直接返回
        if item_type is None:
            return None

        if parent_item is None:
            parent_item = self.tree_widget.invisibleRootItem()

        # 告诉类型检查器 parent_item 一定不是 None
        parent_item = cast(QTreeWidgetItem, parent_item)

        for i in range(parent_item.childCount()):
            item = parent_item.child(i)
            if item is None:
                continue

            # 检查项目类型和名称
            if (self.tree_manager.get_item_type(item) == item_type and 
                self.tree_manager.get_item_name(item) == name):
                return item

            # 递归搜索子项目
            if item.childCount() > 0:
                found = self.find_tree_item_by_name(name, item_type, item)
                if found:
                    return found
        
        return None
    
    def expand_all_tree(self):
        """展开所有树节点"""
        self.tree_widget.expandAll()
    
    def collapse_all_tree(self):
        """折叠所有树节点"""
        self.tree_widget.collapseAll()
    
    # ===================== 生成和预览功能 =====================
    
    def generate_svd(self):
        """生成SVD"""
        # 更新设备信息
        self.update_device_info_from_ui()
        
        # 检查必要信息
        if not self.device_info.name:
            self.show_message("警告", "请先设置IC型号", icon='warning')
            return
        
        if not self.device_info.peripherals:
            self.show_message("警告", "请至少添加一个外设", icon='warning')
            return
        
        try:
            self.status_label.setText("正在生成SVD...")
            QApplication.processEvents()
            
            # 生成SVD
            generator = SVDGenerator(self.device_info)
            svd_content = generator.generate()
            
            # 美化XML
            pretty_content = pretty_xml(svd_content)
            
            # 显示预览
            self.preview_edit.setText(pretty_content)
            
            # 切换到预览标签页
            self.tab_widget.setCurrentIndex(3)
            
            self.status_label.setText("SVD生成完成")
            
            # 询问是否保存
            reply = QMessageBox.question(
                self, "生成成功",
                "SVD生成成功！是否要保存到文件？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.save_svd_file()
            
        except Exception as e:
            self.logger.error(f"生成SVD失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"生成SVD失败:\n{str(e)}")
            self.status_label.setText("生成失败")
    
    # generate_preview removed — use toolbar '生成SVD' which calls `generate_svd()`
    
    def copy_preview_to_clipboard(self):
        """复制预览内容到剪贴板"""
        text = self.preview_edit.toPlainText()
        if not text:
            QMessageBox.warning(self, "警告", "没有内容可以复制")
            return
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
            QMessageBox.information(self, "成功", "已复制到剪贴板")
        else:
            QMessageBox.warning(self, "错误", "无法访问系统剪贴板")

    def clear_preview(self):
        """清除预览文本框内容"""
        self.preview_edit.clear()
        self.status_label.setText("预览已清除")
    
    # ===================== 其他功能 =====================

    def enable_tree_drag_drop(self):
        """启用树控件的拖放功能"""
        self.tree_widget.setDragEnabled(True)
        self.tree_widget.setAcceptDrops(True)
        self.tree_widget.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        self.tree_widget.setDropIndicatorShown(True)
        
        # 设置拖放事件处理
        self.tree_widget.dropEvent = self.custom_drop_event
        
    def custom_drop_event(self, event):
        """自定义拖放事件处理 - 只允许外设之间的同级拖放"""
        # 在拖放前保存源项目信息
        source_item = self.tree_widget.currentItem()
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
        QTreeWidget.dropEvent(self.tree_widget, event)

    # ===================== 日志面板相关 =====================
    class _LogSignalEmitter(QObject):
        append_text = pyqtSignal(str)

    def create_log_panel(self):
        """创建可切换的日志面板并绑定日志处理器"""
        # 日志停靠窗口
        self.log_dock = QDockWidget("日志", self)
        self.log_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.TopDockWidgetArea)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        # 使用容器放置操作按钮和文本区
        container = QWidget()
        container_layout = QVBoxLayout(container)
        button_row = QHBoxLayout()
        clear_btn = QPushButton("清空日志")
        clear_btn.clicked.connect(self.clear_log)
        button_row.addWidget(clear_btn)
        save_btn = QPushButton("保存日志")
        save_btn.clicked.connect(self.save_log_to_file)
        button_row.addWidget(save_btn)
        button_row.addStretch()
        container_layout.addLayout(button_row)
        container_layout.addWidget(self.log_text)
        self.log_dock.setWidget(container)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)
        self.log_dock.hide()

        # 日志信号和处理器
        self._log_emitter = MainWindow._LogSignalEmitter()

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
                            try:
                                existing = ''
                                try:
                                    existing = self.owner.log_text.toPlainText()
                                except Exception:
                                    existing = ''
                                with open(path, 'w', encoding='utf-8') as f:
                                    if existing:
                                        f.write(existing + "\n\n--- NEW ERROR ---\n")
                                    f.write(msg + "\n")
                            except Exception:
                                pass
                    except Exception:
                        pass

                except Exception:
                    pass

        # 绑定信号到文本追加
        def _append_log(text: str):
            self.log_text.append(text)

        self._log_emitter.append_text.connect(_append_log)

        # 创建并添加处理器到根 logger，确保所有模块日志都能被捕获
        handler = GuiLogHandler(self._log_emitter, owner=self)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
        handler.setFormatter(formatter)
        # attach to our Logger instance's underlying logger
        try:
            root_logger = logging.getLogger()
            root_logger.addHandler(handler)
        except Exception:
            pass

        # 保存引用以便后续移除
        self._gui_log_handler = handler

    def clear_log(self):
        """清空日志面板内容"""
        try:
            self.log_text.clear()
            # 记录清空操作
            try:
                self.logger.info("日志已清空")
            except Exception:
                pass
        except Exception:
            pass

    def save_log_to_file(self):
        """手动保存当前日志到文件（弹出保存对话框）"""
        try:
            suggested = os.path.join(os.getcwd(), 'logs', datetime.now().strftime('svd_log_%Y%m%d_%H%M%S.log'))
            path, _ = QFileDialog.getSaveFileName(self, "保存日志", suggested, "Log Files (*.log);;Text Files (*.txt);;All Files (*)")
            if path:
                try:
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(self.log_text.toPlainText())
                    QMessageBox.information(self, "保存成功", f"日志已保存到: {path}")
                except Exception as e:
                    QMessageBox.warning(self, "保存失败", f"保存日志失败: {e}")
        except Exception:
            pass

    def show_message(self, title: str, text: str, icon: str = 'info'):
        """统一消息弹窗接口：icon in ['info','warning','error']"""
        try:
            if icon == 'info':
                QMessageBox.information(self, title, text)
            elif icon == 'warning':
                QMessageBox.warning(self, title, text)
            else:
                QMessageBox.critical(self, title, text)
        except Exception:
            # 回退：直接打印
            print(f"{title}: {text}")

    def toggle_log_panel(self, checked: bool):
        """切换日志面板显示/隐藏"""
        # 如果尚未创建日志面板，先创建（防止在菜单创建后、面板创建前被触发）
        if not hasattr(self, 'log_dock') or self.log_dock is None:
            try:
                self.create_log_panel()
            except Exception:
                pass

        if checked:
            try:
                self.log_dock.show()
            except Exception:
                pass
        else:
            try:
                self.log_dock.hide()
            except Exception:
                pass
        
        
    def _validate_and_fix_tree_structure_after_drop(self, moved_periph_name):
        """拖放后验证并修正树结构"""
        try:
            # 检查树结构是否有效
            valid = True
            for i in range(self.tree_widget.topLevelItemCount()):
                item = self.tree_widget.topLevelItem(i)
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
                self.update_ui_from_device_info(sort_by_name=False)
                QMessageBox.warning(self, "拖放错误", "拖放操作导致无效的树结构，已恢复")
            else:
                # 更新数据模型
                self.update_data_model_from_tree()
                self.status_label.setText(f"已调整外设顺序: {moved_periph_name}")
                
                # 延迟重新选中项目
                QTimer.singleShot(50, lambda: self.select_item_after_drop(moved_periph_name))
        
        except Exception as e:
            print(f"拖放后验证出错: {e}")
            # 出错时恢复
            self.update_ui_from_device_info(sort_by_name=False)

    # def validate_drop(self, source_item, target_item, drop_pos):
    #     """验证拖放是否有效"""
    #     source_type = self.tree_manager.get_item_type(source_item)
    #     target_type = self.tree_manager.get_item_type(target_item)
        
    #     # 不允许跨层级拖放
    #     if source_type != target_type:
    #         return False
        
    #     # 检查放置位置
    #     if drop_pos == QAbstractItemView.DropIndicatorPosition.OnItem:
    #         # 拖放到项目上（作为子项） - 只允许外设包含寄存器，寄存器包含位域
    #         if source_type == "peripheral" and target_type == "peripheral":
    #             return False  # 外设不能成为其他外设的子项
    #         elif source_type == "register" and target_type == "peripheral":
    #             return True   # 寄存器可以拖放到外设下
    #         elif source_type == "field" and target_type == "register":
    #             return True   # 位域可以拖放到寄存器下
    #         else:
    #             return False
    #     else:
    #         # 拖放到项目之间（同级） - 允许
    #         return source_type == target_type
           

    def _update_all_item_flags(self):
        """更新所有树项目的拖放标志"""
        # 遍历所有树项目并设置合适的标志
        def update_item_flags(item):
            item_type = self.tree_manager.get_item_type(item)
            
            if item_type == "field":
                # 位域只能拖动，不能接受放置
                flags = (item.flags() | 
                        Qt.ItemFlag.ItemIsDragEnabled)
                item.setFlags(flags)
            else:
                # 外设和寄存器可以拖动和接受同级放置
                flags = (item.flags() | 
                        Qt.ItemFlag.ItemIsDragEnabled | 
                        Qt.ItemFlag.ItemIsDropEnabled)
                item.setFlags(flags)
            
            # 递归处理子项
            for i in range(item.childCount()):
                child = item.child(i)
                if child is None:
                    continue
                update_item_flags(child)
        
        # 从顶层项目开始
        for i in range(self.tree_widget.topLevelItemCount()):
            update_item_flags(self.tree_widget.topLevelItem(i))

    def _get_type_name(self, type_str):
        """获取类型名称"""
        type_names = {
            "peripheral": "外设",
            "register": "寄存器", 
            "field": "位域"
        }
        return type_names.get(type_str, "未知类型")

    def _validate_and_fix_tree_structure(self):
        """验证并修复树结构"""
        try:
            # 遍历树结构，确保层级正确
            for i in range(self.tree_widget.topLevelItemCount()):
                periph_item = self.tree_widget.topLevelItem(i)
                if periph_item is None:
                    continue
                periph_name = self.tree_manager.get_item_name(periph_item)
                
                # 检查外设是否在数据模型中
                if periph_name not in self.device_info.peripherals:
                    print(f"警告: 树中的外设 '{periph_name}' 不在数据模型中")
                    continue
                
                # 检查寄存器
                for j in range(periph_item.childCount()):
                    reg_item = periph_item.child(j)
                    if reg_item is None:
                        continue
                    reg_name = self.tree_manager.get_item_name(reg_item)
                    reg_type = self.tree_manager.get_item_type(reg_item)
                    
                    # 确保这是寄存器类型
                    if reg_type != "register":
                        print(f"错误: 在外设 '{periph_name}' 中发现非寄存器项目")
                        continue
                    
                    # 检查寄存器是否在数据模型中
                    peripheral = self.device_info.peripherals[periph_name]
                    if reg_name not in peripheral.registers:
                        print(f"警告: 寄存器 '{reg_name}' 不在外设 '{periph_name}' 中")
                        continue
                    
                    # 检查位域
                    for k in range(reg_item.childCount()):
                        field_item = reg_item.child(k)
                        if field_item is None:
                            continue
                        field_name = self.tree_manager.get_item_name(field_item)
                        field_type = self.tree_manager.get_item_type(field_item)
                        
                        # 确保这是位域类型
                        if field_type != "field":
                            print(f"错误: 在寄存器 '{reg_name}' 中发现非位域项目")
                            continue
                        
                        # 检查位域是否在数据模型中
                        register = peripheral.registers[reg_name]
                        if field_name not in register.fields:
                            print(f"警告: 位域 '{field_name}' 不在寄存器 '{reg_name}' 中")
                            continue
            
            # 更新数据模型
            self.update_data_model_from_tree()
        
        except Exception as e:
            print(f"验证树结构时出错: {e}")
            import traceback
            traceback.print_exc()

    def on_tree_rows_moved(self, parent, start, end, destination, row):
        """树行移动事件"""
        # 获取移动的项目
        if parent.isValid():
            # 子项目移动（寄存器或位域）
            parent_item = self.tree_widget.itemFromIndex(parent)
            moved_item = parent_item.child(start) if parent_item is not None else None
        else:
            # 顶级项目移动（外设）
            moved_item = self.tree_widget.topLevelItem(start)
        
        if not moved_item:
            return
        
        item_type = self.tree_manager.get_item_type(moved_item)
        item_name = self.tree_manager.get_item_name(moved_item)
        
        print(f"项目移动: {item_type} - {item_name}")
        
        # 更新数据模型
        self.update_data_model_from_tree()

    def update_data_model_from_tree(self):
        """从树控件更新数据模型"""
        print("更新数据模型以反映树结构调整...")
        
        try:
            # 临时保存原始数据，以防恢复需要
            original_peripherals = self.device_info.peripherals.copy()
            
            # 创建新的外设字典，按照树中的顺序
            new_peripherals = {}
            
            for i in range(self.tree_widget.topLevelItemCount()):
                periph_item = self.tree_widget.topLevelItem(i)
                if periph_item is None:
                    continue
                periph_name = self.tree_manager.get_item_name(periph_item)
                periph_type = self.tree_manager.get_item_type(periph_item)
                
                # 验证项目类型
                if periph_type != "peripheral":
                    print(f"错误: 发现非外设项目在顶级: {periph_name}")
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
                            print(f"错误: 在外设 {periph_name} 中发现非寄存器项目: {reg_name}")
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
                                    print(f"错误: 在寄存器 {reg_name} 中发现非位域项目: {field_name}")
                                    continue
                                    
                                if field_name in register.fields:
                                    new_fields[field_name] = register.fields[field_name]
                                else:
                                    print(f"警告: 位域 {field_name} 不在寄存器 {reg_name} 中")
                            
                            register.fields = new_fields
                            new_registers[reg_name] = register
                        else:
                            print(f"警告: 寄存器 {reg_name} 不在外设 {periph_name} 中")
                    
                    peripheral.registers = new_registers
                    new_peripherals[periph_name] = peripheral
                else:
                    print(f"警告: 外设 {periph_name} 不在数据模型中")
            
            self.device_info.peripherals = new_peripherals
            
            # 清除当前选择，避免引用已删除的项目
            self.clear_selection()
            
            # 更新UI
            self.update_ui_from_device_info(sort_by_name=False)
            self.data_changed.emit()
            self.status_label.setText("已调整项目顺序")

        except Exception as e:
            print(f"更新数据模型时出错: {e}")
            import traceback
            traceback.print_exc()
            
            # 出错时恢复原始数据
            QMessageBox.warning(self, "错误", "更新数据模型时出错，已恢复原始数据")
            self.device_info.peripherals = original_peripherals
            self.update_ui_from_device_info(sort_by_name=False)

    # ===================== 上移/下移功能 =====================
    def _move_peripheral_up(self, periph_name):
        """上移外设"""
        # 获取所有外设名称列表
        periph_names = list(self.device_info.peripherals.keys())
        
        # 找到当前外设的位置
        if periph_name not in periph_names:
            return False
        
        index = periph_names.index(periph_name)
        if index <= 0:  # 已经在最上面
            return False
        
        # 在列表中交换位置
        periph_names[index], periph_names[index-1] = periph_names[index-1], periph_names[index]
        
        # 创建新的有序字典
        from collections import OrderedDict
        new_peripherals = OrderedDict()
        for name in periph_names:
            new_peripherals[name] = self.device_info.peripherals[name]
        
        # 更新数据模型
        self.device_info.peripherals = new_peripherals
        
        # 更新UI - 重要：不按名称排序，保持移动后的顺序！
        self.update_ui_from_device_info(sort_by_name=False)
        
        # 重新选中该项目
        item = self.find_tree_item_by_name(periph_name, "peripheral")
        if item:
            self.tree_widget.setCurrentItem(item)
        
        self.status_label.setText(f"已上移外设: {periph_name}")
        return True

    def _move_peripheral_down(self, periph_name):
        """下移外设"""
        # 获取所有外设名称列表
        periph_names = list(self.device_info.peripherals.keys())
        
        # 找到当前外设的位置
        if periph_name not in periph_names:
            return False
        
        index = periph_names.index(periph_name)
        if index >= len(periph_names) - 1:  # 已经在最下面
            return False
        
        # 在列表中交换位置
        periph_names[index], periph_names[index+1] = periph_names[index+1], periph_names[index]
        
        # 创建新的有序字典
        from collections import OrderedDict
        new_peripherals = OrderedDict()
        for name in periph_names:
            new_peripherals[name] = self.device_info.peripherals[name]
        
        # 更新数据模型
        self.device_info.peripherals = new_peripherals
        
        # 更新UI - 重要：不按名称排序，保持移动后的顺序！
        self.update_ui_from_device_info(sort_by_name=False)
        
        # 重新选中该项目
        item = self.find_tree_item_by_name(periph_name, "peripheral")
        if item:
            self.tree_widget.setCurrentItem(item)
        
        self.status_label.setText(f"已下移外设: {periph_name}")
        return True

    def move_item_up(self):
        """上移选中项目（只支持外设）"""
        selected_items = self.tree_widget.selectedItems()
        if not selected_items:
            return
        
        item = selected_items[0]
        item_type = self.tree_manager.get_item_type(item)
        
        # 只支持外设的上移
        if item_type != "peripheral":
            QMessageBox.warning(self, "操作限制", "只支持外设的上移操作")
            return
        
        item_name = self.tree_manager.get_item_name(item)
        
        # 保存当前状态用于撤销
        old_state = self._get_device_state_snapshot()
        
        # 上移外设
        moved = self._move_peripheral_up(item_name)
        
        if not moved:
            return
        
        # 获取移动后的状态
        new_state = self._get_device_state_snapshot()
        
        # 创建可撤销的命令
        def execute():
            self._restore_device_state(new_state)
        
        def undo():
            self._restore_device_state(old_state)
        
        command = Command(
            execute=execute,
            undo=undo,
            description=f"上移外设: {item_name}"
        )
        
        # 执行命令
        self.command_history.execute(command)
        
        # 发射数据变化信号
        self.data_changed.emit()

    def move_item_down(self):
        """下移选中项目（只支持外设）"""
        selected_items = self.tree_widget.selectedItems()
        if not selected_items:
            return
        
        item = selected_items[0]
        item_type = self.tree_manager.get_item_type(item)
        
        # 只支持外设的下移
        if item_type != "peripheral":
            QMessageBox.warning(self, "操作限制", "只支持外设的下移操作")
            return
        
        item_name = self.tree_manager.get_item_name(item)
        
        # 保存当前状态用于撤销
        old_state = self._get_device_state_snapshot()
        
        # 下移外设
        moved = self._move_peripheral_down(item_name)
        
        if not moved:
            return
        
        # 获取移动后的状态
        new_state = self._get_device_state_snapshot()
        
        # 创建可撤销的命令
        def execute():
            self._restore_device_state(new_state)
        
        def undo():
            self._restore_device_state(old_state)
        
        command = Command(
            execute=execute,
            undo=undo,
            description=f"下移外设: {item_name}"
        )
        
        # 执行命令
        self.command_history.execute(command)
        
        # 发射数据变化信号
        self.data_changed.emit()

    def sort_items_alphabetically(self):
        """按字母顺序排序"""
        # 保存当前选中项
        selected_items = self.tree_widget.selectedItems()
        selected_name = None
        selected_type = None
        if selected_items:
            selected_name = self.tree_manager.get_item_name(selected_items[0])
            selected_type = self.tree_manager.get_item_type(selected_items[0])
        
        # 保存当前展开状态
        expanded_items = self.get_expanded_items()
        
        # 排序外设
        self.tree_widget.sortItems(0, Qt.SortOrder.AscendingOrder)
        
        
        # 更新数据模型
        self.update_data_model_from_tree()
        
        # 恢复展开状态
        self.restore_expanded_items(expanded_items)
        
        # 恢复选中项
        if selected_name:
            item = self.find_tree_item_by_name(selected_name, selected_type)
            if item:
                self.tree_widget.setCurrentItem(item)
        
        self.status_label.setText("已按字母顺序排序")

    def get_expanded_items(self):
        """获取当前展开的项目路径"""
        expanded = []
        
        def traverse(item, path):
            if item is None:
                return
            if item.isExpanded():
                expanded.append(path.copy())

            for i in range(item.childCount()):
                child = item.child(i)
                if child is None:
                    continue
                child_path = path + [self.tree_manager.get_item_name(child)]
                traverse(child, child_path)
        
        # 遍历顶级项目
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            if item is None:
                continue
            path = [self.tree_manager.get_item_name(item)]
            traverse(item, path)
        
        return expanded

    def restore_expanded_items(self, expanded_paths):
        """恢复展开状态"""
        for path in expanded_paths:
            item = None
            for name in path:
                if item is None:
                    # 查找顶级外设
                    item = self.find_tree_item_by_name(name, "peripheral")
                else:
                    # 在子项中查找
                    found = False
                    for i in range(item.childCount()):
                        child = item.child(i)
                        if child is None:
                            continue
                        if self.tree_manager.get_item_name(child) == name:
                            item = child
                            found = True
                            break
                    if not found:
                        break
                
                if item:
                    item.setExpanded(True)

    def sort_items_by_address(self):
        """按地址/偏移排序"""
        # 保存当前选中项
        selected_items = self.tree_widget.selectedItems()
        selected_name = None
        selected_type = None
        
        if selected_items:
            selected_name = self.tree_manager.get_item_name(selected_items[0])
            selected_type = self.tree_manager.get_item_type(selected_items[0])
        
        # # 判断要排序什么：外设按基地址，寄存器按偏移地址
        # if selected_type == "peripheral" or not selected_items:
            # 外设按基地址排序
        self._sort_peripherals_by_address()
        # elif selected_type == "register":
        #     # 寄存器按偏移地址排序
        #     self._sort_registers_by_address(selected_name)
        # elif selected_type == "field":
        #     # 位域按起始位排序
        #     self._sort_fields_by_bit_offset(selected_name)
        
        # 恢复选中项
        if selected_name:
            item = self.find_tree_item_by_name(selected_name, selected_type)
            if item:
                self.tree_widget.setCurrentItem(item)
        
        self.status_label.setText("已按地址排序")

    def _sort_peripherals_by_address(self):
        """按基地址排序外设"""
        # 收集外设和基地址
        peripherals_with_address = []
        
        for periph_name, peripheral in self.device_info.peripherals.items():
            try:
                # 解析基地址
                addr_str = peripheral.base_address.strip().lower()
                if addr_str.startswith('0x'):
                    base_addr = int(addr_str, 16)
                else:
                    base_addr = int(addr_str)
                peripherals_with_address.append((base_addr, periph_name, peripheral))
            except (ValueError, AttributeError):
                peripherals_with_address.append((0, periph_name, peripheral))
        
        # 按基地址排序
        peripherals_with_address.sort(key=lambda x: x[0])
        
        # 清空树控件
        self.tree_widget.clear()
        
        # 按排序顺序重新构建树
        for _, periph_name, peripheral in peripherals_with_address:
            periph_item = self.tree_manager.create_peripheral_item(peripheral)
            self.tree_widget.addTopLevelItem(periph_item)
            
            # 添加寄存器（保持寄存器原来的顺序或按偏移排序）
            for reg_name, register in peripheral.registers.items():
                reg_item = self.tree_manager.create_register_item(register)
                periph_item.addChild(reg_item)
                
                # 添加位域
                for field_name, field in register.fields.items():
                    field_item = self.tree_manager.create_field_item(field)
                    reg_item.addChild(field_item)

    def _sort_registers_by_address(self, peripheral_name):
        """按偏移地址排序指定外设的寄存器"""
        if peripheral_name not in self.device_info.peripherals:
            return
        
        peripheral = self.device_info.peripherals[peripheral_name]
        
        # 收集寄存器和偏移地址
        registers_with_offset = []
        
        for reg_name, register in peripheral.registers.items():
            try:
                # 解析偏移地址
                offset_str = register.offset.strip().lower()
                if offset_str.startswith('0x'):
                    offset = int(offset_str, 16)
                else:
                    offset = int(offset_str)
                registers_with_offset.append((offset, reg_name, register))
            except (ValueError, AttributeError):
                registers_with_offset.append((0, reg_name, register))
        
        # 按偏移地址排序
        registers_with_offset.sort(key=lambda x: x[0])
        
        # 清空原来的寄存器顺序
        peripheral.registers.clear()
        
        # 按排序顺序重新添加到外设
        for _, reg_name, register in registers_with_offset:
            peripheral.registers[reg_name] = register
        
        # 更新UI
        self.update_ui_from_device_info(sort_by_name=False)

    def _sort_fields_by_bit_offset(self, register_name):
        """按起始位排序指定寄存器的位域"""
        # 找到包含该寄存器的外设
        for periph_name, peripheral in self.device_info.peripherals.items():
            if register_name in peripheral.registers:
                register = peripheral.registers[register_name]
                
                # 收集位域和起始位
                fields_with_offset = []
                
                for field_name, field in register.fields.items():
                    fields_with_offset.append((field.bit_offset, field_name, field))
                
                # 按起始位排序
                fields_with_offset.sort(key=lambda x: x[0])
                
                # 清空原来的位域顺序
                register.fields.clear()
                
                # 按排序顺序重新添加到寄存器
                for _, field_name, field in fields_with_offset:
                    register.fields[field_name] = field
                
                # 更新UI
                self.update_ui_from_device_info(sort_by_name=False)
                break
    
    def undo(self):
        """撤消操作"""
        if self.command_history.undo():
            self.status_label.setText("已撤消上一个操作")
            self.data_changed.emit()
    
    def redo(self):
        """重做操作"""
        if self.command_history.redo():
            self.status_label.setText("已重做上一个操作")
            self.data_changed.emit()
    
    def validate_data(self):
        """验证数据"""
        try:
            # 验证基础信息
            if not self.device_info.name:
                raise ValidationError("IC型号不能为空")
            
            # 验证所有外设
            for periph_name, peripheral in self.device_info.peripherals.items():
                # 验证外设
                Validator.validate_peripheral({
                    "name": peripheral.name,
                    "base_address": peripheral.base_address,
                    "description": peripheral.description,
                    "group_name": peripheral.group_name,
                    "address_block": peripheral.address_block
                })
                
                # 验证寄存器
                for reg_name, register in peripheral.registers.items():
                    Validator.validate_register({
                        "name": register.name,
                        "offset": register.offset,
                        "description": register.description,
                        "reset_value": register.reset_value
                    })
                    
                    # 验证位域
                    for field_name, field in register.fields.items():
                        Validator.validate_field({
                            "name": field.name,
                            "offset": field.bit_offset,
                            "width": field.bit_width,
                            "description": field.description,
                            "reset_value": field.reset_value
                        })
            
            QMessageBox.information(self, "验证通过", "所有数据验证通过！")
            self.status_label.setText("数据验证通过")
            
        except ValidationError as e:
            QMessageBox.warning(self, "验证失败", f"数据验证失败:\n{str(e)}")
            self.status_label.setText("数据验证失败")
    
    def show_about(self):
        """显示关于对话框"""
        about_text = """
        <h2>SVD工具 - 专业版</h2>
        <p>版本: 2.0</p>
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
        </ul>
        <p>© 2024 SVD工具开发团队</p>
        """
        # 创建日志面板（默认隐藏）
        self.create_log_panel()
        
        QMessageBox.about(self, "关于SVD工具", about_text)
    

    
    def closeEvent(self, event):
        """关闭事件"""
        if self.check_unsaved_changes():
            event.accept()
        else:
            event.ignore()