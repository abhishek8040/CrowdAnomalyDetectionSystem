"""
Test FastAPI Endpoints (Events, Rules, Health, Config)
"""
import pytest
from starlette.testclient import TestClient
import database
from main import app


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """Use a temporary database for API tests"""
    db_file = tmp_path / "api_test.db"
    monkeypatch.setattr(database, "DB_FILE", db_file)
    monkeypatch.setattr(database, "DB_DIR", tmp_path)
    database.init_db()


client = TestClient(app)


def test_health_and_root():
    """Verify health and root endpoints"""
    r_root = client.get("/")
    assert r_root.status_code == 200
    assert r_root.json()["status"] == "running"

    r_health = client.get("/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "healthy"


def test_config_endpoints():
    """Test getting and updating zone configurations"""
    r_config = client.get("/config")
    assert r_config.status_code == 200
    data = r_config.json()
    assert "overcrowding_threshold" in data
    assert "restricted_zones" in data

    # Update zones
    test_zones = [[[10, 10], [50, 10], [50, 50], [10, 50]]]
    r_zones = client.post("/config/zones", json=test_zones)
    assert r_zones.status_code == 200
    assert r_zones.json()["success"] is True


def test_events_api_crud():
    """Test full CRUD and status transitions on /api/events/"""
    # 1. Create event
    payload = {
        "event_type": "fall",
        "details": {"aspect_ratio": 1.6, "track_id": 4},
        "frame_number": 88,
        "camera_id": "lobby_cam",
        "severity": "high",
        "confidence": 0.9
    }
    r_create = client.post("/api/events/", json=payload)
    assert r_create.status_code == 200
    evt = r_create.json()["event"]
    event_id = evt["event_id"]
    assert evt["event_type"] == "fall"

    # 2. Get single event
    r_get = client.get(f"/api/events/{event_id}")
    assert r_get.status_code == 200
    assert r_get.json()["event_id"] == event_id

    # 3. List events with filter
    r_list = client.get("/api/events/?event_type=fall")
    assert r_list.status_code == 200
    assert r_list.json()["total"] == 1

    # 4. Acknowledge
    r_ack = client.patch(f"/api/events/{event_id}/acknowledge", json={"acknowledged_by": "guard_bob"})
    assert r_ack.status_code == 200
    assert r_ack.json()["status"] == "acknowledged"

    # 5. Resolve
    r_res = client.patch(f"/api/events/{event_id}/resolve", json={"notes": "Medic arrived"})
    assert r_res.status_code == 200
    assert r_res.json()["status"] == "resolved"

    # 6. Stats summary
    r_stats = client.get("/api/events/stats")
    assert r_stats.status_code == 200
    assert r_stats.json()["total_events"] == 1

    # 7. Delete event
    r_del = client.delete(f"/api/events/{event_id}")
    assert r_del.status_code == 200

    r_empty = client.get("/api/events/")
    assert r_empty.json()["total"] == 0


def test_rules_api():
    """Test Natural Language parsing and Rule management endpoints"""
    # 1. Parse rule
    r_parse = client.post("/api/rules/parse", json={"text": "Alert when crowd exceeds 12 people"})
    assert r_parse.status_code == 200
    res = r_parse.json()
    assert res["is_supported"] is True
    assert res["rule_type"] == "overcrowding"
    assert res["parameters"]["threshold"] == 12

    # 2. Save rule
    r_create = client.post("/api/rules/", json={
        "name": res["name"],
        "rule_type": res["rule_type"],
        "config": res["parameters"],
        "natural_language": res["raw_text"]
    })
    assert r_create.status_code == 200
    rule_id = r_create.json()["rule"]["rule_id"]

    # 3. List rules
    r_list = client.get("/api/rules/")
    assert r_list.status_code == 200
    assert len(r_list.json()) == 1

    # 4. Toggle rule
    r_toggle = client.patch(f"/api/rules/{rule_id}/toggle", json={"is_active": False})
    assert r_toggle.status_code == 200
    assert r_toggle.json()["is_active"] is False

    # 5. Delete rule
    r_del = client.delete(f"/api/rules/{rule_id}")
    assert r_del.status_code == 200


def test_snatching_api_flow():
    """Verify creating, querying, and parsing snatching events via REST endpoints"""
    # 1. Post snatching event
    payload = {
        "event_type": "snatching",
        "details": {
            "suspect_id": 2,
            "victim_id": 1,
            "suspect_class": "motorcycle",
            "victim_class": "person",
            "suspect_speed": 18.5,
            "victim_speed": 1.2
        },
        "frame_number": 45,
        "camera_id": "cctv_street",
        "severity": "critical",
        "confidence": 0.95
    }
    r_create = client.post("/api/events/", json=payload)
    assert r_create.status_code == 200
    event_id = r_create.json()["event"]["event_id"]

    # 2. Filter specifically for snatching
    r_filter = client.get("/api/events/?event_type=snatching")
    assert r_filter.status_code == 200
    data = r_filter.json()
    assert data["total"] == 1
    assert data["events"][0]["details"]["suspect_class"] == "motorcycle"

    # 3. Check stats breakdown
    r_stats = client.get("/api/events/stats")
    assert r_stats.status_code == 200
    assert r_stats.json()["by_type"]["snatching"] == 1

    # 4. Parse natural language rule for snatching
    r_nl = client.post("/api/rules/parse", json={"text": "Alert if two bike riders snatch from a pedestrian"})
    assert r_nl.status_code == 200
    nl_res = r_nl.json()
    assert nl_res["is_supported"] is True
    assert nl_res["rule_type"] == "snatching"
    assert nl_res["severity"] == "critical"
