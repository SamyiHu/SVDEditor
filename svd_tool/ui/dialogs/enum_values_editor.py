# svd_tool/ui/dialogs/enum_values_editor.py
"""枚举值(enumeratedValues)编辑器组件"""

from typing import List, Dict, Optional
from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QAbstractItemView, QLabel
)
from PyQt6.QtCore import Qt

from ...i18n.i18n import t


class EnumValuesEditor(QGroupBox):
    """枚举值编辑器 - 嵌入到位域编辑对话框中使用"""

    def __init__(self, parent=None, enumerated_values: Optional[List[Dict[str, str]]] = None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()
        if enumerated_values:
            self.load_data(enumerated_values)

    def _setup_ui(self):
        self.setTitle(t("label.enum_values", default="枚举值 (enumeratedValues)"))
        from ...config.styles import get_style_scheme
        _ec = get_style_scheme().colors
        self.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold; border: 2px solid {_ec.accent}; border-radius: 6px;
                margin-top: 12px; padding-top: 16px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {_ec.accent};
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        hint = QLabel(t("label.enum_hint", default="定义位域的枚举值（如：0=Disabled, 1=Enabled）"))
        from ...config.styles import get_style_scheme
        _c = get_style_scheme().colors
        hint.setStyleSheet(f"color: {_c.text_secondary}; font-size: 11px; font-style: italic;")
        layout.addWidget(hint)

        self.enum_table = QTableWidget(0, 3)
        self.enum_table.setHorizontalHeaderLabels([
            t("label.enum_name", default="名称"),
            t("label.enum_value", default="值"),
            t("label.enum_description", default="描述")
        ])
        hdr = self.enum_table.horizontalHeader()
        if hdr:
            hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
            hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.enum_table.setColumnWidth(1, 80)
        self.enum_table.setMaximumHeight(200)
        self.enum_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.enum_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.enum_table.setAlternatingRowColors(True)
        self.enum_table.setStyleSheet(f"""
            QTableWidget {{ border: 1px solid {_ec.border_light}; border-radius: 4px; gridline-color: {_ec.border_light}; alternate-background-color: {_ec.table_even}; }}
            QTableWidget::item {{ padding: 4px; }}
            QTableWidget::item:selected {{ background-color: {_ec.selected}; color: {_ec.text_primary}; }}
            QHeaderView::section {{ background-color: {_ec.header_background}; padding: 4px; border: 1px solid {_ec.border_light}; font-weight: bold; font-size: 12px; }}
        """)
        layout.addWidget(self.enum_table)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self.add_btn = QPushButton(t("btn.enum_add", default="+ 添加"))
        self.add_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {_ec.button_add_periph}; color: {_ec.text_white}; border: none; border-radius: 4px; padding: 5px 12px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {_ec.button_add_periph_hover}; }}
            QPushButton:pressed {{ background-color: {_ec.button_add_periph_pressed}; }}
        """)

        self.remove_btn = QPushButton(t("btn.enum_remove", default="- 删除"))
        self.remove_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {_ec.button_delete}; color: {_ec.text_white}; border: none; border-radius: 4px; padding: 5px 12px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {_ec.button_delete_hover}; }}
            QPushButton:pressed {{ background-color: {_ec.button_delete_pressed}; }}
        """)
        self.remove_btn.setEnabled(False)

        move_style = f"""
            QPushButton {{ background-color: {_ec.light_gray}; border: none; border-radius: 4px; padding: 5px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {_ec.hover}; }}
            QPushButton:disabled {{ background-color: {_ec.light_gray}; color: {_ec.text_disabled}; }}
        """
        self.move_up_btn = QPushButton("▲")
        self.move_up_btn.setFixedWidth(36)
        self.move_up_btn.setToolTip(t("btn.enum_move_up", default="上移"))
        self.move_up_btn.setEnabled(False)
        self.move_up_btn.setStyleSheet(move_style)

        self.move_down_btn = QPushButton("▼")
        self.move_down_btn.setFixedWidth(36)
        self.move_down_btn.setToolTip(t("btn.enum_move_down", default="下移"))
        self.move_down_btn.setEnabled(False)
        self.move_down_btn.setStyleSheet(move_style)

        self.count_label = QLabel(t("label.enum_count_default", default="共 0 项"))
        from ...config.styles import get_style_scheme
        _c2 = get_style_scheme().colors
        self.count_label.setStyleSheet(f"color: {_c2.text_secondary}; font-size: 11px;")

        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addWidget(self.move_up_btn)
        btn_layout.addWidget(self.move_down_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.count_label)
        layout.addLayout(btn_layout)

    def _connect_signals(self):
        self.add_btn.clicked.connect(self._add_enum_value)
        self.remove_btn.clicked.connect(self._remove_enum_value)
        self.move_up_btn.clicked.connect(self._move_up)
        self.move_down_btn.clicked.connect(self._move_down)
        self.enum_table.itemSelectionChanged.connect(self._update_button_states)

    def _add_enum_value(self):
        row = self.enum_table.rowCount()
        self.enum_table.blockSignals(True)
        self.enum_table.insertRow(row)
        name_item = QTableWidgetItem("")
        value_item = QTableWidgetItem(self._get_next_enum_value())
        value_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_item = QTableWidgetItem("")
        self.enum_table.setItem(row, 0, name_item)
        self.enum_table.setItem(row, 1, value_item)
        self.enum_table.setItem(row, 2, desc_item)
        self.enum_table.blockSignals(False)
        self.enum_table.selectRow(row)
        self.enum_table.editItem(name_item)
        self._update_count_label()
        self._update_button_states()

    def _get_next_enum_value(self) -> str:
        max_val = -1
        for row in range(self.enum_table.rowCount()):
            vi = self.enum_table.item(row, 1)
            if vi:
                try:
                    txt = vi.text().strip()
                    if txt.startswith(("0x", "0X")):
                        val = int(txt, 16)
                    elif txt:
                        val = int(txt)
                    else:
                        continue
                    max_val = max(max_val, val)
                except (ValueError, AttributeError):
                    continue
        nv = max_val + 1
        return str(nv) if nv < 16 else hex(nv)

    def _remove_enum_value(self):
        cr = self.enum_table.currentRow()
        if cr < 0:
            return
        self.enum_table.removeRow(cr)
        self._update_count_label()
        self._update_button_states()

    def _move_up(self):
        cr = self.enum_table.currentRow()
        if cr <= 0:
            return
        self._swap_rows(cr, cr - 1)
        self.enum_table.selectRow(cr - 1)

    def _move_down(self):
        cr = self.enum_table.currentRow()
        if cr >= self.enum_table.rowCount() - 1:
            return
        self._swap_rows(cr, cr + 1)
        self.enum_table.selectRow(cr + 1)

    def _swap_rows(self, r1: int, r2: int):
        self.enum_table.blockSignals(True)
        for col in range(self.enum_table.columnCount()):
            a = self.enum_table.takeItem(r1, col)
            b = self.enum_table.takeItem(r2, col)
            self.enum_table.setItem(r1, col, b or QTableWidgetItem(""))
            self.enum_table.setItem(r2, col, a or QTableWidgetItem(""))
        self.enum_table.blockSignals(False)

    def _update_button_states(self):
        cr = self.enum_table.currentRow()
        sel = cr >= 0
        self.remove_btn.setEnabled(sel)
        self.move_up_btn.setEnabled(sel and cr > 0)
        self.move_down_btn.setEnabled(sel and cr < self.enum_table.rowCount() - 1)

    def _update_count_label(self):
        c = self.enum_table.rowCount()
        self.count_label.setText(t("label.enum_count", default="共 {count} 项", count=c))

    def load_data(self, enumerated_values: List[Dict[str, str]]):
        self.enum_table.blockSignals(True)
        self.enum_table.setRowCount(0)
        for ev in enumerated_values:
            row = self.enum_table.rowCount()
            self.enum_table.insertRow(row)
            ni = QTableWidgetItem(ev.get("name", ""))
            vi = QTableWidgetItem(ev.get("value", ""))
            vi.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            di = QTableWidgetItem(ev.get("description", ""))
            self.enum_table.setItem(row, 0, ni)
            self.enum_table.setItem(row, 1, vi)
            self.enum_table.setItem(row, 2, di)
        self.enum_table.blockSignals(False)
        self._update_count_label()
        self._update_button_states()

    def collect_data(self) -> List[Dict[str, str]]:
        result = []
        for row in range(self.enum_table.rowCount()):
            ni = self.enum_table.item(row, 0)
            vi = self.enum_table.item(row, 1)
            di = self.enum_table.item(row, 2)
            name = ni.text().strip() if ni else ""
            value = vi.text().strip() if vi else ""
            desc = di.text().strip() if di else ""
            if not name and not value:
                continue
            entry = {"name": name, "value": value}
            if desc:
                entry["description"] = desc
            result.append(entry)
        return result

    def validate(self) -> bool:
        errors = []
        seen_names = set()
        seen_values = set()
        for row in range(self.enum_table.rowCount()):
            ni = self.enum_table.item(row, 0)
            vi = self.enum_table.item(row, 1)
            name = ni.text().strip() if ni else ""
            value = vi.text().strip() if vi else ""
            if not name and not value:
                continue
            if not name:
                errors.append(f"第 {row+1} 行: 枚举名称不能为空")
            if not value:
                errors.append(f"第 {row+1} 行: 枚举值不能为空")
            else:
                try:
                    if value.startswith(("0x", "0X")):
                        int(value, 16)
                    elif value.startswith(("0b", "0B")):
                        int(value, 2)
                    else:
                        int(value)
                except ValueError:
                    errors.append(f"第 {row+1} 行: 枚举值 '{value}' 格式无效")
            if name and name in seen_names:
                errors.append(f"枚举名称 '{name}' 重复")
            if name:
                seen_names.add(name)
            if value and value in seen_values:
                errors.append(f"枚举值 '{value}' 重复")
            if value:
                seen_values.add(value)
        if errors:
            msg = "\n".join(errors[:5])
            if len(errors) > 5:
                msg += f"\n... 还有 {len(errors)-5} 个问题"
            QMessageBox.warning(self, t("title.enum_validation_error", default="枚举值验证错误"), msg)
            return False
        return True