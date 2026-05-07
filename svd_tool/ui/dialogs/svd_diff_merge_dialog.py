"""
SVD 比较与合并统一对话框
整合了差异比较和导入合并功能，提供统一的操作界面
"""
import os
import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget,
    QTreeWidgetItem, QLabel, QFileDialog, QGroupBox,
    QSplitter, QMessageBox, QHeaderView, QComboBox,
    QWidget, QTextEdit, QStyledItemDelegate, QApplication,
    QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QFont

from ...core.svd_parser import SVDParser
from ...core.svd_merger import SVDMerger, MergeAction, MergeConflictLevel, MergeItem
from ...core.data_model import DeviceInfo
from ...config.styles import get_style_scheme
from ...i18n.i18n import t
from ..widgets.toggle_switch import ToggleSwitch

logger = logging.getLogger("SVDDiffMerge")

# 操作下拉框选项
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
            # 更新显示文本
            action_text = {a: txt for a, txt in _ACTION_OPTIONS}.get(action, "")
            tree_item.setText(3, action_text)

    def _get_tree_item(self, index):
        tree = self.parent()
        if tree and isinstance(tree, QTreeWidget):
            return tree.itemFromIndex(index)
        return None


class SVDDiffMergeDialog(QDialog):
    """SVD 比较与合并统一对话框"""

    merge_completed = pyqtSignal(DeviceInfo)

    def __init__(self, parent=None, current_device: DeviceInfo = None, document_manager=None):
        super().__init__(parent)
        self.setWindowTitle(t("diff_merge.title"))
        self.setMinimumSize(1050, 700)
        self.resize(1100, 750)
        self.current_device = current_device
        self.source_device: Optional[DeviceInfo] = None
        self.document_manager = document_manager
        self._open_docs = {}  # display_name -> (doc_id, DeviceInfo)
        self.merger = SVDMerger()
        self.merge_items: list = []
        self._setup_ui()

    def _setup_ui(self):
        _c = get_style_scheme().colors
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # === 文件选择栏 ===
        file_bar = QHBoxLayout()
        file_bar.setSpacing(12)

        # 当前文件标签
        curr_frame = QFrame()
        curr_frame.setStyleSheet(f"""
            QFrame {{
                background: {_c.accent_light};
                border: 1px solid {_c.selected_border};
                border-radius: 6px;
                padding: 6px 14px;
            }}
        """)
        curr_layout = QVBoxLayout(curr_frame)
        curr_layout.setContentsMargins(10, 6, 10, 6)
        curr_layout.setSpacing(2)
        curr_title = QLabel(t("diff_merge.current_file"))
        curr_title.setStyleSheet(f"color: {_c.text_secondary}; font-size: 9pt; border: none;")
        curr_layout.addWidget(curr_title)
        self.curr_name_label = QLabel("")
        self.curr_name_label.setStyleSheet(
            f"color: {_c.text_primary}; font-size: 11pt; font-weight: bold; border: none;"
        )
        if self.current_device:
            name = self.current_device.name or t("msg.unnamed")
            n_p = len(self.current_device.peripherals)
            n_r = sum(len(p.registers) for p in self.current_device.peripherals.values())
            self.curr_name_label.setText(f"{name} ({n_p} {t('label.total_peripherals')}, {n_r} {t('label.total_registers')})")
        curr_layout.addWidget(self.curr_name_label)
        file_bar.addWidget(curr_frame, 1)

        # VS
        vs_label = QLabel("VS")
        vs_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vs_label.setStyleSheet(f"color: {_c.gray}; font-size: 14pt; font-weight: bold;")
        vs_label.setFixedWidth(40)
        file_bar.addWidget(vs_label)

        # 导入文件区
        import_frame = QFrame()
        import_frame.setStyleSheet(f"""
            QFrame {{
                background: {_c.surface};
                border: 1px solid {_c.border};
                border-radius: 6px;
                padding: 6px 14px;
            }}
        """)
        import_layout = QVBoxLayout(import_frame)
        import_layout.setContentsMargins(10, 6, 10, 6)
        import_layout.setSpacing(2)
        import_title = QLabel(t("diff_merge.import_file"))
        import_title.setStyleSheet(f"color: {_c.text_secondary}; font-size: 9pt; border: none;")
        import_layout.addWidget(import_title)
        import_row = QHBoxLayout()
        import_row.setSpacing(6)
        self.file_label = QLabel(t("diff_merge.no_file_selected"))
        self.file_label.setStyleSheet(f"color: {_c.text_disabled}; font-size: 10pt; border: none;")
        import_row.addWidget(self.file_label, 1)

        # 已打开文档下拉框
        self._open_doc_combo = QComboBox()
        self._open_doc_combo.setFixedWidth(180)
        self._open_doc_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._open_doc_combo.currentIndexChanged.connect(self._on_open_doc_selected)
        import_row.addWidget(self._open_doc_combo)

        # 填充已打开文档列表（blockSignals 避免添加时触发 currentIndexChanged）
        if self.document_manager:
            self._open_doc_combo.blockSignals(True)
            active_id = self.document_manager.active_doc_id
            for doc_id, doc in self.document_manager.get_all_documents().items():
                if doc_id != active_id:
                    display = doc.display_name or doc.device_info.name or "未命名"
                    self._open_docs[display] = (doc_id, doc.device_info)
                    n_p = len(doc.device_info.peripherals)
                    n_r = sum(len(p.registers) for p in doc.device_info.peripherals.values())
                    self._open_doc_combo.addItem(f"{display} ({n_p} 外设)")
            self._open_doc_combo.blockSignals(False)

        browse_btn = QPushButton(t("diff_merge.browse"))
        browse_btn.setFixedWidth(70)
        browse_btn.clicked.connect(self._browse_file)
        import_row.addWidget(browse_btn)
        self.analyze_btn = QPushButton(t("diff_merge.analyze"))
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {_c.accent}; color: white;
                padding: 5px 16px; border: none; border-radius: 4px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {_c.accent_hover}; }}
            QPushButton:disabled {{ background-color: {_c.border}; color: {_c.text_disabled}; }}
        """)
        self.analyze_btn.clicked.connect(self._do_analyze)
        import_row.addWidget(self.analyze_btn)
        import_layout.addLayout(import_row)
        file_bar.addWidget(import_frame, 1)

        layout.addLayout(file_bar)

        # === 选项栏 ===
        opt_bar = QHBoxLayout()
        opt_bar.setSpacing(16)

        self.chk_ignore_desc = ToggleSwitch(t("diff_merge.ignore_desc"))
        opt_bar.addWidget(self.chk_ignore_desc)

        self.chk_ignore_display = ToggleSwitch(t("diff_merge.ignore_display"))
        opt_bar.addWidget(self.chk_ignore_display)

        self.chk_ignore_reset = ToggleSwitch(t("diff_merge.ignore_reset"))
        opt_bar.addWidget(self.chk_ignore_reset)

        opt_bar.addStretch()

        accept_new_btn = QPushButton(t("diff_merge.accept_all_new"))
        accept_new_btn.setFixedHeight(28)
        accept_new_btn.clicked.connect(self._select_all_new)
        opt_bar.addWidget(accept_new_btn)

        keep_all_btn = QPushButton(t("diff_merge.keep_all_current"))
        keep_all_btn.setFixedHeight(28)
        keep_all_btn.clicked.connect(self._select_all_keep)
        opt_bar.addWidget(keep_all_btn)

        layout.addLayout(opt_bar)

        # === 统计栏 ===
        self.stats_label = QLabel(t("diff_merge.hint_select_file"))
        self.stats_label.setStyleSheet(f"""
            QLabel {{
                padding: 6px 12px;
                background: {_c.light_gray};
                border-radius: 4px;
                font-size: 10pt;
            }}
        """)
        layout.addWidget(self.stats_label)

        # === 主内容区：树 + 详情 ===
        splitter = QSplitter(Qt.Orientation.Vertical)

        # 差异/合并树
        self.merge_tree = QTreeWidget()
        self.merge_tree.setHeaderLabels([
            t("diff_merge.col_item"),
            t("diff_merge.col_status"),
            t("diff_merge.col_current"),
            t("diff_merge.col_action"),
            t("diff_merge.col_import"),
        ])
        header = self.merge_tree.header()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.merge_tree.setAlternatingRowColors(True)
        self.merge_tree.setSelectionBehavior(QTreeWidget.SelectionBehavior.SelectRows)
        self.merge_tree.itemClicked.connect(self._on_item_clicked)

        # 操作列下拉委托
        self.action_delegate = _ActionDelegate(self.merge_tree)
        self.merge_tree.setItemDelegateForColumn(3, self.action_delegate)

        splitter.addWidget(self.merge_tree)

        # 详情面板
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setFont(QFont("Consolas", 9))
        self.detail_text.setMaximumHeight(160)
        self.detail_text.setPlaceholderText(t("diff_merge.detail_placeholder"))
        splitter.addWidget(self.detail_text)

        splitter.setSizes([500, 160])
        layout.addWidget(splitter, 1)

        # === 底部按钮 ===
        btn_layout = QHBoxLayout()

        export_btn = QPushButton(t("diff_merge.export_report"))
        export_btn.clicked.connect(self._export_report)
        btn_layout.addWidget(export_btn)

        btn_layout.addStretch()

        self.merge_btn = QPushButton(t("diff_merge.execute_merge"))
        self.merge_btn.setEnabled(False)
        self.merge_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {_c.accent}; color: white;
                padding: 8px 28px; border: none; border-radius: 6px;
                font-weight: bold; font-size: 10pt;
            }}
            QPushButton:hover {{ background-color: {_c.accent_hover}; }}
            QPushButton:pressed {{ background-color: {_c.accent_pressed}; }}
            QPushButton:disabled {{ background-color: {_c.border}; color: {_c.text_disabled}; }}
        """)
        self.merge_btn.clicked.connect(self._do_merge)
        btn_layout.addWidget(self.merge_btn)

        close_btn = QPushButton(t("button.cancel"))
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {_c.surface}; color: {_c.text_primary};
                padding: 8px 24px; border: 1px solid {_c.border}; border-radius: 6px;
                font-size: 10pt;
            }}
            QPushButton:hover {{ background-color: {_c.hover}; }}
        """)
        close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

        # 所有 UI 就绪后自动选中第一个已打开文档
        if self._open_doc_combo.count() > 0:
            self._open_doc_combo.setCurrentIndex(0)
            self._on_open_doc_selected(0)

    # ==================== 文件选择 ====================

    def _on_open_doc_selected(self, index):
        """从下拉框选择已打开的文档"""
        if index < 0:
            return
        display_name = self._open_doc_combo.itemText(index).split(" (")[0]
        entry = self._open_docs.get(display_name)
        if not entry:
            return
        _, device = entry
        self.source_device = device
        n_p = len(device.peripherals)
        n_r = sum(len(p.registers) for p in device.peripherals.values())
        _c = get_style_scheme().colors
        self.file_label.setText(f"{device.name or display_name} ({n_p} {t('label.total_peripherals')}, {n_r} {t('label.total_registers')})")
        self.file_label.setStyleSheet(f"color: {_c.text_primary}; font-size: 10pt; border: none;")
        self.analyze_btn.setEnabled(self.current_device is not None)

    def _browse_file(self):
        """浏览选择导入文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, t("diff_merge.select_file"), "",
            t("msg.svd_file_filter")
        )
        if not file_path:
            return

        try:
            parser = SVDParser()
            self.source_device = parser.parse_file(file_path)
            self._open_doc_combo.setCurrentIndex(-1)  # 清空下拉框选择

            name = self.source_device.name or os.path.basename(file_path)
            n_p = len(self.source_device.peripherals)
            n_r = sum(len(p.registers) for p in self.source_device.peripherals.values())
            self.file_label.setText(f"{name} ({n_p} {t('label.total_peripherals')}, {n_r} {t('label.total_registers')})")
            self.file_label.setStyleSheet(f"color: {get_style_scheme().colors.text_primary}; font-size: 10pt; border: none;")

            self.analyze_btn.setEnabled(self.current_device is not None)

            if parser.warnings:
                QMessageBox.warning(self, t("message.warning"), "\n".join(parser.warnings[:5]))

        except Exception as e:
            QMessageBox.critical(self, t("message.error"), t("msg.cannot_open_file", error=str(e)))

    # ==================== 分析 ====================

    def _do_analyze(self):
        """执行差异分析"""
        if not self.current_device or not self.source_device:
            QMessageBox.warning(self, t("message.warning"), t("diff_merge.hint_select_file"))
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.merge_items = self.merger.analyze(self.current_device, self.source_device)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, t("message.error"), str(e))
            return
        finally:
            QApplication.restoreOverrideCursor()

        # 过滤
        if self.chk_ignore_desc.isChecked():
            self._filter_items(self.merge_items, "Description")

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

        # 填充树
        self.merge_tree.blockSignals(True)
        self.merge_tree.clear()
        self._populate_tree(self.merge_tree.invisibleRootItem(), self.merge_items)
        self.merge_tree.blockSignals(False)

        # 展开第一层
        for i in range(self.merge_tree.topLevelItemCount()):
            self.merge_tree.topLevelItem(i).setExpanded(True)

        self.merge_btn.setEnabled(True)

    def _filter_items(self, items: list, keyword: str):
        """过滤包含关键字的合并项"""
        to_remove = []
        for item in items:
            if keyword in item.path and item.level.endswith('_attr'):
                to_remove.append(item)
            elif item.children:
                self._filter_items(item.children, keyword)
        for item in to_remove:
            items.remove(item)

    def _populate_tree(self, parent, items: list):
        """递归填充合并树"""
        _c = get_style_scheme().colors

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
            tree_item.setText(2, self._format_value(item.target_obj))

            # 操作
            action_text = {a: txt for a, txt in _ACTION_OPTIONS}.get(item.action, "")
            tree_item.setText(3, action_text)

            # 导入值
            tree_item.setText(4, self._format_value(item.source_obj))

            # 数据
            tree_item.setData(0, Qt.ItemDataRole.UserRole, item)
            tree_item.setToolTip(0, item.path)

            # 颜色
            self._set_item_colors(tree_item, item.conflict_level)

            # 递归
            if item.children:
                self._populate_tree(tree_item, item.children)

            parent.addChild(tree_item)

    def _format_value(self, obj) -> str:
        """格式化显示值"""
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

    def _set_item_colors(self, tree_item: QTreeWidgetItem, conflict_level: MergeConflictLevel):
        """设置行颜色"""
        _c = get_style_scheme().colors
        if conflict_level == MergeConflictLevel.NEW_IN_SOURCE:
            bg = QColor(220, 255, 220)
            fg = QColor(0, 128, 0)
        elif conflict_level == MergeConflictLevel.ONLY_IN_TARGET:
            bg = QColor(240, 240, 240)
            fg = QColor(128, 128, 128)
        elif conflict_level == MergeConflictLevel.ATTR_MODIFIED:
            bg = QColor(255, 255, 220)
            fg = QColor(160, 120, 0)
        elif conflict_level == MergeConflictLevel.STRUCTURE_CHANGED:
            bg = QColor(255, 220, 200)
            fg = QColor(200, 80, 0)
        else:
            return

        for col in range(5):
            tree_item.setBackground(col, QBrush(bg))
            tree_item.setForeground(col, QBrush(fg))

    # ==================== 交互 ====================

    def _on_item_clicked(self, tree_item: QTreeWidgetItem, column: int):
        """点击树项显示详情"""
        merge_item = tree_item.data(0, Qt.ItemDataRole.UserRole)
        if not merge_item:
            return

        lines = []
        lines.append(f"{'=' * 50}")
        lines.append(f"  {merge_item.path}")
        lines.append(f"  {t('diff_merge.col_status')}: {tree_item.text(1)}")
        lines.append(f"{'=' * 50}")
        lines.append("")

        if merge_item.target_obj is not None:
            lines.append(f"[{t('diff_merge.current_file')}]")
            lines.extend(self._detail_object(merge_item.target_obj))

        if merge_item.source_obj is not None:
            lines.append(f"\n[{t('diff_merge.import_file')}]")
            lines.extend(self._detail_object(merge_item.source_obj))

        self.detail_text.setPlainText("\n".join(lines))

    def _detail_object(self, obj) -> list:
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

    # ==================== 快捷操作 ====================

    def _select_all_new(self):
        """将所有新增项设为使用导入"""
        self._set_action_recursive(self.merge_items, MergeConflictLevel.NEW_IN_SOURCE, MergeAction.USE_SOURCE)
        self._refresh_tree_actions()

    def _select_all_keep(self):
        """将所有项设为保留当前"""
        self._set_action_recursive(self.merge_items, None, MergeAction.KEEP_TARGET)
        self._refresh_tree_actions()

    def _set_action_recursive(self, items: list, filter_level: Optional[MergeConflictLevel], action: MergeAction):
        """递归设置合并动作"""
        for item in items:
            if filter_level is None or item.conflict_level == filter_level:
                item.action = action
            if item.children:
                self._set_action_recursive(item.children, filter_level, action)

    def _refresh_tree_actions(self):
        """刷新树的操作列显示"""
        self.merge_tree.blockSignals(True)
        self._refresh_tree_items(self.merge_tree.invisibleRootItem())
        self.merge_tree.blockSignals(False)

    def _refresh_tree_items(self, parent):
        """递归刷新树项"""
        for i in range(parent.childCount()):
            tree_item = parent.child(i)
            merge_item = tree_item.data(0, Qt.ItemDataRole.UserRole)
            if merge_item:
                action_text = {a: txt for a, txt in _ACTION_OPTIONS}.get(merge_item.action, "")
                tree_item.setText(3, action_text)
                # 同步 delegate 缓存
                self.action_delegate._actions[id(tree_item)] = merge_item.action
            self._refresh_tree_items(tree_item)

    # ==================== 执行合并 ====================

    def _do_merge(self):
        """执行合并"""
        if not self.merge_items:
            QMessageBox.warning(self, t("message.warning"), t("diff_merge.hint_analyze_first"))
            return

        counts = SVDMerger.count_items(self.merge_items)
        use_source = counts.get('use_source', 0)

        if use_source == 0:
            QMessageBox.information(
                self, t("message.info"),
                t("diff_merge.no_merge_items")
            )
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
            result_device, stats = self.merger.execute_merge(self.current_device, self.merge_items)
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

    # ==================== 导出报告 ====================

    def _export_report(self):
        """导出差异报告"""
        if not self.merge_items:
            QMessageBox.information(self, t("message.info"), t("diff_merge.hint_analyze_first"))
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, t("diff_merge.export_report"), "svd_diff_report.txt",
            "Text (*.txt);;Markdown (*.md)"
        )
        if not file_path:
            return

        try:
            summary = self.merger.generate_summary(self.merge_items, {})
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(summary)
            QMessageBox.information(self, t("diff_merge.export_done"),
                                    t("diff_merge.export_saved", path=file_path))
        except Exception as e:
            QMessageBox.critical(self, t("message.error"), str(e))
