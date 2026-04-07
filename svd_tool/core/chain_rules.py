"""
连锁规则引擎
支持自定义连锁删除/修改规则
例如：删除GPIO的PA0时，同步删除PBCON寄存器中的MODE0位域
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
    """连锁动作"""
    target_peripheral: str  # 目标外设名（支持通配符 *）
    target_register: str    # 目标寄存器名（支持通配符 *）
    target_field: str = ""  # 目标位域名（为空表示整个寄存器）
    action: str = "delete"  # 动作类型：delete, modify
    description: str = ""   # 描述信息


@dataclass 
class ChainRule:
    """连锁规则"""
    name: str                      # 规则名称
    enabled: bool = True           # 是否启用
    source_type: str = "field"     # 源类型：peripheral, register, field
    source_peripheral: str = ""    # 源外设名（支持通配符 *）
    source_register: str = ""      # 源寄存器名（支持通配符 *）
    source_field: str = ""         # 源位域名（支持通配符 *）
    trigger: str = "delete"        # 触发条件：delete, modify
    actions: List[ChainAction] = field(default_factory=list)
    description: str = ""


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
        """从文件加载规则"""
        if not self._rule_file or not os.path.exists(self._rule_file):
            self.logger.debug("无规则文件或文件不存在，使用空规则")
            return
        
        try:
            with open(self._rule_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.enabled = data.get('enabled', True)
            self.rules = []
            
            for rule_data in data.get('rules', []):
                actions = []
                for act_data in rule_data.get('actions', []):
                    actions.append(ChainAction(**act_data))
                rule_data_copy = dict(rule_data)
                rule_data_copy['actions'] = actions
                self.rules.append(ChainRule(**rule_data_copy))
            
            self.logger.info(f"加载了 {len(self.rules)} 条连锁规则")
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
    
    def get_chain_actions(self, source_type: str, source_peripheral: str,
                          source_register: str = "", source_field: str = "",
                          trigger: str = "delete") -> List[ChainAction]:
        """
        获取匹配的连锁动作
        
        Args:
            source_type: 源类型 (peripheral/register/field)
            source_peripheral: 源外设名
            source_register: 源寄存器名
            source_field: 源位域名
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
            if rule.source_type != source_type:
                continue
            if rule.trigger != trigger:
                continue
            
            # 检查源是否匹配
            if not self._match_pattern(rule.source_peripheral, source_peripheral):
                continue
            if source_type in ("register", "field") and rule.source_register:
                if not self._match_pattern(rule.source_register, source_register):
                    continue
            if source_type == "field" and rule.source_field:
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
                    action=action.action,
                    description=action.description
                )
                actions.append(resolved)
        
        return actions
    
    def _resolve_wildcard(self, pattern: str, primary_value: str,
                          register_value: str = "", field_value: str = "") -> str:
        """
        解析通配符
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
    
    def execute_chain(self, device_info, source_type: str, source_peripheral: str,
                      source_register: str = "", source_field: str = "",
                      trigger: str = "delete") -> List[Dict[str, Any]]:
        """
        执行连锁操作
        
        Args:
            device_info: 设备信息对象
            source_type: 源类型
            source_peripheral: 源外设名
            source_register: 源寄存器名
            source_field: 源位域名
            trigger: 触发条件
        
        Returns:
            执行结果列表，每项包含 {action, success, target, message}
        """
        actions = self.get_chain_actions(
            source_type, source_peripheral, source_register, source_field, trigger)
        
        results = []
        for action in actions:
            result = self._execute_action(device_info, action)
            results.append(result)
        
        return results
    
    def _execute_action(self, device_info, action: ChainAction) -> Dict[str, Any]:
        """执行单个连锁动作"""
        result = {
            'action': action.action,
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
            
            if action.action == "delete":
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
            
        except Exception as e:
            result['message'] = f"执行失败: {e}"
            self.logger.error(f"连锁动作执行失败: {e}")
        
        return result