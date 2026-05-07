"""
MainWindow 包 - Mixin 组合模式拆分的主窗口

将原来的 God Object (main_window_refactored.py, 3556行) 拆分为:
- _base.py: 核心初始化、信号连接
- _file_actions.py: 文件操作
- _edit_actions.py: 编辑操作
- _document_actions.py: 文档管理
- _view_actions.py: 视图/预览
- _tool_actions.py: 工具/搜索/验证
- _settings_actions.py: 设置/主题/日志
- _event_handlers.py: 事件处理
"""

from ._base import MainWindowRefactored

__all__ = ['MainWindowRefactored']
