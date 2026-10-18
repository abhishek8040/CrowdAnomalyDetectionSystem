"""
FastAPI Main Application
Crowd Anomaly Detection System Backend
"""
import sys
from pathlib import Path

# Ensure backend directory is in sys.path regardless of whether uvicorn is launched
# from repository root (uvicorn backend.main:app) or backend directory (uvicorn main:app)
backend_dir = str(Path(__file__).resolve().parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi import FastAPI, WebSocket, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import logging
from contextlib import asynccontextmanager
import database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Global state
app_state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("Initializing Crowd Anomaly Detection System...")
    
    # Initialize SQLite database
    database.init_db()
    
    from models.detector import PersonDetector
    from tracking.deepsort import DeepSORT
    from anomaly.overcrowding import OvercrowdingDetector
    from anomaly.loitering import LoiteringDetector
    from anomaly.zone_violation import ZoneViolationDetector
    from anomaly.suspicious_activity import SuspiciousActivityDetector
    from anomaly.fall_detection import FallDetector
    from anomaly.panic_running import PanicRunningDetector
    from anomaly.snatching_detection import SnatchingDetector
    
    # Initialize models
    app_state['detector'] = None  # Lazy loaded on first frame
    app_state['tracker'] = DeepSORT(max_age=30, min_hits=3)
    app_state['overcrowding'] = OvercrowdingDetector(threshold=10, confirmation_frames=4)
    app_state['loitering'] = LoiteringDetector(pixel_threshold=50.0, time_threshold=300)
    app_state['zone_violation'] = ZoneViolationDetector()
    app_state['suspicious'] = SuspiciousActivityDetector(velocity_threshold=15.0)
    app_state['fall_detector'] = FallDetector()
    app_state['panic_detector'] = PanicRunningDetector()
    app_state['snatching_detector'] = SnatchingDetector()
    
    logger.info("System initialized successfully with multi-anomaly detection and persistent database.")
    
    yield
    
    logger.info("Shutting down Crowd Anomaly Detection System...")
    app_state.clear()


# Create FastAPI app
app = FastAPI(
    title="Crowd Anomaly Detection System",
    description="Real-time crowd monitoring with advanced AI anomaly detection and natural language rules",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
from routes import analyze, stream, events, rules

app.include_router(analyze.router, prefix="/api/analyze", tags=["analysis"])
app.include_router(stream.router, prefix="/api/stream", tags=["streaming"])
app.include_router(events.router, prefix="/api/events", tags=["events"])
app.include_router(rules.router, prefix="/api/rules", tags=["rules"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Crowd Anomaly Detection System API",
        "version": "2.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "components": {
            "detector": "ready",
            "tracker": "ready",
            "anomaly_detectors": "ready",
            "database": "connected"
        }
    }


@app.get("/config")
async def get_config():
    """Get current configuration"""
    return {
        "overcrowding_threshold": app_state['overcrowding'].threshold if 'overcrowding' in app_state else 10,
        "loitering": {
            "pixel_threshold": app_state['loitering'].pixel_threshold if 'loitering' in app_state else 50.0,
            "time_threshold": app_state['loitering'].time_threshold if 'loitering' in app_state else 300
        },
        "restricted_zones": app_state['zone_violation'].get_zones() if 'zone_violation' in app_state else []
    }


@app.post("/config/zones")
async def update_zones(zones: list = Body(...)):
    """
    Update restricted zones
    
    Args:
        zones: List of polygon zones
    """
    if 'zone_violation' not in app_state:
        from anomaly.zone_violation import ZoneViolationDetector
        app_state['zone_violation'] = ZoneViolationDetector()

    app_state['zone_violation'].clear_zones()
    for zone in zones:
        app_state['zone_violation'].add_zone([tuple(point) for point in zone])
    
    return {
        "success": True,
        "message": f"Updated {len(zones)} restricted zones"
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
