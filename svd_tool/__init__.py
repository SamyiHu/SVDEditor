# svd_tool/__init__.py
"""
SVD工具包
"""

__version__ = "V1.2"
__author__ = "SamyiHu"
__author_url__ = "https://github.com/SamyiHu"
__license__ = "GPL-3.0"
__description__ = "A powerful CMSIS SVD file generation and parsing tool"

from .core.data_model import (
    DeviceInfo, Peripheral, Register, Field, Interrupt, CPUInfo
)
from .core.svd_parser import SVDParser, SVDFastParser
from .core.svd_generator import SVDGenerator
from .core.validators import Validator, ValidationError

# MainWindow 惰性导入：CLI / MCP Server 等非 GUI 场景不应强制依赖 PyQt6
def __getattr__(name):
    if name == "MainWindow":
        from .ui.main_window_refactored import MainWindowRefactored as MainWindow
        return MainWindow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

# 导出主要类
__all__ = [
    # 核心类
    "DeviceInfo",
    "Peripheral", 
    "Register",
    "Field",
    "Interrupt",
    "CPUInfo",
    
    # 工具类
    "SVDParser",
    "SVDFastParser",
    "SVDGenerator",
    "Validator",
    "ValidationError",
    
    # UI类
    "MainWindow",
]