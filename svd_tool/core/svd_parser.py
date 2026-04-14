# svd_tool/core/svd_parser.py
import re
from copy import deepcopy
from typing import Dict, Any, Optional, List, Tuple
from xml.dom import minidom
from xml.parsers.expat import ExpatError
import warnings

from .data_model import DeviceInfo, Peripheral, Register, Field, Interrupt, CPUInfo, Cluster
from .validators import Validator, ValidationError
from ..utils.logger import Logger


class SVDParser:
    """SVD文件解析器"""
    
    @staticmethod
    def _get_direct_child(parent_node, tag_name: str):
        """获取直接子节点中指定标签名的第一个元素（非递归）"""
        for child in parent_node.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.tagName == tag_name:
                return child
        return None
    
    def __init__(self):
        self.device_info = DeviceInfo()
        self.warnings: List[str] = []
        self.logger = Logger("svd_parser")
        
        # XML行号跟踪（用于分块加载）
        self.current_line = 0
        
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
            
            # 重置行号
            self.current_line = 0
            
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
        
        # 重置设备信息（避免多次解析数据合并）
        self.device_info = DeviceInfo()
        
        # 解析XML注释中的copyright、author、license信息
        self._parse_comments(dom)
        
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
        
        # 解析外设继承关系
        self._resolve_inheritance()
        
        # 收集所有中断到设备信息
        self._collect_interrupts_to_device()
        
        return self.device_info
    
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
        # 设备名称 - 使用直接子节点搜索
        name_node = self._get_direct_child(device_node, "name")
        if name_node and name_node.firstChild:
            self.device_info.name = name_node.firstChild.data.strip()
        
        # 设备版本
        version_node = self._get_direct_child(device_node, "version")
        if version_node and version_node.firstChild:
            self.device_info.version = version_node.firstChild.data.strip()
        
        # 设备描述
        desc_node = self._get_direct_child(device_node, "description")
        if desc_node and desc_node.firstChild:
            self.device_info.description = desc_node.firstChild.data.strip()
        
        # SVD版本
        if device_node.hasAttribute("schemaVersion"):
            self.device_info.svd_version = device_node.getAttribute("schemaVersion")
        else:
            self.warnings.append("未找到SVD版本信息，使用默认版本1.3")
            self.device_info.svd_version = "1.3"
        
        # 厂商名称
        vendor_node = self._get_direct_child(device_node, "vendor")
        if vendor_node and vendor_node.firstChild:
            self.device_info.vendor = vendor_node.firstChild.data.strip()
        
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
        """解析标准字段 - 使用直接子节点搜索避免匹配到嵌套的同名标签"""
        # 地址单元位数
        addr_unit_node = self._get_direct_child(device_node, "addressUnitBits")
        if addr_unit_node and addr_unit_node.firstChild:
            try:
                self.device_info.address_unit_bits = int(addr_unit_node.firstChild.data.strip())
            except ValueError:
                self.warnings.append(f"地址单元位数解析失败: {addr_unit_node.firstChild.data}")
        
        # 数据宽度
        width_node = self._get_direct_child(device_node, "width")
        if width_node and width_node.firstChild:
            try:
                self.device_info.width = int(width_node.firstChild.data.strip())
            except ValueError:
                self.warnings.append(f"数据宽度解析失败: {width_node.firstChild.data}")
        
        # 大小
        size_node = self._get_direct_child(device_node, "size")
        if size_node and size_node.firstChild:
            self.device_info.size = size_node.firstChild.data.strip()
        
        # 复位值
        reset_value_node = self._get_direct_child(device_node, "resetValue")
        if reset_value_node and reset_value_node.firstChild:
            self.device_info.reset_value = reset_value_node.firstChild.data.strip()
        
        # 复位掩码
        reset_mask_node = self._get_direct_child(device_node, "resetMask")
        if reset_mask_node and reset_mask_node.firstChild:
            self.device_info.reset_mask = reset_mask_node.firstChild.data.strip()
    
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
        
        # 描述 - 只查找直接子节点
        peripheral.description = ""  # 默认值
        for child in periph_node.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.tagName == "description":
                if child.firstChild:
                    peripheral.description = child.firstChild.data.strip()
                break
        
        # 如果没有描述，使用名称作为默认描述
        if not peripheral.description:
            peripheral.description = peripheral.name
        
        # 显示名称 - 只查找直接子节点
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
            peripheral.group_name = name  # 默认使用外设名作为组名
        
        # 继承属性
        if periph_node.hasAttribute("derivedFrom"):
            peripheral.derived_from = periph_node.getAttribute("derivedFrom")
        else:
            peripheral.derived_from = ""  # 确保设置为空字符串
        
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
        """为外设解析寄存器和簇"""
        registers_node = periph_node.getElementsByTagName("registers")
        if not registers_node:
            return
        
        # 只解析直接子节点中的 register（不包含 cluster 内部的寄存器）
        reg_nodes = []
        for child in registers_node[0].childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.tagName == "register":
                reg_nodes.append(child)
        
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
        
        # 解析寄存器簇 (cluster)
        self._parse_clusters_for_node(registers_node[0], peripheral.clusters, peripheral.name)

    def _parse_clusters_for_node(self, parent_node, clusters_dict: dict, parent_name: str):
        """解析 cluster 元素"""
        if not parent_node:
            return
        cluster_nodes = parent_node.getElementsByTagName("cluster")
        # 只取直接子节点中的 cluster（避免递归匹配嵌套簇内的簇）
        direct_clusters = []
        for child in parent_node.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.tagName == "cluster":
                direct_clusters.append(child)

        for cl_node in direct_clusters:
            try:
                cluster = self._parse_cluster(cl_node)
                if cluster:
                    clusters_dict[cluster.name] = cluster
                    self.stats["registers"] += len(cluster.registers)
                    self.logger.debug(f"解析簇 {cluster.name} ({len(cluster.registers)} 个寄存器)")
            except Exception as e:
                self.stats["errors"] += 1
                self.warnings.append(f"解析簇失败 ({parent_name}): {str(e)}")

    def _parse_cluster(self, cl_node) -> Optional[Cluster]:
        """解析单个 cluster 元素"""
        name_nodes = cl_node.getElementsByTagName("name")
        if not name_nodes or not name_nodes[0].firstChild:
            self.warnings.append("跳过未命名的 cluster")
            return None

        name = name_nodes[0].firstChild.data.strip()

        # 地址偏移
        offset = "0x0"
        offset_nodes = cl_node.getElementsByTagName("addressOffset")
        if offset_nodes and offset_nodes[0].firstChild:
            offset = offset_nodes[0].firstChild.data.strip()

        cluster = Cluster(name=name, address_offset=offset)

        # 描述
        desc_nodes = cl_node.getElementsByTagName("description")
        if desc_nodes and desc_nodes[0].firstChild:
            cluster.description = desc_nodes[0].firstChild.data.strip()
        else:
            cluster.description = name

        # 显示名称
        dn_nodes = cl_node.getElementsByTagName("displayName")
        if dn_nodes and dn_nodes[0].firstChild:
            cluster.display_name = dn_nodes[0].firstChild.data.strip()

        # size / access / resetValue / resetMask
        size_nodes = cl_node.getElementsByTagName("size")
        if size_nodes and size_nodes[0].firstChild:
            cluster.size = size_nodes[0].firstChild.data.strip()

        for child in cl_node.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.tagName == "access" and child.firstChild:
                cluster.access = child.firstChild.data.strip()
                break

        rv_nodes = cl_node.getElementsByTagName("resetValue")
        if rv_nodes and rv_nodes[0].firstChild:
            cluster.reset_value = rv_nodes[0].firstChild.data.strip()

        rm_nodes = cl_node.getElementsByTagName("resetMask")
        if rm_nodes and rm_nodes[0].firstChild:
            cluster.reset_mask = rm_nodes[0].firstChild.data.strip()

        # dim 信息
        dim_nodes = cl_node.getElementsByTagName("dim")
        if dim_nodes and dim_nodes[0].firstChild:
            try:
                cluster.dim = int(dim_nodes[0].firstChild.data.strip())
            except ValueError:
                pass

        dim_inc_nodes = cl_node.getElementsByTagName("dimIncrement")
        if dim_inc_nodes and dim_inc_nodes[0].firstChild:
            cluster.dim_increment = dim_inc_nodes[0].firstChild.data.strip()

        dim_idx_nodes = cl_node.getElementsByTagName("dimIndex")
        if dim_idx_nodes and dim_idx_nodes[0].firstChild:
            idx_text = dim_idx_nodes[0].firstChild.data.strip()
            if "-" in idx_text:
                try:
                    start, end = idx_text.split("-")
                    cluster.dim_index = [str(i) for i in range(int(start), int(end) + 1)]
                except ValueError:
                    cluster.dim_index = idx_text.split(",")
            else:
                cluster.dim_index = idx_text.split(",")

        # derivedFrom
        if cl_node.hasAttribute("derivedFrom"):
            cluster.derived_from = cl_node.getAttribute("derivedFrom")

        # 解析簇内的寄存器
        for child in cl_node.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.tagName == "register":
                try:
                    reg = self._parse_register(child)
                    if reg:
                        cluster.registers[reg.name] = reg
                except Exception as e:
                    self.warnings.append(f"簇 {name} 解析寄存器失败: {str(e)}")

        # 递归解析嵌套簇
        for child in cl_node.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.tagName == "cluster":
                try:
                    sub = self._parse_cluster(child)
                    if sub:
                        cluster.clusters[sub.name] = sub
                except Exception as e:
                    self.warnings.append(f"簇 {name} 解析子簇失败: {str(e)}")

        return cluster
    
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

        # 寄存器级 derivedFrom
        if hasattr(reg_node, 'hasAttribute') and reg_node.hasAttribute("derivedFrom"):
            register.derived_from = reg_node.getAttribute("derivedFrom")
        
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
            field.enumerated_values = self._parse_enumerated_values(enum_nodes[0])
        
        return field
    
    def _parse_enumerated_values(self, enum_values_node) -> List[Dict[str, str]]:
        """解析枚举值"""
        result = []
        enum_value_nodes = enum_values_node.getElementsByTagName("enumeratedValue")
        for ev_node in enum_value_nodes:
            try:
                enum_entry = {}
                name_nodes = ev_node.getElementsByTagName("name")
                if name_nodes and name_nodes[0].firstChild:
                    enum_entry["name"] = name_nodes[0].firstChild.data.strip()
                else:
                    continue
                
                desc_nodes = ev_node.getElementsByTagName("description")
                if desc_nodes and desc_nodes[0].firstChild:
                    enum_entry["description"] = desc_nodes[0].firstChild.data.strip()
                
                value_nodes = ev_node.getElementsByTagName("value")
                if value_nodes and value_nodes[0].firstChild:
                    enum_entry["value"] = value_nodes[0].firstChild.data.strip()
                
                result.append(enum_entry)
            except Exception as e:
                self.warnings.append(f"解析枚举值失败: {str(e)}")
        return result
    
    def _resolve_inheritance(self):
        """解析外设继承关系（derivedFrom）— 完整版
        
        CMSIS-SVD 继承规则:
        1. 外设级 derivedFrom: 继承所有未定义的属性、寄存器、簇、中断
        2. 寄存器级 derivedFrom: 继承单个寄存器的未定义属性和位域
        3. 簇级 derivedFrom: 继承簇的未定义属性、寄存器和子簇
        4. 支持多级继承链（A→B→C）
        5. 支持循环引用检测
        """
        # ---- 第一阶段：外设级继承 ----
        self._resolve_peripheral_inheritance()

        # ---- 第二阶段：寄存器级 derivedFrom（外设内部） ----
        for peripheral in self.device_info.peripherals.values():
            self._resolve_register_inheritance(peripheral)
            # 簇内寄存器继承
            for cluster in peripheral.clusters.values():
                self._resolve_cluster_inheritance(cluster, peripheral)

    def _resolve_peripheral_inheritance(self):
        """解析外设级 derivedFrom 继承"""
        max_iterations = 10
        for _ in range(max_iterations):
            resolved_any = False
            for name, peripheral in list(self.device_info.peripherals.items()):
                if not peripheral.derived_from:
                    continue

                parent_name = peripheral.derived_from

                # 循环引用检测
                if self._has_circular_inheritance(name, parent_name):
                    self.warnings.append(
                        f"检测到循环继承: {name} → {parent_name}，跳过"
                    )
                    peripheral.derived_from = ""
                    continue

                if parent_name not in self.device_info.peripherals:
                    self.warnings.append(
                        f"外设 {name} 的继承源 {parent_name} 不存在"
                    )
                    peripheral.derived_from = ""
                    continue

                parent = self.device_info.peripherals[parent_name]

                # 如果父级也有 derivedFrom 且尚未解析，先跳过
                if parent.derived_from:
                    continue

                # 继承未定义的属性
                changed = False

                # 基本属性继承
                for attr in ['display_name', 'group_name']:
                    if not getattr(peripheral, attr, None) and getattr(parent, attr, None):
                        setattr(peripheral, attr, getattr(parent, attr))
                        changed = True

                # 描述继承
                if (not peripheral.description or peripheral.description == peripheral.name):
                    if parent.description and parent.description != parent.name:
                        peripheral.description = parent.description
                        changed = True

                # 地址块继承 — 利用 Peripheral 默认实例判断是否未被修改
                _default_ab = Peripheral(name="__default__", base_address="0x0").address_block
                if peripheral.address_block == _default_ab:
                    if parent.address_block:
                        peripheral.address_block = dict(parent.address_block)
                        changed = True

                # 寄存器继承（只在外设没有自己的寄存器时）
                if not peripheral.registers and parent.registers:
                    peripheral.registers = self._deep_copy_registers(parent.registers)
                    changed = True

                # 簇继承
                if not peripheral.clusters and parent.clusters:
                    peripheral.clusters = self._deep_copy_clusters(parent.clusters)
                    changed = True

                # 中断继承
                if not peripheral.interrupts and parent.interrupts:
                    peripheral.interrupts = list(parent.interrupts)
                    changed = True

                if changed:
                    resolved_any = True

            if not resolved_any:
                break

    def _resolve_register_inheritance(self, peripheral: Peripheral):
        """解析寄存器级 derivedFrom（在外设内部查找源寄存器）"""
        all_regs = peripheral.registers
        for reg_name, register in list(all_regs.items()):
            if not hasattr(register, 'derived_from') or not register.derived_from:
                continue

            source_name = register.derived_from
            if source_name in all_regs and source_name != reg_name:
                source = all_regs[source_name]
                self._merge_register_from_source(register, source)
                register.derived_from = ""  # 清除标记
            else:
                self.warnings.append(
                    f"寄存器 {reg_name} 的继承源 {source_name} 在外设 {peripheral.name} 中不存在"
                )

    def _resolve_cluster_inheritance(self, cluster: Cluster, peripheral: Peripheral):
        """解析簇级 derivedFrom"""
        if cluster.derived_from:
            # 在外设的其他簇中查找源
            if cluster.derived_from in peripheral.clusters:
                source = peripheral.clusters[cluster.derived_from]
                # 继承未定义的属性
                if not cluster.description or cluster.description == cluster.name:
                    cluster.description = source.description
                for attr in ['display_name', 'size', 'access', 'reset_value', 'reset_mask']:
                    if not getattr(cluster, attr, None) and getattr(source, attr, None):
                        setattr(cluster, attr, getattr(source, attr))
                if not cluster.registers and source.registers:
                    cluster.registers = self._deep_copy_registers(source.registers)
                if not cluster.clusters and source.clusters:
                    cluster.clusters = self._deep_copy_clusters(source.clusters)
                cluster.derived_from = ""

        # 递归处理嵌套簇
        for sub in cluster.clusters.values():
            self._resolve_cluster_inheritance(sub, peripheral)

    @staticmethod
    def _is_default_value(obj: Any, attr: str) -> bool:
        """判断属性值是否为数据模型的默认值（即未被用户/XML显式设置）
        
        利用 dataclasses.fields() 提取字段默认值，避免实例化带必填参数的 dataclass。
        """
        val = getattr(obj, attr, None)
        if val is None:
            return True
        # 通过 dataclass 元信息获取默认值
        try:
            from dataclasses import fields, MISSING
            for f in fields(type(obj)):
                if f.name == attr:
                    if f.default is not MISSING:
                        return val == f.default
                    elif f.default_factory is not MISSING:
                        return val == f.default_factory()
                    else:
                        # 无默认值的必填字段 → 不算默认值
                        return False
            # 属性不在 dataclass fields 中
            return False
        except Exception:
            return False

    def _merge_register_from_source(self, target: Register, source: Register):
        """从源寄存器合并未定义的属性到目标寄存器"""
        if not target.description or target.description == target.name:
            target.description = source.description
        if not target.display_name and source.display_name:
            target.display_name = source.display_name
        if self._is_default_value(target, 'size') and source.size:
            target.size = source.size
        if not target.access:
            target.access = source.access
        if self._is_default_value(target, 'reset_value') and source.reset_value:
            target.reset_value = source.reset_value
        if self._is_default_value(target, 'reset_mask') and source.reset_mask:
            target.reset_mask = source.reset_mask
        # 继承位域（只在没有自己的位域时）
        if not target.fields and source.fields:
            target.fields = deepcopy(source.fields)

    def _has_circular_inheritance(self, name: str, derived_from: str) -> bool:
        """检测循环继承"""
        visited = {name}
        current = derived_from
        while current:
            if current in visited:
                return True
            visited.add(current)
            if current in self.device_info.peripherals:
                current = self.device_info.peripherals[current].derived_from
            else:
                break
        return False

    def _deep_copy_registers(self, registers: Dict[str, Register]) -> Dict[str, Register]:
        """深拷贝寄存器字典 — 使用 copy.deepcopy 避免 manually listed fields 遗漏"""
        return deepcopy(registers)

    def _deep_copy_clusters(self, clusters: Dict[str, Cluster]) -> Dict[str, Cluster]:
        """深拷贝簇字典 — 使用 copy.deepcopy 递归拷贝含嵌套簇的完整结构"""
        return deepcopy(clusters)
    
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
        """收集所有中断到设备信息（支持多外设共用中断）"""
        for peripheral in self.device_info.peripherals.values():
            for interrupt in peripheral.interrupts:
                irq_name = interrupt["name"]
                if irq_name in self.device_info.interrupts:
                    # 中断已存在，追加外设关联
                    existing_irq = self.device_info.interrupts[irq_name]
                    if peripheral.name not in existing_irq.peripherals:
                        existing_irq.peripherals.append(peripheral.name)
                else:
                    # 创建新的Interrupt对象
                    irq = Interrupt(
                        name=irq_name,
                        value=interrupt["value"],
                        description=interrupt.get("description", ""),
                        peripheral=interrupt["peripheral"],
                        peripherals=[interrupt["peripheral"]]
                    )
                    self.device_info.interrupts[irq_name] = irq
    
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