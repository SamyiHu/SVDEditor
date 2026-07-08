"""
SVD 核对面板 — 当前 SVD vs 数据手册解析结果的结构化差异复核。

非模态（show），可常驻对照。布局：
- 左侧：外设树（节点带置信度色标 + 差异计数徽章）+ 过滤器
- 右侧：差异表（层级/外设/寄存器/位域/类型/详情/严重度/置信度/SVD值/源值/建议）
- 底部：接受选中 / 全部接受(error) / 导出报告(Markdown) / 重新核对

「接受」调用 DatasourceManager.accept_items（undoable）→ 刷新树。
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QWidget,
    QLabel, QPushButton, QTreeWidget, QTreeWidgetItem, QTableWidget,
    QTableWidgetItem, QHeaderView, QCheckBox, QAbstractItemView,
    QMessageBox, QFileDialog, QGroupBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

from ...i18n.i18n import t
from ...config.styles import get_style_scheme
from ..managers.datasource_manager import DatasourceManager
from ...core.datasource.svd_verifier import VerifyItem, VerifyKind, VerifySeverity

_CONF_COLORS = {
    "high": QColor("#2E7D32"),
    "medium": QColor("#1565C0"),
    "low": QColor("#E65100"),
    "missing": QColor("#C62828"),
    "unknown": QColor("#9E9E9E"),
}
_CONF_LABELS = {"high": "高", "medium": "中", "low": "低",
                "missing": "缺失", "unknown": "未知"}

_SEVERITY_COLORS = {
    "error": QColor("#C62828"),
    "warning": QColor("#E65100"),
    "info": QColor("#9E9E9E"),
}

_KIND_LABELS = {
    VerifyKind.PERIPH_MISSING_IN_SVD.value: "外设缺失(SVD)",
    VerifyKind.PERIPH_MISSING_IN_SOURCE.value: "外设仅SVD有",
    VerifyKind.REG_MISSING_IN_SVD.value: "寄存器缺失(SVD)",
    VerifyKind.REG_MISSING_IN_SOURCE.value: "寄存器仅SVD有",
    VerifyKind.FIELD_MISSING_IN_SVD.value: "位域缺失(SVD)",
    VerifyKind.FIELD_MISSING_IN_SOURCE.value: "位域仅SVD有",
    VerifyKind.ADDRESS_MISMATCH.value: "地址不符",
    VerifyKind.OFFSET_MISMATCH.value: "偏移不符",
    VerifyKind.RESET_MISMATCH.value: "复位值不符",
    VerifyKind.ACCESS_MISMATCH.value: "访问权限不符",
    VerifyKind.WIDTH_MISMATCH.value: "位宽不符",
    VerifyKind.BASE_ADDR_MISMATCH.value: "基地址不符",
}


class SVDVerifyDialog(QDialog):
    """SVD 核对面板（非模态）。"""

    def __init__(self, parent, datasource_manager: DatasourceManager):
        super().__init__(parent)
        self.mgr = datasource_manager
        self._items: list[VerifyItem] = []

        self.setWindowTitle(t("datasource.verify_title", default="SVD 核对"))
        self.setMinimumSize(1000, 660)
        self.setWindowFlag(Qt.WindowType.Window, True)

        self._apply_styles()
        self._build_ui()

    def _apply_styles(self):
        try:
            scheme = get_style_scheme()
            self.setStyleSheet(f"""
                QDialog {{ background-color: {scheme.colors.background}; }}
                QGroupBox {{
                    border: 1px solid {scheme.colors.border};
                    border-radius: 6px; margin-top: 10px; padding-top: 10px;
                    font-weight: bold;
                }}
                QTreeWidget, QTableWidget {{
                    gridline-color: {scheme.colors.border};
                    alternate-background-color: {scheme.colors.surface};
                    selection-background-color: {scheme.colors.accent_light};
                }}
                QPushButton {{
                    background-color: {scheme.colors.accent};
                    color: white; border: none; border-radius: 4px;
                    padding: 6px 14px;
                }}
                QPushButton:hover {{ background-color: {scheme.colors.accent_hover}; }}
                QPushButton:disabled {{ background-color: #BDBDBD; }}
            """)
        except Exception:
            pass

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # 顶部摘要 + 过滤器
        top = QHBoxLayout()
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("font-size: 11pt; font-weight: bold;")
        top.addWidget(self.summary_label)
        top.addStretch()

        self.filter_error = QCheckBox(t("datasource.filter_error", default="仅错误"))
        self.filter_warning = QCheckBox(t("datasource.filter_warning", default="含警告"))
        self.filter_warning.setChecked(True)
        self.filter_error.stateChanged.connect(self._populate_tree)
        self.filter_warning.stateChanged.connect(self._populate_tree)
        top.addWidget(self.filter_error)
        top.addWidget(self.filter_warning)
        layout.addLayout(top)

        # 左右分栏
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左：外设树
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel(t("datasource.periph_tree",
            default="外设（括号为差异数）")))
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([t("datasource.tree_name", default="名称"),
                                   t("datasource.tree_diff", default="差异数"),
                                   t("datasource.tree_conf", default="置信度")])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.itemSelectionChanged.connect(self._on_tree_select)
        left_layout.addWidget(self.tree, 1)
        splitter.addWidget(left)

        # 右：差异表
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel(t("datasource.diff_table", default="差异列表")))
        self.table = QTableWidget()
        headers = ["",  # 复选框列
                   t("datasource.col_level", default="层级"),
                   t("datasource.col_peripheral", default="外设"),
                   t("datasource.col_register", default="寄存器"),
                   t("datasource.col_field", default="位域"),
                   t("datasource.col_type", default="类型"),
                   t("datasource.col_detail", default="详情"),
                   t("datasource.col_severity", default="严重度"),
                   t("datasource.col_conf", default="置信度"),
                   t("datasource.col_svd_val", default="SVD值"),
                   t("datasource.col_src_val", default="源值")]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        right_layout.addWidget(self.table, 1)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, 1)

        # 底部按钮
        btn_row = QHBoxLayout()
        self.accept_btn = QPushButton(t("datasource.accept_selected", default="接受选中"))
        self.accept_btn.clicked.connect(self._accept_selected)
        self.accept_all_btn = QPushButton(t("datasource.accept_all_errors", default="全部接受(错误)"))
        self.accept_all_btn.clicked.connect(self._accept_all_errors)
        self.export_btn = QPushButton(t("datasource.export_report", default="导出报告(Markdown)"))
        self.export_btn.clicked.connect(self._export_report)
        reverify_btn = QPushButton(t("datasource.reverify", default="重新核对"))
        reverify_btn.clicked.connect(self.refresh)
        close_btn = QPushButton(t("button.close", default="关闭"))
        close_btn.clicked.connect(self.close)
        for b in (self.accept_btn, self.accept_all_btn):
            btn_row.addWidget(b)
        btn_row.addStretch()
        for b in (self.export_btn, reverify_btn, close_btn):
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

    # ---------- 数据加载 ----------

    def refresh(self):
        """重新核对并刷新界面。"""
        self._items = self.mgr.run_verify() or []
        self._update_summary()
        self._populate_tree()
        self._populate_table(None)  # 默认显示全部

    def _update_summary(self):
        counts = {"error": 0, "warning": 0, "info": 0}
        for it in self._items:
            counts[it.severity] = counts.get(it.severity, 0) + 1
        self.summary_label.setText(t("datasource.verify_summary",
            total=len(self._items), err=counts["error"],
            warn=counts["warning"], info=counts["info"],
            default=(f"共 {len(self._items)} 项差异："
                     f"{counts['error']} 错误 / {counts['warning']} 警告 / {counts['info']} 提示")))

    # ---------- 外设树 ----------

    def _filtered_items(self) -> list[VerifyItem]:
        """按过滤器筛选差异项。"""
        if self.filter_error.isChecked():
            return [it for it in self._items if it.severity == "error"]
        if not self.filter_warning.isChecked():
            return [it for it in self._items if it.severity == "error"]
        return list(self._items)

    def _populate_tree(self):
        self.tree.clear()
        # 按外设分组，统计每外设的差异数 + 最高置信度
        periph_items: dict = {}
        for it in self._filtered_items():
            periph_items.setdefault(it.peripheral, []).append(it)

        # 「全部」节点
        all_item = QTreeWidgetItem([
            t("datasource.all_periphs", default="全部外设"),
            str(len(self._filtered_items())), ""])
        all_item.setData(0, Qt.ItemDataRole.UserRole, None)  # None=全部
        font = all_item.font(0)
        font.setBold(True)
        all_item.setFont(0, font)
        self.tree.addTopLevelItem(all_item)

        for pname in sorted(periph_items.keys()):
            items = periph_items[pname]
            n = len(items)
            # 该外设最高置信度
            conf_order = {"unknown": 0, "missing": 1, "low": 2, "medium": 3, "high": 4}
            best = "unknown"
            for it in items:
                if conf_order.get(it.confidence, 0) > conf_order.get(best, 0):
                    best = it.confidence
            node = QTreeWidgetItem([pname, str(n), _CONF_LABELS.get(best, best)])
            node.setData(0, Qt.ItemDataRole.UserRole, pname)
            node.setForeground(2, _CONF_COLORS.get(best, QColor("gray")))
            self.tree.addTopLevelItem(node)

        self.tree.setCurrentItem(all_item)

    def _on_tree_select(self):
        node = self.tree.currentItem()
        if node is None:
            return
        pname = node.data(0, Qt.ItemDataRole.UserRole)
        self._populate_table(pname)  # None=全部

    # ---------- 差异表 ----------

    def _populate_table(self, peripheral: Optional[str]):
        items = self._filtered_items()
        if peripheral is not None:
            items = [it for it in items if it.peripheral == peripheral]

        self.table.setRowCount(len(items))
        for row, it in enumerate(items):
            # 复选框（默认勾选 error/warning）
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            check.setCheckState(Qt.CheckState.Checked
                                if it.severity in ("error", "warning")
                                else Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, check)

            self.table.setItem(row, 1, QTableWidgetItem(it.level))
            self.table.setItem(row, 2, QTableWidgetItem(it.peripheral))
            self.table.setItem(row, 3, QTableWidgetItem(it.register or "-"))
            self.table.setItem(row, 4, QTableWidgetItem(it.field or "-"))
            self.table.setItem(row, 5, QTableWidgetItem(_KIND_LABELS.get(it.kind, it.kind)))

            detail_item = QTableWidgetItem(it.detail)
            detail_item.setToolTip(it.detail)
            self.table.setItem(row, 6, detail_item)

            sev_item = QTableWidgetItem(it.severity)
            sev_item.setForeground(_SEVERITY_COLORS.get(it.severity, QColor("gray")))
            self.table.setItem(row, 7, sev_item)

            conf_item = QTableWidgetItem(_CONF_LABELS.get(it.confidence, it.confidence))
            conf_item.setForeground(_CONF_COLORS.get(it.confidence, QColor("gray")))
            self.table.setItem(row, 8, conf_item)

            self.table.setItem(row, 9, QTableWidgetItem(it.svd_value))
            self.table.setItem(row, 10, QTableWidgetItem(it.source_value))

            # 行级 tooltip = 建议值
            if it.suggested:
                suggest_str = ", ".join(f"{k}={v}" for k, v in it.suggested.items())
                for col in range(self.table.columnCount()):
                    cell = self.table.item(row, col)
                    if cell:
                        cell.setToolTip(f"{it.detail}\n建议: {suggest_str}")

    # ---------- 接受逻辑 ----------

    def _get_checked_items(self) -> list[VerifyItem]:
        """返回表格中勾选的差异项（按当前筛选范围）。"""
        result = []
        items = self._filtered_items()
        peripheral = None
        node = self.tree.currentItem()
        if node is not None:
            peripheral = node.data(0, Qt.ItemDataRole.UserRole)
        if peripheral is not None:
            items = [it for it in items if it.peripheral == peripheral]
        for row, it in enumerate(items):
            check = self.table.item(row, 0)
            if check and check.checkState() == Qt.CheckState.Checked:
                result.append(it)
        return result

    def _accept_selected(self):
        selected = self._get_checked_items()
        if not selected:
            QMessageBox.information(self, t("message.info"),
                t("datasource.no_selection", default="未勾选任何差异项"))
            return
        n = self.mgr.accept_items(selected)
        QMessageBox.information(self, t("datasource.accept_done", default="已接受"),
            t("datasource.accepted_n", n=n, default=f"已接受 {n} 项核对建议。可按 Ctrl+Z 撤销。"))
        self.refresh()

    def _accept_all_errors(self):
        errors = [it for it in self._items
                  if it.severity == "error" and it.suggested]
        if not errors:
            QMessageBox.information(self, t("message.info"),
                t("datasource.no_errors", default="没有可接受的错误项"))
            return
        ret = QMessageBox.question(self, t("datasource.confirm", default="确认"),
            t("datasource.confirm_accept_all", n=len(errors),
              default=f"将接受全部 {len(errors)} 个错误项（含缺失与不符），确定吗？"))
        if ret != QMessageBox.StandardButton.Yes:
            return
        n = self.mgr.accept_items(errors)
        QMessageBox.information(self, t("datasource.accept_done", default="已接受"),
            t("datasource.accepted_n", n=n, default=f"已接受 {n} 项。可按 Ctrl+Z 撤销。"))
        self.refresh()

    # ---------- 报告导出 ----------

    def _export_report(self):
        if not self._items:
            QMessageBox.information(self, t("message.info"),
                t("datasource.no_items_to_export", default="没有差异项可导出"))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, t("datasource.export_report", default="导出报告"),
            "svd_verify_report.md", "Markdown (*.md);;Text (*.txt)")
        if not path:
            return
        try:
            md = self._build_markdown()
            with open(path, "w", encoding="utf-8") as f:
                f.write(md)
            QMessageBox.information(self, t("datasource.export_done", default="导出完成"),
                t("datasource.report_saved", path=path, default=f"报告已保存：{path}"))
        except Exception as e:
            QMessageBox.critical(self, t("message.error"),
                t("datasource.export_failed", msg=str(e), default=f"导出失败：{e}"))

    def _build_markdown(self) -> str:
        counts = {"error": 0, "warning": 0, "info": 0}
        for it in self._items:
            counts[it.severity] = counts.get(it.severity, 0) + 1
        lines = ["# SVD 核对报告",
                 "",
                 f"- 差异总数：{len(self._items)}",
                 f"- 错误：{counts['error']}",
                 f"- 警告：{counts['warning']}",
                 f"- 提示：{counts['info']}",
                 "",
                 "| 层级 | 外设 | 寄存器 | 位域 | 类型 | 严重度 | 置信度 | SVD值 | 源值 | 详情 | 建议 |",
                 "|---|---|---|---|---|---|---|---|---|---|---|"]
        for it in self._items:
            suggest = ", ".join(f"{k}={v}" for k, v in it.suggested.items()) if it.suggested else ""
            lines.append("| " + " | ".join([
                it.level, it.peripheral, it.register or "-",
                it.field or "-", _KIND_LABELS.get(it.kind, it.kind),
                it.severity, it.confidence,
                it.svd_value, it.source_value,
                it.detail.replace("|", "\\|"), suggest,
            ]) + " |")
        return "\n".join(lines)

    # ---------- 跳转 ----------

    def _on_double_click(self, row: int, col: int):
        """双击差异行 → 跳转到对应外设/寄存器高亮（若主窗口支持）。"""
        items = self._filtered_items()
        peripheral = None
        node = self.tree.currentItem()
        if node is not None:
            peripheral = node.data(0, Qt.ItemDataRole.UserRole)
        if peripheral is not None:
            items = [it for it in items if it.peripheral == peripheral]
        if row >= len(items):
            return
        it = items[row]
        mw = self.parent()
        if mw is None:
            return
        # 优先用 peripheral_manager 的选中/跳转
        try:
            pm = getattr(mw, "peripheral_manager", None)
            if pm and it.peripheral:
                if hasattr(pm, "select_peripheral"):
                    pm.select_peripheral(it.peripheral, register=it.register or None,
                                         field=it.field or None)
                elif hasattr(pm, "select_node"):
                    pm.select_node(it.peripheral)
        except Exception:
            pass
