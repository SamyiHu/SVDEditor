# SVD Editor 打包指南

## 概述

本文档介绍如何为SVD Editor项目创建可执行文件，支持Windows平台（32位和64位）。

## 依赖项

### 开发环境
- Python 3.10或更高版本
- PyQt6 6.5.0+
- PyInstaller 6.0+

### 安装依赖
```bash
pip install PyQt6 pyinstaller
```

## 打包方法

### 方法1：使用构建脚本（推荐）

项目包含一个构建脚本 `build_windows.py`，支持交互式构建：

```bash
python build_windows.py
```

选项：
1. 构建当前架构版本（自动检测）
2. 构建32位版本（需要32位Python）
3. 构建64位版本（需要64位Python）
4. 构建所有可用版本
5. 构建调试版本（显示控制台）

### 方法2：使用PyInstaller直接构建

#### 单文件模式（所有内容打包到一个EXE）
```bash
python -m PyInstaller --onefile --windowed --name SVDEditor run.py
```

#### 目录模式（推荐，便于调试和更新）
```bash
python -m PyInstaller --windowed --name SVDEditor run.py
```

#### 包含数据文件
```bash
python -m PyInstaller --windowed --name SVDEditor --add-data "config.py;." --add-data "README.md;." --add-data "README_zh.md;." --add-data "LICENSE;." run.py
```

### 方法3：使用spec文件

1. 生成spec文件：
   ```bash
   python -m PyInstaller --onefile --windowed --name SVDEditor run.py
   ```

2. 编辑生成的 `SVDEditor.spec` 文件，添加数据文件：
   ```python
   # 在Analysis部分添加
   datas=[
       ('config.py', '.'),
       ('README.md', '.'),
       ('README_zh.md', '.'),
       ('LICENSE', '.'),
   ],
   ```

3. 使用spec文件构建：
   ```bash
   python -m PyInstaller SVDEditor.spec
   ```

## 平台特定说明

### Windows 64位
- 使用64位Python环境
- 生成的可执行文件可在64位Windows上运行
- 文件大小：约35-40MB

### Windows 32位
- 使用32位Python环境
- 生成的可执行文件可在32位和64位Windows上运行
- 文件大小：约30-35MB

### 注意事项
1. **Qt插件**：PyInstaller会自动包含必要的Qt插件
2. **图标**：如需添加图标，使用 `--icon=icon.ico` 参数
3. **控制台**：GUI应用使用 `--windowed`，调试版本使用 `--console`
4. **UPX压缩**：默认启用UPX压缩以减少文件大小

## 测试打包结果

### 快速测试
1. 导航到 `dist` 目录
2. 运行生成的可执行文件：
   ```bash
   cd dist
   SVDEditor.exe
   ```

### 功能验证
- 启动应用程序
- 打开SVD文件
- 编辑外设、寄存器、位域
- 生成SVD文件
- 验证所有可视化功能

## 常见问题

### 1. 应用程序启动失败
- 确保所有依赖项已正确打包
- 检查是否有缺失的DLL文件
- 尝试在命令行中运行查看错误信息

### 2. 文件大小过大
- 使用UPX压缩（默认已启用）
- 排除不必要的模块
- 使用 `--exclude-module` 参数

### 3. 缺少数据文件
- 确保在spec文件中正确添加了数据文件
- 检查文件路径是否正确

### 4. 跨平台构建
- Windows到Linux：需要在Linux系统上构建
- 考虑使用Docker进行跨平台构建

## 发布准备

### 版本信息
编辑 `svd_tool/__init__.py` 中的版本号：
```python
__version__ = "2.1.0"
```

### 包含文件
发布时应包含：
1. 可执行文件（或安装包）
2. README文档（中英文）
3. LICENSE文件
4. 配置文件示例

### 创建安装包
可以使用以下工具创建安装程序：
- Inno Setup（Windows）
- NSIS（Windows）
- 简单的ZIP压缩包

## 自动化构建

项目包含以下构建配置文件：
1. `requirements.txt` - 依赖项列表
2. `setup.py` - Python包配置
3. `build.spec` - PyInstaller配置示例
4. `build_windows.py` - 自动化构建脚本

## 支持与维护

如有构建问题，请检查：
1. PyInstaller版本兼容性
2. Python和PyQt6版本
3. 操作系统架构匹配
4. 错误日志（在 `build` 目录中）

## 更新日志

### v2.1.0
- 首次提供完整的打包方案
- 支持Windows 32/64位
- 包含所有必要的数据文件
- 提供构建脚本和文档