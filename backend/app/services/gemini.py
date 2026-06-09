from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import get_settings


_llm: ChatGoogleGenerativeAI | None = None


def get_gemini_llm() -> ChatGoogleGenerativeAI:
    global _llm
    if _llm is None:
        settings = get_settings()
        _llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=0.7,
        )
    return _llm
