"""
Chat Router - API Endpoints for Conversational AI

Provides:
- POST /chat - Send a message and get a response
- GET /chat/intents - List supported intents
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List

from app.schemas.chat import (
    ChatRequest, ChatResponse, IntentInfo, SupportedIntentsResponse
)
from app.services.chat_service import chat_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def send_chat_message(request: ChatRequest) -> ChatResponse:
    """
    Send a chat message and receive an AI-powered response.

    The chatbot will:
    1. Detect the intent of your message
    2. Fetch relevant data from appropriate sources
    3. Generate a natural language response

    **Example requests:**
    - "Is this area safe?" (safety query)
    - "What events are nearby?" (event search)
    - "Find restaurants near me" (POI search)

    **Request body:**
    - `message`: Your question or query (required)
    - `lat`: Latitude of current location (optional but recommended)
    - `lon`: Longitude of current location (optional but recommended)
    - `location_name`: Human-readable location name (optional)
    - `conversation_id`: ID to maintain conversation context (optional)

    **Response:**
    - `response`: The chatbot's answer
    - `intent`: Detected intent category
    - `confidence`: Confidence score (0-1)
    - `data_sources`: APIs used to generate the response
    - `actions`: Suggested frontend actions (e.g., show map layers)
    """
    try:
        logger.info(f"Chat request received: '{request.message[:50]}...'")

        response = await chat_service.process_message(request)

        logger.info(
            f"Chat response generated: intent={response.intent}, "
            f"confidence={response.confidence:.2f}, "
            f"time={response.processing_time_ms:.0f}ms"
        )

        return response

    except Exception as e:
        logger.error(f"Chat processing error: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Chat service temporarily unavailable: {str(e)}"
        )


@router.get("/chat/intents", response_model=SupportedIntentsResponse)
async def get_supported_intents() -> SupportedIntentsResponse:
    """
    List all supported chat intents with examples.

    Returns information about what types of queries the chatbot can handle,
    including example questions and data sources used for each intent type.

    Useful for:
    - Displaying help information to users
    - Building UI suggestions
    - Documentation purposes
    """
    intents = chat_service.get_supported_intents()

    return SupportedIntentsResponse(
        intents=intents,
        total_count=len(intents)
    )


@router.get("/chat/health")
async def chat_health_check() -> Dict[str, Any]:
    """
    Check the health of the chat service.

    Returns status of:
    - Intent detection system
    - LLM availability
    - Data service connections
    """
    from app.core.config import settings

    return {
        "status": "healthy",
        "llm_provider": settings.LLM_PROVIDER,
        "llm_available": settings.LLM_PROVIDER != "none",
        "intent_detector": "ready",
        "response_generator": "ready"
    }
