"""
综合可视化控件容器
从main_window.py中提取的独立组件
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal

from .address_map_widget import AddressMapWidget
from .bit_field_widget import BitFieldWidget
from svd_tool.core.data_model import Peripheral


class VisualizationWidget(QWidget):
    """综合可视化控件容器"""
    # 定义信号：跳转到源外设时发射
    jump_to_peripheral = pyqtSignal(str)  # 外设名称
    
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)  # 增加间距，避免外设图被遮挡
        
        self.address_map = AddressMapWidget()
        self.bit_field = BitFieldWidget()
        
        # 连接跳转到源外设的信号
        self.bit_field.jump_to_source_peripheral.connect(self._on_jump_to_source_peripheral)
        
        layout.addWidget(self.address_map)
        layout.addWidget(self.bit_field)
        
        self.current_peripheral = None
        self.current_register = None
        self.state_manager = None  # 存储状态管理器引用
        self.tree_widget = None  # 存储树状图控件引用
    
    def _on_jump_to_source_peripheral(self, source_peripheral_name: str):
        """跳转到源外设"""
        import sys
        print(f"[DEBUG] _on_jump_to_source_peripheral called with: {source_peripheral_name}", file=sys.stderr)
        print(f"[DEBUG] hasattr(self, 'main_window'): {hasattr(self, 'main_window')}", file=sys.stderr)
        print(f"[DEBUG] self.main_window: {getattr(self, 'main_window', None)}", file=sys.stderr)
        print(f"[DEBUG] self.tree_widget: {self.tree_widget}", file=sys.stderr)
        
        # 直接调用主窗口的 on_jump_to_peripheral 方法（主要方案）
        if hasattr(self, 'main_window') and self.main_window:
            print(f"[DEBUG] Calling main_window.on_jump_to_peripheral directly", file=sys.stderr)
            print(f"[DEBUG] hasattr(self.main_window, 'on_jump_to_peripheral'): {hasattr(self.main_window, 'on_jump_to_peripheral')}", file=sys.stderr)
            print(f"[DEBUG] self.main_window.on_jump_to_peripheral: {getattr(self.main_window, 'on_jump_to_peripheral', None)}", file=sys.stderr)
            try:
                self.main_window.on_jump_to_peripheral(source_peripheral_name)
                print(f"[DEBUG] main_window.on_jump_to_peripheral called", file=sys.stderr)
            except Exception as e:
                print(f"[DEBUG] Error calling main_window.on_jump_to_peripheral: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
        else:
            print(f"[DEBUG] main_window not available", file=sys.stderr)
        
        # 同步树状图选择状态（无论state_manager是否可用）
        # 注意：需要在调用main_window.on_jump_to_peripheral之后，因为update_visualization会设置tree_widget
        if self.tree_widget:
            print(f"[DEBUG] Tree widget available, trying to find peripheral: {source_peripheral_name}", file=sys.stderr)
            # 查找外设项
            found = False
            for i in range(self.tree_widget.topLevelItemCount()):
                item = self.tree_widget.topLevelItem(i)
                item_text = item.text(0)
                print(f"[DEBUG] Checking item {i}: {item_text}", file=sys.stderr)
                if item_text == source_peripheral_name:
                    self.tree_widget.setCurrentItem(item)
                    self.tree_widget.scrollToItem(item)
                    print(f"[DEBUG] Tree widget selection updated to: {source_peripheral_name}", file=sys.stderr)
                    found = True
                    break
            if not found:
                print(f"[DEBUG] Peripheral {source_peripheral_name} not found in tree widget", file=sys.stderr)
        else:
            print(f"[DEBUG] Tree widget not available", file=sys.stderr)
        
        # 直接调用主窗口的 on_jump_to_peripheral 方法（主要方案）
        if hasattr(self, 'main_window') and self.main_window:
            print(f"[DEBUG] Calling main_window.on_jump_to_peripheral directly", file=sys.stderr)
            print(f"[DEBUG] hasattr(self.main_window, 'on_jump_to_peripheral'): {hasattr(self.main_window, 'on_jump_to_peripheral')}", file=sys.stderr)
            print(f"[DEBUG] self.main_window.on_jump_to_peripheral: {getattr(self.main_window, 'on_jump_to_peripheral', None)}", file=sys.stderr)
            try:
                self.main_window.on_jump_to_peripheral(source_peripheral_name)
                print(f"[DEBUG] main_window.on_jump_to_peripheral called", file=sys.stderr)
            except Exception as e:
                print(f"[DEBUG] Error calling main_window.on_jump_to_peripheral: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
        else:
            print(f"[DEBUG] main_window not available", file=sys.stderr)
        
        # 如果state_manager可用，也更新状态管理器的选择状态
        if self.state_manager:
            # 设置选中的外设为源外设
            self.state_manager.set_selection(peripheral=source_peripheral_name)
            
            # 发射信号，通知主窗口更新可视化控件
            print(f"[DEBUG] Emitting jump_to_peripheral signal with: {source_peripheral_name}", file=sys.stderr)
            self.jump_to_peripheral.emit(source_peripheral_name)
            print(f"[DEBUG] jump_to_peripheral signal emitted", file=sys.stderr)
        
    def show_peripheral(self, peripheral):
        """显示外设可视化"""
        self.current_peripheral = peripheral
        self.current_register = None
        
        # 处理继承类型外设：如果有derived_from且不为空，获取基类外设的寄存器
        if peripheral and peripheral.derived_from and peripheral.derived_from.strip() and self.main_window:
            # 获取基类外设
            base_periph_name = peripheral.derived_from
            # 尝试通过state_manager获取device_info
            device_info = None
            if hasattr(self.main_window, 'state_manager'):
                device_info = self.main_window.state_manager.device_info
            elif hasattr(self.main_window, 'device_info'):
                device_info = self.main_window.device_info
            
            if (device_info and
                hasattr(device_info, 'peripherals') and
                base_periph_name in device_info.peripherals):
                
                base_peripheral = device_info.peripherals[base_periph_name]
                # 创建合并的寄存器列表：当前外设的寄存器 + 基类外设的寄存器
                # 但注意：当前外设可能没有自己的寄存器定义
                all_registers = {}
                
                # 首先添加基类外设的寄存器
                if hasattr(base_peripheral, 'registers'):
                    for reg_name, reg in base_peripheral.registers.items():
                        all_registers[reg_name] = reg
                
                # 然后添加当前外设的寄存器（如果有，会覆盖基类的同名寄存器）
                if hasattr(peripheral, 'registers'):
                    for reg_name, reg in peripheral.registers.items():
                        all_registers[reg_name] = reg
                
                # 创建一个临时的外设对象用于显示
                display_peripheral = Peripheral(
                    name=peripheral.name,
                    base_address=peripheral.base_address,
                    description=peripheral.description,
                    display_name=peripheral.display_name,
                    group_name=peripheral.group_name,
                    derived_from=peripheral.derived_from,
                    address_block=peripheral.address_block.copy(),
                    registers=all_registers,
                    interrupts=peripheral.interrupts.copy() if hasattr(peripheral, 'interrupts') else []
                )
                self.address_map.set_peripheral(display_peripheral)
                
                # 对于继承外设，只显示继承信息，不显示位域图
                self.bit_field.set_register(None, base_periph_name)
            else:
                # 基类外设不存在，只显示当前外设的寄存器
                self.address_map.set_peripheral(peripheral)
                self.bit_field.set_register(None)
        else:
            # 非继承类型外设，正常显示
            self.address_map.set_peripheral(peripheral)
            self.bit_field.set_register(None)
        
    def show_register(self, register, source_peripheral_name=None):
        """显示寄存器可视化（需提前设置外设）
        
        Args:
            register: 寄存器对象
            source_peripheral_name: 源外设名称（用于继承外设）
        """
        self.current_register = register
        self.bit_field.set_register(register, source_peripheral_name)
        
    def show_peripheral_and_register(self, peripheral, register):
        """同时显示外设和寄存器"""
        self.show_peripheral(peripheral)
        self.show_register(register)
        
    def show_field(self, field):
        """显示位域可视化（高亮选中的位域）"""
        if self.current_register:
            # 高亮选中的位域
            self.bit_field.set_selected_field(field.name if field else None)
        else:
            # 如果没有当前寄存器，清空位域图
            self.bit_field.set_register(None)