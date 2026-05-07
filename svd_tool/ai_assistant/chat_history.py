"""
聊天记录模型
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger("AIAssistant.ChatHistory")


@dataclass
class ChatMessage:
    """聊天消息"""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    actions: List[Dict[str, Any]] = field(default_factory=list)

    def to_api_dict(self) -> Dict[str, str]:
        """转换为 API 请求格式"""
        return {"role": self.role, "content": self.content}


class ChatHistory:
    """会话聊天记录管理"""

    def __init__(self, max_messages: int = 50):
        self._messages: List[ChatMessage] = []
        self._max_messages = max_messages

    def add_message(self, role: str, content: str, actions: Optional[List[Dict]] = None) -> ChatMessage:
        """添加消息"""
        msg = ChatMessage(
            role=role,
            content=content,
            timestamp=datetime.now(),
            actions=actions or []
        )
        self._messages.append(msg)

        # 超过上限时移除最早的消息（保留系统消息）
        while len(self._messages) > self._max_messages:
            # 找到最早的非系统消息移除
            for i, m in enumerate(self._messages):
                if m.role != "system":
                    self._messages.pop(i)
                    break
            else:
                break

        return msg

    def get_messages_for_api(self) -> List[Dict[str, str]]:
        """获取用于 API 调用的消息列表"""
        return [m.to_api_dict() for m in self._messages]

    def get_all_messages(self) -> List[ChatMessage]:
        """获取所有消息"""
        return list(self._messages)

    def clear(self):
        """清空聊天记录"""
        self._messages.clear()

    def __len__(self) -> int:
        return len(self._messages)
