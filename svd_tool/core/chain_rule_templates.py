"""
连锁规则模板库
提供预置的常用连锁规则模板，用户可一键导入
"""
import json
import os
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

from .chain_rules import ChainRule, ChainAction, ChainRulesEngine

logger = logging.getLogger("chain_rule_templates")


@dataclass
class ChainRuleTemplate:
    """连锁规则模板"""
    name: str                           # 模板名称
    description: str = ""               # 模板描述
    category: str = "通用"              # 分类（通用/GPIO/时钟/中断/调试）
    applicable_scenes: str = ""         # 适用场景
    rules: List[ChainRule] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "applicable_scenes": self.applicable_scenes,
            "rules": [asdict(rule) for rule in self.rules]
        }


# ============================================================
#  内置模板定义
# ============================================================

def _make_builtin_templates() -> List[ChainRuleTemplate]:
    """构建内置模板列表"""
    templates: List[ChainRuleTemplate] = []

    # ---- 模板1：GPIO 复用功能连锁 ----
    templates.append(ChainRuleTemplate(
        name="GPIO复用功能连锁",
        description="删除GPIO端口引脚时，同步删除对应的复用功能配置寄存器位域",
        category="GPIO",
        applicable_scenes="适用于具有GPIO复用功能的MCU（如STM32、MM32等），"
                          "删除GPIOx的某个引脚相关配置时，自动删除AFR寄存器中对应的AF位域",
        rules=[
            ChainRule(
                name="删除GPIO MODE位域时同步删除对应的OSPEEDR和OTYPER位域",
                enabled=True,
                source_type="field",
                source_peripheral="GPIO*",
                source_register="MODER",
                source_field="MODE*",
                trigger="delete",
                actions=[
                    ChainAction(
                        target_peripheral="$PERIPHERAL",
                        target_register="OSPEEDR",
                        target_field="OSPEED*",
                        action="delete",
                        description="同步删除输出速度配置"
                    ),
                    ChainAction(
                        target_peripheral="$PERIPHERAL",
                        target_register="OTYPER",
                        target_field="OT*",
                        action="delete",
                        description="同步删除输出类型配置"
                    ),
                ],
            ),
            ChainRule(
                name="删除GPIO引脚的复用功能配置",
                enabled=True,
                source_type="field",
                source_peripheral="GPIO*",
                source_register="AFR*",
                source_field="AF*",
                trigger="delete",
                actions=[
                    ChainAction(
                        target_peripheral="$PERIPHERAL",
                        target_register="MODER",
                        target_field="MODE*",
                        action="delete",
                        description="同步删除模式配置"
                    ),
                ],
            ),
        ],
    ))

    # ---- 模板2：时钟使能连锁 ----
    templates.append(ChainRuleTemplate(
        name="时钟使能连锁",
        description="删除外设时，同步清除对应时钟使能寄存器中的使能位",
        category="时钟",
        applicable_scenes="适用于带有独立时钟使能控制的MCU，"
                          "删除外设后自动清除RCC寄存器中的对应时钟使能位",
        rules=[
            ChainRule(
                name="删除外设时清除时钟使能位",
                enabled=True,
                source_type="peripheral",
                source_peripheral="*",
                trigger="delete",
                actions=[
                    ChainAction(
                        target_peripheral="RCC",
                        target_register="*ENR*",
                        target_field="",
                        action="delete",
                        description="提示：请手动确认并清除RCC时钟使能位"
                    ),
                ],
            ),
        ],
    ))

    # ---- 模板3：中断配置连锁 ----
    templates.append(ChainRuleTemplate(
        name="中断配置连锁",
        description="删除外设时，同步清除NVIC中的中断使能位",
        category="中断",
        applicable_scenes="适用于具有NVIC中断控制器的Cortex-M系列MCU",
        rules=[
            ChainRule(
                name="删除外设时清除NVIC中断使能",
                enabled=True,
                source_type="peripheral",
                source_peripheral="*",
                trigger="delete",
                actions=[
                    ChainAction(
                        target_peripheral="NVIC",
                        target_register="ISER",
                        target_field="",
                        action="delete",
                        description="提示：请手动确认并清除NVIC中断使能位"
                    ),
                ],
            ),
        ],
    ))

    # ---- 模板4：DMA通道连锁 ----
    templates.append(ChainRuleTemplate(
        name="DMA通道连锁",
        description="删除外设时，同步清除DMA通道配置中对应的请求映射位域",
        category="调试",
        applicable_scenes="适用于带有DMA控制器的MCU，"
                          "删除外设后自动清理DMA请求映射",
        rules=[
            ChainRule(
                name="删除外设时清除DMA请求映射",
                enabled=True,
                source_type="peripheral",
                source_peripheral="*",
                trigger="delete",
                actions=[
                    ChainAction(
                        target_peripheral="DMA*",
                        target_register="*",
                        target_field="",
                        action="delete",
                        description="提示：请手动确认并清除DMA通道配置"
                    ),
                ],
            ),
        ],
    ))

    # ---- 模板5：空规则（用户自定义起始模板） ----
    templates.append(ChainRuleTemplate(
        name="空模板",
        description="不包含任何规则的空白模板，可作为自定义模板的起点",
        category="通用",
        applicable_scenes="自定义连锁规则的起始模板",
        rules=[],
    ))

    return templates


class ChainRuleTemplateManager:
    """连锁规则模板管理器"""

    _builtin_templates: Optional[List[ChainRuleTemplate]] = None

    @classmethod
    def get_builtin_templates(cls) -> List[ChainRuleTemplate]:
        """获取内置模板列表"""
        if cls._builtin_templates is None:
            cls._builtin_templates = _make_builtin_templates()
        return cls._builtin_templates

    @classmethod
    def get_template_by_name(cls, name: str) -> Optional[ChainRuleTemplate]:
        """按名称查找模板"""
        for tpl in cls.get_builtin_templates():
            if tpl.name == name:
                return tpl
        return None

    @classmethod
    def get_templates_by_category(cls, category: str) -> List[ChainRuleTemplate]:
        """按分类筛选模板"""
        return [tpl for tpl in cls.get_builtin_templates() if tpl.category == category]

    @classmethod
    def get_all_categories(cls) -> List[str]:
        """获取所有模板分类"""
        seen = set()
        result = []
        for tpl in cls.get_builtin_templates():
            if tpl.category not in seen:
                seen.add(tpl.category)
                result.append(tpl.category)
        return result

    @classmethod
    def apply_template(cls, template: ChainRuleTemplate, engine: ChainRulesEngine):
        """将模板中的规则应用到引擎"""
        for rule in template.rules:
            engine.add_rule(rule)
        logger.info(f"已应用模板 '{template.name}'（{len(template.rules)} 条规则）")

    @classmethod
    def export_template_to_file(cls, template: ChainRuleTemplate, file_path: str):
        """导出模板到JSON文件"""
        try:
            data = template.to_dict()
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"模板 '{template.name}' 已导出到 {file_path}")
        except Exception as e:
            logger.error(f"导出模板失败: {e}")
            raise

    @classmethod
    def import_template_from_file(cls, file_path: str) -> Optional[ChainRuleTemplate]:
        """从JSON文件导入模板"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            rules = []
            for rule_data in data.get('rules', []):
                actions = []
                for act_data in rule_data.get('actions', []):
                    actions.append(ChainAction(**act_data))
                rule_data_copy = dict(rule_data)
                rule_data_copy['actions'] = actions
                rules.append(ChainRule(**rule_data_copy))

            template = ChainRuleTemplate(
                name=data.get('name', '导入模板'),
                description=data.get('description', ''),
                category=data.get('category', '导入'),
                applicable_scenes=data.get('applicable_scenes', ''),
                rules=rules,
            )
            logger.info(f"已从 {file_path} 导入模板 '{template.name}'")
            return template
        except Exception as e:
            logger.error(f"导入模板失败: {e}")
            return None