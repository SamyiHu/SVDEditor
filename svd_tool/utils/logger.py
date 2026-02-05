# svd_tool/utils/logger.py
"""
日志工具模块
"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class Logger:
    """日志管理器"""
    
    def __init__(self, name: str = "svd_tool", log_file: Optional[str] = None):
        """
        初始化日志管理器
        
        Args:
            name: 日志名称
            log_file: 日志文件路径
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # 移除已有的处理器
        self.logger.handlers.clear()
        
        # 创建格式器
        self.formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 控制台处理器
        self.console_handler = logging.StreamHandler(sys.stdout)
        self.console_handler.setLevel(logging.INFO)  # 默认不显示DEBUG日志
        self.console_handler.setFormatter(self.formatter)
        self.logger.addHandler(self.console_handler)
        
        # 文件处理器
        self.file_handler = None
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            self.file_handler = logging.FileHandler(log_file, encoding='utf-8')
            self.file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别
            self.file_handler.setFormatter(self.formatter)
            self.logger.addHandler(self.file_handler)
        
        # 存储当前控制台日志级别
        self.console_log_level = logging.INFO
    
    def debug(self, message: str):
        """调试日志"""
        self.logger.debug(message)
    
    def info(self, message: str):
        """信息日志"""
        self.logger.info(message)
    
    def warning(self, message: str):
        """警告日志"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """错误日志"""
        self.logger.error(message)
    
    def critical(self, message: str):
        """严重错误日志"""
        self.logger.critical(message)
    
    def exception(self, message: str):
        """异常日志"""
        self.logger.exception(message)
    
    def set_console_level(self, level: int):
        """设置控制台日志级别
        
        Args:
            level: 日志级别，如logging.DEBUG, logging.INFO, logging.WARNING等
        """
        self.console_log_level = level
        self.console_handler.setLevel(level)
    
    def enable_debug_logs(self, enabled: bool = True):
        """启用或禁用DEBUG日志
        
        Args:
            enabled: True启用DEBUG日志，False禁用（使用INFO级别）
        """
        if enabled:
            self.set_console_level(logging.DEBUG)
        else:
            self.set_console_level(logging.INFO)
    
    def is_debug_enabled(self) -> bool:
        """检查DEBUG日志是否启用"""
        return self.console_log_level <= logging.DEBUG


# 创建默认日志实例
default_logger = Logger()


def get_logger(name: str = "svd_tool") -> Logger:
    """
    获取日志实例
    
    Args:
        name: 日志名称
    
    Returns:
        日志实例
    """
    return Logger(name)


def log_function_call(func):
    """函数调用日志装饰器"""
    def wrapper(*args, **kwargs):
        default_logger.debug(f"调用函数: {func.__name__}")
        try:
            result = func(*args, **kwargs)
            default_logger.debug(f"函数 {func.__name__} 执行成功")
            return result
        except Exception as e:
            default_logger.error(f"函数 {func.__name__} 执行失败: {str(e)}")
            raise
    
    return wrapper


class LogContext:
    """日志上下文管理器"""
    
    def __init__(self, operation: str):
        self.operation = operation
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        default_logger.info(f"开始: {self.operation}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        if exc_type:
            default_logger.error(f"失败: {self.operation} ({duration:.2f}s) - {exc_val}")
        else:
            default_logger.info(f"完成: {self.operation} ({duration:.2f}s)")
        
        # 不捕获异常
        return False