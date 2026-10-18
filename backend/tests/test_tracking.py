"""
Test DeepSORT Tracker, Appearance Re-ID, Tripwire Counting, and Crowd Density
"""
import pytest
import numpy as np
from tracking.deepsort import DeepSORT, KalmanTracker


def test_kalman_tracker_nan_safety():
    """Verify KalmanTracker protects against negative scale or NaN bounding boxes"""
    # Create extreme/degenerate bbox
    trk = KalmanTracker([100.0, 100.0, 100.5, 100.5])
    # Multiple predictions without updates
    for _ in range(50):
        pos = trk.predict()
        assert not any(np.isnan(pos))
        assert not any(np.isinf(pos))
        assert pos[2] > pos[0]
        assert pos[3] > pos[1]


def test_deepsort_tracking_and_features():
    """Test multi-frame tracking with simulated appearance vectors"""
    tracker = DeepSORT(max_age=10, min_hits=2, iou_threshold=0.3)
    
    # Frame 1: Single person detected
    f1 = np.ones(128, dtype=np.float32)
    f1 /= np.linalg.norm(f1)
    dets_f1 = [[100.0, 100.0, 150.0, 200.0, 0.9]]
    tracks_f1 = tracker.update(dets_f1, features=np.array([f1]))
    assert len(tracks_f1) == 1
    t1_id = tracks_f1[0]['id']

    # Frame 2: Person moves slightly
    dets_f2 = [[105.0, 102.0, 155.0, 202.0, 0.92]]
    tracks_f2 = tracker.update(dets_f2, features=np.array([f1]))
    assert len(tracks_f2) == 1
    assert tracks_f2[0]['id'] == t1_id


def test_tripwire_line_crossing():
    """Test virtual tripwire line-crossing for entry/exit counting"""
    tracker = DeepSORT(max_age=10, min_hits=1)
    
    # Vertical line at x=200 from y=0 to y=500
    tracker.set_tripwire((200.0, 0.0), (200.0, 500.0))
    assert tracker.entry_count == 0
    assert tracker.exit_count == 0

    # Person moves from center x=195 to x=210 (crosses line at x=200)
    tracker.update([[170.0, 100.0, 220.0, 200.0, 0.9]])
    tracker.update([[185.0, 100.0, 235.0, 200.0, 0.9]])

    assert (tracker.entry_count + tracker.exit_count) == 1


def test_crowd_density_estimation():
    """Test crowd density ratio and spatial clustering calculation"""
    tracker = DeepSORT(max_age=10, min_hits=1)
    
    # 3 persons close together
    dets = [
        [100.0, 100.0, 150.0, 200.0, 0.9],
        [160.0, 100.0, 210.0, 200.0, 0.9],
        [120.0, 110.0, 170.0, 210.0, 0.9],
    ]
    tracker.update(dets)

    density = tracker.get_crowd_density((480, 640))
    assert 'density_ratio' in density
    assert density['density_ratio'] > 0.0
    assert density['density_ratio'] <= 1.0
    assert 'density_level' in density
    assert 'avg_neighbor_distance' in density
