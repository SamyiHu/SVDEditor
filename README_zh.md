# SVD Editor

专业的 CMSIS-SVD 解析、编辑、可视化和 CLI 工具。支持外设管理、寄存器编辑、位域可视化、批量操作、差异比较/合并、C头文件生成等。

## 功能特性

### GUI 编辑器
- **SVD/XML 解析**：导入标准 CMSIS-SVD 文件，解析设备/外设/寄存器/位域层次结构
- **可视化树形编辑**：三级树形视图（外设 -> 寄存器 -> 位域），完整增删改查
- **继承外设支持**：自动合并 `derivedFrom` 基类外设的寄存器定义
- **地址映射可视化**：图形化外设地址空间布局和寄存器偏移
- **位域可视化**：寄存器位域图，支持高亮和编辑
- **中断管理**：配置和管理中断向量
- **撤销/重做**：无限操作历史，支持快照恢复
- **高级搜索**：统一搜索语法（`type:periph name:GPIO* addr:0x4001*`），支持结构化和全文搜索
- **批量操作**：批量修改属性、批量生成寄存器、批量克隆到其他外设
- **连锁规则**：级联删除/修改规则，支持可配置的动作类型
- **拖放排序**：直观调整外设和寄存器顺序
- **多文档标签**：打开和切换多个 SVD 文件
- **实时预览**：实时 XML 预览，支持语法高亮
- **深色/浅色主题**：内置主题切换，现代化扁平 UI

### CLI 命令（可集成 CI/CD）

| 命令 | 说明 |
|------|------|
| `validate` | 验证 SVD 的 CMSIS-SVD Schema 完整性（位域重叠、地址冲突、必需字段等） |
| `export` | 导出为 CSV、Markdown 或 HTML 文档 |
| `generate` | 重新生成/格式化 SVD XML |
| `diff` | 比较两个 SVD 文件的结构差异 |
| `info` | 显示设备信息和统计数据 |
| `merge` | 合并两个 SVD 文件，支持冲突策略配置 |
| `header` | 从 SVD 生成 C 语言头文件 |
| `conflicts` | 检测地址重叠、寄存器偏移重复、位域冲突 |
| `extract` | 从 SVD 中提取指定外设到新文件 |
| `create` | **从 JSON 数据创建新的 SVD 文件**（如 AIfull_link 导出的寄存器数据） |
| `add-peripheral` | 从 JSON 向已有 SVD 添加外设 |
| `update-peripheral` | 更新外设属性（基地址、描述等） |
| `remove-peripheral` | 按名称从 SVD 中移除外设 |
| `add-register` | 向指定外设添加寄存器（JSON 或命令行参数） |
| `update-register` | 更新寄存器属性（偏移、大小、访问权限等） |
| `remove-register` | 按名称从外设中移除寄存器 |
| `add-field` | 向指定寄存器添加位域（JSON 或命令行参数） |
| `update-field` | 更新位域属性（位偏移、位宽、访问权限等） |
| `remove-field` | 按名称从寄存器中移除位域 |

### 输出与导出
- **SVD 生成**：格式规范、缩进整齐的 SVD/XML 输出
- **文档导出**：CSV、Markdown、HTML 寄存器文档
- **C 头文件生成**：寄存器地址宏和位域掩码 `#define`
- **差异报告**：文本或 JSON 格式的差异对比报告

## AIfull_link 联动

支持直接从 [AIfull_link](https://github.com/SamyiHu/AIfull_link) 解析的寄存器数据创建 SVD 文件：

```bash
# 1. 在 AIfull_link 中导出寄存器数据为 JSON
#    （使用 Agent Shell 的 export_svd 工具）

# 2. 用 create 命令生成 SVD
python run.py create --data scf10t_svd_data.json -o SCF10T.svd --validate

# 3. 在 GUI 中可视化编辑
python run.py --gui --file SCF10T.svd
```

JSON 格式与 `DeviceInfo.to_dict()` 输出完全兼容，详见 `data_model.py`。

## 安装与运行

### 环境要求
- Python 3.10+
- PyQt6 6.5.0+

### 快速开始

```bash
git clone https://github.com/SamyiHu/SVDEditor.git
cd SVDEditor
pip install PyQt6
python run.py                # GUI 模式
python run.py info file.svd  # CLI 模式
```

## CLI 使用

```bash
# 验证
python run.py validate chip.svd [--json] [--strict]

# 导出文档
python run.py export chip.svd --format markdown -o registers.md
python run.py export chip.svd --format csv --peripheral GPIOA --summary-only

# 重新生成 SVD
python run.py generate chip.svd -o output.svd

# 比较两个版本
python run.py diff chip_v1.svd chip_v2.svd [--json] [--ignore-description]

# 设备信息
python run.py info chip.svd [--json]

# 合并 SVD 文件
python run.py merge target.svd source.svd --strategy source -o merged.svd

# 生成 C 头文件
python run.py header chip.svd --style upper_case --prefix CHIP_ -o device.h

# 检查地址冲突
python run.py conflicts chip.svd [--json] [--strict]

# 提取外设
python run.py extract chip.svd --peripherals GPIOA,GPIOB,GPIOC -o gpio.svd

# 从 JSON 创建 SVD（如 AIfull_link 导出的寄存器数据）
python run.py create --data device_data.json -o chip.svd [--validate] [--open]

# 从 JSON 添加外设
python run.py add-peripheral chip.svd --data peripheral.json -o updated.svd

# 移除外设
python run.py remove-peripheral chip.svd --name GPIOC,GPIOD -o updated.svd

# 更新外设属性
python run.py update-peripheral chip.svd -n GPIOA --base-address 0x48010000 -o updated.svd

# 添加寄存器（命令行参数）
python run.py add-register chip.svd -p GPIOA --name IDR --offset 0x10 --desc "Input data" -o updated.svd

# 添加寄存器（JSON 文件）
python run.py add-register chip.svd -p GPIOA --data registers.json -o updated.svd

# 更新寄存器属性
python run.py update-register chip.svd -p GPIOA -n MODER --offset 0x08 --size 0x20 -o updated.svd

# 移除寄存器
python run.py remove-register chip.svd -p GPIOA --names OTYPER,OSPEEDR -o updated.svd

# 添加位域（命令行参数）
python run.py add-field chip.svd -p GPIOA -r MODER --name MODE7 --bit-offset 14 --bit-width 2 -o updated.svd

# 更新位域属性
python run.py update-field chip.svd -p GPIOA -r MODER -n MODE0 --bit-width 1 --access read-write -o updated.svd

# 移除位域
python run.py remove-field chip.svd -p GPIOA -r MODER --names MODE0,MODE1 -o updated.svd

# 使用 GUI 打开指定文件
python run.py --gui --file chip.svd
```

### 键盘快捷键（GUI）

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+N` | 新建 SVD 文件 |
| `Ctrl+O` | 打开文件 |
| `Ctrl+S` | 保存文件 |
| `Ctrl+Z` | 撤销 |
| `Ctrl+Y` | 重做 |
| `Ctrl+F` | 快速搜索 |
| `Ctrl+H` | 高级搜索 |
| `Ctrl+Shift+G` | 跳转到地址 |
| `F5` | 刷新视图 |

## 项目结构

```
SVDEditor/
├── run.py                          # 入口（GUI + CLI）
├── svd_tool/
│   ├── cli.py                      # CLI 模块（19 个命令）
│   ├── main.py                     # GUI 入口
│   ├── core/
│   │   ├── data_model.py           # 数据模型
│   │   ├── svd_parser.py           # SVD 解析器
│   │   ├── svd_generator.py        # SVD 生成器
│   │   ├── svd_schema_validator.py # Schema 验证
│   │   ├── svd_exporter.py         # CSV/Markdown/HTML 导出
│   │   ├── svd_differ.py           # 差异比较引擎
│   │   ├── svd_merger.py           # 合并引擎
│   │   ├── header_generator.py     # C 头文件生成器
│   │   ├── address_conflict_detector.py  # 冲突检测
│   │   ├── chain_rules.py          # 连锁规则引擎
│   │   ├── document_manager.py     # 多文档管理
│   │   └── command_history.py      # 撤销/重做
│   ├── ui/
│   │   ├── main_window_refactored.py     # 主窗口
│   │   ├── components/                   # 组件目录
│   │   │   ├── state_manager.py          # 状态管理
│   │   │   ├── layout_manager.py         # 布局协调
│   │   │   ├── tab_builder.py            # 标签页构建
│   │   │   └── menu_bar.py / toolbar.py  # 菜单和工具栏
│   │   ├── managers/                     # 管理器目录
│   │   │   ├── search_manager.py         # 搜索（快速+高级）
│   │   │   ├── batch_operations_manager.py  # 批量操作
│   │   │   └── file_operations.py        # 文件 I/O
│   │   ├── dialogs/                      # 对话框目录
│   │   │   ├── chain_rules_dialog.py     # 连锁规则编辑器
│   │   │   ├── svd_diff_merge_dialog.py  # 差异比较与合并
│   │   │   └── new_svd_wizard.py         # 新建文件向导
│   │   └── widgets/                      # 控件目录
│   │       ├── bit_field_widget.py       # 位域可视化
│   │       ├── address_map_widget.py     # 地址映射
│   │       ├── document_tab_bar.py       # 多文档标签
│   │       └── welcome_page.py           # 欢迎页
│   ├── config/
│   │   ├── about.json              # 关于对话框配置
│   │   └── styles.py               # 主题/样式系统（深色/浅色）
│   └── i18n/
│       ├── i18n.py                 # 国际化管理器
│       ├── zh_CN.json              # 中文翻译
│       └── en_US.json              # 英文翻译
├── docs/                           # 文档
├── build_tools/                    # PyInstaller 构建脚本
├── test_data/                      # 测试 SVD 文件
└── tests/                          # 测试套件
```

## 构建

详见 [BUILD_INSTRUCTIONS.md](docs/BUILD_INSTRUCTIONS.md)。

```bash
pip install pyinstaller
cd build_tools
python build_professional_fixed.py
```

## 许可证

Apache License 2.0 - 详见 [LICENSE](LICENSE)。

## 维护者

- SamyiHu ([@SamyiHu](https://github.com/SamyiHu))
