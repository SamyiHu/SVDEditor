# svd_tool/utils/logger.py
"""
日志工具模块

默认会把日志写入用户目录下的 ~/.svd_tool/logs/svd_tool.log，
按大小滚动（单个 5MB，保留 3 个历史文件），记录 DEBUG 及以上级别。
控制台输出行为与历史一致（INFO 级别到 stdout）。
可通过设置环境变量 SVD_TOOL_DISABLE_FILE_LOG=1 关闭文件日志。
"""
import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


# === 默认日志文件路径 ===
# 与 ai_assistant/config.py 的 ~/.svd_tool/ 约定保持一致
_LOG_DIR = Path.home() / ".svd_tool" / "logs"
_LOG_FILE = _LOG_DIR / "svd_tool.log"

# 滚动策略：单个文件上限 / 保留历史文件数（含当前共 maxBytes*(backupCount+1)）
_LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_LOG_BACKUP_COUNT = 3


def get_log_dir() -> Path:
    """返回日志目录路径（不保证已创建）。"""
    return _LOG_DIR


def get_log_file_path() -> Path:
    """返回当前日志文件路径（不保证已创建）。"""
    return _LOG_FILE


def _file_logging_disabled() -> bool:
    """环境变量开关：SVD_TOOL_DISABLE_FILE_LOG=1 时关闭文件日志。

    主要用于打包/测试场景，避免污染用户目录或因权限问题启动失败。
    """
    return os.environ.get("SVD_TOOL_DISABLE_FILE_LOG", "").strip() in ("1", "true", "True", "yes")


def _ensure_log_dir() -> bool:
    """确保日志目录存在。成功返回 True，失败返回 False。"""
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        return True
    except Exception:
        return False


class Logger:
    """日志管理器"""

    def __init__(self, name: str = "svd_tool", log_file: Optional[str] = None,
                 enable_file: bool = True):
        """
        初始化日志管理器

        Args:
            name: 日志名称
            log_file: 日志文件路径；为 None 时使用默认路径
                      (~/.svd_tool/logs/svd_tool.log)，除非 enable_file=False
            enable_file: 是否启用文件日志。默认 True。测试/打包场景可置 False
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # 只移除当前logger的处理器，不影响其他logger
        # 注意：这不会清除根logger的处理器（如GuiLogHandler）
        if self.logger.handlers:
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

        # 文件处理器（按大小滚动）
        self.file_handler = None
        if enable_file and not _file_logging_disabled():
            # 显式传了路径就用它；否则用默认路径
            target = Path(log_file) if log_file else _LOG_FILE
            # target 是自定义路径时，用其父目录；默认路径用专用 _ensure_log_dir
            if log_file:
                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    ok = True
                except Exception:
                    ok = False
            else:
                ok = _ensure_log_dir()

            if ok:
                try:
                    self.file_handler = logging.handlers.RotatingFileHandler(
                        target,
                        maxBytes=_LOG_MAX_BYTES,
                        backupCount=_LOG_BACKUP_COUNT,
                        encoding='utf-8',
                        delay=True,  # 延迟到首次写入才打开文件，且首写失败不会抛到构造处
                    )
                    self.file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别
                    self.file_handler.setFormatter(self.formatter)
                    self.logger.addHandler(self.file_handler)
                except Exception:
                    # 文件日志初始化失败不应阻断程序启动，降级为仅控制台
                    self.file_handler = None

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

    def is_file_logging_enabled(self) -> bool:
        """文件日志是否成功启用（用于启动时打印路径）"""
        return self.file_handler is not None


# 创建默认日志实例
default_logger = Logger()

# 日志实例缓存
_logger_cache: dict[str, Logger] = {}


def get_logger(name: str = "svd_tool") -> Logger:
    """
    获取日志实例（使用缓存，避免重复创建）

    Args:
        name: 日志名称

    Returns:
        日志实例
    """
    if name not in _logger_cache:
        _logger_cache[name] = Logger(name)
    return _logger_cache[name]


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
