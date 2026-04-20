# SVD Editor 打包指南 | Build Guide

## 概述 | Overview

本文档介绍如何为 SVD Editor 创建可执行文件，支持 Windows 平台（32/64 位）。
This document describes how to create executables for SVD Editor on Windows (32/64-bit).

## 依赖项 | Dependencies

- Python 3.10+
- PyQt6 6.5.0+
- PyInstaller 6.0+

```bash
pip install PyQt6 pyinstaller
```

## 打包方法 | Packaging Methods

### 方法 1：构建脚本（推荐）| Method 1: Build Script (Recommended)

```bash
python build_windows.py
```

Options: 选项：
1. Build current arch / 当前架构
2. Build 32-bit / 32 位版本
3. Build 64-bit / 64 位版本
4. Build all / 所有版本
5. Debug build / 调试版本

### 方法 2：PyInstaller 直接构建 | Method 2: PyInstaller Direct

单文件模式 / Single-file:
```bash
python -m PyInstaller --onefile --windowed --name SVDEditor run.py
```

目录模式 / Directory mode (recommended):
```bash
python -m PyInstaller --windowed --name SVDEditor run.py
```

包含数据文件 / Include data files:
```bash
python -m PyInstaller --windowed --name SVDEditor \
  --add-data "config.py;." --add-data "LICENSE;." run.py
```

### 方法 3：Spec 文件 | Method 3: Spec File

1. 生成 / Generate: `python -m PyInstaller --onefile --windowed --name SVDEditor run.py`
2. 编辑 `SVDEditor.spec`:
   ```python
   datas=[('config.py', '.'), ('LICENSE', '.'), ('README.md', '.')],
   ```
3. 构建 / Build: `python -m PyInstaller SVDEditor.spec`

## 平台说明 | Platform Notes

| Platform 平台 | Python | Output Size 大小 |
|---|---|---|
| Windows 64-bit | 64-bit Python | ~35-40MB |
| Windows 32-bit | 32-bit Python | ~30-35MB |

Notes 注意事项:
- `--windowed` for GUI, `--console` for debug / GUI 用 `--windowed`，调试用 `--console`
- Icon: `--icon=icon.ico` / 图标: `--icon=icon.ico`

## 测试构建结果 | Testing the Build

```bash
cd dist
SVDEditor.exe
```

验证 / Verify: open SVD file, edit peripherals/registers/fields, generate SVD, check visualizations.
打开 SVD 文件，编辑外设/寄存器/位域，生成 SVD，检查可视化功能。

## 常见问题 | Common Issues

| Problem 问题 | Solution 解决方案 |
|---|---|
| App fails to start 启动失败 | Check missing DLLs, run from CLI 检查缺失 DLL，命令行运行看错误 |
| File too large 文件过大 | Enable UPX, use `--exclude-module` 启用 UPX，排除多余模块 |
| Missing data files 数据文件缺失 | Check spec file paths 检查 spec 文件路径 |
| Cross-platform 跨平台 | Must build on target OS 需在目标系统上构建 |

## 发布 | Release

1. 更新版本号 `svd_tool/__init__.py` / Update version in `__init__.py`
2. 包含: 可执行文件 + README + LICENSE / Include: executable + README + LICENSE
3. 安装包工具 / Installer tools: Inno Setup, NSIS, or ZIP
