"""
预览管理器
支持灵活的预览显示模式：嵌入标签页、展开、主界面下方、可拖动
"""
import logging
from typing import Optional, Dict, Any, List
from enum import Enum

from PyQt6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTabWidget, QSplitter, QFrame,
    QLabel, QComboBox, QCheckBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QIcon

from .realtime_preview import RealtimePreviewWidget
from ...i18n.i18n import t


class PreviewMode(Enum):
    """预览模式枚举"""
    TAB = "tab"  # 嵌入标签页
    BOTTOM = "bottom"  # 主界面下方
    DOCK = "dock"  # 停靠窗口（可拖动）


class PreviewManager(QObject):
    """预览管理器 - 管理预览功能的多种显示模式"""
    
    @staticmethod
    def _show_widget_recursively(widget):
        """递归显示部件及其所有子部件"""
        import sys
        import traceback
        if not widget:
            print(f"[DEBUG PREVIEW MANAGER] _show_widget_recursively: widget 为 None，跳过", file=sys.stderr)
            return
        try:
            print(f"[DEBUG PREVIEW MANAGER] _show_widget_recursively: 显示部件 {widget.__class__.__name__}", file=sys.stderr)
            parent = widget.parent()
            print(f"[DEBUG PREVIEW MANAGER] _show_widget_recursively: {widget.__class__.__name__} 父部件={parent.__class__.__name__ if parent else 'None'}", file=sys.stderr)
            widget.show()
            # 强制更新布局，确保部件可见
            widget.updateGeometry()
            widget.update()
            print(f"[DEBUG PREVIEW MANAGER] _show_widget_recursively: {widget.__class__.__name__} 可见性={widget.isVisible()}, 尺寸={widget.size()}", file=sys.stderr)
            if widget.layout():
                print(f"[DEBUG PREVIEW MANAGER] _show_widget_recursively: {widget.__class__.__name__} 有布局，子部件数量={widget.layout().count()}", file=sys.stderr)
                for i in range(widget.layout().count()):
                    item = widget.layout().itemAt(i)
                    if item:
                        child = item.widget()
                        if child:
                            print(f"[DEBUG PREVIEW MANAGER] _show_widget_recursively: 递归显示子部件 {i}: {child.__class__.__name__}", file=sys.stderr)
                            PreviewManager._show_widget_recursively(child)
            else:
                print(f"[DEBUG PREVIEW MANAGER] _show_widget_recursively: {widget.__class__.__name__} 没有布局", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR PREVIEW MANAGER] _show_widget_recursively 异常: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)

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

        # 底部模式的分割器
        self.preview_splitter: Optional[QSplitter] = None

        # 保存主分割器的原始子部件（用于底部模式切换）
        self.main_splitter_original_children: List[QWidget] = []

        self.logger.info("预览管理器初始化完成")

    def create_preview_widget(self) -> RealtimePreviewWidget:
        """创建预览组件"""
        if self.preview_widget is None:
            # 指定父部件，防止显示为独立窗口
            self.preview_widget = RealtimePreviewWidget(
                state_manager=self.state_manager,
                coordinator=self.coordinator,
                parent=self.main_window
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
        # 不在这里调用 show()，因为这个部件应该作为子部件显示
        # 而不是作为独立窗口显示
        # self.preview_container.show()

        # 创建模式切换工具栏
        self._create_mode_toolbar()

        # 创建标签页模式
        self._create_tab_mode()
        
        # 创建底部模式
        self._create_bottom_mode()
        
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

        # 注意：preview_container将在_show_bottom_mode中动态添加
        # 不在这里添加，避免重复添加问题

        # 默认隐藏底部模式
        self.preview_bottom_widget.hide()

        self.logger.debug("底部模式创建完成")


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
        mode_label = QLabel(t("label.preview_mode") + ":")
        mode_label.setStyleSheet("font-size: 9pt; color: #666;")
        toolbar_layout.addWidget(mode_label)

        # 模式选择下拉框
        self.mode_combo = QComboBox()
        self.mode_combo.addItem(t("preview_mode.tab"), PreviewMode.TAB)
        self.mode_combo.addItem(t("preview_mode.bottom"), PreviewMode.BOTTOM)
        self.mode_combo.addItem(t("preview_mode.dock"), PreviewMode.DOCK)
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

    def set_mode(self, mode: PreviewMode):
        """
        设置预览模式
        
        Args:
            mode: 预览模式
        """
        import sys
        print(f"[DEBUG PREVIEW MANAGER] set_mode 被调用，mode={mode.value}, current_mode={self.current_mode.value if self.current_mode else 'None'}", file=sys.stderr)
        if self.current_mode == mode:
            print(f"[DEBUG PREVIEW MANAGER] 模式未变化，但仍调用_show_tab_mode", file=sys.stderr)
            # 即使模式未变化，也要调用_show_tab_mode来确保预览标签页被正确显示
            if mode == PreviewMode.TAB:
                self._show_tab_mode()
            return
        
        self.logger.info(f"切换预览模式: {self.current_mode.value} -> {mode.value}")
        
        # 隐藏所有模式，传递目标模式以避免不必要的隐藏操作
        self._hide_all_modes(target_mode=mode)

        # 显示选中的模式
        if mode == PreviewMode.TAB:
            self._show_tab_mode()
        elif mode == PreviewMode.BOTTOM:
            self._show_bottom_mode()
        elif mode == PreviewMode.DOCK:
            self._show_dock_mode()

        self.current_mode = mode
        self.mode_changed.emit(mode.value)

    def _hide_all_modes(self, target_mode: Optional[PreviewMode] = None):
        """
        隐藏所有模式
        
        Args:
            target_mode: 目标模式，如果提供，则不会隐藏该模式
        """
        import sys
        print(f"[DEBUG PREVIEW MANAGER] _hide_all_modes 被调用，target_mode={target_mode.value if target_mode else 'None'}, current_mode={self.current_mode.value if self.current_mode else 'None'}", file=sys.stderr)
        
        # 隐藏标签页模式（仅当当前模式是标签页模式时）
        if self.preview_tab and self.tab_widget and self.current_mode == PreviewMode.TAB:
            index = self.tab_widget.indexOf(self.preview_tab)
            if index >= 0:
                self.tab_widget.removeTab(index)
            # 注意：不从preview_tab的布局中移除preview_container，以保持其布局
            # _show_tab_mode、_show_bottom_mode、_show_dock_mode会自动处理preview_container的移动

        # 隐藏底部模式并恢复主分割器结构（仅当当前模式是底部模式时）
        if self.preview_bottom_widget and self.current_mode == PreviewMode.BOTTOM:
            print(f"[DEBUG PREVIEW MANAGER] 当前是底部模式，调用 _hide_bottom_mode", file=sys.stderr)
            self._hide_bottom_mode()
        elif self.preview_bottom_widget:
            print(f"[DEBUG PREVIEW MANAGER] 当前不是底部模式，跳过 _hide_bottom_mode", file=sys.stderr)

        # 隐藏停靠窗口模式（仅当当前模式是停靠窗口模式时）
        if self.preview_dock and self.current_mode == PreviewMode.DOCK:
            self.preview_dock.hide()
            # 从主窗口中移除dock，避免重复添加
            self.main_window.removeDockWidget(self.preview_dock)
            # 注意：不从dock_content的布局中移除preview_container，以保持其布局
            # _show_tab_mode、_show_bottom_mode、_show_dock_mode会自动处理preview_container的移动

    def _show_tab_mode(self):
        """显示标签页模式"""
        import sys
        print(f"[DEBUG PREVIEW MANAGER] _show_tab_mode 被调用", file=sys.stderr)
        if self.preview_tab and self.tab_widget:
            # 将preview_container移动到preview_tab的布局中
            layout = self.preview_tab.layout()
            print(f"[DEBUG PREVIEW MANAGER] preview_tab layout={layout}, preview_container={self.preview_container}", file=sys.stderr)
            if layout:
                # 检查preview_container是否已经在布局中
                container_index = layout.indexOf(self.preview_container)
                print(f"[DEBUG PREVIEW MANAGER] preview_container 在布局中的索引={container_index}", file=sys.stderr)
                if container_index < 0:
                    # 在移动preview_container之前，先保存preview_widget的引用
                    saved_preview_widget = None
                    if hasattr(self, 'preview_widget') and self.preview_widget:
                        saved_preview_widget = self.preview_widget
                        # 从preview_container的布局中移除preview_widget
                        if self.preview_container.layout():
                            self.preview_container.layout().removeWidget(self.preview_widget)
                            self.preview_widget.setParent(None)
                    
                    # 直接添加到新布局，PyQt会自动处理父部件的变更
                    print(f"[DEBUG PREVIEW MANAGER] preview_container 当前父级={self.preview_container.parent().__class__.__name__ if self.preview_container.parent() else 'None'}", file=sys.stderr)
                    layout.addWidget(self.preview_container)
                    print(f"[DEBUG PREVIEW MANAGER] preview_container 已添加到布局", file=sys.stderr)
                    print(f"[DEBUG PREVIEW MANAGER] preview_container 新父级={self.preview_container.parent().__class__.__name__ if self.preview_container.parent() else 'None'}", file=sys.stderr)
                
                # 确保preview_widget被正确添加到preview_container的布局中
                print(f"[DEBUG PREVIEW MANAGER] 检查preview_widget是否在preview_container中", file=sys.stderr)
                if hasattr(self, 'preview_widget') and self.preview_widget:
                    # 先从preview_container的布局中移除preview_widget（如果存在）
                    if self.preview_container.layout():
                        for i in range(self.preview_container.layout().count()):
                            item = self.preview_container.layout().itemAt(i)
                            if item and item.widget() == self.preview_widget:
                                print(f"[DEBUG PREVIEW MANAGER] 从preview_container中移除preview_widget", file=sys.stderr)
                                self.preview_container.layout().removeWidget(self.preview_widget)
                                self.preview_widget.setParent(None)
                                break
                    
                    # 重新添加preview_widget到preview_container的布局中
                    print(f"[DEBUG PREVIEW MANAGER] 重新添加preview_widget到preview_container", file=sys.stderr)
                    if not self.preview_container.layout():
                        container_layout = QVBoxLayout(self.preview_container)
                        container_layout.setContentsMargins(0, 0, 0, 0)
                    self.preview_container.layout().addWidget(self.preview_widget)
                    print(f"[DEBUG PREVIEW MANAGER] preview_widget 已添加到 preview_container 布局", file=sys.stderr)
                    print(f"[DEBUG PREVIEW MANAGER] preview_widget 父部件={self.preview_widget.parent().__class__.__name__ if self.preview_widget.parent() else 'None'}", file=sys.stderr)
                
                # 确保preview_container和preview_widget可见
                self.preview_container.show()
                if hasattr(self, 'preview_widget') and self.preview_widget:
                    self.preview_widget.show()
                    self._show_widget_recursively(self.preview_widget)
            
            # 重新添加到标签页（如果不存在）
            index = self.tab_widget.indexOf(self.preview_tab)
            print(f"[DEBUG PREVIEW MANAGER] preview_tab 在tab_widget中的索引={index}", file=sys.stderr)
            if index < 0:
                self.tab_widget.addTab(self.preview_tab, t("tab.preview_tab"))
                print(f"[DEBUG PREVIEW MANAGER] preview_tab 已添加到tab_widget", file=sys.stderr)
            else:
                print(f"[DEBUG PREVIEW MANAGER] preview_tab 已在tab_widget中", file=sys.stderr)
            
            # 切换到预览标签页
            index = self.tab_widget.indexOf(self.preview_tab)
            if index >= 0:
                self.tab_widget.setCurrentIndex(index)
                print(f"[DEBUG PREVIEW MANAGER] 已切换到预览标签页，索引={index}", file=sys.stderr)
        else:
            print(f"[DEBUG PREVIEW MANAGER] preview_tab 或 tab_widget 为 None", file=sys.stderr)

    def _hide_bottom_mode(self):
        """隐藏底部模式并恢复主分割器结构"""
        import sys
        print(f"[DEBUG PREVIEW MANAGER] _hide_bottom_mode 被调用", file=sys.stderr)
        
        if self.preview_bottom_widget:
            print(f"[DEBUG PREVIEW MANAGER] 隐藏 preview_bottom_widget", file=sys.stderr)
            try:
                self.preview_bottom_widget.hide()
                print(f"[DEBUG PREVIEW MANAGER] preview_bottom_widget 已隐藏", file=sys.stderr)
            except Exception as e:
                print(f"[DEBUG PREVIEW MANAGER] 隐藏 preview_bottom_widget 时出错: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)

        # 如果存在预览分割器，恢复主分割器的原始结构
        print(f"[DEBUG PREVIEW MANAGER] preview_splitter={self.preview_splitter}, main_splitter={self.main_splitter}", file=sys.stderr)
        if self.preview_splitter and self.main_splitter:
            print(f"[DEBUG PREVIEW MANAGER] 开始恢复主分割器结构", file=sys.stderr)
            print(f"[DEBUG PREVIEW MANAGER] main_splitter_original_children={self.main_splitter_original_children}", file=sys.stderr)
            
            # 在删除preview_splitter之前，先保存preview_widget的引用
            if hasattr(self, 'preview_widget') and self.preview_widget:
                # 从preview_splitter中移除preview_widget（通过设置父级为None）
                if self.preview_splitter.indexOf(self.preview_widget) >= 0:
                    self.preview_widget.setParent(None)
                    print(f"[DEBUG PREVIEW MANAGER] preview_widget 已从 preview_splitter 中移除", file=sys.stderr)
            
            # 从主分割器中移除预览分割器（通过设置父级为None）
            print(f"[DEBUG PREVIEW MANAGER] 设置 preview_splitter 父级为 None", file=sys.stderr)
            self.preview_splitter.setParent(None)
            print(f"[DEBUG PREVIEW MANAGER] preview_splitter 父级已设置为 None", file=sys.stderr)

            # 将保存的原始子部件重新添加到主分割器
            print(f"[DEBUG PREVIEW MANAGER] 开始重新添加子部件到主分割器", file=sys.stderr)
            for i, child in enumerate(self.main_splitter_original_children):
                print(f"[DEBUG PREVIEW MANAGER] 添加子部件 {i}: {child}", file=sys.stderr)
                child.setParent(self.main_splitter)
                self.main_splitter.addWidget(child)
                # 确保子部件被正确显示
                child.show()
                self._show_widget_recursively(child)
            print(f"[DEBUG PREVIEW MANAGER] 所有子部件已重新添加", file=sys.stderr)

            # 清空原始子部件列表
            self.main_splitter_original_children = []
            print(f"[DEBUG PREVIEW MANAGER] 原始子部件列表已清空", file=sys.stderr)

            # 删除预览分割器以释放资源
            print(f"[DEBUG PREVIEW MANAGER] 删除 preview_splitter", file=sys.stderr)
            self.preview_splitter.deleteLater()
            self.preview_splitter = None
            print(f"[DEBUG PREVIEW MANAGER] preview_splitter 已删除", file=sys.stderr)

            # 强制更新主分割器的布局，确保界面间距正确
            print(f"[DEBUG PREVIEW MANAGER] 更新主分割器布局", file=sys.stderr)
            self.main_splitter.updateGeometry()
            self.main_splitter.update()
            self.main_splitter.repaint()
            print(f"[DEBUG PREVIEW MANAGER] 主分割器布局已更新", file=sys.stderr)
        else:
            print(f"[DEBUG PREVIEW MANAGER] preview_splitter 或 main_splitter 不存在，跳过恢复操作", file=sys.stderr)
        
        print(f"[DEBUG PREVIEW MANAGER] _hide_bottom_mode 完成", file=sys.stderr)

    def _show_bottom_mode(self):
        """显示底部模式"""
        import sys
        print(f"[DEBUG PREVIEW MANAGER] _show_bottom_mode 被调用", file=sys.stderr)
        print(f"[DEBUG PREVIEW MANAGER] preview_container={self.preview_container}, preview_bottom_widget={self.preview_bottom_widget}", file=sys.stderr)
        
        if not self.preview_bottom_widget:
            print(f"[DEBUG PREVIEW MANAGER] preview_bottom_widget 为 None，返回", file=sys.stderr)
            return
        
        # 如果有主分割器，创建底部预览的分割器结构
        import sys
        print(f"[DEBUG PREVIEW MANAGER] main_splitter={self.main_splitter}, preview_splitter={self.preview_splitter}", file=sys.stderr)
        if self.main_splitter and not self.preview_splitter:
            print(f"[DEBUG PREVIEW MANAGER] 进入底部模式创建逻辑", file=sys.stderr)
            # 保存主分割器的原始子部件
            self.main_splitter_original_children = []
            for i in range(self.main_splitter.count()):
                child = self.main_splitter.widget(i)
                if child:
                    self.main_splitter_original_children.append(child)
            print(f"[DEBUG PREVIEW MANAGER] 保存的原始子部件数量={len(self.main_splitter_original_children)}", file=sys.stderr)

            # 创建新的垂直分割器
            self.preview_splitter = QSplitter(Qt.Orientation.Vertical)
            self.preview_splitter.setChildrenCollapsible(False)  # 防止部件被完全折叠
            self.preview_splitter.setHandleWidth(8)  # 增加手柄宽度，使其更容易拖动

            # 将主分割器的子部件移到新分割器（通过设置父级）
            for child in self.main_splitter_original_children:
                child.setParent(self.preview_splitter)
                self.preview_splitter.addWidget(child)

            # 添加预览到底部（直接添加preview_widget）
            # 先从preview_container的布局中移除preview_widget
            if hasattr(self, 'preview_widget') and self.preview_widget:
                if self.preview_container.layout():
                    self.preview_container.layout().removeWidget(self.preview_widget)
                    self.preview_widget.setParent(None)
                self.preview_splitter.addWidget(self.preview_widget)
            print(f"[DEBUG PREVIEW MANAGER] preview_splitter 子部件数量={self.preview_splitter.count()}", file=sys.stderr)
            
            # 在底部模式下，将模式切换工具栏添加到preview_widget的顶部
            # 从preview_container中提取工具栏
            if self.preview_container.layout() and self.preview_container.layout().count() > 0:
                toolbar = self.preview_container.layout().itemAt(0).widget()
                if toolbar and hasattr(self.preview_widget, 'layout'):
                    # 创建一个容器部件来包装工具栏
                    toolbar_container = QWidget()
                    toolbar_layout = QVBoxLayout(toolbar_container)
                    toolbar_layout.setContentsMargins(0, 0, 0, 0)
                    toolbar_layout.addWidget(toolbar)
                    # 将容器添加到preview_widget布局的顶部
                    self.preview_widget.layout().insertWidget(0, toolbar_container)
                    print(f"[DEBUG PREVIEW MANAGER] 工具栏已添加到 preview_widget 顶部", file=sys.stderr)
            
            # 确保preview_widget可见
            self.preview_widget.show()
            print(f"[DEBUG PREVIEW MANAGER] preview_widget.show() 已调用", file=sys.stderr)
            print(f"[DEBUG PREVIEW MANAGER] preview_widget.isVisible()={self.preview_widget.isVisible()}", file=sys.stderr)


            # 设置分割比例，允许用户自由拉伸
            total_height = self.main_splitter.height() if self.main_splitter else 800
            main_height = int(total_height * 0.6)
            preview_height = int(total_height * 0.4)
            self.preview_splitter.setSizes([main_height, preview_height])

            # 设置每个部件的最小高度为40，允许更大范围拉伸
            if self.preview_splitter.count() > 0:
                main_widget = self.preview_splitter.widget(0)
                if main_widget:
                    main_widget.setMinimumHeight(40)
                    main_widget.setSizePolicy(main_widget.sizePolicy().horizontalPolicy(), QSizePolicy.Policy.Expanding)
                    self.preview_splitter.setStretchFactor(0, 3)
            if self.preview_splitter.count() > 1:
                preview_widget = self.preview_splitter.widget(1)
                if preview_widget:
                    preview_widget.setMinimumHeight(40)
                    preview_widget.setSizePolicy(preview_widget.sizePolicy().horizontalPolicy(), QSizePolicy.Policy.Expanding)
                    self.preview_splitter.setStretchFactor(1, 2)

            # 确保分割器手柄可见且可交互
            self.preview_splitter.setEnabled(True)
            self.preview_splitter.setOpaqueResize(True)  # 实时显示拖动效果

            # 将新分割器添加到主分割器
            self.main_splitter.addWidget(self.preview_splitter)
            print(f"[DEBUG PREVIEW MANAGER] preview_splitter 已添加到 main_splitter", file=sys.stderr)
            
            # 显示预览分割器
            self.preview_splitter.show()
            print(f"[DEBUG PREVIEW MANAGER] preview_splitter 已显示", file=sys.stderr)

        # 注意：在底部模式下，preview_widget被添加到preview_splitter中，而不是preview_container
        # 工具栏已经被添加到preview_widget的顶部，不需要在这里处理preview_container
        # preview_bottom_widget不需要被显示，因为它只是一个占位符
        print(f"[DEBUG PREVIEW MANAGER] preview_container 已显示（递归）", file=sys.stderr)
        print(f"[DEBUG PREVIEW MANAGER] preview_container.isVisible()={self.preview_container.isVisible()}", file=sys.stderr)
        
        # 确保 preview_widget 可见（递归显示所有子部件）
        if hasattr(self, 'preview_widget') and self.preview_widget:
            self._show_widget_recursively(self.preview_widget)
            print(f"[DEBUG PREVIEW MANAGER] preview_widget 已显示（递归）", file=sys.stderr)
            # 检查 preview_edit 的状态
            if hasattr(self.preview_widget, 'preview_edit') and self.preview_widget.preview_edit:
                print(f"[DEBUG PREVIEW MANAGER] preview_edit 可见={self.preview_widget.preview_edit.isVisible()}, 文本长度={len(self.preview_widget.preview_edit.toPlainText())}", file=sys.stderr)
        
        # 强制更新布局，确保部件可见
        self.preview_bottom_widget.updateGeometry()
        self.preview_bottom_widget.update()
        self.preview_bottom_widget.repaint()
        
        # 如果存在预览分割器，确保它也被更新
        if self.preview_splitter:
            self.preview_splitter.updateGeometry()
            self.preview_splitter.update()
            self.preview_splitter.repaint()
        
        # 强制刷新预览内容，确保在切换到底部模式时显示内容
        # 注释掉刷新调用，避免阻塞
        # if hasattr(self, 'preview_widget') and self.preview_widget:
        #     print(f"[DEBUG PREVIEW MANAGER] 强制刷新预览内容", file=sys.stderr)
        #     try:
        #         self.preview_widget.refresh_preview(immediate=True)
        #     except Exception as e:
        #         print(f"[DEBUG PREVIEW MANAGER] 刷新预览内容时出错: {e}", file=sys.stderr)
        #         import traceback
        #         traceback.print_exc(file=sys.stderr)
        
        print(f"[DEBUG PREVIEW MANAGER] _show_bottom_mode 完成", file=sys.stderr)

    def _show_dock_mode(self):
        """显示停靠窗口模式"""
        import sys
        print(f"[DEBUG PREVIEW MANAGER] _show_dock_mode 被调用", file=sys.stderr)
        
        # 如果停靠窗口不存在，创建它
        if not self.preview_dock:
            print(f"[DEBUG PREVIEW MANAGER] 创建停靠窗口", file=sys.stderr)
            self.preview_dock = QDockWidget(t("tab.preview_tab"), self.main_window)
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
            
            # 将预览组件添加到停靠窗口
            if hasattr(self, 'preview_widget') and self.preview_widget:
                # 先从preview_container的布局中移除preview_widget
                if self.preview_container.layout():
                    self.preview_container.layout().removeWidget(self.preview_widget)
                    self.preview_widget.setParent(None)
                self.preview_dock.setWidget(self.preview_widget)
                print(f"[DEBUG PREVIEW MANAGER] preview_widget 已添加到停靠窗口", file=sys.stderr)
            
            # 将停靠窗口添加到主窗口
            self.main_window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.preview_dock)
            print(f"[DEBUG PREVIEW MANAGER] 停靠窗口已添加到主窗口", file=sys.stderr)
        
        # 显示停靠窗口
        self.preview_dock.show()
        print(f"[DEBUG PREVIEW MANAGER] 停靠窗口已显示", file=sys.stderr)
        
        # 确保preview_widget可见（递归显示所有子部件）
        if hasattr(self, 'preview_widget') and self.preview_widget:
            self._show_widget_recursively(self.preview_widget)
            print(f"[DEBUG PREVIEW MANAGER] preview_widget 已显示（递归）", file=sys.stderr)
        
        print(f"[DEBUG PREVIEW MANAGER] _show_dock_mode 完成", file=sys.stderr)

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
            elif self.current_mode == PreviewMode.BOTTOM and self.preview_bottom_widget:
                self.preview_bottom_widget.show()
            elif self.current_mode == PreviewMode.DOCK and self.preview_dock:
                self.preview_dock.show()
        else:
            if self.current_mode == PreviewMode.TAB and self.preview_tab and self.tab_widget:
                index = self.tab_widget.indexOf(self.preview_tab)
                if index >= 0:
                    self.tab_widget.removeTab(index)
            elif self.current_mode == PreviewMode.BOTTOM and self.preview_bottom_widget:
                self.preview_bottom_widget.hide()
            elif self.current_mode == PreviewMode.DOCK and self.preview_dock:
                self.preview_dock.hide()

        self.preview_visibility_changed.emit(visible)

    def refresh_preview(self, immediate: bool = False):
        """刷新预览"""
        import sys
        print(f"[DEBUG PREVIEW MANAGER] refresh_preview 被调用，immediate={immediate}, preview_widget={self.preview_widget}", file=sys.stderr)
        if self.preview_widget:
            self.preview_widget.refresh_preview(immediate=immediate)
        else:
            print(f"[DEBUG PREVIEW MANAGER] preview_widget 为 None，无法刷新", file=sys.stderr)

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
