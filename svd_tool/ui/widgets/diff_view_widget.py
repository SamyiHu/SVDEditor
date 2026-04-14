# -*- coding: utf-8 -*-
"""
SVD差异比较视图组件
提供两个SVD文件的并排比较界面，逐条对齐显示
"""
import logging
from typing import Optional, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget,
    QTreeWidgetItem, QLabel, QPushButton, QHeaderView,
    QSplitter, QFrame, QSizePolicy, QTableWidget,
    QTableWidgetItem, QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QFont

from ...core.svd_differ import DiffType, DiffItem, SVDDiffer
from ...core.data_model import DeviceInfo


# 颜色定义
COLOR_ADDED_BG = QColor(220, 255, 220)
COLOR_REMOVED_BG = QColor(255, 220, 220)
COLOR_MODIFIED_BG = QColor(255, 255, 210)
COLOR_ADDED_TEXT = QColor(0, 120, 0)
COLOR_REMOVED_TEXT = QColor(180, 0, 0)
COLOR_MODIFIED_TEXT = QColor(160, 100, 0)


class DiffHeaderView(QWidget):
    """差异比较头部 - 显示两个SVD型号对比"""
    
    def __init__(self, name_a: str, name_b: str, parent=None):
        super().__init__(parent)
        self._setup_ui(name_a, name_b)
    
    def _setup_ui(self, name_a: str, name_b: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(0)
        
        # 左侧：文档A名称
        left_frame = QFrame()
        from ...config.styles import get_style_scheme
        _dc = get_style_scheme().colors
        left_frame.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {_dc.diff_header_a_gradient_start}, stop:1 {_dc.diff_header_a_gradient_end});
                border: 1px solid {_dc.diff_header_a_border};
                border-radius: 6px;
                padding: 6px 12px;
            }}
        """)
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(12, 6, 12, 6)
        left_layout.setSpacing(2)
        
        label_a_title = QLabel("基准 (A)")
        from ...config.styles import get_style_scheme
        _dc = get_style_scheme().colors
        label_a_title.setStyleSheet(f"color: {_dc.diff_label_a_title_color}; font-size: 11px; font-weight: bold; border: none;")
        label_a_name = QLabel(name_a)
        label_a_name.setStyleSheet(f"color: {_dc.diff_label_a_name_color}; font-size: 13px; font-weight: bold; border: none;")
        label_a_name.setWordWrap(True)
        # 确保完整显示
        label_a_name.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        left_layout.addWidget(label_a_title)
        left_layout.addWidget(label_a_name)
        
        # 中间：VS + 统计
        center_frame = QFrame()
        center_frame.setStyleSheet("QFrame { background: transparent; }")
        center_layout = QVBoxLayout(center_frame)
        center_layout.setContentsMargins(6, 0, 6, 0)
        center_layout.setSpacing(2)
        
        vs_label = QLabel("VS")
        vs_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vs_label.setStyleSheet(f"""
            font-size: 16px; font-weight: bold; color: {_dc.gray};
            background: transparent; border: none;
        """)
        center_layout.addWidget(vs_label)
        
        self._stats_label = QLabel("")
        self._stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stats_label.setStyleSheet(f"""
            font-size: 10px; color: {_dc.dark_gray};
            background: transparent; border: none;
        """)
        center_layout.addWidget(self._stats_label)
        
        center_frame.setFixedWidth(100)
        
        # 右侧：文档B名称
        right_frame = QFrame()
        right_frame.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {_dc.diff_header_b_gradient_start}, stop:1 {_dc.diff_header_b_gradient_end});
                border: 1px solid {_dc.diff_header_b_border};
                border-radius: 6px;
                padding: 6px 12px;
            }}
        """)
        right_layout = QVBoxLayout(right_frame)
        right_layout.setContentsMargins(12, 6, 12, 6)
        right_layout.setSpacing(2)
        
        label_b_title = QLabel("比较 (B)")
        label_b_title.setStyleSheet(f"color: {_dc.diff_label_b_title_color}; font-size: 11px; font-weight: bold; border: none;")
        label_b_name = QLabel(name_b)
        label_b_name.setStyleSheet(f"color: {_dc.diff_label_b_name_color}; font-size: 13px; font-weight: bold; border: none;")
        label_b_name.setWordWrap(True)
        label_b_name.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        right_layout.addWidget(label_b_title)
        right_layout.addWidget(label_b_name)
        
        layout.addWidget(left_frame, 1)
        layout.addWidget(center_frame)
        layout.addWidget(right_frame, 1)
    
    def set_stats(self, added: int, removed: int, modified: int, total: int):
        """更新统计信息"""
        self._stats_label.setText(
            f"<span style='color:green'>+{added}</span> "
            f"<span style='color:red'>-{removed}</span> "
            f"<span style='color:orange'>~{modified}</span>"
        )


class DiffViewWidget(QWidget):
    """SVD差异比较视图
    
    显示两个SVD文件的并排对比，包含：
    - 顶部显示两个型号名称的对比头
    - 并排表格：左侧A、右侧B，逐条对齐
    - 差异用颜色标注
    
    信号：
        close_requested: 关闭比较标签请求
    """
    
    close_requested = pyqtSignal()
    diff_item_clicked = pyqtSignal(str, str)  # (item_type, item_path)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger("DiffViewWidget")
        self._diffs: List[DiffItem] = []
        self._differ: Optional[SVDDiffer] = None
        self._name_a = ""
        self._name_b = ""
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 头部占位（稍后由 set_diff_data 设置）
        self._header: Optional[DiffHeaderView] = None
        self._header_placeholder = QLabel("等待比较数据...")
        self._header_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._header_placeholder.setStyleSheet("color: gray; padding: 20px;")
        layout.addWidget(self._header_placeholder)
        
        # 统计栏
        self._stats_bar = QLabel("")
        from ...config.styles import get_style_scheme
        _dc = get_style_scheme().colors
        self._stats_bar.setStyleSheet(f"""
            QLabel {{
                background: {_dc.diff_stats_bar_background};
                border-top: 1px solid {_dc.diff_stats_bar_border};
                border-bottom: 1px solid {_dc.diff_stats_bar_border};
                padding: 4px 12px;
                font-size: 11px;
            }}
        """)
        self._stats_bar.hide()
        layout.addWidget(self._stats_bar)
        
        # 并排比较表格
        self._diff_table = QTableWidget()
        self._diff_table.setColumnCount(5)
        self._diff_table.setHorizontalHeaderLabels(["类型", "属性", "A (基准)", "B (比较)", "状态"])
        self._diff_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._diff_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._diff_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._diff_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._diff_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._diff_table.setAlternatingRowColors(True)
        self._diff_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._diff_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._diff_table.verticalHeader().setDefaultSectionSize(24)
        self._diff_table.setStyleSheet(f"""
            QTableWidget {{
                border: none;
                font-size: 12px;
                gridline-color: {_dc.diff_table_gridline};
            }}
            QTableWidget::item {{
                padding: 2px 6px;
            }}
            QTableWidget::item:hover {{
                background: {_dc.diff_table_hover};
            }}
            QHeaderView::section {{
                background: {_dc.diff_table_header_background};
                border: none;
                border-bottom: 2px solid {_dc.diff_table_gridline};
                border-right: 1px solid {_dc.diff_table_gridline};
                padding: 4px 8px;
                font-weight: bold;
                font-size: 11px;
            }}
        """)
        layout.addWidget(self._diff_table, 1)
    
    def set_diff_data(self, device_a: DeviceInfo, device_b: DeviceInfo,
                      name_a: str = "文档A", name_b: str = "文档B"):
        """设置比较数据并执行比较
        
        Args:
            device_a: 基准DeviceInfo
            device_b: 比较DeviceInfo
            name_a: 基准名称
            name_b: 比较名称
        """
        self._name_a = name_a
        self._name_b = name_b
        
        try:
            # 执行比较
            self._differ = SVDDiffer()
            self._diffs = self._differ.diff(device_a, device_b)
            self.logger.info(f"比较完成，获得 {len(self._diffs)} 个顶层差异项")
        except Exception as e:
            self.logger.error(f"比较执行失败: {e}")
            import traceback
            traceback.print_exc()
            self._diffs = []
        
        # 替换占位为真正的头部
        if self._header:
            self._header.deleteLater()
        
        self.layout().removeWidget(self._header_placeholder)
        self._header_placeholder.deleteLater()
        
        self._header = DiffHeaderView(name_a, name_b, self)
        self.layout().insertWidget(0, self._header)
        
        # 计算统计
        added = sum(d.count_changes for d in self._diffs if self._has_type(d, DiffType.ADDED))
        removed = sum(d.count_changes for d in self._diffs if self._has_type(d, DiffType.REMOVED))
        modified = sum(d.count_changes for d in self._diffs if self._has_type(d, DiffType.MODIFIED))
        total = added + removed + modified
        
        # 更新头部统计
        self._header.set_stats(added, removed, modified, total)
        
        # 更新统计栏
        from ...config.styles import get_style_scheme
        _dc = get_style_scheme().colors
        self._stats_bar.setText(
            f"  📊 比较: <b>{name_a}</b> vs <b>{name_b}</b>  │  "
            f"<span style='color:{_dc.diff_stats_added_color}'>✚ 新增: {added}</span>  "
            f"<span style='color:{_dc.diff_stats_removed_color}'>✖ 删除: {removed}</span>  "
            f"<span style='color:{_dc.diff_stats_modified_color}'>✎ 修改: {modified}</span>  "
            f"│ 总计: {total} 项变更"
        )
        self._stats_bar.show()
        
        if total == 0:
            # 没有差异时显示提示
            self._diff_table.setRowCount(1)
            no_diff_item = QTableWidgetItem("✅ 两个SVD文件完全一致，没有发现差异")
            no_diff_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            no_diff_item.setFlags(no_diff_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            font = no_diff_item.font()
            font.setPointSize(12)
            no_diff_item.setFont(font)
            self._diff_table.setItem(0, 0, no_diff_item)
            self._diff_table.setSpan(0, 0, 1, 5)
            self.logger.info("两个SVD文件完全一致")
        else:
            # 填充并排表格
            self._populate_table(self._diffs)
    
    def _populate_table(self, items: List[DiffItem]):
        """将差异项填充到并排表格中"""
        rows = []
        self._flatten_diffs(items, rows, "")
        
        self._diff_table.setRowCount(len(rows))
        
        for row_idx, (item_type, prop, old_val, new_val, status, diff_type, path) in enumerate(rows):
            # 类型列
            type_item = QTableWidgetItem(item_type)
            type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._diff_table.setItem(row_idx, 0, type_item)
            
            # 属性列
            prop_item = QTableWidgetItem(prop)
            self._diff_table.setItem(row_idx, 1, prop_item)
            
            # A列（基准值）
            a_item = QTableWidgetItem(old_val)
            self._diff_table.setItem(row_idx, 2, a_item)
            
            # B列（比较值）
            b_item = QTableWidgetItem(new_val)
            self._diff_table.setItem(row_idx, 3, b_item)
            
            # 状态列
            status_map = {
                DiffType.ADDED: "✚ 新增",
                DiffType.REMOVED: "✖ 删除",
                DiffType.MODIFIED: "✎ 修改",
                DiffType.UNCHANGED: "",
            }
            status_item = QTableWidgetItem(status_map.get(diff_type, ""))
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._diff_table.setItem(row_idx, 4, status_item)
            
            # 设置行颜色
            bg_color = None
            fg_color = None
            if diff_type == DiffType.ADDED:
                bg_color = COLOR_ADDED_BG
                fg_color = COLOR_ADDED_TEXT
            elif diff_type == DiffType.REMOVED:
                bg_color = COLOR_REMOVED_BG
                fg_color = COLOR_REMOVED_TEXT
            elif diff_type == DiffType.MODIFIED:
                bg_color = COLOR_MODIFIED_BG
                fg_color = COLOR_MODIFIED_TEXT
            
            if bg_color and fg_color:
                for col in range(5):
                    cell = self._diff_table.item(row_idx, col)
                    if cell:
                        cell.setBackground(QBrush(bg_color))
                        cell.setForeground(QBrush(fg_color))
            
            # 设置tooltip为完整路径
            for col in range(5):
                cell = self._diff_table.item(row_idx, col)
                if cell:
                    cell.setToolTip(path)
        
        self._diff_table.resizeRowsToContents()
    
    def _flatten_diffs(self, items: List[DiffItem], rows: list, parent_path: str):
        """将树形差异项扁平化为行列表"""
        for item in items:
            path_parts = item.path.rsplit('.', 1)
            display_name = path_parts[-1] if len(path_parts) > 1 else item.path
            
            # 判断类型（外设/寄存器/位域/属性）
            parts = item.path.split('.')
            if len(parts) == 1:
                item_type = "外设"
            elif len(parts) == 2:
                item_type = "寄存器"
            elif len(parts) == 3:
                item_type = "位域"
            else:
                item_type = "属性"
            
            old_str = str(item.old_value) if item.old_value is not None else ""
            new_str = str(item.new_value) if item.new_value is not None else ""
            if len(old_str) > 150:
                old_str = old_str[:147] + "..."
            if len(new_str) > 150:
                new_str = new_str[:147] + "..."
            
            rows.append((item_type, display_name, old_str, new_str, "", item.diff_type, item.path))
            
            # 递归处理子项
            if item.children:
                self._flatten_diffs(item.children, rows, item.path)
    
    def get_summary(self) -> str:
        """获取差异摘要文本"""
        if self._differ:
            return self._differ.generate_summary(self._diffs)
        return ""
    
    def _has_type(self, item: DiffItem, diff_type: DiffType) -> bool:
        """递归检查差异类型"""
        if item.diff_type == diff_type:
            return True
        return any(self._has_type(c, diff_type) for c in item.children)