# -*- coding: utf-8 -*-
"""
文档标签栏组件
在编辑器顶部显示已打开的文档标签页和比较标签页，支持切换、关闭、拖拽排序
"""
import logging
from typing import Optional, Dict

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QTabBar, QPushButton, QLabel,
    QMenu, QToolButton, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QCursor, QAction, QColor, QFont

from ...core.document_manager import DocumentManager, DocumentState
from ...i18n.i18n import t
from ...config.styles import get_style_scheme


class DocumentTabBar(QWidget):
    """文档标签栏
    
    显示在编辑器顶部，每个标签代表一个打开的SVD文档或比较结果。
    支持：
    - 点击切换文档/比较视图
    - 中键/按钮关闭文档
    - 右键菜单（关闭、关闭其他、关闭所有、导出差异报告）
    - 修改状态指示（●标记）
    - 比较标签（不同颜色区分）
    """
    
    # 信号
    tab_clicked = pyqtSignal(str)        # doc_id
    tab_close_requested = pyqtSignal(str) # doc_id
    close_others_requested = pyqtSignal(str)  # doc_id (保留此文档)
    close_all_requested = pyqtSignal()
    new_tab_requested = pyqtSignal()
    diff_tab_clicked = pyqtSignal(str)   # diff_id
    diff_tab_close_requested = pyqtSignal(str)  # diff_id
    
    # 标签类型角色
    TAB_TYPE_ROLE = Qt.ItemDataRole.UserRole + 100
    
    def __init__(self, document_manager: DocumentManager, parent=None):
        super().__init__(parent)
        self.doc_manager = document_manager
        self.logger = logging.getLogger("DocumentTabBar")
        
        # 比较标签存储: diff_id -> {name, widget_ref}
        self._diff_tabs: Dict[str, dict] = {}
        self._diff_counter = 0
        
        self._setup_ui()
        self._connect_signals()
        
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(36)
        self.hide()  # 初始隐藏（无文档时）
    
    def _setup_ui(self):
        """设置UI"""
        layout = QHBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 标签栏
        self._tab_bar = QTabBar()
        self._tab_bar.setDocumentMode(True)
        self._tab_bar.setTabsClosable(True)
        self._tab_bar.setMovable(True)  # 允许拖拽排序
        self._tab_bar.setExpanding(False)
        self._tab_bar.setUsesScrollButtons(True)
        self._tab_bar.setElideMode(Qt.TextElideMode.ElideMiddle)
        
        # 新建标签按钮
        self._new_btn = QToolButton()
        self._new_btn.setText("+")
        self._new_btn.setToolTip(t("doc.new_tab", default="新建标签页"))
        self._new_btn.setFixedSize(30, 30)
        self._new_btn.clicked.connect(self.new_tab_requested.emit)
        
        layout.addWidget(self._tab_bar, 1)
        layout.addWidget(self._new_btn)
        
        # 样式
        self.setStyleSheet(self._get_style())
    
    def _get_style(self) -> str:
        """获取标签栏样式 - 从全局样式方案获取"""
        scheme = get_style_scheme()
        c = scheme.colors
        f = scheme.fonts
        s = scheme.sizes
        return f"""
            DocumentTabBar {{
                background: {c.doc_tab_bar_background};
                border-bottom: 1px solid {c.doc_tab_bar_border};
            }}
            QTabBar {{
                background: transparent;
                border: none;
                font-size: {f.large_size}pt;
            }}
            QTabBar::tab {{
                background: {c.doc_tab_normal_background};
                border: 1px solid {c.doc_tab_normal_border};
                border-bottom: none;
                border-top-left-radius: {s.radius_sm};
                border-top-right-radius: {s.radius_sm};
                padding: 5px 12px;
                margin-right: 1px;
                min-width: 80px;
                max-width: 220px;
            }}
            QTabBar::tab:selected {{
                background: {c.tab_selected};
                border-bottom: 2px solid {c.accent};
                color: {c.text_primary};
                font-weight: bold;
            }}
            QTabBar::tab:hover:!selected {{
                background: {c.doc_tab_hover_background};
            }}
            QTabBar::close-button {{
                subcontrol-position: right;
                subcontrol-origin: padding;
                padding: 0 4px;
                background: transparent;
                border: none;
                border-radius: 3px;
                max-width: 16px;
                max-height: 16px;
            }}
            QTabBar::close-button:hover {{
                background: {c.doc_tab_hover_background};
            }}
            QToolButton {{
                background: transparent;
                border: none;
                font-size: 16px;
                font-weight: bold;
                color: {c.doc_tab_new_btn_color};
                border-radius: 3px;
            }}
            QToolButton:hover {{
                background: {c.doc_tab_new_btn_hover_background};
                color: {c.doc_tab_new_btn_hover_color};
            }}
        """
    
    def _connect_signals(self):
        """连接信号"""
        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        self._tab_bar.tabCloseRequested.connect(self._on_tab_close_requested)
        self._tab_bar.tabMoved.connect(self._on_tab_moved)
        self._tab_bar.customContextMenuRequested.connect(self._on_context_menu)
        self._tab_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        # 文档管理器信号
        self.doc_manager.document_added.connect(self._on_document_added)
        self.doc_manager.document_removed.connect(self._on_document_removed)
        self.doc_manager.document_switched.connect(self._on_document_switched)
        self.doc_manager.document_modified.connect(self._on_document_modified)
        self.doc_manager.document_saved.connect(self._on_document_saved)
        self.doc_manager.all_documents_closed.connect(self._on_all_closed)
    
    def _doc_id_to_index(self, doc_id: str) -> int:
        """文档ID转标签索引"""
        doc_ids = self.doc_manager.document_ids
        if doc_id in doc_ids:
            return doc_ids.index(doc_id)
        return -1
    
    def _index_to_doc_id(self, index: int) -> Optional[str]:
        """标签索引转文档ID"""
        doc_ids = self.doc_manager.document_ids
        if 0 <= index < len(doc_ids):
            return doc_ids[index]
        return None
    
    def _get_tab_type(self, index: int) -> str:
        """获取标签类型"""
        if index < 0:
            return 'unknown'
        # 检查是否是差异标签
        tab_data = self._tab_bar.tabData(index)
        if tab_data and isinstance(tab_data, dict) and tab_data.get('type') == 'diff':
            return 'diff'
        return 'document'
    
    def _get_diff_id(self, index: int) -> Optional[str]:
        """从标签索引获取差异ID"""
        tab_data = self._tab_bar.tabData(index)
        if tab_data and isinstance(tab_data, dict):
            return tab_data.get('diff_id')
        return None
    
    # ===================== 比较标签管理 =====================
    
    def add_diff_tab(self, name: str) -> str:
        """添加一个比较标签
        
        Args:
            name: 标签显示名称
            
        Returns:
            diff_id: 比较标签的唯一ID
        """
        self._diff_counter += 1
        diff_id = f"diff_{self._diff_counter}"
        
        self._diff_tabs[diff_id] = {
            'name': name,
        }
        
        self._tab_bar.blockSignals(True)
        index = self._tab_bar.addTab(f"📊 {name}")
        self._tab_bar.setTabData(index, {'type': 'diff', 'diff_id': diff_id})
        self._tab_bar.setTabToolTip(index, f"比较结果: {name}")
        
        # 为比较标签设置不同颜色
        scheme = get_style_scheme()
        self._tab_bar.setTabTextColor(index, QColor(scheme.colors.doc_tab_diff_text_color))
        
        self._tab_bar.setCurrentIndex(index)
        self._tab_bar.blockSignals(False)
        
        self.show()
        return diff_id
    
    def remove_diff_tab(self, diff_id: str):
        """移除比较标签"""
        if diff_id not in self._diff_tabs:
            return
        
        # 查找标签索引
        for i in range(self._tab_bar.count()):
            tab_data = self._tab_bar.tabData(i)
            if tab_data and isinstance(tab_data, dict) and tab_data.get('diff_id') == diff_id:
                self._tab_bar.blockSignals(True)
                self._tab_bar.removeTab(i)
                self._tab_bar.blockSignals(False)
                break
        
        del self._diff_tabs[diff_id]
        
        # 如果没有任何标签了，隐藏
        if self.doc_manager.document_count == 0 and len(self._diff_tabs) == 0:
            self.hide()
    
    def get_diff_ids(self):
        """获取所有比较标签ID"""
        return list(self._diff_tabs.keys())
    
    # ===================== 槽函数 =====================
    
    def _on_document_added(self, doc_id: str):
        """文档添加时创建标签"""
        doc = self.doc_manager.get_document(doc_id)
        if not doc:
            return

        self._tab_bar.blockSignals(True)

        index = self._tab_bar.addTab(doc.get_tab_title())
        self._tab_bar.setTabToolTip(index, doc.get_tooltip())
        self._tab_bar.setCurrentIndex(index)

        # 设置可见的关闭按钮
        close_btn = QToolButton()
        close_btn.setText("×")
        close_btn.setFixedSize(16, 16)
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.setToolTip(t("menu.file.close_doc", default="关闭文档"))
        close_btn.setStyleSheet("QToolButton { background: transparent; border: none; font-size: 14px; font-weight: bold; color: gray; } QToolButton:hover { color: red; background: rgba(255,0,0,50); border-radius: 2px; }")
        close_btn.clicked.connect(lambda checked, did=doc_id: self.tab_close_requested.emit(did))
        self._tab_bar.setTabButton(index, QTabBar.ButtonPosition.RightSide, close_btn)

        self._tab_bar.blockSignals(False)

        if self.doc_manager.document_count == 1 and len(self._diff_tabs) == 0:
            self.show()
        self.show()
    
    def _on_document_removed(self, doc_id: str):
        """文档移除时删除标签"""
        index = self._doc_id_to_index(doc_id)
        if index < 0:
            return
        
        self._tab_bar.blockSignals(True)
        self._tab_bar.removeTab(index)
        self._tab_bar.blockSignals(False)
        
        if self.doc_manager.document_count == 0 and len(self._diff_tabs) == 0:
            self.hide()
    
    def _on_document_switched(self, doc_id: str):
        """文档切换时更新选中标签"""
        index = self._doc_id_to_index(doc_id)
        if index >= 0 and self._tab_bar.currentIndex() != index:
            self._tab_bar.blockSignals(True)
            self._tab_bar.setCurrentIndex(index)
            self._tab_bar.blockSignals(False)
    
    def _on_document_modified(self, doc_id: str):
        """文档修改时更新标签标题"""
        self._update_tab_title(doc_id)
    
    def _on_document_saved(self, doc_id: str):
        """文档保存时更新标签标题"""
        self._update_tab_title(doc_id)
    
    def _on_all_closed(self):
        """所有文档关闭"""
        # 只移除文档标签，保留比较标签
        self._tab_bar.blockSignals(True)
        # 从后往前移除文档标签
        for i in range(self._tab_bar.count() - 1, -1, -1):
            if self._get_tab_type(i) == 'document':
                self._tab_bar.removeTab(i)
        self._tab_bar.blockSignals(False)
        
        if len(self._diff_tabs) == 0:
            self.hide()
    
    def _on_tab_changed(self, index: int):
        """标签切换时通知"""
        if index < 0:
            return
            
        tab_type = self._get_tab_type(index)
        if tab_type == 'diff':
            diff_id = self._get_diff_id(index)
            if diff_id:
                self.diff_tab_clicked.emit(diff_id)
        else:
            doc_id = self._index_to_doc_id(index)
            if doc_id:
                self.tab_clicked.emit(doc_id)
    
    def _on_tab_close_requested(self, index: int):
        """标签关闭请求"""
        tab_type = self._get_tab_type(index)
        if tab_type == 'diff':
            diff_id = self._get_diff_id(index)
            if diff_id:
                self.diff_tab_close_requested.emit(diff_id)
        else:
            doc_id = self._index_to_doc_id(index)
            if doc_id:
                self.tab_close_requested.emit(doc_id)
    
    def _on_tab_moved(self, from_index: int, to_index: int):
        """标签拖拽移动"""
        # 只对文档标签重排
        if self._get_tab_type(from_index) == 'document' and self._get_tab_type(to_index) == 'document':
            self.doc_manager.reorder_document(from_index, to_index)
    
    def _on_context_menu(self, pos):
        """右键菜单"""
        index = self._tab_bar.tabAt(pos)
        menu = QMenu(self)
        
        tab_type = self._get_tab_type(index)
        
        if tab_type == 'diff' and index >= 0:
            diff_id = self._get_diff_id(index)
            
            # 关闭比较标签
            close_action = menu.addAction("关闭比较")
            close_action.triggered.connect(
                lambda checked, did=diff_id: self.diff_tab_close_requested.emit(did))
            
            menu.addSeparator()
            
            # 导出差异报告
            export_action = menu.addAction("导出差异报告...")
            if diff_id and diff_id in self._diff_tabs:
                export_action.triggered.connect(
                    lambda checked, did=diff_id: self._export_diff_report(did))
        
        elif index >= 0:
            doc_id = self._index_to_doc_id(index)
            
            # 关闭当前
            close_action = menu.addAction(
                t("doc.close", default="关闭"))
            close_action.triggered.connect(
                lambda checked, did=doc_id: self.tab_close_requested.emit(did))
            
            # 关闭其他
            close_others_action = menu.addAction(
                t("doc.close_others", default="关闭其他"))
            close_others_action.triggered.connect(
                lambda checked, did=doc_id: self.close_others_requested.emit(did))
            
            # 复制文件路径
            doc = self.doc_manager.get_document(doc_id)
            if doc and doc.file_path:
                menu.addSeparator()
                copy_path_action = menu.addAction(
                    t("doc.copy_path", default="复制文件路径"))
                copy_path_action.triggered.connect(
                    lambda checked, p=doc.file_path: self._copy_to_clipboard(p))
        
        menu.addSeparator()
        
        # 关闭所有
        close_all_action = menu.addAction(
            t("doc.close_all", default="关闭所有"))
        close_all_action.triggered.connect(self.close_all_requested.emit)
        
        # 关闭所有比较标签
        if self._diff_tabs:
            close_diffs_action = menu.addAction("关闭所有比较")
            close_diffs_action.triggered.connect(self._close_all_diffs)
        
        menu.exec(QCursor.pos())
    
    def _export_diff_report(self, diff_id: str):
        """导出差异报告（由主窗口处理）"""
        # 发送关闭信号，主窗口可拦截做导出
        self.diff_tab_close_requested.emit(diff_id)
    
    def _close_all_diffs(self):
        """关闭所有比较标签"""
        for diff_id in list(self._diff_tabs.keys()):
            self.diff_tab_close_requested.emit(diff_id)
    
    def _update_tab_title(self, doc_id: str):
        """更新指定文档的标签标题"""
        index = self._doc_id_to_index(doc_id)
        doc = self.doc_manager.get_document(doc_id)
        if index >= 0 and doc:
            self._tab_bar.setTabText(index, doc.get_tab_title())
            self._tab_bar.setTabToolTip(index, doc.get_tooltip())
    
    def update_tab_title(self, doc_id: str):
        """公开接口：更新标签标题"""
        self._update_tab_title(doc_id)
    
    def _copy_to_clipboard(self, text: str):
        """复制到剪贴板"""
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
    
    def refresh_all(self):
        """刷新所有标签（用于语言切换等场景）"""
        self._tab_bar.blockSignals(True)
        
        # 重建所有标签
        while self._tab_bar.count() > 0:
            self._tab_bar.removeTab(0)
        
        # 重新添加文档标签
        for doc_id in self.doc_manager.document_ids:
            doc = self.doc_manager.get_document(doc_id)
            if doc:
                index = self._tab_bar.addTab(doc.get_tab_title())
                self._tab_bar.setTabToolTip(index, doc.get_tooltip())
        
        # 重新添加比较标签
        for diff_id, info in self._diff_tabs.items():
            index = self._tab_bar.addTab(f"📊 {info['name']}")
            self._tab_bar.setTabData(index, {'type': 'diff', 'diff_id': diff_id})
            self._tab_bar.setTabToolTip(index, f"比较结果: {info['name']}")
            scheme = get_style_scheme()
            self._tab_bar.setTabTextColor(index, QColor(scheme.colors.doc_tab_diff_text_color))
        
        # 恢复当前选中
        active_id = self.doc_manager.active_doc_id
        if active_id:
            idx = self._doc_id_to_index(active_id)
            if idx >= 0:
                self._tab_bar.setCurrentIndex(idx)
        
        self._tab_bar.blockSignals(False)
        
        # 更新可见性
        if self.doc_manager.document_count > 0 or len(self._diff_tabs) > 0:
            self.show()
        else:
            self.hide()