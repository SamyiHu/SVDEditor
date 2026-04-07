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
    QTableWidget, QTableWidgetItem, QComboBox, QSpinBox, QCheckBox,
    QFormLayout, QGridLayout, QFrame
)
from PyQt6.QtCore import Qt
from ...i18n.i18n import t


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

            # 统一的分组样式 - 现代卡片风格
            group_style = """
                QGroupBox {
                    font-weight: bold;
                    font-size: 10pt;
                    color: #333333;
                    border: 1px solid #E0E0E0;
                    border-radius: 8px;
                    margin-top: 14px;
                    padding: 12px;
                    padding-top: 24px;
                    background-color: #FFFFFF;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 4px 12px;
                    background-color: #FFFFFF;
                    border: 1px solid #E0E0E0;
                    border-radius: 4px;
                    color: #2962FF;
                }
            """

            # === 设备信息组 ===
            device_group = QGroupBox(t("label.basic_info"))
            device_group.setStyleSheet(group_style)
            device_layout = QGridLayout(device_group)
            device_layout.setSpacing(8)
            device_layout.setContentsMargins(12, 20, 12, 12)

            # 第一行：IC型号和描述
            ic_model_label = QLabel(t("label.ic_model") + ":")
            device_layout.addWidget(ic_model_label, 0, 0)
            ic_name_edit = QLineEdit()
            ic_name_edit.setPlaceholderText(t("placeholder.ic_model"))
            ic_name_edit.setMinimumWidth(150)
            device_layout.addWidget(ic_name_edit, 0, 1)

            ic_desc_label = QLabel(t("label.ic_description") + ":")
            device_layout.addWidget(ic_desc_label, 0, 2)
            ic_desc_edit = QLineEdit()
            ic_desc_edit.setPlaceholderText(t("placeholder.ic_description"))
            ic_desc_edit.setMinimumWidth(150)
            device_layout.addWidget(ic_desc_edit, 0, 3)

            # 第二行：版本和SVD版本
            version_label = QLabel(t("label.version") + ":")
            device_layout.addWidget(version_label, 1, 0)
            version_edit = QLineEdit()
            version_edit.setPlaceholderText(t("placeholder.version"))
            version_edit.setMaximumWidth(80)
            device_layout.addWidget(version_edit, 1, 1)

            svd_version_label = QLabel(t("label.svd_version") + ":")
            device_layout.addWidget(svd_version_label, 1, 2)
            svd_version_combo = QComboBox()
            svd_version_combo.addItems(["1.0", "1.1", "1.2", "1.3", "1.3.1"])
            svd_version_combo.setCurrentText("1.3")
            svd_version_combo.setMaximumWidth(80)
            device_layout.addWidget(svd_version_combo, 1, 3)

            # 第三行：CPU名称和修订版
            cpu_name_label = QLabel(t("label.cpu_name") + ":")
            device_layout.addWidget(cpu_name_label, 2, 0)
            cpu_name_edit = QLineEdit()
            cpu_name_edit.setPlaceholderText(t("placeholder.cpu_name"))
            cpu_name_edit.setMinimumWidth(150)
            device_layout.addWidget(cpu_name_edit, 2, 1)

            cpu_rev_label = QLabel(t("label.cpu_revision") + ":")
            device_layout.addWidget(cpu_rev_label, 2, 2)
            cpu_rev_edit = QLineEdit()
            cpu_rev_edit.setPlaceholderText(t("placeholder.cpu_revision"))
            cpu_rev_edit.setMaximumWidth(80)
            device_layout.addWidget(cpu_rev_edit, 2, 3)

            # 第四行：端序和MPU
            endian_label = QLabel(t("label.endian") + ":")
            device_layout.addWidget(endian_label, 3, 0)
            endian_combo = QComboBox()
            endian_combo.addItems([t("value.little"), t("value.big"), t("value.selectable")])
            endian_combo.setCurrentText(t("value.little"))
            endian_combo.setMaximumWidth(100)
            device_layout.addWidget(endian_combo, 3, 1)

            mpu_label = QLabel(t("label.mpu_exists") + ":")
            device_layout.addWidget(mpu_label, 3, 2)
            mpu_combo = QComboBox()
            mpu_combo.addItems([t("value.yes"), t("value.no")])
            mpu_combo.setCurrentText(t("value.no"))
            mpu_combo.setMaximumWidth(60)
            device_layout.addWidget(mpu_combo, 3, 3)

            # 第五行：FPU和NVIC优先级位数
            fpu_label = QLabel(t("label.fpu_exists") + ":")
            device_layout.addWidget(fpu_label, 4, 0)
            fpu_combo = QComboBox()
            fpu_combo.addItems([t("value.yes"), t("value.no")])
            fpu_combo.setCurrentText(t("value.no"))
            fpu_combo.setMaximumWidth(60)
            device_layout.addWidget(fpu_combo, 4, 1)

            nvic_label = QLabel(t("label.nvic_prio_bits") + ":")
            device_layout.addWidget(nvic_label, 4, 2)
            nvic_prio_spin = QSpinBox()
            nvic_prio_spin.setRange(0, 8)
            nvic_prio_spin.setValue(4)
            nvic_prio_spin.setMaximumWidth(60)
            device_layout.addWidget(nvic_prio_spin, 4, 3)

            device_layout.setColumnStretch(1, 1)
            device_layout.setColumnStretch(3, 1)
            layout.addWidget(device_group)

            # === 公司版权信息组 ===
            company_group = QGroupBox(t("label.company_copyright"))
            company_group.setStyleSheet(group_style)
            company_layout = QGridLayout(company_group)
            company_layout.setSpacing(8)
            company_layout.setContentsMargins(12, 20, 12, 12)

            company_name_label = QLabel(t("label.company_name") + ":")
            company_layout.addWidget(company_name_label, 0, 0)
            company_name_edit = QLineEdit()
            company_name_edit.setPlaceholderText(t("placeholder.company_name"))
            company_name_edit.setMinimumWidth(150)
            company_layout.addWidget(company_name_edit, 0, 1)

            company_checkbox = QCheckBox(t("label.do_not_display"))
            company_checkbox.setChecked(False)
            company_layout.addWidget(company_checkbox, 0, 2)

            copyright_label = QLabel(t("label.copyright_info") + ":")
            company_layout.addWidget(copyright_label, 0, 3)
            copyright_edit = QLineEdit()
            copyright_edit.setPlaceholderText(t("placeholder.copyright_info"))
            copyright_edit.setMinimumWidth(150)
            company_layout.addWidget(copyright_edit, 0, 4)

            copyright_checkbox = QCheckBox(t("label.do_not_display"))
            copyright_checkbox.setChecked(False)
            company_layout.addWidget(copyright_checkbox, 0, 5)

            author_label = QLabel(t("label.author") + ":")
            company_layout.addWidget(author_label, 1, 0)
            author_edit = QLineEdit()
            author_edit.setPlaceholderText(t("placeholder.author"))
            author_edit.setMinimumWidth(150)
            company_layout.addWidget(author_edit, 1, 1)

            author_checkbox = QCheckBox(t("label.do_not_display"))
            author_checkbox.setChecked(False)
            company_layout.addWidget(author_checkbox, 1, 2)

            license_label = QLabel(t("label.license") + ":")
            company_layout.addWidget(license_label, 1, 3)
            license_combo = QComboBox()
            license_combo.addItems([
                t("license.do_not_display"), t("license.apache_2_0"),
                t("license.mit"), t("license.bsd_3_clause"),
                t("license.proprietary"), t("license.other")
            ])
            license_combo.setCurrentText(t("license.apache_2_0"))
            license_combo.setMinimumWidth(150)
            company_layout.addWidget(license_combo, 1, 4)

            company_layout.setColumnStretch(1, 1)
            company_layout.setColumnStretch(4, 1)
            layout.addWidget(company_group)

            # === 数据汇总组 ===
            summary_group = QGroupBox(t("label.data_summary"))
            summary_group.setStyleSheet(group_style)
            summary_layout = QHBoxLayout(summary_group)
            summary_layout.setSpacing(16)
            summary_layout.setContentsMargins(12, 20, 12, 12)

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
            periph_card.setStyleSheet(card_style % "#FFF3E0")
            pcl = QVBoxLayout(periph_card)
            pcl.setSpacing(2)
            pcl.setContentsMargins(10, 6, 10, 6)
            periph_count_label = QLabel("0")
            periph_count_label.setStyleSheet("font-size: 22pt; font-weight: bold; color: #E65100;")
            periph_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pcl.addWidget(periph_count_label)
            ptl = QLabel(t("label.total_peripherals"))
            ptl.setStyleSheet("font-size: 8pt; color: #BF360C;")
            ptl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pcl.addWidget(ptl)
            summary_layout.addWidget(periph_card)

            # 寄存器卡片
            reg_card = QFrame()
            reg_card.setStyleSheet(card_style % "#E3F2FD")
            rcl = QVBoxLayout(reg_card)
            rcl.setSpacing(2)
            rcl.setContentsMargins(10, 6, 10, 6)
            reg_count_label = QLabel("0")
            reg_count_label.setStyleSheet("font-size: 22pt; font-weight: bold; color: #1565C0;")
            reg_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rcl.addWidget(reg_count_label)
            rtl = QLabel(t("label.total_registers"))
            rtl.setStyleSheet("font-size: 8pt; color: #0D47A1;")
            rtl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rcl.addWidget(rtl)
            summary_layout.addWidget(reg_card)

            # 位域卡片
            field_card = QFrame()
            field_card.setStyleSheet(card_style % "#E8F5E9")
            fcl = QVBoxLayout(field_card)
            fcl.setSpacing(2)
            fcl.setContentsMargins(10, 6, 10, 6)
            field_count_label = QLabel("0")
            field_count_label.setStyleSheet("font-size: 22pt; font-weight: bold; color: #2E7D32;")
            field_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fcl.addWidget(field_count_label)
            ftl = QLabel(t("label.total_fields"))
            ftl.setStyleSheet("font-size: 8pt; color: #1B5E20;")
            ftl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fcl.addWidget(ftl)
            summary_layout.addWidget(field_card)

            # 中断卡片
            irq_card = QFrame()
            irq_card.setStyleSheet(card_style % "#FCE4EC")
            icl = QVBoxLayout(irq_card)
            icl.setSpacing(2)
            icl.setContentsMargins(10, 6, 10, 6)
            irq_count_label = QLabel("0")
            irq_count_label.setStyleSheet("font-size: 22pt; font-weight: bold; color: #C62828;")
            irq_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icl.addWidget(irq_count_label)
            itl = QLabel(t("label.total_interrupts"))
            itl.setStyleSheet("font-size: 8pt; color: #B71C1C;")
            itl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icl.addWidget(itl)
            summary_layout.addWidget(irq_card)

            layout.addWidget(summary_group)
            layout.addStretch(1)

            # 复选框信号
            def on_company_checkbox_changed(state):
                company_name_edit.setEnabled(not company_checkbox.isChecked())
                if company_checkbox.isChecked():
                    company_name_edit.clear()
            company_checkbox.stateChanged.connect(on_company_checkbox_changed)
            company_name_edit.setEnabled(not company_checkbox.isChecked())

            def on_copyright_checkbox_changed(state):
                copyright_edit.setEnabled(not copyright_checkbox.isChecked())
                if copyright_checkbox.isChecked():
                    copyright_edit.clear()
            copyright_checkbox.stateChanged.connect(on_copyright_checkbox_changed)
            copyright_edit.setEnabled(not copyright_checkbox.isChecked())

            def on_author_checkbox_changed(state):
                author_edit.setEnabled(not author_checkbox.isChecked())
                if author_checkbox.isChecked():
                    author_edit.clear()
            author_checkbox.stateChanged.connect(on_author_checkbox_changed)
            author_edit.setEnabled(not author_checkbox.isChecked())

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
                'company_checkbox': company_checkbox,
                'copyright_edit': copyright_edit,
                'copyright_checkbox': copyright_checkbox,
                'author_edit': author_edit,
                'author_checkbox': author_checkbox,
                'license_combo': license_combo,
                'periph_count_label': periph_count_label,
                'reg_count_label': reg_count_label,
                'field_count_label': field_count_label,
                'irq_count_label': irq_count_label,
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
        periph_tree.setStyleSheet("""
            QTreeWidget {
                font-family: "Segoe UI", "Microsoft YaHei";
                font-size: 10pt;
                outline: 0;
            }
            QTreeWidget::item {
                padding: 4px;
                border-bottom: 1px solid #e0e0e0;
                border-radius: 2px;
            }
            QTreeWidget::item:hover { background-color: #f5f5f5; }
            QTreeWidget::item:selected {
                background-color: #d1e9ff;
                color: #000000;
                border: 1px solid #90c8ff;
                border-radius: 3px;
            }
            QTreeWidget::item:selected:active { background-color: #b8daff; }
            QTreeWidget::branch:selected { background-color: transparent; }
            QTreeWidget::item:focus { outline: none; }
        """)
        periph_tree.setSelectionBehavior(QTreeWidget.SelectionBehavior.SelectRows)
        periph_tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
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
            visualization_widget.setStyleSheet("background-color: #f0f0f0;")
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
            header.setStyleSheet("""
                QHeaderView::section {
                    background-color: #f0f0f0;
                    padding: 6px;
                    border: 1px solid #d0d0d0;
                    font-weight: bold;
                }
            """)
        field_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed)
        field_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        field_table.setAlternatingRowColors(True)
        field_table.setShowGrid(True)
        field_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #e0e0e0;
                font-family: "Segoe UI", "Microsoft YaHei";
                font-size: 10pt;
                outline: 0;
            }
            QTableWidget::item { padding: 4px; border-radius: 2px; }
            QTableWidget::item:selected {
                background-color: #d1e9ff; color: #000000;
                border: 1px solid #90c8ff; border-radius: 3px;
            }
            QTableWidget::item:hover { background-color: #f5f5f5; }
            QTableWidget::item:focus { outline: none; }
        """)
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
            header.setStyleSheet("""
                QHeaderView::section {
                    background-color: #f0f0f0; padding: 6px;
                    border: 1px solid #d0d0d0; font-weight: bold;
                }
            """)
        irq_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #e0e0e0;
                font-family: "Segoe UI", "Microsoft YaHei";
                font-size: 10pt; outline: 0;
            }
            QTableWidget::item { padding: 4px; border-radius: 2px; }
            QTableWidget::item:selected {
                background-color: #d1e9ff; color: #000000;
                border: 1px solid #90c8ff; border-radius: 3px;
            }
            QTableWidget::item:hover { background-color: #f5f5f5; }
            QTableWidget::item:focus { outline: none; }
        """)
        vheader = irq_table.verticalHeader()
        if vheader:
            vheader.setDefaultSectionSize(28)
        irq_table.setColumnWidth(0, 150)
        irq_table.setColumnWidth(1, 80)
        irq_table.setColumnWidth(2, 120)
        irq_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        irq_table.setAlternatingRowColors(True)
        irq_table.setShowGrid(True)
        irq_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed)
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
        """创建预览标签页"""
        from .realtime_preview import RealtimePreviewWidget

        tab = QWidget()
        layout = QVBoxLayout(tab)

        toolbar = QHBoxLayout()
        generate_btn = QPushButton(t("button.generate"))
        toolbar.addWidget(generate_btn)
        export_btn = QPushButton(t("button.export_file"))
        toolbar.addWidget(export_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.realtime_preview = RealtimePreviewWidget(
            state_manager=None,
            coordinator=None
        )
        layout.addWidget(self.realtime_preview)
        tab_widget.addTab(tab, t("tab.preview_tab"))

        widgets = {
            'preview_tab': tab,
            'realtime_preview': self.realtime_preview,
            'generate_btn': generate_btn,
            'export_btn': export_btn,
        }
        return tab, widgets