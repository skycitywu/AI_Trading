"""Anthropic Claude 实现"""

import logging

import anthropic

from config.settings import settings
from src.analyst.base_llm import BaseLLM

logger = logging.getLogger(__name__)


class ClaudeLLM(BaseLLM):
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-20250514"

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude API 调用失败: {e}")
            raise
