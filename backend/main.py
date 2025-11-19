"""
FastAPI Main Application
Crowd Anomaly Detection System Backend
"""
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import logging
from contextlib import asynccontextmanager

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
    # Startup
    logger.info("Initializing Crowd Anomaly Detection System...")
    
    from models.detector import PersonDetector
    from tracking.deepsort import DeepSORT
    from anomaly.overcrowding import OvercrowdingDetector
    from anomaly.loitering import LoiteringDetector
    from anomaly.zone_violation import ZoneViolationDetector
    from anomaly.suspicious_activity import SuspiciousActivityDetector
    
    # Initialize models (lazy loading - will download on first use)
    app_state['detector'] = None  # Will be initialized when needed
    app_state['tracker'] = DeepSORT(max_age=30, min_hits=3)
    app_state['overcrowding'] = OvercrowdingDetector(threshold=10)
    app_state['loitering'] = LoiteringDetector(pixel_threshold=50.0, time_threshold=300)
    app_state['zone_violation'] = ZoneViolationDetector()
    app_state['suspicious'] = SuspiciousActivityDetector(velocity_threshold=15.0)
    
    logger.info("System initialized successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Crowd Anomaly Detection System...")
    app_state.clear()


# Create FastAPI app
app = FastAPI(
    title="Crowd Anomaly Detection System",
    description="Real-time crowd monitoring with anomaly detection",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
from routes import analyze, stream

app.include_router(analyze.router, prefix="/api/analyze", tags=["analysis"])
app.include_router(stream.router, prefix="/api/stream", tags=["streaming"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Crowd Anomaly Detection System API",
        "version": "1.0.0",
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
            "anomaly_detectors": "ready"
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
async def update_zones(zones: list):
    """
    Update restricted zones
    
    Args:
        zones: List of polygon zones
    """
    if 'zone_violation' in app_state:
        app_state['zone_violation'].clear_zones()
        for zone in zones:
            app_state['zone_violation'].add_zone([tuple(point) for point in zone])
        
        return {
            "success": True,
            "message": f"Updated {len(zones)} restricted zones"
        }
    
    return {"success": False, "message": "Zone detector not initialized"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
