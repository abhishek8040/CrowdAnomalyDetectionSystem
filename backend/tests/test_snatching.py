"""
Tests for Snatching and Drive-by Theft Detection
Verifies kinematic modeling of approach -> intercept -> escape phases,
multi-class vehicle tracking, and natural-language security rule parsing.
"""
import pytest
import numpy as np
from anomaly.snatching_detection import SnatchingDetector
from anomaly.rule_engine import parse_natural_language_rule, RuleEvaluator
from tracking.deepsort import DeepSORT, KalmanTracker


def test_drive_by_snatching_detection():
    """Test simulated drive-by snatching with motorcycle and pedestrian"""
    detector = SnatchingDetector(
        intercept_distance=85.0,
        min_approach_speed=6.0,
        min_escape_speed=10.0,
        escape_distance_delta=35.0,
        max_intercept_window=30,
        cooldown_frames=40
    )

    alert_triggered = False
    triggered_event = None

    # Track 1: Victim (walking slowly at y=250, x=300 -> 315)
    # Track 2: Suspect (motorcycle moving rapidly from x=100 to x=600 at y=250)
    for frame in range(1, 30):
        # Victim moves 0.5 px per frame
        v_x = 300.0 + (frame * 0.5)
        v_track = {
            'id': 1,
            'bbox': [v_x - 15, 230.0, v_x + 15, 270.0],
            'speed': 1.5,
            'class_name': 'person'
        }

        # Suspect motorcycle approaches and zooms past
        # Frames 1-10: approach from x=120 to x=270 (speed = 15 px/f)
        # Frames 11-13: close intercept at x=290 to x=320
        # Frames 14-29: escape from x=340 to x=580 (speed = 16 px/f)
        s_x = 120.0 + (frame * 16.0)
        s_speed = 16.0
        s_track = {
            'id': 2,
            'bbox': [s_x - 25, 230.0, s_x + 25, 270.0],
            'speed': s_speed,
            'class_name': 'motorcycle'
        }

        res = detector.update_and_detect([v_track, s_track], frame)
        if res['alert_triggered']:
            alert_triggered = True
            triggered_event = res
            break

    assert alert_triggered is True
    assert triggered_event is not None
    assert triggered_event['is_snatching'] is True
    assert triggered_event['suspect_id'] == 2
    assert triggered_event['victim_id'] == 1
    assert triggered_event['suspect_class'] == 'motorcycle'
    assert triggered_event['severity'] == 'critical'
    assert triggered_event['confidence'] >= 0.85


def test_normal_passing_pedestrians_no_false_alarm():
    """Verify that two normal pedestrians passing each other do NOT trigger a snatching alert"""
    detector = SnatchingDetector(
        intercept_distance=85.0,
        min_approach_speed=6.0,
        min_escape_speed=10.0,
        escape_distance_delta=35.0
    )

    alert_triggered = False

    # Two pedestrians walking past each other at 2.5 px/f
    for frame in range(1, 40):
        p1_x = 200.0 + (frame * 2.5)  # moving right
        p2_x = 400.0 - (frame * 2.5)  # moving left

        p1_track = {
            'id': 10,
            'bbox': [p1_x - 15, 200.0, p1_x + 15, 260.0],
            'speed': 2.5,
            'class_name': 'person'
        }
        p2_track = {
            'id': 20,
            'bbox': [p2_x - 15, 200.0, p2_x + 15, 260.0],
            'speed': 2.5,
            'class_name': 'person'
        }

        res = detector.update_and_detect([p1_track, p2_track], frame)
        if res['alert_triggered']:
            alert_triggered = True
            break

    assert alert_triggered is False


def test_snatching_cooldown_and_cleanup():
    """Verify alert cooldown avoids duplicate spam and old tracks are cleaned up"""
    detector = SnatchingDetector(
        intercept_distance=80.0,
        min_approach_speed=6.0,
        min_escape_speed=10.0,
        escape_distance_delta=30.0,
        cooldown_frames=50
    )

    # Frame 1: intercept
    t1 = {'id': 1, 'bbox': [100.0, 100.0, 130.0, 150.0], 'speed': 2.0, 'class_name': 'person'}
    t2 = {'id': 2, 'bbox': [110.0, 100.0, 150.0, 150.0], 'speed': 14.0, 'class_name': 'motorcycle'}
    detector.update_and_detect([t1, t2], frame_num=1)

    # Frame 5: escape
    t2['bbox'] = [180.0, 100.0, 220.0, 150.0]
    res1 = detector.update_and_detect([t1, t2], frame_num=5)
    assert res1['alert_triggered'] is True

    # Frame 6: immediately next frame, should be suppressed by cooldown
    t2['bbox'] = [195.0, 100.0, 235.0, 150.0]
    res2 = detector.update_and_detect([t1, t2], frame_num=6)
    assert res2['alert_triggered'] is False

    # Cleanup old tracks
    detector.cleanup_old_tracks(active_track_ids=[99])
    assert len(detector._interactions) == 0
    assert len(detector._cooldowns) == 0


def test_snatching_nl_rule_parsing_and_evaluation():
    """Verify natural-language rule engine parsing and evaluation for snatching"""
    # 1. Parse rule
    rule = parse_natural_language_rule("Alert immediately on motorcycle snatching or drive-by theft")
    assert rule['is_supported'] is True
    assert rule['rule_type'] == 'snatching'
    assert rule['severity'] == 'critical'

    # 2. Evaluate rule
    evaluator = RuleEvaluator([rule])
    anomaly_summary = {
        'snatching': {
            'is_snatching': True,
            'suspect_id': 5,
            'victim_id': 2,
            'suspect_class': 'motorcycle',
            'confidence': 0.95
        }
    }
    alerts = evaluator.evaluate(frame_num=10, tracks=[], zones=[], anomaly_results=anomaly_summary)
    assert len(alerts) == 1
    assert alerts[0]['event_type'] == 'custom_rule'
    assert alerts[0]['details']['rule_type'] == 'snatching'
    assert alerts[0]['details']['suspect_id'] == 5


def test_tracker_class_propagation():
    """Verify DeepSORT tracker retains and outputs semantic class_name"""
    tracker = DeepSORT(max_age=10, min_hits=1)

    # Detection with class_name='motorcycle'
    dets = [[100.0, 100.0, 160.0, 180.0, 0.95, 3, 'motorcycle']]
    tracks = tracker.update(dets)
    assert len(tracks) == 1
    assert tracks[0]['class_name'] == 'motorcycle'
    assert 'trajectory' in tracks[0]
