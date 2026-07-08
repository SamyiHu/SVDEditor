"""
多源融合审阅对话框 — 展示 FusionReport 的冲突项与一致性提升项。

冲突项（conflicts）：各数据源给出不同值，按权重裁决，列出来供人工复核。
提升项（promotions）：多源一致、置信度被提升的项（通常无需干预，仅展示）。

非模态（show），可常驻对照。每项冲突可展开看各源取值。
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget, QWidget,
    QAbstractItemView,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from ...i18n.i18n import t
from ...config.styles import get_style_scheme


class FusionReviewDialog(QDialog):
    """多源融合审阅对话框。"""

    def __init__(self, parent, parse_result, datasource_manager=None):
        super().__init__(parent)
        self.result = parse_result
        self.mgr = datasource_manager

        self.setWindowTitle(t("datasource.fusion_review_title", default="多源融合审阅"))
        self.setMinimumSize(820, 560)
        self._apply_styles()
        self._build_ui()

    def _apply_styles(self):
        try:
            scheme = get_style_scheme()
            self.setStyleSheet(f"""
                QDialog {{ background-color: {scheme.colors.background}; }}
                QGroupBox {{
                    border: 1px solid {scheme.colors.border};
                    border-radius: 6px;
                    margin-top: 10px;
                    padding-top: 10px;
                    font-weight: bold;
                }}
                QTableWidget {{
                    gridline-color: {scheme.colors.border};
                    alternate-background-color: {scheme.colors.surface};
                    selection-background-color: {scheme.colors.accent_light};
                }}
                QPushButton {{
                    background-color: {scheme.colors.accent};
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 16px;
                }}
                QPushButton:hover {{ background-color: {scheme.colors.accent_hover}; }}
            """)
        except Exception:
            pass

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # 顶部摘要
        fr = getattr(self.result, "fusion_report", None)
        strategy = getattr(self.result, "strategy", "")
        summary = QLabel()
        if fr is None or strategy != "fusion":
            summary.setText(t("datasource.fusion_not_applicable",
                default="当前解析结果非多源融合产生，无可审阅的冲突/提升项。"))
            summary.setStyleSheet("color: #E65100; font-weight: bold; padding: 12px;")
            layout.addWidget(summary)
            close_btn = QPushButton(t("button.close", default="关闭"))
            close_btn.clicked.connect(self.accept)
            layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
            return

        n_conf = len(fr.conflicts)
        n_promo = len(fr.promotions)
        summary.setText(t("datasource.fusion_summary",
            strategy=strategy, primary=fr.primary_source or "-",
            conflicts=n_conf, promotions=n_promo,
            default=(f"策略：{strategy}（主源={fr.primary_source or '-'}）  |  "
                     f"冲突：{n_conf} 处  |  一致性提升：{n_promo} 处")))
        summary.setStyleSheet("font-size: 11pt; padding: 8px;")
        layout.addWidget(summary)

        # 标签页：冲突 / 提升
        tabs = QTabWidget()
        tabs.addTab(self._build_conflicts_tab(fr), t("datasource.tab_conflicts", default="冲突项"))
        tabs.addTab(self._build_promotions_tab(fr), t("datasource.tab_promotions", default="一致性提升"))
        layout.addWidget(tabs, 1)

        # 底部按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton(t("button.close", default="关闭"))
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _build_conflicts_tab(self, fr) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        if not fr.conflicts:
            layout.addWidget(QLabel(t("datasource.no_conflicts",
                default="✓ 无冲突项。各数据源对每个属性的取值一致。")))
            return w

        hint = QLabel(t("datasource.conflicts_hint",
            default="以下属性各源取值不同，已按权重裁决（取最高分）。可据此判断是否需复核原手册。"))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; padding: 4px;")
        layout.addWidget(hint)

        table = QTableWidget()
        headers = [t("datasource.col_peripheral", default="外设"),
                   t("datasource.col_register", default="寄存器"),
                   t("datasource.col_attr", default="属性"),
                   t("datasource.col_values", default="各源取值"),
                   t("datasource.col_resolved", default="裁决值"),
                   t("datasource.col_reason", default="原因")]
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        table.setRowCount(len(fr.conflicts))

        for row, c in enumerate(fr.conflicts):
            values_str = "\n".join(f"{v}  ← {', '.join(s)}" for v, s in (c.get("values", {})).items())
            items = [c.get("peripheral", ""), c.get("register", "") or "-",
                     c.get("attr", ""), values_str,
                     str(c.get("resolved", "")), c.get("reason", "")]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                if col == 4:  # 裁决值高亮
                    item.setForeground(QColor("#1565C0"))
                    item.setFont(self._bold_font())
                table.setItem(row, col, item)
        table.resizeColumnsToContents()
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(table, 1)
        return w

    def _build_promotions_tab(self, fr) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        if not fr.promotions:
            layout.addWidget(QLabel(t("datasource.no_promotions",
                default="无一致性提升项。")))
            return w

        hint = QLabel(t("datasource.promotions_hint",
            default="以下属性被多个数据源一致给出，置信度已被提升（更可信）。通常无需干预。"))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; padding: 4px;")
        layout.addWidget(hint)

        table = QTableWidget()
        headers = [t("datasource.col_peripheral", default="外设"),
                   t("datasource.col_register", default="寄存器"),
                   t("datasource.col_attr", default="属性"),
                   t("datasource.col_value", default="一致值"),
                   t("datasource.col_n_sources", default="源数"),
                   t("datasource.col_conf_change", default="置信度变化")]
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.setRowCount(len(fr.promotions))

        for row, p in enumerate(fr.promotions):
            old = p.get("old_conf", "")
            new = p.get("new_conf", "")
            conf_change = f"{old} → {new}" if old or new else ""
            items = [p.get("peripheral", ""), p.get("register", "") or "-",
                     p.get("attr", ""), str(p.get("value", "")),
                     str(p.get("n_sources", "")), conf_change]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                if col == 5 and new:
                    item.setForeground(QColor("#2E7D32"))
                table.setItem(row, col, item)
        layout.addWidget(table, 1)
        return w

    def _bold_font(self):
        from PyQt6.QtGui import QFont
        f = QFont()
        f.setBold(True)
        return f
