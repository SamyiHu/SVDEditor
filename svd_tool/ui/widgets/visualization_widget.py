"""
综合可视化控件容器
从main_window.py中提取的独立组件
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt

from .address_map_widget import AddressMapWidget
from .bit_field_widget import BitFieldWidget
from svd_tool.core.data_model import Peripheral


class VisualizationWidget(QWidget):
    """综合可视化控件容器"""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)  # 增加间距，避免外设图被遮挡
        
        self.address_map = AddressMapWidget()
        self.bit_field = BitFieldWidget()
        
        layout.addWidget(self.address_map)
        layout.addWidget(self.bit_field)
        
        self.current_peripheral = None
        self.current_register = None
        self.main_window = None  # 存储对主窗口的引用
        
    def show_peripheral(self, peripheral):
        """显示外设可视化"""
        self.current_peripheral = peripheral
        self.current_register = None
        
        # 处理继承类型外设：如果有derived_from，获取基类外设的寄存器
        if peripheral and peripheral.derived_from and self.main_window:
            # 获取基类外设
            base_periph_name = peripheral.derived_from
            if (hasattr(self.main_window, 'device_info') and
                hasattr(self.main_window.device_info, 'peripherals') and
                base_periph_name in self.main_window.device_info.peripherals):
                
                base_peripheral = self.main_window.device_info.peripherals[base_periph_name]
                # 创建合并的寄存器列表：当前外设的寄存器 + 基类外设的寄存器
                # 但注意：当前外设可能没有自己的寄存器定义
                all_registers = {}
                
                # 首先添加基类外设的寄存器
                if hasattr(base_peripheral, 'registers'):
                    for reg_name, reg in base_peripheral.registers.items():
                        all_registers[reg_name] = reg
                
                # 然后添加当前外设的寄存器（如果有，会覆盖基类的同名寄存器）
                if hasattr(peripheral, 'registers'):
                    for reg_name, reg in peripheral.registers.items():
                        all_registers[reg_name] = reg
                
                # 创建一个临时的外设对象用于显示
                display_peripheral = Peripheral(
                    name=peripheral.name,
                    base_address=peripheral.base_address,
                    description=peripheral.description,
                    display_name=peripheral.display_name,
                    group_name=peripheral.group_name,
                    derived_from=peripheral.derived_from,
                    address_block=peripheral.address_block.copy(),
                    registers=all_registers,
                    interrupts=peripheral.interrupts.copy() if hasattr(peripheral, 'interrupts') else []
                )
                self.address_map.set_peripheral(display_peripheral)
            else:
                # 基类外设不存在，只显示当前外设的寄存器
                self.address_map.set_peripheral(peripheral)
        else:
            # 非继承类型外设，正常显示
            self.address_map.set_peripheral(peripheral)
        
        # 不清空位域图，保留之前可能存在的寄存器（但属于不同外设？）
        # 如果外设改变，位域图可能不相关，清空
        self.bit_field.set_register(None)
        
    def show_register(self, register):
        """显示寄存器可视化（需提前设置外设）"""
        self.current_register = register
        self.bit_field.set_register(register)
        
    def show_peripheral_and_register(self, peripheral, register):
        """同时显示外设和寄存器"""
        self.show_peripheral(peripheral)
        self.show_register(register)
        
    def show_field(self, field):
        """显示位域可视化（高亮选中的位域）"""
        if self.current_register:
            # 高亮选中的位域
            self.bit_field.set_selected_field(field.name if field else None)
        else:
            # 如果没有当前寄存器，清空位域图
            self.bit_field.set_register(None)