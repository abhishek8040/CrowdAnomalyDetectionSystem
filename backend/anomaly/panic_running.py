"""
Panic & Running Motion Detection Module
Detects individual sprinting / running and collective panic / sudden crowd dispersion
using track velocity vectors and motion directionality.
"""
import numpy as np
from typing import Dict, List, Tuple
from collections import deque
import logging

logger = logging.getLogger(__name__)


class PanicRunningDetector:
    """
    Detects sudden acceleration, fast running, and collective panic dispersion
    across tracked persons.
    """
    
    def __init__(
        self,
        running_speed_threshold: float = 16.0,
        panic_min_people: int = 3,
        panic_fraction: float = 0.4,
        cooldown_frames: int = 45
    ):
        """
        Initialize Panic & Running detector.
        
        Args:
            running_speed_threshold: Speed (pixels/frame) to qualify as running
            panic_min_people: Minimum number of fast-moving people to declare crowd panic
            panic_fraction: Fraction of visible crowd that must be running for crowd panic
            cooldown_frames: Frames before a new panic alert can fire
        """
        self.running_speed_threshold = running_speed_threshold
        self.panic_min_people = panic_min_people
        self.panic_fraction = panic_fraction
        self.cooldown_frames = cooldown_frames
        
        self.last_panic_alert_frame = -9999
        self.running_tracks_alerted = set()
        
    def detect_motion_anomalies(
        self,
        tracks: List[Dict],
        frame_number: int
    ) -> Dict:
        """
        Analyze current tracks for running individuals and crowd panic motion.
        
        Args:
            tracks: List of active track dictionaries with 'id', 'bbox', 'speed', 'velocity'
            frame_number: Current frame index
            
        Returns:
            Dictionary with 'is_panic', 'running_count', 'running_track_ids', 'alert_triggered'
        """
        if not tracks:
            return {
                'is_panic': False,
                'is_running': False,
                'running_count': 0,
                'running_track_ids': [],
                'alert_triggered': False,
                'event_type': None
            }
            
        running_track_ids = []
        velocities = []
        
        for trk in tracks:
            speed = trk.get('speed', 0.0)
            tid = trk.get('id')
            if speed >= self.running_speed_threshold:
                running_track_ids.append(tid)
                vel = trk.get('velocity', (0.0, 0.0))
                velocities.append(vel)
                
        num_running = len(running_track_ids)
        total_people = len(tracks)
        fraction_running = num_running / float(total_people) if total_people > 0 else 0.0
        
        # Check for collective crowd panic
        is_panic = (
            num_running >= self.panic_min_people and
            (fraction_running >= self.panic_fraction or num_running >= 5)
        )
        
        alert_triggered = False
        event_subtype = None
        severity = 'none'
        confidence = 0.0
        
        if is_panic:
            event_subtype = 'panic_dispersion'
            severity = 'critical'
            confidence = min(1.0, 0.5 + 0.1 * num_running)
            if frame_number - self.last_panic_alert_frame > self.cooldown_frames:
                alert_triggered = True
                self.last_panic_alert_frame = frame_number
                logger.warning(
                    f"Crowd panic / sudden dispersion detected at frame {frame_number}! "
                    f"({num_running}/{total_people} persons running)"
                )
        elif num_running > 0:
            event_subtype = 'running'
            severity = 'medium'
            confidence = 0.75
            # Alert on new running individuals
            new_runners = [tid for tid in running_track_ids if tid not in self.running_tracks_alerted]
            if new_runners:
                alert_triggered = True
                self.running_tracks_alerted.update(new_runners)
                logger.info(f"Running individual(s) detected: IDs {new_runners} at frame {frame_number}")
                
        # Cleanup alerted running tracks that have slowed down or left
        active_ids = {trk.get('id') for trk in tracks}
        self.running_tracks_alerted = {
            tid for tid in self.running_tracks_alerted
            if tid in active_ids and tid in running_track_ids
        }
        
        return {
            'is_panic': is_panic,
            'is_running': num_running > 0,
            'running_count': num_running,
            'total_count': total_people,
            'running_track_ids': running_track_ids,
            'alert_triggered': alert_triggered,
            'event_type': event_subtype,
            'severity': severity,
            'confidence': float(confidence)
        }
