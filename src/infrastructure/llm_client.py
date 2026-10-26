import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


def get_llm(temperature: float = 0.0, model: str | None = None) -> ChatOpenAI:
    """
    Фабрика для создания LLM-клиента через OpenRouter (или локальный vLLM).
    Совместима с OpenAI API стандартом.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("Не задан OPENROUTER_API_KEY в переменных окружения (.env)")

    model_name = model or os.getenv("OPENROUTER_MODEL", "OPENROUTER_MODEL")

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        temperature=temperature,
        max_retries=2,
    )
