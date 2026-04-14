"""
预览管理器
支持停靠窗口模式的预览显示
"""
import logging
from typing import Optional, List

from PyQt6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout,
    QLabel, QCheckBox, QSizePolicy, QFrame, QHBoxLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject

from .realtime_preview import RealtimePreviewWidget
from ...i18n.i18n import t


class PreviewManager(QObject):
    """预览管理器 - 管理预览功能的停靠窗口模式"""
    
    # 信号定义
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

        # 预览是否可见
        self._preview_visible = True

        self.logger.info("预览管理器初始化完成")

    def create_preview_widget(self) -> RealtimePreviewWidget:
        """创建预览组件"""
        if self.preview_widget is None:
            self.preview_widget = RealtimePreviewWidget(
                state_manager=self.state_manager,
                coordinator=self.coordinator,
            )
            # 不设置parent，避免作为主窗口的浮动子控件显示
            # 当添加到dock widget时会自动设置parent
            self.preview_widget.hide()
            self.logger.info("预览组件创建完成")
        return self.preview_widget

    def setup_preview_modes(self, tab_widget=None, main_splitter=None):
        """
        设置预览模式（停靠窗口）

        Args:
            tab_widget: 标签页控件（保留兼容性，不使用）
            main_splitter: 主分割器（保留兼容性，不使用）
        """
        # 创建预览组件
        self.create_preview_widget()

        # 默认显示预览窗口
        self._preview_visible = True
        self._ensure_dock()
        if self.preview_dock:
            self.preview_dock.show()
        if self.preview_widget:
            self.preview_widget.show()

        self.logger.info("预览模式设置完成（默认显示）")

    def _ensure_dock(self):
        """确保停靠窗口已创建"""
        if not self.preview_dock:
            self.preview_dock = QDockWidget(t("tab.preview_tab", default="SVD预览"), self.main_window)
            self.preview_dock.setAllowedAreas(
                Qt.DockWidgetArea.BottomDockWidgetArea |
                Qt.DockWidgetArea.TopDockWidgetArea |
                Qt.DockWidgetArea.LeftDockWidgetArea |
                Qt.DockWidgetArea.RightDockWidgetArea
            )
            self.preview_dock.setFeatures(
                QDockWidget.DockWidgetFeature.DockWidgetClosable |
                QDockWidget.DockWidgetFeature.DockWidgetMovable |
                QDockWidget.DockWidgetFeature.DockWidgetFloatable
            )
            
            # 将预览组件设置为dock的widget
            self.preview_dock.setWidget(self.preview_widget)
            
            # 将停靠窗口添加到主窗口
            self.main_window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.preview_dock)
            
            # 连接关闭事件
            self.preview_dock.closeEvent = self._on_dock_close_event

    def _on_dock_close_event(self, event):
        """处理停靠窗口的关闭事件"""
        self.logger.info("用户关闭了停靠窗口")
        event.accept()
        self._preview_visible = False
        self.preview_visibility_changed.emit(False)

    def set_preview_visible(self, visible: bool):
        """
        设置预览可见性

        Args:
            visible: 是否可见
        """
        self._preview_visible = visible
        
        if visible:
            self._ensure_dock()
            if self.preview_dock:
                self.preview_dock.show()
            if self.preview_widget:
                self.preview_widget.show()
        else:
            if self.preview_dock:
                self.preview_dock.hide()

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

    def cleanup(self):
        """清理资源"""
        self.logger.debug("开始清理预览管理器资源")
        
        if self.preview_widget:
            self.preview_widget.cleanup()
        
        self.logger.debug("预览管理器资源清理完成")