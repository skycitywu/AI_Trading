"""Google Gemini 实现"""

import logging

from google import genai
from google.genai import types

from config.settings import settings
from src.analyst.base_llm import BaseLLM

logger = logging.getLogger(__name__)


class GeminiLLM(BaseLLM):
    def __init__(self):
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY 未设置")
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = settings.llm_model or "gemini-3-flash-preview"

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=types.GenerateContentConfig(system_instruction=system_prompt),
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini API 调用失败 (model={self.model}): {e}")
            raise
