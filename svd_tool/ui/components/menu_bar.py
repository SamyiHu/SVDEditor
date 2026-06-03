"""
菜单栏组件
从 main_window.py 中提取的独立组件
"""
from typing import Callable, Optional
from PyQt6.QtWidgets import (
    QMenuBar, QMenu
)
from PyQt6.QtGui import QKeySequence, QAction
from ...i18n.i18n import t
from ...config.icons import get_icon


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
        
        file_menu = self.menubar.addMenu(t("menu.file"))
        if file_menu is None:
            return
        
        # 新建
        new_action = QAction(t("menu.file.new"), self.parent)
        new_action.triggered.connect(self.main_window.new_file)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.setIcon(get_icon("file_new"))
        file_menu.addAction(new_action)
        
        # 打开
        open_action = QAction(t("menu.file.open"), self.parent)
        open_action.triggered.connect(self.main_window.open_svd_file)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.setIcon(get_icon("file_open"))
        file_menu.addAction(open_action)
        
        # 保存
        save_action = QAction(t("menu.file.save"), self.parent)
        save_action.triggered.connect(self.main_window.save_svd_file)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.setIcon(get_icon("file_save"))
        file_menu.addAction(save_action)
        
        # 另存为
        save_as_action = QAction(t("menu.file.save_as"), self.parent)
        save_as_action.triggered.connect(self.main_window.save_svd_file_as)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.setIcon(get_icon("file_save_as"))
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        # 关闭文档
        close_doc_action = QAction(t("menu.file.close_doc", default="关闭文档"), self.parent)
        close_doc_action.triggered.connect(self._close_current_document)
        close_doc_action.setShortcut(QKeySequence("Ctrl+W"))
        file_menu.addAction(close_doc_action)
        
        # 关闭所有文档
        close_all_action = QAction(t("menu.file.close_all", default="关闭所有文档"), self.parent)
        close_all_action.triggered.connect(self._close_all_documents)
        close_all_action.setShortcut(QKeySequence("Ctrl+Shift+W"))
        file_menu.addAction(close_all_action)
        
        file_menu.addSeparator()
        
        # 退出
        exit_action = QAction(t("menu.file.exit"), self.parent)
        exit_action.triggered.connect(self.parent.close)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.setIcon(get_icon("file_exit"))
        file_menu.addAction(exit_action)
    def _create_edit_menu(self):
        """创建编辑菜单"""
        edit_menu = self.menubar.addMenu(t("menu.edit"))
        
        # 撤消
        undo_action = QAction(t("menu.edit.undo"), self.parent)
        undo_action.triggered.connect(self.main_window.undo)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        undo_action.setIcon(get_icon("edit_undo"))
        edit_menu.addAction(undo_action)
        
        # 重做
        redo_action = QAction(t("menu.edit.redo"), self.parent)
        redo_action.triggered.connect(self.main_window.redo)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        redo_action.setIcon(get_icon("edit_redo"))
        edit_menu.addAction(redo_action)
        
        edit_menu.addSeparator()
        
        # 高级搜索
        advanced_search_action = QAction(t("menu.edit.advanced_search"), self.parent)
        advanced_search_action.triggered.connect(self.main_window.show_advanced_search)
        advanced_search_action.setShortcut(QKeySequence("Ctrl+H"))
        edit_menu.addAction(advanced_search_action)

        # 跳转到地址
        goto_addr_action = QAction(t("menu.edit.goto_address"), self.parent)
        goto_addr_action.triggered.connect(self.main_window.show_goto_address)
        goto_addr_action.setShortcut(QKeySequence("Ctrl+Shift+G"))
        edit_menu.addAction(goto_addr_action)

        edit_menu.addSeparator()

        # 批量操作子菜单
        batch_menu = edit_menu.addMenu(t("menu.edit.batch_ops"))

        batch_modify_action = QAction(t("menu.edit.batch_modify"), self.parent)
        batch_modify_action.triggered.connect(self.main_window.show_batch_modify)
        batch_menu.addAction(batch_modify_action)

        batch_generate_action = QAction(t("menu.edit.batch_generate"), self.parent)
        batch_generate_action.triggered.connect(self.main_window.show_batch_generate)
        batch_menu.addAction(batch_generate_action)

        batch_clone_action = QAction(t("menu.edit.batch_clone"), self.parent)
        batch_clone_action.triggered.connect(self.main_window.show_batch_clone)
        batch_menu.addAction(batch_clone_action)
        
        edit_menu.addSeparator()
        
        # 剪切（暂未实现功能）
        cut_action = QAction(t("menu.edit.cut"), self.parent)
        cut_action.setShortcut(QKeySequence.StandardKey.Cut)
        edit_menu.addAction(cut_action)
        
        # 复制（暂未实现功能）
        copy_action = QAction(t("menu.edit.copy"), self.parent)
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        edit_menu.addAction(copy_action)
        
        # 粘贴（暂未实现功能）
        paste_action = QAction(t("menu.edit.paste"), self.parent)
        paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        edit_menu.addAction(paste_action)
    
    def _create_view_menu(self):
        """创建视图菜单"""
        view_menu = self.menubar.addMenu(t("menu.view"))
        
        # 展开所有
        expand_all_action = QAction(t("menu.view.expand_all"), self.parent)
        expand_all_action.triggered.connect(self.main_window.expand_all_tree)
        expand_all_action.setIcon(get_icon("view_expand"))
        view_menu.addAction(expand_all_action)
        
        # 折叠所有
        collapse_all_action = QAction(t("menu.view.collapse_all"), self.parent)
        collapse_all_action.triggered.connect(self.main_window.collapse_all_tree)
        collapse_all_action.setIcon(get_icon("view_collapse"))
        view_menu.addAction(collapse_all_action)
        
        view_menu.addSeparator()
        
        # ===== 显示子菜单（统一管理所有显示选项） =====
        display_menu = view_menu.addMenu(t("menu.view.display"))

        # SVD预览窗口（可切换，默认隐藏）
        self.main_window.toggle_preview_action = QAction(t("menu.view.svd_preview"), self.parent)
        self.main_window.toggle_preview_action.setCheckable(True)
        self.main_window.toggle_preview_action.setChecked(False)
        self.main_window.toggle_preview_action.setShortcut(QKeySequence("Ctrl+P"))
        self.main_window.toggle_preview_action.triggered.connect(self.main_window.toggle_preview_window)
        display_menu.addAction(self.main_window.toggle_preview_action)

        display_menu.addSeparator()

        # 位域图选项
        self.main_window.toggle_bit_field_action = QAction(t("menu.view.hide_bit_field"), self.parent)
        self.main_window.toggle_bit_field_action.setCheckable(True)
        self.main_window.toggle_bit_field_action.setChecked(False)
        self.main_window.toggle_bit_field_action.triggered.connect(self.main_window.toggle_bit_field_visibility)
        display_menu.addAction(self.main_window.toggle_bit_field_action)
        
        # 地址映射图选项
        self.main_window.toggle_address_map_action = QAction(t("menu.view.hide_address_map"), self.parent)
        self.main_window.toggle_address_map_action.setCheckable(True)
        self.main_window.toggle_address_map_action.setChecked(False)
        self.main_window.toggle_address_map_action.triggered.connect(self.main_window.toggle_address_map_visibility)
        display_menu.addAction(self.main_window.toggle_address_map_action)
        
        view_menu.addSeparator()
        
        # 深色模式切换
        self.main_window.toggle_dark_mode_action = QAction(t("menu.view.dark_mode"), self.parent)
        self.main_window.toggle_dark_mode_action.setCheckable(True)
        self.main_window.toggle_dark_mode_action.setChecked(False)
        self.main_window.toggle_dark_mode_action.triggered.connect(self.main_window.toggle_dark_mode)
        view_menu.addAction(self.main_window.toggle_dark_mode_action)
        
        # 语言切换
        language_menu = view_menu.addMenu(t("menu.view.language"))
        
        # 中文
        zh_action = QAction("中文", self.parent)
        zh_action.triggered.connect(lambda: self.main_window.set_language("zh_CN"))
        language_menu.addAction(zh_action)
        
        # English
        en_action = QAction("English", self.parent)
        en_action.triggered.connect(lambda: self.main_window.set_language("en_US"))
        language_menu.addAction(en_action)
        
        view_menu.addSeparator()
        
        # 日志显示切换
        self.main_window.toggle_log_action = QAction(t("menu.view.show_log"), self.parent)
        self.main_window.toggle_log_action.setCheckable(True)
        self.main_window.toggle_log_action.setChecked(False)
        self.main_window.toggle_log_action.triggered.connect(self.main_window.toggle_log_panel)
        view_menu.addAction(self.main_window.toggle_log_action)
        
        # 错误自动保存开关
        self.main_window.toggle_auto_save_action = QAction(t("menu.view.auto_save_log"), self.parent)
        self.main_window.toggle_auto_save_action.setCheckable(True)
        self.main_window.toggle_auto_save_action.setChecked(True)
        self.main_window.toggle_auto_save_action.triggered.connect(
            lambda checked: setattr(self.main_window, 'auto_save_error', checked)
        )
        view_menu.addAction(self.main_window.toggle_auto_save_action)

        # AI 助手面板切换
        if hasattr(self.main_window, 'ai_assistant') and self.main_window.ai_assistant:
            view_menu.addSeparator()
            self.main_window.toggle_ai_assistant_action = QAction(
                t("menu.view.ai_assistant", default="AI 助手"), self.parent)
            self.main_window.toggle_ai_assistant_action.setCheckable(True)
            self.main_window.toggle_ai_assistant_action.setChecked(False)
            self.main_window.toggle_ai_assistant_action.setShortcut(QKeySequence("Ctrl+Shift+A"))
            self.main_window.toggle_ai_assistant_action.triggered.connect(self.main_window.toggle_ai_assistant)
            view_menu.addAction(self.main_window.toggle_ai_assistant_action)
    
    def _create_tools_menu(self):
        """创建工具菜单"""
        tools_menu = self.menubar.addMenu(t("menu.tools"))
        
        # 验证数据
        validate_action = QAction(t("menu.tools.validate"), self.parent)
        validate_action.triggered.connect(self.main_window.validate_data)
        validate_action.setIcon(get_icon("tools_validate"))
        tools_menu.addAction(validate_action)

        tools_menu.addSeparator()
        
        # 导出文档子菜单
        export_menu = tools_menu.addMenu(t("menu.tools.export_doc"))

        # CSV 寄存器详情
        csv_action = QAction(t("menu.tools.export_csv"), self.parent)
        csv_action.triggered.connect(lambda: self.main_window.export_document("csv"))
        export_menu.addAction(csv_action)

        # CSV 寄存器汇总
        csv_summary_action = QAction(t("menu.tools.export_csv_summary"), self.parent)
        csv_summary_action.triggered.connect(lambda: self.main_window.export_document("csv_summary"))
        export_menu.addAction(csv_summary_action)

        # Markdown
        md_action = QAction(t("menu.tools.export_markdown"), self.parent)
        md_action.triggered.connect(lambda: self.main_window.export_document("markdown"))
        md_action.setShortcut(QKeySequence("Ctrl+Shift+M"))
        export_menu.addAction(md_action)

        # HTML
        html_action = QAction(t("menu.tools.export_html"), self.parent)
        html_action.triggered.connect(lambda: self.main_window.export_document("html"))
        export_menu.addAction(html_action)

        # C头文件
        header_action = QAction(t("menu.tools.export_header"), self.parent)
        header_action.triggered.connect(self.main_window.export_header_file)
        export_menu.addAction(header_action)
        
        tools_menu.addSeparator()

        # SVD 比较
        diff_action = QAction(t("menu.tools.svd_diff", default="SVD 比较"), self.parent)
        diff_action.triggered.connect(self.main_window.show_svd_diff)
        diff_action.setShortcut(QKeySequence("Ctrl+D"))
        tools_menu.addAction(diff_action)

        # SVD 比较与合并
        diff_merge_action = QAction(t("menu.tools.svd_diff_merge"), self.parent)
        diff_merge_action.triggered.connect(self.main_window.show_svd_diff_merge)
        diff_merge_action.setShortcut(QKeySequence("Ctrl+Shift+D"))
        tools_menu.addAction(diff_merge_action)


        tools_menu.addSeparator()
        
        # 连锁操作开关
        self.main_window.toggle_chain_action = QAction(
            t("menu.tools.chain_enabled"), self.parent)
        self.main_window.toggle_chain_action.setCheckable(True)
        self.main_window.toggle_chain_action.setChecked(True)
        self.main_window.toggle_chain_action.triggered.connect(
            lambda checked: setattr(self.main_window.chain_rules_engine, 'enabled', checked))
        tools_menu.addAction(self.main_window.toggle_chain_action)

        # 继承外设不写入寄存器开关
        self.main_window.skip_derived_action = QAction(
            t("menu.tools.skip_derived_registers"), self.parent)
        self.main_window.skip_derived_action.setCheckable(True)
        self.main_window.skip_derived_action.setChecked(True)
        self.main_window.skip_derived_action.setToolTip(t("menu.tools.skip_derived_registers_tip"))
        self.main_window.skip_derived_action.triggered.connect(
            self.main_window.toggle_skip_derived_registers)
        tools_menu.addAction(self.main_window.skip_derived_action)
        
        # 连锁规则编辑
        chain_edit_action = QAction(
            t("menu.tools.chain_rules"), self.parent)
        chain_edit_action.triggered.connect(self.main_window.show_chain_rules_dialog)
        tools_menu.addAction(chain_edit_action)

        # AI 助手设置
        if hasattr(self.main_window, 'ai_assistant') and self.main_window.ai_assistant:
            tools_menu.addSeparator()
            ai_settings_action = QAction(
                t("menu.tools.ai_settings", default="AI 助手设置..."), self.parent)
            ai_settings_action.triggered.connect(self.main_window.show_ai_assistant_settings)
            tools_menu.addAction(ai_settings_action)
    
    def _close_current_document(self):
        """关闭当前文档"""
        if hasattr(self.main_window, 'document_manager') and self.main_window.document_manager:
            active_id = self.main_window.document_manager.active_doc_id
            if active_id:
                self.main_window._on_document_tab_close(active_id)
    
    def _close_all_documents(self):
        """关闭所有文档"""
        if hasattr(self.main_window, 'document_manager') and self.main_window.document_manager:
            self.main_window.document_manager.clear_all()
    
    def _create_help_menu(self):
        """创建帮助菜单"""
        help_menu = self.menubar.addMenu(t("menu.help"))
        
        # 关于
        about_action = QAction(t("menu.help.about"), self.parent)
        about_action.triggered.connect(self.main_window.show_about)
        about_action.setIcon(get_icon("help_about"))
        help_menu.addAction(about_action)
