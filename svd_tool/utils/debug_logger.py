"""
调试日志工具
提供统一的调试日志输出接口，支持全局禁用
"""
import sys
from typing import Optional

# 全局调试日志开关
_debug_enabled = True


def set_debug_enabled(enabled: bool):
    """
    设置调试日志是否启用
    
    Args:
        enabled: 是否启用调试日志
    """
    global _debug_enabled
    _debug_enabled = enabled


def is_debug_enabled() -> bool:
    """
    获取调试日志是否启用
    
    Returns:
        是否启用调试日志
    """
    return _debug_enabled


def debug_print(message: str, prefix: str = "DEBUG"):
    """
    统一的调试日志输出函数
    
    Args:
        message: 日志消息
        prefix: 日志前缀（默认为"DEBUG"）
    """
    if _debug_enabled:
        print(f"[{prefix}] {message}", file=sys.stderr)


def debug_print_preview(message: str):
    """
    预览相关的调试日志输出
    
    Args:
        message: 日志消息
    """
    debug_print(message, "DEBUG PREVIEW")


def debug_print_layout(message: str):
    """
    布局相关的调试日志输出
    
    Args:
        message: 日志消息
    """
    debug_print(message, "DEBUG LAYOUT MANAGER")


def debug_print_preview_manager(message: str):
    """
    预览管理器相关的调试日志输出
    
    Args:
        message: 日志消息
    """
    debug_print(message, "DEBUG PREVIEW MANAGER")


def debug_print_main_window(message: str):
    """
    主窗口相关的调试日志输出
    
    Args:
        message: 日志消息
    """
    debug_print(message, "DEBUG MAIN WINDOW")


def debug_print_error(message: str, prefix: str = "ERROR"):
    """
    错误相关的调试日志输出
    
    Args:
        message: 日志消息
        prefix: 日志前缀（默认为"ERROR"）
    """
    if _debug_enabled:
        print(f"[{prefix}] {message}", file=sys.stderr)
