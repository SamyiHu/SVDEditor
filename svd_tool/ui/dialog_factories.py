# svd_tool/ui/dialog_factories.py (完整修复版本)

from typing import Optional, Dict, Any, List

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QDialogButtonBox,
    QComboBox, QTextEdit, QMessageBox,
    QListWidget, QListWidgetItem, QAbstractItemView,
    QCheckBox, QGroupBox, QToolButton, QWidget,
    QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt

from .dialogs import BaseEditDialog
from .dialogs.enum_values_editor import EnumValuesEditor
from ..core.data_model import Peripheral, Register, Field, Interrupt
from ..core.validators import Validator, ValidationError
from ..core.constants import ACCESS_OPTIONS
from .widgets.modern_spinbox import ModernSpinBox
from .widgets.labeled_slider import LabeledSlider
from ..core.svd_schema_validator import SVDSchemaValidator
from ..i18n.i18n import t


class DialogFactory:
    """对话框工厂"""
    
    def __init__(self, parent=None):
        self.parent = parent
        self.existing_peripherals: List[str] = []
        self.existing_registers: List[str] = []
        # 完整数据字典（用于实时冲突检测）
        self.existing_peripherals_data: Dict[str, Peripheral] = {}
        self.existing_registers_data: Dict[str, Register] = {}
        self.existing_fields_data: Dict[str, Field] = {}
    
    def set_existing_peripherals(self, peripherals):
        """设置已存在的外设列表"""
        if isinstance(peripherals, dict):
            self.existing_peripherals = list(peripherals.keys())
            self.existing_peripherals_data = peripherals
        else:
            self.existing_peripherals = peripherals
    
    def set_existing_registers(self, registers):
        """设置已存在的寄存器列表"""
        if isinstance(registers, dict):
            self.existing_registers = list(registers.keys())
            self.existing_registers_data = registers
        else:
            self.existing_registers = registers
    
    def set_existing_fields(self, fields: Dict[str, Field]):
        """设置已存在的位域字典"""
        self.existing_fields_data = fields
    
    def create_peripheral_dialog(self, peripheral: Optional[Peripheral] = None, 
                                is_edit: bool = False) -> QDialog:
        """创建外设编辑对话框"""
        dialog = PeripheralEditDialog(
            self.parent, peripheral, self.existing_peripherals,
            self.existing_peripherals_data, is_edit
        )
        return dialog
    
    def create_register_dialog(self, register: Optional[Register] = None,
                              is_edit: bool = False) -> QDialog:
        """创建寄存器编辑对话框"""
        dialog = RegisterEditDialog(
            self.parent, register, self.existing_registers,
            self.existing_registers_data, is_edit
        )
        return dialog
    
    def create_field_dialog(self, field: Optional[Field] = None,
                           is_edit: bool = False) -> QDialog:
        """创建位域编辑对话框"""
        dialog = FieldEditDialog(
            self.parent, field, self.existing_fields_data, is_edit
        )
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
                 existing_peripherals: Optional[List[str]] = None,
                 existing_peripherals_data: Optional[Dict[str, Peripheral]] = None,
                 is_edit: bool = False):
        # 保存实例变量
        self.peripheral = peripheral
        self.existing_peripherals = existing_peripherals or []
        self.existing_peripherals_data = existing_peripherals_data or {}
        self.is_edit = is_edit
        self.original_name = peripheral.name if peripheral else ""
        
        # 设置标题
        title = t("label.dialog_title_edit_peripheral") if is_edit and peripheral else t("label.dialog_title_add_peripheral")
        
        # 调用父类初始化
        super().__init__(parent, title)
        
        # 是否存在地址冲突标志
        self._has_address_conflict = False
        
        # 连接实时检测信号
        self.base_addr_edit.textChanged.connect(self._check_address_conflict)
        self.offset_edit.textChanged.connect(self._check_address_conflict)
        self.size_edit.textChanged.connect(self._check_address_conflict)

        # 连接预览刷新信号
        for w in [self.name_edit, self.base_addr_edit, self.display_name_edit,
                  self.desc_edit, self.group_edit, self.offset_edit, self.size_edit]:
            self._connect_preview_signal(w)
        self._connect_preview_signal(self.derived_combo)

        if peripheral:
            self.load_data(peripheral)
    
    def setup_form(self):
        """设置表单内容"""
        # 外设名
        self.name_edit = QLineEdit()
        self.add_form_row(t("label.peripheral_name") + ":", self.name_edit)
        
        # 基地址
        self.base_addr_edit = QLineEdit()
        self.base_addr_edit.setPlaceholderText(t("placeholder.base_address"))
        self.add_form_row(t("label.base_address") + ":", self.base_addr_edit)
        
        # 显示名称
        self.display_name_edit = QLineEdit()
        self.display_name_edit.setPlaceholderText(t("placeholder.display_name"))
        self.add_form_row(t("label.display_name") + ":", self.display_name_edit)
        
        # 描述
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText(t("placeholder.description"))
        self.add_form_row(t("label.description") + ":", self.desc_edit)
        
        # 组名
        self.group_edit = QLineEdit()
        self.group_edit.setPlaceholderText(t("placeholder.group_name"))
        self.add_form_row(t("label.group_name") + ":", self.group_edit)
        
        # 地址块偏移
        self.offset_edit = QLineEdit()
        self.offset_edit.setText("0x0")
        self.add_form_row(t("label.address_block_offset") + ":", self.offset_edit)
        
        # 地址块大小
        self.size_edit = QLineEdit()
        self.size_edit.setText("0x14")
        self.add_form_row(t("label.address_block_size") + ":", self.size_edit)
        
        # 继承自
        self.derived_combo = QComboBox()
        self.derived_combo.addItem(t("value.none"))
        
        # 添加已存在的外设（排除当前编辑的外设）
        for periph in self.existing_peripherals:
            if not self.is_edit or periph != self.original_name:
                self.derived_combo.addItem(periph)
        
        self.add_form_row(t("label.derived_from") + ":", self.derived_combo)
    
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
    
    def _check_address_conflict(self):
        """实时检测外设地址冲突"""
        base_addr = self.base_addr_edit.text().strip()
        if not base_addr:
            self._clear_conflict_style(self.base_addr_edit)
            self._has_address_conflict = False
            return

        addr_block = {
            "offset": self.offset_edit.text().strip(),
            "size": self.size_edit.text().strip(),
        }

        conflict = SVDSchemaValidator.check_peripheral_address_conflict(
            new_name=self.name_edit.text().strip(),
            new_base_addr=base_addr,
            new_addr_block=addr_block,
            existing_peripherals=self.existing_peripherals_data,
            exclude_name=self.original_name if self.is_edit else ""
        )

        if conflict:
            self._set_conflict_style(self.base_addr_edit, conflict)
            self._has_address_conflict = True
        else:
            self._clear_conflict_style(self.base_addr_edit)
            self._has_address_conflict = False
    
    def validate_input(self):
        """验证输入"""
        name = self.name_edit.text().strip()
        Validator.validate_name(name, t("error.peripheral_name_validation"))
        
        # 检查名称是否已存在（如果是添加模式或名称已更改）
        if (not self.is_edit or name != self.original_name) and name in self.existing_peripherals:
            raise ValidationError(t("error.peripheral_name_exists", name=name))
        
        Validator.validate_hex(self.base_addr_edit.text().strip(), t("error.base_address_validation"))
        Validator.validate_hex(self.offset_edit.text().strip(), t("error.offset_address_validation"))
        Validator.validate_hex(self.size_edit.text().strip(), t("error.address_block_size_validation"))
        
        # 检查地址冲突（阻止保存）
        if self._has_address_conflict:
            raise ValidationError("外设地址与现有外设冲突，请修改基地址或地址块大小")
        
        # 验证继承关系
        derived_from = self.derived_combo.currentText()
        if derived_from != t("value.none") and derived_from not in self.existing_peripherals:
            raise ValidationError(t("error.derived_peripheral_not_exist", derived_from=derived_from))
    
    def collect_data(self):
        """收集数据"""
        derived_from = self.derived_combo.currentText()
        if derived_from == t("value.none"):
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

    def _generate_preview_xml(self) -> str:
        """生成当前外设配置部分的 XML 预览（不含寄存器/位域）"""
        try:
            from ..core.svd_generator import SVDGenerator
            from ..core.data_model import Peripheral
            p = Peripheral(
                name=self.name_edit.text().strip() or "unnamed",
                base_address=self.base_addr_edit.text().strip() or "0x0",
                description=self.desc_edit.text().strip(),
                display_name=self.display_name_edit.text().strip(),
                group_name=self.group_edit.text().strip(),
                derived_from=self.derived_combo.currentText() if self.derived_combo.currentText() != t("value.none") else "",
                address_block={
                    "offset": self.offset_edit.text().strip() or "0x0",
                    "size": self.size_edit.text().strip() or "0x14",
                    "usage": "registers"
                },
            )
            # 只显示外设自身的配置，不包含子元素
            return SVDGenerator.generate_peripheral_xml(p)
        except Exception:
            return ""


class RegisterEditDialog(BaseEditDialog):
    """寄存器编辑对话框"""
    
    def __init__(self, parent=None, register: Optional[Register] = None,
                 existing_registers: Optional[List[str]] = None,
                 existing_registers_data: Optional[Dict[str, Register]] = None,
                 is_edit: bool = False):
        # 保存实例变量
        self.register = register
        self.existing_registers = existing_registers or []
        self.existing_registers_data = existing_registers_data or {}
        self.is_edit = is_edit
        self.original_name = register.name if register else ""
        
        # 设置标题
        title = t("label.dialog_title_edit_register") if is_edit and register else t("label.dialog_title_add_register")
        
        super().__init__(parent, title)
        
        # 是否存在偏移冲突标志
        self._has_offset_conflict = False
        
        # 连接实时检测信号
        self.offset_edit.textChanged.connect(self._check_offset_conflict)

        # 连接预览刷新信号
        for w in [self.name_edit, self.offset_edit, self.display_name_edit,
                  self.desc_edit, self.reset_edit, self.size_edit]:
            self._connect_preview_signal(w)
        self._connect_preview_signal(self.access_combo)

        if register:
            self.load_data(register)
    
    def setup_form(self):
        """设置表单内容"""
        # 寄存器名
        self.name_edit = QLineEdit()
        self.add_form_row(t("label.register_name") + ":", self.name_edit)
        
        # 偏移地址
        self.offset_edit = QLineEdit()
        self.offset_edit.setPlaceholderText(t("placeholder.offset"))
        self.add_form_row(t("label.offset_prefix") + ":", self.offset_edit)
        
        # 显示名称
        self.display_name_edit = QLineEdit()
        self.display_name_edit.setPlaceholderText(t("placeholder.display_name"))
        self.add_form_row(t("label.display_name") + ":", self.display_name_edit)
        
        # 描述
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText(t("placeholder.register_description"))
        self.add_form_row(t("label.description") + ":", self.desc_edit)
        
        # 访问权限
        self.access_combo = QComboBox()
        self.access_combo.addItems(ACCESS_OPTIONS)
        self.add_form_row(t("label.access") + ":", self.access_combo)
        
        # 复位值
        self.reset_edit = QLineEdit()
        self.reset_edit.setText("0x00000000")
        self.add_form_row(t("label.reset_value") + ":", self.reset_edit)
        
        # 大小
        self.size_edit = QLineEdit()
        self.size_edit.setText("0x20")
        self.size_edit.setPlaceholderText(t("placeholder.size"))
        self.add_form_row(t("label.size") + ":", self.size_edit)
    
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
    
    def _check_offset_conflict(self):
        """实时检测寄存器偏移冲突"""
        offset = self.offset_edit.text().strip()
        if not offset:
            self._clear_conflict_style(self.offset_edit)
            self._has_offset_conflict = False
            return
        
        conflict = SVDSchemaValidator.check_register_offset_conflict(
            new_name=self.name_edit.text().strip(),
            new_offset=offset,
            existing_registers=self.existing_registers_data,
            exclude_name=self.original_name if self.is_edit else ""
        )
        
        if conflict:
            self._set_conflict_style(self.offset_edit, conflict)
            self._has_offset_conflict = True
        else:
            self._clear_conflict_style(self.offset_edit)
            self._has_offset_conflict = False
    
    def validate_input(self):
        """验证输入"""
        name = self.name_edit.text().strip()
        Validator.validate_name(name, t("error.register_name_validation"))
        
        # 检查名称是否已存在
        if (not self.is_edit or name != self.original_name) and name in self.existing_registers:
            raise ValidationError(t("error.register_name_exists", name=name))
        
        Validator.validate_hex(self.offset_edit.text().strip(), t("error.offset_address_validation"))
        Validator.validate_hex(self.reset_edit.text().strip(), t("error.reset_value_validation"))
        Validator.validate_hex(self.size_edit.text().strip(), t("error.size_validation"))
        
        # 检查偏移冲突（阻止保存）
        if self._has_offset_conflict:
            raise ValidationError("寄存器偏移地址与现有寄存器冲突，请修改偏移地址")
    
    def collect_data(self):
        """收集数据"""
        access = self.access_combo.currentText()
        if access == t("value.none"):
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

    def _generate_preview_xml(self) -> str:
        """生成当前寄存器配置部分的 XML 预览（不含位域）"""
        try:
            from ..core.svd_generator import SVDGenerator
            from ..core.data_model import Register
            access = self.access_combo.currentText()
            if access == t("value.none"):
                access = None
            r = Register(
                name=self.name_edit.text().strip() or "unnamed",
                offset=self.offset_edit.text().strip() or "0x0",
                description=self.desc_edit.text().strip(),
                display_name=self.display_name_edit.text().strip(),
                access=access,
                reset_value=self.reset_edit.text().strip() or "0x00000000",
                size=self.size_edit.text().strip() or "0x20",
            )
            # 只显示寄存器自身配置，不包含位域
            return SVDGenerator.generate_register_xml(r)
        except Exception:
            return ""


class FieldEditDialog(BaseEditDialog):
    """位域编辑对话框"""
    
    def __init__(self, parent=None, field: Optional[Field] = None,
                 existing_fields_data: Optional[Dict[str, Field]] = None,
                 is_edit: bool = False):
        # 保存实例变量
        self.field = field
        self.existing_fields_data = existing_fields_data or {}
        self.is_edit = is_edit
        self.original_name = field.name if field else ""
        
        # 设置标题
        title = t("label.dialog_title_edit_field") if is_edit and field else t("label.dialog_title_add_field")
        
        super().__init__(parent, title)
        
        # 是否存在位域冲突标志
        self._has_bit_conflict = False
        
        # 连接实时检测信号
        self.offset_spin.valueChanged.connect(self._check_bit_conflict)
        self.width_spin.valueChanged.connect(self._check_bit_conflict)

        # 连接预览刷新信号
        self._connect_preview_signal(self.name_edit)
        self._connect_preview_signal(self.offset_spin)
        self._connect_preview_signal(self.width_spin)
        self._connect_preview_signal(self.display_name_edit)
        self._connect_preview_signal(self.desc_edit)
        self._connect_preview_signal(self.reset_edit)
        self._connect_preview_signal(self.access_combo)

        if field:
            self.load_data(field)
    
    def setup_form(self):
        """设置表单内容"""
        # 位域名
        self.name_edit = QLineEdit()
        self.add_form_row(t("label.field_name") + ":", self.name_edit)
        
        # 起始位
        self.offset_spin = LabeledSlider()
        self.offset_spin.setRange(0, 31)
        self.add_form_row(t("label.bit_offset") + ":", self.offset_spin)

        # 位宽
        self.width_spin = LabeledSlider()
        self.width_spin.setRange(1, 32)
        self.width_spin.setValue(1)
        self.add_form_row(t("label.bit_width") + ":", self.width_spin)
        
        # 显示名称
        self.display_name_edit = QLineEdit()
        self.display_name_edit.setPlaceholderText(t("placeholder.optional_display_name"))
        self.add_form_row(t("label.display_name") + ":", self.display_name_edit)
        
        # 描述
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText(t("placeholder.field_description"))
        self.add_form_row(t("label.description") + ":", self.desc_edit)
        
        # 访问权限
        self.access_combo = QComboBox()
        self.access_combo.addItems(ACCESS_OPTIONS)
        self.add_form_row(t("label.access") + ":", self.access_combo)
        
        # 复位值
        self.reset_edit = QLineEdit()
        self.reset_edit.setText("0x0")
        self.add_form_row(t("label.reset_value") + ":", self.reset_edit)
        
        # 枚举值编辑器
        enum_values = self.field.enumerated_values if (self.field and hasattr(self.field, 'enumerated_values') and self.field.enumerated_values) else None
        self.enum_editor = EnumValuesEditor(enumerated_values=enum_values)
        self.add_form_row("", self.enum_editor)
    
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
        
        # 加载枚举值
        if hasattr(field, 'enumerated_values') and field.enumerated_values:
            self.enum_editor.load_data(field.enumerated_values)
    
    def _check_bit_conflict(self):
        """实时检测位域位范围冲突"""
        bit_offset = self.offset_spin.value()
        bit_width = self.width_spin.value()
        
        if not self.existing_fields_data:
            self._clear_conflict_style(self.offset_spin)
            self._clear_conflict_style(self.width_spin)
            self._has_bit_conflict = False
            return
        
        conflict = SVDSchemaValidator.check_field_bit_conflict(
            new_name=self.name_edit.text().strip(),
            new_bit_offset=bit_offset,
            new_bit_width=bit_width,
            existing_fields=self.existing_fields_data,
            exclude_name=self.original_name if self.is_edit else ""
        )
        
        if conflict:
            self._set_conflict_style(self.offset_spin, conflict)
            self._set_conflict_style(self.width_spin, conflict)
            self._has_bit_conflict = True
        else:
            self._clear_conflict_style(self.offset_spin)
            self._clear_conflict_style(self.width_spin)
            self._has_bit_conflict = False
    
    def validate_input(self):
        """验证输入"""
        name = self.name_edit.text().strip()
        Validator.validate_name(name, t("error.field_name_validation"))
        
        # 验证位域范围
        offset = self.offset_spin.value()
        width = self.width_spin.value()
        Validator.validate_bit_range(offset, width)
        
        Validator.validate_hex(self.reset_edit.text().strip(), t("error.reset_value_validation"))
        
        # 检查位域冲突（阻止保存）
        if self._has_bit_conflict:
            raise ValidationError("位域位范围与现有位域冲突，请修改起始位或位宽")
        
        # 验证枚举值
        if not self.enum_editor.validate():
            raise ValidationError("枚举值验证失败")
    
    def collect_data(self):
        """收集数据"""
        access = self.access_combo.currentText()
        if access == t("value.none"):
            access = None
        
        self.result_data = {
            "old_name": self.original_name if self.is_edit else "",
            "name": self.name_edit.text().strip(),
            "offset": self.offset_spin.value(),
            "width": self.width_spin.value(),
            "display_name": self.display_name_edit.text().strip(),
            "description": self.desc_edit.text().strip(),
            "access": access,
            "reset_value": self.reset_edit.text().strip(),
            "enumerated_values": self.enum_editor.collect_data()
        }

    def _generate_preview_xml(self) -> str:
        """生成当前位域编辑状态的 XML 预览"""
        try:
            from ..core.svd_generator import SVDGenerator
            from ..core.data_model import Field
            access = self.access_combo.currentText()
            if access == t("value.none"):
                access = None
            f = Field(
                name=self.name_edit.text().strip() or "unnamed",
                bit_offset=self.offset_spin.value(),
                bit_width=self.width_spin.value(),
                description=self.desc_edit.text().strip(),
                display_name=self.display_name_edit.text().strip(),
                access=access,
                reset_value=self.reset_edit.text().strip() or "0x0",
                enumerated_values=self.enum_editor.collect_data() or [],
            )
            return SVDGenerator.generate_field_xml(f)
        except Exception:
            return ""


class InterruptEditDialog(BaseEditDialog):
    """中断编辑对话框（支持多外设共用中断，标签式选择）"""

    # 标签样式
    _TAG_STYLE = """
        QFrame {
            background-color: #FFFFFF;
            border: 1.5px solid #42A5F5;
            border-radius: 10px;
            padding: 2px 6px 2px 8px;
        }
        QLabel {
            background: transparent;
            border: none;
            color: #1A1A1A;
            font-size: 12px;
            font-weight: 500;
        }
        QPushButton {
            background: transparent;
            border: none;
            color: #BDBDBD;
            font-size: 14px;
            font-weight: bold;
            padding: 0px;
            margin: 0px;
        }
        QPushButton:hover {
            color: #E53935;
        }
    """
    _SUGGEST_ITEM_STYLE = """
        QPushButton {
            background-color: #FFFFFF;
            border: 1px solid #E0E0E0;
            border-radius: 10px;
            padding: 2px 8px;
            color: #424242;
            font-size: 12px;
            text-align: left;
        }
        QPushButton:hover {
            background-color: #E3F2FD;
            border-color: #42A5F5;
            color: #1565C0;
        }
    """

    def __init__(self, parent=None, interrupt: Optional[Interrupt] = None,
                 peripherals: Optional[List[str]] = None, is_edit: bool = False):
        # 保存实例变量
        self.interrupt = interrupt
        self.all_peripherals = sorted(peripherals or [])
        self.is_edit = is_edit
        self.original_name = interrupt.name if interrupt else ""
        self._selected_peripherals: List[str] = []

        # 设置标题
        title = t("label.dialog_title_edit_interrupt") if is_edit and interrupt else t("label.dialog_title_add_interrupt")

        super().__init__(parent, title)

        if interrupt:
            self.load_data(interrupt)

    def setup_form(self):
        """设置表单内容"""
        # 中断名
        self.name_edit = QLineEdit()
        self.add_form_row(t("label.interrupt_name") + ":", self.name_edit)

        # 中断号
        self.value_spin = LabeledSlider()
        self.value_spin.setRange(0, 255)
        self.add_form_row(t("label.interrupt_value") + ":", self.value_spin)

        # === 关联外设（标签式选择） ===
        periph_widget = QWidget()
        periph_layout = QVBoxLayout(periph_widget)
        periph_layout.setContentsMargins(0, 0, 0, 0)
        periph_layout.setSpacing(4)

        # 搜索/添加输入框
        self.periph_search = QLineEdit()
        self.periph_search.setPlaceholderText(t("placeholder.search_peripheral", default="搜索或添加外设..."))
        self.periph_search.setClearButtonEnabled(True)
        self.periph_search.textChanged.connect(self._on_search_changed)
        periph_layout.addWidget(self.periph_search)

        # 已选标签区域（带滚动）
        self.tag_scroll = QScrollArea()
        self.tag_scroll.setWidgetResizable(True)
        self.tag_scroll.setMaximumHeight(80)
        self.tag_scroll.setMinimumHeight(36)
        self.tag_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.tag_scroll.setStyleSheet("QScrollArea { background: #FFFFFF; border: 1px solid #E0E0E0; border-radius: 4px; }")

        self.tag_container = QWidget()
        self.tag_flow = QHBoxLayout(self.tag_container)
        self.tag_flow.setContentsMargins(4, 4, 4, 4)
        self.tag_flow.setSpacing(4)
        self.tag_flow.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.tag_flow.addStretch()
        self.tag_scroll.setWidget(self.tag_container)
        periph_layout.addWidget(self.tag_scroll)

        # 已选计数
        self.selected_count_label = QLabel("已选: 0 个外设")
        from ..config.styles import get_style_scheme
        _c = get_style_scheme().colors
        self.selected_count_label.setStyleSheet(f"color: {_c.text_secondary}; font-size: 11px;")
        periph_layout.addWidget(self.selected_count_label)

        # 可添加的外设列表（搜索时显示）
        self.suggest_scroll = QScrollArea()
        self.suggest_scroll.setWidgetResizable(True)
        self.suggest_scroll.setMaximumHeight(100)
        self.suggest_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.suggest_scroll.setStyleSheet("QScrollArea { background: white; border: 1px solid #E0E0E0; border-radius: 4px; }")
        self.suggest_scroll.setVisible(False)

        self.suggest_container = QWidget()
        self.suggest_layout = QVBoxLayout(self.suggest_container)
        self.suggest_layout.setContentsMargins(2, 2, 2, 2)
        self.suggest_layout.setSpacing(2)
        self.suggest_layout.addStretch()
        self.suggest_scroll.setWidget(self.suggest_container)
        periph_layout.addWidget(self.suggest_scroll)

        # 快捷操作按钮行
        action_layout = QHBoxLayout()
        self.select_all_btn = QPushButton(t("button.select_all", default="全选"))
        self.select_all_btn.setFixedWidth(60)
        self.select_all_btn.clicked.connect(self._select_all)
        action_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton(t("button.clear_all", default="清空"))
        self.deselect_all_btn.setFixedWidth(60)
        self.deselect_all_btn.clicked.connect(self._deselect_all)
        action_layout.addWidget(self.deselect_all_btn)

        action_layout.addStretch()
        periph_layout.addLayout(action_layout)

        self.add_form_row(t("label.peripheral") + ":", periph_widget)

        # 描述
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText(t("placeholder.interrupt_description"))
        self.add_form_row(t("label.description") + ":", self.desc_edit)

        # 连接预览刷新信号
        self._connect_preview_signal(self.name_edit)
        self._connect_preview_signal(self.value_spin)
        self._connect_preview_signal(self.desc_edit)

    # === 标签操作方法 ===

    def _create_tag(self, name: str) -> QFrame:
        """创建一个外设标签"""
        tag = QFrame()
        tag.setStyleSheet(self._TAG_STYLE)
        tag.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        tag_layout = QHBoxLayout(tag)
        tag_layout.setContentsMargins(0, 0, 0, 0)
        tag_layout.setSpacing(2)

        label = QLabel(name)
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        tag_layout.addWidget(label)

        close_btn = QPushButton("x")
        close_btn.setFixedSize(16, 16)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close_btn.clicked.connect(lambda checked, n=name: self._remove_tag(n))
        tag_layout.addWidget(close_btn)

        tag.setProperty("periph_name", name)
        return tag

    def _add_tag(self, name: str):
        """添加一个外设标签"""
        if name in self._selected_peripherals:
            return
        self._selected_peripherals.append(name)

        # 插入到 stretch 之前
        tag = self._create_tag(name)
        count = self.tag_flow.count()
        self.tag_flow.insertWidget(count - 1, tag)  # stretch is last item
        self._update_count()
        self._refresh_suggestions()
        self.update_preview()

    def _remove_tag(self, name: str):
        """移除一个外设标签"""
        if name not in self._selected_peripherals:
            return
        self._selected_peripherals.remove(name)

        # 找到并移除对应的 tag widget
        for i in range(self.tag_flow.count()):
            widget = self.tag_flow.itemAt(i).widget()
            if widget and widget.property("periph_name") == name:
                self.tag_flow.removeWidget(widget)
                widget.deleteLater()
                break
        self._update_count()
        self._refresh_suggestions()
        self.update_preview()
        self._update_count()
        self._refresh_suggestions()

    def _update_count(self):
        """更新已选计数"""
        count = len(self._selected_peripherals)
        self.selected_count_label.setText(f"已选: {count} 个外设")

    # === 搜索和建议 ===

    def _on_search_changed(self, text: str):
        """搜索文本变化时刷新建议列表"""
        self._refresh_suggestions()

    def _refresh_suggestions(self):
        """刷新可添加的外设建议列表"""
        filter_text = self.periph_search.text().strip().lower()

        # 清除旧的建议按钮
        while self.suggest_layout.count() > 1:  # 保留最后的 stretch
            item = self.suggest_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # 计算可添加的外设
        available = [
            p for p in self.all_peripherals
            if p not in self._selected_peripherals
            and (not filter_text or filter_text in p.lower())
        ]

        if not available:
            self.suggest_scroll.setVisible(False)
            return

        self.suggest_scroll.setVisible(True)

        for periph_name in available[:15]:
            btn = QPushButton(periph_name)
            btn.setStyleSheet(self._SUGGEST_ITEM_STYLE)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, n=periph_name: self._on_add_periph(n))
            self.suggest_layout.insertWidget(self.suggest_layout.count() - 1, btn)

    def _on_add_periph(self, name: str):
        """点击建议项时添加标签"""
        self._add_tag(name)
        self.periph_search.clear()

    def _select_all(self):
        """全选"""
        for p in self.all_peripherals:
            if p not in self._selected_peripherals:
                self._add_tag(p)

    def _deselect_all(self):
        """清空所有选择"""
        for name in list(self._selected_peripherals):
            self._remove_tag(name)

    # === 数据接口 ===

    def _get_selected_peripherals(self) -> List[str]:
        """获取选中的外设列表"""
        return list(self._selected_peripherals)

    def load_data(self, interrupt: Interrupt):
        """加载数据"""
        if not hasattr(self, 'name_edit'):
            return

        self.name_edit.setText(interrupt.name)
        self.value_spin.setValue(interrupt.value)
        self.desc_edit.setText(interrupt.description)

        # 设置关联外设
        selected = interrupt.peripherals if interrupt.peripherals else (
            [interrupt.peripheral] if interrupt.peripheral else []
        )
        for name in selected:
            self._add_tag(name)

    def validate_input(self):
        """验证输入"""
        name = self.name_edit.text().strip()
        Validator.validate_name(name, t("error.interrupt_name_validation"))

        value = self.value_spin.value()
        Validator.validate_irq_number(value)

        selected = self._get_selected_peripherals()
        if not selected:
            raise ValidationError(t("error.must_select_peripheral"))

    def collect_data(self):
        """收集数据"""
        selected_peripherals = self._get_selected_peripherals()
        self.result_data = {
            "old_name": self.original_name if self.is_edit else "",
            "name": self.name_edit.text().strip(),
            "value": self.value_spin.value(),
            "description": self.desc_edit.text().strip(),
            "peripheral": selected_peripherals[0] if selected_peripherals else "",
            "peripherals": selected_peripherals
        }

    def _generate_preview_xml(self) -> str:
        """生成当前中断编辑状态的 XML 预览"""
        try:
            from ..core.svd_generator import SVDGenerator
            from ..core.data_model import Interrupt
            irq = Interrupt(
                name=self.name_edit.text().strip() or "unnamed",
                value=self.value_spin.value(),
                description=self.desc_edit.text().strip(),
                peripheral=self._selected_peripherals[0] if self._selected_peripherals else "",
                peripherals=list(self._selected_peripherals),
            )
            return SVDGenerator.generate_interrupt_xml(irq)
        except Exception:
            return ""
