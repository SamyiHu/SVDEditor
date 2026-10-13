"""可人工纠错、可审计的 TRM 解析结果审阅控件。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QPlainTextEdit, QFileDialog, QMessageBox,
    QLineEdit, QAbstractItemView, QHeaderView, QSplitter, QGroupBox, QSizePolicy,
    QComboBox, QSpinBox, QCheckBox, QFrame,
)

from ...i18n.i18n import t
from ...config.styles import get_style_scheme


_STATUS_LABELS = {
    "machine_extracted": "机器提取",
    "human_confirmed": "人工确认",
    "human_rejected": "人工拒绝",
    "ignored": "已忽略",
}


def _status_label(value: str) -> str:
    return _STATUS_LABELS.get(value, value or "待核实")


class CorrectionReviewWidget(QWidget):
    """字段级解析结果编辑器。"""

    columns = [
        "层级", "外设", "寄存器", "位域", "属性",
        "解析值", "人工值", "最终值", "人工状态",
        "来源权威度", "解析完整度", "多源一致度", "匹配理由",
        "对象 ID", "来源定位", "备注",
    ]

    def __init__(self, mgr, parent=None):
        super().__init__(parent)
        self.mgr = mgr
        self.setMinimumSize(960, 560)
        self._records = []
        self._filtered_records = []
        self._page_records = []
        self._loading = False
        self._page_size = 200
        self._current_page = 1
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        try:
            c = get_style_scheme().colors
        except Exception:
            class _C:
                accent = "#4A90D9"; accent_hover = "#3A7BC8"
                success = "#52C41A"; error = "#FF4D4F"
                surface = "#FFFFFF"; border = "#D9D9D9"
                text_primary = "#1A1A1A"; text_secondary = "#8C8C8C"
                light_gray = "#F7F8FA"; selected = "#E8F0FE"
            c = _C()
        self._colors = c
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(8)

        summary_card = QFrame()
        summary_card.setObjectName("ReviewSummaryCard")
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(12, 8, 12, 8)
        summary_layout.setSpacing(2)
        top_row = QHBoxLayout()
        badge = QLabel("审核")
        badge.setObjectName("ReviewBadge")
        summary = QLabel("")
        self.summary_label = summary
        self.summary_label.setWordWrap(True)
        top_row.addWidget(badge)
        top_row.addWidget(summary, 1)
        summary_layout.addLayout(top_row)
        self.header_summary_label = QLabel("")
        self.header_summary_label.setObjectName("SourceMeta")
        self.header_summary_label.setWordWrap(True)
        self.header_summary_label.hide()
        summary_layout.addWidget(self.header_summary_label)
        root.addWidget(summary_card)

        filter_card = QFrame()
        filter_card.setObjectName("ReviewFilterCard")
        filter_row = QHBoxLayout(filter_card)
        filter_row.setContentsMargins(10, 8, 10, 8)
        filter_row.setSpacing(8)
        filter_label = QLabel(t("datasource.review_filter", default="筛选"))
        filter_label.setObjectName("FieldLabel")
        filter_row.addWidget(filter_label)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText(
            t("datasource.review_filter_hint", default="外设 / 寄存器 / 位域 / 属性 / 原文"))
        self.filter_edit.textChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self.filter_edit, 1)
        self.status_filter = QComboBox()
        self.status_filter.addItem("差异优先（待核实）", "pending")
        self.status_filter.addItem("人工值有改动", "changed")
        self.status_filter.addItem("高风险字段", "high_risk")
        self.status_filter.addItem("多源冲突", "conflict")
        self.status_filter.addItem("人工确认", "human_confirmed")
        self.status_filter.addItem("人工拒绝", "human_rejected")
        self.status_filter.addItem("已忽略", "ignored")
        self.status_filter.addItem("全部", "all")
        self.status_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self.status_filter)
        self.show_semantics_chk = QCheckBox("审核维度")
        self.show_semantics_chk.toggled.connect(self._toggle_semantic_columns)
        filter_row.addWidget(self.show_semantics_chk)
        self.prev_page_btn = QPushButton("‹")
        self.prev_page_btn.setObjectName("PageNavButton")
        self.prev_page_btn.setFixedSize(24, 24)
        self.prev_page_btn.clicked.connect(self._go_previous_page)
        filter_row.addWidget(self.prev_page_btn)
        self.page_value_label = QLabel("1 / 1")
        self.page_value_label.setObjectName("PageValue")
        self.page_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_value_label.setFixedWidth(52)
        self.page_value_label.setMinimumHeight(24)
        self.page_value_label.setMaximumHeight(24)
        filter_row.addWidget(self.page_value_label)
        self.next_page_btn = QPushButton("›")
        self.next_page_btn.setObjectName("PageNavButton")
        self.next_page_btn.setFixedSize(24, 24)
        self.next_page_btn.clicked.connect(self._go_next_page)
        filter_row.addWidget(self.next_page_btn)
        self.page_label = QLabel("")
        self.page_label.setObjectName("PageLabel")
        filter_row.addWidget(self.page_label)
        root.addWidget(filter_card)

        toolbar = QFrame()
        toolbar.setObjectName("ReviewToolbar")
        toolbar_row = QHBoxLayout(toolbar)
        toolbar_row.setContentsMargins(10, 8, 10, 8)
        toolbar_row.setSpacing(8)
        self.accept_btn = QPushButton(t("datasource.accept_selected", default="接受选中"))
        self.reject_btn = QPushButton(t("datasource.reject_selected", default="拒绝选中"))
        self.batch_accept_btn = QPushButton(t("datasource.batch_accept", default="批量接受"))
        self.batch_ignore_btn = QPushButton(t("datasource.batch_ignore", default="批量忽略"))
        self.undo_btn = QPushButton(t("datasource.undo_review", default="撤销"))
        self.locate_btn = QPushButton(t("datasource.locate_source", default="定位 TRM 原文"))
        self.export_svd_btn = QPushButton(t("datasource.export_final_svd", default="导出最终 SVD"))
        self.export_report_btn = QPushButton(t("datasource.export_correction_report", default="导出纠错报告"))
        self.export_manifest_btn = QPushButton(t("datasource.export_manifest", default="Manifest"))
        for btn in (
            self.undo_btn, self.locate_btn, self.batch_accept_btn,
            self.batch_ignore_btn, self.export_svd_btn, self.export_report_btn,
            self.export_manifest_btn,
        ):
            btn.setObjectName("GhostButton")
            toolbar_row.addWidget(btn)
        self.accept_btn.setObjectName("PrimaryButton")
        self.reject_btn.setObjectName("DangerButton")
        toolbar_row.addWidget(self.accept_btn)
        toolbar_row.addWidget(self.reject_btn)
        toolbar_row.addStretch(1)
        self.accept_btn.clicked.connect(lambda: self._decide("human_confirmed"))
        self.reject_btn.clicked.connect(lambda: self._decide("human_rejected"))
        self.batch_accept_btn.clicked.connect(lambda: self._decide("human_confirmed", batch=True))
        self.batch_ignore_btn.clicked.connect(lambda: self._decide("ignored", batch=True))
        self.undo_btn.clicked.connect(self._undo)
        self.locate_btn.clicked.connect(self._locate)
        self.export_svd_btn.clicked.connect(self._export_svd)
        self.export_report_btn.clicked.connect(self._export_report)
        self.export_manifest_btn.clicked.connect(self._export_manifest)
        root.addWidget(toolbar)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        self.table = QTableWidget(0, len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)
        self.table.setWordWrap(False)
        self.table.setMinimumHeight(220)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.setObjectName("ReviewTable")
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(12, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(12, 130)
        header.setSectionResizeMode(13, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(13, 150)
        header.setSectionResizeMode(14, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(15, QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.itemSelectionChanged.connect(self._show_selected_source)
        splitter.addWidget(self.table)

        source_box = QGroupBox(t("datasource.source_trace", default="TRM 原文与定位"))
        source_box.setObjectName("SourceCard")
        source_layout = QVBoxLayout(source_box)
        self.source_label = QLabel(t("datasource.select_row", default="选择任意一行查看原文片段"))
        self.source_label.setObjectName("SourceMeta")
        self.source_label.setWordWrap(True)
        self.source_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.source_text = QPlainTextEdit()
        self.source_text.setReadOnly(True)
        self.source_text.setMinimumHeight(120)
        source_layout.addWidget(self.source_label)
        source_layout.addWidget(self.source_text)
        splitter.addWidget(source_box)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([360, 150])
        root.addWidget(splitter, 1)
        self._toggle_semantic_columns(False)
        self.setStyleSheet(f"""
            QFrame#ReviewSummaryCard, QFrame#ReviewFilterCard, QFrame#ReviewToolbar {{
                background: {c.surface};
                border: 1px solid {c.border_light};
                border-radius: 8px;
            }}
            QLabel#ReviewBadge {{
                background: {c.accent_light};
                color: {c.accent};
                border-radius: 10px;
                padding: 4px 10px;
                font-weight: 700;
            }}
            QLabel#FieldLabel {{ color: {c.text_secondary}; }}
            QLabel#PageLabel {{
                color: {c.text_secondary};
                min-width: 86px;
            }}
            QPushButton {{
                border: 1px solid {c.border};
                border-radius: 6px;
                padding: 6px 12px;
                background: {c.surface};
                color: {c.text_primary};
            }}
            QPushButton:hover {{ background: {c.light_gray}; }}
            QPushButton#PrimaryButton {{
                background: {c.accent};
                border-color: {c.accent};
                color: white;
                font-weight: 600;
            }}
            QPushButton#PrimaryButton:hover {{ background: {c.accent_hover}; }}
            QPushButton#DangerButton {{
                border-color: {c.error};
                color: {c.error};
                font-weight: 600;
            }}
            QPushButton#DangerButton:hover {{ background: #FFF1F0; }}
            QPushButton#PageNavButton {{
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
                padding: 0;
                color: {c.text_secondary};
            }}
            QLabel#PageValue {{
                background: {c.light_gray};
                border: 1px solid {c.border_light};
                border-radius: 6px;
                color: {c.text_primary};
                font-size: 9pt;
                font-weight: 600;
            }}
            QTableWidget#ReviewTable {{
                border: 1px solid {c.border_light};
                border-radius: 8px;
                background: {c.surface};
                alternate-background-color: {c.light_gray};
                gridline-color: transparent;
                selection-background-color: {c.selected};
                selection-color: {c.text_primary};
            }}
            QHeaderView::section {{
                background: {c.light_gray};
                color: {c.text_secondary};
                border: none;
                border-bottom: 1px solid {c.border_light};
                padding: 7px 8px;
                font-weight: 600;
            }}
            QTableWidget::item {{ padding: 4px; border: none; }}
            QGroupBox#SourceCard {{
                background: {c.surface};
                border: 1px solid {c.border_light};
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 8px;
                font-weight: 600;
            }}
            QLabel#SourceMeta {{ color: {c.text_secondary}; }}
        """)

    def _styled_status(self, value: str):
        colors = {
            "machine_extracted": getattr(self._colors, "text_secondary", "#8C8C8C"),
            "human_confirmed": getattr(self._colors, "success", "#52C41A"),
            "human_rejected": getattr(self._colors, "error", "#FF4D4F"),
            "ignored": getattr(self._colors, "text_secondary", "#8C8C8C"),
        }
        return QColor(colors.get(value, "#8C8C8C"))

    def _toggle_semantic_columns(self, visible: bool):
        for col in range(9, 14):
            self.table.setColumnHidden(col, not visible)

    def refresh(self):
        self._loading = True
        self._records = list(getattr(self.mgr, "correction_records", []) or [])
        self._loading = False
        self._update_summary()
        self._apply_filter(reset_page=True)

    def _on_filter_changed(self, *_args):
        self._apply_filter(reset_page=True)

    def _go_previous_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._populate_current_page()

    def _go_next_page(self):
        total_pages = max(1, (len(self._filtered_records) + self._page_size - 1) // self._page_size)
        if self._current_page < total_pages:
            self._current_page += 1
            self._populate_current_page()

    def set_import_mode(self, mode: str):
        """单源隐藏多源冲突筛选项；多源保持冲突审计入口。"""
        self._import_mode = mode or "single"
        conflict_index = -1
        for index in range(self.status_filter.count()):
            if self.status_filter.itemData(index) == "conflict":
                conflict_index = index
                break
        if conflict_index >= 0:
            self.status_filter.setItemData(conflict_index, not self._import_mode == "single",
                                           Qt.ItemDataRole.UserRole - 1)
            model = self.status_filter.model()
            model.setItemData(
                model.index(conflict_index, 0),
                {int(Qt.ItemDataRole.UserRole - 1): not self._import_mode == "single"},
            )
        if self._import_mode == "single":
            self.table.setColumnHidden(11, True)
            if self.status_filter.currentData() == "conflict":
                self.status_filter.setCurrentIndex(0)
        elif self.show_semantics_chk.isChecked():
            self.table.setColumnHidden(11, False)

    def _populate_current_page(self, *_args):
        self._loading = True
        total = len(self._filtered_records)
        pages = max(1, (total + self._page_size - 1) // self._page_size)
        page = min(max(1, self._current_page), pages)
        self._current_page = page
        start = (page - 1) * self._page_size
        self._page_records = self._filtered_records[start:start + self._page_size]
        self.table.setRowCount(len(self._page_records))
        for row, record in enumerate(self._page_records):
            values = [
                record.level, record.peripheral, record.register, record.field,
                record.property_name, record.extracted_value, record.manual_value,
                record.resolved_final_value(), _status_label(record.status),
                record.source_authority, record.parse_completeness,
                record.multi_source_agreement, record.match_reason,
                record.object_id, self._source_location(record), record.note,
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, record.key)
                if col in (6, 15):
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col == 8:
                    item.setForeground(self._styled_status(record.status))
                elif col in (0, 4):
                    item.setForeground(QColor(str(getattr(self._colors, "text_secondary", "#8C8C8C"))))
                self.table.setItem(row, col, item)
        first = start + 1 if self._page_records else 0
        last = start + len(self._page_records)
        self.page_value_label.setText(f"{page} / {pages}")
        self.page_label.setText(f"{first}-{last} / {total}")
        self.prev_page_btn.setEnabled(page > 1)
        self.next_page_btn.setEnabled(page < pages)
        self._loading = False

    def _update_summary(self):
        if hasattr(self.mgr, "correction_store") and self.mgr.correction_store:
            summary = self.mgr.correction_store.summary()
        else:
            summary = {}
        manual = summary.get("manual_confirmation", {})
        total = summary.get("total", len(self._records))
        changed = sum(1 for record in self._records if record.manual_value)
        self.summary_label.setText(
            f"<b>待核实 {manual.get('pending', 0)}</b>"
            f"<span style='color:#8C8C8C'> / {total}</span>　·　"
            f"已改动 {changed}　·　确认 {manual.get('confirmed', 0)}　·　"
            f"拒绝 {manual.get('rejected', 0)}　·　忽略 {manual.get('ignored', 0)}"
            "　·　<span style='color:#8C8C8C'>来源权威度 / 解析完整度 / 多源一致度 / 人工状态相互独立，均不代表准确率</span>"
        )
        self._update_header_summary()

    def _update_header_summary(self):
        """H 主控模式的覆盖率摘要区（未启用 H 链路时隐藏）。"""
        coverage = {}
        try:
            coverage = dict(self.mgr.header_coverage or {})
        except AttributeError:
            coverage = {}
        if not coverage:
            self.header_summary_label.hide()
            return
        trm_only = len(coverage.get("trm_only_items", []) or [])
        text = (
            f"H 主控模式：H 外设 {coverage.get('header_peripherals', 0)}"
            f" · TRM 外设 {coverage.get('trm_peripherals', 0)}"
            f"（匹配 {coverage.get('trm_peripherals_matched', 0)}）"
            f" · TRM 补充率 {coverage.get('trm_supplement_percent', 0)}%"
            f" · 未解析 H 条目 {coverage.get('unresolved_header_items', 0)}"
        )
        if trm_only:
            text += f" · <span style='color:#D46B08'>TRM 独有外设 {trm_only}（待人工处置）</span>"
        self.header_summary_label.setText(text)
        self.header_summary_label.show()

    def _apply_filter(self, reset_page: bool = True):
        needle = self.filter_edit.text().strip().lower()
        mode = self.status_filter.currentData() if hasattr(self, "status_filter") else "all"
        high_risk = {"name", "base_address", "address_offset", "reset_value", "access"}
        filtered = []
        for record in self._records:
            haystack = " ".join(str(x) for x in (
                record.level, record.peripheral, record.register, record.field,
                record.property_name, record.extracted_value, record.manual_value,
                record.status, record.source_authority, record.parse_completeness,
                record.multi_source_agreement, record.match_reason, record.object_id,
                (record.source_ref or {}).get("section", ""),
                (record.source_ref or {}).get("raw_text", ""),
            )).lower()
            visible = not needle or needle in haystack
            if visible and mode == "pending":
                visible = record.status == "machine_extracted"
            elif visible and mode == "changed":
                visible = bool(record.manual_value)
            elif visible and mode == "high_risk":
                visible = record.property_name in high_risk
            elif visible and mode == "conflict":
                visible = record.multi_source_agreement == "conflict"
            elif visible and mode not in ("all", None):
                visible = record.status == mode
            if visible:
                filtered.append(record)
        self._filtered_records = filtered
        if reset_page:
            self._current_page = 1
        self._populate_current_page()

    def _selected_records(self, batch: bool = False):
        rows = sorted({index.row() for index in self.table.selectedIndexes()})
        if batch and not rows:
            return list(self._filtered_records)
        return [self._page_records[row] for row in rows if 0 <= row < len(self._page_records)]

    def _manual_values(self, records) -> dict:
        values = {}
        key_to_row = {record.key: row for row, record in enumerate(self._page_records)}
        for record in records:
            row = key_to_row.get(record.key)
            item = self.table.item(row, 6) if row is not None else None
            values[record.key] = item.text() if item is not None else record.manual_value
        return values

    def _decide(self, status: str, batch: bool = False):
        records = self._selected_records(batch)
        if not records:
            QMessageBox.information(self, t("message.info"),
                t("datasource.no_selection", default="未选择任何记录"))
            return
        values = self._manual_values(records)
        keys = [record.key for record in records]
        if status == "human_confirmed":
            count = self.mgr.accept_corrections(keys, values)
        elif status == "human_rejected":
            count = self.mgr.reject_corrections(keys)
        else:
            count = self.mgr.ignore_corrections(keys)
        self.refresh()
        QMessageBox.information(
            self, t("message.info"),
            t("datasource.review_done", n=count, default=f"已处理 {count} 条记录"))

    def _undo(self):
        count = self.mgr.undo_last_correction()
        self.refresh()
        QMessageBox.information(
            self, t("message.info"),
            t("datasource.review_undo_done", n=count, default=f"已撤销 {count} 个字段修改"))

    def _on_item_changed(self, item: QTableWidgetItem):
        if self._loading or item.column() not in (6, 15):
            return
        row = item.row()
        if not (0 <= row < len(self._page_records)):
            return
        record = self._page_records[row]
        manual_item = self.table.item(row, 6)
        note_item = self.table.item(row, 15)
        self.mgr.update_correction_value(
            record.key,
            manual_item.text() if manual_item else record.manual_value,
            note_item.text() if note_item else record.note,
        )
        final_item = self.table.item(row, 7)
        if final_item:
            self._loading = True
            final_item.setText(record.resolved_final_value())
            self._loading = False
        self._update_summary()

    def _show_selected_source(self):
        records = self._selected_records()
        if not records:
            return
        record = records[-1]
        ref = record.source_ref or {}
        self.source_label.setText(
            f"{ref.get('source_file', record.source_file)} | "
            f"章节：{ref.get('section', '-')} | 表格：{ref.get('table_index', '-')} | "
            f"行：{ref.get('row_number', '-')} | "
            f"来源权威度：{record.source_authority or '-'} | "
            f"解析完整度：{record.parse_completeness or '-'} | "
            f"多源一致度：{record.multi_source_agreement} | "
            f"匹配：{record.match_reason}({record.match_score:.2f}) | "
            f"对象：{record.object_id or '-'}"
        )
        self.source_text.setPlainText(ref.get("raw_text", "") or t(
            "datasource.no_raw_text", default="当前解析器未提供原始文本，请使用来源定位按钮打开 TRM。"))

    def _locate(self):
        records = self._selected_records()
        if not records:
            QMessageBox.information(self, t("message.info"),
                t("datasource.no_selection", default="未选择任何记录"))
            return
        locate_source_reference(self, records[-1])

    def _export_svd(self):
        path, _ = QFileDialog.getSaveFileName(
            self, t("datasource.export_final_svd", default="导出最终 SVD"),
            "final_reviewed.svd", "CMSIS-SVD (*.svd);;XML (*.xml)")
        if not path:
            return
        try:
            out = self.mgr.export_final_svd(path)
            QMessageBox.information(self, t("message.info"),
                t("datasource.saved", path=out, default=f"已保存：{out}"))
        except Exception as exc:
            QMessageBox.critical(self, t("message.error"), str(exc))

    def _export_report(self):
        path, selected = QFileDialog.getSaveFileName(
            self, t("datasource.export_correction_report", default="导出纠错报告"),
            "trm_correction_report.md", "Markdown (*.md);;JSON (*.json)")
        if not path:
            return
        try:
            out = self.mgr.export_correction_report(path, markdown=not path.lower().endswith(".json"))
            QMessageBox.information(self, t("message.info"),
                t("datasource.saved", path=out, default=f"已保存：{out}"))
        except Exception as exc:
            QMessageBox.critical(self, t("message.error"), str(exc))

    def _export_manifest(self):
        path, _ = QFileDialog.getSaveFileName(
            self, t("datasource.export_manifest", default="导出交付 Manifest"),
            "trm_review_manifest.json", "JSON (*.json)")
        if not path:
            return
        try:
            out = self.mgr.export_manifest(path)
            QMessageBox.information(self, t("message.info"),
                t("datasource.saved", path=out, default=f"已保存：{out}"))
        except Exception as exc:
            QMessageBox.critical(self, t("message.error"), str(exc))

    @staticmethod
    def _source_location(record) -> str:
        ref = record.source_ref or {}
        if not ref:
            return "-"
        return f"T{ref.get('table_index', '-')}/R{ref.get('row_number', '-')}"


def locate_source_reference(parent: QWidget, record) -> None:
    ref = record.source_ref or {}
    source_file = ref.get("source_file", record.source_file)
    if not source_file or not Path(source_file).exists():
        QMessageBox.warning(parent, t("message.warning"),
            t("datasource.source_missing", default="找不到来源文件"))
        return
    raw = ref.get("raw_text", "")
    needle = raw.split("|", 1)[0].strip() if raw else record.extracted_value
    try:
        if source_file.lower().endswith((".doc", ".docx")) and needle:
            try:
                import win32com.client
                word = win32com.client.DispatchEx("Word.Application")
                word.Visible = True
                doc = word.Documents.Open(str(Path(source_file).resolve()))
                find = word.Selection.Find
                find.ClearFormatting()
                find.Text = needle[:255]
                find.Forward = True
                find.Wrap = 0
                find.Execute()
                return
            except Exception:
                pass
        os.startfile(str(Path(source_file).resolve()))
    except Exception as exc:
        QMessageBox.critical(parent, t("message.error"), str(exc))
