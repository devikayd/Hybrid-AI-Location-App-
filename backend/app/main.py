from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import logging
import os
import time
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.core.config import settings
from app.core.database import init_db
from app.core.redis import init_redis
from app.routers import health as status, geocode, crime, events, news, pois, summary, scoring, data_collection, data_cleaning, feature_engineering, model_training, location_data, user_interaction, user_recommendations, metrics, chat
from app.core.exceptions import setup_exception_handlers
from app.core.metrics import metrics_collector

from app.models import CrimeData, EventData, NewsData, POIData, TrainingData, UserInteraction

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Hybrid AI Location App...")
    
    try:
        # Initialize Redis connection
        await init_redis()
        logger.info("Redis connection established")
        
        # Initialize database
        await init_db()
        logger.info("Database initialized")
        
        logger.info("Application startup complete")
        yield
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    finally:
        # Shutdown
        logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Hybrid AI Location App API",
    description="Real-time map of events, attractions, news, and crimes in the UK",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Metrics middleware - track request latencies
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Middleware to track request latencies for all endpoints"""
    start_time = time.time()
    response = await call_next(request)
    latency = time.time() - start_time

    # Record metrics for API endpoints
    if request.url.path.startswith("/api/"):
        metrics_collector.record_request(request.url.path, latency)

    return response


# Setup exception handlers
setup_exception_handlers(app)

# Include routers
app.include_router(status.router, prefix="/api/v1", tags=["status"])
app.include_router(geocode.router, prefix="/api/v1", tags=["geocoding"])
app.include_router(crime.router, prefix="/api/v1", tags=["crime"])
app.include_router(events.router, prefix="/api/v1", tags=["events"])
app.include_router(news.router, prefix="/api/v1", tags=["news"])
app.include_router(pois.router, prefix="/api/v1", tags=["pois"])
app.include_router(summary.router, prefix="/api/v1", tags=["summary"])
app.include_router(scoring.router, prefix="/api/v1", tags=["scoring"])
app.include_router(location_data.router, prefix="/api/v1", tags=["location-data"])
app.include_router(user_interaction.router, prefix="/api/v1", tags=["user-interactions"])
app.include_router(user_recommendations.router, prefix="/api/v1", tags=["user-recommendations"])
app.include_router(data_collection.router, prefix="/api/v1", tags=["data-collection"])
app.include_router(data_cleaning.router, prefix="/api/v1", tags=["data-cleaning"])
app.include_router(feature_engineering.router, prefix="/api/v1/features", tags=["feature-engineering"])
app.include_router(model_training.router, prefix="/api/v1/models", tags=["model-training"])
app.include_router(metrics.router, prefix="/api/v1", tags=["metrics"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])

# Catch-all for SPA (React router)
# @app.get("/{full_path:path}")
def spa_handler(full_path: str):
    return FileResponse(os.path.join("dist", "index.html"))


@app.get("/api")
async def api_root():
    """API root endpoint"""
    return {
        "message": "Hybrid AI Location App API v1",
        "endpoints": {
            "status": "/api/v1/status",
            "geocode": "/api/v1/geocode",
            "crime": "/api/v1/crime",
            "events": "/api/v1/events",
            "news": "/api/v1/news",
            "pois": "/api/v1/pois",
            "summary": "/api/v1/summarise",
            "scoring": "/api/v1/scores",
            "location-data": "/api/v1/location-data",
            "user-interactions": "/api/v1/interaction",
            "user-recommendations": "/api/v1/user-recommendations",
            "data-collection": "/api/v1/collect",
            "data-cleaning": "/api/v1/clean",
            "feature-engineering": "/api/v1/features",
            "model-training": "/api/v1/models",
            "chat": "/api/v1/chat"
        }
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
