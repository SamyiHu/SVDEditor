# 连锁规则编写指南 | Chain Rules Guide

连锁操作在某个元素发生特定操作时，**自动联动对其他关联元素执行目标操作**。
Chain operations **automatically apply a target operation to related elements** when a specific operation happens on a source element.

一条规则的完整语义：
> **当 [源] 发生 [触发条件] 时，对 [目标] 执行 [目标操作]**

A rule means:
> **When [Source] meets [Trigger], apply [Target Operation] to [Target]**

例如：删除 GPIOA 的 PA0 位域时，自动删除 PACON 寄存器中的 MODE0 位域。
Example: deleting GPIOA's PA0 field automatically deletes MODE0 in PACON register.

---

## 打开编辑界面 | Opening the Editor

菜单栏 → **工具** → **编辑连锁规则...**
Menu → **Tools** → **Edit Chain Rules...**

通过 **工具 → 启用连锁操作** 开关全局连锁功能。
Toggle global chain operations via **Tools → Enable Chain Operations**.

---

## 四要素 | Four Elements

每条规则由四个要素组成 / Each rule has four elements：

| 要素 Element | 说明 Description |
|---|---|
| **源 Source** | 触发规则的对象，由外设/寄存器/位域组合（可只填一个或几个）The object that triggers the rule |
| **触发条件 Trigger** | 源发生的操作：`delete` / `modify` / `add` What happens to the source |
| **目标 Target** | 被联动操作的对象，同样由外设/寄存器/位域组合 The object the operation acts on |
| **目标操作 Target Operation** | 对目标执行的操作：`delete` / `modify` / `add`，modify 可定义改哪个属性=什么值 What is done to the target |

### 源的匹配规则 | Source Matching

**填了的层才参与匹配，留空=该层不限（匹配任意值）。**
Only filled layers participate in matching; an empty layer means "no limit at this layer".

| 源外设 | 源寄存器 | 源位域 | 实际含义 Meaning |
|---|---|---|---|
| `GPIOA` | `MODER` | `MODE0` | 仅当删除 GPIOA.MODER.MODE0 时触发 Only exact field |
| `GPIOA` | `MODER` | *(空 empty)* | 删除 GPIOA.MODER 任意位域时触发 Any field under GPIOA.MODER |
| `GPIOA` | *(空 empty)* | *(空 empty)* | 删除 GPIOA 下任意寄存器/位域时触发 Anything under GPIOA |
| `GPIO*` | *(空 empty)* | *(空 empty)* | 删除任意 GPIO 外设下任何元素时触发 Anything under any GPIO* peripheral |

### ChainRule 规则定义 | Rule Definition

| Field 字段 | Description 说明 | Example 示例 |
|---|---|---|
| `name` | 规则名称 Rule name | `"PA0 chain"` |
| `enabled` | 是否启用 Enabled | `true` / `false` |
| `source_peripheral` | 源外设名（支持 `*` 通配符，空=不限）Source peripheral (wildcards, empty=no limit) | `"GPIOA"` / `"GPIO*"` |
| `source_register` | 源寄存器名（空=不限）Source register (empty=no limit) | `"MODER"` / `"*"` |
| `source_field` | 源位域名（空=不限）Source field (empty=no limit) | `"MODE0"` / `"PA*"` |
| `trigger` | 触发条件 Trigger | `"delete"` / `"modify"` / `"add"` |
| `actions` | 目标操作列表 Target operations | See below |

### ChainAction 目标操作 | Target Operation

| Field 字段 | Description 说明 | Example 示例 |
|---|---|---|
| `target_peripheral` | 目标外设（支持变量 `$PERIPHERAL`）Target peripheral (variables) | `"PACON"` / `"$PERIPHERAL"` |
| `target_register` | 目标寄存器（空=操作整个外设）Target register (empty=whole peripheral) | `"MODER"` |
| `target_field` | 目标位域（空=操作整个寄存器）Target field (empty=whole register) | `"MODE0"` |
| `operation` | 目标操作 Target operation | `"delete"` / `"modify"` / `"add"` |
| `property_name` | modify 时要改的属性名（见下表）Property to modify (see below) | `"access"` |
| `value` | modify/add 时的值 Value | `"read-only"` |
| `description` | 描述 Description | `"Sync config"` |

### modify 可改的属性 | Modifiable Properties

属性可选项取决于目标层级 / Available properties depend on the target layer：

| 目标层 Target Layer | 可改属性 Available Properties |
|---|---|
| 位域 Field | `access`, `description`, `display_name`, `reset_value`, `bit_offset`, `bit_width`, `name` |
| 寄存器 Register | `access`, `description`, `display_name`, `reset_value`, `reset_mask`, `size`, `offset`, `name` |
| 外设 Peripheral | `description`, `display_name`, `group_name`, `base_address`, `name` |

---

## 通配符与变量 | Wildcards & Variables

### 通配符 | Wildcards

| Pattern 模式 | Description 说明 | Example 示例 |
|---|---|---|
| `*` | 匹配所有 Match all | `source_peripheral: "*"` |
| `prefix*` 前缀匹配 | Match prefix | `"GPIO*"` → GPIOA, GPIOB... |
| `*suffix` 后缀匹配 | Match suffix | `"*CON"` → PACON, PBCON... |
| `*mid*` 包含匹配 | Contains | `"*OD*"` → MODER, ODR... |
| 精确值 Exact | Exact match | `"GPIOA"` → GPIOA only |

### 变量替换 | Variable Substitution

| Variable 变量 | Replaced By 替换为 | Description 说明 |
|---|---|---|
| `$PERIPHERAL` | 源外设名 Source peripheral | GPIOA → `"GPIOA"` |
| `$REGISTER` | 源寄存器名 Source register | MODER → `"MODER"` |
| `$FIELD` | 源位域名 Source field | MODE0 → `"MODE0"` |

---

## 实际示例 | Examples

### 示例 1：精确匹配 → 删除 GPIOA.PA0 时同步删除 PACON.MODE0

```json
{
  "name": "PA0 chain",
  "enabled": true,
  "source_peripheral": "GPIOA",
  "source_register": "PA",
  "source_field": "PA0",
  "trigger": "delete",
  "actions": [
    {
      "target_peripheral": "GPIOA",
      "target_register": "PACON",
      "target_field": "MODE0",
      "operation": "delete"
    }
  ]
}
```

### 示例 2：通配符匹配 → 删除任意 GPIO 位域时同步删除 PACON 同名位域

```json
{
  "name": "GPIO wildcard chain",
  "enabled": true,
  "source_peripheral": "GPIO*",
  "source_register": "*",
  "source_field": "*",
  "trigger": "delete",
  "actions": [
    {
      "target_peripheral": "PBCON",
      "target_register": "$REGISTER",
      "target_field": "$FIELD",
      "operation": "delete"
    }
  ]
}
```

### 示例 3：寄存器级联 → 删除整个寄存器时同步删除关联寄存器

```json
{
  "name": "Register cascade",
  "enabled": true,
  "source_peripheral": "GPIOA",
  "source_register": "MODER",
  "source_field": "",
  "trigger": "delete",
  "actions": [
    {
      "target_peripheral": "GPIOA",
      "target_register": "OSPEEDR",
      "target_field": "",
      "operation": "delete"
    }
  ]
}
```

### 示例 4：modify 操作 → 删除时把目标位域改为只读

```json
{
  "name": "Set read-only on delete",
  "enabled": true,
  "source_peripheral": "GPIO*",
  "source_register": "*",
  "source_field": "*",
  "trigger": "delete",
  "actions": [
    {
      "target_peripheral": "RCC",
      "target_register": "CR",
      "target_field": "RDY",
      "operation": "modify",
      "property_name": "access",
      "value": "read-only"
    }
  ]
}
```

---

## UI 中编辑 | Editing in UI

### 源 Source

填写外设 / 寄存器 / 位域三栏（任填一个或几个，留空=该层不限）。
Fill any of peripheral / register / field; leave empty = no limit at that layer.

### 目标操作表格 Target Operation Table

每行一个目标操作，7 列 / One target operation per row, 7 columns：

| 列 Column | 说明 Description |
|---|---|
| 目标外设 | 目标外设名 Target peripheral |
| 目标寄存器 | 留空=操作整个外设 Empty = whole peripheral |
| 目标位域 | 留空=操作整个寄存器 Empty = whole register |
| 目标操作 | `delete` / `modify` / `add` |
| 属性 | modify 时启用，从可选属性下拉选 Enabled when operation=modify |
| 值 | modify/add 时填入 Enabled when operation=modify or add |
| × | 删除该行 Remove this row |

操作类型为 `delete` 时，属性与值列自动禁用。
Property and value columns are disabled when operation=`delete`.

---

## 规则文件格式 | Rule File Format

通过 `set_rule_file()` 设置路径后可持久化到 JSON 文件。
Rules can be persisted to a JSON file via `set_rule_file()`.

```json
{
  "enabled": true,
  "rules": [
    {
      "name": "GPIO wildcard chain",
      "enabled": true,
      "source_peripheral": "GPIO*",
      "source_register": "*",
      "source_field": "*",
      "trigger": "delete",
      "actions": [
        {
          "target_peripheral": "PBCON",
          "target_register": "$REGISTER",
          "target_field": "$FIELD",
          "operation": "delete"
        }
      ],
      "description": ""
    }
  ]
}
```

### 旧格式自动迁移 | Legacy Format Auto-Migration

旧版本规则文件使用 `source_type`（单选枚举）字段。加载时引擎会自动迁移：
Legacy rule files use a `source_type` (single-select enum) field. The engine migrates them on load:

- 旧 `source_type="field"` → 保留 source_peripheral/register/field 三个字段
- 旧 `source_type="register"` → 仅保留 source_peripheral/register，source_field 清空
- 旧 `source_type="peripheral"` → 仅保留 source_peripheral
- 旧动作字段 `action` / `new_value` / `new_value_property` → 重命名为 `operation` / `value` / `property_name`

迁移后立即覆盖写回文件，下次打开看到的就是新格式。
Migrated files are written back immediately; subsequent opens show the new format.

---

## 触发流程 | Trigger Flow

当删除一个元素时 / When an element is deleted:
1. 引擎检查所有已启用的规则 / Engine checks all enabled rules
2. 匹配触发条件 + 源（填了的层才匹配，留空=不限）/ Match trigger + source (filled layers only)
3. 执行所有匹配规则的目标操作（resolve 变量后）/ Execute target operations of matching rules (after variable resolution)
4. 弹出对话框显示连锁操作结果 / Show dialog with chain operation results

支持的触发层级 / Supported trigger levels：
- 删除位域 / 单删寄存器 / 批删寄存器 / 批删位域 都会触发连锁
- Field delete / single register delete / batch register delete / batch field delete all trigger chains
