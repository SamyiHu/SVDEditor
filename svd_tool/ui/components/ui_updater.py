"""
UI更新器
负责更新UI内容
"""
import sys
import logging
from typing import Dict, Any, Optional

from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem
from PyQt6.QtCore import Qt
from ...i18n.i18n import t


class UIUpdater:
    """UI更新器"""

    def __init__(self, widget_manager):
        """
        初始化UI更新器

        Args:
            widget_manager: 控件管理器实例
        """
        self.widget_manager = widget_manager
        self.logger = logging.getLogger("UIUpdater")

    def update_data_stats(self, stats: Dict[str, int]):
        """
        更新数据统计

        Args:
            stats: 统计数据字典
        """
        label = self.widget_manager.get_widget('data_stats_label')
        if label:
            text = t("status.data_stats", peripherals=stats.get('peripherals', 0), registers=stats.get('registers', 0), fields=stats.get('fields', 0), interrupts=stats.get('interrupts', 0))
            label.setText(text)

    def update_status(self, message: str):
        """
        更新状态栏消息

        Args:
            message: 状态消息
        """
        label = self.widget_manager.get_widget('status_label')
        if label:
            label.setText(message)

    def update_basic_info(self, device_info):
        """
        更新基础信息标签页的UI内容

        Args:
            device_info: DeviceInfo对象，包含设备信息
        """
        self.logger.debug(f"update_basic_info开始，device_info={device_info}")
        try:
            # 映射字段到控件
            if self.widget_manager.has_widget('ic_name_edit'):
                self.widget_manager.get_widget('ic_name_edit').setText(device_info.name)
            if self.widget_manager.has_widget('ic_desc_edit'):
                self.widget_manager.get_widget('ic_desc_edit').setText(device_info.description)
            if self.widget_manager.has_widget('version_edit'):
                self.widget_manager.get_widget('version_edit').setText(device_info.version)
            if self.widget_manager.has_widget('svd_version_combo'):
                # 尝试设置SVD版本，如果不在下拉项中则添加
                combo = self.widget_manager.get_widget('svd_version_combo')
                current_text = device_info.svd_version
                index = combo.findText(current_text)
                if index >= 0:
                    combo.setCurrentIndex(index)
                else:
                    combo.addItem(current_text)
                    combo.setCurrentText(current_text)
            if self.widget_manager.has_widget('cpu_name_edit'):
                self.widget_manager.get_widget('cpu_name_edit').setText(device_info.cpu.name)
            if self.widget_manager.has_widget('cpu_rev_edit'):
                self.widget_manager.get_widget('cpu_rev_edit').setText(device_info.cpu.revision)
            if self.widget_manager.has_widget('endian_combo'):
                combo = self.widget_manager.get_widget('endian_combo')
                current_text = device_info.cpu.endian
                index = combo.findText(current_text)
                if index >= 0:
                    combo.setCurrentIndex(index)
                else:
                    combo.addItem(current_text)
                    combo.setCurrentText(current_text)
            if self.widget_manager.has_widget('mpu_combo'):
                combo = self.widget_manager.get_widget('mpu_combo')
                # device_info.cpu.mpu_present 是布尔值，转换为"是"/"否"
                mpu_text = t("value.yes") if device_info.cpu.mpu_present else t("value.no")
                index = combo.findText(mpu_text)
                if index >= 0:
                    combo.setCurrentIndex(index)
                else:
                    combo.addItem(mpu_text)
                    combo.setCurrentText(mpu_text)
            if self.widget_manager.has_widget('fpu_combo'):
                combo = self.widget_manager.get_widget('fpu_combo')
                fpu_text = t("value.yes") if device_info.cpu.fpu_present else t("value.no")
                index = combo.findText(fpu_text)
                if index >= 0:
                    combo.setCurrentIndex(index)
                else:
                    combo.addItem(fpu_text)
                    combo.setCurrentText(fpu_text)
            if self.widget_manager.has_widget('desc_edit'):
                # device_info.description 已经用于ic_desc_edit，这里使用description字段
                # 但可能没有单独的详细描述字段，暂留空
                pass
            if self.widget_manager.has_widget('nvic_prio_spin'):
                self.widget_manager.get_widget('nvic_prio_spin').setValue(device_info.cpu.nvic_prio_bits)

            # 更新公司版权信息字段
            if self.widget_manager.has_widget('company_name_edit'):
                self.widget_manager.get_widget('company_name_edit').setText(device_info.vendor)
            if self.widget_manager.has_widget('copyright_edit'):
                self.widget_manager.get_widget('copyright_edit').setText(device_info.copyright)
            if self.widget_manager.has_widget('author_edit') and self.widget_manager.has_widget('author_checkbox'):
                # 更新作者字段和复选框状态
                author_edit = self.widget_manager.get_widget('author_edit')
                author_checkbox = self.widget_manager.get_widget('author_checkbox')

                # 如果作者字段为空或为None，则勾选"不显示"
                if not device_info.author or device_info.author.strip() == "":
                    author_checkbox.setChecked(True)
                    author_edit.clear()
                    author_edit.setEnabled(False)
                else:
                    author_checkbox.setChecked(False)
                    author_edit.setText(device_info.author)
                    author_edit.setEnabled(True)

            if self.widget_manager.has_widget('license_combo'):
                # 更新许可证字段
                combo = self.widget_manager.get_widget('license_combo')
                current_text = device_info.license

                # 如果许可证为空或为None，则设置为"不显示"
                if not current_text or current_text.strip() == "":
                    current_text = t("license.do_not_display")

                index = combo.findText(current_text)
                if index >= 0:
                    combo.setCurrentIndex(index)
                else:
                    combo.addItem(current_text)
                    combo.setCurrentText(current_text)

            self.logger.debug("update_basic_info完成")
        except Exception as e:
            self.logger.error(f"update_basic_info异常: {e}")
            import traceback
            traceback.print_exc()

    def update_field_table(self, peripheral_name: Optional[str] = None,
                          register_name: Optional[str] = None, register=None):
        """
        更新位域表格

        Args:
            peripheral_name: 外设名称
            register_name: 寄存器名称
            register: 寄存器对象（如果提供，则忽略peripheral_name和register_name）
        """
        self.logger.debug(f"update_field_table开始，peripheral={peripheral_name}, register={register_name}, register对象={register}")

        field_table = self.widget_manager.get_widget('field_table')
        if not field_table:
            self.logger.debug(t("warning.field_table_not_found"))
            return

        # 清除表格内容
        field_table.setRowCount(0)

        # 如果没有寄存器，清空表格
        if not register and (not peripheral_name or not register_name):
            self.logger.debug("无寄存器信息，清空表格")
            return

        # 获取寄存器对象 - 通过main_window访问state_manager
        reg_obj = register
        if not reg_obj and peripheral_name and register_name:
            # 尝试通过main_window获取state_manager
            if hasattr(self.widget_manager, 'main_window') and hasattr(self.widget_manager.main_window, 'state_manager'):
                state_manager = self.widget_manager.main_window.state_manager
                device_info = state_manager.device_info
                if (peripheral_name in device_info.peripherals and
                    register_name in device_info.peripherals[peripheral_name].registers):
                    reg_obj = device_info.peripherals[peripheral_name].registers[register_name]
                    self.logger.debug("通过state_manager获取到寄存器对象")
                else:
                    self.logger.debug("外设或寄存器不存在")
                    return
            else:
                self.logger.debug("main_window无state_manager属性")
                return

        if not reg_obj:
            return

        # 获取位域列表
        fields = reg_obj.fields if hasattr(reg_obj, 'fields') else {}
        if not fields:
            self.logger.debug("寄存器无位域，清空表格")
            field_table.setRowCount(0)
            return

        # 设置行数
        field_table.setRowCount(len(fields))

        # 填充表格
        for row, (field_name, field) in enumerate(fields.items()):
            # 名称
            name_item = QTableWidgetItem(field_name)
            field_table.setItem(row, 0, name_item)

            # 位偏移
            bit_offset_item = QTableWidgetItem(str(field.bit_offset))
            bit_offset_item.setFlags(bit_offset_item.flags() | Qt.ItemFlag.ItemIsEditable)
            field_table.setItem(row, 1, bit_offset_item)

            # 位宽
            bit_width_item = QTableWidgetItem(str(field.bit_width))
            bit_width_item.setFlags(bit_width_item.flags() | Qt.ItemFlag.ItemIsEditable)
            field_table.setItem(row, 2, bit_width_item)

            # 访问权限
            access_item = QTableWidgetItem(field.access if field.access else "")
            access_item.setFlags(access_item.flags() | Qt.ItemFlag.ItemIsEditable)
            field_table.setItem(row, 3, access_item)

            # 复位值
            reset_item = QTableWidgetItem(field.reset_value if field.reset_value else "")
            reset_item.setFlags(reset_item.flags() | Qt.ItemFlag.ItemIsEditable)
            field_table.setItem(row, 4, reset_item)

            # 描述
            desc_item = QTableWidgetItem(field.description if field.description else "")
            desc_item.setFlags(desc_item.flags() | Qt.ItemFlag.ItemIsEditable)
            field_table.setItem(row, 5, desc_item)

        self.logger.debug(f"update_field_table完成，填充{len(fields)}行")
