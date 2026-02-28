"""
Review router — adaptive review session generation.

Unity polls this endpoint every 15 active gameplay minutes.
The ReviewScheduler checks if review should be triggered and generates
a dynamic exercise session based on the player's mistake history.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from dataclasses import asdict

from api.dependency import ReviewSchedulerDep

router = APIRouter()


class ReviewCheckRequest(BaseModel):
    player_id: str
    active_minutes: int


@router.post("/check")
async def check_review(body: ReviewCheckRequest, review_scheduler: ReviewSchedulerDep):
    """
    Unity calls this after every 15 minutes of active play.
    Returns whether a review session should be triggered and the session data if so.
    """
    should_trigger = await review_scheduler.should_trigger_review(
        player_id=body.player_id,
        active_minutes=body.active_minutes,
    )

    if not should_trigger:
        return {"trigger_review": False}

    session = await review_scheduler.generate_review_session(body.player_id)
    return {
        "trigger_review": True,
        "session": asdict(session),
    }


@router.post("/{player_id}/generate")
async def generate_review(player_id: str, review_scheduler: ReviewSchedulerDep):
    """Force-generate a review session for a player (for testing / manual triggers)."""
    session = await review_scheduler.generate_review_session(player_id)
    return asdict(session)
