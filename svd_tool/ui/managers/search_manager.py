"""
搜索管理器
负责处理搜索功能，包括树控件和表格的搜索
支持深度搜索（描述、地址、复位值等数据模型内容）
支持统一搜索语法：type:peripheral name:GPIO* addr:0x4001* access:read-write
"""
import logging
import re
from typing import List, Dict, Any, Optional, Tuple

from PyQt6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem,
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QComboBox, QLineEdit, QSizePolicy
)
from PyQt6.QtCore import QObject, pyqtSignal, Qt
from PyQt6.QtGui import QBrush, QColor, QIcon
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
        
        # 深度搜索结果面板
        self._results_panel: Optional[QWidget] = None
        self._results_list: Optional[QListWidget] = None
        
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
    
    # ==================== 深度搜索（数据模型搜索） ====================
    
    def deep_search(self, search_text: str, search_scope: str = 'all') -> List[Dict[str, Any]]:
        """
        深度搜索数据模型：搜索名称、描述、地址、复位值、访问权限等所有属性
        
        Args:
            search_text: 搜索文本
            search_scope: 搜索范围 'all'/'name'/'description'/'address'/'value'
        
        Returns:
            匹配结果列表，每项包含:
              - level: 'peripheral'/'register'/'field'/'interrupt'
              - path: 显示路径 (e.g. "GPIOA > MODER > MODE0")
              - peripheral/register/field: 对应数据对象
              - match_field: 匹配的字段名
              - match_text: 匹配的文本片段
        """
        if not search_text:
            return []
        
        results = []
        text_lower = search_text.lower()
        state_mgr = self._get_state_manager()
        if not state_mgr:
            return results
        
        device = state_mgr.device_info
        
        # 搜索外设
        for pname, periph in device.peripherals.items():
            if search_scope in ('all', 'name') and text_lower in pname.lower():
                results.append({
                    'level': 'peripheral', 'path': pname,
                    'peripheral': pname, 'register': None, 'field': None,
                    'match_field': 'name', 'match_text': pname
                })
            if search_scope in ('all', 'description') and periph.description and text_lower in periph.description.lower():
                results.append({
                    'level': 'peripheral', 'path': pname,
                    'peripheral': pname, 'register': None, 'field': None,
                    'match_field': 'description', 'match_text': periph.description[:80]
                })
            if search_scope in ('all', 'address') and text_lower in periph.base_address.lower():
                results.append({
                    'level': 'peripheral', 'path': f"{pname} ({periph.base_address})",
                    'peripheral': pname, 'register': None, 'field': None,
                    'match_field': 'base_address', 'match_text': periph.base_address
                })
            
            # 搜索寄存器
            for rname, reg in periph.registers.items():
                reg_path = f"{pname} > {rname}"
                if search_scope in ('all', 'name') and text_lower in rname.lower():
                    results.append({
                        'level': 'register', 'path': reg_path,
                        'peripheral': pname, 'register': rname, 'field': None,
                        'match_field': 'name', 'match_text': rname
                    })
                if search_scope in ('all', 'description') and reg.description and text_lower in reg.description.lower():
                    results.append({
                        'level': 'register', 'path': reg_path,
                        'peripheral': pname, 'register': rname, 'field': None,
                        'match_field': 'description', 'match_text': reg.description[:80]
                    })
                if search_scope in ('all', 'address') and text_lower in reg.offset.lower():
                    results.append({
                        'level': 'register', 'path': f"{reg_path} (偏移: {reg.offset})",
                        'peripheral': pname, 'register': rname, 'field': None,
                        'match_field': 'offset', 'match_text': reg.offset
                    })
                if search_scope in ('all', 'value') and text_lower in reg.reset_value.lower():
                    results.append({
                        'level': 'register', 'path': f"{reg_path} (复位值: {reg.reset_value})",
                        'peripheral': pname, 'register': rname, 'field': None,
                        'match_field': 'reset_value', 'match_text': reg.reset_value
                    })
                if search_scope in ('all', 'name') and reg.access and text_lower in reg.access.lower():
                    results.append({
                        'level': 'register', 'path': f"{reg_path} (访问: {reg.access})",
                        'peripheral': pname, 'register': rname, 'field': None,
                        'match_field': 'access', 'match_text': reg.access
                    })
                
                # 搜索位域
                for fname, fld in reg.fields.items():
                    field_path = f"{pname} > {rname} > {fname}"
                    if search_scope in ('all', 'name') and text_lower in fname.lower():
                        results.append({
                            'level': 'field', 'path': field_path,
                            'peripheral': pname, 'register': rname, 'field': fname,
                            'match_field': 'name', 'match_text': fname
                        })
                    if search_scope in ('all', 'description') and fld.description and text_lower in fld.description.lower():
                        results.append({
                            'level': 'field', 'path': field_path,
                            'peripheral': pname, 'register': rname, 'field': fname,
                            'match_field': 'description', 'match_text': fld.description[:80]
                        })
                    # 按位范围搜索 (e.g. "7:4" or "bit 5")
                    bit_str = str(fld.bit_offset) if fld.bit_width == 1 else f"{fld.bit_offset + fld.bit_width - 1}:{fld.bit_offset}"
                    if search_scope in ('all', 'address') and text_lower in bit_str:
                        results.append({
                            'level': 'field', 'path': f"{field_path} [{bit_str}]",
                            'peripheral': pname, 'register': rname, 'field': fname,
                            'match_field': 'bit_range', 'match_text': bit_str
                        })
                    if search_scope in ('all', 'value') and text_lower in fld.reset_value.lower():
                        results.append({
                            'level': 'field', 'path': field_path,
                            'peripheral': pname, 'register': rname, 'field': fname,
                            'match_field': 'reset_value', 'match_text': fld.reset_value
                        })
                    # 搜索位域访问权限
                    if fld.access and text_lower in fld.access.lower():
                        results.append({
                            'level': 'field', 'path': f"{field_path} ({fld.access})",
                            'peripheral': pname, 'register': rname, 'field': fname,
                            'match_field': 'access', 'match_text': fld.access
                        })
        
        # 搜索中断
        for iname, irq in device.interrupts.items():
            irq_path = f"中断: {iname}"
            if search_scope in ('all', 'name') and text_lower in iname.lower():
                results.append({
                    'level': 'interrupt', 'path': irq_path,
                    'peripheral': None, 'register': None, 'field': None,
                    'interrupt': iname,
                    'match_field': 'name', 'match_text': iname
                })
            if search_scope in ('all', 'description') and irq.description and text_lower in irq.description.lower():
                results.append({
                    'level': 'interrupt', 'path': irq_path,
                    'peripheral': None, 'register': None, 'field': None,
                    'interrupt': iname,
                    'match_field': 'description', 'match_text': irq.description[:80]
                })
            # 按中断号搜索
            if search_scope in ('all', 'value') and text_lower in str(irq.value):
                results.append({
                    'level': 'interrupt', 'path': f"{irq_path} (IRQ#{irq.value})",
                    'peripheral': None, 'register': None, 'field': None,
                    'interrupt': iname,
                    'match_field': 'irq_number', 'match_text': str(irq.value)
                })
        
        return results
    
    def goto_address(self, address_text: str) -> bool:
        """
        按地址跳转：输入地址（如 0x40010000），自动定位到对应的外设和寄存器
        
        Args:
            address_text: 地址字符串（十六进制）
        
        Returns:
            是否找到匹配项
        """
        state_mgr = self._get_state_manager()
        if not state_mgr:
            return False
        
        try:
            addr = int(address_text.strip(), 16)
        except ValueError:
            try:
                addr = int(address_text.strip())
            except ValueError:
                return False
        
        device = state_mgr.device_info
        best_periph = None
        best_reg = None
        
        for pname, periph in device.peripherals.items():
            base = self._parse_hex(periph.base_address)
            if base is None:
                continue
            # 解析 address_block
            block = periph.address_block
            block_offset = self._parse_hex(block.get('offset', '0x0')) or 0
            block_size = self._parse_hex(block.get('size', '0x0')) or 0
            
            if block_size > 0:
                if not (base + block_offset <= addr < base + block_offset + block_size):
                    continue
            elif addr < base:
                continue
            
            best_periph = pname
            
            # 查找具体寄存器
            for rname, reg in periph.registers.items():
                offset = self._parse_hex(reg.offset)
                if offset is not None and base + offset == addr:
                    best_reg = rname
                    break
            break
        
        if best_periph:
            # 跳转
            if best_reg:
                state_mgr.set_selection(peripheral=best_periph, register=best_reg, field=None)
            else:
                state_mgr.set_selection(peripheral=best_periph, register=None, field=None)
            return True
        
        return False
    
    def show_advanced_search_dialog(self, parent=None):
        """显示高级搜索对话框（Ctrl+H）- 支持统一搜索语法"""
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QTextEdit
        
        dlg = QDialog(parent or None)
        dlg.setWindowTitle(t("dialog.advanced_search", default="🔍 高级搜索"))
        dlg.setMinimumSize(700, 550)
        dlg.resize(850, 650)
        layout = QVBoxLayout(dlg)
        
        # === 搜索条件 ===
        cond_layout = QHBoxLayout()
        
        search_edit = QLineEdit()
        search_edit.setPlaceholderText(
            t("search.advanced_placeholder",
              default="输入关键词或使用语法: type:periph name:GPIO* access:ro"))
        search_edit.setClearButtonEnabled(True)
        search_edit.setToolTip(
            "支持统一搜索语法:\n"
            "  type:peripheral  按类型\n"
            "  name:GPIO*       按名称（通配符）\n"
            "  desc:clock       按描述\n"
            "  addr:0x4001*     按地址\n"
            "  access:ro        按权限\n"
            "  periph:GPIOA     限定外设\n"
            "  纯文本           全属性搜索")
        cond_layout.addWidget(search_edit)
        
        # 搜索范围（兼容旧模式）
        scope_combo = QComboBox()
        scope_combo.addItem(t("search.scope_all", default="全部属性"), "all")
        scope_combo.addItem(t("search.scope_name", default="仅名称"), "name")
        scope_combo.addItem(t("search.scope_desc", default="仅描述"), "description")
        scope_combo.addItem(t("search.scope_addr", default="仅地址"), "address")
        scope_combo.addItem(t("search.scope_value", default="仅复位值"), "value")
        cond_layout.addWidget(scope_combo)
        
        # 语法帮助按钮
        help_btn = QPushButton("❓")
        help_btn.setFixedWidth(35)
        help_btn.setToolTip("搜索语法帮助")
        cond_layout.addWidget(help_btn)
        
        search_btn = QPushButton(t("search.button", default="搜索"))
        search_btn.setDefault(True)
        cond_layout.addWidget(search_btn)
        
        layout.addLayout(cond_layout)
        
        # === 语法提示栏 ===
        from ...config.styles import get_style_scheme
        _sc = get_style_scheme().colors
        syntax_label = QLabel(
            f'<span style="color:{_sc.gray}; font-size:11px;">'
            '💡 语法: <b>type:</b>periph <b>name:</b>GPIO* <b>addr:</b>0x4001* <b>access:</b>ro <b>periph:</b>GPIOA <b>desc:</b>"clock"  |  纯文本搜索所有属性'
            '</span>')
        syntax_label.setWordWrap(True)
        layout.addWidget(syntax_label)
        
        # 结果统计
        count_label = QLabel("")
        layout.addWidget(count_label)
        
        # 结果列表
        results_list = QListWidget()
        results_list.setAlternatingRowColors(True)
        layout.addWidget(results_list, 1)
        
        # 双击跳转
        _search_results_data = []
        state_mgr = self._get_state_manager()
        
        def _is_structured_query(text: str) -> bool:
            """检测是否使用了结构化搜索语法"""
            return bool(re.search(r'\w+:', text))
        
        def do_search():
            nonlocal _search_results_data
            from ...config.styles import get_style_scheme as _gss
            _sc2 = _gss().colors
            text = search_edit.text().strip()
            if not text:
                return
            
            # 自动检测：如果输入包含 key: 语法，使用结构化搜索
            if _is_structured_query(text):
                _search_results_data = self.structured_search(text)
                count_label.setText(
                    f'<span style="color:{_sc2.accent};">🔤 结构化搜索</span> | '
                    f'找到 <b>{len(_search_results_data)}</b> 个结果')
            else:
                # 使用传统的深度搜索
                scope = scope_combo.currentData() or 'all'
                _search_results_data = self.deep_search(text, scope)
                count_label.setText(
                    f'<span style="color:{_sc2.gray};">🔎 全文搜索</span> | '
                    f'找到 <b>{len(_search_results_data)}</b> 个结果')
            
            results_list.clear()
            
            level_icons = {
                'peripheral': '📦', 'register': '📋', 'field': '🔹', 'interrupt': '⚡'
            }
            level_labels = {
                'peripheral': '外设', 'register': '寄存器', 'field': '位域', 'interrupt': '中断'
            }
            level_colors = {
                'peripheral': _sc2.accent, 'register': _sc2.success, 'field': _sc2.warning, 'interrupt': _sc2.search_interrupt_color
            }
            
            for r in _search_results_data:
                icon = level_icons.get(r['level'], '')
                label = level_labels.get(r['level'], r['level'])
                color = level_colors.get(r['level'], _sc2.text_primary)
                item = QListWidgetItem(
                    f"{icon} [{label}] {r['path']}  ← {r['match_field']}: {r['match_text']}"
                )
                item.setForeground(QBrush(QColor(color)))
                item.setData(Qt.ItemDataRole.UserRole, r)
                results_list.addItem(item)
        
        def show_help():
            """显示搜索语法帮助"""
            help_dlg = QDialog(dlg)
            help_dlg.setWindowTitle("🔍 搜索语法帮助")
            help_dlg.resize(550, 500)
            help_layout = QVBoxLayout(help_dlg)
            
            help_text = QTextEdit()
            help_text.setReadOnly(True)
            help_text.setHtml(f'<pre style="font-size:12px; line-height:1.5;">{self.get_search_syntax_help()}</pre>')
            help_layout.addWidget(help_text)
            
            close_btn = QPushButton("关闭")
            close_btn.clicked.connect(help_dlg.accept)
            help_layout.addWidget(close_btn)
            
            help_dlg.exec()
        
        def on_result_double_clicked(item):
            data = item.data(Qt.ItemDataRole.UserRole)
            if not data or not state_mgr:
                return
            
            periph = data.get('peripheral')
            reg = data.get('register')
            field = data.get('field')
            interrupt = data.get('interrupt')
            
            if interrupt:
                state_mgr.set_selection(peripheral=None, register=None, field=None)
                irq_table = self.get_widget('irq_table')
                if irq_table:
                    for row in range(irq_table.rowCount()):
                        name_item = irq_table.item(row, 0)
                        if name_item and name_item.text() == interrupt:
                            irq_table.selectRow(row)
                            irq_table.scrollToItem(name_item)
                            break
                    tab_widget = self.get_widget('tab_widget')
                    if tab_widget:
                        tab_widget.setCurrentIndex(2)
            else:
                state_mgr.set_selection(peripheral=periph, register=reg, field=field)
                if periph:
                    periph_tree = self.get_widget('periph_tree')
                    if periph_tree:
                        for i in range(periph_tree.topLevelItemCount()):
                            pi = periph_tree.topLevelItem(i)
                            if pi.text(0) == periph:
                                pi.setExpanded(True)
                                if reg:
                                    for j in range(pi.childCount()):
                                        ri = pi.child(j)
                                        if ri.text(0) == reg:
                                            ri.setExpanded(True)
                                            if field:
                                                for k in range(ri.childCount()):
                                                    fi = ri.child(k)
                                                    if fi.text(0) == field:
                                                        periph_tree.setCurrentItem(fi)
                                                        periph_tree.scrollToItem(fi)
                                                        break
                                            else:
                                                periph_tree.setCurrentItem(ri)
                                                periph_tree.scrollToItem(ri)
                                            break
                                else:
                                    periph_tree.setCurrentItem(pi)
                                    periph_tree.scrollToItem(pi)
                                break
                    tab_widget = self.get_widget('tab_widget')
                    if tab_widget:
                        tab_widget.setCurrentIndex(1)
            
            dlg.accept()
        
        search_btn.clicked.connect(do_search)
        search_edit.returnPressed.connect(do_search)
        results_list.itemDoubleClicked.connect(on_result_double_clicked)
        help_btn.clicked.connect(show_help)
        
        # 快捷搜索: 输入时自动搜索（延迟）
        from PyQt6.QtCore import QTimer
        search_timer = QTimer()
        search_timer.setSingleShot(True)
        search_timer.setInterval(400)
        search_timer.timeout.connect(do_search)
        search_edit.textChanged.connect(lambda: search_timer.start())
        
        # 初始焦点
        search_edit.setFocus()
        search_edit.selectAll()
        
        dlg.exec()
    
    def show_goto_address_dialog(self, parent=None):
        """显示跳转到地址对话框（Ctrl+Shift+G）"""
        from PyQt6.QtWidgets import QInputDialog
        
        text, ok = QInputDialog.getText(
            parent or None,
            t("dialog.goto_address", default="📍 跳转到地址"),
            t("label.enter_address", default="输入寄存器绝对地址（如 0x40010000）:"),
        )
        
        if ok and text.strip():
            found = self.goto_address(text.strip())
            if not found:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(
                    parent or None,
                    t("dialog.goto_address"),
                    t("msg.address_not_found", default=f"未找到地址 {text.strip()} 对应的寄存器")
                )
    
    # ==================== 辅助方法 ====================
    
    def _get_state_manager(self):
        """获取 StateManager"""
        if self.coordinator:
            sm = self.coordinator.get_component('state_manager')
            if sm:
                return sm
        # fallback: 从 layout_manager 获取
        if self.coordinator:
            lm = self.coordinator.get_component('layout_manager')
            if lm and hasattr(lm, 'main_window') and hasattr(lm.main_window, 'state_manager'):
                return lm.main_window.state_manager
        return None
    
    @staticmethod
    def _parse_hex(value) -> Optional[int]:
        """解析十六进制或十进制数值"""
        if value is None:
            return None
        try:
            s = str(value).strip()
            if not s:
                return None
            if s.lower().startswith("0x"):
                return int(s, 16)
            return int(s)
        except (ValueError, AttributeError):
            return None

    # ==================== 统一搜索语法 ====================

    def parse_search_query(self, query: str) -> Dict[str, Any]:
        """
        解析统一搜索语法的查询字符串
        
        支持的语法:
          type:peripheral       按元素类型过滤 (peripheral/register/field/interrupt/cluster)
          name:GPIO*            按名称搜索（支持通配符 * 和 ?）
          desc:xxx / desc:"长描述"  按描述搜索
          addr:0x4001*          按地址/偏移搜索（支持通配符）
          access:read-write     按访问权限过滤 (read-write/read-only/write-only)
          reset:0x00            按复位值搜索
          periph:GPIOA          限定在外设范围内
          reg:MODER             限定在寄存器范围内
          bit:5 / bit:7:4       按位范围搜索
          纯文本               搜索所有属性
        
        示例:
          "GPIOA"                           → 搜索所有属性包含GPIOA
          "type:peripheral name:GPIO*"      → 搜索名称以GPIO开头的外设
          "access:read-only"                → 搜索只读的寄存器/位域
          "addr:0x40010000 periph:GPIOA"    → 在GPIOA外设中搜索地址0x40010000
          "type:field bit:5"                → 搜索位5的位域
          "desc:clock periph:RCC"           → 在RCC中搜索描述含clock的
        
        Returns:
            解析后的查询字典:
            {
                'raw': str,           # 原始查询
                'text': str|None,     # 纯文本部分
                'type': list[str],    # 元素类型过滤
                'name': str|None,     # 名称模式
                'desc': str|None,     # 描述模式
                'addr': str|None,     # 地址模式
                'access': str|None,   # 访问权限
                'reset': str|None,    # 复位值
                'periph': str|None,   # 外设名限定
                'reg': str|None,      # 寄存器名限定
                'bit': str|None,      # 位范围
            }
        """
        result = {
            'raw': query,
            'text': None,
            'type': [],
            'name': None,
            'desc': None,
            'addr': None,
            'access': None,
            'reset': None,
            'periph': None,
            'reg': None,
            'bit': None,
        }

        if not query or not query.strip():
            return result

        # 正则匹配 key:value 对（值可以用引号包围）
        # 匹配: key:value 或 key:"value with spaces"
        pattern = r'(\w+):(?:("[^"]*")|(\S+))'
        matches = re.findall(pattern, query)

        matched_positions = []  # 记录已匹配的位置
        for key, quoted_val, bare_val in matches:
            value = quoted_val[1:-1] if quoted_val else bare_val  # 去掉引号
            key_lower = key.lower()
            matched_positions.append((query.find(f"{key}:"), len(f"{key}:{quoted_val or bare_val}")))

            if key_lower in ('type', 't'):
                # type 可以逗号分隔多个
                result['type'] = [v.strip().lower() for v in value.split(',')]
            elif key_lower in ('name', 'n'):
                result['name'] = value
            elif key_lower in ('desc', 'description', 'd'):
                result['desc'] = value
            elif key_lower in ('addr', 'address', 'a'):
                result['addr'] = value
            elif key_lower in ('access', 'acc'):
                result['access'] = value.lower()
            elif key_lower in ('reset', 'reset_value', 'rv'):
                result['reset'] = value
            elif key_lower in ('periph', 'peripheral', 'p'):
                result['periph'] = value
            elif key_lower in ('reg', 'register', 'r'):
                result['reg'] = value
            elif key_lower in ('bit', 'b'):
                result['bit'] = value

        # 提取纯文本部分（不在 key:value 对中的文本）
        remaining = query
        # 按位置从后往前删除已匹配的部分
        for pos, length in sorted(matched_positions, reverse=True):
            if pos >= 0:
                remaining = remaining[:pos] + remaining[pos + length:]
        result['text'] = remaining.strip() or None

        return result

    def _pattern_matches(self, pattern: str, text: str) -> bool:
        """
        检查文本是否匹配模式（支持通配符 * 和 ?，不区分大小写）
        """
        if not pattern:
            return True
        if not text:
            return False
        # 将通配符模式转为正则
        regex = ''
        for ch in pattern:
            if ch == '*':
                regex += '.*'
            elif ch == '?':
                regex += '.'
            else:
                regex += re.escape(ch)
        try:
            return bool(re.match(f'^{regex}$', text, re.IGNORECASE))
        except re.error:
            # 正则失败时回退到简单包含匹配
            return pattern.lower() in text.lower()

    def structured_search(self, query: str) -> List[Dict[str, Any]]:
        """
        使用统一搜索语法执行结构化搜索
        
        Args:
            query: 搜索查询字符串
        
        Returns:
            匹配结果列表（同 deep_search 格式）
        """
        if not query or not query.strip():
            return []

        parsed = self.parse_search_query(query)
        state_mgr = self._get_state_manager()
        if not state_mgr:
            return []

        device = state_mgr.device_info
        if not device:
            return []

        results = []
        type_filter = parsed['type']  # e.g. ['peripheral', 'register']
        name_pattern = parsed['name']
        desc_pattern = parsed['desc']
        addr_pattern = parsed['addr']
        access_filter = parsed['access']
        reset_pattern = parsed['reset']
        periph_filter = parsed['periph']
        reg_filter = parsed['reg']
        bit_pattern = parsed['bit']
        free_text = parsed['text']

        def _match_any_field(text_lower: str, obj_dict: Dict[str, str]) -> bool:
            """检查纯文本是否匹配任意字段"""
            if not text_lower:
                return True
            for val in obj_dict.values():
                if val and text_lower in str(val).lower():
                    return True
            return False

        def _check_type(level: str) -> bool:
            """检查类型过滤"""
            if not type_filter:
                return True
            # 支持别名
            aliases = {
                'periph': 'peripheral', 'p': 'peripheral',
                'reg': 'register', 'r': 'register',
                'f': 'field', 'irq': 'interrupt', 'i': 'interrupt',
                'cl': 'cluster',
            }
            expanded = [aliases.get(t, t) for t in type_filter]
            return level in expanded

        def _check_access(access_val) -> bool:
            """检查访问权限"""
            if not access_filter:
                return True
            if not access_val:
                return False
            access_str = str(access_val)
            # 支持简写
            access_map = {
                'rw': 'read-write', 'ro': 'read-only', 'wo': 'write-only',
                'rw1c': 'write-one-to-clear', 'w1c': 'write-one-to-clear',
            }
            target = access_map.get(access_filter, access_filter)
            return target in access_str.lower()

        def _check_reset(reset_val) -> bool:
            """检查复位值"""
            if not reset_pattern:
                return True
            if not reset_val:
                return False
            return self._pattern_matches(reset_pattern, str(reset_val))

        # ===== 搜索外设 =====
        for pname, periph in device.peripherals.items():
            # 外设名过滤
            if periph_filter and not self._pattern_matches(periph_filter, pname):
                continue

            if _check_type('peripheral'):
                p_all_fields = {
                    'name': pname,
                    'description': periph.description or '',
                    'base_address': periph.base_address or '',
                    'group': periph.group_name or '',
                }
                matched = True
                match_field = None
                match_text = None

                if name_pattern:
                    if self._pattern_matches(name_pattern, pname):
                        match_field, match_text = 'name', pname
                    else:
                        matched = False
                if matched and desc_pattern:
                    if periph.description and self._pattern_matches(desc_pattern, periph.description):
                        match_field, match_text = 'description', periph.description[:80]
                    else:
                        matched = False
                if matched and addr_pattern:
                    if self._pattern_matches(addr_pattern, periph.base_address or ''):
                        match_field, match_text = 'base_address', periph.base_address
                    else:
                        matched = False
                if matched and free_text:
                    if _match_any_field(free_text.lower(), p_all_fields):
                        match_field, match_text = 'text', free_text
                    else:
                        matched = False

                if matched and (name_pattern or desc_pattern or addr_pattern or free_text):
                    results.append({
                        'level': 'peripheral',
                        'path': pname,
                        'peripheral': pname, 'register': None, 'field': None,
                        'match_field': match_field or 'name',
                        'match_text': match_text or pname,
                    })

            # ===== 搜索寄存器 =====
            for rname, reg in periph.registers.items():
                if reg_filter and not self._pattern_matches(reg_filter, rname):
                    continue

                if _check_type('register'):
                    r_matched = True
                    r_match_field = None
                    r_match_text = None

                    if name_pattern:
                        if self._pattern_matches(name_pattern, rname):
                            r_match_field, r_match_text = 'name', rname
                        else:
                            r_matched = False
                    if r_matched and desc_pattern:
                        if reg.description and self._pattern_matches(desc_pattern, reg.description):
                            r_match_field, r_match_text = 'description', reg.description[:80]
                        else:
                            r_matched = False
                    if r_matched and addr_pattern:
                        if self._pattern_matches(addr_pattern, reg.offset or ''):
                            r_match_field, r_match_text = 'offset', reg.offset
                        else:
                            r_matched = False
                    if r_matched and access_filter:
                        if _check_access(reg.access):
                            r_match_field, r_match_text = 'access', reg.access
                        else:
                            r_matched = False
                    if r_matched and reset_pattern:
                        if _check_reset(reg.reset_value):
                            r_match_field, r_match_text = 'reset_value', reg.reset_value
                        else:
                            r_matched = False
                    if r_matched and free_text:
                        r_all = {
                            'name': rname,
                            'description': reg.description or '',
                            'offset': reg.offset or '',
                            'reset_value': reg.reset_value or '',
                            'access': reg.access or '',
                            'size': str(reg.size) if reg.size else '',
                        }
                        if _match_any_field(free_text.lower(), r_all):
                            r_match_field, r_match_text = 'text', free_text
                        else:
                            r_matched = False

                    if r_matched and (name_pattern or desc_pattern or addr_pattern
                                      or access_filter or reset_pattern or free_text):
                        reg_path = f"{pname} > {rname}"
                        suffix = f" (偏移: {reg.offset})" if addr_pattern and r_match_field == 'offset' else ''
                        suffix += f" ({reg.access})" if access_filter and r_match_field == 'access' else ''
                        results.append({
                            'level': 'register',
                            'path': f"{reg_path}{suffix}",
                            'peripheral': pname, 'register': rname, 'field': None,
                            'match_field': r_match_field or 'name',
                            'match_text': r_match_text or rname,
                        })

                # ===== 搜索位域 =====
                for fname, fld in reg.fields.items():
                    if not _check_type('field'):
                        continue

                    f_matched = True
                    f_match_field = None
                    f_match_text = None

                    # 位范围过滤
                    if bit_pattern:
                        bit_str = str(fld.bit_offset) if fld.bit_width == 1 else f"{fld.bit_offset + fld.bit_width - 1}:{fld.bit_offset}"
                        if not self._pattern_matches(bit_pattern, bit_str):
                            # 也检查单个位号
                            try:
                                target_bit = int(bit_pattern)
                                if not (fld.bit_offset <= target_bit < fld.bit_offset + fld.bit_width):
                                    f_matched = False
                            except ValueError:
                                f_matched = False

                    if f_matched and name_pattern:
                        if self._pattern_matches(name_pattern, fname):
                            f_match_field, f_match_text = 'name', fname
                        else:
                            f_matched = False
                    if f_matched and desc_pattern:
                        if fld.description and self._pattern_matches(desc_pattern, fld.description):
                            f_match_field, f_match_text = 'description', fld.description[:80]
                        else:
                            f_matched = False
                    if f_matched and access_filter:
                        if _check_access(fld.access):
                            f_match_field, f_match_text = 'access', fld.access
                        else:
                            f_matched = False
                    if f_matched and reset_pattern:
                        if _check_reset(fld.reset_value):
                            f_match_field, f_match_text = 'reset_value', fld.reset_value
                        else:
                            f_matched = False
                    if f_matched and free_text:
                        f_all = {
                            'name': fname,
                            'description': fld.description or '',
                            'access': fld.access or '',
                            'reset_value': fld.reset_value or '',
                            'bit_offset': str(fld.bit_offset),
                            'bit_width': str(fld.bit_width),
                        }
                        if _match_any_field(free_text.lower(), f_all):
                            f_match_field, f_match_text = 'text', free_text
                        else:
                            f_matched = False

                    if f_matched and (name_pattern or desc_pattern or bit_pattern
                                      or access_filter or reset_pattern or free_text):
                        field_path = f"{pname} > {rname} > {fname}"
                        results.append({
                            'level': 'field',
                            'path': field_path,
                            'peripheral': pname, 'register': rname, 'field': fname,
                            'match_field': f_match_field or 'name',
                            'match_text': f_match_text or fname,
                        })

        # ===== 搜索中断 =====
        if _check_type('interrupt'):
            for iname, irq in device.interrupts.items():
                i_matched = True
                i_match_field = None
                i_match_text = None

                if name_pattern:
                    if self._pattern_matches(name_pattern, iname):
                        i_match_field, i_match_text = 'name', iname
                    else:
                        i_matched = False
                if i_matched and desc_pattern:
                    if irq.description and self._pattern_matches(desc_pattern, irq.description):
                        i_match_field, i_match_text = 'description', irq.description[:80]
                    else:
                        i_matched = False
                if i_matched and free_text:
                    i_all = {
                        'name': iname,
                        'description': irq.description or '',
                        'value': str(irq.value),
                    }
                    if _match_any_field(free_text.lower(), i_all):
                        i_match_field, i_match_text = 'text', free_text
                    else:
                        i_matched = False

                if i_matched and (name_pattern or desc_pattern or free_text):
                    results.append({
                        'level': 'interrupt',
                        'path': f"中断: {iname}",
                        'peripheral': None, 'register': None, 'field': None,
                        'interrupt': iname,
                        'match_field': i_match_field or 'name',
                        'match_text': i_match_text or iname,
                    })

        return results

    @staticmethod
    def get_search_syntax_help() -> str:
        """返回搜索语法帮助文本"""
        return """\
🔍 统一搜索语法帮助
═══════════════════

基本语法: key:value key2:value2 纯文本

类型过滤:
  type:peripheral   仅外设
  type:register     仅寄存器
  type:field        仅位域
  type:interrupt    仅中断
  type:periph,reg   多类型（逗号分隔）

名称搜索（支持 * 和 ? 通配符）:
  name:GPIO*        名称以GPIO开头
  name:MODER        名称包含MODER
  n:GPIOA           简写

描述搜索:
  desc:clock        描述含clock
  desc:"clock control"  含空格用引号
  d:clock           简写

地址/偏移搜索:
  addr:0x4001*      地址以0x4001开头
  a:0x40010000      精确地址

访问权限:
  access:read-write  读写
  access:read-only   只读（简写 ro）
  access:write-only  只写（简写 wo）
  acc:rw             简写

复位值:
  reset:0x00         复位值为0x00
  rv:0xFFFFFFFF      精确值

范围限定:
  periph:GPIOA       限定外设
  reg:MODER          限定寄存器
  bit:5              指定位号
  bit:7:4            指定位范围

纯文本:
  GPIO               搜索所有属性
  0x40010000         搜索地址/复位值

组合示例:
  type:periph name:GPIO* addr:0x400*
  access:ro periph:RCC
  type:field bit:5 desc:enable
  desc:clock type:reg
"""
