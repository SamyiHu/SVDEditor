"""
控件管理器
负责管理UI控件的引用
"""
from typing import Dict, Any, Optional


class WidgetManager:
    """控件管理器"""

    def __init__(self):
        """初始化控件管理器"""
        self.widgets: Dict[str, Any] = {}

    def register_widget(self, name: str, widget: Any):
        """
        注册控件

        Args:
            name: 控件名称
            widget: 控件对象
        """
        self.widgets[name] = widget

    def register_widgets(self, widgets: Dict[str, Any]):
        """
        批量注册控件

        Args:
            widgets: 控件字典
        """
        self.widgets.update(widgets)

    def get_widget(self, name: str) -> Optional[Any]:
        """
        获取控件

        Args:
            name: 控件名称

        Returns:
            控件对象，如果不存在则返回None
        """
        return self.widgets.get(name)

    def has_widget(self, name: str) -> bool:
        """
        检查控件是否存在

        Args:
            name: 控件名称

        Returns:
            如果控件存在返回True，否则返回False
        """
        return name in self.widgets

    def remove_widget(self, name: str):
        """
        移除控件

        Args:
            name: 控件名称
        """
        if name in self.widgets:
            del self.widgets[name]

    def clear(self):
        """清空所有控件"""
        self.widgets.clear()

    def get_all_widgets(self) -> Dict[str, Any]:
        """
        获取所有控件

        Returns:
            所有控件的字典
        """
        return self.widgets.copy()
