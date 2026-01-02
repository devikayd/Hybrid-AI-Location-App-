"""
Chat router for conversational Q&A with location context
"""

import logging
from fastapi import APIRouter, HTTPException

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import chat_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Process a chat message with location context.

    Accepts a user message along with current map context (center, bbox, zoom)
    and returns an AI-generated response with optional UI actions.

    UI Actions can include:
    - SET_VIEWPORT: Navigate the map to a specific location
    - FIT_BOUNDS: Fit the map to show a specific area
    - HIGHLIGHT_RESULTS: Highlight specific items on the map
    - CLEAR_HIGHLIGHTS: Remove all highlights
    - REFRESH_DATA: Refresh location data
    - SET_FILTERS: Update active filters
    """
    try:
        logger.info(f"Chat request received: {request.message[:50]}...")

        response = await chat_service.process_chat(request)

        logger.info(f"Chat response generated with {len(response.ui_actions)} actions")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Chat service temporarily unavailable: {str(e)}"
        )
