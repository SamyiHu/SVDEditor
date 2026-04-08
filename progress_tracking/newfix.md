# SVDEditor 四项Bug分析与修复计划

## 一、代码探索总结

已完整阅读以下关键文件：
- `svd_tool/ui/components/peripheral_manager.py` — 上移/下移逻辑（607-778行）
- `svd_tool/ui/components/state_manager.py` — 状态管理、移动操作（638-648行 execute_command，959-1026行 move函数）
- `svd_tool/core/command_history.py` — 命令历史（25-42行 execute）
- `svd_tool/ui/widgets/bit_field_widget.py` — 位域图渲染（260-501行）
- `svd_tool/core/data_model.py` — Field数据模型（bit_offset: int, bit_width: int）

---

## 二、问题根因分析

### 问题1：上移/下移误提示"外设已在最上方/最下方"

**根因：`state_manager.execute_command()` 没有返回值**

```python
# state_manager.py 第638行
def execute_command(self, command: Command):
    """执行命令并记录到历史"""
    command.selection_before = self.get_selection()
    self.command_history.execute(command)  # 这个方法返回execute()的结果，但被丢弃了
    command.selection_after = self.get_selection()
    self._notify_state_change()
    # ← 没有 return 语句！返回 None
```

而 `peripheral_manager.py` 中：
```python
# 第672行
moved = self.state_manager.execute_command(command)  # moved 永远是 None

if moved:  # 永远 False
    # 重新选中该项目 ← 永远不会执行
    QTimer.singleShot(50, lambda: self._select_peripheral_in_tree(periph_name))
else:
    # 永远执行这个分支！
    QMessageBox.information(..., "外设已在最上方，无法上移")
```

**关键点：移动操作实际上成功了**（command.execute() 确实被调用，数据确实被修改），但返回值丢失了，导致始终显示错误提示。

### 问题2：上移/下移会展开移动的外设

**根因：双重状态通知导致树被重建两次**

调用链：
1. `state_manager.execute_command(command)` 
2. → `command.execute()` → `move_peripheral_up()` → `_notify_state_change()` → `update_peripheral_tree()` **[第一次重建]**
3. → `_notify_state_change()` → `update_peripheral_tree()` **[第二次重建]**

每次 `update_peripheral_tree()` 都会：
- 保存展开状态 → 清空树 → 重建 → 恢复展开状态

由于问题1导致重新选中代码（`_select_peripheral_in_tree`）永远不会执行，树的状态恢复不一致，加上双重重建导致视觉上的异常展开行为。

### 问题3：移动手感差

**根因：整棵树完全重建 + 双重通知**

- `update_peripheral_tree()` 每次都 `clear()` 整棵树再完全重建，这在项目数量多时非常慢
- 双重 `_notify_state_change()` 导致重建执行两次，加倍卡顿
- 滚动位置和视觉焦点在 `clear()` 时丢失

### 问题4：位域图显示bug

#### 4a. 有的块只显示名字，既不在外部显示位域大小，也不在内部显示

**根因：`_paint_fields` 和 `_paint_external_labels` 使用不同的字体度量计算 `is_fully_shown_inside`**

在 `_paint_fields`（第306行）中：
```python
fm = QFontMetrics(QFont("Arial", 9))  # 9号字体
name_width = fm.horizontalAdvance(name_text)
```

在 `_paint_external_labels`（第408行）中：
```python
fm = QFontMetrics(QFont("Arial", 8))  # 8号字体 ← 不同！
name_width = fm.horizontalAdvance(field.name)
```

这导致：
- `_paint_fields` 中用 **Arial 9** 计算 `total_needed`，可能判断为"空间不够，不显示完整内容"
- `_paint_external_labels` 中用 **Arial 8** 计算 `is_fully_shown_inside`，可能判断为"已完整显示，跳过外部标签"
- **结果：字段既不在内部完整显示，也不生成外部标签**

#### 4b. 同样大小的位域有的显示全名，有的显示缩写

**根因：显示逻辑以 `field.name` 的像素宽度为阈值条件，而非以位域的 `bit_width`（像素宽度）为主要判断依据**

```python
# _paint_fields 第318-320行
total_needed = max(name_width, range_width) + 8
if field_width >= total_needed and field_width >= 40:
    # 完整显示
elif field_width >= name_width + 8:
    # 只显示名称
elif field_width >= 20:
    # 小字体或首字母缩写
```

同样 `bit_width=1` 的位域，像素宽度相同（约18.75px），但：
- `PD0`（3字符）→ `name_width` 较小 → 可能满足 `name_width + 8 < 18.75` → 显示名称
- `PD10`（4字符）→ `name_width` 较大 → 可能不满足 → 显示缩写或首字母

**这不是浮点精度问题，而是显示策略不合理。** 相同位宽的位域应该采用一致的显示策略（统一用缩写或统一用全名）。

---

## 三、修复计划

### 修复1：上移/下移误提示

**文件**: `svd_tool/ui/components/state_manager.py`

- 修改 `execute_command()` 方法，返回 `command_history.execute(command)` 的结果
- 同时移除末尾多余的 `_notify_state_change()`（因为命令的 execute 函数内部已经调用过）

```python
def execute_command(self, command: Command):
    command.selection_before = self.get_selection()
    result = self.command_history.execute(command)  # 捕获返回值
    command.selection_after = self.get_selection()
    # 移除: self._notify_state_change()  # 避免双重通知
    return result  # 添加返回
```

**风险**：需确认其他调用 `execute_command` 的地方（如 add_peripheral, update_peripheral 等）的 execute 函数是否也自己调用了 `_notify_state_change()`。如果有些命令的 execute 不调用通知，则需要保留。

### 修复2：上移/下移展开外设

**文件**: `svd_tool/ui/components/peripheral_manager.py`

- 修复问题1后，`_select_peripheral_in_tree` 会被正确调用
- 在 `_select_peripheral_in_tree` 中，确保选中项不被展开
- 或者在 `update_peripheral_tree` 中排除正在移动的外设的展开状态恢复

**具体方案**：
- 在 `move_selected_peripheral_up/down` 中，移动前保存当前外设的展开状态
- 移动后，确保该外设的展开状态与移动前一致

### 修复3：移动手感优化

**文件**: `svd_tool/ui/components/peripheral_manager.py`, `svd_tool/ui/components/state_manager.py`

**方案A（最小改动）**：
- 移除 `execute_command` 中的双重通知
- 使用 `blockSignals` 避免中间过程触发UI更新

**方案B（更好的体验）**：
- `update_peripheral_tree()` 改为增量更新而非全量重建
- 只交换两个顶层项的位置，不重建整棵树

推荐方案B，但可以先实施方案A快速修复。

### 修复4：位域图显示

**文件**: `svd_tool/ui/widgets/bit_field_widget.py`

**4a. 统一字体度量**：
- 将 `is_fully_shown_inside` 的判断逻辑抽取为一个共享方法
- 确保内外使用完全一致的字体和计算方式
- 或者直接在 `_paint_fields` 中记录每个字段的显示状态，`_paint_external_labels` 直接使用该状态

**4b. 改进显示策略**：
- 对于相同 `bit_width` 的位域，采用统一的显示模式
- 新策略建议：
  1. 先计算位域的像素宽度 `field_px_width`
  2. 根据像素宽度确定显示等级（完整/名称/缩写/外部标签）
  3. 同等级内的所有位域使用相同的显示模式
  4. 名称过长时统一截断为缩写，而非有的全写有的缩写

---

## 四、涉及文件清单

| 文件 | 修改内容 |
|---|---|
| `svd_tool/ui/components/state_manager.py` | `execute_command` 返回值、双重通知 |
| `svd_tool/ui/components/peripheral_manager.py` | 移动后选中/展开状态保持 |
| `svd_tool/ui/widgets/bit_field_widget.py` | 统一字体度量、改进显示策略 |

## 五、建议修复优先级

1. **问题1**（误提示）— 一行代码修复，影响最大
2. **问题4**（位域图）— 纯渲染逻辑，不影响数据
3. **问题3**（移动手感）— 需要测试双重通知移除后的副作用
4. **问题2**（展开状态）— 依赖问题1的修复，可能自动解决

---

如果您对这个计划满意，请 **toggle to Act mode** 以开始实施修复。如果需要调整优先级或修改方案，请告诉我。