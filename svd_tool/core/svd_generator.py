# svd_tool/core/svd_generator.py
from typing import Dict, Any, Optional
from xml.etree import ElementTree as ET
from xml.dom import minidom

from .data_model import DeviceInfo
from .constants import SVD_VERSIONS


class SVDGenerator:
    """SVD文件生成器"""
    
    def __init__(self, device_info: DeviceInfo):
        self.device_info = device_info
        self.indent = "  "
    
    def generate(self, pretty_print: bool = True) -> str:
        """生成SVD XML字符串"""
        # 创建根节点
        root = self._create_root_element()
        
        # 添加设备信息
        self._add_device_info(root)
        
        # 添加CPU信息
        self._add_cpu_info(root)
        
        # 添加标准字段
        self._add_standard_fields(root)
        
        # 添加外设
        self._add_peripherals(root)
        
        # 转换为XML字符串
        xml_str = ET.tostring(root, encoding="utf-8", method="xml")
        
        if pretty_print:
            xml_str = self._pretty_format(xml_str)
        else:
            xml_str = xml_str.decode('utf-8')
        
        return xml_str
    
    def _create_root_element(self) -> ET.Element:
        """创建根节点"""
        schema_version = self.device_info.svd_version
        
        # 检查SVD版本是否支持
        if schema_version not in SVD_VERSIONS:
            schema_version = "1.3"  # 默认使用1.3版本
        
        # 创建根元素，不设置属性
        root = ET.Element("device")
        
        # 根据SVD版本设置正确的schema位置
        if schema_version == "1.1":
            schema_file = "CMSIS-SVD_Schema_1_1.xsd"
        elif schema_version == "1.3":
            schema_file = "CMSIS-SVD_Schema_1_3.xsd"
        else:  # 2.0
            schema_file = "CMSIS-SVD_Schema_2_0.xsd"
        
        # 按照标准顺序设置属性
        root.set("schemaVersion", schema_version)
        root.set("xmlns:xs", "http://www.w3.org/2001/XMLSchema-instance")
        root.set("xs:noNamespaceSchemaLocation", schema_file)
        
        return root
    
    def _add_device_info(self, root: ET.Element):
        """添加设备信息"""
        ET.SubElement(root, "name").text = self.device_info.name
        ET.SubElement(root, "version").text = self.device_info.version
        
        # 如果有描述则添加，否则使用设备名
        if self.device_info.description:
            ET.SubElement(root, "description").text = self.device_info.description
        else:
            ET.SubElement(root, "description").text = self.device_info.name
        
        # 添加厂商信息（如果存在）
        if self.device_info.vendor:
            ET.SubElement(root, "vendor").text = self.device_info.vendor
        
        # 添加版权信息（如果存在）
        if self.device_info.copyright:
            ET.SubElement(root, "copyright").text = self.device_info.copyright
    
    def _add_cpu_info(self, root: ET.Element):
        """添加CPU信息"""
        cpu = self.device_info.cpu
        
        cpu_elem = ET.SubElement(root, "cpu")
        ET.SubElement(cpu_elem, "name").text = cpu.name
        ET.SubElement(cpu_elem, "revision").text = cpu.revision
        ET.SubElement(cpu_elem, "endian").text = cpu.endian
        ET.SubElement(cpu_elem, "mpuPresent").text = "true" if cpu.mpu_present else "false"
        ET.SubElement(cpu_elem, "fpuPresent").text = "true" if cpu.fpu_present else "false"
        ET.SubElement(cpu_elem, "nvicPrioBits").text = str(cpu.nvic_prio_bits)
        ET.SubElement(cpu_elem, "vendorSystickConfig").text = "true" if cpu.vendor_systick_config else "false"
    
    def _add_standard_fields(self, root: ET.Element):
        """添加标准字段"""
        ET.SubElement(root, "addressUnitBits").text = str(self.device_info.address_unit_bits)
        ET.SubElement(root, "width").text = str(self.device_info.width)
        ET.SubElement(root, "size").text = self.device_info.size
        ET.SubElement(root, "resetValue").text = self.device_info.reset_value
        ET.SubElement(root, "resetMask").text = self.device_info.reset_mask
    
    def _add_peripherals(self, root: ET.Element):
        """添加所有外设"""
        peripherals_elem = ET.SubElement(root, "peripherals")
        
        for periph_name, peripheral in self.device_info.peripherals.items():
            periph_elem = self._create_peripheral_element(peripheral)
            if periph_elem:
                peripherals_elem.append(periph_elem)
    
    def _create_peripheral_element(self, peripheral) -> Optional[ET.Element]:
        """创建外设元素"""
        # 设置属性
        attrs = {}
        if peripheral.derived_from:
            attrs["derivedFrom"] = peripheral.derived_from
        
        periph_elem = ET.Element("peripheral", attrs)
        
        # 添加基本信息
        ET.SubElement(periph_elem, "name").text = peripheral.name
        
        
        # 添加显示名称（如果有）
        if peripheral.display_name:
            ET.SubElement(periph_elem, "displayName").text = peripheral.display_name

        ET.SubElement(periph_elem, "description").text = peripheral.description
        ET.SubElement(periph_elem, "groupName").text = peripheral.group_name
        ET.SubElement(periph_elem, "baseAddress").text = peripheral.base_address
        
        # 添加地址块
        addr_block_elem = ET.SubElement(periph_elem, "addressBlock")
        ET.SubElement(addr_block_elem, "offset").text = peripheral.address_block["offset"]
        ET.SubElement(addr_block_elem, "size").text = peripheral.address_block["size"]
        ET.SubElement(addr_block_elem, "usage").text = peripheral.address_block.get("usage", "registers")
        
        # 添加中断
        for interrupt in peripheral.interrupts:
            self._add_interrupt_to_peripheral(periph_elem, interrupt)
        
        # 添加寄存器
        if peripheral.registers:
            registers_elem = ET.SubElement(periph_elem, "registers")
            
            for reg_name, register in peripheral.registers.items():
                reg_elem = self._create_register_element(register)
                if reg_elem:
                    registers_elem.append(reg_elem)
        
        return periph_elem
    
    def _add_interrupt_to_peripheral(self, periph_elem: ET.Element, interrupt: dict):
        """添加中断到外设"""
        irq_elem = ET.SubElement(periph_elem, "interrupt")
        ET.SubElement(irq_elem, "name").text = interrupt["name"]
        
        # 中断描述
        description = interrupt.get("description", "")
        if not description:
            description = f"{interrupt['name']} interrupt"
        ET.SubElement(irq_elem, "description").text = description
        
        ET.SubElement(irq_elem, "value").text = str(interrupt["value"])
    
    def _create_register_element(self, register) -> Optional[ET.Element]:
        """创建寄存器元素"""
        reg_elem = ET.Element("register")
        
        ET.SubElement(reg_elem, "name").text = register.name
        
        # 添加显示名称（如果有）
        if register.display_name:
            ET.SubElement(reg_elem, "displayName").text = register.display_name

        # 使用寄存器名作为描述，如果没有描述的话
        description = register.description or register.name
        ET.SubElement(reg_elem, "description").text = description
        
        ET.SubElement(reg_elem, "addressOffset").text = register.offset
        
        # 设置默认大小为32位
        ET.SubElement(reg_elem, "size").text = register.size or "0x20"
        
        # 仅当access有值时才添加标签
        if register.access :
            ET.SubElement(reg_elem, "access").text = register.access
        
        ET.SubElement(reg_elem, "resetValue").text = register.reset_value or "0x00000000"
        
        # 添加位域
        if register.fields:
            fields_elem = ET.SubElement(reg_elem, "fields")
            
            for field_name, field in register.fields.items():
                field_elem = self._create_field_element(field)
                if field_elem:
                    fields_elem.append(field_elem)
        
        return reg_elem
    
    def _create_field_element(self, field) -> Optional[ET.Element]:
        """创建位域元素"""
        field_elem = ET.Element("field")
        
        ET.SubElement(field_elem, "name").text = field.name
          
        # 添加显示名称（如果有）
        if field.display_name:
            ET.SubElement(field_elem, "displayName").text = field.display_name

        # 使用位域名作为描述，如果没有描述的话
        description = field.description or field.name
        ET.SubElement(field_elem, "description").text = description
        
        ET.SubElement(field_elem, "bitOffset").text = str(field.bit_offset)
        ET.SubElement(field_elem, "bitWidth").text = str(field.bit_width)
        
        # 仅当access有值时才添加标签
        if field.access:
            ET.SubElement(field_elem, "access").text = field.access
        
        # 添加复位值
        if field.reset_value and field.reset_value != "0x0":
            ET.SubElement(field_elem, "resetValue").text = field.reset_value
        
        return field_elem
    
    def _pretty_format(self, xml_bytes: bytes) -> str:
        """美化XML格式，确保格式与原版一致"""
        try:
            # 解析XML
            dom = minidom.parseString(xml_bytes)
            
            # 生成正确的XML头部
            declaration = '<?xml version="1.0" encoding="utf-8" standalone="no"?>\n'
            
            # 生成版权注释
            comment_lines = []
            if hasattr(self.device_info, 'copyright'):
                comment_lines.append(self.device_info.copyright)
            
            if hasattr(self.device_info, 'author') and self.device_info.author:
                comment_lines.append(f"Author: {self.device_info.author}")
            
            if hasattr(self.device_info, 'license') and self.device_info.license:
                comment_lines.append(f"License: {self.device_info.license}")
            
            if comment_lines:
                copyright_comment = f'<!--\n' + '\n'.join(comment_lines) + '\n-->\n'
            else:
                copyright_comment = '<!--\nCopyright (c) 2024 SinOneMicroelectronics.\n-->\n'
            
            # 美化XML内容
            pretty_xml_str = dom.toprettyxml(indent=self.indent)
            
            # 移除原始XML声明
            lines = pretty_xml_str.split('\n')
            clean_lines = []
            
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith('<?xml'):
                    clean_lines.append(line)
            
            # 构建最终XML字符串
            xml_body = '\n'.join(clean_lines)
            
            # 确保device标签格式正确（属性分行显示）
            lines = xml_body.split('\n')
            formatted_lines = []
            
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith('<device'):
                    # 找到device标签行
                    if 'schemaVersion="' in stripped and 'xmlns:xs="' in stripped:
                        # 提取属性
                        import re
                        schema_match = re.search(r'schemaVersion="([^"]+)"', stripped)
                        xmlns_match = re.search(r'xmlns:xs="([^"]+)"', stripped)
                        schema_location_match = re.search(r'xs:noNamespaceSchemaLocation="([^"]+)"', stripped)
                        
                        if schema_match and xmlns_match and schema_location_match:
                            schema_version = schema_match.group(1)
                            xmlns = xmlns_match.group(1)
                            schema_location = schema_location_match.group(1)
                            
                            # 按照标准格式重写device标签
                            formatted_line = f'  <device schemaVersion="{schema_version}"\n    xmlns:xs="{xmlns}"\n    xs:noNamespaceSchemaLocation="{schema_location}">'
                            formatted_lines.append(formatted_line)
                        else:
                            formatted_lines.append(line)
                    else:
                        formatted_lines.append(line)
                else:
                    formatted_lines.append(line)
            
            formatted_body = '\n'.join(formatted_lines)
            
            # 合并所有部分
            final_xml = declaration + copyright_comment + formatted_body
            
            return final_xml
            
        except Exception as e:
            # 如果美化失败，返回原始字符串
            print(f"美化XML失败: {e}")
            return xml_bytes.decode('utf-8')