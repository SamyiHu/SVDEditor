# svd_tool/config.py
"""
配置文件 - 配置模板

注意：当前版本中这些配置项可能未被完全使用。
这是配置结构的示例，未来版本将实现完整的配置系统。

配置分类：
1. UI配置：窗口大小、主题、字体、自动保存等
2. 编辑器配置：缩进、换行、行号、字体等
3. 解析器配置：验证模式、快速模式、警告限制等
4. 生成器配置：美化打印、排序、注释等输出选项
5. 路径配置：最后访问目录、模板目录、导出目录等

使用说明：
- 此文件定义了应用程序的默认配置结构
- 当前版本可能未完全实现所有配置项
- 用户可修改此文件来自定义应用程序行为
- 构建时会包含此文件到发布包中
"""

# 默认配置（配置模板）
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