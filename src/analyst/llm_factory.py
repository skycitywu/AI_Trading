"""LLM 工厂 — 根据配置创建对应的 LLM 实例"""

from config.settings import settings
from src.analyst.base_llm import BaseLLM


def create_llm() -> BaseLLM:
    provider = settings.llm_provider.lower()
    if provider == "claude":
        from src.analyst.claude_client import ClaudeLLM
        return ClaudeLLM()
    elif provider == "zhipu":
        from src.analyst.zhipu_client import ZhipuLLM
        return ZhipuLLM()
    elif provider == "gemini":
        from src.analyst.gemini_client import GeminiLLM
        return GeminiLLM()
    else:
        raise ValueError(f"不支持的 LLM provider: {provider}")
