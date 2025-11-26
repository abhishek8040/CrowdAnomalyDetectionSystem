"""
WebSocket Stream Route
Real-time video streaming with anomaly alerts
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from typing import List, Set
import json
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        """Accept new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"New WebSocket connection. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send message to specific client"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to broadcast to client: {e}")
                disconnected.append(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)


# Global connection manager
manager = ConnectionManager()
live_task = None
live_source = None
# Raw JPEG bytes for MJPEG preview (updated each frame)
last_live_jpeg = None
# Alert cooldown tracking: {(event_type, track_id or None): last_timestamp}
_alert_last_ts = {}
_ALERT_COOLDOWN_SEC = 5.0


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time streaming
    
    Receives:
        - Configuration updates
        - Start/stop stream commands
        
    Sends:
        - Real-time detections
        - Anomaly alerts
        - Frame metadata
    """
    await manager.connect(websocket)
    
    try:
        global live_task, live_source
        while True:
            # Receive messages from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            command = message.get('command')
            
            if command == 'ping':
                # Respond to keepalive
                await websocket.send_json({
                    'type': 'pong',
                    'timestamp': datetime.now().isoformat()
                })
            
            elif command == 'update_config':
                # Handle configuration updates
                config = message.get('config', {})
                logger.info(f"Config update received: {config}")
                try:
                    from main import app_state
                    overcrowding = app_state.get('overcrowding')
                    loitering = app_state.get('loitering')
                    zone_violation = app_state.get('zone_violation')
                    suspicious = app_state.get('suspicious')

                    if overcrowding and 'overcrowding_threshold' in config:
                        overcrowding.threshold = int(config['overcrowding_threshold'])
                    if loitering:
                        if 'loitering_distance' in config:
                            loitering.pixel_threshold = float(config['loitering_distance'])
                        if 'loitering_time' in config:
                            loitering.time_threshold = int(config['loitering_time'])
                        # Optionally FPS override
                        if 'fps' in config:
                            loitering.fps = int(config['fps'])
                        loitering.frame_threshold = int(loitering.time_threshold * loitering.fps)
                    if suspicious and 'velocity_threshold' in config:
                        suspicious.velocity_threshold = float(config['velocity_threshold'])
                    if zone_violation and 'restricted_zones' in config:
                        zone_violation.clear_zones()
                        for zone in config['restricted_zones']:
                            zone_violation.add_zone([tuple(p) for p in zone])
                except Exception as e:
                    logger.error(f"Failed applying config update: {e}", exc_info=True)
                
                await websocket.send_json({
                    'type': 'config_updated',
                    'config': config,
                    'timestamp': datetime.now().isoformat()
                })
            
            elif command == 'get_status':
                # Send current status
                await websocket.send_json({
                    'type': 'status',
                    'active_connections': len(manager.active_connections),
                    'live_running': bool(live_task),
                    'live_source': live_source,
                    'timestamp': datetime.now().isoformat()
                })

            elif command == 'start_stream':
                # Start live CCTV/IP camera stream
                source_url = message.get('source')
                config = message.get('config', {})
                if not source_url:
                    await websocket.send_json({'type': 'error', 'message': 'source URL missing'})
                    continue
                # Cancel any existing live task
                if live_task:
                    live_task.cancel()
                    live_task = None
                live_source = source_url
                live_task = asyncio.create_task(_run_live_stream(source_url, config))
                await websocket.send_json({'type': 'live_started', 'source': source_url})

            elif command == 'stop_stream':
                if live_task:
                    live_task.cancel()
                    live_task = None
                live_source = None
                await websocket.send_json({'type': 'live_stopped'})
            
            else:
                logger.warning(f"Unknown command: {command}")
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Client disconnected normally")
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        manager.disconnect(websocket)


async def send_detection_update(detections: List[dict], frame_number: int):
    """
    Send detection update to all clients
    
    Args:
        detections: List of detection dictionaries
        frame_number: Current frame number
    """
    message = {
        'type': 'detection',
        'frame_number': frame_number,
        'detections': detections,
        'count': len(detections),
        'timestamp': datetime.now().isoformat()
    }
    
    await manager.broadcast(message)


async def send_anomaly_alert(event_type: str, details: dict, frame_number: int, snapshot: str = None):
    """
    Send anomaly alert to all clients
    
    Args:
        event_type: Type of anomaly (overcrowding, loitering, zone_violation, suspicious_activity)
        details: Event details dictionary
        frame_number: Frame number where event occurred
        snapshot: Optional base64 encoded snapshot
    """
    # Debounce repeated alerts per event/track within cooldown window
    track_id = details.get('track_id')
    key = (event_type, track_id)
    try:
        from time import time
        now = time()
        last = _alert_last_ts.get(key, 0)
        if now - last < _ALERT_COOLDOWN_SEC:
            return
        _alert_last_ts[key] = now
    except Exception:
        pass

    # Sanitize details to ensure JSON-serializable native Python types
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

    try:
        safe_details = {k: _to_py(v) for k, v in (details or {}).items()}
    except Exception:
        safe_details = details or {}

    message = {
        'type': 'alert',
        'event_type': event_type,
        'frame_number': frame_number,
        'details': safe_details,
        'timestamp': datetime.now().isoformat(),
        'snapshot': snapshot
    }
    
    await manager.broadcast(message)


async def send_tracking_update(tracks: List[dict], frame_number: int):
    """
    Send tracking update to all clients
    
    Args:
        tracks: List of tracked objects
        frame_number: Current frame number
    """
    message = {
        'type': 'tracking',
        'frame_number': frame_number,
        'tracks': tracks,
        'timestamp': datetime.now().isoformat()
    }
    
    await manager.broadcast(message)


@router.get("/mjpeg")
async def mjpeg_stream():
    """MJPEG streaming endpoint for smooth live preview.

    Serves multipart/x-mixed-replace with latest JPEG frames produced by the live stream loop.
    If no live stream is active, yields a placeholder frame periodically.
    """
    import cv2
    import numpy as np
    from time import time
    boundary = b"frame"

    async def frame_gen():
        global last_live_jpeg, live_task
        placeholder = None
        last_sent_ts = 0.0
        target_interval = 1.0 / 25.0  # ~25 FPS display if frames available
        while True:
            start = time()
            frame_bytes = last_live_jpeg
            if frame_bytes is None:
                if placeholder is None:
                    # Create a simple placeholder image
                    img = np.zeros((240, 320, 3), dtype=np.uint8)
                    cv2.putText(img, 'Waiting for stream...', (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1, cv2.LINE_AA)
                    ok, buf = cv2.imencode('.jpg', img)
                    if ok:
                        placeholder = buf.tobytes()
                frame_bytes = placeholder
            # Build multipart frame
            yield b"--" + boundary + b"\r\n" + b"Content-Type: image/jpeg\r\n" + b"Content-Length: " + str(len(frame_bytes)).encode() + b"\r\n\r\n" + frame_bytes + b"\r\n"
            # Sleep to regulate output rate
            elapsed = time() - start
            sleep_for = max(0.0, target_interval - elapsed)
            await asyncio.sleep(sleep_for)
            # If stream task ended, keep placeholder frames
    return StreamingResponse(frame_gen(), media_type='multipart/x-mixed-replace; boundary=frame')


async def _run_live_stream(source: str, config: dict):
    """Run live stream processing loop and broadcast detections/alerts."""
    import cv2
    from main import app_state
    from models.detector import PersonDetector
    from tracking.deepsort import DeepSORT
    from anomaly.overcrowding import OvercrowdingDetector
    from anomaly.loitering import LoiteringDetector
    from anomaly.zone_violation import ZoneViolationDetector
    from anomaly.suspicious_activity import SuspiciousActivityDetector
    from utils.video_stream import VideoStream
    from .analyze import _encode_frame

    # Reuse initialized components
    detector = app_state.get('detector') or PersonDetector()
    app_state['detector'] = detector
    tracker = app_state['tracker']
    overcrowding = app_state['overcrowding']
    loitering = app_state['loitering']
    zone_violation = app_state['zone_violation']
    suspicious = app_state['suspicious']

    # Apply config thresholds if provided
    overcrowding.threshold = int(config.get('overcrowding_threshold', overcrowding.threshold))
    loitering.pixel_threshold = float(config.get('loitering_distance', loitering.pixel_threshold))
    loitering.time_threshold = int(config.get('loitering_time', loitering.time_threshold))
    # Recompute frame threshold for loitering if fps/time change
    try:
        if 'fps' in config:
            loitering.fps = int(config['fps'])
        loitering.frame_threshold = int(loitering.time_threshold * loitering.fps)
    except Exception:
        pass
    suspicious.velocity_threshold = float(config.get('velocity_threshold', suspicious.velocity_threshold))
    # Zones
    if 'restricted_zones' in config:
        zone_violation.clear_zones()
        for zone in config['restricted_zones']:
            zone_violation.add_zone([tuple(p) for p in zone])

    frame_num = 0
    # Preview settings (can be overridden by client config)
    try:
        preview_interval = int(config.get('preview_interval', 10))
    except Exception:
        preview_interval = 10
    try:
        preview_max_width = int(config.get('preview_max_width', 960))
    except Exception:
        preview_max_width = 960
    global last_live_jpeg
    try:
        with VideoStream(source) as vs:
            last_w, last_h = None, None
            while True:
                ret, frame = vs.read()
                if not ret:
                    await manager.broadcast({'type': 'error', 'message': 'Stream ended/unavailable'})
                    break
                frame_num += 1

                # Send initial stream info
                if last_w is None or last_h is None:
                    last_h, last_w = frame.shape[:2]
                    await manager.broadcast({
                        'type': 'stream_info',
                        'width': last_w,
                        'height': last_h
                    })

                # Detection
                detections = detector.detect_people(frame)
                detection_list = [[*bbox, conf] for bbox, conf, _ in detections]
                # Tracking
                tracks = tracker.update(detection_list, frame)

                # Send detection count
                await send_detection_update(
                    [{'bbox': bbox, 'confidence': conf} for bbox, conf, _ in detections],
                    frame_num
                )

                # Periodic preview frame for UI background/overlay
                if preview_interval > 0 and frame_num % preview_interval == 0:
                    try:
                        preview = frame
                        # Optionally downscale large frames to reduce bandwidth
                        if preview.shape[1] > preview_max_width:
                            import cv2
                            scale = preview_max_width / preview.shape[1]
                            preview = cv2.resize(preview, (int(preview.shape[1]*scale), int(preview.shape[0]*scale)))
                        from .analyze import _encode_frame
                        encoded = _encode_frame(preview)
                        await manager.broadcast({
                            'type': 'frame',
                            'image': encoded,
                            'width': preview.shape[1],
                            'height': preview.shape[0],
                            'frame_number': frame_num
                        })
                    except Exception as _:
                        # Non-fatal if preview encoding fails
                        pass

                # Always update MJPEG buffer (downscale like preview)
                try:
                    import cv2
                    mjpeg_frame = frame
                    if mjpeg_frame.shape[1] > preview_max_width:
                        scale2 = preview_max_width / mjpeg_frame.shape[1]
                        mjpeg_frame = cv2.resize(mjpeg_frame, (int(mjpeg_frame.shape[1]*scale2), int(mjpeg_frame.shape[0]*scale2)))
                    ok, buf = cv2.imencode('.jpg', mjpeg_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                    if ok:
                        last_live_jpeg = buf.tobytes()
                except Exception:
                    pass

                # Check anomalies
                count = len(tracks)
                overcrowd_result = overcrowding.detect_overcrowding(count)
                if overcrowd_result['alert_triggered']:
                    await send_anomaly_alert('overcrowding', overcrowd_result, frame_num, _encode_frame(frame))

                active_track_ids = []
                for track in tracks:
                    track_id = track['id']
                    bbox = track['bbox']
                    active_track_ids.append(track_id)
                    center_x = (bbox[0] + bbox[2]) / 2
                    center_y = (bbox[1] + bbox[3]) / 2
                    center = (center_x, center_y)

                    loitering.update_track(track_id, center, frame_num)
                    loiter_result = loitering.detect_loitering(track_id)
                    if loiter_result['alert_triggered']:
                        await send_anomaly_alert('loitering', loiter_result, frame_num, _encode_frame(frame))

                    zone_result = zone_violation.detect_zone_violation(center, track_id=track_id)
                    if zone_result['alert_triggered']:
                        await send_anomaly_alert('zone_violation', zone_result, frame_num, _encode_frame(frame))

                    pose_keypoints = suspicious.extract_pose(frame, bbox)
                    if pose_keypoints is not None:
                        suspicious.update_pose_history(track_id, pose_keypoints)
                        if frame_num % 5 == 0:
                            activity_result = suspicious.detect_fight_like_motion(track_id=track_id)
                            # Derive subtype heuristics using proximity to nearest neighbor
                            try:
                                # Compute center distance to nearest other track
                                min_dist = None
                                for other in tracks:
                                    if other['id'] == track_id:
                                        continue
                                    ob = other['bbox']
                                    ox = (ob[0] + ob[2]) / 2
                                    oy = (ob[1] + ob[3]) / 2
                                    dx = ox - center_x
                                    dy = oy - center_y
                                    d = (dx*dx + dy*dy) ** 0.5
                                    if min_dist is None or d < min_dist:
                                        min_dist = d
                                subtype = 'fight'
                                if activity_result.get('is_suspicious'):
                                    arm_v = activity_result.get('arm_velocity', 0.0)
                                    max_v = activity_result.get('max_velocity', 0.0)
                                    mean_v = activity_result.get('mean_velocity', 0.0)
                                    frac_ex = activity_result.get('frac_exceed', 0.0)
                                    # Basic classification
                                    if max_v > suspicious.velocity_threshold and arm_v > suspicious.velocity_threshold * 1.2:
                                        subtype = 'fight'
                                    elif (min_dist is not None and min_dist < 60) and mean_v < suspicious.velocity_threshold * 0.4:
                                        subtype = 'intimacy'
                                    elif arm_v > suspicious.velocity_threshold and (min_dist is not None and min_dist < 80):
                                        subtype = 'cruelty'
                                    else:
                                        subtype = 'suspicious'
                                    activity_result['subtype'] = subtype
                                    activity_result['nearest_distance'] = float(min_dist) if min_dist is not None else None
                                    # Compute reliability score and gate alerts to reduce false positives
                                    proximity_factor = 1.0 if (min_dist is not None and min_dist < 80) else 0.6
                                    motion_factor = min(1.0, (max_v / (suspicious.velocity_threshold * 1.2)) * 0.5 + (arm_v / (suspicious.velocity_threshold * 1.2)) * 0.5)
                                    spread_factor = min(1.0, frac_ex / 0.35)
                                    reliability = max(0.0, min(1.0, 0.4 * motion_factor + 0.4 * spread_factor + 0.2 * proximity_factor))
                                    activity_result['reliability'] = float(reliability)
                                    # Gate alert: require higher reliability for fight/cruelty; intimacy never alerts; generic suspicious needs moderate reliability
                                    should_alert = False
                                    if subtype == 'fight':
                                        should_alert = reliability >= 0.6 and (min_dist is not None and min_dist < 120)
                                    elif subtype == 'cruelty':
                                        should_alert = reliability >= 0.6 and (min_dist is not None and min_dist < 140)
                                    elif subtype == 'intimacy':
                                        should_alert = False  # do not alert intimacy as violation unless policy changes
                                    else:
                                        should_alert = reliability >= 0.5
                                    activity_result['alert_triggered'] = bool(should_alert)
                                if activity_result['alert_triggered']:
                                    await send_anomaly_alert('suspicious_activity', activity_result, frame_num, _encode_frame(frame))
                            except Exception:
                                if activity_result['alert_triggered']:
                                    await send_anomaly_alert('suspicious_activity', activity_result, frame_num, _encode_frame(frame))

                loitering.cleanup_old_tracks(active_track_ids)
                suspicious.cleanup_old_tracks(active_track_ids)

                # Small async sleep to yield control; adapt to FPS if needed
                await asyncio.sleep(0)
    except asyncio.CancelledError:
        logger.info('Live stream task cancelled.')
        last_live_jpeg = None
    except Exception as e:
        logger.error(f'Live stream error: {e}', exc_info=True)
        await manager.broadcast({'type': 'error', 'message': f'Live stream error: {e}'})
