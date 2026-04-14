"""
工具栏组件 - 精简现代风格
纯文字按钮，紧凑布局
"""
from PyQt6.QtWidgets import QToolBar, QToolButton
from PyQt6.QtCore import Qt, QSize
from ...i18n.i18n import t


class ToolBarBuilder:
    """工具栏构建器 - 精简现代风格"""

    def __init__(self, parent, main_window):
        self.parent = parent
        self.main_window = main_window
        self.toolbar = None

    def create(self) -> QToolBar:
        """创建工具栏并返回"""
        toolbar = self.parent.addToolBar(t("toolbar.main"))
        if toolbar is None:
            return None

        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.toolbar = toolbar

        self._add_file_actions()
        self._add_edit_actions()

        return toolbar

    def _add_file_actions(self):
        """添加文件操作按钮"""
        if self.toolbar is None:
            return

        new_action = self.toolbar.addAction(t("toolbar.new"))
        new_action.triggered.connect(self.main_window.new_file)

        open_action = self.toolbar.addAction(t("toolbar.open"))
        open_action.triggered.connect(self.main_window.open_svd_file)

        save_action = self.toolbar.addAction(t("toolbar.save"))
        save_action.triggered.connect(self.main_window.save_svd_file)

        self.toolbar.addSeparator()

    def _add_edit_actions(self):
        """添加编辑操作按钮"""
        if self.toolbar is None:
            return

        undo_action = self.toolbar.addAction(t("toolbar.undo"))
        undo_action.triggered.connect(self.main_window.undo)

        redo_action = self.toolbar.addAction(t("toolbar.redo"))
        redo_action.triggered.connect(self.main_window.redo)

        self.toolbar.addSeparator()
