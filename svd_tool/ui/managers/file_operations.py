"""
文件操作管理器
负责处理文件操作（导入、导出、生成等）
"""
import os
import logging
from typing import Optional

from PyQt6.QtWidgets import QFileDialog, QMessageBox, QLabel
from PyQt6.QtCore import QObject, pyqtSignal
from ...i18n.i18n import t

from ...core.svd_parser import SVDParser
from ...core.svd_generator import SVDGenerator
from ...core.svd_schema_validator import SVDSchemaValidator
from ...core.svd_exporter import SVDExporter
from ...utils.helpers import pretty_xml


class FileOperations(QObject):
    """文件操作管理器"""

    # 信号定义
    file_loaded = pyqtSignal(object)  # 文件加载完成
    file_saved = pyqtSignal(str)  # 文件保存完成

    def __init__(self, state_manager, layout_manager):
        """
        初始化文件操作管理器

        Args:
            state_manager: 状态管理器实例
            layout_manager: 布局管理器实例
        """
        super().__init__()
        self.state_manager = state_manager
        self.layout_manager = layout_manager
        self.logger = logging.getLogger("FileOperations")
        self.current_file_path: Optional[str] = None

    def new_file(self):
        """新建文件"""
        # 检查未保存的更改
        if self.check_unsaved_changes():
            # 重置状态
            self.state_manager.reset()
            self.state_manager.command_history.clear()

            # 更新状态
            self.layout_manager.update_status(t("status.new_file_created"))

    def open_svd_file(self):
        """打开SVD文件"""
        # 检查未保存的更改
        if self.check_unsaved_changes():
            file_path, _ = QFileDialog.getOpenFileName(
                self.layout_manager.main_window,
                t("dialog.select_svd"),
                "",
                t("filter.svd_xml")
            )

            if file_path:
                try:
                    self.layout_manager.update_status(t("status.parsing"))
                    from PyQt6.QtWidgets import QApplication
                    QApplication.processEvents()  # 更新UI

                    # 解析文件
                    parser = SVDParser()
                    device_info = parser.parse_file(file_path)

                    # 更新状态管理器
                    self.state_manager.device_info = device_info
                    self.state_manager.clear_selection()
                    self.state_manager.command_history.clear()
                    
                    # 通知状态变化（触发实时预览更新）
                    self.state_manager._notify_state_change()

                    # 更新UI
                    self.logger.debug(f"发射file_loaded信号: {device_info.name if device_info else 'None'}")
                    self.file_loaded.emit(device_info)
                    self.layout_manager.update_status(t("status.loaded", name=os.path.basename(file_path)))

                    # 显示警告
                    if parser.warnings:
                        warning_msg = "\n".join(parser.warnings[:10])
                        if len(parser.warnings) > 10:
                            warning_msg += t("validation.more_warnings", count=len(parser.warnings)-10)
                        QMessageBox.warning(
                            self.layout_manager.main_window,
                            t("msg.parse_warnings"),
                            warning_msg
                        )

                except Exception as e:
                    self.logger.error(f"File load failed: {str(e)}")
                    QMessageBox.critical(
                        self.layout_manager.main_window,
                        t("msg.load_error"),
                        t("msg.load_failed", error=str(e))
                    )

    def save_svd_file(self):
        """保存SVD文件"""
        self.save_svd_file_impl(force_save_as=False)

    def save_svd_file_as(self):
        """另存为SVD文件"""
        self.save_svd_file_impl(force_save_as=True)

    def save_svd_file_impl(self, force_save_as=False):
        """保存SVD文件实现"""
        try:
            # 获取保存路径
            file_path = None
            if not force_save_as and self.current_file_path:
                file_path = self.current_file_path
            else:
                file_path, _ = QFileDialog.getSaveFileName(
                    self.layout_manager.main_window,
                    t("dialog.save_svd"),
                    "",
                    "SVD (*.svd);;All (*.*)"
                )

            if not file_path:
                return

            # 保存前先从UI更新设备信息（包括公司、版权、协议等基本信息）
            self.update_device_info_from_ui()

            # ===== 保存前执行 CMSIS-SVD Schema 验证 =====
            should_save = self._validate_before_save()
            if not should_save:
                return

            # 生成SVD
            generator = SVDGenerator(self.state_manager.device_info, skip_derived_registers=getattr(self.state_manager, 'skip_derived_registers', True))
            svd_xml = generator.generate()

            # 保存文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(svd_xml)

            # 更新状态
            self.current_file_path = file_path
            self.layout_manager.update_status(t("status.saved", path=file_path))
            self.file_saved.emit(file_path)
            QMessageBox.information(
                self.layout_manager.main_window,
                t("msg.save_success"),
                t("msg.save_success_text", path=file_path)
            )

        except Exception as e:
            self.logger.error(f"File save failed: {str(e)}")
            QMessageBox.critical(
                self.layout_manager.main_window,
                t("msg.save_error"),
                t("msg.save_failed", error=str(e))
            )

    def _validate_before_save(self) -> bool:
        """
        保存前执行 CMSIS-SVD Schema 验证
        返回 True 表示可以继续保存，False 表示应中止保存
        """
        validator = SVDSchemaValidator()
        validator.validate_all(self.state_manager.device_info)

        if not validator.has_errors():
            # 没有错误，直接保存（可能有警告，在状态栏提示）
            warnings = validator.get_warnings()
            if warnings:
                self.layout_manager.update_status(
                    t("validation.pass_with_warnings", count=len(warnings))
                )
            else:
                self.layout_manager.update_status(t("validation.pass_saving"))
            return True

        # 有错误，显示验证结果对话框
        result_text = validator.format_results_text(max_items=30)
        summary = validator.get_summary()

        # 询问用户是否继续保存
        msg_box = QMessageBox(self.layout_manager.main_window)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle(t("validation.schema_issues"))
        msg_box.setText(
            t("validation.schema_issues_text",
              errors=summary['errors'], warnings=summary['warnings'])
        )
        msg_box.setDetailedText(result_text)
        save_btn = msg_box.addButton(t("validation.save_anyway"), QMessageBox.ButtonRole.AcceptRole)
        cancel_btn = msg_box.addButton(t("validation.go_back"), QMessageBox.ButtonRole.RejectRole)
        msg_box.setDefaultButton(cancel_btn)

        msg_box.exec()
        return msg_box.clickedButton() == save_btn

    # 地址冲突相关的 Schema 类别，由 AddressConflictDetector 专门处理
    _ADDRESS_CONFLICT_CATEGORIES = {
        "外设地址", "地址重叠", "寄存器偏移", "位域重叠", "中断号重复",
        "Peripheral Address", "Address Overlap", "Register Offset",
        "Field Bit Overlap", "Interrupt Duplicate",
    }

    def validate_svd(self):
        """独立的 SVD 验证功能（菜单触发），去重后显示合并结果（支持多文档）"""
        try:
            # 从UI更新设备信息
            self.update_device_info_from_ui()

            # 检查是否有多个文档
            main_win = self.layout_manager.main_window
            dm = getattr(main_win, 'document_manager', None)
            if dm and dm.document_count > 1:
                self._validate_all_documents(dm)
                return

            # ===== 1. 执行 CMSIS-SVD Schema 验证 =====
            validator = SVDSchemaValidator()
            validator.validate_all(self.state_manager.device_info)

            # 过滤掉地址冲突相关的重复项（由 AddressConflictDetector 专门处理）
            schema_items = [
                r for r in validator.results
                if r.category not in self._ADDRESS_CONFLICT_CATEGORIES
            ]
            schema_errors = sum(1 for r in schema_items if r.severity.value == "error")
            schema_warnings = sum(1 for r in schema_items if r.severity.value == "warning")
            schema_infos = sum(1 for r in schema_items if r.severity.value == "info")

            # ===== 2. 执行地址冲突检测 =====
            conflict_results = []
            main_win = self.layout_manager.main_window
            if hasattr(main_win, 'conflict_detector') and main_win.conflict_detector:
                main_win.conflict_detector.detect_all(self.state_manager.device_info)
                conflict_results = main_win.conflict_detector.conflicts

            conflict_count = len(conflict_results)
            conflict_errors = sum(1 for c in conflict_results if c.severity.value == "error")
            conflict_warnings = sum(1 for c in conflict_results if c.severity.value == "warning")

            # ===== 3. 合并统计 =====
            total_errors = schema_errors + conflict_errors
            total_warnings = schema_warnings + conflict_warnings
            total_infos = schema_infos

            # ===== 4. 构建格式化结果文本 =====
            result_lines = []

            # 4a. 地址冲突检测（放在前面，因为最关键）
            if conflict_results:
                from ...core.address_conflict_detector import ConflictType
                type_map = {
                    ConflictType.PERIPHERAL_ADDRESS_OVERLAP: t("conflict.periph_addr_overlap"),
                    ConflictType.PERIPHERAL_BASE_DUPLICATE: t("conflict.periph_base_dup"),
                    ConflictType.REGISTER_OFFSET_DUPLICATE: t("conflict.reg_offset_dup"),
                    ConflictType.REGISTER_ADDRESS_OVERLAP: t("conflict.reg_addr_overlap"),
                    ConflictType.FIELD_BIT_OVERLAP: t("conflict.field_bit_overlap"),
                    ConflictType.INTERRUPT_VALUE_DUPLICATE: t("conflict.irq_dup"),
                }
                result_lines.append(t("validation.conflict_header", count=conflict_count))
                result_lines.append("-" * 50)
                for i, c in enumerate(conflict_results[:30]):
                    icon = "[ERROR]" if c.severity.value == "error" else "[WARN]"
                    c_type = type_map.get(c.conflict_type, str(c.conflict_type))
                    result_lines.append(f"  {i+1}. {icon} [{c_type}] {c.message}")
                    if c.detail:
                        result_lines.append(f"       -> {c.detail}")
                if len(conflict_results) > 30:
                    result_lines.append(f"  {t('validation.more_conflicts', count=len(conflict_results) - 30)}")

            # 4b. Schema 验证结果（按严重程度分组）
            if schema_items:
                errors = [r for r in schema_items if r.severity.value == "error"]
                warnings = [r for r in schema_items if r.severity.value == "warning"]
                infos = [r for r in schema_items if r.severity.value == "info"]

                if errors:
                    result_lines.append("")
                    result_lines.append(t("validation.schema_errors", count=len(errors)))
                    result_lines.append("-" * 50)
                    for i, item in enumerate(errors[:30]):
                        loc = f" [{item.location}]" if item.location else ""
                        result_lines.append(f"  {i+1}. {item.category}{loc}: {item.message}")
                        if item.suggestion:
                            result_lines.append(f"       {t('validation.suggestion', text=item.suggestion)}")

                if warnings:
                    result_lines.append("")
                    result_lines.append(t("validation.schema_warnings", count=len(warnings)))
                    result_lines.append("-" * 50)
                    for i, item in enumerate(warnings[:20]):
                        loc = f" [{item.location}]" if item.location else ""
                        result_lines.append(f"  {i+1}. {item.category}{loc}: {item.message}")

                if infos:
                    result_lines.append("")
                    result_lines.append(t("validation.schema_infos", count=len(infos)))
                    result_lines.append("-" * 50)
                    for i, item in enumerate(infos[:10]):
                        loc = f" [{item.location}]" if item.location else ""
                        result_lines.append(f"  {i+1}. {item.category}{loc}: {item.message}")
                    if len(infos) > 10:
                        result_lines.append(f"  {t('validation.more_infos', count=len(infos) - 10)}")

            result_text = "\n".join(result_lines)

            # ===== 5. 显示结果 =====
            if total_errors == 0 and total_warnings == 0:
                QMessageBox.information(
                    self.layout_manager.main_window,
                    t("validation.passed_title"),
                    t("validation.passed_text", count=len(schema_items))
                )
            else:
                self._show_validation_result_dialog(
                    total_errors, total_warnings, total_infos,
                    conflict_count, result_text
                )

            status_msg = t("validation.complete_status",
                           errors=total_errors, warnings=total_warnings)
            if conflict_count > 0:
                status_msg += t("validation.with_conflicts", count=conflict_count)
            self.layout_manager.update_status(status_msg)

        except Exception as e:
            self.logger.error(f"Validation failed: {str(e)}")
            QMessageBox.critical(
                self.layout_manager.main_window,
                t("validation.error_title"),
                t("validation.error_text", error=str(e))
            )

    def _validate_all_documents(self, document_manager):
        """验证所有已打开的文档（遍历切换，复用单文档验证逻辑）"""
        from ...core.svd_schema_validator import SVDSchemaValidator
        from ...core.address_conflict_detector import AddressConflictDetector, ConflictType

        main_win = self.layout_manager.main_window

        # 保存当前文档状态
        if hasattr(main_win, '_save_current_document_state'):
            main_win._save_current_document_state()
        original_doc_id = document_manager.active_doc_id

        all_results = []
        total_errors = 0
        total_warnings = 0

        for doc_id, doc in document_manager.get_all_documents().items():
            try:
                # 切换到目标文档，复用现有验证逻辑
                document_manager.switch_to(doc_id)
                if hasattr(main_win, '_restore_document_state'):
                    main_win._restore_document_state(doc)

                validator = SVDSchemaValidator()
                validator.validate_all(doc.device_info)
                schema_items = [r for r in validator.results if r.category not in self._ADDRESS_CONFLICT_CATEGORIES]
                doc_errors = sum(1 for r in schema_items if r.severity.value == "error")
                doc_warnings = sum(1 for r in schema_items if r.severity.value == "warning")

                # 地址冲突检测
                conflict_count = 0
                conflict_details = []
                if hasattr(main_win, 'conflict_detector') and main_win.conflict_detector:
                    detector = AddressConflictDetector()
                    conflicts = detector.detect_all(doc.device_info)
                    conflict_count = len(conflicts)
                    doc_errors += sum(1 for c in conflicts if c.severity.value == "error")
                    for c in conflicts[:10]:
                        icon = "ERROR" if c.severity.value == "error" else "WARN"
                        conflict_details.append(f"  [{icon}] {c.message}" + (f" -> {c.detail}" if c.detail else ""))

                # 构建该文档的详情文本
                detail_lines = []
                errors = [r for r in schema_items if r.severity.value == "error"]
                warnings = [r for r in schema_items if r.severity.value == "warning"]
                for r in errors[:15]:
                    loc = f" [{r.location}]" if r.location else ""
                    detail_lines.append(f"  [ERROR] {r.category}{loc}: {r.message}")
                    if r.suggestion:
                        detail_lines.append(f"          -> 建议: {r.suggestion}")
                for r in warnings[:10]:
                    loc = f" [{r.location}]" if r.location else ""
                    detail_lines.append(f"  [WARN]  {r.category}{loc}: {r.message}")
                if conflict_details:
                    detail_lines.append(f"  [{t('conflict.periph_addr_overlap')}] ({conflict_count})")
                    detail_lines.extend(conflict_details)
                if len(errors) > 15:
                    detail_lines.append(f"  ... {len(errors) - 15} more errors")

                total_errors += doc_errors
                total_warnings += doc_warnings
                all_results.append({
                    "name": doc.display_name, "errors": doc_errors, "warnings": doc_warnings,
                    "conflicts": conflict_count, "detail": "\n".join(detail_lines),
                })
            except Exception as e:
                all_results.append({"name": doc.display_name, "errors": 1, "warnings": 0, "conflicts": 0, "detail": f"  {t('validation.doc_error', error=str(e))}"})
                total_errors += 1

        # 切回原文档
        if original_doc_id and original_doc_id in document_manager.get_all_documents():
            document_manager.switch_to(original_doc_id)
            original_doc = document_manager.get_document(original_doc_id)
            if original_doc and hasattr(main_win, '_restore_document_state'):
                main_win._restore_document_state(original_doc)

        # 构建汇总结果
        result_lines = [t("validation.multi_doc_result", count=len(all_results)), "=" * 60]
        for r in all_results:
            icon = "PASS" if r["errors"] == 0 else "FAIL"
            line = f"\n[{icon}] {t('validation.doc_summary', name=r['name'], errors=r['errors'], warnings=r['warnings'])}"
            if r["conflicts"] > 0:
                line += t("validation.doc_conflicts", count=r['conflicts'])
            result_lines.append(line)
            result_lines.append("-" * 50)
            if r["detail"]:
                result_lines.append(r["detail"])
            elif r["errors"] == 0:
                result_lines.append(t("validation.doc_pass"))

        result_text = "\n".join(result_lines)

        if total_errors == 0 and total_warnings == 0:
            QMessageBox.information(main_win, t("validation.multi_doc_passed"),
                                    t("validation.multi_doc_passed_text", count=len(all_results)))
        else:
            self._show_validation_result_dialog(total_errors, total_warnings, 0, 0, result_text)

        self.layout_manager.update_status(t("validation.multi_doc_status", errors=total_errors, warnings=total_warnings))

    def _show_validation_result_dialog(self, errors, warnings, infos,
                                        conflict_count, detail_text):
        """显示验证结果汇总对话框"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox

        dialog = QDialog(self.layout_manager.main_window)
        dialog.setWindowTitle(t("validation.result_title"))
        dialog.setMinimumSize(640, 480)
        dialog.resize(720, 560)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(8)

        # 摘要标签
        summary_parts = []
        if errors > 0:
            summary_parts.append(t("validation.n_errors", count=errors))
        if warnings > 0:
            summary_parts.append(t("validation.n_warnings", count=warnings))
        if infos > 0:
            summary_parts.append(t("validation.n_infos", count=infos))
        if conflict_count > 0:
            summary_parts.append(t("validation.n_conflicts", count=conflict_count))

        summary_label = QLabel(
            t("validation.result_summary", summary="，".join(summary_parts))
        )
        summary_label.setWordWrap(True)
        layout.addWidget(summary_label)

        # 详细结果文本
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(detail_text)
        text_edit.setFontFamily("Consolas, Microsoft YaHei, monospace")
        layout.addWidget(text_edit)

        # 按钮
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn_box.button(QDialogButtonBox.StandardButton.Ok).setText(t("button.ok"))
        btn_box.accepted.connect(dialog.accept)
        layout.addWidget(btn_box)

        dialog.exec()

    def check_unsaved_changes(self) -> bool:
        """检查未保存的更改"""
        # 这里可以添加检查逻辑
        # 暂时返回True表示可以继续
        return True

    def preview_xml(self):
        """预览XML"""
        self.logger.debug("preview_xml 被调用")
        try:
            # 首先从UI更新设备信息
            self.update_device_info_from_ui()
            self.logger.debug("update_device_info_from_ui 完成")
 
            generator = SVDGenerator(self.state_manager.device_info, skip_derived_registers=getattr(self.state_manager, 'skip_derived_registers', True))
            svd_xml = generator.generate()
            self.logger.debug(f"SVD生成完成，长度={len(svd_xml)}")
 
            # 使用预览管理器刷新预览
            preview_manager = self.layout_manager.main_window.preview_manager
            if preview_manager:
                self.logger.debug("调用 preview_manager.refresh_preview(immediate=True)")
                preview_manager.refresh_preview(immediate=True)
            else:
                self.logger.debug("preview_manager 为 None")
 
            self.logger.info("XML预览生成成功")
 
        except Exception as e:
            self.logger.error(f"XML预览失败: {str(e)}")
            self.logger.exception("预览失败")
            QMessageBox.critical(
                self.layout_manager.main_window,
                t("msg.preview_error"),
                t("msg.preview_failed", error=str(e))
            )

    def export_file(self):
        """导出文件 — 支持多种格式"""
        try:
            file_path, selected_filter = QFileDialog.getSaveFileName(
                self.layout_manager.main_window,
                t("dialog.export_file"),
                "",
                "SVD (*.svd);;CSV Detail (*.csv);;CSV Summary (*.csv);;"
                "Markdown (*.md);;HTML (*.html);;All (*.*)"
            )

            if not file_path:
                return

            # 从UI更新设备信息
            self.update_device_info_from_ui()

            exporter = SVDExporter(self.state_manager.device_info)
            success = False

            if selected_filter.startswith("CSV 寄存器详情") or file_path.endswith("_detail.csv"):
                success = exporter.export_csv(file_path)
            elif selected_filter.startswith("CSV 寄存器汇总") or file_path.endswith("_summary.csv"):
                success = exporter.export_register_summary_csv(file_path)
            elif selected_filter.startswith("Markdown") or file_path.endswith(".md"):
                success = exporter.export_markdown(file_path)
            elif selected_filter.startswith("HTML") or file_path.endswith(".html"):
                success = exporter.export_html(file_path)
            else:
                # 默认 SVD 格式
                generator = SVDGenerator(self.state_manager.device_info, skip_derived_registers=getattr(self.state_manager, 'skip_derived_registers', True))
                svd_xml = generator.generate()
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(svd_xml)
                success = True

            if success:
                self.logger.info(f"File exported: {file_path}")
                self.layout_manager.update_status(t("msg.export_success"))
                QMessageBox.information(
                    self.layout_manager.main_window,
                    t("msg.export_success"),
                    t("msg.export_success_text", path=file_path)
                )
            else:
                QMessageBox.warning(
                    self.layout_manager.main_window,
                    t("msg.export_error"),
                    t("msg.export_failed")
                )

        except Exception as e:
            self.logger.error(f"File export failed: {str(e)}")
            QMessageBox.critical(
                self.layout_manager.main_window,
                t("msg.export_error"),
                t("msg.export_error_text", error=str(e))
            )

    def export_document(self, format_type: str = "markdown"):
        """
        快捷导出文档

        Args:
            format_type: "csv", "csv_summary", "markdown", "html"
        """
        try:
            self.update_device_info_from_ui()

            ext_map = {
                "csv": ("CSV 寄存器详情", "CSV文件 (*.csv)", ".csv"),
                "csv_summary": ("CSV 寄存器汇总", "CSV文件 (*.csv)", "_summary.csv"),
                "markdown": ("Markdown 文档", "Markdown文件 (*.md)", ".md"),
                "html": ("HTML 文档", "HTML文件 (*.html)", ".html"),
            }
            info = ext_map.get(format_type, ext_map["markdown"])
            default_name = (self.state_manager.device_info.name or "device") + info[2]

            file_path, _ = QFileDialog.getSaveFileName(
                self.layout_manager.main_window,
                f"导出{info[0]}",
                default_name,
                info[1]
            )

            if not file_path:
                return

            exporter = SVDExporter(self.state_manager.device_info)

            if format_type == "csv":
                success = exporter.export_csv(file_path)
            elif format_type == "csv_summary":
                success = exporter.export_register_summary_csv(file_path)
            elif format_type == "html":
                success = exporter.export_html(file_path)
            else:
                success = exporter.export_markdown(file_path)

            if success:
                self.layout_manager.update_status(f"{info[0]}导出成功")
                QMessageBox.information(
                    self.layout_manager.main_window,
                    "导出成功",
                    f"{info[0]}已导出到:\n{file_path}"
                )
            else:
                QMessageBox.warning(
                    self.layout_manager.main_window, "导出失败", "导出失败，请检查日志。"
                )

        except Exception as e:
            self.logger.error(f"文档导出失败: {e}")
            QMessageBox.critical(
                self.layout_manager.main_window, "导出错误", f"导出失败: {e}"
            )

    def update_device_info_from_ui(self):
        """从UI更新设备信息"""
        # 获取基础信息标签页的控件
        ic_name_edit = self.layout_manager.get_widget('ic_name_edit')
        ic_desc_edit = self.layout_manager.get_widget('ic_desc_edit')
        version_edit = self.layout_manager.get_widget('version_edit')
        svd_version_combo = self.layout_manager.get_widget('svd_version_combo')
        cpu_name_edit = self.layout_manager.get_widget('cpu_name_edit')
        cpu_rev_edit = self.layout_manager.get_widget('cpu_rev_edit')
        endian_combo = self.layout_manager.get_widget('endian_combo')
        mpu_combo = self.layout_manager.get_widget('mpu_combo')
        fpu_combo = self.layout_manager.get_widget('fpu_combo')
        nvic_prio_spin = self.layout_manager.get_widget('nvic_prio_spin')
        company_name_edit = self.layout_manager.get_widget('company_name_edit')
        company_checkbox = self.layout_manager.get_widget('company_checkbox')
        copyright_edit = self.layout_manager.get_widget('copyright_edit')
        copyright_checkbox = self.layout_manager.get_widget('copyright_checkbox')
        author_edit = self.layout_manager.get_widget('author_edit')
        license_combo = self.layout_manager.get_widget('license_combo')

        # 更新设备信息
        if ic_name_edit:
            self.state_manager.device_info.name = ic_name_edit.text()
        if ic_desc_edit:
            self.state_manager.device_info.description = ic_desc_edit.text()
        if version_edit:
            self.state_manager.device_info.version = version_edit.text()
        if svd_version_combo:
            self.state_manager.device_info.svd_version = svd_version_combo.currentText()
        if cpu_name_edit:
            self.state_manager.device_info.cpu.name = cpu_name_edit.text()
        if cpu_rev_edit:
            self.state_manager.device_info.cpu.revision = cpu_rev_edit.text()
        if endian_combo:
            self.state_manager.device_info.cpu.endian = endian_combo.currentText()
        if mpu_combo:
            self.state_manager.device_info.cpu.mpu_present = mpu_combo.isChecked()
        if fpu_combo:
            self.state_manager.device_info.cpu.fpu_present = fpu_combo.isChecked()
        if nvic_prio_spin:
            self.state_manager.device_info.cpu.nvic_prio_bits = nvic_prio_spin.value()
        if company_name_edit:
            self.state_manager.device_info.vendor = company_name_edit.text().strip()
        if copyright_edit:
            self.state_manager.device_info.copyright = copyright_edit.text().strip()
        if author_edit:
            self.state_manager.device_info.author = author_edit.text().strip()
        if license_combo:
            license_text = license_combo.currentText()
            if license_text != "不显示":
                self.state_manager.device_info.license = license_text
            else:
                self.state_manager.device_info.license = ""
