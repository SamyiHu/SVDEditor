# 构建工具目录

本目录包含SVD Editor项目的构建和打包工具。

## 工具列表

### 1. build_professional_fixed.py
**专业构建脚本（推荐）**
- 解决编码问题和目录结构问题
- 减少杀毒软件误报
- 支持图标和版本信息
- 生成整洁的发布文件

**使用方法：**
```bash
cd build_tools
python build_professional_fixed.py
```

### 2. build_windows.py
**基础Windows构建脚本**
- 支持32/64位架构选择
- 提供多种构建选项
- 交互式构建界面

**使用方法：**
```bash
cd build_tools
python build_windows.py
```

## 构建配置

### 依赖文件
- `../requirements.txt` - Python依赖
- `../setup.py` - Python包配置
- `../version_info.txt` - 版本信息（自动生成）

### 输出目录
- `../_build/` - 构建临时文件
- `../_dist/` - 输出文件
- `../release/` - 发布文件

## 快速开始

1. 安装依赖：
   ```bash
   pip install -r ../requirements.txt
   pip install pyinstaller
   ```

2. 构建应用程序：
   ```bash
   python build_professional_fixed.py
   ```

3. 查看结果：
   - 可执行文件：`../_dist/SVDEditor_64bit.exe`
   - 发布文件：`../release/64bit/`

## 注意事项

1. 图标文件应放在项目根目录 `../icon.ico`
2. 构建前确保所有依赖已安装
3. 如果遇到杀毒软件误报，请参考文档中的解决方案
