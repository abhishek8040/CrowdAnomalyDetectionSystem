"""
Drive-by Snatching and Theft Anomaly Detection Module
Detects sudden drive-by theft and snatching incidents (e.g. motorcycle or bicycle
intercepting a pedestrian at close proximity and rapidly fleeing).
"""
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class SnatchingDetector:
    """
    Detects snatching / drive-by theft incidents using kinematic analysis:
    1. Fast or vehicular approach (motorcycle, bicycle, or fast runner).
    2. Close intercept proximity with a pedestrian / slow-moving individual.
    3. Rapid flee / escape phase with increasing separation distance.
    """

    def __init__(
        self,
        intercept_distance: float = 85.0,
        min_approach_speed: float = 6.0,
        min_escape_speed: float = 10.0,
        escape_distance_delta: float = 35.0,
        max_intercept_window: int = 35,
        cooldown_frames: int = 60
    ):
        """
        Args:
            intercept_distance: Max inter-centroid distance (px) to register an intercept.
            min_approach_speed: Speed threshold (px/f) to qualify as active approach.
            min_escape_speed: Speed threshold (px/f) for suspect escape velocity.
            escape_distance_delta: Minimum separation expansion (px) post-intercept.
            max_intercept_window: Maximum frames after intercept to evaluate escape.
            cooldown_frames: Cooldown frames between consecutive alerts for the same track pair.
        """
        self.intercept_distance = intercept_distance
        self.min_approach_speed = min_approach_speed
        self.min_escape_speed = min_escape_speed
        self.escape_distance_delta = escape_distance_delta
        self.max_intercept_window = max_intercept_window
        self.cooldown_frames = cooldown_frames

        # Interaction history per track pair:
        # key: (id_a, id_b) where id_a is suspect candidate, id_b is victim candidate
        # value: dict with intercept info, minimum distance, history
        self._interactions: Dict[Tuple[int, int], Dict[str, Any]] = {}

        # Alert cooldown tracking: (id_a, id_b) -> last_alert_frame
        self._cooldowns: Dict[Tuple[int, int], int] = {}

    def _get_centroid(self, bbox: List[float]) -> Tuple[float, float]:
        """Calculate centroid (cx, cy) from bbox [x1, y1, x2, y2]."""
        return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)

    def _euclidean_dist(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        """Euclidean distance between two 2D points."""
        return float(np.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2))

    def _is_vehicular_or_fast(self, track: Dict) -> bool:
        """Check if track is a motorcycle, bicycle, or fast-moving entity."""
        cname = track.get('class_name', 'person').lower()
        speed = track.get('speed', 0.0)
        return cname in ('motorcycle', 'bicycle') or speed >= self.min_approach_speed

    def update_and_detect(self, tracks: List[Dict], frame_num: int) -> Dict[str, Any]:
        """
        Evaluate all active tracks in the current frame for snatching / drive-by theft.

        Args:
            tracks: List of active track dictionaries with 'id', 'bbox', 'speed', 'class_name'
            frame_num: Current frame index

        Returns:
            Anomaly detection result dict
        """
        default_res = {
            'is_snatching': False,
            'alert_triggered': False,
            'suspect_id': None,
            'victim_id': None,
            'suspect_class': None,
            'victim_class': None,
            'suspect_speed': 0.0,
            'victim_speed': 0.0,
            'confidence': 0.0,
            'severity': 'critical',
            'message': '',
            'details': {}
        }

        if len(tracks) < 2:
            return default_res

        # Map tracks by id for quick lookup
        track_map = {t['id']: t for t in tracks}
        track_ids = list(track_map.keys())

        # Evaluate all ordered pairs (candidate_suspect, candidate_victim)
        for i in range(len(track_ids)):
            for j in range(len(track_ids)):
                if i == j:
                    continue

                s_id = track_ids[i]
                v_id = track_ids[j]
                pair_key = (s_id, v_id)

                s_track = track_map[s_id]
                v_track = track_map[v_id]

                s_class = s_track.get('class_name', 'person')
                v_class = v_track.get('class_name', 'person')
                s_speed = float(s_track.get('speed', 0.0))
                v_speed = float(v_track.get('speed', 0.0))

                s_center = self._get_centroid(s_track['bbox'])
                v_center = self._get_centroid(v_track['bbox'])
                dist = self._euclidean_dist(s_center, v_center)

                # Initialize or fetch interaction history
                if pair_key not in self._interactions:
                    self._interactions[pair_key] = {
                        'intercept_frame': None,
                        'min_intercept_dist': float('inf'),
                        'approach_speed': s_speed,
                        'history': []
                    }

                record = self._interactions[pair_key]
                record['history'].append({
                    'frame': frame_num,
                    'dist': dist,
                    's_speed': s_speed,
                    'v_speed': v_speed
                })
                if len(record['history']) > 60:
                    record['history'].pop(0)

                # Check if this frame is a close intercept
                if dist <= self.intercept_distance:
                    # Update minimum intercept distance
                    if dist < record['min_intercept_dist']:
                        record['min_intercept_dist'] = dist
                        record['intercept_frame'] = frame_num
                        record['approach_speed'] = max(record['approach_speed'], s_speed)

                # If an intercept was recorded in recent frames, evaluate escape phase
                intercept_f = record.get('intercept_frame')
                if intercept_f is not None:
                    frames_since_intercept = frame_num - intercept_f

                    if 1 <= frames_since_intercept <= self.max_intercept_window:
                        min_dist = record['min_intercept_dist']
                        dist_delta = dist - min_dist

                        # Criteria for drive-by snatching:
                        # 1. Separation expanded significantly from intercept point
                        # 2. Suspect speed meets escape threshold OR is motorcycle/bicycle moving fast
                        # 3. Suspect is significantly faster than victim
                        has_expanded = dist_delta >= self.escape_distance_delta
                        has_escape_speed = (s_speed >= self.min_escape_speed) or (
                            s_class in ('motorcycle', 'bicycle') and s_speed >= 7.0
                        )
                        suspect_faster = (s_speed >= v_speed * 1.5) or (s_speed >= 8.0 and v_speed <= 5.0)

                        if has_expanded and has_escape_speed and suspect_faster:
                            # Check cooldown
                            last_alert = self._cooldowns.get(pair_key, -999)
                            if (frame_num - last_alert) >= self.cooldown_frames:
                                self._cooldowns[pair_key] = frame_num

                                # Compute confidence
                                conf = 0.82
                                if s_class in ('motorcycle', 'bicycle'):
                                    conf += 0.12
                                elif record.get('approach_speed', 0.0) >= self.min_approach_speed:
                                    conf += 0.06

                                if v_speed <= 4.0:
                                    conf += 0.04
                                if s_speed >= 14.0:
                                    conf += 0.04
                                conf = min(0.98, conf)

                                msg = (
                                    f"Drive-by snatching detected: Track #{s_id} ({s_class}) "
                                    f"intercepted Track #{v_id} ({v_class}) at dist {round(min_dist, 1)}px "
                                    f"and fled at {round(s_speed, 1)} px/f."
                                )

                                logger.warning(f"ALERT [Frame {frame_num}]: {msg}")

                                return {
                                    'is_snatching': True,
                                    'alert_triggered': True,
                                    'suspect_id': s_id,
                                    'victim_id': v_id,
                                    'suspect_class': s_class,
                                    'victim_class': v_class,
                                    'suspect_speed': round(s_speed, 2),
                                    'victim_speed': round(v_speed, 2),
                                    'min_intercept_dist': round(min_dist, 1),
                                    'current_dist': round(dist, 1),
                                    'dist_delta': round(dist_delta, 1),
                                    'confidence': round(conf, 2),
                                    'severity': 'critical',
                                    'message': msg,
                                    'details': {
                                        'suspect_id': s_id,
                                        'victim_id': v_id,
                                        'suspect_class': s_class,
                                        'victim_class': v_class,
                                        'suspect_speed': round(s_speed, 2),
                                        'victim_speed': round(v_speed, 2),
                                        'intercept_frame': intercept_f,
                                        'frames_since_intercept': frames_since_intercept,
                                        'min_intercept_dist': round(min_dist, 1),
                                        'current_dist': round(dist, 1),
                                        'dist_delta': round(dist_delta, 1)
                                    }
                                }
                    elif frames_since_intercept > self.max_intercept_window:
                        # Reset intercept record if time expired without an escape snatch
                        record['intercept_frame'] = None
                        record['min_intercept_dist'] = float('inf')

        return default_res

    def cleanup_old_tracks(self, active_track_ids: List[int]):
        """Remove interaction data for tracks that are no longer active."""
        active_set = set(active_track_ids)
        to_del = [
            pair for pair in self._interactions
            if pair[0] not in active_set or pair[1] not in active_set
        ]
        for pair in to_del:
            del self._interactions[pair]

        to_del_cd = [
            pair for pair in self._cooldowns
            if pair[0] not in active_set or pair[1] not in active_set
        ]
        for pair in to_del_cd:
            del self._cooldowns[pair]
