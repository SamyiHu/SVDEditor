"""
文件操作管理器
负责处理文件操作（导入、导出、生成等）
"""
import os
import logging
from typing import Optional

from PyQt6.QtWidgets import QFileDialog, QMessageBox, QLabel
from PyQt6.QtCore import QObject, pyqtSignal

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
    svd_generated = pyqtSignal(str)  # SVD生成完成

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
            self.layout_manager.update_status("已创建新文件")

    def open_svd_file(self):
        """打开SVD文件"""
        # 检查未保存的更改
        if self.check_unsaved_changes():
            file_path, _ = QFileDialog.getOpenFileName(
                self.layout_manager.main_window,
                "选择SVD文件",
                "",
                "SVD文件 (*.svd);;XML文件 (*.xml)"
            )

            if file_path:
                try:
                    self.layout_manager.update_status("正在解析SVD文件...")
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
                    self.layout_manager.update_status(f"已加载: {os.path.basename(file_path)}")

                    # 显示警告
                    if parser.warnings:
                        warning_msg = "\n".join(parser.warnings[:10])
                        if len(parser.warnings) > 10:
                            warning_msg += f"\n...还有{len(parser.warnings)-10}条警告"
                        QMessageBox.warning(
                            self.layout_manager.main_window,
                            "解析警告",
                            warning_msg
                        )

                except Exception as e:
                    self.logger.error(f"文件加载失败: {str(e)}")
                    QMessageBox.critical(
                        self.layout_manager.main_window,
                        "加载错误",
                        f"文件加载失败: {str(e)}"
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
                    "保存SVD文件",
                    "",
                    "SVD文件 (*.svd);;所有文件 (*.*)"
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
            generator = SVDGenerator(self.state_manager.device_info)
            svd_xml = generator.generate()

            # 保存文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(svd_xml)

            # 更新状态
            self.current_file_path = file_path
            self.layout_manager.update_status(f"SVD文件已保存: {file_path}")
            self.file_saved.emit(file_path)
            QMessageBox.information(
                self.layout_manager.main_window,
                "保存成功",
                f"SVD文件已保存到:\n{file_path}"
            )

        except Exception as e:
            self.logger.error(f"文件保存失败: {str(e)}")
            QMessageBox.critical(
                self.layout_manager.main_window,
                "保存错误",
                f"文件保存失败: {str(e)}"
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
                    f"验证通过（{len(warnings)} 条警告）- 正在保存..."
                )
            else:
                self.layout_manager.update_status("验证通过 - 正在保存...")
            return True

        # 有错误，显示验证结果对话框
        result_text = validator.format_results_text(max_items=30)
        summary = validator.get_summary()

        # 询问用户是否继续保存
        msg_box = QMessageBox(self.layout_manager.main_window)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("SVD 验证发现问题")
        msg_box.setText(
            f"验证发现 {summary['errors']} 个错误和 {summary['warnings']} 个警告。\n"
            f"建议修复错误后再保存，否则下游工具可能解析失败。"
        )
        msg_box.setDetailedText(result_text)
        save_btn = msg_box.addButton("仍然保存", QMessageBox.ButtonRole.AcceptRole)
        cancel_btn = msg_box.addButton("返回修改", QMessageBox.ButtonRole.RejectRole)
        msg_box.setDefaultButton(cancel_btn)

        msg_box.exec()
        return msg_box.clickedButton() == save_btn

    # 地址冲突相关的 Schema 类别，由 AddressConflictDetector 专门处理
    _ADDRESS_CONFLICT_CATEGORIES = {
        "外设地址", "地址重叠", "寄存器偏移", "位域重叠", "中断号重复",
    }

    def validate_svd(self):
        """独立的 SVD 验证功能（菜单触发），去重后显示合并结果"""
        try:
            # 从UI更新设备信息
            self.update_device_info_from_ui()

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
                    ConflictType.PERIPHERAL_ADDRESS_OVERLAP: "外设地址重叠",
                    ConflictType.PERIPHERAL_BASE_DUPLICATE: "外设基地址重复",
                    ConflictType.REGISTER_OFFSET_DUPLICATE: "寄存器偏移重复",
                    ConflictType.REGISTER_ADDRESS_OVERLAP: "寄存器地址重叠",
                    ConflictType.FIELD_BIT_OVERLAP: "位域位重叠",
                    ConflictType.INTERRUPT_VALUE_DUPLICATE: "中断号重复",
                }
                result_lines.append(f"[地址冲突检测] 共 {conflict_count} 个冲突")
                result_lines.append("-" * 50)
                for i, c in enumerate(conflict_results[:30]):
                    icon = "[ERROR]" if c.severity.value == "error" else "[WARN]"
                    c_type = type_map.get(c.conflict_type, str(c.conflict_type))
                    result_lines.append(f"  {i+1}. {icon} [{c_type}] {c.message}")
                    if c.detail:
                        result_lines.append(f"       -> {c.detail}")
                if len(conflict_results) > 30:
                    result_lines.append(f"  ... 还有 {len(conflict_results) - 30} 个冲突")

            # 4b. Schema 验证结果（按严重程度分组）
            if schema_items:
                errors = [r for r in schema_items if r.severity.value == "error"]
                warnings = [r for r in schema_items if r.severity.value == "warning"]
                infos = [r for r in schema_items if r.severity.value == "info"]

                if errors:
                    result_lines.append("")
                    result_lines.append(f"[Schema 错误] 共 {len(errors)} 项")
                    result_lines.append("-" * 50)
                    for i, item in enumerate(errors[:30]):
                        loc = f" [{item.location}]" if item.location else ""
                        result_lines.append(f"  {i+1}. {item.category}{loc}: {item.message}")
                        if item.suggestion:
                            result_lines.append(f"       -> 建议: {item.suggestion}")

                if warnings:
                    result_lines.append("")
                    result_lines.append(f"[Schema 警告] 共 {len(warnings)} 项")
                    result_lines.append("-" * 50)
                    for i, item in enumerate(warnings[:20]):
                        loc = f" [{item.location}]" if item.location else ""
                        result_lines.append(f"  {i+1}. {item.category}{loc}: {item.message}")

                if infos:
                    result_lines.append("")
                    result_lines.append(f"[Schema 信息] 共 {len(infos)} 项")
                    result_lines.append("-" * 50)
                    for i, item in enumerate(infos[:10]):
                        loc = f" [{item.location}]" if item.location else ""
                        result_lines.append(f"  {i+1}. {item.category}{loc}: {item.message}")
                    if len(infos) > 10:
                        result_lines.append(f"  ... 还有 {len(infos) - 10} 条信息")

            result_text = "\n".join(result_lines)

            # ===== 5. 显示结果 =====
            if total_errors == 0 and total_warnings == 0:
                QMessageBox.information(
                    self.layout_manager.main_window,
                    "SVD 验证通过",
                    "验证通过，未发现任何问题。\n\n"
                    f"已检查 Schema 验证规则 {len(schema_items)} 项。\n"
                    f"已检查地址冲突检测（0 个冲突）。"
                )
            else:
                self._show_validation_result_dialog(
                    total_errors, total_warnings, total_infos,
                    conflict_count, result_text
                )

            self.layout_manager.update_status(
                f"验证完成: {total_errors} 错误, {total_warnings} 警告"
                + (f" (含 {conflict_count} 个地址冲突)" if conflict_count > 0 else "")
            )

        except Exception as e:
            self.logger.error(f"验证失败: {str(e)}")
            QMessageBox.critical(
                self.layout_manager.main_window,
                "验证错误",
                f"验证过程出错: {str(e)}"
            )

    def _show_validation_result_dialog(self, errors, warnings, infos,
                                        conflict_count, detail_text):
        """显示验证结果汇总对话框"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox

        dialog = QDialog(self.layout_manager.main_window)
        dialog.setWindowTitle("SVD 验证结果")
        dialog.setMinimumSize(640, 480)
        dialog.resize(720, 560)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(8)

        # 摘要标签
        summary_parts = []
        if errors > 0:
            summary_parts.append(f"{errors} 个错误")
        if warnings > 0:
            summary_parts.append(f"{warnings} 个警告")
        if infos > 0:
            summary_parts.append(f"{infos} 条信息")
        if conflict_count > 0:
            summary_parts.append(f"{conflict_count} 个地址冲突")

        summary_label = QLabel(
            f"验证发现: {'，'.join(summary_parts)}。\n"
            f"建议优先修复错误项，警告项可酌情处理。"
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
        btn_box.accepted.connect(dialog.accept)
        layout.addWidget(btn_box)

        dialog.exec()

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
                QMessageBox.warning(
                    self.layout_manager.main_window,
                    "验证错误",
                    "\n".join(errors)
                )
                return

            # 生成SVD
            generator = SVDGenerator(self.state_manager.device_info)
            svd_xml = generator.generate()

            # 更新预览
            preview_edit = self.layout_manager.get_widget('preview_edit')
            if preview_edit:
                preview_edit.setPlainText(pretty_xml(svd_xml))

            self.logger.info("SVD生成成功")
            self.layout_manager.update_status("SVD生成成功")
            self.svd_generated.emit(svd_xml)

        except Exception as e:
            self.logger.error(f"SVD生成失败: {str(e)}")
            QMessageBox.critical(
                self.layout_manager.main_window,
                "生成错误",
                f"SVD生成失败: {str(e)}"
            )

    def preview_xml(self):
        """预览XML"""
        self.logger.debug("preview_xml 被调用")
        try:
            # 首先从UI更新设备信息
            self.update_device_info_from_ui()
            self.logger.debug("update_device_info_from_ui 完成")
 
            generator = SVDGenerator(self.state_manager.device_info)
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
                "预览错误",
                f"XML预览失败: {str(e)}"
            )

    def export_file(self):
        """导出文件 — 支持多种格式"""
        try:
            file_path, selected_filter = QFileDialog.getSaveFileName(
                self.layout_manager.main_window,
                "导出文件",
                "",
                "SVD文件 (*.svd);;CSV 寄存器详情 (*.csv);;CSV 寄存器汇总 (*.csv);;"
                "Markdown 文档 (*.md);;HTML 文档 (*.html);;所有文件 (*.*)"
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
                generator = SVDGenerator(self.state_manager.device_info)
                svd_xml = generator.generate()
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(svd_xml)
                success = True

            if success:
                self.logger.info(f"文件导出成功: {file_path}")
                self.layout_manager.update_status(f"文件导出成功: {os.path.basename(file_path)}")
                QMessageBox.information(
                    self.layout_manager.main_window,
                    "导出成功",
                    f"文件已导出到:\n{file_path}"
                )
            else:
                QMessageBox.warning(
                    self.layout_manager.main_window,
                    "导出失败",
                    "文件导出失败，请检查日志。"
                )

        except Exception as e:
            self.logger.error(f"文件导出失败: {str(e)}")
            QMessageBox.critical(
                self.layout_manager.main_window,
                "导出错误",
                f"文件导出失败: {str(e)}"
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
