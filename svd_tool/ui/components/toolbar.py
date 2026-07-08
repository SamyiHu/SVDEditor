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

        # AI 助手按钮
        if hasattr(self.main_window, 'ai_assistant') and self.main_window.ai_assistant:
            ai_btn = QToolButton()
            ai_btn.setText("AI")
            ai_btn.setToolTip(t("menu.view.ai_assistant", default="AI 助手"))
            ai_btn.clicked.connect(self.main_window.toggle_ai_assistant)
            ai_btn.setStyleSheet("""
                QToolButton {
                    background-color: #4A90D9;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-weight: bold;
                    font-size: 10pt;
                    min-height: 20px;
                }
                QToolButton:hover {
                    background-color: #3A7BC8;
                }
                QToolButton:pressed {
                    background-color: #2E6AB5;
                }
            """)
            self.toolbar.addWidget(ai_btn)
            self.toolbar.addSeparator()

        # 数据手册导入按钮（资源导入入口，绿色强调）
        if hasattr(self.main_window, 'datasource_manager') and self.main_window.datasource_manager:
            from ..config.styles import get_style_scheme
            try:
                colors = get_style_scheme().colors
                accent = colors.button_success
                accent_hover = colors.button_success_hover
                accent_pressed = colors.button_success_pressed
            except Exception:
                accent, accent_hover, accent_pressed = "#2E7D32", "#1B5E20", "#0D3814"
            ds_btn = QToolButton()
            ds_btn.setText(t("toolbar.import", default="导入"))
            ds_btn.setToolTip(t("menu.tools.import_datasheet", default="从数据手册导入…"))
            ds_btn.clicked.connect(self.main_window.import_datasheet)
            ds_btn.setStyleSheet(f"""
                QToolButton {{
                    background-color: {accent};
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-weight: bold;
                    font-size: 10pt;
                    min-height: 20px;
                }}
                QToolButton:hover {{
                    background-color: {accent_hover};
                }}
                QToolButton:pressed {{
                    background-color: {accent_pressed};
                }}
            """)
            self.toolbar.addWidget(ds_btn)
            self.toolbar.addSeparator()
