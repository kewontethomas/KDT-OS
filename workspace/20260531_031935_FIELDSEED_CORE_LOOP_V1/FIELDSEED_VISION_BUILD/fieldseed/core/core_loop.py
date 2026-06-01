import json
import hashlib
from datetime import datetime

from fieldseed.paths import LOGS
from .database import connect, now, self_check_record, add_improvement
from .agent_loop import run_health_check
from .self_healing import visual_self_inspection, list_repair_candidates

CORE_LOG = LOGS / "core_loop"
CORE_LOG.mkdir(parents=True, exist_ok=True)

def fp(*parts):
    return hashlib.sha256("|".join(str(x or "") for x in parts).encode()).hexdigest()[:16]

def add_event(event_type, title, details="", source="core_loop", severity="Info"):
    fingerprint = fp(event_type, title, details[:300])
    con = connect()
    exists = con.execute("SELECT id FROM observer_events WHERE fingerprint=? LIMIT 1", (fingerprint,)).fetchone()
    if not exists:
        con.execute(
            "INSERT INTO observer_events(created_at,event_type,source,severity,title,details,fingerprint) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (now(), event_type, source, severity, title, details, fingerprint)
        )
    con.commit()
    con.close()

def write_memory(memory_type, title, details="", source="core_loop", confidence=30, success=False, failure=False):
    con = connect()
    row = con.execute(
        "SELECT id,confidence,success_count,failure_count FROM seed_memory WHERE memory_type=? AND title=? ORDER BY id DESC LIMIT 1",
        (memory_type, title)
    ).fetchone()
    if row:
        mid, old_conf, sc, fc = row
        delta = 10 if success else -10 if failure else 2
        new_conf = max(0, min(100, (old_conf or 0) + delta))
        con.execute(
            "UPDATE seed_memory SET details=?, confidence=?, success_count=?, failure_count=?, last_seen=? WHERE id=?",
            (details, new_conf, sc + (1 if success else 0), fc + (1 if failure else 0), now(), mid)
        )
    else:
        con.execute(
            "INSERT INTO seed_memory(created_at,memory_type,source,title,details,confidence,success_count,failure_count,last_seen) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (now(), memory_type, source, title, details, confidence, 1 if success else 0, 1 if failure else 0, now())
        )
    con.commit()
    con.close()

def observe_health():
    result = run_health_check()
    failures = result.get("failures", [])
    if failures:
        add_event("compile_failure", "Python compile failure", json.dumps(failures[:5]), "health", "High")
        write_memory("system_flaw", "Python compile failure", json.dumps(failures[:5]), "health", 90, failure=True)
    else:
        write_memory("system_strength", "Python compile healthy", f"{result.get('checked')} files checked.", "health", 60, success=True)
    return result

def observe_tickets():
    con = connect()
    open_rows = con.execute("SELECT id,title,next_action FROM tickets WHERE status!='Closed' ORDER BY updated_at DESC LIMIT 20").fetchall()
    closed = con.execute("SELECT id,title,root_cause,resolution FROM tickets WHERE status='Closed' ORDER BY updated_at DESC LIMIT 10").fetchall()
    con.close()
    for tid, title, next_action in open_rows:
        add_event("open_ticket", f"Open ticket #{tid}: {title}", next_action or "", "tickets", "Info")
        write_memory("open_work", title, f"Ticket #{tid}. Next: {next_action}", "tickets", 25)
    for tid, title, root, resolution in closed:
        if resolution:
            write_memory("confirmed_resolution", title, f"Root cause: {root}\nResolution: {resolution}", "tickets", 70, success=True)
    return {"open": len(open_rows), "closed_recent": len(closed)}

def observe_repairs():
    con = connect()
    rows = con.execute("SELECT check_name,status,details,recommendation FROM self_checks ORDER BY id DESC LIMIT 50").fetchall()
    con.close()
    for name, status, details, rec in rows:
        if name == "self_repair":
            write_memory("repair_outcome", details or "Self repair", rec or "", "self_checks", 50, success=(status=="OK"), failure=(status!="OK"))
            add_event("repair_outcome", details or "Self repair", rec or "", "self_checks", "Info" if status=="OK" else "Warning")
    return {"seen": len(rows)}

def detect_patterns():
    con = connect()
    rows = con.execute("""
        SELECT event_type,title,COUNT(*) FROM observer_events
        GROUP BY event_type,title
        HAVING COUNT(*) >= 2
        ORDER BY COUNT(*) DESC
        LIMIT 20
    """).fetchall()
    con.close()
    patterns = []
    for event_type, title, count in rows:
        patterns.append({"event_type": event_type, "title": title, "count": count})
        write_memory("repeated_pattern", title, f"Repeated {count} times.", "pattern_detector", min(90, 30 + count*10))
        if count >= 3:
            add_improvement("pattern_detector", f"Repeated issue: {title}", f"Repeated {count} times.", "Review whether Seed can automate or reduce this repeated issue.")
    return patterns

def core_loop_tick(run_deep=False):
    summary = {"started_at": now()}
    try:
        summary["health"] = observe_health()
    except Exception as e:
        add_event("observer_error", "Health observer failed", str(e), "core_loop", "High")
    try:
        summary["tickets"] = observe_tickets()
    except Exception as e:
        add_event("observer_error", "Ticket observer failed", str(e), "core_loop", "High")
    try:
        summary["repairs"] = observe_repairs()
    except Exception as e:
        add_event("observer_error", "Repair observer failed", str(e), "core_loop", "High")
    if run_deep:
        try:
            summary["self_inspection"] = visual_self_inspection()
        except Exception as e:
            add_event("observer_error", "Self-inspection failed", str(e), "core_loop", "High")
    try:
        summary["patterns"] = detect_patterns()
    except Exception as e:
        add_event("observer_error", "Pattern detector failed", str(e), "core_loop", "High")
    try:
        summary["repair_queue"] = list_repair_candidates()
    except Exception:
        summary["repair_queue"] = []
    out = CORE_LOG / f"core_loop_tick_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    self_check_record("core_loop", "OK", "Core loop tick completed", str(out))
    return summary

def recent_core_memory(limit=50):
    con = connect()
    rows = con.execute("SELECT created_at,memory_type,title,details,confidence,success_count,failure_count,last_seen FROM seed_memory ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    con.close()
    return rows

def recent_observer_events(limit=50):
    con = connect()
    rows = con.execute("SELECT created_at,event_type,severity,title,details FROM observer_events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    con.close()
    return rows
