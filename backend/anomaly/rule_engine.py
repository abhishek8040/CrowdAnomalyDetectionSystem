"""
Natural Language Anomaly Rule Engine
Translates human operator natural-language specifications into structured, validated rules,
rejects unsupported concepts with explicit technical rationales, and evaluates active rules.
"""
import re
from typing import Dict, Any, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


# Supported capability categories mapped to keywords
SUPPORTED_CAPABILITIES = {
    'overcrowding': [
        r'(?:crowd|people|persons|gathering|count)\s*(?:exceeds?|greater than|more than|>|above)\s*(\d+)',
        r'(?:more than|>|above)\s*(\d+)\s*(?:people|persons|individuals)',
        r'overcrowd(?:ing)?(?:\s*(?:threshold|limit|exceeds?)\s*(\d+))?'
    ],
    'loitering': [
        r'loiter(?:ing)?.*?(?:longer than|more than|>|for)?\s*(\d+)\s*(?:seconds?|s|mins?|minutes?)',
        r'stays?\s*(?:in place|stationary|around)\s*(?:for|longer than)\s*(\d+)\s*(?:seconds?|s|mins?|minutes?)',
        r'standing still for\s*(\d+)\s*(?:seconds?|s|mins?|minutes?)'
    ],
    'zone_violation': [
        r'(?:enters?|walks? into|breaches?|in)\s*(?:restricted\s*)?zone\s*(\d+)',
        r'(?:restricted\s*zone|designated\s*area|forbidden\s*area)',
        r'boundary\s*violation'
    ],
    'fight': [
        r'(?:fighting|fights?|physical altercation|violence|brawl|assault)',
        r'people (?:hitting|punching|attacking) each other'
    ],
    'fall': [
        r'(?:falls?|falling|collapsed?|lying on the (?:ground|floor)|downed person|slip and fall)'
    ],
    'running_panic': [
        r'(?:running|sprint(?:ing)?|rush(?:ing)?)',
        r'(?:panic|crowd dispersion|stampede|fleeing|scatter(?:ing)?)'
    ],
    'tripwire': [
        r'(?:entry|exit|enter|leave)\s*(?:counting|crossing|tripwire)',
        r'line\s*crossing'
    ],
    'snatching': [
        r'(?:snatch(?:ing)?|theft|robbery|drive[- ]by(?:\s*theft)?|grab(?:bing)?\s*(?:and|&)\s*run)',
        r'(?:bike|motorcycle|scooter|vehicle)\s*(?:snatch(?:ing)?|theft|robbery)'
    ]
}

# Explicitly unsupported capabilities requiring separate models or modalities
UNSUPPORTED_DOMAINS = {
    'weapon': {
        'patterns': [r'gun', r'knife', r'weapon', r'firearm', r'pistol', r'rifle', r'blade'],
        'reason': "Weapon detection requires an object detector trained on weapon classes (e.g. YOLOv8-Weapons) which is not loaded."
    },
    'luggage_abandonment': {
        'patterns': [r'abandoned (?:bag|backpack|luggage|suitcase|package)', r'unattended (?:bag|object|luggage)'],
        'reason': "Stationary luggage abandonment requires background-subtraction item classification and ownership attribution models."
    },
    'fire_smoke': {
        'patterns': [r'fire', r'smoke', r'flame'],
        'reason': "Fire and smoke detection requires a dedicated visual smoke/fire segmentation model."
    },
    'facial_recognition': {
        'patterns': [r'recognize\s+(?:face|person|individual|suspect)', r'blacklist', r'identity of'],
        'reason': "Facial recognition requires high-resolution face detection and feature embedding models (e.g. ArcFace/FaceNet) not present in this crowd safety system."
    },
    'audio_shouting': {
        'patterns': [r'screaming', r'shouting', r'gunshot sound', r'glass break sound', r'audio'],
        'reason': "Audio acoustic event detection requires an audio sensor pipeline and audio classification model."
    }
}


def parse_natural_language_rule(text: str) -> Dict[str, Any]:
    """
    Parse a natural language instruction into a validated rule dictionary.
    
    Args:
        text: Operator prompt (e.g. "Alert when the crowd exceeds 5 people in zone 1")
        
    Returns:
        Structured result dict with:
        - 'is_supported': bool
        - 'rule_type': str
        - 'parameters': dict
        - 'explanation': str
        - 'unsupported_reason': Optional[str]
    """
    cleaned = text.strip().lower()
    
    # 1. Check for explicitly unsupported requests
    for domain, info in UNSUPPORTED_DOMAINS.items():
        for pat in info['patterns']:
            if re.search(pat, cleaned):
                return {
                    'is_supported': False,
                    'rule_type': 'unsupported',
                    'raw_text': text,
                    'domain': domain,
                    'explanation': f"The requested rule '{text}' cannot be fulfilled with the current model stack.",
                    'unsupported_reason': info['reason']
                }
                
    # 2. Check Overcrowding
    for pat in SUPPORTED_CAPABILITIES['overcrowding']:
        match = re.search(pat, cleaned)
        if match:
            threshold = 10
            if match.groups() and match.group(1):
                try:
                    threshold = int(match.group(1))
                except ValueError:
                    threshold = 10
            # Also check if a specific zone was mentioned
            zone_match = re.search(r'zone\s*(\d+)', cleaned)
            zone_idx = int(zone_match.group(1)) - 1 if zone_match else None
            
            return {
                'is_supported': True,
                'rule_type': 'overcrowding',
                'name': f"Crowd > {threshold}" + (f" in Zone {zone_idx + 1}" if zone_idx is not None else ""),
                'raw_text': text,
                'parameters': {
                    'threshold': threshold,
                    'zone_index': zone_idx,
                    'confirmation_frames': 5
                },
                'severity': 'high' if threshold <= 5 else 'medium',
                'explanation': f"Alert will trigger when person count exceeds {threshold}" + (f" within Zone {zone_idx + 1}" if zone_idx is not None else "") + "."
            }

    # 3. Check Loitering
    for pat in SUPPORTED_CAPABILITIES['loitering']:
        match = re.search(pat, cleaned)
        if match:
            time_sec = 60
            if match.groups() and match.group(1):
                try:
                    val = int(match.group(1))
                    # check if minutes
                    if 'min' in cleaned:
                        time_sec = val * 60
                    else:
                        time_sec = val
                except ValueError:
                    time_sec = 60
                    
            return {
                'is_supported': True,
                'rule_type': 'loitering',
                'name': f"Loitering > {time_sec}s",
                'raw_text': text,
                'parameters': {
                    'time_threshold': time_sec,
                    'pixel_radius': 50.0
                },
                'severity': 'medium',
                'explanation': f"Alert will trigger when any tracked person remains stationary within 50px for over {time_sec} seconds."
            }

    # 4. Check Zone Violation
    for pat in SUPPORTED_CAPABILITIES['zone_violation']:
        match = re.search(pat, cleaned)
        if match:
            zone_idx = None
            if match.groups() and match.group(1):
                try:
                    zone_idx = int(match.group(1)) - 1
                except ValueError:
                    zone_idx = None
            return {
                'is_supported': True,
                'rule_type': 'zone_violation',
                'name': f"Restricted Zone" + (f" {zone_idx + 1}" if zone_idx is not None else ""),
                'raw_text': text,
                'parameters': {
                    'zone_index': zone_idx
                },
                'severity': 'high',
                'explanation': f"Alert will trigger when any person enters " + (f"restricted zone {zone_idx + 1}." if zone_idx is not None else "any restricted zone.")
            }

    # 5. Check Fighting / Physical Altercation
    for pat in SUPPORTED_CAPABILITIES['fight']:
        if re.search(pat, cleaned):
            return {
                'is_supported': True,
                'rule_type': 'fight',
                'name': "Physical Altercation Alert",
                'raw_text': text,
                'parameters': {
                    'velocity_threshold': 15.0,
                    'require_proximity': True
                },
                'severity': 'critical',
                'explanation': "Alert will trigger when two or more proximate persons exhibit rapid joint movements characteristic of a physical altercation."
            }

    # 6. Check Fall / Person Down
    for pat in SUPPORTED_CAPABILITIES['fall']:
        if re.search(pat, cleaned):
            return {
                'is_supported': True,
                'rule_type': 'fall',
                'name': "Person Down / Fall Alert",
                'raw_text': text,
                'parameters': {
                    'aspect_ratio_threshold': 1.05,
                    'confirmation_frames': 10
                },
                'severity': 'high',
                'explanation': "Alert will trigger when an individual experiences a rapid downward collapse or remains horizontal on the ground."
            }

    # 7. Check Running / Panic
    for pat in SUPPORTED_CAPABILITIES['running_panic']:
        if re.search(pat, cleaned):
            is_panic = ('panic' in cleaned or 'dispersion' in cleaned or 'scatter' in cleaned)
            return {
                'is_supported': True,
                'rule_type': 'panic_running',
                'name': "Crowd Panic / Sudden Dispersion" if is_panic else "Rapid Running Alert",
                'raw_text': text,
                'parameters': {
                    'running_speed_threshold': 16.0,
                    'is_collective': is_panic
                },
                'severity': 'critical' if is_panic else 'medium',
                'explanation': "Alert will trigger when collective sudden acceleration occurs across the crowd." if is_panic else "Alert will trigger when an individual sprints or runs rapidly."
            }

    # 8. Tripwire Line Crossing
    for pat in SUPPORTED_CAPABILITIES['tripwire']:
        if re.search(pat, cleaned):
            return {
                'is_supported': True,
                'rule_type': 'tripwire',
                'name': "Tripwire Line Crossing",
                'raw_text': text,
                'parameters': {},
                'severity': 'low',
                'explanation': "Counts and alerts upon entry or exit crossings across the configured virtual tripwire."
            }

    # 9. Drive-by Snatching & Theft
    for pat in SUPPORTED_CAPABILITIES['snatching']:
        if re.search(pat, cleaned):
            return {
                'is_supported': True,
                'rule_type': 'snatching',
                'name': "Drive-by Snatching & Theft Alert",
                'raw_text': text,
                'parameters': {
                    'intercept_distance': 85.0,
                    'min_escape_speed': 10.0
                },
                'severity': 'critical',
                'explanation': "Alert will trigger when a motorcycle, bicycle, or fast runner intercepts a pedestrian at close range and rapidly flees."
            }

    # Generic Fallback: Not understood
    return {
        'is_supported': False,
        'rule_type': 'unknown',
        'raw_text': text,
        'explanation': f"Could not match '{text}' to any supported anomaly rules.",
        'unsupported_reason': "Please specify a supported rule, such as crowd counting, loitering time, zone entry, fighting, falls, snatching, or running."
    }


class RuleEvaluator:
    """Evaluates active rules against frame-level detections and tracks."""
    
    def __init__(self, rules: Optional[List[Dict[str, Any]]] = None):
        self.rules = rules or []
        
    def set_rules(self, rules: List[Dict[str, Any]]):
        self.rules = rules
        
    def evaluate(
        self,
        frame_num: int,
        tracks: List[Dict],
        zones: List[List[Tuple[float, float]]],
        anomaly_results: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Evaluate all active rules and return triggered alerts.
        """
        triggered_alerts = []
        
        for rule in self.rules:
            if not rule.get('is_active', True):
                continue
                
            rule_type = rule.get('rule_type')
            config = rule.get('config', {})
            rule_id = rule.get('rule_id', 'custom_rule')
            rule_name = rule.get('name', 'Custom Rule')
            
            # 1. Overcrowding rule
            if rule_type == 'overcrowding':
                thresh = config.get('threshold', 10)
                zone_idx = config.get('zone_index')
                
                # If zone_index specified, count people inside that zone
                if zone_idx is not None and 0 <= zone_idx < len(zones):
                    from shapely.geometry import Point, Polygon
                    poly = Polygon(zones[zone_idx])
                    count = 0
                    for trk in tracks:
                        bbox = trk.get('bbox', [0, 0, 0, 0])
                        cx = (bbox[0] + bbox[2]) / 2.0
                        cy = (bbox[1] + bbox[3]) / 2.0
                        if poly.contains(Point(cx, cy)):
                            count += 1
                else:
                    count = len(tracks)
                    
                if count > thresh:
                    triggered_alerts.append({
                        'event_type': 'custom_rule',
                        'rule_id': rule_id,
                        'rule_name': rule_name,
                        'severity': rule.get('severity', 'high'),
                        'confidence': 0.9,
                        'details': {
                            'rule_type': 'overcrowding',
                            'threshold': thresh,
                            'current_count': count,
                            'zone_index': zone_idx,
                            'message': f"Rule '{rule_name}' triggered: {count} people > {thresh}"
                        }
                    })
                    
            # 2. Zone violation rule
            elif rule_type == 'zone_violation':
                target_zone = config.get('zone_index')
                zone_res = anomaly_results.get('zone_violation', {})
                if zone_res.get('is_violation'):
                    violated = zone_res.get('violated_zones', [])
                    if target_zone is None or target_zone in violated:
                        triggered_alerts.append({
                            'event_type': 'custom_rule',
                            'rule_id': rule_id,
                            'rule_name': rule_name,
                            'severity': 'high',
                            'confidence': 0.95,
                            'details': {
                                'rule_type': 'zone_violation',
                                'target_zone': target_zone,
                                'violated_zones': violated,
                                'message': f"Rule '{rule_name}' triggered: unauthorized zone entry"
                            }
                        })
                        
            # 3. Fight rule
            elif rule_type == 'fight':
                fight_res = anomaly_results.get('fight', {})
                if fight_res.get('is_fight'):
                    triggered_alerts.append({
                        'event_type': 'custom_rule',
                        'rule_id': rule_id,
                        'rule_name': rule_name,
                        'severity': 'critical',
                        'confidence': fight_res.get('confidence', 0.85),
                        'details': {
                            'rule_type': 'fight',
                            'track_id': fight_res.get('track_id'),
                            'message': f"Rule '{rule_name}' triggered: physical altercation confirmed"
                        }
                    })
                    
            # 4. Fall rule
            elif rule_type == 'fall':
                fall_res = anomaly_results.get('fall', {})
                if fall_res.get('is_fall'):
                    triggered_alerts.append({
                        'event_type': 'custom_rule',
                        'rule_id': rule_id,
                        'rule_name': rule_name,
                        'severity': 'high',
                        'confidence': fall_res.get('confidence', 0.8),
                        'details': {
                            'rule_type': 'fall',
                            'track_id': fall_res.get('track_id'),
                            'message': f"Rule '{rule_name}' triggered: person collapse detected"
                        }
                    })
                    
            # 5. Panic / Running rule
            elif rule_type == 'panic_running':
                panic_res = anomaly_results.get('panic_running', {})
                is_collective = config.get('is_collective', False)
                
                if (is_collective and panic_res.get('is_panic')) or (not is_collective and panic_res.get('is_running')):
                    triggered_alerts.append({
                        'event_type': 'custom_rule',
                        'rule_id': rule_id,
                        'rule_name': rule_name,
                        'severity': 'critical' if is_collective else 'medium',
                        'confidence': panic_res.get('confidence', 0.75),
                        'details': {
                            'rule_type': 'panic_running',
                            'running_count': panic_res.get('running_count', 0),
                            'message': f"Rule '{rule_name}' triggered: unusual motion detected"
                        }
                    })

            # 6. Snatching / Theft rule
            elif rule_type == 'snatching':
                snatch_res = anomaly_results.get('snatching', {})
                if snatch_res.get('is_snatching'):
                    triggered_alerts.append({
                        'event_type': 'custom_rule',
                        'rule_id': rule_id,
                        'rule_name': rule_name,
                        'severity': 'critical',
                        'confidence': snatch_res.get('confidence', 0.9),
                        'details': {
                            'rule_type': 'snatching',
                            'suspect_id': snatch_res.get('suspect_id'),
                            'victim_id': snatch_res.get('victim_id'),
                            'suspect_class': snatch_res.get('suspect_class'),
                            'message': f"Rule '{rule_name}' triggered: drive-by snatching detected"
                        }
                    })
                    
        return triggered_alerts
