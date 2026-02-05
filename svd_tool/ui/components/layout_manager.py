"""
UI布局管理组件
负责创建主窗口的UI布局，包括标签页、搜索栏、状态栏等
"""
import logging
import sys
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel,
    QLineEdit, QPushButton, QStatusBar, QGroupBox, QSplitter,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QTextEdit,
    QTableWidget, QTableWidgetItem, QComboBox, QSpinBox,
    QToolBar, QMenuBar, QApplication, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QAction, QIcon, QKeySequence

from .menu_bar import MenuBarBuilder
from .toolbar import ToolBarBuilder


class LayoutManager:
    """布局管理器"""
    
    def __init__(self, main_window):
        """
        初始化布局管理器
        
        Args:
            main_window: 主窗口实例
        """
        self.main_window = main_window
        self.widgets: Dict[str, Any] = {}
        
    def create_layout(self):
        """创建主布局"""
        logging.debug("[DEBUG LayoutManager] create_layout开始")
        # 设置窗口标题和大小
        self.main_window.setWindowTitle("SVD工具 - 专业版")
        self.main_window.setGeometry(100, 100, 1600, 900)
        
        # 创建中央部件
        central_widget = QWidget()
        self.main_window.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        logging.debug("[DEBUG LayoutManager] 中央部件和布局创建完成")
        
        # 创建菜单栏（如果主窗口有相应方法）
        try:
            menu_builder = MenuBarBuilder(self.main_window, self.main_window)
            menu_builder.create()
            logging.debug("[DEBUG LayoutManager] 菜单栏创建完成")
        except Exception as e:
            logging.debug(f"[DEBUG LayoutManager] 菜单栏创建失败（可忽略）: {e}")
        
        # 创建工具栏（如果主窗口有相应方法）
        try:
            toolbar_builder = ToolBarBuilder(self.main_window, self.main_window)
            toolbar_builder.create()
            logging.debug("[DEBUG LayoutManager] 工具栏创建完成")
        except Exception as e:
            logging.debug(f"[DEBUG LayoutManager] 工具栏创建失败（可忽略）: {e}")
        
        # 创建状态栏
        self.create_status_bar()
        logging.debug("[DEBUG LayoutManager] 状态栏创建完成")
        
        # 搜索栏
        self.create_search_bar(main_layout)
        logging.debug("[DEBUG LayoutManager] 搜索栏创建完成")
        
        # 创建标签页
        self.widgets['tab_widget'] = QTabWidget(central_widget)
        main_layout.addWidget(self.widgets['tab_widget'])
        logging.debug("[DEBUG LayoutManager] 标签页控件创建并添加到布局")
        
        return self.widgets
    
    def create_status_bar(self):
        """创建状态栏"""
        status_bar = QStatusBar()
        self.main_window.setStatusBar(status_bar)
        
        # 状态标签
        status_label = QLabel("就绪")
        status_bar.addWidget(status_label)
        
        # 数据统计标签
        data_stats_label = QLabel("")
        status_bar.addPermanentWidget(data_stats_label)
        
        self.widgets['status_bar'] = status_bar
        self.widgets['status_label'] = status_label
        self.widgets['data_stats_label'] = data_stats_label
        
        return status_bar
    
    def create_search_bar(self, parent_layout):
        """创建搜索栏"""
        search_layout = QHBoxLayout()
        
        search_label = QLabel("搜索:")
        search_layout.addWidget(search_label)
        
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("搜索外设/寄存器/位域...")
        search_layout.addWidget(search_edit)
        
        search_prev_btn = QPushButton("上一个")
        search_prev_btn.setEnabled(False)
        search_layout.addWidget(search_prev_btn)
        
        search_next_btn = QPushButton("下一个")
        search_next_btn.setEnabled(False)
        search_layout.addWidget(search_next_btn)
        
        search_count_label = QLabel("")
        search_layout.addWidget(search_count_label)
        
        search_layout.addStretch()
        parent_layout.addLayout(search_layout)
        
        self.widgets['search_edit'] = search_edit
        self.widgets['search_prev_btn'] = search_prev_btn
        self.widgets['search_next_btn'] = search_next_btn
        self.widgets['search_count_label'] = search_count_label
        
        return search_layout
    
    def create_basic_info_tab(self, tab_widget):
        """创建基础信息标签页"""
        logging.debug(f"[DEBUG LayoutManager] create_basic_info_tab开始，tab_widget={tab_widget}")
        try:
            from PyQt6.QtWidgets import QFormLayout, QGridLayout
            
            tab = QWidget()
            layout = QVBoxLayout(tab)
            
            # 基本信息组
            basic_group = QGroupBox("基本信息")
            basic_layout = QHBoxLayout(basic_group)
            
            left_layout = QVBoxLayout()
            right_layout = QVBoxLayout()
            
            # 左侧表单
            left_layout.addWidget(QLabel("IC型号:"))
            ic_name_edit = QLineEdit()
            ic_name_edit.setPlaceholderText("例如: STM32F103C8")
            left_layout.addWidget(ic_name_edit)
            
            left_layout.addWidget(QLabel("IC描述:"))
            ic_desc_edit = QLineEdit()
            ic_desc_edit.setPlaceholderText("例如: 32位ARM Cortex-M3微控制器")
            left_layout.addWidget(ic_desc_edit)
            
            left_layout.addWidget(QLabel("版本号:"))
            version_edit = QLineEdit()
            version_edit.setPlaceholderText("例如: 1.0")
            left_layout.addWidget(version_edit)
            
            left_layout.addWidget(QLabel("SVD版本:"))
            svd_version_combo = QComboBox()
            svd_version_combo.addItems(["1.0", "1.1", "1.2", "1.3", "1.3.1"])
            svd_version_combo.setCurrentText("1.3")
            left_layout.addWidget(svd_version_combo)
            
            # 右侧表单
            right_layout.addWidget(QLabel("CPU名称:"))
            cpu_name_edit = QLineEdit()
            cpu_name_edit.setPlaceholderText("例如: Cortex-M3")
            right_layout.addWidget(cpu_name_edit)
            
            right_layout.addWidget(QLabel("CPU修订版:"))
            cpu_rev_edit = QLineEdit()
            cpu_rev_edit.setPlaceholderText("例如: r1p1")
            right_layout.addWidget(cpu_rev_edit)
            
            right_layout.addWidget(QLabel("端序:"))
            endian_combo = QComboBox()
            endian_combo.addItems(["little", "big", "selectable"])
            endian_combo.setCurrentText("little")
            right_layout.addWidget(endian_combo)
            
            right_layout.addWidget(QLabel("MPU存在:"))
            mpu_combo = QComboBox()
            mpu_combo.addItems(["是", "否"])
            mpu_combo.setCurrentText("否")
            right_layout.addWidget(mpu_combo)
            
            right_layout.addWidget(QLabel("FPU存在:"))
            fpu_combo = QComboBox()
            fpu_combo.addItems(["是", "否"])
            fpu_combo.setCurrentText("否")
            right_layout.addWidget(fpu_combo)
            
            right_layout.addWidget(QLabel("NVIC优先级位数:"))
            nvic_prio_spin = QSpinBox()
            nvic_prio_spin.setRange(0, 8)
            nvic_prio_spin.setValue(4)
            right_layout.addWidget(nvic_prio_spin)
            
            basic_layout.addLayout(left_layout)
            basic_layout.addLayout(right_layout)
            layout.addWidget(basic_group)
            
            # 公司版权信息组
            company_group = QGroupBox("公司版权信息")
            company_layout = QHBoxLayout(company_group)
            
            company_left_layout = QVBoxLayout()
            company_right_layout = QVBoxLayout()
            
            company_left_layout.addWidget(QLabel("公司名称:"))
            company_name_edit = QLineEdit()
            company_name_edit.setPlaceholderText("例如: STMicroelectronics")
            company_left_layout.addWidget(company_name_edit)
            
            company_left_layout.addWidget(QLabel("版权信息:"))
            copyright_edit = QLineEdit()
            copyright_edit.setPlaceholderText("例如: Copyright 2025 STMicroelectronics. All rights reserved.")
            company_left_layout.addWidget(copyright_edit)
            
            # 作者字段，带"不显示"复选框
            author_layout = QHBoxLayout()
            author_layout.addWidget(QLabel("作者:"))
            author_edit = QLineEdit()
            author_edit.setPlaceholderText("例如: SVD Tool Team")
            author_layout.addWidget(author_edit)
            author_checkbox = QCheckBox("不显示")
            author_checkbox.setChecked(False)
            author_layout.addWidget(author_checkbox)
            company_right_layout.addLayout(author_layout)
            
            # 许可证字段，添加"不显示"选项
            license_layout = QHBoxLayout()
            license_layout.addWidget(QLabel("许可证:"))
            license_combo = QComboBox()
            license_combo.addItems(["不显示", "Apache-2.0", "MIT", "BSD-3-Clause", "Proprietary", "Other"])
            license_combo.setCurrentText("Apache-2.0")
            license_layout.addWidget(license_combo)
            company_right_layout.addLayout(license_layout)
            
            company_layout.addLayout(company_left_layout)
            company_layout.addLayout(company_right_layout)
            layout.addWidget(company_group)
            
            # 描述信息组
            desc_group = QGroupBox("详细描述")
            desc_layout = QVBoxLayout(desc_group)
            
            desc_edit = QTextEdit()
            desc_edit.setPlaceholderText("输入设备的详细描述...")
            desc_edit.setMaximumHeight(150)
            desc_layout.addWidget(desc_edit)
            
            layout.addWidget(desc_group)
            
            layout.addStretch()
            
            # 保存控件引用
            self.widgets['basic_info_tab'] = tab
            self.widgets['ic_name_edit'] = ic_name_edit
            self.widgets['ic_desc_edit'] = ic_desc_edit
            self.widgets['version_edit'] = version_edit
            self.widgets['svd_version_combo'] = svd_version_combo
            self.widgets['cpu_name_edit'] = cpu_name_edit
            self.widgets['cpu_rev_edit'] = cpu_rev_edit
            self.widgets['endian_combo'] = endian_combo
            self.widgets['mpu_combo'] = mpu_combo
            self.widgets['fpu_combo'] = fpu_combo
            self.widgets['company_name_edit'] = company_name_edit
            self.widgets['copyright_edit'] = copyright_edit
            self.widgets['author_edit'] = author_edit
            self.widgets['author_checkbox'] = author_checkbox
            self.widgets['license_combo'] = license_combo
            self.widgets['desc_edit'] = desc_edit
            
            # 连接作者复选框信号
            def on_author_checkbox_changed(state):
                author_edit.setEnabled(not author_checkbox.isChecked())
                if author_checkbox.isChecked():
                    author_edit.clear()
            
            author_checkbox.stateChanged.connect(on_author_checkbox_changed)
            # 初始状态
            author_edit.setEnabled(not author_checkbox.isChecked())
            
            print(f"[DEBUG LayoutManager] 调用addTab前，标签页数量: {tab_widget.count()}", file=sys.stderr)
            index = tab_widget.addTab(tab, "基本信息")
            print(f"[DEBUG LayoutManager] addTab返回索引: {index}，标签页数量: {tab_widget.count()}", file=sys.stderr)
            print(f"[DEBUG LayoutManager] 已添加基本信息标签页，当前标签页数量: {tab_widget.count()}", file=sys.stderr)
            
            return tab
        except Exception as e:
            print(f"[DEBUG LayoutManager] create_basic_info_tab异常: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            raise
    
    def create_peripheral_tab(self, tab_widget):
        """创建外设标签页"""
        import sys
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：外设树
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # 外设树工具栏
        periph_toolbar = QHBoxLayout()
        
        # 三个独立的添加按钮
        add_periph_btn = QPushButton("添加外设")
        add_periph_btn.setToolTip("添加新的外设")
        periph_toolbar.addWidget(add_periph_btn)
        
        add_reg_btn = QPushButton("添加寄存器")
        add_reg_btn.setEnabled(False)
        add_reg_btn.setToolTip("在当前选中的外设下添加寄存器")
        periph_toolbar.addWidget(add_reg_btn)
        
        add_field_btn = QPushButton("添加位域")
        add_field_btn.setEnabled(False)
        add_field_btn.setToolTip("在当前选中的寄存器下添加位域")
        periph_toolbar.addWidget(add_field_btn)
        
        edit_periph_btn = QPushButton("编辑")
        edit_periph_btn.setEnabled(False)
        edit_periph_btn.setToolTip("编辑当前选中的项目")
        periph_toolbar.addWidget(edit_periph_btn)
        
        delete_periph_btn = QPushButton("删除")
        delete_periph_btn.setEnabled(False)
        delete_periph_btn.setToolTip("删除当前选中的项目")
        periph_toolbar.addWidget(delete_periph_btn)
        
        periph_toolbar.addStretch()
        left_layout.addLayout(periph_toolbar)
        
        # 外设树（现在包含寄存器作为子项）
        periph_tree = QTreeWidget()
        periph_tree.setHeaderLabels(["名称", "偏移量/基地址", "描述", "访问权限", "复位值"])
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
            print(f"[DEBUG LayoutManager] 可视化控件创建成功", file=sys.stderr)
        except Exception as e:
            print(f"[DEBUG LayoutManager] 可视化控件创建失败: {e}, 使用占位符", file=sys.stderr)
            visualization_widget = QWidget()
            visualization_widget.setMinimumHeight(200)
            visualization_widget.setStyleSheet("background-color: #f0f0f0;")
            placeholder_label = QLabel("可视化控件加载失败")
            placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout_placeholder = QVBoxLayout(visualization_widget)
            layout_placeholder.addWidget(placeholder_label)
        
        right_layout.addWidget(visualization_widget)
        
        # 位域表格（直接编辑，无需工具栏按钮）
        field_table = QTableWidget()
        field_table.setColumnCount(6)
        field_table.setHorizontalHeaderLabels(["名称", "位偏移", "位宽", "访问权限", "复位值", "描述"])
        
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
        
        # 添加部件到分割器
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        # 设置分割器初始大小：左侧占一半，右侧占一半
        # 使用较大的初始值确保树状图的所有列都能显示
        splitter.setSizes([700, 700])
        
        layout.addWidget(splitter)
        
        # 保存控件引用
        self.widgets['peripheral_tab'] = tab
        self.widgets['periph_tree'] = periph_tree
        self.widgets['field_table'] = field_table
        self.widgets['visualization_widget'] = visualization_widget
        self.widgets['add_periph_btn'] = add_periph_btn
        self.widgets['add_reg_btn'] = add_reg_btn
        self.widgets['add_field_btn'] = add_field_btn
        self.widgets['edit_periph_btn'] = edit_periph_btn
        self.widgets['delete_periph_btn'] = delete_periph_btn
        # 注意：现在有三个独立的添加按钮，编辑和删除按钮根据选择智能操作
        
        tab_widget.addTab(tab, "外设/寄存器")
        
        return tab
    
    def create_interrupt_tab(self, tab_widget):
        """创建中断标签页"""
        from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem
        
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 工具栏
        toolbar = QHBoxLayout()
        
        add_irq_btn = QPushButton("添加中断")
        toolbar.addWidget(add_irq_btn)
        
        edit_irq_btn = QPushButton("编辑中断")
        edit_irq_btn.setEnabled(False)
        toolbar.addWidget(edit_irq_btn)
        
        delete_irq_btn = QPushButton("删除中断")
        delete_irq_btn.setEnabled(False)
        toolbar.addWidget(delete_irq_btn)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # 中断表格（列顺序：名称、值、外设、描述）
        irq_table = QTableWidget()
        irq_table.setColumnCount(4)
        irq_table.setHorizontalHeaderLabels(["名称", "值", "外设", "描述"])
        
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
        
        # 保存控件引用
        self.widgets['interrupt_tab'] = tab
        self.widgets['irq_table'] = irq_table
        self.widgets['add_irq_btn'] = add_irq_btn
        self.widgets['edit_irq_btn'] = edit_irq_btn
        self.widgets['delete_irq_btn'] = delete_irq_btn
        
        tab_widget.addTab(tab, "中断")
        
        return tab
    
    def create_preview_tab(self, tab_widget):
        """创建预览标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 工具栏
        toolbar = QHBoxLayout()
        
        generate_btn = QPushButton("生成SVD")
        toolbar.addWidget(generate_btn)
        
        preview_btn = QPushButton("预览XML")
        toolbar.addWidget(preview_btn)
        
        export_btn = QPushButton("导出文件")
        toolbar.addWidget(export_btn)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # 预览文本编辑框
        preview_edit = QTextEdit()
        preview_edit.setReadOnly(True)
        preview_edit.setFontFamily("Courier New")
        preview_edit.setFontPointSize(10)
        layout.addWidget(preview_edit)
        
        # 保存控件引用
        self.widgets['preview_tab'] = tab
        self.widgets['preview_edit'] = preview_edit
        self.widgets['generate_btn'] = generate_btn
        self.widgets['preview_btn'] = preview_btn
        self.widgets['export_btn'] = export_btn
        
        tab_widget.addTab(tab, "预览/导出")
        
        return tab
    
    def get_widget(self, name: str):
        """获取控件"""
        return self.widgets.get(name)
    
    def update_data_stats(self, stats: Dict[str, int]):
        """更新数据统计"""
        if 'data_stats_label' in self.widgets:
            label = self.widgets['data_stats_label']
            text = f"外设: {stats.get('peripherals', 0)} | 寄存器: {stats.get('registers', 0)} | 位域: {stats.get('fields', 0)} | 中断: {stats.get('interrupts', 0)}"
            label.setText(text)
    
    def update_status(self, message: str):
        """更新状态栏消息"""
        if 'status_label' in self.widgets:
            self.widgets['status_label'].setText(message)

    def update_basic_info(self, device_info):
        """更新基础信息标签页的UI内容
        
        Args:
            device_info: DeviceInfo对象，包含设备信息
        """
        import sys
        print(f"[DEBUG LayoutManager] update_basic_info开始，device_info={device_info}", file=sys.stderr)
        try:
            # 映射字段到控件
            if 'ic_name_edit' in self.widgets:
                self.widgets['ic_name_edit'].setText(device_info.name)
            if 'ic_desc_edit' in self.widgets:
                self.widgets['ic_desc_edit'].setText(device_info.description)
            if 'version_edit' in self.widgets:
                self.widgets['version_edit'].setText(device_info.version)
            if 'svd_version_combo' in self.widgets:
                # 尝试设置SVD版本，如果不在下拉项中则添加
                combo = self.widgets['svd_version_combo']
                current_text = device_info.svd_version
                index = combo.findText(current_text)
                if index >= 0:
                    combo.setCurrentIndex(index)
                else:
                    combo.addItem(current_text)
                    combo.setCurrentText(current_text)
            if 'cpu_name_edit' in self.widgets:
                self.widgets['cpu_name_edit'].setText(device_info.cpu.name)
            if 'cpu_rev_edit' in self.widgets:
                self.widgets['cpu_rev_edit'].setText(device_info.cpu.revision)
            if 'endian_combo' in self.widgets:
                combo = self.widgets['endian_combo']
                current_text = device_info.cpu.endian
                index = combo.findText(current_text)
                if index >= 0:
                    combo.setCurrentIndex(index)
                else:
                    combo.addItem(current_text)
                    combo.setCurrentText(current_text)
            if 'mpu_combo' in self.widgets:
                combo = self.widgets['mpu_combo']
                # device_info.cpu.mpu_present 是布尔值，转换为"是"/"否"
                mpu_text = "是" if device_info.cpu.mpu_present else "否"
                index = combo.findText(mpu_text)
                if index >= 0:
                    combo.setCurrentIndex(index)
                else:
                    combo.addItem(mpu_text)
                    combo.setCurrentText(mpu_text)
            if 'fpu_combo' in self.widgets:
                combo = self.widgets['fpu_combo']
                fpu_text = "是" if device_info.cpu.fpu_present else "否"
                index = combo.findText(fpu_text)
                if index >= 0:
                    combo.setCurrentIndex(index)
                else:
                    combo.addItem(fpu_text)
                    combo.setCurrentText(fpu_text)
            if 'desc_edit' in self.widgets:
                # device_info.description 已经用于ic_desc_edit，这里使用description字段
                # 但可能没有单独的详细描述字段，暂留空
                pass
            if 'nvic_prio_spin' in self.widgets:
                self.widgets['nvic_prio_spin'].setValue(device_info.cpu.nvic_prio_bits)
            
            # 更新公司版权信息字段
            if 'company_name_edit' in self.widgets:
                self.widgets['company_name_edit'].setText(device_info.vendor)
            if 'copyright_edit' in self.widgets:
                self.widgets['copyright_edit'].setText(device_info.copyright)
            if 'author_edit' in self.widgets and 'author_checkbox' in self.widgets:
                # 更新作者字段和复选框状态
                author_edit = self.widgets['author_edit']
                author_checkbox = self.widgets['author_checkbox']
                
                # 如果作者字段为空或为None，则勾选"不显示"
                if not device_info.author or device_info.author.strip() == "":
                    author_checkbox.setChecked(True)
                    author_edit.clear()
                    author_edit.setEnabled(False)
                else:
                    author_checkbox.setChecked(False)
                    author_edit.setText(device_info.author)
                    author_edit.setEnabled(True)
            
            if 'license_combo' in self.widgets:
                # 更新许可证字段
                combo = self.widgets['license_combo']
                current_text = device_info.license
                
                # 如果许可证为空或为None，则设置为"不显示"
                if not current_text or current_text.strip() == "":
                    current_text = "不显示"
                
                index = combo.findText(current_text)
                if index >= 0:
                    combo.setCurrentIndex(index)
                else:
                    combo.addItem(current_text)
                    combo.setCurrentText(current_text)
            
            print(f"[DEBUG LayoutManager] update_basic_info完成", file=sys.stderr)
        except Exception as e:
            print(f"[DEBUG LayoutManager] update_basic_info异常: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)

    def update_field_table(self, peripheral_name: Optional[str] = None, register_name: Optional[str] = None, register=None):
        """更新位域表格
        
        Args:
            peripheral_name: 外设名称
            register_name: 寄存器名称
            register: 寄存器对象（如果提供，则忽略peripheral_name和register_name）
        """
        import sys
        print(f"[DEBUG LayoutManager] update_field_table开始，peripheral={peripheral_name}, register={register_name}, register对象={register}", file=sys.stderr)
        
        field_table = self.get_widget('field_table')
        if not field_table:
            print(f"[DEBUG LayoutManager] 未找到field_table控件", file=sys.stderr)
            return
        
        # 清除表格内容
        field_table.setRowCount(0)
        
        # 如果没有寄存器，清空表格
        if not register and (not peripheral_name or not register_name):
            print(f"[DEBUG LayoutManager] 无寄存器信息，清空表格", file=sys.stderr)
            return
        
        # 获取寄存器对象 - 通过main_window访问state_manager
        reg_obj = register
        if not reg_obj and peripheral_name and register_name:
            # 尝试通过main_window获取state_manager
            if hasattr(self.main_window, 'state_manager'):
                state_manager = self.main_window.state_manager
                device_info = state_manager.device_info
                if (peripheral_name in device_info.peripherals and
                    register_name in device_info.peripherals[peripheral_name].registers):
                    reg_obj = device_info.peripherals[peripheral_name].registers[register_name]
                    print(f"[DEBUG LayoutManager] 通过state_manager获取到寄存器对象", file=sys.stderr)
                else:
                    print(f"[DEBUG LayoutManager] 外设或寄存器不存在", file=sys.stderr)
                    return
            else:
                print(f"[DEBUG LayoutManager] main_window无state_manager属性", file=sys.stderr)
                return
        
        if not reg_obj:
            return
        
        # 获取位域列表
        fields = reg_obj.fields if hasattr(reg_obj, 'fields') else {}
        if not fields:
            print(f"[DEBUG LayoutManager] 寄存器无位域，清空表格", file=sys.stderr)
            field_table.setRowCount(0)
            return
        
        # 设置行数
        field_table.setRowCount(len(fields))
        
        # 填充表格
        for row, (field_name, field) in enumerate(fields.items()):
            # 名称
            name_item = QTableWidgetItem(field_name)
            field_table.setItem(row, 0, name_item)
            
            # 位偏移
            bit_offset_item = QTableWidgetItem(str(field.bit_offset))
            bit_offset_item.setFlags(bit_offset_item.flags() | Qt.ItemFlag.ItemIsEditable)
            field_table.setItem(row, 1, bit_offset_item)
            
            # 位宽
            bit_width_item = QTableWidgetItem(str(field.bit_width))
            bit_width_item.setFlags(bit_width_item.flags() | Qt.ItemFlag.ItemIsEditable)
            field_table.setItem(row, 2, bit_width_item)
            
            # 访问权限
            access_item = QTableWidgetItem(field.access if field.access else "")
            access_item.setFlags(access_item.flags() | Qt.ItemFlag.ItemIsEditable)
            field_table.setItem(row, 3, access_item)
            
            # 复位值
            reset_item = QTableWidgetItem(field.reset_value if field.reset_value else "")
            reset_item.setFlags(reset_item.flags() | Qt.ItemFlag.ItemIsEditable)
            field_table.setItem(row, 4, reset_item)
            
            # 描述
            desc_item = QTableWidgetItem(field.description if field.description else "")
            desc_item.setFlags(desc_item.flags() | Qt.ItemFlag.ItemIsEditable)
            field_table.setItem(row, 5, desc_item)
        
        print(f"[DEBUG LayoutManager] update_field_table完成，填充{len(fields)}行", file=sys.stderr)