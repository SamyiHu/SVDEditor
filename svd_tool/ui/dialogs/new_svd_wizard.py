"""
新建SVD文件向导
使用QWizard引导用户创建新的SVD文件
"""
from PyQt6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QSpinBox, QGroupBox, QTextEdit,
    QPushButton, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt
from ...i18n.i18n import t
from ...config.styles import get_style_scheme


class NewSVDWizard(QWizard):
    """新建SVD文件向导"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("wizard.title", default="新建SVD文件"))
        self.setMinimumSize(600, 500)
        
        # 添加向导页面
        self.addPage(BasicInfoPage(self))
        self.addPage(CPUConfigPage(self))
        self.addPage(DefaultParamsPage(self))
        
        # 设置向导样式
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.HaveHelpButton, False)


class BasicInfoPage(QWizardPage):
    """第1步：基本信息"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle(t("wizard.step1_title", default="基本信息"))
        self.setSubTitle(t("wizard.step1_subtitle", default="填写芯片基本信息"))
        
        layout = QFormLayout(self)
        
        self.chip_name_edit = QLineEdit()
        self.chip_name_edit.setPlaceholderText(t("wizard.chip_name_hint", default="例如: STM32F407"))
        layout.addRow(t("wizard.chip_name", default="芯片名称*:"), self.chip_name_edit)
        
        self.vendor_edit = QLineEdit()
        self.vendor_edit.setPlaceholderText(t("wizard.vendor_hint", default="例如: STMicroelectronics"))
        layout.addRow(t("wizard.vendor", default="厂商:"), self.vendor_edit)
        
        self.version_edit = QLineEdit("1.0")
        layout.addRow(t("wizard.version", default="版本:"), self.version_edit)
        
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.description_edit.setPlaceholderText(t("wizard.description_hint", default="芯片简要描述"))
        layout.addRow(t("wizard.description", default="描述:"), self.description_edit)
        
        self.series_edit = QLineEdit()
        self.series_edit.setPlaceholderText(t("wizard.series_hint", default="例如: STM32F4"))
        layout.addRow(t("wizard.series", default="系列:"), self.series_edit)
        
        self.copyright_edit = QLineEdit()
        self.copyright_edit.setPlaceholderText(t("wizard.copyright_hint", default="例如: Copyright 2025"))
        layout.addRow(t("wizard.copyright_label", default="版权:"), self.copyright_edit)
        
        self.registerField("chip_name*", self.chip_name_edit)
        self.registerField("vendor", self.vendor_edit)
        self.registerField("version", self.version_edit)
        self.registerField("description", self.description_edit, "plainText")
        self.registerField("series", self.series_edit)
        self.registerField("copyright", self.copyright_edit)


class CPUConfigPage(QWizardPage):
    """第2步：CPU配置"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle(t("wizard.step2_title", default="CPU配置"))
        self.setSubTitle(t("wizard.step2_subtitle", default="选择CPU类型和配置"))
        
        layout = QFormLayout(self)
        
        self.cpu_type_combo = QComboBox()
        cpu_types = [
            "CM0", "CM0PLUS", "CM0+", "CM1", "SC000",
            "CM3", "CM23", "CM33", "CM35P", "CM55",
            "CM4", "CM7",
            "SC300", "CA5", "CA7", "CA8", "CA9", "CA15", "CA17", "CA53", "CA57",
            "other"
        ]
        self.cpu_type_combo.addItems(cpu_types)
        self.cpu_type_combo.setCurrentText("CM4")
        layout.addRow(t("wizard.cpu_type", default="CPU类型:"), self.cpu_type_combo)
        
        self.cpu_revision_edit = QLineEdit("r0p0")
        layout.addRow(t("wizard.cpu_revision", default="CPU修订版本:"), self.cpu_revision_edit)
        
        self.endian_combo = QComboBox()
        self.endian_combo.addItems(["little", "big"])
        self.endian_combo.setCurrentText("little")
        layout.addRow(t("wizard.endian", default="字节序:"), self.endian_combo)
        
        self.fpu_present_combo = QComboBox()
        self.fpu_present_combo.addItems(["0 (无FPU)", "1 (有FPU)", "2 (双精度FPU)"])
        self.fpu_present_combo.setCurrentIndex(1)
        layout.addRow(t("wizard.fpu", default="FPU:"), self.fpu_present_combo)
        
        self.mpu_present_combo = QComboBox()
        self.mpu_present_combo.addItems(["0 (无MPU)", "1 (有MPU)"])
        self.mpu_present_combo.setCurrentIndex(1)
        layout.addRow(t("wizard.mpu", default="MPU:"), self.mpu_present_combo)
        
        self.registerField("cpu_type", self.cpu_type_combo, "currentText")
        self.registerField("cpu_revision", self.cpu_revision_edit)
        self.registerField("endian", self.endian_combo, "currentText")


class DefaultParamsPage(QWizardPage):
    """第3步：默认参数"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle(t("wizard.step3_title", default="默认参数"))
        self.setSubTitle(t("wizard.step3_subtitle", default="配置寄存器和位域的默认参数"))
        
        layout = QFormLayout(self)
        
        self.width_combo = QComboBox()
        self.width_combo.addItems(["8", "16", "32", "64"])
        self.width_combo.setCurrentText("32")
        layout.addRow(t("wizard.width", default="寄存器位宽:"), self.width_combo)
        
        self.reset_value_edit = QLineEdit("0x00000000")
        layout.addRow(t("wizard.reset_value", default="默认复位值:"), self.reset_value_edit)
        
        self.reset_mask_edit = QLineEdit("0xFFFFFFFF")
        layout.addRow(t("wizard.reset_mask", default="默认复位掩码:"), self.reset_mask_edit)
        
        self.access_combo = QComboBox()
        self.access_combo.addItems(["read-write", "read-only", "write-only", "read-writeOnce"])
        self.access_combo.setCurrentText("read-write")
        layout.addRow(t("wizard.access", default="默认访问权限:"), self.access_combo)
        
        layout.addRow(QLabel(""))
        
        hint_label = QLabel(t("wizard.hint", default="提示：向导完成后将自动填入基础信息，您可以在编辑器中继续添加外设和寄存器。"))
        hint_label.setWordWrap(True)
        _c = get_style_scheme().colors
        hint_label.setStyleSheet(f"color: {_c.text_secondary}; font-style: italic;")
        layout.addRow(hint_label)
        
        self.registerField("width", self.width_combo, "currentText")
        self.registerField("reset_value", self.reset_value_edit)
        self.registerField("reset_mask", self.reset_mask_edit)
        self.registerField("access", self.access_combo, "currentText")