"""
连锁规则编辑对话框
独立的规则编辑器，支持添加/删除/修改动作的可视化编辑
"""
import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget,
    QTreeWidgetItem, QLabel, QLineEdit, QComboBox,
    QGroupBox, QFormLayout, QSplitter, QWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QDialogButtonBox,
    QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from ...core.chain_rules import ChainRule, ChainAction
from ...config.styles import get_style_scheme
from ...i18n.i18n import t
from ..widgets.toggle_switch import ToggleSwitch
from ..widgets.labeled_slider import LabeledSlider

logger = logging.getLogger("ChainRulesDialog")

# 动作类型选项
_ACTION_TYPES = ["delete", "modify", "add"]
_TRIGGER_TYPES = ["delete", "modify", "add"]
_SOURCE_TYPES = ["peripheral", "register", "field"]


class ChainRulesDialog(QDialog):
    """连锁规则编辑对话框"""

    def __init__(self, parent=None, engine=None):
        super().__init__(parent)
        self.engine = engine
        self._current_rule_index: int = -1

        self.setWindowTitle(t("dialog.chain_rules"))
        self.setMinimumSize(950, 650)
        self.resize(1000, 700)

        self._setup_ui()
        self._load_rules_list()

    def _setup_ui(self):
        _c = get_style_scheme().colors
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # === 顶部：全局开关 ===
        top_bar = QHBoxLayout()
        self.global_toggle = ToggleSwitch(t("label.chain_enabled"))
        self.global_toggle.setChecked(self.engine.enabled if self.engine else True)
        top_bar.addWidget(self.global_toggle)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        # === 主分割器 ===
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- 左侧：规则列表 ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        left_header = QHBoxLayout()
        left_header.addWidget(QLabel(t("chain.rules_list")))
        self.rule_count_label = QLabel("")
        self.rule_count_label.setStyleSheet(f"color: {_c.text_secondary}; font-size: 9pt;")
        left_header.addWidget(self.rule_count_label)
        left_header.addStretch()
        left_layout.addLayout(left_header)

        self.rules_tree = QTreeWidget()
        self.rules_tree.setHeaderLabels([
            t("chain.col_name"), t("chain.col_trigger"), t("chain.col_enabled")
        ])
        header = self.rules_tree.header()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.rules_tree.setAlternatingRowColors(True)
        self.rules_tree.setSelectionBehavior(QTreeWidget.SelectionBehavior.SelectRows)
        self.rules_tree.currentItemChanged.connect(self._on_rule_selected)
        left_layout.addWidget(self.rules_tree)

        btn_bar = QHBoxLayout()
        add_btn = QPushButton(t("button.add"))
        add_btn.clicked.connect(self._add_rule)
        btn_bar.addWidget(add_btn)
        del_btn = QPushButton(t("button.delete"))
        del_btn.clicked.connect(self._del_rule)
        btn_bar.addWidget(del_btn)
        batch_btn = QPushButton(t("chain.batch_generate"))
        batch_btn.clicked.connect(self._batch_generate)
        btn_bar.addWidget(batch_btn)
        left_layout.addLayout(btn_bar)

        splitter.addWidget(left_widget)

        # --- 右侧：规则编辑 ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        # 规则配置组
        config_group = QGroupBox(t("chain.rule_config"))
        config_form = QFormLayout(config_group)
        config_form.setSpacing(6)
        config_form.setContentsMargins(12, 20, 12, 8)

        self.name_edit = QLineEdit()
        config_form.addRow(t("chain.rule_name"), self.name_edit)

        self.trigger_combo = QComboBox()
        for trig in _TRIGGER_TYPES:
            self.trigger_combo.addItem(t(f"chain.trigger_{trig}"), trig)
        config_form.addRow(t("chain.trigger_label"), self.trigger_combo)

        self.source_type_combo = QComboBox()
        for st in _SOURCE_TYPES:
            self.source_type_combo.addItem(t(f"chain.source_{st}"), st)
        config_form.addRow(t("label.source_type"), self.source_type_combo)

        self.source_periph = QLineEdit()
        self.source_periph.setPlaceholderText(t("chain.wildcard_hint"))
        config_form.addRow(t("label.source_peripheral"), self.source_periph)

        self.source_reg = QLineEdit()
        self.source_reg.setPlaceholderText(t("chain.no_limit"))
        config_form.addRow(t("label.source_register"), self.source_reg)

        self.source_field = QLineEdit()
        self.source_field.setPlaceholderText(t("chain.no_limit"))
        config_form.addRow(t("label.source_field"), self.source_field)

        self.rule_enabled = ToggleSwitch(t("label.enabled"))
        self.rule_enabled.setChecked(True)
        config_form.addRow(self.rule_enabled)

        right_layout.addWidget(config_group)

        # 连锁动作组
        actions_group = QGroupBox(t("chain.actions"))
        actions_layout = QVBoxLayout(actions_group)
        actions_layout.setContentsMargins(8, 20, 8, 8)
        actions_layout.setSpacing(6)

        self.actions_table = QTableWidget(0, 4)
        self.actions_table.setHorizontalHeaderLabels([
            t("chain.col_target_periph"),
            t("chain.col_target_reg"),
            t("chain.col_target_field"),
            t("chain.col_action_type"),
        ])
        act_header = self.actions_table.horizontalHeader()
        if act_header:
            act_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            act_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            act_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            act_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.actions_table.setAlternatingRowColors(True)
        self.actions_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.actions_table.verticalHeader().setVisible(False)
        actions_layout.addWidget(self.actions_table)

        act_btn_bar = QHBoxLayout()
        add_act_btn = QPushButton(t("chain.add_action"))
        add_act_btn.clicked.connect(self._add_action_row)
        act_btn_bar.addWidget(add_act_btn)
        del_act_btn = QPushButton(t("chain.remove_action"))
        del_act_btn.clicked.connect(self._del_action_row)
        act_btn_bar.addWidget(del_act_btn)
        act_btn_bar.addStretch()
        actions_layout.addLayout(act_btn_bar)

        vars_hint = QLabel(t("chain.vars_hint"))
        vars_hint.setStyleSheet(f"color: {_c.text_secondary}; font-size: 9pt;")
        actions_layout.addWidget(vars_hint)

        right_layout.addWidget(actions_group, 1)

        splitter.addWidget(right_widget)
        splitter.setSizes([300, 650])
        layout.addWidget(splitter, 1)

        # === 底部按钮 ===
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        save_btn = QPushButton(t("button.save"))
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {_c.accent}; color: white;
                padding: 8px 24px; border: none; border-radius: 6px;
                font-weight: bold; font-size: 10pt;
            }}
            QPushButton:hover {{ background-color: {_c.accent_hover}; }}
        """)
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)
        cancel_btn = QPushButton(t("button.cancel"))
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {_c.surface}; color: {_c.text_primary};
                padding: 8px 24px; border: 1px solid {_c.border}; border-radius: 6px;
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    # ==================== 规则列表操作 ====================

    def _load_rules_list(self):
        """加载规则列表"""
        self.rules_tree.clear()
        if not self.engine:
            return
        for rule in self.engine.rules:
            self._add_rule_item(rule)
        self._update_rule_count()

    def _add_rule_item(self, rule: ChainRule):
        """添加规则到列表"""
        item = QTreeWidgetItem()
        item.setText(0, rule.name)
        trigger_text = t(f"chain.trigger_{rule.trigger}", default=rule.trigger)
        item.setText(1, trigger_text)
        enabled_text = "ON" if rule.enabled else "OFF"
        item.setText(2, enabled_text)
        self.rules_tree.addTopLevelItem(item)

    def _update_rule_count(self):
        """更新规则计数"""
        count = self.rules_tree.topLevelItemCount()
        self.rule_count_label.setText(f"({count})")

    def _on_rule_selected(self, current: Optional[QTreeWidgetItem], previous: Optional[QTreeWidgetItem]):
        """选中规则时加载详情"""
        if not current or not self.engine:
            return

        row = self.rules_tree.indexOfTopLevelItem(current)
        if row < 0 or row >= len(self.engine.rules):
            return

        self._current_rule_index = row
        rule = self.engine.rules[row]

        # 填充表单
        self.name_edit.setText(rule.name)

        # 设置触发条件
        idx = _TRIGGER_TYPES.index(rule.trigger) if rule.trigger in _TRIGGER_TYPES else 0
        self.trigger_combo.setCurrentIndex(idx)

        # 设置源类型
        idx = _SOURCE_TYPES.index(rule.source_type) if rule.source_type in _SOURCE_TYPES else 0
        self.source_type_combo.setCurrentIndex(idx)

        self.source_periph.setText(rule.source_peripheral)
        self.source_reg.setText(rule.source_register)
        self.source_field.setText(rule.source_field)
        self.rule_enabled.setChecked(rule.enabled)

        # 填充动作表格
        self.actions_table.setRowCount(0)
        for action in rule.actions:
            self._add_action_row_data(action)

    # ==================== 规则增删 ====================

    def _add_rule(self):
        """添加新规则"""
        if not self.engine:
            return
        rule = ChainRule(name=t("chain.new_rule"))
        self.engine.rules.append(rule)
        self._add_rule_item(rule)
        self._update_rule_count()
        # 选中新添加的规则
        self.rules_tree.setCurrentItem(self.rules_tree.topLevelItem(self.rules_tree.topLevelItemCount() - 1))

    def _del_rule(self):
        """删除选中规则"""
        if not self.engine:
            return
        item = self.rules_tree.currentItem()
        if not item:
            return
        row = self.rules_tree.indexOfTopLevelItem(item)
        if 0 <= row < len(self.engine.rules):
            self.engine.rules.pop(row)
            self.rules_tree.takeTopLevelItem(row)
            self._update_rule_count()
            self._current_rule_index = -1

    # ==================== 动作表格操作 ====================

    def _add_action_row(self):
        """添加一个空动作行"""
        row = self.actions_table.rowCount()
        self.actions_table.insertRow(row)
        self.actions_table.setItem(row, 0, QTableWidgetItem(""))
        self.actions_table.setItem(row, 1, QTableWidgetItem(""))
        self.actions_table.setItem(row, 2, QTableWidgetItem(""))
        # 动作类型下拉框
        combo = QComboBox()
        for act in _ACTION_TYPES:
            combo.addItem(t(f"chain.action_{act}"), act)
        self.actions_table.setCellWidget(row, 3, combo)

    def _add_action_row_data(self, action: ChainAction):
        """添加已有动作数据行"""
        row = self.actions_table.rowCount()
        self.actions_table.insertRow(row)
        self.actions_table.setItem(row, 0, QTableWidgetItem(action.target_peripheral))
        self.actions_table.setItem(row, 1, QTableWidgetItem(action.target_register))
        self.actions_table.setItem(row, 2, QTableWidgetItem(action.target_field))
        # 动作类型下拉框
        combo = QComboBox()
        for act in _ACTION_TYPES:
            combo.addItem(t(f"chain.action_{act}"), act)
        act_idx = _ACTION_TYPES.index(action.action) if action.action in _ACTION_TYPES else 0
        combo.setCurrentIndex(act_idx)
        self.actions_table.setCellWidget(row, 3, combo)

    def _del_action_row(self):
        """删除选中的动作行"""
        row = self.actions_table.currentRow()
        if row >= 0:
            self.actions_table.removeRow(row)

    def _collect_actions(self) -> list:
        """从表格收集动作列表"""
        actions = []
        for row in range(self.actions_table.rowCount()):
            periph = self.actions_table.item(row, 0)
            reg = self.actions_table.item(row, 1)
            field = self.actions_table.item(row, 2)
            combo = self.actions_table.cellWidget(row, 3)

            p_text = periph.text().strip() if periph else ""
            r_text = reg.text().strip() if reg else ""
            f_text = field.text().strip() if field else ""
            a_text = combo.currentData() if combo else "delete"

            if p_text or r_text:
                actions.append(ChainAction(
                    target_peripheral=p_text or "*",
                    target_register=r_text,
                    target_field=f_text,
                    action=a_text,
                ))
        return actions

    # ==================== 保存 ====================

    def _save(self):
        """保存当前编辑的规则"""
        if not self.engine:
            self.reject()
            return

        # 如果有选中的规则，先更新它
        if self._current_rule_index >= 0 and self._current_rule_index < len(self.engine.rules):
            actions = self._collect_actions()
            rule = ChainRule(
                name=self.name_edit.text() or t("chain.unnamed"),
                enabled=self.rule_enabled.isChecked(),
                source_type=self.source_type_combo.currentData() or "field",
                source_peripheral=self.source_periph.text(),
                source_register=self.source_reg.text(),
                source_field=self.source_field.text(),
                trigger=self.trigger_combo.currentData() or "delete",
                actions=actions,
            )
            self.engine.rules[self._current_rule_index] = rule
            # 更新列表显示
            item = self.rules_tree.topLevelItem(self._current_rule_index)
            if item:
                item.setText(0, rule.name)
                item.setText(1, t(f"chain.trigger_{rule.trigger}", default=rule.trigger))
                item.setText(2, "ON" if rule.enabled else "OFF")

        # 保存全局开关
        self.engine.enabled = self.global_toggle.isChecked()
        self.engine.save_rules()
        self.accept()

    # ==================== 批量生成 ====================

    def _batch_generate(self):
        """批量生成连锁规则（子对话框）"""
        if not self.engine:
            return

        _c = get_style_scheme().colors
        batch_dlg = QDialog(self)
        batch_dlg.setWindowTitle(t("chain.batch_generate"))
        batch_dlg.setMinimumSize(550, 520)
        batch_lay = QVBoxLayout(batch_dlg)

        # 模板选择
        tpl_group = QGroupBox(t("chain.load_template"))
        tpl_form = QFormLayout(tpl_group)
        tpl_combo = QComboBox()
        tpl_combo.addItems([t("chain.tpl_gpio_pin"), t("chain.tpl_custom")])
        tpl_form.addRow(t("chain.load_template"), tpl_combo)
        batch_lay.addWidget(tpl_group)

        # 参数
        param_group = QGroupBox(t("chain.params"))
        param_form = QFormLayout(param_group)

        source_pattern_edit = QLineEdit("GPIO*")
        param_form.addRow(t("chain.source_pattern"), source_pattern_edit)

        port_prefix_edit = QLineEdit("PA,PB,PC,PD,PE")
        param_form.addRow(t("chain.port_prefix"), port_prefix_edit)

        pin_start_spin = LabeledSlider()
        pin_start_spin.setRange(0, 31)
        pin_start_spin.setValue(0)
        pin_end_spin = LabeledSlider()
        pin_end_spin.setRange(0, 31)
        pin_end_spin.setValue(15)
        pin_range_w = QWidget()
        pin_range_lay = QHBoxLayout(pin_range_w)
        pin_range_lay.setContentsMargins(0, 0, 0, 0)
        pin_range_lay.addWidget(pin_start_spin)
        pin_range_lay.addWidget(QLabel("-"))
        pin_range_lay.addWidget(pin_end_spin)
        param_form.addRow(t("chain.pin_range"), pin_range_w)

        # 触发条件
        batch_trigger_combo = QComboBox()
        for trig in _TRIGGER_TYPES:
            batch_trigger_combo.addItem(t(f"chain.trigger_{trig}"), trig)
        param_form.addRow(t("chain.trigger_label"), batch_trigger_combo)

        batch_lay.addWidget(param_group)

        # 目标寄存器组
        target_group = QGroupBox(t("chain.target_groups"))
        target_lay = QVBoxLayout(target_group)
        target_groups_list = []
        target_rows_layout = QVBoxLayout()
        target_lay.addLayout(target_rows_layout)

        grp_btn_layout = QHBoxLayout()
        add_grp_btn = QPushButton(t("chain.add_group"))
        remove_grp_btn = QPushButton(t("chain.remove_group"))
        grp_btn_layout.addWidget(add_grp_btn)
        grp_btn_layout.addWidget(remove_grp_btn)
        grp_btn_layout.addStretch()
        target_lay.addLayout(grp_btn_layout)
        batch_lay.addWidget(target_group)

        # 预览
        preview_group = QGroupBox(t("batch.preview"))
        preview_lay = QVBoxLayout(preview_group)
        from PyQt6.QtWidgets import QListWidget, QListWidgetItem
        preview_list = QListWidget()
        preview_lay.addWidget(preview_list)
        batch_lay.addWidget(preview_group)

        count_label = QLabel("")
        batch_lay.addWidget(count_label)

        def refresh_preview():
            preview_list.clear()
            prefixes = [p.strip() for p in port_prefix_edit.text().split(",") if p.strip()]
            start_pin = pin_start_spin.value()
            end_pin = pin_end_spin.value()
            rules_count = 0
            for prefix in prefixes:
                for pin in range(start_pin, end_pin + 1):
                    name = f"{prefix}{pin}"
                    port = prefix
                    targets = []
                    for reg_edit, field_edit, _ in target_groups_list:
                        reg_suffix = reg_edit.text().strip()
                        field_pfx = field_edit.text().strip()
                        if reg_suffix:
                            reg_name = f"{port}{reg_suffix}"
                            field_name = f"{field_pfx}{pin}" if field_pfx else ""
                            targets.append(f"{reg_name}.{field_name}" if field_name else reg_name)
                    if targets:
                        trigger = batch_trigger_combo.currentData() or "delete"
                        preview_list.addItem(
                            t("chain.preview_action",
                              name=name, trigger=trigger, targets=", ".join(targets)))
                    rules_count += 1
            count_label.setText(t("chain.total_rules", count=rules_count))

        # 信号
        port_prefix_edit.textChanged.connect(refresh_preview)
        pin_start_spin.valueChanged.connect(refresh_preview)
        pin_end_spin.valueChanged.connect(refresh_preview)
        batch_trigger_combo.currentIndexChanged.connect(refresh_preview)

        def add_target_group(reg_suffix="", field_prefix=""):
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 2, 0, 2)
            row_layout.addWidget(QLabel(t("chain.reg_suffix")))
            reg_edit = QLineEdit(reg_suffix)
            reg_edit.setMaximumWidth(80)
            row_layout.addWidget(reg_edit)
            row_layout.addWidget(QLabel(t("chain.field_prefix")))
            field_edit = QLineEdit(field_prefix)
            field_edit.setMaximumWidth(80)
            row_layout.addWidget(field_edit)
            target_groups_list.append((reg_edit, field_edit, row_widget))
            target_rows_layout.addWidget(row_widget)
            reg_edit.textChanged.connect(refresh_preview)
            field_edit.textChanged.connect(refresh_preview)
            refresh_preview()

        def remove_target_group():
            if target_groups_list:
                _, _, row_widget = target_groups_list.pop()
                target_rows_layout.removeWidget(row_widget)
                row_widget.deleteLater()
                refresh_preview()

        def on_template_changed():
            while target_groups_list:
                _, _, row_widget = target_groups_list.pop()
                target_rows_layout.removeWidget(row_widget)
                row_widget.deleteLater()
            idx = tpl_combo.currentIndex()
            if idx == 0:  # GPIO
                source_pattern_edit.setText("GPIO*")
                port_prefix_edit.setText("PA,PB,PC,PD,PE")
                pin_start_spin.setValue(0)
                pin_end_spin.setValue(15)
                add_target_group("CON", "MODE")
                add_target_group("PH", "PUPD")
                add_target_group("VEV", "LEV")
            else:
                source_pattern_edit.setText("*")
                port_prefix_edit.setText("")
                add_target_group()

        tpl_combo.currentIndexChanged.connect(on_template_changed)
        add_grp_btn.clicked.connect(lambda: add_target_group())
        remove_grp_btn.clicked.connect(remove_target_group)

        # 初始
        add_target_group("CON", "MODE")
        add_target_group("PH", "PUPD")
        add_target_group("VEV", "LEV")
        refresh_preview()

        # 按钮
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(batch_dlg.accept)
        btn_box.rejected.connect(batch_dlg.reject)
        batch_lay.addWidget(btn_box)

        if batch_dlg.exec() == QDialog.DialogCode.Accepted:
            prefixes = [p.strip() for p in port_prefix_edit.text().split(",") if p.strip()]
            start_pin = pin_start_spin.value()
            end_pin = pin_end_spin.value()
            src_pattern = source_pattern_edit.text().strip() or "*"
            trigger = batch_trigger_combo.currentData() or "delete"
            generated = 0

            for prefix in prefixes:
                for pin in range(start_pin, end_pin + 1):
                    name = f"{prefix}{pin}"
                    port = prefix

                    actions = []
                    for reg_edit, field_edit, _ in target_groups_list:
                        reg_suffix = reg_edit.text().strip()
                        field_pfx = field_edit.text().strip()
                        if reg_suffix:
                            reg_name = f"{port}{reg_suffix}"
                            field_name = f"{field_pfx}{pin}" if field_pfx else ""
                            actions.append(ChainAction(
                                target_peripheral="*",
                                target_register=reg_name,
                                target_field=field_name,
                                action=trigger,
                                description=f"{trigger} {reg_name}.{field_name}"
                            ))

                    if not actions:
                        continue

                    rule = ChainRule(
                        name=t("chain.rule_name_action",
                               trigger=t(f"chain.trigger_{trigger}", default=trigger),
                               name=name),
                        enabled=True,
                        source_type="field",
                        source_peripheral=src_pattern,
                        source_register="*" + name,
                        source_field=name,
                        trigger=trigger,
                        actions=actions
                    )
                    self.engine.add_rule(rule)
                    self._add_rule_item(rule)
                    generated += 1

            self.engine.save_rules()
            self._update_rule_count()
            QMessageBox.information(self, t("batch.complete"),
                                    t("batch.modify_success", count=generated))
