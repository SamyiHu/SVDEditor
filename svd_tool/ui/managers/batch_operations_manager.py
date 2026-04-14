"""
批量操作管理器
支持批量修改寄存器/位域属性、批量生成寄存器、批量克隆等
"""
import logging
import copy
from typing import List, Dict, Any, Optional, Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QComboBox, QLineEdit,
    QGroupBox, QFormLayout, QDialog, QCheckBox, QSpinBox,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialogButtonBox, QProgressBar
)
from PyQt6.QtCore import QObject, pyqtSignal, Qt

from ...core.data_model import DeviceInfo, Peripheral, Register, Field
from ...config.styles import get_style_scheme

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

    # ==================== 批量修改属性 ====================

    def show_batch_modify_dialog(self, parent=None):
        """显示批量修改属性对话框"""
        device = self._get_device()
        if not device or not device.peripherals:
            QMessageBox.warning(parent, "提示", "请先加载 SVD 文件")
            return

        dlg = QDialog(parent)
        dlg.setWindowTitle("⚡ 批量修改属性")
        dlg.setMinimumSize(700, 550)
        dlg.resize(800, 600)
        layout = QVBoxLayout(dlg)

        # === 第1步：选择目标范围 ===
        scope_group = QGroupBox("1. 选择目标范围")
        scope_layout = QFormLayout(scope_group)

        # 外设选择
        periph_combo = QComboBox()
        periph_combo.addItem("所有外设", "__all__")
        for pname in sorted(device.peripherals.keys()):
            periph_combo.addItem(pname, pname)
        scope_layout.addRow("外设:", periph_combo)

        # 目标类型
        target_combo = QComboBox()
        target_combo.addItem("寄存器", "register")
        target_combo.addItem("位域", "field")
        scope_layout.addRow("目标类型:", target_combo)

        # 过滤条件（可选）
        filter_edit = QLineEdit()
        filter_edit.setPlaceholderText("可选：输入关键词过滤（如 MODE）")
        scope_layout.addRow("名称过滤:", filter_edit)

        layout.addWidget(scope_group)

        # === 第2步：选择要修改的属性 ===
        prop_group = QGroupBox("2. 设置要修改的属性")
        prop_layout = QVBoxLayout(prop_group)

        # 属性表格：属性名 | 新值 | 启用
        prop_table = QTableWidget(0, 3)
        prop_table.setHorizontalHeaderLabels(["属性", "新值", "启用"])
        prop_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        prop_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        prop_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        # 寄存器可修改属性
        reg_properties = [
            ("access", "访问权限 (read-write/read-only/write-only)"),
            ("size", "大小 (8/16/32)"),
            ("reset_value", "复位值"),
            ("description", "描述"),
        ]
        # 位域可修改属性
        field_properties = [
            ("access", "访问权限"),
            ("reset_value", "复位值"),
            ("description", "描述"),
        ]

        def update_properties_table():
            prop_table.setRowCount(0)
            is_field = target_combo.currentData() == "field"
            props = field_properties if is_field else reg_properties
            for prop_name, prop_desc in props:
                row = prop_table.rowCount()
                prop_table.insertRow(row)
                name_item = QTableWidgetItem(f"{prop_desc} ({prop_name})")
                name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                name_item.setData(Qt.ItemDataRole.UserRole, prop_name)
                prop_table.setItem(row, 0, name_item)
                prop_table.setItem(row, 1, QTableWidgetItem(""))
                cb = QCheckBox()
                cb.setChecked(False)
                cb_widget = QWidget()
                cb_layout = QHBoxLayout(cb_widget)
                cb_layout.addWidget(cb)
                cb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cb_layout.setContentsMargins(0, 0, 0, 0)
                prop_table.setCellWidget(row, 2, cb_widget)

        update_properties_table()
        target_combo.currentIndexChanged.connect(update_properties_table)
        layout.addWidget(prop_group)

        # === 预览 ===
        preview_group = QGroupBox("3. 预览受影响的项目")
        preview_layout = QVBoxLayout(preview_group)
        preview_list = QListWidget()
        preview_layout.addWidget(preview_list)
        count_label = QLabel("")
        preview_layout.addWidget(count_label)
        layout.addWidget(preview_group)

        def refresh_preview():
            preview_list.clear()
            periph_name = periph_combo.currentData()
            target_type = target_combo.currentData()
            filter_text = filter_edit.text().strip().lower()

            affected = self._collect_targets(device, periph_name, target_type, filter_text)
            for item_info in affected:
                icon = "📋" if target_type == "register" else "🔹"
                preview_list.addItem(f"{icon} {item_info}")
            count_label.setText(f"共 {len(affected)} 个项目将被修改")

        periph_combo.currentIndexChanged.connect(refresh_preview)
        target_combo.currentIndexChanged.connect(refresh_preview)
        filter_edit.textChanged.connect(refresh_preview)
        refresh_preview()

        # === 按钮 ===
        btn_layout = QHBoxLayout()
        apply_btn = QPushButton("⚡ 应用批量修改")
        _c = get_style_scheme().colors
        apply_btn.setStyleSheet(f"background-color: {_c.accent}; color: {_c.text_white}; padding: 8px 20px; font-weight: bold;")
        cancel_btn = QPushButton("取消")
        btn_layout.addStretch()
        btn_layout.addWidget(apply_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        def apply_changes():
            # 收集要修改的属性
            changes = {}
            for row in range(prop_table.rowCount()):
                cb_widget = prop_table.cellWidget(row, 2)
                cb = cb_widget.findChild(QCheckBox)
                if cb and cb.isChecked():
                    prop_name = prop_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
                    new_value = prop_table.item(row, 1).text().strip()
                    if new_value:
                        changes[prop_name] = new_value

            if not changes:
                QMessageBox.warning(dlg, "提示", "请至少启用并填写一个属性的新值")
                return

            periph_name = periph_combo.currentData()
            target_type = target_combo.currentData()
            filter_text = filter_edit.text().strip().lower()
            affected = self._collect_targets(device, periph_name, target_type, filter_text)

            if not affected:
                QMessageBox.information(dlg, "提示", "没有匹配的项目")
                return

            # 确认
            reply = QMessageBox.question(
                dlg, "确认批量修改",
                f"即将修改 {len(affected)} 个{('位域' if target_type == 'field' else '寄存器')}的以下属性:\n"
                + "\n".join(f"  • {k}: {v}" for k, v in changes.items())
                + f"\n\n确定继续吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

            # 执行批量修改
            count = self._apply_batch_modify(device, periph_name, target_type, filter_text, changes)

            # 通知 UI 更新
            self.operation_completed.emit(f"批量修改 {count} 个项目", count)
            if self.state_manager:
                self.state_manager._notify_state_change()

            QMessageBox.information(dlg, "完成", f"已成功修改 {count} 个项目")
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
        """显示批量生成寄存器对话框"""
        device = self._get_device()
        if not device or not device.peripherals:
            QMessageBox.warning(parent, "提示", "请先加载 SVD 文件")
            return

        dlg = QDialog(parent)
        dlg.setWindowTitle("📋 批量生成寄存器")
        dlg.setMinimumSize(650, 550)
        layout = QVBoxLayout(dlg)

        # 目标外设
        target_group = QGroupBox("目标外设")
        target_layout = QFormLayout(target_group)
        periph_combo = QComboBox()
        for pname in sorted(device.peripherals.keys()):
            periph_combo.addItem(pname, pname)
        target_layout.addRow("外设:", periph_combo)
        layout.addWidget(target_group)

        # 生成模式
        mode_group = QGroupBox("生成模式")
        mode_layout = QFormLayout(mode_group)

        mode_combo = QComboBox()
        mode_combo.addItem("序号递增（如 REG0, REG1, REG2...）", "sequence")
        mode_combo.addItem("名称列表（逗号分隔）", "named")
        mode_combo.addItem("从模板寄存器复制", "copy")
        mode_layout.addRow("模式:", mode_combo)

        # 名称前缀/后缀
        prefix_edit = QLineEdit("REG")
        prefix_edit.setPlaceholderText("寄存器名称前缀")
        mode_layout.addRow("名称前缀:", prefix_edit)

        start_spin = QSpinBox()
        start_spin.setRange(0, 1023)
        start_spin.setValue(0)
        mode_layout.addRow("起始序号:", start_spin)

        count_spin = QSpinBox()
        count_spin.setRange(1, 256)
        count_spin.setValue(8)
        mode_layout.addRow("数量:", count_spin)

        offset_spin = QLineEdit("0x04")
        offset_spin.setPlaceholderText("寄存器之间的偏移步长（如 0x04）")
        mode_layout.addRow("偏移步长:", offset_spin)

        # (mode_combo display is covered by the label above)
        layout.addWidget(mode_group)

        # 模板参数
        template_group = QGroupBox("寄存器属性模板")
        template_layout = QFormLayout(template_group)

        desc_edit = QLineEdit("")
        desc_edit.setPlaceholderText("寄存器描述（支持 {n} 作为序号占位符）")
        template_layout.addRow("描述:", desc_edit)

        access_combo = QComboBox()
        access_combo.addItems(["read-write", "read-only", "write-only"])
        template_layout.addRow("访问权限:", access_combo)

        size_combo = QComboBox()
        size_combo.addItems(["8", "16", "32"])
        size_combo.setCurrentText("32")
        template_layout.addRow("大小(位):", size_combo)

        reset_edit = QLineEdit("0x00000000")
        template_layout.addRow("复位值:", reset_edit)
        layout.addWidget(template_group)

        # 预览
        preview_group = QGroupBox("预览")
        preview_layout = QVBoxLayout(preview_group)
        preview_list = QListWidget()
        preview_layout.addWidget(preview_list)
        layout.addWidget(preview_group)

        def refresh_preview():
            preview_list.clear()
            prefix = prefix_edit.text().strip() or "REG"
            start = start_spin.value()
            count = count_spin.value()
            step_text = offset_spin.text().strip()
            try:
                step = int(step_text, 16) if step_text.startswith("0x") else int(step_text)
            except ValueError:
                step = 4

            # 获取当前外设的基地址用于计算绝对地址
            pname = periph_combo.currentData()
            base = 0
            if pname and pname in device.peripherals:
                ba = device.peripherals[pname].base_address
                try:
                    base = int(ba, 16) if isinstance(ba, str) else int(ba)
                except (ValueError, TypeError):
                    pass

            # 获取已有寄存器的最大偏移
            max_offset = 0
            if pname and pname in device.peripherals:
                for reg in device.peripherals[pname].registers.values():
                    try:
                        off = int(reg.offset, 16) if isinstance(reg.offset, str) else int(reg.offset)
                        max_offset = max(max_offset, off)
                    except (ValueError, TypeError):
                        pass

            for i in range(count):
                idx = start + i
                offset = max_offset + step * (i + 1)
                name = f"{prefix}{idx}"
                desc_text = desc_edit.text().replace("{n}", str(idx))
                preview_list.addItem(
                    f"📋 {name}  偏移: 0x{offset:04X}  绝对: 0x{base + offset:08X}  {desc_text}"
                )

        for w in [prefix_edit, start_spin, count_spin, offset_spin, desc_edit, periph_combo]:
            if isinstance(w, (QSpinBox, QComboBox)):
                w.valueChanged.connect(refresh_preview) if isinstance(w, QSpinBox) else w.currentIndexChanged.connect(refresh_preview)
            else:
                w.textChanged.connect(refresh_preview)
        refresh_preview()

        # 按钮
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(lambda: self._do_batch_generate(
            dlg, device, periph_combo.currentData(), prefix_edit.text().strip(),
            start_spin.value(), count_spin.value(), offset_spin.text().strip(),
            desc_edit.text(), access_combo.currentText(),
            int(size_combo.currentText()), reset_edit.text()))
        btn_box.rejected.connect(dlg.reject)
        layout.addWidget(btn_box)

        dlg.exec()

    def _do_batch_generate(self, dlg, device, periph_name, prefix, start, count,
                           step_text, desc_template, access, size, reset_value):
        """执行批量生成寄存器"""
        if periph_name not in device.peripherals:
            QMessageBox.warning(dlg, "错误", f"外设 {periph_name} 不存在")
            return

        periph = device.peripherals[periph_name]

        try:
            step = int(step_text, 16) if step_text.startswith("0x") else int(step_text)
        except ValueError:
            step = 4

        # 计算起始偏移（已有寄存器之后）
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
                self.logger.warning(f"寄存器 {name} 已存在，跳过")
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

        # 通知更新
        self.operation_completed.emit(f"批量生成 {generated} 个寄存器", generated)
        if self.state_manager:
            self.state_manager._notify_state_change()

        QMessageBox.information(dlg, "完成", f"已生成 {generated} 个寄存器到 {periph_name}")
        dlg.accept()

    # ==================== 批量克隆寄存器到其他外设 ====================

    def show_batch_clone_dialog(self, parent=None):
        """显示批量克隆寄存器对话框"""
        device = self._get_device()
        if not device or not device.peripherals:
            QMessageBox.warning(parent, "提示", "请先加载 SVD 文件")
            return

        dlg = QDialog(parent)
        dlg.setWindowTitle("📋 批量克隆寄存器")
        dlg.setMinimumSize(600, 500)
        layout = QVBoxLayout(dlg)

        # 源外设
        src_group = QGroupBox("源外设")
        src_layout = QFormLayout(src_group)
        src_combo = QComboBox()
        for pname in sorted(device.peripherals.keys()):
            src_combo.addItem(pname, pname)
        src_layout.addRow("从外设:", src_combo)

        src_reg_label = QLabel("")
        src_layout.addRow("寄存器数:", src_reg_label)
        layout.addWidget(src_group)

        # 目标外设（多选）
        dst_group = QGroupBox("目标外设（勾选要克隆到的外设）")
        dst_layout = QVBoxLayout(dst_group)
        dst_list = QListWidget()
        for pname in sorted(device.peripherals.keys()):
            item = QListWidgetItem(pname)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, pname)
            dst_list.addItem(item)
        dst_layout.addWidget(dst_list)

        # 全选/取消按钮
        sel_layout = QHBoxLayout()
        select_all_btn = QPushButton("全选")
        deselect_all_btn = QPushButton("取消全选")
        sel_layout.addWidget(select_all_btn)
        sel_layout.addWidget(deselect_all_btn)
        sel_layout.addStretch()
        dst_layout.addLayout(sel_layout)
        layout.addWidget(dst_group)

        # 选项
        opt_layout = QHBoxLayout()
        overwrite_cb = QCheckBox("覆盖同名寄存器")
        overwrite_cb.setChecked(False)
        opt_layout.addWidget(overwrite_cb)
        opt_layout.addStretch()
        layout.addLayout(opt_layout)

        def update_src_info():
            pname = src_combo.currentData()
            if pname and pname in device.peripherals:
                src_reg_label.setText(str(len(device.peripherals[pname].registers)))

        src_combo.currentIndexChanged.connect(update_src_info)
        update_src_info()

        select_all_btn.clicked.connect(lambda: self._set_all_checked(dst_list, True))
        deselect_all_btn.clicked.connect(lambda: self._set_all_checked(dst_list, False))

        # 按钮
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(lambda: self._do_batch_clone(
            dlg, device, src_combo.currentData(), dst_list, overwrite_cb.isChecked()))
        btn_box.rejected.connect(dlg.reject)
        layout.addWidget(btn_box)

        dlg.exec()

    @staticmethod
    def _set_all_checked(list_widget: QListWidget, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(list_widget.count()):
            list_widget.item(i).setCheckState(state)

    def _do_batch_clone(self, dlg, device, src_name, dst_list, overwrite):
        """执行批量克隆"""
        if src_name not in device.peripherals:
            QMessageBox.warning(dlg, "错误", f"源外设 {src_name} 不存在")
            return

        src_periph = device.peripherals[src_name]
        src_regs = list(src_periph.registers.values())

        # 收集目标外设
        targets = []
        for i in range(dst_list.count()):
            item = dst_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                pname = item.data(Qt.ItemDataRole.UserRole)
                if pname != src_name:
                    targets.append(pname)

        if not targets:
            QMessageBox.warning(dlg, "提示", "请至少选择一个目标外设")
            return

        total = 0
        for tgt_name in targets:
            if tgt_name not in device.peripherals:
                continue
            tgt_periph = device.peripherals[tgt_name]
            for reg in src_regs:
                if reg.name in tgt_periph.registers and not overwrite:
                    continue
                tgt_periph.registers[reg.name] = copy.deepcopy(reg)
                total += 1

        self.operation_completed.emit(f"批量克隆 {total} 个寄存器", total)
        if self.state_manager:
            self.state_manager._notify_state_change()

        QMessageBox.information(dlg, "完成",
                                f"已将 {len(src_regs)} 个寄存器克隆到 {len(targets)} 个外设（共 {total} 项）")
        dlg.accept()