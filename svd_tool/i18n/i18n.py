"""
国际化（i18n）框架
支持多语言切换
"""
import os
import json
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class Translation:
    """翻译条目"""
    key: str
    text: str


class I18nManager:
    """国际化管理器"""
    
    def __init__(self, locale: str = "zh_CN"):
        """
        初始化国际化管理器
        
        Args:
            locale: 语言代码（如 "zh_CN", "en_US"）
        """
        self.locale = locale
        self.translations: Dict[str, str] = {}
        self.fallback_translations: Dict[str, str] = {}
        self._load_translations()
    
    def _load_translations(self):
        """加载翻译文件"""
        # 加载当前语言的翻译
        current_file = self._get_translation_file(self.locale)
        if os.path.exists(current_file):
            with open(current_file, 'r', encoding='utf-8') as f:
                self.translations = json.load(f)
        
        # 加载回退语言（中文）
        fallback_file = self._get_translation_file("zh_CN")
        if os.path.exists(fallback_file):
            with open(fallback_file, 'r', encoding='utf-8') as f:
                self.fallback_translations = json.load(f)
    
    def _get_translation_file(self, locale: str) -> str:
        """获取翻译文件路径"""
        return os.path.join(os.path.dirname(__file__), f"{locale}.json")
    
    def set_locale(self, locale: str):
        """
        设置语言
        
        Args:
            locale: 语言代码
        """
        self.locale = locale
        self._load_translations()
    
    def get(self, key: str, **kwargs) -> str:
        """
        获取翻译文本
        
        Args:
            key: 翻译键
            **kwargs: 格式化参数
            
        Returns:
            翻译后的文本
        """
        # 首先尝试当前语言
        if key in self.translations:
            text = self.translations[key]
        # 回退到中文
        elif key in self.fallback_translations:
            text = self.fallback_translations[key]
        # 如果都没有，返回键本身
        else:
            text = key
        
        # 格式化参数
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass
        
        return text
    
    def __call__(self, key: str, **kwargs) -> str:
        """使管理器可调用"""
        return self.get(key, **kwargs)
    
    def get_available_locales(self) -> list:
        """获取可用的语言列表"""
        locales = []
        i18n_dir = os.path.dirname(__file__)
        
        for filename in os.listdir(i18n_dir):
            if filename.endswith('.json'):
                locale_code = filename[:-5]  # 移除 .json
                locales.append(locale_code)
        
        return locales


# 全局国际化管理器实例
_i18n_manager: Optional[I18nManager] = None


def get_i18n_manager() -> I18nManager:
    """获取全局国际化管理器"""
    global _i18n_manager
    if _i18n_manager is None:
        _i18n_manager = I18nManager()
    return _i18n_manager


def set_i18n_manager(manager: I18nManager):
    """设置全局国际化管理器"""
    global _i18n_manager
    _i18n_manager = manager


def t(key: str, **kwargs) -> str:
    """
    翻译函数（快捷方式）
    
    Args:
        key: 翻译键
        **kwargs: 格式化参数
        
    Returns:
        翻译后的文本
    """
    return get_i18n_manager().get(key, **kwargs)


# 常用翻译键
class TranslationKeys:
    """翻译键常量"""
    
    # 菜单
    MENU_FILE = "menu.file"
    MENU_EDIT = "menu.edit"
    MENU_VIEW = "menu.view"
    MENU_HELP = "menu.help"
    
    MENU_FILE_NEW = "menu.file.new"
    MENU_FILE_OPEN = "menu.file.open"
    MENU_FILE_SAVE = "menu.file.save"
    MENU_FILE_SAVE_AS = "menu.file.save_as"
    MENU_FILE_EXPORT = "menu.file.export"
    MENU_FILE_EXIT = "menu.file.exit"
    
    # 按钮
    BUTTON_ADD = "button.add"
    BUTTON_EDIT = "button.edit"
    BUTTON_DELETE = "button.delete"
    BUTTON_SAVE = "button.save"
    BUTTON_CANCEL = "button.cancel"
    BUTTON_OK = "button.ok"
    BUTTON_YES = "button.yes"
    BUTTON_NO = "button.no"
    
    BUTTON_ADD_PERIPHERAL = "button.add_peripheral"
    BUTTON_ADD_REGISTER = "button.add_register"
    BUTTON_ADD_FIELD = "button.add_field"
    BUTTON_ADD_INTERRUPT = "button.add_interrupt"
    
    BUTTON_DELETE = "button.delete"
    BUTTON_MOVE_UP = "button.move_up"
    BUTTON_MOVE_DOWN = "button.move_down"
    BUTTON_SORT = "button.sort"
    
    BUTTON_GENERATE = "button.generate"
    BUTTON_PREVIEW = "button.preview"
    
    # 标签页
    TAB_BASIC_INFO = "tab.basic_info"
    TAB_PERIPHERALS = "tab.peripherals"
    TAB_INTERRUPTS = "tab.interrupts"
    TAB_PREVIEW = "tab.preview"
    
    # 消息
    MSG_SUCCESS = "message.success"
    MSG_WARNING = "message.warning"
    MSG_ERROR = "message.error"
    MSG_INFO = "message.info"
    
    MSG_FILE_LOADED = "message.file_loaded"
    MSG_FILE_SAVED = "message.file_saved"
    MSG_FILE_LOAD_FAILED = "message.file_load_failed"
    MSG_FILE_SAVE_FAILED = "message.file_save_failed"
    
    MSG_VALIDATION_PASSED = "message.validation_passed"
    MSG_VALIDATION_FAILED = "message.validation_failed"
    
    MSG_CONFIRM_DELETE = "message.confirm_delete"
    MSG_CONFIRM_EXIT = "message.confirm_exit"
    MSG_UNSAVED_CHANGES = "message.unsaved_changes"
    
    # 错误
    ERROR_FILE_NOT_FOUND = "error.file_not_found"
    ERROR_INVALID_FORMAT = "error.invalid_format"
    ERROR_VALIDATION_FAILED = "error.validation_failed"
    ERROR_PARSE_FAILED = "error.parse_failed"
    ERROR_GENERATE_FAILED = "error.generate_failed"
    
    # 提示
    TIP_SELECT_ITEM = "tip.select_item"
    TIP_DRAG_DROP = "tip.drag_drop"
    TIP_SEARCH = "tip.search"
