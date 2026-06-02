"""KDT OS Learning Roadmaps V37

V37 turns current skill intelligence into direction:
- where Kewonte is on each learning path
- what comes next
- what skills are blocking a path
- which quest should move the path forward
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _json_files(folder: Path) -> List[Path]:
    try:
        return sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception:
        return []


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _skill_name(raw: Any) -> str:
    text = str(raw or "Unclassified").strip()
    text = re.sub(r"\s+", " ", text)
    key = text.lower().replace(".", "").strip()
    mapping = {
        "api / routes": "API / Routes",
        "api routes": "API / Routes",
        "apis": "API / Routes",
        "html css": "HTML/CSS",
        "html/css": "HTML/CSS",
        "sqlite": "SQLite",
        "database storage": "SQLite",
        "python": "Python",
        "javascript": "JavaScript",
        "flask": "Flask",
        "testing": "Testing",
        "health monitoring": "Health Monitoring",
        "active directory": "Active Directory",
        "active directory ous": "Active Directory",
        "cpu usage": "CPU Usage",
        "dashboard/ui": "HTML/CSS",
        "task management": "Task Management",
        "project tracking": "Project Tracking",
    }
    return mapping.get(key, text[:80])


def _quest_score(q: Dict[str, Any]) -> int:
    quality = q.get("quest_quality")
    if isinstance(quality, dict):
        try:
            return int(quality.get("score", 0))
        except Exception:
            return 0
    if isinstance(quality, (int, float)):
        return int(quality)
    return 0


def _quest_text(q: Dict[str, Any]) -> str:
    parts = [q.get("title"), q.get("goal"), q.get("what_to_build"), q.get("skill"), q.get("type")]
    parts += [str(x) for x in _as_list(q.get("requirements"))]
    parts += [str(x) for x in _as_list(q.get("success_criteria"))]
    return " ".join([str(p) for p in parts if p])


def _status_from_evidence(skill: str, evidence: Dict[str, Any]) -> str:
    key = skill.lower()
    if evidence["verified"].get(key, 0) > 0:
        return "Proven"
    if evidence["completed"].get(key, 0) > 0:
        return "Practiced"
    if evidence["strong_quests"].get(key, 0) > 0 or evidence["active_quests"].get(key, 0) > 0:
        return "Practicing"
    if evidence["projects"].get(key, 0) > 0:
        return "Seen"
    return "Missing"


def _score_for_status(status: str) -> int:
    return {"Proven": 100, "Practiced": 75, "Practicing": 55, "Seen": 30, "Missing": 0}.get(status, 0)


def _roadmaps() -> List[Dict[str, Any]]:
    return [
        {
            "name": "Python Developer Path",
            "mission": "Build reliable Python tools, automation scripts, and backend logic.",
            "steps": ["Python", "Variables", "Functions", "Lists", "Dictionaries", "File Handling", "JSON", "Error Handling", "Testing", "SQLite", "API / Routes", "Flask"],
        },
        {
            "name": "Web App Builder Path",
            "mission": "Build browser apps that look good, respond to clicks, save data, and use APIs.",
            "steps": ["HTML/CSS", "Responsive Layout", "JavaScript", "DOM Events", "Forms", "Local Storage", "Fetch/API", "API / Routes", "Testing"],
        },
        {
            "name": "Flask Backend Path",
            "mission": "Turn Python scripts into useful web tools with routes, templates, storage, and proof.",
            "steps": ["Python", "Flask", "Routes", "Templates", "Forms", "JSON", "SQLite", "Testing", "Project Structure", "Deployment"],
        },
        {
            "name": "SQLite & Data Path",
            "mission": "Store, update, query, and reason about real app data.",
            "steps": ["SQLite", "Tables", "INSERT", "SELECT", "UPDATE", "DELETE", "Filtering", "Relationships", "Reports", "Backup/Restore"],
        },
        {
            "name": "IT Support Growth Path",
            "mission": "Build field-ready support skills for Windows, servers, logs, AD, and automation.",
            "steps": ["Windows Troubleshooting", "CPU Usage", "Event Viewer", "Active Directory", "Group Policy", "PowerShell", "Networking", "Documentation", "Ticket System", "Automation/Scheduling"],
        },
        {
            "name": "KDT OS Builder Path",
            "mission": "Grow KDT OS from a Flask project into a personal learning and project operating system.",
            "steps": ["Project Tracking", "Quest System", "Evidence Collection", "Learning Intelligence", "Skill Verification", "Proof Promotion", "Learning Memory", "Skill Refresh", "Route Extraction", "Core Storage", "Testing", "Architecture"],
        },
    ]


def _normalize_step_skill(step: str) -> str:
    mapping = {
        "variables": "Python",
        "functions": "Python",
        "lists": "Python",
        "dictionaries": "Python",
        "json": "Python",
        "error handling": "Python",
        "file handling": "File Handling",
        "fetch/api": "API / Routes",
        "dom events": "JavaScript",
        "forms": "HTML/CSS",
        "responsive layout": "HTML/CSS",
        "routes": "API / Routes",
        "templates": "Flask",
        "tables": "SQLite",
        "insert": "SQLite",
        "select": "SQLite",
        "update": "SQLite",
        "delete": "SQLite",
        "filtering": "SQLite",
        "relationships": "SQLite",
        "reports": "Project Tracking",
        "windows troubleshooting": "Health Monitoring",
        "event viewer": "Windows Server Logs",
        "group policy": "Active Directory",
        "networking": "Networking",
        "documentation": "Journal/Reflection",
        "quest system": "Learning/Practice",
        "architecture": "Route Extraction",
    }
    return mapping.get(step.lower(), _skill_name(step))


def _recommended_refresh_for(step: str) -> str:
    s = step.lower()
    if "sqlite" in s or step in {"Tables", "INSERT", "SELECT", "UPDATE", "DELETE"}:
        return "Build or refresh a tiny SQLite CRUD table with insert, select, update, and delete proof."
    if "flask" in s or "route" in s:
        return "Create one Flask route, load it in the browser, and screenshot the result."
    if "api" in s or "fetch" in s:
        return "Create a button that fetches JSON and displays one field on the page."
    if "testing" in s:
        return "Write one smoke test or one assert that proves the feature works."
    if "active directory" in s or "group policy" in s:
        return "Write a proof note explaining the object, where it lives, and what action you performed."
    if "python" in s or step in {"Variables", "Functions", "Lists", "Dictionaries"}:
        return "Write one small Python file that demonstrates this concept and upload the file as proof."
    return f"Complete one tiny proof artifact for {step} and explain what it proves."


def _collect_evidence(root: Path) -> Dict[str, Any]:
    evidence = {
        "verified": Counter(), "completed": Counter(), "active_quests": Counter(),
        "strong_quests": Counter(), "projects": Counter(), "quest_candidates": defaultdict(list),
    }

    # Verified ledger from V34/V35.
    ledger = _read_json(root / "reports" / "verified_skill_ledger.json", [])
    if isinstance(ledger, dict):
        ledger = ledger.get("skills", []) or ledger.get("ledger", []) or []
    if isinstance(ledger, list):
        for item in ledger:
            if isinstance(item, dict):
                skill = _skill_name(item.get("skill") or item.get("name") or item.get("title"))
                evidence["verified"][skill.lower()] += int(item.get("proof_count", 1) or 1)

    # Learning memory can carry proof counts even before promotion.
    memory = _read_json(root / "reports" / "learning_memory.json", {})
    for item in _as_list(memory.get("skills") if isinstance(memory, dict) else []):
        if isinstance(item, dict):
            skill = _skill_name(item.get("skill"))
            proof = int(item.get("proof_count", 0) or item.get("proof_items", 0) or 0)
            if proof > 0:
                evidence["completed"][skill.lower()] += proof

    for f in _json_files(root / "quests"):
        q = _read_json(f, {})
        if not isinstance(q, dict):
            continue
        q["filename"] = f.name
        skill = _skill_name(q.get("skill") or q.get("type") or "Unclassified")
        key = skill.lower()
        evidence["active_quests"][key] += 1
        score = _quest_score(q)
        if score >= 85:
            evidence["strong_quests"][key] += 1
        status = str(q.get("status", "")).lower()
        if status in {"completed", "approved", "verified"} or q.get("submissions"):
            evidence["completed"][key] += 1
        evidence["quest_candidates"][key].append({"title": q.get("title", "Untitled"), "filename": f.name, "score": score})

        # Concept hints: let concept steps use relevant quests too.
        text = _quest_text(q).lower()
        for concept, words in {
            "variables": ["variable"], "functions": ["function", "def "], "lists": ["list"],
            "dictionaries": ["dictionary", "dict"], "json": ["json"], "file handling": ["file", "upload", "folder"],
            "testing": ["test", "pytest", "assert"], "forms": ["form", "input"], "dom events": ["button", "click", "addeventlistener"],
            "fetch/api": ["fetch", "api"], "routes": ["route", "url_for"], "templates": ["template", "jinja"],
            "tables": ["table"], "insert": ["insert"], "select": ["select"], "update": ["update"], "delete": ["delete"],
        }.items():
            if any(w in text for w in words):
                evidence["active_quests"][concept] += 1
                evidence["quest_candidates"][concept].append({"title": q.get("title", "Untitled"), "filename": f.name, "score": score})

    for f in _json_files(root / "projects"):
        p = _read_json(f, {})
        if not isinstance(p, dict):
            continue
        for item in _as_list(p.get("latest_technologies")) + _as_list(p.get("latest_capabilities")):
            evidence["projects"][_skill_name(item).lower()] += 1

    return evidence


def learning_roadmaps_snapshot(kdt: Any) -> Dict[str, Any]:
    root = Path(kdt.APP_ROOT)
    evidence = _collect_evidence(root)
    roadmaps = []
    all_next = []

    for roadmap in _roadmaps():
        steps = []
        points = 0
        blocked = []
        next_step = None
        for index, step in enumerate(roadmap["steps"], start=1):
            skill = _normalize_step_skill(step)
            status = _status_from_evidence(skill, evidence)
            if status == "Missing" and step.lower() in evidence["active_quests"]:
                status = "Practicing"
            if status == "Missing" and step.lower() in evidence["projects"]:
                status = "Seen"
            score = _score_for_status(status)
            points += score
            key_options = [skill.lower(), step.lower()]
            candidates = []
            for key in key_options:
                candidates.extend(evidence["quest_candidates"].get(key, []))
            candidates = sorted(candidates, key=lambda q: q.get("score", 0), reverse=True)
            row = {
                "index": index,
                "step": step,
                "skill": skill,
                "status": status,
                "score": score,
                "recommended_action": _recommended_refresh_for(step),
                "quest": candidates[0] if candidates else None,
            }
            steps.append(row)
            if status in {"Missing", "Seen", "Practicing"} and next_step is None:
                next_step = row
            if status in {"Missing", "Seen"}:
                blocked.append(row)
        completion = int(points / (len(steps) * 100) * 100) if steps else 0
        if next_step:
            all_next.append({"roadmap": roadmap["name"], **next_step, "completion": completion})
        roadmaps.append({
            "name": roadmap["name"],
            "mission": roadmap["mission"],
            "completion": completion,
            "steps": steps,
            "next_step": next_step,
            "blocked_count": len(blocked),
            "proven_count": len([s for s in steps if s["status"] == "Proven"]),
        })

    roadmaps = sorted(roadmaps, key=lambda r: (r["completion"], -r["blocked_count"]))
    all_next = sorted(all_next, key=lambda s: (s.get("completion", 0), s.get("index", 99)))
    recommended = all_next[0] if all_next else None
    avg_completion = int(sum(r["completion"] for r in roadmaps) / len(roadmaps)) if roadmaps else 0
    blocked_paths = len([r for r in roadmaps if r["blocked_count"] > 0])

    snapshot = {
        "version": "V37",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "totals": {
            "active_roadmaps": len(roadmaps),
            "average_completion": avg_completion,
            "recommended_next_skills": len(all_next[:5]),
            "blocked_paths": blocked_paths,
        },
        "recommended": recommended,
        "roadmaps": roadmaps,
        "next_steps": all_next[:8],
        "rule": "A roadmap turns scattered quests into ordered growth. KDT OS should show what comes next, not just what exists.",
    }
    _write_json(root / "reports" / "learning_roadmaps.json", snapshot)
    _write_json(root / "reports" / "roadmap_progress.json", {"created_at": snapshot["created_at"], "roadmaps": roadmaps})
    return snapshot


def install(kdt: Any) -> None:
    app = kdt.app

    def learning_roadmaps():
        return kdt.render_template("learning_roadmaps.html", data=learning_roadmaps_snapshot(kdt))

    def learning_roadmaps_json():
        return kdt.jsonify(learning_roadmaps_snapshot(kdt))

    app.add_url_rule("/learning_roadmaps", "learning_roadmaps", learning_roadmaps, methods=["GET"])
    app.add_url_rule("/learning_roadmaps.json", "learning_roadmaps_json", learning_roadmaps_json, methods=["GET"])

    kdt.learning_roadmaps_snapshot_v37 = lambda: learning_roadmaps_snapshot(kdt)
