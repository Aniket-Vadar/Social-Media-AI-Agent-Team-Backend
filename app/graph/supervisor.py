import uuid
from typing import Dict, Any, List, Optional
from app.graph.state import AgentState, PlanStep
from langchain_core.messages import AIMessage, HumanMessage
import logging

logger = logging.getLogger(__name__)


def classify_intent(message: str) -> str:
    """Classifies user intent from natural language input."""
    msg = message.lower()
    if any(k in msg for k in ["post", "create", "draft", "write", "instagram", "linkedin", "caption"]):
        return "create_content"
    if any(k in msg for k in ["trend", "research", "competitor", "topic", "hook"]):
        return "research"
    if any(k in msg for k in ["schedule", "calendar", "publish", "time"]):
        return "schedule"
    if any(k in msg for k in ["analytics", "report", "growth", "performance", "metrics"]):
        return "analyze"
    return "chitchat"


def generate_plan(intent: str, message: str) -> List[PlanStep]:
    """Generates a structured execution plan based on user intent."""
    if intent == "create_content":
        return [
            {
                "id": "step_1",
                "agent": "researcher",
                "instruction": f"Research trending angles and virality hooks for: '{message}'",
                "depends_on": [],
                "status": "pending",
                "result_ref": None
            },
            {
                "id": "step_2",
                "agent": "creator",
                "instruction": "Craft platform-tailored caption, hashtags, and apply ImageKit visual presets",
                "depends_on": ["step_1"],
                "status": "pending",
                "result_ref": None
            },
            {
                "id": "step_3",
                "agent": "scheduler",
                "instruction": "Calculate best engagement time slots and schedule with Blotato",
                "depends_on": ["step_2"],
                "status": "pending",
                "result_ref": None
            }
        ]
    elif intent == "research":
        return [
            {
                "id": "step_1",
                "agent": "researcher",
                "instruction": f"Perform comprehensive trend research for: '{message}'",
                "depends_on": [],
                "status": "pending",
                "result_ref": None
            }
        ]
    elif intent == "analyze":
        return [
            {
                "id": "step_1",
                "agent": "analytics",
                "instruction": "Compute deterministic weekly performance KPIs and derive strategic recommendations",
                "depends_on": [],
                "status": "pending",
                "result_ref": None
            }
        ]
    else:
        return []


async def supervisor_node(state: AgentState) -> Dict[str, Any]:
    """
    Master Agent (Supervisor):
    - Parses request and establishes structured plan if not already created.
    - Determines the next executable worker agent.
    - Synthesizes final deliverables when execution concludes.
    """
    plan = list(state.get("plan", []))
    last_msg = state["messages"][-1].content if state.get("messages") else ""

    # 1. If no plan exists, initialize plan based on classified intent
    if not plan:
        intent = classify_intent(str(last_msg))
        if intent == "chitchat":
            response = AIMessage(
                content="Hello! I'm your Master Agent at Socialix. I coordinate your Researcher, Creator, Scheduler, and Analytics agents. What would you like us to achieve today? (e.g. 'Create 2 Instagram posts about our new AI features')",
                name="master"
            )
            return {"messages": [response], "next": "__end__"}

        plan = generate_plan(intent, str(last_msg))
        logger.info(f"Master Agent created plan with {len(plan)} steps for intent '{intent}'")
        intro_msg = AIMessage(
            content=(
                f"🎯 **Master Agent Plan Initialized:**\n"
                f"I've mapped out a **{len(plan)}-step workflow** with your team:\n\n"
                + "\n".join([f"**Step {i+1} ({s['agent'].title()}):** {s['instruction']}" for i, s in enumerate(plan)])
                + "\n\nBeginning execution with **Researcher Agent** now..."
            ),
            name="master"
        )
        return {
            "plan": plan,
            "messages": [intro_msg],
            "next": "supervisor",
            "step_count": state.get("step_count", 0) + 1
        }

    # 2. Find next runnable step
    done_ids = {s["id"] for s in plan if s["status"] == "done"}
    next_step: Optional[PlanStep] = None

    for step in plan:
        if step["status"] == "pending":
            deps_met = all(dep in done_ids for dep in step.get("depends_on", []))
            if deps_met:
                next_step = step
                break

    if next_step is not None:
        # Mark as running and route to worker
        for s in plan:
            if s["id"] == next_step["id"]:
                s["status"] = "running"
        return {
            "plan": plan,
            "next": next_step["agent"],
            "step_count": state.get("step_count", 0) + 1
        }

    # 3. All steps completed -> Synthesize and finalize
    artifacts = state.get("artifacts", {})
    drafts = artifacts.get("draft_posts", [])
    scheduled = artifacts.get("scheduled_posts", [])

    summary_text = (
        f"✅ **Mission Completed!** All plan objectives executed successfully.\n\n"
    )
    if scheduled:
        summary_text += f"🚀 **{len(scheduled)} posts** have been verified and scheduled across your accounts. You can inspect them anytime on the **Posts** or **Calendar** tab.\n"
    elif drafts:
        summary_text += f"📝 **{len(drafts)} drafts** generated and ready in your workspace for review.\n"

    final_msg = AIMessage(content=summary_text, name="master")
    return {
        "messages": [final_msg],
        "next": "__end__",
        "step_count": state.get("step_count", 0) + 1
    }
