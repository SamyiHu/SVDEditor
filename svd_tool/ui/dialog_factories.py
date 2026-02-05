# svd_tool/ui/dialog_factories.py (完整修复版本)

from typing import Optional, Dict, Any, List

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QDialogButtonBox,
    QComboBox, QSpinBox, QTextEdit, QMessageBox
)
from PyQt6.QtCore import Qt

from .dialogs import BaseEditDialog
from ..core.data_model import Peripheral, Register, Field, Interrupt
from ..core.validators import Validator, ValidationError
from ..core.constants import ACCESS_OPTIONS


class DialogFactory:
    """对话框工厂"""
    
    def __init__(self, parent=None):
        self.parent = parent
        self.existing_peripherals: List[str] = []
        self.existing_registers: List[str] = []
    
    def set_existing_peripherals(self, peripherals: List[str]):
        """设置已存在的外设列表"""
        self.existing_peripherals = peripherals
    
    def set_existing_registers(self, registers: List[str]):
        """设置已存在的寄存器列表"""
        self.existing_registers = registers
    
    def create_peripheral_dialog(self, peripheral: Optional[Peripheral] = None, 
                                is_edit: bool = False) -> QDialog:
        """创建外设编辑对话框"""
        dialog = PeripheralEditDialog(self.parent, peripheral, self.existing_peripherals, is_edit)
        return dialog
    
    def create_register_dialog(self, register: Optional[Register] = None,
                              is_edit: bool = False) -> QDialog:
        """创建寄存器编辑对话框"""
        dialog = RegisterEditDialog(self.parent, register, self.existing_registers, is_edit)
        return dialog
    
    def create_field_dialog(self, field: Optional[Field] = None,
                           is_edit: bool = False) -> QDialog:
        """创建位域编辑对话框"""
        dialog = FieldEditDialog(self.parent, field, is_edit)
        return dialog
    
    def create_interrupt_dialog(self, interrupt: Optional[Interrupt] = None,
                               peripherals: Optional[List[str]] = None,
                               is_edit: bool = False) -> QDialog:
        """创建中断编辑对话框"""
        periph_list = peripherals if peripherals is not None else []
        dialog = InterruptEditDialog(self.parent, interrupt, periph_list, is_edit)
        return dialog


class PeripheralEditDialog(BaseEditDialog):
    """外设编辑对话框"""
    
    def __init__(self, parent=None, peripheral: Optional[Peripheral] = None,
                 existing_peripherals: Optional[List[str]] = None, is_edit: bool = False):
        # 保存实例变量
        self.peripheral = peripheral
        self.existing_peripherals = existing_peripherals or []
        self.is_edit = is_edit
        self.original_name = peripheral.name if peripheral else ""
        
        # 设置标题
        title = "编辑外设" if is_edit and peripheral else "添加外设"
        
        # 调用父类初始化
        super().__init__(parent, title)
        
        if peripheral:
            self.load_data(peripheral)
    
    def setup_form(self):
        """设置表单内容"""
        # 外设名
        self.name_edit = QLineEdit()
        self.add_form_row("外设名:", self.name_edit)
        
        # 基地址
        self.base_addr_edit = QLineEdit()
        self.base_addr_edit.setPlaceholderText("例如: 0x40000000")
        self.add_form_row("基地址:", self.base_addr_edit)
        
        # 显示名称
        self.display_name_edit = QLineEdit()
        self.display_name_edit.setPlaceholderText("可选的显示名称")
        self.add_form_row("显示名称:", self.display_name_edit)
        
        # 描述
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("外设描述")
        self.add_form_row("描述:", self.desc_edit)
        
        # 组名
        self.group_edit = QLineEdit()
        self.group_edit.setPlaceholderText("分组名称")
        self.add_form_row("组名:", self.group_edit)
        
        # 地址块偏移
        self.offset_edit = QLineEdit()
        self.offset_edit.setText("0x0")
        self.add_form_row("地址块偏移:", self.offset_edit)
        
        # 地址块大小
        self.size_edit = QLineEdit()
        self.size_edit.setText("0x14")
        self.add_form_row("地址块大小:", self.size_edit)
        
        # 继承自
        self.derived_combo = QComboBox()
        self.derived_combo.addItem("无")
        
        # 添加已存在的外设（排除当前编辑的外设）
        for periph in self.existing_peripherals:
            if not self.is_edit or periph != self.original_name:
                self.derived_combo.addItem(periph)
        
        self.add_form_row("继承自:", self.derived_combo)
    
    def load_data(self, peripheral: Peripheral):
        """加载数据"""
        if not hasattr(self, 'name_edit'):
            return  # UI元素可能还没创建
            
        self.name_edit.setText(peripheral.name)
        self.base_addr_edit.setText(peripheral.base_address)
        self.display_name_edit.setText(peripheral.display_name)
        self.desc_edit.setText(peripheral.description)
        self.group_edit.setText(peripheral.group_name)
        self.offset_edit.setText(peripheral.address_block["offset"])
        self.size_edit.setText(peripheral.address_block["size"])
        
        # 设置继承选项
        if peripheral.derived_from:
            index = self.derived_combo.findText(peripheral.derived_from)
            if index >= 0:
                self.derived_combo.setCurrentIndex(index)
    
    def validate_input(self):
        """验证输入"""
        name = self.name_edit.text().strip()
        Validator.validate_name(name, "外设名")
        
        # 检查名称是否已存在（如果是添加模式或名称已更改）
        if (not self.is_edit or name != self.original_name) and name in self.existing_peripherals:
            raise ValidationError(f"外设名 '{name}' 已存在")
        
        Validator.validate_hex(self.base_addr_edit.text().strip(), "基地址")
        Validator.validate_hex(self.offset_edit.text().strip(), "地址块偏移")
        Validator.validate_hex(self.size_edit.text().strip(), "地址块大小")
        
        # 验证继承关系
        derived_from = self.derived_combo.currentText()
        if derived_from != "无" and derived_from not in self.existing_peripherals:
            raise ValidationError(f"继承的外设 '{derived_from}' 不存在")
    
    def collect_data(self):
        """收集数据"""
        derived_from = self.derived_combo.currentText()
        if derived_from == "无":
            derived_from = ""
        
        self.result_data = {
            "old_name": self.original_name if self.is_edit else "",
            "name": self.name_edit.text().strip(),
            "base_address": self.base_addr_edit.text().strip(),
            "display_name": self.display_name_edit.text().strip(),
            "description": self.desc_edit.text().strip(),
            "group_name": self.group_edit.text().strip(),
            "address_block": {
                "offset": self.offset_edit.text().strip(),
                "size": self.size_edit.text().strip(),
                "usage": "registers"
            },
            "derived_from": derived_from
        }


class RegisterEditDialog(BaseEditDialog):
    """寄存器编辑对话框"""
    
    def __init__(self, parent=None, register: Optional[Register] = None,
                 existing_registers: Optional[List[str]] = None, is_edit: bool = False):
        # 保存实例变量
        self.register = register
        self.existing_registers = existing_registers or []
        self.is_edit = is_edit
        self.original_name = register.name if register else ""
        
        # 设置标题
        title = "编辑寄存器" if is_edit and register else "添加寄存器"
        
        super().__init__(parent, title)
        
        if register:
            self.load_data(register)
    
    def setup_form(self):
        """设置表单内容"""
        # 寄存器名
        self.name_edit = QLineEdit()
        self.add_form_row("寄存器名:", self.name_edit)
        
        # 偏移地址
        self.offset_edit = QLineEdit()
        self.offset_edit.setPlaceholderText("例如: 0x0C")
        self.add_form_row("偏移地址:", self.offset_edit)
        
        # 显示名称
        self.display_name_edit = QLineEdit()
        self.display_name_edit.setPlaceholderText("可选的显示名称")
        self.add_form_row("显示名称:", self.display_name_edit)
        
        # 描述
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("寄存器描述")
        self.add_form_row("描述:", self.desc_edit)
        
        # 访问权限
        self.access_combo = QComboBox()
        self.access_combo.addItems(ACCESS_OPTIONS)
        self.add_form_row("访问权限:", self.access_combo)
        
        # 复位值
        self.reset_edit = QLineEdit()
        self.reset_edit.setText("0x00000000")
        self.add_form_row("复位值:", self.reset_edit)
        
        # 大小
        self.size_edit = QLineEdit()
        self.size_edit.setText("0x20")
        self.size_edit.setPlaceholderText("例如: 0x20 (32位)")
        self.add_form_row("大小:", self.size_edit)
    
    def load_data(self, register: Register):
        """加载数据"""
        if not hasattr(self, 'name_edit'):
            return  # UI元素可能还没创建
            
        self.name_edit.setText(register.name)
        self.offset_edit.setText(register.offset)
        self.display_name_edit.setText(register.display_name)
        self.desc_edit.setText(register.description)
        self.reset_edit.setText(register.reset_value)
        self.size_edit.setText(register.size)
        
        # 设置访问权限
        if register.access:
            index = self.access_combo.findText(register.access)
            if index >= 0:
                self.access_combo.setCurrentIndex(index)
        else:
            self.access_combo.setCurrentIndex(0)  # 设置为"无"
    
    def validate_input(self):
        """验证输入"""
        name = self.name_edit.text().strip()
        Validator.validate_name(name, "寄存器名")
        
        # 检查名称是否已存在
        if (not self.is_edit or name != self.original_name) and name in self.existing_registers:
            raise ValidationError(f"寄存器名 '{name}' 已存在")
        
        Validator.validate_hex(self.offset_edit.text().strip(), "偏移地址")
        Validator.validate_hex(self.reset_edit.text().strip(), "复位值")
        Validator.validate_hex(self.size_edit.text().strip(), "大小")
    
    def collect_data(self):
        """收集数据"""
        access = self.access_combo.currentText()
        if access == "无":
            access = None
        
        self.result_data = {
            "old_name": self.original_name if self.is_edit else "",
            "name": self.name_edit.text().strip(),
            "offset": self.offset_edit.text().strip(),
            "display_name": self.display_name_edit.text().strip(),
            "description": self.desc_edit.text().strip(),
            "access": access,
            "reset_value": self.reset_edit.text().strip(),
            "size": self.size_edit.text().strip()
        }


class FieldEditDialog(BaseEditDialog):
    """位域编辑对话框"""
    
    def __init__(self, parent=None, field: Optional[Field] = None, is_edit: bool = False):
        # 保存实例变量
        self.field = field
        self.is_edit = is_edit
        self.original_name = field.name if field else ""
        
        # 设置标题
        title = "编辑位域" if is_edit and field else "添加位域"
        
        super().__init__(parent, title)
        
        if field:
            self.load_data(field)
    
    def setup_form(self):
        """设置表单内容"""
        # 位域名
        self.name_edit = QLineEdit()
        self.add_form_row("位域名:", self.name_edit)
        
        # 起始位
        self.offset_spin = QSpinBox()
        self.offset_spin.setRange(0, 31)
        self.add_form_row("起始位:", self.offset_spin)
        
        # 位宽
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 32)
        self.width_spin.setValue(1)
        self.add_form_row("位宽:", self.width_spin)
        
        # 显示名称
        self.display_name_edit = QLineEdit()
        self.display_name_edit.setPlaceholderText("可选的显示名称")
        self.add_form_row("显示名称:", self.display_name_edit)
        
        # 描述
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("位域描述")
        self.add_form_row("描述:", self.desc_edit)
        
        # 访问权限
        self.access_combo = QComboBox()
        self.access_combo.addItems(ACCESS_OPTIONS)
        self.add_form_row("访问权限:", self.access_combo)
        
        # 复位值
        self.reset_edit = QLineEdit()
        self.reset_edit.setText("0x0")
        self.add_form_row("复位值:", self.reset_edit)
    
    def load_data(self, field: Field):
        """加载数据"""
        if not hasattr(self, 'name_edit'):
            return  # UI元素可能还没创建
            
        self.name_edit.setText(field.name)
        self.offset_spin.setValue(field.bit_offset)
        self.width_spin.setValue(field.bit_width)
        self.display_name_edit.setText(field.display_name)
        self.desc_edit.setText(field.description)
        self.reset_edit.setText(field.reset_value)
        
        # 设置访问权限
        if field.access:
            index = self.access_combo.findText(field.access)
            if index >= 0:
                self.access_combo.setCurrentIndex(index)
        else:
            self.access_combo.setCurrentIndex(0)  # 设置为"无"
    
    def validate_input(self):
        """验证输入"""
        name = self.name_edit.text().strip()
        Validator.validate_name(name, "位域名")
        
        # 验证位域范围
        offset = self.offset_spin.value()
        width = self.width_spin.value()
        Validator.validate_bit_range(offset, width)
        
        Validator.validate_hex(self.reset_edit.text().strip(), "复位值")
    
    def collect_data(self):
        """收集数据"""
        access = self.access_combo.currentText()
        if access == "无":
            access = None
        
        self.result_data = {
            "old_name": self.original_name if self.is_edit else "",
            "name": self.name_edit.text().strip(),
            "offset": self.offset_spin.value(),
            "width": self.width_spin.value(),
            "display_name": self.display_name_edit.text().strip(),
            "description": self.desc_edit.text().strip(),
            "access": access,
            "reset_value": self.reset_edit.text().strip()
        }


class InterruptEditDialog(BaseEditDialog):
    """中断编辑对话框"""
    
    def __init__(self, parent=None, interrupt: Optional[Interrupt] = None,
                 peripherals: Optional[List[str]] = None, is_edit: bool = False):
        # 保存实例变量
        self.interrupt = interrupt
        self.peripherals = peripherals or []
        self.is_edit = is_edit
        self.original_name = interrupt.name if interrupt else ""
        
        # 设置标题
        title = "编辑中断" if is_edit and interrupt else "添加中断"
        
        super().__init__(parent, title)
        
        if interrupt:
            self.load_data(interrupt)
    
    def setup_form(self):
        """设置表单内容"""
        # 中断名
        self.name_edit = QLineEdit()
        self.add_form_row("中断名:", self.name_edit)
        
        # 中断号
        self.value_spin = QSpinBox()
        self.value_spin.setRange(0, 255)
        self.add_form_row("中断号:", self.value_spin)
        
        # 关联外设
        self.periph_combo = QComboBox()
        self.periph_combo.addItems(self.peripherals)
        self.add_form_row("关联外设:", self.periph_combo)
        
        # 描述
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("中断描述")
        self.add_form_row("描述:", self.desc_edit)
    
    def load_data(self, interrupt: Interrupt):
        """加载数据"""
        if not hasattr(self, 'name_edit'):
            return  # UI元素可能还没创建
            
        self.name_edit.setText(interrupt.name)
        self.value_spin.setValue(interrupt.value)
        self.desc_edit.setText(interrupt.description)
        
        # 设置关联外设
        if interrupt.peripheral:
            index = self.periph_combo.findText(interrupt.peripheral)
            if index >= 0:
                self.periph_combo.setCurrentIndex(index)
    
    def validate_input(self):
        """验证输入"""
        name = self.name_edit.text().strip()
        Validator.validate_name(name, "中断名")
        
        # 验证中断号
        value = self.value_spin.value()
        Validator.validate_irq_number(value)
        
        # 验证关联外设
        peripheral = self.periph_combo.currentText()
        if not peripheral:
            raise ValidationError("必须选择关联外设")
    
    def collect_data(self):
        """收集数据"""
        self.result_data = {
            "old_name": self.original_name if self.is_edit else "",
            "name": self.name_edit.text().strip(),
            "value": self.value_spin.value(),
            "description": self.desc_edit.text().strip(),
            "peripheral": self.periph_combo.currentText()
        }