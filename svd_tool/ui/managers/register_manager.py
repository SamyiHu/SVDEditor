"""
寄存器和位域管理器
负责管理寄存器和位域的添加、编辑、删除
"""
import logging
from typing import Optional

from PyQt6.QtWidgets import QMessageBox
from ...i18n.i18n import t


class RegisterManager:
    """寄存器和位域管理器"""
    
    def __init__(self, coordinator=None):
        """初始化寄存器和位域管理器"""
        self.coordinator = coordinator
        self.logger = logging.getLogger("RegisterManager")
        
        self.logger.info("Register and field manager initialized")
    
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
    
    def get_dialog_factory(self):
        """获取对话框工厂"""
        if self.coordinator:
            main_window = self.coordinator.get_component("main_window")
            if main_window and hasattr(main_window, 'dialog_factory'):
                return main_window.dialog_factory
        return None
    
    def get_layout_manager(self):
        """获取布局管理器"""
        if self.coordinator:
            return self.coordinator.get_layout_manager()
        return None
    
    def get_peripheral_manager(self):
        """获取外设管理器"""
        if self.coordinator:
            return self.coordinator.get_peripheral_manager()
        return None
    
    def _get_current_selection(self):
        """获取当前选择的外设和寄存器"""
        state_manager = self.get_state_manager()
        if not state_manager:
            return None, None
        
        selection = state_manager.get_selection()
        peripheral = selection.get('peripheral')
        register = selection.get('register')
        
        return peripheral, register
    
    def add_register(self):
        """添加寄存器"""
        peripheral, _ = self._get_current_selection()
        if not peripheral:
            QMessageBox.warning(None, t("message.warning"), t("msg.select_peripheral_first"))
            return
        
        state_manager = self.get_state_manager()
        if not state_manager:
            return
        
        # 获取对话框工厂
        dialog_factory = self.get_dialog_factory()
        if not dialog_factory:
            self.logger.error(t("warning.dialog_factory_not_found"))
            return
        
        # 创建寄存器对话框
        dialog = dialog_factory.create_register_dialog(
            register=None,
            is_edit=False
        )
        
        if dialog.exec():
            result = getattr(dialog, "result_data", None)
            if result is None:
                return
            
            # 创建寄存器对象
            from ..core.data_model import Register
            register = Register(
                name=result["name"],
                offset=result["offset"],
                size=result["size"],
                access=result["access"],
                reset_value=result["reset_value"],
                description=result["description"]
            )
            
            # 使用StateManager添加寄存器
            state_manager.add_register(peripheral, register)
            
            # 更新外设树
            peripheral_manager = self.get_peripheral_manager()
            if peripheral_manager:
                peripheral_manager.update_peripheral_tree()
            
            # 更新状态
            layout_manager = self.get_layout_manager()
            if layout_manager:
                layout_manager.update_status(f"已添加寄存器: {register.name}")
            self.logger.info(f"添加寄存器: {register.name}")
            
            # 发射数据变化信号
            main_window = self.coordinator.get_component("main_window")
            if main_window and hasattr(main_window, 'data_changed'):
                main_window.data_changed.emit()
    
    def edit_register(self, reg_name: str = None):
        """编辑寄存器"""
        peripheral, current_register = self._get_current_selection()
        if not peripheral:
            QMessageBox.warning(None, "警告", "请先选择一个外设")
            return
        
        state_manager = self.get_state_manager()
        if not state_manager:
            return
        
        # 如果没有提供寄存器名，使用当前选择的寄存器
        if reg_name is None:
            reg_name = current_register
        
        if not reg_name:
            QMessageBox.warning(None, "警告", "请先选择一个寄存器")
            return
        
        # 检查寄存器是否存在
        if peripheral not in state_manager.device_info.peripherals:
            QMessageBox.warning(None, "警告", f"外设 '{peripheral}' 不存在")
            return
        
        periph = state_manager.device_info.peripherals[peripheral]
        if reg_name not in periph.registers:
            QMessageBox.warning(None, "警告", f"寄存器 '{reg_name}' 不存在")
            return
        
        # 获取寄存器对象
        register = periph.registers[reg_name]
        
        # 获取对话框工厂
        dialog_factory = self.get_dialog_factory()
        if not dialog_factory:
            self.logger.error("对话框工厂未找到")
            return
        
        # 创建寄存器对话框
        dialog = dialog_factory.create_register_dialog(
            register=register,
            is_edit=True
        )
        
        if dialog.exec():
            result = getattr(dialog, "result_data", None)
            if result is None:
                return
            
            # 检查名称是否更改
            old_name = reg_name
            new_name = result["name"]
            name_changed = old_name != new_name
            
            # 创建更新后的寄存器对象
            from ..core.data_model import Register
            updated_register = Register(
                name=new_name,
                offset=result["offset"],
                size=result["size"],
                access=result["access"],
                reset_value=result["reset_value"],
                description=result["description"]
            )
            
            # 使用StateManager更新寄存器
            if name_changed:
                # 先删除旧的，再添加新的
                state_manager.delete_register(peripheral, old_name)
                state_manager.add_register(peripheral, updated_register)
            else:
                # 直接更新
                state_manager.update_register(peripheral, old_name, updated_register)
            
            # 更新外设树
            peripheral_manager = self.get_peripheral_manager()
            if peripheral_manager:
                peripheral_manager.update_peripheral_tree()
            
            # 更新状态
            layout_manager = self.get_layout_manager()
            if layout_manager:
                layout_manager.update_status(f"已更新寄存器: {new_name}")
            self.logger.info(f"编辑寄存器: {old_name} -> {new_name}")
            
            # 发射数据变化信号
            main_window = self.coordinator.get_component("main_window")
            if main_window and hasattr(main_window, 'data_changed'):
                main_window.data_changed.emit()
    
    def delete_register(self, reg_name: str = None):
        """删除寄存器"""
        peripheral, current_register = self._get_current_selection()
        if not peripheral:
            QMessageBox.warning(None, "警告", "请先选择一个外设")
            return
        
        state_manager = self.get_state_manager()
        if not state_manager:
            return
        
        # 如果没有提供寄存器名，使用当前选择的寄存器
        if reg_name is None:
            reg_name = current_register
        
        if not reg_name:
            QMessageBox.warning(None, "警告", "请先选择一个寄存器")
            return
        
        # 检查寄存器是否存在
        if peripheral not in state_manager.device_info.peripherals:
            QMessageBox.warning(None, "警告", f"外设 '{peripheral}' 不存在")
            return
        
        periph = state_manager.device_info.peripherals[peripheral]
        if reg_name not in periph.registers:
            QMessageBox.warning(None, "警告", f"寄存器 '{reg_name}' 不存在")
            return
        
        # 确认删除
        reply = QMessageBox.question(
            None, "确认删除",
            f"确定要删除寄存器 '{reg_name}' 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # 使用StateManager删除寄存器
        state_manager.delete_register(peripheral, reg_name)
        
        # 更新外设树
        peripheral_manager = self.get_peripheral_manager()
        if peripheral_manager:
            peripheral_manager.update_peripheral_tree()
        
        # 更新状态
        layout_manager = self.get_layout_manager()
        if layout_manager:
            layout_manager.update_status(f"已删除寄存器: {reg_name}")
        self.logger.info(f"删除寄存器: {reg_name}")
        
        # 发射数据变化信号
        main_window = self.coordinator.get_component("main_window")
        if main_window and hasattr(main_window, 'data_changed'):
            main_window.data_changed.emit()
    
    def delete_multiple_registers(self, reg_names: list):
        """删除多个寄存器"""
        peripheral, _ = self._get_current_selection()
        if not peripheral:
            QMessageBox.warning(None, "警告", "请先选择一个外设")
            return
        
        state_manager = self.get_state_manager()
        if not state_manager:
            return
        
        # 确认删除
        reply = QMessageBox.question(
            None, "确认删除",
            f"确定要删除选中的 {len(reg_names)} 个寄存器吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # 删除所有选中的寄存器
        deleted_count = 0
        for reg_name in reg_names:
            try:
                state_manager.delete_register(peripheral, reg_name)
                deleted_count += 1
            except Exception as e:
                self.logger.error(f"删除寄存器 '{reg_name}' 失败: {e}")
        
        # 更新外设树
        peripheral_manager = self.get_peripheral_manager()
        if peripheral_manager:
            peripheral_manager.update_peripheral_tree()
        
        # 更新状态
        layout_manager = self.get_layout_manager()
        if layout_manager:
            layout_manager.update_status(f"已删除 {deleted_count} 个寄存器")
        self.logger.info(f"删除了 {deleted_count} 个寄存器")
        
        # 发射数据变化信号
        main_window = self.coordinator.get_component("main_window")
        if main_window and hasattr(main_window, 'data_changed'):
            main_window.data_changed.emit()
    
    def add_field(self):
        """添加位域"""
        peripheral, register = self._get_current_selection()
        if not peripheral or not register:
            QMessageBox.warning(None, "警告", "请先选择一个寄存器")
            return
        
        state_manager = self.get_state_manager()
        if not state_manager:
            return
        
        # 获取对话框工厂
        dialog_factory = self.get_dialog_factory()
        if not dialog_factory:
            self.logger.error("对话框工厂未找到")
            return
        
        # 创建位域对话框
        dialog = dialog_factory.create_field_dialog(
            field=None,
            is_edit=False
        )
        
        if dialog.exec():
            result = getattr(dialog, "result_data", None)
            if result is None:
                return
            
            # 创建位域对象
            from ..core.data_model import Field
            field = Field(
                name=result["name"],
                offset=result["offset"],
                width=result["width"],
                access=result["access"],
                description=result["description"]
            )
            
            # 使用StateManager添加位域
            state_manager.add_field(peripheral, register, field)
            
            # 更新位域表格
            layout_manager = self.get_layout_manager()
            if layout_manager:
                layout_manager.update_field_table(peripheral, register)
            
            # 更新状态
            if layout_manager:
                layout_manager.update_status(f"已添加位域: {field.name}")
            self.logger.info(f"添加位域: {field.name}")
            
            # 发射数据变化信号
            main_window = self.coordinator.get_component("main_window")
            if main_window and hasattr(main_window, 'data_changed'):
                main_window.data_changed.emit()
    
    def edit_field(self, field_name: str = None):
        """编辑位域"""
        peripheral, register = self._get_current_selection()
        if not peripheral or not register:
            QMessageBox.warning(None, "警告", "请先选择一个寄存器")
            return
        
        state_manager = self.get_state_manager()
        if not state_manager:
            return
        
        # 如果没有提供位域名，使用当前选择的位域
        if field_name is None:
            selection = state_manager.get_selection()
            field_name = selection.get('field')
        
        if not field_name:
            QMessageBox.warning(None, "警告", "请先选择一个位域")
            return
        
        # 检查位域是否存在
        if peripheral not in state_manager.device_info.peripherals:
            QMessageBox.warning(None, "警告", f"外设 '{peripheral}' 不存在")
            return
        
        periph = state_manager.device_info.peripherals[peripheral]
        if register not in periph.registers:
            QMessageBox.warning(None, "警告", f"寄存器 '{register}' 不存在")
            return
        
        reg = periph.registers[register]
        if field_name not in reg.fields:
            QMessageBox.warning(None, "警告", f"位域 '{field_name}' 不存在")
            return
        
        # 获取位域对象
        field = reg.fields[field_name]
        
        # 获取对话框工厂
        dialog_factory = self.get_dialog_factory()
        if not dialog_factory:
            self.logger.error("对话框工厂未找到")
            return
        
        # 创建位域对话框
        dialog = dialog_factory.create_field_dialog(
            field=field,
            is_edit=True
        )
        
        if dialog.exec():
            result = getattr(dialog, "result_data", None)
            if result is None:
                return
            
            # 检查名称是否更改
            old_name = field_name
            new_name = result["name"]
            name_changed = old_name != new_name
            
            # 创建更新后的位域对象
            from ..core.data_model import Field
            updated_field = Field(
                name=new_name,
                offset=result["offset"],
                width=result["width"],
                access=result["access"],
                description=result["description"]
            )
            
            # 使用StateManager更新位域
            if name_changed:
                # 先删除旧的，再添加新的
                state_manager.delete_field(peripheral, register, old_name)
                state_manager.add_field(peripheral, register, updated_field)
            else:
                # 直接更新
                state_manager.update_field(peripheral, register, old_name, updated_field)
            
            # 更新位域表格
            layout_manager = self.get_layout_manager()
            if layout_manager:
                layout_manager.update_field_table(peripheral, register)
            
            # 更新状态
            if layout_manager:
                layout_manager.update_status(f"已更新位域: {new_name}")
            self.logger.info(f"编辑位域: {old_name} -> {new_name}")
            
            # 发射数据变化信号
            main_window = self.coordinator.get_component("main_window")
            if main_window and hasattr(main_window, 'data_changed'):
                main_window.data_changed.emit()
    
    def delete_field(self, field_name: str = None):
        """删除位域"""
        peripheral, register = self._get_current_selection()
        if not peripheral or not register:
            QMessageBox.warning(None, "警告", "请先选择一个寄存器")
            return
        
        state_manager = self.get_state_manager()
        if not state_manager:
            return
        
        # 如果没有提供位域名，使用当前选择的位域
        if field_name is None:
            selection = state_manager.get_selection()
            field_name = selection.get('field')
        
        if not field_name:
            QMessageBox.warning(None, "警告", "请先选择一个位域")
            return
        
        # 检查位域是否存在
        if peripheral not in state_manager.device_info.peripherals:
            QMessageBox.warning(None, "警告", f"外设 '{peripheral}' 不存在")
            return
        
        periph = state_manager.device_info.peripherals[peripheral]
        if register not in periph.registers:
            QMessageBox.warning(None, "警告", f"寄存器 '{register}' 不存在")
            return
        
        reg = periph.registers[register]
        if field_name not in reg.fields:
            QMessageBox.warning(None, "警告", f"位域 '{field_name}' 不存在")
            return
        
        # 确认删除
        reply = QMessageBox.question(
            None, "确认删除",
            f"确定要删除位域 '{field_name}' 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # 使用StateManager删除位域
        state_manager.delete_field(peripheral, register, field_name)
        
        # 更新位域表格
        layout_manager = self.get_layout_manager()
        if layout_manager:
            layout_manager.update_field_table(peripheral, register)
        
        # 更新状态
        if layout_manager:
            layout_manager.update_status(f"已删除位域: {field_name}")
        self.logger.info(f"删除位域: {field_name}")
        
        # 发射数据变化信号
        main_window = self.coordinator.get_component("main_window")
        if main_window and hasattr(main_window, 'data_changed'):
            main_window.data_changed.emit()
