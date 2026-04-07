"""智谱 GLM 实现"""

import logging

from zhipuai import ZhipuAI

from config.settings import settings
from src.analyst.base_llm import BaseLLM

logger = logging.getLogger(__name__)


class ZhipuLLM(BaseLLM):
    def __init__(self):
        self.client = ZhipuAI(api_key=settings.zhipu_api_key)
        self.model = "glm-4-plus"

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"智谱 API 调用失败: {e}")
            raise
