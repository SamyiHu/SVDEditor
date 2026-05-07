import os
import logging
from datetime import datetime
from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit,
    QDockWidget, QCheckBox, QFileDialog, QMessageBox, QToolBar
)
from ...i18n.i18n import t


class SettingsActionsMixin:

    def toggle_dark_mode(self, checked: bool):
        """切换深色模式"""
        from ...config.styles import set_dark_mode, get_current_stylesheet
        set_dark_mode(checked)
        self.setStyleSheet(get_current_stylesheet())

        # 更新可视化控件背景
        visualization_widget = self.layout_manager.get_widget('visualization_widget')
        if visualization_widget:
            visualization_widget.update()

        status = t("status.dark_mode_on") if checked else t("status.dark_mode_off")
        self.layout_manager.update_status(status)

    def set_language(self, locale: str):
        """设置语言"""
        if hasattr(self, 'i18n_manager') and self.i18n_manager:
            self.i18n_manager.set_locale(locale)
            language_name = "中文" if locale == "zh_CN" else "English"
            self.layout_manager.update_status(t("msg.language_changed", language=language_name))
            self.logger.info(f"语言已切换为: {language_name}")

            # 重新创建菜单栏以更新文本
            self._recreate_menu_bar()

            # 重新创建工具栏以更新文本
            self._recreate_toolbar()

            # 更新搜索相关文本
            self._update_search_ui()

            # 重新创建标签页以更新文本（但保留数据）
            self._recreate_tabs()

            # 刷新欢迎页文本
            welcome_page = self.layout_manager.get_widget('welcome_page')
            if welcome_page and hasattr(welcome_page, 'refresh_ui'):
                welcome_page.refresh_ui()

    def _recreate_toolbar(self):
        """重新创建工具栏以更新语言"""
        # 删除所有现有工具栏
        toolbars = self.findChildren(QToolBar)
        for toolbar in toolbars:
            self.removeToolBar(toolbar)

        # 重新创建工具栏
        from ..components.toolbar import ToolBarBuilder
        toolbar_builder = ToolBarBuilder(self, self)
        toolbar_builder.create()

    def _recreate_menu_bar(self):
        """重新创建菜单栏以更新语言"""
        # 清除现有菜单栏
        menubar = self.menuBar()
        if menubar:
            menubar.clear()

        # 重新创建菜单栏
        from ..components.menu_bar import MenuBarBuilder
        menu_builder = MenuBarBuilder(self, self)
        menu_builder.create()

    def _update_search_ui(self):
        """更新搜索相关的UI文本"""
        # 更新搜索标签
        search_label = self.layout_manager.get_widget('search_label')
        if search_label:
            search_label.setText(t("search.label"))

        # 更新搜索框占位符
        search_edit = self.layout_manager.get_widget('search_edit')
        if search_edit:
            search_edit.setPlaceholderText(t("search.placeholder"))

        # 更新搜索按钮文本
        search_prev_btn = self.layout_manager.get_widget('search_prev_btn')
        if search_prev_btn:
            search_prev_btn.setText(t("search.prev"))

        search_next_btn = self.layout_manager.get_widget('search_next_btn')
        if search_next_btn:
            search_next_btn.setText(t("search.next"))

    def _update_tab_titles(self):
        """更新标签页标题（不重新创建标签页）"""
        tab_widget = self.layout_manager.get_widget('tab_widget')
        if not tab_widget:
            return

        # 更新标签页标题
        tab_widget.setTabText(0, t("tab.basic_info"))
        tab_widget.setTabText(1, t("tab.peripherals"))
        tab_widget.setTabText(2, t("tab.interrupts"))
        tab_widget.setTabText(3, t("tab.preview"))

    def _recreate_tabs(self):
        """重新创建标签页以更新语言"""
        # 获取标签页控件
        tab_widget = self.layout_manager.get_widget('tab_widget')
        if not tab_widget:
            return

        # 保存当前选中的标签页索引
        current_index = tab_widget.currentIndex()

        # 保存当前状态快照（包括设备信息和选中状态）
        state_snapshot = self.state_manager.get_device_state_snapshot()

        # 清理 realtime_preview 资源（在删除标签页之前）
        realtime_preview = self.layout_manager.get_widget('realtime_preview')
        if realtime_preview and hasattr(realtime_preview, 'cleanup'):
            try:
                realtime_preview.cleanup()
            except Exception as e:
                import logging
                logging.warning(f"清理 realtime_preview 时出错: {e}")

        # 清除所有标签页
        while tab_widget.count() > 0:
            tab_widget.removeTab(0)

        # 重新创建标签页
        self.layout_manager.create_basic_info_tab(tab_widget)
        self.layout_manager.create_peripheral_tab(tab_widget)
        self.layout_manager.create_interrupt_tab(tab_widget)

        # 重新连接UI信号（重要：重新创建标签页后必须重新连接信号）
        self.peripheral_manager.connect_ui_signals()
        self.setup_signals()

        # 重新连接中断表格右键菜单
        irq_table = self.layout_manager.get_widget('irq_table')
        if irq_table:
            irq_table.customContextMenuRequested.disconnect()
            irq_table.customContextMenuRequested.connect(self.on_irq_context_menu)

        # 恢复状态快照（包括设备信息和选中状态）
        self.state_manager.restore_device_state(state_snapshot)

        # 刷新UI以显示恢复的数据
        # 直接传递设备信息，避免通过coordinator获取
        self.device_info_manager.update_ui_from_device_info(self.state_manager.device_info)
        self.peripheral_manager.update_peripheral_tree()
        self._update_interrupt_table()

        # 恢复之前选中的标签页
        if current_index >= 0 and current_index < tab_widget.count():
            tab_widget.setCurrentIndex(current_index)

        # 重新填充数据到新创建的控件中
        self._refresh_all_data()

    def show_about(self):
        """显示关于对话框（内容来自配置文件，支持国际化）"""
        import json
        from ... import __version__

        # 读取 about.json 配置
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "config", "about.json"
        )
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                about_cfg = json.load(f)
        except Exception:
            about_cfg = {}

        app_name = about_cfg.get("app_name", "SVD Tool")
        author = about_cfg.get("author", {})
        license_info = about_cfg.get("license", {})
        copyright_year = about_cfg.get("copyright_year", "2025")

        # 通过 i18n 获取翻译文本
        version_text = t("about.version", version=__version__)
        description = t("about.description")
        features_title = t("about.features")
        features = [t(key) for key in about_cfg.get("features", [])]
        author_label = t("about.author")
        license_label = t("about.license")
        copyright_text = t("about.copyright", year=copyright_year, author=author.get("name", ""))

        # 构造 HTML
        features_html = "".join(f"<li>{f}</li>" for f in features)
        about_text = f"""
        <h2>{app_name}</h2>
        <p>{version_text}</p>
        <p>{description}</p>
        <p>{features_title}:</p>
        <ul>{features_html}</ul>
        <hr>
        <p>{author_label}: <a href="{author.get('url', '')}">{author.get('name', '')}</a></p>
        <p>{license_label}: <a href="{license_info.get('url', '')}">{license_info.get('name', '')}</a></p>
        <p>{copyright_text}</p>
        """

        # 创建日志面板（如果不存在）
        if not hasattr(self, 'log_dock') or not self.log_dock:
            self.create_log_panel()

        QMessageBox.about(self, t("about.title"), about_text)
        self.logger.info("显示关于对话框")

    def create_log_panel(self):
        """创建可切换的日志面板并绑定日志处理器"""
        # 如果日志面板已存在，直接返回
        if hasattr(self, 'log_dock') and self.log_dock:
            return

        # 日志停靠窗口
        self.log_dock = QDockWidget("日志", self)
        self.log_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.TopDockWidgetArea)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)

        # 使用容器放置操作按钮和文本区
        container = QWidget()
        container_layout = QVBoxLayout(container)

        # 顶部工具栏：按钮和复选框
        toolbar = QHBoxLayout()

        clear_btn = QPushButton("清空日志")
        clear_btn.clicked.connect(self.clear_log)
        toolbar.addWidget(clear_btn)

        save_btn = QPushButton("保存日志")
        save_btn.clicked.connect(self.save_log_to_file)
        toolbar.addWidget(save_btn)

        toolbar.addStretch()

        # 添加"显示Debug日志"复选框
        self.show_debug_checkbox = QCheckBox("显示Debug日志")
        self.show_debug_checkbox.setChecked(False)  # 默认不显示debug日志
        self.show_debug_checkbox.stateChanged.connect(self.on_debug_log_checkbox_changed)
        toolbar.addWidget(self.show_debug_checkbox)

        # 添加"禁用调试日志"复选框
        self.disable_debug_checkbox = QCheckBox("禁用调试日志")
        self.disable_debug_checkbox.setChecked(False)  # 默认不禁用调试日志
        self.disable_debug_checkbox.stateChanged.connect(self.on_disable_debug_checkbox_changed)
        toolbar.addWidget(self.disable_debug_checkbox)

        container_layout.addLayout(toolbar)
        container_layout.addWidget(self.log_text)
        self.log_dock.setWidget(container)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)
        self.log_dock.hide()

        # 日志信号和处理器
        from PyQt6.QtCore import QObject, pyqtSignal

        class _LogSignalEmitter(QObject):
            append_text = pyqtSignal(str)

        self._log_emitter = _LogSignalEmitter()
        self._log_emitter.append_text.connect(self._append_log_text)

        class GuiLogHandler(logging.Handler):
            def __init__(self, emitter, owner=None):
                super().__init__()
                self.emitter = emitter
                self.owner = owner
                # 初始级别设置为INFO，避免大量DEBUG日志阻塞UI线程
                self.setLevel(logging.INFO)

            def emit(self, record):
                try:
                    msg = self.format(record)
                    # 通过信号在主线程追加文本
                    self.emitter.append_text.emit(msg)

                    # 如果是错误级别且启用了自动保存，则把日志写入文件（包含当前面板内容）
                    try:
                        if (hasattr(self, 'owner') and self.owner is not None and
                                getattr(self.owner, 'auto_save_error', False) and
                                record.levelno >= logging.ERROR):
                            logs_dir = os.path.join(os.getcwd(), 'logs')
                            os.makedirs(logs_dir, exist_ok=True)
                            fname = datetime.now().strftime('svd_error_%Y%m%d_%H%M%S.log')
                            path = os.path.join(logs_dir, fname)
                            existing = ''
                            if hasattr(self.owner, 'log_text') and self.owner.log_text:
                                existing = self.owner.log_text.toPlainText()
                            with open(path, 'w', encoding='utf-8') as f:
                                f.write(existing + '\n' + msg)
                    except Exception:
                        pass  # 文件保存失败不影响主流程
                except Exception:
                    pass  # 日志显示失败不影响主流程

        self._gui_log_handler = GuiLogHandler(self._log_emitter, self)
        # 将GUI日志处理器添加到根logger，这样所有logger的日志都会显示在日志面板中
        root_logger = logging.getLogger()
        root_logger.addHandler(self._gui_log_handler)

        # 创建日志面板后，在init_ui中调用
        self.logger.info("日志面板已创建")

    def _append_log_text(self, text: str):
        """在日志文本框中追加文本（线程安全）"""
        if hasattr(self, 'log_text') and self.log_text:
            self.log_text.append(text)
            # 自动滚动到底部
            scrollbar = self.log_text.verticalScrollBar()
            if scrollbar:
                scrollbar.setValue(scrollbar.maximum())

    def on_debug_log_checkbox_changed(self, state):
        """处理Debug日志复选框状态变化"""
        show_debug = (state == Qt.CheckState.Checked.value)
        # 更新日志记录器的控制台级别
        self.logger.enable_debug_logs(show_debug)
        # 更新GUI日志处理器的过滤级别
        if hasattr(self, '_gui_log_handler') and self._gui_log_handler is not None:
            if show_debug:
                self._gui_log_handler.setLevel(logging.DEBUG)
            else:
                self._gui_log_handler.setLevel(logging.INFO)
        # 更新状态显示
        status_msg = "Debug日志已启用" if show_debug else "Debug日志已禁用"
        self.layout_manager.update_status(status_msg)
        self.logger.info(status_msg)

    def on_disable_debug_checkbox_changed(self, state):
        """处理禁用调试日志复选框状态变化"""
        disable_debug = (state == Qt.CheckState.Checked.value)
        # 更新调试日志开关
        self.logger.enable_debug_logs(not disable_debug)
        # 更新GUI日志处理器的过滤级别
        if hasattr(self, '_gui_log_handler') and self._gui_log_handler is not None:
            self._gui_log_handler.setLevel(logging.INFO if disable_debug else logging.DEBUG)
        # 更新状态显示
        status_msg = "调试日志已禁用" if disable_debug else "调试日志已启用"
        self.layout_manager.update_status(status_msg)
        self.logger.info(status_msg)

    def clear_log(self):
        """清空日志面板内容"""
        try:
            if hasattr(self, 'log_text') and self.log_text:
                self.log_text.clear()
                self.layout_manager.update_status(t("status.log_cleared"))
                self.logger.info("日志面板已清空")
        except Exception as e:
            self.logger.error(f"清空日志时出错: {str(e)}")

    def save_log_to_file(self):
        """手动保存当前日志到文件（弹出保存对话框）"""
        try:
            if not hasattr(self, 'log_text') or not self.log_text:
                QMessageBox.warning(self, t("message.warning"), t("msg.log_panel_not_created"))
                return

            log_content = self.log_text.toPlainText()
            if not log_content.strip():
                QMessageBox.warning(self, t("message.warning"), t("msg.log_content_empty"))
                return

            file_path, _ = QFileDialog.getSaveFileName(
                self, t("msg.save_success"), "svd_log.txt", "文本文件 (*.txt);;所有文件 (*.*)"
            )

            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(log_content)

                self.layout_manager.update_status(t("status.log_saved", path=file_path))
                self.logger.info(f"日志已保存到: {file_path}")
                QMessageBox.information(self, t("message.success"), t("msg.log_save_success"))

        except Exception as e:
            self.logger.error(f"保存日志时出错: {str(e)}")
            QMessageBox.warning(self, t("message.error"), t("msg.save_log_error_detail", error=str(e)))

    def toggle_log_panel(self, checked: bool):
        """切换日志面板显示/隐藏"""
        try:
            if not hasattr(self, 'log_dock') or not self.log_dock:
                # 如果日志面板不存在，先创建
                try:
                    self.create_log_panel()
                except Exception:
                    QMessageBox.warning(self, t("message.error"), t("msg.create_log_panel_error"))
                    return

            if checked:
                self.log_dock.show()
                self.layout_manager.update_status(t("status.log_panel_shown"))
            else:
                self.log_dock.hide()
                self.layout_manager.update_status(t("status.log_panel_hidden"))

        except Exception as e:
            self.logger.error(f"切换日志面板时出错: {str(e)}")

    def toggle_ai_assistant(self, checked: bool):
        """切换 AI 助手面板显示/隐藏"""
        if self.ai_assistant:
            self.ai_assistant.toggle_panel()

    def show_ai_assistant_settings(self):
        """显示 AI 助手设置"""
        if self.ai_assistant:
            self.ai_assistant.show_settings()

    def show_chain_rules_dialog(self):
        """显示连锁规则编辑对话框"""
        from ..dialogs.chain_rules_dialog import ChainRulesDialog
        dialog = ChainRulesDialog(self, self.chain_rules_engine)
        dialog.exec()

    def update_data_stats(self):
        """更新数据统计"""
        stats = self.state_manager.get_data_stats()
        self.layout_manager.update_data_stats(stats)

    def _refresh_all_data(self):
        """重新填充所有数据到新创建的控件中"""
        # 更新基础信息标签页
        if hasattr(self, 'device_info_manager'):
            self.device_info_manager.update_ui_from_device_info(self.state_manager.device_info)

        # 更新外设树
        if hasattr(self, 'peripheral_manager'):
            self.peripheral_manager.update_peripheral_tree()

        # 更新中断表格
        self._update_interrupt_table()

        # 更新可视化控件（使用当前选择）
        selection = self.state_manager.get_selection()
        self.update_visualization(
            selection.get('peripheral') or '',
            selection.get('register') or '',
            selection.get('field') or ''
        )

        # 更新位域表格
        if selection.get('register') and selection.get('peripheral'):
            device_info = self.state_manager.device_info
            if (selection['peripheral'] in device_info.peripherals and
                selection['register'] in device_info.peripherals[selection['peripheral']].registers):
                reg_obj = device_info.peripherals[selection['peripheral']].registers[selection['register']]
                self.layout_manager.update_field_table(selection['peripheral'], selection['register'], reg_obj)
            else:
                self.layout_manager.update_field_table()
        else:
            self.layout_manager.update_field_table()

        # 更新位域图（触发重绘以更新语言）
        visualization_widget = self.layout_manager.get_widget('visualization_widget')
        if visualization_widget and hasattr(visualization_widget, 'bit_field'):
            visualization_widget.bit_field.update()

    def apply_styles(self):
        """应用样式"""
        from ...config.styles import get_current_stylesheet
        self.setStyleSheet(get_current_stylesheet())
