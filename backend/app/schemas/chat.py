"""
Chat Schemas for Conversational AI Interface

Defines Pydantic models for:
- Chat requests and responses
- Intent types and classifications
- Conversation messages and context
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class IntentType(str, Enum):
    """
    Supported user intent categories.

    Each intent maps to specific data sources and response strategies.
    """
    SAFETY_QUERY = "safety_query"      # "Is it safe?", "Crime rate?"
    EVENT_SEARCH = "event_search"      # "What's happening?", "Events nearby"
    POI_SEARCH = "poi_search"          # "Find restaurants", "Hotels near me"
    NEWS_QUERY = "news_query"          # "Recent news", "What's new?"
    COMPARISON = "comparison"          # "Compare A vs B", "Which is safer?"
    GENERAL_INFO = "general_info"      # "Tell me about X", "Overview"
    GREETING = "greeting"              # "Hello", "Hi"
    HELP = "help"                      # "What can you do?", "Help"
    UNKNOWN = "unknown"                # Fallback for unrecognized queries


class ChatMessage(BaseModel):
    """Single message in a conversation"""
    role: str = Field(
        ...,
        description="Message role: 'user' or 'assistant'"
    )
    content: str = Field(
        ...,
        description="Message text content"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Message timestamp"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "role": "user",
                "content": "Is this area safe?",
                "timestamp": "2026-01-05T10:30:00Z"
            }
        }


class ChatRequest(BaseModel):
    """
    Incoming chat request from frontend.

    Contains the user's message and optional location context.
    """
    message: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="User's message text"
    )
    lat: Optional[float] = Field(
        None,
        ge=-90,
        le=90,
        description="Latitude of current map location"
    )
    lon: Optional[float] = Field(
        None,
        ge=-180,
        le=180,
        description="Longitude of current map location"
    )
    conversation_id: Optional[str] = Field(
        None,
        description="Conversation ID for context continuity"
    )
    location_name: Optional[str] = Field(
        None,
        description="Human-readable location name if available"
    )
    context: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional context from frontend"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Is this area safe at night?",
                "lat": 51.5074,
                "lon": -0.1278,
                "location_name": "London",
                "conversation_id": "conv_abc123"
            }
        }


class ChatAction(BaseModel):
    """
    Action to be executed by frontend.

    Examples:
    - Show a specific layer on the map
    - Navigate to a location
    - Open a detail panel
    """
    type: str = Field(
        ...,
        description="Action type: 'show_layer', 'navigate', 'open_panel', etc."
    )
    target: Optional[str] = Field(
        None,
        description="Target of the action (layer name, coordinates, etc.)"
    )
    params: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional action parameters"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "type": "show_layer",
                "target": "crimes",
                "params": {"highlight": True}
            }
        }


class ChatResponse(BaseModel):
    """
    Response sent back to frontend.

    Contains the assistant's response, detected intent,
    data sources used, and any actions to execute.
    """
    response: str = Field(
        ...,
        description="Assistant's response message"
    )
    intent: IntentType = Field(
        ...,
        description="Detected user intent"
    )
    confidence: float = Field(
        ...,
        ge=0,
        le=1,
        description="Intent detection confidence (0-1)"
    )
    data_sources: List[str] = Field(
        default_factory=list,
        description="Data sources used for the response"
    )
    actions: List[ChatAction] = Field(
        default_factory=list,
        description="Actions for frontend to execute"
    )
    conversation_id: str = Field(
        ...,
        description="Conversation ID for context continuity"
    )
    processing_time_ms: Optional[float] = Field(
        None,
        description="Response processing time in milliseconds"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "response": "Based on recent data, this area has a safety score of 0.72/1.0...",
                "intent": "safety_query",
                "confidence": 0.85,
                "data_sources": ["UK Police API", "Safety Scoring Model"],
                "actions": [{"type": "show_layer", "target": "crimes"}],
                "conversation_id": "conv_abc123",
                "processing_time_ms": 1250.5
            }
        }


class ConversationHistory(BaseModel):
    """
    Conversation history for context management.

    Stores recent messages for multi-turn conversations.
    """
    conversation_id: str
    messages: List[ChatMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    location_context: Optional[Dict[str, Any]] = Field(default_factory=dict)

    def add_message(self, role: str, content: str):
        """Add a message to the conversation"""
        self.messages.append(ChatMessage(role=role, content=content))
        self.last_updated = datetime.utcnow()

    def get_recent_messages(self, limit: int = 10) -> List[ChatMessage]:
        """Get the most recent messages"""
        return self.messages[-limit:] if self.messages else []


class IntentInfo(BaseModel):
    """Information about a supported intent"""
    intent: IntentType
    description: str
    example_queries: List[str]
    data_sources: List[str]


class SupportedIntentsResponse(BaseModel):
    """Response listing all supported intents"""
    intents: List[IntentInfo]
    total_count: int
