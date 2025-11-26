"""
Video Analysis Route
POST endpoint for uploading and analyzing videos
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Optional
import cv2
import numpy as np
import tempfile
import os
import base64
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter()


class AnalysisConfig(BaseModel):
    """Configuration for video analysis"""
    overcrowding_threshold: int = 10
    loitering_time: int = 300  # seconds
    loitering_distance: float = 50.0  # pixels
    velocity_threshold: float = 15.0
    restricted_zones: List[List[List[float]]] = []


class EventModel(BaseModel):
    """Model for detected events"""
    event_type: str
    timestamp: str
    frame_number: int
    details: Dict
    snapshot: Optional[str] = None


class AnalysisResult(BaseModel):
    """Model for analysis results"""
    success: bool
    total_frames: int
    events: List[EventModel]
    summary: Dict
def _to_py(obj):
    """Recursively convert numpy types to native Python types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _to_py(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [
            _to_py(x) for x in obj
        ]
    # Scalars
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    return obj



@router.post("/upload", response_model=AnalysisResult)
async def analyze_video(
    video: UploadFile = File(...),
    config: str = Form(default='{}')
):
    """
    Analyze uploaded video for anomalies
    
    Args:
        video: Uploaded video file
        config: JSON configuration string
        
    Returns:
        Analysis results with detected events
    """
    import json
    # Reuse global components from main to avoid re-loading heavy models each request
    from main import app_state
    from models.detector import PersonDetector
    
    # Parse configuration
    try:
        config_dict = json.loads(config)
        analysis_config = AnalysisConfig(**config_dict)
    except Exception as e:
        logger.warning(f"Invalid config, using defaults: {e}")
        analysis_config = AnalysisConfig()
    
    # Save uploaded file temporarily (streamed to avoid large memory usage)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    try:
        size = 0
        chunk_size = 1024 * 1024  # 1MB
        while True:
            chunk = await video.read(chunk_size)
            if not chunk:
                break
            temp_file.write(chunk)
            size += len(chunk)
        temp_file.flush()
        temp_file.close()
        if size < 1024:
            raise HTTPException(status_code=400, detail="Uploaded file is empty or too small to be a valid video.")

        # Initialize or reuse heavy components
        if app_state.get('detector') is None:
            logger.info("Lazy-loading YOLO detector for first use.")
            app_state['detector'] = PersonDetector()
        detector = app_state['detector']
        tracker = app_state['tracker']  # already initialized in lifespan
        overcrowding = app_state['overcrowding']
        # Update thresholds dynamically from config
        overcrowding.threshold = analysis_config.overcrowding_threshold
        loitering = app_state['loitering']
        loitering.pixel_threshold = analysis_config.loitering_distance
        loitering.time_threshold = analysis_config.loitering_time
        zone_violation = app_state['zone_violation']
        suspicious = app_state['suspicious']
        suspicious.velocity_threshold = analysis_config.velocity_threshold

        # Replace zones with provided restricted zones
        zone_violation.clear_zones()
        for zone in analysis_config.restricted_zones:
            zone_violation.add_zone([tuple(point) for point in zone])
        
        # Process video
        cap = cv2.VideoCapture(temp_file.name)
        if not cap.isOpened():
            raise HTTPException(status_code=400, detail="Failed to open video. Unsupported codec or corrupted file.")
        fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames == 0:
            raise HTTPException(status_code=400, detail="Video contains 0 frames. Possibly corrupted or unsupported format.")
        
        events = []
        frame_num = 0
        
        logger.info(f"Processing video: {total_frames} frames @ {fps}fps")
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_num += 1
            
            # Detect people
            detections = detector.detect_people(frame)
            detection_list = [[*bbox, conf] for bbox, conf, _ in detections]
            
            # Track people
            tracks = tracker.update(detection_list, frame)
            
            # Count people
            count = len(tracks)
            
            # Check overcrowding
            overcrowd_result = overcrowding.detect_overcrowding(count)
            if overcrowd_result['alert_triggered']:
                event = EventModel(
                    event_type="overcrowding",
                    timestamp=datetime.now().isoformat(),
                    frame_number=frame_num,
                    details=_to_py(overcrowd_result),
                    snapshot=_encode_frame(frame)
                )
                events.append(event)
            
            # Process each track
            active_track_ids = []
            for track in tracks:
                track_id = track['id']
                bbox = track['bbox']
                active_track_ids.append(track_id)
                
                # Calculate center point
                center_x = (bbox[0] + bbox[2]) / 2
                center_y = (bbox[1] + bbox[3]) / 2
                center = (center_x, center_y)
                
                # Update loitering history
                loitering.update_track(track_id, center, frame_num)
                
                # Check loitering
                loiter_result = loitering.detect_loitering(track_id)
                if loiter_result['alert_triggered']:
                    event = EventModel(
                        event_type="loitering",
                        timestamp=datetime.now().isoformat(),
                        frame_number=frame_num,
                        details=_to_py(loiter_result),
                        snapshot=_encode_frame(frame)
                    )
                    events.append(event)
                
                # Check zone violation
                zone_result = zone_violation.detect_zone_violation(center, track_id=track_id)
                if zone_result['alert_triggered']:
                    event = EventModel(
                        event_type="zone_violation",
                        timestamp=datetime.now().isoformat(),
                        frame_number=frame_num,
                        details=_to_py(zone_result),
                        snapshot=_encode_frame(frame)
                    )
                    events.append(event)
                
                # Extract pose and check suspicious activity
                pose_keypoints = suspicious.extract_pose(frame, bbox)
                if pose_keypoints is not None:
                    suspicious.update_pose_history(track_id, pose_keypoints)
                    
                    # Check for suspicious activity
                    if frame_num % 10 == 0:  # Check every 10 frames
                        activity_result = suspicious.detect_fight_like_motion(track_id=track_id)
                        if activity_result['alert_triggered']:
                            event = EventModel(
                                event_type="suspicious_activity",
                                timestamp=datetime.now().isoformat(),
                                frame_number=frame_num,
                                details=_to_py(activity_result),
                                snapshot=_encode_frame(frame)
                            )
                            events.append(event)
            
            # Cleanup old tracks
            loitering.cleanup_old_tracks(active_track_ids)
            suspicious.cleanup_old_tracks(active_track_ids)
        
        cap.release()
        
        # Generate summary
        summary = {
            'total_frames': total_frames,
            'fps': fps,
            'total_events': len(events),
            'event_breakdown': {
                'overcrowding': sum(1 for e in events if e.event_type == 'overcrowding'),
                'loitering': sum(1 for e in events if e.event_type == 'loitering'),
                'zone_violation': sum(1 for e in events if e.event_type == 'zone_violation'),
                'suspicious_activity': sum(1 for e in events if e.event_type == 'suspicious_activity')
            }
        }
        
        logger.info(f"Analysis complete: {len(events)} events detected")
        
        return AnalysisResult(
            success=True,
            total_frames=total_frames,
            events=events,
            summary=summary
        )
        
    except HTTPException:
        # Re-raise HTTPExceptions unchanged
        raise
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal processing error. Check server logs.")
    
    finally:
        # Cleanup temp file
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)


def _encode_frame(frame: np.ndarray, max_size: int = 400) -> str:
    """
    Encode frame as base64 JPEG
    
    Args:
        frame: Input frame
        max_size: Maximum dimension size
        
    Returns:
        Base64 encoded JPEG string
    """
    # Resize frame
    h, w = frame.shape[:2]
    scale = max_size / max(h, w)
    if scale < 1:
        new_w = int(w * scale)
        new_h = int(h * scale)
        frame = cv2.resize(frame, (new_w, new_h))
    
    # Encode as JPEG
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    
    # Convert to base64
    jpg_base64 = base64.b64encode(buffer).decode('utf-8')
    
    return f"data:image/jpeg;base64,{jpg_base64}"
