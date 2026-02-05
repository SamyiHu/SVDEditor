# svd_tool/config.py
"""
配置文件
"""

# 默认配置
DEFAULT_CONFIG = {
    "ui": {
        "window_size": [1600, 900],
        "splitter_sizes": [800, 400],
        "font_size": 9,
        "theme": "light",
        "auto_save": True,
        "auto_save_interval": 300,  # 5分钟
    },
    "editor": {
        "auto_indent": True,
        "tab_width": 4,
        "show_line_numbers": True,
        "word_wrap": False,
        "font_family": "Consolas",
        "font_size": 10,
    },
    "parser": {
        "validate_on_load": True,
        "fast_mode": False,
        "max_warnings": 50,
        "ignore_derived_peripherals": False,
    },
    "generator": {
        "pretty_print": True,
        "indent_size": 2,
        "sort_peripherals": True,
        "sort_registers": True,
        "add_comments": True,
    },
    "paths": {
        "last_directory": "",
        "template_directory": "",
        "export_directory": "",
    }
}