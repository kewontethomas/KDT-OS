import sqlite3
from datetime import datetime
from fieldseed.paths import DB

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT DEFAULT 'Open',
    site TEXT DEFAULT '',
    contact_name TEXT DEFAULT '',
    contact_phone TEXT DEFAULT '',
    contact_email TEXT DEFAULT '',
    category TEXT DEFAULT 'Unknown',
    confirmed_system TEXT DEFAULT 'Unknown',
    access_mode TEXT DEFAULT 'Unknown',
    access_tool TEXT DEFAULT '',
    raw_intake TEXT DEFAULT '',
    confirmed_facts TEXT DEFAULT '',
    unknowns TEXT DEFAULT '',
    next_action TEXT DEFAULT '',
    completeness INTEGER DEFAULT 0,
    root_cause TEXT DEFAULT '',
    resolution TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS timeline (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER,
    created_at TEXT NOT NULL,
    note TEXT DEFAULT '',
    result TEXT DEFAULT '',
    evidence_path TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    source_ticket_id INTEGER,
    pattern TEXT NOT NULL,
    category TEXT DEFAULT '',
    confirmed_system TEXT DEFAULT '',
    symptoms TEXT DEFAULT '',
    root_cause TEXT DEFAULT '',
    fix TEXT DEFAULT '',
    confidence INTEGER DEFAULT 100,
    confirmed INTEGER DEFAULT 1,
    success_count INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS evidence_packages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    package_path TEXT NOT NULL,
    hostname TEXT DEFAULT '',
    summary TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS self_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    check_name TEXT NOT NULL,
    status TEXT NOT NULL,
    details TEXT DEFAULT '',
    recommendation TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS improvement_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    source TEXT DEFAULT '',
    issue TEXT NOT NULL,
    evidence TEXT DEFAULT '',
    suggested_fix TEXT DEFAULT '',
    status TEXT DEFAULT 'Backlog'
);

CREATE TABLE IF NOT EXISTS ai_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS seed_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    source TEXT DEFAULT '',
    title TEXT NOT NULL,
    details TEXT DEFAULT '',
    confidence INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    last_seen TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS observer_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    source TEXT DEFAULT '',
    severity TEXT DEFAULT 'Info',
    title TEXT NOT NULL,
    details TEXT DEFAULT '',
    fingerprint TEXT DEFAULT ''
);
"""

def now():
    return datetime.now().isoformat(timespec="seconds")

def connect():
    return sqlite3.connect(DB)

def ensure_column(con, table, column, definition):
    existing = {row[1] for row in con.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

def migrate_db():
    con = connect()
    con.executescript(SCHEMA)
    ensure_column(con, "tickets", "contact_name", "TEXT DEFAULT ''")
    ensure_column(con, "tickets", "contact_phone", "TEXT DEFAULT ''")
    ensure_column(con, "tickets", "contact_email", "TEXT DEFAULT ''")
    con.commit()
    con.close()

def init_db():
    migrate_db()

def self_check_record(name, status, details="", recommendation=""):
    con = connect()
    con.execute(
        "INSERT INTO self_checks(created_at, check_name, status, details, recommendation) VALUES (?, ?, ?, ?, ?)",
        (now(), name, status, details, recommendation)
    )
    con.commit()
    con.close()

def add_improvement(source, issue, evidence="", suggested_fix=""):
    con = connect()
    con.execute(
        "INSERT INTO improvement_queue(created_at, source, issue, evidence, suggested_fix) VALUES (?, ?, ?, ?, ?)",
        (now(), source, issue, evidence, suggested_fix)
    )
    con.commit()
    con.close()
