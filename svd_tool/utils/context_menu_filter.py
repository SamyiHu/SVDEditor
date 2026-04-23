"""
全局文本控件右键菜单样式统一过滤器
拦截 QLineEdit / QPlainTextEdit / QTextEdit 的默认右键菜单，
替换为与应用全局菜单风格一致的 QMenu。
"""
from PyQt6.QtWidgets import (
    QMenu, QLineEdit, QPlainTextEdit, QTextEdit, QWidget
)
from PyQt6.QtCore import QObject, QEvent


def _build_text_menu(widget: QWidget) -> QMenu:
    """根据控件能力构建标准文本编辑菜单"""
    from ..i18n.i18n import t
    menu = QMenu(widget)

    is_readonly = widget.isReadOnly() if hasattr(widget, 'isReadOnly') else False
    has_selection = False
    if isinstance(widget, QLineEdit):
        has_selection = widget.hasSelectedText()
    elif isinstance(widget, (QPlainTextEdit, QTextEdit)):
        has_selection = bool(widget.textCursor().hasSelection())

    if not is_readonly:
        undo_ok = widget.isUndoAvailable() if hasattr(widget, 'isUndoAvailable') else False
        redo_ok = widget.isRedoAvailable() if hasattr(widget, 'isRedoAvailable') else False
        if undo_ok:
            a = menu.addAction(t("menu.edit.undo"))
            a.triggered.connect(widget.undo)
        if redo_ok:
            a = menu.addAction(t("menu.edit.redo"))
            a.triggered.connect(widget.redo)
        if undo_ok or redo_ok:
            menu.addSeparator()

        if has_selection:
            a = menu.addAction(t("menu.edit.cut"))
            a.triggered.connect(widget.cut)

    if has_selection:
        a = menu.addAction(t("menu.edit.copy"))
        a.triggered.connect(widget.copy)

    if not is_readonly:
        a = menu.addAction(t("menu.edit.paste"))
        a.triggered.connect(widget.paste)

    menu.addSeparator()
    a = menu.addAction(t("menu.edit.select_all", default="全选"))
    a.triggered.connect(widget.selectAll)

    return menu


class _StyledTextMenuFilter(QObject):
    """事件过滤器：拦截文本控件的 ContextMenu 事件"""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.ContextMenu:
            if isinstance(obj, (QLineEdit, QPlainTextEdit, QTextEdit)):
                # 仅拦截使用 DefaultContextMenu 策略的控件
                # （已改为 CustomContextMenu 的控件由各自的 handler 处理）
                if obj.contextMenuPolicy() == QWidget.ContextMenuPolicy.DefaultContextMenu:
                    menu = _build_text_menu(obj)
                    if menu.actions():
                        menu.exec(event.globalPos())
                    return True  # 事件已处理，阻止默认菜单
        return super().eventFilter(obj, event)


# 全局单例
_filter_instance = None


def install_text_context_menu_filter(app_or_widget):
    """安装全局文本控件右键菜单过滤器"""
    global _filter_instance
    if _filter_instance is None:
        _filter_instance = _StyledTextMenuFilter()
    app_or_widget.installEventFilter(_filter_instance)
