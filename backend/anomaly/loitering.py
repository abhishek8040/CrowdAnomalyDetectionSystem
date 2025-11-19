"""
Loitering Detection Module
Detects when people stay in one location for too long
"""
import numpy as np
from typing import Dict, List, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class LoiteringDetector:
    """Detects loitering behavior based on movement history"""
    
    def __init__(self, pixel_threshold: float = 50.0, time_threshold: int = 300, fps: int = 30):
        """
        Initialize loitering detector
        
        Args:
            pixel_threshold: Maximum pixel movement to consider stationary
            time_threshold: Time in seconds before flagging as loitering
            fps: Frames per second of video
        """
        self.pixel_threshold = pixel_threshold
        self.time_threshold = time_threshold
        self.fps = fps
        self.frame_threshold = time_threshold * fps
        
        # Track history: {track_id: [(x, y, frame_num), ...]}
        self.track_history = defaultdict(list)
        self.loitering_tracks = set()
        
    def update_track(self, track_id: int, center_point: Tuple[float, float], frame_num: int):
        """
        Update track history with new position
        
        Args:
            track_id: Unique track identifier
            center_point: (x, y) center coordinates
            frame_num: Current frame number
        """
        self.track_history[track_id].append((center_point[0], center_point[1], frame_num))
        
        # Keep only recent history (last time_threshold seconds)
        max_history = self.frame_threshold + 100  # Keep some buffer
        if len(self.track_history[track_id]) > max_history:
            self.track_history[track_id] = self.track_history[track_id][-max_history:]
    
    def detect_loitering(self, track_id: int, history: List[Tuple] = None, 
                        pixel_threshold: float = None, time_threshold: int = None) -> Dict:
        """
        Detect if a track is loitering
        
        Args:
            track_id: Track ID to check
            history: Optional override for track history
            pixel_threshold: Override default pixel threshold
            time_threshold: Override default time threshold (in frames)
            
        Returns:
            Dictionary with loitering detection results
        """
        active_pixel_threshold = pixel_threshold if pixel_threshold is not None else self.pixel_threshold
        active_time_threshold = time_threshold if time_threshold is not None else self.frame_threshold
        
        # Use provided history or stored history
        track_positions = history if history is not None else self.track_history.get(track_id, [])
        
        if len(track_positions) < active_time_threshold:
            return {
                'is_loitering': False,
                'track_id': track_id,
                'duration_frames': len(track_positions),
                'movement_distance': 0.0,
                'alert_triggered': False
            }
        
        # Check movement over the threshold period
        recent_positions = track_positions[-int(active_time_threshold):]
        
        # Calculate total movement
        total_movement = self._calculate_movement(recent_positions)
        
        # Check if movement is below threshold
        is_loitering = total_movement < active_pixel_threshold
        
        # Trigger alert on state change
        alert_triggered = False
        if is_loitering and track_id not in self.loitering_tracks:
            alert_triggered = True
            self.loitering_tracks.add(track_id)
            logger.warning(f"Loitering detected for track {track_id}: movement={total_movement:.2f}px over {len(recent_positions)} frames")
        elif not is_loitering and track_id in self.loitering_tracks:
            self.loitering_tracks.remove(track_id)
        
        return {
            'is_loitering': is_loitering,
            'track_id': track_id,
            'duration_frames': len(recent_positions),
            'duration_seconds': len(recent_positions) / self.fps,
            'movement_distance': total_movement,
            'alert_triggered': alert_triggered,
            'position': recent_positions[-1][:2] if recent_positions else None
        }
    
    @staticmethod
    def _calculate_movement(positions: List[Tuple]) -> float:
        """
        Calculate total movement distance
        
        Args:
            positions: List of (x, y, frame) tuples
            
        Returns:
            Total Euclidean distance moved
        """
        if len(positions) < 2:
            return 0.0
        
        # Calculate max displacement from mean position
        coords = np.array([(p[0], p[1]) for p in positions])
        mean_pos = np.mean(coords, axis=0)
        
        # Calculate maximum distance from mean
        distances = np.sqrt(np.sum((coords - mean_pos) ** 2, axis=1))
        max_distance = np.max(distances)
        
        return float(max_distance)
    
    def cleanup_old_tracks(self, active_track_ids: List[int]):
        """
        Remove history for tracks that are no longer active
        
        Args:
            active_track_ids: List of currently active track IDs
        """
        all_track_ids = list(self.track_history.keys())
        for track_id in all_track_ids:
            if track_id not in active_track_ids:
                del self.track_history[track_id]
                self.loitering_tracks.discard(track_id)
