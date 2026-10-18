"""
Suspicious Activity & Physical Altercation Detection Module
Detects fighting, aggression, and violent physical altercations using MediaPipe Pose
combined with multi-person proxemics and temporal motion analysis.
"""
import cv2
import numpy as np
import mediapipe as mp
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class SuspiciousActivityDetector:
    """Detects physical altercations and violent motions with proxemic confirmation"""
    
    def __init__(self, velocity_threshold: float = 15.0, min_frames: int = 8):
        """
        Initialize suspicious activity detector.
        
        Args:
            velocity_threshold: Threshold for joint velocity to detect rapid movement
            min_frames: Minimum consecutive frames of pose history to analyze
        """
        self.velocity_threshold = velocity_threshold
        self.min_frames = min_frames
        
        # Initialize MediaPipe Pose
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # Track pose history: {track_id: [keypoints_sequence]}
        self.pose_history = defaultdict(list)
        self.suspicious_tracks = set()
        
    def extract_pose(self, frame: np.ndarray, bbox: List[float]) -> Optional[np.ndarray]:
        """
        Extract pose keypoints from person bounding box crop.
        
        Args:
            frame: Input frame (BGR)
            bbox: [x1, y1, x2, y2]
            
        Returns:
            Keypoints array of shape (33, 3) [x_px, y_px, visibility] or None
        """
        x1, y1, x2, y2 = map(int, bbox)
        h, w = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        
        if x2 <= x1 or y2 <= y1:
            return None
            
        person_crop = frame[y1:y2, x1:x2]
        if person_crop.size == 0:
            return None
            
        person_rgb = cv2.cvtColor(person_crop, cv2.COLOR_BGR2RGB)
        try:
            results = self.pose.process(person_rgb)
            if results.pose_landmarks:
                keypoints = []
                crop_w = max(1, x2 - x1)
                crop_h = max(1, y2 - y1)
                for landmark in results.pose_landmarks.landmark:
                    x_px = x1 + float(landmark.x) * crop_w
                    y_px = y1 + float(landmark.y) * crop_h
                    keypoints.append([x_px, y_px, float(landmark.visibility)])
                return np.array(keypoints, dtype=np.float32)
        except Exception as e:
            logger.debug(f"MediaPipe pose extraction failed: {e}")
            
        return None
    
    def update_pose_history(self, track_id: int, keypoints: np.ndarray):
        """Record pose keypoints for a track"""
        self.pose_history[track_id].append(keypoints)
        if len(self.pose_history[track_id]) > 60:
            self.pose_history[track_id].pop(0)
    
    def detect_fight_like_motion(
        self,
        track_id: int,
        all_tracks: Optional[List[Dict]] = None,
        keypoints_sequence: Optional[List[np.ndarray]] = None,
        velocity_threshold: Optional[float] = None
    ) -> Dict:
        """
        Analyze track for fight-like motion with multi-person proxemic verification.
        
        Args:
            track_id: ID of the primary track being analyzed
            all_tracks: Optional list of all current active tracks for proximity check
            keypoints_sequence: Optional manual override of keypoint sequence
            velocity_threshold: Optional override for velocity threshold
            
        Returns:
            Dictionary with altercation metrics, subtype, and alert flag
        """
        active_thresh = velocity_threshold if velocity_threshold is not None else self.velocity_threshold
        seq = keypoints_sequence if keypoints_sequence is not None else self.pose_history.get(track_id, [])
        
        if len(seq) < self.min_frames:
            return {
                'is_suspicious': False,
                'track_id': track_id,
                'frames_analyzed': len(seq),
                'alert_triggered': False,
                'activity_type': 'normal'
            }
            
        recent_seq = seq[-self.min_frames:]
        velocities = self._calculate_joint_velocities(recent_seq)
        
        max_vel = float(np.max(velocities)) if len(velocities) > 0 else 0.0
        mean_vel = float(np.mean(velocities)) if len(velocities) > 0 else 0.0
        frac_exceed = float(np.mean(velocities > active_thresh)) if len(velocities) > 0 else 0.0
        
        # Arm joints: 11-16 (shoulders, elbows, wrists)
        arm_indices = [11, 12, 13, 14, 15, 16]
        arm_velocities = self._calculate_specific_joint_velocities(recent_seq, arm_indices)
        arm_vel = float(np.mean(arm_velocities)) if len(arm_velocities) > 0 else 0.0
        
        # Motion magnitude check
        motion_elevated = (
            (max_vel > active_thresh * 1.2 and mean_vel > active_thresh * 0.5 and frac_exceed >= 0.2) or
            (arm_vel > active_thresh * 1.3 and frac_exceed >= 0.15)
        )
        
        # Proxemics: check distance to nearest other tracked person
        nearest_distance = None
        nearest_track_id = None
        if all_tracks:
            # Find primary track centroid
            my_centroid = None
            for trk in all_tracks:
                if trk.get('id') == track_id:
                    bbox = trk.get('bbox', [0, 0, 0, 0])
                    my_centroid = ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)
                    break
                    
            if my_centroid:
                min_d = float('inf')
                for other in all_tracks:
                    oid = other.get('id')
                    if oid == track_id:
                        continue
                    obbox = other.get('bbox', [0, 0, 0, 0])
                    oc = ((obbox[0] + obbox[2]) / 2.0, (obbox[1] + obbox[3]) / 2.0)
                    dist = np.sqrt((my_centroid[0] - oc[0])**2 + (my_centroid[1] - oc[1])**2)
                    if dist < min_d:
                        min_d = dist
                        nearest_track_id = oid
                if min_d != float('inf'):
                    nearest_distance = float(min_d)
                    
        # Subtype and alert gating
        # A true fight requires rapid motion AND proximity to another individual
        is_close_proximity = (nearest_distance is not None and nearest_distance <= 140.0)
        
        is_fight = motion_elevated and is_close_proximity
        is_solitary_rapid = motion_elevated and not is_close_proximity
        
        subtype = 'normal'
        severity = 'none'
        confidence = 0.0
        
        if is_fight:
            subtype = 'fight'
            severity = 'critical'
            confidence = min(1.0, 0.6 + 0.2 * frac_exceed + (0.2 if nearest_distance < 80 else 0.1))
        elif is_solitary_rapid:
            subtype = 'aggressive_motion'
            severity = 'medium'
            confidence = 0.65
            
        is_suspicious = is_fight or is_solitary_rapid
        alert_triggered = False
        
        # Only trigger alert for confirmed physical altercation (or operator custom rule)
        if is_fight and track_id not in self.suspicious_tracks:
            alert_triggered = True
            self.suspicious_tracks.add(track_id)
            logger.warning(
                f"Physical altercation detected between track {track_id} and nearest track {nearest_track_id}: "
                f"arm_vel={arm_vel:.1f}, dist={nearest_distance:.1f}px"
            )
        elif not is_suspicious and track_id in self.suspicious_tracks:
            self.suspicious_tracks.remove(track_id)
            
        return {
            'is_suspicious': is_suspicious,
            'is_fight': is_fight,
            'track_id': track_id,
            'nearest_track_id': nearest_track_id,
            'nearest_distance': nearest_distance,
            'max_velocity': float(max_vel),
            'mean_velocity': float(mean_vel),
            'arm_velocity': float(arm_vel),
            'frac_exceed': float(frac_exceed),
            'subtype': subtype,
            'severity': severity,
            'confidence': float(confidence),
            'alert_triggered': alert_triggered,
            'activity_type': subtype
        }
        
    @staticmethod
    def _calculate_joint_velocities(keypoints_sequence: List[np.ndarray]) -> np.ndarray:
        """Calculate joint Euclidean displacements weighted by visibility"""
        if len(keypoints_sequence) < 2:
            return np.array([], dtype=np.float32)
        vels = []
        for i in range(1, len(keypoints_sequence)):
            prev_kp = keypoints_sequence[i - 1]
            curr_kp = keypoints_sequence[i]
            diff = curr_kp[:, :2] - prev_kp[:, :2]
            dist = np.linalg.norm(diff, axis=1)
            vis = (prev_kp[:, 2] + curr_kp[:, 2]) / 2.0
            vels.extend(dist * vis)
        return np.array(vels, dtype=np.float32)
        
    @staticmethod
    def _calculate_specific_joint_velocities(keypoints_sequence: List[np.ndarray], joint_indices: List[int]) -> np.ndarray:
        """Calculate velocities for targeted joint indices"""
        if len(keypoints_sequence) < 2:
            return np.array([], dtype=np.float32)
        vels = []
        for i in range(1, len(keypoints_sequence)):
            prev_kp = keypoints_sequence[i - 1]
            curr_kp = keypoints_sequence[i]
            for idx in joint_indices:
                if idx < len(prev_kp):
                    diff = curr_kp[idx, :2] - prev_kp[idx, :2]
                    dist = np.linalg.norm(diff)
                    vis = (prev_kp[idx, 2] + curr_kp[idx, 2]) / 2.0
                    vels.append(dist * vis)
        return np.array(vels, dtype=np.float32)
        
    def cleanup_old_tracks(self, active_track_ids: List[int]):
        """Remove history for inactive tracks"""
        all_ids = list(self.pose_history.keys())
        for tid in all_ids:
            if tid not in active_track_ids:
                del self.pose_history[tid]
                self.suspicious_tracks.discard(tid)
