"""
UI更新器
负责更新UI内容
"""
import sys
import logging
from typing import Dict, Any, Optional

from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QComboBox
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
            stats: 统计数据字典（全局统计）
        """
        label = self.widget_manager.get_widget('data_stats_label')
        if label:
            text = t("status.data_stats", peripherals=stats.get('peripherals', 0), registers=stats.get('registers', 0), fields=stats.get('fields', 0), interrupts=stats.get('interrupts', 0))
            label.setText(text)

        # 获取筛选控件
        filter_combo = self.widget_manager.get_widget('data_summary_filter')

        # 获取当前筛选的外设名
        selected_periph = None
        if filter_combo and isinstance(filter_combo, QComboBox):
            selected_periph = filter_combo.currentData()
            # 更新筛选下拉框的选项列表
            self._update_filter_options(filter_combo, stats)

        # 根据筛选计算统计数据
        display_stats = stats
        if selected_periph and selected_periph != "__all__":
            display_stats = self._get_filtered_stats(selected_periph, stats)

        # 更新基本信息页面的统计卡片
        periph_label = self.widget_manager.get_widget('periph_count_label')
        if periph_label:
            periph_label.setText(str(display_stats.get('peripherals', 0)))

        reg_label = self.widget_manager.get_widget('reg_count_label')
        if reg_label:
            reg_label.setText(str(display_stats.get('registers', 0)))

        field_label = self.widget_manager.get_widget('field_count_label')
        if field_label:
            field_label.setText(str(display_stats.get('fields', 0)))

        irq_label = self.widget_manager.get_widget('irq_count_label')
        if irq_label:
            irq_label.setText(str(display_stats.get('interrupts', 0)))

    def _update_filter_options(self, combo: QComboBox, stats: Dict[str, int]):
        """更新筛选下拉框选项"""
        # 获取 state_manager 来读取外设列表
        state_mgr = getattr(self.widget_manager, 'main_window', None)
        if state_mgr:
            state_mgr = getattr(state_mgr, 'state_manager', None)
        if not state_mgr or not hasattr(state_mgr, 'device_info'):
            return

        current_data = combo.currentData()
        periph_names = sorted(state_mgr.device_info.peripherals.keys())

        combo.blockSignals(True)
        combo.clear()
        combo.addItem(t("value.all", default="全部"), "__all__")
        for name in periph_names:
            combo.addItem(name, name)

        # 恢复之前的选择
        idx = combo.findData(current_data)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.blockSignals(False)

    def _get_filtered_stats(self, periph_name: str, global_stats: Dict[str, int]) -> Dict[str, int]:
        """获取指定外设的统计数据"""
        state_mgr = getattr(self.widget_manager, 'main_window', None)
        if state_mgr:
            state_mgr = getattr(state_mgr, 'state_manager', None)
        if not state_mgr or not hasattr(state_mgr, 'device_info'):
            return global_stats

        peripherals = state_mgr.device_info.peripherals
        if periph_name not in peripherals:
            return global_stats

        periph = peripherals[periph_name]
        reg_count = len(periph.registers)
        field_count = 0
        for reg in periph.registers.values():
            field_count += len(reg.fields)

        return {
            'peripherals': 1,
            'registers': reg_count,
            'fields': field_count,
            'interrupts': 0,  # 单个外设的中断数不好界定，显示为 "-"
        }

    def update_data_stats_by_filter(self):
        """根据当前筛选条件刷新统计显示"""
        filter_combo = self.widget_manager.get_widget('data_summary_filter')
        if not filter_combo:
            return

        selected_periph = filter_combo.currentData()

        # 获取全局统计
        state_mgr = getattr(self.widget_manager, 'main_window', None)
        if state_mgr:
            state_mgr = getattr(state_mgr, 'state_manager', None)
        if not state_mgr:
            return

        global_stats = state_mgr.get_data_stats()

        # 根据筛选计算
        if selected_periph and selected_periph != "__all__":
            display_stats = self._get_filtered_stats(selected_periph, global_stats)
        else:
            display_stats = global_stats

        # 更新卡片（不更新状态栏和筛选框，避免循环）
        periph_label = self.widget_manager.get_widget('periph_count_label')
        if periph_label:
            periph_label.setText(str(display_stats.get('peripherals', 0)))

        reg_label = self.widget_manager.get_widget('reg_count_label')
        if reg_label:
            reg_label.setText(str(display_stats.get('registers', 0)))

        field_label = self.widget_manager.get_widget('field_count_label')
        if field_label:
            field_label.setText(str(display_stats.get('fields', 0)))

        irq_label = self.widget_manager.get_widget('irq_count_label')
        if irq_label:
            val = display_stats.get('interrupts', 0)
            irq_label.setText("-" if val == 0 and selected_periph != "__all__" else str(val))

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
                mpu_widget = self.widget_manager.get_widget('mpu_combo')
                if hasattr(mpu_widget, 'setChecked'):
                    mpu_widget.setChecked(bool(device_info.cpu.mpu_present))
                elif hasattr(mpu_widget, 'findText'):
                    mpu_text = t("value.yes") if device_info.cpu.mpu_present else t("value.no")
                    index = mpu_widget.findText(mpu_text)
                    if index >= 0:
                        mpu_widget.setCurrentIndex(index)
            if self.widget_manager.has_widget('fpu_combo'):
                fpu_widget = self.widget_manager.get_widget('fpu_combo')
                if hasattr(fpu_widget, 'setChecked'):
                    fpu_widget.setChecked(bool(device_info.cpu.fpu_present))
                elif hasattr(fpu_widget, 'findText'):
                    fpu_text = t("value.yes") if device_info.cpu.fpu_present else t("value.no")
                    index = fpu_widget.findText(fpu_text)
                    if index >= 0:
                        fpu_widget.setCurrentIndex(index)
            if self.widget_manager.has_widget('nvic_prio_spin'):
                self.widget_manager.get_widget('nvic_prio_spin').setValue(device_info.cpu.nvic_prio_bits)

            # 更新公司版权信息字段（留空=不写入）
            if self.widget_manager.has_widget('company_name_edit'):
                self.widget_manager.get_widget('company_name_edit').setText(device_info.vendor or "")
            if self.widget_manager.has_widget('copyright_edit'):
                self.widget_manager.get_widget('copyright_edit').setText(device_info.copyright or "")
            if self.widget_manager.has_widget('author_edit'):
                self.widget_manager.get_widget('author_edit').setText(device_info.author or "")

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
