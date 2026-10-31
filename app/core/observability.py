import os
import logging
from typing import Optional, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)


def setup_langsmith():
    """
    Initializes LangSmith tracing environment variables for LangChain and LangGraph.
    Enables automatic tracing, token accounting, and latency monitoring.
    """
    api_key = settings.LANGSMITH_API_KEY or os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY")
    tracing_enabled = settings.LANGSMITH_TRACING or os.environ.get("LANGSMITH_TRACING", "").lower() in ("true", "1") or os.environ.get("LANGCHAIN_TRACING_V2", "").lower() in ("true", "1")
    project = settings.LANGSMITH_PROJECT or os.environ.get("LANGSMITH_PROJECT") or os.environ.get("LANGCHAIN_PROJECT") or "socialix-agents-dev"
    endpoint = settings.LANGSMITH_ENDPOINT or os.environ.get("LANGSMITH_ENDPOINT") or "https://api.smith.langchain.com"

    if api_key and tracing_enabled:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = api_key
        os.environ["LANGSMITH_API_KEY"] = api_key
        os.environ["LANGCHAIN_PROJECT"] = project
        os.environ["LANGSMITH_PROJECT"] = project
        os.environ["LANGCHAIN_ENDPOINT"] = endpoint
        os.environ["LANGSMITH_ENDPOINT"] = endpoint
        logger.info(f"LangSmith Tracing ENABLED for project: '{project}' at {endpoint}")
    else:
        if not api_key:
            logger.info("LangSmith Tracing: No API key provided. Tracing remains local/disabled.")
        else:
            logger.info("LangSmith Tracing is disabled (LANGSMITH_TRACING=false).")


def record_langsmith_feedback(
    run_id: str,
    key: str,
    score: float,
    comment: Optional[str] = None,
    correction: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Sends human-in-the-loop feedback (approvals/rejections) directly to LangSmith
    to power continuous evaluation and prompt refinement.
    """
    api_key = settings.LANGSMITH_API_KEY or os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY")
    if not api_key:
        return False

    try:
        from langsmith import Client
        client = Client(api_key=api_key)
        client.create_feedback(
            run_id=run_id,
            key=key,
            score=score,
            comment=comment,
            correction=correction
        )
        logger.info(f"Sent LangSmith feedback for run {run_id}: key={key}, score={score}")
        return True
    except Exception as e:
        logger.warning(f"Could not send LangSmith feedback: {e}")
        return False
