"""
Fall Detection Module
Detects sudden falls or a person lying on the ground using bounding box aspect ratio,
centroid kinematics, and optional pose inclination.
"""
import numpy as np
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class FallDetector:
    """
    Detects falls and persons lying down using temporal bounding box analysis
    and pose orientation.
    """
    
    def __init__(
        self,
        aspect_ratio_threshold: float = 1.05,
        fall_velocity_threshold: float = 12.0,
        confirmation_frames: int = 10,
        fps: int = 30
    ):
        """
        Initialize Fall Detector.
        
        Args:
            aspect_ratio_threshold: Width/Height ratio indicating horizontal orientation (w > h)
            fall_velocity_threshold: Downward centroid velocity (pixels/frame) indicating collapse
            confirmation_frames: Number of consecutive frames lying down to confirm a fall
            fps: Frame rate
        """
        self.aspect_ratio_threshold = aspect_ratio_threshold
        self.fall_velocity_threshold = fall_velocity_threshold
        self.confirmation_frames = confirmation_frames
        self.fps = fps
        
        # Track history: {track_id: [{'bbox': [x1,y1,x2,y2], 'cy': float, 'ar': float, 'frame': int}]}
        self.track_history = defaultdict(list)
        # Fall state per track: {track_id: {'down_frames': int, 'alerted': bool}}
        self.fall_state = defaultdict(lambda: {'down_frames': 0, 'alerted': False})
        
    def update_and_detect(
        self,
        track_id: int,
        bbox: List[float],
        frame_number: int,
        pose_landmarks: Optional[np.ndarray] = None
    ) -> Dict:
        """
        Update track state and evaluate for fall / collapse anomaly.
        
        Args:
            track_id: Unique tracking identifier
            bbox: [x1, y1, x2, y2]
            frame_number: Current frame index
            pose_landmarks: Optional MediaPipe pose landmark coordinates (33, 3)
            
        Returns:
            Detection dictionary with 'is_fall', 'alert_triggered', and diagnostic metrics
        """
        w = max(1.0, bbox[2] - bbox[0])
        h = max(1.0, bbox[3] - bbox[1])
        aspect_ratio = w / h  # > 1 means wider than tall
        cy = (bbox[1] + bbox[3]) / 2.0
        
        hist = self.track_history[track_id]
        
        # Calculate downward velocity if previous state exists
        downward_velocity = 0.0
        if hist:
            prev_cy = hist[-1]['cy']
            downward_velocity = cy - prev_cy  # Positive means moving down
            
        hist.append({
            'bbox': bbox,
            'cy': cy,
            'ar': aspect_ratio,
            'frame': frame_number
        })
        if len(hist) > 60:
            hist.pop(0)
            
        # Pose-based inclination check (if available)
        pose_horizontal = False
        if pose_landmarks is not None and len(pose_landmarks) >= 25:
            # 11: left shoulder, 12: right shoulder, 23: left hip, 24: right hip
            try:
                shoulder_y = (pose_landmarks[11][1] + pose_landmarks[12][1]) / 2.0
                hip_y = (pose_landmarks[23][1] + pose_landmarks[24][1]) / 2.0
                shoulder_x = (pose_landmarks[11][0] + pose_landmarks[12][0]) / 2.0
                hip_x = (pose_landmarks[23][0] + pose_landmarks[24][0]) / 2.0
                
                dx = abs(shoulder_x - hip_x)
                dy = abs(shoulder_y - hip_y)
                angle_deg = np.degrees(np.arctan2(dy, dx + 1e-6))
                if angle_deg < 35.0:  # Torso is within 35 degrees of horizontal
                    pose_horizontal = True
            except Exception:
                pass
                
        # Condition for being in a fallen / horizontal pose
        is_lying_down = (aspect_ratio >= self.aspect_ratio_threshold) or pose_horizontal
        
        # Check historical downward motion in the last 15 frames
        had_downward_spike = False
        if len(hist) >= 3:
            recent_vels = [
                hist[i]['cy'] - hist[i-1]['cy']
                for i in range(max(1, len(hist) - 15), len(hist))
            ]
            if recent_vels and max(recent_vels) >= self.fall_velocity_threshold:
                had_downward_spike = True
                
        state = self.fall_state[track_id]
        if is_lying_down:
            state['down_frames'] += 1
        else:
            state['down_frames'] = max(0, state['down_frames'] - 2)
            
        is_confirmed_fall = (state['down_frames'] >= self.confirmation_frames)
        alert_triggered = False
        
        if is_confirmed_fall and not state['alerted']:
            state['alerted'] = True
            alert_triggered = True
            logger.warning(
                f"Fall / collapse detected for track {track_id} at frame {frame_number} "
                f"(aspect_ratio={aspect_ratio:.2f}, down_frames={state['down_frames']})"
            )
        elif not is_lying_down and state['down_frames'] == 0:
            state['alerted'] = False
            
        confidence = 0.85 if pose_horizontal else (0.75 if had_downward_spike else 0.65)
        
        return {
            'is_fall': is_confirmed_fall,
            'track_id': track_id,
            'aspect_ratio': float(aspect_ratio),
            'downward_velocity': float(downward_velocity),
            'down_frames': state['down_frames'],
            'pose_horizontal': pose_horizontal,
            'had_downward_spike': had_downward_spike,
            'alert_triggered': alert_triggered,
            'severity': 'high' if is_confirmed_fall else 'none',
            'confidence': float(confidence) if is_confirmed_fall else 0.0
        }
        
    def cleanup_old_tracks(self, active_track_ids: List[int]):
        """Remove history for inactive tracks"""
        all_ids = list(self.track_history.keys())
        for tid in all_ids:
            if tid not in active_track_ids:
                del self.track_history[tid]
                if tid in self.fall_state:
                    del self.fall_state[tid]
