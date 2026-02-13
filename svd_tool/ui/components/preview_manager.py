"""
预览管理器
支持灵活的预览显示模式：嵌入标签页、展开、主界面下方、可拖动
"""
import logging
from typing import Optional, Dict, Any
from enum import Enum

from PyQt6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTabWidget, QSplitter, QFrame,
    QLabel, QComboBox, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QIcon

from .realtime_preview import RealtimePreviewWidget
from ...i18n.i18n import t


class PreviewMode(Enum):
    """预览模式枚举"""
    TAB = "tab"  # 嵌入标签页
    BOTTOM = "bottom"  # 主界面下方
    DOCK = "dock"  # 可拖动停靠窗口
    EXPANDED = "expanded"  # 展开（全屏或最大化）


class PreviewManager(QObject):
    """预览管理器 - 管理预览功能的多种显示模式"""

    # 信号定义
    mode_changed = pyqtSignal(str)  # 预览模式改变
    preview_visibility_changed = pyqtSignal(bool)  # 预览可见性改变

    def __init__(self, main_window, state_manager, coordinator=None):
        """
        初始化预览管理器

        Args:
            main_window: 主窗口实例
            state_manager: 状态管理器
            coordinator: 协调器
        """
        super().__init__()
        self.main_window = main_window
        self.state_manager = state_manager
        self.coordinator = coordinator
        self.logger = logging.getLogger("PreviewManager")

        # 预览组件（只创建一个实例）
        self.preview_widget: Optional[RealtimePreviewWidget] = None
        self.preview_dock: Optional[QDockWidget] = None
        self.preview_tab: Optional[QWidget] = None
        self.preview_bottom_widget: Optional[QWidget] = None

        # 当前模式
        self.current_mode = PreviewMode.TAB

        # 控件引用
        self.tab_widget: Optional[QTabWidget] = None
        self.main_splitter: Optional[QSplitter] = None

        # 模式切换控件
        self.mode_combo: Optional[QComboBox] = None
        self.visibility_checkbox: Optional[QCheckBox] = None

        # 预览组件的父容器（用于在不同模式间移动）
        self.preview_container: Optional[QWidget] = None

        self.logger.info("预览管理器初始化完成")

    def create_preview_widget(self) -> RealtimePreviewWidget:
        """创建预览组件"""
        if self.preview_widget is None:
            self.preview_widget = RealtimePreviewWidget(
                state_manager=self.state_manager,
                coordinator=self.coordinator
            )
            self.logger.info("预览组件创建完成")
        return self.preview_widget

    def setup_preview_modes(self, tab_widget: QTabWidget, main_splitter: QSplitter = None):
        """
        设置预览的多种显示模式

        Args:
            tab_widget: 主标签页控件
            main_splitter: 主分割器（用于底部模式）
        """
        self.tab_widget = tab_widget
        self.main_splitter = main_splitter

        # 创建预览组件
        self.create_preview_widget()

        # 创建预览容器（用于在不同模式间移动预览组件）
        self.preview_container = QWidget()
        container_layout = QVBoxLayout(self.preview_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(self.preview_widget)

        # 创建模式切换工具栏
        self._create_mode_toolbar()

        # 创建标签页模式
        self._create_tab_mode()

        # 创建底部模式
        self._create_bottom_mode()

        # 创建停靠窗口模式
        self._create_dock_mode()

        # 默认使用标签页模式
        self.set_mode(PreviewMode.TAB)

        self.logger.info("预览模式设置完成")

    def _create_tab_mode(self):
        """创建标签页模式"""
        self.preview_tab = QWidget()
        layout = QVBoxLayout(self.preview_tab)
        layout.setContentsMargins(0, 0, 0, 0)

        # 添加预览容器（包含预览组件和工具栏）
        layout.addWidget(self.preview_container)

        # 添加到标签页
        if self.tab_widget:
            self.tab_widget.addTab(self.preview_tab, t("tab.preview_tab"))

        self.logger.debug("标签页模式创建完成")

    def _create_bottom_mode(self):
        """创建底部模式"""
        self.preview_bottom_widget = QWidget()
        layout = QVBoxLayout(self.preview_bottom_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # 添加预览容器（包含预览组件和工具栏）
        layout.addWidget(self.preview_container)

        # 如果有主分割器，添加到底部
        if self.main_splitter:
            # 创建新的垂直分割器
            self.preview_splitter = QSplitter(Qt.Orientation.Vertical)
            self.preview_splitter.setChildrenCollapsible(False)

            # 获取主分割器的所有子部件
            children = []
            for i in range(self.main_splitter.count()):
                children.append(self.main_splitter.widget(i))

            # 将主分割器的子部件移到新分割器
            for child in children:
                self.main_splitter.removeWidget(child)
                self.preview_splitter.addWidget(child)

            # 添加预览到底部
            self.preview_splitter.addWidget(self.preview_bottom_widget)

            # 设置分割比例（主内容占70%，预览占30%）
            self.preview_splitter.setSizes([700, 300])

            # 将新分割器添加到主分割器
            self.main_splitter.addWidget(self.preview_splitter)

        self.logger.debug("底部模式创建完成")

    def _create_dock_mode(self):
        """创建停靠窗口模式"""
        self.preview_dock = QDockWidget(t("tab.preview_tab"), self.main_window)
        self.preview_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea |
            Qt.DockWidgetArea.RightDockWidgetArea |
            Qt.DockWidgetArea.BottomDockWidgetArea
        )
        self.preview_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetFloatable |
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable
        )

        # 创建停靠窗口内容
        dock_content = QWidget()
        dock_layout = QVBoxLayout(dock_content)
        dock_layout.setContentsMargins(0, 0, 0, 0)
        dock_layout.addWidget(self.preview_container)

        self.preview_dock.setWidget(dock_content)

        # 默认隐藏
        self.preview_dock.hide()

        self.logger.debug("停靠窗口模式创建完成")

    def _create_mode_toolbar(self):
        """创建模式切换工具栏"""
        toolbar = QFrame()
        toolbar.setFrameStyle(QFrame.Shape.StyledPanel)
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border-bottom: 1px solid #e0e0e0;
            }
        """)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(5, 2, 5, 2)

        # 模式标签
        mode_label = QLabel(t("label.preview_mode") + ":")
        mode_label.setStyleSheet("font-size: 9pt; color: #666;")
        toolbar_layout.addWidget(mode_label)

        # 模式选择下拉框
        self.mode_combo = QComboBox()
        self.mode_combo.addItem(t("preview_mode.tab"), PreviewMode.TAB)
        self.mode_combo.addItem(t("preview_mode.bottom"), PreviewMode.BOTTOM)
        self.mode_combo.addItem(t("preview_mode.dock"), PreviewMode.DOCK)
        self.mode_combo.addItem(t("preview_mode.expanded"), PreviewMode.EXPANDED)
        self.mode_combo.setStyleSheet("""
            QComboBox {
                padding: 3px 8px;
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: white;
                font-size: 9pt;
                min-height: 18px;
            }
            QComboBox:focus {
                border: 1px solid #4a90e2;
            }
        """)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        toolbar_layout.addWidget(self.mode_combo)

        # 可见性复选框
        self.visibility_checkbox = QCheckBox(t("label.show_preview"))
        self.visibility_checkbox.setChecked(True)
        self.visibility_checkbox.setStyleSheet("""
            QCheckBox {
                font-size: 9pt;
                spacing: 5px;
            }
        """)
        self.visibility_checkbox.toggled.connect(self._on_visibility_changed)
        toolbar_layout.addWidget(self.visibility_checkbox)

        toolbar_layout.addStretch()

        # 将工具栏添加到预览容器顶部
        container_layout = self.preview_container.layout()
        if container_layout:
            container_layout.insertWidget(0, toolbar)

        self.logger.debug("模式切换工具栏创建完成")

    def _on_mode_changed(self, index: int):
        """模式改变事件处理"""
        mode = self.mode_combo.itemData(index)
        if mode:
            self.set_mode(mode)

    def _on_visibility_changed(self, checked: bool):
        """可见性改变事件处理"""
        self.set_preview_visible(checked)

    def set_mode(self, mode: PreviewMode):
        """
        设置预览模式

        Args:
            mode: 预览模式
        """
        if self.current_mode == mode:
            return

        self.logger.info(f"切换预览模式: {self.current_mode.value} -> {mode.value}")

        # 隐藏所有模式
        self._hide_all_modes()

        # 显示选中的模式
        if mode == PreviewMode.TAB:
            self._show_tab_mode()
        elif mode == PreviewMode.BOTTOM:
            self._show_bottom_mode()
        elif mode == PreviewMode.DOCK:
            self._show_dock_mode()
        elif mode == PreviewMode.EXPANDED:
            self._show_expanded_mode()

        self.current_mode = mode
        self.mode_changed.emit(mode.value)

    def _hide_all_modes(self):
        """隐藏所有模式"""
        # 隐藏标签页模式
        if self.preview_tab and self.tab_widget:
            index = self.tab_widget.indexOf(self.preview_tab)
            if index >= 0:
                self.tab_widget.removeTab(index)

        # 隐藏底部模式
        if self.preview_bottom_widget:
            self.preview_bottom_widget.hide()

        # 隐藏停靠窗口模式
        if self.preview_dock:
            self.preview_dock.hide()

    def _show_tab_mode(self):
        """显示标签页模式"""
        if self.preview_tab and self.tab_widget:
            # 重新添加到标签页
            self.tab_widget.addTab(self.preview_tab, t("tab.preview_tab"))
            # 切换到预览标签页
            index = self.tab_widget.indexOf(self.preview_tab)
            if index >= 0:
                self.tab_widget.setCurrentIndex(index)

    def _show_bottom_mode(self):
        """显示底部模式"""
        if self.preview_bottom_widget:
            self.preview_bottom_widget.show()
            # 确保分割器存在
            if self.preview_splitter:
                # 恢复分割比例
                self.preview_splitter.setSizes([700, 300])

    def _show_dock_mode(self):
        """显示停靠窗口模式"""
        if self.preview_dock:
            self.main_window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.preview_dock)
            self.preview_dock.show()

    def _show_expanded_mode(self):
        """显示展开模式（全屏或最大化）"""
        if self.preview_dock:
            self.main_window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.preview_dock)
            self.preview_dock.show()
            # 最大化停靠窗口
            self.preview_dock.setFloating(True)
            self.preview_dock.resize(1200, 800)

    def set_preview_visible(self, visible: bool):
        """
        设置预览可见性

        Args:
            visible: 是否可见
        """
        if visible:
            if self.current_mode == PreviewMode.TAB and self.preview_tab:
                # 确保标签页存在
                if self.tab_widget and self.tab_widget.indexOf(self.preview_tab) < 0:
                    self.tab_widget.addTab(self.preview_tab, t("tab.preview_tab"))
            elif self.current_mode == PreviewMode.DOCK and self.preview_dock:
                self.preview_dock.show()
            elif self.current_mode == PreviewMode.BOTTOM and self.preview_bottom_widget:
                self.preview_bottom_widget.show()
        else:
            if self.current_mode == PreviewMode.TAB and self.preview_tab and self.tab_widget:
                index = self.tab_widget.indexOf(self.preview_tab)
                if index >= 0:
                    self.tab_widget.removeTab(index)
            elif self.current_mode == PreviewMode.DOCK and self.preview_dock:
                self.preview_dock.hide()
            elif self.current_mode == PreviewMode.BOTTOM and self.preview_bottom_widget:
                self.preview_bottom_widget.hide()

        self.preview_visibility_changed.emit(visible)

    def refresh_preview(self, immediate: bool = False):
        """刷新预览"""
        if self.preview_widget:
            self.preview_widget.refresh_preview(immediate=immediate)

    def highlight_element(self, selection):
        """高亮显示指定元素"""
        if self.preview_widget:
            self.preview_widget.highlight_element(selection)

    def jump_to_selection(self):
        """跳转到当前选中的元素"""
        if self.preview_widget:
            self.preview_widget.jump_to_selection()

    def get_current_mode(self) -> PreviewMode:
        """获取当前预览模式"""
        return self.current_mode

    def cleanup(self):
        """清理资源"""
        self.logger.debug("开始清理预览管理器资源")

        if self.preview_widget:
            self.preview_widget.cleanup()

        if self.preview_dock:
            self.preview_dock.close()

        self.logger.debug("预览管理器资源清理完成")
