"""
工具栏组件
从 main_window.py 中提取的独立组件
"""
from PyQt6.QtWidgets import QToolBar, QToolButton
from PyQt6.QtCore import Qt
from ...i18n.i18n import t


class ToolBarBuilder:
    """工具栏构建器"""
    
    def __init__(self, parent, main_window):
        """
        初始化工具栏构建器
        
        Args:
            parent: 父窗口
            main_window: 主窗口实例，用于连接信号
        """
        self.parent = parent
        self.main_window = main_window
        self.toolbar = None
        
    def create(self) -> QToolBar:
        """创建工具栏并返回"""
        toolbar = self.parent.addToolBar(t("toolbar.main"))
        if toolbar is None:
            return None
        
        toolbar.setMovable(False)
        self.toolbar = toolbar
        
        self._add_file_actions()
        self._add_edit_actions()
        self._add_generate_action()
        self._add_preview_action()
        
        return toolbar
    
    def _add_file_actions(self):
        """添加文件操作按钮"""
        if self.toolbar is None:
            return
        
        # 新建
        new_btn = QToolButton()
        new_btn.setText(t("toolbar.new"))
        new_btn.clicked.connect(self.main_window.new_file)
        self.toolbar.addWidget(new_btn)
        
        # 打开
        open_btn = QToolButton()
        open_btn.setText(t("toolbar.open"))
        open_btn.clicked.connect(self.main_window.open_svd_file)
        self.toolbar.addWidget(open_btn)
        
        # 保存
        save_btn = QToolButton()
        save_btn.setText(t("toolbar.save"))
        save_btn.clicked.connect(self.main_window.save_svd_file)
        self.toolbar.addWidget(save_btn)
        
        self.toolbar.addSeparator()
    
    def _add_edit_actions(self):
        """添加编辑操作按钮"""
        if self.toolbar is None:
            return
        
        # 撤消
        undo_btn = QToolButton()
        undo_btn.setText(t("toolbar.undo"))
        undo_btn.clicked.connect(self.main_window.undo)
        self.toolbar.addWidget(undo_btn)
        
        # 重做
        redo_btn = QToolButton()
        redo_btn.setText(t("toolbar.redo"))
        redo_btn.clicked.connect(self.main_window.redo)
        self.toolbar.addWidget(redo_btn)
        
        self.toolbar.addSeparator()
    
    def _add_generate_action(self):
        """添加生成操作按钮"""
        if self.toolbar is None:
            return
        
        # 生成SVD
        generate_btn = QToolButton()
        generate_btn.setText(t("toolbar.generate_svd"))
        generate_btn.clicked.connect(self.main_window.generate_svd)
        generate_btn.setObjectName("generateSvdBtn")
        self.toolbar.addWidget(generate_btn)
        
        self.toolbar.addSeparator()
    
    def _add_preview_action(self):
        """添加预览窗口按钮"""
        if self.toolbar is None:
            return
        
        # 实时预览
        preview_btn = QToolButton()
        preview_btn.setText(t("toolbar.preview"))
        preview_btn.clicked.connect(self.main_window.open_preview_window)
        self.toolbar.addWidget(preview_btn)
        
        self.toolbar.addSeparator()