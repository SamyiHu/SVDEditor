"""
批量操作管理器
支持批量修改寄存器/位域属性、批量生成寄存器、批量克隆等
"""
import logging
import copy
from typing import List, Dict, Any, Optional, Tuple

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QGroupBox, QFormLayout, QDialog,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QFrame, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import QObject, pyqtSignal, Qt
from PyQt6.QtGui import QColor

from ...core.data_model import DeviceInfo, Peripheral, Register, Field
from ...config.styles import get_style_scheme
from ...i18n.i18n import t
from ..widgets.toggle_switch import ToggleSwitch
from ..widgets.labeled_slider import LabeledSlider

logger = logging.getLogger("BatchOperations")


class BatchOperationsManager(QObject):
    """批量操作管理器"""

    operation_completed = pyqtSignal(str, int)  # (操作描述, 影响数量)

    def __init__(self, state_manager=None, coordinator=None):
        super().__init__()
        self.state_manager = state_manager
        self.coordinator = coordinator
        self.logger = logging.getLogger("BatchOperations")

    def _get_device(self) -> Optional[DeviceInfo]:
        if self.state_manager:
            return self.state_manager.device_info
        return None

    # ==================== 公共工具方法 ====================

    @staticmethod
    def _make_apply_btn(text: str) -> QPushButton:
        """创建统一样式的应用按钮"""
        btn = QPushButton(text)
        _c = get_style_scheme().colors
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {_c.accent};
                color: {_c.text_white};
                padding: 8px 24px;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 10pt;
            }}
            QPushButton:hover {{ background-color: {_c.accent_hover}; }}
            QPushButton:pressed {{ background-color: {_c.accent_pressed}; }}
        """)
        return btn

    @staticmethod
    def _make_cancel_btn(text: str) -> QPushButton:
        """创建统一样式的取消按钮"""
        btn = QPushButton(text)
        _c = get_style_scheme().colors
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {_c.surface};
                color: {_c.text_primary};
                padding: 8px 24px;
                border: 1px solid {_c.border};
                border-radius: 6px;
                font-size: 10pt;
            }}
            QPushButton:hover {{ background-color: {_c.hover}; }}
        """)
        return btn

    @staticmethod
    def _make_group_box(title: str) -> QGroupBox:
        """创建统一样式的分组框"""
        group = QGroupBox(title)
        _c = get_style_scheme().colors
        group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                color: {_c.text_primary};
                border: 1px solid {_c.border_light};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 16px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: {_c.text_secondary};
            }}
        """)
        return group

    # ==================== 批量修改属性 ====================

    def show_batch_modify_dialog(self, parent=None):
        """显示批量修改属性对话框（重写版）"""
        device = self._get_device()
        if not device or not device.peripherals:
            QMessageBox.warning(parent, t("message.warning"), t("batch.load_file_first"))
            return

        _c = get_style_scheme().colors

        dlg = QDialog(parent)
        dlg.setWindowTitle(t("batch.title_modify"))
        dlg.setMinimumSize(920, 580)
        dlg.resize(960, 620)

        main_layout = QVBoxLayout(dlg)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ======== 左侧：配置区 ========
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        # --- 目标范围 ---
        scope_group = self._make_group_box(t("batch.scope_group"))
        scope_layout = QFormLayout(scope_group)
        scope_layout.setSpacing(6)
        scope_layout.setContentsMargins(12, 20, 12, 8)

        periph_combo = QComboBox()
        periph_combo.addItem(t("batch.all_peripherals"), "__all__")
        for pname in sorted(device.peripherals.keys()):
            periph_combo.addItem(pname, pname)
        scope_layout.addRow(t("batch.peripheral_label"), periph_combo)

        target_combo = QComboBox()
        target_combo.addItem(t("type.register"), "register")
        target_combo.addItem(t("label.field"), "field")
        scope_layout.addRow(t("batch.target_type"), target_combo)

        filter_row = QHBoxLayout()
        filter_edit = QLineEdit()
        filter_edit.setPlaceholderText(t("batch.filter_placeholder"))
        filter_row.addWidget(filter_edit)
        match_label = QLabel("")
        match_label.setStyleSheet(f"color: {_c.text_secondary}; font-size: 9pt;")
        match_label.setFixedWidth(120)
        filter_row.addWidget(match_label)
        scope_layout.addRow(t("batch.name_filter"), filter_row)

        left_layout.addWidget(scope_group)

        # --- 修改属性 ---
        prop_group = self._make_group_box(t("batch.prop_group"))
        prop_layout = QVBoxLayout(prop_group)
        prop_layout.setContentsMargins(12, 20, 12, 8)
        prop_layout.setSpacing(6)

        reg_properties = [
            ("access", t("batch.prop_access"), "combo"),
            ("size", t("batch.prop_size"), "combo_size"),
            ("reset_value", t("batch.prop_reset_value"), "text"),
            ("description", t("batch.prop_description"), "text"),
        ]
        field_properties = [
            ("access", t("batch.prop_access"), "combo"),
            ("reset_value", t("batch.prop_reset_value"), "text"),
            ("description", t("batch.prop_description"), "text"),
        ]

        # 存储属性行控件: [(toggle, value_widget, prop_name), ...]
        prop_rows = []
        prop_rows_container = QWidget()
        prop_rows_layout = QVBoxLayout(prop_rows_container)
        prop_rows_layout.setContentsMargins(0, 0, 0, 0)
        prop_rows_layout.setSpacing(4)

        def rebuild_property_rows():
            # 清除旧行
            for toggle, value_w, _ in prop_rows:
                toggle.setParent(None)
                value_w.setParent(None)
                row_w = toggle.parent()
                if row_w:
                    row_w.setParent(None)
            prop_rows.clear()
            # 清空 layout
            while prop_rows_layout.count():
                item = prop_rows_layout.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()

            is_field = target_combo.currentData() == "field"
            props = field_properties if is_field else reg_properties

            for prop_name, prop_desc, widget_type in props:
                row_w = QWidget()
                row_layout = QHBoxLayout(row_w)
                row_layout.setContentsMargins(0, 2, 0, 2)
                row_layout.setSpacing(8)

                toggle = ToggleSwitch()
                toggle.setFixedWidth(50)
                row_layout.addWidget(toggle)

                name_lbl = QLabel(prop_desc)
                name_lbl.setFixedWidth(80)
                name_lbl.setStyleSheet(f"color: {_c.text_primary}; font-size: 9pt;")
                row_layout.addWidget(name_lbl)

                if widget_type == "combo":
                    val_w = QComboBox()
                    val_w.addItems(["read-write", "read-only", "write-only", "write-once"])
                    val_w.setEnabled(False)
                elif widget_type == "combo_size":
                    val_w = QComboBox()
                    val_w.addItems(["8", "16", "32"])
                    val_w.setCurrentText("32")
                    val_w.setEnabled(False)
                else:
                    val_w = QLineEdit()
                    val_w.setPlaceholderText(f"{prop_desc}...")
                    val_w.setEnabled(False)

                row_layout.addWidget(val_w, 1)
                prop_rows_layout.addWidget(row_w)
                prop_rows.append((toggle, val_w, prop_name))

                # 开关控制值控件启用状态
                toggle.toggled.connect(lambda checked, w=val_w: w.setEnabled(checked))
                # 值变更刷新预览
                if isinstance(val_w, QComboBox):
                    val_w.currentIndexChanged.connect(refresh_preview)
                elif isinstance(val_w, QLineEdit):
                    val_w.textChanged.connect(refresh_preview)
                toggle.toggled.connect(refresh_preview)

        prop_layout.addWidget(prop_rows_container)
        left_layout.addWidget(prop_group, 1)

        splitter.addWidget(left_widget)

        # ======== 右侧：预览区 ========
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        preview_group = self._make_group_box(t("batch.preview_group"))
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(8, 20, 8, 8)

        preview_table = QTableWidget(0, 4)
        preview_table.setHorizontalHeaderLabels([
            t("batch.col_name"),
            t("batch.col_property"),
            t("batch.old_value"),
            t("batch.new_value"),
        ])
        header = preview_table.horizontalHeader()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        preview_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        preview_table.setAlternatingRowColors(True)
        preview_table.setShowGrid(True)
        vheader = preview_table.verticalHeader()
        if vheader:
            vheader.setDefaultSectionSize(28)
        preview_layout.addWidget(preview_table)

        count_label = QLabel("")
        count_label.setStyleSheet(f"color: {_c.text_secondary}; font-size: 9pt; padding: 4px;")
        preview_layout.addWidget(count_label)

        right_layout.addWidget(preview_group)

        splitter.addWidget(right_widget)
        splitter.setSizes([400, 520])

        main_layout.addWidget(splitter, 1)

        # ======== 底部按钮 ========
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        apply_btn = self._make_apply_btn(t("batch.apply_btn"))
        cancel_btn = self._make_cancel_btn(t("button.cancel"))
        btn_layout.addWidget(apply_btn)
        btn_layout.addWidget(cancel_btn)
        main_layout.addLayout(btn_layout)

        # ======== 逻辑 ========

        def _collect_detailed_targets() -> List[Tuple[str, object]]:
            """收集目标，返回 [(显示名, 对象), ...]"""
            periph_name = periph_combo.currentData()
            target_type = target_combo.currentData()
            filter_text = filter_edit.text().strip().lower()
            result = []
            peripherals = ([device.peripherals[periph_name]] if periph_name != "__all__"
                           else list(device.peripherals.values()))
            for periph in peripherals:
                if target_type == "register":
                    for rname, reg in periph.registers.items():
                        if filter_text and filter_text not in rname.lower():
                            continue
                        result.append((f"{periph.name} > {rname}", reg))
                elif target_type == "field":
                    for rname, reg in periph.registers.items():
                        for fname, fld in reg.fields.items():
                            if filter_text and filter_text not in fname.lower():
                                continue
                            result.append((f"{periph.name} > {rname} > {fname}", fld))
            return result

        def refresh_preview():
            targets = _collect_detailed_targets()
            target_type = target_combo.currentData()
            type_label = t("batch.type_register") if target_type == "register" else t("batch.type_field")
            match_label.setText(t("batch.match_count", count=len(targets), type=type_label))

            # 收集已启用的属性修改
            active_changes = {}
            for toggle, val_w, prop_name in prop_rows:
                if toggle.isChecked():
                    if isinstance(val_w, QComboBox):
                        active_changes[prop_name] = val_w.currentText()
                    elif isinstance(val_w, QLineEdit):
                        val = val_w.text().strip()
                        if val:
                            active_changes[prop_name] = val

            # 填充预览表
            preview_table.setRowCount(0)
            for display_name, obj in targets:
                for prop, new_val in active_changes.items():
                    old_val = getattr(obj, prop, "") or ""
                    row = preview_table.rowCount()
                    preview_table.insertRow(row)
                    preview_table.setItem(row, 0, QTableWidgetItem(display_name))
                    preview_table.setItem(row, 1, QTableWidgetItem(prop))

                    old_item = QTableWidgetItem(str(old_val))
                    old_item.setForeground(QColor(_c.text_secondary))
                    preview_table.setItem(row, 2, old_item)

                    new_item = QTableWidgetItem(str(new_val))
                    new_item.setForeground(QColor(_c.accent))
                    preview_table.setItem(row, 3, new_item)

            count_label.setText(t("batch.affected_count", count=len(targets)))

        target_combo.currentIndexChanged.connect(lambda: (rebuild_property_rows(), refresh_preview()))
        periph_combo.currentIndexChanged.connect(refresh_preview)
        filter_edit.textChanged.connect(refresh_preview)

        # 初始构建
        rebuild_property_rows()
        refresh_preview()

        def apply_changes():
            # 收集变更
            changes = {}
            for toggle, val_w, prop_name in prop_rows:
                if toggle.isChecked():
                    if isinstance(val_w, QComboBox):
                        val = val_w.currentText()
                    elif isinstance(val_w, QLineEdit):
                        val = val_w.text().strip()
                    else:
                        val = ""
                    if val:
                        changes[prop_name] = val

            if not changes:
                QMessageBox.warning(dlg, t("message.warning"), t("batch.no_property"))
                return

            periph_name = periph_combo.currentData()
            target_type = target_combo.currentData()
            filter_text = filter_edit.text().strip().lower()

            affected = self._collect_targets(device, periph_name, target_type, filter_text)
            if not affected:
                QMessageBox.information(dlg, t("message.info"), t("batch.no_match"))
                return

            type_name = t("batch.type_field") if target_type == "field" else t("batch.type_register")
            props_text = "\n".join(f"  {k}: {v}" for k, v in changes.items())
            reply = QMessageBox.question(
                dlg, t("batch.confirm_title"),
                t("batch.confirm_msg", count=len(affected), type=type_name, props=props_text),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

            count = self._apply_batch_modify(device, periph_name, target_type, filter_text, changes)
            self.operation_completed.emit(f"Batch modify {count} items", count)
            if self.state_manager:
                self.state_manager._notify_state_change()

            QMessageBox.information(dlg, t("batch.complete"), t("batch.modify_success", count=count))
            dlg.accept()

        apply_btn.clicked.connect(apply_changes)
        cancel_btn.clicked.connect(dlg.reject)

        dlg.exec()

    def _collect_targets(self, device, periph_name: str, target_type: str,
                         filter_text: str) -> List[str]:
        """收集符合条件的目标列表"""
        affected = []
        peripherals = ([device.peripherals[periph_name]] if periph_name != "__all__"
                       else list(device.peripherals.values()))

        for periph in peripherals:
            if target_type == "register":
                for rname, reg in periph.registers.items():
                    if filter_text and filter_text not in rname.lower():
                        continue
                    affected.append(f"{periph.name} > {rname}")
            elif target_type == "field":
                for rname, reg in periph.registers.items():
                    for fname, fld in reg.fields.items():
                        if filter_text and filter_text not in fname.lower():
                            continue
                        affected.append(f"{periph.name} > {rname} > {fname}")
        return affected

    def _apply_batch_modify(self, device, periph_name: str, target_type: str,
                            filter_text: str, changes: Dict[str, str]) -> int:
        """执行批量修改"""
        count = 0
        peripherals = ([device.peripherals[periph_name]] if periph_name != "__all__"
                       else list(device.peripherals.values()))

        for periph in peripherals:
            if target_type == "register":
                for rname, reg in periph.registers.items():
                    if filter_text and filter_text not in rname.lower():
                        continue
                    for prop, value in changes.items():
                        if hasattr(reg, prop):
                            setattr(reg, prop, value)
                    count += 1
            elif target_type == "field":
                for rname, reg in periph.registers.items():
                    for fname, fld in reg.fields.items():
                        if filter_text and filter_text not in fname.lower():
                            continue
                        for prop, value in changes.items():
                            if hasattr(fld, prop):
                                setattr(fld, prop, value)
                        count += 1
        return count

    # ==================== 批量生成寄存器 ====================

    def show_batch_generate_dialog(self, parent=None):
        """显示批量生成寄存器对话框（重写版）"""
        device = self._get_device()
        if not device or not device.peripherals:
            QMessageBox.warning(parent, t("message.warning"), t("batch.load_file_first"))
            return

        _c = get_style_scheme().colors

        dlg = QDialog(parent)
        dlg.setWindowTitle(t("batch.title_generate"))
        dlg.setMinimumSize(920, 580)
        dlg.resize(960, 620)

        main_layout = QVBoxLayout(dlg)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ======== 左侧：配置区 ========
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        # --- 目标外设 ---
        target_group = self._make_group_box(t("batch.target_peripheral"))
        target_layout = QFormLayout(target_group)
        target_layout.setSpacing(6)
        target_layout.setContentsMargins(12, 20, 12, 8)

        periph_combo = QComboBox()
        for pname in sorted(device.peripherals.keys()):
            periph_combo.addItem(pname, pname)
        target_layout.addRow(t("batch.peripheral_label"), periph_combo)

        reg_count_label = QLabel("")
        reg_count_label.setStyleSheet(f"color: {_c.text_secondary}; font-size: 9pt;")
        target_layout.addRow(t("batch.reg_count"), reg_count_label)

        left_layout.addWidget(target_group)

        # --- 命名规则 ---
        naming_group = self._make_group_box(t("batch.naming_group"))
        naming_layout = QFormLayout(naming_group)
        naming_layout.setSpacing(6)
        naming_layout.setContentsMargins(12, 20, 12, 8)

        prefix_edit = QLineEdit("REG")
        prefix_edit.setPlaceholderText(t("batch.prefix_placeholder"))
        naming_layout.addRow(t("batch.name_prefix"), prefix_edit)

        start_spin = LabeledSlider()
        start_spin.setRange(0, 1023)
        start_spin.setValue(0)
        naming_layout.addRow(t("batch.start_index"), start_spin)

        count_spin = LabeledSlider()
        count_spin.setRange(1, 256)
        count_spin.setValue(8)
        naming_layout.addRow(t("batch.count"), count_spin)

        left_layout.addWidget(naming_group)

        # --- 寄存器模板 ---
        template_group = self._make_group_box(t("batch.reg_template"))
        template_layout = QFormLayout(template_group)
        template_layout.setSpacing(6)
        template_layout.setContentsMargins(12, 20, 12, 8)

        _INPUT_HEIGHT = 32  # 统一输入控件高度

        offset_edit = QLineEdit("0x04")
        offset_edit.setPlaceholderText(t("batch.offset_placeholder"))
        offset_edit.setFixedHeight(_INPUT_HEIGHT)
        template_layout.addRow(t("batch.offset_step"), offset_edit)

        access_combo = QComboBox()
        access_combo.addItems(["read-write", "read-only", "write-only"])
        access_combo.setFixedHeight(_INPUT_HEIGHT)
        template_layout.addRow(t("batch.access_label"), access_combo)

        size_combo = QComboBox()
        size_combo.addItems(["8", "16", "32"])
        size_combo.setCurrentText("32")
        size_combo.setFixedHeight(_INPUT_HEIGHT)
        template_layout.addRow(t("batch.size_bits"), size_combo)

        reset_edit = QLineEdit("0x00000000")
        reset_edit.setFixedHeight(_INPUT_HEIGHT)
        template_layout.addRow(t("batch.reset_label"), reset_edit)

        desc_edit = QLineEdit("")
        desc_edit.setPlaceholderText(t("batch.desc_placeholder"))
        desc_edit.setFixedHeight(_INPUT_HEIGHT)
        template_layout.addRow(t("label.description"), desc_edit)

        left_layout.addWidget(template_group, 1)

        splitter.addWidget(left_widget)

        # ======== 右侧：预览区 ========
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        preview_group = self._make_group_box(t("batch.preview"))
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(8, 20, 8, 8)

        preview_table = QTableWidget(0, 4)
        preview_table.setHorizontalHeaderLabels([
            t("batch.col_index"),
            t("label.name_column"),
            t("batch.col_offset"),
            t("label.description_column"),
        ])
        header = preview_table.horizontalHeader()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        preview_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        preview_table.setAlternatingRowColors(True)
        preview_table.setShowGrid(True)
        vheader = preview_table.verticalHeader()
        if vheader:
            vheader.setDefaultSectionSize(28)
        preview_layout.addWidget(preview_table)

        right_layout.addWidget(preview_group)

        splitter.addWidget(right_widget)
        splitter.setSizes([380, 540])

        main_layout.addWidget(splitter, 1)

        # ======== 底部按钮 ========
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        apply_btn = self._make_apply_btn(t("button.ok"))
        cancel_btn = self._make_cancel_btn(t("button.cancel"))
        btn_layout.addWidget(apply_btn)
        btn_layout.addWidget(cancel_btn)
        main_layout.addLayout(btn_layout)

        # ======== 逻辑 ========

        def _get_max_offset(periph_name: str) -> int:
            """获取外设中最大偏移"""
            max_off = 0
            if periph_name and periph_name in device.peripherals:
                for reg in device.peripherals[periph_name].registers.values():
                    try:
                        off = int(reg.offset, 16) if isinstance(reg.offset, str) else int(reg.offset)
                        max_off = max(max_off, off)
                    except (ValueError, TypeError):
                        pass
            return max_off

        def _parse_step(step_text: str) -> int:
            try:
                return int(step_text, 16) if step_text.startswith("0x") else int(step_text)
            except ValueError:
                return 4

        def update_reg_count():
            pname = periph_combo.currentData()
            if pname and pname in device.peripherals:
                cnt = len(device.peripherals[pname].registers)
                reg_count_label.setText(t("batch.reg_count_info", count=cnt))
            else:
                reg_count_label.setText("")

        def refresh_preview():
            preview_table.setRowCount(0)
            prefix = prefix_edit.text().strip() or "REG"
            start = start_spin.value()
            count = count_spin.value()
            step = _parse_step(offset_edit.text().strip())
            pname = periph_combo.currentData()
            max_offset = _get_max_offset(pname)

            for i in range(count):
                idx = start + i
                offset = max_offset + step * (i + 1)
                name = f"{prefix}{idx}"
                desc_text = desc_edit.text().replace("{n}", str(idx)) if desc_edit.text() else ""

                row = preview_table.rowCount()
                preview_table.insertRow(row)
                preview_table.setItem(row, 0, QTableWidgetItem(str(i + 1)))
                preview_table.setItem(row, 1, QTableWidgetItem(name))
                preview_table.setItem(row, 2, QTableWidgetItem(f"0x{offset:04X}"))
                preview_table.setItem(row, 3, QTableWidgetItem(desc_text))

        # 连接信号
        periph_combo.currentIndexChanged.connect(lambda: (update_reg_count(), refresh_preview()))
        for w in [prefix_edit, offset_edit, desc_edit]:
            w.textChanged.connect(refresh_preview)
        for w in [start_spin, count_spin]:
            w.valueChanged.connect(refresh_preview)

        update_reg_count()
        refresh_preview()

        def do_generate():
            pname = periph_combo.currentData()
            if not pname or pname not in device.peripherals:
                QMessageBox.warning(dlg, t("message.error"),
                                    t("batch.error_no_periph", name=pname or ""))
                return

            self._do_batch_generate(
                dlg, device, pname, prefix_edit.text().strip(),
                start_spin.value(), count_spin.value(), offset_edit.text().strip(),
                desc_edit.text(), access_combo.currentText(),
                int(size_combo.currentText()), reset_edit.text()
            )

        apply_btn.clicked.connect(do_generate)
        cancel_btn.clicked.connect(dlg.reject)

        dlg.exec()

    def _do_batch_generate(self, dlg, device, periph_name, prefix, start, count,
                           step_text, desc_template, access, size, reset_value):
        """执行批量生成寄存器"""
        if periph_name not in device.peripherals:
            QMessageBox.warning(dlg, t("message.error"),
                                t("batch.error_no_periph", name=periph_name))
            return

        periph = device.peripherals[periph_name]

        try:
            step = int(step_text, 16) if step_text.startswith("0x") else int(step_text)
        except ValueError:
            step = 4

        max_offset = 0
        for reg in periph.registers.values():
            try:
                off = int(reg.offset, 16) if isinstance(reg.offset, str) else int(reg.offset)
                max_offset = max(max_offset, off)
            except (ValueError, TypeError):
                pass

        generated = 0
        for i in range(count):
            idx = start + i
            offset = max_offset + step * (i + 1)
            name = f"{prefix}{idx}"
            desc = desc_template.replace("{n}", str(idx)) if desc_template else f"{name} register"

            if name in periph.registers:
                self.logger.warning(t("batch.register_exists", name=name))
                continue

            reg = Register(
                name=name,
                offset=f"0x{offset:04X}",
                description=desc,
                access=access,
                size=size,
                reset_value=reset_value,
            )
            periph.registers[name] = reg
            generated += 1

        self.operation_completed.emit(f"Batch generate {generated} registers", generated)
        if self.state_manager:
            self.state_manager._notify_state_change()

        QMessageBox.information(dlg, t("batch.complete"),
                                t("batch.generate_success", count=generated, name=periph_name))
        dlg.accept()

    # ==================== 批量克隆寄存器到其他外设 ====================

    def show_batch_clone_dialog(self, parent=None):
        """显示批量克隆寄存器对话框（重写版）"""
        device = self._get_device()
        if not device or not device.peripherals:
            QMessageBox.warning(parent, t("message.warning"), t("batch.load_file_first"))
            return

        _c = get_style_scheme().colors

        dlg = QDialog(parent)
        dlg.setWindowTitle(t("batch.title_clone"))
        dlg.setMinimumSize(850, 550)
        dlg.resize(880, 580)

        main_layout = QVBoxLayout(dlg)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ======== 左侧：源区 ========
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        # --- 源外设 ---
        src_group = self._make_group_box(t("batch.source_periph"))
        src_layout = QFormLayout(src_group)
        src_layout.setSpacing(6)
        src_layout.setContentsMargins(12, 20, 12, 8)

        src_combo = QComboBox()
        for pname in sorted(device.peripherals.keys()):
            src_combo.addItem(pname, pname)
        src_layout.addRow(t("batch.from_periph"), src_combo)

        src_reg_label = QLabel("")
        src_reg_label.setStyleSheet(f"color: {_c.text_secondary}; font-size: 9pt;")
        src_layout.addRow(t("batch.reg_count"), src_reg_label)

        left_layout.addWidget(src_group)

        # --- 选项 ---
        opt_group = self._make_group_box(t("batch.options"))
        opt_layout = QVBoxLayout(opt_group)
        opt_layout.setContentsMargins(12, 20, 12, 8)

        overwrite_toggle = ToggleSwitch(t("batch.overwrite"))
        overwrite_toggle.setChecked(False)
        opt_layout.addWidget(overwrite_toggle)

        summary_label = QLabel("")
        summary_label.setWordWrap(True)
        summary_label.setStyleSheet(f"color: {_c.text_secondary}; font-size: 9pt; padding: 8px 0;")
        opt_layout.addWidget(summary_label)

        left_layout.addWidget(opt_group)
        left_layout.addStretch(1)

        splitter.addWidget(left_widget)

        # ======== 右侧：目标区 ========
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        dst_group = self._make_group_box(t("batch.target_peripherals"))
        dst_layout = QVBoxLayout(dst_group)
        dst_layout.setContentsMargins(8, 20, 8, 8)
        dst_layout.setSpacing(6)

        # 全选/取消按钮行
        sel_layout = QHBoxLayout()
        select_all_btn = QPushButton(t("batch.select_all"))
        select_all_btn.setFixedHeight(28)
        deselect_all_btn = QPushButton(t("batch.deselect_all"))
        deselect_all_btn.setFixedHeight(28)
        sel_layout.addWidget(select_all_btn)
        sel_layout.addWidget(deselect_all_btn)
        sel_layout.addStretch()
        dst_layout.addLayout(sel_layout)

        # 目标列表 - 使用 QTableWidget + 勾选列
        dst_table = QTableWidget(0, 2)
        dst_table.setHorizontalHeaderLabels(["", t("batch.col_peripheral")])
        header = dst_table.horizontalHeader()
        if header:
            header.setMinimumSectionSize(60)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            dst_table.setColumnWidth(0, 70)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        dst_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        dst_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        dst_table.setAlternatingRowColors(True)
        dst_table.setShowGrid(True)
        vheader = dst_table.verticalHeader()
        if vheader:
            vheader.setDefaultSectionSize(32)
            vheader.setVisible(False)
        dst_layout.addWidget(dst_table)

        right_layout.addWidget(dst_group)

        splitter.addWidget(right_widget)
        splitter.setSizes([360, 480])

        main_layout.addWidget(splitter, 1)

        # ======== 底部按钮 ========
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        apply_btn = self._make_apply_btn(t("button.ok"))
        cancel_btn = self._make_cancel_btn(t("button.cancel"))
        btn_layout.addWidget(apply_btn)
        btn_layout.addWidget(cancel_btn)
        main_layout.addLayout(btn_layout)

        # ======== 逻辑 ========

        def build_target_table():
            """构建目标外设表格"""
            src_name = src_combo.currentData()
            dst_table.setRowCount(0)
            for pname in sorted(device.peripherals.keys()):
                if pname == src_name:
                    continue
                periph = device.peripherals[pname]
                reg_cnt = len(periph.registers)

                row = dst_table.rowCount()
                dst_table.insertRow(row)

                # 勾选框
                cb = ToggleSwitch()
                cb_widget = QWidget()
                cb_layout = QHBoxLayout(cb_widget)
                cb_layout.addWidget(cb)
                cb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cb_layout.setContentsMargins(0, 0, 0, 0)
                dst_table.setCellWidget(row, 0, cb_widget)
                cb.toggled.connect(update_summary)

                # 外设名 + 寄存器数
                display = f"{pname}  ({t('batch.reg_count_info', count=reg_cnt)})"
                name_item = QTableWidgetItem(display)
                name_item.setData(Qt.ItemDataRole.UserRole, pname)
                dst_table.setItem(row, 1, name_item)

        def update_src_info():
            pname = src_combo.currentData()
            if pname and pname in device.peripherals:
                src_reg_label.setText(str(len(device.peripherals[pname].registers)))
            else:
                src_reg_label.setText("")
            build_target_table()
            update_summary()

        def update_summary():
            src_name = src_combo.currentData()
            src_count = 0
            if src_name and src_name in device.peripherals:
                src_count = len(device.peripherals[src_name].registers)

            tgt_count = 0
            for row in range(dst_table.rowCount()):
                cb_widget = dst_table.cellWidget(row, 0)
                if cb_widget:
                    toggle = cb_widget.findChild(ToggleSwitch)
                    if toggle and toggle.isChecked():
                        tgt_count += 1

            if tgt_count > 0 and src_count > 0:
                summary_label.setText(
                    t("batch.clone_summary",
                      src_count=src_count, tgt_count=tgt_count,
                      total=src_count * tgt_count))
            else:
                summary_label.setText("")

        def select_all():
            for row in range(dst_table.rowCount()):
                cb_widget = dst_table.cellWidget(row, 0)
                if cb_widget:
                    toggle = cb_widget.findChild(ToggleSwitch)
                    if toggle:
                        toggle.setChecked(True)

        def deselect_all():
            for row in range(dst_table.rowCount()):
                cb_widget = dst_table.cellWidget(row, 0)
                if cb_widget:
                    toggle = cb_widget.findChild(ToggleSwitch)
                    if toggle:
                        toggle.setChecked(False)

        src_combo.currentIndexChanged.connect(update_src_info)
        select_all_btn.clicked.connect(select_all)
        deselect_all_btn.clicked.connect(deselect_all)
        update_src_info()

        def do_clone():
            src_name = src_combo.currentData()
            if not src_name or src_name not in device.peripherals:
                QMessageBox.warning(dlg, t("message.error"),
                                    t("batch.error_no_source", name=src_name or ""))
                return

            # 收集目标
            targets = []
            for row in range(dst_table.rowCount()):
                cb_widget = dst_table.cellWidget(row, 0)
                if cb_widget:
                    toggle = cb_widget.findChild(ToggleSwitch)
                    if toggle and toggle.isChecked():
                        name_item = dst_table.item(row, 1)
                        if name_item:
                            targets.append(name_item.data(Qt.ItemDataRole.UserRole))

            if not targets:
                QMessageBox.warning(dlg, t("message.warning"), t("batch.select_target"))
                return

            self._do_batch_clone(
                dlg, device, src_name, targets, overwrite_toggle.isChecked()
            )

        apply_btn.clicked.connect(do_clone)
        cancel_btn.clicked.connect(dlg.reject)

        dlg.exec()

    def _do_batch_clone(self, dlg, device, src_name, target_names: List[str], overwrite: bool):
        """执行批量克隆"""
        src_periph = device.peripherals[src_name]
        src_regs = list(src_periph.registers.values())

        total = 0
        for tgt_name in target_names:
            if tgt_name not in device.peripherals:
                continue
            tgt_periph = device.peripherals[tgt_name]
            for reg in src_regs:
                if reg.name in tgt_periph.registers and not overwrite:
                    continue
                tgt_periph.registers[reg.name] = copy.deepcopy(reg)
                total += 1

        self.operation_completed.emit(f"Batch clone {total} registers", total)
        if self.state_manager:
            self.state_manager._notify_state_change()

        QMessageBox.information(dlg, t("batch.complete"),
                                t("batch.clone_success",
                                  src_count=len(src_regs),
                                  tgt_count=len(target_names),
                                  total=total))
        dlg.accept()
