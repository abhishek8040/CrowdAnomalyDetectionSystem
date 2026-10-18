"""
Overcrowding Detection Module
Detects when the number of people exceeds configured thresholds with temporal confirmation
and spatial density estimation.
"""
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class OvercrowdingDetector:
    """Detects overcrowding based on people count and spatial density with temporal smoothing"""
    
    def __init__(self, threshold: int = 10, confirmation_frames: int = 5):
        """
        Initialize overcrowding detector.
        
        Args:
            threshold: Maximum allowed number of people
            confirmation_frames: Consecutive frames over threshold before triggering alert
        """
        self.threshold = threshold
        self.confirmation_frames = confirmation_frames
        self.alert_active = False
        self.over_count_frames = 0
        
    def detect_overcrowding(
        self,
        count: int,
        threshold: Optional[int] = None,
        density_info: Optional[Dict] = None
    ) -> Dict:
        """
        Detect if overcrowding is occurring with temporal confirmation.
        
        Args:
            count: Current number of people detected
            threshold: Override default count threshold
            density_info: Optional spatial density dict from tracker
            
        Returns:
            Dictionary with detection results
        """
        active_threshold = threshold if threshold is not None else self.threshold
        
        is_above_threshold = count > active_threshold
        
        if is_above_threshold:
            self.over_count_frames += 1
        else:
            self.over_count_frames = max(0, self.over_count_frames - 1)
            
        # Confirmed when sustained over confirmation_frames
        is_overcrowded = self.over_count_frames >= self.confirmation_frames
        
        # Trigger alert on state transition to confirmed overcrowded
        alert_triggered = False
        if is_overcrowded and not self.alert_active:
            alert_triggered = True
            self.alert_active = True
            logger.warning(
                f"Overcrowding confirmed: {count} people (threshold: {active_threshold}, "
                f"sustained for {self.over_count_frames} frames)"
            )
        elif not is_above_threshold and self.over_count_frames == 0:
            self.alert_active = False
            
        severity = self._calculate_severity(count, active_threshold, density_info)
        
        res = {
            'is_overcrowded': is_overcrowded,
            'current_count': count,
            'threshold': active_threshold,
            'sustained_frames': self.over_count_frames,
            'alert_triggered': alert_triggered,
            'severity': severity,
            'confidence': min(1.0, 0.7 + 0.05 * (count - active_threshold)) if is_overcrowded else 0.0
        }
        if density_info:
            res['density_ratio'] = density_info.get('density_ratio', 0.0)
            res['density_level'] = density_info.get('density_level', 'low')
            
        return res
    
    @staticmethod
    def _calculate_severity(count: int, threshold: int, density_info: Optional[Dict] = None) -> str:
        """
        Calculate severity level of overcrowding (none, low, medium, high, critical).
        """
        if count <= threshold:
            return 'none'
        
        ratio = count / float(threshold)
        density_ratio = density_info.get('density_ratio', 0.0) if density_info else 0.0
        
        if ratio >= 2.0 or density_ratio > 0.4:
            return 'critical'
        elif ratio >= 1.5 or density_ratio > 0.25:
            return 'high'
        elif ratio >= 1.2:
            return 'medium'
        else:
            return 'low'
    
    def set_threshold(self, threshold: int):
        """Update the count threshold"""
        self.threshold = threshold
        logger.info(f"Overcrowding threshold updated to: {threshold}")
