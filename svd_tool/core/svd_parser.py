# svd_tool/core/svd_parser.py
import re
from typing import Dict, Any, Optional, List, Tuple
from xml.dom import minidom
from xml.parsers.expat import ExpatError
import warnings

from .data_model import DeviceInfo, Peripheral, Register, Field, Interrupt, CPUInfo
from .validators import Validator, ValidationError
from ..utils.logger import Logger


class SVDParser:
    """SVD文件解析器"""
    
    def __init__(self):
        self.device_info = DeviceInfo()
        self.warnings: List[str] = []
        self.logger = Logger("svd_parser")
        
        # 解析统计
        self.stats = {
            "peripherals": 0,
            "registers": 0,
            "fields": 0,
            "interrupts": 0,
            "errors": 0
        }
    
    def parse_file(self, file_path: str) -> DeviceInfo:
        """解析SVD文件"""
        try:
            self.logger.info(f"开始解析SVD文件: {file_path}")
            
            dom = minidom.parse(file_path)
            device_info = self._parse_dom(dom)
            
            self.logger.info(f"SVD文件解析完成: {self.stats}")
            
            if self.warnings:
                self.logger.warning(f"解析过程中发现 {len(self.warnings)} 条警告")
                for warning in self.warnings[:5]:  # 只显示前5条警告
                    self.logger.warning(warning)
            
            return device_info
            
        except ExpatError as e:
            error_msg = f"XML解析错误: {str(e)}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"解析SVD文件失败: {str(e)}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
    
    def parse_string(self, xml_string: str) -> DeviceInfo:
        """解析SVD字符串"""
        try:
            self.logger.info("开始解析SVD字符串")
            
            dom = minidom.parseString(xml_string)
            device_info = self._parse_dom(dom)
            
            self.logger.info(f"SVD字符串解析完成: {self.stats}")
            
            return device_info
            
        except ExpatError as e:
            error_msg = f"XML解析错误: {str(e)}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"解析SVD字符串失败: {str(e)}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
    
    def _parse_dom(self, dom: minidom.Document) -> DeviceInfo:
        """解析DOM对象"""
        # 重置统计
        self.stats = {k: 0 for k in self.stats.keys()}
        self.warnings.clear()
        
        # 获取根节点
        root = dom.documentElement
        
        # 解析设备基本信息
        self._parse_device_info(root)
        
        # 解析CPU信息
        self._parse_cpu_info(root)
        
        # 解析标准字段
        self._parse_standard_fields(root)
        
        # 解析外设
        self._parse_peripherals(root)
        
        # 收集所有中断到设备信息
        self._collect_interrupts_to_device()
        
        return self.device_info
    
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
    
    def _parse_peripherals(self, device_node):
        """解析所有外设"""
        peripherals_node = device_node.getElementsByTagName("peripherals")
        if not peripherals_node:
            self.warnings.append("未找到外设定义")
            return
        
        periph_nodes = peripherals_node[0].getElementsByTagName("peripheral")
        
        self.logger.info(f"找到 {len(periph_nodes)} 个外设定义")
        
        for i, periph_node in enumerate(periph_nodes):
            try:
                peripheral = self._parse_peripheral(periph_node)
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
    
    def _parse_peripheral(self, periph_node) -> Optional[Peripheral]:
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
        peripheral.description = ""  # 默认值
        for child in periph_node.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.tagName == "description":
                if child.firstChild:
                    peripheral.description = child.firstChild.data.strip()
                break

        # 如果没有描述，使用名称作为默认描述
        if not peripheral.description:
            peripheral.description = peripheral.name
        
        # 显示名称
        peripheral.display_name = ""  # 默认值
    
        # 只查找直接的 displayName 子节点
        for child in periph_node.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.tagName == "displayName":
                if child.firstChild:
                    peripheral.display_name = child.firstChild.data.strip()
                break  # 找到第一个直接子节点就停止
        
        # 或者使用更精确的方法：
        display_name = None
        for child in periph_node.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.tagName == "displayName":
                if child.firstChild:
                    display_name = child.firstChild.data.strip()
                break
    
        # 如果没有找到，保持为空
        peripheral.display_name = display_name if display_name else ""
        
        # 组名
        group_nodes = periph_node.getElementsByTagName("groupName")
        if group_nodes and group_nodes[0].firstChild:
            peripheral.group_name = group_nodes[0].firstChild.data.strip()
        else:
            peripheral.group_name = name  # 默认使用外设名作为组名
        
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
        self._parse_registers_for_peripheral(periph_node, peripheral)
        
        # 解析中断
        self._parse_interrupts_for_peripheral(periph_node, peripheral)
        
        return peripheral
    
    def _parse_registers_for_peripheral(self, periph_node, peripheral: Peripheral):
        """为外设解析寄存器"""
        registers_node = periph_node.getElementsByTagName("registers")
        if not registers_node:
            return
        
        reg_nodes = registers_node[0].getElementsByTagName("register")
        
        self.logger.debug(f"外设 {peripheral.name} 有 {len(reg_nodes)} 个寄存器")
        
        for i, reg_node in enumerate(reg_nodes):
            try:
                register = self._parse_register(reg_node)
                if register:
                    peripheral.registers[register.name] = register
                    self.stats["registers"] += 1
                    
            except Exception as e:
                self.stats["errors"] += 1
                error_msg = f"外设 {peripheral.name} 解析寄存器失败: {str(e)}"
                self.warnings.append(error_msg)
    
    def _parse_register(self, reg_node) -> Optional[Register]:
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
        
        # ----- 关键修复：回归简单直接的解析方式 -----
        
        # 显示名称 - 直接使用getElementsByTagName，不要遍历childNodes
        display_name_nodes = reg_node.getElementsByTagName("displayName")
        if display_name_nodes and display_name_nodes[0].firstChild:
            register.display_name = display_name_nodes[0].firstChild.data.strip()
        else:
            register.display_name = ""
        
        # 描述 - 直接使用getElementsByTagName
        desc_nodes = reg_node.getElementsByTagName("description")
        if desc_nodes and desc_nodes[0].firstChild:
            register.description = desc_nodes[0].firstChild.data.strip()
        else:
            register.description = name  # 使用名称作为默认描述
        
        # 访问权限 - 直接使用getElementsByTagName
        # 直接查找 register 的直接子元素中的 access
        reg_access = None
        
        # 遍历 register 的直接子节点
        for child in reg_node.childNodes:
            if child.nodeType == child.ELEMENT_NODE:
                if child.tagName == "access" and child.firstChild:
                    # 找到 access 标签
                    access_text = child.firstChild.data.strip()
                    if access_text:
                        reg_access = access_text
                    break  # 找到第一个就停止
                elif child.tagName == "fields":
                    # 遇到 fields，说明 register 级的 access 应该在 fields 之前
                    break
        
        # 如果上面没找到，再尝试通用查找（作为后备）
        if not reg_access:
            access_nodes = reg_node.getElementsByTagName("access")
            if access_nodes and access_nodes[0].firstChild:
                # 但需要确认这个 access 不在 fields 内部
                for access_node in access_nodes:
                    # 检查这个 access 节点的父节点是不是 fields
                    parent = access_node.parentNode
                    is_in_fields = False
                    
                    # 向上遍历查找父节点
                    while parent and parent.nodeType == parent.ELEMENT_NODE:
                        if parent.tagName == "fields":
                            is_in_fields = True
                            break
                        if parent == reg_node:
                            # 找到 register 直接父节点
                            break
                        parent = parent.parentNode
                    
                    if not is_in_fields and access_node.firstChild:
                        reg_access = access_node.firstChild.data.strip()
                        break
        
        if reg_access:
            register.access = reg_access
        
        # 复位值
        reset_nodes = reg_node.getElementsByTagName("resetValue")
        if reset_nodes and reset_nodes[0].firstChild:
            register.reset_value = reset_nodes[0].firstChild.data.strip()
        
        # 大小
        size_nodes = reg_node.getElementsByTagName("size")
        if size_nodes and size_nodes[0].firstChild:
            register.size = size_nodes[0].firstChild.data.strip()
        
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
        
        for i, field_node in enumerate(field_nodes):
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
        
        # 创建位域对象
        field = Field(name=name)

        # 位偏移和位宽
        bit_offset_nodes = field_node.getElementsByTagName("bitOffset")
        field.bit_offset = int(bit_offset_nodes[0].firstChild.data.strip()) if (bit_offset_nodes and bit_offset_nodes[0].firstChild) else 0

        bit_width_nodes = field_node.getElementsByTagName("bitWidth")
        field.bit_width = int(bit_width_nodes[0].firstChild.data.strip()) if (bit_width_nodes and bit_width_nodes[0].firstChild) else 1
        
        # 显示名称
        display_name_nodes = field_node.getElementsByTagName("displayName")
        if display_name_nodes and display_name_nodes[0].firstChild:
            field.display_name = display_name_nodes[0].firstChild.data.strip()
        else:
            field.display_name = ""
        
        # 描述
        desc_nodes = field_node.getElementsByTagName("description")
        if desc_nodes and desc_nodes[0].firstChild:
            field.description = desc_nodes[0].firstChild.data.strip()
        else:
            field.description = name
        
        
        # 访问权限
        field_access_nodes = field_node.getElementsByTagName("access")
        if field_access_nodes and field_access_nodes[0].firstChild:
           field.access = field_access_nodes[0].firstChild.data.strip()
        else:
           field.access = None  # 明确设置为None

        # 复位值
        reset_nodes = field_node.getElementsByTagName("resetValue")
        if reset_nodes and reset_nodes[0].firstChild:
            field.reset_value = reset_nodes[0].firstChild.data.strip()
        
        # 枚举值 (如果存在)
        enum_nodes = field_node.getElementsByTagName("enumeratedValues")
        if enum_nodes:
            # 这里可以解析枚举值，但为了简化，我们先跳过
            pass
        
        return field
    
    def _parse_interrupts_for_peripheral(self, periph_node, peripheral: Peripheral):
        """为外设解析中断"""
        irq_nodes = periph_node.getElementsByTagName("interrupt")
        
        for irq_node in irq_nodes:
            try:
                interrupt = self._parse_interrupt(irq_node, peripheral.name)
                if interrupt:
                    peripheral.interrupts.append(interrupt)
                    self.stats["interrupts"] += 1
                    
            except Exception as e:
                self.stats["errors"] += 1
                error_msg = f"解析中断失败: {str(e)}"
                self.warnings.append(error_msg)
    
    def _parse_interrupt(self, irq_node, peripheral_name) -> Optional[Dict[str, Any]]:
        """解析中断"""
        # 中断名称
        name_nodes = irq_node.getElementsByTagName("name")
        if not name_nodes or not name_nodes[0].firstChild:
            self.warnings.append("跳过未命名的中断")
            return None
        
        name = name_nodes[0].firstChild.data.strip()
        
        # 中断号
        value_nodes = irq_node.getElementsByTagName("value")
        if not value_nodes or not value_nodes[0].firstChild:
            self.warnings.append(f"中断 {name} 缺少中断号，跳过")
            return None
        
        try:
            value = int(value_nodes[0].firstChild.data.strip())
        except ValueError:
            self.warnings.append(f"中断 {name} 中断号解析失败: {value_nodes[0].firstChild.data}")
            return None
        
        # 中断描述
        description = ""
        desc_nodes = irq_node.getElementsByTagName("description")
        if desc_nodes and desc_nodes[0].firstChild:
            description = desc_nodes[0].firstChild.data.strip()
        
        return {
            "name": name,
            "value": value,
            "description": description,
            "peripheral": peripheral_name
        }
    
    def _collect_interrupts_to_device(self):
        """收集所有中断到设备信息"""
        for peripheral in self.device_info.peripherals.values():
            for interrupt in peripheral.interrupts:
                # 创建Interrupt对象
                irq = Interrupt(
                    name=interrupt["name"],
                    value=interrupt["value"],
                    description=interrupt.get("description", ""),
                    peripheral=interrupt["peripheral"]
                )
                self.device_info.interrupts[irq.name] = irq
    
    def get_stats(self) -> Dict[str, int]:
        """获取解析统计"""
        return self.stats.copy()
    
    def get_warnings(self) -> List[str]:
        """获取警告列表"""
        return self.warnings.copy()
    
    def clear(self):
        """清除解析器状态"""
        self.device_info = DeviceInfo()
        self.warnings.clear()
        self.stats = {k: 0 for k in self.stats.keys()}


class SVDFastParser(SVDParser):
    """快速SVD解析器（用于大型文件）"""
    
    def _parse_peripherals(self, device_node):
        """快速解析所有外设"""
        peripherals_node = device_node.getElementsByTagName("peripherals")
        if not peripherals_node:
            self.warnings.append("未找到外设定义")
            return
        
        periph_nodes = peripherals_node[0].getElementsByTagName("peripheral")
        
        self.logger.info(f"快速解析 {len(periph_nodes)} 个外设定义")
        
        # 使用批处理提高性能
        batch_size = 50
        for i in range(0, len(periph_nodes), batch_size):
            batch = periph_nodes[i:i + batch_size]
            for periph_node in batch:
                try:
                    peripheral = self._parse_peripheral_fast(periph_node)
                    if peripheral:
                        self.device_info.peripherals[peripheral.name] = peripheral
                        self.stats["peripherals"] += 1
                        
                except Exception as e:
                    self.stats["errors"] += 1
                    # 快速模式下不记录详细错误
            
            # 更新进度
            if (i + batch_size) % 500 == 0:
                self.logger.debug(f"已快速解析 {min(i + batch_size, len(periph_nodes))}/{len(periph_nodes)} 个外设")
    
    def _parse_peripheral_fast(self, periph_node) -> Optional[Peripheral]:
        """快速解析单个外设（不解析位域）"""
        # 外设名称
        name_nodes = periph_node.getElementsByTagName("name")
        if not name_nodes or not name_nodes[0].firstChild:
            return None
        
        name = name_nodes[0].firstChild.data.strip()
        
        # 基地址
        base_addr_nodes = periph_node.getElementsByTagName("baseAddress")
        if not base_addr_nodes or not base_addr_nodes[0].firstChild:
            return None
        
        base_address = base_addr_nodes[0].firstChild.data.strip()
        
        # 创建外设对象
        peripheral = Peripheral(name=name, base_address=base_address)
        
        # 描述
        desc_nodes = periph_node.getElementsByTagName("description")
        if desc_nodes and desc_nodes[0].firstChild:
            peripheral.description = desc_nodes[0].firstChild.data.strip()
        
        # 只解析基本信息，不解析寄存器和位域（加快速度）
        # 在实际使用中，可以根据需要选择是否解析详细信息
        
        return peripheral