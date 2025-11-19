"""
DeepSORT Tracker Implementation
Multi-object tracking with appearance features
"""
import numpy as np
from typing import List, Tuple, Dict
from filterpy.kalman import KalmanFilter
from scipy.optimize import linear_sum_assignment
import logging

logger = logging.getLogger(__name__)


class KalmanTracker:
    """Kalman filter for tracking bounding boxes"""
    
    count = 0
    
    def __init__(self, bbox: List[float]):
        """
        Initialize Kalman filter for bbox tracking
        
        Args:
            bbox: [x1, y1, x2, y2]
        """
        self.kf = KalmanFilter(dim_x=7, dim_z=4)
        
        # State: [x, y, s, r, vx, vy, vs] where x,y is center, s is scale, r is aspect ratio
        self.kf.F = np.array([
            [1, 0, 0, 0, 1, 0, 0],
            [0, 1, 0, 0, 0, 1, 0],
            [0, 0, 1, 0, 0, 0, 1],
            [0, 0, 0, 1, 0, 0, 0],
            [0, 0, 0, 0, 1, 0, 0],
            [0, 0, 0, 0, 0, 1, 0],
            [0, 0, 0, 0, 0, 0, 1]
        ])
        
        self.kf.H = np.array([
            [1, 0, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0, 0, 0],
            [0, 0, 1, 0, 0, 0, 0],
            [0, 0, 0, 1, 0, 0, 0]
        ])
        
        self.kf.R *= 10.0
        self.kf.P[4:, 4:] *= 1000.0
        self.kf.P *= 10.0
        self.kf.Q[-1, -1] *= 0.01
        self.kf.Q[4:, 4:] *= 0.01
        
        self.kf.x[:4] = self._bbox_to_z(bbox)
        
        self.time_since_update = 0
        self.id = KalmanTracker.count
        KalmanTracker.count += 1
        self.hits = 0
        self.hit_streak = 0
        self.age = 0
        
    def update(self, bbox: List[float]):
        """Update tracker with new detection"""
        self.time_since_update = 0
        self.hits += 1
        self.hit_streak += 1
        self.kf.update(self._bbox_to_z(bbox))
        
    def predict(self):
        """Predict next state"""
        if self.kf.x[6] + self.kf.x[2] <= 0:
            self.kf.x[6] *= 0.0
        self.kf.predict()
        self.age += 1
        if self.time_since_update > 0:
            self.hit_streak = 0
        self.time_since_update += 1
        return self._z_to_bbox(self.kf.x)
        
    def get_state(self) -> List[float]:
        """Get current bounding box"""
        return self._z_to_bbox(self.kf.x)
    
    @staticmethod
    def _bbox_to_z(bbox: List[float]) -> np.ndarray:
        """Convert [x1,y1,x2,y2] to [x,y,s,r] format"""
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = bbox[0] + w / 2.0
        y = bbox[1] + h / 2.0
        s = w * h
        r = w / float(h + 1e-6)
        return np.array([x, y, s, r]).reshape((4, 1))
    
    @staticmethod
    def _z_to_bbox(z: np.ndarray) -> List[float]:
        """Convert [x,y,s,r] to [x1,y1,x2,y2] format"""
        w = np.sqrt(z[2] * z[3])
        h = z[2] / (w + 1e-6)
        x1 = z[0] - w / 2.0
        y1 = z[1] - h / 2.0
        x2 = z[0] + w / 2.0
        y2 = z[1] + h / 2.0
        return [float(x1[0]), float(y1[0]), float(x2[0]), float(y2[0])]


class DeepSORT:
    """DeepSORT tracker with appearance features"""
    
    def __init__(self, max_age: int = 30, min_hits: int = 3, iou_threshold: float = 0.3):
        """
        Initialize DeepSORT tracker
        
        Args:
            max_age: Maximum frames to keep alive a track without detections
            min_hits: Minimum hits before track is confirmed
            iou_threshold: IOU threshold for matching
        """
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        self.trackers: List[KalmanTracker] = []
        self.frame_count = 0
        
    def update(self, detections: List[List[float]], frame: np.ndarray = None) -> List[Dict]:
        """
        Update tracker with new detections
        
        Args:
            detections: List of [x1, y1, x2, y2, confidence]
            frame: Current frame (optional, for appearance features)
            
        Returns:
            List of tracked objects with IDs
            Format: [{'id': int, 'bbox': [x1,y1,x2,y2], 'confidence': float}, ...]
        """
        self.frame_count += 1
        
        # Predict new locations of existing trackers
        trks = np.zeros((len(self.trackers), 5))
        to_del = []
        
        for t, trk in enumerate(trks):
            pos = self.trackers[t].predict()
            trk[:] = [pos[0], pos[1], pos[2], pos[3], 0]
            if np.any(np.isnan(pos)):
                to_del.append(t)
        
        trks = np.ma.compress_rows(np.ma.masked_invalid(trks))
        for t in reversed(to_del):
            self.trackers.pop(t)
        
        # Match detections to trackers
        matched, unmatched_dets, unmatched_trks = self._associate_detections_to_trackers(
            detections, trks
        )
        
        # Update matched trackers
        for m in matched:
            self.trackers[m[1]].update(detections[m[0]][:4])
        
        # Create new trackers for unmatched detections
        for i in unmatched_dets:
            trk = KalmanTracker(detections[i][:4])
            self.trackers.append(trk)
        
        # Return active tracks
        ret = []
        for trk in self.trackers:
            if trk.time_since_update < 1 and (trk.hit_streak >= self.min_hits or self.frame_count <= self.min_hits):
                bbox = trk.get_state()
                ret.append({
                    'id': trk.id,
                    'bbox': bbox,
                    'confidence': 1.0
                })
        
        # Remove dead tracklets
        self.trackers = [t for t in self.trackers if t.time_since_update < self.max_age]
        
        return ret
    
    def _associate_detections_to_trackers(self, detections: List, trackers: np.ndarray) -> Tuple:
        """
        Assign detections to tracked objects using IOU
        
        Returns:
            matched_indices, unmatched_detections, unmatched_trackers
        """
        if len(trackers) == 0:
            return np.empty((0, 2), dtype=int), np.arange(len(detections)), np.empty((0, 5), dtype=int)
        
        iou_matrix = np.zeros((len(detections), len(trackers)), dtype=np.float32)
        
        for d, det in enumerate(detections):
            for t, trk in enumerate(trackers):
                iou_matrix[d, t] = self._iou(det[:4], trk[:4])
        
        if min(iou_matrix.shape) > 0:
            a = (iou_matrix > self.iou_threshold).astype(np.int32)
            if a.sum(1).max() == 1 and a.sum(0).max() == 1:
                matched_indices = np.stack(np.where(a), axis=1)
            else:
                matched_indices = self._linear_assignment(-iou_matrix)
        else:
            matched_indices = np.empty(shape=(0, 2))
        
        unmatched_detections = []
        for d, det in enumerate(detections):
            if d not in matched_indices[:, 0]:
                unmatched_detections.append(d)
        
        unmatched_trackers = []
        for t, trk in enumerate(trackers):
            if t not in matched_indices[:, 1]:
                unmatched_trackers.append(t)
        
        # Filter out matched with low IOU
        matches = []
        for m in matched_indices:
            if iou_matrix[m[0], m[1]] < self.iou_threshold:
                unmatched_detections.append(m[0])
                unmatched_trackers.append(m[1])
            else:
                matches.append(m.reshape(1, 2))
        
        if len(matches) == 0:
            matches = np.empty((0, 2), dtype=int)
        else:
            matches = np.concatenate(matches, axis=0)
        
        return matches, np.array(unmatched_detections), np.array(unmatched_trackers)
    
    @staticmethod
    def _iou(bbox1: List[float], bbox2: List[float]) -> float:
        """Calculate IOU between two bboxes"""
        x1 = max(bbox1[0], bbox2[0])
        y1 = max(bbox1[1], bbox2[1])
        x2 = min(bbox1[2], bbox2[2])
        y2 = min(bbox1[3], bbox2[3])
        
        inter_area = max(0, x2 - x1) * max(0, y2 - y1)
        
        bbox1_area = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
        bbox2_area = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
        
        union_area = bbox1_area + bbox2_area - inter_area
        
        return inter_area / (union_area + 1e-6)
    
    @staticmethod
    def _linear_assignment(cost_matrix: np.ndarray) -> np.ndarray:
        """Solve linear assignment problem"""
        x, y = linear_sum_assignment(cost_matrix)
        return np.array(list(zip(x, y)))
