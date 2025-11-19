"""
Test Anomaly Detection Modules
"""
import pytest
import numpy as np
from anomaly.overcrowding import OvercrowdingDetector
from anomaly.loitering import LoiteringDetector
from anomaly.zone_violation import ZoneViolationDetector


def test_overcrowding_detector():
    """Test overcrowding detection"""
    detector = OvercrowdingDetector(threshold=5)
    
    # No overcrowding
    result = detector.detect_overcrowding(3)
    assert result['is_overcrowded'] == False
    
    # Overcrowding
    result = detector.detect_overcrowding(8)
    assert result['is_overcrowded'] == True
    assert result['current_count'] == 8
    assert result['alert_triggered'] == True


def test_loitering_detector():
    """Test loitering detection"""
    detector = LoiteringDetector(pixel_threshold=50.0, time_threshold=10, fps=30)
    
    # Add track positions (stationary)
    for i in range(300):  # 10 seconds at 30fps
        detector.update_track(1, (100, 100), i)
    
    result = detector.detect_loitering(1)
    assert result['is_loitering'] == True
    assert result['alert_triggered'] == True


def test_zone_violation_detector():
    """Test zone violation detection"""
    detector = ZoneViolationDetector()
    
    # Add a restricted zone (square)
    zone = [(100, 100), (200, 100), (200, 200), (100, 200)]
    detector.add_zone(zone)
    
    # Point inside zone
    result = detector.detect_zone_violation((150, 150), track_id=1)
    assert result['is_violation'] == True
    assert result['alert_triggered'] == True
    
    # Point outside zone
    result = detector.detect_zone_violation((300, 300), track_id=2)
    assert result['is_violation'] == False


def test_zone_point_in_polygon():
    """Test point in polygon algorithm"""
    detector = ZoneViolationDetector()
    
    polygon = [(0, 0), (100, 0), (100, 100), (0, 100)]
    
    # Inside
    assert detector.point_in_polygon_manual((50, 50), polygon) == True
    
    # Outside
    assert detector.point_in_polygon_manual((150, 150), polygon) == False
    
    # On edge (may vary based on implementation)
    # assert detector.point_in_polygon_manual((0, 50), polygon) in [True, False]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
