"""
可视化控件管理器
负责管理可视化控件的显示和交互
"""
import logging
from typing import Optional

from PyQt6.QtWidgets import QTreeWidget


class VisualizationManager:
    """可视化控件管理器"""
    
    def __init__(self, coordinator=None):
        """初始化可视化控件管理器"""
        self.coordinator = coordinator
        self.logger = logging.getLogger("VisualizationManager")
        
        self.logger.info("可视化控件管理器初始化完成")
    
    def set_coordinator(self, coordinator):
        """设置协调器（依赖注入）"""
        self.coordinator = coordinator
    
    def get_widget(self, widget_name: str):
        """获取控件（通过协调器）"""
        if self.coordinator:
            return self.coordinator.get_widget(widget_name)
        return None
    
    def get_state_manager(self):
        """获取状态管理器"""
        if self.coordinator:
            return self.coordinator.get_state_manager()
        return None
    
    def update_visualization(self, peripheral: str, register: str, field: str):
        """更新可视化控件显示"""
        visualization_widget = self.get_widget('visualization_widget')
        if not visualization_widget:
            return
        
        # 设置状态管理器引用
        state_manager = self.get_state_manager()
        visualization_widget.state_manager = state_manager
        
        # 设置树状图引用
        tree_widget = self.get_widget('periph_tree')
        visualization_widget.tree_widget = tree_widget
        
        # 获取设备信息
        state_manager = self.get_state_manager()
        if not state_manager:
            return
        
        device_info = state_manager.device_info
        
        if peripheral:
            # 显示外设
            if peripheral in device_info.peripherals:
                periph = device_info.peripherals[peripheral]
                visualization_widget.show_peripheral(periph)
                
                if register:
                    # 显示寄存器
                    if register in periph.registers:
                        reg = periph.registers[register]
                        # 如果是继承外设，传递源外设名称
                        source_peripheral_name = periph.derived_from if periph.derived_from else None
                        visualization_widget.show_register(reg, source_peripheral_name)
                        
                        if field:
                            # 显示位域
                            if field in reg.fields:
                                field_obj = reg.fields[field]
                                visualization_widget.show_field(field_obj)
                            else:
                                visualization_widget.show_field(None)
                        else:
                            visualization_widget.show_field(None)
                    else:
                        visualization_widget.show_register(None)
                else:
                    visualization_widget.show_register(None)
            else:
                visualization_widget.show_peripheral(None)
        else:
            # 没有选中外设，清空可视化
            visualization_widget.show_peripheral(None)
    
    def on_field_clicked(self, field):
        """位域点击事件处理"""
        # 获取当前选择
        state_manager = self.get_state_manager()
        if not state_manager:
            return
        
        selection = state_manager.get_selection()
        peripheral = selection.get('peripheral')
        register = selection.get('register')
        
        if not peripheral or not register:
            return
        
        # 设置选择
        state_manager.set_selection(
            peripheral=peripheral,
            register=register,
            field=field.name if field else None
        )
        
        # 更新树控件中的选择
        if field and peripheral and register:
            periph_tree = self.get_widget('periph_tree')
            if periph_tree:
                # 使用 peripheral_manager 的选择方法（兼容新旧 API）
                main_window = self.main_window
                if main_window and hasattr(main_window, 'peripheral_manager'):
                    main_window.peripheral_manager.select_field(peripheral, register, field.name)

    def on_register_clicked(self, register):
        """寄存器点击事件处理"""
        # 获取当前选择
        state_manager = self.get_state_manager()
        if not state_manager:
            return

        selection = state_manager.get_selection()
        peripheral = selection.get('peripheral')

        if not peripheral:
            return

        # 设置选择
        state_manager.set_selection(
            peripheral=peripheral,
            register=register.name if register else None,
            field=None
        )

        # 更新树控件中的选择
        if register and peripheral:
            periph_tree = self.get_widget('periph_tree')
            if periph_tree:
                main_window = self.main_window
                if main_window and hasattr(main_window, 'peripheral_manager'):
                    main_window.peripheral_manager.select_register(peripheral, register.name)
