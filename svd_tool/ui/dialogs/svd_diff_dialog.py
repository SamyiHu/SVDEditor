"""
SVD Diff 对话框
提供两个 SVD 文件的结构化比较界面
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget,
    QTreeWidgetItem, QLabel, QFileDialog, QCheckBox, QGroupBox,
    QSplitter, QTextEdit, QMessageBox, QProgressBar, QHeaderView
)
import os
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QFont

from ...core.svd_parser import SVDParser
from ...core.svd_differ import SVDDiffer, DiffType, DiffItem
from ...core.data_model import DeviceInfo


# 颜色定义
COLOR_ADDED = QColor(200, 255, 200)      # 绿色背景 - 新增
COLOR_REMOVED = QColor(255, 200, 200)     # 红色背景 - 删除
COLOR_MODIFIED = QColor(255, 255, 200)    # 黄色背景 - 修改
COLOR_ADDED_TEXT = QColor(0, 128, 0)
COLOR_REMOVED_TEXT = QColor(200, 0, 0)
COLOR_MODIFIED_TEXT = QColor(180, 120, 0)


class SVDDiffDialog(QDialog):
    """SVD 差异比较对话框"""

    def __init__(self, parent=None, current_device: DeviceInfo = None):
        super().__init__(parent)
        self.setWindowTitle("SVD 文件比较 (Diff)")
        self.setMinimumSize(900, 650)
        self.current_device = current_device
        self.other_device = None
        self.differ = SVDDiffer()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 文件选择区域
        file_group = QGroupBox("选择比较文件")
        file_layout = QHBoxLayout(file_group)

        self.file_label = QLabel("未选择文件")
        self.file_label.setStyleSheet("color: gray;")
        file_layout.addWidget(self.file_label, 1)

        browse_btn = QPushButton("选择 SVD 文件...")
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn)

        # 使用当前已打开的文件
        if self.current_device:
            info = f"当前: {self.current_device.name or '未命名'} ({len(self.current_device.peripherals)} 外设)"
            self.file_label.setText(info)
            self.file_label.setStyleSheet("color: black;")

        layout.addWidget(file_group)

        # 过滤选项
        filter_group = QGroupBox("比较选项")
        filter_layout = QHBoxLayout(filter_group)

        self.chk_description = QCheckBox("忽略描述")
        self.chk_description.stateChanged.connect(self._re_diff)
        filter_layout.addWidget(self.chk_description)

        self.chk_display_name = QCheckBox("忽略显示名称")
        self.chk_display_name.stateChanged.connect(self._re_diff)
        filter_layout.addWidget(self.chk_display_name)

        self.chk_reset_value = QCheckBox("忽略复位值")
        self.chk_reset_value.stateChanged.connect(self._re_diff)
        filter_layout.addWidget(self.chk_reset_value)

        filter_layout.addStretch()

        # 比较按钮
        self.compare_btn = QPushButton("开始比较")
        self.compare_btn.setEnabled(False)
        self.compare_btn.clicked.connect(self._do_compare)
        self.compare_btn.setStyleSheet("font-weight: bold; padding: 6px;")
        filter_layout.addWidget(self.compare_btn)

        layout.addWidget(filter_group)

        # 结果区域 - 分割器
        splitter = QSplitter(Qt.Orientation.Vertical)

        # 统计标签
        self.stats_label = QLabel("请选择文件并点击比较")
        self.stats_label.setFont(QFont("", 10, QFont.Weight.Bold))
        splitter.addWidget(self.stats_label)

        # 差异树
        self.diff_tree = QTreeWidget()
        self.diff_tree.setHeaderLabels(["差异项", "类型", "旧值", "新值"])
        self.diff_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.diff_tree.setColumnWidth(1, 80)
        self.diff_tree.setColumnWidth(2, 200)
        self.diff_tree.setColumnWidth(3, 200)
        self.diff_tree.setAlternatingRowColors(True)
        splitter.addWidget(self.diff_tree)

        # 文本摘要
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setFont(QFont("Consolas", 9))
        self.summary_text.setMaximumHeight(180)
        splitter.addWidget(self.summary_text)

        splitter.setSizes([30, 400, 180])
        layout.addWidget(splitter)

        # 底部按钮
        btn_layout = QHBoxLayout()

        export_btn = QPushButton("导出差异报告...")
        export_btn.clicked.connect(self._export_report)
        btn_layout.addWidget(export_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _browse_file(self):
        """浏览选择 SVD 文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择要比较的 SVD 文件", "", "SVD 文件 (*.svd);;XML 文件 (*.xml)"
        )
        if not file_path:
            return

        try:
            parser = SVDParser()
            self.other_device = parser.parse_file(file_path)

            name = self.other_device.name or os.path.basename(file_path)
            n_periphs = len(self.other_device.peripherals)
            self.file_label.setText(f"比较文件: {name} ({n_periphs} 外设)")
            self.file_label.setStyleSheet("color: black;")

            self.compare_btn.setEnabled(self.current_device is not None)

            if parser.warnings:
                QMessageBox.warning(self, "解析警告",
                    "\n".join(parser.warnings[:5]))

        except Exception as e:
            QMessageBox.critical(self, "解析失败", f"无法解析 SVD 文件:\n{str(e)}")

    def _re_diff(self):
        """选项变化时重新比较"""
        if self.other_device and self.current_device:
            self._do_compare()

    def _do_compare(self):
        """执行比较"""
        if not self.current_device or not self.other_device:
            QMessageBox.warning(self, "提示", "请先选择要比较的 SVD 文件")
            return

        # 应用过滤选项
        self.differ.ignore_description = self.chk_description.isChecked()
        self.differ.ignore_display_name = self.chk_display_name.isChecked()
        self.differ.ignore_reset_value = self.chk_reset_value.isChecked()

        # 执行比较
        diffs = self.differ.diff(self.current_device, self.other_device)

        # 统计
        added = sum(d.count_changes for d in diffs if self._has_type(d, DiffType.ADDED))
        removed = sum(d.count_changes for d in diffs if self._has_type(d, DiffType.REMOVED))
        modified = sum(d.count_changes for d in diffs if self._has_type(d, DiffType.MODIFIED))
        total = added + removed + modified

        old_name = self.current_device.name or "当前"
        new_name = self.other_device.name or "比较文件"
        self.stats_label.setText(
            f"比较: {old_name} vs {new_name}  |  "
            f"<span style='color:green'>新增: {added}</span>  "
            f"<span style='color:red'>删除: {removed}</span>  "
            f"<span style='color:orange'>修改: {modified}</span>  "
            f"总计: {total} 项变更"
        )

        # 填充差异树
        self.diff_tree.clear()
        self._populate_tree(self.diff_tree.invisibleRootItem(), diffs)

        # 生成文本摘要
        summary = self.differ.generate_summary(diffs)
        self.summary_text.setPlainText(summary)

    def _populate_tree(self, parent: QTreeWidgetItem, items: list):
        """递归填充差异树"""
        for item in items:
            tree_item = QTreeWidgetItem()

            # 设置显示文本
            path_parts = item.path.rsplit('.', 1)
            display_name = path_parts[-1] if len(path_parts) > 1 else item.path
            tree_item.setText(0, display_name)

            # 类型
            type_text = {
                DiffType.ADDED: "新增 [+]",
                DiffType.REMOVED: "删除 [-]",
                DiffType.MODIFIED: "修改 [~]",
                DiffType.UNCHANGED: "",
            }.get(item.diff_type, "")
            tree_item.setText(1, type_text)

            # 旧值/新值
            old_str = str(item.old_value) if item.old_value is not None else ""
            new_str = str(item.new_value) if item.new_value is not None else ""
            # 截断过长的值
            if len(old_str) > 100:
                old_str = old_str[:97] + "..."
            if len(new_str) > 100:
                new_str = new_str[:97] + "..."
            tree_item.setText(2, old_str)
            tree_item.setText(3, new_str)

            # 设置颜色
            if item.diff_type == DiffType.ADDED:
                for col in range(4):
                    tree_item.setBackground(col, QBrush(COLOR_ADDED))
                    tree_item.setForeground(col, QBrush(COLOR_ADDED_TEXT))
            elif item.diff_type == DiffType.REMOVED:
                for col in range(4):
                    tree_item.setBackground(col, QBrush(COLOR_REMOVED))
                    tree_item.setForeground(col, QBrush(COLOR_REMOVED_TEXT))
            elif item.diff_type == DiffType.MODIFIED:
                for col in range(4):
                    tree_item.setBackground(col, QBrush(COLOR_MODIFIED))
                    tree_item.setForeground(col, QBrush(COLOR_MODIFIED_TEXT))

            # 设置路径完整信息为 tooltip
            tree_item.setToolTip(0, item.path)

            # 递归添加子项
            if item.children:
                self._populate_tree(tree_item, item.children)

            parent.addChild(tree_item)

        # 展开第一层
        if isinstance(parent, QTreeWidgetItem):
            parent.setExpanded(True)
        else:
            # invisibleRootItem 的子项
            for i in range(self.diff_tree.topLevelItemCount()):
                self.diff_tree.topLevelItem(i).setExpanded(True)

    def _has_type(self, item: DiffItem, diff_type: DiffType) -> bool:
        """递归检查差异类型"""
        if item.diff_type == diff_type:
            return True
        return any(self._has_type(c, diff_type) for c in item.children)

    def _export_report(self):
        """导出差异报告"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出差异报告", "svd_diff_report.txt",
            "文本文件 (*.txt);;Markdown (*.md)"
        )
        if not file_path:
            return

        try:
            summary = self.summary_text.toPlainText()
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(summary)
            QMessageBox.information(self, "导出成功", f"差异报告已保存到:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))