"""
统一错误处理框架
提供一致的错误处理、日志记录和用户通知机制
"""
import logging
import traceback
from typing import Optional, Callable, Any, Dict, List
from enum import Enum
from PyQt6.QtWidgets import QMessageBox, QWidget
from ..i18n.i18n import t


class ErrorLevel(Enum):
    """错误级别"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """错误类别"""
    VALIDATION = "validation"  # 验证错误
    FILE_IO = "file_io"  # 文件操作错误
    PARSING = "parsing"  # 解析错误
    GENERATION = "generation"  # 生成错误
    UI = "ui"  # UI错误
    NETWORK = "network"  # 网络错误
    DATABASE = "database"  # 数据库错误
    UNKNOWN = "unknown"  # 未知错误


class AppError(Exception):
    """应用程序基础异常类"""
    
    def __init__(
        self,
        message: str,
        level: ErrorLevel = ErrorLevel.ERROR,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        details: Optional[str] = None,
        user_message: Optional[str] = None
    ):
        """
        初始化应用程序异常
        
        Args:
            message: 错误消息（用于日志）
            level: 错误级别
            category: 错误类别
            details: 错误详细信息
            user_message: 用户友好的错误消息（用于显示）
        """
        super().__init__(message)
        self.message = message
        self.level = level
        self.category = category
        self.details = details
        self.user_message = user_message or message
        self.traceback = traceback.format_exc()
    
    def __str__(self):
        return self.message


class ValidationError(AppError):
    """验证错误"""
    
    def __init__(self, message: str, details: Optional[str] = None):
        super().__init__(
            message=message,
            level=ErrorLevel.WARNING,
            category=ErrorCategory.VALIDATION,
            details=details,
            user_message=message
        )


class FileIOError(AppError):
    """文件操作错误"""

    def __init__(self, message: str, details: Optional[str] = None):
        super().__init__(
            message=message,
            level=ErrorLevel.ERROR,
            category=ErrorCategory.FILE_IO,
            details=details,
            user_message=t("error.file_io", message=message)
        )


class ParsingError(AppError):
    """解析错误"""

    def __init__(self, message: str, details: Optional[str] = None):
        super().__init__(
            message=message,
            level=ErrorLevel.ERROR,
            category=ErrorCategory.PARSING,
            details=details,
            user_message=t("error.parsing", message=message)
        )


class GenerationError(AppError):
    """生成错误"""

    def __init__(self, message: str, details: Optional[str] = None):
        super().__init__(
            message=message,
            level=ErrorLevel.ERROR,
            category=ErrorCategory.GENERATION,
            details=details,
            user_message=t("error.generation", message=message)
        )


class UIError(AppError):
    """UI错误"""
    
    def __init__(self, message: str, details: Optional[str] = None):
        super().__init__(
            message=message,
            level=ErrorLevel.WARNING,
            category=ErrorCategory.UI,
            details=details,
            user_message=message
        )


class ErrorHandler:
    """统一错误处理器"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        初始化错误处理器
        
        Args:
            logger: 日志记录器
        """
        self.logger = logger or logging.getLogger("ErrorHandler")
        self.error_history: List[AppError] = []
        self.max_history = 100
    
    def handle(
        self,
        error: Exception,
        parent_widget: Optional[QWidget] = None,
        show_user_message: bool = True,
        log_error: bool = True
    ) -> AppError:
        """
        处理错误
        
        Args:
            error: 异常对象
            parent_widget: 父窗口（用于显示消息框）
            show_user_message: 是否显示用户消息
            log_error: 是否记录日志
            
        Returns:
            AppError: 处理后的错误对象
        """
        # 转换为 AppError
        app_error = self._convert_to_app_error(error)
        
        # 记录日志
        if log_error:
            self._log_error(app_error)
        
        # 添加到历史记录
        self._add_to_history(app_error)
        
        # 显示用户消息
        if show_user_message and parent_widget:
            self._show_user_message(app_error, parent_widget)
        
        return app_error
    
    def _convert_to_app_error(self, error: Exception) -> AppError:
        """将异常转换为 AppError"""
        if isinstance(error, AppError):
            return error
        
        # 根据异常类型创建对应的 AppError
        error_type = type(error).__name__
        error_message = str(error)
        
        # 根据异常类型判断类别
        if "File" in error_type or "IO" in error_type:
            return FileIOError(error_message)
        elif "Parse" in error_type or "XML" in error_type:
            return ParsingError(error_message)
        elif "Validation" in error_type:
            return ValidationError(error_message)
        else:
            return AppError(
                message=error_message,
                level=ErrorLevel.ERROR,
                category=ErrorCategory.UNKNOWN,
                details=traceback.format_exc()
            )
    
    def _log_error(self, error: AppError):
        """记录错误日志"""
        log_message = f"[{error.category.value.upper()}] {error.message}"
        if error.details:
            log_message += f"\nDetails: {error.details}"
        
        if error.level == ErrorLevel.DEBUG:
            self.logger.debug(log_message)
        elif error.level == ErrorLevel.INFO:
            self.logger.info(log_message)
        elif error.level == ErrorLevel.WARNING:
            self.logger.warning(log_message)
        elif error.level == ErrorLevel.ERROR:
            self.logger.error(log_message)
        elif error.level == ErrorLevel.CRITICAL:
            self.logger.critical(log_message)
    
    def _add_to_history(self, error: AppError):
        """添加错误到历史记录"""
        self.error_history.append(error)
        if len(self.error_history) > self.max_history:
            self.error_history.pop(0)
    
    def _show_user_message(self, error: AppError, parent_widget: QWidget):
        """显示用户消息"""
        if error.level == ErrorLevel.DEBUG or error.level == ErrorLevel.INFO:
            # 信息级别不显示消息框
            return
        
        title = self._get_message_title(error.level)
        message = error.user_message
        
        if error.level == ErrorLevel.WARNING:
            QMessageBox.warning(parent_widget, title, message)
        elif error.level == ErrorLevel.ERROR or error.level == ErrorLevel.CRITICAL:
            QMessageBox.critical(parent_widget, title, message)
    
    def _get_message_title(self, level: ErrorLevel) -> str:
        """获取消息框标题"""
        if level == ErrorLevel.WARNING:
            return t("error.title_warning")
        elif level == ErrorLevel.ERROR:
            return t("error.title_error")
        elif level == ErrorLevel.CRITICAL:
            return t("error.title_critical")
        else:
            return t("error.title_info")
    
    def get_error_history(self) -> List[AppError]:
        """获取错误历史记录"""
        return self.error_history.copy()
    
    def clear_error_history(self):
        """清除错误历史记录"""
        self.error_history.clear()


def handle_errors(
    error_handler: ErrorHandler,
    parent_widget: Optional[QWidget] = None,
    show_user_message: bool = True,
    log_error: bool = True,
    default_return: Any = None
) -> Callable:
    """
    错误处理装饰器
    
    Args:
        error_handler: 错误处理器
        parent_widget: 父窗口
        show_user_message: 是否显示用户消息
        log_error: 是否记录日志
        default_return: 发生错误时的默认返回值
        
    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_handler.handle(
                    e,
                    parent_widget=parent_widget,
                    show_user_message=show_user_message,
                    log_error=log_error
                )
                return default_return
        return wrapper
    return decorator


# 全局错误处理器实例
_global_error_handler: Optional[ErrorHandler] = None


def get_global_error_handler() -> ErrorHandler:
    """获取全局错误处理器"""
    global _global_error_handler
    if _global_error_handler is None:
        _global_error_handler = ErrorHandler()
    return _global_error_handler


def set_global_error_handler(handler: ErrorHandler):
    """设置全局错误处理器"""
    global _global_error_handler
    _global_error_handler = handler


def handle_error(
    error: Exception,
    parent_widget: Optional[QWidget] = None,
    show_user_message: bool = True,
    log_error: bool = True
) -> AppError:
    """
    使用全局错误处理器处理错误
    
    Args:
        error: 异常对象
        parent_widget: 父窗口
        show_user_message: 是否显示用户消息
        log_error: 是否记录日志
        
    Returns:
        AppError: 处理后的错误对象
    """
    return get_global_error_handler().handle(
        error,
        parent_widget=parent_widget,
        show_user_message=show_user_message,
        log_error=log_error
    )
