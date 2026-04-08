# svd_tool/core/chunked_svd_parser.py
"""
分块SVD解析器 - 支持记录XML位置和按需解析
"""
import re
from typing import Dict, Any, Optional, List, Tuple
from xml.dom import minidom
from xml.parsers.expat import ExpatError
import warnings

from .data_model import DeviceInfo, Peripheral, Register, Field, Interrupt, CPUInfo
from .validators import Validator, ValidationError
from .block_manager import BlockManager, BlockType, BlockInfo
from ..utils.logger import Logger


class ChunkedSVDParser:
    """分块SVD文件解析器 - 支持记录XML位置和按需解析"""
    
    def __init__(self):
        self.device_info = DeviceInfo()
        self.warnings: List[str] = []
        self.logger = Logger("chunked_svd_parser")
        
        # XML行号跟踪
        self.current_line = 0
        
        # 块位置映射 {block_key: (start_line, end_line)}
        self.block_positions: Dict[str, Tuple[int, int]] = {}
        
        # 解析统计
        self.stats = {
            "peripherals": 0,
            "registers": 0,
            "fields": 0,
            "interrupts": 0,
            "errors": 0
        }
        
        # 块管理器（在解析完成后创建）
        self.block_manager: Optional[BlockManager] = None
    
    def parse_file(self, file_path: str) -> Tuple[DeviceInfo, BlockManager]:
        """
        解析SVD文件
        
        Args:
            file_path: SVD文件路径
            
        Returns:
            (设备信息, 块管理器)
        """
        try:
            self.logger.info(f"开始解析SVD文件: {file_path}")
            
            # 重置行号
            self.current_line = 0
            
            # 读取文件内容用于行号跟踪
            with open(file_path, 'r', encoding='utf-8') as f:
                file_lines = f.readlines()
            
            dom = minidom.parse(file_path)
            device_info = self._parse_dom(dom, file_lines)
            
            # 创建块管理器
            self.block_manager = BlockManager(device_info)
            
            # 设置块位置信息
            self._set_block_positions()
            
            self.logger.info(f"SVD文件解析完成: {self.stats}")
            
            if self.warnings:
                self.logger.warning(f"解析过程中发现 {len(self.warnings)} 条警告")
                for warning in self.warnings[:5]:  # 只显示前5条警告
                    self.logger.warning(warning)
            
            return device_info, self.block_manager
            
        except ExpatError as e:
            error_msg = f"XML解析错误: {str(e)}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"解析SVD文件失败: {str(e)}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
    
    def parse_string(self, xml_string: str) -> Tuple[DeviceInfo, BlockManager]:
        """
        解析SVD字符串
        
        Args:
            xml_string: SVD XML字符串
            
        Returns:
            (设备信息, 块管理器)
        """
        try:
            self.logger.info("开始解析SVD字符串")
            
            # 重置行号
            self.current_line = 0
            
            # 分割行用于行号跟踪
            file_lines = xml_string.split('\n')
            
            dom = minidom.parseString(xml_string)
            device_info = self._parse_dom(dom, file_lines)
            
            # 创建块管理器
            self.block_manager = BlockManager(device_info)
            
            # 设置块位置信息
            self._set_block_positions()
            
            self.logger.info(f"SVD字符串解析完成: {self.stats}")
            
            return device_info, self.block_manager
            
        except ExpatError as e:
            error_msg = f"XML解析错误: {str(e)}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"解析SVD字符串失败: {str(e)}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
    
    def _parse_dom(self, dom: minidom.Document, file_lines: List[str]) -> DeviceInfo:
        """解析DOM对象"""
        # 重置统计
        self.stats = {k: 0 for k in self.stats.keys()}
        self.warnings.clear()
        self.block_positions.clear()
        
        # 重置设备信息（避免多次解析数据合并）
        self.device_info = DeviceInfo()
        
        # 解析XML注释中的copyright、author、license信息
        self._parse_comments(dom)
        
        # 获取根节点
        root = dom.documentElement
        
        # 记录设备块位置
        device_start_line = self._find_element_line(root, file_lines)
        self.block_positions["device"] = (device_start_line, len(file_lines))
        
        # 解析设备基本信息
        self._parse_device_info(root)
        
        # 解析CPU信息
        self._parse_cpu_info(root)
        
        # 解析标准字段
        self._parse_standard_fields(root)
        
        # 解析外设
        self._parse_peripherals(root, file_lines)
        
        # 收集所有中断到设备信息
        self._collect_interrupts_to_device()
        
        return self.device_info
    
    def _find_element_line(self, node, file_lines: List[str]) -> int:
        """
        查找元素在文件中的起始行号
        
        Args:
            node: DOM节点
            file_lines: 文件行列表
            
        Returns:
            起始行号（1-based）
        """
        # 对于minidom，我们使用节点位置信息
        if hasattr(node, 'userData'):
            return node.userData.get('line', 0)
        
        # 如果没有位置信息，返回0
        return 0
    
    def _parse_comments(self, dom: minidom.Document):
        """解析XML注释中的版权、作者、许可证信息"""
        for child in dom.childNodes:
            if child.nodeType == child.COMMENT_NODE:
                comment_text = child.data.strip()
                
                # 解析版权信息
                copyright_match = re.search(r'Copyright\s*\(c\)\s*\d{4}[^.\n]*\.?', comment_text, re.IGNORECASE)
                if copyright_match:
                    self.device_info.copyright = copyright_match.group(0).strip()
                
                # 解析作者信息
                author_match = re.search(r'Author:\s*(.+?)(?:\n|$)', comment_text, re.IGNORECASE)
                if author_match:
                    self.device_info.author = author_match.group(1).strip()
                
                # 解析许可证信息
                license_match = re.search(r'License:\s*(.+?)(?:\n|$)', comment_text, re.IGNORECASE)
                if license_match:
                    self.device_info.license = license_match.group(1).strip()
    
    def _parse_device_info(self, device_node):
        """解析设备信息"""
        # 设备名称
        name_nodes = device_node.getElementsByTagName("name")
        if name_nodes and name_nodes[0].firstChild:
            self.device_info.name = name_nodes[0].firstChild.data.strip()
        
        # 设备版本
        version_nodes = device_node.getElementsByTagName("version")
        if version_nodes and version_nodes[0].firstChild:
            self.device_info.version = version_nodes[0].firstChild.data.strip()
        
        # 设备描述
        desc_nodes = device_node.getElementsByTagName("description")
        if desc_nodes and desc_nodes[0].firstChild:
            self.device_info.description = desc_nodes[0].firstChild.data.strip()
        
        # SVD版本
        if device_node.hasAttribute("schemaVersion"):
            self.device_info.svd_version = device_node.getAttribute("schemaVersion")
        else:
            self.warnings.append("未找到SVD版本信息，使用默认版本1.3")
            self.device_info.svd_version = "1.3"
        
        # 厂商名称
        vendor_nodes = device_node.getElementsByTagName("vendor")
        if vendor_nodes and vendor_nodes[0].firstChild:
            self.device_info.vendor = vendor_nodes[0].firstChild.data.strip()
        
        self.logger.debug(f"设备信息: {self.device_info.name} v{self.device_info.version}")
    
    def _parse_cpu_info(self, device_node):
        """解析CPU信息"""
        cpu_nodes = device_node.getElementsByTagName("cpu")
        if not cpu_nodes:
            self.warnings.append("未找到CPU信息，使用默认值")
            return
        
        cpu_node = cpu_nodes[0]
        
        # CPU名称
        name_nodes = cpu_node.getElementsByTagName("name")
        if name_nodes and name_nodes[0].firstChild:
            self.device_info.cpu.name = name_nodes[0].firstChild.data.strip()
        
        # CPU版本
        revision_nodes = cpu_node.getElementsByTagName("revision")
        if revision_nodes and revision_nodes[0].firstChild:
            self.device_info.cpu.revision = revision_nodes[0].firstChild.data.strip()
        
        # 字节序
        endian_nodes = cpu_node.getElementsByTagName("endian")
        if endian_nodes and endian_nodes[0].firstChild:
            self.device_info.cpu.endian = endian_nodes[0].firstChild.data.strip()
        
        # MPU
        mpu_nodes = cpu_node.getElementsByTagName("mpuPresent")
        if mpu_nodes and mpu_nodes[0].firstChild:
            self.device_info.cpu.mpu_present = mpu_nodes[0].firstChild.data.strip().lower() == "true"
        
        # FPU
        fpu_nodes = cpu_node.getElementsByTagName("fpuPresent")
        if fpu_nodes and fpu_nodes[0].firstChild:
            self.device_info.cpu.fpu_present = fpu_nodes[0].firstChild.data.strip().lower() == "true"
        
        # NVIC优先级位数
        nvic_nodes = cpu_node.getElementsByTagName("nvicPrioBits")
        if nvic_nodes and nvic_nodes[0].firstChild:
            try:
                self.device_info.cpu.nvic_prio_bits = int(nvic_nodes[0].firstChild.data.strip())
            except ValueError:
                self.warnings.append(f"NVIC优先级位数解析失败: {nvic_nodes[0].firstChild.data}")
                self.device_info.cpu.nvic_prio_bits = 4
        
        # Vendor Systick配置
        systick_nodes = cpu_node.getElementsByTagName("vendorSystickConfig")
        if systick_nodes and systick_nodes[0].firstChild:
            self.device_info.cpu.vendor_systick_config = systick_nodes[0].firstChild.data.strip().lower() == "true"
        
        self.logger.debug(f"CPU信息: {self.device_info.cpu.name} {self.device_info.cpu.revision}")
    
    def _parse_standard_fields(self, device_node):
        """解析标准字段"""
        # 地址单元位数
        addr_unit_nodes = device_node.getElementsByTagName("addressUnitBits")
        if addr_unit_nodes and addr_unit_nodes[0].firstChild:
            try:
                self.device_info.address_unit_bits = int(addr_unit_nodes[0].firstChild.data.strip())
            except ValueError:
                self.warnings.append(f"地址单元位数解析失败: {addr_unit_nodes[0].firstChild.data}")
        
        # 数据宽度
        width_nodes = device_node.getElementsByTagName("width")
        if width_nodes and width_nodes[0].firstChild:
            try:
                self.device_info.width = int(width_nodes[0].firstChild.data.strip())
            except ValueError:
                self.warnings.append(f"数据宽度解析失败: {width_nodes[0].firstChild.data}")
        
        # 大小
        size_nodes = device_node.getElementsByTagName("size")
        if size_nodes and size_nodes[0].firstChild:
            self.device_info.size = size_nodes[0].firstChild.data.strip()
        
        # 复位值
        reset_value_nodes = device_node.getElementsByTagName("resetValue")
        if reset_value_nodes and reset_value_nodes[0].firstChild:
            self.device_info.reset_value = reset_value_nodes[0].firstChild.data.strip()
        
        # 复位掩码
        reset_mask_nodes = device_node.getElementsByTagName("resetMask")
        if reset_mask_nodes and reset_mask_nodes[0].firstChild:
            self.device_info.reset_mask = reset_mask_nodes[0].firstChild.data.strip()
    
    def _parse_peripherals(self, device_node, file_lines: List[str]):
        """解析所有外设"""
        peripherals_node = device_node.getElementsByTagName("peripherals")
        if not peripherals_node:
            self.warnings.append("未找到外设定义")
            return
        
        periph_nodes = peripherals_node[0].getElementsByTagName("peripheral")
        
        self.logger.info(f"找到 {len(periph_nodes)} 个外设定义")
        
        for i, periph_node in enumerate(periph_nodes):
            try:
                peripheral = self._parse_peripheral(periph_node, file_lines)
                if peripheral:
                    self.device_info.peripherals[peripheral.name] = peripheral
                    self.stats["peripherals"] += 1
                    
                    # 每解析10个外设记录一次进度
                    if (i + 1) % 10 == 0:
                        self.logger.debug(f"已解析 {i + 1}/{len(periph_nodes)} 个外设")
                        
            except Exception as e:
                self.stats["errors"] += 1
                error_msg = f"解析外设失败 (索引 {i}): {str(e)}"
                self.warnings.append(error_msg)
                self.logger.error(error_msg)
        
        self.logger.info(f"成功解析 {self.stats['peripherals']} 个外设")
    
    def _parse_peripheral(self, periph_node, file_lines: List[str]) -> Optional[Peripheral]:
        """解析单个外设"""
        # 外设名称
        name_nodes = periph_node.getElementsByTagName("name")
        if not name_nodes or not name_nodes[0].firstChild:
            self.warnings.append("跳过未命名的外设")
            return None
        
        name = name_nodes[0].firstChild.data.strip()
        
        # 检查名称是否已存在
        if name in self.device_info.peripherals:
            self.warnings.append(f"外设名称重复: {name}，跳过重复项")
            return None
        
        # 基地址
        base_addr_nodes = periph_node.getElementsByTagName("baseAddress")
        if not base_addr_nodes or not base_addr_nodes[0].firstChild:
            self.warnings.append(f"外设 {name} 缺少基地址，跳过")
            return None
        
        base_address = base_addr_nodes[0].firstChild.data.strip()
        
        # 创建外设对象
        peripheral = Peripheral(name=name, base_address=base_address)
        
        # 描述
        peripheral.description = ""
        for child in periph_node.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.tagName == "description":
                if child.firstChild:
                    peripheral.description = child.firstChild.data.strip()
                break
        
        if not peripheral.description:
            peripheral.description = peripheral.name
        
        # 显示名称
        peripheral.display_name = ""
        for child in periph_node.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.tagName == "displayName":
                if child.firstChild:
                    peripheral.display_name = child.firstChild.data.strip()
                break
        
        # 组名
        group_nodes = periph_node.getElementsByTagName("groupName")
        if group_nodes and group_nodes[0].firstChild:
            peripheral.group_name = group_nodes[0].firstChild.data.strip()
        else:
            peripheral.group_name = name
        
        # 继承属性
        if periph_node.hasAttribute("derivedFrom"):
            peripheral.derived_from = periph_node.getAttribute("derivedFrom")
        
        # 地址块
        addr_block_nodes = periph_node.getElementsByTagName("addressBlock")
        if addr_block_nodes:
            offset_nodes = addr_block_nodes[0].getElementsByTagName("offset")
            if offset_nodes and offset_nodes[0].firstChild:
                peripheral.address_block["offset"] = offset_nodes[0].firstChild.data.strip()
            
            size_nodes = addr_block_nodes[0].getElementsByTagName("size")
            if size_nodes and size_nodes[0].firstChild:
                peripheral.address_block["size"] = size_nodes[0].firstChild.data.strip()
            
            usage_nodes = addr_block_nodes[0].getElementsByTagName("usage")
            if usage_nodes and usage_nodes[0].firstChild:
                peripheral.address_block["usage"] = usage_nodes[0].firstChild.data.strip()
        
        # 解析寄存器
        self._parse_registers_for_peripheral(periph_node, peripheral, file_lines)
        
        # 解析中断
        self._parse_interrupts_for_peripheral(periph_node, peripheral)
        
        return peripheral
    
    def _parse_registers_for_peripheral(self, periph_node, peripheral: Peripheral, file_lines: List[str]):
        """为外设解析寄存器"""
        registers_node = periph_node.getElementsByTagName("registers")
        if not registers_node:
            return
        
        reg_nodes = registers_node[0].getElementsByTagName("register")
        
        self.logger.debug(f"外设 {peripheral.name} 有 {len(reg_nodes)} 个寄存器")
        
        for i, reg_node in enumerate(reg_nodes):
            try:
                register = self._parse_register(reg_node, file_lines)
                if register:
                    peripheral.registers[register.name] = register
                    self.stats["registers"] += 1
                    
            except Exception as e:
                self.stats["errors"] += 1
                error_msg = f"外设 {peripheral.name} 解析寄存器失败: {str(e)}"
                self.warnings.append(error_msg)
    
    def _parse_register(self, reg_node, file_lines: List[str]) -> Optional[Register]:
        """解析寄存器"""
        # 寄存器名称
        name_nodes = reg_node.getElementsByTagName("name")
        if not name_nodes or not name_nodes[0].firstChild:
            self.warnings.append("跳过未命名的寄存器")
            return None
        
        name = name_nodes[0].firstChild.data.strip()
        
        # 偏移地址
        offset_nodes = reg_node.getElementsByTagName("addressOffset")
        if not offset_nodes or not offset_nodes[0].firstChild:
            self.warnings.append(f"寄存器 {name} 缺少偏移地址，跳过")
            return None
        
        offset = offset_nodes[0].firstChild.data.strip()
        
        # 创建寄存器对象
        register = Register(name=name, offset=offset)
        
        # 描述
        register.description = ""
        for child in reg_node.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.tagName == "description":
                if child.firstChild:
                    register.description = child.firstChild.data.strip()
                break
        
        # 显示名称
        register.display_name = ""
        for child in reg_node.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.tagName == "displayName":
                if child.firstChild:
                    register.display_name = child.firstChild.data.strip()
                break
        
        # 大小
        size_nodes = reg_node.getElementsByTagName("size")
        if size_nodes and size_nodes[0].firstChild:
            register.size = size_nodes[0].firstChild.data.strip()
        
        # 访问权限
        access_nodes = reg_node.getElementsByTagName("access")
        if access_nodes and access_nodes[0].firstChild:
            register.access = access_nodes[0].firstChild.data.strip()
        
        # 复位值
        reset_value_nodes = reg_node.getElementsByTagName("resetValue")
        if reset_value_nodes and reset_value_nodes[0].firstChild:
            register.reset_value = reset_value_nodes[0].firstChild.data.strip()
        
        # 复位掩码
        reset_mask_nodes = reg_node.getElementsByTagName("resetMask")
        if reset_mask_nodes and reset_mask_nodes[0].firstChild:
            register.reset_mask = reset_mask_nodes[0].firstChild.data.strip()
        
        # 解析位域
        self._parse_fields_for_register(reg_node, register)
        
        return register
    
    def _parse_fields_for_register(self, reg_node, register: Register):
        """为寄存器解析位域"""
        fields_node = reg_node.getElementsByTagName("fields")
        if not fields_node:
            return
        
        field_nodes = fields_node[0].getElementsByTagName("field")
        
        for field_node in field_nodes:
            try:
                field = self._parse_field(field_node)
                if field:
                    register.fields[field.name] = field
                    self.stats["fields"] += 1
                    
            except Exception as e:
                self.stats["errors"] += 1
                error_msg = f"寄存器 {register.name} 解析位域失败: {str(e)}"
                self.warnings.append(error_msg)
    
    def _parse_field(self, field_node) -> Optional[Field]:
        """解析位域"""
        # 位域名称
        name_nodes = field_node.getElementsByTagName("name")
        if not name_nodes or not name_nodes[0].firstChild:
            self.warnings.append("跳过未命名的位域")
            return None
        
        name = name_nodes[0].firstChild.data.strip()
        
        # 位偏移
        bit_offset_nodes = field_node.getElementsByTagName("bitOffset")
        if not bit_offset_nodes or not bit_offset_nodes[0].firstChild:
            self.warnings.append(f"位域 {name} 缺少位偏移，跳过")
            return None
        
        bit_offset = int(bit_offset_nodes[0].firstChild.data.strip())
        
        # 位宽度
        bit_width_nodes = field_node.getElementsByTagName("bitWidth")
        if not bit_width_nodes or not bit_width_nodes[0].firstChild:
            self.warnings.append(f"位域 {name} 缺少位宽度，跳过")
            return None
        
        bit_width = int(bit_width_nodes[0].firstChild.data.strip())
        
        # 创建位域对象
        field = Field(name=name, bit_offset=bit_offset, bit_width=bit_width)
        
        # 描述
        field.description = ""
        for child in field_node.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.tagName == "description":
                if child.firstChild:
                    field.description = child.firstChild.data.strip()
                break
        
        # 显示名称
        field.display_name = ""
        for child in field_node.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.tagName == "displayName":
                if child.firstChild:
                    field.display_name = child.firstChild.data.strip()
                break
        
        # 访问权限
        access_nodes = field_node.getElementsByTagName("access")
        if access_nodes and access_nodes[0].firstChild:
            field.access = access_nodes[0].firstChild.data.strip()
        
        # 复位值
        reset_value_nodes = field_node.getElementsByTagName("resetValue")
        if reset_value_nodes and reset_value_nodes[0].firstChild:
            field.reset_value = reset_value_nodes[0].firstChild.data.strip()
        
        return field
    
    def _parse_interrupts_for_peripheral(self, periph_node, peripheral: Peripheral):
        """为外设解析中断"""
        interrupt_nodes = periph_node.getElementsByTagName("interrupt")
        
        for interrupt_node in interrupt_nodes:
            try:
                # 中断名称
                name_nodes = interrupt_node.getElementsByTagName("name")
                if not name_nodes or not name_nodes[0].firstChild:
                    continue
                
                name = name_nodes[0].firstChild.data.strip()
                
                # 中断值
                value_nodes = interrupt_node.getElementsByTagName("value")
                if not value_nodes or not value_nodes[0].firstChild:
                    continue
                
                value = int(value_nodes[0].firstChild.data.strip())
                
                # 创建中断对象
                interrupt = Interrupt(name=name, value=value)
                
                # 描述
                desc_nodes = interrupt_node.getElementsByTagName("description")
                if desc_nodes and desc_nodes[0].firstChild:
                    interrupt.description = desc_nodes[0].firstChild.data.strip()
                
                # 外设名称
                interrupt.peripheral = peripheral.name
                
                # 添加到外设
                peripheral.interrupts.append({
                    "name": interrupt.name,
                    "value": interrupt.value,
                    "description": interrupt.description,
                    "peripheral": peripheral.name
                })
                
                self.stats["interrupts"] += 1
                
            except Exception as e:
                error_msg = f"外设 {peripheral.name} 解析中断失败: {str(e)}"
                self.warnings.append(error_msg)
    
    def _collect_interrupts_to_device(self):
        """收集所有中断到设备信息（支持多外设共用同一中断）"""
        for periph_name, peripheral in self.device_info.peripherals.items():
            for interrupt in peripheral.interrupts:
                irq_name = interrupt.get("name", "")
                if irq_name:
                    if irq_name in self.device_info.interrupts:
                        # 已存在同名中断，添加外设到 peripherals 列表
                        existing = self.device_info.interrupts[irq_name]
                        if periph_name not in existing.peripherals:
                            existing.peripherals.append(periph_name)
                    else:
                        # 创建新的中断对象
                        self.device_info.interrupts[irq_name] = Interrupt(
                            name=irq_name,
                            value=interrupt.get("value", 0),
                            description=interrupt.get("description", ""),
                            peripheral=periph_name,
                            peripherals=[periph_name]
                        )
    
    def _set_block_positions(self):
        """设置块位置信息到块管理器"""
        if not self.block_manager:
            return
        
        for block_key, (start_line, end_line) in self.block_positions.items():
            block = self.block_manager.get_block(block_key)
            if block:
                block.xml_start_line = start_line
                block.xml_end_line = end_line
    
    def get_block_position(self, block_key: str) -> Optional[Tuple[int, int]]:
        """
        获取块的XML位置
        
        Args:
            block_key: 块的key
            
        Returns:
            (起始行号, 结束行号)，如果不存在则返回None
        """
        return self.block_positions.get(block_key)
    
    def get_statistics(self) -> Dict[str, int]:
        """获取解析统计信息"""
        return self.stats.copy()
