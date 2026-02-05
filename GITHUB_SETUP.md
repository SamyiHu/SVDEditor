# GitHub 仓库设置指南

## 项目分离完成

已成功将 SVD 工具项目分离为两个独立版本：

1. **旧版 (legacy)** - 位于 `old_version/` 目录
   - 使用原始的 `main_window.py` 主窗口
   - 保持原有架构，无组件化重构
   - 包含完整的核心功能

2. **新版 (refactored)** - 位于当前目录 (`./`)
   - 使用重构的 `main_window_refactored.py` 主窗口
   - 采用组件化架构（StateManager, LayoutManager, PeripheralManager）
   - 包含所有重构改进

两个版本都具备完整的依赖文件，可以独立运行。

## 仓库管理步骤

### 1. 旧版程序 - 上传到原仓库

当前 Git 仓库已包含新旧混合代码。需要将旧版代码提交到新分支并合并到 main。

```bash
# 确保当前在项目根目录
cd /path/to/svd_tool_V1.1

# 创建并切换到旧版分支
git checkout -b legacy-version

# 移除新版特有文件（保留旧版文件）
git rm svd_tool/ui/main_window_refactored.py
git rm -r svd_tool/ui/components/state_manager.py
git rm -r svd_tool/ui/components/layout_manager.py
git rm -r svd_tool/ui/components/peripheral_manager.py
# 注意：保留 menu_bar.py 和 toolbar.py（两者共享）

# 添加旧版文件夹（可选，如果希望将旧版作为子目录）
# 或者将整个仓库内容替换为旧版文件夹内容

# 提交更改
git add .
git commit -m "分离旧版程序，移除重构文件"

# 推送到远程仓库
git push origin legacy-version

# 创建 Pull Request 合并到 main（通过 GitHub 界面）
```

### 2. 新版程序 - 创建新仓库

新建一个名为 `SVDEditor` 的 GitHub 仓库，将当前目录（新版）推送到该仓库。

```bash
# 在 GitHub 上创建新仓库 "SVDEditor"（不要初始化 README）

# 初始化新版目录为新仓库
cd /path/to/svd_tool_V1.1
rm -rf .git  # 删除现有 Git 历史（或使用新目录）
git init
git add .
git commit -m "初始提交：重构版 SVD 编辑器"

# 添加远程仓库
git remote add origin https://github.com/你的用户名/SVDEditor.git
git branch -M main
git push -u origin main
```

### 3. 清理工作区

完成仓库分离后，可以删除 `old_version/` 文件夹（如果已上传到原仓库），或者保留作为备份。

## 开源协议

两个版本均使用 MIT 许可证：
- `LICENSE` 文件已复制到两个版本目录
- 确保在 GitHub 仓库设置中正确显示许可证

## 验证

运行以下命令验证两个版本均可独立启动：

```bash
# 测试旧版
cd old_version
python run.py  # 或 python -m svd_tool.main

# 测试新版
cd ..
python run.py  # 现在使用重构版本
```

## 注意事项

- 两个版本共享相同的核心模块（`svd_tool/core/`, `svd_tool/utils/`），但 UI 层不同
- 确保 PyQt6 依赖在两个环境中都可用
- 测试文件（`tests/`）主要针对新版，旧版可能需要单独测试

## 后续维护

- 旧版仓库：仅接收错误修复，不添加新功能
- 新版仓库：作为主要开发分支，持续改进

完成上述步骤后，你将拥有两个独立的 GitHub 仓库，分别对应两个版本的 SVD 工具。