"""
Zone Violation Detection Module
Detects when people enter restricted zones
"""
import numpy as np
from typing import List, Tuple, Dict
from shapely.geometry import Point, Polygon
import logging

logger = logging.getLogger(__name__)


class ZoneViolationDetector:
    """Detects violations of restricted zones"""
    
    def __init__(self, restricted_zones: List[List[Tuple[float, float]]] = None):
        """
        Initialize zone violation detector
        
        Args:
            restricted_zones: List of polygon zones, each defined by list of (x,y) points
        """
        self.restricted_zones = []
        self.zone_polygons = []
        
        if restricted_zones:
            for zone in restricted_zones:
                self.add_zone(zone)
        
        self.violating_tracks = set()
    
    def add_zone(self, zone_points: List[Tuple[float, float]]):
        """
        Add a restricted zone
        
        Args:
            zone_points: List of (x, y) coordinates defining the polygon
        """
        if len(zone_points) < 3:
            logger.warning("Zone must have at least 3 points")
            return
        
        self.restricted_zones.append(zone_points)
        self.zone_polygons.append(Polygon(zone_points))
        logger.info(f"Added restricted zone with {len(zone_points)} points")
    
    def remove_zone(self, zone_index: int):
        """Remove a zone by index"""
        if 0 <= zone_index < len(self.restricted_zones):
            self.restricted_zones.pop(zone_index)
            self.zone_polygons.pop(zone_index)
            logger.info(f"Removed zone at index {zone_index}")
    
    def clear_zones(self):
        """Clear all zones"""
        self.restricted_zones = []
        self.zone_polygons = []
        self.violating_tracks = set()
        logger.info("Cleared all restricted zones")
    
    def detect_zone_violation(self, center_point: Tuple[float, float], 
                             zone_polygons: List = None, track_id: int = None) -> Dict:
        """
        Detect if a point violates any restricted zone
        
        Args:
            center_point: (x, y) coordinates to check
            zone_polygons: Optional override for zone polygons
            track_id: Optional track ID for alert tracking
            
        Returns:
            Dictionary with violation results
        """
        if zone_polygons is None:
            zone_polygons = self.zone_polygons
        
        if not zone_polygons:
            return {
                'is_violation': False,
                'violated_zones': [],
                'alert_triggered': False
            }
        
        point = Point(center_point[0], center_point[1])
        violated_zones = []
        
        for i, zone_poly in enumerate(zone_polygons):
            if self._point_in_polygon(point, zone_poly):
                violated_zones.append(i)
        
        is_violation = len(violated_zones) > 0
        
        # Track alerts per track ID
        alert_triggered = False
        if track_id is not None:
            if is_violation and track_id not in self.violating_tracks:
                alert_triggered = True
                self.violating_tracks.add(track_id)
                logger.warning(f"Zone violation detected for track {track_id} at {center_point}")
            elif not is_violation and track_id in self.violating_tracks:
                self.violating_tracks.remove(track_id)
        
        return {
            'is_violation': is_violation,
            'violated_zones': violated_zones,
            'point': center_point,
            'alert_triggered': alert_triggered,
            'track_id': track_id
        }
    
    @staticmethod
    def _point_in_polygon(point: Point, polygon: Polygon) -> bool:
        """
        Check if point is inside polygon using Shapely
        
        Args:
            point: Point object
            polygon: Polygon object
            
        Returns:
            True if point is inside polygon
        """
        return polygon.contains(point)
    
    @staticmethod
    def point_in_polygon_manual(point: Tuple[float, float], 
                               polygon: List[Tuple[float, float]]) -> bool:
        """
        Check if point is inside polygon using ray casting algorithm
        
        Args:
            point: (x, y) coordinates
            polygon: List of (x, y) vertices
            
        Returns:
            True if point is inside polygon
        """
        x, y = point
        n = len(polygon)
        inside = False
        
        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside
    
    def get_zones(self) -> List[List[Tuple[float, float]]]:
        """Get all defined zones"""
        return self.restricted_zones
