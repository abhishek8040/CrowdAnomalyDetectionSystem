"""
YOLOv8 Person Detector Module
Detects people in video frames using YOLOv8
"""
import cv2
import numpy as np
from ultralytics import YOLO
from typing import List, Tuple, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PersonDetector:
    """YOLOv8-based person detector"""
    
    def __init__(self, model_name: str = "yolov8n.pt", conf_threshold: float = 0.5):
        """
        Initialize the person detector
        
        Args:
            model_name: YOLOv8 model variant (yolov8n, yolov8s, yolov8m, yolov8l, yolov8x)
            conf_threshold: Confidence threshold for detections
        """
        self.conf_threshold = conf_threshold
        self.model = YOLO(model_name)
        logger.info(f"Loaded YOLOv8 model: {model_name}")
        
    def detect_people(self, frame: np.ndarray) -> List[Tuple[List[float], float, int]]:
        """
        Detect people in a frame
        
        Args:
            frame: Input frame (BGR format)
            
        Returns:
            List of tuples: [(bbox, confidence, class_id), ...]
            bbox format: [x1, y1, x2, y2]
        """
        results = self.model(frame, conf=self.conf_threshold, verbose=False)
        
        detections = []
        
        for result in results:
            boxes = result.boxes
            
            for box in boxes:
                # Filter only person class (class_id = 0 in COCO dataset)
                class_id = int(box.cls[0])
                if class_id == 0:  # person class
                    bbox = box.xyxy[0].cpu().numpy().tolist()  # [x1, y1, x2, y2]
                    confidence = float(box.conf[0])
                    detections.append((bbox, confidence, class_id))
        
        return detections
    
    def detect_people_with_features(self, frame: np.ndarray) -> Tuple[List, np.ndarray]:
        """
        Detect people and extract appearance features for tracking
        
        Args:
            frame: Input frame
            
        Returns:
            detections: List of [x1, y1, x2, y2, confidence]
            features: Appearance features for each detection
        """
        detections = self.detect_people(frame)
        
        detection_list = []
        features = []
        
        for bbox, conf, _ in detections:
            x1, y1, x2, y2 = map(int, bbox)
            detection_list.append([x1, y1, x2, y2, conf])
            
            # Extract appearance feature (simple color histogram)
            person_crop = frame[y1:y2, x1:x2]
            if person_crop.size > 0:
                feature = self._extract_appearance_feature(person_crop)
                features.append(feature)
            else:
                features.append(np.zeros(128))
        
        return detection_list, np.array(features) if features else np.array([])
    
    def _extract_appearance_feature(self, crop: np.ndarray) -> np.ndarray:
        """
        Extract simple appearance feature from person crop
        
        Args:
            crop: Person bounding box crop
            
        Returns:
            Feature vector
        """
        # Resize to fixed size
        crop_resized = cv2.resize(crop, (64, 128))
        
        # Compute color histogram (simple feature)
        hist_b = cv2.calcHist([crop_resized], [0], None, [32], [0, 256])
        hist_g = cv2.calcHist([crop_resized], [1], None, [32], [0, 256])
        hist_r = cv2.calcHist([crop_resized], [2], None, [32], [0, 256])
        
        feature = np.concatenate([hist_b, hist_g, hist_r]).flatten()
        feature = feature / (np.linalg.norm(feature) + 1e-6)  # Normalize
        
        return feature
