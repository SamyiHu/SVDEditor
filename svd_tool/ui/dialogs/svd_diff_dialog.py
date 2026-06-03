"""
SVD 对话框 — 对比 + 合并统一界面
左右并排树形对比 / 原始 XML 对比 / 合并操作
"""
import os
from typing import Optional, Dict, Tuple, List
from xml.dom import minidom
import re as _re

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTreeWidget, QTreeWidgetItem, QLabel, QFileDialog,
    QMessageBox, QComboBox, QFrame, QSizePolicy, QHeaderView, QSplitter,
    QStackedWidget, QPlainTextEdit, QTextEdit, QStyledItemDelegate, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QTextCursor, QTextBlockFormat

from ...core.svd_parser import SVDParser
from ...core.svd_differ import SVDDiffer, DiffType, DiffItem
from ...core.svd_merger import SVDMerger, MergeAction, MergeConflictLevel, MergeItem
from ...core.svd_generator import SVDGenerator
from ...core.data_model import DeviceInfo
from ...config.styles import get_style_scheme
from ...i18n.i18n import t
from ..widgets.toggle_switch import ToggleSwitch

# 合并操作下拉框选项
_ACTION_OPTIONS = [
    (MergeAction.KEEP_TARGET, "保留当前"),
    (MergeAction.USE_SOURCE, "使用导入"),
    (MergeAction.MERGE_BOTH, "逐项合并"),
]


class _ActionDelegate(QStyledItemDelegate):
    """合并操作列下拉委托"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._actions = {}  # id(tree_item) -> MergeAction

    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        for action, text in _ACTION_OPTIONS:
            combo.addItem(text, action.value)
        return combo

    def setEditorData(self, editor, index):
        tree_item = self._get_tree_item(index)
        if tree_item:
            action = self._actions.get(id(tree_item), MergeAction.KEEP_TARGET)
            for i, (act, _) in enumerate(_ACTION_OPTIONS):
                if act == action:
                    editor.setCurrentIndex(i)
                    break

    def setModelData(self, editor, model, index):
        tree_item = self._get_tree_item(index)
        if tree_item:
            action = MergeAction(editor.currentData())
            self._actions[id(tree_item)] = action
            merge_item = tree_item.data(0, Qt.ItemDataRole.UserRole)
            if merge_item:
                merge_item.action = action
            action_text = {a: txt for a, txt in _ACTION_OPTIONS}.get(action, "")
            tree_item.setText(3, action_text)

    def _get_tree_item(self, index):
        tree = self.parent()
        if tree and isinstance(tree, QTreeWidget):
            return tree.itemFromIndex(index)
        return None


class SVDDiffDialog(QDialog):
    """SVD 对比 + 合并统一对话框"""

    merge_completed = pyqtSignal(DeviceInfo)

    def __init__(self, parent=None, current_device: DeviceInfo = None,
                 document_manager=None, initial_mode: str = "compare"):
        super().__init__(parent)
        self.setWindowTitle(t("diff_merge.title"))
        self.setMinimumSize(900, 600)
        self.resize(1050, 700)
        self.current_device = current_device
        self.other_device: Optional[DeviceInfo] = None
        self.document_manager = document_manager
        self._open_docs: Dict[str, Tuple[str, DeviceInfo]] = {}
        self.differ = SVDDiffer()
        self.merger = SVDMerger()
        self.merge_items: list = []
        self._diffs: List[DiffItem] = []
        self._syncing_scroll = False
        self._current_mode = initial_mode  # "compare" or "merge"
        self._setup_ui()

    def _setup_ui(self):
        _c = get_style_scheme().colors
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # === 文件选择栏 ===
        file_bar = QHBoxLayout()
        file_bar.setSpacing(8)

        # 当前文件
        curr_frame = QFrame()
        curr_frame.setStyleSheet(f"""
            QFrame {{
                background: {_c.accent_light};
                border: 1px solid {_c.selected_border};
                border-radius: 6px;
            }}
        """)
        curr_lay = QHBoxLayout(curr_frame)
        curr_lay.setContentsMargins(10, 4, 10, 4)
        curr_lay.setSpacing(6)
        curr_tag = QLabel("A")
        curr_tag.setStyleSheet(f"background: {_c.accent}; color: white; border-radius: 3px; padding: 1px 6px; font-weight: bold;")
        curr_lay.addWidget(curr_tag)
        self.curr_name_label = QLabel("")
        self.curr_name_label.setStyleSheet(f"color: {_c.text_primary}; font-weight: bold; border: none;")
        if self.current_device:
            self.curr_name_label.setText(self.current_device.name or t("msg.unnamed"))
        curr_lay.addWidget(self.curr_name_label, 1)
        file_bar.addWidget(curr_frame, 1)

        # 过滤
        self.chk_description = ToggleSwitch(t("diff.ignore_desc"))
        self.chk_description.stateChanged.connect(self._re_diff)
        file_bar.addWidget(self.chk_description)

        self.chk_reset_value = ToggleSwitch(t("diff.ignore_reset"))
        self.chk_reset_value.stateChanged.connect(self._re_diff)
        file_bar.addWidget(self.chk_reset_value)

        # 比较文件
        other_frame = QFrame()
        other_frame.setStyleSheet(f"""
            QFrame {{
                background: {_c.surface};
                border: 1px solid {_c.border};
                border-radius: 6px;
            }}
        """)
        other_lay = QHBoxLayout(other_frame)
        other_lay.setContentsMargins(10, 4, 10, 4)
        other_lay.setSpacing(6)
        b_tag = QLabel("B")
        b_tag.setStyleSheet(f"background: {_c.text_secondary}; color: white; border-radius: 3px; padding: 1px 6px; font-weight: bold;")
        other_lay.addWidget(b_tag)
        self.file_label = QLabel(t("diff_merge.no_file_selected"))
        self.file_label.setStyleSheet(f"color: {_c.text_disabled}; border: none;")
        other_lay.addWidget(self.file_label, 1)

        self._open_doc_combo = QComboBox()
        self._open_doc_combo.setFixedWidth(160)
        self._open_doc_combo.currentIndexChanged.connect(self._on_open_doc_selected)
        other_lay.addWidget(self._open_doc_combo)

        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(30)
        browse_btn.clicked.connect(self._browse_file)
        other_lay.addWidget(browse_btn)

        file_bar.addWidget(other_frame, 1)
        layout.addLayout(file_bar)

        # 填充已打开文档
        if self.document_manager:
            self._open_doc_combo.blockSignals(True)
            active_id = self.document_manager.active_doc_id
            for doc_id, doc in self.document_manager.get_all_documents().items():
                if doc_id != active_id:
                    display = doc.display_name or doc.device_info.name or t("msg.unnamed")
                    self._open_docs[display] = (doc_id, doc.device_info)
                    self._open_doc_combo.addItem(display)
            self._open_doc_combo.blockSignals(False)

        # === 统计栏 ===
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(f"color: {_c.text_secondary}; font-size: 9pt; padding: 2px 4px;")
        layout.addWidget(self.stats_label)

        # === 视图切换按钮 ===
        view_bar = QHBoxLayout()
        view_bar.setSpacing(4)

        # 模式切换：对比 / 合并
        self.btn_mode_compare = QPushButton(t("diff.mode_compare"))
        self.btn_mode_compare.setCheckable(True)
        self.btn_mode_compare.setChecked(self._current_mode == "compare")
        self.btn_mode_compare.setFixedHeight(26)
        self.btn_mode_compare.clicked.connect(lambda: self._switch_mode("compare"))
        view_bar.addWidget(self.btn_mode_compare)

        self.btn_mode_merge = QPushButton(t("diff.mode_merge"))
        self.btn_mode_merge.setCheckable(True)
        self.btn_mode_merge.setChecked(self._current_mode == "merge")
        self.btn_mode_merge.setFixedHeight(26)
        self.btn_mode_merge.clicked.connect(lambda: self._switch_mode("merge"))
        view_bar.addWidget(self.btn_mode_merge)

        # 分隔
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(12)
        view_bar.addWidget(sep)

        # 子视图切换（仅对比模式可见）
        self.btn_tree_view = QPushButton(t("diff.view_tree"))
        self.btn_tree_view.setCheckable(True)
        self.btn_tree_view.setChecked(True)
        self.btn_tree_view.setFixedHeight(26)
        self.btn_tree_view.clicked.connect(lambda: self._switch_view("tree"))
        view_bar.addWidget(self.btn_tree_view)

        self.btn_raw_view = QPushButton(t("diff.view_raw"))
        self.btn_raw_view.setCheckable(True)
        self.btn_raw_view.setChecked(False)
        self.btn_raw_view.setFixedHeight(26)
        self.btn_raw_view.clicked.connect(lambda: self._switch_view("raw"))
        view_bar.addWidget(self.btn_raw_view)

        # 合并模式快捷按钮（仅合并模式可见）
        self.btn_accept_all = QPushButton(t("diff.accept_all"))
        self.btn_accept_all.setFixedHeight(26)
        self.btn_accept_all.clicked.connect(self._accept_all_new)
        view_bar.addWidget(self.btn_accept_all)

        self.btn_keep_all = QPushButton(t("diff.keep_all"))
        self.btn_keep_all.setFixedHeight(26)
        self.btn_keep_all.clicked.connect(self._keep_all_current)
        view_bar.addWidget(self.btn_keep_all)

        view_bar.addStretch()
        layout.addLayout(view_bar)

        # === 视图堆叠 ===
        self.view_stack = QStackedWidget()

        # --- 第 0 页：树形对比 ---
        tree_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.tree_a = QTreeWidget()
        self.tree_a.setHeaderLabels([t("diff.current")])
        self.tree_a.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree_a.setStyleSheet(f"""
            QTreeWidget {{ border: 1px solid {_c.border_light}; border-radius: 4px; }}
            QTreeWidget::item {{ padding: 2px 4px; height: 22px; }}
        """)
        # 隐藏左侧滚动条
        self.tree_a.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tree_a.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.tree_b = QTreeWidget()
        self.tree_b.setHeaderLabels([t("diff.other")])
        self.tree_b.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree_b.setStyleSheet(f"""
            QTreeWidget {{ border: 1px solid {_c.border_light}; border-radius: 4px; }}
            QTreeWidget::item {{ padding: 2px 4px; height: 22px; }}
        """)

        # 同步展开/折叠
        self.tree_a.itemExpanded.connect(lambda item: self._sync_expand(item, self.tree_b, True))
        self.tree_b.itemExpanded.connect(lambda item: self._sync_expand(item, self.tree_a, True))
        self.tree_a.itemCollapsed.connect(lambda item: self._sync_expand(item, self.tree_b, False))
        self.tree_b.itemCollapsed.connect(lambda item: self._sync_expand(item, self.tree_a, False))

        # 同步滚动
        self.tree_b.verticalScrollBar().valueChanged.connect(self._sync_tree_scroll_from_b)
        self.tree_a.verticalScrollBar().valueChanged.connect(self._sync_tree_scroll_from_a)

        tree_splitter.addWidget(self.tree_a)
        tree_splitter.addWidget(self.tree_b)
        tree_splitter.setSizes([500, 500])
        self.view_stack.addWidget(tree_splitter)

        # --- 第 1 页：原始 XML 对比 ---
        xml_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.xml_edit_a = QPlainTextEdit()
        self.xml_edit_a.setReadOnly(True)
        self.xml_edit_a.setFont(QFont("Consolas", 9))
        self.xml_edit_a.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.xml_edit_a.setStyleSheet("""
            QPlainTextEdit {
                background: #ffffff;
                border: 1px solid #d0d0d0; border-radius: 4px;
                color: #333333;
            }
        """)
        self.xml_edit_a.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.xml_edit_a.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.xml_edit_b = QPlainTextEdit()
        self.xml_edit_b.setReadOnly(True)
        self.xml_edit_b.setFont(QFont("Consolas", 9))
        self.xml_edit_b.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.xml_edit_b.setStyleSheet("""
            QPlainTextEdit {
                background: #ffffff;
                border: 1px solid #d0d0d0; border-radius: 4px;
                color: #333333;
            }
        """)

        # 同步滚动
        self.xml_edit_b.verticalScrollBar().valueChanged.connect(self._sync_xml_scroll_from_b)
        self.xml_edit_a.verticalScrollBar().valueChanged.connect(self._sync_xml_scroll_from_a)

        xml_splitter.addWidget(self.xml_edit_a)
        xml_splitter.addWidget(self.xml_edit_b)
        xml_splitter.setSizes([500, 500])
        self.view_stack.addWidget(xml_splitter)

        # --- 第 2 页：合并树 ---
        merge_splitter = QSplitter(Qt.Orientation.Vertical)

        self.merge_tree = QTreeWidget()
        self.merge_tree.setHeaderLabels([
            t("diff_merge.col_item"),
            t("diff_merge.col_status"),
            t("diff_merge.col_current"),
            t("diff_merge.col_action"),
            t("diff_merge.col_import"),
        ])
        merge_header = self.merge_tree.header()
        if merge_header:
            merge_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            merge_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            merge_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            merge_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            merge_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.merge_tree.setAlternatingRowColors(True)
        self.merge_tree.setSelectionBehavior(QTreeWidget.SelectionBehavior.SelectRows)
        self.merge_tree.itemClicked.connect(self._on_merge_tree_clicked)

        # 操作列下拉委托
        self.action_delegate = _ActionDelegate(self.merge_tree)
        self.merge_tree.setItemDelegateForColumn(3, self.action_delegate)

        merge_splitter.addWidget(self.merge_tree)

        # 详情面板
        self.merge_detail = QTextEdit()
        self.merge_detail.setReadOnly(True)
        self.merge_detail.setFont(QFont("Consolas", 9))
        self.merge_detail.setMaximumHeight(160)
        self.merge_detail.setPlaceholderText(t("diff_merge.detail_placeholder"))
        merge_splitter.addWidget(self.merge_detail)

        merge_splitter.setSizes([500, 160])
        self.view_stack.addWidget(merge_splitter)

        layout.addWidget(self.view_stack, 1)

        # === 底部 ===
        btn_layout = QHBoxLayout()
        export_btn = QPushButton(t("diff_merge.export_report"))
        export_btn.clicked.connect(self._export_report)
        btn_layout.addWidget(export_btn)
        btn_layout.addStretch()

        self.btn_execute_merge = QPushButton(t("diff.execute_merge"))
        self.btn_execute_merge.setEnabled(False)
        self.btn_execute_merge.setStyleSheet(f"""
            QPushButton {{
                background-color: {_c.accent}; color: white;
                padding: 6px 20px; border: none; border-radius: 4px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {_c.accent_hover}; }}
            QPushButton:disabled {{ background-color: {_c.border}; color: {_c.text_disabled}; }}
        """)
        self.btn_execute_merge.clicked.connect(self._do_merge)
        btn_layout.addWidget(self.btn_execute_merge)

        close_btn = QPushButton(t("dialog.close", default="关闭"))
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        # 初始化模式可见性
        self._apply_mode_visibility()

        # 自动选中
        if self._open_doc_combo.count() > 0:
            self._open_doc_combo.setCurrentIndex(0)
            self._on_open_doc_selected(0)

    # ==================== 模式 / 视图切换 ====================

    def _switch_mode(self, mode: str):
        """切换对比/合并模式"""
        if mode == self._current_mode:
            return
        self._current_mode = mode
        self._apply_mode_visibility()

        if mode == "compare":
            self.btn_mode_compare.setChecked(True)
            self.btn_mode_merge.setChecked(False)
            self._switch_view("tree")
        else:
            self.btn_mode_compare.setChecked(False)
            self.btn_mode_merge.setChecked(True)
            self._do_merge_analyze()

    def _apply_mode_visibility(self):
        """根据当前模式控制 UI 元素可见性"""
        is_compare = self._current_mode == "compare"
        # 对比子视图按钮
        self.btn_tree_view.setVisible(is_compare)
        self.btn_raw_view.setVisible(is_compare)
        # 合并快捷按钮
        self.btn_accept_all.setVisible(not is_compare)
        self.btn_keep_all.setVisible(not is_compare)
        # 执行合并按钮
        self.btn_execute_merge.setVisible(not is_compare)

    def _switch_view(self, mode: str):
        """切换对比子视图（树形/XML）"""
        if mode == "tree":
            self.view_stack.setCurrentIndex(0)
            self.btn_tree_view.setChecked(True)
            self.btn_raw_view.setChecked(False)
        else:
            self._populate_raw_xml()
            self.view_stack.setCurrentIndex(1)
            self.btn_tree_view.setChecked(False)
            self.btn_raw_view.setChecked(True)

    # ==================== 同步滚动 ====================

    def _sync_tree_scroll_from_b(self, value):
        if self._syncing_scroll:
            return
        self._syncing_scroll = True
        self.tree_a.verticalScrollBar().setValue(value)
        self._syncing_scroll = False

    def _sync_tree_scroll_from_a(self, value):
        if self._syncing_scroll:
            return
        self._syncing_scroll = True
        self.tree_b.verticalScrollBar().setValue(value)
        self._syncing_scroll = False

    def _sync_xml_scroll_from_b(self, value):
        if self._syncing_scroll:
            return
        self._syncing_scroll = True
        self.xml_edit_a.verticalScrollBar().setValue(value)
        self._syncing_scroll = False

    def _sync_xml_scroll_from_a(self, value):
        if self._syncing_scroll:
            return
        self._syncing_scroll = True
        self.xml_edit_b.verticalScrollBar().setValue(value)
        self._syncing_scroll = False

    # ==================== 树同步展开 ====================

    def _sync_expand(self, item, target_tree, expand):
        """同步展开/折叠到另一棵树"""
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path:
            return
        target = self._find_item_by_path(target_tree, path)
        if target:
            target.setExpanded(expand)

    def _find_item_by_path(self, tree, path):
        """按路径查找树节点"""
        root = tree.invisibleRootItem()
        return self._find_in_children(root, path)

    def _find_in_children(self, parent, path):
        for i in range(parent.childCount()):
            child = parent.child(i)
            if child.data(0, Qt.ItemDataRole.UserRole) == path:
                return child
            result = self._find_in_children(child, path)
            if result:
                return result
        return None

    # ==================== 文件选择 ====================

    def _on_open_doc_selected(self, index):
        if index < 0:
            return
        display_name = self._open_doc_combo.itemText(index)
        entry = self._open_docs.get(display_name)
        if not entry:
            return
        _, device = entry
        self.other_device = device
        self.file_label.setText(device.name or display_name)
        self.file_label.setStyleSheet(f"color: {get_style_scheme().colors.text_primary}; border: none;")
        self._do_compare()

    def _browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, t("diff_merge.select_file"), "", t("msg.svd_file_filter")
        )
        if not file_path:
            return
        try:
            parser = SVDParser()
            self.other_device = parser.parse_file(file_path)
            self._open_doc_combo.setCurrentIndex(-1)
            name = self.other_device.name or os.path.basename(file_path)
            self.file_label.setText(name)
            self.file_label.setStyleSheet(f"color: {get_style_scheme().colors.text_primary}; border: none;")
            self._do_compare()
            if parser.warnings:
                QMessageBox.warning(self, t("message.warning"), "\n".join(parser.warnings[:5]))
        except Exception as e:
            QMessageBox.critical(self, t("message.error"), str(e))

    def set_other_device(self, device: DeviceInfo):
        self.other_device = device
        self.file_label.setText(device.name or t("diff.compare_file"))
        self.file_label.setStyleSheet(f"color: {get_style_scheme().colors.text_primary}; border: none;")

    # ==================== 比较 ====================

    def _re_diff(self):
        if self.other_device and self.current_device:
            self._do_compare()

    def _do_compare(self):
        if not self.current_device or not self.other_device:
            return

        self.differ.ignore_description = self.chk_description.isChecked()
        self.differ.ignore_reset_value = self.chk_reset_value.isChecked()
        self._diffs = self.differ.diff(self.current_device, self.other_device)

        # 统计
        added = sum(d.count_changes for d in self._diffs if self._has_type(d, DiffType.ADDED))
        removed = sum(d.count_changes for d in self._diffs if self._has_type(d, DiffType.REMOVED))
        modified = sum(d.count_changes for d in self._diffs if self._has_type(d, DiffType.MODIFIED))
        total = added + removed + modified

        _c = get_style_scheme().colors
        if total == 0:
            self.stats_label.setText(t("diff.identical"))
        else:
            self.stats_label.setText(
                t("diff.stats", added=added, removed=removed, modified=modified, total=total)
            )

        # 填充双树
        self.tree_a.blockSignals(True)
        self.tree_b.blockSignals(True)
        self.tree_a.clear()
        self.tree_b.clear()

        self._build_trees(self._diffs, self.tree_a.invisibleRootItem(), self.tree_b.invisibleRootItem())

        # 展开第一层
        for tree in (self.tree_a, self.tree_b):
            for i in range(tree.topLevelItemCount()):
                tree.topLevelItem(i).setExpanded(True)

        self.tree_a.blockSignals(False)
        self.tree_b.blockSignals(False)

        # 如果当前是合并模式，也触发合并分析
        if self._current_mode == "merge":
            self._do_merge_analyze()

    def _build_trees(self, diffs, parent_a, parent_b):
        """同时构建左右两棵树"""
        # 浅色背景 + 深色文字，清晰可见
        bg_add = QBrush(QColor(200, 255, 200))       # 浅绿
        bg_rem = QBrush(QColor(255, 200, 200))       # 浅红
        bg_mod = QBrush(QColor(255, 245, 200))       # 浅黄
        fg_add = QBrush(QColor(0, 120, 0))            # 深绿
        fg_rem = QBrush(QColor(180, 0, 0))            # 深红
        fg_mod = QBrush(QColor(150, 100, 0))          # 深黄
        fg_dim = QBrush(QColor(160, 160, 160))        # 灰色(不存在)

        for diff in diffs:
            path_parts = diff.path.rsplit('.', 1)
            name = path_parts[-1] if len(path_parts) > 1 else diff.path

            # 层级标签
            label = name
            if diff.category == 'peripheral':
                label = f"{t('diff.label_periph')} {name}"
            elif diff.category == 'register':
                label = f"{t('diff.label_reg')} {name}"
            elif diff.category == 'field':
                label = f"{t('diff.label_field')} {name}"

            item_a = QTreeWidgetItem()
            item_a.setText(0, label)
            item_a.setData(0, Qt.ItemDataRole.UserRole, diff.path)

            item_b = QTreeWidgetItem()
            item_b.setText(0, label)
            item_b.setData(0, Qt.ItemDataRole.UserRole, diff.path)

            # 着色
            if diff.diff_type == DiffType.ADDED:
                item_a.setText(0, label + "  —")
                item_a.setForeground(0, fg_dim)
                item_b.setBackground(0, bg_add)
                item_b.setForeground(0, fg_add)
                item_b.setText(0, label + f"  {t('diff.added_suffix')}")
            elif diff.diff_type == DiffType.REMOVED:
                item_a.setBackground(0, bg_rem)
                item_a.setForeground(0, fg_rem)
                item_a.setText(0, label + f"  {t('diff.removed_suffix')}")
                item_b.setText(0, label + "  —")
                item_b.setForeground(0, fg_dim)
            elif diff.diff_type == DiffType.MODIFIED:
                old_str = str(diff.old_value) if diff.old_value is not None else ""
                new_str = str(diff.new_value) if diff.new_value is not None else ""
                if old_str or new_str:
                    item_a.setText(0, f"{label}: {old_str}")
                    item_b.setText(0, f"{label}: {new_str}")
                item_a.setBackground(0, bg_mod)
                item_a.setForeground(0, fg_mod)
                item_b.setBackground(0, bg_mod)
                item_b.setForeground(0, fg_mod)

            parent_a.addChild(item_a)
            parent_b.addChild(item_b)

            # 递归子项
            if diff.children:
                self._build_trees(diff.children, item_a, item_b)

    def _has_type(self, item: DiffItem, diff_type: DiffType) -> bool:
        if item.diff_type == diff_type:
            return True
        return any(self._has_type(c, diff_type) for c in item.children)

    # ==================== 原始 XML 对比 ====================

    # 差异颜色常量
    _BG_ADDED = QColor(0xcd, 0xff, 0xd8)
    _BG_ADDED_DIM = QColor(0xe6, 0xff, 0xec)
    _BG_REMOVED = QColor(0xff, 0xc0, 0xbe)
    _BG_REMOVED_DIM = QColor(0xff, 0xeb, 0xe9)
    _BG_MODIFIED = QColor(0xff, 0xf8, 0xc5)
    _BG_SEP = QColor(0xf0, 0xf0, 0xf0)

    def _populate_raw_xml(self):
        """生成并显示带颜色高亮的对齐原始 XML 内容"""
        if not self.current_device or not self.other_device:
            self.xml_edit_a.clear()
            self.xml_edit_b.clear()
            return

        try:
            lines_a, lines_b = self._generate_aligned_xml()
            self.xml_edit_a.setPlainText("\n".join(lines_a))
            self.xml_edit_b.setPlainText("\n".join(lines_b))

            # 用 QTextBlockFormat 设置行背景色（保证等宽行高，滚动不漂移）
            self._apply_block_colors(self.xml_edit_a, lines_a, lines_b, 'a')
            self._apply_block_colors(self.xml_edit_b, lines_a, lines_b, 'b')
        except Exception as e:
            self.xml_edit_a.setPlainText(f"Error generating XML: {e}")
            self.xml_edit_b.clear()

    def _apply_block_colors(self, editor, lines_a, lines_b, side):
        """用 QTextBlockFormat 设置每行背景色"""
        doc = editor.document()
        cursor = QTextCursor(doc)
        cursor.beginEditBlock()

        count = min(len(lines_a), len(lines_b), doc.blockCount())
        for i in range(count):
            la = lines_a[i]
            lb = lines_b[i]
            bg = self._line_bg_color(la, lb, la.strip() == "", lb.strip() == "", side)

            block = doc.findBlockByNumber(i)
            cursor.setPosition(block.position())
            fmt = QTextBlockFormat(block.blockFormat())
            if bg is not None:
                fmt.setBackground(bg)
            else:
                fmt.clearBackground()
            cursor.setBlockFormat(fmt)

        cursor.endEditBlock()

    def _line_bg_color(self, la, lb, a_empty, b_empty, side):
        """计算单行背景色"""
        if la.startswith("===") or lb.startswith("==="):
            return self._BG_SEP
        if a_empty and b_empty:
            return None
        if a_empty and not b_empty:
            return self._BG_ADDED_DIM if side == 'a' else self._BG_ADDED
        if not a_empty and b_empty:
            return self._BG_REMOVED if side == 'a' else self._BG_REMOVED_DIM
        if la == lb:
            return None
        return self._BG_MODIFIED

    def _generate_aligned_xml(self) -> Tuple[List[str], List[str]]:
        """生成按 B（参考）顺序对齐的 XML 行列表

        Returns:
            (lines_a, lines_b) 对齐后的两份行列表
        """
        # 生成完整 XML
        gen_a = SVDGenerator(self.current_device, skip_derived_registers=False)
        xml_str_a = gen_a.generate(pretty_print=True)

        gen_b = SVDGenerator(self.other_device, skip_derived_registers=False)
        xml_str_b = gen_b.generate(pretty_print=True)

        # 解析为 DOM
        dom_a = minidom.parseString(xml_str_a)
        dom_b = minidom.parseString(xml_str_b)
        self._strip_whitespace_nodes(dom_a)
        self._strip_whitespace_nodes(dom_b)

        # 提取外设元素，按 name 建映射
        periphs_a = self._extract_peripheral_map(dom_a)
        periphs_b = self._extract_peripheral_map(dom_b)

        # 按 B 的顺序对齐
        lines_a = []
        lines_b = []

        # 头部（device 级别属性）
        header_a = self._extract_header(dom_a)
        header_b = self._extract_header(dom_b)
        self._align_text_blocks(lines_a, lines_b, header_a, header_b)

        # 分隔线
        sep = "=" * 60
        lines_a.append(sep)
        lines_b.append(sep)

        # 外设：按 B 的顺序，逐个外设内部分层对齐（寄存器级别）
        seen = set()
        for name in periphs_b:
            seen.add(name)
            self._align_peripheral_pair(lines_a, lines_b,
                                        periphs_a.get(name), periphs_b[name])
            lines_a.append("")
            lines_b.append("")

        # A 中剩余的外设
        for name in periphs_a:
            if name not in seen:
                self._align_peripheral_pair(lines_a, lines_b,
                                            periphs_a[name], None)
                lines_a.append("")
                lines_b.append("")

        # 中断表
        irqs_a = self._extract_interrupts_text(dom_a)
        irqs_b = self._extract_interrupts_text(dom_b)
        if irqs_a or irqs_b:
            lines_a.append(sep)
            lines_b.append(sep)
            self._align_text_blocks(lines_a, lines_b, irqs_a, irqs_b)

        return lines_a, lines_b

    @staticmethod
    def _strip_whitespace_nodes(node):
        """递归移除 DOM 中的纯空白文本节点，防止 toprettyxml 双重缩进"""
        to_remove = []
        for child in node.childNodes:
            if child.nodeType == minidom.Node.TEXT_NODE:
                if child.nodeValue.strip() == '':
                    to_remove.append(child)
            elif child.nodeType == minidom.Node.ELEMENT_NODE:
                SVDDiffDialog._strip_whitespace_nodes(child)
        for child in to_remove:
            node.removeChild(child)

    def _extract_peripheral_map(self, dom) -> Dict[str, 'minidom.Element']:
        """从 DOM 中提取外设映射 {name: element}"""
        result = {}
        peripherals_elements = dom.getElementsByTagName('peripheral')
        for elem in peripherals_elements:
            name_nodes = elem.getElementsByTagName('name')
            if name_nodes and name_nodes[0].firstChild:
                name = name_nodes[0].firstChild.nodeValue.strip()
                result[name] = elem
        return result

    def _extract_header(self, dom) -> str:
        """提取 device 级别的头部属性（peripherals 之前的部分）"""
        device_elem = dom.getElementsByTagName('device')
        if not device_elem:
            return ""
        device_elem = device_elem[0]
        lines = []
        for child in device_elem.childNodes:
            if child.nodeType != minidom.Node.ELEMENT_NODE:
                continue
            if child.tagName == 'peripherals':
                break
            text = child.toprettyxml(indent="  ").strip()
            if text:
                lines.append(text)
        return "\n".join(lines)

    def _peripheral_to_text(self, elem) -> str:
        """将外设元素转换为格式化文本"""
        if elem is None:
            return ""
        raw = elem.toprettyxml(indent="  ")
        lines = [l for l in raw.split('\n') if l.strip()]
        return "\n".join(lines)

    # ==================== 分层对齐（基于文本切割） ====================

    def _align_peripheral_pair(self, lines_a: list, lines_b: list,
                               elem_a, elem_b):
        """对齐一对外设：按寄存器名称逐个对齐"""
        if elem_a is None and elem_b is None:
            return

        if elem_a is None:
            text_b = self._peripheral_to_text(elem_b)
            self._align_text_blocks(lines_a, lines_b, "", text_b)
            return

        if elem_b is None:
            text_a = self._peripheral_to_text(elem_a)
            self._align_text_blocks(lines_a, lines_b, text_a, "")
            return

        # 两侧都有 → 按寄存器拆分对齐
        text_a = self._peripheral_to_text(elem_a)
        text_b = self._peripheral_to_text(elem_b)

        parts_a = self._split_xml_by_children(text_a, 'register')
        parts_b = self._split_xml_by_children(text_b, 'register')

        # 头部（<peripheral>...<registers>）
        self._align_text_blocks(lines_a, lines_b, parts_a['pre'], parts_b['pre'])

        # 寄存器按 B 的顺序对齐
        seen = set()
        for rname in parts_b['items']:
            seen.add(rname)
            reg_a = parts_a['items'].get(rname, "")
            reg_b = parts_b['items'][rname]
            # 寄存器内部再做位域对齐
            self._align_register_text(lines_a, lines_b, reg_a, reg_b)

        for rname in parts_a['items']:
            if rname not in seen:
                self._align_register_text(lines_a, lines_b,
                                          parts_a['items'][rname], "")

        # 尾部（</registers>...</peripheral>）
        self._align_text_blocks(lines_a, lines_b, parts_a['post'], parts_b['post'])

    def _align_register_text(self, lines_a: list, lines_b: list,
                             text_a: str, text_b: str):
        """对齐一对寄存器文本：内部按位域名称对齐"""
        if not text_a and not text_b:
            return

        if not text_a:
            self._align_text_blocks(lines_a, lines_b, "", text_b)
            return

        if not text_b:
            self._align_text_blocks(lines_a, lines_b, text_a, "")
            return

        # 两侧都有 → 按位域拆分对齐
        parts_a = self._split_xml_by_children(text_a, 'field')
        parts_b = self._split_xml_by_children(text_b, 'field')

        # 头部（<register>...<fields>）
        self._align_text_blocks(lines_a, lines_b, parts_a['pre'], parts_b['pre'])

        # 位域按 B 的顺序对齐
        seen = set()
        for fname in parts_b['items']:
            seen.add(fname)
            self._align_text_blocks(lines_a, lines_b,
                                    parts_a['items'].get(fname, ""),
                                    parts_b['items'][fname])

        for fname in parts_a['items']:
            if fname not in seen:
                self._align_text_blocks(lines_a, lines_b,
                                        parts_a['items'][fname], "")

        # 尾部（</fields>...</register>）
        self._align_text_blocks(lines_a, lines_b, parts_a['post'], parts_b['post'])

    @staticmethod
    def _split_xml_by_children(text: str, child_tag: str) -> dict:
        """在完整 XML 文本中按子标签切割。

        例如 child_tag='register' 会找到 <registers>...</registers> 区段，
        再按 <register>...</register> 逐个拆分。

        Returns:
            {
                'pre':   str,             # <registers> 及之前的行
                'items': {name: str, ...}, # 每个子标签的文本块
                'post':  str,             # </registers> 及之后的行
            }
        """

        if not text:
            return {'pre': '', 'items': {}, 'post': ''}

        lines = text.split('\n')

        open_tag = f'<{child_tag}s>'
        close_tag = f'</{child_tag}s>'

        sec_start = None
        sec_end = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            if open_tag in stripped and sec_start is None:
                sec_start = i
            if close_tag in stripped:
                sec_end = i

        # 没有子标签区段 → 整块作为 pre
        if sec_start is None or sec_end is None:
            return {'pre': text, 'items': {}, 'post': ''}

        pre = '\n'.join(lines[:sec_start + 1])
        post = '\n'.join(lines[sec_end:])

        # 解析区段内的子项
        inner = lines[sec_start + 1: sec_end]
        items = {}
        cur_name = None
        cur_block = []
        depth = 0

        tag_open = f'<{child_tag}'
        tag_close = f'</{child_tag}>'

        for line in inner:
            stripped = line.strip()

            if stripped.startswith(tag_open) and not stripped.startswith(tag_close):
                if depth == 0:
                    cur_block = [line]
                    cur_name = None
                else:
                    cur_block.append(line)
                depth += 1
            elif stripped.startswith(tag_close):
                depth -= 1
                cur_block.append(line)
                if depth == 0:
                    block = '\n'.join(cur_block)
                    m = _re.search(r'<name>([^<]+)</name>', block)
                    if m:
                        items[m.group(1)] = block
                    cur_block = []
            else:
                if depth > 0:
                    cur_block.append(line)

        return {'pre': pre, 'items': items, 'post': post}

    # ==================== DOM 拆分工具 ====================

    @staticmethod
    def _get_elem_name(elem) -> str:
        """获取元素的 <name> 子节点文本"""
        for child in elem.childNodes:
            if child.nodeType == minidom.Node.ELEMENT_NODE and child.tagName == 'name':
                if child.firstChild:
                    return child.firstChild.nodeValue.strip()
        return ""

    @staticmethod
    def _elem_to_lines(elem) -> List[str]:
        """将 DOM 元素转为格式化行列表"""
        if elem is None:
            return []
        raw = elem.toprettyxml(indent="  ")
        return [l for l in raw.split('\n') if l.strip()]

    @staticmethod
    def _extend_padded(lines_a: list, lines_b: list, rows_a: list, rows_b: list):
        """将两侧行列表补齐到相同长度后追加"""
        max_len = max(len(rows_a), len(rows_b))
        lines_a.extend(rows_a + [""] * (max_len - len(rows_a)))
        lines_b.extend(rows_b + [""] * (max_len - len(rows_b)))

    def _extract_interrupts_text(self, dom) -> str:
        """提取中断表文本"""
        device_elem = dom.getElementsByTagName('device')
        if not device_elem:
            return ""
        device_elem = device_elem[0]
        for child in device_elem.childNodes:
            if child.nodeType == minidom.Node.ELEMENT_NODE and child.tagName == 'interrupts':
                raw = child.toprettyxml(indent="  ")
                lines = [l for l in raw.split('\n') if l.strip()]
                return "\n".join(lines)
        return ""

    @staticmethod
    def _align_text_blocks(lines_a: list, lines_b: list, text_a: str, text_b: str):
        """对齐两个文本块，添加空行使两侧行数一致"""
        rows_a = text_a.split('\n') if text_a else []
        rows_b = text_b.split('\n') if text_b else []

        max_len = max(len(rows_a), len(rows_b))

        rows_a_padded = rows_a + [""] * (max_len - len(rows_a))
        rows_b_padded = rows_b + [""] * (max_len - len(rows_b))

        lines_a.extend(rows_a_padded)
        lines_b.extend(rows_b_padded)

    # ==================== 导出 ====================

    def _export_report(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, t("diff_merge.export_report"), "svd_diff_report.txt",
            "文本文件 (*.txt);;Markdown (*.md)"
        )
        if not file_path:
            return
        try:
            if self._current_mode == "merge" and self.merge_items:
                summary = self.merger.generate_summary(self.merge_items, {})
            elif self._diffs:
                summary = self.differ.generate_summary(self._diffs)
            else:
                summary = t("diff.no_diff")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(summary)
            QMessageBox.information(self, t("diff_merge.export_done"),
                                    t("diff_merge.export_saved", path=file_path))
        except Exception as e:
            QMessageBox.critical(self, t("message.error"), str(e))

    # ==================== 合并模式 ====================

    def _do_merge_analyze(self):
        """执行合并分析，填充合并树"""
        if not self.current_device or not self.other_device:
            return

        self.view_stack.setCurrentIndex(2)

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.merge_items = self.merger.analyze(self.current_device, self.other_device)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, t("message.error"), str(e))
            return
        finally:
            QApplication.restoreOverrideCursor()

        # 过滤
        if self.chk_description.isChecked():
            self._filter_merge_items(self.merge_items, "Description")

        # 统计
        counts = SVDMerger.count_items(self.merge_items)
        _c = get_style_scheme().colors
        self.stats_label.setText(
            f"{t('diff_merge.analysis_done')}  |  "
            f"<span style='color:{_c.button_success}'>{t('diff_merge.status_new')}: {counts['new_in_source']}</span>  "
            f"<span style='color:{_c.text_secondary}'>{t('diff_merge.status_only_current')}: {counts['only_in_target']}</span>  "
            f"<span style='color:{_c.button_warning}'>{t('diff_merge.status_attr')}: {counts['attr_modified']}</span>  "
            f"<span style='color:{_c.button_danger}'>{t('diff_merge.status_struct')}: {counts['structure_changed']}</span>  "
            f"|  {t('diff_merge.total')}: {counts['total']}"
        )

        # 填充合并树
        self.merge_tree.blockSignals(True)
        self.merge_tree.clear()
        self._populate_merge_tree(self.merge_tree.invisibleRootItem(), self.merge_items)
        self.merge_tree.blockSignals(False)

        # 展开第一层
        for i in range(self.merge_tree.topLevelItemCount()):
            self.merge_tree.topLevelItem(i).setExpanded(True)

        self.btn_execute_merge.setEnabled(True)

    def _populate_merge_tree(self, parent, items: list):
        """递归填充合并树"""
        for item in items:
            tree_item = QTreeWidgetItem()

            # 名称
            path_parts = item.path.rsplit('.', 1)
            display_name = path_parts[-1] if len(path_parts) > 1 else item.path
            tree_item.setText(0, display_name)

            # 状态
            status_map = {
                MergeConflictLevel.NEW_IN_SOURCE: t("diff_merge.status_new"),
                MergeConflictLevel.ONLY_IN_TARGET: t("diff_merge.status_only_current"),
                MergeConflictLevel.ATTR_MODIFIED: t("diff_merge.status_attr"),
                MergeConflictLevel.STRUCTURE_CHANGED: t("diff_merge.status_struct"),
            }
            tree_item.setText(1, status_map.get(item.conflict_level, ""))

            # 当前值
            tree_item.setText(2, self._format_merge_value(item.target_obj))

            # 操作
            action_text = {a: txt for a, txt in _ACTION_OPTIONS}.get(item.action, "")
            tree_item.setText(3, action_text)

            # 导入值
            tree_item.setText(4, self._format_merge_value(item.source_obj))

            # 数据
            tree_item.setData(0, Qt.ItemDataRole.UserRole, item)
            tree_item.setToolTip(0, item.path)

            # 颜色
            self._set_merge_item_colors(tree_item, item.conflict_level)

            # 递归
            if item.children:
                self._populate_merge_tree(tree_item, item.children)

            parent.addChild(tree_item)

    def _format_merge_value(self, obj) -> str:
        """格式化合并值显示"""
        if obj is None:
            return "(" + t("diff_merge.none") + ")"
        if isinstance(obj, (int, float, str, bool)):
            s = str(obj)
            return s[:50] + "..." if len(s) > 50 else s
        if isinstance(obj, dict):
            if 'name' in obj:
                return str(obj['name'])
            return f"dict({len(obj)})"
        if hasattr(obj, 'name'):
            return obj.name
        return type(obj).__name__

    def _set_merge_item_colors(self, tree_item: QTreeWidgetItem,
                                conflict_level: MergeConflictLevel):
        """设置合并树行颜色"""
        if conflict_level == MergeConflictLevel.NEW_IN_SOURCE:
            bg, fg = QColor(220, 255, 220), QColor(0, 128, 0)
        elif conflict_level == MergeConflictLevel.ONLY_IN_TARGET:
            bg, fg = QColor(240, 240, 240), QColor(128, 128, 128)
        elif conflict_level == MergeConflictLevel.ATTR_MODIFIED:
            bg, fg = QColor(255, 255, 220), QColor(160, 120, 0)
        elif conflict_level == MergeConflictLevel.STRUCTURE_CHANGED:
            bg, fg = QColor(255, 220, 200), QColor(200, 80, 0)
        else:
            return
        for col in range(5):
            tree_item.setBackground(col, QBrush(bg))
            tree_item.setForeground(col, QBrush(fg))

    def _on_merge_tree_clicked(self, tree_item: QTreeWidgetItem, column: int):
        """点击合并树项显示详情"""
        merge_item = tree_item.data(0, Qt.ItemDataRole.UserRole)
        if not merge_item:
            return

        lines = [
            f"{'=' * 50}",
            f"  {merge_item.path}",
            f"  {t('diff_merge.col_status')}: {tree_item.text(1)}",
            f"{'=' * 50}",
            "",
        ]
        if merge_item.target_obj is not None:
            lines.append(f"[{t('diff_merge.current_file')}]")
            lines.extend(self._detail_merge_object(merge_item.target_obj))
        if merge_item.source_obj is not None:
            lines.append(f"\n[{t('diff_merge.import_file')}]")
            lines.extend(self._detail_merge_object(merge_item.source_obj))

        self.merge_detail.setPlainText("\n".join(lines))

    def _detail_merge_object(self, obj) -> list:
        """生成对象详情行"""
        lines = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                lines.append(f"  {k}: {v}")
        elif hasattr(obj, '__dict__'):
            for k, v in vars(obj).items():
                if k.startswith('_') or isinstance(v, (dict, list)):
                    continue
                lines.append(f"  {k}: {v}")
        else:
            lines.append(f"  {obj}")
        return lines

    def _filter_merge_items(self, items: list, keyword: str):
        """过滤包含关键字的合并项"""
        to_remove = []
        for item in items:
            if keyword in item.path and item.level.endswith('_attr'):
                to_remove.append(item)
            elif item.children:
                self._filter_merge_items(item.children, keyword)
        for item in to_remove:
            items.remove(item)

    # ==================== 合并快捷操作 ====================

    def _accept_all_new(self):
        """将所有新增项设为使用导入"""
        self._set_merge_action_recursive(
            self.merge_items, MergeConflictLevel.NEW_IN_SOURCE, MergeAction.USE_SOURCE)
        self._refresh_merge_tree_actions()

    def _keep_all_current(self):
        """将所有项设为保留当前"""
        self._set_merge_action_recursive(
            self.merge_items, None, MergeAction.KEEP_TARGET)
        self._refresh_merge_tree_actions()

    def _set_merge_action_recursive(self, items: list,
                                     filter_level: Optional[MergeConflictLevel],
                                     action: MergeAction):
        """递归设置合并动作"""
        for item in items:
            if filter_level is None or item.conflict_level == filter_level:
                item.action = action
            if item.children:
                self._set_merge_action_recursive(item.children, filter_level, action)

    def _refresh_merge_tree_actions(self):
        """刷新合并树的操作列显示"""
        self.merge_tree.blockSignals(True)
        self._refresh_merge_items(self.merge_tree.invisibleRootItem())
        self.merge_tree.blockSignals(False)

    def _refresh_merge_items(self, parent):
        """递归刷新合并树项"""
        for i in range(parent.childCount()):
            tree_item = parent.child(i)
            merge_item = tree_item.data(0, Qt.ItemDataRole.UserRole)
            if merge_item:
                action_text = {a: txt for a, txt in _ACTION_OPTIONS}.get(
                    merge_item.action, "")
                tree_item.setText(3, action_text)
                self.action_delegate._actions[id(tree_item)] = merge_item.action
            self._refresh_merge_items(tree_item)

    # ==================== 执行合并 ====================

    def _do_merge(self):
        """执行合并"""
        if not self.merge_items:
            QMessageBox.warning(self, t("message.warning"),
                                t("diff_merge.hint_analyze_first"))
            return

        counts = SVDMerger.count_items(self.merge_items)
        use_source = counts.get('use_source', 0)

        if use_source == 0:
            QMessageBox.information(self, t("message.info"),
                                    t("diff_merge.no_merge_items"))
            return

        reply = QMessageBox.question(
            self, t("diff_merge.confirm_merge_title"),
            t("diff_merge.confirm_merge_msg", count=use_source),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            result_device, stats = self.merger.execute_merge(
                self.current_device, self.merge_items)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, t("message.error"), str(e))
            return
        finally:
            QApplication.restoreOverrideCursor()

        QMessageBox.information(self, t("diff_merge.merge_done"),
            t("diff_merge.merge_summary",
              periph=stats['peripherals_added'],
              reg=stats['registers_added'],
              field=stats['fields_added'],
              cluster=stats['clusters_added'],
              irq=stats['interrupts_added'],
              attr=stats['attrs_updated'],
              skipped=stats['skipped']))

        self.merge_completed.emit(result_device)
        self.accept()
