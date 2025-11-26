"""
Suspicious Activity Detection Module
Detects fight-like anomalies using pose estimation
"""
import cv2
import numpy as np
import mediapipe as mp
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class SuspiciousActivityDetector:
    """Detects suspicious activities like fights using pose estimation"""
    
    def __init__(self, velocity_threshold: float = 15.0, min_frames: int = 10):
        """
        Initialize suspicious activity detector
        
        Args:
            velocity_threshold: Threshold for joint velocity to detect rapid movement
            min_frames: Minimum frames to analyze for pattern detection
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
        Extract pose keypoints from person bounding box
        
        Args:
            frame: Input frame
            bbox: Bounding box [x1, y1, x2, y2]
            
        Returns:
            Keypoints array of shape (33, 3) or None if detection fails
        """
        x1, y1, x2, y2 = map(int, bbox)
        
        # Ensure valid crop
        h, w = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        
        if x2 <= x1 or y2 <= y1:
            return None
        
        person_crop = frame[y1:y2, x1:x2]
        
        if person_crop.size == 0:
            return None
        
        # Convert BGR to RGB
        person_rgb = cv2.cvtColor(person_crop, cv2.COLOR_BGR2RGB)
        
        # Process with MediaPipe
        results = self.pose.process(person_rgb)
        
        if results.pose_landmarks:
            # Extract keypoints and convert to pixel coordinates in original frame space
            keypoints = []
            crop_w = max(1, x2 - x1)
            crop_h = max(1, y2 - y1)
            for landmark in results.pose_landmarks.landmark:
                # landmark.x/y are normalized [0,1] within the crop
                x_px = x1 + float(landmark.x) * crop_w
                y_px = y1 + float(landmark.y) * crop_h
                keypoints.append([x_px, y_px, float(landmark.visibility)])
            return np.array(keypoints)
        
        return None
    
    def update_pose_history(self, track_id: int, keypoints: np.ndarray):
        """
        Update pose history for a track
        
        Args:
            track_id: Track identifier
            keypoints: Pose keypoints
        """
        self.pose_history[track_id].append(keypoints)
        
        # Keep only recent history
        max_history = 100
        if len(self.pose_history[track_id]) > max_history:
            self.pose_history[track_id] = self.pose_history[track_id][-max_history:]
    
    def detect_fight_like_motion(self, keypoints_sequence: List[np.ndarray] = None,
                                 velocity_thresholds: float = None,
                                 track_id: int = None) -> Dict:
        """
        Detect fight-like motion based on joint velocities
        
        Args:
            keypoints_sequence: Sequence of keypoints over time
            velocity_thresholds: Override default velocity threshold
            track_id: Track ID to analyze
            
        Returns:
            Dictionary with detection results
        """
        active_threshold = velocity_thresholds if velocity_thresholds is not None else self.velocity_threshold
        
        # Use provided sequence or stored history
        if keypoints_sequence is None and track_id is not None:
            keypoints_sequence = self.pose_history.get(track_id, [])
        elif keypoints_sequence is None:
            return {'is_suspicious': False, 'alert_triggered': False}
        
        if len(keypoints_sequence) < self.min_frames:
            return {
                'is_suspicious': False,
                'track_id': track_id,
                'frames_analyzed': len(keypoints_sequence),
                'alert_triggered': False
            }
        
        # Calculate joint velocities
        velocities = self._calculate_joint_velocities(keypoints_sequence[-self.min_frames:])
        
        # Analyze for suspicious patterns
        max_velocity = np.max(velocities) if len(velocities) > 0 else 0.0
        mean_velocity = np.mean(velocities) if len(velocities) > 0 else 0.0

        # Fraction of joint transitions exceeding threshold
        frac_exceed = float(np.mean(velocities > active_threshold)) if len(velocities) > 0 else 0.0
        
        # Check for specific joint movements (arms)
        arm_indices = [11, 12, 13, 14, 15, 16]  # Shoulders, elbows, wrists
        arm_velocities = self._calculate_specific_joint_velocities(
            keypoints_sequence[-self.min_frames:], arm_indices
        )
        arm_velocity = float(np.mean(arm_velocities)) if len(arm_velocities) > 0 else 0.0

        # Stricter detection combining magnitude and spread across joints
        # Require both high max and sufficient fraction of joints exceeding threshold
        is_suspicious = (max_velocity > active_threshold * 1.2 and
                 mean_velocity > active_threshold * 0.6 and
                 frac_exceed >= 0.25) or (arm_velocity > active_threshold * 1.4 and frac_exceed >= 0.2)
        
        # Track alerts
        alert_triggered = False
        if track_id is not None:
            if is_suspicious and track_id not in self.suspicious_tracks:
                alert_triggered = True
                self.suspicious_tracks.add(track_id)
                logger.warning(f"Suspicious activity detected for track {track_id}: max_vel={max_velocity:.2f}, arm_vel={arm_velocity:.2f}")
            elif not is_suspicious and track_id in self.suspicious_tracks:
                self.suspicious_tracks.remove(track_id)
        
        return {
            'is_suspicious': is_suspicious,
            'track_id': track_id,
            'max_velocity': float(max_velocity),
            'mean_velocity': float(mean_velocity),
            'arm_velocity': float(arm_velocity),
            'frac_exceed': float(frac_exceed),
            'frames_analyzed': len(keypoints_sequence),
            'alert_triggered': alert_triggered,
            'activity_type': 'fight_like' if is_suspicious else 'normal'
        }
    
    @staticmethod
    def _calculate_joint_velocities(keypoints_sequence: List[np.ndarray]) -> np.ndarray:
        """
        Calculate velocities of all joints
        
        Args:
            keypoints_sequence: List of keypoint arrays
            
        Returns:
            Array of velocities
        """
        if len(keypoints_sequence) < 2:
            return np.array([])
        
        velocities = []
        
        for i in range(1, len(keypoints_sequence)):
            prev_kp = keypoints_sequence[i - 1]
            curr_kp = keypoints_sequence[i]
            
            # Calculate Euclidean distance for each joint
            diff = curr_kp[:, :2] - prev_kp[:, :2]  # Only x, y coordinates
            dist = np.linalg.norm(diff, axis=1)
            
            # Weight by visibility
            visibility = (prev_kp[:, 2] + curr_kp[:, 2]) / 2.0
            weighted_dist = dist * visibility
            
            velocities.extend(weighted_dist)
        
        return np.array(velocities)
    
    @staticmethod
    def _calculate_specific_joint_velocities(keypoints_sequence: List[np.ndarray],
                                            joint_indices: List[int]) -> np.ndarray:
        """
        Calculate velocities for specific joints
        
        Args:
            keypoints_sequence: List of keypoint arrays
            joint_indices: Indices of joints to analyze
            
        Returns:
            Array of velocities for specified joints
        """
        if len(keypoints_sequence) < 2:
            return np.array([])
        
        velocities = []
        
        for i in range(1, len(keypoints_sequence)):
            prev_kp = keypoints_sequence[i - 1]
            curr_kp = keypoints_sequence[i]
            
            for joint_idx in joint_indices:
                if joint_idx < len(prev_kp):
                    diff = curr_kp[joint_idx, :2] - prev_kp[joint_idx, :2]
                    dist = np.linalg.norm(diff)
                    visibility = (prev_kp[joint_idx, 2] + curr_kp[joint_idx, 2]) / 2.0
                    velocities.append(dist * visibility)
        
        return np.array(velocities)
    
    def cleanup_old_tracks(self, active_track_ids: List[int]):
        """Remove history for inactive tracks"""
        all_track_ids = list(self.pose_history.keys())
        for track_id in all_track_ids:
            if track_id not in active_track_ids:
                del self.pose_history[track_id]
                self.suspicious_tracks.discard(track_id)
