"""
YOLOv8 Person Detector Module
Detects people in video frames using YOLOv8 with appearance feature extraction
"""
import cv2
import numpy as np
from ultralytics import YOLO
from typing import List, Tuple, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class PersonDetector:
    """YOLOv8-based person detector with appearance feature extraction"""
    
    CLASS_NAMES = {
        0: "person",
        1: "bicycle",
        2: "car",
        3: "motorcycle",
    }
    
    def __init__(
        self,
        model_name: str = "yolov8n.pt",
        conf_threshold: float = 0.5,
        iou_threshold: float = 0.45,
        target_classes: Tuple[int, ...] = (0, 1, 3)
    ):
        """
        Initialize the detector.
        
        Args:
            model_name: YOLOv8 model variant or weight file
            conf_threshold: Confidence threshold for detections
            iou_threshold: NMS IoU threshold
            target_classes: COCO class IDs to detect (0=person, 1=bicycle, 3=motorcycle)
        """
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.target_classes = target_classes
        
        # Check local paths first to prevent unnecessary re-downloads or SSL cert errors
        resolved_path = model_name
        possible_paths = [
            Path(model_name),
            Path(__file__).resolve().parent.parent / model_name,
            Path(__file__).resolve().parent.parent.parent / model_name,
        ]
        for p in possible_paths:
            if p.exists() and p.is_file():
                resolved_path = str(p)
                break
                
        self.model = YOLO(resolved_path)
        logger.info(f"Loaded YOLOv8 model from: {resolved_path} with target classes {target_classes}")
        
    def detect_people(self, frame: np.ndarray, conf: Optional[float] = None) -> List[Tuple[List[float], float, int, str]]:
        """
        Detect people, bicycles, and motorcycles in a frame.
        
        Args:
            frame: Input frame (BGR format)
            conf: Optional override for confidence threshold
            
        Returns:
            List of tuples: [(bbox, confidence, class_id, class_name), ...]
            bbox format: [x1, y1, x2, y2]
        """
        active_conf = conf if conf is not None else self.conf_threshold
        results = self.model(frame, conf=active_conf, iou=self.iou_threshold, verbose=False)
        
        detections = []
        for result in results:
            boxes = result.boxes
            for box in boxes:
                class_id = int(box.cls[0])
                if class_id in self.target_classes:
                    bbox = box.xyxy[0].cpu().numpy().tolist()  # [x1, y1, x2, y2]
                    confidence = float(box.conf[0])
                    class_name = self.CLASS_NAMES.get(class_id, "person")
                    detections.append((bbox, confidence, class_id, class_name))
        
        return detections
    
    def detect_people_with_features(self, frame: np.ndarray, conf: Optional[float] = None) -> Tuple[List, np.ndarray]:
        """
        Detect people/vehicles and extract normalized appearance features for tracking.
        
        Args:
            frame: Input frame
            conf: Optional confidence threshold override
            
        Returns:
            detections: List of [x1, y1, x2, y2, confidence, class_id, class_name]
            features: Appearance features matrix (N, 128)
        """
        detections = self.detect_people(frame, conf=conf)
        
        detection_list = []
        features = []
        h, w = frame.shape[:2]
        
        for item in detections:
            bbox = item[0]
            conf_score = item[1]
            class_id = item[2]
            class_name = item[3] if len(item) > 3 else self.CLASS_NAMES.get(class_id, "person")
            
            x1, y1, x2, y2 = map(int, bbox)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            
            detection_list.append([float(x1), float(y1), float(x2), float(y2), float(conf_score), class_id, class_name])
            
            # Extract appearance feature
            if x2 > x1 and y2 > y1:
                crop = frame[y1:y2, x1:x2]
                feature = self._extract_appearance_feature(crop)
                features.append(feature)
            else:
                features.append(np.zeros(128, dtype=np.float32))
        
        features_arr = np.array(features, dtype=np.float32) if features else np.empty((0, 128), dtype=np.float32)
        return detection_list, features_arr
    
    def _extract_appearance_feature(self, crop: np.ndarray) -> np.ndarray:
        """
        Extract normalized appearance feature vector combining HSV color histogram
        and spatial gradients.
        
        Args:
            crop: Person bounding box crop
            
        Returns:
            128-dimensional normalized feature vector
        """
        if crop.size == 0:
            return np.zeros(128, dtype=np.float32)
            
        crop_resized = cv2.resize(crop, (64, 128))
        hsv = cv2.cvtColor(crop_resized, cv2.COLOR_BGR2HSV)
        
        # Upper body (torso) and lower body (legs) split for spatial representation
        h_half = 64
        upper_hsv = hsv[:h_half, :]
        lower_hsv = hsv[h_half:, :]
        
        # 32 bins H, 16 bins S, 16 bins V for upper
        hist_u_h = cv2.calcHist([upper_hsv], [0], None, [32], [0, 180]).flatten()
        hist_u_s = cv2.calcHist([upper_hsv], [1], None, [16], [0, 256]).flatten()
        hist_u_v = cv2.calcHist([upper_hsv], [2], None, [16], [0, 256]).flatten()
        
        # 32 bins H, 16 bins S, 16 bins V for lower
        hist_l_h = cv2.calcHist([lower_hsv], [0], None, [32], [0, 180]).flatten()
        hist_l_s = cv2.calcHist([lower_hsv], [1], None, [16], [0, 256]).flatten()
        hist_l_v = cv2.calcHist([lower_hsv], [2], None, [16], [0, 256]).flatten()
        
        feature = np.concatenate([
            hist_u_h, hist_u_s, hist_u_v,
            hist_l_h, hist_l_s, hist_l_v
        ]).astype(np.float32)
        
        norm = np.linalg.norm(feature)
        if norm > 1e-6:
            feature /= norm
            
        return feature
