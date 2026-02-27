# 任务4：修复显示预览按钮bug（问题10）

## 问题描述
生成SVD按钮旁边的显示预览按钮有bug，当我已经以某种方式预览时，再点击显示预览按钮，界面会异常，回到了标签页模式，但是工具栏的选项还是之前的模式。我希望这个按钮只是用来唤起预览窗口的，而不是切换布局模式的。布局模式应该通过预览窗口的工具栏来切换。

## 问题分析

### 根本原因
在`main_window_refactored.py`的`open_preview_window`方法中（第307-313行），总是调用`self.preview_manager.set_mode(PreviewMode.TAB)`，这会导致无论当前是什么模式，点击预览按钮都会强制切换到标签页模式。

```python
def open_preview_window(self):
    """打开预览窗口（使用预览管理器）"""
    # 使用预览管理器切换到标签页模式
    from .components.preview_manager import PreviewMode
    self.preview_manager.set_mode(PreviewMode.TAB)  # 问题：总是切换到标签页模式
    self.preview_manager.set_preview_visible(True)
    self.logger.info("预览窗口已打开")
```

**问题所在**：
1. 点击预览按钮时，总是强制切换到标签页模式
2. 如果当前是底部模式或停靠窗口模式，点击预览按钮会切换到标签页模式
3. 预览窗口的工具栏选项（模式选择下拉框）仍然显示之前的模式，导致界面状态不一致

### 相关文件
- `svd_tool/ui/main_window_refactored.py` - 主窗口，包含open_preview_window方法
- `svd_tool/ui/components/toolbar.py` - 工具栏组件，包含预览按钮
- `svd_tool/ui/components/preview_manager.py` - 预览管理器

## 修复方案

### 修改1：修改open_preview_window方法
**文件**: `svd_tool/ui/main_window_refactored.py`
**位置**: `open_preview_window`方法（第307-313行）

**修改内容**：
移除`set_mode(PreviewMode.TAB)`调用，只保留`set_preview_visible(True)`，这样预览按钮只会唤起预览窗口，而不会改变当前的布局模式。

## 修复效果

### 修复前
- 点击预览按钮时，总是切换到标签页模式
- 如果当前是底部模式或停靠窗口模式，点击预览按钮会切换到标签页模式
- 预览窗口的工具栏选项仍然显示之前的模式，导致界面状态不一致

### 修复后
- 点击预览按钮时，只唤起预览窗口，不改变当前的布局模式
- 如果当前是底部模式，点击预览按钮后仍然是底部模式
- 如果当前是停靠窗口模式，点击预览按钮后仍然是停靠窗口模式
- 预览窗口的工具栏选项与实际模式一致

## 测试建议
1. 测试在标签页模式下点击预览按钮
2. 测试在底部模式下点击预览按钮
3. 测试在停靠窗口模式下点击预览按钮
4. 测试预览窗口的工具栏选项是否与实际模式一致

## 完成状态
✅ 已完成

## 下次任务
修复撤销功能（问题1）
