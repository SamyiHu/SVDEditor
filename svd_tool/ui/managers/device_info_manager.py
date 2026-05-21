"""
设备信息管理器
负责管理设备信息的更新和验证
使用协调器模式减少组件间耦合
"""
import logging
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from ...core.data_model import DeviceInfo
from ...i18n.i18n import t


class DeviceInfoManager(QObject):
    """设备信息管理器"""

    # 信号定义
    device_info_updated = pyqtSignal(object)  # 设备信息更新完成
    validation_failed = pyqtSignal(list)  # 验证失败

    def __init__(self, coordinator=None):
        """
        初始化设备信息管理器

        Args:
            coordinator: 协调器实例（可选）
        """
        super().__init__()
        self.coordinator = coordinator
        self.logger = logging.getLogger("DeviceInfoManager")
    
    def set_coordinator(self, coordinator):
        """设置协调器（依赖注入）"""
        self.coordinator = coordinator

    def update_device_info_from_ui(self):
        """从UI更新设备信息"""
        try:
            if not self.coordinator:
                self.logger.error("协调器未设置，无法更新设备信息")
                return
            
            # 通过协调器获取设备信息
            device_info = self.coordinator.get_device_info()
            if not device_info:
                self.logger.error("无法获取设备信息")
                return
            
            # 通过协调器获取控件
            ic_name_edit = self.coordinator.get_widget('ic_name_edit')
            if ic_name_edit:
                device_info.name = ic_name_edit.text().strip()
            
            ic_desc_edit = self.coordinator.get_widget('ic_desc_edit')
            if ic_desc_edit:
                device_info.description = ic_desc_edit.text().strip()
            
            version_edit = self.coordinator.get_widget('version_edit')
            if version_edit:
                device_info.version = version_edit.text().strip()
            
            svd_version_combo = self.coordinator.get_widget('svd_version_combo')
            if svd_version_combo:
                device_info.svd_version = svd_version_combo.currentText()
            
            # 更新CPU信息
            cpu_name_edit = self.coordinator.get_widget('cpu_name_edit')
            if cpu_name_edit:
                device_info.cpu.name = cpu_name_edit.text().strip()
            
            cpu_rev_edit = self.coordinator.get_widget('cpu_rev_edit')
            if cpu_rev_edit:
                device_info.cpu.revision = cpu_rev_edit.text().strip()
            
            endian_combo = self.coordinator.get_widget('endian_combo')
            if endian_combo:
                device_info.cpu.endian = endian_combo.currentText()
            
            mpu_combo = self.coordinator.get_widget('mpu_combo')
            if mpu_combo:
                device_info.cpu.mpu_present = mpu_combo.isChecked()

            fpu_combo = self.coordinator.get_widget('fpu_combo')
            if fpu_combo:
                device_info.cpu.fpu_present = fpu_combo.isChecked()
            
            nvic_prio_spin = self.coordinator.get_widget('nvic_prio_spin')
            if nvic_prio_spin:
                device_info.cpu.nvic_prio_bits = nvic_prio_spin.value()
            
            # 更新公司版权信息（留空=不写入）
            company_name_edit = self.coordinator.get_widget('company_name_edit')
            if company_name_edit:
                device_info.vendor = company_name_edit.text().strip()

            copyright_edit = self.coordinator.get_widget('copyright_edit')
            if copyright_edit:
                device_info.copyright = copyright_edit.text().strip()

            author_edit = self.coordinator.get_widget('author_edit')
            if author_edit:
                device_info.author = author_edit.text().strip()
            
            # 处理许可证字段（考虑"不显示"选项）
            license_combo = self.coordinator.get_widget('license_combo')
            if license_combo:
                license_text = license_combo.currentText()
                # 支持中文和英文的"不显示"/"Do not display"
                if license_text == "不显示" or license_text == "Do not display":
                    # 如果选择了"不显示"，则清空许可证字段
                    device_info.license = ""
                else:
                    device_info.license = license_text
            
            self.logger.debug("设备信息已从UI更新")
            self.device_info_updated.emit(device_info)
            
        except Exception as e:
            self.logger.error(f"更新设备信息时出错: {str(e)}")
            raise

    def validate_device_info(self) -> list:
        """
        验证设备信息
        
        Returns:
            list: 错误消息列表，如果验证通过则返回空列表
        """
        errors = []
        
        if not self.coordinator:
            errors.append("协调器未设置，无法验证设备信息")
            return errors
        
        device_info = self.coordinator.get_device_info()
        if not device_info:
            errors.append("无法获取设备信息")
            return errors
        
        # 验证基本信息
        if not device_info.name or device_info.name.strip() == "":
            errors.append("设备名称不能为空")
        
        if not device_info.version or device_info.version.strip() == "":
            errors.append("设备版本不能为空")
        
        if not device_info.svd_version or device_info.svd_version.strip() == "":
            errors.append("SVD版本不能为空")
        
        # 验证CPU信息
        if not device_info.cpu.name or device_info.cpu.name.strip() == "":
            errors.append("CPU名称不能为空")
        
        if device_info.cpu.nvic_prio_bits < 0 or device_info.cpu.nvic_prio_bits > 32:
            errors.append("NVIC优先级位数必须在0-32之间")
        
        # 验证数值范围
        if hasattr(device_info, 'address_unit_bits') and device_info.address_unit_bits <= 0:
            errors.append("地址单元位数必须大于0")
        
        if hasattr(device_info, 'width') and device_info.width <= 0:
            errors.append("数据宽度必须大于0")
        
        if hasattr(device_info, 'size') and device_info.size <= 0:
            errors.append("设备大小必须大于0")
        
        return errors

    def update_ui_from_device_info(self, device_info=None):
        """从设备信息更新UI

        Args:
            device_info: 可选的设备信息对象，如果为None则从协调器获取
        """
        try:
            # 如果没有提供设备信息，则从协调器获取
            if device_info is None:
                if not self.coordinator:
                    self.logger.error("协调器未设置，无法更新UI")
                    return

                # 通过协调器获取设备信息
                device_info = self.coordinator.get_device_info()
                if not device_info:
                    self.logger.error("无法获取设备信息")
                    return

            # 设置保护标志，防止控件信号触发 _on_basic_info_edited 覆盖数据模型
            main_win = self.coordinator.get_component("layout_manager")
            if main_win and hasattr(main_win, 'main_window'):
                main_win = main_win.main_window
            if main_win and hasattr(main_win, '_basic_info_updating'):
                main_win._basic_info_updating = True

            # 更新基本信息控件
            ic_name_edit = self.coordinator.get_widget('ic_name_edit')
            if ic_name_edit:
                ic_name_edit.setText(device_info.name or "")
            
            ic_desc_edit = self.coordinator.get_widget('ic_desc_edit')
            if ic_desc_edit:
                ic_desc_edit.setText(device_info.description or "")
            
            version_edit = self.coordinator.get_widget('version_edit')
            if version_edit:
                version_edit.setText(device_info.version or "")
            
            svd_version_combo = self.coordinator.get_widget('svd_version_combo')
            if svd_version_combo:
                index = svd_version_combo.findText(device_info.svd_version or "")
                if index >= 0:
                    svd_version_combo.setCurrentIndex(index)
            
            # 更新CPU信息控件
            cpu_name_edit = self.coordinator.get_widget('cpu_name_edit')
            if cpu_name_edit:
                cpu_name_edit.setText(device_info.cpu.name or "")
            
            cpu_rev_edit = self.coordinator.get_widget('cpu_rev_edit')
            if cpu_rev_edit:
                cpu_rev_edit.setText(device_info.cpu.revision or "")
            
            endian_combo = self.coordinator.get_widget('endian_combo')
            if endian_combo:
                index = endian_combo.findText(device_info.cpu.endian or "")
                if index >= 0:
                    endian_combo.setCurrentIndex(index)
            
            mpu_combo = self.coordinator.get_widget('mpu_combo')
            if mpu_combo:
                mpu_combo.setChecked(bool(device_info.cpu.mpu_present))

            fpu_combo = self.coordinator.get_widget('fpu_combo')
            if fpu_combo:
                fpu_combo.setChecked(bool(device_info.cpu.fpu_present))
            
            nvic_prio_spin = self.coordinator.get_widget('nvic_prio_spin')
            if nvic_prio_spin:
                nvic_prio_spin.setValue(device_info.cpu.nvic_prio_bits)
            
            # 更新公司版权信息控件
            company_name_edit = self.coordinator.get_widget('company_name_edit')
            company_checkbox = self.coordinator.get_widget('company_checkbox')
            if company_name_edit and company_checkbox:
                # 如果厂商名称为空或为None，则勾选"不显示"
                if not device_info.vendor or device_info.vendor.strip() == "":
                    company_checkbox.setChecked(True)
                    company_name_edit.clear()
                    company_name_edit.setEnabled(False)
                else:
                    company_checkbox.setChecked(False)
                    company_name_edit.setText(device_info.vendor)
                    company_name_edit.setEnabled(True)
            
            copyright_edit = self.coordinator.get_widget('copyright_edit')
            copyright_checkbox = self.coordinator.get_widget('copyright_checkbox')
            if copyright_edit and copyright_checkbox:
                # 如果版权信息为空或为None，则勾选"不显示"
                if not device_info.copyright or device_info.copyright.strip() == "":
                    copyright_checkbox.setChecked(True)
                    copyright_edit.clear()
                    copyright_edit.setEnabled(False)
                else:
                    copyright_checkbox.setChecked(False)
                    copyright_edit.setText(device_info.copyright)
                    copyright_edit.setEnabled(True)
            
            # 更新作者字段和复选框状态
            author_edit = self.coordinator.get_widget('author_edit')
            author_checkbox = self.coordinator.get_widget('author_checkbox')
            if author_edit and author_checkbox:
                # 如果作者字段为空或为None，则勾选"不显示"
                if not device_info.author or device_info.author.strip() == "":
                    author_checkbox.setChecked(True)
                    author_edit.clear()
                    author_edit.setEnabled(False)
                else:
                    author_checkbox.setChecked(False)
                    author_edit.setText(device_info.author)
                    author_edit.setEnabled(True)
            
            # 更新许可证字段
            license_combo = self.coordinator.get_widget('license_combo')
            if license_combo:
                current_text = device_info.license
                # 如果许可证为空或为None，则设置为"不显示"
                if not current_text or current_text.strip() == "":
                    current_text = t("license.do_not_display")
                
                index = license_combo.findText(current_text)
                if index >= 0:
                    license_combo.setCurrentIndex(index)
                else:
                    license_combo.addItem(current_text)
                    license_combo.setCurrentText(current_text)
            
            # 更新其他信息控件
            vendor_id_edit = self.coordinator.get_widget('vendor_id_edit')
            if vendor_id_edit:
                vendor_id_edit.setText(device_info.vendor_id or "")
            
            vendor_name_edit = self.coordinator.get_widget('vendor_name_edit')
            if vendor_name_edit:
                vendor_name_edit.setText(device_info.vendor_name or "")
            
            address_unit_bits_spin = self.coordinator.get_widget('address_unit_bits_spin')
            if address_unit_bits_spin:
                address_unit_bits_spin.setValue(device_info.address_unit_bits)
            
            width_spin = self.coordinator.get_widget('width_spin')
            if width_spin:
                width_spin.setValue(device_info.width)
            
            size_spin = self.coordinator.get_widget('size_spin')
            if size_spin:
                size_spin.setValue(device_info.size)
            
            access_combo = self.coordinator.get_widget('access_combo')
            if access_combo:
                index = access_combo.findText(device_info.access or "")
                if index >= 0:
                    access_combo.setCurrentIndex(index)
            
            protection_combo = self.coordinator.get_widget('protection_combo')
            if protection_combo:
                index = protection_combo.findText(device_info.protection or "")
                if index >= 0:
                    protection_combo.setCurrentIndex(index)
            
            reset_value_edit = self.coordinator.get_widget('reset_value_edit')
            if reset_value_edit:
                reset_value_edit.setText(device_info.reset_value or "")
            
            reset_mask_edit = self.coordinator.get_widget('reset_mask_edit')
            if reset_mask_edit:
                reset_mask_edit.setText(device_info.reset_mask or "")
            
            self.logger.debug("UI已从设备信息更新")

        except Exception as e:
            self.logger.error(f"从设备信息更新UI时出错: {str(e)}")
            raise
        finally:
            # 重置保护标志
            main_win = self.coordinator.get_component("layout_manager")
            if main_win and hasattr(main_win, 'main_window'):
                main_win = main_win.main_window
            if main_win and hasattr(main_win, '_basic_info_updating'):
                main_win._basic_info_updating = False

    def reset_device_info(self):
        """重置设备信息为默认值"""
        try:
            if not self.coordinator:
                self.logger.error("协调器未设置，无法重置设备信息")
                return
            
            # 通过协调器获取设备信息
            device_info = self.coordinator.get_device_info()
            if not device_info:
                self.logger.error("无法获取设备信息")
                return
            
            # 设置默认值
            device_info.name = "NewDevice"
            device_info.description = "New Device"
            device_info.version = "1.0"
            device_info.svd_version = "1.3"
            device_info.cpu.name = "Cortex-M0"
            device_info.cpu.revision = "r0p0"
            device_info.cpu.endian = "little"
            device_info.cpu.mpu_present = False
            device_info.cpu.fpu_present = False
            device_info.cpu.nvic_prio_bits = 2
            
            # 更新UI
            self.update_ui_from_device_info()
            
            self.logger.info("设备信息已重置为默认值")
            
        except Exception as e:
            self.logger.error(f"重置设备信息时出错: {str(e)}")
            raise