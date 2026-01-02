"""
Chat schemas for request/response models and UI actions
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any, Union, Annotated
from typing_extensions import Literal
from datetime import datetime
import re


# --- Request Models ---

class MapCenter(BaseModel):
    """Map center coordinates"""
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lng: float = Field(..., ge=-180, le=180, description="Longitude")


class MapContext(BaseModel):
    """Current map viewport state"""
    center: MapCenter = Field(..., description="Current map center")
    bbox: List[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Bounding box [west, south, east, north]"
    )
    zoom: int = Field(..., ge=1, le=20, description="Current zoom level")

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, v: List[float]) -> List[float]:
        west, south, east, north = v
        if not (-180 <= west <= 180):
            raise ValueError(f"west ({west}) must be between -180 and 180")
        if not (-180 <= east <= 180):
            raise ValueError(f"east ({east}) must be between -180 and 180")
        if not (-90 <= south <= 90):
            raise ValueError(f"south ({south}) must be between -90 and 90")
        if not (-90 <= north <= 90):
            raise ValueError(f"north ({north}) must be between -90 and 90")
        if south > north:
            raise ValueError(f"south ({south}) must be <= north ({north})")
        return v


class TimeContext(BaseModel):
    """Optional time range filter"""
    from_time: Optional[str] = Field(None, alias="from", description="Start time ISO 8601")
    to_time: Optional[str] = Field(None, alias="to", description="End time ISO 8601")

    class Config:
        populate_by_name = True


class FiltersContext(BaseModel):
    """Optional filters for data queries"""
    category: Optional[str] = Field(None, max_length=100, description="Category filter")
    tags: Optional[List[str]] = Field(None, description="Tag filters")
    budget: Optional[Literal["low", "medium", "high"]] = Field(None, description="Budget level")
    price_min: Optional[float] = Field(None, ge=0, description="Minimum price")
    price_max: Optional[float] = Field(None, ge=0, description="Maximum price")
    types: Optional[List[str]] = Field(None, description="Data types to include")

    @model_validator(mode="after")
    def validate_price_range(self):
        if self.price_min is not None and self.price_max is not None:
            if self.price_min > self.price_max:
                raise ValueError("price_min must be <= price_max")
        return self


class ChatContext(BaseModel):
    """Combined context for chat request"""
    map: MapContext = Field(..., description="Current map state")
    time: Optional[TimeContext] = Field(None, description="Time range filter")
    filters: Optional[FiltersContext] = Field(None, description="Active filters")


class ChatRequest(BaseModel):
    """Chat request from frontend"""
    message: str = Field(..., min_length=1, max_length=2000, description="User message")
    context: ChatContext = Field(..., description="Current UI context")
    conversation_id: Optional[str] = Field(None, max_length=100, description="Conversation ID for continuity")


# --- UI Action Payload Models ---

class SetViewportPayload(BaseModel):
    """Payload for SET_VIEWPORT action - navigate to specific location"""
    lat: float = Field(..., ge=-90, le=90, description="Target latitude")
    lng: float = Field(..., ge=-180, le=180, description="Target longitude")
    zoom: Optional[int] = Field(None, ge=1, le=20, description="Target zoom level")
    animate: bool = Field(True, description="Whether to animate the transition")


class FitBoundsPayload(BaseModel):
    """Payload for FIT_BOUNDS action - fit map to show specified bounds"""
    bbox: List[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Bounding box [west, south, east, north]"
    )
    padding: int = Field(50, ge=0, le=200, description="Padding in pixels")
    max_zoom: Optional[int] = Field(None, ge=1, le=20, description="Maximum zoom level")

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, v: List[float]) -> List[float]:
        west, south, east, north = v
        if not (-180 <= west <= 180):
            raise ValueError(f"west ({west}) must be between -180 and 180")
        if not (-180 <= east <= 180):
            raise ValueError(f"east ({east}) must be between -180 and 180")
        if not (-90 <= south <= 90):
            raise ValueError(f"south ({south}) must be between -90 and 90")
        if not (-90 <= north <= 90):
            raise ValueError(f"north ({north}) must be between -90 and 90")
        if south > north:
            raise ValueError(f"south ({south}) must be <= north ({north})")
        return v


class SetFiltersPayload(BaseModel):
    """Payload for SET_FILTERS action - update active filters"""
    category: Optional[str] = Field(None, max_length=100, description="Category filter")
    tags: Optional[List[str]] = Field(None, description="Tag filters")
    budget: Optional[Literal["low", "medium", "high"]] = Field(None, description="Budget level")
    price_min: Optional[float] = Field(None, ge=0, description="Minimum price")
    price_max: Optional[float] = Field(None, ge=0, description="Maximum price")
    merge: bool = Field(False, description="Merge with existing filters instead of replace")


class HighlightResultsPayload(BaseModel):
    """Payload for HIGHLIGHT_RESULTS action - highlight specific items on map"""
    ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Item IDs to highlight"
    )
    scroll_to_first: bool = Field(False, description="Scroll list to first highlighted item")

    @field_validator("ids")
    @classmethod
    def validate_ids(cls, v: List[str]) -> List[str]:
        id_pattern = re.compile(r'^[a-zA-Z0-9_-]+$')
        for item_id in v:
            if not item_id or len(item_id) > 100:
                raise ValueError(f"Invalid id: must be 1-100 characters")
            if not id_pattern.match(item_id):
                raise ValueError(f"Invalid id format: {item_id}. Use alphanumeric, dash, underscore only.")
        return v


class ClearHighlightsPayload(BaseModel):
    """Payload for CLEAR_HIGHLIGHTS action - remove all highlights"""
    pass


class RefreshDataPayload(BaseModel):
    """Payload for REFRESH_DATA action - refresh location data"""
    radius_km: float = Field(5.0, ge=0.1, le=50.0, description="Search radius in kilometers")
    types: Optional[List[Literal["crimes", "events", "news", "pois"]]] = Field(
        None,
        description="Data types to refresh (None = all)"
    )
    force: bool = Field(False, description="Bypass cache")


# --- Discriminated Union UI Actions ---

class SetViewportAction(BaseModel):
    """Navigate map to specific location"""
    type: Literal["SET_VIEWPORT"] = "SET_VIEWPORT"
    payload: SetViewportPayload


class FitBoundsAction(BaseModel):
    """Fit map to show specified bounds"""
    type: Literal["FIT_BOUNDS"] = "FIT_BOUNDS"
    payload: FitBoundsPayload


class SetFiltersAction(BaseModel):
    """Update active filters"""
    type: Literal["SET_FILTERS"] = "SET_FILTERS"
    payload: SetFiltersPayload


class HighlightResultsAction(BaseModel):
    """Highlight specific items on map"""
    type: Literal["HIGHLIGHT_RESULTS"] = "HIGHLIGHT_RESULTS"
    payload: HighlightResultsPayload


class ClearHighlightsAction(BaseModel):
    """Remove all highlights"""
    type: Literal["CLEAR_HIGHLIGHTS"] = "CLEAR_HIGHLIGHTS"
    payload: ClearHighlightsPayload = Field(default_factory=ClearHighlightsPayload)


class RefreshDataAction(BaseModel):
    """Refresh location data"""
    type: Literal["REFRESH_DATA"] = "REFRESH_DATA"
    payload: RefreshDataPayload = Field(default_factory=RefreshDataPayload)


# Discriminated union of all UI actions
UiAction = Annotated[
    Union[
        SetViewportAction,
        FitBoundsAction,
        SetFiltersAction,
        HighlightResultsAction,
        ClearHighlightsAction,
        RefreshDataAction,
    ],
    Field(discriminator="type")
]


# --- Response Models ---

class Citation(BaseModel):
    """Source citation for response"""
    id: str = Field(..., max_length=100, description="Source item ID")
    type: Literal["crime", "event", "news", "poi"] = Field(..., description="Source type")
    title: Optional[str] = Field(None, max_length=500, description="Source title")
    snippet: Optional[str] = Field(None, max_length=1000, description="Relevant snippet")


class MarkerData(BaseModel):
    """Marker to display on map"""
    id: str = Field(..., max_length=100, description="Marker ID")
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    type: Literal["crime", "event", "news", "poi"] = Field(..., description="Marker type")
    label: Optional[str] = Field(None, max_length=200, description="Marker label")
    highlighted: bool = Field(False, description="Whether to highlight this marker")


class CardData(BaseModel):
    """Info card to display"""
    id: str = Field(..., max_length=100, description="Card ID")
    type: Literal["crime", "event", "news", "poi", "summary"] = Field(..., description="Card type")
    title: str = Field(..., max_length=500, description="Card title")
    subtitle: Optional[str] = Field(None, max_length=300, description="Card subtitle")
    description: Optional[str] = Field(None, max_length=2000, description="Card description")
    image_url: Optional[str] = Field(None, max_length=1000, description="Card image URL")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class ChatResponse(BaseModel):
    """Chat response to frontend"""
    assistant_text: str = Field(..., description="Assistant response text")
    ui_actions: List[UiAction] = Field(default_factory=list, description="UI actions to execute")
    citations: Optional[List[Citation]] = Field(None, description="Source citations")
    markers: Optional[List[MarkerData]] = Field(None, description="Markers to display")
    cards: Optional[List[CardData]] = Field(None, description="Cards to render")
    conversation_id: Optional[str] = Field(None, max_length=100, description="Conversation ID")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
