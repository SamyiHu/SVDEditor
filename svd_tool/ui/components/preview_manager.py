"""
预览管理器
SVD预览固定在标签页中显示
"""
import logging
from typing import Optional

from PyQt6.QtWidgets import QWidget, QTabWidget, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal, QObject

from .realtime_preview import RealtimePreviewWidget
from ...i18n.i18n import t


class PreviewManager(QObject):
    """预览管理器 - 管理固定在标签页中的SVD预览"""

    # 信号定义
    preview_visibility_changed = pyqtSignal(bool)  # 预览可见性改变

    def __init__(self, main_window, state_manager, coordinator=None):
        super().__init__()
        self.main_window = main_window
        self.state_manager = state_manager
        self.coordinator = coordinator
        self.logger = logging.getLogger("PreviewManager")

        self.preview_widget: Optional[RealtimePreviewWidget] = None
        self._tab_widget: Optional[QTabWidget] = None
        self._preview_tab_index: int = -1

        self.logger.info("预览管理器初始化完成")

    def create_preview_widget(self) -> RealtimePreviewWidget:
        """创建预览组件"""
        if self.preview_widget is None:
            self.preview_widget = RealtimePreviewWidget(
                state_manager=self.state_manager,
                coordinator=self.coordinator,
            )
            self.logger.info("预览组件创建完成")
        return self.preview_widget

    def setup_preview_modes(self, tab_widget=None, main_splitter=None):
        """
        设置预览模式（固定标签页）

        Args:
            tab_widget: 标签页控件
            main_splitter: 主分割器（保留兼容性，不使用）
        """
        self._tab_widget = tab_widget
        self.create_preview_widget()

        injected = False

        # 方式1: 通过 layout_manager → tab_builder → 占位区域
        lm = getattr(self.main_window, 'layout_manager', None)
        if lm:
            tb = getattr(lm, 'tab_builder', None)
            if tb and hasattr(tb, '_preview_placeholder'):
                layout = tb._preview_placeholder.layout()
                if layout:
                    layout.addWidget(self.preview_widget)
                    self.preview_widget.show()
                    injected = True

        # 方式2: 回退 — 直接替换预览标签页内容
        if not injected and tab_widget:
            preview_title = t("tab.preview_tab", default="预览")
            for i in range(tab_widget.count()):
                if tab_widget.tabText(i) == preview_title:
                    tab = tab_widget.widget(i)
                    if tab:
                        # 清空原有内容，换为预览组件
                        old_layout = tab.layout()
                        if old_layout:
                            while old_layout.count():
                                item = old_layout.takeAt(0)
                                w = item.widget()
                                if w:
                                    w.setParent(None)
                        else:
                            from PyQt6.QtWidgets import QVBoxLayout
                            old_layout = QVBoxLayout(tab)
                            old_layout.setContentsMargins(0, 0, 0, 0)
                            old_layout.setSpacing(0)
                        old_layout.addWidget(self.preview_widget)
                        self.preview_widget.show()
                        injected = True
                    break

        if not injected:
            self.logger.warning("未能将预览组件注入标签页")

        self._preview_visible = True
        self.logger.info("预览模式设置完成（固定标签页）")

    def set_preview_visible(self, visible: bool):
        """
        设置预览可见性（切换到/离开预览标签页）

        Args:
            visible: 是否可见
        """
        self._preview_visible = visible

        if visible:
            # 切换到预览标签页
            if self._tab_widget:
                # 查找预览标签页索引
                for i in range(self._tab_widget.count()):
                    if self._tab_widget.tabText(i) == t("tab.preview_tab", default="预览"):
                        self._tab_widget.setCurrentIndex(i)
                        break
            # 确保在切换到预览标签时刷新内容（避免之前未触发的更新）
            try:
                if self.preview_widget:
                    self.preview_widget.refresh_preview(immediate=True)
            except Exception:
                self.logger.exception("刷新预览时发生错误")

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
