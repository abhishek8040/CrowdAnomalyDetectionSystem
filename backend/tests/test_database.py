"""
Test Database Persistence Module
"""
import pytest
import os
import database


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    """Use a temporary database file for testing"""
    db_file = tmp_path / "test_anomaly.db"
    monkeypatch.setattr(database, "DB_FILE", db_file)
    monkeypatch.setattr(database, "DB_DIR", tmp_path)
    database.init_db()


def test_save_and_get_events():
    """Test saving and retrieving anomaly events"""
    evt = database.save_event(
        event_type="overcrowding",
        details={"current_count": 12, "threshold": 10},
        frame_number=42,
        camera_id="cam_east",
        severity="high",
        confidence=0.95
    )
    assert evt["event_id"] is not None
    assert evt["status"] == "new"

    # Fetch events
    res = database.get_events()
    assert res["total"] == 1
    assert len(res["events"]) == 1
    saved = res["events"][0]
    assert saved["event_type"] == "overcrowding"
    assert saved["details"]["current_count"] == 12
    assert saved["severity"] == "high"


def test_filter_events():
    """Test filtering events by type, severity, and status"""
    database.save_event("loitering", {"dwell": 45}, frame_number=10, severity="medium")
    database.save_event("fight", {"arm_vel": 22}, frame_number=20, severity="critical")
    database.save_event("fall", {"ar": 1.5}, frame_number=30, severity="high")

    # Filter by severity
    res_crit = database.get_events(severity="critical")
    assert res_crit["total"] == 1
    assert res_crit["events"][0]["event_type"] == "fight"

    # Filter by event_type
    res_fall = database.get_events(event_type="fall")
    assert res_fall["total"] == 1
    assert res_fall["events"][0]["event_type"] == "fall"


def test_acknowledge_and_resolve_event():
    """Test updating event status to acknowledged and resolved"""
    evt = database.save_event("zone_violation", {"zone": 1})
    event_id = evt["event_id"]

    # Acknowledge
    ok_ack = database.acknowledge_event(event_id, acknowledged_by="security_officer_1")
    assert ok_ack is True

    item = database.get_event_by_id(event_id)
    assert item["status"] == "acknowledged"
    assert item["acknowledged_by"] == "security_officer_1"
    assert item["acknowledged_at"] is not None

    # Resolve
    ok_res = database.resolve_event(event_id, notes="Security dispatched, area cleared")
    assert ok_res is True

    item = database.get_event_by_id(event_id)
    assert item["status"] == "resolved"
    assert "Security dispatched" in item["resolution_notes"]


def test_delete_and_clear_events():
    """Test deleting single event and clearing all events"""
    e1 = database.save_event("loitering", {})
    e2 = database.save_event("fall", {})

    database.delete_event(e1["event_id"])
    res = database.get_events()
    assert res["total"] == 1

    cleared = database.clear_events()
    assert cleared == 1
    res_after = database.get_events()
    assert res_after["total"] == 0


def test_rules_persistence():
    """Test creating, listing, toggling, and deleting detection rules"""
    rule = database.save_rule(
        name="Crowd Over 8",
        rule_type="overcrowding",
        config={"threshold": 8},
        natural_language="Alert when crowd exceeds 8 people"
    )
    assert rule["rule_id"] is not None

    rules = database.get_rules()
    assert len(rules) == 1
    assert rules[0]["name"] == "Crowd Over 8"
    assert rules[0]["is_active"] is True

    # Toggle
    database.toggle_rule(rule["rule_id"], False)
    rules_after = database.get_rules()
    assert rules_after[0]["is_active"] is False

    # Delete
    database.delete_rule(rule["rule_id"])
    assert len(database.get_rules()) == 0
