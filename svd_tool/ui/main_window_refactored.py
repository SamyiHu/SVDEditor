"""
主窗口重导出 - 向后兼容

原始的 God Object 已拆分为 svd_tool/ui/main_window/ 包中的 Mixin 文件。
此文件保留以维持所有现有 import 路径不变。
"""

from .main_window import MainWindowRefactored

__all__ = ['MainWindowRefactored']
