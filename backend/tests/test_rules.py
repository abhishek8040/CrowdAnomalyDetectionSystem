"""
Test Natural Language Rule Engine
"""
import pytest
from anomaly.rule_engine import parse_natural_language_rule, RuleEvaluator


def test_parse_overcrowding_rule():
    """Test parsing overcrowding natural language statements"""
    r1 = parse_natural_language_rule("Alert when the crowd exceeds 7 people")
    assert r1['is_supported'] is True
    assert r1['rule_type'] == 'overcrowding'
    assert r1['parameters']['threshold'] == 7

    r2 = parse_natural_language_rule("Notify if more than 15 people in zone 2")
    assert r2['is_supported'] is True
    assert r2['rule_type'] == 'overcrowding'
    assert r2['parameters']['threshold'] == 15
    assert r2['parameters']['zone_index'] == 1


def test_parse_loitering_rule():
    """Test parsing loitering rules"""
    r1 = parse_natural_language_rule("Alert if anyone loiters for longer than 45 seconds")
    assert r1['is_supported'] is True
    assert r1['rule_type'] == 'loitering'
    assert r1['parameters']['time_threshold'] == 45

    r2 = parse_natural_language_rule("Warn when a person is standing still for 2 minutes")
    assert r2['is_supported'] is True
    assert r2['rule_type'] == 'loitering'
    assert r2['parameters']['time_threshold'] == 120


def test_parse_fight_and_fall_rules():
    """Test parsing physical altercations and fall rules"""
    r_fight = parse_natural_language_rule("Alert when people appear to be fighting")
    assert r_fight['is_supported'] is True
    assert r_fight['rule_type'] == 'fight'
    assert r_fight['severity'] == 'critical'

    r_fall = parse_natural_language_rule("Alert if a person falls or collapses on the floor")
    assert r_fall['is_supported'] is True
    assert r_fall['rule_type'] == 'fall'
    assert r_fall['severity'] == 'high'


def test_parse_running_and_panic_rules():
    """Test parsing running and crowd panic rules"""
    r_run = parse_natural_language_rule("Alert if anyone is running fast")
    assert r_run['is_supported'] is True
    assert r_run['rule_type'] == 'panic_running'

    r_panic = parse_natural_language_rule("Alert on sudden crowd panic dispersion")
    assert r_panic['is_supported'] is True
    assert r_panic['rule_type'] == 'panic_running'
    assert r_panic['severity'] == 'critical'


def test_unsupported_rules_rejection():
    """Verify that unsupported requirements are rejected with clear explanations"""
    r_weapon = parse_natural_language_rule("Alert if someone pulls out a gun or firearm")
    assert r_weapon['is_supported'] is False
    assert r_weapon['domain'] == 'weapon'
    assert 'weapon' in r_weapon['unsupported_reason'].lower()

    r_bag = parse_natural_language_rule("Detect abandoned backpack or unattended luggage")
    assert r_bag['is_supported'] is False
    assert r_bag['domain'] == 'luggage_abandonment'
    assert 'luggage' in r_bag['unsupported_reason'].lower()

    r_face = parse_natural_language_rule("Recognize face of suspect from blacklist")
    assert r_face['is_supported'] is False
    assert r_face['domain'] == 'facial_recognition'


def test_rule_evaluator():
    """Test evaluation of active rules against frame tracks and results"""
    rules = [
        {
            'rule_id': 'rule_1',
            'name': 'Max 3 People',
            'rule_type': 'overcrowding',
            'config': {'threshold': 3},
            'is_active': True
        },
        {
            'rule_id': 'rule_2',
            'name': 'Fight Alert',
            'rule_type': 'fight',
            'config': {},
            'is_active': True
        }
    ]
    evaluator = RuleEvaluator(rules)

    tracks = [
        {'id': 1, 'bbox': [10, 10, 50, 90]},
        {'id': 2, 'bbox': [60, 10, 100, 90]},
        {'id': 3, 'bbox': [110, 10, 150, 90]},
        {'id': 4, 'bbox': [160, 10, 200, 90]},
    ]
    anomaly_results = {
        'fight': {'is_fight': True, 'track_id': 1, 'confidence': 0.9}
    }

    triggered = evaluator.evaluate(1, tracks, [], anomaly_results)
    assert len(triggered) == 2
    types = [t['details']['rule_type'] for t in triggered]
    assert 'overcrowding' in types
    assert 'fight' in types
