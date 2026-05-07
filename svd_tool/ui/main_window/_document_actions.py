import copy
from PyQt6.QtWidgets import QMessageBox
from ...i18n.i18n import t
from ...core.data_model import DeviceInfo


class DocumentActionsMixin:
    """文档管理操作"""

    def new_file(self):
        """新建文件 - 使用向导引导创建"""
        from ..dialogs.new_svd_wizard import NewSVDWizard
        from ...core.data_model import DeviceInfo, CPUInfo

        wizard = NewSVDWizard(self)
        if wizard.exec() == NewSVDWizard.DialogCode.Accepted:
            # 先保存当前文档状态（确保数据隔离）
            self._save_current_document_state()

            # 从向导获取数据
            chip_name = wizard.field("chip_name") or ""
            vendor = wizard.field("vendor") or ""
            version = wizard.field("version") or "1.0"
            description = wizard.field("description") or ""
            series = wizard.field("series") or ""
            copyright_text = wizard.field("copyright") or ""
            cpu_type = wizard.field("cpu_type") or "CM4"
            cpu_revision = wizard.field("cpu_revision") or "r0p0"
            endian = wizard.field("endian") or "little"
            width = int(wizard.field("width") or 32)
            reset_value = wizard.field("reset_value") or "0x00000000"
            reset_mask = wizard.field("reset_mask") or "0xFFFFFFFF"
            access = wizard.field("access") or "read-write"

            # 创建 CPUInfo
            cpu_info = CPUInfo(name=cpu_type)
            cpu_info.revision = cpu_revision
            cpu_info.endian = endian
            cpu_info.mpu_present = 1
            cpu_info.fpu_present = 1
            cpu_info.nvic_prio_bits = 4
            cpu_info.vendor_systick_config = 0

            # 创建 DeviceInfo
            device_info = DeviceInfo(name=chip_name)
            device_info.vendor = vendor
            device_info.version = version
            device_info.description = description
            device_info.cpu = cpu_info
            device_info.width = width
            device_info.reset_value = reset_value
            device_info.reset_mask = reset_mask

            # 暂停通知，防止旧文档的树展开状态泄漏到新文档
            self.state_manager.pause_notifications()

            try:
                # 更新状态管理器
                self.state_manager.device_info = device_info
                self.state_manager.clear_selection()
                self.state_manager.command_history.clear()

                # 重置预览器状态（新文档不应该继承旧文档的选中/折叠状态）
                if self.preview_manager and self.preview_manager.preview_widget:
                    pw = self.preview_manager.preview_widget
                    pw.folded_elements = set()
                    pw.current_selection = {
                        'type': None, 'peripheral': None, 'register': None,
                        'field': None, 'interrupt': None
                    }
                    if hasattr(pw, 'preview_edit') and pw.preview_edit:
                        pw.preview_edit.clear_highlight()

                # 更新UI（不保留旧文档的展开状态）
                self.peripheral_manager.update_peripheral_tree(preserve_expanded=False)
                self.update_data_stats()
                self._update_interrupt_table()
            finally:
                # 恢复通知（此时树已正确重建，不会泄漏展开状态）
                self.state_manager.resume_notifications()

            if hasattr(self.layout_manager, 'update_basic_info'):
                self.layout_manager.update_basic_info(device_info)

            self.layout_manager.update_status(t("status.file_created", name=chip_name))

            # 注册到文档管理器
            try:
                self.document_manager.open_document(
                    device_info, file_path=None, display_name=chip_name or "未命名")
            except Exception as e:
                self.logger.warning(f"注册文档到DocumentManager失败: {e}")

            # 切换到编辑器视图
            self.layout_manager.show_editor()
        else:
            # 用户取消向导，不做任何操作，留在当前页面
            pass

    def _save_current_document_state(self):
        """保存当前文档的UI状态到DocumentManager"""
        doc = self.document_manager.active_document
        if not doc:
            return

        # 保存选择状态
        selection = self.state_manager.get_selection()
        doc.selection = selection.copy()

        # 保存树展开状态
        periph_tree = self.layout_manager.get_widget('periph_tree')
        if periph_tree:
            from ..model.device_tree_model import DeviceTreeModel
            model = periph_tree.model()
            if isinstance(model, DeviceTreeModel):
                expanded_paths = model.get_expanded_paths(periph_tree)
                expanded_periphs = {}
                expanded_regs = {}
                for path in expanded_paths:
                    parts = path.split("/")
                    if len(parts) == 1:
                        expanded_periphs[parts[0]] = True
                    elif len(parts) == 2:
                        expanded_periphs[parts[0]] = True
                        expanded_regs[path] = True
                doc.tree_expanded_periphs = expanded_periphs
                doc.tree_expanded_regs = expanded_regs

        # 保存当前标签页索引
        tab_widget = self.layout_manager.get_widget('tab_widget')
        if tab_widget:
            doc.current_tab_index = tab_widget.currentIndex()

        # 保存中断表滚动位置
        irq_table = self.layout_manager.get_widget('irq_table')
        if irq_table:
            doc.irq_table_scroll = irq_table.verticalScrollBar().value()

        # 仅在数据被修改时才深拷贝（大幅减少切换文档时的开销）
        if doc.modified or doc.device_info is None:
            doc.device_info = copy.deepcopy(self.state_manager.device_info)
        else:
            # 未修改时直接引用（文档切换时不会修改 device_info）
            doc.device_info = self.state_manager.device_info

        # 保存命令历史（每个文档独立维护撤销/重做栈）
        doc.command_history = self.state_manager.command_history

        # 保存预览器折叠状态和选中状态
        if self.preview_manager and self.preview_manager.preview_widget:
            pw = self.preview_manager.preview_widget
            doc.preview_folded_elements = set(pw.folded_elements)
            if hasattr(pw, 'current_selection'):
                doc.preview_selection = dict(pw.current_selection)

    def _restore_document_state(self, doc: 'DocumentState'):
        """从DocumentState恢复文档的UI状态（优化：减少不必要的UI刷新）"""
        if not doc:
            return

        # 暂停通知，避免恢复过程中多次触发UI刷新
        self.state_manager.pause_notifications()

        try:
            # 恢复设备数据
            # 如果文档未修改，doc.device_info 就是 state_manager 原来的引用，可以直接使用
            # 如果文档已修改，doc.device_info 是之前保存时的深拷贝，需要再拷贝一份保证隔离
            if doc.modified:
                self.state_manager.device_info = copy.deepcopy(doc.device_info)
            else:
                # 未修改时直接使用引用（_save_current_document_state 保证了数据一致性）
                self.state_manager.device_info = doc.device_info

            # 恢复命令历史（每个文档独立维护撤销/重做栈）
            if doc.command_history is not None:
                self.state_manager.command_history = doc.command_history

            self.state_manager.clear_selection()

            # 恢复树（单次重建，不保留旧文档的展开状态）
            self.peripheral_manager.update_peripheral_tree(preserve_expanded=False)

            # 恢复树展开状态
            periph_tree = self.layout_manager.get_widget('periph_tree')
            if periph_tree:
                from ..model.device_tree_model import DeviceTreeModel
                model = periph_tree.model()
                if isinstance(model, DeviceTreeModel):
                    # 从旧格式还原展开路径
                    paths = list(doc.tree_expanded_periphs.keys())
                    for reg_key in doc.tree_expanded_regs:
                        if reg_key not in paths:
                            paths.append(reg_key)
                    model.restore_expanded(periph_tree, paths)

            # 恢复选择
            if doc.selection:
                sel = doc.selection
                self.state_manager.set_selection(
                    peripheral=sel.get('peripheral'),
                    register=sel.get('register'),
                    field=sel.get('field'),
                    element_type=sel.get('element_type')
                )
                # 在树中选中对应项
                if sel.get('peripheral'):
                    self.peripheral_manager.select_peripheral(sel['peripheral'])
                    if sel.get('register'):
                        self.peripheral_manager.select_register(sel['peripheral'], sel['register'])

            # 恢复标签页索引
            tab_widget = self.layout_manager.get_widget('tab_widget')
            if tab_widget and doc.current_tab_index < tab_widget.count():
                tab_widget.setCurrentIndex(doc.current_tab_index)

            # 恢复中断表滚动位置
            irq_table = self.layout_manager.get_widget('irq_table')
            if irq_table:
                irq_table.verticalScrollBar().setValue(doc.irq_table_scroll)

            # 批量更新UI（只刷新一次）
            self.update_data_stats()
            self._update_interrupt_table()
            if hasattr(self.layout_manager, 'update_basic_info'):
                self.layout_manager.update_basic_info(doc.device_info)

            self.update_visualization(
                (doc.selection or {}).get('peripheral') or '',
                (doc.selection or {}).get('register') or '',
                (doc.selection or {}).get('field') or ''
            )

            # 恢复预览器状态（折叠状态和选中状态）
            if self.preview_manager and self.preview_manager.preview_widget:
                pw = self.preview_manager.preview_widget
                # 恢复折叠状态
                pw.folded_elements = set(doc.preview_folded_elements)
                # 恢复选中状态
                if hasattr(pw, 'current_selection'):
                    pw.current_selection = dict(doc.preview_selection)
                # 清除预览高亮，避免残留
                if hasattr(pw, 'preview_edit') and pw.preview_edit:
                    pw.preview_edit.clear_highlight()
                # 刷新预览内容（使用新文档的数据）
                pw.refresh_preview(immediate=True)
                # 如果有选中状态，重新应用高亮
                if doc.preview_selection.get('type') and hasattr(pw, '_apply_highlight'):
                    pw._apply_highlight()
                    pw.jump_to_selection()
        finally:
            # 恢复通知前，标记跳过下一次树重建（避免 resume_notifications 触发的
            # on_state_changed 再次重建树——我们在上面已经重建过了）
            self.peripheral_manager._skip_next_tree_rebuild = True
            self.state_manager.resume_notifications()

        # 重新应用树选中状态
        if doc and doc.selection:
            sel = doc.selection
            periph = sel.get('peripheral')
            reg = sel.get('register')
            if periph:
                if reg:
                    self.peripheral_manager.select_register(periph, reg)
                else:
                    self.peripheral_manager.select_peripheral(periph)

    def _on_document_tab_clicked(self, doc_id: str):
        """文档标签点击 - 切换文档（保存旧状态，恢复新状态）"""
        # 如果点击的是当前活动文档，且没有在对比视图中，忽略
        if doc_id == self.document_manager.active_doc_id and self._active_diff_id is None:
            return

        # 保存当前文档状态
        self._save_current_document_state()

        # 清除活动diff ID（切换到文档模式）
        self._active_diff_id = None

        # 切换文档
        self.document_manager.switch_to(doc_id)
        doc = self.document_manager.get_document(doc_id)
        if doc:
            self._restore_document_state(doc)

        # 确保editor_stack显示正常编辑器（页面0）
        editor_stack = self.layout_manager.get_widget('editor_stack')
        if editor_stack:
            editor_stack.setCurrentIndex(0)

    def _on_document_tab_close(self, doc_id: str):
        """文档标签关闭请求"""
        doc = self.document_manager.get_document(doc_id)
        if doc and doc.modified:
            reply = QMessageBox.question(self, t("msg.close_doc_title"),
                t("msg.close_doc_confirm", name=doc.display_name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.document_manager.close_document(doc_id)

    def _on_close_others(self, keep_doc_id: str):
        """关闭其他文档"""
        # 先保存当前文档状态
        self._save_current_document_state()

        for doc_id in self.document_manager.document_ids[:]:
            if doc_id != keep_doc_id:
                self.document_manager.close_document(doc_id)

        # 确保留下的文档被激活并恢复其状态
        doc = self.document_manager.get_document(keep_doc_id)
        if doc:
            if self.document_manager.active_doc_id != keep_doc_id:
                self.document_manager.switch_to(keep_doc_id)
            self._restore_document_state(doc)

    def _on_close_all(self):
        """关闭所有文档"""
        # 保存当前文档状态
        self._save_current_document_state()
        self.document_manager.clear_all()

    def _on_all_documents_closed_show_welcome(self):
        """所有文档关闭时，切换回欢迎页"""
        # 重置状态管理器的数据为空
        if hasattr(self, 'state_manager'):
            self.state_manager.device_info = DeviceInfo()
            self.state_manager.clear_selection()
        # 切换到欢迎页
        self.layout_manager.show_welcome()
        self.layout_manager.update_status(t("status.all_docs_closed"))
