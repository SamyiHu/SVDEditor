# 任务2：修复预览窗口布局模式bug（问题7）

## 问题描述
预览窗口的布局模式有bug，切换布局模式后界面显示异常，或者预览窗口消失了。

## 问题分析

### 根本原因
1. **工具栏重复添加问题**：在底部模式下，工具栏被添加到preview_widget的顶部（第514-525行），但切换回标签页模式时没有正确移除，导致工具栏重复添加或丢失。

2. **preview_widget父级管理混乱**：
   - 在标签页模式下，preview_widget在preview_container中
   - 在底部模式下，preview_widget被移到preview_splitter中
   - 在停靠窗口模式下，preview_widget被移到preview_dock中
   - 切换模式时，preview_widget的父级被频繁改变，可能导致显示问题

3. **preview_container布局不一致**：
   - 在标签页模式下，preview_container包含工具栏和preview_widget
   - 在底部模式下，preview_container被忽略，preview_widget直接添加到preview_splitter
   - 在停靠窗口模式下，preview_container也被忽略

### 相关文件
- `svd_tool/ui/components/preview_manager.py` - 预览管理器，负责模式切换
- `svd_tool/ui/components/layout_manager.py` - 布局管理器
- `svd_tool/ui/preview_window.py` - 预览窗口

## 修复方案

### 修改1：统一工具栏管理
**文件**: `svd_tool/ui/components/preview_manager.py`

**修改内容**：
1. 工具栏始终保持在preview_container的顶部，不移动到preview_widget
2. 在底部模式下，将整个preview_container添加到preview_splitter，而不是只添加preview_widget
3. 在停靠窗口模式下，将整个preview_container添加到preview_dock，而不是只添加preview_widget

### 修改2：简化preview_widget父级管理
**修改内容**：
1. preview_widget始终保持在preview_container中，不移动
2. 模式切换时，只移动preview_container，不移动preview_widget
3. 这样可以避免preview_widget的父级频繁改变

### 修改3：修复_show_bottom_mode方法
**修改内容**：
1. 移除将工具栏添加到preview_widget顶部的代码（第514-525行）
2. 直接将preview_container添加到preview_splitter
3. 确保preview_container和preview_widget都可见

### 修改4：修复_show_dock_mode方法
**修改内容**：
1. 将preview_container添加到preview_dock，而不是只添加preview_widget
2. 确保preview_container和preview_widget都可见

### 修改5：修复_hide_bottom_mode方法
**修改内容**：
1. 从preview_splitter中移除preview_container，而不是preview_widget
2. 确保preview_container被正确恢复

### 修改6：简化_show_tab_mode方法
**修改内容**：
1. 移除不必要的preview_widget父级管理代码
2. 简化preview_container的添加逻辑

## 修复效果

### 修复前
- 切换布局模式后界面显示异常
- 预览窗口消失
- 工具栏重复添加或丢失

### 修复后
- 切换布局模式后界面正常显示
- 预览窗口始终可见
- 工具栏始终在正确位置

## 测试建议
1. 测试标签页模式切换到底部模式
2. 测试底部模式切换到标签页模式
3. 测试标签页模式切换到停靠窗口模式
4. 测试停靠窗口模式切换到标签页模式
5. 测试底部模式切换到停靠窗口模式
6. 测试停靠窗口模式切换到底部模式
7. 测试多次切换模式

## 完成状态
✅ 已完成

## 下次任务
修复SVD预览框选bug（问题8）
