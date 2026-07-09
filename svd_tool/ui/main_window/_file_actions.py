import os
from PyQt6.QtWidgets import QApplication, QMessageBox, QFileDialog
from PyQt6.QtCore import QEventLoop
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from ...core.svd_parser import SVDParser
from ...core.svd_generator import SVDGenerator
from ...core.svd_loader_worker import SVDLoaderWorker
from ...utils.helpers import pretty_xml
from ...i18n.i18n import t


class FileActionsMixin:
    """文件操作"""

    def _accept_svd_drop(self, event) -> bool:
        """判断拖拽事件是否含 SVD/XML 文件。供 dragEnterEvent/dragMoveEvent 复用。"""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    if url.toLocalFile().lower().endswith(('.svd', '.xml')):
                        return True
        return False

    def dragEnterEvent(self, event: QDragEnterEvent):
        """主窗口级拖拽进入：接受 SVD/XML 文件（欢迎页之外也能拖拽打开，Bug 修复）。

        注意：device_tree_view 自己 setAcceptDrops 处理外设重排序，树上的拖拽由它
        自身消费、不冒泡到主窗口；其余区域（编辑器空白、标签栏、预览等）的事件冒泡
        到这里，统一走文件打开。
        """
        if self._accept_svd_drop(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """拖拽移动：保持接受状态（某些平台 dropEvent 需要 dragMoveEvent 接受才触发）。"""
        if self._accept_svd_drop(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        """拖拽放下：收集所有 SVD/XML 文件路径，走统一后台解析入口。"""
        file_paths = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                path = url.toLocalFile()
                if path.lower().endswith(('.svd', '.xml')):
                    file_paths.append(path)
        if file_paths:
            event.acceptProposedAction()
            self._on_files_dropped(file_paths)
        else:
            event.ignore()

    def open_svd_file(self):
        """打开SVD文件（支持多选）。

        重构后：解析在 QThreadPool 后台线程并发执行，主线程只做轻量装配，
        避免多文档打开时 GUI 线程被阻塞导致卡顿。
        """
        if not self.check_unsaved_changes():
            return
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, t("msg.svd_select_file"), "", t("msg.svd_file_filter")
        )
        if file_paths:
            self._open_files_async(file_paths)

    def _open_files_async(self, file_paths: list):
        """并发解析并装配多个 SVD 文件（对话框 + 拖拽共用入口）。

        解析在后台线程，装配在主线程信号槽（天然串行，避免数据竞争）。
        去重：已打开的文件不再重新解析，而是切回其文档（保留未保存编辑）。
        警告：所有文件解析完后汇总弹一次（而非每文件弹一次）。
        """
        paths = [p for p in file_paths if p]
        if not paths:
            return

        # 先切到编辑器视图并给进度提示（UI 保持响应）
        self.layout_manager.show_editor()
        if len(paths) > 1:
            self.layout_manager.update_status(
                t("status.files_parsing", count=len(paths),
                  default="正在后台解析 {count} 个文件…"))
        else:
            self.layout_manager.update_status(
                t("status.file_parsing", name=os.path.basename(paths[0])))

        # 收集本轮所有文件的警告，待全部完成后汇总弹一次
        collected_warnings = []  # [(file_basename, [warnings])]

        worker = SVDLoaderWorker(parent=self)

        def _on_parsed(file_path, device_info, warnings):
            try:
                self._assemble_loaded_document(file_path, device_info)
            except Exception as e:
                self.logger.error(f"装配文件失败: {file_path} - {e}", exc_info=True)
                QMessageBox.critical(
                    self, t("msg.load_error"),
                    t("msg.file_load_failed_detail", error=str(e)))
            if warnings:
                collected_warnings.append((os.path.basename(file_path), list(warnings)))
            worker._mark_one_done()

        def _on_failed(file_path, error_msg):
            self.logger.error(f"后台解析失败: {file_path} - {error_msg}")
            QMessageBox.critical(
                self, t("msg.load_error"),
                t("msg.file_load_failed_detail", error=error_msg))
            worker._mark_one_done()

        def _on_all_done():
            # 汇总警告弹一次
            if collected_warnings:
                lines = []
                total = 0
                for name, ws in collected_warnings:
                    total += len(ws)
                    sample = ws[:5]
                    lines.append(f"[{name}] ({len(ws)}): " + " | ".join(sample))
                    if len(ws) > 5:
                        lines.append(f"  …还有 {len(ws) - 5} 条")
                QMessageBox.warning(
                    self, t("msg.parse_warning"),
                    t("msg.parse_warnings_summary", total=total,
                      default="共 {total} 条解析警告：\n\n") + "\n".join(lines))

        worker.parsed.connect(_on_parsed)
        worker.failed.connect(_on_failed)
        worker.all_done.connect(_on_all_done)

        # 保留引用防止被 GC（槽闭包期间 worker 须存活）
        self._active_loaders = getattr(self, "_active_loaders", [])
        self._active_loaders.append(worker)

        def _cleanup():
            try:
                self._active_loaders.remove(worker)
            except (ValueError, AttributeError):
                pass
        worker.all_done.connect(_cleanup)

        worker.load_files(paths)

    def _assemble_loaded_document(self, file_path: str, device_info):
        """在主线程装配一个已解析好的 device_info 到编辑器（去重 + 注册文档）。

        与旧同步路径逻辑等价：先保存当前文档状态、去重检查、暂停通知更新
        state_manager + 重建树 + 中断表、注册文档并切换 active、加入最近文件。
        """
        # 先保存当前文档状态（确保数据隔离）
        self._save_current_document_state()

        # 去重：已打开则切回，绝不用新解析数据覆盖（保留未保存编辑）
        existing_doc_id = self.document_manager.find_by_file_path(file_path) \
            if hasattr(self.document_manager, 'find_by_file_path') else None
        if existing_doc_id:
            self.document_manager.switch_to(existing_doc_id)
            existing_doc = self.document_manager.get_document(existing_doc_id)
            if existing_doc:
                self._restore_document_state(existing_doc)
            self.layout_manager.update_status(
                t("status.file_loaded", name=os.path.basename(file_path)))
            self.layout_manager.add_recent_file(file_path)
            return

        # 达文档上限时必须先拒绝，绝不能先改 state_manager 再让 open_document 抛异常——
        # 否则第 21 个文件的数据会写进当前活动文档(state_manager.device_info 已被赋值)，
        # 但没有新标签页、也没 switch_to，导致 UI 内容与标签错位（Bug 修复）。
        max_docs = getattr(self.document_manager, "_max_documents", 20)
        if len(self.document_manager._documents) >= max_docs:
            QMessageBox.warning(
                self, t("message.warning"),
                t("msg.max_documents_reached", max=max_docs,
                  default="已达到最大文档数限制({max})，无法打开更多文件。\n请先关闭部分文档。"))
            self.layout_manager.update_status(
                t("status.file_loaded", name=os.path.basename(file_path)))
            self.layout_manager.add_recent_file(file_path)
            return

        # 暂停通知，防止旧文档的树展开状态泄漏到新文档
        self.state_manager.pause_notifications()
        try:
            self.state_manager.device_info = device_info
            self.state_manager.clear_selection()
            self.state_manager.command_history.clear()

            # 重置预览器状态（新文件不应继承旧文件的选中/折叠状态）
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
            self.state_manager.resume_notifications()

        # 发射文件加载信号（触发实时预览刷新）
        if hasattr(self, 'coordinator') and self.coordinator:
            self.coordinator.emit_event("device_info_updated", device_info)

        if hasattr(self.layout_manager, 'update_basic_info'):
            self.layout_manager.update_basic_info(device_info)

        self.layout_manager.update_status(t("status.file_loaded", name=os.path.basename(file_path)))

        # 注册到文档管理器并切换 active
        try:
            new_doc_id = self.document_manager.open_document(device_info, file_path=file_path)
            self.document_manager.switch_to(new_doc_id)
        except Exception as e:
            self.logger.warning(f"注册文档到DocumentManager失败: {e}")

        self.layout_manager.show_editor()
        self.layout_manager.add_recent_file(file_path)


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
            if generator.save_to_file(file_path, style="cmsis"):
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
        """从指定路径加载单个 SVD 文件（最近文件/向导/AI 非静默路径共用）。

        解析在后台线程执行，用本地 QEventLoop 同步等待结果（保持同步调用语义，
        调用方无需改造）。装配复用 _assemble_loaded_document。单文件影响小，
        此处的阻塞等待主要是为了维持旧调用方的同步签名。
        """
        self.layout_manager.update_status(
            t("status.file_parsing", name=os.path.basename(file_path)))

        result_box = {"device_info": None, "error": None}
        loop = QEventLoop()
        worker = SVDLoaderWorker(parent=self)

        def _on_parsed(fp, device_info, warnings):
            result_box["device_info"] = device_info
            result_box["_warnings"] = warnings
            worker._mark_one_done()

        def _on_failed(fp, error_msg):
            result_box["error"] = error_msg
            worker._mark_one_done()

        def _on_all_done():
            loop.quit()

        worker.parsed.connect(_on_parsed)
        worker.failed.connect(_on_failed)
        worker.all_done.connect(_on_all_done)
        self._active_loaders = getattr(self, "_active_loaders", [])
        self._active_loaders.append(worker)

        worker.load_files([file_path])
        loop.exec()  # 阻塞直到 all_done

        if result_box["error"] is not None:
            raise Exception(result_box["error"])
        if result_box["device_info"] is None:
            raise Exception("解析未返回结果")

        device_info = result_box["device_info"]
        self._assemble_loaded_document(file_path, device_info)

        # 最近文件单文件路径也弹警告（与旧行为一致）
        warnings = result_box.get("_warnings") or []
        if warnings:
            warning_msg = "\n".join(warnings[:10])
            if len(warnings) > 10:
                warning_msg += t("msg.more_warnings", count=len(warnings) - 10)
            QMessageBox.warning(self, t("msg.parse_warning"), warning_msg)

    def validate_data(self):
        """验证 SVD 数据（CMSIS-SVD Schema 完整验证）"""
        self.file_operations.validate_svd()

    def _on_files_dropped(self, file_paths: list):
        """处理拖拽打开的文件（欢迎页拖拽多文件）。

        复用 _open_files_async 后台并发解析 + 去重 + 警告汇总，
        不再逐个同步解析（避免卡顿与重复拖拽覆盖未保存编辑）。
        """
        if file_paths:
            self._open_files_async(file_paths)


    def export_document(self, format_type: str = "markdown"):
        """导出文档（CSV/Markdown/HTML）"""
        self.file_operations.export_document(format_type)
