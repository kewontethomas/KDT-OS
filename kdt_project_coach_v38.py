"""KDT OS Project Coach V38

V38 turns learning data into build recommendations.
It answers: what should Kewonte build next, why, what skills it trains,
and what exact first step should start the project.
"""
from __future__ import annotations

import json
import re
from collections import Counter
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
        "dashboard/ui": "HTML/CSS",
        "database storage": "SQLite",
        "sqlite": "SQLite",
        "python": "Python",
        "javascript": "JavaScript",
        "js": "JavaScript",
        "flask": "Flask",
        "testing": "Testing",
        "health monitoring": "Health Monitoring",
        "active directory": "Active Directory",
        "active directory ous": "Active Directory",
        "cpu usage": "CPU Usage",
        "task management": "Task Management",
        "project tracking": "Project Tracking",
        "automation/scheduling": "Automation/Scheduling",
    }
    return mapping.get(key, text[:80] or "Unclassified")


def _quest_score(q: Dict[str, Any]) -> int:
    quality = q.get("quest_quality")
    if isinstance(quality, dict):
        try:
            return int(quality.get("score", 0))
        except Exception:
            return 0
    if isinstance(quality, (int, float)):
        return int(quality)
    # older quests may be usable but unscored
    if q.get("title") and q.get("what_to_build"):
        return 55
    return 0


def _quest_text(q: Dict[str, Any]) -> str:
    parts = [q.get("title"), q.get("goal"), q.get("what_to_build"), q.get("skill"), q.get("type")]
    parts += [str(x) for x in _as_list(q.get("requirements"))]
    parts += [str(x) for x in _as_list(q.get("success_criteria"))]
    return " ".join([str(p) for p in parts if p])


def _project_names(root: Path) -> List[str]:
    names = []
    for f in _json_files(root / "projects"):
        data = _read_json(f, {})
        if isinstance(data, dict):
            name = data.get("project_name") or data.get("name") or f.stem
            names.append(str(name))
    return sorted(set(names))


def _collect_signals(root: Path) -> Dict[str, Any]:
    weak = Counter()
    strong = Counter()
    active = Counter()
    verified = Counter()
    roadmaps = Counter()
    refresh = Counter()
    project_gaps = Counter()
    source_projects = _project_names(root)

    # Active quest signals.
    for f in _json_files(root / "quests"):
        q = _read_json(f, {})
        if not isinstance(q, dict):
            continue
        skill = _skill_name(q.get("skill") or q.get("category") or q.get("type"))
        score = _quest_score(q)
        active[skill] += 1
        if score >= 85:
            strong[skill] += 1
        else:
            weak[skill] += 1
        text = _quest_text(q).lower()
        for token, mapped in [
            ("sqlite", "SQLite"), ("database", "SQLite"), ("crud", "SQLite"),
            ("flask", "Flask"), ("route", "API / Routes"), ("api", "API / Routes"),
            ("fetch", "JavaScript"), ("button", "JavaScript"), ("html", "HTML/CSS"),
            ("css", "HTML/CSS"), ("test", "Testing"), ("health", "Health Monitoring"),
        ]:
            if token in text:
                active[mapped] += 1

    # Verified ledger.
    ledger = _read_json(root / "reports" / "verified_skill_ledger.json", [])
    if isinstance(ledger, dict):
        ledger = ledger.get("skills", []) or ledger.get("ledger", []) or []
    if isinstance(ledger, list):
        for item in ledger:
            if isinstance(item, dict):
                verified[_skill_name(item.get("skill") or item.get("name"))] += int(item.get("proof_count", 1) or 1)

    # Learning roadmaps next skills and blocked path data.
    roadmap_report = _read_json(root / "reports" / "roadmap_progress.json", {})
    roadmap_items = []
    if isinstance(roadmap_report, dict):
        roadmap_items = roadmap_report.get("roadmaps", []) or roadmap_report.get("paths", []) or []
    for rm in _as_list(roadmap_items):
        if not isinstance(rm, dict):
            continue
        next_skill = rm.get("next_step") or rm.get("next_skill") or rm.get("recommended_next")
        if isinstance(next_skill, dict):
            next_skill = next_skill.get("skill") or next_skill.get("name") or next_skill.get("step")
        if next_skill:
            roadmaps[_skill_name(next_skill)] += 2
        for gap in _as_list(rm.get("blocked_by") or rm.get("gaps") or []):
            project_gaps[_skill_name(gap)] += 1

    # Learning intelligence bottlenecks.
    learning = _read_json(root / "reports" / "learning_intelligence.json", {})
    if isinstance(learning, dict):
        for key in ["primary_bottleneck", "recommended_next_skill", "next_skill"]:
            val = learning.get(key)
            if isinstance(val, dict):
                val = val.get("skill") or val.get("name")
            if val:
                weak[_skill_name(val)] += 3
        for item in _as_list(learning.get("skills") or learning.get("skill_scores") or []):
            if isinstance(item, dict):
                s = _skill_name(item.get("skill") or item.get("name"))
                try:
                    score = int(item.get("score", 0) or item.get("estimated_score", 0) or 0)
                except Exception:
                    score = 0
                if score < 60:
                    weak[s] += 1

    # Skill refresh queue.
    refresh_report = _read_json(root / "reports" / "refresh_queue.json", {})
    refresh_items = refresh_report.get("queue", []) if isinstance(refresh_report, dict) else []
    for item in _as_list(refresh_items):
        if isinstance(item, dict):
            refresh[_skill_name(item.get("skill") or item.get("name"))] += 2

    priority = Counter()
    for c, weight in [(weak, 3), (roadmaps, 3), (refresh, 2), (project_gaps, 2), (active, 1)]:
        for skill, count in c.items():
            priority[skill] += count * weight
    # Reduce priority slightly for already verified skills, but do not remove them.
    for skill, count in verified.items():
        priority[skill] -= min(count, 3)

    return {
        "weak_skills": dict(weak),
        "strong_skills": dict(strong),
        "active_skills": dict(active),
        "verified_skills": dict(verified),
        "roadmap_skills": dict(roadmaps),
        "refresh_skills": dict(refresh),
        "project_gap_skills": dict(project_gaps),
        "priority_skills": dict(priority),
        "source_projects": source_projects,
    }


def _project_templates() -> List[Dict[str, Any]]:
    return [
        {
            "name": "Workout Database App",
            "type": "Practice Project", "difficulty": "Beginner", "time": "2-4 hours",
            "skills": ["SQLite", "Python", "CRUD", "Data Validation"],
            "why": "Builds the exact SQLite CRUD skills KDT OS keeps detecting as useful while staying small and personal.",
            "first_step": "Create a folder with app.py and workouts.json or workouts.db, then add one workout record with exercise, reps, sets, and date.",
            "proof": "Upload a ZIP showing create, list, update, and delete working on workout records.",
        },
        {
            "name": "Expense Tracker CLI",
            "type": "Practice Project", "difficulty": "Beginner", "time": "2-3 hours",
            "skills": ["Python", "Functions", "Lists", "JSON", "File Handling"],
            "why": "Strengthens Python basics with a useful real-life tool and gives clear proof through saved totals.",
            "first_step": "Create expense_tracker.py with a list of three expenses and print the total.",
            "proof": "Upload the Python file and a screenshot of the terminal total.",
        },
        {
            "name": "API Weather Lookup App",
            "type": "Practice Project", "difficulty": "Beginner", "time": "2-4 hours",
            "skills": ["JavaScript", "API / Routes", "HTML/CSS", "Fetch/API"],
            "why": "Turns API and JavaScript gaps into a visible browser app with an easy proof target.",
            "first_step": "Create index.html, style.css, and script.js with a button that displays sample weather JSON.",
            "proof": "Upload a ZIP and screenshot showing city, temperature, and condition displayed after button click.",
        },
        {
            "name": "Flask Route Smoke Test Suite",
            "type": "Project Upgrade", "difficulty": "Beginner", "time": "1-2 hours",
            "skills": ["Flask", "Testing", "Routes", "Python"],
            "why": "Protects KDT OS from breaking as it grows by proving important routes still load.",
            "first_step": "Create tests/test_routes.py and add one test that checks the home route returns 200.",
            "proof": "Upload test_routes.py and a screenshot or copied output from pytest.",
        },
        {
            "name": "Help Desk Ticket Tracker",
            "type": "Career Project", "difficulty": "Intermediate", "time": "4-8 hours",
            "skills": ["Flask", "SQLite", "Forms", "Ticket System", "IT Support"],
            "why": "Connects your IT support experience to a portfolio project that demonstrates real workflow understanding.",
            "first_step": "Create a ticket form with fields for issue, device, priority, status, and resolution notes.",
            "proof": "Upload a ZIP and screenshots showing create, update status, and resolution notes.",
        },
        {
            "name": "System Health Dashboard",
            "type": "Career Project", "difficulty": "Intermediate", "time": "4-6 hours",
            "skills": ["Health Monitoring", "Python", "Dashboard/UI", "File Handling"],
            "why": "Turns your server troubleshooting experience into a reusable tool for CPU, RAM, disk, and service checks.",
            "first_step": "Create a Python script that outputs fake or real CPU, memory, disk, and service status as OK/WARNING.",
            "proof": "Upload code and a screenshot of the dashboard or terminal health report.",
        },
        {
            "name": "KDT OS Quest Quality Repair Tool",
            "type": "KDT OS Upgrade", "difficulty": "Intermediate", "time": "3-6 hours",
            "skills": ["Project Tracking", "Governance", "Python", "JSON"],
            "why": "Improves KDT OS directly by making weak quests easier to repair and trust.",
            "first_step": "Create a function that loads active quest JSON and prints quests missing quest_quality metadata.",
            "proof": "Upload the function and a before/after report showing detected quest files.",
        },
        {
            "name": "Personal Project Portfolio Page",
            "type": "Portfolio Project", "difficulty": "Beginner", "time": "2-4 hours",
            "skills": ["HTML/CSS", "Responsive Layout", "Project Tracking"],
            "why": "Creates a clean place to show KDT OS, FieldSeed, and future projects while improving layout skills.",
            "first_step": "Create index.html with cards for three projects: KDT OS, FieldSeed, and one future app.",
            "proof": "Upload HTML/CSS and screenshot at full screen and mobile width.",
        },
        {
            "name": "Active Directory OU Practice Notes",
            "type": "IT Support Proof", "difficulty": "Beginner", "time": "30-60 minutes",
            "skills": ["Active Directory", "Documentation", "IT Support"],
            "why": "Converts your AD/OU confusion into a proof-backed explanation you can reuse for interviews and field work.",
            "first_step": "Create README.md explaining what an OU is, why it matters, and where one test user/computer should go.",
            "proof": "Upload README.md and, if available, a screenshot from your lab showing the OU structure.",
        },
        {
            "name": "JavaScript Form Saver",
            "type": "Practice Project", "difficulty": "Beginner", "time": "2-3 hours",
            "skills": ["JavaScript", "Forms", "Local Storage", "HTML/CSS"],
            "why": "Builds browser app confidence by saving form input without needing a backend yet.",
            "first_step": "Create a form with name, note, and category fields, then save one entry to localStorage.",
            "proof": "Upload ZIP and screenshot showing saved data still appears after refresh.",
        },
    ]


def _score_project(project: Dict[str, Any], signals: Dict[str, Any]) -> Dict[str, Any]:
    priority = signals.get("priority_skills", {})
    weak = signals.get("weak_skills", {})
    roadmaps = signals.get("roadmap_skills", {})
    refresh = signals.get("refresh_skills", {})
    verified = signals.get("verified_skills", {})
    source_projects = [p.lower() for p in signals.get("source_projects", [])]
    score = 25
    reasons = []
    for skill in project["skills"]:
        s = _skill_name(skill)
        if priority.get(s, 0) > 0:
            score += min(priority.get(s, 0) * 3, 24)
            reasons.append(f"Strengthens priority skill: {s}")
        if weak.get(s, 0) > 0:
            score += 12
            reasons.append(f"Targets current weak area: {s}")
        if roadmaps.get(s, 0) > 0:
            score += 10
            reasons.append(f"Moves a roadmap forward: {s}")
        if refresh.get(s, 0) > 0:
            score += 8
            reasons.append(f"Refreshes skill at risk: {s}")
        if verified.get(s, 0) > 0:
            score += 3
            reasons.append(f"Builds on proven foundation: {s}")
    name_l = project["name"].lower()
    if any(name_l in existing or existing in name_l for existing in source_projects):
        score -= 18
        reasons.append("Similar project may already exist; consider extending instead of duplicating.")
    if project["difficulty"] == "Beginner":
        score += 8
        reasons.append("Small enough to finish and prove quickly.")
    if project["type"] in {"KDT OS Upgrade", "Career Project"}:
        score += 6
        reasons.append("Strategic project for career or KDT OS growth.")
    score = max(0, min(100, score))
    bucket = "Strategic" if project["type"] in {"KDT OS Upgrade", "Career Project"} else project["difficulty"]
    return {**project, "score": score, "bucket": bucket, "reasons": list(dict.fromkeys(reasons))[:6]}


def project_coach_snapshot(kdt: Any) -> Dict[str, Any]:
    root = Path(kdt.APP_ROOT)
    signals = _collect_signals(root)
    scored = [_score_project(p, signals) for p in _project_templates()]
    scored = sorted(scored, key=lambda p: p["score"], reverse=True)
    recommended = scored[:8]
    beginner = [p for p in scored if p["difficulty"] == "Beginner"]
    strategic = [p for p in scored if p["bucket"] == "Strategic"]
    intermediate = [p for p in scored if p["difficulty"] == "Intermediate"]
    skill_map = {}
    for p in scored:
        for s in p["skills"]:
            skill_map.setdefault(_skill_name(s), []).append(p["name"])
    top = recommended[0] if recommended else None
    report = {
        "version": "V38",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "recommended_count": len(scored),
        "beginner_count": len(beginner),
        "intermediate_count": len(intermediate),
        "strategic_count": len(strategic),
        "top_project": top,
        "recommended_projects": recommended,
        "all_projects": scored,
        "skill_map": skill_map,
        "signals": signals,
        "rule": "KDT OS should turn learning gaps into real projects with a reason, first step, and proof requirement.",
    }
    _write_json(root / "reports" / "project_recommendations.json", report)
    _write_json(root / "reports" / "project_skill_map.json", {"created_at": report["created_at"], "skill_map": skill_map})
    return report


def install(kdt: Any) -> None:
    app = kdt.app

    def project_coach():
        snapshot = project_coach_snapshot(kdt)
        return kdt.render_template("project_coach.html", snapshot=snapshot)

    def project_coach_json():
        return kdt.jsonify(project_coach_snapshot(kdt))

    app.add_url_rule("/project_coach", "project_coach", project_coach, methods=["GET"])
    app.add_url_rule("/project_coach.json", "project_coach_json", project_coach_json, methods=["GET"])

    kdt.project_coach_snapshot_v38 = lambda: project_coach_snapshot(kdt)
