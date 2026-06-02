"""KDT OS Skill Refresh Engine V36

V36 closes the long-term learning loop:
Learn -> Verify -> Promote -> Remember -> Refresh.

A verified skill should become less trusted when it has not been practiced
recently. This engine builds a refresh queue from Learning Memory, verified
skill history, and current quest/project signals.
"""
from __future__ import annotations

import json
from datetime import datetime
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


def _load_learning_memory(kdt: Any) -> Dict[str, Any]:
    """Prefer the live V35 snapshot when available, then fall back to reports."""
    try:
        if hasattr(kdt, "learning_memory_snapshot_v35"):
            data = kdt.learning_memory_snapshot_v35()
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    root = Path(kdt.APP_ROOT)
    data = _read_json(root / "reports" / "learning_memory.json", {})
    return data if isinstance(data, dict) else {}


def _load_active_quests(root: Path) -> List[Dict[str, Any]]:
    quests: List[Dict[str, Any]] = []
    qdir = root / "quests"
    for path in sorted(qdir.glob("*.json")) if qdir.exists() else []:
        q = _read_json(path, {})
        if isinstance(q, dict):
            q = dict(q)
            q["filename"] = path.name
            quests.append(q)
    return quests


def _skill_importance(skill: str, quests: List[Dict[str, Any]]) -> int:
    """Estimate how important a skill is based on active quests and project-analysis quests."""
    skill_l = (skill or "").lower()
    score = 0
    for q in quests:
        blob = " ".join([
            str(q.get("skill", "")),
            str(q.get("title", "")),
            str(q.get("goal", "")),
            str(q.get("what_to_build", "")),
            " ".join(map(str, q.get("requirements", []) if isinstance(q.get("requirements"), list) else [])),
        ]).lower()
        if skill_l and skill_l in blob:
            score += 6
        if skill_l and str(q.get("skill", "")).lower() == skill_l:
            score += 10
        if "project_analysis" in str(q.get("source", "")).lower() or str(q.get("title", "")).lower().startswith("project analysis"):
            score += 2
    return min(score, 40)


def _risk_for_skill(skill: Dict[str, Any], importance: int) -> Dict[str, Any]:
    days = skill.get("days_since_verified")
    proof_count = int(skill.get("proof_count") or 0)
    score = int(skill.get("score") or 0)

    if proof_count <= 0:
        base = 70
        reason = "No proof has been promoted for this skill yet."
    elif days is None:
        base = 55
        reason = "KDT OS has proof, but no clear last-verified date."
    elif days <= 30:
        base = max(0, 10 - proof_count * 2)
        reason = "Recently verified."
    elif days <= 90:
        base = 35 + min(20, (days - 30) // 3)
        reason = "This skill is moving into review range."
    else:
        base = 75 + min(20, (days - 90) // 10)
        reason = "This skill has not been refreshed recently."

    if score >= 85:
        base -= 8
    elif score < 50:
        base += 10

    risk_score = max(0, min(100, base + importance // 3))

    if risk_score >= 75:
        level = "High"
    elif risk_score >= 45:
        level = "Medium"
    elif risk_score >= 20:
        level = "Low"
    else:
        level = "Healthy"

    return {"risk_score": risk_score, "risk_level": level, "reason": reason}


def _refresh_template(skill: str) -> Dict[str, Any]:
    s = (skill or "").lower()
    if "sqlite" in s:
        return {
            "title": "Refresh SQLite CRUD",
            "action": "Create or update one tiny SQLite table, insert one record, select it back, then explain the query.",
            "proof": "Upload app.py or .sql file plus a screenshot or copied terminal output.",
            "estimated_time": "20-35 minutes",
        }
    if "flask" in s:
        return {
            "title": "Refresh Flask Route",
            "action": "Create one route that returns visible text or JSON, then open it in the browser.",
            "proof": "Upload app.py and a screenshot of the route working.",
            "estimated_time": "15-25 minutes",
        }
    if "javascript" in s or "api" in s:
        return {
            "title": "Refresh Browser API Skill",
            "action": "Create a button that calls fetch(), reads JSON, and updates the page.",
            "proof": "Upload index.html/script.js and screenshot the displayed result.",
            "estimated_time": "20-35 minutes",
        }
    if "python" in s:
        return {
            "title": "Refresh Python Function",
            "action": "Write one function that accepts input, returns a result, and prints a test output.",
            "proof": "Upload the .py file and terminal output.",
            "estimated_time": "10-20 minutes",
        }
    if "active directory" in s or "ou" in s:
        return {
            "title": "Refresh Active Directory OU Reasoning",
            "action": "Draw or write a tiny OU structure and explain where one user, one computer, and one group should go.",
            "proof": "Upload a screenshot or written explanation.",
            "estimated_time": "10-20 minutes",
        }
    return {
        "title": f"Refresh {skill}",
        "action": f"Complete one tiny proof task that demonstrates {skill} without using a generated project as the only evidence.",
        "proof": "Upload a screenshot, code file, or written proof plus one sentence explaining what you proved.",
        "estimated_time": "10-25 minutes",
    }


def _build_refresh_rows(kdt: Any) -> List[Dict[str, Any]]:
    root = Path(kdt.APP_ROOT)
    memory = _load_learning_memory(kdt)
    skills = memory.get("skills", []) if isinstance(memory.get("skills"), list) else []
    quests = _load_active_quests(root)

    rows: List[Dict[str, Any]] = []
    for skill in skills:
        if not isinstance(skill, dict):
            continue
        name = str(skill.get("skill", "Unknown"))
        importance = _skill_importance(name, quests)
        risk = _risk_for_skill(skill, importance)
        template = _refresh_template(name)
        days = skill.get("days_since_verified")
        rows.append({
            "skill": name,
            "score": int(skill.get("score") or 0),
            "proof_count": int(skill.get("proof_count") or 0),
            "last_verified": skill.get("last_verified"),
            "days_since_verified": days,
            "status": skill.get("status", "Unknown"),
            "trend": skill.get("trend", "Unknown"),
            "importance": importance,
            "risk_score": risk["risk_score"],
            "risk_level": risk["risk_level"],
            "risk_reason": risk["reason"],
            "refresh_title": template["title"],
            "refresh_action": template["action"],
            "refresh_proof": template["proof"],
            "estimated_time": template["estimated_time"],
        })

    # If no memory exists yet, seed from active quest skills so page stays useful.
    if not rows:
        seen = {}
        for q in quests:
            name = str(q.get("skill") or "General")
            seen.setdefault(name, 0)
            seen[name] += 1
        for name, count in sorted(seen.items(), key=lambda x: x[1], reverse=True):
            template = _refresh_template(name)
            rows.append({
                "skill": name,
                "score": 0,
                "proof_count": 0,
                "last_verified": None,
                "days_since_verified": None,
                "status": "Unverified",
                "trend": "Unknown",
                "importance": min(40, count * 6),
                "risk_score": 80,
                "risk_level": "High",
                "risk_reason": "This skill appears in active quests but has no promoted proof yet.",
                "refresh_title": template["title"],
                "refresh_action": template["action"],
                "refresh_proof": template["proof"],
                "estimated_time": template["estimated_time"],
            })

    rows.sort(key=lambda r: (r["risk_score"], r["importance"], -r["proof_count"]), reverse=True)
    return rows


def skill_refresh_snapshot(kdt: Any) -> Dict[str, Any]:
    root = Path(kdt.APP_ROOT)
    rows = _build_refresh_rows(kdt)
    verified = [r for r in rows if r["proof_count"] > 0]
    needs_refresh = [r for r in rows if r["risk_level"] in {"High", "Medium"}]
    critical = [r for r in rows if r["risk_level"] == "High"]
    healthy = [r for r in rows if r["risk_level"] in {"Healthy", "Low"}]
    avg_days_values = [r["days_since_verified"] for r in verified if isinstance(r.get("days_since_verified"), int)]
    avg_days = round(sum(avg_days_values) / len(avg_days_values)) if avg_days_values else 0
    weekly_queue = needs_refresh[:7]

    snapshot = {
        "version": "V36",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "tracked_skills": len(rows),
        "verified_skills": len(verified),
        "need_refresh": len(needs_refresh),
        "critical_decay": len(critical),
        "average_days_since_practice": avg_days,
        "weekly_queue": weekly_queue,
        "critical": critical[:8],
        "healthy": healthy[:8],
        "all_skills": rows,
        "rule": "A verified skill must be refreshed over time or KDT OS should lower its trust and recommend practice.",
    }

    _write_json(root / "reports" / "skill_decay.json", snapshot)
    _write_json(root / "reports" / "refresh_queue.json", weekly_queue)
    return snapshot


def install(kdt: Any) -> None:
    app = kdt.app

    def skill_refresh():
        return kdt.render_template("skill_refresh.html", data=skill_refresh_snapshot(kdt))

    def skill_refresh_json():
        return kdt.jsonify(skill_refresh_snapshot(kdt))

    app.add_url_rule("/skill_refresh", "skill_refresh", skill_refresh, methods=["GET"])
    app.add_url_rule("/skill_refresh.json", "skill_refresh_json", skill_refresh_json, methods=["GET"])
    kdt.skill_refresh_snapshot_v36 = lambda: skill_refresh_snapshot(kdt)
