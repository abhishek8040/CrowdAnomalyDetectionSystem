"""
Loitering Detection Module
Detects when people remain within a localized spatial radius for extended durations.
"""
import numpy as np
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class LoiteringDetector:
    """Detects loitering behavior based on spatial radius and temporal duration"""
    
    def __init__(self, pixel_threshold: float = 50.0, time_threshold: int = 300, fps: int = 30):
        """
        Initialize loitering detector.
        
        Args:
            pixel_threshold: Maximum displacement radius (pixels) to consider stationary
            time_threshold: Duration in seconds before flagging as loitering
            fps: Video frames per second
        """
        self.pixel_threshold = pixel_threshold
        self.time_threshold = time_threshold
        self.fps = max(1, fps)
        self.frame_threshold = int(time_threshold * self.fps)
        
        # Track history: {track_id: [(x, y, frame_num, timestamp), ...]}
        self.track_history = defaultdict(list)
        self.loitering_tracks = set()
        
    def update_track(self, track_id: int, center_point: Tuple[float, float], frame_num: int):
        """
        Record position for a tracked individual.
        
        Args:
            track_id: Unique track ID
            center_point: (x, y) centroid coordinates
            frame_num: Current frame index
        """
        self.track_history[track_id].append((float(center_point[0]), float(center_point[1]), int(frame_num)))
        
        max_history = self.frame_threshold + 150
        if len(self.track_history[track_id]) > max_history:
            self.track_history[track_id] = self.track_history[track_id][-max_history:]
    
    def detect_loitering(
        self,
        track_id: int,
        history: Optional[List[Tuple]] = None,
        pixel_threshold: Optional[float] = None,
        time_threshold: Optional[int] = None
    ) -> Dict:
        """
        Evaluate if a track has remained stationary beyond duration threshold.
        
        Args:
            track_id: Track ID to inspect
            history: Optional override for track positions
            pixel_threshold: Optional radius override
            time_threshold: Optional duration override (seconds)
            
        Returns:
            Dictionary with loitering detection results
        """
        active_pixel_threshold = pixel_threshold if pixel_threshold is not None else self.pixel_threshold
        time_sec = time_threshold if time_threshold is not None else self.time_threshold
        active_frame_threshold = int(time_sec * self.fps)
        
        track_positions = history if history is not None else self.track_history.get(track_id, [])
        
        if len(track_positions) < active_frame_threshold:
            return {
                'is_loitering': False,
                'track_id': track_id,
                'duration_seconds': len(track_positions) / float(self.fps),
                'threshold_seconds': time_sec,
                'movement_distance': 0.0,
                'alert_triggered': False,
                'severity': 'none'
            }
        
        recent_positions = track_positions[-active_frame_threshold:]
        max_displacement = self._calculate_movement(recent_positions)
        is_loitering = max_displacement <= active_pixel_threshold
        
        alert_triggered = False
        duration_sec = len(recent_positions) / float(self.fps)
        
        if is_loitering and track_id not in self.loitering_tracks:
            alert_triggered = True
            self.loitering_tracks.add(track_id)
            logger.warning(
                f"Loitering confirmed for track {track_id}: displacement={max_displacement:.1f}px "
                f"<= threshold {active_pixel_threshold}px over {duration_sec:.1f}s"
            )
        elif not is_loitering and track_id in self.loitering_tracks:
            self.loitering_tracks.remove(track_id)
            
        # Determine severity
        severity = 'none'
        if is_loitering:
            if duration_sec >= time_sec * 2.0:
                severity = 'high'
            elif duration_sec >= time_sec * 1.5:
                severity = 'medium'
            else:
                severity = 'low'
        
        return {
            'is_loitering': is_loitering,
            'track_id': track_id,
            'duration_frames': len(recent_positions),
            'duration_seconds': float(duration_sec),
            'threshold_seconds': time_sec,
            'movement_distance': float(max_displacement),
            'alert_triggered': alert_triggered,
            'position': recent_positions[-1][:2] if recent_positions else None,
            'severity': severity,
            'confidence': 0.85 if is_loitering else 0.0
        }
    
    @staticmethod
    def _calculate_movement(positions: List[Tuple]) -> float:
        """Calculate max displacement from centroid center"""
        if len(positions) < 2:
            return 0.0
        coords = np.array([(p[0], p[1]) for p in positions], dtype=np.float32)
        mean_pos = np.mean(coords, axis=0)
        distances = np.linalg.norm(coords - mean_pos, axis=1)
        return float(np.max(distances))
    
    def cleanup_old_tracks(self, active_track_ids: List[int]):
        """Remove history for inactive tracks"""
        all_ids = list(self.track_history.keys())
        for tid in all_ids:
            if tid not in active_track_ids:
                del self.track_history[tid]
                self.loitering_tracks.discard(tid)
