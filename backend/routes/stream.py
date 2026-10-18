"""
WebSocket Stream Route
Real-time video streaming with advanced multi-anomaly detection, tripwire counting,
natural language rule evaluation, and persistent event logging.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from typing import List, Set, Dict, Optional, Any
import json
import asyncio
import logging
from datetime import datetime
import database

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict):
        disconnected = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to broadcast: {e}")
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()
live_task: Optional[asyncio.Task] = None
live_source: Optional[str] = None
last_live_jpeg: Optional[bytes] = None

# Alert cooldown tracking: {(event_type, track_id or None): last_timestamp}
_alert_last_ts = {}
_ALERT_COOLDOWN_SEC = 5.0


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for bidirectional real-time control and telemetry.
    """
    await manager.connect(websocket)
    global live_task, live_source
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            command = message.get('command')
            
            if command == 'ping':
                await websocket.send_json({
                    'type': 'pong',
                    'timestamp': datetime.now().isoformat()
                })
            
            elif command == 'update_config':
                config = message.get('config', {})
                logger.info(f"Config update received: {config}")
                try:
                    from main import app_state
                    overcrowding = app_state.get('overcrowding')
                    loitering = app_state.get('loitering')
                    zone_violation = app_state.get('zone_violation')
                    suspicious = app_state.get('suspicious')
                    tracker = app_state.get('tracker')

                    if overcrowding and 'overcrowding_threshold' in config:
                        overcrowding.threshold = int(config['overcrowding_threshold'])
                    if loitering:
                        if 'loitering_distance' in config:
                            loitering.pixel_threshold = float(config['loitering_distance'])
                        if 'loitering_time' in config:
                            loitering.time_threshold = int(config['loitering_time'])
                        if 'fps' in config:
                            loitering.fps = int(config['fps'])
                        loitering.frame_threshold = int(loitering.time_threshold * loitering.fps)
                    if suspicious and 'velocity_threshold' in config:
                        suspicious.velocity_threshold = float(config['velocity_threshold'])
                    if zone_violation and 'restricted_zones' in config:
                        zone_violation.clear_zones()
                        for zone in config['restricted_zones']:
                            zone_violation.add_zone([tuple(p) for p in zone])
                    if tracker and 'tripwire' in config and config['tripwire']:
                        tw = config['tripwire']
                        if len(tw) == 2:
                            tracker.set_tripwire(tuple(tw[0]), tuple(tw[1]))
                except Exception as e:
                    logger.error(f"Failed applying config update: {e}", exc_info=True)
                
                await websocket.send_json({
                    'type': 'config_updated',
                    'config': config,
                    'timestamp': datetime.now().isoformat()
                })
            
            elif command == 'get_status':
                await websocket.send_json({
                    'type': 'status',
                    'active_connections': len(manager.active_connections),
                    'live_running': bool(live_task),
                    'live_source': live_source,
                    'timestamp': datetime.now().isoformat()
                })

            elif command == 'start_stream':
                source_url = message.get('source')
                config = message.get('config', {})
                if source_url is None:
                    await websocket.send_json({'type': 'error', 'message': 'Source URL missing'})
                    continue
                if live_task and not live_task.done():
                    live_task.cancel()
                    live_task = None
                live_source = str(source_url)
                live_task = asyncio.create_task(_run_live_stream(source_url, config))
                await websocket.send_json({'type': 'live_started', 'source': str(source_url)})

            elif command == 'stop_stream':
                if live_task and not live_task.done():
                    live_task.cancel()
                    live_task = None
                live_source = None
                await websocket.send_json({'type': 'live_stopped'})
            
            else:
                logger.warning(f"Unknown command: {command}")
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        manager.disconnect(websocket)


async def send_detection_update(
    detections: List[dict],
    frame_number: int,
    crowd_density: Optional[Dict] = None,
    entry_count: int = 0,
    exit_count: int = 0
):
    """Broadcast frame-level detection summary and crowd metrics to clients."""
    message = {
        'type': 'detection',
        'frame_number': frame_number,
        'detections': detections,
        'count': len(detections),
        'crowd_density': crowd_density or {},
        'entry_count': entry_count,
        'exit_count': exit_count,
        'timestamp': datetime.now().isoformat()
    }
    await manager.broadcast(message)


async def send_anomaly_alert(
    event_type: str,
    details: dict,
    frame_number: int,
    snapshot: Optional[str] = None,
    camera_id: str = "camera_0",
    severity: str = "medium",
    confidence: float = 1.0
):
    """
    Save event to persistent database and broadcast alert to all clients.
    """
    track_id = details.get('track_id')
    key = (event_type, track_id)
    
    # Cooldown verification to prevent frame-by-frame alert flooding
    from time import time
    now = time()
    last = _alert_last_ts.get(key, 0)
    if now - last < _ALERT_COOLDOWN_SEC:
        return
    _alert_last_ts[key] = now

    # Convert NumPy objects to standard Python types
    def _to_py(val):
        try:
            import numpy as np
            if isinstance(val, (np.bool_,)):
                return bool(val)
            if isinstance(val, (np.integer,)):
                return int(val)
            if isinstance(val, (np.floating,)):
                return float(val)
            if isinstance(val, (np.ndarray,)):
                return val.tolist()
        except Exception:
            pass
        return val

    safe_details = {k: _to_py(v) for k, v in (details or {}).items()}
    actual_severity = details.get('severity', severity)
    actual_confidence = details.get('confidence', confidence)

    # 1. Persist to SQLite Database
    saved_event = None
    try:
        saved_event = database.save_event(
            event_type=event_type,
            details=safe_details,
            frame_number=frame_number,
            camera_id=camera_id,
            severity=actual_severity,
            confidence=actual_confidence,
            snapshot=snapshot
        )
    except Exception as e:
        logger.error(f"Failed to persist event to database: {e}", exc_info=True)

    event_id = saved_event.get('event_id') if saved_event else None

    # 2. Broadcast via WebSocket
    message = {
        'type': 'alert',
        'event_id': event_id,
        'event_type': event_type,
        'camera_id': camera_id,
        'severity': actual_severity,
        'confidence': actual_confidence,
        'frame_number': frame_number,
        'details': safe_details,
        'timestamp': datetime.now().isoformat(),
        'snapshot': snapshot
    }
    await manager.broadcast(message)


@router.get("/mjpeg")
async def mjpeg_stream():
    """MJPEG streaming endpoint for smooth live video preview."""
    import cv2
    import numpy as np
    from time import time
    boundary = b"frame"

    async def frame_gen():
        global last_live_jpeg
        placeholder = None
        target_interval = 1.0 / 25.0
        while True:
            start = time()
            frame_bytes = last_live_jpeg
            if frame_bytes is None:
                if placeholder is None:
                    img = np.zeros((240, 320, 3), dtype=np.uint8)
                    cv2.putText(
                        img, 'Awaiting Stream...', (40, 120),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA
                    )
                    ok, buf = cv2.imencode('.jpg', img)
                    if ok:
                        placeholder = buf.tobytes()
                frame_bytes = placeholder

            yield (
                b"--" + boundary + b"\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(frame_bytes)).encode() + b"\r\n\r\n"
                + frame_bytes + b"\r\n"
            )
            elapsed = time() - start
            sleep_for = max(0.005, target_interval - elapsed)
            await asyncio.sleep(sleep_for)

    return StreamingResponse(frame_gen(), media_type='multipart/x-mixed-replace; boundary=frame')


async def _run_live_stream(source: Any, config: dict):
    """
    Continuous live stream processing loop with multi-anomaly detection and rule evaluation.
    """
    import cv2
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
    from utils.video_stream import VideoStream
    from .analyze import _encode_frame

    # Lazy-load / reuse components
    detector = app_state.get('detector') or PersonDetector()
    app_state['detector'] = detector
    tracker = app_state.get('tracker') or DeepSORT(max_age=30, min_hits=3)
    app_state['tracker'] = tracker
    overcrowding = app_state.get('overcrowding') or OvercrowdingDetector()
    loitering = app_state.get('loitering') or LoiteringDetector()
    zone_violation = app_state.get('zone_violation') or ZoneViolationDetector()
    suspicious = app_state.get('suspicious') or SuspiciousActivityDetector()
    
    fall_detector = app_state.get('fall_detector') or FallDetector()
    app_state['fall_detector'] = fall_detector
    panic_detector = app_state.get('panic_detector') or PanicRunningDetector()
    app_state['panic_detector'] = panic_detector
    snatching_detector = app_state.get('snatching_detector') or SnatchingDetector()
    app_state['snatching_detector'] = snatching_detector

    # Load active rules from database
    active_rules = database.get_rules(active_only=True)
    rule_evaluator = RuleEvaluator(active_rules)

    # Apply configuration
    overcrowding.threshold = int(config.get('overcrowding_threshold', overcrowding.threshold))
    loitering.pixel_threshold = float(config.get('loitering_distance', loitering.pixel_threshold))
    loitering.time_threshold = int(config.get('loitering_time', loitering.time_threshold))
    suspicious.velocity_threshold = float(config.get('velocity_threshold', suspicious.velocity_threshold))
    
    camera_id = str(config.get('camera_id', 'camera_0'))

    if 'restricted_zones' in config:
        zone_violation.clear_zones()
        for zone in config['restricted_zones']:
            zone_violation.add_zone([tuple(p) for p in zone])

    if 'tripwire' in config and config['tripwire'] and len(config['tripwire']) == 2:
        tracker.set_tripwire(tuple(config['tripwire'][0]), tuple(config['tripwire'][1]))

    preview_interval = int(config.get('preview_interval', 10))
    preview_max_width = int(config.get('preview_max_width', 960))
    
    global last_live_jpeg
    frame_num = 0

    try:
        with VideoStream(source) as vs:
            last_w, last_h = None, None
            while True:
                ret, frame = vs.read()
                if not ret:
                    await manager.broadcast({'type': 'error', 'message': f'Stream ended/unavailable: {source}'})
                    break
                frame_num += 1

                if last_w is None or last_h is None:
                    last_h, last_w = frame.shape[:2]
                    await manager.broadcast({
                        'type': 'stream_info',
                        'width': last_w,
                        'height': last_h
                    })

                # 1. Person Detection with Appearance Features
                detection_list, features = detector.detect_people_with_features(frame)

                # 2. Tracking with Appearance Re-ID
                tracks = tracker.update(detection_list, frame=frame, features=features)
                count = len(tracks)

                # 3. Crowd Density Estimation
                density_info = tracker.get_crowd_density(frame.shape[:2])

                # 4. Broadcast Detection & Counter Telemetry
                await send_detection_update(
                    [{'id': t['id'], 'bbox': t['bbox'], 'confidence': t['confidence'], 'speed': t.get('speed', 0.0)} for t in tracks],
                    frame_num,
                    crowd_density=density_info,
                    entry_count=tracker.entry_count,
                    exit_count=tracker.exit_count
                )

                # Update MJPEG preview buffer
                try:
                    mjpeg_frame = frame
                    if mjpeg_frame.shape[1] > preview_max_width:
                        scale = preview_max_width / mjpeg_frame.shape[1]
                        mjpeg_frame = cv2.resize(mjpeg_frame, (int(mjpeg_frame.shape[1] * scale), int(mjpeg_frame.shape[0] * scale)))
                    ok, buf = cv2.imencode('.jpg', mjpeg_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                    if ok:
                        last_live_jpeg = buf.tobytes()
                except Exception:
                    pass

                # Encode snapshot on demand
                current_snapshot = None

                def get_snapshot():
                    nonlocal current_snapshot
                    if current_snapshot is None:
                        current_snapshot = _encode_frame(frame)
                    return current_snapshot

                # 5. Overcrowding Check
                overcrowd_result = overcrowding.detect_overcrowding(count, density_info=density_info)
                if overcrowd_result['alert_triggered']:
                    await send_anomaly_alert(
                        'overcrowding',
                        overcrowd_result,
                        frame_num,
                        snapshot=get_snapshot(),
                        camera_id=camera_id,
                        severity=overcrowd_result.get('severity', 'high'),
                        confidence=overcrowd_result.get('confidence', 0.9)
                    )

                # 6. Panic & Running Check
                panic_result = panic_detector.detect_motion_anomalies(tracks, frame_num)
                if panic_result['alert_triggered']:
                    event_name = 'panic' if panic_result.get('is_panic') else 'running'
                    await send_anomaly_alert(
                        event_name,
                        panic_result,
                        frame_num,
                        snapshot=get_snapshot(),
                        camera_id=camera_id,
                        severity=panic_result.get('severity', 'high'),
                        confidence=panic_result.get('confidence', 0.8)
                    )

                # 6b. Snatching & Drive-by Theft Check
                snatch_result = snatching_detector.update_and_detect(tracks, frame_num)
                if snatch_result['alert_triggered']:
                    await send_anomaly_alert(
                        'snatching',
                        snatch_result,
                        frame_num,
                        snapshot=get_snapshot(),
                        camera_id=camera_id,
                        severity=snatch_result.get('severity', 'critical'),
                        confidence=snatch_result.get('confidence', 0.92)
                    )

                # 7. Per-Track Anomaly Checks (Loitering, Zone Violation, Fall, Suspicious Activity)
                active_track_ids = []
                anomaly_eval_summary = {
                    'overcrowding': overcrowd_result,
                    'panic_running': panic_result,
                    'snatching': snatch_result,
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

                    # A. Loitering
                    loitering.update_track(track_id, center, frame_num)
                    loiter_result = loitering.detect_loitering(track_id)
                    if loiter_result['alert_triggered']:
                        await send_anomaly_alert(
                            'loitering',
                            loiter_result,
                            frame_num,
                            snapshot=get_snapshot(),
                            camera_id=camera_id,
                            severity=loiter_result.get('severity', 'medium'),
                            confidence=loiter_result.get('confidence', 0.85)
                        )

                    # B. Zone Violation
                    zone_result = zone_violation.detect_zone_violation(center, track_id=track_id)
                    if zone_result.get('is_violation'):
                        anomaly_eval_summary['zone_violation'] = zone_result
                    if zone_result['alert_triggered']:
                        await send_anomaly_alert(
                            'zone_violation',
                            zone_result,
                            frame_num,
                            snapshot=get_snapshot(),
                            camera_id=camera_id,
                            severity='high',
                            confidence=0.95
                        )

                    # C. Pose Extraction for Fall and Altercation
                    pose_keypoints = None
                    if frame_num % 3 == 0:  # Sample pose every 3 frames for throughput
                        pose_keypoints = suspicious.extract_pose(frame, bbox)

                    # D. Fall Detection
                    fall_result = fall_detector.update_and_detect(
                        track_id, bbox, frame_num, pose_landmarks=pose_keypoints
                    )
                    if fall_result.get('is_fall'):
                        anomaly_eval_summary['fall'] = fall_result
                    if fall_result['alert_triggered']:
                        await send_anomaly_alert(
                            'fall',
                            fall_result,
                            frame_num,
                            snapshot=get_snapshot(),
                            camera_id=camera_id,
                            severity=fall_result.get('severity', 'high'),
                            confidence=fall_result.get('confidence', 0.85)
                        )

                    # E. Physical Altercation / Suspicious Motion
                    if pose_keypoints is not None:
                        suspicious.update_pose_history(track_id, pose_keypoints)
                        activity_result = suspicious.detect_fight_like_motion(
                            track_id=track_id, all_tracks=tracks
                        )
                        if activity_result.get('is_fight'):
                            anomaly_eval_summary['fight'] = activity_result
                        if activity_result['alert_triggered']:
                            await send_anomaly_alert(
                                'suspicious_activity',
                                activity_result,
                                frame_num,
                                snapshot=get_snapshot(),
                                camera_id=camera_id,
                                severity=activity_result.get('severity', 'critical'),
                                confidence=activity_result.get('confidence', 0.9)
                            )

                # 8. Evaluate Operator Custom Rules
                if active_rules:
                    rule_alerts = rule_evaluator.evaluate(
                        frame_num, tracks, zone_violation.get_zones(), anomaly_eval_summary
                    )
                    for rule_alert in rule_alerts:
                        await send_anomaly_alert(
                            rule_alert['event_type'],
                            rule_alert['details'],
                            frame_num,
                            snapshot=get_snapshot(),
                            camera_id=camera_id,
                            severity=rule_alert.get('severity', 'high'),
                            confidence=rule_alert.get('confidence', 0.9)
                        )

                # Track cleanup
                loitering.cleanup_old_tracks(active_track_ids)
                suspicious.cleanup_old_tracks(active_track_ids)
                fall_detector.cleanup_old_tracks(active_track_ids)
                snatching_detector.cleanup_old_tracks(active_track_ids)

                await asyncio.sleep(0.001)

    except asyncio.CancelledError:
        logger.info(f"Live stream task for '{source}' cancelled.")
        last_live_jpeg = None
    except Exception as e:
        logger.error(f"Live stream encountered unhandled error: {e}", exc_info=True)
        await manager.broadcast({'type': 'error', 'message': f"Stream error: {e}"})
