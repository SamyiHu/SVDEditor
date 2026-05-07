"""
AI 助手配置管理
"""
import json
import os
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional


logger = logging.getLogger("AIAssistant.Config")

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
    request_timeout: int = 60

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
