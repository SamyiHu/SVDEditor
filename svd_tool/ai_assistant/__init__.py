"""
AI 助手模块
提供自然语言交互式 SVD 数据操作能力

此模块为独立模块，依赖 openai 或 anthropic 库（可选）。
未安装时不影响主程序其他功能。
"""

from .config import AIConfig, AIConfigManager


def create_ai_assistant(coordinator, main_window):
    """创建 AI 助手控制器（工厂函数）

    Args:
        coordinator: 中央协调器
        main_window: 主窗口实例

    Returns:
        AIAssistantController 实例
    """
    from .controller import AIAssistantController
    return AIAssistantController(coordinator, main_window)
