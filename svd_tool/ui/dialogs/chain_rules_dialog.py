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
from ...core.constants import ACCESS_OPTIONS
from ...config.styles import get_style_scheme
from ...i18n.i18n import t
from ..widgets.toggle_switch import ToggleSwitch
from ..widgets.labeled_slider import LabeledSlider

logger = logging.getLogger("ChainRulesDialog")

# 目标操作选项
_OPERATION_TYPES = ["delete", "modify", "add"]
_TRIGGER_TYPES = ["delete", "modify", "add"]

# 目标层级（决定可选属性集合）
_TARGET_LAYERS = ["field", "register", "peripheral"]

# 各层级可修改的属性名（与 data_model 字段对应）
_PROPS_BY_LAYER: dict = {
    "field": [
        "access", "description", "display_name", "reset_value",
        "bit_offset", "bit_width", "name",
    ],
    "register": [
        "access", "description", "display_name", "reset_value",
        "reset_mask", "size", "offset", "name",
    ],
    "peripheral": [
        "description", "display_name", "group_name",
        "base_address", "name",
    ],
}

# access 属性的合法枚举值（去掉首项"无"，来自 core/constants.py 的 ACCESS_OPTIONS）
_ACCESS_VALUES = [v for v in ACCESS_OPTIONS if v and v != "无"]

# 枚举值 → i18n 键 的映射（用于值下拉框的本地化显示）
_ACCESS_I18N_KEYS = {
    "read-write": "access.read_write",
    "read-only": "access.read_only",
    "write-only": "access.write_only",
    "writeOnce": "access.write_once",
    "read-writeOnce": "access.read_write_once",
}


class ChainRulesDialog(QDialog):
    """连锁规则编辑对话框"""

    def __init__(self, parent=None, engine=None):
        super().__init__(parent)
        self.engine = engine
        self._current_rule_index: int = -1
        # 行级控件引用：row -> {"prop": QComboBox, "container": QWidget, "value_holder": QWidget}
        # value_holder 随属性类型在 QLineEdit/QComboBox 间切换
        self._row_widgets: dict = {}

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

        # 注：全局总开关（engine.enabled）由主窗口菜单"工具→启用连锁操作"控制，
        # 此处不再重复放置 global_toggle，避免与菜单入口功能重复、让人困惑。
        # 单条规则的启用状态由下方"规则配置"区的 rule_enabled 开关控制。

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
            t("chain.col_name"), t("chain.col_trigger")
        ])
        header = self.rules_tree.header()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
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

        # --- 源 ---
        source_hint = QLabel(t("label.source") + "  (" + t("label.no_limit_layer") + ")")
        source_hint.setStyleSheet(f"color: {_c.text_secondary}; font-size: 9pt;")
        config_form.addRow(source_hint)

        self.source_periph = QLineEdit()
        self.source_periph.setPlaceholderText(t("chain.wildcard_hint"))
        config_form.addRow(t("label.source_peripheral"), self.source_periph)

        self.source_reg = QLineEdit()
        self.source_reg.setPlaceholderText(t("chain.no_limit"))
        config_form.addRow(t("label.source_register"), self.source_reg)

        self.source_field = QLineEdit()
        self.source_field.setPlaceholderText(t("chain.no_limit"))
        config_form.addRow(t("label.source_field"), self.source_field)

        # --- 触发条件 ---
        self.trigger_combo = QComboBox()
        for trig in _TRIGGER_TYPES:
            self.trigger_combo.addItem(t(f"chain.trigger_{trig}"), trig)
        config_form.addRow(t("chain.trigger_label"), self.trigger_combo)

        self.rule_enabled = ToggleSwitch(t("label.enabled"))
        self.rule_enabled.setChecked(True)
        config_form.addRow(self.rule_enabled)

        right_layout.addWidget(config_group)

        # 目标操作组
        actions_group = QGroupBox(t("label.target"))
        actions_layout = QVBoxLayout(actions_group)
        actions_layout.setContentsMargins(8, 20, 8, 8)
        actions_layout.setSpacing(6)

        # 5列：目标外设 | 目标寄存器 | 目标位域 | 目标操作 | 属性+值
        # （原"属性"和"值"两列合并为一列，内嵌属性下拉+值输入控件）
        self.actions_table = QTableWidget(0, 5)
        self.actions_table.setHorizontalHeaderLabels([
            t("chain.col_target_periph"),
            t("chain.col_target_reg"),
            t("chain.col_target_field"),
            t("chain.col_operation"),
            t("chain.col_property") + " / " + t("chain.col_value"),
        ])
        act_header = self.actions_table.horizontalHeader()
        if act_header:
            # 目标外设/寄存器/位域：可交互拉伸，均分剩余空间
            # 目标外设/寄存器/位域：Interactive（初始宽度固定，用户可拖拽调整）。
            # 不用 Stretch：这三个名字通常较短，给固定较窄宽度可把空间让给第4列
            # （属性+值），避免第4列装两个下拉框时溢出重叠。
            for col in (0, 1, 2):
                act_header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            self.actions_table.setColumnWidth(0, 110)
            self.actions_table.setColumnWidth(1, 110)
            self.actions_table.setColumnWidth(2, 110)
            # 目标操作：下拉框，按内容自适应
            act_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            # 属性+值：拉伸填充，吃掉前3列让出的所有剩余空间
            act_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
            # 给下拉框列设最小宽度，避免中文表头被压扁
            act_header.setMinimumSectionSize(90)
        self.actions_table.setAlternatingRowColors(True)
        self.actions_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.actions_table.verticalHeader().setVisible(False)
        self.actions_table.cellChanged.connect(self._on_action_cell_changed)
        # 统一行高：40px 给下拉框留足垂直空间，避免下边缘被单元格裁切
        self.actions_table.verticalHeader().setDefaultSectionSize(40)
        self.actions_table.setMinimumHeight(160)
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

        self.source_periph.setText(rule.source_peripheral)
        self.source_reg.setText(rule.source_register)
        self.source_field.setText(rule.source_field)
        self.rule_enabled.setChecked(rule.enabled)

        # 填充动作表格（清空时同步清理行级控件引用 dict）
        self.actions_table.setRowCount(0)
        self._row_widgets = {}
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

    def _detect_target_layer(self, periph: str, reg: str, field: str) -> str:
        """根据填了哪些目标层推断层级，用于选择可用属性集合"""
        if field.strip():
            return "field"
        if reg.strip():
            return "register"
        if periph.strip():
            return "peripheral"
        return "field"

    def _make_property_combo(self, layer: str, current_prop: str = "") -> QComboBox:
        """构造属性下拉框（按目标层过滤可选属性）"""
        combo = QComboBox()
        # AdjustToContents 让宽度按最长选项自适应（避免"访问"截断成"访讧"），
        # 但必须设上限：否则"访问权限"等长选项会把下拉框撑得过宽，
        # 在列宽不足时溢出并与右侧值控件重叠。设最大宽度兜底。
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        combo.setMinimumWidth(90)
        combo.setMaximumWidth(140)
        combo.addItem("", "")
        for prop in _PROPS_BY_LAYER.get(layer, []):
            combo.addItem(t(f"chain.prop_{prop}", default=prop), prop)
        if current_prop:
            idx = combo.findData(current_prop)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        return combo

    def _make_operation_combo(self, current_op: str = "delete") -> QComboBox:
        """构造目标操作下拉框"""
        combo = QComboBox()
        for op in _OPERATION_TYPES:
            combo.addItem(t(f"chain.operation_{op}", default=t(f"chain.action_{op}", default=op)), op)
        idx = _OPERATION_TYPES.index(current_op) if current_op in _OPERATION_TYPES else 0
        combo.setCurrentIndex(idx)
        return combo

    def _refresh_row_editability(self, row: int):
        """根据目标操作类型刷新属性+值列的可用状态。

        语义：仅 modify 需要属性；modify 和 add 都需要值；delete 都不需要。
        实现上对第 4 列容器内的属性下拉单独控制（仅 modify 启用），
        对值控件按 modify/add 启用、delete 禁用。
        """
        op_combo = self.actions_table.cellWidget(row, 3)
        widgets = self._row_widgets.get(row)
        if not op_combo or not widgets:
            return
        op = op_combo.currentData() or "delete"
        prop_combo = widgets.get("prop")
        value_holder = widgets.get("value_holder")
        # 属性下拉：仅 modify 启用
        if prop_combo:
            prop_combo.setEnabled(op == "modify")
        # 值控件：modify / add 启用，delete 禁用
        if value_holder:
            value_holder.setEnabled(op in ("modify", "add"))

    def _on_action_cell_changed(self, row: int, col: int):
        """当动作表格单元格内容变化时，刷新对应行的属性可选项"""
        if col in (0, 1, 2):  # 目标外设、寄存器、位域列
            self._refresh_row_property_options(row)

    def _refresh_row_property_options(self, row: int):
        """根据当前填写的目标层，刷新属性下拉可选项"""
        periph = self.actions_table.item(row, 0)
        reg = self.actions_table.item(row, 1)
        field = self.actions_table.item(row, 2)
        p_text = periph.text() if periph else ""
        r_text = reg.text() if reg else ""
        f_text = field.text() if field else ""
        layer = self._detect_target_layer(p_text, r_text, f_text)

        widgets = self._row_widgets.get(row)
        if not widgets:
            return
        prop_combo = widgets.get("prop")
        if not isinstance(prop_combo, QComboBox):
            return
        # 保留当前选中值
        current_prop = prop_combo.currentData() or ""
        # 重建可选项（屏蔽信号，避免触发值控件误切换）
        prop_combo.blockSignals(True)
        prop_combo.clear()
        prop_combo.addItem("", "")
        for prop in _PROPS_BY_LAYER.get(layer, []):
            prop_combo.addItem(t(f"chain.prop_{prop}", default=prop), prop)
        idx = prop_combo.findData(current_prop)
        prop_combo.setCurrentIndex(idx if idx >= 0 else 0)
        prop_combo.blockSignals(False)

    def _make_value_holder(self, prop: str, current_value: str = "") -> QWidget:
        """构造值控件：access 属性用下拉框，其余用文本框。

        返回的控件引用记入 _row_widgets[row]["value_holder"]，类型可能是
        QComboBox 或 QLineEdit，由 _get_row_value 统一取值。
        """
        if prop == "access":
            combo = QComboBox()
            # 自适应内容宽度（避免"读写一次"截断），但设上限防溢出重叠
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
            combo.setMaximumWidth(110)
            for v in _ACCESS_VALUES:
                i18n_key = _ACCESS_I18N_KEYS.get(v)
                label = t(i18n_key, default=v) if i18n_key else v
                combo.addItem(label, v)
            if current_value:
                idx = combo.findData(current_value)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            return combo
        else:
            edit = QLineEdit(current_value)
            # 不设 placeholder：删除操作禁用时，灰显的"值"占位文字会显得像"缺一块空白"，
            # 干净的空文本框禁用后视觉更清晰。
            return edit

    def _refresh_row_value_input(self, row: int):
        """属性下拉变化时，按属性类型重建值控件。

        值保留策略：仅在同类控件（下拉↔下拉 / 文本框↔文本框）间切换时
        保留旧值；跨类型切换（如下拉→文本框）时清空，避免枚举值
        （如 read-only）作为自由文本残留。
        """
        widgets = self._row_widgets.get(row)
        if not widgets:
            return
        prop_combo = widgets.get("prop")
        container = widgets.get("container")
        old_holder = widgets.get("value_holder")
        layout = container.layout() if container else None
        if not prop_combo or not container or layout is None:
            return

        new_prop = prop_combo.currentData() or ""
        old_is_combo = isinstance(old_holder, QComboBox)
        new_is_combo = (new_prop == "access")
        # 仅当新旧控件同为下拉或同为文本框时才保留值
        if old_holder is not None and (old_is_combo == new_is_combo):
            old_value = self._get_widget_value(old_holder)
        else:
            old_value = ""

        new_holder = self._make_value_holder(new_prop, old_value)

        # 替换布局里的值控件（index=1，属性下拉是 index=0）
        if old_holder is not None:
            layout.removeWidget(old_holder)
            old_holder.deleteLater()
        layout.addWidget(new_holder)
        widgets["value_holder"] = new_holder

        # 继承当前的启用状态（操作类型决定）
        self._refresh_row_editability(row)

    @staticmethod
    def _get_widget_value(widget: Optional[QWidget]) -> str:
        """统一从值控件取值（QComboBox→currentData，QLineEdit→text）"""
        if isinstance(widget, QComboBox):
            return widget.currentData() or ""
        if isinstance(widget, QLineEdit):
            return widget.text()
        return ""

    def _make_property_value_widget(self, row: int, layer: str,
                                    current_prop: str = "", current_value: str = "") -> QWidget:
        """构造第 4 列「属性 + 值」合并容器。

        布局：[属性下拉] [值控件]
        值控件类型随属性变化（access→下拉，其它→文本框），
        由 prop_combo.currentIndexChanged -> _refresh_row_value_input 驱动切换。
        控件引用记入 self._row_widgets[row]，便于后续取值/重建。
        """
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.setContentsMargins(2, 0, 2, 0)
        lay.setSpacing(8)  # 属性下拉与值控件之间的间隔

        prop_combo = self._make_property_combo(layer, current_prop)
        # 注意：currentIndexChanged 会把 index 作为位置参数传给槽，
        # 不能用 lambda _r=row:（会被信号参数覆盖），需用 *_ 吞掉信号参数
        prop_combo.currentIndexChanged.connect(lambda *_, _r=row: self._refresh_row_value_input(_r))
        lay.addWidget(prop_combo, stretch=0)  # 属性下拉按内容宽，不拉伸

        value_holder = self._make_value_holder(current_prop, current_value)
        lay.addWidget(value_holder, stretch=1)  # 值控件吃剩余空间

        self._row_widgets[row] = {
            "prop": prop_combo,
            "container": container,
            "value_holder": value_holder,
        }
        return container

    def _add_action_row(self):
        """添加一个空动作行"""
        row = self.actions_table.rowCount()
        self.actions_table.insertRow(row)
        self.actions_table.setItem(row, 0, QTableWidgetItem(""))
        self.actions_table.setItem(row, 1, QTableWidgetItem(""))
        self.actions_table.setItem(row, 2, QTableWidgetItem(""))

        # 目标操作下拉
        op_combo = self._make_operation_combo("delete")
        # 用 *_ 吞掉 currentIndexChanged 传来的 index 参数（详见 _make_property_value_widget 注释）
        op_combo.currentIndexChanged.connect(lambda *_, _r=row: self._refresh_row_editability(_r))
        self.actions_table.setCellWidget(row, 3, op_combo)

        # 第 4 列：属性 + 值 合并容器（默认 field 层）
        pv_widget = self._make_property_value_widget(row, "field")
        self.actions_table.setCellWidget(row, 4, pv_widget)

        self._refresh_row_editability(row)

    def _add_action_row_data(self, action: ChainAction):
        """添加已有动作数据行"""
        row = self.actions_table.rowCount()
        self.actions_table.insertRow(row)
        # 填充文本单元格时屏蔽 cellChanged，避免逐格触发属性下拉重建
        self.actions_table.blockSignals(True)
        try:
            self.actions_table.setItem(row, 0, QTableWidgetItem(action.target_peripheral))
            self.actions_table.setItem(row, 1, QTableWidgetItem(action.target_register))
            self.actions_table.setItem(row, 2, QTableWidgetItem(action.target_field))
        finally:
            self.actions_table.blockSignals(False)

        # 目标操作下拉
        op_combo = self._make_operation_combo(action.operation or "delete")
        op_combo.currentIndexChanged.connect(lambda *_, _r=row: self._refresh_row_editability(_r))
        self.actions_table.setCellWidget(row, 3, op_combo)

        # 第 4 列：属性 + 值 合并容器（按已填目标层确定属性可选项）
        layer = self._detect_target_layer(action.target_peripheral, action.target_register, action.target_field)
        pv_widget = self._make_property_value_widget(
            row, layer, action.property_name, action.value)
        self.actions_table.setCellWidget(row, 4, pv_widget)

        self._refresh_row_editability(row)

    def _del_action_row(self):
        """删除选中的动作行（按当前选中行）"""
        row = self.actions_table.currentRow()
        if row >= 0:
            self._remove_action_row(row)

    def _remove_action_row(self, row: int):
        """删除指定行并清理行级控件引用 dict。

        removeRow 会让后续行的行号前移，_row_widgets 的键也要同步重排，
        否则行号错位会导致后续操作（取值/重建）打到错误的行。
        """
        self.actions_table.removeRow(row)
        # 删除被移除行的引用，并把后续行号前移
        if row in self._row_widgets:
            del self._row_widgets[row]
        shifted = {}
        for r, w in self._row_widgets.items():
            shifted[r - 1 if r > row else r] = w
        self._row_widgets = shifted

    def _collect_actions(self) -> list:
        """从表格收集动作列表"""
        actions = []
        for row in range(self.actions_table.rowCount()):
            periph = self.actions_table.item(row, 0)
            reg = self.actions_table.item(row, 1)
            field = self.actions_table.item(row, 2)
            op_combo = self.actions_table.cellWidget(row, 3)
            widgets = self._row_widgets.get(row, {})

            p_text = periph.text().strip() if periph else ""
            r_text = reg.text().strip() if reg else ""
            f_text = field.text().strip() if field else ""
            op_text = op_combo.currentData() if op_combo else "delete"
            prop_combo = widgets.get("prop")
            value_holder = widgets.get("value_holder")
            prop_text = prop_combo.currentData() if isinstance(prop_combo, QComboBox) else ""
            v_text = self._get_widget_value(value_holder).strip() if value_holder else ""

            # 至少要有一个目标层
            if p_text or r_text or f_text:
                actions.append(ChainAction(
                    target_peripheral=p_text or "*",
                    target_register=r_text,
                    target_field=f_text,
                    operation=op_text,
                    property_name=prop_text,
                    value=v_text,
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

        # 保存规则（全局 enabled 状态由主窗口菜单维护，此处不改）
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
            row_layout.setContentsMargins(0, 3, 0, 3)
            row_layout.addWidget(QLabel(t("chain.reg_suffix")))
            reg_edit = QLineEdit(reg_suffix)
            reg_edit.setMaximumWidth(80)
            # 用 padding 撑高而非 minimumHeight：后者会把内容区填满，
            # 导致原生样式的 1px 下边框（下划线）被挤出可绘制区域而被裁切。
            # padding 给文字留垂直空间的同时，边框仍完整保留在控件边界内。
            reg_edit.setStyleSheet("QLineEdit { padding: 3px 4px; }")
            row_layout.addWidget(reg_edit)
            row_layout.addWidget(QLabel(t("chain.field_prefix")))
            field_edit = QLineEdit(field_prefix)
            field_edit.setMaximumWidth(80)
            field_edit.setStyleSheet("QLineEdit { padding: 3px 4px; }")
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
        btn_box.button(QDialogButtonBox.StandardButton.Ok).setText(t("button.ok"))
        btn_box.button(QDialogButtonBox.StandardButton.Cancel).setText(t("button.cancel"))
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
                                operation=trigger,
                                description=f"{trigger} {reg_name}.{field_name}"
                            ))

                    if not actions:
                        continue

                    rule = ChainRule(
                        name=t("chain.rule_name_action",
                               trigger=t(f"chain.trigger_{trigger}", default=trigger),
                               name=name),
                        enabled=True,
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
