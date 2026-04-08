"""
文件操作管理器
负责处理文件操作（导入、导出、生成等）
"""
import os
import logging
from typing import Optional

from PyQt6.QtWidgets import QFileDialog, QMessageBox
from PyQt6.QtCore import QObject, pyqtSignal

from ...core.svd_parser import SVDParser
from ...core.svd_generator import SVDGenerator
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
        """导出文件"""
        try:
            # 获取保存路径
            file_path, _ = QFileDialog.getSaveFileName(
                self.layout_manager.main_window,
                "保存SVD文件",
                "",
                "SVD文件 (*.svd);;所有文件 (*.*)"
            )

            if not file_path:
                return

            # 首先从UI更新设备信息
            self.update_device_info_from_ui()

            # 生成SVD
            generator = SVDGenerator(self.state_manager.device_info)
            svd_xml = generator.generate()

            # 保存文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(svd_xml)

            self.logger.info(f"SVD文件已保存: {file_path}")
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
            self.state_manager.device_info.cpu.mpu_present = (mpu_combo.currentText() == "是")
        if fpu_combo:
            self.state_manager.device_info.cpu.fpu_present = (fpu_combo.currentText() == "是")
        if nvic_prio_spin:
            self.state_manager.device_info.cpu.nvic_prio_bits = nvic_prio_spin.value()
        if company_name_edit and company_checkbox:
            if company_checkbox.isChecked():
                self.state_manager.device_info.vendor = ""
            else:
                self.state_manager.device_info.vendor = company_name_edit.text()
        elif company_name_edit:
            self.state_manager.device_info.vendor = company_name_edit.text()
        if copyright_edit and copyright_checkbox:
            if copyright_checkbox.isChecked():
                self.state_manager.device_info.copyright = ""
            else:
                self.state_manager.device_info.copyright = copyright_edit.text()
        elif copyright_edit:
            self.state_manager.device_info.copyright = copyright_edit.text()
        if author_edit:
            self.state_manager.device_info.author = author_edit.text()
        if license_combo:
            license_text = license_combo.currentText()
            if license_text != "不显示":
                self.state_manager.device_info.license = license_text
            else:
                self.state_manager.device_info.license = ""
