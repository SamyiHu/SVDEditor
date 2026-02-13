# 实时SVD预览功能说明

## 概述

实时SVD预览功能提供了一个实时显示SVD XML内容的窗口，并支持双向同步选择：
- **实时更新**：当您编辑外设、寄存器或位域时，预览窗口会自动更新
- **双向同步**：在预览窗口选中元素时，树状图、外设图、位域图会同步选中；反之亦然
- **集成布局**：预览窗口集成在外设标签页中，无需翻页即可同时查看树状图、可视化和预览

## 功能特性

### 1. 实时XML预览
- 自动显示当前SVD文件的XML内容
- 支持XML语法高亮
- 显示行数统计

### 2. 自动刷新
- 默认启用自动刷新（500ms延迟）
- 可通过"自动刷新"按钮开关
- 手动刷新按钮可立即更新预览

### 3. 双向同步选择

#### 从预览窗口到其他视图
在预览窗口中点击任意行：
- 如果是外设行 → 树状图选中对应外设，外设图显示该外设
- 如果是寄存器行 → 树状图选中对应寄存器，位域图显示该寄存器
- 如果是位域行 → 树状图选中对应位域，位域图高亮该位域
- 如果是中断行 → 中断表格选中对应中断

#### 从其他视图到预览窗口
在树状图、外设图或位域图中选中元素：
- 预览窗口自动跳转到对应行
- 高亮显示该行

### 4. 跳转功能
- "跳转到选中"按钮可快速定位到当前选中的元素

## 使用方法

### 基本使用
1. 打开SVD文件或创建新文件
2. 切换到"外设"标签页
3. 在同一页面中查看树状图、可视化和实时预览

### 同步选择
1. 在预览窗口中点击任意元素（外设/寄存器/位域/中断）
2. 树状图、可视化和位域表格自动同步选中该元素
3. 或者在树状图中选中元素，预览窗口自动跳转到对应行

### 自动刷新控制
- 点击"自动刷新"按钮可开关自动更新功能
- 禁用后需要手动点击"刷新"按钮更新预览
- 预览窗口位于外设标签页右侧，可调整分割器大小

## 技术实现

### 核心组件
- **RealtimePreviewWidget** ([`svd_tool/ui/components/realtime_preview.py`](svd_tool/ui/components/realtime_preview.py)) - 实时预览组件
- **XMLHighlighter** - XML语法高亮器

### 布局结构
外设标签页采用三列分割器布局：
- **左侧（40%）**：外设树状图
- **中间（30%）**：可视化控件（地址映射、位域可视化）
- **右侧（30%）**：实时SVD预览

用户可以拖动分割器调整各列宽度。

### 信号连接
```
RealtimePreviewWidget.element_selected
    → MainWindowRefactored.on_preview_element_selected
        → StateManager.set_selection
        → VisualizationWidget.show_*
        → FieldTable.update
```

### 行号映射
预览组件维护一个行号映射表，将XML行号与元素信息关联：
```python
self.line_map = {
    line_number: (element_type, peripheral_name, element_name)
}
```

## 文件修改清单

### 新增文件
- [`svd_tool/ui/components/realtime_preview.py`](svd_tool/ui/components/realtime_preview.py) - 实时预览组件

### 修改文件
- [`svd_tool/ui/components/tab_builder.py`](svd_tool/ui/components/tab_builder.py) - 更新预览标签页创建逻辑
- [`svd_tool/ui/main_window_refactored.py`](svd_tool/ui/main_window_refactored.py) - 添加信号连接和处理方法
- [`svd_tool/i18n/zh_CN.json`](svd_tool/i18n/zh_CN.json) - 添加中文翻译
- [`svd_tool/i18n/en_US.json`](svd_tool/i18n/en_US.json) - 添加英文翻译

## 新增翻译键

### 中文 (zh_CN.json)
```json
{
  "button.enabled": "已启用",
  "button.disabled": "已禁用",
  "button.refresh": "刷新",
  "button.jump_to_selection": "跳转到选中",
  "label.auto_refresh": "自动刷新",
  "status.lines": "行数",
  "status.error": "错误",
  "status.selected": "已选中"
}
```

### 英文 (en_US.json)
```json
{
  "button.enabled": "Enabled",
  "button.disabled": "Disabled",
  "button.refresh": "Refresh",
  "button.jump_to_selection": "Jump to Selection",
  "label.auto_refresh": "Auto Refresh",
  "status.lines": "Lines",
  "status.error": "Error",
  "status.selected": "Selected"
}
```

## 性能优化

### 防抖机制
使用500ms延迟的定时器避免频繁更新：
```python
self.update_timer = QTimer()
self.update_timer.setSingleShot(True)
self.update_timer.timeout.connect(self._update_preview)
self.update_delay = 500
```

### QPlainTextEdit
使用`QPlainTextEdit`而非`QTextEdit`以获得更好的性能。

## 已知限制

1. **大型文件性能**：对于非常大的SVD文件（>10MB），实时更新可能会有延迟
2. **行号映射**：行号映射在每次更新时重建，对于频繁编辑可能影响性能
3. **高亮显示**：当前高亮是临时的，滚动后会消失

## 未来改进方向

1. **增量更新**：只更新修改的部分，而非重新生成整个XML
2. **持久化高亮**：使用QTextBlock的userData存储高亮信息
3. **搜索功能**：在预览窗口中添加搜索功能
4. **差异显示**：显示修改前后的差异
5. **折叠/展开**：支持XML元素的折叠和展开

## 测试建议

### 功能测试
1. 测试实时更新：添加/修改/删除外设、寄存器、位域
2. 测试双向同步：从预览窗口选择元素，从其他视图选择元素
3. 测试自动刷新：开关自动刷新，手动刷新
4. 测试跳转功能：使用"跳转到选中"按钮

### 性能测试
1. 测试大型SVD文件的加载和更新性能
2. 测试频繁编辑时的响应速度
3. 测试内存使用情况

### 兼容性测试
1. 测试不同SVD版本的兼容性
2. 测试特殊字符的处理
3. 测试继承外设的显示
