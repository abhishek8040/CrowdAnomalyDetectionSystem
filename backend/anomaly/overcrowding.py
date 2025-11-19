"""
Overcrowding Detection Module
Detects when the number of people exceeds a threshold
"""
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class OvercrowdingDetector:
    """Detects overcrowding based on people count"""
    
    def __init__(self, threshold: int = 10):
        """
        Initialize overcrowding detector
        
        Args:
            threshold: Maximum allowed number of people
        """
        self.threshold = threshold
        self.alert_active = False
        
    def detect_overcrowding(self, count: int, threshold: Optional[int] = None) -> Dict:
        """
        Detect if overcrowding is occurring
        
        Args:
            count: Current number of people detected
            threshold: Override default threshold
            
        Returns:
            Dictionary with detection results
        """
        active_threshold = threshold if threshold is not None else self.threshold
        
        is_overcrowded = count > active_threshold
        
        # Trigger alert on state change
        alert_triggered = False
        if is_overcrowded and not self.alert_active:
            alert_triggered = True
            logger.warning(f"Overcrowding detected: {count} people (threshold: {active_threshold})")
        
        self.alert_active = is_overcrowded
        
        return {
            'is_overcrowded': is_overcrowded,
            'current_count': count,
            'threshold': active_threshold,
            'alert_triggered': alert_triggered,
            'severity': self._calculate_severity(count, active_threshold)
        }
    
    @staticmethod
    def _calculate_severity(count: int, threshold: int) -> str:
        """
        Calculate severity level of overcrowding
        
        Returns:
            'low', 'medium', or 'high'
        """
        if count <= threshold:
            return 'none'
        
        ratio = count / threshold
        
        if ratio <= 1.2:
            return 'low'
        elif ratio <= 1.5:
            return 'medium'
        else:
            return 'high'
    
    def set_threshold(self, threshold: int):
        """Update the threshold"""
        self.threshold = threshold
        logger.info(f"Overcrowding threshold updated to: {threshold}")
