# svd_tool/core/base_svd_parser.py
"""
SVD 解析器基类

提取 SVDParser 和 ChunkedSVDParser 的共享解析逻辑，
消除两个解析器之间的代码重复。
"""
import re
from typing import Dict, List, Optional
from xml.dom import minidom

from .data_model import DeviceInfo, Interrupt
from ..utils.logger import Logger

# 设备级已消费的子元素（不在名单内的元素走 extra_xml 透传，防静默丢失）
_DEVICE_KNOWN = {
    "vendor", "vendorID", "name", "series", "version", "description",
    "licenseText", "cpu", "headerSystemFilename", "headerDefinitionsPrefix",
    "addressUnitBits", "width", "size", "resetValue", "resetMask", "peripherals",
}
# CPU 已消费的子元素（fpuDP/dspPresent/icachePresent/dcachePresent/itcmPresent/
# dtcmPresent/vtorPresent 等扩展标志走透传）
_CPU_KNOWN = {
    "name", "revision", "endian", "mpuPresent", "fpuPresent",
    "nvicPrioBits", "vendorSystickConfig",
}


class BaseSVDParser:
    """SVD 解析器基类 - 提供共享的解析基础设施"""

    @staticmethod
    def _get_direct_child(parent_node, tag_name: str):
        """获取直接子节点中指定标签名的第一个元素（非递归）"""
        for child in parent_node.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.tagName == tag_name:
                return child
        return None

    @staticmethod
    def _collect_extra_xml(parent_node, known_tags) -> List[str]:
        """收集未消费的子元素原文（XML 片段），供生成器原样回写。

        CMSIS-SVD 规范元素众多且持续演进，解析白名单外的元素（如 writeConstraint、
        protection、vendorExtensions、CPU 扩展标志等）在这里原文保留，
        打开→保存往返不再静默丢失。
        """
        extras: List[str] = []
        for child in parent_node.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.tagName not in known_tags:
                try:
                    extras.append(child.toxml())
                except Exception:  # noqa: BLE001 - 片段序列化失败不应中断解析
                    continue
        return extras

    def __init__(self, logger_name: str = "svd_parser"):
        self.device_info = DeviceInfo()
        self.warnings: List[str] = []
        self.logger = Logger(logger_name)
        self.current_line = 0
        self.stats = {
            "peripherals": 0,
            "registers": 0,
            "fields": 0,
            "interrupts": 0,
            "errors": 0
        }

    def _parse_comments(self, dom: minidom.Document):
        """解析XML注释中的版权、作者、许可证信息"""
        for child in dom.childNodes:
            if child.nodeType == child.COMMENT_NODE:
                comment_text = child.data.strip()

                copyright_match = re.search(r'Copyright\s*\(c\)\s*\d{4}[^.\n]*\.?', comment_text, re.IGNORECASE)
                if copyright_match:
                    self.device_info.copyright = copyright_match.group(0).strip()

                author_match = re.search(r'Author:\s*(.+?)(?:\n|$)', comment_text, re.IGNORECASE)
                if author_match:
                    self.device_info.author = author_match.group(1).strip()

                license_match = re.search(r'License:\s*(.+?)(?:\n|$)', comment_text, re.IGNORECASE)
                if license_match:
                    self.device_info.license = license_match.group(1).strip()

    def _parse_device_info(self, device_node):
        """解析设备信息 - 使用 _get_direct_child 避免匹配嵌套同名标签"""
        name_node = self._get_direct_child(device_node, "name")
        if name_node and name_node.firstChild:
            self.device_info.name = name_node.firstChild.data.strip()

        version_node = self._get_direct_child(device_node, "version")
        if version_node and version_node.firstChild:
            self.device_info.version = version_node.firstChild.data.strip()

        desc_node = self._get_direct_child(device_node, "description")
        if desc_node and desc_node.firstChild:
            self.device_info.description = desc_node.firstChild.data.strip()

        if device_node.hasAttribute("schemaVersion"):
            self.device_info.svd_version = device_node.getAttribute("schemaVersion")
        else:
            self.warnings.append("未找到SVD版本信息，使用默认版本1.3")
            self.device_info.svd_version = "1.3"

        vendor_node = self._get_direct_child(device_node, "vendor")
        if vendor_node and vendor_node.firstChild:
            self.device_info.vendor = vendor_node.firstChild.data.strip()

        # CMSIS-SVD 可选设备级元素
        for tag, attr in (("vendorID", "vendor_id"),
                          ("series", "series"),
                          ("licenseText", "license_text"),
                          ("headerSystemFilename", "header_system_filename"),
                          ("headerDefinitionsPrefix", "header_definitions_prefix")):
            node = self._get_direct_child(device_node, tag)
            if node is not None and node.firstChild:
                setattr(self.device_info, attr, node.firstChild.data.strip())

        # 未消费元素透传（vendorExtensions / 设备级 access、protection 等）
        self.device_info.extra_xml = self._collect_extra_xml(device_node, _DEVICE_KNOWN)

        self.logger.debug(f"设备信息: {self.device_info.name} v{self.device_info.version}")

    def _parse_cpu_info(self, device_node):
        """解析CPU信息"""
        cpu_nodes = device_node.getElementsByTagName("cpu")
        if not cpu_nodes:
            self.warnings.append("未找到CPU信息，使用默认值")
            return

        cpu_node = cpu_nodes[0]

        name_nodes = cpu_node.getElementsByTagName("name")
        if name_nodes and name_nodes[0].firstChild:
            self.device_info.cpu.name = name_nodes[0].firstChild.data.strip()

        revision_nodes = cpu_node.getElementsByTagName("revision")
        if revision_nodes and revision_nodes[0].firstChild:
            self.device_info.cpu.revision = revision_nodes[0].firstChild.data.strip()

        endian_nodes = cpu_node.getElementsByTagName("endian")
        if endian_nodes and endian_nodes[0].firstChild:
            self.device_info.cpu.endian = endian_nodes[0].firstChild.data.strip()

        mpu_nodes = cpu_node.getElementsByTagName("mpuPresent")
        if mpu_nodes and mpu_nodes[0].firstChild:
            self.device_info.cpu.mpu_present = mpu_nodes[0].firstChild.data.strip().lower() == "true"

        fpu_nodes = cpu_node.getElementsByTagName("fpuPresent")
        if fpu_nodes and fpu_nodes[0].firstChild:
            self.device_info.cpu.fpu_present = fpu_nodes[0].firstChild.data.strip().lower() == "true"

        nvic_nodes = cpu_node.getElementsByTagName("nvicPrioBits")
        if nvic_nodes and nvic_nodes[0].firstChild:
            try:
                self.device_info.cpu.nvic_prio_bits = int(nvic_nodes[0].firstChild.data.strip())
            except ValueError:
                self.warnings.append(f"NVIC优先级位数解析失败: {nvic_nodes[0].firstChild.data}")
                self.device_info.cpu.nvic_prio_bits = 4

        systick_nodes = cpu_node.getElementsByTagName("vendorSystickConfig")
        if systick_nodes and systick_nodes[0].firstChild:
            self.device_info.cpu.vendor_systick_config = systick_nodes[0].firstChild.data.strip().lower() == "true"

        # CPU 扩展标志（fpuDP/dspPresent/icachePresent 等）透传保留
        self.device_info.cpu.extra_xml = self._collect_extra_xml(cpu_node, _CPU_KNOWN)

        self.logger.debug(f"CPU信息: {self.device_info.cpu.name} {self.device_info.cpu.revision}")

    def _parse_standard_fields(self, device_node):
        """解析标准字段 - 使用 _get_direct_child 避免匹配嵌套同名标签"""
        addr_unit_node = self._get_direct_child(device_node, "addressUnitBits")
        if addr_unit_node and addr_unit_node.firstChild:
            try:
                self.device_info.address_unit_bits = int(addr_unit_node.firstChild.data.strip())
            except ValueError:
                self.warnings.append(f"地址单元位数解析失败: {addr_unit_node.firstChild.data}")

        width_node = self._get_direct_child(device_node, "width")
        if width_node and width_node.firstChild:
            try:
                self.device_info.width = int(width_node.firstChild.data.strip())
            except ValueError:
                self.warnings.append(f"数据宽度解析失败: {width_node.firstChild.data}")

        size_node = self._get_direct_child(device_node, "size")
        if size_node and size_node.firstChild:
            self.device_info.size = size_node.firstChild.data.strip()

        reset_value_node = self._get_direct_child(device_node, "resetValue")
        if reset_value_node and reset_value_node.firstChild:
            self.device_info.reset_value = reset_value_node.firstChild.data.strip()

        reset_mask_node = self._get_direct_child(device_node, "resetMask")
        if reset_mask_node and reset_mask_node.firstChild:
            self.device_info.reset_mask = reset_mask_node.firstChild.data.strip()

    def _collect_interrupts_to_device(self):
        """收集所有中断到设备信息（支持多外设共用中断）"""
        for periph_name, peripheral in self.device_info.peripherals.items():
            for interrupt in peripheral.interrupts:
                irq_name = interrupt.get("name", "") if isinstance(interrupt, dict) else interrupt["name"]
                if not irq_name:
                    continue
                if irq_name in self.device_info.interrupts:
                    existing_irq = self.device_info.interrupts[irq_name]
                    if periph_name not in existing_irq.peripherals:
                        existing_irq.peripherals.append(periph_name)
                else:
                    periph_val = interrupt.get("peripheral", periph_name) if isinstance(interrupt, dict) else interrupt.get("peripheral", periph_name)
                    irq = Interrupt(
                        name=irq_name,
                        value=interrupt.get("value", 0) if isinstance(interrupt, dict) else interrupt["value"],
                        description=interrupt.get("description", "") if isinstance(interrupt, dict) else interrupt.get("description", ""),
                        peripheral=periph_val,
                        peripherals=[periph_val]
                    )
                    self.device_info.interrupts[irq_name] = irq

    def get_stats(self) -> Dict[str, int]:
        """获取解析统计"""
        return self.stats.copy()
