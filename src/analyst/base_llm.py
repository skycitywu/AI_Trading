"""LLM 抽象基类 — 支持多模型切换"""

from abc import ABC, abstractmethod


class BaseLLM(ABC):
    """LLM 客户端抽象基类"""

    @abstractmethod
    def chat(self, system_prompt: str, user_prompt: str) -> str:
        """发送消息并获取回复

        Args:
            system_prompt: 系统提示词 (角色设定)
            user_prompt: 用户提示词 (本次分析数据)
        Returns:
            LLM 的文本回复
        """
        ...
