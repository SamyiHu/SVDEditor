"""
国际化（i18n）模块
支持多语言切换
"""
from .i18n import I18nManager, get_i18n_manager, set_i18n_manager, t, TranslationKeys

__all__ = [
    'I18nManager',
    'get_i18n_manager',
    'set_i18n_manager',
    't',
    'TranslationKeys'
]
