"""KDT OS Learning Memory Engine V35

V35 turns verified proof into long-term learning memory.
It reads the V34 verified skill ledger and skill library, then answers:
- what has been proven
- what is getting stronger
- what is stale
- what should be refreshed next
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _parse_date(value: Any):
    if not value:
        return None
    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00").split("+")[0])
    except Exception:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d")
        except Exception:
            return None


def _days_since(value: Any) -> int | None:
    dt = _parse_date(value)
    if not dt:
        return None
    return max(0, (datetime.now() - dt).days)


def _load_skill_library(root: Path) -> Dict[str, Any]:
    data = _read_json(root / "skill_library" / "skills.json", {})
    return data if isinstance(data, dict) else {}


def _load_ledger(root: Path) -> List[Dict[str, Any]]:
    data = _read_json(root / "reports" / "verified_skill_ledger.json", [])
    return data if isinstance(data, list) else []


def _load_quests(root: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    qdir = root / "quests"
    for path in sorted(qdir.glob("*.json")) if qdir.exists() else []:
        q = _read_json(path, {})
        if isinstance(q, dict):
            q = dict(q)
            q["filename"] = path.name
            rows.append(q)
    return rows


def _proof_count(entry: Dict[str, Any]) -> int:
    completed = entry.get("completed_quests", []) if isinstance(entry.get("completed_quests"), list) else []
    submissions = entry.get("submissions", []) if isinstance(entry.get("submissions"), list) else []
    evidence = entry.get("evidence", []) if isinstance(entry.get("evidence"), list) else []
    return max(len(completed), len(submissions), len(evidence))


def _score(entry: Dict[str, Any]) -> int:
    raw = entry.get("verified_confidence") or entry.get("confidence") or 0
    try:
        return max(0, min(100, int(raw)))
    except Exception:
        return 0


def _status(score: int, proofs: int, stale_days: int | None) -> str:
    if proofs <= 0:
        return "Unverified"
    if stale_days is not None and stale_days >= 45:
        return "Needs Refresh"
    if score >= 90 and proofs >= 3:
        return "Strong"
    if score >= 70:
        return "Verified"
    if score >= 40:
        return "Practiced"
    return "Learning"


def _trend(entry: Dict[str, Any]) -> str:
    proofs = _proof_count(entry)
    score = _score(entry)
    days = _days_since(entry.get("last_verified_at") or entry.get("last_seen"))
    if proofs >= 3 and score >= 80:
        return "Growing"
    if days is not None and days >= 45:
        return "Stale"
    if proofs >= 1:
        return "Started"
    return "Unknown"


def _build_skill_memory(root: Path) -> List[Dict[str, Any]]:
    skills = _load_skill_library(root)
    ledger = _load_ledger(root)
    ledger_by_skill: Dict[str, List[Dict[str, Any]]] = {}
    for item in ledger:
        if isinstance(item, dict):
            ledger_by_skill.setdefault(str(item.get("skill", "General")), []).append(item)

    rows: List[Dict[str, Any]] = []
    for skill, entry in skills.items():
        if not isinstance(entry, dict):
            continue
        proofs = _proof_count(entry)
        score = _score(entry)
        first_verified = None
        dates = []
        for item in ledger_by_skill.get(skill, []):
            dt = _parse_date(item.get("at"))
            if dt:
                dates.append(dt)
        for item in entry.get("completed_quests", []) if isinstance(entry.get("completed_quests"), list) else []:
            if isinstance(item, dict):
                dt = _parse_date(item.get("at"))
                if dt:
                    dates.append(dt)
        if dates:
            first_verified = min(dates).isoformat(timespec="seconds")
        last_verified = entry.get("last_verified_at") or (max(dates).isoformat(timespec="seconds") if dates else None)
        stale_days = _days_since(last_verified)
        rows.append({
            "skill": skill,
            "score": score,
            "proof_count": proofs,
            "first_verified": first_verified,
            "last_verified": last_verified,
            "days_since_verified": stale_days,
            "status": _status(score, proofs, stale_days),
            "trend": _trend(entry),
            "projects": entry.get("projects", []) if isinstance(entry.get("projects"), list) else [],
            "recent_events": (ledger_by_skill.get(skill, [])[:5]),
        })
    rows.sort(key=lambda r: (r["proof_count"], r["score"]), reverse=True)
    return rows


def _timeline(root: Path) -> List[Dict[str, Any]]:
    ledger = _load_ledger(root)
    rows = []
    for item in ledger[:50]:
        if isinstance(item, dict):
            rows.append({
                "at": item.get("at"),
                "skill": item.get("skill", "Unknown"),
                "title": item.get("quest_title") or item.get("quest_filename") or "Verified proof",
                "result": item.get("result", "promoted"),
            })
    return rows


def _quest_activity(root: Path) -> Dict[str, Any]:
    quests = _load_quests(root)
    verification = [q for q in quests if "verification" in str(q.get("quest_type", q.get("type", ""))).lower()]
    verified = [q for q in verification if str(q.get("status", "")).lower() == "verified" or q.get("skill_promoted_at")]
    assigned = [q for q in verification if q not in verified]
    return {"total_verification_quests": len(verification), "verified_quests": len(verified), "assigned_verification_quests": len(assigned)}


def learning_memory_snapshot(kdt: Any) -> Dict[str, Any]:
    root = Path(kdt.APP_ROOT)
    skills = _build_skill_memory(root)
    timeline = _timeline(root)
    quest_activity = _quest_activity(root)
    strong = [s for s in skills if s["status"] in {"Strong", "Verified"}]
    stale = [s for s in skills if s["status"] == "Needs Refresh"]
    unproven_seen = [s for s in skills if s["proof_count"] == 0]
    next_refresh = stale[0] if stale else (unproven_seen[0] if unproven_seen else (skills[-1] if skills else None))
    total_proofs = sum(s["proof_count"] for s in skills)
    memory_strength = 0
    if skills:
        memory_strength = round((len(strong) / len(skills)) * 70 + min(30, total_proofs * 3))
    snapshot = {
        "version": "V35",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "tracked_skills": len(skills),
        "proof_items": total_proofs,
        "strong_skills": len(strong),
        "stale_skills": len(stale),
        "memory_strength": min(100, memory_strength),
        "skills": skills,
        "strongest": strong[:8],
        "stale": stale[:8],
        "timeline": timeline,
        "next_refresh": next_refresh,
        "quest_activity": quest_activity,
        "rule": "A skill is not long-term memory until KDT OS can show when it was proven, how often it was proven, and whether it needs refresh.",
    }
    _write_json(root / "reports" / "learning_memory.json", snapshot)
    _write_json(root / "reports" / "skill_timeline.json", timeline)
    return snapshot


def install(kdt: Any) -> None:
    app = kdt.app

    def learning_memory():
        return kdt.render_template("learning_memory.html", data=learning_memory_snapshot(kdt))

    def learning_memory_json():
        return kdt.jsonify(learning_memory_snapshot(kdt))

    app.add_url_rule("/learning_memory", "learning_memory", learning_memory, methods=["GET"])
    app.add_url_rule("/learning_memory.json", "learning_memory_json", learning_memory_json, methods=["GET"])
    kdt.learning_memory_snapshot_v35 = lambda: learning_memory_snapshot(kdt)
