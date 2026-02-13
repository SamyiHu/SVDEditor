# svd_tool/core/chunked_svd_generator.py
"""
分块SVD生成器 - 支持按需生成单个块或多个块的组合XML
"""
from typing import Dict, Any, Optional, List, Set
from xml.etree import ElementTree as ET
from xml.dom import minidom

from .data_model import DeviceInfo, Peripheral, Register, Field
from .block_manager import BlockManager, BlockType, BlockInfo
from .constants import SVD_VERSIONS


class ChunkedSVDGenerator:
    """分块SVD生成器 - 支持按需生成XML"""
    
    def __init__(self, device_info: DeviceInfo, block_manager: BlockManager):
        """
        初始化分块生成器
        
        Args:
            device_info: 设备信息对象
            block_manager: 块管理器
        """
        self.device_info = device_info
        self.block_manager = block_manager
        self.indent = "  "
    
    def generate_device_header(self) -> str:
        """
        生成设备头部XML（包含设备信息和CPU信息）
        
        Returns:
            设备头部XML字符串
        """
        root = self._create_root_element()
        
        # 添加设备信息
        self._add_device_info(root)
        
        # 添加CPU信息
        self._add_cpu_info(root)
        
        # 添加标准字段
        self._add_standard_fields(root)
        
        # 添加外设容器（空）
        peripherals_elem = ET.SubElement(root, "peripherals")
        
        # 转换为XML字符串
        xml_str = ET.tostring(root, encoding="utf-8", method="xml")
        return self._pretty_format(xml_str)
    
    def generate_peripheral_block(self, peripheral_name: str, include_registers: bool = True) -> str:
        """
        生成单个外设块的XML
        
        Args:
            peripheral_name: 外设名称
            include_registers: 是否包含寄存器
            
        Returns:
            外设块XML字符串
        """
        if peripheral_name not in self.device_info.peripherals:
            return ""
        
        peripheral = self.device_info.peripherals[peripheral_name]
        
        # 创建外设元素
        periph_elem = ET.Element("peripheral")
        
        # 添加外设属性
        ET.SubElement(periph_elem, "name").text = peripheral.name
        ET.SubElement(periph_elem, "baseAddress").text = peripheral.base_address
        
        if peripheral.description:
            ET.SubElement(periph_elem, "description").text = peripheral.description
        
        if peripheral.display_name:
            ET.SubElement(periph_elem, "displayName").text = peripheral.display_name
        
        if peripheral.group_name:
            ET.SubElement(periph_elem, "groupName").text = peripheral.group_name
        
        if peripheral.derived_from:
            periph_elem.set("derivedFrom", peripheral.derived_from)
        
        # 添加地址块
        if peripheral.address_block:
            addr_block_elem = ET.SubElement(periph_elem, "addressBlock")
            ET.SubElement(addr_block_elem, "offset").text = peripheral.address_block.get("offset", "0x0")
            ET.SubElement(addr_block_elem, "size").text = peripheral.address_block.get("size", "0x14")
            ET.SubElement(addr_block_elem, "usage").text = peripheral.address_block.get("usage", "registers")
        
        # 添加寄存器
        if include_registers:
            self._add_registers_to_element(periph_elem, peripheral)
        
        # 添加中断
        self._add_interrupts_to_element(periph_elem, peripheral)
        
        # 转换为XML字符串
        xml_str = ET.tostring(periph_elem, encoding="utf-8", method="xml")
        return self._pretty_format(xml_str)
    
    def generate_register_block(self, peripheral_name: str, register_name: str, include_fields: bool = True) -> str:
        """
        生成单个寄存器块的XML
        
        Args:
            peripheral_name: 外设名称
            register_name: 寄存器名称
            include_fields: 是否包含位域
            
        Returns:
            寄存器块XML字符串
        """
        if peripheral_name not in self.device_info.peripherals:
            return ""
        
        peripheral = self.device_info.peripherals[peripheral_name]
        if register_name not in peripheral.registers:
            return ""
        
        register = peripheral.registers[register_name]
        
        # 创建寄存器元素
        reg_elem = ET.Element("register")
        
        # 添加寄存器属性
        ET.SubElement(reg_elem, "name").text = register.name
        ET.SubElement(reg_elem, "addressOffset").text = register.offset
        
        if register.description:
            ET.SubElement(reg_elem, "description").text = register.description
        
        if register.display_name:
            ET.SubElement(reg_elem, "displayName").text = register.display_name
        
        if register.size:
            ET.SubElement(reg_elem, "size").text = register.size
        
        if register.access:
            ET.SubElement(reg_elem, "access").text = register.access
        
        if register.reset_value:
            ET.SubElement(reg_elem, "resetValue").text = register.reset_value
        
        if register.reset_mask:
            ET.SubElement(reg_elem, "resetMask").text = register.reset_mask
        
        # 添加位域
        if include_fields:
            self._add_fields_to_element(reg_elem, register)
        
        # 转换为XML字符串
        xml_str = ET.tostring(reg_elem, encoding="utf-8", method="xml")
        return self._pretty_format(xml_str)
    
    def generate_field_block(self, peripheral_name: str, register_name: str, field_name: str) -> str:
        """
        生成单个位域块的XML
        
        Args:
            peripheral_name: 外设名称
            register_name: 寄存器名称
            field_name: 位域名称
            
        Returns:
            位域块XML字符串
        """
        if peripheral_name not in self.device_info.peripherals:
            return ""
        
        peripheral = self.device_info.peripherals[peripheral_name]
        if register_name not in peripheral.registers:
            return ""
        
        register = peripheral.registers[register_name]
        if field_name not in register.fields:
            return ""
        
        field = register.fields[field_name]
        
        # 创建位域元素
        field_elem = ET.Element("field")
        
        # 添加位域属性
        ET.SubElement(field_elem, "name").text = field.name
        
        if field.description:
            ET.SubElement(field_elem, "description").text = field.description
        
        if field.display_name:
            ET.SubElement(field_elem, "displayName").text = field.display_name
        
        ET.SubElement(field_elem, "bitOffset").text = str(field.bit_offset)
        ET.SubElement(field_elem, "bitWidth").text = str(field.bit_width)
        
        if field.access:
            ET.SubElement(field_elem, "access").text = field.access
        
        if field.reset_value:
            ET.SubElement(field_elem, "resetValue").text = field.reset_value
        
        # 转换为XML字符串
        xml_str = ET.tostring(field_elem, encoding="utf-8", method="xml")
        return self._pretty_format(xml_str)
    
    def generate_visible_blocks(self) -> str:
        """
        生成所有可见块的组合XML
        
        Returns:
            组合XML字符串
        """
        # 获取可见块
        visible_blocks = self.block_manager.get_visible_blocks()
        
        if not visible_blocks:
            return ""
        
        # 创建根元素
        root = self._create_root_element()
        
        # 添加设备信息
        self._add_device_info(root)
        
        # 添加CPU信息
        self._add_cpu_info(root)
        
        # 添加标准字段
        self._add_standard_fields(root)
        
        # 添加外设容器
        peripherals_elem = ET.SubElement(root, "peripherals")
        
        # 按外设分组添加可见块
        current_peripheral_elem = None
        current_peripheral_name = None
        current_registers_elem = None
        
        for block in visible_blocks:
            if block.block_type == BlockType.PERIPHERAL:
                # 添加外设
                peripheral = self.device_info.peripherals[block.peripheral_name]
                current_peripheral_elem = self._add_peripheral_to_element(peripherals_elem, peripheral)
                current_peripheral_name = block.peripheral_name
                current_registers_elem = None
                
            elif block.block_type == BlockType.REGISTER:
                # 确保外设元素存在
                if current_peripheral_name != block.peripheral_name:
                    peripheral = self.device_info.peripherals[block.peripheral_name]
                    current_peripheral_elem = self._add_peripheral_to_element(peripherals_elem, peripheral)
                    current_peripheral_name = block.peripheral_name
                
                # 添加寄存器
                register = self.device_info.peripherals[block.peripheral_name].registers[block.register_name]
                self._add_register_to_element(current_peripheral_elem, register)
                
            elif block.block_type == BlockType.FIELD:
                # 位域需要包含在寄存器中，这里暂时跳过
                # 位域会在寄存器生成时一起生成
                pass
        
        # 转换为XML字符串
        xml_str = ET.tostring(root, encoding="utf-8", method="xml")
        return self._pretty_format(xml_str)
    
    def generate_blocks_by_keys(self, block_keys: List[str]) -> str:
        """
        根据块key列表生成组合XML
        
        Args:
            block_keys: 块key列表
            
        Returns:
            组合XML字符串
        """
        if not block_keys:
            return ""
        
        # 创建根元素
        root = self._create_root_element()
        
        # 添加设备信息
        self._add_device_info(root)
        
        # 添加CPU信息
        self._add_cpu_info(root)
        
        # 添加标准字段
        self._add_standard_fields(root)
        
        # 添加外设容器
        peripherals_elem = ET.SubElement(root, "peripherals")
        
        # 按外设分组添加块
        current_peripheral_elem = None
        current_peripheral_name = None
        current_registers_elem = None
        
        for block_key in block_keys:
            block = self.block_manager.get_block(block_key)
            if not block:
                continue
            
            if block.block_type == BlockType.PERIPHERAL:
                # 添加外设
                peripheral = self.device_info.peripherals[block.peripheral_name]
                current_peripheral_elem = self._add_peripheral_to_element(peripherals_elem, peripheral)
                current_peripheral_name = block.peripheral_name
                
            elif block.block_type == BlockType.REGISTER:
                # 确保外设元素存在
                if current_peripheral_name != block.peripheral_name:
                    peripheral = self.device_info.peripherals[block.peripheral_name]
                    current_peripheral_elem = self._add_peripheral_to_element(peripherals_elem, peripheral)
                    current_peripheral_name = block.peripheral_name
                
                # 添加寄存器
                register = self.device_info.peripherals[block.peripheral_name].registers[block.register_name]
                self._add_register_to_element(current_peripheral_elem, register)
        
        # 转换为XML字符串
        xml_str = ET.tostring(root, encoding="utf-8", method="xml")
        return self._pretty_format(xml_str)
    
    def _create_root_element(self) -> ET.Element:
        """创建根节点"""
        schema_version = self.device_info.svd_version
        
        # 检查SVD版本是否支持
        if schema_version not in SVD_VERSIONS:
            schema_version = "1.3"  # 默认使用1.3版本
        
        # 创建根元素
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
        
        if self.device_info.description:
            ET.SubElement(root, "description").text = self.device_info.description
        else:
            ET.SubElement(root, "description").text = self.device_info.name
        
        if self.device_info.vendor:
            ET.SubElement(root, "vendor").text = self.device_info.vendor
    
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
        
        if self.device_info.size:
            ET.SubElement(root, "size").text = self.device_info.size
        
        if self.device_info.reset_value:
            ET.SubElement(root, "resetValue").text = self.device_info.reset_value
        
        if self.device_info.reset_mask:
            ET.SubElement(root, "resetMask").text = self.device_info.reset_mask
    
    def _add_peripheral_to_element(self, parent_elem: ET.Element, peripheral: Peripheral) -> ET.Element:
        """添加外设到父元素"""
        periph_elem = ET.SubElement(parent_elem, "peripheral")
        
        ET.SubElement(periph_elem, "name").text = peripheral.name
        ET.SubElement(periph_elem, "baseAddress").text = peripheral.base_address
        
        if peripheral.description:
            ET.SubElement(periph_elem, "description").text = peripheral.description
        
        if peripheral.display_name:
            ET.SubElement(periph_elem, "displayName").text = peripheral.display_name
        
        if peripheral.group_name:
            ET.SubElement(periph_elem, "groupName").text = peripheral.group_name
        
        if peripheral.derived_from:
            periph_elem.set("derivedFrom", peripheral.derived_from)
        
        # 添加地址块
        if peripheral.address_block:
            addr_block_elem = ET.SubElement(periph_elem, "addressBlock")
            ET.SubElement(addr_block_elem, "offset").text = peripheral.address_block.get("offset", "0x0")
            ET.SubElement(addr_block_elem, "size").text = peripheral.address_block.get("size", "0x14")
            ET.SubElement(addr_block_elem, "usage").text = peripheral.address_block.get("usage", "registers")
        
        return periph_elem
    
    def _add_registers_to_element(self, parent_elem: ET.Element, peripheral: Peripheral):
        """添加寄存器到父元素"""
        registers_elem = ET.SubElement(parent_elem, "registers")
        
        # 按偏移地址排序
        reg_names = sorted(peripheral.registers.keys(), 
                          key=lambda x: int(peripheral.registers[x].offset, 0))
        
        for reg_name in reg_names:
            register = peripheral.registers[reg_name]
            self._add_register_to_element(registers_elem, register)
    
    def _add_register_to_element(self, parent_elem: ET.Element, register: Register):
        """添加寄存器到父元素"""
        reg_elem = ET.SubElement(parent_elem, "register")
        
        ET.SubElement(reg_elem, "name").text = register.name
        ET.SubElement(reg_elem, "addressOffset").text = register.offset
        
        if register.description:
            ET.SubElement(reg_elem, "description").text = register.description
        
        if register.display_name:
            ET.SubElement(reg_elem, "displayName").text = register.display_name
        
        if register.size:
            ET.SubElement(reg_elem, "size").text = register.size
        
        if register.access:
            ET.SubElement(reg_elem, "access").text = register.access
        
        if register.reset_value:
            ET.SubElement(reg_elem, "resetValue").text = register.reset_value
        
        if register.reset_mask:
            ET.SubElement(reg_elem, "resetMask").text = register.reset_mask
        
        # 添加位域
        self._add_fields_to_element(reg_elem, register)
    
    def _add_fields_to_element(self, parent_elem: ET.Element, register: Register):
        """添加位域到父元素"""
        fields_elem = ET.SubElement(parent_elem, "fields")
        
        # 按位偏移排序
        field_names = sorted(register.fields.keys(),
                            key=lambda x: register.fields[x].bit_offset)
        
        for field_name in field_names:
            field = register.fields[field_name]
            self._add_field_to_element(fields_elem, field)
    
    def _add_field_to_element(self, parent_elem: ET.Element, field: Field):
        """添加位域到父元素"""
        field_elem = ET.SubElement(parent_elem, "field")
        
        ET.SubElement(field_elem, "name").text = field.name
        
        if field.description:
            ET.SubElement(field_elem, "description").text = field.description
        
        if field.display_name:
            ET.SubElement(field_elem, "displayName").text = field.display_name
        
        ET.SubElement(field_elem, "bitOffset").text = str(field.bit_offset)
        ET.SubElement(field_elem, "bitWidth").text = str(field.bit_width)
        
        if field.access:
            ET.SubElement(field_elem, "access").text = field.access
        
        if field.reset_value:
            ET.SubElement(field_elem, "resetValue").text = field.reset_value
    
    def _add_interrupts_to_element(self, parent_elem: ET.Element, peripheral: Peripheral):
        """添加中断到父元素"""
        for interrupt in peripheral.interrupts:
            interrupt_elem = ET.SubElement(parent_elem, "interrupt")
            
            ET.SubElement(interrupt_elem, "name").text = interrupt.get("name", "")
            ET.SubElement(interrupt_elem, "value").text = str(interrupt.get("value", 0))
            
            if interrupt.get("description"):
                ET.SubElement(interrupt_elem, "description").text = interrupt["description"]
    
    def _pretty_format(self, xml_bytes: bytes) -> str:
        """美化XML格式"""
        try:
            dom = minidom.parseString(xml_bytes)
            return dom.toprettyxml(indent=self.indent, encoding="utf-8").decode('utf-8')
        except Exception:
            return xml_bytes.decode('utf-8')
