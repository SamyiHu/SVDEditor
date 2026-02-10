"""
UI布局管理组件
负责创建主窗口的UI布局，包括标签页、搜索栏、状态栏等
"""
import logging
from typing import Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel,
    QLineEdit, QPushButton, QStatusBar
)

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

        # 将main_window引用传递给widget_manager，以便ui_updater可以访问
        self.widget_manager.main_window = main_window

    def create_layout(self) -> Dict[str, Any]:
        """创建主布局"""
        self.logger.debug("create_layout开始")

        # 设置窗口标题和大小
        self.main_window.setWindowTitle("SVD工具 - 专业版")
        self.main_window.setGeometry(100, 100, 1600, 900)

        # 创建中央部件
        central_widget = QWidget()
        self.main_window.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        self.logger.debug("中央部件和布局创建完成")

        # 创建菜单栏（如果主窗口有相应方法）
        try:
            menu_builder = MenuBarBuilder(self.main_window, self.main_window)
            menu_builder.create()
            self.logger.debug("菜单栏创建完成")
        except Exception as e:
            self.logger.debug(f"菜单栏创建失败（可忽略）: {e}")

        # 创建工具栏（如果主窗口有相应方法）
        try:
            toolbar_builder = ToolBarBuilder(self.main_window, self.main_window)
            toolbar_builder.create()
            self.logger.debug("工具栏创建完成")
        except Exception as e:
            self.logger.debug(f"工具栏创建失败（可忽略）: {e}")

        # 创建状态栏
        self._create_status_bar()
        self.logger.debug("状态栏创建完成")

        # 搜索栏
        self._create_search_bar(main_layout)
        self.logger.debug("搜索栏创建完成")

        # 创建标签页
        tab_widget = QTabWidget(central_widget)
        main_layout.addWidget(tab_widget)
        self.widget_manager.register_widget('tab_widget', tab_widget)
        self.logger.debug("标签页控件创建并添加到布局")

        return self.widget_manager.get_all_widgets()

    def _create_status_bar(self):
        """创建状态栏"""
        status_bar = QStatusBar()
        self.main_window.setStatusBar(status_bar)

        # 状态标签
        status_label = QLabel("就绪")
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

        search_label = QLabel(t("search.label"))
        search_layout.addWidget(search_label)
        
        search_edit = QLineEdit()
        search_edit.setPlaceholderText(t("search.placeholder"))
        search_layout.addWidget(search_edit)

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
        self.widget_manager.register_widget('search_prev_btn', search_prev_btn)
        self.widget_manager.register_widget('search_next_btn', search_next_btn)
        self.widget_manager.register_widget('search_count_label', search_count_label)

        return search_layout

    def create_basic_info_tab(self, tab_widget):
        """创建基础信息标签页"""
        tab, widgets = self.tab_builder.create_basic_info_tab(tab_widget)
        self.widget_manager.register_widgets(widgets)
        return tab

    def create_peripheral_tab(self, tab_widget):
        """创建外设标签页"""
        tab, widgets = self.tab_builder.create_peripheral_tab(tab_widget)
        self.widget_manager.register_widgets(widgets)
        return tab

    def create_interrupt_tab(self, tab_widget):
        """创建中断标签页"""
        tab, widgets = self.tab_builder.create_interrupt_tab(tab_widget)
        self.widget_manager.register_widgets(widgets)
        return tab

    def create_preview_tab(self, tab_widget):
        """创建预览标签页"""
        tab, widgets = self.tab_builder.create_preview_tab(tab_widget)
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
        self.ui_updater.update_basic_info(device_info)

    def update_field_table(self, peripheral_name=None, register_name=None, register=None):
        """更新位域表格

        Args:
            peripheral_name: 外设名称
            register_name: 寄存器名称
            register: 寄存器对象（如果提供，则忽略peripheral_name和register_name）
        """
        self.ui_updater.update_field_table(peripheral_name, register_name, register)
