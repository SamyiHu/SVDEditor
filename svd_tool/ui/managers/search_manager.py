"""
搜索管理器
负责处理搜索功能，包括树控件和表格的搜索
"""
import logging
from typing import List, Dict, Any, Optional

from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from ...i18n.i18n import t


class SearchManager(QObject):
    """搜索管理器"""
    
    # 信号定义
    search_results_updated = pyqtSignal(list)  # 搜索结果更新
    search_highlight_changed = pyqtSignal()  # 搜索高亮变化
    
    def __init__(self, coordinator=None):
        """初始化搜索管理器"""
        super().__init__()
        self.coordinator = coordinator
        self.logger = logging.getLogger("SearchManager")
        
        # 搜索相关
        self.search_results: List[Dict[str, Any]] = []
        self.current_search_index: int = -1
        
        self.logger.info("Search manager initialized")
    
    def set_coordinator(self, coordinator):
        """设置协调器（依赖注入）"""
        self.coordinator = coordinator
    
    def get_widget(self, widget_name: str):
        """获取控件（通过协调器）"""
        if self.coordinator:
            return self.coordinator.get_widget(widget_name)
        return None
    
    def search_in_tree(self, tree: QTreeWidget, search_text: str, tree_type: str):
        """在树中搜索"""
        if not tree or not search_text:
            return
        
        search_text = search_text.lower()
        # 不清除结果，由 perform_search 统一管理
        
        # 递归搜索所有项
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            self._search_tree_item(item, search_text, tree_type)
    
    def _search_tree_item(self, item: QTreeWidgetItem, search_text: str, tree_type: str):
        """递归搜索树项"""
        if not item:
            return
        
        # 检查当前项
        item_text = item.text(0).lower()
        if search_text in item_text:
            self.search_results.append({
                'type': tree_type,
                'item': item,
                'text': item.text(0)
            })
        
        # 递归搜索子项
        for i in range(item.childCount()):
            child = item.child(i)
            self._search_tree_item(child, search_text, tree_type)
    
    def search_in_table(self, table: QTableWidget, search_text: str, table_type: str):
        """在表格中搜索"""
        if not table or not search_text:
            return
        
        search_text = search_text.lower()
        # 不清除结果，由 perform_search 统一管理
        
        # 搜索所有行
        for row in range(table.rowCount()):
            for col in range(table.columnCount()):
                item = table.item(row, col)
                if item and search_text in item.text().lower():
                    self.search_results.append({
                        'type': table_type,
                        'table': table,
                        'row': row,
                        'col': col,
                        'text': item.text()
                    })
    
    def clear_search_highlights(self):
        """清除搜索高亮"""
        # 清除外设树高亮
        periph_tree = self.get_widget('periph_tree')
        if periph_tree:
            self._clear_tree_item_highlights(periph_tree.invisibleRootItem())
            periph_tree.clearSelection()  # 清除选中状态
        
        # 清除中断表格高亮
        irq_table = self.get_widget('irq_table')
        if irq_table:
            for row in range(irq_table.rowCount()):
                for col in range(irq_table.columnCount()):
                    item = irq_table.item(row, col)
                    if item:
                        item.setBackground(QBrush())
            irq_table.clearSelection()  # 清除选中状态
        
        self.search_results.clear()
        self.current_search_index = -1
        self._update_search_count()
    
    def _clear_tree_item_highlights(self, item: QTreeWidgetItem):
        """递归清除树项高亮"""
        if not item:
            return
        
        item.setBackground(0, QBrush())
        
        # 递归清除子项
        for i in range(item.childCount()):
            child = item.child(i)
            self._clear_tree_item_highlights(child)
    
    def _update_search_count(self):
        """更新搜索计数显示"""
        search_count_label = self.get_widget('search_count_label')
        if search_count_label:
            if self.search_results:
                search_count_label.setText(t("search.found", count=len(self.search_results)))
                search_count_label.setStyleSheet("color: green;")
            else:
                search_count_label.setText("无结果")
                search_count_label.setStyleSheet("color: gray;")
        
        # 更新按钮状态
        search_prev_btn = self.get_widget('search_prev_btn')
        search_next_btn = self.get_widget('search_next_btn')
        
        if search_prev_btn:
            search_prev_btn.setEnabled(len(self.search_results) > 0 and self.current_search_index > 0)
        if search_next_btn:
            search_next_btn.setEnabled(len(self.search_results) > 0 and 
                                      self.current_search_index < len(self.search_results) - 1)
    
    def _highlight_current_search_result(self):
        """高亮当前搜索结果"""
        if not self.search_results or self.current_search_index < 0:
            return
        
        result = self.search_results[self.current_search_index]
        
        if result['type'] == 'periph':
            # 高亮树项
            item = result['item']
            # 使用更明显的颜色，并设置所有列
            for col in range(item.columnCount()):
                item.setBackground(col, QBrush(QColor(255, 200, 100)))  # 橙黄色背景
            
            # 展开父项并滚动到该项
            tree = self.get_widget('periph_tree')
            if tree:
                tree.expandItem(item.parent() if item.parent() else item)
                tree.scrollToItem(item)
                tree.setCurrentItem(item)  # 选中该项
                
                # 切换到外设标签页
                tab_widget = self.get_widget('tab_widget')
                if tab_widget:
                    tab_widget.setCurrentIndex(1)  # 外设标签页索引
        
        elif result['type'] == 'irq':
            # 高亮表格行
            table = result['table']
            row = result['row']
            
            for col in range(table.columnCount()):
                item = table.item(row, col)
                if item:
                    item.setBackground(QBrush(QColor(255, 200, 100)))  # 橙黄色背景
            
            # 滚动到该行
            table.scrollToItem(table.item(row, 0))
            table.selectRow(row)  # 选中该行
            
            # 切换到中断标签页
            tab_widget = self.get_widget('tab_widget')
            if tab_widget:
                tab_widget.setCurrentIndex(2)  # 中断标签页索引
        
        self._update_search_count()
    
    def goto_next_result(self):
        """跳转到下一个搜索结果"""
        if not self.search_results:
            return
        
        # 清除当前高亮
        if self.current_search_index >= 0:
            self._clear_current_highlight()
        
        # 移动到下一个
        self.current_search_index += 1
        if self.current_search_index >= len(self.search_results):
            self.current_search_index = 0
        
        # 高亮新结果
        self._highlight_current_search_result()
    
    def goto_prev_result(self):
        """跳转到上一个搜索结果"""
        if not self.search_results:
            return
        
        # 清除当前高亮
        if self.current_search_index >= 0:
            self._clear_current_highlight()
        
        # 移动到上一个
        self.current_search_index -= 1
        if self.current_search_index < 0:
            self.current_search_index = len(self.search_results) - 1
        
        # 高亮新结果
        self._highlight_current_search_result()
    
    def _clear_current_highlight(self):
        """清除当前高亮"""
        if self.current_search_index < 0 or self.current_search_index >= len(self.search_results):
            return
        
        result = self.search_results[self.current_search_index]
        
        if result['type'] == 'periph':
            # 清除树项高亮
            item = result['item']
            for col in range(item.columnCount()):
                item.setBackground(col, QBrush())
            
            # 清除选中状态
            tree = self.get_widget('periph_tree')
            if tree:
                tree.clearSelection()
        
        elif result['type'] == 'irq':
            # 清除表格行高亮
            table = result['table']
            row = result['row']
            
            for col in range(table.columnCount()):
                item = table.item(row, col)
                if item:
                    item.setBackground(QBrush())
            
            # 清除选中状态
            table.clearSelection()
    
    def perform_search(self, search_text: str):
        """执行搜索（整合树和表格搜索，支持搜索类型选择）"""
        if not search_text:
            self.clear_search_highlights()
            return
        
        # 获取搜索类型
        search_type_combo = self.get_widget('search_type_combo')
        search_type = search_type_combo.currentData() if search_type_combo else 'all'
        
        # 清除之前的高亮和结果
        self.clear_search_highlights()
        self.search_results.clear()
        self.current_search_index = -1
        
        # 根据搜索类型决定搜索范围
        if search_type == 'all':
            # 搜索全部
            periph_tree = self.get_widget('periph_tree')
            if periph_tree:
                self.search_in_tree(periph_tree, search_text, 'periph')
            
            irq_table = self.get_widget('irq_table')
            if irq_table:
                self.search_in_table(irq_table, search_text, 'irq')
        elif search_type == 'peripheral':
            # 只搜索外设
            periph_tree = self.get_widget('periph_tree')
            if periph_tree:
                self.search_in_tree(periph_tree, search_text, 'periph')
        elif search_type == 'register':
            # 只搜索寄存器
            periph_tree = self.get_widget('periph_tree')
            if periph_tree:
                self.search_in_tree(periph_tree, search_text, 'register')
        elif search_type == 'field':
            # 只搜索位域
            periph_tree = self.get_widget('periph_tree')
            if periph_tree:
                self.search_in_tree(periph_tree, search_text, 'field')
        elif search_type == 'interrupt':
            # 只搜索中断
            irq_table = self.get_widget('irq_table')
            if irq_table:
                self.search_in_table(irq_table, search_text, 'irq')
        else:
            # 默认搜索全部
            periph_tree = self.get_widget('periph_tree')
            if periph_tree:
                self.search_in_tree(periph_tree, search_text, 'periph')
            
            irq_table = self.get_widget('irq_table')
            if irq_table:
                self.search_in_table(irq_table, search_text, 'irq')
        
        # 更新搜索计数
        self._update_search_count()
        
        # 如果有结果，跳转到第一个
        if self.search_results:
            self.current_search_index = 0
            self._highlight_current_search_result()
        else:
            self.logger.info(t("search.no_results", text=search_text))
    
    def connect_search_signals(self):
        """连接搜索相关信号"""
        search_edit = self.get_widget('search_edit')
        if search_edit:
            search_edit.textChanged.connect(self._on_search_text_changed)
        
        search_prev_btn = self.get_widget('search_prev_btn')
        if search_prev_btn:
            search_prev_btn.clicked.connect(self.goto_prev_result)
        
        search_next_btn = self.get_widget('search_next_btn')
        if search_next_btn:
            search_next_btn.clicked.connect(self.goto_next_result)
    
    def _on_search_text_changed(self, text: str):
        """搜索文本变化处理"""
        self.perform_search(text)