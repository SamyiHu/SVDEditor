"""
标签页构建器
负责创建各个标签页
"""
import sys
import logging
from typing import Dict, Any, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel,
    QLineEdit, QPushButton, QGroupBox, QSplitter,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QTextEdit,
    QTableWidget, QTableWidgetItem, QComboBox, QSpinBox,
    QFormLayout, QGridLayout, QFrame
)
from PyQt6.QtCore import Qt
from ...i18n.i18n import t
from ...config.styles import get_style_scheme
from ...config.tree_branch_style import apply_tree_branch_style
from ..widgets.toggle_switch import ToggleSwitch
from ..widgets.labeled_slider import LabeledSlider


class TabBuilder:
    """标签页构建器"""

    def __init__(self, main_window):
        self.main_window = main_window
        self.logger = logging.getLogger("TabBuilder")

    def create_basic_info_tab(self, tab_widget: QTabWidget) -> tuple:
        """创建基础信息标签页（优化版）"""
        self.logger.debug("create_basic_info_tab开始")
        try:
            tab = QWidget()
            layout = QVBoxLayout(tab)
            layout.setSpacing(10)
            layout.setContentsMargins(16, 12, 16, 12)

            # === 设备信息组 ===
            device_group = QGroupBox(t("label.basic_info"))
            device_layout = QGridLayout(device_group)
            device_layout.setSpacing(8)
            device_layout.setContentsMargins(16, 22, 16, 16)

            # 统一标签宽度
            label_fixed_width = 100

            # 第一行：IC型号和描述
            ic_model_label = QLabel(t("label.ic_model") + ":")
            ic_model_label.setFixedWidth(label_fixed_width)
            ic_model_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            device_layout.addWidget(ic_model_label, 0, 0)
            ic_name_edit = QLineEdit()
            ic_name_edit.setPlaceholderText(t("placeholder.ic_model"))
            device_layout.addWidget(ic_name_edit, 0, 1)

            ic_desc_label = QLabel(t("label.ic_description") + ":")
            ic_desc_label.setFixedWidth(label_fixed_width)
            ic_desc_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            device_layout.addWidget(ic_desc_label, 0, 2)
            ic_desc_edit = QLineEdit()
            ic_desc_edit.setPlaceholderText(t("placeholder.ic_description"))
            device_layout.addWidget(ic_desc_edit, 0, 3)

            # 第二行：版本和SVD版本
            version_label = QLabel(t("label.version") + ":")
            version_label.setFixedWidth(label_fixed_width)
            version_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            device_layout.addWidget(version_label, 1, 0)
            version_edit = QLineEdit()
            version_edit.setPlaceholderText(t("placeholder.version"))
            device_layout.addWidget(version_edit, 1, 1)

            svd_version_label = QLabel(t("label.svd_version") + ":")
            svd_version_label.setFixedWidth(label_fixed_width)
            svd_version_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            device_layout.addWidget(svd_version_label, 1, 2)
            svd_version_combo = QComboBox()
            svd_version_combo.addItems(["1.0", "1.1", "1.2", "1.3", "1.3.1"])
            svd_version_combo.setCurrentText("1.3")
            device_layout.addWidget(svd_version_combo, 1, 3)

            # 第三行：CPU名称和修订版
            cpu_name_label = QLabel(t("label.cpu_name") + ":")
            cpu_name_label.setFixedWidth(label_fixed_width)
            cpu_name_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            device_layout.addWidget(cpu_name_label, 2, 0)
            cpu_name_edit = QLineEdit()
            cpu_name_edit.setPlaceholderText(t("placeholder.cpu_name"))
            device_layout.addWidget(cpu_name_edit, 2, 1)

            cpu_rev_label = QLabel(t("label.cpu_revision") + ":")
            cpu_rev_label.setFixedWidth(label_fixed_width)
            cpu_rev_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            device_layout.addWidget(cpu_rev_label, 2, 2)
            cpu_rev_edit = QLineEdit()
            cpu_rev_edit.setPlaceholderText(t("placeholder.cpu_revision"))
            device_layout.addWidget(cpu_rev_edit, 2, 3)

            # 第四行：端序和MPU
            endian_label = QLabel(t("label.endian") + ":")
            endian_label.setFixedWidth(label_fixed_width)
            endian_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            device_layout.addWidget(endian_label, 3, 0)
            endian_combo = QComboBox()
            endian_combo.addItems([t("value.little"), t("value.big"), t("value.selectable")])
            endian_combo.setCurrentText(t("value.little"))
            device_layout.addWidget(endian_combo, 3, 1)

            mpu_label = QLabel(t("label.mpu_exists") + ":")
            mpu_label.setFixedWidth(label_fixed_width)
            mpu_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            device_layout.addWidget(mpu_label, 3, 2)
            mpu_combo = ToggleSwitch()
            device_layout.addWidget(mpu_combo, 3, 3)

            # 第五行：FPU和NVIC优先级位数
            fpu_label = QLabel(t("label.fpu_exists") + ":")
            fpu_label.setFixedWidth(label_fixed_width)
            fpu_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            device_layout.addWidget(fpu_label, 4, 0)
            fpu_combo = ToggleSwitch()
            device_layout.addWidget(fpu_combo, 4, 1)

            nvic_label = QLabel(t("label.nvic_prio_bits") + ":")
            nvic_label.setFixedWidth(label_fixed_width)
            nvic_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            device_layout.addWidget(nvic_label, 4, 2)
            nvic_prio_spin = LabeledSlider()
            nvic_prio_spin.setRange(0, 8)
            nvic_prio_spin.setValue(4)
            device_layout.addWidget(nvic_prio_spin, 4, 3)

            device_layout.setColumnStretch(1, 1)
            device_layout.setColumnStretch(3, 1)
            layout.addWidget(device_group)

            # === 公司版权信息组（留空则不写入SVD） ===
            company_group = QGroupBox(t("label.company_copyright"))
            company_layout = QGridLayout(company_group)
            company_layout.setSpacing(8)
            company_layout.setContentsMargins(16, 22, 16, 16)

            # 公司名
            company_name_label = QLabel(t("label.company_name") + ":")
            company_name_label.setFixedWidth(label_fixed_width)
            company_name_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            company_layout.addWidget(company_name_label, 0, 0)
            company_name_edit = QLineEdit()
            company_name_edit.setPlaceholderText(t("placeholder.company_name"))
            company_layout.addWidget(company_name_edit, 0, 1)

            # 版权
            copyright_label = QLabel(t("label.copyright_info") + ":")
            copyright_label.setFixedWidth(label_fixed_width)
            copyright_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            company_layout.addWidget(copyright_label, 0, 2)
            copyright_edit = QLineEdit()
            copyright_edit.setPlaceholderText(t("placeholder.copyright_info"))
            company_layout.addWidget(copyright_edit, 0, 3)

            # 作者
            author_label = QLabel(t("label.author") + ":")
            author_label.setFixedWidth(label_fixed_width)
            author_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            company_layout.addWidget(author_label, 1, 0)
            author_edit = QLineEdit()
            author_edit.setPlaceholderText(t("placeholder.author"))
            company_layout.addWidget(author_edit, 1, 1)

            # 许可证
            license_label = QLabel(t("label.license") + ":")
            license_label.setFixedWidth(label_fixed_width)
            license_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            company_layout.addWidget(license_label, 1, 2)
            license_combo = QComboBox()
            license_combo.addItems([
                t("license.do_not_display"), t("license.apache_2_0"),
                t("license.mit"), t("license.bsd_3_clause"),
                t("license.proprietary"), t("license.other")
            ])
            license_combo.setCurrentText(t("license.apache_2_0"))
            company_layout.addWidget(license_combo, 1, 3)

            company_layout.setColumnStretch(1, 1)
            company_layout.setColumnStretch(3, 1)
            layout.addWidget(company_group)

            # === 数据汇总组 ===
            summary_group = QGroupBox(t("label.data_summary"))
            summary_outer = QVBoxLayout(summary_group)
            summary_outer.setSpacing(8)
            summary_outer.setContentsMargins(12, 20, 12, 12)

            _scheme = get_style_scheme()
            _c = _scheme.colors

            # 筛选行
            filter_row = QHBoxLayout()
            filter_row.setSpacing(8)

            filter_label = QLabel(t("label.filter_periph", default="筛选外设:"))
            filter_label.setStyleSheet(f"color: {_c.text_secondary}; font-size: 9pt;")
            filter_row.addWidget(filter_label)

            periph_filter_combo = QComboBox()
            periph_filter_combo.addItem(t("value.all", default="全部"), "__all__")
            periph_filter_combo.setMinimumWidth(160)
            periph_filter_combo.setFixedHeight(28)
            filter_row.addWidget(periph_filter_combo)
            filter_row.addStretch()
            summary_outer.addLayout(filter_row)

            # 卡片行
            summary_layout = QHBoxLayout()
            summary_layout.setSpacing(16)

            card_style = """
                QFrame {
                    background-color: %s;
                    border-radius: 8px;
                    padding: 8px;
                    min-width: 80px;
                }
                QLabel {
                    background: transparent;
                    border: none;
                    padding: 0px;
                }
            """

            # 外设卡片
            periph_card = QFrame()
            periph_card.setStyleSheet(card_style % _c.card_periph_background)
            pcl = QVBoxLayout(periph_card)
            pcl.setSpacing(2)
            pcl.setContentsMargins(10, 6, 10, 6)
            periph_count_label = QLabel("0")
            periph_count_label.setStyleSheet(f"font-size: 22pt; font-weight: bold; color: {_c.card_periph_count_color};")
            periph_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pcl.addWidget(periph_count_label)
            ptl = QLabel(t("label.total_peripherals"))
            ptl.setStyleSheet(f"font-size: 8pt; color: {_c.card_periph_label_color};")
            ptl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pcl.addWidget(ptl)
            summary_layout.addWidget(periph_card)

            # 寄存器卡片
            reg_card = QFrame()
            reg_card.setStyleSheet(card_style % _c.card_reg_background)
            rcl = QVBoxLayout(reg_card)
            rcl.setSpacing(2)
            rcl.setContentsMargins(10, 6, 10, 6)
            reg_count_label = QLabel("0")
            reg_count_label.setStyleSheet(f"font-size: 22pt; font-weight: bold; color: {_c.card_reg_count_color};")
            reg_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rcl.addWidget(reg_count_label)
            rtl = QLabel(t("label.total_registers"))
            rtl.setStyleSheet(f"font-size: 8pt; color: {_c.card_reg_label_color};")
            rtl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rcl.addWidget(rtl)
            summary_layout.addWidget(reg_card)

            # 位域卡片
            field_card = QFrame()
            field_card.setStyleSheet(card_style % _c.card_field_background)
            fcl = QVBoxLayout(field_card)
            fcl.setSpacing(2)
            fcl.setContentsMargins(10, 6, 10, 6)
            field_count_label = QLabel("0")
            field_count_label.setStyleSheet(f"font-size: 22pt; font-weight: bold; color: {_c.card_field_count_color};")
            field_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fcl.addWidget(field_count_label)
            ftl = QLabel(t("label.total_fields"))
            ftl.setStyleSheet(f"font-size: 8pt; color: {_c.card_field_label_color};")
            ftl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fcl.addWidget(ftl)
            summary_layout.addWidget(field_card)

            # 中断卡片
            irq_card = QFrame()
            irq_card.setStyleSheet(card_style % _c.card_irq_background)
            icl = QVBoxLayout(irq_card)
            icl.setSpacing(2)
            icl.setContentsMargins(10, 6, 10, 6)
            irq_count_label = QLabel("0")
            irq_count_label.setStyleSheet(f"font-size: 22pt; font-weight: bold; color: {_c.card_irq_count_color};")
            irq_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icl.addWidget(irq_count_label)
            itl = QLabel(t("label.total_interrupts"))
            itl.setStyleSheet(f"font-size: 8pt; color: {_c.card_irq_label_color};")
            itl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icl.addWidget(itl)
            summary_layout.addWidget(irq_card)

            summary_outer.addLayout(summary_layout)
            layout.addWidget(summary_group)
            layout.addStretch(1)

            self.logger.debug(f"调用addTab前，标签页数量: {tab_widget.count()}")
            index = tab_widget.addTab(tab, t("tab.basic_info_tab"))
            self.logger.debug(f"addTab返回索引: {index}，标签页数量: {tab_widget.count()}")

            widgets = {
                'basic_info_tab': tab,
                'ic_name_edit': ic_name_edit,
                'ic_desc_edit': ic_desc_edit,
                'version_edit': version_edit,
                'svd_version_combo': svd_version_combo,
                'cpu_name_edit': cpu_name_edit,
                'cpu_rev_edit': cpu_rev_edit,
                'endian_combo': endian_combo,
                'mpu_combo': mpu_combo,
                'fpu_combo': fpu_combo,
                'nvic_prio_spin': nvic_prio_spin,
                'company_name_edit': company_name_edit,
                'copyright_edit': copyright_edit,
                'author_edit': author_edit,
                'license_combo': license_combo,
                'periph_count_label': periph_count_label,
                'reg_count_label': reg_count_label,
                'field_count_label': field_count_label,
                'irq_count_label': irq_count_label,
                'data_summary_filter': periph_filter_combo,
            }
            return tab, widgets

        except Exception as e:
            self.logger.error(f"create_basic_info_tab异常: {e}")
            import traceback
            traceback.print_exc()
            raise

    def create_peripheral_tab(self, tab_widget: QTabWidget) -> tuple:
        """创建外设标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：外设树
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        periph_toolbar = QHBoxLayout()
        add_periph_btn = QPushButton(t("button.add_peripheral"))
        add_periph_btn.setToolTip(t("tooltip.add_peripheral"))
        periph_toolbar.addWidget(add_periph_btn)
        add_reg_btn = QPushButton(t("button.add_register"))
        add_reg_btn.setEnabled(False)
        add_reg_btn.setToolTip(t("tooltip.add_register"))
        periph_toolbar.addWidget(add_reg_btn)
        add_field_btn = QPushButton(t("button.add_field"))
        add_field_btn.setEnabled(False)
        add_field_btn.setToolTip(t("tooltip.add_field"))
        periph_toolbar.addWidget(add_field_btn)
        edit_periph_btn = QPushButton(t("button.edit"))
        edit_periph_btn.setEnabled(False)
        edit_periph_btn.setToolTip(t("tooltip.edit_peripheral"))
        periph_toolbar.addWidget(edit_periph_btn)
        delete_periph_btn = QPushButton(t("button.delete"))
        delete_periph_btn.setEnabled(False)
        delete_periph_btn.setToolTip(t("tooltip.delete_peripheral"))
        periph_toolbar.addWidget(delete_periph_btn)
        # 紧凑模式复选框（只显示到寄存器级别，位域在右侧表格中查看）
        compact_tree_cb = ToggleSwitch(t("label.compact_tree", default="紧凑模式"))
        compact_tree_cb.setToolTip(t("tooltip.compact_tree", default="树状图只显示到寄存器级别，位域信息在右侧表格中查看"))
        compact_tree_cb.setChecked(False)
        periph_toolbar.addWidget(compact_tree_cb)
        periph_toolbar.addStretch()
        left_layout.addLayout(periph_toolbar)

        periph_tree = QTreeWidget()
        periph_tree.setHeaderLabels([
            t("label.name_column"), t("label.offset_column"),
            t("label.description_column"), t("label.access_column"),
            t("label.reset_value_column")
        ])
        periph_tree.setColumnWidth(0, 180)
        periph_tree.setColumnWidth(1, 100)
        periph_tree.setColumnWidth(2, 200)
        periph_tree.setColumnWidth(3, 80)
        periph_tree.setColumnWidth(4, 80)
        periph_tree.setAlternatingRowColors(True)
        periph_tree.setSelectionBehavior(QTreeWidget.SelectionBehavior.SelectRows)
        periph_tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        # 应用自定义分支箭头样式
        apply_tree_branch_style(periph_tree)
        left_layout.addWidget(periph_tree)

        # 右侧
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        visualization_widget = None
        try:
            from ..widgets.visualization_widget import VisualizationWidget
            visualization_widget = VisualizationWidget()
            visualization_widget.setMinimumHeight(200)
            self.logger.debug("可视化控件创建成功")
        except Exception as e:
            self.logger.warning(f"可视化控件创建失败: {e}, 使用占位符")
            visualization_widget = QWidget()
            visualization_widget.setMinimumHeight(200)
            _scheme2 = get_style_scheme()
            visualization_widget.setStyleSheet(f"background-color: {_scheme2.colors.visualization_background};")
            placeholder_label = QLabel(t("label.no_data"))
            placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout_placeholder = QVBoxLayout(visualization_widget)
            layout_placeholder.addWidget(placeholder_label)
        right_layout.addWidget(visualization_widget)

        field_table = QTableWidget()
        field_table.setColumnCount(6)
        field_table.setHorizontalHeaderLabels([
            t("label.name_column"), t("label.bit_offset_column"),
            t("label.bit_width_column"), t("label.access_column"),
            t("label.reset_value_column"), t("label.description_column")
        ])
        header = field_table.horizontalHeader()
        if header:
            header.setStretchLastSection(True)
        field_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        field_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        field_table.setAlternatingRowColors(True)
        field_table.setShowGrid(True)
        vheader = field_table.verticalHeader()
        if vheader:
            vheader.setDefaultSectionSize(28)
        field_table.setColumnWidth(0, 120)
        field_table.setColumnWidth(1, 80)
        field_table.setColumnWidth(2, 80)
        field_table.setColumnWidth(3, 100)
        field_table.setColumnWidth(4, 100)
        right_layout.addWidget(field_table)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([800, 800])
        layout.addWidget(splitter)
        tab_widget.addTab(tab, t("tab.peripheral_tab"))

        widgets = {
            'peripheral_tab': tab,
            'periph_tree': periph_tree,
            'field_table': field_table,
            'visualization_widget': visualization_widget,
            'add_periph_btn': add_periph_btn,
            'add_reg_btn': add_reg_btn,
            'add_field_btn': add_field_btn,
            'edit_periph_btn': edit_periph_btn,
            'delete_periph_btn': delete_periph_btn,
            'compact_tree_cb': compact_tree_cb,
        }
        return tab, widgets

    def create_interrupt_tab(self, tab_widget: QTabWidget) -> tuple:
        """创建中断标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        toolbar = QHBoxLayout()
        add_irq_btn = QPushButton(t("button.add_interrupt"))
        toolbar.addWidget(add_irq_btn)
        edit_irq_btn = QPushButton(t("label.edit_interrupt"))
        edit_irq_btn.setEnabled(False)
        toolbar.addWidget(edit_irq_btn)
        delete_irq_btn = QPushButton(t("label.delete_interrupt"))
        delete_irq_btn.setEnabled(False)
        toolbar.addWidget(delete_irq_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        irq_table = QTableWidget()
        irq_table.setColumnCount(4)
        irq_table.setHorizontalHeaderLabels([
            t("label.name_column"), t("label.value_column"),
            t("label.peripheral"), t("label.description_column")
        ])
        header = irq_table.horizontalHeader()
        if header:
            header.setStretchLastSection(True)
        vheader = irq_table.verticalHeader()
        if vheader:
            vheader.setDefaultSectionSize(28)
        irq_table.setColumnWidth(0, 150)
        irq_table.setColumnWidth(1, 80)
        irq_table.setColumnWidth(2, 120)
        irq_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        irq_table.setAlternatingRowColors(True)
        irq_table.setShowGrid(True)
        irq_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(irq_table)
        tab_widget.addTab(tab, t("tab.interrupt_tab"))

        widgets = {
            'interrupt_tab': tab,
            'irq_table': irq_table,
            'add_irq_btn': add_irq_btn,
            'edit_irq_btn': edit_irq_btn,
            'delete_irq_btn': delete_irq_btn,
        }
        return tab, widgets

    def create_preview_tab(self, tab_widget: QTabWidget) -> tuple:
        """创建预览标签页（纯 XML 视图，使用 preview_manager 的组件）"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 预览组件占位 — 将由 preview_manager 在 setup_preview_modes() 中填入
        self._preview_placeholder = QWidget()
        self._preview_layout = QVBoxLayout(self._preview_placeholder)
        self._preview_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._preview_placeholder)

        tab_widget.addTab(tab, t("tab.preview_tab"))

        widgets = {
            'preview_tab': tab,
        }
        return tab, widgets