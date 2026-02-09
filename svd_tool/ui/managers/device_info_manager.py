"""
设备信息管理器
负责管理设备信息的更新和验证
"""
import logging
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from ...core.data_model import DeviceInfo


class DeviceInfoManager(QObject):
    """设备信息管理器"""

    # 信号定义
    device_info_updated = pyqtSignal(object)  # 设备信息更新完成
    validation_failed = pyqtSignal(list)  # 验证失败

    def __init__(self, state_manager, layout_manager):
        """
        初始化设备信息管理器

        Args:
            state_manager: 状态管理器实例
            layout_manager: 布局管理器实例
        """
        super().__init__()
        self.state_manager = state_manager
        self.layout_manager = layout_manager
        self.logger = logging.getLogger("DeviceInfoManager")

    def update_device_info_from_ui(self):
        """从UI更新设备信息"""
        try:
            # 获取设备信息对象
            device_info = self.state_manager.device_info
            
            # 获取布局管理器中的控件
            layout = self.layout_manager
            
            # 更新基本信息
            ic_name_edit = layout.get_widget('ic_name_edit')
            if ic_name_edit:
                device_info.name = ic_name_edit.text().strip()
            
            ic_desc_edit = layout.get_widget('ic_desc_edit')
            if ic_desc_edit:
                device_info.description = ic_desc_edit.text().strip()
            
            version_edit = layout.get_widget('version_edit')
            if version_edit:
                device_info.version = version_edit.text().strip()
            
            svd_version_combo = layout.get_widget('svd_version_combo')
            if svd_version_combo:
                device_info.svd_version = svd_version_combo.currentText()
            
            # 更新CPU信息
            cpu_name_edit = layout.get_widget('cpu_name_edit')
            if cpu_name_edit:
                device_info.cpu.name = cpu_name_edit.text().strip()
            
            cpu_rev_edit = layout.get_widget('cpu_rev_edit')
            if cpu_rev_edit:
                device_info.cpu.revision = cpu_rev_edit.text().strip()
            
            endian_combo = layout.get_widget('endian_combo')
            if endian_combo:
                device_info.cpu.endian = endian_combo.currentText()
            
            mpu_combo = layout.get_widget('mpu_combo')
            if mpu_combo:
                mpu_text = mpu_combo.currentText()
                device_info.cpu.mpu_present = (mpu_text == "是")
            
            fpu_combo = layout.get_widget('fpu_combo')
            if fpu_combo:
                fpu_text = fpu_combo.currentText()
                device_info.cpu.fpu_present = (fpu_text == "是")
            
            nvic_prio_spin = layout.get_widget('nvic_prio_spin')
            if nvic_prio_spin:
                device_info.cpu.nvic_prio_bits = nvic_prio_spin.value()
            
            vendor_id_edit = layout.get_widget('vendor_id_edit')
            if vendor_id_edit:
                device_info.vendor_id = vendor_id_edit.text().strip()
            
            vendor_name_edit = layout.get_widget('vendor_name_edit')
            if vendor_name_edit:
                device_info.vendor_name = vendor_name_edit.text().strip()
            
            address_unit_bits_spin = layout.get_widget('address_unit_bits_spin')
            if address_unit_bits_spin:
                device_info.address_unit_bits = address_unit_bits_spin.value()
            
            width_spin = layout.get_widget('width_spin')
            if width_spin:
                device_info.width = width_spin.value()
            
            size_spin = layout.get_widget('size_spin')
            if size_spin:
                device_info.size = size_spin.value()
            
            access_combo = layout.get_widget('access_combo')
            if access_combo:
                device_info.access = access_combo.currentText()
            
            protection_combo = layout.get_widget('protection_combo')
            if protection_combo:
                device_info.protection = protection_combo.currentText()
            
            reset_value_edit = layout.get_widget('reset_value_edit')
            if reset_value_edit:
                device_info.reset_value = reset_value_edit.text().strip()
            
            reset_mask_edit = layout.get_widget('reset_mask_edit')
            if reset_mask_edit:
                device_info.reset_mask = reset_mask_edit.text().strip()
            
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
        device_info = self.state_manager.device_info
        
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
        if device_info.address_unit_bits <= 0:
            errors.append("地址单元位数必须大于0")
        
        if device_info.width <= 0:
            errors.append("数据宽度必须大于0")
        
        if device_info.size <= 0:
            errors.append("设备大小必须大于0")
        
        return errors

    def update_ui_from_device_info(self):
        """从设备信息更新UI"""
        try:
            device_info = self.state_manager.device_info
            layout = self.layout_manager
            
            # 更新基本信息控件
            ic_name_edit = layout.get_widget('ic_name_edit')
            if ic_name_edit:
                ic_name_edit.setText(device_info.name or "")
            
            ic_desc_edit = layout.get_widget('ic_desc_edit')
            if ic_desc_edit:
                ic_desc_edit.setText(device_info.description or "")
            
            version_edit = layout.get_widget('version_edit')
            if version_edit:
                version_edit.setText(device_info.version or "")
            
            svd_version_combo = layout.get_widget('svd_version_combo')
            if svd_version_combo:
                index = svd_version_combo.findText(device_info.svd_version or "")
                if index >= 0:
                    svd_version_combo.setCurrentIndex(index)
            
            # 更新CPU信息控件
            cpu_name_edit = layout.get_widget('cpu_name_edit')
            if cpu_name_edit:
                cpu_name_edit.setText(device_info.cpu.name or "")
            
            cpu_rev_edit = layout.get_widget('cpu_rev_edit')
            if cpu_rev_edit:
                cpu_rev_edit.setText(device_info.cpu.revision or "")
            
            endian_combo = layout.get_widget('endian_combo')
            if endian_combo:
                index = endian_combo.findText(device_info.cpu.endian or "")
                if index >= 0:
                    endian_combo.setCurrentIndex(index)
            
            mpu_combo = layout.get_widget('mpu_combo')
            if mpu_combo:
                mpu_combo.setCurrentText("是" if device_info.cpu.mpu_present else "否")
            
            fpu_combo = layout.get_widget('fpu_combo')
            if fpu_combo:
                fpu_combo.setCurrentText("是" if device_info.cpu.fpu_present else "否")
            
            nvic_prio_spin = layout.get_widget('nvic_prio_spin')
            if nvic_prio_spin:
                nvic_prio_spin.setValue(device_info.cpu.nvic_prio_bits)
            
            # 更新其他信息控件
            vendor_id_edit = layout.get_widget('vendor_id_edit')
            if vendor_id_edit:
                vendor_id_edit.setText(device_info.vendor_id or "")
            
            vendor_name_edit = layout.get_widget('vendor_name_edit')
            if vendor_name_edit:
                vendor_name_edit.setText(device_info.vendor_name or "")
            
            address_unit_bits_spin = layout.get_widget('address_unit_bits_spin')
            if address_unit_bits_spin:
                address_unit_bits_spin.setValue(device_info.address_unit_bits)
            
            width_spin = layout.get_widget('width_spin')
            if width_spin:
                width_spin.setValue(device_info.width)
            
            size_spin = layout.get_widget('size_spin')
            if size_spin:
                size_spin.setValue(device_info.size)
            
            access_combo = layout.get_widget('access_combo')
            if access_combo:
                index = access_combo.findText(device_info.access or "")
                if index >= 0:
                    access_combo.setCurrentIndex(index)
            
            protection_combo = layout.get_widget('protection_combo')
            if protection_combo:
                index = protection_combo.findText(device_info.protection or "")
                if index >= 0:
                    protection_combo.setCurrentIndex(index)
            
            reset_value_edit = layout.get_widget('reset_value_edit')
            if reset_value_edit:
                reset_value_edit.setText(device_info.reset_value or "")
            
            reset_mask_edit = layout.get_widget('reset_mask_edit')
            if reset_mask_edit:
                reset_mask_edit.setText(device_info.reset_mask or "")
            
            self.logger.debug("UI已从设备信息更新")
            
        except Exception as e:
            self.logger.error(f"从设备信息更新UI时出错: {str(e)}")
            raise

    def reset_device_info(self):
        """重置设备信息为默认值"""
        try:
            # 创建新的设备信息对象
            from ...core.data_model import DeviceInfo, CPUInfo
            device_info = DeviceInfo()
            device_info.cpu = CPUInfo()
            
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
            device_info.vendor_id = "0x0000"
            device_info.vendor_name = "Vendor"
            device_info.address_unit_bits = 8
            device_info.width = 32
            device_info.size = 0x10000000
            device_info.access = "read-write"
            device_info.protection = "none"
            device_info.reset_value = "0x00000000"
            device_info.reset_mask = "0xFFFFFFFF"
            
            # 更新状态管理器
            self.state_manager.device_info = device_info
            
            # 更新UI
            self.update_ui_from_device_info()
            
            self.logger.info("设备信息已重置为默认值")
            
        except Exception as e:
            self.logger.error(f"重置设备信息时出错: {str(e)}")
            raise