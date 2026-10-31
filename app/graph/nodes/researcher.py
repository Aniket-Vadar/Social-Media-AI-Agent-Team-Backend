from typing import Dict, Any
from app.graph.state import AgentState
from app.tools.web_search import search_trending_topics
from langchain_core.messages import AIMessage
import logging

logger = logging.getLogger(__name__)


async def researcher_node(state: AgentState) -> Dict[str, Any]:
    """
    Researcher Agent Node:
    Investigates current trends, competitor angles, and relevant hooks based on the campaign goal.
    Produces a structured ResearchBrief.
    """
    campaign_ctx = state.get("campaign_ctx", {})
    goal = campaign_ctx.get("goal", "Tech & Social Media Growth")
    user_prompt = state["messages"][-1].content if state.get("messages") else ""

    logger.info(f"Researcher Agent running for goal: {goal}")
    briefs = await search_trending_topics(niche=goal, query=str(user_prompt))

    # Mark current step done in plan
    updated_plan = []
    for step in state.get("plan", []):
        if step["agent"] == "researcher" and step["status"] in ["pending", "running"]:
            step["status"] = "done"
            step["result_ref"] = "research_briefs_1"
        updated_plan.append(step)

    updated_artifacts = dict(state.get("artifacts", {}))
    updated_artifacts["research_brief"] = briefs

    msg = AIMessage(
        content=(
            f"🔍 **Research Agent Report:**\n"
            f"Found {len(briefs)} high-potential trending angles for **{goal}**.\n\n"
            + "\n".join([f"• **{b['title']}** (Virality Score: {int(b['relevance_score']*100)}%)" for b in briefs])
            + "\n\nHanding off insights to Creator Agent."
        ),
        name="researcher"
    )

    return {
        "messages": [msg],
        "plan": updated_plan,
        "artifacts": updated_artifacts,
        "step_count": state.get("step_count", 0) + 1
    }
