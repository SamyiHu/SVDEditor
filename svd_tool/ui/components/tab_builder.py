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
    QTableWidget, QTableWidgetItem, QComboBox, QSpinBox, QCheckBox
)
from PyQt6.QtCore import Qt
from ...i18n.i18n import t


class TabBuilder:
    """标签页构建器"""

    def __init__(self, main_window):
        """
        初始化标签页构建器

        Args:
            main_window: 主窗口实例
        """
        self.main_window = main_window
        self.logger = logging.getLogger("TabBuilder")

    def create_basic_info_tab(self, tab_widget: QTabWidget) -> QWidget:
        """创建基础信息标签页（优化版）"""
        self.logger.debug("create_basic_info_tab开始")
        try:
            from PyQt6.QtWidgets import QFormLayout, QGridLayout, QFrame
            from PyQt6.QtCore import Qt

            tab = QWidget()
            layout = QVBoxLayout(tab)
            layout.setSpacing(15)  # 增加组之间的间距
            layout.setContentsMargins(20, 20, 20, 20)  # 增加边距

            # 设备信息组（使用网格布局，更整齐）
            device_group = QGroupBox(t("label.basic_info"))
            device_group.setStyleSheet("""
                QGroupBox {
                    font-weight: bold;
                    font-size: 11pt;
                    border: 2px solid #d0d0d0;
                    border-radius: 8px;
                    margin-top: 12px;
                    padding: 15px;
                    background-color: #fafafa;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 15px;
                    padding: 0 5px;
                    color: #333;
                }
            """)
            device_layout = QGridLayout(device_group)
            device_layout.setSpacing(10)
            device_layout.setContentsMargins(10, 20, 10, 10)

            # 第一行：IC型号和描述
            device_layout.addWidget(QLabel(t("label.ic_model") + ":"), 0, 0)
            ic_name_edit = QLineEdit()
            ic_name_edit.setPlaceholderText(t("placeholder.ic_model"))
            ic_name_edit.setStyleSheet("""
                QLineEdit {
                    padding: 6px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    background-color: white;
                    font-size: 10pt;
                }
                QLineEdit:focus {
                    border: 2px solid #4a90e2;
                }
            """)
            device_layout.addWidget(ic_name_edit, 0, 1)

            device_layout.addWidget(QLabel(t("label.ic_description") + ":"), 0, 2)
            ic_desc_edit = QLineEdit()
            ic_desc_edit.setPlaceholderText(t("placeholder.ic_description"))
            ic_desc_edit.setStyleSheet("""
                QLineEdit {
                    padding: 6px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    background-color: white;
                    font-size: 10pt;
                }
                QLineEdit:focus {
                    border: 2px solid #4a90e2;
                }
            """)
            device_layout.addWidget(ic_desc_edit, 0, 3)

            # 第二行：版本和SVD版本
            device_layout.addWidget(QLabel(t("label.version") + ":"), 1, 0)
            version_edit = QLineEdit()
            version_edit.setPlaceholderText(t("placeholder.version"))
            version_edit.setStyleSheet("""
                QLineEdit {
                    padding: 6px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    background-color: white;
                    font-size: 10pt;
                }
                QLineEdit:focus {
                    border: 2px solid #4a90e2;
                }
            """)
            device_layout.addWidget(version_edit, 1, 1)

            device_layout.addWidget(QLabel(t("label.svd_version") + ":"), 1, 2)
            svd_version_combo = QComboBox()
            svd_version_combo.addItems(["1.0", "1.1", "1.2", "1.3", "1.3.1"])
            svd_version_combo.setCurrentText("1.3")
            svd_version_combo.setStyleSheet("""
                QComboBox {
                    padding: 6px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    background-color: white;
                    font-size: 10pt;
                    min-height: 20px;
                }
                QComboBox:focus {
                    border: 2px solid #4a90e2;
                }
                QComboBox::drop-down {
                    border: none;
                }
                QComboBox::down-arrow {
                    width: 12px;
                    height: 12px;
                }
            """)
            device_layout.addWidget(svd_version_combo, 1, 3)

            # 第三行：CPU名称和修订版
            device_layout.addWidget(QLabel(t("label.cpu_name") + ":"), 2, 0)
            cpu_name_edit = QLineEdit()
            cpu_name_edit.setPlaceholderText(t("placeholder.cpu_name"))
            cpu_name_edit.setStyleSheet("""
                QLineEdit {
                    padding: 6px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    background-color: white;
                    font-size: 10pt;
                }
                QLineEdit:focus {
                    border: 2px solid #4a90e2;
                }
            """)
            device_layout.addWidget(cpu_name_edit, 2, 1)

            device_layout.addWidget(QLabel(t("label.cpu_revision") + ":"), 2, 2)
            cpu_rev_edit = QLineEdit()
            cpu_rev_edit.setPlaceholderText(t("placeholder.cpu_revision"))
            cpu_rev_edit.setStyleSheet("""
                QLineEdit {
                    padding: 6px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    background-color: white;
                    font-size: 10pt;
                }
                QLineEdit:focus {
                    border: 2px solid #4a90e2;
                }
            """)
            device_layout.addWidget(cpu_rev_edit, 2, 3)

            # 第四行：端序和MPU
            device_layout.addWidget(QLabel(t("label.endian") + ":"), 3, 0)
            endian_combo = QComboBox()
            endian_combo.addItems([t("value.little"), t("value.big"), t("value.selectable")])
            endian_combo.setCurrentText(t("value.little"))
            endian_combo.setStyleSheet("""
                QComboBox {
                    padding: 6px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    background-color: white;
                    font-size: 10pt;
                    min-height: 20px;
                }
                QComboBox:focus {
                    border: 2px solid #4a90e2;
                }
            """)
            device_layout.addWidget(endian_combo, 3, 1)

            device_layout.addWidget(QLabel(t("label.mpu_exists") + ":"), 3, 2)
            mpu_combo = QComboBox()
            mpu_combo.addItems([t("value.yes"), t("value.no")])
            mpu_combo.setCurrentText(t("value.no"))
            mpu_combo.setStyleSheet("""
                QComboBox {
                    padding: 6px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    background-color: white;
                    font-size: 10pt;
                    min-height: 20px;
                }
                QComboBox:focus {
                    border: 2px solid #4a90e2;
                }
            """)
            device_layout.addWidget(mpu_combo, 3, 3)

            # 第五行：FPU和NVIC优先级位数
            device_layout.addWidget(QLabel(t("label.fpu_exists") + ":"), 4, 0)
            fpu_combo = QComboBox()
            fpu_combo.addItems([t("value.yes"), t("value.no")])
            fpu_combo.setCurrentText(t("value.no"))
            fpu_combo.setStyleSheet("""
                QComboBox {
                    padding: 6px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    background-color: white;
                    font-size: 10pt;
                    min-height: 20px;
                }
                QComboBox:focus {
                    border: 2px solid #4a90e2;
                }
            """)
            device_layout.addWidget(fpu_combo, 4, 1)

            device_layout.addWidget(QLabel(t("label.nvic_prio_bits") + ":"), 4, 2)
            nvic_prio_spin = QSpinBox()
            nvic_prio_spin.setRange(0, 8)
            nvic_prio_spin.setValue(4)
            nvic_prio_spin.setStyleSheet("""
                QSpinBox {
                    padding: 6px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    background-color: white;
                    font-size: 10pt;
                    min-height: 20px;
                }
                QSpinBox:focus {
                    border: 2px solid #4a90e2;
                }
                QSpinBox::up-button, QSpinBox::down-button {
                    width: 16px;
                    border: none;
                    background-color: #f0f0f0;
                }
                QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                    background-color: #e0e0e0;
                }
            """)
            device_layout.addWidget(nvic_prio_spin, 4, 3)

            # 设置列拉伸
            device_layout.setColumnStretch(1, 1)
            device_layout.setColumnStretch(3, 1)

            layout.addWidget(device_group)

            # 分隔线
            separator = QFrame()
            separator.setFrameShape(QFrame.Shape.HLine)
            separator.setFrameShadow(QFrame.Shadow.Sunken)
            separator.setStyleSheet("background-color: #e0e0e0; max-height: 1px;")
            layout.addWidget(separator)

            # 公司版权信息组
            company_group = QGroupBox(t("label.company_copyright"))
            company_group.setStyleSheet("""
                QGroupBox {
                    font-weight: bold;
                    font-size: 11pt;
                    border: 2px solid #d0d0d0;
                    border-radius: 8px;
                    margin-top: 12px;
                    padding: 15px;
                    background-color: #fafafa;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 15px;
                    padding: 0 5px;
                    color: #333;
                }
            """)
            company_layout = QGridLayout(company_group)
            company_layout.setSpacing(10)
            company_layout.setContentsMargins(10, 20, 10, 10)

            # 第一行：厂商ID和版权信息
            company_layout.addWidget(QLabel(t("label.company_name") + ":"), 0, 0)
            company_name_edit = QLineEdit()
            company_name_edit.setPlaceholderText(t("placeholder.company_name"))
            company_name_edit.setStyleSheet("""
                QLineEdit {
                    padding: 6px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    background-color: white;
                    font-size: 10pt;
                }
                QLineEdit:focus {
                    border: 2px solid #4a90e2;
                }
            """)
            company_layout.addWidget(company_name_edit, 0, 1)

            company_layout.addWidget(QLabel(t("label.copyright_info") + ":"), 0, 2)
            copyright_edit = QLineEdit()
            copyright_edit.setPlaceholderText(t("placeholder.copyright_info"))
            copyright_edit.setStyleSheet("""
                QLineEdit {
                    padding: 6px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    background-color: white;
                    font-size: 10pt;
                }
                QLineEdit:focus {
                    border: 2px solid #4a90e2;
                }
            """)
            company_layout.addWidget(copyright_edit, 0, 3)

            # 第二行：作者和许可证
            company_layout.addWidget(QLabel(t("label.author") + ":"), 1, 0)
            author_edit = QLineEdit()
            author_edit.setPlaceholderText(t("placeholder.author"))
            author_edit.setStyleSheet("""
                QLineEdit {
                    padding: 6px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    background-color: white;
                    font-size: 10pt;
                }
                QLineEdit:focus {
                    border: 2px solid #4a90e2;
                }
            """)
            company_layout.addWidget(author_edit, 1, 1)

            author_checkbox = QCheckBox(t("label.do_not_display"))
            author_checkbox.setChecked(False)
            author_checkbox.setStyleSheet("""
                QCheckBox {
                    font-size: 9pt;
                    spacing: 5px;
                }
                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    background-color: white;
                }
                QCheckBox::indicator:checked {
                    background-color: #4a90e2;
                    border: 1px solid #4a90e2;
                }
            """)
            company_layout.addWidget(author_checkbox, 1, 2)

            company_layout.addWidget(QLabel(t("label.license") + ":"), 1, 3)
            license_combo = QComboBox()
            license_combo.addItems([t("license.do_not_display"), t("license.apache_2_0"), t("license.mit"), t("license.bsd_3_clause"), t("license.proprietary"), t("license.other")])
            license_combo.setCurrentText(t("license.apache_2_0"))
            license_combo.setStyleSheet("""
                QComboBox {
                    padding: 6px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    background-color: white;
                    font-size: 10pt;
                    min-height: 20px;
                }
                QComboBox:focus {
                    border: 2px solid #4a90e2;
                }
            """)
            company_layout.addWidget(license_combo, 1, 4)

            # 设置列拉伸
            company_layout.setColumnStretch(1, 1)
            company_layout.setColumnStretch(3, 1)
            company_layout.setColumnStretch(4, 1)

            layout.addWidget(company_group)

            # 分隔线
            separator2 = QFrame()
            separator2.setFrameShape(QFrame.Shape.HLine)
            separator2.setFrameShadow(QFrame.Shadow.Sunken)
            separator2.setStyleSheet("background-color: #e0e0e0; max-height: 1px;")
            layout.addWidget(separator2)

            # 描述信息组
            desc_group = QGroupBox(t("label.detailed_description"))
            desc_group.setStyleSheet("""
                QGroupBox {
                    font-weight: bold;
                    font-size: 11pt;
                    border: 2px solid #d0d0d0;
                    border-radius: 8px;
                    margin-top: 12px;
                    padding: 15px;
                    background-color: #fafafa;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 15px;
                    padding: 0 5px;
                    color: #333;
                }
            """)
            desc_layout = QVBoxLayout(desc_group)
            desc_layout.setContentsMargins(10, 20, 10, 10)

            desc_edit = QTextEdit()
            desc_edit.setPlaceholderText(t("label.enter_detailed_description"))
            desc_edit.setMaximumHeight(150)
            desc_edit.setStyleSheet("""
                QTextEdit {
                    padding: 8px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    background-color: white;
                    font-size: 10pt;
                }
                QTextEdit:focus {
                    border: 2px solid #4a90e2;
                }
            """)
            desc_layout.addWidget(desc_edit)

            layout.addWidget(desc_group)

            layout.addStretch()

            # 连接作者复选框信号
            def on_author_checkbox_changed(state):
                author_edit.setEnabled(not author_checkbox.isChecked())
                if author_checkbox.isChecked():
                    author_edit.clear()

            author_checkbox.stateChanged.connect(on_author_checkbox_changed)
            # 初始状态
            author_edit.setEnabled(not author_checkbox.isChecked())

            self.logger.debug(f"调用addTab前，标签页数量: {tab_widget.count()}")
            index = tab_widget.addTab(tab, t("tab.basic_info_tab"))
            self.logger.debug(f"addTab返回索引: {index}，标签页数量: {tab_widget.count()}")

            # 返回控件字典
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
                'author_checkbox': author_checkbox,
                'license_combo': license_combo,
                'desc_edit': desc_edit,
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

        # 创建两列分割器（移除了实时预览）
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：外设树
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # 外设树工具栏
        periph_toolbar = QHBoxLayout()

        # 三个独立的添加按钮
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

        # 外设树（现在包含寄存器作为子项）
        periph_tree = QTreeWidget()
        periph_tree.setHeaderLabels([t("label.name_column"), t("label.offset_column"), t("label.description_column"), t("label.access_column"), t("label.reset_value_column")])
        periph_tree.setColumnWidth(0, 180)  # 名称
        periph_tree.setColumnWidth(1, 100)  # 偏移量/基地址
        periph_tree.setColumnWidth(2, 200)  # 描述
        periph_tree.setColumnWidth(3, 80)   # 访问权限
        periph_tree.setColumnWidth(4, 80)   # 复位值

        # 设置交替行颜色，提高可读性
        periph_tree.setAlternatingRowColors(True)

        # 设置行高，增加可读性
        periph_tree.setStyleSheet("""
            QTreeWidget {
                font-family: "Segoe UI", "Microsoft YaHei";
                font-size: 10pt;
                outline: 0; /* 移除焦点边框 */
            }
            QTreeWidget::item {
                padding: 4px;
                border-bottom: 1px solid #e0e0e0;
                border-radius: 2px;
            }
            QTreeWidget::item:hover {
                background-color: #f5f5f5;
            }
            QTreeWidget::item:selected {
                background-color: #d1e9ff; /* 更柔和的蓝色 */
                color: #000000;
                border: 1px solid #90c8ff;
                border-radius: 3px;
            }
            QTreeWidget::item:selected:active {
                background-color: #b8daff;
            }
            QTreeWidget::branch:selected {
                background-color: transparent; /* 确保分支图标区域也有背景色 */
            }
            /* 移除焦点虚线框 */
            QTreeWidget::item:focus {
                outline: none;
            }
        """)

        # 设置选择行为为整行选择
        periph_tree.setSelectionBehavior(QTreeWidget.SelectionBehavior.SelectRows)
        periph_tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)

        left_layout.addWidget(periph_tree)

        # 右侧：寄存器树
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # 可视化控件（处理可能的导入错误）
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

        # 位域表格（直接编辑，无需工具栏按钮）
        field_table = QTableWidget()
        field_table.setColumnCount(6)
        field_table.setHorizontalHeaderLabels([t("label.name_column"), t("label.bit_offset_column"), t("label.bit_width_column"), t("label.access_column"), t("label.reset_value_column"), t("label.description_column")])

        # 获取header对象并设置拉伸
        header = field_table.horizontalHeader()
        if header:
            header.setStretchLastSection(True)
            # 设置表头样式
            header.setStyleSheet("""
                QHeaderView::section {
                    background-color: #f0f0f0;
                    padding: 6px;
                    border: 1px solid #d0d0d0;
                    font-weight: bold;
                }
            """)

        # 设置表格为可编辑
        field_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed)
        # 设置选择行为
        field_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        # 设置交替行颜色，使表格更好看
        field_table.setAlternatingRowColors(True)
        # 设置网格线
        field_table.setShowGrid(True)
        # 设置网格线颜色（与树选中样式统一）
        field_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #e0e0e0;
                font-family: "Segoe UI", "Microsoft YaHei";
                font-size: 10pt;
                outline: 0; /* 移除焦点边框 */
            }
            QTableWidget::item {
                padding: 4px;
                border-radius: 2px;
            }
            QTableWidget::item:selected {
                background-color: #d1e9ff; /* 与树选中样式统一 */
                color: #000000;
                border: 1px solid #90c8ff;
                border-radius: 3px;
            }
            QTableWidget::item:hover {
                background-color: #f5f5f5;
            }
            QTableWidget::item:nth-child(even) {
                background-color: #f9f9f9;
            }
            QTableWidget::item:nth-child(odd) {
                background-color: #ffffff;
            }
            /* 移除焦点虚线框 */
            QTableWidget::item:focus {
                outline: none;
            }
        """)

        # 设置行高
        vheader = field_table.verticalHeader()
        if vheader:
            vheader.setDefaultSectionSize(28)

        # 设置列宽
        field_table.setColumnWidth(0, 120)  # 名称
        field_table.setColumnWidth(1, 80)   # 位偏移
        field_table.setColumnWidth(2, 80)   # 位宽
        field_table.setColumnWidth(3, 100)  # 访问权限
        field_table.setColumnWidth(4, 100)  # 复位值
        # 描述列自动拉伸

        right_layout.addWidget(field_table)

        # 添加部件到分割器（两列布局）
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        # 设置分割器初始大小：左50%，右50%
        splitter.setSizes([800, 800])

        layout.addWidget(splitter)

        tab_widget.addTab(tab, t("tab.peripheral_tab"))

        # 返回控件字典
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

        # 工具栏
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

        # 中断表格（列顺序：名称、值、外设、描述）
        irq_table = QTableWidget()
        irq_table.setColumnCount(4)
        irq_table.setHorizontalHeaderLabels([t("label.name_column"), t("label.value_column"), t("label.peripheral"), t("label.description_column")])

        # 获取header对象并设置拉伸和样式
        header = irq_table.horizontalHeader()
        if header:
            header.setStretchLastSection(True)
            # 设置表头样式
            header.setStyleSheet("""
                QHeaderView::section {
                    background-color: #f0f0f0;
                    padding: 6px;
                    border: 1px solid #d0d0d0;
                    font-weight: bold;
                }
            """)

        # 设置表格样式（与树选中样式统一）
        irq_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #e0e0e0;
                font-family: "Segoe UI", "Microsoft YaHei";
                font-size: 10pt;
                outline: 0; /* 移除焦点边框 */
            }
            QTableWidget::item {
                padding: 4px;
                border-radius: 2px;
            }
            QTableWidget::item:selected {
                background-color: #d1e9ff; /* 与树选中样式统一 */
                color: #000000;
                border: 1px solid #90c8ff;
                border-radius: 3px;
            }
            QTableWidget::item:hover {
                background-color: #f5f5f5;
            }
            QTableWidget::item:nth-child(even) {
                background-color: #f9f9f9;
            }
            QTableWidget::item:nth-child(odd) {
                background-color: #ffffff;
            }
            /* 移除焦点虚线框 */
            QTableWidget::item:focus {
                outline: none;
            }
        """)

        # 设置行高
        vheader = irq_table.verticalHeader()
        if vheader:
            vheader.setDefaultSectionSize(28)

        # 设置列宽
        irq_table.setColumnWidth(0, 150)  # 名称
        irq_table.setColumnWidth(1, 80)   # 值
        irq_table.setColumnWidth(2, 120)  # 外设

        irq_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        irq_table.setAlternatingRowColors(True)
        irq_table.setShowGrid(True)

        # 启用双击编辑
        irq_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed)

        layout.addWidget(irq_table)

        tab_widget.addTab(tab, t("tab.interrupt_tab"))

        # 返回控件字典
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

        # 工具栏
        toolbar = QHBoxLayout()

        generate_btn = QPushButton(t("button.generate"))
        toolbar.addWidget(generate_btn)

        export_btn = QPushButton(t("button.export_file"))
        toolbar.addWidget(export_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 创建实时预览组件
        # 注意：state_manager和coordinator需要在主窗口中设置
        self.realtime_preview = RealtimePreviewWidget(
            state_manager=None,  # 将在主窗口中设置
            coordinator=None
        )
        layout.addWidget(self.realtime_preview)

        tab_widget.addTab(tab, t("tab.preview_tab"))

        # 返回控件字典
        widgets = {
            'preview_tab': tab,
            'realtime_preview': self.realtime_preview,
            'generate_btn': generate_btn,
            'export_btn': export_btn,
        }

        return tab, widgets
