"""
SVD 导入合并对话框
选择源SVD文件 → 解析比较差异 → 用户选择合并项 → 执行合并
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget,
    QTreeWidgetItem, QLabel, QFileDialog, QGroupBox,
    QSplitter, QMessageBox, QHeaderView, QComboBox, QProgressBar,
    QCheckBox, QWidget, QTextEdit, QStyledItemDelegate, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QFont
import os

from ...core.svd_parser import SVDParser
from ...core.svd_merger import (
    SVDMerger, MergeAction, MergeConflictLevel, MergeItem
)
from ...core.data_model import DeviceInfo


# 颜色定义
COLOR_NEW = QColor(200, 255, 200)           # 绿色 - 新增
COLOR_ONLY_TARGET = QColor(230, 230, 230)    # 灰色 - 仅当前
COLOR_MODIFIED = QColor(255, 255, 200)       # 黄色 - 属性修改
COLOR_STRUCTURE = QColor(255, 210, 180)      # 橙色 - 结构变化
COLOR_NEW_TEXT = QColor(0, 128, 0)
COLOR_ONLY_TEXT = QColor(128, 128, 128)
COLOR_MODIFIED_TEXT = QColor(180, 120, 0)
COLOR_STRUCTURE_TEXT = QColor(200, 80, 0)


# 合并动作下拉框数据
ACTION_DATA = [
    ("保留当前", MergeAction.KEEP_TARGET),
    ("使用导入", MergeAction.USE_SOURCE),
    ("逐项合并", MergeAction.MERGE_BOTH),
]


class MergeActionDelegate(QStyledItemDelegate):
    """合并动作下拉委托"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._action_cache = {}  # tree_item -> MergeAction

    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        for text, action in ACTION_DATA:
            combo.addItem(text, action.value)
        return combo

    def setEditorData(self, editor, index):
        tree_item = self._get_tree_item(index)
        if tree_item:
            action = self._action_cache.get(id(tree_item), MergeAction.KEEP_TARGET)
            for i, (_, act) in enumerate(ACTION_DATA):
                if act == action:
                    editor.setCurrentIndex(i)
                    break

    def setModelData(self, editor, model, index):
        tree_item = self._get_tree_item(index)
        if tree_item:
            action_val = editor.currentData()
            action = MergeAction(action_val)
            self._action_cache[id(tree_item)] = action
            # 更新 MergeItem
            merge_item = tree_item.data(0, Qt.ItemDataRole.UserRole)
            if merge_item:
                merge_item.action = action
                self._update_row_display(tree_item, action)

    def _get_tree_item(self, index):
        tree = self.parent()
        if tree and isinstance(tree, QTreeWidget):
            return tree.itemFromIndex(index)
        return None

    def _update_row_display(self, tree_item: QTreeWidgetItem, action: MergeAction):
        """更新行的显示"""
        action_text = {a: t for t, a in ACTION_DATA}.get(action, "")
        tree_item.setText(3, action_text)


class SVDMergeDialog(QDialog):
    """SVD 导入合并对话框（整合了差异比较功能）"""

    merge_completed = pyqtSignal(DeviceInfo)  # 合并完成信号

    def __init__(self, parent=None, current_device: DeviceInfo = None, diff_only: bool = False):
        """初始化

        Args:
            parent: 父窗口
            current_device: 当前设备信息
            diff_only: 是否为仅差异比较模式（不显示合并功能）
        """
        super().__init__(parent)
        self._diff_only = diff_only
        self.setWindowTitle("SVD 文件差异比较" if diff_only else "SVD 文件导入合并")
        self.setMinimumSize(1000, 700)
        self.resize(1100, 750)
        self.current_device = current_device
        self.source_device = None
        self.merger = SVDMerger()
        self.merge_items: list = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # === 第1步：文件选择区域 ===
        file_group = QGroupBox("步骤 1：选择要导入的 SVD 文件")
        file_layout = QHBoxLayout(file_group)

        # 当前文件信息
        if self.current_device:
            curr_name = self.current_device.name or "未命名"
            curr_count = len(self.current_device.peripherals)
            curr_label = QLabel(f"当前文件: {curr_name} ({curr_count} 个外设)")
            from ...config.styles import get_style_scheme
            _c = get_style_scheme().colors
            curr_label.setStyleSheet(f"font-weight: bold; color: {_c.text_primary};")
            file_layout.addWidget(curr_label)

        file_layout.addWidget(QLabel("  导入文件: "), alignment=Qt.AlignmentFlag.AlignRight)

        self.file_label = QLabel("未选择文件")
        self.file_label.setStyleSheet("color: gray;")
        self.file_label.setMinimumWidth(250)
        file_layout.addWidget(self.file_label, 1)

        browse_btn = QPushButton("浏览...")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn)

        self.analyze_btn = QPushButton("分析差异")
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setStyleSheet("font-weight: bold; padding: 5px 15px;")
        self.analyze_btn.clicked.connect(self._do_analyze)
        file_layout.addWidget(self.analyze_btn)

        layout.addWidget(file_group)

        # === 第2步：合并选项（仅合并模式显示） ===
        self.option_group = QGroupBox("步骤 2：选择合并策略")
        opt_layout = QHBoxLayout(self.option_group)

        self.chk_auto_accept_new = QCheckBox("自动接受所有新增项")
        self.chk_auto_accept_new.setChecked(True)
        self.chk_auto_accept_new.setToolTip("新增的外设/寄存器/位域默认使用导入文件的版本")
        opt_layout.addWidget(self.chk_auto_accept_new)

        self.chk_ignore_desc = QCheckBox("忽略描述差异")
        opt_layout.addWidget(self.chk_ignore_desc)

        opt_layout.addStretch()

        # 快捷操作按钮
        select_all_new_btn = QPushButton("全部接受新增")
        select_all_new_btn.clicked.connect(self._select_all_new)
        opt_layout.addWidget(select_all_new_btn)

        select_none_btn = QPushButton("全部保留当前")
        select_none_btn.clicked.connect(self._select_all_keep)
        opt_layout.addWidget(select_none_btn)

        # diff_only 模式下隐藏合并选项
        if self._diff_only:
            self.option_group.hide()
        else:
            layout.addWidget(self.option_group)
        
        # diff_only 模式下也显示忽略描述选项
        if self._diff_only:
            diff_opt_layout = QHBoxLayout()
            self.chk_ignore_desc_diff = QCheckBox("忽略描述差异")
            self.chk_ignore_desc_diff.stateChanged.connect(self._re_analyze_if_has_data)
            diff_opt_layout.addWidget(self.chk_ignore_desc_diff)
            diff_opt_layout.addStretch()
            layout.addLayout(diff_opt_layout)

        # === 统计信息 ===
        self.stats_label = QLabel("请选择导入文件并点击\"分析差异\"")
        self.stats_label.setFont(QFont("", 10))
        from ...config.styles import get_style_scheme
        _c = get_style_scheme().colors
        self.stats_label.setStyleSheet(f"padding: 5px; background: {_c.light_gray}; border-radius: 3px;")
        layout.addWidget(self.stats_label)

        # === 第3步：差异合并树 ===
        splitter = QSplitter(Qt.Orientation.Vertical)

        self.merge_tree = QTreeWidget()
        self.merge_tree.setHeaderLabels(["合并项", "冲突级别", "当前值", "合并策略", "导入值"])
        self.merge_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.merge_tree.setColumnWidth(1, 100)
        self.merge_tree.setColumnWidth(2, 180)
        self.merge_tree.setColumnWidth(3, 100)
        self.merge_tree.setColumnWidth(4, 180)
        self.merge_tree.setAlternatingRowColors(True)
        self.merge_tree.itemChanged.connect(self._on_tree_item_changed)

        # 设置合并策略列为下拉委托
        self.action_delegate = MergeActionDelegate(self.merge_tree)
        self.merge_tree.setItemDelegateForColumn(3, self.action_delegate)

        splitter.addWidget(self.merge_tree)

        # 详情文本区域
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setFont(QFont("Consolas", 9))
        self.detail_text.setMaximumHeight(150)
        self.detail_text.setPlaceholderText("选中合并项后在此处显示详细信息...")
        splitter.addWidget(self.detail_text)

        splitter.setSizes([500, 150])
        layout.addWidget(splitter, 1)

        # === 底部按钮 ===
        btn_layout = QHBoxLayout()

        btn_layout.addStretch()

        self.merge_btn = QPushButton("执行合并")
        self.merge_btn.setEnabled(False)
        _mc = get_style_scheme().colors
        self.merge_btn.setStyleSheet(
            f"font-weight: bold; padding: 8px 25px; "
            f"background-color: {_mc.button_generate}; color: {_mc.text_white}; border-radius: 4px;"
        )
        self.merge_btn.clicked.connect(self._do_merge)
        # diff_only 模式下隐藏合并按钮
        if self._diff_only:
            self.merge_btn.hide()
        btn_layout.addWidget(self.merge_btn)

        close_btn = QPushButton("关闭")
        close_btn.setFixedWidth(80)
        close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _browse_file(self):
        """浏览选择要导入的 SVD 文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择要导入的 SVD 文件", "",
            "SVD 文件 (*.svd);;XML 文件 (*.xml)"
        )
        if not file_path:
            return

        try:
            parser = SVDParser()
            self.source_device = parser.parse_file(file_path)

            name = self.source_device.name or os.path.basename(file_path)
            n_periphs = len(self.source_device.peripherals)
            n_regs = sum(len(p.registers) for p in self.source_device.peripherals.values())
            self.file_label.setText(f"{name} ({n_periphs} 外设, {n_regs} 寄存器)")
            self.file_label.setStyleSheet("color: black;")

            self.analyze_btn.setEnabled(self.current_device is not None)

            if parser.warnings:
                QMessageBox.warning(self, "解析警告",
                    "\n".join(parser.warnings[:5]))

        except Exception as e:
            QMessageBox.critical(self, "解析失败", f"无法解析 SVD 文件:\n{str(e)}")

    def _re_analyze_if_has_data(self):
        """选项变化时重新分析（仅diff模式）"""
        if self.source_device and self.current_device:
            self._do_analyze()

    def _do_analyze(self):
        """执行差异分析"""
        if not self.current_device or not self.source_device:
            QMessageBox.warning(self, "提示", "请先选择要导入的 SVD 文件")
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.merge_items = self.merger.analyze(self.current_device, self.source_device)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "分析失败", f"差异分析出错:\n{str(e)}")
            return
        finally:
            QApplication.restoreOverrideCursor()

        # 如果忽略描述，过滤掉描述相关的 MergeItem
        if self.chk_ignore_desc.isChecked():
            self._filter_items(self.merge_items)

        # 更新统计
        counts = SVDMerger.count_items(self.merge_items)
        self.stats_label.setText(
            f"分析完成  |  "
            f"<span style='color:green'>新增: {counts['new_in_source']}</span>  "
            f"<span style='color:gray'>仅当前: {counts['only_in_target']}</span>  "
            f"<span style='color:orange'>属性修改: {counts['attr_modified']}</span>  "
            f"<span style='color:red'>结构变化: {counts['structure_changed']}</span>  "
            f"总计: {counts['total']} 项"
        )

        # 填充合并树
        self.merge_tree.blockSignals(True)
        self.merge_tree.clear()
        self._populate_tree(self.merge_tree.invisibleRootItem(), self.merge_items)
        self.merge_tree.blockSignals(False)

        # 展开第一层
        for i in range(self.merge_tree.topLevelItemCount()):
            self.merge_tree.topLevelItem(i).setExpanded(True)

        self.merge_btn.setEnabled(True)

    def _filter_items(self, items: list):
        """过滤描述相关的合并项（递归）"""
        to_remove = []
        for item in items:
            if 'Description' in item.path and item.level.endswith('_attr'):
                to_remove.append(item)
            elif item.children:
                self._filter_items(item.children)
        for item in to_remove:
            items.remove(item)

    def _populate_tree(self, parent, items: list):
        """递归填充合并树"""
        for item in items:
            tree_item = QTreeWidgetItem()

            # 显示名称
            path_parts = item.path.rsplit('.', 1)
            display_name = path_parts[-1] if len(path_parts) > 1 else item.path

            # 层级图标
            level_icons = {
                "peripheral": "📦",
                "register": "📋",
                "field": "🔖",
                "cluster": "📁",
                "interrupt": "⚡",
                "device": "🔧",
            }
            icon = level_icons.get(item.level, "")
            tree_item.setText(0, f"{icon} {display_name}" if icon else display_name)

            # 冲突级别
            level_text = {
                MergeConflictLevel.NEW_IN_SOURCE: "✅ 新增",
                MergeConflictLevel.ONLY_IN_TARGET: "➖ 仅当前",
                MergeConflictLevel.ATTR_MODIFIED: "⚠️ 属性修改",
                MergeConflictLevel.STRUCTURE_CHANGED: "🔴 结构变化",
            }.get(item.conflict_level, "")
            tree_item.setText(1, level_text)

            # 当前值
            tree_item.setText(2, self._format_value(item.target_obj))

            # 合并策略
            action_text = {a: t for t, a in ACTION_DATA}.get(item.action, "")
            tree_item.setText(3, action_text)

            # 导入值
            tree_item.setText(4, self._format_value(item.source_obj))

            # 存储数据
            tree_item.setData(0, Qt.ItemDataRole.UserRole, item)

            # 设置颜色
            self._set_item_colors(tree_item, item.conflict_level)

            # 设置 tooltip
            tree_item.setToolTip(0, item.path)

            # 递归添加子项
            if item.children:
                self._populate_tree(tree_item, item.children)

            parent.addChild(tree_item)

    def _format_value(self, obj) -> str:
        """格式化显示值"""
        if obj is None:
            return "(无)"
        if isinstance(obj, (int, float, str, bool)):
            s = str(obj)
            return s[:60] + "..." if len(s) > 60 else s
        if isinstance(obj, dict):
            if 'name' in obj:
                return str(obj['name'])
            return f"dict({len(obj)} items)"
        if hasattr(obj, 'name'):
            return obj.name
        return type(obj).__name__

    def _set_item_colors(self, tree_item: QTreeWidgetItem, conflict_level: MergeConflictLevel):
        """设置行颜色"""
        if conflict_level == MergeConflictLevel.NEW_IN_SOURCE:
            bg, fg = COLOR_NEW, COLOR_NEW_TEXT
        elif conflict_level == MergeConflictLevel.ONLY_IN_TARGET:
            bg, fg = COLOR_ONLY_TARGET, COLOR_ONLY_TEXT
        elif conflict_level == MergeConflictLevel.ATTR_MODIFIED:
            bg, fg = COLOR_MODIFIED, COLOR_MODIFIED_TEXT
        elif conflict_level == MergeConflictLevel.STRUCTURE_CHANGED:
            bg, fg = COLOR_STRUCTURE, COLOR_STRUCTURE_TEXT
        else:
            return

        for col in range(5):
            tree_item.setBackground(col, QBrush(bg))
            tree_item.setForeground(col, QBrush(fg))

    def _on_tree_item_changed(self, item: QTreeWidgetItem, column: int):
        """树项变化时处理"""
        if column == 0:
            # 复选框变化（暂不使用复选框，保留接口）
            pass

    def _select_all_new(self):
        """将所有新增项设为使用导入"""
        self._set_action_recursive(self.merge_items, MergeConflictLevel.NEW_IN_SOURCE, MergeAction.USE_SOURCE)
        self._refresh_tree_actions()

    def _select_all_keep(self):
        """将所有项设为保留当前"""
        self._set_action_recursive(self.merge_items, None, MergeAction.KEEP_TARGET)
        self._refresh_tree_actions()

    def _set_action_recursive(self, items: list, filter_level: MergeConflictLevel, action: MergeAction):
        """递归设置合并动作"""
        for item in items:
            if filter_level is None or item.conflict_level == filter_level:
                item.action = action
            if item.children:
                self._set_action_recursive(item.children, filter_level, action)

    def _refresh_tree_actions(self):
        """刷新树的合并策略显示"""
        self.merge_tree.blockSignals(True)
        self._refresh_tree_items(self.merge_tree.invisibleRootItem())
        self.merge_tree.blockSignals(False)

    def _refresh_tree_items(self, parent):
        """递归刷新树项"""
        for i in range(parent.childCount()):
            tree_item = parent.child(i)
            merge_item = tree_item.data(0, Qt.ItemDataRole.UserRole)
            if merge_item:
                action_text = {a: t for t, a in ACTION_DATA}.get(merge_item.action, "")
                tree_item.setText(3, action_text)
            self._refresh_tree_items(tree_item)

    def _do_merge(self):
        """执行合并"""
        if not self.merge_items:
            QMessageBox.warning(self, "提示", "请先分析差异")
            return

        # 确认操作
        counts = SVDMerger.count_items(self.merge_items)
        use_source_count = counts.get('use_source', 0)

        if use_source_count == 0:
            QMessageBox.information(self, "提示", "没有选择任何要合并的项目。请在合并策略列中选择\"使用导入\"。")
            return

        reply = QMessageBox.question(
            self, "确认合并",
            f"即将合并 {use_source_count} 项变更到当前文件。\n"
            f"此操作可以通过撤销(Ctrl+Z)回退。\n\n确定要执行合并吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            result_device, stats = self.merger.execute_merge(self.current_device, self.merge_items)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "合并失败", f"合并过程中出错:\n{str(e)}")
            return
        finally:
            QApplication.restoreOverrideCursor()

        # 生成摘要
        summary = self.merger.generate_summary(self.merge_items, stats)

        # 显示合并结果
        QMessageBox.information(self, "合并完成",
            f"合并已成功完成！\n\n"
            f"新增外设: {stats['peripherals_added']}\n"
            f"新增寄存器: {stats['registers_added']}\n"
            f"新增位域: {stats['fields_added']}\n"
            f"新增簇: {stats['clusters_added']}\n"
            f"新增中断: {stats['interrupts_added']}\n"
            f"属性更新: {stats['attrs_updated']}\n"
            f"跳过(保留): {stats['skipped']}"
        )

        # 发射合并完成信号
        self.merge_completed.emit(result_device)
        self.accept()