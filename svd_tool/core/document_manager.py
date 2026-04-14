"""
多文档管理器
支持同时打开多个SVD文件，每个文档独立管理状态和命令历史
"""
import os
import copy
import logging
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
from PyQt6.QtCore import QObject, pyqtSignal

from .data_model import DeviceInfo
from .command_history import CommandHistory


@dataclass
class DocumentState:
    """单个文档的完整状态"""
    doc_id: str  # 唯一标识
    device_info: DeviceInfo  # 设备数据
    file_path: Optional[str] = None  # 文件路径（None表示新建未保存）
    modified: bool = False  # 是否有未保存的修改
    display_name: str = ""  # 显示名称
    
    # 选择状态
    selection: Dict[str, Optional[str]] = field(default_factory=lambda: {
        'peripheral': None, 'register': None, 'field': None, 'element_type': None
    })
    
    # 树展开状态（外设名 -> 是否展开）
    tree_expanded_periphs: Dict[str, bool] = field(default_factory=dict)
    # 寄存器展开状态（"外设/寄存器" -> 是否展开）
    tree_expanded_regs: Dict[str, bool] = field(default_factory=dict)
    
    # 当前标签页索引
    current_tab_index: int = 0
    
    # 命令历史（每个文档独立）
    command_history: Optional[CommandHistory] = None
    
    # 中断表滚动位置
    irq_table_scroll: int = 0
    
    # 预览器折叠状态（存储 frozenset 以便序列化）
    preview_folded_elements: set = field(default_factory=set)
    # 预览器选中状态
    preview_selection: Dict[str, Optional[str]] = field(default_factory=lambda: {
        'type': None, 'peripheral': None, 'register': None, 'field': None, 'interrupt': None
    })
    
    def __post_init__(self):
        if self.command_history is None:
            self.command_history = CommandHistory()
        if not self.display_name:
            if self.file_path:
                self.display_name = os.path.basename(self.file_path)
            elif self.device_info:
                self.display_name = self.device_info.name or "未命名"
            else:
                self.display_name = "未命名"
    
    def get_tab_title(self) -> str:
        """获取标签页标题（修改过的加*前缀）"""
        prefix = "● " if self.modified else ""
        return f"{prefix}{self.display_name}"
    
    def get_tooltip(self) -> str:
        """获取标签页悬停提示"""
        if self.file_path:
            return self.file_path
        return f"新建文件 - {self.display_name}"


class DocumentManager(QObject):
    """多文档管理器
    
    管理多个打开的SVD文档，每个文档独立维护：
    - 设备数据 (DeviceInfo)
    - 命令历史 (CommandHistory)  
    - 选择状态
    - UI状态（展开/折叠、滚动位置等）
    
    使用方式：
    1. 通过 open_document() / new_document() 添加文档
    2. 通过 switch_to() 切换文档（自动保存/恢复状态）
    3. 通过 close_document() 关闭文档
    """
    
    # 信号
    document_added = pyqtSignal(str)        # doc_id
    document_removed = pyqtSignal(str)      # doc_id
    document_switched = pyqtSignal(str)     # doc_id (新激活的文档)
    document_modified = pyqtSignal(str)     # doc_id
    document_saved = pyqtSignal(str)        # doc_id
    all_documents_closed = pyqtSignal()     # 所有文档关闭
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger("DocumentManager")
        self._documents: Dict[str, DocumentState] = {}
        self._active_doc_id: Optional[str] = None
        self._doc_counter = 0  # 用于生成唯一ID
        self._max_documents = 20  # 最大文档数
    
    def _generate_doc_id(self) -> str:
        """生成唯一文档ID"""
        self._doc_counter += 1
        return f"doc_{self._doc_counter}"
    
    @property
    def active_document(self) -> Optional[DocumentState]:
        """获取当前活动文档"""
        if self._active_doc_id:
            return self._documents.get(self._active_doc_id)
        return None
    
    @property
    def active_doc_id(self) -> Optional[str]:
        """获取当前活动文档ID"""
        return self._active_doc_id
    
    @property
    def document_count(self) -> int:
        """文档数量"""
        return len(self._documents)
    
    @property
    def document_ids(self) -> List[str]:
        """所有文档ID列表（按打开顺序）"""
        return list(self._documents.keys())
    
    def get_document(self, doc_id: str) -> Optional[DocumentState]:
        """获取指定文档"""
        return self._documents.get(doc_id)
    
    def get_all_documents(self) -> Dict[str, DocumentState]:
        """获取所有文档"""
        return self._documents.copy()
    
    def open_document(self, device_info: DeviceInfo, 
                      file_path: Optional[str] = None,
                      display_name: Optional[str] = None) -> str:
        """打开一个文档
        
        Args:
            device_info: 设备信息
            file_path: 文件路径（None表示新建）
            display_name: 显示名称
            
        Returns:
            文档ID
        """
        # 检查是否已经打开
        if file_path:
            for doc_id, doc in self._documents.items():
                if doc.file_path and os.path.normpath(doc.file_path) == os.path.normpath(file_path):
                    # 已经打开，直接切换
                    self.switch_to(doc_id)
                    return doc_id
        
        # 检查文档数量限制
        if len(self._documents) >= self._max_documents:
            raise ValueError(f"已达到最大文档数量限制 ({self._max_documents})")
        
        doc_id = self._generate_doc_id()
        doc = DocumentState(
            doc_id=doc_id,
            device_info=copy.deepcopy(device_info),  # 深拷贝确保文档间数据隔离
            file_path=file_path,
            display_name=display_name or ""
        )
        
        self._documents[doc_id] = doc
        self.document_added.emit(doc_id)
        
        self.logger.info(f"打开文档: {doc.display_name} (id={doc_id})")
        return doc_id
    
    def new_document(self, device_info: DeviceInfo, 
                     display_name: Optional[str] = None) -> str:
        """新建文档
        
        Args:
            device_info: 设备信息
            display_name: 显示名称
            
        Returns:
            文档ID
        """
        return self.open_document(device_info, file_path=None, display_name=display_name)
    
    def close_document(self, doc_id: str) -> bool:
        """关闭文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            是否成功关闭
        """
        if doc_id not in self._documents:
            return False
        
        doc = self._documents[doc_id]
        self.logger.info(f"关闭文档: {doc.display_name} (id={doc_id})")
        
        # 如果关闭的是活动文档，切换到相邻文档
        was_active = (doc_id == self._active_doc_id)
        next_doc_id = None
        
        if was_active:
            next_doc_id = self._get_adjacent_doc_id(doc_id)
        
        # 先发送移除信号（让TabBar在文档还存在时能找到对应的标签索引）
        self.document_removed.emit(doc_id)
        
        # 然后移除文档
        del self._documents[doc_id]
        
        if was_active:
            if next_doc_id and next_doc_id in self._documents:
                self.switch_to(next_doc_id)
            else:
                self._active_doc_id = None
                if len(self._documents) == 0:
                    self.all_documents_closed.emit()
        
        return True
    
    def switch_to(self, doc_id: str) -> bool:
        """切换到指定文档
        
        Args:
            doc_id: 目标文档ID
            
        Returns:
            是否成功切换
        """
        if doc_id not in self._documents:
            self.logger.warning(f"文档不存在: {doc_id}")
            return False
        
        if doc_id == self._active_doc_id:
            return True  # 已经是活动文档
        
        old_doc_id = self._active_doc_id
        self._active_doc_id = doc_id
        
        self.logger.debug(f"切换文档: {old_doc_id} -> {doc_id}")
        self.document_switched.emit(doc_id)
        return True
    
    def _get_adjacent_doc_id(self, doc_id: str) -> Optional[str]:
        """获取相邻文档ID"""
        doc_ids = list(self._documents.keys())
        if doc_id not in doc_ids:
            return None
        
        idx = doc_ids.index(doc_id)
        # 优先选择右边的，否则选左边的
        if idx + 1 < len(doc_ids):
            return doc_ids[idx + 1]
        elif idx - 1 >= 0:
            return doc_ids[idx - 1]
        return None
    
    def save_document(self, doc_id: str, file_path: Optional[str] = None):
        """标记文档已保存
        
        Args:
            doc_id: 文档ID
            file_path: 新的文件路径（另存为时使用）
        """
        doc = self._documents.get(doc_id)
        if not doc:
            return
        
        if file_path:
            doc.file_path = file_path
            doc.display_name = os.path.basename(file_path)
        
        doc.modified = False
        self.document_saved.emit(doc_id)
    
    def mark_modified(self, doc_id: Optional[str] = None):
        """标记文档已修改
        
        Args:
            doc_id: 文档ID（None表示当前活动文档）
        """
        if doc_id is None:
            doc_id = self._active_doc_id
        
        doc = self._documents.get(doc_id) if doc_id else None
        if doc and not doc.modified:
            doc.modified = True
            self.document_modified.emit(doc_id)
    
    def is_modified(self, doc_id: Optional[str] = None) -> bool:
        """检查文档是否已修改"""
        if doc_id is None:
            doc_id = self._active_doc_id
        doc = self._documents.get(doc_id) if doc_id else None
        return doc.modified if doc else False
    
    def get_modified_documents(self) -> List[str]:
        """获取所有已修改的文档ID"""
        return [doc_id for doc_id, doc in self._documents.items() if doc.modified]
    
    def save_selection_state(self, doc_id: Optional[str] = None, 
                            selection: Optional[Dict] = None):
        """保存文档的选择状态"""
        if doc_id is None:
            doc_id = self._active_doc_id
        doc = self._documents.get(doc_id) if doc_id else None
        if doc and selection:
            doc.selection = selection.copy()
    
    def save_tree_state(self, doc_id: Optional[str] = None,
                       expanded_periphs: Optional[Dict] = None,
                       expanded_regs: Optional[Dict] = None):
        """保存文档的树展开状态"""
        if doc_id is None:
            doc_id = self._active_doc_id
        doc = self._documents.get(doc_id) if doc_id else None
        if doc:
            if expanded_periphs is not None:
                doc.tree_expanded_periphs = expanded_periphs.copy()
            if expanded_regs is not None:
                doc.tree_expanded_regs = expanded_regs.copy()
    
    def save_tab_index(self, tab_index: int, doc_id: Optional[str] = None):
        """保存当前标签页索引"""
        if doc_id is None:
            doc_id = self._active_doc_id
        doc = self._documents.get(doc_id) if doc_id else None
        if doc:
            doc.current_tab_index = tab_index
    
    def find_by_file_path(self, file_path: str) -> Optional[str]:
        """通过文件路径查找文档ID"""
        norm_path = os.path.normpath(file_path)
        for doc_id, doc in self._documents.items():
            if doc.file_path and os.path.normpath(doc.file_path) == norm_path:
                return doc_id
        return None
    
    def reorder_document(self, from_index: int, to_index: int):
        """重新排列文档顺序（拖拽排序用）"""
        doc_ids = list(self._documents.keys())
        if 0 <= from_index < len(doc_ids) and 0 <= to_index < len(doc_ids):
            moved_id = doc_ids[from_index]
            # 重建有序字典
            doc_ids.pop(from_index)
            doc_ids.insert(to_index, moved_id)
            new_docs = {did: self._documents[did] for did in doc_ids}
            self._documents = new_docs
    
    def clear_all(self):
        """关闭所有文档"""
        doc_ids = list(self._documents.keys())
        # 先发送所有移除信号（让TabBar在文档还存在时能找到对应的标签索引）
        for doc_id in doc_ids:
            self.document_removed.emit(doc_id)
        # 然后删除所有文档
        for doc_id in doc_ids:
            if doc_id in self._documents:
                del self._documents[doc_id]
        self._active_doc_id = None
        self.all_documents_closed.emit()
