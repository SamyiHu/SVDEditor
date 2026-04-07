"""
预览管理器
支持灵活的预览显示模式：嵌入主界面下方、可拖动停靠窗口
"""
import logging
from typing import Optional, Dict, Any, List
from enum import Enum

from PyQt6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QSplitter, QFrame,
    QLabel, QComboBox, QCheckBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QIcon

from .realtime_preview import RealtimePreviewWidget
from ...i18n.i18n import t


class PreviewMode(Enum):
    """预览模式枚举"""
    BOTTOM = "bottom"  # 主界面下方
    DOCK = "dock"  # 停靠窗口（可拖动）


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

        # 当前模式
        self.current_mode = PreviewMode.BOTTOM

        # 控件引用
        self.main_splitter: Optional[QSplitter] = None

        # 模式切换控件
        self.mode_combo: Optional[QComboBox] = None
        self.visibility_checkbox: Optional[QCheckBox] = None

        # 预览容器（包含工具栏，在不同模式间移动预览内容）
        self.preview_container: Optional[QWidget] = None
        self.mode_toolbar: Optional[QFrame] = None

        # 底部模式的分割器
        self.preview_splitter: Optional[QSplitter] = None

        # 保存主分割器的原始子部件（用于底部模式切换）
        self.main_splitter_original_children: List[QWidget] = []

        # 记录dock是否因为模式切换而被隐藏（区别于用户关闭）
        self._dock_hidden_by_mode_switch = False

        # 预览是否可见
        self._preview_visible = True

        self.logger.info("预览管理器初始化完成")

    def create_preview_widget(self) -> RealtimePreviewWidget:
        """创建预览组件"""
        if self.preview_widget is None:
            self.preview_widget = RealtimePreviewWidget(
                state_manager=self.state_manager,
                coordinator=self.coordinator,
                parent=self.main_window
            )
            self.logger.info("预览组件创建完成")
        return self.preview_widget

    def setup_preview_modes(self, tab_widget=None, main_splitter: QSplitter = None):
        """
        设置预览的多种显示模式

        Args:
            tab_widget: 标签页控件（不再使用，保留兼容性）
            main_splitter: 主分割器（用于底部模式）
        """
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

        # 默认使用底部模式
        self.set_mode(PreviewMode.BOTTOM)

        self.logger.info("预览模式设置完成")

    def _create_mode_toolbar(self):
        """创建模式切换工具栏"""
        self.mode_toolbar = QFrame()
        toolbar = self.mode_toolbar
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
        mode_label = QLabel(t("label.preview_mode", default="预览模式") + ":")
        mode_label.setStyleSheet("font-size: 9pt; color: #666;")
        toolbar_layout.addWidget(mode_label)

        # 模式选择下拉框
        self.mode_combo = QComboBox()
        self.mode_combo.addItem(t("preview_mode.bottom", default="底部面板"), PreviewMode.BOTTOM)
        self.mode_combo.addItem(t("preview_mode.dock", default="停靠窗口"), PreviewMode.DOCK)
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
        self.visibility_checkbox = QCheckBox(t("label.show_preview", default="显示预览"))
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
        self.logger.debug(f"模式改变事件触发，index={index}")
        if self.mode_combo is None:
            self.logger.error("mode_combo为None，无法切换模式")
            return
        
        mode = self.mode_combo.itemData(index)
        self.logger.debug(f"获取到的mode={mode}")
        if mode:
            self.set_mode(mode)
        else:
            self.logger.warning(f"无法获取index={index}对应的模式数据")

    def _on_visibility_changed(self, checked: bool):
        """可见性改变事件处理"""
        self.set_preview_visible(checked)

    def _reparent_preview_container(self):
        """
        将preview_container（包含工具栏和preview_widget）移动到当前模式对应的容器中。
        """
        self.logger.debug(f"_reparent_preview_container: 从当前父布局中移除preview_container")
        
        # 从当前父布局中移除
        old_parent_layout = self.preview_container.parent() and self.preview_container.parent().layout()
        if old_parent_layout:
            idx = old_parent_layout.indexOf(self.preview_container)
            if idx >= 0:
                old_parent_layout.removeWidget(self.preview_container)
        
        # 确保preview_container的布局完整
        container_layout = self.preview_container.layout()
        if not container_layout:
            container_layout = QVBoxLayout(self.preview_container)
            container_layout.setContentsMargins(0, 0, 0, 0)
        
        # 确保mode_toolbar在布局中
        if self.mode_toolbar:
            toolbar_idx = container_layout.indexOf(self.mode_toolbar)
            if toolbar_idx < 0:
                container_layout.insertWidget(0, self.mode_toolbar)
        
        # 确保preview_widget在布局中
        if self.preview_widget:
            widget_idx = container_layout.indexOf(self.preview_widget)
            if widget_idx < 0:
                container_layout.addWidget(self.preview_widget)

    def set_mode(self, mode: PreviewMode):
        """
        设置预览模式
        
        Args:
            mode: 预览模式
        """
        if self.current_mode == mode:
            return
        
        self.logger.info(f"切换预览模式: {self.current_mode.value} -> {mode.value}")
        
        # 清除当前模式
        self._deactivate_current_mode()

        # 激活新模式
        if mode == PreviewMode.BOTTOM:
            self._activate_bottom_mode()
        elif mode == PreviewMode.DOCK:
            self._activate_dock_mode()

        self.current_mode = mode
        self.mode_changed.emit(mode.value)

    def _deactivate_current_mode(self):
        """停用当前预览模式，清理并恢复状态"""
        if self.current_mode == PreviewMode.BOTTOM:
            self._deactivate_bottom_mode()
        elif self.current_mode == PreviewMode.DOCK:
            self._deactivate_dock_mode()

    def _deactivate_bottom_mode(self):
        """停用底部模式：恢复主分割器结构"""
        if self.preview_splitter and self.main_splitter:
            # 先将preview_container从preview_splitter的预览区域中移除
            if self.preview_container:
                splitter_idx = self.preview_splitter.indexOf(self.preview_container)
                if splitter_idx >= 0:
                    self.preview_container.setParent(self.main_window)

            # 保存preview_splitter中的子部件
            children = []
            for i in range(self.preview_splitter.count()):
                child = self.preview_splitter.widget(i)
                if child:
                    children.append(child)

            # 从主分割器中移除preview_splitter
            self.preview_splitter.setParent(None)

            # 恢复主分割器的原始子部件
            for child in children:
                child.setParent(self.main_splitter)
                self.main_splitter.addWidget(child)
                child.show()

            # 清理preview_splitter
            self.preview_splitter.deleteLater()
            self.preview_splitter = None

            # 强制更新主分割器
            self.main_splitter.updateGeometry()
            self.main_splitter.update()

    def _deactivate_dock_mode(self):
        """停用停靠窗口模式：隐藏并清理dock"""
        if self.preview_dock:
            self._dock_hidden_by_mode_switch = True
            
            # 先从dock中取出preview_container
            dock_content = self.preview_dock.widget()
            if dock_content is self.preview_container:
                self.preview_dock.setWidget(None)
                self.preview_container.setParent(self.main_window)
            
            self.preview_dock.hide()
            self.main_window.removeDockWidget(self.preview_dock)

    def _activate_bottom_mode(self):
        """激活底部模式"""
        if not self.main_splitter:
            return

        # 移动preview_container（先从旧父级移除）
        self._reparent_preview_container()

        # 创建垂直分割器
        self.preview_splitter = QSplitter(Qt.Orientation.Vertical)
        self.preview_splitter.setChildrenCollapsible(False)
        self.preview_splitter.setHandleWidth(8)

        # 保存并移动主分割器的子部件到preview_splitter
        self.main_splitter_original_children = []
        for i in range(self.main_splitter.count()):
            child = self.main_splitter.widget(i)
            if child:
                self.main_splitter_original_children.append(child)

        for child in self.main_splitter_original_children:
            child.setParent(self.preview_splitter)
            self.preview_splitter.addWidget(child)

        # 添加preview_container到底部
        self.preview_splitter.addWidget(self.preview_container)
        self.preview_container.show()
        if self.preview_widget:
            self.preview_widget.show()

        # 设置分割比例
        total_height = self.main_splitter.height() if self.main_splitter else 800
        main_height = int(total_height * 0.6)
        preview_height = int(total_height * 0.4)
        self.preview_splitter.setSizes([main_height, preview_height])

        # 设置拉伸因子
        if self.preview_splitter.count() > 0:
            self.preview_splitter.setStretchFactor(0, 3)
        if self.preview_splitter.count() > 1:
            self.preview_splitter.setStretchFactor(1, 2)

        self.preview_splitter.setOpaqueResize(True)

        # 将preview_splitter添加到主分割器
        self.main_splitter.addWidget(self.preview_splitter)
        self.preview_splitter.show()

    def _activate_dock_mode(self):
        """激活停靠窗口模式"""
        # 移动preview_container（先从旧父级移除）
        self._reparent_preview_container()

        if not self.preview_dock:
            # 创建停靠窗口
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
            
            # 连接关闭事件
            self.preview_dock.closeEvent = self._on_dock_close_event
        else:
            # dock已存在，确保内容被正确恢复
            old_widget = self.preview_dock.widget()
            if old_widget and old_widget is not self.preview_container:
                self.preview_dock.setWidget(None)
                old_widget.setParent(None)

        # 将preview_container设置为dock的widget
        self.preview_dock.setWidget(self.preview_container)
        
        # 将停靠窗口添加到主窗口
        self.main_window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.preview_dock)
        
        self._dock_hidden_by_mode_switch = False
        self.preview_dock.show()
        
        self.preview_container.show()
        if self.preview_widget:
            self.preview_widget.show()

    def _on_dock_close_event(self, event):
        """
        处理停靠窗口的关闭事件。
        """
        if self._dock_hidden_by_mode_switch:
            self._dock_hidden_by_mode_switch = False
            event.accept()
            return
        
        # 用户手动关闭了dock窗口
        self.logger.info("用户关闭了停靠窗口")
        event.accept()
        self._preview_visible = False
        
        # 更新可见性复选框
        if self.visibility_checkbox:
            self.visibility_checkbox.blockSignals(True)
            self.visibility_checkbox.setChecked(False)
            self.visibility_checkbox.blockSignals(False)
        
        self.preview_visibility_changed.emit(False)

    def set_preview_visible(self, visible: bool):
        """
        设置预览可见性

        Args:
            visible: 是否可见
        """
        self._preview_visible = visible
        
        if visible:
            if self.current_mode == PreviewMode.DOCK and self.preview_dock:
                self.preview_dock.show()
                self.preview_container.show()
                if self.preview_widget:
                    self.preview_widget.show()
            elif self.current_mode == PreviewMode.BOTTOM and self.preview_container:
                self.preview_container.show()
                if self.preview_widget:
                    self.preview_widget.show()
        else:
            if self.current_mode == PreviewMode.DOCK and self.preview_dock:
                self._dock_hidden_by_mode_switch = True
                self.preview_dock.hide()
            elif self.current_mode == PreviewMode.BOTTOM and self.preview_container:
                self.preview_container.hide()

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
        
        self.logger.debug("预览管理器资源清理完成")