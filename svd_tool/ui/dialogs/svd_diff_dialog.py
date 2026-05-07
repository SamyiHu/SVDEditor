"""
SVD Diff 对话框
左右并排树形对比，一目了然
"""
import os
from typing import Optional, Dict, Tuple, List

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTreeWidget, QTreeWidgetItem, QLabel, QFileDialog, QCheckBox,
    QMessageBox, QComboBox, QFrame, QSizePolicy, QHeaderView, QSplitter
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor

from ...core.svd_parser import SVDParser
from ...core.svd_differ import SVDDiffer, DiffType, DiffItem
from ...core.data_model import DeviceInfo
from ...config.styles import get_style_scheme
from ...i18n.i18n import t


class SVDDiffDialog(QDialog):
    """SVD 差异比较对话框 — 左右并排树形对比"""

    def __init__(self, parent=None, current_device: DeviceInfo = None,
                 document_manager=None):
        super().__init__(parent)
        self.setWindowTitle(t("diff_merge.title"))
        self.setMinimumSize(900, 600)
        self.resize(1050, 700)
        self.current_device = current_device
        self.other_device: Optional[DeviceInfo] = None
        self.document_manager = document_manager
        self._open_docs: Dict[str, Tuple[str, DeviceInfo]] = {}
        self.differ = SVDDiffer()
        self._diffs: List[DiffItem] = []
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
        self.chk_description = QCheckBox("忽略描述")
        self.chk_description.stateChanged.connect(self._re_diff)
        file_bar.addWidget(self.chk_description)

        self.chk_reset_value = QCheckBox("忽略复位值")
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
                    display = doc.display_name or doc.device_info.name or "未命名"
                    self._open_docs[display] = (doc_id, doc.device_info)
                    self._open_doc_combo.addItem(display)
            self._open_doc_combo.blockSignals(False)

        # === 统计栏 ===
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(f"color: {_c.text_secondary}; font-size: 9pt; padding: 2px 4px;")
        layout.addWidget(self.stats_label)

        # === 左右并排树 ===
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.tree_a = QTreeWidget()
        self.tree_a.setHeaderLabels(["A — 当前"])
        self.tree_a.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree_a.setStyleSheet(f"""
            QTreeWidget {{ border: 1px solid {_c.border_light}; border-radius: 4px; }}
            QTreeWidget::item {{ padding: 2px 4px; height: 22px; }}
        """)

        self.tree_b = QTreeWidget()
        self.tree_b.setHeaderLabels(["B — 比较"])
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

        splitter.addWidget(self.tree_a)
        splitter.addWidget(self.tree_b)
        splitter.setSizes([500, 500])
        layout.addWidget(splitter, 1)

        # === 底部 ===
        btn_layout = QHBoxLayout()
        export_btn = QPushButton(t("diff_merge.export_report"))
        export_btn.clicked.connect(self._export_report)
        btn_layout.addWidget(export_btn)
        btn_layout.addStretch()
        close_btn = QPushButton(t("dialog.close", default="关闭"))
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        # 自动选中
        if self._open_doc_combo.count() > 0:
            self._open_doc_combo.setCurrentIndex(0)
            self._on_open_doc_selected(0)

    # ==================== 树同步 ====================

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
        self.file_label.setText(device.name or "比较文件")
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
            self.stats_label.setText("完全一致，没有差异")
        else:
            self.stats_label.setText(
                f"新增 {added}  ·  删除 {removed}  ·  修改 {modified}  ·  共 {total} 处差异"
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
                label = f"[外设] {name}"
            elif diff.category == 'register':
                label = f"[寄存器] {name}"
            elif diff.category == 'field':
                label = f"[位域] {name}"

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
                item_b.setText(0, label + "  [+新增]")
            elif diff.diff_type == DiffType.REMOVED:
                item_a.setBackground(0, bg_rem)
                item_a.setForeground(0, fg_rem)
                item_a.setText(0, label + "  [-删除]")
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

    # ==================== 导出 ====================

    def _export_report(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, t("diff_merge.export_report"), "svd_diff_report.txt",
            "文本文件 (*.txt);;Markdown (*.md)"
        )
        if not file_path:
            return
        try:
            if self._diffs:
                summary = self.differ.generate_summary(self._diffs)
            else:
                summary = "没有差异"
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(summary)
            QMessageBox.information(self, t("diff_merge.export_done"),
                                    t("diff_merge.export_saved", path=file_path))
        except Exception as e:
            QMessageBox.critical(self, t("message.error"), str(e))
