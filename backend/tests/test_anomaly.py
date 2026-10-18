"""
Test Anomaly Detection Modules
"""
import pytest
import numpy as np
from anomaly.overcrowding import OvercrowdingDetector
from anomaly.loitering import LoiteringDetector
from anomaly.zone_violation import ZoneViolationDetector
from anomaly.fall_detection import FallDetector
from anomaly.panic_running import PanicRunningDetector


def test_overcrowding_detector():
    """Test overcrowding detection with temporal confirmation"""
    detector = OvercrowdingDetector(threshold=5, confirmation_frames=3)
    
    # Below threshold
    res1 = detector.detect_overcrowding(3)
    assert res1['is_overcrowded'] is False
    assert res1['alert_triggered'] is False
    
    # Exceed threshold once (not yet confirmed)
    res2 = detector.detect_overcrowding(8)
    assert res2['is_overcrowded'] is False
    assert res2['alert_triggered'] is False
    
    # Exceed threshold 2 more times to meet confirmation_frames=3
    detector.detect_overcrowding(8)
    res4 = detector.detect_overcrowding(8)
    assert res4['is_overcrowded'] is True
    assert res4['alert_triggered'] is True
    assert res4['severity'] in ['medium', 'high', 'critical']


def test_loitering_detector():
    """Test loitering detection duration and movement threshold"""
    detector = LoiteringDetector(pixel_threshold=50.0, time_threshold=2, fps=10)
    
    # Stationary track for 20 frames (2 seconds)
    for i in range(20):
        detector.update_track(1, (100.0, 100.0), i)
    
    result = detector.detect_loitering(1)
    assert result['is_loitering'] is True
    assert result['alert_triggered'] is True
    assert result['duration_seconds'] >= 2.0


def test_zone_violation_detector():
    """Test zone violation detection"""
    detector = ZoneViolationDetector()
    
    # Add a restricted zone (square: 100,100 to 200,200)
    zone = [(100.0, 100.0), (200.0, 100.0), (200.0, 200.0), (100.0, 200.0)]
    detector.add_zone(zone)
    
    # Point inside zone
    res_inside = detector.detect_zone_violation((150.0, 150.0), track_id=1)
    assert res_inside['is_violation'] is True
    assert res_inside['alert_triggered'] is True
    
    # Point outside zone
    res_outside = detector.detect_zone_violation((350.0, 350.0), track_id=2)
    assert res_outside['is_violation'] is False


def test_fall_detector():
    """Test fall detector on aspect ratio change and downward motion"""
    detector = FallDetector(aspect_ratio_threshold=1.1, confirmation_frames=3)
    
    # Standing person (tall: w=40, h=120)
    for i in range(5):
        res = detector.update_and_detect(1, [100.0, 50.0, 140.0, 170.0], i)
        assert res['is_fall'] is False

    # Person falls and lies horizontal (wide: w=140, h=50, aspect_ratio=2.8)
    res_fall = None
    for i in range(5, 12):
        res_fall = detector.update_and_detect(1, [80.0, 150.0, 220.0, 200.0], i)
        
    assert res_fall['is_fall'] is True
    assert res_fall['aspect_ratio'] > 1.1


def test_panic_running_detector():
    """Test panic and running detection based on track speeds"""
    detector = PanicRunningDetector(running_speed_threshold=15.0, panic_min_people=2)
    
    # Normal walking tracks (speed < 15)
    tracks_walking = [
        {'id': 1, 'speed': 3.0, 'velocity': (2.0, 1.0)},
        {'id': 2, 'speed': 4.0, 'velocity': (1.0, 3.0)}
    ]
    res_walk = detector.detect_motion_anomalies(tracks_walking, 1)
    assert res_walk['is_running'] is False
    assert res_walk['is_panic'] is False

    # 3 persons running (speed >= 18)
    tracks_panic = [
        {'id': 1, 'speed': 20.0, 'velocity': (18.0, 5.0)},
        {'id': 2, 'speed': 22.0, 'velocity': (-15.0, 10.0)},
        {'id': 3, 'speed': 19.0, 'velocity': (5.0, -17.0)}
    ]
    res_panic = detector.detect_motion_anomalies(tracks_panic, 10)
    assert res_panic['is_panic'] is True
    assert res_panic['alert_triggered'] is True
    assert res_panic['severity'] == 'critical'
