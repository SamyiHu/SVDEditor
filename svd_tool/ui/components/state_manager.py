"""
状态管理组件
负责管理应用程序的状态，包括设备信息、当前选择、命令历史等
"""
import copy
from typing import Dict, List, Optional, Any, Callable
from dataclasses import asdict

from svd_tool.core.data_model import DeviceInfo, Peripheral, Register, Field, Interrupt, CPUInfo
from svd_tool.core.command_history import CommandHistory, Command
from svd_tool.core.validators import Validator


class StateManager:
    """状态管理器"""
    
    def __init__(self):
        """初始化状态管理器"""
        self.device_info = DeviceInfo()
        self.command_history = CommandHistory()
        
        # 当前选中项
        self.current_peripheral: Optional[str] = None
        self.current_register: Optional[str] = None
        self.current_field: Optional[str] = None
        
        # 状态变更回调
        self._state_change_callbacks: List[Callable[[], None]] = []
        self._selection_change_callbacks: List[Callable[[], None]] = []
    
    def register_state_change_callback(self, callback: Callable[[], None]):
        """注册状态变更回调"""
        if callback not in self._state_change_callbacks:
            self._state_change_callbacks.append(callback)
    
    def register_selection_change_callback(self, callback: Callable[[], None]):
        """注册选择变更回调"""
        if callback not in self._selection_change_callbacks:
            self._selection_change_callbacks.append(callback)
    
    def _notify_state_change(self):
        """通知状态变更"""
        for callback in self._state_change_callbacks:
            callback()
    
    def _notify_selection_change(self):
        """通知选择变更"""
        for callback in self._selection_change_callbacks:
            callback()
    
    # ===================== 状态快照方法 =====================
    def get_device_state_snapshot(self) -> Dict[str, Any]:
        """获取设备状态快照（用于撤销）"""
        # 创建深拷贝的状态快照
        snapshot = {
            'device_info': {
                'name': self.device_info.name,
                'version': self.device_info.version,
                'description': self.device_info.description,
                'svd_version': self.device_info.svd_version,
                'peripherals': copy.deepcopy(self.device_info.peripherals),
                'interrupts': copy.deepcopy(self.device_info.interrupts),
                'cpu': copy.deepcopy(self.device_info.cpu),
            },
            'selection': {
                'peripheral': self.current_peripheral,
                'register': self.current_register,
                'field': self.current_field
            }
        }
        
        return snapshot
    
    def restore_device_state(self, snapshot: Dict[str, Any]):
        """恢复设备状态"""
        if not snapshot:
            return
        
        # 恢复设备信息
        if 'device_info' in snapshot:
            device_data = snapshot['device_info']
            self.device_info.name = device_data.get('name', '')
            self.device_info.version = device_data.get('version', '1.0')
            self.device_info.description = device_data.get('description', '')
            self.device_info.svd_version = device_data.get('svd_version', '1.3')
            
            # 恢复外设
            if 'peripherals' in device_data:
                self.device_info.peripherals = copy.deepcopy(device_data['peripherals'])
            
            # 恢复中断
            if 'interrupts' in device_data:
                self.device_info.interrupts = copy.deepcopy(device_data['interrupts'])
            
            # 恢复CPU信息
            if 'cpu' in device_data:
                self.device_info.cpu = copy.deepcopy(device_data['cpu'])
        
        # 恢复选中状态
        if 'selection' in snapshot:
            selection = snapshot['selection']
            self.current_peripheral = selection.get('peripheral')
            self.current_register = selection.get('register')
            self.current_field = selection.get('field')
        
        # 通知状态变更
        self._notify_state_change()
        self._notify_selection_change()
    
    # ===================== 选择管理 =====================
    def set_selection(self, peripheral: Optional[str] = None,
                     register: Optional[str] = None,
                     field: Optional[str] = None):
        """设置当前选中项"""
        changed = False
        
        # 如果设置了新的外设，清除寄存器和位域选择（除非同时设置了寄存器）
        if peripheral is not None and peripheral != self.current_peripheral:
            self.current_peripheral = peripheral
            changed = True
            
            # 如果只设置了外设而没有设置寄存器，清除寄存器和位域选择
            if register is None:
                if self.current_register is not None:
                    self.current_register = None
                    changed = True
                if self.current_field is not None:
                    self.current_field = None
                    changed = True
        
        # 如果设置了新的寄存器，清除位域选择（除非同时设置了位域）
        if register is not None and register != self.current_register:
            self.current_register = register
            changed = True
            
            # 如果只设置了寄存器而没有设置位域，清除位域选择
            if field is None:
                if self.current_field is not None:
                    self.current_field = None
                    changed = True
        
        if field is not None and field != self.current_field:
            self.current_field = field
            changed = True
        
        if changed:
            self._notify_selection_change()
    
    def clear_selection(self):
        """清除所有选中项"""
        self.set_selection(None, None, None)
    
    def get_selection(self) -> Dict[str, Optional[str]]:
        """获取当前选中项"""
        return {
            'peripheral': self.current_peripheral,
            'register': self.current_register,
            'field': self.current_field
        }
    
    def get_current_peripheral(self) -> Optional[str]:
        """获取当前选中的外设名称"""
        return self.current_peripheral
    
    def get_current_register(self) -> Optional[str]:
        """获取当前选中的寄存器名称"""
        return self.current_register
    
    def get_current_field(self) -> Optional[str]:
        """获取当前选中的位域名称"""
        return self.current_field
    
    # ===================== 设备信息操作 =====================
    def reset(self):
        """重置设备信息到初始状态"""
        self.device_info = DeviceInfo()
        self.current_peripheral = None
        self.current_register = None
        self.current_field = None
        self._notify_state_change()
        self._notify_selection_change()
    
    def add_peripheral(self, peripheral: Peripheral):
        """添加外设"""
        # 创建执行函数
        def execute():
            self.device_info.peripherals[peripheral.name] = peripheral
            self._notify_state_change()
        
        # 创建撤销函数
        def undo():
            del self.device_info.peripherals[peripheral.name]
            self._notify_state_change()
        
        # 创建命令并执行
        command = Command(
            execute=execute,
            undo=undo,
            description=f"添加外设: {peripheral.name}"
        )
        self.execute_command(command)
    
    def update_peripheral(self, name: str, peripheral: Peripheral):
        """更新外设"""
        if name in self.device_info.peripherals:
            self.device_info.peripherals[name] = peripheral
            self._notify_state_change()
    
    def delete_peripheral(self, name: str):
        """删除外设"""
        if name not in self.device_info.peripherals:
            return
        
        # 保存旧的外设数据用于撤销
        old_peripheral = self.device_info.peripherals[name]
        was_current = (self.current_peripheral == name)
        
        # 创建执行函数
        def execute():
            del self.device_info.peripherals[name]
            # 如果删除的是当前选中的外设，清除相关选择
            if was_current:
                self.current_peripheral = None
                self.current_register = None
                self.current_field = None
                self._notify_selection_change()
            self._notify_state_change()
        
        # 创建撤销函数
        def undo():
            self.device_info.peripherals[name] = old_peripheral
            # 恢复选中状态
            if was_current:
                self.current_peripheral = name
                self.current_register = None
                self.current_field = None
                self._notify_selection_change()
            self._notify_state_change()
        
        # 创建命令并执行
        command = Command(
            execute=execute,
            undo=undo,
            description=f"删除外设: {name}"
        )
        self.execute_command(command)
    
    def add_register(self, peripheral_name: str, register: Register):
        """添加寄存器"""
        if peripheral_name in self.device_info.peripherals:
            self.device_info.peripherals[peripheral_name].registers[register.name] = register
            self._notify_state_change()
    
    def update_register(self, peripheral_name: str, name: str, register: Register):
        """更新寄存器"""
        if (peripheral_name in self.device_info.peripherals and 
            name in self.device_info.peripherals[peripheral_name].registers):
            self.device_info.peripherals[peripheral_name].registers[name] = register
            self._notify_state_change()
    
    def delete_register(self, peripheral_name: str, name: str):
        """删除寄存器"""
        if (peripheral_name in self.device_info.peripherals and 
            name in self.device_info.peripherals[peripheral_name].registers):
            del self.device_info.peripherals[peripheral_name].registers[name]
            # 如果删除的是当前选中的寄存器，清除相关选择
            if self.current_peripheral == peripheral_name and self.current_register == name:
                self.current_register = None
                self.current_field = None
                self._notify_selection_change()
            self._notify_state_change()
    
    def add_field(self, peripheral_name: str, register_name: str, field: Field):
        """添加位域"""
        if (peripheral_name in self.device_info.peripherals and 
            register_name in self.device_info.peripherals[peripheral_name].registers):
            self.device_info.peripherals[peripheral_name].registers[register_name].fields[field.name] = field
            self._notify_state_change()
    
    def update_field(self, peripheral_name: str, register_name: str, name: str, field: Field):
        """更新位域"""
        if (peripheral_name in self.device_info.peripherals and 
            register_name in self.device_info.peripherals[peripheral_name].registers and
            name in self.device_info.peripherals[peripheral_name].registers[register_name].fields):
            self.device_info.peripherals[peripheral_name].registers[register_name].fields[name] = field
            self._notify_state_change()
    
    def delete_field(self, peripheral_name: str, register_name: str, name: str):
        """删除位域"""
        if (peripheral_name in self.device_info.peripherals and 
            register_name in self.device_info.peripherals[peripheral_name].registers and
            name in self.device_info.peripherals[peripheral_name].registers[register_name].fields):
            del self.device_info.peripherals[peripheral_name].registers[register_name].fields[name]
            # 如果删除的是当前选中的位域，清除相关选择
            if (self.current_peripheral == peripheral_name and 
                self.current_register == register_name and 
                self.current_field == name):
                self.current_field = None
                self._notify_selection_change()
            self._notify_state_change()
    
    def add_interrupt(self, interrupt: Interrupt):
        """添加中断"""
        self.device_info.interrupts[interrupt.name] = interrupt
        self._notify_state_change()
    
    def update_interrupt(self, name: str, interrupt: Interrupt):
        """更新中断"""
        if name in self.device_info.interrupts:
            self.device_info.interrupts[name] = interrupt
            self._notify_state_change()
    
    def delete_interrupt(self, name: str):
        """删除中断"""
        if name in self.device_info.interrupts:
            del self.device_info.interrupts[name]
            self._notify_state_change()
    
    # ===================== 命令历史操作 =====================
    def execute_command(self, command: Command):
        """执行命令并记录到历史"""
        self.command_history.execute(command)
        self._notify_state_change()
    
    def undo(self):
        """撤销"""
        if self.command_history.can_undo():
            self.command_history.undo()
            self._notify_state_change()
    
    def redo(self):
        """重做"""
        if self.command_history.can_redo():
            self.command_history.redo()
            self._notify_state_change()
    
    # ===================== 数据统计 =====================
    def get_data_stats(self) -> Dict[str, int]:
        """获取数据统计"""
        peripheral_count = len(self.device_info.peripherals)
        register_count = 0
        field_count = 0
        
        for peripheral in self.device_info.peripherals.values():
            register_count += len(peripheral.registers)
            for register in peripheral.registers.values():
                field_count += len(register.fields)
        
        interrupt_count = len(self.device_info.interrupts)
        
        return {
            'peripherals': peripheral_count,
            'registers': register_count,
            'fields': field_count,
            'interrupts': interrupt_count
        }
    
    # ===================== 数据验证 =====================
    def validate_device_info(self) -> List[str]:
        """验证设备信息，返回错误列表"""
        errors = []
        
        try:
            # 检查基本字段
            if not self.device_info.name:
                errors.append("设备名称不能为空")
            
            if not self.device_info.version:
                errors.append("设备版本不能为空")
            
            # 使用Validator验证外设
            for periph_name, peripheral in self.device_info.peripherals.items():
                try:
                    # 验证外设名称
                    Validator.validate_name(periph_name, "外设名称")
                    
                    # 验证基地址
                    if peripheral.base_address:
                        Validator.validate_hex(str(peripheral.base_address), "基地址")
                    
                    # 验证寄存器
                    for reg_name, register in peripheral.registers.items():
                        try:
                            Validator.validate_name(reg_name, "寄存器名称")
                            
                            if register.offset is not None:
                                Validator.validate_hex(str(register.offset), "偏移地址")
                            
                            # 验证位域
                            for field_name, field in register.fields.items():
                                try:
                                    Validator.validate_name(field_name, "位域名称")
                                    
                                    # 验证位偏移和位宽
                                    if field.bit_offset is not None:
                                        Validator.validate_decimal(str(field.bit_offset), "位偏移")
                                    
                                    if field.bit_width is not None:
                                        Validator.validate_decimal(str(field.bit_width), "位宽")
                                        
                                except Exception as e:
                                    errors.append(f"外设 '{periph_name}' -> 寄存器 '{reg_name}' -> 位域 '{field_name}' 验证失败: {str(e)}")
                                    
                        except Exception as e:
                            errors.append(f"外设 '{periph_name}' -> 寄存器 '{reg_name}' 验证失败: {str(e)}")
                            
                except Exception as e:
                    errors.append(f"外设 '{periph_name}' 验证失败: {str(e)}")
            # 验证中断
            for interrupt_name, interrupt in self.device_info.interrupts.items():
                try:
                    if interrupt.name:
                        Validator.validate_name(interrupt.name, "中断名称")
                    
                    if interrupt.value is not None:
                        Validator.validate_decimal(str(interrupt.value), "中断号")
                        
                except Exception as e:
                    errors.append(f"中断 '{interrupt.name if interrupt.name else '未命名'}' 验证失败: {str(e)}")
                    
                    
        except Exception as e:
            errors.append(f"验证过程中发生错误: {str(e)}")
        
        return errors
    
    def validate_and_get_summary(self) -> Dict[str, Any]:
        """验证数据并返回摘要信息"""
        errors = self.validate_device_info()
        
        # 获取数据统计
        stats = self.get_data_stats()
        
        return {
            'valid': len(errors) == 0,
            'error_count': len(errors),
            'errors': errors,
            'stats': stats,
            'has_data': stats['peripherals'] > 0 or stats['registers'] > 0 or stats['fields'] > 0
        }
    
    # ===================== 排序功能 =====================
    def sort_peripherals_alphabetically(self) -> bool:
        """按字母顺序排序外设"""
        try:
            # 获取外设名称列表并排序
            sorted_names = sorted(self.device_info.peripherals.keys())
            
            # 如果顺序没有变化，直接返回
            current_names = list(self.device_info.peripherals.keys())
            if current_names == sorted_names:
                return False
            
            # 创建新的有序字典
            from collections import OrderedDict
            sorted_peripherals = OrderedDict()
            for name in sorted_names:
                sorted_peripherals[name] = self.device_info.peripherals[name]
            
            # 更新外设字典
            self.device_info.peripherals = sorted_peripherals
            
            # 通知状态变化
            self._notify_state_change()
            return True
            
        except Exception as e:
            print(f"按字母排序外设失败: {e}")
            return False
    
    def sort_peripherals_by_address(self) -> bool:
        """按基地址排序外设"""
        try:
            peripherals_with_address = []
            
            for periph_name, peripheral in self.device_info.peripherals.items():
                try:
                    # 解析基地址
                    addr_str = str(peripheral.base_address).strip().lower()
                    if addr_str.startswith('0x'):
                        base_addr = int(addr_str, 16)
                    else:
                        base_addr = int(addr_str)
                    peripherals_with_address.append((base_addr, periph_name, peripheral))
                except (ValueError, AttributeError):
                    # 如果地址解析失败，放到最后
                    peripherals_with_address.append((0xFFFFFFFF, periph_name, peripheral))
            
            # 按基地址排序
            peripherals_with_address.sort(key=lambda x: x[0])
            
            # 创建新的有序字典
            from collections import OrderedDict
            sorted_peripherals = OrderedDict()
            for _, periph_name, peripheral in peripherals_with_address:
                sorted_peripherals[periph_name] = peripheral
            
            # 检查顺序是否变化
            current_names = list(self.device_info.peripherals.keys())
            new_names = list(sorted_peripherals.keys())
            if current_names == new_names:
                return False
            
            # 更新外设字典
            self.device_info.peripherals = sorted_peripherals
            
            # 通知状态变化
            self._notify_state_change()
            return True
            
        except Exception as e:
            print(f"按地址排序外设失败: {e}")
            return False
    
    def sort_registers_by_address(self, peripheral_name: str) -> bool:
        """按偏移地址排序指定外设的寄存器"""
        try:
            if peripheral_name not in self.device_info.peripherals:
                return False
            
            peripheral = self.device_info.peripherals[peripheral_name]
            registers_with_offset = []
            
            for reg_name, register in peripheral.registers.items():
                try:
                    # 解析偏移地址
                    offset_str = str(register.address_offset).strip().lower()
                    if offset_str.startswith('0x'):
                        offset = int(offset_str, 16)
                    else:
                        offset = int(offset_str)
                    registers_with_offset.append((offset, reg_name, register))
                except (ValueError, AttributeError):
                    # 如果偏移解析失败，放到最后
                    registers_with_offset.append((0xFFFFFFFF, reg_name, register))
            
            # 按偏移地址排序
            registers_with_offset.sort(key=lambda x: x[0])
            
            # 创建新的有序字典
            from collections import OrderedDict
            sorted_registers = OrderedDict()
            for _, reg_name, register in registers_with_offset:
                sorted_registers[reg_name] = register
            
            # 检查顺序是否变化
            current_names = list(peripheral.registers.keys())
            new_names = list(sorted_registers.keys())
            if current_names == new_names:
                return False
            
            # 更新寄存器字典
            peripheral.registers = sorted_registers
            
            # 通知状态变化
            self._notify_state_change()
            return True
            
        except Exception as e:
            print(f"按地址排序寄存器失败: {e}")
            return False
    
    def sort_fields_by_bit_offset(self, register_name: str) -> bool:
        """按起始位排序指定寄存器的位域"""
        try:
            # 查找寄存器
            target_register = None
            target_peripheral = None
            
            for periph_name, peripheral in self.device_info.peripherals.items():
                if register_name in peripheral.registers:
                    target_register = peripheral.registers[register_name]
                    target_peripheral = peripheral
                    break
            
            if not target_register:
                return False
            
            fields_with_offset = []
            
            for field_name, field in target_register.fields.items():
                try:
                    # 获取位偏移
                    bit_offset = field.bit_offset
                    fields_with_offset.append((bit_offset, field_name, field))
                except (ValueError, AttributeError):
                    # 如果位偏移解析失败，放到最后
                    fields_with_offset.append((0xFFFFFFFF, field_name, field))
            
            # 按位偏移排序
            fields_with_offset.sort(key=lambda x: x[0])
            
            # 创建新的有序字典
            from collections import OrderedDict
            sorted_fields = OrderedDict()
            for _, field_name, field in fields_with_offset:
                sorted_fields[field_name] = field
            
            # 检查顺序是否变化
            current_names = list(target_register.fields.keys())
            new_names = list(sorted_fields.keys())
            if current_names == new_names:
                return False
            
            # 更新位域字典
            target_register.fields = sorted_fields
            
            # 通知状态变化
            self._notify_state_change()
            return True
            
        except Exception as e:
            print(f"按位偏移排序位域失败: {e}")
            return False
    
    # ===================== 移动功能 =====================
    def move_peripheral_up(self, periph_name: str) -> bool:
        """上移外设"""
        try:
            # 获取所有外设名称列表
            periph_names = list(self.device_info.peripherals.keys())
            
            # 找到当前外设的位置
            if periph_name not in periph_names:
                return False
            
            index = periph_names.index(periph_name)
            if index <= 0:  # 已经在最上面
                return False
            
            # 在列表中交换位置
            periph_names[index], periph_names[index-1] = periph_names[index-1], periph_names[index]
            
            # 创建新的有序字典
            from collections import OrderedDict
            new_peripherals = OrderedDict()
            for name in periph_names:
                new_peripherals[name] = self.device_info.peripherals[name]
            
            # 更新数据模型
            self.device_info.peripherals = new_peripherals
            
            # 通知状态变化
            self._notify_state_change()
            return True
            
        except Exception as e:
            print(f"上移外设失败: {e}")
            return False
    
    def move_peripheral_down(self, periph_name: str) -> bool:
        """下移外设"""
        try:
            # 获取所有外设名称列表
            periph_names = list(self.device_info.peripherals.keys())
            
            # 找到当前外设的位置
            if periph_name not in periph_names:
                return False
            
            index = periph_names.index(periph_name)
            if index >= len(periph_names) - 1:  # 已经在最下面
                return False
            
            # 在列表中交换位置
            periph_names[index], periph_names[index+1] = periph_names[index+1], periph_names[index]
            
            # 创建新的有序字典
            from collections import OrderedDict
            new_peripherals = OrderedDict()
            for name in periph_names:
                new_peripherals[name] = self.device_info.peripherals[name]
            
            # 更新数据模型
            self.device_info.peripherals = new_peripherals
            
            # 通知状态变化
            self._notify_state_change()
            return True
            
        except Exception as e:
            print(f"下移外设失败: {e}")
            return False