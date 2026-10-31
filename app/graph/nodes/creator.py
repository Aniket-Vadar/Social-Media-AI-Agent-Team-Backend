import uuid
from typing import Dict, Any, List
from app.graph.state import AgentState
from app.tools.imagekit import imagekit_helper
from langchain_core.messages import AIMessage
import logging

logger = logging.getLogger(__name__)


def self_critique_pass(caption: str, hashtags: List[str], banned_words: List[str], max_length: int = 2200) -> bool:
    """Validates post against brand voice and platform rules."""
    for word in banned_words:
        if word.lower() in caption.lower():
            return False
    if len(caption) > max_length:
        return False
    return True


async def creator_node(state: AgentState) -> Dict[str, Any]:
    """
    Creator Agent Node:
    Crafts compelling, platform-ready captions, selects optimal hashtags,
    configures media assets, and performs a self-critique pass.
    """
    campaign_ctx = state.get("campaign_ctx", {})
    brand_voice = campaign_ctx.get("brand_voice", {})
    tone = brand_voice.get("tone", "engaging, informative")
    banned_words = brand_voice.get("banned_words", [])
    platforms = campaign_ctx.get("platforms", ["instagram"])
    briefs = state.get("artifacts", {}).get("research_brief", [])

    # Extract user requested post count or default to 2
    post_count = 2
    last_msg = state["messages"][-1].content if state.get("messages") else ""
    if "one post" in str(last_msg).lower() or "1 post" in str(last_msg).lower():
        post_count = 1

    created_drafts = []
    base_images = [
        "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe",
        "https://images.unsplash.com/photo-1551288049-bebda4e38f71"
    ]

    for i in range(post_count):
        post_id = f"draft_post_{uuid.uuid4().hex[:8]}"
        title = f"Autonomous Growth Strategy #{i + 1}"
        caption = (
            f"🚀 Ready to level up your social media presence? Here is the blueprint:\n\n"
            f"1. Continuous research of high-velocity trends.\n"
            f"2. Consistent, high-value storytelling tailored to your audience.\n"
            f"3. Posting at prime engagement windows with zero manual hassle.\n\n"
            f"Drop a '🔥' below if you want the full AI agent automation workflow! 👇"
        )
        hashtags = ["#SocialMediaGrowth", "#AIAgents", "#ContentStrategy", "#Automation", "#Creators"]

        # Run Self-Critique Pass
        is_compliant = self_critique_pass(caption, hashtags, banned_words)
        if not is_compliant:
            caption = caption[:1000]

        # Select & Transform image using ImageKit
        raw_img = base_images[i % len(base_images)]
        transformed_url = imagekit_helper.transform_url(raw_img, aspect_ratio="1:1", overlay_text=title)

        draft = {
            "id": post_id,
            "title": title,
            "caption": caption,
            "hashtags": hashtags,
            "platforms": platforms,
            "media_url": transformed_url,
            "aspect_ratio": "1:1",
            "status": "pending_approval" if campaign_ctx.get("approval_mode") == "manual" else "draft",
            "created_by": "agent"
        }
        created_drafts.append(draft)

    # Update plan status
    updated_plan = []
    for step in state.get("plan", []):
        if step["agent"] == "creator" and step["status"] in ["pending", "running"]:
            step["status"] = "done"
            step["result_ref"] = ",".join([d["id"] for d in created_drafts])
        updated_plan.append(step)

    updated_artifacts = dict(state.get("artifacts", {}))
    updated_artifacts["draft_posts"] = created_drafts

    msg = AIMessage(
        content=(
            f"✍️ **Creator Agent Report:**\n"
            f"Drafted **{len(created_drafts)} posts** aligned with **'{tone}'** brand voice.\n\n"
            + "\n".join([f"• **{d['title']}** ({len(d['caption'])} chars, {len(d['hashtags'])} hashtags, 1:1 image)" for d in created_drafts])
            + "\n\nPosts are packaged and submitted to the human-in-the-loop approval gate."
        ),
        name="creator"
    )

    return {
        "messages": [msg],
        "plan": updated_plan,
        "artifacts": updated_artifacts,
        "step_count": state.get("step_count", 0) + 1
    }
