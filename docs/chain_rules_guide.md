# 连锁规则编写指南 | Chain Rules Guide

连锁操作可以在删除/修改某个元素时**自动联动操作其他关联元素**。
Chain operations **automatically sync related elements** when deleting or modifying an item.

例如：删除 GPIOA 的 PA0 位域时，自动删除 PBCON 寄存器中的 MODE0 位域。
Example: deleting GPIOA's PA0 field automatically deletes MODE0 in PBCON register.

---

## 打开编辑界面 | Opening the Editor

菜单栏 → **工具** → **编辑连锁规则...**
Menu → **Tools** → **Edit Chain Rules...**

通过 **工具 → 启用连锁操作** 开关全局连锁功能。
Toggle global chain operations via **Tools → Enable Chain Operations**.

---

## 数据结构 | Data Structure

每条规则由两部分组成：**规则定义（源）** + **连锁动作（目标）**
Each rule consists of: **Rule definition (source)** + **Chain actions (target)**

### ChainRule 规则定义 | Rule Definition

| Field 字段 | Description 说明 | Example 示例 |
|---|---|---|
| `name` | 规则名称 Rule name | `"GPIO-port chain"` |
| `enabled` | 是否启用 Enabled | `true` / `false` |
| `source_type` | 源类型 Source type | `"peripheral"` / `"register"` / `"field"` |
| `source_peripheral` | 源外设名（支持 `*` 通配符）Source peripheral (wildcards) | `"GPIOA"` / `"GPIO*"` |
| `source_register` | 源寄存器名 Source register | `"MODER"` / `"*"` |
| `source_field` | 源位域名 Source field | `"MODE0"` / `"PA*"` |
| `trigger` | 触发条件 Trigger | `"delete"` / `"modify"` |
| `actions` | 连锁动作列表 Action list | See below |

### ChainAction 连锁动作 | Chain Action

| Field 字段 | Description 说明 | Example 示例 |
|---|---|---|
| `target_peripheral` | 目标外设（支持变量）Target peripheral (variables) | `"PBCON"` / `"$PERIPHERAL"` |
| `target_register` | 目标寄存器 Target register | `"MODER"` / `"$REGISTER"` |
| `target_field` | 目标位域（空=整个寄存器）Target field (empty=whole register) | `"MODE0"` / `"$FIELD"` |
| `action` | 动作类型 Action type | `"delete"` / `"modify"` |
| `description` | 描述 Description | `"Sync delete port config"` |

---

## 通配符与变量 | Wildcards & Variables

### 通配符 | Wildcards

| Pattern 模式 | Description 说明 | Example 示例 |
|---|---|---|
| `*` | 匹配所有 Match all | `source_peripheral: "*"` |
| `prefix*` 前缀匹配 | Match prefix | `"GPIO*"` → GPIOA, GPIOB... |
| `*suffix` 后缀匹配 | Match suffix | `"*CON"` → PBCON, PCCON... |
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

### 示例 1：精确匹配 → 删除 GPIOA.PA0 时同步删除 PBCON.MODE0

```json
{
  "name": "GPIO-port chain",
  "enabled": true,
  "source_type": "field",
  "source_peripheral": "GPIOA",
  "source_register": "MODER",
  "source_field": "PA0",
  "trigger": "delete",
  "actions": [
    {
      "target_peripheral": "PBCON",
      "target_register": "MODER",
      "target_field": "MODE0",
      "action": "delete"
    }
  ]
}
```

### 示例 2：通配符匹配 → 删除任意 GPIO 位域时同步删除 PBCON 同名位域

```json
{
  "name": "GPIO wildcard chain",
  "enabled": true,
  "source_type": "field",
  "source_peripheral": "GPIO*",
  "source_register": "*",
  "source_field": "*",
  "trigger": "delete",
  "actions": [
    {
      "target_peripheral": "PBCON",
      "target_register": "$REGISTER",
      "target_field": "$FIELD",
      "action": "delete"
    }
  ]
}
```

### 示例 3：寄存器级联 → 删除整个寄存器

```json
{
  "name": "Register cascade",
  "enabled": true,
  "source_type": "register",
  "source_peripheral": "GPIOA",
  "source_register": "MODER",
  "source_field": "",
  "trigger": "delete",
  "actions": [
    {
      "target_peripheral": "PBCON",
      "target_register": "MODER",
      "target_field": "",
      "action": "delete"
    }
  ]
}
```

---

## UI 中编辑动作 | Editing Actions in UI

每行一个动作，格式为 / One action per line:
```
target_peripheral, target_register, target_field, action_type
```

```
PBCON, MODER, MODE0, delete
PCCON, MODER, MODE0, delete
```

目标位域为空时（操作整个寄存器）留空即可 / Leave field empty to target the whole register:
```
PBCON, MODER, , delete
```

---

## 规则文件格式 | Rule File Format

通过 `set_rule_file()` 设置路径后可持久化到 JSON 文件。
Rules can be persisted to a JSON file via `set_rule_file()`.

```json
{
  "enabled": true,
  "rules": [
    {
      "name": "Rule name",
      "enabled": true,
      "source_type": "field",
      "source_peripheral": "GPIO*",
      "source_register": "*",
      "source_field": "*",
      "trigger": "delete",
      "actions": [
        {
          "target_peripheral": "PBCON",
          "target_register": "$REGISTER",
          "target_field": "$FIELD",
          "action": "delete"
        }
      ]
    }
  ]
}
```

---

## 触发流程 | Trigger Flow

当删除一个元素时 / When an element is deleted:
1. 引擎检查所有已启用的规则 / Engine checks all enabled rules
2. 匹配源类型、外设、寄存器、位域和触发条件 / Match source type, peripheral, register, field and trigger
3. 执行所有匹配的动作 / Execute all matching actions
4. 弹出对话框显示连锁操作结果 / Show dialog with chain operation results
