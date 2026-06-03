"""
中断管理器
负责管理中断的添加、编辑、删除和表格更新
"""
import logging
from typing import Optional

from PyQt6.QtWidgets import QTableWidget, QMessageBox, QMenu, QTableWidgetItem
from ...i18n.i18n import t


class InterruptManager:
    """中断管理器"""
    
    def __init__(self, coordinator=None):
        """初始化中断管理器"""
        self.coordinator = coordinator
        self.logger = logging.getLogger("InterruptManager")
        
        self.logger.info("Interrupt manager initialized")
    
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
    
    def add_interrupt(self):
        """添加中断"""
        state_manager = self.get_state_manager()
        if not state_manager:
            return
        
        # 获取外设列表
        periph_list = list(state_manager.device_info.peripherals.keys())
        
        # 获取对话框工厂
        dialog_factory = self.get_dialog_factory()
        if not dialog_factory:
            self.logger.error(t("warning.dialog_factory_not_found"))
            return
        
        # 创建中断对话框
        dialog = dialog_factory.create_interrupt_dialog(
            interrupt=None,
            peripherals=periph_list,
            is_edit=False
        )
        
        if dialog.exec():
            result = getattr(dialog, "result_data", None)
            if result is None:
                return
            
            # 创建中断对象
            from ..core.data_model import Interrupt
            peripherals = result.get("peripherals", [result["peripheral"]] if result.get("peripheral") else [])
            interrupt = Interrupt(
                name=result["name"],
                value=result["value"],  # 保持为int
                description=result["description"],
                peripheral=result["peripheral"],
                peripherals=peripherals
            )
            
            # 使用StateManager添加中断
            state_manager.add_interrupt(interrupt)
            
            # 更新中断表格
            self._update_interrupt_table()
            
            # 更新状态
            layout_manager = self.get_layout_manager()
            if layout_manager:
                layout_manager.update_status(f"已添加中断: {interrupt.name}")
            self.logger.info(f"添加中断: {interrupt.name}")
            
            # 发射数据变化信号
            main_window = self.coordinator.get_component("main_window")
            if main_window and hasattr(main_window, 'data_changed'):
                main_window.data_changed.emit()
    
    def edit_interrupt(self, interrupt_name: str = None):
        """编辑中断"""
        state_manager = self.get_state_manager()
        if not state_manager:
            return
        
        # 如果没有提供中断名，尝试从当前选择获取
        if interrupt_name is None:
            # 获取中断表格当前选中的行
            irq_table = self.get_widget('irq_table')
            if not irq_table:
                QMessageBox.warning(None, t("error.title_warning"), t("msg.irq_table_not_found"))
                return
            
            selected_rows = irq_table.selectedItems()
            if not selected_rows:
                QMessageBox.warning(None, t("error.title_warning"), t("msg.select_irq_first"))
                return
            
            # 获取第一列（名称列）的文本
            interrupt_name = selected_rows[0].text()
        
        # 检查中断是否存在
        if interrupt_name not in state_manager.device_info.interrupts:
            QMessageBox.warning(None, t("error.title_warning"), t("msg.irq_not_exist", name=interrupt_name))
            return
        
        # 获取中断对象
        interrupt = state_manager.device_info.interrupts[interrupt_name]
        
        # 获取外设列表
        periph_list = list(state_manager.device_info.peripherals.keys())
        
        # 获取对话框工厂
        dialog_factory = self.get_dialog_factory()
        if not dialog_factory:
            self.logger.error("对话框工厂未找到")
            return
        
        # 创建中断对话框
        dialog = dialog_factory.create_interrupt_dialog(
            interrupt=interrupt,
            peripherals=periph_list,
            is_edit=True
        )
        
        if dialog.exec():
            result = getattr(dialog, "result_data", None)
            if result is None:
                return
            
            # 检查名称是否更改
            old_name = interrupt_name
            new_name = result["name"]
            name_changed = old_name != new_name
            
            # 创建更新后的中断对象
            from ..core.data_model import Interrupt
            updated_peripherals = result.get("peripherals", [result["peripheral"]] if result.get("peripheral") else [])
            updated_interrupt = Interrupt(
                name=new_name,
                value=result["value"],  # 保持为int
                description=result["description"],
                peripheral=result["peripheral"],
                peripherals=updated_peripherals
            )
            
            # 使用StateManager更新中断
            if name_changed:
                # 先删除旧的，再添加新的
                state_manager.delete_interrupt(old_name)
                state_manager.add_interrupt(updated_interrupt)
            else:
                # 直接更新
                state_manager.update_interrupt(old_name, updated_interrupt)
            
            # 更新中断表格
            self._update_interrupt_table()
            
            # 更新状态
            layout_manager = self.get_layout_manager()
            if layout_manager:
                layout_manager.update_status(f"已更新中断: {new_name}")
            self.logger.info(f"编辑中断: {old_name} -> {new_name}")
            
            # 发射数据变化信号
            main_window = self.coordinator.get_component("main_window")
            if main_window and hasattr(main_window, 'data_changed'):
                main_window.data_changed.emit()
    
    def delete_interrupt(self, interrupt_name: str = None):
        """删除中断"""
        state_manager = self.get_state_manager()
        if not state_manager:
            return
        
        # 如果没有提供中断名，尝试从当前选择获取
        if interrupt_name is None:
            # 获取中断表格当前选中的行
            irq_table = self.get_widget('irq_table')
            if not irq_table:
                QMessageBox.warning(None, t("error.title_warning"), t("msg.irq_table_not_found"))
                return
            
            selected_rows = irq_table.selectedItems()
            if not selected_rows:
                QMessageBox.warning(None, t("error.title_warning"), t("msg.select_irq_first"))
                return
            
            # 获取第一列（名称列）的文本
            interrupt_name = selected_rows[0].text()
        
        # 检查中断是否存在
        if interrupt_name not in state_manager.device_info.interrupts:
            QMessageBox.warning(None, t("error.title_warning"), t("msg.irq_not_exist", name=interrupt_name))
            return
        
        # 确认删除
        reply = QMessageBox.question(
            None, t("msg.confirm_delete_title"),
            t("msg.confirm_delete_irq", name=interrupt_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # 使用StateManager删除中断
        state_manager.delete_interrupt(interrupt_name)
        
        # 更新中断表格
        self._update_interrupt_table()
        
        # 更新状态
        layout_manager = self.get_layout_manager()
        if layout_manager:
            layout_manager.update_status(f"已删除中断: {interrupt_name}")
        self.logger.info(f"删除中断: {interrupt_name}")
        
        # 发射数据变化信号
        main_window = self.coordinator.get_component("main_window")
        if main_window and hasattr(main_window, 'data_changed'):
            main_window.data_changed.emit()
    
    def _update_interrupt_table(self):
        """更新中断表格"""
        irq_table = self.get_widget('irq_table')
        if not irq_table:
            return
        
        state_manager = self.get_state_manager()
        if not state_manager:
            return
        
        # 清空表格
        irq_table.setRowCount(0)
        
        # 获取所有中断
        interrupts = state_manager.device_info.interrupts
        
        # 按中断值排序
        sorted_interrupts = sorted(interrupts.values(), key=lambda x: x.value)
        
        # 填充表格（列顺序：名称、值、外设、描述）
        for i, interrupt in enumerate(sorted_interrupts):
            irq_table.insertRow(i)
            irq_table.setItem(i, 0, QTableWidgetItem(interrupt.name))
            irq_table.setItem(i, 1, QTableWidgetItem(str(interrupt.value)))
            # 显示所有关联外设（逗号分隔）
            periph_display = ", ".join(interrupt.peripherals) if interrupt.peripherals else (interrupt.peripheral or "")
            irq_table.setItem(i, 2, QTableWidgetItem(periph_display))
            irq_table.setItem(i, 3, QTableWidgetItem(interrupt.description or ""))
    
    def update_interrupt_buttons_state(self):
        """更新中断按钮状态（根据表格选择）"""
        irq_table = self.get_widget('irq_table')
        if not irq_table:
            return
        
        # 获取按钮
        edit_irq_btn = self.get_widget('edit_irq_btn')
        delete_irq_btn = self.get_widget('delete_irq_btn')
        
        # 检查是否有选中项
        has_selection = len(irq_table.selectedItems()) > 0
        
        # 更新按钮状态
        if edit_irq_btn:
            edit_irq_btn.setEnabled(has_selection)
        if delete_irq_btn:
            delete_irq_btn.setEnabled(has_selection)
    
    def on_irq_context_menu(self, pos):
        """中断表格右键菜单"""
        irq_table = self.get_widget('irq_table')
        if not irq_table:
            return
        
        item = irq_table.itemAt(pos)
        if not item:
            return
        
        row = item.row()
        interrupt_name = irq_table.item(row, 0).text()
        
        # 创建右键菜单
        menu = QMenu(irq_table)
        
        edit_action = menu.addAction("编辑中断")
        delete_action = menu.addAction("删除中断")
        
        # 执行菜单动作
        action = menu.exec(irq_table.mapToGlobal(pos))
        if action == edit_action:
            self.edit_interrupt(interrupt_name)
        elif action == delete_action:
            self.delete_interrupt(interrupt_name)
