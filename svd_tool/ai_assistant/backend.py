"""
AI 后端抽象层
支持 OpenAI 兼容协议 和 Anthropic Claude API
"""
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Iterator, Optional

from .config import AIConfig

logger = logging.getLogger("AIAssistant.Backend")


class AIBackend(ABC):
    """AI 后端抽象接口"""

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], config: AIConfig) -> str:
        """同步聊天，返回完整响应文本"""
        ...

    @abstractmethod
    def chat_stream(self, messages: List[Dict[str, str]], config: AIConfig) -> Iterator[str]:
        """流式聊天，逐块返回响应文本"""
        ...


class OpenAICompatibleBackend(AIBackend):
    """OpenAI 兼容协议后端（支持 OpenAI、DeepSeek、Ollama 等）"""

    def _get_client(self, config: AIConfig):
        """懒加载 openai 客户端"""
        try:
            import openai
        except ImportError:
            raise ImportError(
                "未安装 openai 库。请运行: pip install openai"
            )
        return openai.OpenAI(
            api_key=config.api_key,
            base_url=config.api_base_url,
            timeout=config.request_timeout,
        )

    def chat(self, messages: List[Dict[str, str]], config: AIConfig) -> str:
        """同步聊天"""
        client = self._get_client(config)
        response = client.chat.completions.create(
            model=config.model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
        return response.choices[0].message.content or ""

    def chat_stream(self, messages: List[Dict[str, str]], config: AIConfig) -> Iterator[str]:
        """流式聊天"""
        client = self._get_client(config)
        stream = client.chat.completions.create(
            model=config.model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content


class AnthropicBackend(AIBackend):
    """Anthropic Claude API 后端"""

    def _get_client(self, config: AIConfig):
        """懒加载 anthropic 客户端"""
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "未安装 anthropic 库。请运行: pip install anthropic"
            )
        return anthropic.Anthropic(
            api_key=config.api_key,
            base_url=config.api_base_url if config.api_base_url != "https://api.openai.com/v1" else None,
            timeout=config.request_timeout,
        )

    def chat(self, messages: List[Dict[str, str]], config: AIConfig) -> str:
        """同步聊天"""
        client = self._get_client(config)
        # 分离 system 消息
        system_msg = ""
        api_messages = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                api_messages.append(m)

        response = client.messages.create(
            model=config.model,
            max_tokens=config.max_tokens,
            system=system_msg if system_msg else anthropic.NOT_GIVEN,
            messages=api_messages,
        )
        return response.content[0].text if response.content else ""

    def chat_stream(self, messages: List[Dict[str, str]], config: AIConfig) -> Iterator[str]:
        """流式聊天"""
        client = self._get_client(config)
        # 分离 system 消息
        system_msg = ""
        api_messages = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                api_messages.append(m)

        with client.messages.stream(
            model=config.model,
            max_tokens=config.max_tokens,
            system=system_msg if system_msg else anthropic.NOT_GIVEN,
            messages=api_messages,
        ) as stream:
            for text in stream.text_stream:
                yield text


def create_backend(api_type: str) -> AIBackend:
    """根据 API 类型创建后端实例

    Args:
        api_type: "openai" 或 "anthropic"

    Returns:
        AIBackend 实例
    """
    if api_type == "anthropic":
        return AnthropicBackend()
    return OpenAICompatibleBackend()
