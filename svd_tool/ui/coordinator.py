"""
中央协调器
负责管理组件间的通信，减少直接耦合，实现依赖注入和事件驱动架构
"""
import logging
from typing import Dict, Any, Optional, Callable
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot


class Coordinator(QObject):
    """中央协调器，管理组件间的通信"""
    
    # 全局事件信号
    device_info_updated = pyqtSignal(object)  # 设备信息更新
    file_loaded = pyqtSignal(object)  # 文件加载完成
    file_saved = pyqtSignal(str)  # 文件保存完成
    peripheral_added = pyqtSignal(str)  # 外设添加
    peripheral_updated = pyqtSignal(str)  # 外设更新
    peripheral_deleted = pyqtSignal(str)  # 外设删除
    selection_changed = pyqtSignal(dict)  # 选择变化
    status_updated = pyqtSignal(str)  # 状态更新
    data_stats_updated = pyqtSignal(dict)  # 数据统计更新
    
    def __init__(self):
        """初始化协调器"""
        super().__init__()
        self.logger = logging.getLogger("Coordinator")
        
        # 组件注册表
        self._components: Dict[str, Any] = {}
        
        # 服务注册表
        self._services: Dict[str, Any] = {}
        
        # 事件监听器
        self._event_listeners: Dict[str, list] = {}
        
        self.logger.info("协调器初始化完成")
    
    def register_component(self, name: str, component: Any):
        """注册组件"""
        if name in self._components:
            self.logger.warning(f"组件 '{name}' 已存在，将被覆盖")
        
        self._components[name] = component
        self.logger.debug(f"注册组件: {name}")
        
        # 如果组件有初始化方法，调用它
        if hasattr(component, 'set_coordinator'):
            component.set_coordinator(self)
    
    def get_component(self, name: str) -> Optional[Any]:
        """获取组件"""
        return self._components.get(name)
    
    def register_service(self, name: str, service: Any):
        """注册服务"""
        if name in self._services:
            self.logger.warning(f"服务 '{name}' 已存在，将被覆盖")
        
        self._services[name] = service
        self.logger.debug(f"注册服务: {name}")
    
    def get_service(self, name: str) -> Optional[Any]:
        """获取服务"""
        return self._services.get(name)
    
    def register_event_listener(self, event_type: str, callback: Callable):
        """注册事件监听器"""
        if event_type not in self._event_listeners:
            self._event_listeners[event_type] = []
        
        self._event_listeners[event_type].append(callback)
        self.logger.debug(f"注册事件监听器: {event_type}")
    
    def emit_event(self, event_type: str, data: Any = None):
        """触发事件"""
        self.logger.debug(f"触发事件: {event_type}")
        
        # 调用全局信号
        if event_type == "device_info_updated":
            self.device_info_updated.emit(data)
        elif event_type == "file_loaded":
            self.file_loaded.emit(data)
        elif event_type == "file_saved":
            self.file_saved.emit(data)
        elif event_type == "peripheral_added":
            self.peripheral_added.emit(data)
        elif event_type == "peripheral_updated":
            self.peripheral_updated.emit(data)
        elif event_type == "peripheral_deleted":
            self.peripheral_deleted.emit(data)
        elif event_type == "selection_changed":
            self.selection_changed.emit(data)
        elif event_type == "status_updated":
            self.status_updated.emit(data)
        elif event_type == "data_stats_updated":
            self.data_stats_updated.emit(data)
        
        # 调用注册的监听器
        if event_type in self._event_listeners:
            for callback in self._event_listeners[event_type]:
                try:
                    callback(data)
                except Exception as e:
                    self.logger.error(f"事件监听器调用失败: {e}")
    
    # 便捷方法
    def get_state_manager(self):
        """获取状态管理器"""
        return self.get_component("state_manager")
    
    def get_layout_manager(self):
        """获取布局管理器"""
        return self.get_component("layout_manager")
    
    def get_peripheral_manager(self):
        """获取外设管理器"""
        return self.get_component("peripheral_manager")
    
    def get_file_operations(self):
        """获取文件操作管理器"""
        return self.get_component("file_operations")
    
    def get_device_info_manager(self):
        """获取设备信息管理器"""
        return self.get_component("device_info_manager")
    
    def update_status(self, message: str):
        """更新状态"""
        self.emit_event("status_updated", message)
    
    def update_data_stats(self, stats: Dict[str, Any]):
        """更新数据统计"""
        self.emit_event("data_stats_updated", stats)
    
    def notify_selection_changed(self, selection: Dict[str, Any]):
        """通知选择变化"""
        self.emit_event("selection_changed", selection)
    
    def notify_device_info_updated(self, device_info):
        """通知设备信息更新"""
        self.emit_event("device_info_updated", device_info)
    
    def notify_file_loaded(self, device_info):
        """通知文件加载完成"""
        self.emit_event("file_loaded", device_info)
    
    def notify_file_saved(self, file_path: str):
        """通知文件保存完成"""
        self.emit_event("file_saved", file_path)

    def notify_peripheral_added(self, peripheral_name: str):
        """通知外设添加"""
        self.emit_event("peripheral_added", peripheral_name)
    
    def notify_peripheral_updated(self, peripheral_name: str):
        """通知外设更新"""
        self.emit_event("peripheral_updated", peripheral_name)
    
    def notify_peripheral_deleted(self, peripheral_name: str):
        """通知外设删除"""
        self.emit_event("peripheral_deleted", peripheral_name)
    
    # 服务方法
    def get_widget(self, widget_name: str):
        """获取控件（通过布局管理器）"""
        layout_manager = self.get_layout_manager()
        if layout_manager and hasattr(layout_manager, 'get_widget'):
            return layout_manager.get_widget(widget_name)
        return None
    
    def get_device_info(self):
        """获取设备信息（通过状态管理器）"""
        state_manager = self.get_state_manager()
        if state_manager and hasattr(state_manager, 'device_info'):
            return state_manager.device_info
        return None
    
    def validate_device_info(self):
        """验证设备信息"""
        device_info_manager = self.get_device_info_manager()
        if device_info_manager and hasattr(device_info_manager, 'validate_device_info'):
            return device_info_manager.validate_device_info()
        return []
    
    def update_device_info_from_ui(self):
        """从UI更新设备信息"""
        device_info_manager = self.get_device_info_manager()
        if device_info_manager and hasattr(device_info_manager, 'update_device_info_from_ui'):
            return device_info_manager.update_device_info_from_ui()
        return None

    def open_svd_file(self):
        """打开SVD文件"""
        file_operations = self.get_file_operations()
        if file_operations and hasattr(file_operations, 'open_svd_file'):
            return file_operations.open_svd_file()
        return None
    
    def save_svd_file(self):
        """保存SVD文件"""
        file_operations = self.get_file_operations()
        if file_operations and hasattr(file_operations, 'save_svd_file'):
            return file_operations.save_svd_file()
        return None
    
    def save_svd_file_as(self):
        """另存为SVD文件"""
        file_operations = self.get_file_operations()
        if file_operations and hasattr(file_operations, 'save_svd_file_as'):
            return file_operations.save_svd_file_as()
        return None
    
    def add_peripheral(self):
        """添加外设"""
        peripheral_manager = self.get_peripheral_manager()
        if peripheral_manager and hasattr(peripheral_manager, 'add_peripheral_dialog'):
            return peripheral_manager.add_peripheral_dialog()
        return None
    
    def edit_peripheral(self, peripheral_name: str = None):
        """编辑外设"""
        peripheral_manager = self.get_peripheral_manager()
        if peripheral_manager and hasattr(peripheral_manager, 'edit_peripheral'):
            return peripheral_manager.edit_peripheral(peripheral_name)
        return None
    
    def delete_peripheral(self, peripheral_name: str = None):
        """删除外设"""
        peripheral_manager = self.get_peripheral_manager()
        if peripheral_manager and hasattr(peripheral_manager, 'delete_selected_peripheral'):
            return peripheral_manager.delete_selected_peripheral()
        return None