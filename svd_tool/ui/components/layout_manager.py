"""
UI布局管理组件
负责创建主窗口的UI布局，包括标签页、搜索栏、状态栏等
"""
import os
import logging
from typing import Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel,
    QLineEdit, QPushButton, QStatusBar, QSplitter, QApplication,
    QStackedWidget, QSizePolicy
)
from PyQt6.QtCore import Qt

from .menu_bar import MenuBarBuilder
from .toolbar import ToolBarBuilder
from .tab_builder import TabBuilder
from .widget_manager import WidgetManager
from .ui_updater import UIUpdater
from ...i18n.i18n import t


class LayoutManager:
    """布局管理器 - 负责协调UI布局的创建和管理"""

    def __init__(self, main_window):
        """
        初始化布局管理器

        Args:
            main_window: 主窗口实例
        """
        self.main_window = main_window
        self.logger = logging.getLogger("LayoutManager")

        # 初始化子组件
        self.widget_manager = WidgetManager()
        self.tab_builder = TabBuilder(main_window)
        self.ui_updater = UIUpdater(self.widget_manager)

        # 如果WidgetManager需要访问main_window，可通过方法参数传递或在UIUpdater中处理

    def create_layout(self) -> Dict[str, Any]:
        """创建主布局（使用QStackedWidget支持欢迎页/编辑器切换）"""
        self.logger.debug("create_layout开始")

        # 设置窗口标题
        self.main_window.setWindowTitle(t("app.title"))
        
        # 自适应窗口大小（基于屏幕分辨率）
        self._restore_window_geometry()

        # 创建中央部件
        central_widget = QWidget()
        self.main_window.setCentralWidget(central_widget)
        central_layout = QVBoxLayout(central_widget)
        central_layout.setSpacing(0)
        central_layout.setContentsMargins(0, 0, 0, 0)

        # ===== 创建堆叠页面 =====
        self._stacked_widget = QStackedWidget()
        central_layout.addWidget(self._stacked_widget)
        
        # --- 页面0：欢迎页 ---
        from ..widgets.welcome_page import WelcomePage
        self._welcome_page = WelcomePage()
        self._stacked_widget.addWidget(self._welcome_page)
        self.widget_manager.register_widget('welcome_page', self._welcome_page)
        
        # --- 页面1：编辑器 ---
        editor_page = QWidget()
        self._editor_layout = QVBoxLayout(editor_page)
        self._editor_layout.setSpacing(0)
        self._editor_layout.setContentsMargins(0, 0, 0, 0)
        self._stacked_widget.addWidget(editor_page)
        self.widget_manager.register_widget('editor_page', editor_page)
        
        # --- 文档标签栏（在编辑器页面顶部，搜索栏上方） ---
        self._document_tab_bar = None  # 延迟创建，需要DocumentManager

        # 创建菜单栏
        try:
            menu_builder = MenuBarBuilder(self.main_window, self.main_window)
            menu_builder.create()
            self.logger.debug("菜单栏创建完成")
        except Exception as e:
            self.logger.debug(f"菜单栏创建失败（可忽略）: {e}")

        # 创建工具栏
        try:
            toolbar_builder = ToolBarBuilder(self.main_window, self.main_window)
            toolbar_builder.create()
            self.logger.debug("工具栏创建完成")
        except Exception as e:
            self.logger.debug(f"工具栏创建失败（可忽略）: {e}")

        # 创建状态栏
        self._create_status_bar()

        # 搜索栏（在编辑器页面内）
        self._create_search_bar(self._editor_layout)

        # 创建编辑器堆叠（用于在编辑器和diff视图之间切换）
        editor_stack = QStackedWidget()
        self._editor_layout.addWidget(editor_stack)
        self._editor_layout.setStretchFactor(editor_stack, 1)
        self.widget_manager.register_widget('editor_stack', editor_stack)
        
        # --- 编辑器页面（页面0：正常编辑器） ---
        editor_content = QWidget()
        editor_content_layout = QVBoxLayout(editor_content)
        editor_content_layout.setSpacing(0)
        editor_content_layout.setContentsMargins(0, 0, 0, 0)
        editor_stack.addWidget(editor_content)
        
        # 创建主分割器
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setChildrenCollapsible(True)
        main_splitter.setHandleWidth(5)
        editor_content_layout.addWidget(main_splitter)
        editor_content_layout.setStretchFactor(main_splitter, 1)
        self.widget_manager.register_widget('main_splitter', main_splitter)

        # 创建标签页
        tab_widget = QTabWidget(editor_content)
        tab_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        main_splitter.addWidget(tab_widget)
        self.widget_manager.register_widget('tab_widget', tab_widget)

        # 默认显示欢迎页
        self._stacked_widget.setCurrentIndex(0)
        self._editor_visible = False
        
        # 加载最近文件列表
        self._load_recent_files()

        return self.widget_manager.get_all_widgets()

    def _create_status_bar(self):
        """创建状态栏"""
        status_bar = QStatusBar()
        self.main_window.setStatusBar(status_bar)

        # 状态标签
        status_label = QLabel(t("status.ready"))
        status_bar.addWidget(status_label)

        # 数据统计标签
        data_stats_label = QLabel("")
        status_bar.addPermanentWidget(data_stats_label)

        # 注册控件
        self.widget_manager.register_widget('status_bar', status_bar)
        self.widget_manager.register_widget('status_label', status_label)
        self.widget_manager.register_widget('data_stats_label', data_stats_label)

        return status_bar

    def _create_search_bar(self, parent_layout):
        """创建搜索栏"""
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(5, 3, 5, 3)  # 设置搜索栏边距
        
        search_label = QLabel(t("search.label"))
        search_layout.addWidget(search_label)
        
        search_edit = QLineEdit()
        search_edit.setPlaceholderText(t("search.placeholder"))
        search_layout.addWidget(search_edit)
        
        # 搜索类型选择下拉框
        from PyQt6.QtWidgets import QComboBox
        search_type_combo = QComboBox()
        search_type_combo.addItem(t("search_type.all"), "all")
        search_type_combo.addItem(t("search_type.peripheral"), "peripheral")
        search_type_combo.addItem(t("search_type.register"), "register")
        search_type_combo.addItem(t("search_type.field"), "field")
        search_type_combo.addItem(t("search_type.interrupt"), "interrupt")
        search_type_combo.setObjectName("searchTypeCombo")
        search_layout.addWidget(search_type_combo)
        
        search_prev_btn = QPushButton(t("search.prev"))
        search_prev_btn.setEnabled(False)
        search_layout.addWidget(search_prev_btn)
        
        search_next_btn = QPushButton(t("search.next"))
        search_next_btn.setEnabled(False)
        search_layout.addWidget(search_next_btn)
        
        search_count_label = QLabel("")
        search_layout.addWidget(search_count_label)
        
        search_layout.addStretch()
        parent_layout.addLayout(search_layout)
        
        # 注册控件
        self.widget_manager.register_widget('search_label', search_label)
        self.widget_manager.register_widget('search_edit', search_edit)
        self.widget_manager.register_widget('search_type_combo', search_type_combo)
        self.widget_manager.register_widget('search_prev_btn', search_prev_btn)
        self.widget_manager.register_widget('search_next_btn', search_next_btn)
        self.widget_manager.register_widget('search_count_label', search_count_label)
        
        return search_layout

    def create_basic_info_tab(self, tab_widget):
        """创建基础信息标签页"""
        tab, widgets = self.tab_builder.create_basic_info_tab(tab_widget)
        # 注册控件到widget_manager
        self.widget_manager.register_widgets(widgets)
        # 连接数据汇总筛选信号
        filter_combo = widgets.get('data_summary_filter')
        if filter_combo:
            from PyQt6.QtWidgets import QComboBox
            filter_combo.currentIndexChanged.connect(
                lambda: self.ui_updater.update_data_stats_by_filter()
            )
        return tab

    def create_peripheral_tab(self, tab_widget):
        """创建外设标签页"""
        tab, widgets = self.tab_builder.create_peripheral_tab(tab_widget)
        # 注册控件到widget_manager
        self.widget_manager.register_widgets(widgets)
        return tab

    def create_interrupt_tab(self, tab_widget):
        """创建中断标签页"""
        tab, widgets = self.tab_builder.create_interrupt_tab(tab_widget)
        # 注册控件到widget_manager
        self.widget_manager.register_widgets(widgets)
        return tab

    def create_preview_tab(self, tab_widget):
        """创建预览标签页"""
        tab, widgets = self.tab_builder.create_preview_tab(tab_widget)
        # 注册控件到widget_manager
        self.widget_manager.register_widgets(widgets)
        return tab

    def get_widget(self, name: str):
        """获取控件"""
        return self.widget_manager.get_widget(name)

    def update_data_stats(self, stats: Dict[str, int]):
        """更新数据统计"""
        self.ui_updater.update_data_stats(stats)

    def update_status(self, message: str):
        """更新状态栏消息"""
        self.ui_updater.update_status(message)

    def update_basic_info(self, device_info):
        """更新基础信息标签页的UI内容

        Args:
            device_info: DeviceInfo对象，包含设备信息
        """
        # 设置防重入标志，防止程序填充控件时触发预览刷新
        if hasattr(self.main_window, '_basic_info_updating'):
            self.main_window._basic_info_updating = True
        try:
            self.ui_updater.update_basic_info(device_info)
        finally:
            if hasattr(self.main_window, '_basic_info_updating'):
                self.main_window._basic_info_updating = False

    def update_field_table(self, peripheral_name=None, register_name=None, register=None):
        """更新位域表格

        Args:
            peripheral_name: 外设名称
            register_name: 寄存器名称
            register: 寄存器对象（如果提供，则忽略peripheral_name和register_name）
        """
        self.ui_updater.update_field_table(peripheral_name, register_name, register)

    def _restore_window_geometry(self):
        """恢复窗口几何信息（自适应屏幕 + 用户偏好记忆）"""
        from PyQt6.QtCore import QSettings
        settings = QSettings("SVDEditor", "MainWindow")
        
        # 尝试恢复上次的窗口几何信息
        geometry = settings.value("geometry")
        if geometry is not None:
            self.main_window.restoreGeometry(geometry)
        else:
            # 首次启动：根据屏幕分辨率自适应
            screen = QApplication.primaryScreen()
            if screen:
                available = screen.availableGeometry()
                # 占屏幕80%大小，居中显示
                w = int(available.width() * 0.8)
                h = int(available.height() * 0.8)
                x = available.x() + (available.width() - w) // 2
                y = available.y() + (available.height() - h) // 2
                self.main_window.setGeometry(x, y, w, h)
            else:
                # 回退默认值
                self.main_window.setGeometry(100, 100, 1280, 720)
    
    def save_window_geometry(self):
        """保存窗口几何信息到配置"""
        from PyQt6.QtCore import QSettings
        settings = QSettings("SVDEditor", "MainWindow")
        
        # 保存窗口位置和大小
        settings.setValue("geometry", self.main_window.saveGeometry())
        
        # 保存分割器比例
        main_splitter = self.widget_manager.get_widget('main_splitter')
        if main_splitter:
            settings.setValue("main_splitter_sizes", main_splitter.sizes())
        
        # 保存可视化分割器比例
        vis_widget = self.widget_manager.get_widget('visualization_widget')
        if vis_widget and hasattr(vis_widget, 'vis_splitter'):
            settings.setValue("vis_splitter_sizes", vis_widget.vis_splitter.sizes())
    
    def toggle_left_panel(self):
        """切换左侧面板（标签页）的显示/隐藏"""
        main_splitter = self.widget_manager.get_widget('main_splitter')
        tab_widget = self.widget_manager.get_widget('tab_widget')
        if not main_splitter or not tab_widget:
            return
        
        if tab_widget.isVisible():
            # 记住当前大小，然后隐藏
            self._left_panel_sizes = main_splitter.sizes()
            tab_widget.hide()
            self.update_status(t("status.left_panel_hidden", default="左侧面板已隐藏（F9恢复）"))
        else:
            tab_widget.show()
            # 恢复之前的大小
            if hasattr(self, '_left_panel_sizes') and self._left_panel_sizes:
                main_splitter.setSizes(self._left_panel_sizes)
            self.update_status(t("status.left_panel_shown", default="左侧面板已显示"))
    
    # ===================== 欢迎页/编辑器切换 =====================
    
    def show_editor(self):
        """切换到编辑器视图"""
        if hasattr(self, '_stacked_widget'):
            self._stacked_widget.setCurrentIndex(1)
            self._editor_visible = True
    
    def show_welcome(self):
        """切换到欢迎页"""
        if hasattr(self, '_stacked_widget'):
            self._stacked_widget.setCurrentIndex(0)
            self._editor_visible = False
    
    def is_editor_visible(self) -> bool:
        """编辑器是否可见"""
        return getattr(self, '_editor_visible', False)
    
    def _load_recent_files(self):
        """从配置加载最近文件列表"""
        from PyQt6.QtCore import QSettings
        settings = QSettings("SVDEditor", "MainWindow")
        recent = settings.value("recent_files", [])
        if isinstance(recent, list):
            # 过滤不存在的文件
            valid = [f for f in recent if os.path.exists(f)] if recent else []
            self._welcome_page.set_recent_files(valid)
    
    def add_recent_file(self, file_path: str):
        """添加最近打开的文件"""
        from PyQt6.QtCore import QSettings
        settings = QSettings("SVDEditor", "MainWindow")
        recent = settings.value("recent_files", [])
        if not isinstance(recent, list):
            recent = []
        # 去重并放到最前面
        if file_path in recent:
            recent.remove(file_path)
        recent.insert(0, file_path)
        recent = recent[:10]  # 最多保存10个
        settings.setValue("recent_files", recent)
        self._welcome_page.set_recent_files(recent)
    
    # ===================== 文档标签栏 =====================
    
    def setup_document_tab_bar(self, document_manager):
        """设置文档标签栏（由主窗口调用）"""
        from ..widgets.document_tab_bar import DocumentTabBar
        
        self._document_tab_bar = DocumentTabBar(document_manager, self.main_window)
        # 插入到编辑器布局的最顶部（搜索栏之前）
        if hasattr(self, '_editor_layout'):
            self._editor_layout.insertWidget(0, self._document_tab_bar)
        self.widget_manager.register_widget('document_tab_bar', self._document_tab_bar)
        return self._document_tab_bar
    
    def get_document_tab_bar(self):
        """获取文档标签栏"""
        return self._document_tab_bar
    
    def restore_vis_splitter(self):
        """恢复可视化分割器比例"""
        from PyQt6.QtCore import QSettings
        settings = QSettings("SVDEditor", "MainWindow")
        vis_widget = self.widget_manager.get_widget('visualization_widget')
        if vis_widget and hasattr(vis_widget, 'vis_splitter'):
            vis_sizes = settings.value("vis_splitter_sizes")
            if vis_sizes is not None:
                try:
                    vis_widget.vis_splitter.setSizes([int(s) for s in vis_sizes])
                except Exception:
                    vis_widget.vis_splitter.setSizes([250, 250])
