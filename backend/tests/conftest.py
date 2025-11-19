"""
Test Configuration Module
Contains test fixtures and utilities
"""
import pytest
import numpy as np


@pytest.fixture
def sample_frame():
    """Generate a sample video frame"""
    return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)


@pytest.fixture
def sample_detections():
    """Generate sample detections"""
    return [
        ([100, 100, 200, 300], 0.95, 0),
        ([250, 150, 350, 320], 0.87, 0),
        ([400, 200, 500, 400], 0.92, 0),
    ]


@pytest.fixture
def sample_tracks():
    """Generate sample tracks"""
    return [
        {'id': 1, 'bbox': [100, 100, 200, 300], 'confidence': 0.95},
        {'id': 2, 'bbox': [250, 150, 350, 320], 'confidence': 0.87},
        {'id': 3, 'bbox': [400, 200, 500, 400], 'confidence': 0.92},
    ]
