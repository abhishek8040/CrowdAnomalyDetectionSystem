"""
Video Analysis Route
POST endpoint for uploading and analyzing video files with the comprehensive anomaly suite.
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import cv2
import numpy as np
import tempfile
import os
import base64
import logging
import json
from datetime import datetime
import database

logger = logging.getLogger(__name__)

router = APIRouter()


class AnalysisConfig(BaseModel):
    """Configuration for uploaded video analysis."""
    overcrowding_threshold: int = 10
    loitering_time: int = 300  # seconds
    loitering_distance: float = 50.0  # pixels
    velocity_threshold: float = 15.0
    restricted_zones: List[List[List[float]]] = []
    tripwire: Optional[List[List[float]]] = None
    camera_id: str = "upload_0"


class EventModel(BaseModel):
    """Model for detected events."""
    event_id: Optional[str] = None
    event_type: str
    camera_id: str = "upload_0"
    severity: str = "medium"
    confidence: float = 1.0
    timestamp: str
    frame_number: int
    details: Dict[str, Any]
    snapshot: Optional[str] = None


class AnalysisResult(BaseModel):
    """Model for analysis results."""
    success: bool
    total_frames: int
    fps: int
    events: List[EventModel]
    summary: Dict[str, Any]
    frame_tracks: Dict[int, List[Dict[str, Any]]] = {}


def _to_py(obj):
    """Recursively convert numpy types to native Python types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _to_py(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_py(x) for x in obj]
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    return obj


def _encode_frame(frame: np.ndarray, max_size: int = 400) -> str:
    """Encode frame as base64 JPEG."""
    h, w = frame.shape[:2]
    scale = max_size / max(h, w)
    if scale < 1.0:
        new_w = int(w * scale)
        new_h = int(h * scale)
        frame = cv2.resize(frame, (new_w, new_h))
    
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    jpg_base64 = base64.b64encode(buffer).decode('utf-8')
    return f"data:image/jpeg;base64,{jpg_base64}"


@router.post("/upload", response_model=AnalysisResult)
async def analyze_video(
    video: UploadFile = File(...),
    config: str = Form(default='{}')
):
    """
    Analyze an uploaded video file for public crowd anomalies, logging detected
    incidents to the database and returning frame tracking coordinates for UI overlay.
    """
    from main import app_state
    from models.detector import PersonDetector
    from tracking.deepsort import DeepSORT
    from anomaly.overcrowding import OvercrowdingDetector
    from anomaly.loitering import LoiteringDetector
    from anomaly.zone_violation import ZoneViolationDetector
    from anomaly.suspicious_activity import SuspiciousActivityDetector
    from anomaly.fall_detection import FallDetector
    from anomaly.panic_running import PanicRunningDetector
    from anomaly.snatching_detection import SnatchingDetector
    from anomaly.rule_engine import RuleEvaluator

    # Parse configuration
    try:
        config_dict = json.loads(config)
        analysis_config = AnalysisConfig(**config_dict)
    except Exception as e:
        logger.warning(f"Invalid config, using defaults: {e}")
        analysis_config = AnalysisConfig()

    # Save uploaded video to temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    try:
        size = 0
        chunk_size = 1024 * 1024
        while True:
            chunk = await video.read(chunk_size)
            if not chunk:
                break
            temp_file.write(chunk)
            size += len(chunk)
        temp_file.flush()
        temp_file.close()

        if size < 1024:
            raise HTTPException(status_code=400, detail="Uploaded file is empty or corrupted.")

        # Initialize analysis pipeline
        if app_state.get('detector') is None:
            app_state['detector'] = PersonDetector()
        detector = app_state['detector']
        
        # Dedicated tracker instance for this video upload
        tracker = DeepSORT(max_age=30, min_hits=3)
        if analysis_config.tripwire and len(analysis_config.tripwire) == 2:
            tracker.set_tripwire(tuple(analysis_config.tripwire[0]), tuple(analysis_config.tripwire[1]))

        overcrowding = OvercrowdingDetector(
            threshold=analysis_config.overcrowding_threshold,
            confirmation_frames=4
        )
        loitering = LoiteringDetector(
            pixel_threshold=analysis_config.loitering_distance,
            time_threshold=analysis_config.loitering_time,
            fps=30
        )
        zone_violation = ZoneViolationDetector()
        for zone in analysis_config.restricted_zones:
            zone_violation.add_zone([tuple(p) for p in zone])

        suspicious = SuspiciousActivityDetector(
            velocity_threshold=analysis_config.velocity_threshold
        )
        fall_detector = FallDetector()
        panic_detector = PanicRunningDetector()
        snatching_detector = SnatchingDetector()

        # Active rules
        active_rules = database.get_rules(active_only=True)
        rule_evaluator = RuleEvaluator(active_rules)

        cap = cv2.VideoCapture(temp_file.name)
        if not cap.isOpened():
            raise HTTPException(status_code=400, detail="Failed to open video. Unsupported codec or corrupted file.")

        fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
        loitering.fps = fps
        loitering.frame_threshold = int(loitering.time_threshold * fps)

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames == 0:
            raise HTTPException(status_code=400, detail="Video contains zero frames.")

        events = []
        frame_tracks = {}
        frame_num = 0
        camera_id = analysis_config.camera_id

        logger.info(f"Analyzing uploaded video: {total_frames} frames @ {fps}fps")

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            frame_num += 1

            # 1. Person Detection with Appearance Features
            detection_list, features = detector.detect_people_with_features(frame)

            # 2. Tracking with Appearance Re-ID
            tracks = tracker.update(detection_list, frame=frame, features=features)
            count = len(tracks)

            # Record track coordinates (sample every frame for player overlay)
            # Store essential fields: id, bbox, speed, class_name
            frame_tracks[frame_num] = [
                {
                    'id': t['id'],
                    'bbox': [round(c, 1) for c in t['bbox']],
                    'speed': round(t.get('speed', 0.0), 1),
                    'class_name': t.get('class_name', 'person')
                }
                for t in tracks
            ]

            density_info = tracker.get_crowd_density(frame.shape[:2])

            current_snapshot = None
            def get_snapshot():
                nonlocal current_snapshot
                if current_snapshot is None:
                    current_snapshot = _encode_frame(frame)
                return current_snapshot

            # Helper to persist and store event
            def record_event(etype, details, severity="medium", confidence=1.0):
                safe_d = _to_py(details)
                saved = database.save_event(
                    event_type=etype,
                    details=safe_d,
                    frame_number=frame_num,
                    camera_id=camera_id,
                    severity=severity,
                    confidence=confidence,
                    snapshot=get_snapshot()
                )
                events.append(EventModel(
                    event_id=saved.get('event_id'),
                    event_type=etype,
                    camera_id=camera_id,
                    severity=severity,
                    confidence=confidence,
                    timestamp=saved.get('timestamp', datetime.now().isoformat()),
                    frame_number=frame_num,
                    details=safe_d,
                    snapshot=current_snapshot
                ))

            # 3. Overcrowding
            overcrowd_res = overcrowding.detect_overcrowding(count, density_info=density_info)
            if overcrowd_res['alert_triggered']:
                record_event(
                    'overcrowding',
                    overcrowd_res,
                    severity=overcrowd_res.get('severity', 'high'),
                    confidence=overcrowd_res.get('confidence', 0.9)
                )

            # 4. Panic & Running
            panic_res = panic_detector.detect_motion_anomalies(tracks, frame_num)
            if panic_res['alert_triggered']:
                ename = 'panic' if panic_res.get('is_panic') else 'running'
                record_event(
                    ename,
                    panic_res,
                    severity=panic_res.get('severity', 'high'),
                    confidence=panic_res.get('confidence', 0.8)
                )

            # 4b. Drive-by Snatching & Theft
            snatch_res = snatching_detector.update_and_detect(tracks, frame_num)
            if snatch_res['alert_triggered']:
                record_event(
                    'snatching',
                    snatch_res,
                    severity=snatch_res.get('severity', 'critical'),
                    confidence=snatch_res.get('confidence', 0.92)
                )

            # 5. Per-Track Anomalies
            active_track_ids = []
            anomaly_eval_summary = {
                'overcrowding': overcrowd_res,
                'panic_running': panic_res,
                'snatching': snatch_res,
                'zone_violation': {},
                'fight': {},
                'fall': {}
            }

            for track in tracks:
                track_id = track['id']
                bbox = track['bbox']
                active_track_ids.append(track_id)
                center_x = (bbox[0] + bbox[2]) / 2.0
                center_y = (bbox[1] + bbox[3]) / 2.0
                center = (center_x, center_y)

                # Loitering
                loitering.update_track(track_id, center, frame_num)
                loiter_res = loitering.detect_loitering(track_id)
                if loiter_res['alert_triggered']:
                    record_event(
                        'loitering',
                        loiter_res,
                        severity=loiter_res.get('severity', 'medium'),
                        confidence=loiter_res.get('confidence', 0.85)
                    )

                # Zone Violation
                zone_res = zone_violation.detect_zone_violation(center, track_id=track_id)
                if zone_res.get('is_violation'):
                    anomaly_eval_summary['zone_violation'] = zone_res
                if zone_res['alert_triggered']:
                    record_event(
                        'zone_violation',
                        zone_res,
                        severity='high',
                        confidence=0.95
                    )

                # Pose (sample every 3 frames)
                pose_kps = None
                if frame_num % 3 == 0:
                    pose_kps = suspicious.extract_pose(frame, bbox)

                # Fall Detection
                fall_res = fall_detector.update_and_detect(
                    track_id, bbox, frame_num, pose_landmarks=pose_kps
                )
                if fall_res.get('is_fall'):
                    anomaly_eval_summary['fall'] = fall_res
                if fall_res['alert_triggered']:
                    record_event(
                        'fall',
                        fall_res,
                        severity=fall_res.get('severity', 'high'),
                        confidence=fall_res.get('confidence', 0.85)
                    )

                # Physical Altercation
                if pose_kps is not None:
                    suspicious.update_pose_history(track_id, pose_kps)
                    activity_res = suspicious.detect_fight_like_motion(
                        track_id=track_id, all_tracks=tracks
                    )
                    if activity_res.get('is_fight'):
                        anomaly_eval_summary['fight'] = activity_res
                    if activity_res['alert_triggered']:
                        record_event(
                            'suspicious_activity',
                            activity_res,
                            severity=activity_res.get('severity', 'critical'),
                            confidence=activity_res.get('confidence', 0.9)
                        )

            # 6. Active Custom Rules
            if active_rules:
                rule_alerts = rule_evaluator.evaluate(
                    frame_num, tracks, zone_violation.get_zones(), anomaly_eval_summary
                )
                for r_alert in rule_alerts:
                    record_event(
                        r_alert['event_type'],
                        r_alert['details'],
                        severity=r_alert.get('severity', 'high'),
                        confidence=r_alert.get('confidence', 0.9)
                    )

            loitering.cleanup_old_tracks(active_track_ids)
            suspicious.cleanup_old_tracks(active_track_ids)
            fall_detector.cleanup_old_tracks(active_track_ids)
            snatching_detector.cleanup_old_tracks(active_track_ids)

        cap.release()

        # Generate summary
        snatching_count = sum(1 for e in events if e.event_type == 'snatching')
        event_breakdown = {
            'overcrowding': sum(1 for e in events if e.event_type == 'overcrowding'),
            'loitering': sum(1 for e in events if e.event_type == 'loitering'),
            'zone_violation': sum(1 for e in events if e.event_type == 'zone_violation'),
            'suspicious_activity': sum(1 for e in events if e.event_type == 'suspicious_activity'),
            'fall': sum(1 for e in events if e.event_type == 'fall'),
            'panic': sum(1 for e in events if e.event_type == 'panic'),
            'running': sum(1 for e in events if e.event_type == 'running'),
            'snatching': snatching_count,
            'custom_rule': sum(1 for e in events if e.event_type == 'custom_rule'),
        }

        summary = {
            'total_frames': total_frames,
            'fps': fps,
            'total_events': len(events),
            'entry_count': tracker.entry_count,
            'exit_count': tracker.exit_count,
            'snatching_detected': snatching_count > 0,
            'event_breakdown': event_breakdown
        }

        logger.info(f"Video analysis complete: {len(events)} events detected across {total_frames} frames (snatching: {snatching_count}).")

        return AnalysisResult(
            success=True,
            total_frames=total_frames,
            fps=fps,
            events=events,
            summary=summary,
            frame_tracks=frame_tracks
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")
    finally:
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)
