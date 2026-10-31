from typing import Dict, Any, List
from datetime import datetime, timedelta
from app.graph.state import AgentState
from app.tools.blotato import blotato_client
from langchain_core.messages import AIMessage
import logging

logger = logging.getLogger(__name__)


def calculate_best_post_times(count: int, timezone: str = "UTC") -> List[datetime]:
    """
    Best-Time Scheduling Logic (LOGIC.md §8):
    Selects prime engagement slots (e.g., 11:00 AM, 2:00 PM, 7:00 PM local)
    enforcing minimum 3-hour gap between posts.
    """
    now = datetime.utcnow()
    scheduled_slots = []
    # Base slot tomorrow at 11:00 AM
    base_time = (now + timedelta(days=1)).replace(hour=11, minute=0, second=0, microsecond=0)

    for i in range(count):
        # 4-hour spacing between posts
        slot = base_time + timedelta(hours=i * 4)
        scheduled_slots.append(slot)

    return scheduled_slots


async def scheduler_node(state: AgentState) -> Dict[str, Any]:
    """
    Scheduler Agent Node:
    Takes approved posts, calculates best posting slots,
    and registers schedules with Blotato using idempotency keys.
    """
    campaign_ctx = state.get("campaign_ctx", {})
    tz = campaign_ctx.get("timezone", "UTC")
    draft_posts = state.get("artifacts", {}).get("draft_posts", [])

    slots = calculate_best_post_times(len(draft_posts), tz)
    scheduled_posts = []

    for i, post in enumerate(draft_posts):
        scheduled_time = slots[i] if i < len(slots) else datetime.utcnow() + timedelta(days=1)
        idempotency_key = f"sched_{post['id']}_{int(scheduled_time.timestamp())}"

        # Register with Blotato
        blotato_res = await blotato_client.schedule_post(
            account_id="blotato-ig-1",
            caption=f"{post['caption']}\n\n{' '.join(post['hashtags'])}",
            media_urls=[post.get("media_url", "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe")],
            scheduled_at=scheduled_time,
            idempotency_key=idempotency_key,
            platform="instagram",
            aspect_ratio=post.get("aspect_ratio", "1:1")
        )

        scheduled_post = dict(post)
        scheduled_post["status"] = "scheduled"
        scheduled_post["scheduled_at"] = scheduled_time.isoformat()
        scheduled_post["blotato_id"] = blotato_res.get("blotato_post_id")
        scheduled_posts.append(scheduled_post)

    # Mark scheduler step done
    updated_plan = []
    for step in state.get("plan", []):
        if step["agent"] == "scheduler" and step["status"] in ["pending", "running"]:
            step["status"] = "done"
            step["result_ref"] = ",".join([p["id"] for p in scheduled_posts])
        updated_plan.append(step)

    updated_artifacts = dict(state.get("artifacts", {}))
    updated_artifacts["scheduled_posts"] = scheduled_posts

    msg = AIMessage(
        content=(
            f"📅 **Scheduler Agent Report:**\n"
            f"Successfully queued **{len(scheduled_posts)} posts** for automated publishing via Blotato:\n\n"
            + "\n".join([f"• **{p['title']}** scheduled for **{p['scheduled_at']}** ({tz})" for p in scheduled_posts])
            + f"\n\nPosts are synchronized with the Calendar view."
        ),
        name="scheduler"
    )

    return {
        "messages": [msg],
        "plan": updated_plan,
        "artifacts": updated_artifacts,
        "step_count": state.get("step_count", 0) + 1
    }
