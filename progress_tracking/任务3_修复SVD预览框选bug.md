# 任务3：修复SVD预览框选bug（问题8）

## 问题描述
SVD预览有bug，当选中一次位域之后，再选中寄存器或者外设，不会出现新的框选图，还是之前的。如果一开始是选中的是寄存器，那么不会框选外设，位域还是可以框选。怀疑跟层级有关系。

## 问题分析

### 根本原因
在`HighlightedTextEdit`类中，`highlight_keys`字典用于存储不同类型元素的高亮键：
```python
self.highlight_keys = {
    'peripheral': None,  # 当前选中的外设
    'register': None,    # 当前选中的寄存器
    'field': None        # 当前选中的位域
}
```

在`paintEvent`方法中，采用优先级策略（field > register > peripheral）来决定高亮哪个元素：
```python
priority_order = ['field', 'register', 'peripheral']
selected_element = None
selected_type = None

for element_type in priority_order:
    key = self.highlight_keys.get(element_type)
    if key and key in self.element_line_ranges:
        selected_element = key
        selected_type = element_type
        break  # 找到最高优先级的元素后立即停止
```

**问题所在**：
1. 当选中位域时，`highlight_keys['field']`被设置，但`highlight_keys['register']`和`highlight_keys['peripheral']`没有被清除
2. 当选中寄存器时，`highlight_keys['register']`被设置，但`highlight_keys['field']`没有被清除
3. 当选中外设时，`highlight_keys['peripheral']`被设置，但`highlight_keys['field']`和`highlight_keys['register']`没有被清除

由于优先级策略是field > register > peripheral，所以：
- 如果之前选中了位域，再选中寄存器或外设，由于`highlight_keys['field']`仍然存在，会继续高亮位域
- 如果之前选中了寄存器，再选中外设，由于`highlight_keys['register']`仍然存在，会继续高亮寄存器

### 相关文件
- `svd_tool/ui/components/realtime_preview.py` - 实时预览组件，包含HighlightedTextEdit类

## 修复方案

### 修改1：在set_current_highlight方法中清除其他类型的高亮键
**文件**: `svd_tool/ui/components/realtime_preview.py`
**位置**: `HighlightedTextEdit.set_current_highlight`方法（第168-193行）

**修改内容**：
在设置当前高亮时，根据元素类型清除其他类型的高亮键：
- 如果选中位域，清除寄存器和外设的高亮键
- 如果选中寄存器，清除位域和外设的高亮键
- 如果选中外设，清除位域和寄存器的高亮键

### 修改2：在clear_highlight方法中清除所有高亮键
**文件**: `svd_tool/ui/components/realtime_preview.py`
**位置**: `HighlightedTextEdit.clear_highlight`方法（第207-210行）

**修改内容**：
清除所有类型的高亮键，而不仅仅是`current_highlight_key`

## 修复效果

### 修复前
- 选中位域后，再选中寄存器或外设，仍然显示位域的框选
- 选中寄存器后，再选中外设，仍然显示寄存器的框选
- 框选显示与实际选择不一致

### 修复后
- 选中任何元素时，只显示该元素的框选
- 框选显示与实际选择一致
- 切换选择时，框选正确更新

## 测试建议
1. 测试选中位域后，再选中寄存器，框选是否正确更新
2. 测试选中位域后，再选中外设，框选是否正确更新
3. 测试选中寄存器后，再选中外设，框选是否正确更新
4. 测试选中外设后，再选中寄存器，框选是否正确更新
5. 测试选中寄存器后，再选中位域，框选是否正确更新
6. 测试选中外设后，再选中位域，框选是否正确更新

## 完成状态
✅ 已完成

## 下次任务
修复显示预览按钮bug（问题10）
