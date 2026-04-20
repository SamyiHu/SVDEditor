# 项目结构 | Project Structure

```
SVDEditor/
├── run.py                          # 启动脚本 | Startup script
├── setup.py                        # 包配置 | Package config
├── config.py                       # 应用配置 | App configuration
├── requirements.txt                # 依赖列表 | Dependencies
├── pytest.ini                      # 测试配置 | Test config
├── icon.ico                        # 应用图标 | App icon
├── LICENSE                         # Apache-2.0
├── README.md                       # English README
├── README_zh.md                    # 中文 README
│
├── svd_tool/                       # 源代码 | Source code
│   ├── __init__.py                 # 包初始化 + 版本 | Package init + version
│   ├── main.py                     # GUI 入口 | GUI entry
│   ├── cli.py                      # CLI 入口 | CLI entry
│   ├── config/
│   │   ├── about.json              # 关于对话框数据 | About dialog data
│   │   ├── icons.py                # 图标配置 | Icon config
│   │   ├── styles.py               # 样式配置 | Style config
│   │   └── tree_branch_style.py
│   ├── core/                       # 核心逻辑 | Core logic
│   │   ├── data_model.py           # 数据模型 | Data model
│   │   ├── svd_parser.py           # SVD 解析 | SVD parser
│   │   ├── svd_generator.py        # SVD 生成 | SVD generator
│   │   ├── svd_exporter.py         # 文档导出 | Doc exporter (CSV/MD/HTML)
│   │   ├── svd_differ.py           # 文件比较 | File diff
│   │   ├── svd_merger.py           # 文件合并 | File merge
│   │   ├── header_generator.py     # C 头文件 | C header gen
│   │   ├── validators.py           # 数据验证 | Validation
│   │   ├── command_history.py      # 撤销/重做 | Undo/Redo
│   │   ├── chain_rules.py          # 连锁规则 | Chain rules
│   │   ├── document_manager.py     # 多文档管理 | Multi-doc manager
│   │   ├── block_manager.py        # 分块加载 | Chunked loading
│   │   └── constants.py
│   ├── ui/                         # 用户界面 | UI
│   │   ├── main_window_refactored.py  # 主窗口 | Main window
│   │   ├── coordinator.py          # 组件协调 | Coordinator
│   │   ├── dialog_factories.py     # 对话框工厂 | Dialog factory
│   │   ├── form_builder.py         # 表单构建 | Form builder
│   │   ├── tree_manager.py         # 树视图管理 | Tree manager
│   │   ├── preview_window.py       # 预览窗口 | Preview
│   │   ├── components/             # UI 组件 | UI components
│   │   │   ├── menu_bar.py         # 菜单栏 | Menu bar
│   │   │   ├── toolbar.py          # 工具栏 | Toolbar
│   │   │   ├── peripheral_manager.py
│   │   │   └── ...
│   │   ├── dialogs/                # 对话框 | Dialogs
│   │   │   ├── chain_rules_dialog.py
│   │   │   ├── svd_diff_merge_dialog.py
│   │   │   └── ...
│   │   ├── widgets/                # 自定义控件 | Custom widgets
│   │   │   ├── bit_field_widget.py
│   │   │   ├── address_map_widget.py
│   │   │   ├── document_tab_bar.py
│   │   │   └── ...
│   │   └── managers/               # 功能管理器 | Managers
│   │       ├── batch_operations_manager.py
│   │       ├── search_manager.py
│   │       └── ...
│   ├── i18n/                       # 国际化 | i18n
│   │   ├── i18n.py
│   │   ├── zh_CN.json
│   │   └── en_US.json
│   └── utils/                      # 工具函数 | Utilities
│       ├── helpers.py
│       ├── logger.py
│       └── error_handler.py
│
├── docs/                           # 文档 | Documentation
├── build_tools/                    # 构建工具 | Build tools
├── test_data/                      # 测试数据 | Test data
└── tests/                          # 测试 | Tests
```

## 模块说明 | Module Overview

| Module 模块 | Responsibility 职责 |
|---|---|
| `core/` | 数据模型、SVD 解析/生成、验证、导出、比较合并 |
| `ui/components/` | 菜单栏、工具栏、外设管理等 UI 组件 |
| `ui/dialogs/` | 各种编辑对话框 |
| `ui/widgets/` | 位域图、地址映射、文档标签等自定义控件 |
| `ui/managers/` | 批量操作、搜索、设备信息等功能管理器 |
| `i18n/` | 中英文翻译 JSON |
| `config/` | 样式、图标、关于对话框等配置 |
| `utils/` | 日志、错误处理、辅助函数 |
