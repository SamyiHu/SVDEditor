"""
AI 助手配置管理
"""
import json
import os
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional


logger = logging.getLogger("svd_tool.ai_assistant.Config")

# 默认配置路径
_CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".svd_tool")
_CONFIG_FILE = os.path.join(_CONFIG_DIR, "ai_config.json")


@dataclass
class AIConfig:
    """AI 助手配置"""
    # API 配置
    api_key: str = ""
    api_base_url: str = "https://api.openai.com/v1"
    api_type: str = "openai"  # "openai" 或 "anthropic"

    # 模型配置
    model: str = "gpt-4o-mini"
    temperature: float = 0.3
    max_tokens: int = 2048
    enable_streaming: bool = True

    # 会话配置
    max_history_messages: int = 50
    # 请求超时（秒）。批量任务上下文大、模型推理慢，60s 偏紧易在中途断流；
    # 提高到 120。流式场景下此值约束"两个 chunk 之间的最长间隔"。
    request_timeout: int = 120
    # 单次任务工具调用轮数预算。
    # 0 = 无限制（一直跑到 AI 不再调工具或用户停止为止，适合大型批量任务）；
    # >0 = 每跑完这么多轮就弹框问用户是否继续（防失控）。
    max_tool_iterations: int = 0

    # 上下文压缩配置（控制批量任务中 tool 结果的体积，防止上下文膨胀）：
    # compact_keep_groups: 最近多少"组"tool 调用保持完整，更早的会被压缩
    # compact_max_chars: 较早 tool 结果超过此字符数则截断保概要。0=禁用压缩（全量保留）
    compact_keep_groups: int = 6
    compact_max_chars: int = 400

    # 自定义系统提示词补充
    system_prompt_extra: str = ""

    def is_configured(self) -> bool:
        """是否已配置（至少有 API Key）"""
        return bool(self.api_key.strip())


class AIConfigManager:
    """AI 配置持久化管理"""

    @staticmethod
    def get_config_path() -> str:
        """获取配置文件路径"""
        return _CONFIG_FILE

    @staticmethod
    def load() -> AIConfig:
        """从文件加载配置，不存在则返回默认配置"""
        try:
            if os.path.exists(_CONFIG_FILE):
                with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return AIConfig(**{k: v for k, v in data.items() if k in AIConfig.__dataclass_fields__})
        except Exception as e:
            logger.warning(f"加载 AI 配置失败: {e}")
        return AIConfig()

    @staticmethod
    def save(config: AIConfig) -> bool:
        """保存配置到文件"""
        try:
            os.makedirs(_CONFIG_DIR, exist_ok=True)
            data = asdict(config)
            with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("AI 配置已保存")
            return True
        except Exception as e:
            logger.error(f"保存 AI 配置失败: {e}")
            return False
