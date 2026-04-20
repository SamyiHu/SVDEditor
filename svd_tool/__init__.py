# svd_tool/__init__.py
"""
SVD工具包
"""

__version__ = "2.1.0"
__author__ = "SamyiHu"
__author_url__ = "https://github.com/SamyiHu"
__license__ = "Apache-2.0"
__description__ = "A powerful CMSIS SVD file generation and parsing tool"

from .core.data_model import (
    DeviceInfo, Peripheral, Register, Field, Interrupt, CPUInfo
)
from .core.svd_parser import SVDParser, SVDFastParser
from .core.svd_generator import SVDGenerator
from .core.validators import Validator, ValidationError
from .ui.main_window_refactored import MainWindowRefactored as MainWindow

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