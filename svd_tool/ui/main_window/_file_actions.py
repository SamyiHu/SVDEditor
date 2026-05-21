import os
from PyQt6.QtWidgets import QApplication, QMessageBox, QFileDialog
from ...core.svd_parser import SVDParser
from ...core.svd_generator import SVDGenerator
from ...utils.helpers import pretty_xml
from ...i18n.i18n import t


class FileActionsMixin:
    """文件操作"""

    def open_svd_file(self):
        """打开SVD文件（支持多选）"""
        # 检查未保存的更改
        if self.check_unsaved_changes():
            file_paths, _ = QFileDialog.getOpenFileNames(
                self, t("msg.svd_select_file"), "", t("msg.svd_file_filter")
            )

            if file_paths:
                for file_path in file_paths:
                    try:
                        # 先保存当前文档状态（确保数据隔离）
                        self._save_current_document_state()

                        self.layout_manager.update_status(t("status.file_parsing", name=os.path.basename(file_path)))
                        QApplication.processEvents()  # 更新UI

                        # 解析文件
                        parser = SVDParser()
                        device_info = parser.parse_file(file_path)

                        # 暂停通知，防止旧文档的树展开状态泄漏到新文档
                        self.state_manager.pause_notifications()

                        try:
                            # 更新状态管理器
                            self.state_manager.device_info = device_info
                            self.state_manager.clear_selection()
                            self.state_manager.command_history.clear()

                            # 重置预览器状态（新打开的文件不应该继承旧文件的选中/折叠状态）
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

                        # 发射文件加载信号（触发实时预览刷新）
                        if hasattr(self, 'coordinator') and self.coordinator:
                            self.logger.debug("调用coordinator.emit_event(device_info_updated)")
                            self.coordinator.emit_event("device_info_updated", device_info)

                        # 更新基础信息
                        if hasattr(self.layout_manager, 'update_basic_info'):
                            self.layout_manager.update_basic_info(device_info)

                        self.layout_manager.update_status(t("status.file_loaded", name=os.path.basename(file_path)))

                        # 注册到文档管理器
                        try:
                            self.document_manager.open_document(
                                device_info, file_path=file_path)
                        except Exception as e:
                            self.logger.warning(f"注册文档到DocumentManager失败: {e}")

                        # 切换到编辑器视图
                        self.layout_manager.show_editor()
                        self.layout_manager.add_recent_file(file_path)

                        # 显示警告
                        if parser.warnings:
                            warning_msg = "\n".join(parser.warnings[:10])
                            if len(parser.warnings) > 10:
                                warning_msg += t("msg.more_warnings", count=len(parser.warnings)-10)
                            QMessageBox.warning(self, t("msg.parse_warning"), warning_msg)

                    except Exception as e:
                        self.logger.error(f"文件加载失败: {str(e)}")
                        QMessageBox.critical(self, t("msg.load_error"), t("msg.file_load_failed_detail", error=str(e)))

                # 多文件加载完成后更新状态
                if len(file_paths) > 1:
                    self.layout_manager.update_status(t("status.files_loaded", count=len(file_paths)))

    def save_svd_file(self):
        """保存SVD文件（多文档时保存全部）"""
        if hasattr(self, 'document_manager') and self.document_manager and self.document_manager.document_count > 1:
            self.save_all_documents()
        else:
            self.save_svd_file_impl(force_save_as=False)

    def save_all_documents(self):
        """保存所有已修改的文档"""
        if not hasattr(self, 'document_manager') or not self.document_manager:
            self.save_svd_file_impl(force_save_as=False)
            return

        dm = self.document_manager
        # 先保存当前文档的 UI 状态
        self._save_current_document_state()
        self.update_device_info_from_ui()

        saved_count = 0
        failed_count = 0
        no_path_docs = []

        for doc_id, doc in dm.get_all_documents().items():
            if not doc.file_path:
                no_path_docs.append(doc)
                continue
            try:
                generator = SVDGenerator(doc.device_info, skip_derived_registers=self.skip_derived_registers)
                svd_xml = generator.generate()
                with open(doc.file_path, 'w', encoding='utf-8') as f:
                    f.write(svd_xml)
                dm.save_document(doc_id)
                saved_count += 1
            except Exception as e:
                self.logger.error(f"保存文档 {doc.display_name} 失败: {e}")
                failed_count += 1

        # 未保存过的新文档逐个弹窗让用户选路径
        for doc in no_path_docs:
            file_path, _ = QFileDialog.getSaveFileName(
                self, f"保存 {doc.display_name}", "",
                "SVD文件 (*.svd);;所有文件 (*.*)"
            )
            if file_path:
                try:
                    generator = SVDGenerator(doc.device_info, skip_derived_registers=self.skip_derived_registers)
                    svd_xml = generator.generate()
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(svd_xml)
                    dm.save_document(doc.doc_id, file_path=file_path)
                    saved_count += 1
                except Exception as e:
                    self.logger.error(f"保存文档 {doc.display_name} 失败: {e}")
                    failed_count += 1
            else:
                failed_count += 1

        self.layout_manager.update_status(f"批量保存完成: {saved_count} 成功" + (f", {failed_count} 失败" if failed_count else ""))
        if failed_count:
            QMessageBox.warning(self, t("msg.save_error"), f"{failed_count} 个文档保存失败")
        elif saved_count:
            QMessageBox.information(self, t("msg.save_success"), f"已保存 {saved_count} 个文档")

    def save_svd_file_as(self):
        """另存为SVD文件"""
        self.save_svd_file_impl(force_save_as=True)

    def save_svd_file_impl(self, force_save_as=False):
        """保存SVD文件实现（支持多文档）"""
        try:
            # 从 DocumentManager 获取当前文档的保存路径
            file_path = None
            active_doc = None
            if hasattr(self, 'document_manager') and self.document_manager:
                active_doc = self.document_manager.active_document

            if not force_save_as:
                # 优先使用当前文档的路径
                if active_doc and active_doc.file_path:
                    file_path = active_doc.file_path
                elif hasattr(self, 'current_file_path') and self.current_file_path:
                    file_path = self.current_file_path

            if not file_path:
                file_path, _ = QFileDialog.getSaveFileName(
                    self, "保存SVD文件", "", "SVD文件 (*.svd);;所有文件 (*.*)"
                )

            if not file_path:
                return

            # 保存前先从UI更新设备信息（包括公司、版权、协议等基本信息）
            self.update_device_info_from_ui()

            # 生成SVD
            generator = SVDGenerator(self.state_manager.device_info, skip_derived_registers=self.skip_derived_registers)
            svd_xml = generator.generate()

            # 保存文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(svd_xml)

            # 更新 DocumentManager 中的文档状态
            if active_doc:
                self.document_manager.save_document(active_doc.doc_id, file_path=file_path)

            # 更新兼容性字段
            self.current_file_path = file_path
            self.layout_manager.update_status(t("status.svd_saved", path=file_path))
            QMessageBox.information(self, t("msg.save_success"), t("msg.svd_file_saved", path=file_path))

        except Exception as e:
            self.logger.error(f"文件保存失败: {str(e)}")
            QMessageBox.critical(self, t("msg.save_error"), t("msg.file_save_failed_detail", error=str(e)))

    def check_unsaved_changes(self) -> bool:
        """检查未保存的更改"""
        # 这里可以添加检查逻辑
        # 暂时返回True表示可以继续
        return True

    def generate_svd(self):
        """生成SVD文件"""
        try:
            # 首先从UI更新设备信息
            self.update_device_info_from_ui()

            # 验证数据
            errors = self.state_manager.validate_device_info()
            if errors:
                QMessageBox.warning(self, t("msg.validation_error"), "\n".join(errors))
                return

            # 生成SVD
            generator = SVDGenerator(self.state_manager.device_info, skip_derived_registers=self.skip_derived_registers)
            svd_xml = generator.generate()

            # 更新预览
            preview_edit = self.layout_manager.get_widget('preview_edit')
            if preview_edit:
                preview_edit.setPlainText(pretty_xml(svd_xml))

            self.logger.info("SVD生成成功")
            self.layout_manager.update_status(t("status.svd_generated"))

        except Exception as e:
            self.logger.error(f"SVD生成失败: {str(e)}")
            QMessageBox.critical(self, t("msg.generate_error"), t("msg.svd_generate_failed", error=str(e)))

    def preview_xml(self):
        """预览XML"""
        try:
            # 首先从UI更新设备信息
            self.update_device_info_from_ui()

            generator = SVDGenerator(self.state_manager.device_info, skip_derived_registers=self.skip_derived_registers)
            svd_xml = generator.generate()

            preview_edit = self.layout_manager.get_widget('preview_edit')
            if preview_edit:
                preview_edit.setPlainText(pretty_xml(svd_xml))

            self.logger.info("XML预览生成成功")

        except Exception as e:
            self.logger.error(f"XML预览失败: {str(e)}")
            QMessageBox.critical(self, t("msg.preview_error"), t("msg.xml_preview_failed", error=str(e)))

    def export_file(self):
        """导出文件"""
        try:
            # 获取保存路径
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存SVD文件", "", "SVD文件 (*.svd);;所有文件 (*.*)"
            )

            if not file_path:
                return

            # 首先从UI更新设备信息
            self.update_device_info_from_ui()

            # 生成SVD
            generator = SVDGenerator(self.state_manager.device_info, skip_derived_registers=self.skip_derived_registers)
            svd_xml = generator.generate()

            # 保存文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(svd_xml)

            self.logger.info(f"SVD文件已保存: {file_path}")
            QMessageBox.information(self, t("msg.save_success"), t("msg.svd_file_saved", path=file_path))

        except Exception as e:
            self.logger.error(f"文件保存失败: {str(e)}")
            QMessageBox.critical(self, t("msg.save_error"), t("msg.file_save_failed_detail", error=str(e)))

    def export_header_file(self):
        """导出C语言头文件"""
        from ...core.header_generator import HeaderGenerator

        if not self.state_manager.device_info or not self.state_manager.device_info.peripherals:
            QMessageBox.warning(self, t("message.info"), t("msg.load_svd_first"))
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, t("msg.export_header_title"),
            f"{self.state_manager.device_info.name or 'device'}.h",
            t("msg.export_header_filter")
        )

        if file_path:
            generator = HeaderGenerator(self.state_manager.device_info)
            if generator.save_to_file(file_path):
                QMessageBox.information(self, t("msg.export_success"), t("msg.export_header_saved", path=file_path))
                self.layout_manager.update_status(t("status.header_exported", path=file_path))
            else:
                QMessageBox.critical(self, t("msg.export_failed"), t("msg.header_gen_failed"))

    def _open_recent_file(self, file_path: str):
        """从欢迎页打开最近文件"""
        if os.path.exists(file_path):
            try:
                self._load_svd_from_path(file_path)
                self.layout_manager.show_editor()
                self.layout_manager.add_recent_file(file_path)
            except Exception as e:
                QMessageBox.critical(self, t("message.error"), t("msg.cannot_open_file", error=str(e)))

    def _load_svd_from_path(self, file_path: str):
        """从指定路径加载SVD文件"""
        # 先保存当前文档状态（确保数据隔离）
        self._save_current_document_state()

        parser = SVDParser()
        device_info = parser.parse_file(file_path)

        # 暂停通知，防止旧文档的树展开状态泄漏到新文档
        self.state_manager.pause_notifications()

        try:
            self.state_manager.device_info = device_info
            self.state_manager.clear_selection()
            self.state_manager.command_history.clear()

            # 重置预览器状态（新打开的文件不应该继承旧文件的选中/折叠状态）
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

        # 发射文件加载信号（触发实时预览刷新）
        if hasattr(self, 'coordinator') and self.coordinator:
            self.logger.debug("调用coordinator.emit_event(device_info_updated)")
            self.coordinator.emit_event("device_info_updated", device_info)

        if hasattr(self.layout_manager, 'update_basic_info'):
            self.layout_manager.update_basic_info(device_info)
        self.layout_manager.update_status(t("status.file_loaded", name=os.path.basename(file_path)))

        # 注册到文档管理器（创建型号标签页）
        try:
            self.document_manager.open_document(
                device_info, file_path=file_path)
        except Exception as e:
            self.logger.warning(f"注册文档到DocumentManager失败: {e}")

    def validate_data(self):
        """验证 SVD 数据（CMSIS-SVD Schema 完整验证）"""
        self.file_operations.validate_svd()

    def _on_files_dropped(self, file_paths: list):
        """处理拖拽打开的文件"""
        for file_path in file_paths:
            try:
                self._load_svd_from_path(file_path)
                self.layout_manager.show_editor()
                self.layout_manager.add_recent_file(file_path)
            except Exception as e:
                self.logger.error(f"拖拽打开文件失败: {file_path} - {e}")
                QMessageBox.critical(self, t("msg.load_error"), t("msg.file_load_failed_detail", error=str(e)))

    def export_document(self, format_type: str = "markdown"):
        """导出文档（CSV/Markdown/HTML）"""
        self.file_operations.export_document(format_type)
