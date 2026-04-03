# svd_tool/core/block_manager.py
"""
块管理器 - 管理SVD文件的分块加载和导航
支持按需加载外设、寄存器和位域
"""
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import logging

from .data_model import DeviceInfo, Peripheral, Register, Field


class BlockType(Enum):
    """块类型枚举"""
    DEVICE = "device"      # 设备信息
    PERIPHERAL = "peripheral"  # 外设
    REGISTER = "register"      # 寄存器
    FIELD = "field"            # 位域


@dataclass
class BlockInfo:
    """块信息"""
    block_type: BlockType
    peripheral_name: str = ""
    register_name: str = ""
    field_name: str = ""
    
    # XML位置信息
    xml_start_line: int = 0
    xml_end_line: int = 0
    
    # 加载状态
    is_loaded: bool = False
    is_visible: bool = False
    
    # 父子关系
    parent_key: Optional[str] = None
    child_keys: Set[str] = field(default_factory=set)
    
    @property
    def key(self) -> str:
        """获取块的唯一标识"""
        if self.block_type == BlockType.DEVICE:
            return "device"
        elif self.block_type == BlockType.PERIPHERAL:
            return f"peripheral:{self.peripheral_name}"
        elif self.block_type == BlockType.REGISTER:
            return f"register:{self.peripheral_name}:{self.register_name}"
        elif self.block_type == BlockType.FIELD:
            return f"field:{self.peripheral_name}:{self.register_name}:{self.field_name}"
        return ""
    
    @property
    def display_name(self) -> str:
        """获取显示名称"""
        if self.block_type == BlockType.DEVICE:
            return "Device"
        elif self.block_type == BlockType.PERIPHERAL:
            return self.peripheral_name
        elif self.block_type == BlockType.REGISTER:
            return self.register_name
        elif self.block_type == BlockType.FIELD:
            return self.field_name
        return ""


class BlockManager:
    """块管理器 - 管理SVD文件的分块加载和导航"""
    
    def __init__(self, device_info: DeviceInfo):
        """
        初始化块管理器
        
        Args:
            device_info: 设备信息对象
        """
        self.device_info = device_info
        self.logger = logging.getLogger("BlockManager")
        
        # 块信息字典 {key: BlockInfo}
        self.blocks: Dict[str, BlockInfo] = {}
        
        # 加载状态
        self.loaded_peripherals: Set[str] = set()
        self.loaded_registers: Dict[str, Set[str]] = {}  # {peripheral_name: {register_name}}
        self.loaded_fields: Dict[str, Dict[str, Set[str]]] = {}  # {peripheral_name: {register_name: {field_name}}}
        
        # 可见状态
        self.visible_blocks: Set[str] = set()
        
        # 当前选中的块
        self.current_block_key: Optional[str] = None
        
        # 初始化块结构
        self._initialize_blocks()
    
    def _initialize_blocks(self):
        """初始化块结构"""
        self.logger.info("初始化块结构...")
        
        # 创建设备块
        device_block = BlockInfo(
            block_type=BlockType.DEVICE,
            is_loaded=True,
            is_visible=True
        )
        self.blocks[device_block.key] = device_block
        
        # 创建外设块
        for periph_name in self.device_info.peripherals:
            periph_block = BlockInfo(
                block_type=BlockType.PERIPHERAL,
                peripheral_name=periph_name,
                parent_key="device"
            )
            self.blocks[periph_block.key] = periph_block
            device_block.child_keys.add(periph_block.key)
            
            # 创建寄存器块
            peripheral = self.device_info.peripherals[periph_name]
            for reg_name in peripheral.registers:
                reg_block = BlockInfo(
                    block_type=BlockType.REGISTER,
                    peripheral_name=periph_name,
                    register_name=reg_name,
                    parent_key=periph_block.key
                )
                self.blocks[reg_block.key] = reg_block
                periph_block.child_keys.add(reg_block.key)
                
                # 创建位域块
                register = peripheral.registers[reg_name]
                for field_name in register.fields:
                    field_block = BlockInfo(
                        block_type=BlockType.FIELD,
                        peripheral_name=periph_name,
                        register_name=reg_name,
                        field_name=field_name,
                        parent_key=reg_block.key
                    )
                    self.blocks[field_block.key] = field_block
                    reg_block.child_keys.add(field_block.key)
        
        self.logger.info(f"块结构初始化完成，共 {len(self.blocks)} 个块")
    
    def load_peripheral(self, peripheral_name: str) -> bool:
        """
        加载外设块
        
        Args:
            peripheral_name: 外设名称
            
        Returns:
            是否加载成功
        """
        key = f"peripheral:{peripheral_name}"
        if key not in self.blocks:
            self.logger.warning(f"外设块不存在: {peripheral_name}")
            return False
        
        block = self.blocks[key]
        if block.is_loaded:
            return True
        
        # 标记为已加载
        block.is_loaded = True
        self.loaded_peripherals.add(peripheral_name)
        
        # 初始化寄存器加载集合
        self.loaded_registers[peripheral_name] = set()
        self.loaded_fields[peripheral_name] = {}
        
        self.logger.debug(f"加载外设块: {peripheral_name}")
        return True
    
    def load_register(self, peripheral_name: str, register_name: str) -> bool:
        """
        加载寄存器块
        
        Args:
            peripheral_name: 外设名称
            register_name: 寄存器名称
            
        Returns:
            是否加载成功
        """
        # 确保外设已加载
        if peripheral_name not in self.loaded_peripherals:
            self.load_peripheral(peripheral_name)
        
        key = f"register:{peripheral_name}:{register_name}"
        if key not in self.blocks:
            self.logger.warning(f"寄存器块不存在: {peripheral_name}.{register_name}")
            return False
        
        block = self.blocks[key]
        if block.is_loaded:
            return True
        
        # 标记为已加载
        block.is_loaded = True
        self.loaded_registers[peripheral_name].add(register_name)
        
        # 初始化位域加载集合
        self.loaded_fields[peripheral_name][register_name] = set()
        
        self.logger.debug(f"加载寄存器块: {peripheral_name}.{register_name}")
        return True
    
    def load_field(self, peripheral_name: str, register_name: str, field_name: str) -> bool:
        """
        加载位域块
        
        Args:
            peripheral_name: 外设名称
            register_name: 寄存器名称
            field_name: 位域名称
            
        Returns:
            是否加载成功
        """
        # 确保寄存器已加载
        if register_name not in self.loaded_registers.get(peripheral_name, set()):
            self.load_register(peripheral_name, register_name)
        
        key = f"field:{peripheral_name}:{register_name}:{field_name}"
        if key not in self.blocks:
            self.logger.warning(f"位域块不存在: {peripheral_name}.{register_name}.{field_name}")
            return False
        
        block = self.blocks[key]
        if block.is_loaded:
            return True
        
        # 标记为已加载
        block.is_loaded = True
        self.loaded_fields[peripheral_name][register_name].add(field_name)
        
        self.logger.debug(f"加载位域块: {peripheral_name}.{register_name}.{field_name}")
        return True
    
    def set_visible(self, block_key: str, visible: bool = True):
        """
        设置块的可见性
        
        Args:
            block_key: 块的key
            visible: 是否可见
        """
        if block_key not in self.blocks:
            return
        
        block = self.blocks[block_key]
        block.is_visible = visible
        
        if visible:
            self.visible_blocks.add(block_key)
        else:
            self.visible_blocks.discard(block_key)
        
        self.logger.debug(f"设置块可见性: {block_key} -> {visible}")
    
    def set_visible_range(self, start_key: str, end_key: str):
        """
        设置可见范围（包含两个块之间的所有块）
        
        Args:
            start_key: 起始块的key
            end_key: 结束块的key
        """
        # 获取所有块的有序列表
        block_keys = self._get_ordered_block_keys()
        
        try:
            start_idx = block_keys.index(start_key)
            end_idx = block_keys.index(end_key)
        except ValueError:
            self.logger.warning(f"无效的块范围: {start_key} -> {end_key}")
            return
        
        # 设置范围内的块为可见
        for i in range(start_idx, end_idx + 1):
            self.set_visible(block_keys[i], True)
    
    def get_block(self, block_key: str) -> Optional[BlockInfo]:
        """
        获取块信息
        
        Args:
            block_key: 块的key
            
        Returns:
            块信息，如果不存在则返回None
        """
        return self.blocks.get(block_key)
    
    def get_visible_blocks(self) -> List[BlockInfo]:
        """
        获取所有可见的块
        
        Returns:
            可见块列表（按顺序）
        """
        ordered_keys = self._get_ordered_block_keys()
        return [self.blocks[key] for key in ordered_keys if key in self.visible_blocks]
    
    def get_loaded_blocks(self) -> List[BlockInfo]:
        """
        获取所有已加载的块
        
        Returns:
            已加载块列表（按顺序）
        """
        ordered_keys = self._get_ordered_block_keys()
        return [self.blocks[key] for key in ordered_keys if self.blocks[key].is_loaded]
    
    def navigate_to(self, block_key: str) -> Optional[BlockInfo]:
        """
        导航到指定块
        
        Args:
            block_key: 目标块的key
            
        Returns:
            目标块信息，如果不存在则返回None
        """
        if block_key not in self.blocks:
            self.logger.warning(f"导航目标不存在: {block_key}")
            return None
        
        # 设置当前选中块
        self.current_block_key = block_key
        
        # 确保块已加载
        block = self.blocks[block_key]
        if not block.is_loaded:
            if block.block_type == BlockType.PERIPHERAL:
                self.load_peripheral(block.peripheral_name)
            elif block.block_type == BlockType.REGISTER:
                self.load_register(block.peripheral_name, block.register_name)
            elif block.block_type == BlockType.FIELD:
                self.load_field(block.peripheral_name, block.register_name, block.field_name)
        
        # 设置为可见
        self.set_visible(block_key, True)
        
        self.logger.debug(f"导航到块: {block_key}")
        return block
    
    def get_parent_block(self, block_key: str) -> Optional[BlockInfo]:
        """
        获取父块
        
        Args:
            block_key: 块的key
            
        Returns:
            父块信息，如果不存在则返回None
        """
        block = self.blocks.get(block_key)
        if not block or not block.parent_key:
            return None
        return self.blocks.get(block.parent_key)
    
    def get_child_blocks(self, block_key: str) -> List[BlockInfo]:
        """
        获取子块列表
        
        Args:
            block_key: 块的key
            
        Returns:
            子块列表
        """
        block = self.blocks.get(block_key)
        if not block:
            return []
        
        return [self.blocks[child_key] for child_key in block.child_keys if child_key in self.blocks]
    
    def get_next_block(self, block_key: str) -> Optional[BlockInfo]:
        """
        获取下一个块
        
        Args:
            block_key: 当前块的key
            
        Returns:
            下一个块信息，如果不存在则返回None
        """
        ordered_keys = self._get_ordered_block_keys()
        try:
            idx = ordered_keys.index(block_key)
            if idx + 1 < len(ordered_keys):
                return self.blocks[ordered_keys[idx + 1]]
        except ValueError:
            pass
        return None
    
    def get_previous_block(self, block_key: str) -> Optional[BlockInfo]:
        """
        获取上一个块
        
        Args:
            block_key: 当前块的key
            
        Returns:
            上一个块信息，如果不存在则返回None
        """
        ordered_keys = self._get_ordered_block_keys()
        try:
            idx = ordered_keys.index(block_key)
            if idx > 0:
                return self.blocks[ordered_keys[idx - 1]]
        except ValueError:
            pass
        return None
    
    def _get_ordered_block_keys(self) -> List[str]:
        """
        获取按顺序排列的块key列表
        
        Returns:
            有序的块key列表
        """
        ordered_keys = []
        
        # 设备块
        ordered_keys.append("device")
        
        # 外设块（按名称排序）
        periph_names = sorted(self.device_info.peripherals.keys())
        for periph_name in periph_names:
            ordered_keys.append(f"peripheral:{periph_name}")
            
            # 寄存器块（按偏移地址排序）
            peripheral = self.device_info.peripherals[periph_name]
            def _safe_offset(name):
                try:
                    return int(peripheral.registers[name].offset, 0)
                except (ValueError, TypeError):
                    return 0
            reg_names = sorted(peripheral.registers.keys(), key=_safe_offset)
            for reg_name in reg_names:
                ordered_keys.append(f"register:{periph_name}:{reg_name}")
                
                # 位域块（按位偏移排序）
                register = peripheral.registers[reg_name]
                field_names = sorted(register.fields.keys(),
                                   key=lambda x: register.fields[x].bit_offset)
                for field_name in field_names:
                    ordered_keys.append(f"field:{periph_name}:{reg_name}:{field_name}")
        
        return ordered_keys
    
    def get_statistics(self) -> Dict[str, int]:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        return {
            "total_blocks": len(self.blocks),
            "loaded_blocks": sum(1 for block in self.blocks.values() if block.is_loaded),
            "visible_blocks": len(self.visible_blocks),
            "loaded_peripherals": len(self.loaded_peripherals),
            "loaded_registers": sum(len(regs) for regs in self.loaded_registers.values()),
            "loaded_fields": sum(
                len(fields) for periph_fields in self.loaded_fields.values() 
                for fields in periph_fields.values()
            )
        }
    
    def clear_loaded(self):
        """清除所有已加载状态（保留设备块）"""
        self.loaded_peripherals.clear()
        self.loaded_registers.clear()
        self.loaded_fields.clear()
        
        for key, block in self.blocks.items():
            if block.block_type != BlockType.DEVICE:
                block.is_loaded = False
        
        self.logger.debug("清除所有已加载状态")
