# SVD Editor

一个基于组件化架构的 ARM SVD 文件编辑工具，提供更佳的可维护性和扩展性。

> 此版本为重构版本（原 `svd_tool` 的重构版），采用组件化设计，包含状态管理、布局管理、外设管理等独立模块。旧版代码已分离到独立仓库。

## 主要改进

- **组件化架构**：将主窗口逻辑拆分为独立组件（StateManager, LayoutManager, PeripheralManager）
- **更好的代码组织**：减少耦合，提高可测试性
- **增强的状态管理**：集中化状态处理，支持快照和恢复
- **现代化 UI 组件**：使用专用 widgets 实现可视化功能
- **完整的测试套件**：包含单元测试、集成测试和 GUI 测试

## 功能特性

### 核心功能
- **SVD/XML 文件解析**：导入标准 SVD 文件，解析设备、外设、寄存器、位域等层次结构
- **可视化编辑**：树形视图展示三级结构（外设 → 寄存器 → 位域），支持增删改查操作
- **继承外设支持**：自动合并基类外设的寄存器定义，可视化显示继承关系
- **地址映射可视化**：图形化显示外设地址空间布局和寄存器偏移
- **位域可视化**：寄存器位域图形化展示，支持位域高亮和编辑
- **中断管理**：配置和管理外设中断向量

### 用户体验
- **撤销/重做**：完整的操作历史记录，支持无限级撤销重做
- **搜索与过滤**：快速定位外设、寄存器、位域
- **拖放排序**：直观调整外设、寄存器顺序
- **多标签界面**：分页管理不同功能模块
- **实时预览**：编辑时实时更新可视化效果

### 输出与导出
- **美化 SVD 生成**：生成格式规范、缩进整齐的 SVD/XML 文件
- **自定义配置**：支持输出格式定制（缩进、属性顺序等）
- **批量处理**：支持批量导入导出

## 安装与运行

### 环境要求
- Python 3.10 或更高版本
- PyQt6 6.5.0+

### 快速开始

1. **克隆仓库**
   ```bash
   git clone https://github.com/SamyiHu/SVDEditor.git
   cd SVDEditor
   ```

2. **创建虚拟环境（推荐）**
   ```bash
   python -m venv .venv
   # Windows
   .\.venv\Scripts\activate
   # Linux/Mac
   source .venv/bin/activate
   ```

3. **安装依赖**
   ```bash
   pip install PyQt6
   # 或使用 requirements.txt（如果存在）
   pip install -r requirements.txt
   ```

4. **运行应用**
   ```bash
   python run.py
   ```

## 使用指南

### 基本工作流程
1. **导入 SVD 文件**：点击"文件" → "打开"，选择 SVD/XML 文件
2. **浏览结构**：左侧树形视图展示设备→外设→寄存器→位域层次
3. **编辑项目**：
   - 双击树节点编辑属性
   - 右键菜单添加/删除项目
   - 拖放调整顺序
4. **可视化查看**：
   - 选择外设查看地址映射图
   - 选择寄存器查看位域分布图
   - 选择位域查看详细属性
5. **保存结果**：点击"生成"按钮保存美化后的 SVD 文件

### 继承外设处理
当外设使用 `derivedFrom` 属性时，工具会自动：
- 合并基类外设的寄存器定义
- 在地址映射图中用不同颜色区分继承寄存器
- 保持寄存器定义的完整性

### 快捷键
- `Ctrl+O`：打开文件
- `Ctrl+S`：保存文件
- `Ctrl+Z`：撤销
- `Ctrl+Y`：重做
- `Ctrl+F`：搜索
- `F5`：刷新视图

## 项目结构（重构版）

```
SVDEditor/
├── run.py                    # 应用启动脚本
├── config.py                 # 配置文件
├── README.md                 # 本文档
├── svd_tool/                 # 主包目录
│   ├── main.py              # 应用入口（使用 MainWindowRefactored）
│   ├── core/                # 核心逻辑
│   │   ├── data_model.py    # 数据模型（Device, Peripheral, Register, Field）
│   │   ├── svd_parser.py    # SVD 解析器
│   │   ├── svd_generator.py # SVD 生成器
│   │   ├── validators.py    # 数据验证
│   │   └── command_history.py # 命令历史（撤销/重做）
│   ├── ui/                  # 用户界面（组件化）
│   │   ├── main_window_refactored.py   # 重构主窗口（组件化架构）
│   │   ├── dialog_factories.py # 对话框工厂
│   │   ├── dialogs.py       # 各种对话框
│   │   ├── form_builder.py  # 表单构建器
│   │   ├── tree_manager.py  # 树形视图管理
│   │   ├── components/      # 组件目录
│   │   │   ├── state_manager.py     # 状态管理组件
│   │   │   ├── layout_manager.py    # UI布局管理组件
│   │   │   ├── peripheral_manager.py # 外设管理组件
│   │   │   ├── menu_bar.py          # 菜单栏组件
│   │   │   └── toolbar.py           # 工具栏组件
│   │   └── widgets/         # 专用小部件
│   │       ├── address_map_widget.py   # 地址映射小部件
│   │       ├── bit_field_widget.py     # 位域小部件
│   │       └── visualization_widget.py # 可视化小部件
│   └── utils/               # 工具函数
│       ├── helpers.py       # 辅助函数
│       └── logger.py        # 日志配置
├── tests/                   # 测试套件
│   ├── unit_tests/         # 单元测试
│   ├── integration_tests/  # 集成测试
│   └── gui_tests/          # GUI测试
├── GITHUB_SETUP.md         # GitHub仓库设置指南
├── MIGRATION_PROGRESS.md   # 迁移进度文档
├── PR_DESCRIPTION.md       # PR描述模板
├── LICENSE                 # MIT许可证
└── .venv/                  # 虚拟环境（可选）
```

## 开发与贡献

### 代码规范
- 遵循 PEP 8 Python 代码规范
- 使用类型注解（Type Hints）
- 模块化设计，关注点分离

### 测试
项目包含多个测试脚本，验证核心功能：
- `test_all_improvements.py`：综合测试所有改进功能
- `test_inheritance_fix.py`：测试继承外设功能
- `test_graphics.py`：测试图形化组件
- `test_rectangle_fix.py`：测试矩形绘制
- `test_final_verification.py`：最终验证测试

运行测试：
```bash
python test_all_improvements.py
```

### 提交贡献
1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/your-feature`)
3. 提交更改 (`git commit -m 'Add some feature'`)
4. 推送到分支 (`git push origin feature/your-feature`)
5. 创建 Pull Request

### 开源许可证说明

本项目采用 MIT 许可证，这是一种宽松的开源许可证，允许：

- 商业使用
- 修改和分发
- 私人使用
- 子许可证
- 专利授权

唯一的要求是保留原始的版权声明和许可证声明。

### 贡献者协议

通过向本项目提交代码，您同意您的贡献将在 MIT 许可证下发布。

## 维护者

- SamyiHu (@SamyiHu) - 项目创建者和主要维护者

## 更新日志

### 最新版本 (v2.1)
- **可视化改进**：添加地址映射图和位域可视化组件
- **继承外设支持**：完善 derivedFrom 外设的寄存器合并显示
- **UI 优化**：重构工具栏，移除冗余按钮，优化布局
- **测试套件**：添加多个功能测试脚本
- **Bug 修复**：修复树形视图选择、撤销重做等已知问题
