"""
分块SVD预览组件 - 支持按需加载和显示
提供高效的XML预览和快速导航功能
"""
import re
import logging
from typing import Dict, Any, Optional, Tuple, List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QPlainTextEdit, QFrame, QLabel, QMessageBox, QTextEdit, QScrollBar,
    QComboBox, QSpinBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRegularExpression, QMargins, QPoint, QRect
from PyQt6.QtGui import (
    QTextCursor, QTextCharFormat, QColor, QSyntaxHighlighter,
    QTextDocument, QFont, QMouseEvent, QPainter,
    QTextBlock, QPaintEvent, QPen, QBrush, QTextBlockUserData, QPalette
)

from ...core.chunked_svd_generator import ChunkedSVDGenerator
from ...core.block_manager import BlockManager, BlockType, BlockInfo
from ...utils.helpers import pretty_xml
from ...i18n.i18n import t


class XMLHighlighter(QSyntaxHighlighter):
    """XML语法高亮器"""
    
    def __init__(self, document: QTextDocument):
        super().__init__(document)
        
        # 定义高亮规则
        self.highlighting_rules = []
        
        # XML标签
        tag_format = QTextCharFormat()
        tag_format.setForeground(QColor("#0000FF"))
        tag_format.setFontWeight(QFont.Weight.Bold)
        self.highlighting_rules.append((re.compile(r'<[^>]+>'), tag_format))
        
        # 属性名
        attr_format = QTextCharFormat()
        attr_format.setForeground(QColor("#FF00FF"))
        self.highlighting_rules.append((re.compile(r'\s\w+='), attr_format))
        
        # 属性值
        value_format = QTextCharFormat()
        value_format.setForeground(QColor("#FF0000"))
        self.highlighting_rules.append((re.compile(r'"[^"]*"'), value_format))
        
        # 注释
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#008000"))
        comment_format.setFontItalic(True)
        self.highlighting_rules.append((re.compile(r'<!--.*?-->', re.DOTALL), comment_format))
    
    def highlightBlock(self, text: str):
        """高亮文本块"""
        for pattern, format in self.highlighting_rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), format)


class ChunkedPreviewWidget(QWidget):
    """分块SVD预览组件 - 支持按需加载和显示"""
    
    # 信号定义
    element_selected = pyqtSignal(str, str, str)  # (element_type, peripheral_name, element_name)
    block_navigated = pyqtSignal(str)  # (block_key)
    
    def __init__(self, state_manager, coordinator=None):
        """
        初始化分块预览组件
        
        Args:
            state_manager: 状态管理器
            coordinator: 协调器（可选）
        """
        super().__init__()
        self.state_manager = state_manager
        self.coordinator = coordinator
        self.logger = logging.getLogger("ChunkedPreviewWidget")
        
        # 块管理器和生成器
        self.block_manager: Optional[BlockManager] = None
        self.generator: Optional[ChunkedSVDGenerator] = None
        
        # 当前选中的元素信息
        self.current_selection = {
            'type': None,  # 'peripheral', 'register', 'field', 'interrupt'
            'peripheral': None,
            'register': None,
            'field': None,
            'interrupt': None
        }
        
        # XML行号映射（用于快速定位）
        self.line_map = {}  # {line_number: (element_type, peripheral_name, element_name)}
        
        # 元素范围映射（用于框选）
        self.element_ranges = {}  # {(element_type, peripheral_name, element_name): (start_line, end_line)}
        
        # 折叠状态
        self.folded_elements = set()  # {(element_type, peripheral_name, element_name)}
        
        # 防抖定时器（避免频繁更新）
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self._update_preview)
        self.update_delay = 500  # 500ms延迟
        
        # 加载模式
        self.load_mode = "visible"  # "visible" (只加载可见), "all" (加载全部), "selected" (只加载选中)
        
        # 初始化UI
        self.init_ui()
        
        # 注册状态变化回调
        if self.state_manager:
            self.state_manager.register_state_change_callback(self.on_state_changed)
            self.state_manager.register_selection_change_callback(self.on_selection_changed)
        
        # 注册协调器事件
        if self.coordinator:
            self.coordinator.device_info_updated.connect(self.on_device_info_updated)
            self.coordinator.selection_changed.connect(self.on_coordinator_selection_changed)
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 工具栏
        toolbar = QHBoxLayout()
        
        # 加载模式选择
        self.load_mode_label = QLabel(t("label.load_mode") + ":")
        toolbar.addWidget(self.load_mode_label)
        
        self.load_mode_combo = QComboBox()
        self.load_mode_combo.addItem(t("load_mode.visible"), "visible")
        self.load_mode_combo.addItem(t("load_mode.selected"), "selected")
        self.load_mode_combo.addItem(t("load_mode.all"), "all")
        self.load_mode_combo.currentIndexChanged.connect(self.on_load_mode_changed)
        toolbar.addWidget(self.load_mode_combo)
        
        toolbar.addStretch()
        
        toolbar.addStretch()
        
        # 刷新按钮
        refresh_btn = QPushButton(t("button.refresh"))
        refresh_btn.clicked.connect(self.refresh_preview)
        toolbar.addWidget(refresh_btn)
        
        # 跳转到选中按钮
        jump_btn = QPushButton(t("button.jump_to_selection"))
        jump_btn.clicked.connect(self.jump_to_selection)
        toolbar.addWidget(jump_btn)
        
        # 导航按钮
        prev_btn = QPushButton(t("button.previous"))
        prev_btn.clicked.connect(self.navigate_previous)
        toolbar.addWidget(prev_btn)
        
        next_btn = QPushButton(t("button.next"))
        next_btn.clicked.connect(self.navigate_next)
        toolbar.addWidget(next_btn)
        
        layout.addLayout(toolbar)
        
        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)
        
        # 预览文本编辑器
        self.preview_edit = QTextEdit()
        self.preview_edit.setReadOnly(False)
        
        # 设置字体
        font = QFont("Consolas, 'Courier New', monospace")
        font.setPointSize(10)
        self.preview_edit.setFont(font)
        self.preview_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        
        # 设置样式
        self.preview_edit.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                color: #000000;
                selection-background-color: #d1e9ff;
                selection-color: #000000;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 4px;
            }
            QTextEdit:focus {
                border: 1px solid #90c8ff;
            }
        """)
        
        # 连接选择变化信号
        self.preview_edit.selectionChanged.connect(self.on_preview_selection_changed)
        # 连接文本变化信号
        self.preview_edit.textChanged.connect(self.on_text_changed)
        
        layout.addWidget(self.preview_edit)
        
        # 添加语法高亮
        doc = self.preview_edit.document()
        if doc:
            self.highlighter = XMLHighlighter(doc)
        
        # 状态栏
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666; font-size: 9pt;")
        layout.addWidget(self.status_label)
    
    def set_block_manager(self, block_manager: BlockManager):
        """
        设置块管理器
        
        Args:
            block_manager: 块管理器
        """
        self.block_manager = block_manager
        self.generator = ChunkedSVDGenerator(self.state_manager.device_info, block_manager)
        self.logger.info("块管理器已设置")
    
    def on_load_mode_changed(self, index: int):
        """加载模式改变"""
        self.load_mode = self.load_mode_combo.itemData(index)
        self.logger.debug(f"加载模式改变: {self.load_mode}")
        self.refresh_preview()
    
    def refresh_preview(self, immediate: bool = False):
        """刷新预览"""
        self.logger.debug(f"refresh_preview called, immediate={immediate}")
        if immediate:
            self.logger.debug("立即刷新预览")
            self._update_preview()
        else:
            self.logger.debug("使用防抖刷新预览")
            self.update_timer.start(self.update_delay)
    
    def _update_preview(self):
        """更新预览内容（内部方法）"""
        try:
            # 获取设备信息
            device_info = self.state_manager.device_info
            if not device_info:
                self.logger.debug("设备信息为空，无法更新预览")
                return
            
            # 确保块管理器已设置
            if not self.block_manager:
                self.logger.warning("块管理器未设置，无法更新预览")
                return
            
            self.logger.debug("开始更新预览内容...")
            
            # 根据加载模式生成XML
            if self.load_mode == "all":
                # 加载全部
                svd_xml = self.generator.generate_visible_blocks()
            elif self.load_mode == "selected":
                # 只加载选中的块
                block_keys = self._get_selected_block_keys()
                svd_xml = self.generator.generate_blocks_by_keys(block_keys)
            else:  # visible
                # 加载可见的块
                svd_xml = self.generator.generate_visible_blocks()
            
            # 美化XML
            pretty_svd = pretty_xml(svd_xml)
            
            # 保存当前选择位置
            current_cursor = self.preview_edit.textCursor()
            current_position = current_cursor.position()
            
            # 更新文本
            self.preview_edit.setPlainText(pretty_svd)
            
            # 重建行号映射
            self._build_line_map(pretty_svd)
            
            # 恢复选择位置
            if current_position > 0 and current_position < len(pretty_svd):
                new_cursor = QTextCursor(self.preview_edit.document())
                new_cursor.setPosition(current_position)
                self.preview_edit.setTextCursor(new_cursor)
            
            # 更新状态
            doc = self.preview_edit.document()
            if doc:
                line_count = doc.blockCount()
                stats = self.block_manager.get_statistics()
                self.status_label.setText(
                    f"{t('status.lines')}: {line_count} | "
                    f"{t('status.loaded_blocks')}: {stats['loaded_blocks']}/{stats['total_blocks']}"
                )
                self.logger.debug(f"预览更新完成，共 {line_count} 行")
            
        except Exception as e:
            self.logger.error(f"更新预览失败: {e}")
            self.status_label.setText(f"{t('status.error')}: {str(e)}")
    
    def _get_selected_block_keys(self) -> List[str]:
        """获取当前选中的块key列表"""
        block_keys = []
        
        # 根据当前选择确定要加载的块
        if self.current_selection.get('type') == 'peripheral':
            periph_name = self.current_selection.get('peripheral')
            if periph_name:
                block_keys.append(f"peripheral:{periph_name}")
        elif self.current_selection.get('type') == 'register':
            periph_name = self.current_selection.get('peripheral')
            reg_name = self.current_selection.get('register')
            if periph_name and reg_name:
                block_keys.append(f"peripheral:{periph_name}")
                block_keys.append(f"register:{periph_name}:{reg_name}")
        elif self.current_selection.get('type') == 'field':
            periph_name = self.current_selection.get('peripheral')
            reg_name = self.current_selection.get('register')
            field_name = self.current_selection.get('field')
            if periph_name and reg_name and field_name:
                block_keys.append(f"peripheral:{periph_name}")
                block_keys.append(f"register:{periph_name}:{reg_name}")
                block_keys.append(f"field:{periph_name}:{reg_name}:{field_name}")
        
        return block_keys
    
    def _build_line_map(self, xml_text: str):
        """构建行号映射和元素范围映射"""
        self.line_map.clear()
        self.element_ranges.clear()
        lines = xml_text.split('\n')
        
        # 用于跟踪元素范围
        element_stack = []  # [(element_type, peripheral_name, element_name, start_line)]
        
        current_peripheral = None
        current_register = None
        current_field = None
        current_interrupt = None
        
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # 检测外设开始
            peripheral_match = re.search(r'<peripheral\s+name="([^"]+)"', stripped)
            if peripheral_match:
                current_peripheral = peripheral_match.group(1)
                self.line_map[line_num] = ('peripheral', current_peripheral, current_peripheral)
                element_stack.append(('peripheral', current_peripheral, current_peripheral, line_num))
                continue
            
            # 检测外设结束
            if stripped == '</peripheral>':
                if element_stack and element_stack[-1][0] == 'peripheral':
                    elem_type, periph_name, elem_name, start_line = element_stack.pop()
                    self.element_ranges[(elem_type, periph_name, elem_name)] = (start_line, line_num)
                    current_peripheral = None
                continue
            
            # 检测寄存器开始
            register_match = re.search(r'<register\s+name="([^"]+)"', stripped)
            if register_match and current_peripheral:
                current_register = register_match.group(1)
                self.line_map[line_num] = ('register', current_peripheral, current_register)
                element_stack.append(('register', current_peripheral, current_register, line_num))
                continue
            
            # 检测寄存器结束
            if stripped == '</register>':
                if element_stack and element_stack[-1][0] == 'register':
                    elem_type, periph_name, elem_name, start_line = element_stack.pop()
                    self.element_ranges[(elem_type, periph_name, elem_name)] = (start_line, line_num)
                    current_register = None
                continue
            
            # 检测位域开始
            field_match = re.search(r'<field\s+name="([^"]+)"', stripped)
            if field_match and current_peripheral and current_register:
                current_field = field_match.group(1)
                self.line_map[line_num] = ('field', current_peripheral, current_field)
                element_stack.append(('field', current_peripheral, current_field, line_num))
                continue
            
            # 检测位域结束
            if stripped == '</field>':
                if element_stack and element_stack[-1][0] == 'field':
                    elem_type, periph_name, elem_name, start_line = element_stack.pop()
                    self.element_ranges[(elem_type, periph_name, elem_name)] = (start_line, line_num)
                    current_field = None
                continue
            
            # 检测中断开始
            interrupt_match = re.search(r'<interrupt\s+name="([^"]+)"', stripped)
            if interrupt_match and current_peripheral:
                current_interrupt = interrupt_match.group(1)
                self.line_map[line_num] = ('interrupt', current_peripheral, current_interrupt)
                element_stack.append(('interrupt', current_peripheral, current_interrupt, line_num))
                continue
            
            # 检测中断结束
            if stripped == '</interrupt>':
                if element_stack and element_stack[-1][0] == 'interrupt':
                    elem_type, periph_name, elem_name, start_line = element_stack.pop()
                    self.element_ranges[(elem_type, periph_name, elem_name)] = (start_line, line_num)
                    current_interrupt = None
                continue
    
    def on_preview_selection_changed(self):
        """预览选择变化处理"""
        cursor = self.preview_edit.textCursor()
        line_num = cursor.blockNumber() + 1
        
        if line_num in self.line_map:
            element_type, peripheral_name, element_name = self.line_map[line_num]
            self.element_selected.emit(element_type, peripheral_name, element_name)
    
    def on_text_changed(self):
        """文本变化处理"""
        # 可以在这里实现XML编辑功能
        pass
    
    def on_state_changed(self, state: Dict[str, Any]):
        """状态变化回调"""
        self.logger.debug("状态变化，刷新预览")
        self.refresh_preview()
    
    def on_selection_changed(self, selection: Dict[str, Any]):
        """选择变化回调"""
        self.current_selection = selection
        self.logger.debug(f"选择变化: {selection}")
        
        # 如果是selected模式，刷新预览
        if self.load_mode == "selected":
            self.refresh_preview()
    
    def on_device_info_updated(self, device_info):
        """设备信息更新回调"""
        self.logger.debug("设备信息更新，刷新预览")
        self.refresh_preview()
    
    def on_coordinator_selection_changed(self, selection: Dict[str, Any]):
        """协调器选择变化回调"""
        self.on_selection_changed(selection)
    
    def jump_to_selection(self):
        """跳转到选中的元素"""
        if not self.current_selection.get('type'):
            self.logger.debug("没有选中的元素")
            return
        
        element_type = self.current_selection.get('type')
        peripheral_name = self.current_selection.get('peripheral')
        element_name = self.current_selection.get('register') or self.current_selection.get('field') or peripheral_name
        
        # 查找对应的行号
        for line_num, (elem_type, periph_name, elem_name) in self.line_map.items():
            if elem_type == element_type and periph_name == peripheral_name and elem_name == element_name:
                # 跳转到该行
                cursor = QTextCursor(self.preview_edit.document())
                cursor.movePosition(QTextCursor.MoveOperation.Start)
                cursor.movePosition(QTextCursor.MoveOperation.NextBlock, QTextCursor.MoveMode.MoveAnchor, line_num - 1)
                self.preview_edit.setTextCursor(cursor)
                self.preview_edit.setFocus()
                self.logger.debug(f"跳转到行 {line_num}")
                return
        
        self.logger.warning(f"未找到元素: {element_type} - {element_name}")
    
    def navigate_previous(self):
        """导航到上一个块"""
        if not self.block_manager:
            return
        
        current_key = self._get_current_block_key()
        if not current_key:
            return
        
        prev_block = self.block_manager.get_previous_block(current_key)
        if prev_block:
            self.block_manager.navigate_to(prev_block.key)
            self.block_navigated.emit(prev_block.key)
            self.refresh_preview(immediate=True)
    
    def navigate_next(self):
        """导航到下一个块"""
        if not self.block_manager:
            return
        
        current_key = self._get_current_block_key()
        if not current_key:
            return
        
        next_block = self.block_manager.get_next_block(current_key)
        if next_block:
            self.block_manager.navigate_to(next_block.key)
            self.block_navigated.emit(next_block.key)
            self.refresh_preview(immediate=True)
    
    def _get_current_block_key(self) -> Optional[str]:
        """获取当前块的key"""
        if not self.current_selection.get('type'):
            return None
        
        element_type = self.current_selection.get('type')
        peripheral_name = self.current_selection.get('peripheral')
        register_name = self.current_selection.get('register')
        field_name = self.current_selection.get('field')
        
        if element_type == 'peripheral':
            return f"peripheral:{peripheral_name}"
        elif element_type == 'register':
            return f"register:{peripheral_name}:{register_name}"
        elif element_type == 'field':
            return f"field:{peripheral_name}:{register_name}:{field_name}"
        
        return None
    
    def navigate_to_block(self, block_key: str):
        """
        导航到指定块
        
        Args:
            block_key: 块的key
        """
        if not self.block_manager:
            return
        
        block = self.block_manager.navigate_to(block_key)
        if block:
            self.block_navigated.emit(block_key)
            self.refresh_preview(immediate=True)
            
            # 更新当前选择
            if block.block_type == BlockType.PERIPHERAL:
                self.current_selection = {
                    'type': 'peripheral',
                    'peripheral': block.peripheral_name,
                    'register': None,
                    'field': None,
                    'interrupt': None
                }
            elif block.block_type == BlockType.REGISTER:
                self.current_selection = {
                    'type': 'register',
                    'peripheral': block.peripheral_name,
                    'register': block.register_name,
                    'field': None,
                    'interrupt': None
                }
            elif block.block_type == BlockType.FIELD:
                self.current_selection = {
                    'type': 'field',
                    'peripheral': block.peripheral_name,
                    'register': block.register_name,
                    'field': block.field_name,
                    'interrupt': None
                }
