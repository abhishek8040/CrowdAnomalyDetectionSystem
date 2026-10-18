"""
Database Persistence Layer
SQLite storage for anomaly events, operator rules, and system audits.
"""
import sqlite3
import json
import os
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)

DB_DIR = Path(__file__).resolve().parent / "data"
DB_FILE = DB_DIR / "anomaly_system.db"


_tables_initialized = False


def _create_tables(conn: sqlite3.Connection):
    """Internal helper to ensure tables and indexes exist."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT UNIQUE NOT NULL,
            event_type TEXT NOT NULL,
            camera_id TEXT NOT NULL DEFAULT 'camera_0',
            severity TEXT NOT NULL DEFAULT 'medium',
            confidence REAL NOT NULL DEFAULT 1.0,
            frame_number INTEGER NOT NULL DEFAULT 0,
            timestamp TEXT NOT NULL,
            details TEXT,
            snapshot TEXT,
            status TEXT NOT NULL DEFAULT 'new',
            acknowledged_at TEXT,
            acknowledged_by TEXT,
            resolved_at TEXT,
            resolution_notes TEXT
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            natural_language TEXT,
            rule_type TEXT NOT NULL,
            config TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_severity ON events(severity);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_camera ON events(camera_id);")
    conn.commit()


def get_db_connection() -> sqlite3.Connection:
    """Create and return a configured SQLite connection with guaranteed tables."""
    global _tables_initialized
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_FILE), timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    if not _tables_initialized:
        _create_tables(conn)
        _tables_initialized = True
    return conn


def init_db():
    """Explicitly initialize database tables."""
    with get_db_connection() as conn:
        _create_tables(conn)
    logger.info(f"Database initialized at {DB_FILE}")


def save_event(
    event_type: str,
    details: Dict[str, Any],
    frame_number: int = 0,
    camera_id: str = "camera_0",
    severity: str = "medium",
    confidence: float = 1.0,
    snapshot: Optional[str] = None,
    timestamp: Optional[str] = None
) -> Dict[str, Any]:
    """Insert a new anomaly event into the database."""
    event_id = str(uuid.uuid4())
    ts = timestamp or datetime.now().isoformat()
    details_json = json.dumps(details or {})
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO events (
                event_id, event_type, camera_id, severity, confidence,
                frame_number, timestamp, details, snapshot, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'new')
        """, (
            event_id, event_type, camera_id, severity, confidence,
            frame_number, ts, details_json, snapshot
        ))
        conn.commit()
    
    return {
        "event_id": event_id,
        "event_type": event_type,
        "camera_id": camera_id,
        "severity": severity,
        "confidence": confidence,
        "frame_number": frame_number,
        "timestamp": ts,
        "details": details,
        "snapshot": snapshot,
        "status": "new"
    }


def get_events(
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    camera_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> Dict[str, Any]:
    """Retrieve filtered events with pagination."""
    query = "SELECT * FROM events WHERE 1=1"
    params = []
    
    if event_type and event_type != "all":
        query += " AND event_type = ?"
        params.append(event_type)
        
    if severity and severity != "all":
        query += " AND severity = ?"
        params.append(severity)
        
    if status and status != "all":
        query += " AND status = ?"
        params.append(status)
        
    if camera_id and camera_id != "all":
        query += " AND camera_id = ?"
        params.append(camera_id)
        
    if start_date:
        query += " AND timestamp >= ?"
        params.append(start_date)
        
    if end_date:
        query += " AND timestamp <= ?"
        params.append(end_date)
        
    if search:
        query += " AND (event_type LIKE ? OR details LIKE ? OR resolution_notes LIKE ?)"
        wildcard = f"%{search}%"
        params.extend([wildcard, wildcard, wildcard])
        
    # Count total
    count_query = f"SELECT COUNT(*) as total FROM ({query})"
    
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params_for_query = list(params) + [limit, offset]
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(count_query, params)
        total = cursor.fetchone()["total"]
        
        cursor.execute(query, params_for_query)
        rows = cursor.fetchall()
        
    events = []
    for row in rows:
        evt = dict(row)
        try:
            evt["details"] = json.loads(evt["details"]) if evt["details"] else {}
        except Exception:
            pass
        events.append(evt)
        
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "events": events
    }


def get_event_by_id(event_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a single event by event_id."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()
        if not row:
            return None
        evt = dict(row)
        try:
            evt["details"] = json.loads(evt["details"]) if evt["details"] else {}
        except Exception:
            pass
        return evt


def acknowledge_event(event_id: str, acknowledged_by: str = "operator") -> bool:
    """Mark an event as acknowledged."""
    now = datetime.now().isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE events
            SET status = 'acknowledged', acknowledged_at = ?, acknowledged_by = ?
            WHERE event_id = ?
        """, (now, acknowledged_by, event_id))
        conn.commit()
        return cursor.rowcount > 0


def resolve_event(event_id: str, notes: str = "") -> bool:
    """Mark an event as resolved."""
    now = datetime.now().isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE events
            SET status = 'resolved', resolved_at = ?, resolution_notes = ?
            WHERE event_id = ?
        """, (now, notes, event_id))
        conn.commit()
        return cursor.rowcount > 0


def delete_event(event_id: str) -> bool:
    """Delete an event by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM events WHERE event_id = ?", (event_id,))
        conn.commit()
        return cursor.rowcount > 0


def clear_events() -> int:
    """Clear all events from the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM events")
        conn.commit()
        return cursor.rowcount


def get_events_summary() -> Dict[str, Any]:
    """Get aggregated summary of events by type, severity, and status."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as total FROM events")
        total = cursor.fetchone()["total"]
        
        cursor.execute("SELECT event_type, COUNT(*) as count FROM events GROUP BY event_type")
        by_type = {row["event_type"]: row["count"] for row in cursor.fetchall()}
        
        cursor.execute("SELECT severity, COUNT(*) as count FROM events GROUP BY severity")
        by_severity = {row["severity"]: row["count"] for row in cursor.fetchall()}
        
        cursor.execute("SELECT status, COUNT(*) as count FROM events GROUP BY status")
        by_status = {row["status"]: row["count"] for row in cursor.fetchall()}
        
    return {
        "total_events": total,
        "by_type": by_type,
        "by_severity": by_severity,
        "by_status": by_status
    }


# Rules Storage
def save_rule(
    name: str,
    rule_type: str,
    config: Dict[str, Any],
    natural_language: Optional[str] = None
) -> Dict[str, Any]:
    """Save a detection rule."""
    rule_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    config_json = json.dumps(config)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO rules (rule_id, name, natural_language, rule_type, config, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
        """, (rule_id, name, natural_language, rule_type, config_json, now, now))
        conn.commit()
        
    return {
        "rule_id": rule_id,
        "name": name,
        "natural_language": natural_language,
        "rule_type": rule_type,
        "config": config,
        "is_active": True,
        "created_at": now
    }


def get_rules(active_only: bool = False) -> List[Dict[str, Any]]:
    """Retrieve all saved detection rules."""
    query = "SELECT * FROM rules"
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY id DESC"
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        
    rules = []
    for row in rows:
        r = dict(row)
        r["is_active"] = bool(r["is_active"])
        try:
            r["config"] = json.loads(r["config"])
        except Exception:
            pass
        rules.append(r)
    return rules


def delete_rule(rule_id: str) -> bool:
    """Delete a rule by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM rules WHERE rule_id = ?", (rule_id,))
        conn.commit()
        return cursor.rowcount > 0


def toggle_rule(rule_id: str, is_active: bool) -> bool:
    """Toggle a rule active status."""
    now = datetime.now().isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE rules SET is_active = ?, updated_at = ? WHERE rule_id = ?
        """, (1 if is_active else 0, now, rule_id))
        conn.commit()
        return cursor.rowcount > 0
