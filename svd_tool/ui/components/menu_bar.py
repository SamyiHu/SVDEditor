"""
菜单栏组件
从 main_window.py 中提取的独立组件
"""
from typing import Callable, Optional
from PyQt6.QtWidgets import (
    QMenuBar, QMenu
)
from PyQt6.QtGui import QKeySequence, QAction


class MenuBarBuilder:
    """菜单栏构建器"""
    
    def __init__(self, parent, main_window):
        """
        初始化菜单栏构建器
        
        Args:
            parent: 父窗口
            main_window: 主窗口实例，用于连接信号
        """
        self.parent = parent
        self.main_window = main_window
        self.menubar = None
        
    def create(self) -> QMenuBar:
        """创建菜单栏并返回"""
        menubar = self.parent.menuBar()
        if menubar is None:
            menubar = QMenuBar(self.parent)
            self.parent.setMenuBar(menubar)
        
        self.menubar = menubar
        self._create_file_menu()
        self._create_edit_menu()
        self._create_view_menu()
        self._create_tools_menu()
        self._create_help_menu()
        
        return menubar
    
    def _create_file_menu(self):
        """创建文件菜单"""
        if self.menubar is None:
            return
        file_menu = self.menubar.addMenu("文件")
        if file_menu is None:
            return
        
        # 新建
        new_action = QAction("新建", self.parent)
        new_action.triggered.connect(self.main_window.new_file)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        file_menu.addAction(new_action)
        
        # 打开
        open_action = QAction("打开SVD", self.parent)
        open_action.triggered.connect(self.main_window.open_svd_file)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        file_menu.addAction(open_action)
        
        # 保存
        save_action = QAction("保存SVD", self.parent)
        save_action.triggered.connect(self.main_window.save_svd_file)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        file_menu.addAction(save_action)
        
        # 另存为
        save_as_action = QAction("另存为", self.parent)
        save_as_action.triggered.connect(self.main_window.save_svd_file_as)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        # 退出
        exit_action = QAction("退出", self.parent)
        exit_action.triggered.connect(self.parent.close)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        file_menu.addAction(exit_action)
    
    def _create_edit_menu(self):
        """创建编辑菜单"""
        edit_menu = self.menubar.addMenu("编辑")
        
        # 撤消
        undo_action = QAction("撤消", self.parent)
        undo_action.triggered.connect(self.main_window.undo)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        edit_menu.addAction(undo_action)
        
        # 重做
        redo_action = QAction("重做", self.parent)
        redo_action.triggered.connect(self.main_window.redo)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        edit_menu.addAction(redo_action)
        
        edit_menu.addSeparator()
        
        # 剪切（暂未实现功能）
        cut_action = QAction("剪切", self.parent)
        cut_action.setShortcut(QKeySequence.StandardKey.Cut)
        edit_menu.addAction(cut_action)
        
        # 复制（暂未实现功能）
        copy_action = QAction("复制", self.parent)
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        edit_menu.addAction(copy_action)
        
        # 粘贴（暂未实现功能）
        paste_action = QAction("粘贴", self.parent)
        paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        edit_menu.addAction(paste_action)
    
    def _create_view_menu(self):
        """创建视图菜单"""
        view_menu = self.menubar.addMenu("视图")
        
        # 展开所有
        expand_all_action = QAction("展开所有", self.parent)
        expand_all_action.triggered.connect(self.main_window.expand_all_tree)
        view_menu.addAction(expand_all_action)
        
        # 折叠所有
        collapse_all_action = QAction("折叠所有", self.parent)
        collapse_all_action.triggered.connect(self.main_window.collapse_all_tree)
        view_menu.addAction(collapse_all_action)
        
        view_menu.addSeparator()
        
        # 日志显示切换
        self.main_window.toggle_log_action = QAction("显示日志", self.parent)
        self.main_window.toggle_log_action.setCheckable(True)
        self.main_window.toggle_log_action.setChecked(False)
        self.main_window.toggle_log_action.triggered.connect(self.main_window.toggle_log_panel)
        view_menu.addAction(self.main_window.toggle_log_action)
        
        # 错误自动保存开关
        self.main_window.toggle_auto_save_action = QAction("错误发生时自动保存日志", self.parent)
        self.main_window.toggle_auto_save_action.setCheckable(True)
        self.main_window.toggle_auto_save_action.setChecked(True)
        self.main_window.toggle_auto_save_action.triggered.connect(
            lambda checked: setattr(self.main_window, 'auto_save_error', checked)
        )
        view_menu.addAction(self.main_window.toggle_auto_save_action)
    
    def _create_tools_menu(self):
        """创建工具菜单"""
        tools_menu = self.menubar.addMenu("工具")
        
        # 验证数据
        validate_action = QAction("验证数据", self.parent)
        validate_action.triggered.connect(self.main_window.validate_data)
        tools_menu.addAction(validate_action)
        
        # 生成SVD
        generate_action = QAction("生成SVD", self.parent)
        generate_action.triggered.connect(self.main_window.generate_svd)
        generate_action.setShortcut(QKeySequence("Ctrl+G"))
        tools_menu.addAction(generate_action)
    
    def _create_help_menu(self):
        """创建帮助菜单"""
        help_menu = self.menubar.addMenu("帮助")
        
        # 关于
        about_action = QAction("关于", self.parent)
        about_action.triggered.connect(self.main_window.show_about)
        help_menu.addAction(about_action)