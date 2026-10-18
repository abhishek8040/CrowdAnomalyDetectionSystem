"""
Anomaly Detection Suite
"""
from .overcrowding import OvercrowdingDetector
from .loitering import LoiteringDetector
from .zone_violation import ZoneViolationDetector
from .suspicious_activity import SuspiciousActivityDetector
from .fall_detection import FallDetector
from .panic_running import PanicRunningDetector
from .snatching_detection import SnatchingDetector

__all__ = [
    "OvercrowdingDetector",
    "LoiteringDetector",
    "ZoneViolationDetector",
    "SuspiciousActivityDetector",
    "FallDetector",
    "PanicRunningDetector",
    "SnatchingDetector"
]
