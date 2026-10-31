import os
from typing import Optional, Literal
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


def get_llm(role: Literal["planner", "worker", "critic"] = "worker") -> BaseChatModel:
    """
    Factory to return Google Gemini model based on agent role:
    - 'planner': Gemini Pro for complex reasoning, multi-step planning, and intent parsing.
    - 'worker': Gemini Flash for fast generation, research synthesis, and scheduling.
    - 'critic': Gemini Pro or Flash for self-critique and brand voice compliance.
    """
    api_key = settings.GOOGLE_API_KEY or os.environ.get("GOOGLE_API_KEY")

    if role == "planner":
        model_name = settings.GEMINI_PRO_MODEL
        temperature = 0.2
    elif role == "critic":
        model_name = settings.GEMINI_PRO_MODEL
        temperature = 0.1
    else:  # worker
        model_name = settings.GEMINI_FLASH_MODEL
        temperature = 0.7

    if not api_key:
        logger.warning("GOOGLE_API_KEY is not set. Gemini API calls will fail unless configured in .env.")
        api_key = "dummy_key_set_in_env"

    return ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temperature,
        google_api_key=api_key,
        max_retries=3,
        timeout=60,
    )
