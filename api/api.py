from fastapi import APIRouter

from api.routers import conversations, events, review

api_router = APIRouter(prefix="/api")

api_router.include_router(conversations.router, prefix="/conversations", tags=["Conversations"])
api_router.include_router(events.router, prefix="/events", tags=["Game Events"])
api_router.include_router(review.router, prefix="/review", tags=["Review Sessions"])
