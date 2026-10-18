"""
DeepSORT Tracker Implementation with Appearance Features & Tripwire Counting
Multi-object tracking with appearance re-identification, Kalman filtering,
velocity calculation, and entry/exit counting.
"""
import numpy as np
from typing import List, Tuple, Dict, Optional
from filterpy.kalman import KalmanFilter
from scipy.optimize import linear_sum_assignment
import logging

logger = logging.getLogger(__name__)


class KalmanTracker:
    """Kalman filter for tracking bounding boxes with appearance embedding history"""
    
    _counter = 0
    
    @classmethod
    def reset_counter(cls):
        cls._counter = 0
        
    def __init__(self, bbox: List[float], feature: Optional[np.ndarray] = None, class_name: str = 'person'):
        """
        Initialize Kalman filter for bbox tracking.
        
        Args:
            bbox: [x1, y1, x2, y2]
            feature: Initial appearance feature embedding (optional)
            class_name: Semantic class name (e.g. 'person', 'motorcycle', 'bicycle')
        """
        self.kf = KalmanFilter(dim_x=7, dim_z=4)
        self.class_name = class_name
        
        # State: [x, y, s, r, vx, vy, vs] where x,y is center, s is scale (area), r is aspect ratio
        self.kf.F = np.array([
            [1, 0, 0, 0, 1, 0, 0],
            [0, 1, 0, 0, 0, 1, 0],
            [0, 0, 1, 0, 0, 0, 1],
            [0, 0, 0, 1, 0, 0, 0],
            [0, 0, 0, 0, 1, 0, 0],
            [0, 0, 0, 0, 0, 1, 0],
            [0, 0, 0, 0, 0, 0, 1]
        ], dtype=np.float32)
        
        self.kf.H = np.array([
            [1, 0, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0, 0, 0],
            [0, 0, 1, 0, 0, 0, 0],
            [0, 0, 0, 1, 0, 0, 0]
        ], dtype=np.float32)
        
        self.kf.R[2:, 2:] *= 10.0
        self.kf.P[4:, 4:] *= 1000.0  # High uncertainty for initial velocities
        self.kf.P *= 10.0
        self.kf.Q[-1, -1] *= 0.01
        self.kf.Q[4:, 4:] *= 0.01
        
        self.kf.x[:4] = self._bbox_to_z(bbox)
        
        self.time_since_update = 0
        KalmanTracker._counter += 1
        self.id = KalmanTracker._counter
        self.hits = 1
        self.hit_streak = 1
        self.age = 0
        
        # Appearance feature smoothing (exponential moving average)
        self.features: List[np.ndarray] = []
        if feature is not None and feature.size > 0:
            self.features.append(feature / (np.linalg.norm(feature) + 1e-6))
            
        # Trajectory history for velocity and tripwire
        self.centroid_history: List[Tuple[float, float]] = []
        cx = (bbox[0] + bbox[2]) / 2.0
        cy = (bbox[1] + bbox[3]) / 2.0
        self.centroid_history.append((cx, cy))
        self.velocity = (0.0, 0.0)
        self.speed = 0.0
        
    def update(self, bbox: List[float], feature: Optional[np.ndarray] = None, class_name: Optional[str] = None):
        """Update tracker with new detection, appearance feature, and optional class name"""
        self.time_since_update = 0
        self.hits += 1
        self.hit_streak += 1
        if class_name:
            self.class_name = class_name
        self.kf.update(self._bbox_to_z(bbox))
        
        cx = (bbox[0] + bbox[2]) / 2.0
        cy = (bbox[1] + bbox[3]) / 2.0
        if self.centroid_history:
            prev_cx, prev_cy = self.centroid_history[-1]
            vx = cx - prev_cx
            vy = cy - prev_cy
            self.velocity = (vx, vy)
            self.speed = float(np.sqrt(vx**2 + vy**2))
            
        self.centroid_history.append((cx, cy))
        if len(self.centroid_history) > 60:
            self.centroid_history.pop(0)
            
        if feature is not None and feature.size > 0:
            norm_feat = feature / (np.linalg.norm(feature) + 1e-6)
            self.features.append(norm_feat)
            if len(self.features) > 10:
                self.features.pop(0)
        
    def predict(self) -> List[float]:
        """Predict next state and advance Kalman filter"""
        if self.kf.x[6] + self.kf.x[2] <= 0:
            self.kf.x[6] *= 0.0
            
        self.kf.predict()
        self.age += 1
        if self.time_since_update > 0:
            self.hit_streak = 0
        self.time_since_update += 1
        
        # Ensure non-negative scale
        if self.kf.x[2] < 1.0:
            self.kf.x[2] = 1.0
            
        predicted_bbox = self._z_to_bbox(self.kf.x)
        return predicted_bbox
        
    def get_state(self) -> List[float]:
        """Get current estimated bounding box"""
        return self._z_to_bbox(self.kf.x)
    
    def get_feature(self) -> Optional[np.ndarray]:
        """Get current representative appearance embedding"""
        if not self.features:
            return None
        return np.mean(self.features, axis=0)
    
    @staticmethod
    def _bbox_to_z(bbox: List[float]) -> np.ndarray:
        """Convert [x1, y1, x2, y2] to state vector [x, y, s, r]"""
        w = max(1.0, bbox[2] - bbox[0])
        h = max(1.0, bbox[3] - bbox[1])
        x = bbox[0] + w / 2.0
        y = bbox[1] + h / 2.0
        s = w * h
        r = w / (h + 1e-6)
        return np.array([x, y, s, r]).reshape((4, 1))
    
    @staticmethod
    def _z_to_bbox(z: np.ndarray) -> List[float]:
        """Convert state vector [x, y, s, r] to [x1, y1, x2, y2] with NaN safety"""
        try:
            s = float(z[2][0]) if hasattr(z[2], '__len__') else float(z[2])
            r = float(z[3][0]) if hasattr(z[3], '__len__') else float(z[3])
            x = float(z[0][0]) if hasattr(z[0], '__len__') else float(z[0])
            y = float(z[1][0]) if hasattr(z[1], '__len__') else float(z[1])
            
            s = max(1.0, s)
            r = max(0.01, min(100.0, r))
            
            prod = max(1.0, s * r)
            w = np.sqrt(prod)
            h = max(1.0, s / (w + 1e-6))
            
            x1 = x - w / 2.0
            y1 = y - h / 2.0
            x2 = x + w / 2.0
            y2 = y + h / 2.0
            
            coords = [float(x1), float(y1), float(x2), float(y2)]
            # Guard against NaNs or infinities
            if any(c != c or abs(c) > 1e9 for c in coords):
                return [0.0, 0.0, 10.0, 10.0]
                
            return coords
        except Exception:
            return [0.0, 0.0, 10.0, 10.0]


class DeepSORT:
    """
    Enhanced DeepSORT tracker with appearance re-identification,
    temporal stability, crowd density metrics, and tripwire line counting.
    """
    
    def __init__(
        self,
        max_age: int = 30,
        min_hits: int = 3,
        iou_threshold: float = 0.3,
        appearance_weight: float = 0.3
    ):
        """
        Initialize DeepSORT tracker.
        
        Args:
            max_age: Maximum frames to retain a track without detections
            min_hits: Minimum consecutive detections before track is confirmed
            iou_threshold: Minimum spatial IoU for valid assignment
            appearance_weight: Weight given to appearance distance vs spatial IoU [0.0, 1.0]
        """
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        self.appearance_weight = appearance_weight
        self.trackers: List[KalmanTracker] = []
        self.frame_count = 0
        
        # Tripwire line for entry/exit counting: ((x1, y1), (x2, y2))
        self.tripwire: Optional[Tuple[Tuple[float, float], Tuple[float, float]]] = None
        self.entry_count = 0
        self.exit_count = 0
        self._crossed_tracks = set()  # (track_id, direction)
        
    def set_tripwire(self, p1: Tuple[float, float], p2: Tuple[float, float]):
        """Set a virtual tripwire line for bidirectional entry/exit counting"""
        self.tripwire = (p1, p2)
        logger.info(f"Tripwire configured from {p1} to {p2}")
        
    def reset_counts(self):
        """Reset entry/exit counters"""
        self.entry_count = 0
        self.exit_count = 0
        self._crossed_tracks.clear()
        
    def update(
        self,
        detections: List[List[float]],
        frame: Optional[np.ndarray] = None,
        features: Optional[np.ndarray] = None
    ) -> List[Dict]:
        """
        Update tracker with new detections.
        
        Args:
            detections: List of [x1, y1, x2, y2, confidence]
            frame: Current image frame (optional)
            features: Optional appearance feature embeddings (N, D)
            
        Returns:
            List of confirmed active tracks:
            [{'id': int, 'bbox': [x1,y1,x2,y2], 'confidence': float, 'velocity': (vx, vy), 'speed': float}, ...]
        """
        self.frame_count += 1
        
        # Step 1: Predict positions for existing trackers
        to_del = []
        predicted_boxes = []
        for t, trk in enumerate(self.trackers):
            pos = trk.predict()
            if any(np.isnan(pos)) or any(np.isinf(pos)):
                to_del.append(t)
            else:
                predicted_boxes.append(pos)
                
        for t in reversed(to_del):
            self.trackers.pop(t)
            
        # Step 2: Associate detections to trackers using spatial + appearance distance
        matched, unmatched_dets, unmatched_trks = self._associate(
            detections, self.trackers, features
        )
        
        # Step 3: Update matched trackers
        for d_idx, t_idx in matched:
            feat = features[d_idx] if (features is not None and d_idx < len(features)) else None
            det_class = detections[d_idx][6] if len(detections[d_idx]) > 6 else 'person'
            self.trackers[t_idx].update(detections[d_idx][:4], feature=feat, class_name=det_class)
            
        # Step 4: Initialize new trackers for unmatched detections
        for d_idx in unmatched_dets:
            feat = features[d_idx] if (features is not None and d_idx < len(features)) else None
            det_class = detections[d_idx][6] if len(detections[d_idx]) > 6 else 'person'
            trk = KalmanTracker(detections[d_idx][:4], feature=feat, class_name=det_class)
            self.trackers.append(trk)
            
        # Step 5: Extract active confirmed tracks and evaluate tripwire
        active_tracks = []
        for trk in self.trackers:
            if trk.time_since_update < 1 and (trk.hit_streak >= self.min_hits or self.frame_count <= self.min_hits):
                bbox = trk.get_state()
                track_info = {
                    'id': trk.id,
                    'bbox': bbox,
                    'confidence': 1.0,
                    'velocity': trk.velocity,
                    'speed': trk.speed,
                    'centroid': trk.centroid_history[-1] if trk.centroid_history else (0.0, 0.0),
                    'class_name': getattr(trk, 'class_name', 'person'),
                    'trajectory': list(trk.centroid_history)
                }
                active_tracks.append(track_info)
                
                # Check tripwire crossing
                if self.tripwire and len(trk.centroid_history) >= 2:
                    self._check_tripwire(trk)
                    
        # Step 6: Prune dead tracks
        self.trackers = [t for t in self.trackers if t.time_since_update < self.max_age]
        
        return active_tracks
        
    def _associate(
        self,
        detections: List[List[float]],
        trackers: List[KalmanTracker],
        features: Optional[np.ndarray] = None
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Associate detections to trackers using a combined spatial (IoU) and appearance cost matrix.
        """
        if len(trackers) == 0:
            return np.empty((0, 2), dtype=int), np.arange(len(detections)), np.empty(0, dtype=int)
        if len(detections) == 0:
            return np.empty((0, 2), dtype=int), np.empty(0, dtype=int), np.arange(len(trackers))
            
        cost_matrix = np.zeros((len(detections), len(trackers)), dtype=np.float32)
        iou_matrix = np.zeros((len(detections), len(trackers)), dtype=np.float32)
        
        for d, det in enumerate(detections):
            for t, trk in enumerate(trackers):
                trk_box = trk.get_state()
                iou = self._iou(det[:4], trk_box)
                iou_matrix[d, t] = iou
                
                # Spatial cost: 1 - IoU
                spatial_cost = 1.0 - iou
                
                # Appearance cost: cosine distance if features available
                app_cost = 0.5
                if features is not None and d < len(features):
                    trk_feat = trk.get_feature()
                    if trk_feat is not None:
                        det_feat = features[d]
                        dot = float(np.dot(det_feat, trk_feat))
                        app_cost = max(0.0, min(1.0, 1.0 - dot))
                        
                # Combined weighted cost
                cost_matrix[d, t] = (1.0 - self.appearance_weight) * spatial_cost + self.appearance_weight * app_cost
                
        # Hungarian assignment
        matched_indices = self._linear_assignment(cost_matrix)
        
        unmatched_detections = []
        for d in range(len(detections)):
            if d not in matched_indices[:, 0]:
                unmatched_detections.append(d)
                
        unmatched_trackers = []
        for t in range(len(trackers)):
            if t not in matched_indices[:, 1]:
                unmatched_trackers.append(t)
                
        # Filter matches where spatial overlap is below threshold
        matches = []
        for d, t in matched_indices:
            if iou_matrix[d, t] < self.iou_threshold:
                unmatched_detections.append(d)
                unmatched_trackers.append(t)
            else:
                matches.append([d, t])
                
        matches_arr = np.array(matches, dtype=int) if matches else np.empty((0, 2), dtype=int)
        return matches_arr, np.array(unmatched_detections, dtype=int), np.array(unmatched_trackers, dtype=int)
        
    def _check_tripwire(self, trk: KalmanTracker):
        """Detect if track's trajectory crossed the virtual tripwire"""
        p1, p2 = self.tripwire
        c_prev = trk.centroid_history[-2]
        c_curr = trk.centroid_history[-1]
        
        # Line segment intersection between (c_prev, c_curr) and (p1, p2)
        if self._segments_intersect(c_prev, c_curr, p1, p2):
            # Determine direction using cross product
            v_line = (p2[0] - p1[0], p2[1] - p1[1])
            v_move = (c_curr[0] - c_prev[0], c_curr[1] - c_prev[1])
            cross = v_line[0] * v_move[1] - v_line[1] * v_move[0]
            
            direction = "entry" if cross > 0 else "exit"
            crossing_key = (trk.id, direction)
            
            if crossing_key not in self._crossed_tracks:
                self._crossed_tracks.add(crossing_key)
                if direction == "entry":
                    self.entry_count += 1
                    logger.info(f"Track {trk.id} crossed tripwire: Entry (Total: {self.entry_count})")
                else:
                    self.exit_count += 1
                    logger.info(f"Track {trk.id} crossed tripwire: Exit (Total: {self.exit_count})")
                    
    @staticmethod
    def _segments_intersect(a1, a2, b1, b2) -> bool:
        """Check if segment a1-a2 intersects segment b1-b2 using orientation test"""
        def ccw(A, B, C):
            return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])
        return (ccw(a1, b1, b2) != ccw(a2, b1, b2)) and (ccw(a1, a2, b1) != ccw(a1, a2, b2))
        
    @staticmethod
    def _iou(bbox1: List[float], bbox2: List[float]) -> float:
        """Calculate Intersection over Union (IoU)"""
        x1 = max(bbox1[0], bbox2[0])
        y1 = max(bbox1[1], bbox2[1])
        x2 = min(bbox1[2], bbox2[2])
        y2 = min(bbox1[3], bbox2[3])
        
        inter_area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        bbox1_area = max(0.0, bbox1[2] - bbox1[0]) * max(0.0, bbox1[3] - bbox1[1])
        bbox2_area = max(0.0, bbox2[2] - bbox2[0]) * max(0.0, bbox2[3] - bbox2[1])
        
        union_area = bbox1_area + bbox2_area - inter_area
        return float(inter_area / (union_area + 1e-6))
        
    @staticmethod
    def _linear_assignment(cost_matrix: np.ndarray) -> np.ndarray:
        """Solve bipartite matching via Hungarian algorithm"""
        x, y = linear_sum_assignment(cost_matrix)
        return np.array(list(zip(x, y)))
        
    def get_crowd_density(self, frame_shape: Tuple[int, int]) -> Dict[str, float]:
        """
        Estimate crowd density metrics.
        
        Args:
            frame_shape: (height, width) of the video frame
            
        Returns:
            Dictionary with density ratio (0.0 to 1.0) and nearest neighbor average distance
        """
        h, w = frame_shape[:2]
        frame_area = float(h * w) if (h * w) > 0 else 1.0
        
        confirmed_boxes = [trk.get_state() for trk in self.trackers if trk.time_since_update < 1]
        if not confirmed_boxes:
            return {"density_ratio": 0.0, "avg_neighbor_distance": 999.0, "density_level": "low"}
            
        total_bbox_area = sum(
            max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1]) for b in confirmed_boxes
        )
        density_ratio = min(1.0, total_bbox_area / frame_area)
        
        # Nearest neighbor average distance
        centroids = [((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0) for b in confirmed_boxes]
        if len(centroids) < 2:
            avg_dist = 999.0
        else:
            dists = []
            for i, c1 in enumerate(centroids):
                min_d = min(
                    np.sqrt((c1[0] - c2[0])**2 + (c1[1] - c2[1])**2)
                    for j, c2 in enumerate(centroids) if i != j
                )
                dists.append(min_d)
            avg_dist = float(np.mean(dists))
            
        # Categorize density level
        if density_ratio > 0.35 or (len(centroids) >= 15 and avg_dist < 40.0):
            level = "high"
        elif density_ratio > 0.15 or (len(centroids) >= 8 and avg_dist < 80.0):
            level = "medium"
        else:
            level = "low"
            
        return {
            "density_ratio": float(density_ratio),
            "avg_neighbor_distance": float(avg_dist),
            "density_level": level
        }
