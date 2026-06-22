"""
连锁规则引擎
支持自定义连锁删除/修改规则
例如：删除GPIO的PA0时，同步删除PBCON寄存器中的MODE0位域

规则语义：当 [源] 发生 [触发条件] 时，对 [目标] 执行 [目标操作]
- 源：外设/寄存器/位域的组合（填了的层才参与匹配，留空=该层不限）
- 触发条件：delete / modify / add
- 目标：外设/寄存器/位域的组合
- 目标操作：delete / modify / add（modify 可定义改哪个属性=什么值）
"""
import json
import os
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from copy import deepcopy

logger = logging.getLogger("chain_rules")


@dataclass
class ChainAction:
    """目标操作（与目标绑定）"""
    target_peripheral: str = ""   # 目标外设名（支持通配符 * / 变量 $PERIPHERAL）
    target_register: str = ""     # 目标寄存器名（空=操作整个外设）
    target_field: str = ""        # 目标位域名（空=操作整个寄存器）
    operation: str = "delete"     # 目标操作：delete, modify, add
    property_name: str = ""       # modify 时要修改的属性名（access/description/reset_value/size…）
    value: str = ""               # modify/add 时的值
    description: str = ""         # 描述信息


@dataclass
class ChainRule:
    """连锁规则 = 源 + 触发条件 + 目标操作列表"""
    name: str                              # 规则名称
    enabled: bool = True                   # 是否启用
    # --- 源（外设/寄存器/位域；填了才参与匹配，留空=该层不限）---
    source_peripheral: str = ""            # 源外设名（支持通配符 *）
    source_register: str = ""              # 源寄存器名（支持通配符 *）
    source_field: str = ""                 # 源位域名（支持通配符 *）
    # --- 触发条件 ---
    trigger: str = "delete"                # 触发条件：delete, modify, add
    # --- 目标操作列表 ---
    actions: List[ChainAction] = field(default_factory=list)
    description: str = ""


def _migrate_action_data(act_data: dict) -> dict:
    """把旧版动作字典迁移为新版字段名。

    旧：action / new_value / new_value_property
    新：operation / value / property_name
    """
    migrated = dict(act_data)
    if "action" in migrated and "operation" not in migrated:
        migrated["operation"] = migrated.pop("action")
    if "new_value_property" in migrated and "property_name" not in migrated:
        migrated["property_name"] = migrated.pop("new_value_property")
    if "new_value" in migrated and "value" not in migrated:
        migrated["value"] = migrated.pop("new_value")
    # 兼容缺失的新字段
    migrated.setdefault("operation", "delete")
    return migrated


def _migrate_rule_data(rule_data: dict) -> dict:
    """把旧版规则字典迁移为新版结构。

    旧：source_type=peripheral/register/field（单选枚举）
    新：去掉 source_type，源由 source_peripheral/register/field 哪些非空决定
    """
    migrated = dict(rule_data)
    source_type = migrated.pop("source_type", None)

    # 旧模型按 source_type 强制约束各源字段的语义；迁移后保留已填字段即可，
    # 因为新模型的匹配逻辑本身就是"非空才匹配"，等价于旧的单选行为。
    # 这里仅做一次规范化：旧 source_type=peripheral 时若 source_register/field 误填则清空。
    if source_type == "peripheral":
        migrated.setdefault("source_register", "")
        migrated.setdefault("source_field", "")
        migrated["source_register"] = ""
        migrated["source_field"] = ""
    elif source_type == "register":
        migrated.setdefault("source_field", "")
        migrated["source_field"] = ""
    # source_type == "field" 或为空：原样保留三个源字段

    # 迁移动作列表
    if "actions" in migrated and isinstance(migrated["actions"], list):
        migrated["actions"] = [_migrate_action_data(a) for a in migrated["actions"]]

    return migrated


class ChainRulesEngine:
    """连锁规则引擎"""

    def __init__(self):
        self.rules: List[ChainRule] = []
        self.enabled = True  # 全局开关
        self._rule_file = None
        self.logger = logging.getLogger("ChainRulesEngine")

    def set_rule_file(self, path: str):
        """设置规则文件路径"""
        self._rule_file = path
        self.load_rules()

    def load_rules(self):
        """从文件加载规则（自动迁移旧格式）"""
        if not self._rule_file or not os.path.exists(self._rule_file):
            self.logger.debug("无规则文件或文件不存在，使用空规则")
            return

        try:
            with open(self._rule_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.enabled = data.get('enabled', True)
            self.rules = []
            migrated_any = False

            for rule_data in data.get('rules', []):
                # 检测旧格式（含 source_type 或旧动作字段）
                is_legacy = ("source_type" in rule_data)
                if not is_legacy and isinstance(rule_data.get("actions"), list):
                    for a in rule_data["actions"]:
                        if "action" in a or "new_value" in a or "new_value_property" in a:
                            is_legacy = True
                            break

                migrated = _migrate_rule_data(rule_data) if is_legacy else dict(rule_data)
                migrated_any = migrated_any or is_legacy

                actions = []
                for act_data in migrated.get('actions', []):
                    actions.append(ChainAction(**act_data))
                rule_data_copy = dict(migrated)
                rule_data_copy['actions'] = actions
                self.rules.append(ChainRule(**rule_data_copy))

            self.logger.info(f"加载了 {len(self.rules)} 条连锁规则")

            # 若发生过迁移，立即回写为新格式
            if migrated_any:
                self.logger.info("检测到旧格式连锁规则，已自动迁移为新格式并回写")
                self.save_rules()
        except Exception as e:
            self.logger.error(f"加载连锁规则失败: {e}")

    def save_rules(self):
        """保存规则到文件"""
        if not self._rule_file:
            self.logger.warning("未设置规则文件路径")
            return

        try:
            data = {
                'enabled': self.enabled,
                'rules': []
            }
            for rule in self.rules:
                rule_dict = asdict(rule)
                data['rules'].append(rule_dict)

            with open(self._rule_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.logger.info(f"保存了 {len(self.rules)} 条连锁规则")
        except Exception as e:
            self.logger.error(f"保存连锁规则失败: {e}")

    def add_rule(self, rule: ChainRule):
        """添加规则"""
        self.rules.append(rule)
        if self._rule_file:
            self.save_rules()

    def remove_rule(self, index: int):
        """删除规则"""
        if 0 <= index < len(self.rules):
            self.rules.pop(index)
            if self._rule_file:
                self.save_rules()

    def update_rule(self, index: int, rule: ChainRule):
        """更新规则"""
        if 0 <= index < len(self.rules):
            self.rules[index] = rule
            if self._rule_file:
                self.save_rules()

    def _match_pattern(self, pattern: str, value: str) -> bool:
        """
        匹配模式，支持通配符 *
        例如: "GPIO*" 匹配 "GPIOA", "GPIOB"
              "*" 匹配所有
        """
        if not pattern or pattern == "*":
            return True
        if "*" not in pattern:
            return pattern == value

        # 简单的通配符匹配
        parts = pattern.split("*")
        if len(parts) == 2:
            prefix, suffix = parts
            if prefix and not value.startswith(prefix):
                return False
            if suffix and not value.endswith(suffix):
                return False
            return True

        # 多个通配符 - 转为简单检查
        for part in parts:
            if part and part not in value:
                return False
        return True

    def get_chain_actions(self, source_peripheral: str,
                          source_register: str = "", source_field: str = "",
                          trigger: str = "delete") -> List[ChainAction]:
        """
        获取匹配的连锁动作

        源匹配规则：规则里 source_* 填了的层才参与匹配，留空=该层不限。

        Args:
            source_peripheral: 源外设名（实际被操作的外设）
            source_register: 源寄存器名（实际被操作的寄存器，可空）
            source_field: 源位域名（实际被操作的位域，可空）
            trigger: 触发条件

        Returns:
            匹配到的连锁动作列表
        """
        if not self.enabled:
            return []

        actions = []
        for rule in self.rules:
            if not rule.enabled:
                continue
            if rule.trigger != trigger:
                continue

            # 源匹配：填了的层才匹配，留空=该层不限
            if rule.source_peripheral:
                if not self._match_pattern(rule.source_peripheral, source_peripheral):
                    continue
            if rule.source_register:
                if not self._match_pattern(rule.source_register, source_register):
                    continue
            if rule.source_field:
                if not self._match_pattern(rule.source_field, source_field):
                    continue

            # 收集动作，替换通配符
            for action in rule.actions:
                resolved = ChainAction(
                    target_peripheral=self._resolve_wildcard(
                        action.target_peripheral, source_peripheral,
                        source_register, source_field),
                    target_register=self._resolve_wildcard(
                        action.target_register, source_register,
                        source_register, source_field),
                    target_field=self._resolve_wildcard(
                        action.target_field, source_field,
                        source_register, source_field) if action.target_field else "",
                    operation=action.operation,
                    property_name=action.property_name,
                    value=action.value,
                    description=action.description
                )
                actions.append(resolved)

        return actions

    def _resolve_wildcard(self, pattern: str, primary_value: str,
                          register_value: str = "", field_value: str = "") -> str:
        """
        解析变量
        $PERIPHERAL -> 替换为源外设名
        $REGISTER -> 替换为源寄存器名
        $FIELD -> 替换为源位域名
        $NAME -> 替换为primary_value
        """
        if not pattern:
            return pattern

        result = pattern
        result = result.replace("$PERIPHERAL", primary_value)
        result = result.replace("$REGISTER", register_value)
        result = result.replace("$FIELD", field_value)
        result = result.replace("$NAME", primary_value)

        return result

    def execute_chain(self, device_info, source_peripheral: str,
                      source_register: str = "", source_field: str = "",
                      trigger: str = "delete") -> List[Dict[str, Any]]:
        """
        执行连锁操作

        Args:
            device_info: 设备信息对象
            source_peripheral: 源外设名
            source_register: 源寄存器名
            source_field: 源位域名
            trigger: 触发条件

        Returns:
            执行结果列表，每项包含 {operation, success, target, message}
        """
        actions = self.get_chain_actions(
            source_peripheral, source_register, source_field, trigger)

        results = []
        for action in actions:
            result = self._execute_action(device_info, action)
            results.append(result)

        return results

    def _execute_action(self, device_info, action: ChainAction) -> Dict[str, Any]:
        """执行单个目标操作"""
        result = {
            'operation': action.operation,
            'success': False,
            'target': f"{action.target_peripheral}.{action.target_register}" +
                      (f".{action.target_field}" if action.target_field else ""),
            'message': ''
        }

        try:
            # 查找目标外设
            peripherals = device_info.peripherals
            target_periph = None
            for pname, periph in peripherals.items():
                if self._match_pattern(action.target_peripheral, pname):
                    target_periph = periph
                    result['target'] = pname + "." + action.target_register
                    break

            if not target_periph:
                result['message'] = f"目标外设 '{action.target_peripheral}' 未找到"
                return result

            if action.operation == "delete":
                result = self._exec_delete(target_periph, action, result)
            elif action.operation == "modify":
                result = self._exec_modify(target_periph, action, result)
            elif action.operation == "add":
                result = self._exec_add(target_periph, action, result)
            else:
                result['message'] = f"未知目标操作 '{action.operation}'"

        except Exception as e:
            result['message'] = f"执行失败: {e}"
            self.logger.error(f"连锁动作执行失败: {e}")

        return result

    # ==================== 目标操作实现 ====================

    def _exec_delete(self, target_periph, action: ChainAction, result: dict) -> dict:
        """执行删除操作"""
        if action.target_field:
            # 删除位域
            if hasattr(target_periph, 'registers') and action.target_register in target_periph.registers:
                reg = target_periph.registers[action.target_register]
                if hasattr(reg, 'fields') and action.target_field in reg.fields:
                    del reg.fields[action.target_field]
                    result['success'] = True
                    result['message'] = f"已删除位域 {target_periph.name}.{action.target_register}.{action.target_field}"
                    result['target'] = f"{target_periph.name}.{action.target_register}.{action.target_field}"
                else:
                    result['message'] = f"位域 '{action.target_field}' 未找到"
            else:
                result['message'] = f"寄存器 '{action.target_register}' 未找到"
        elif action.target_register:
            # 删除寄存器
            if hasattr(target_periph, 'registers') and action.target_register in target_periph.registers:
                del target_periph.registers[action.target_register]
                result['success'] = True
                result['message'] = f"已删除寄存器 {target_periph.name}.{action.target_register}"
                result['target'] = f"{target_periph.name}.{action.target_register}"
            else:
                result['message'] = f"寄存器 '{action.target_register}' 未找到"
        else:
            # 删除外设——连锁引擎不应直接删除外设（会破坏 device_info.peripherals 字典迭代），
            # 仅给出提示，由上层在确认后处理。
            result['message'] = f"删除外设需在主界面操作，目标外设 {target_periph.name}"
        return result

    def _exec_modify(self, target_periph, action: ChainAction, result: dict) -> dict:
        """执行修改操作（改属性=值）"""
        prop = action.property_name or "access"
        raw_value = action.value

        if action.target_field:
            # 修改位域属性
            if hasattr(target_periph, 'registers') and action.target_register in target_periph.registers:
                reg = target_periph.registers[action.target_register]
                if hasattr(reg, 'fields') and action.target_field in reg.fields:
                    fld = reg.fields[action.target_field]
                    if hasattr(fld, prop):
                        setattr(fld, prop, raw_value)
                        result['success'] = True
                        result['message'] = f"已修改 {target_periph.name}.{action.target_register}.{action.target_field}.{prop} = {raw_value}"
                        result['target'] = f"{target_periph.name}.{action.target_register}.{action.target_field}"
                    else:
                        result['message'] = f"位域属性 '{prop}' 不存在"
                else:
                    result['message'] = f"位域 '{action.target_field}' 未找到"
            else:
                result['message'] = f"寄存器 '{action.target_register}' 未找到"
        elif action.target_register:
            # 修改寄存器属性
            if hasattr(target_periph, 'registers') and action.target_register in target_periph.registers:
                reg = target_periph.registers[action.target_register]
                if hasattr(reg, prop):
                    setattr(reg, prop, raw_value)
                    result['success'] = True
                    result['message'] = f"已修改 {target_periph.name}.{action.target_register}.{prop} = {raw_value}"
                    result['target'] = f"{target_periph.name}.{action.target_register}"
                else:
                    result['message'] = f"寄存器属性 '{prop}' 不存在"
            else:
                result['message'] = f"寄存器 '{action.target_register}' 未找到"
        else:
            # 修改外设属性
            if hasattr(target_periph, prop):
                setattr(target_periph, prop, raw_value)
                result['success'] = True
                result['message'] = f"已修改 {target_periph.name}.{prop} = {raw_value}"
                result['target'] = target_periph.name
            else:
                result['message'] = f"外设属性 '{prop}' 不存在"
        return result

    def _exec_add(self, target_periph, action: ChainAction, result: dict) -> dict:
        """执行添加操作"""
        if action.target_field and action.target_register:
            # 添加位域到寄存器
            if hasattr(target_periph, 'registers') and action.target_register in target_periph.registers:
                reg = target_periph.registers[action.target_register]
                if hasattr(reg, 'fields') and action.target_field not in reg.fields:
                    from .data_model import Field
                    new_field = Field(name=action.target_field,
                                      description=action.description or "Added by chain rule")
                    reg.fields[action.target_field] = new_field
                    result['success'] = True
                    result['message'] = f"已添加位域 {target_periph.name}.{action.target_register}.{action.target_field}"
                    result['target'] = f"{target_periph.name}.{action.target_register}.{action.target_field}"
                else:
                    result['message'] = f"位域 '{action.target_field}' 已存在或寄存器无 fields"
            else:
                result['message'] = f"寄存器 '{action.target_register}' 未找到"
        elif action.target_register:
            # 添加寄存器到外设
            if hasattr(target_periph, 'registers') and action.target_register not in target_periph.registers:
                from .data_model import Register
                new_reg = Register(name=action.target_register, offset="0x00",
                                   description=action.description or "Added by chain rule")
                target_periph.registers[action.target_register] = new_reg
                result['success'] = True
                result['message'] = f"已添加寄存器 {target_periph.name}.{action.target_register}"
                result['target'] = f"{target_periph.name}.{action.target_register}"
            else:
                result['message'] = f"寄存器 '{action.target_register}' 已存在"
        return result
