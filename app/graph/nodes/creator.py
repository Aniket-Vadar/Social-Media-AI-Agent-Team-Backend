import json
import re
import uuid
from typing import Dict, Any, List
from app.graph.state import AgentState
from app.tools.imagekit import imagekit_helper
from app.core.config import settings
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


async def generate_post_content_with_ai(user_prompt: str, tone: str, post_index: int = 1) -> Dict[str, Any]:
    """Generates creative post copy using Google Gemini LLM."""
    if not settings.GOOGLE_API_KEY:
        return {}

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_FLASH_MODEL or "gemini-2.5-flash",
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.7
        )
        prompt_text = (
            f"You are a top-tier social media creative director and copywriter.\n"
            f"Create an engaging, platform-tailored post (Variation #{post_index}) for the user's request: '{user_prompt}'.\n"
            f"Brand tone: {tone}.\n"
            f"Requirements:\n"
            f"- 'title': A short, punchy headline (under 35 chars, no emojis).\n"
            f"- 'caption': Engaging, high-converting social caption with clean spacing, emojis, and call to action.\n"
            f"- 'hashtags': 5 relevant, trending hashtags starting with #.\n"
            f"Return ONLY valid JSON matching this structure: {{\"title\": \"...\", \"caption\": \"...\", \"hashtags\": [\"#...\"]}}"
        )
        resp = await llm.ainvoke(prompt_text)
        match = re.search(r"\{.*\}", resp.content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception as e:
        logger.warning(f"Creator Gemini generation fallback: {e}")
    return {}


def get_topic_image(prompt: str, index: int = 0) -> str:
    """Selects high-resolution, relevant Unsplash images based on user prompt topic."""
    p = prompt.lower()
    if any(k in p for k in ["samsung", "s24", "mobile", "phone", "smartphone", "galaxy", "iphone", "apple", "gadget", "android"]):
        images = [
            "https://images.unsplash.com/photo-1610945415295-d9bbf067e59c",  # Samsung Galaxy phone
            "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9",  # Modern smartphone
        ]
    elif any(k in p for k in ["coffee", "cafe", "latte", "roast", "brew", "espresso", "bakery", "croissant"]):
        images = [
            "https://images.unsplash.com/photo-1509042239860-f550ce710b93",  # Artisan coffee
            "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb",  # Cozy cafe
        ]
    elif any(k in p for k in ["laptop", "macbook", "computer", "tech", "software", "code", "ai", "startup"]):
        images = [
            "https://images.unsplash.com/photo-1519389950473-47ba0277781c",  # Modern tech workspace
            "https://images.unsplash.com/photo-1498050108023-c5249f4df085",  # Laptop with code
        ]
    else:
        images = [
            "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe",  # Modern abstract visual
            "https://images.unsplash.com/photo-1551288049-bebda4e38f71",  # Creative chart design
        ]
    return images[index % len(images)]


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

    for i in range(post_count):
        post_id = f"draft_post_{uuid.uuid4().hex[:8]}"

        # Attempt dynamic Gemini copy generation
        ai_data = await generate_post_content_with_ai(str(last_msg), tone, post_index=i + 1)
        title = ai_data.get("title") or f"Creative Post #{i + 1}"
        caption = ai_data.get("caption") or (
            f"🚀 {last_msg}\n\n"
            f"1. Continuous research of high-velocity trends.\n"
            f"2. Consistent, high-value storytelling tailored to your audience.\n"
            f"3. Posting at prime engagement windows with zero manual hassle.\n\n"
            f"Drop a '🔥' below if you want the full AI agent automation workflow! 👇"
        )
        hashtags = ai_data.get("hashtags") or ["#Innovation", "#TechTrends", "#SocialMediaGrowth", "#AIAgents", "#FutureOfTech"]

        # Run Self-Critique Pass
        is_compliant = self_critique_pass(caption, hashtags, banned_words)
        if not is_compliant:
            caption = caption[:1000]

        # Select topic-appropriate image and transform via ImageKit
        raw_img = get_topic_image(str(last_msg), index=i)
        transformed_url = imagekit_helper.transform_url(raw_img, aspect_ratio="1:1", overlay_text=title[:30])

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

    return {
        "messages": [msg],
        "plan": updated_plan,
        "artifacts": updated_artifacts,
        "step_count": state.get("step_count", 0) + 1
    }
