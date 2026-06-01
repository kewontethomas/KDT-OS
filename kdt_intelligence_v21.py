"""KDT OS Intelligence V21

Adds higher-level intelligence on top of the existing app.py + Quest Intelligence V20.

V21 focuses on the next level of the vision:
- mastery maps instead of flat skill percentages
- next-best-action recommendations
- project memory summaries
- adaptive learning profile
- quest system health overview

This module is intentionally additive. It does not delete old logic.
It registers new Flask routes when install(app_module) is called.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


MASTERY_CONCEPTS = {
    "Python": [
        {"name": "Variables", "proof_terms": ["variable", "name =", "expenses", "cpu_usage"]},
        {"name": "Functions", "proof_terms": ["def ", "function", "calculate_total", "cpu_check"]},
        {"name": "Return values", "proof_terms": ["return", "returns", "what did", "send back"]},
        {"name": "Lists", "proof_terms": ["list", "expenses", "append", "three numbers"]},
        {"name": "Loops", "proof_terms": ["for ", "loop", "each"]},
        {"name": "File output", "proof_terms": ["write", ".txt", "json", "health_log", "report"]},
    ],
    "SQLite": [
        {"name": "Tables", "proof_terms": ["create table", "table", "workouts table"]},
        {"name": "Rows", "proof_terms": ["row", "rows", "listed after restart"]},
        {"name": "Columns", "proof_terms": ["column", "exercise", "sets", "reps", "date"]},
        {"name": "INSERT", "proof_terms": ["insert", "add_workout", "add a workout"]},
        {"name": "SELECT", "proof_terms": ["select", "list_workouts", "view all"]},
        {"name": "UPDATE", "proof_terms": ["update", "edit", "change reps"]},
        {"name": "DELETE", "proof_terms": ["delete", "remove"]},
        {"name": "Persistence", "proof_terms": ["workouts.db", "after restart", "saved rows still exist"]},
    ],
    "Testing": [
        {"name": "Test file", "proof_terms": ["test_", "tests/test", "test file"]},
        {"name": "Assert", "proof_terms": ["assert", "expected"]},
        {"name": "Pytest command", "proof_terms": ["pytest", "python -m pytest"]},
        {"name": "Route test", "proof_terms": ["route", "status_code", "test_client"]},
        {"name": "Failure reading", "proof_terms": ["fail", "error", "which route"]},
    ],
    "API / Routes": [
        {"name": "Button event", "proof_terms": ["addEventListener", "button", "searchBtn"]},
        {"name": "Fetch request", "proof_terms": ["fetch", "api request"]},
        {"name": "JSON parsing", "proof_terms": ["response.json", ".json()", "json"]},
        {"name": "DOM result", "proof_terms": ["textContent", "result", "innerHTML", "display"]},
        {"name": "Error handling", "proof_terms": ["catch", "try", "error message"]},
    ],
    "HTML/CSS": [
        {"name": "HTML structure", "proof_terms": ["index.html", "section", "article", "card"]},
        {"name": "CSS linking", "proof_terms": ["style.css", "link"]},
        {"name": "Layout", "proof_terms": ["grid", "flex", "card-grid"]},
        {"name": "Spacing", "proof_terms": ["gap", "padding", "margin"]},
        {"name": "Responsive design", "proof_terms": ["@media", "mobile", "responsive"]},
    ],
    "Active Directory": [
        {"name": "Domain tree", "proof_terms": ["domain", "ADUC", "Active Directory Users and Computers"]},
        {"name": "OU creation", "proof_terms": ["KDT_Practice", "Organizational Unit", "OU"]},
        {"name": "Sub-OU", "proof_terms": ["Workstations", "sub-OU"]},
        {"name": "Object organization", "proof_terms": ["move", "user", "computer", "object"]},
        {"name": "GPO relationship", "proof_terms": ["GPO", "policy"]},
    ],
    "CPU Usage": [
        {"name": "Open Task Manager", "proof_terms": ["Task Manager", "Ctrl + Shift + Esc"]},
        {"name": "Sort by CPU", "proof_terms": ["CPU column", "sort"]},
        {"name": "Identify process", "proof_terms": ["process", "top process"]},
        {"name": "Read percentage", "proof_terms": ["percentage", "%", "CPU usage"]},
        {"name": "Troubleshooting meaning", "proof_terms": ["high CPU", "low CPU", "what it means"]},
    ],
    "Health Monitoring": [
        {"name": "Threshold", "proof_terms": ["> 80", "threshold", "warning if"]},
        {"name": "OK/WARNING status", "proof_terms": ["OK", "WARNING"]},
        {"name": "Multiple checks", "proof_terms": ["cpu_check", "memory_check", "disk_check"]},
        {"name": "Overall health", "proof_terms": ["Overall Health", "Needs Attention"]},
        {"name": "Log file", "proof_terms": ["health_log", "write", ".txt"]},
    ],
}

DEFAULT_CONCEPTS = [
    {"name": "Definition", "proof_terms": ["what is", "definition", "explain"]},
    {"name": "Small practice", "proof_terms": ["practice", "example", "demo"]},
    {"name": "Visible proof", "proof_terms": ["screenshot", "upload", "proof"]},
    {"name": "Reflection", "proof_terms": ["confused", "what changed", "explain"]},
]


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return fallback


def _as_text(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(_as_text(x) for x in value)
    if isinstance(value, dict):
        return "\n".join(f"{k}: {_as_text(v)}" for k, v in value.items())
    return str(value or "")


def _quest_text(q: Dict[str, Any]) -> str:
    fields = [
        q.get("title", ""), q.get("skill", ""), q.get("goal", ""), q.get("what_to_build", ""),
        q.get("requirements", []), q.get("steps", []), q.get("success_criteria", []), q.get("proof_required", []),
        q.get("submissions", []), q.get("quest_quality", {}), q.get("governance", {}),
    ]
    return _as_text(fields).lower()


def _normalize_skill(skill: str) -> str:
    low = (skill or "").lower()
    if "sqlite" in low or "database" in low:
        return "SQLite"
    if "active directory" in low or "organizational unit" in low or re.search(r"\bou\b", low):
        return "Active Directory"
    if "cpu" in low or "task manager" in low:
        return "CPU Usage"
    if "test" in low or "pytest" in low or "smoke" in low:
        return "Testing"
    if "api" in low or "route" in low or "fetch" in low:
        return "API / Routes"
    if "html" in low or "css" in low or "layout" in low:
        return "HTML/CSS"
    if "health" in low or "diagnostic" in low:
        return "Health Monitoring"
    if "python" in low or "function" in low:
        return "Python"
    return (skill or "Unknown").strip() or "Unknown"


def _list_quest_files(kdt: Any, include_archived: bool = False) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in sorted(kdt.QUEST_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        q = _read_json(path, None)
        if not isinstance(q, dict):
            continue
        q["filename"] = path.name
        if not include_archived and q.get("status") in {"Archived", "Superseded", "Rejected"}:
            continue
        rows.append(q)
    return rows


def _submission_strength(q: Dict[str, Any]) -> int:
    strength = 0
    for sub in q.get("submissions", []) or []:
        if not isinstance(sub, dict):
            continue
        try:
            score = int(sub.get("score", sub.get("rule_score", 0)) or 0)
        except Exception:
            score = 0
        if score >= 90:
            strength += 3
        elif score >= 75:
            strength += 2
        elif score > 0:
            strength += 1
    if str(q.get("status", "")).lower() in {"completed", "verified"}:
        strength += 2
    return strength


def mastery_map(kdt: Any) -> Dict[str, Any]:
    skills = kdt.load_skill_library() if hasattr(kdt, "load_skill_library") else {}
    quests = _list_quest_files(kdt, include_archived=False)
    archived = len(list(kdt.QUEST_ARCHIVE_DIR.glob("*.json"))) if hasattr(kdt, "QUEST_ARCHIVE_DIR") else 0
    postmortems = len(list(kdt.QUEST_POSTMORTEM_DIR.glob("*.json"))) if hasattr(kdt, "QUEST_POSTMORTEM_DIR") else 0

    grouped: Dict[str, Dict[str, Any]] = {}
    for skill_name, entry in skills.items():
        norm = _normalize_skill(skill_name)
        grouped.setdefault(norm, {"skill": norm, "library": entry, "quests": [], "concepts": [], "score": 0})
    for q in quests:
        norm = _normalize_skill(q.get("skill", q.get("title", "Unknown")))
        grouped.setdefault(norm, {"skill": norm, "library": {}, "quests": [], "concepts": [], "score": 0})
        grouped[norm]["quests"].append(q)

    for skill, bundle in grouped.items():
        concepts = MASTERY_CONCEPTS.get(skill, DEFAULT_CONCEPTS)
        qtexts = [_quest_text(q) for q in bundle.get("quests", [])]
        library_text = _as_text(bundle.get("library", {})).lower()
        concept_rows = []
        earned = 0
        for concept in concepts:
            terms = [t.lower() for t in concept.get("proof_terms", [])]
            evidence_hits = []
            for idx, text in enumerate(qtexts):
                if any(term in text for term in terms):
                    q = bundle["quests"][idx]
                    strength = _submission_strength(q)
                    evidence_hits.append({
                        "quest_title": q.get("title", "Untitled"),
                        "filename": q.get("filename", ""),
                        "status": q.get("status", "Assigned"),
                        "strength": strength,
                    })
            library_hit = any(term in library_text for term in terms)
            status = "Missing"
            if evidence_hits and max(hit["strength"] for hit in evidence_hits) >= 2:
                status = "Proven"
                earned += 2
            elif evidence_hits or library_hit:
                status = "Seen"
                earned += 1
            concept_rows.append({
                "name": concept["name"],
                "status": status,
                "evidence": evidence_hits[:4],
                "next_micro_action": next_micro_action(skill, concept["name"], status),
            })
        max_score = max(1, len(concepts) * 2)
        score = int((earned / max_score) * 100)
        bundle["concepts"] = concept_rows
        bundle["score"] = score
        bundle["status"] = "Mastery Track" if score >= 80 else ("Building" if score >= 35 else "Needs Foundation")
        bundle["next_gap"] = next((c for c in concept_rows if c["status"] != "Proven"), None)

    skill_rows = sorted(grouped.values(), key=lambda x: (x.get("score", 0), len(x.get("quests", []))), reverse=True)
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "skills": skill_rows,
        "totals": {
            "skills": len(skill_rows),
            "active_quests": len(quests),
            "archived_quests": archived,
            "postmortems": postmortems,
            "proven_concepts": sum(1 for s in skill_rows for c in s.get("concepts", []) if c.get("status") == "Proven"),
            "seen_concepts": sum(1 for s in skill_rows for c in s.get("concepts", []) if c.get("status") == "Seen"),
            "missing_concepts": sum(1 for s in skill_rows for c in s.get("concepts", []) if c.get("status") == "Missing"),
        },
    }


def next_micro_action(skill: str, concept: str, status: str) -> str:
    if status == "Proven":
        return "Use this concept inside a larger project quest."
    actions = {
        "SQLite": f"Create a 5-minute proof for SQLite concept: {concept}.",
        "Python": f"Create one tiny Python file that proves: {concept}.",
        "Testing": f"Write one test or one assert proving: {concept}.",
        "API / Routes": f"Build one browser click/request proof for: {concept}.",
        "HTML/CSS": f"Create one visible page section proving: {concept}.",
        "Active Directory": f"Create screenshot or notes proof for AD concept: {concept}.",
        "CPU Usage": f"Use Task Manager notes to prove: {concept}.",
        "Health Monitoring": f"Create one OK/WARNING check proving: {concept}.",
    }
    return actions.get(skill, f"Create a small proof artifact for: {concept}.")


def next_best_moves(kdt: Any, limit: int = 6) -> List[Dict[str, Any]]:
    graph = mastery_map(kdt)
    moves: List[Dict[str, Any]] = []
    # 1. Fix quest system quality first if needed.
    summary = kdt.quest_maintenance_summary() if hasattr(kdt, "quest_maintenance_summary") else {"needs_work": 0, "quests": []}
    if summary.get("needs_work", 0):
        moves.append({
            "priority": 1,
            "type": "Quest Governance",
            "title": "Regenerate weak or duplicated quests",
            "why": "Weak quests poison the skill bank. Fixing them keeps future learning data clean.",
            "action": "Open Quest Intelligence and regenerate weak/clone quests under the minimum score.",
            "proof": "Quest Maintenance shows 0 duplicated/generic quests needing work.",
            "url_endpoint": "quest_maintenance",
        })
    # 2. Choose the first missing concept in the strongest active skill.
    for skill in graph["skills"]:
        gap = skill.get("next_gap")
        if gap:
            moves.append({
                "priority": 2,
                "type": "Mastery Gap",
                "title": f"Prove {skill['skill']}: {gap['name']}",
                "why": f"{skill['skill']} is not just one percentage. This specific concept is still {gap['status'].lower()}.",
                "action": gap.get("next_micro_action"),
                "proof": "Submit a screenshot, file, terminal output, or README answer tied to this exact concept.",
                "url_endpoint": "quests",
            })
            break
    # 3. Project memory refresh.
    projects = kdt.list_projects() if hasattr(kdt, "list_projects") else []
    if projects:
        stale = projects[0]
        moves.append({
            "priority": 3,
            "type": "Project Memory",
            "title": f"Refresh project memory: {stale.get('project_name', 'Current Project')}",
            "why": "KDT OS becomes smarter when project records stay current instead of relying on old screenshots or old reports.",
            "action": "Use Sources to rescan the project folder or upload the latest project version.",
            "proof": "Project page shows a recent scan/version and updated gaps.",
            "url_endpoint": "sources",
        })
    # 4. Long-term architecture nudge.
    moves.append({
        "priority": 4,
        "type": "Architecture",
        "title": "Begin modularizing app.py safely",
        "why": "The app works, but app.py is carrying too many responsibilities. Modular systems are easier to improve without breaking old features.",
        "action": "Keep app.py stable and add new intelligence layers as modules first, then gradually move engines into /core.",
        "proof": "New features load through install() modules and app.py remains runnable.",
        "url_endpoint": "system_intelligence",
    })
    return moves[:limit]


def project_memory(kdt: Any) -> Dict[str, Any]:
    projects = kdt.list_projects() if hasattr(kdt, "list_projects") else []
    rows = []
    for p in projects[:12]:
        rows.append({
            "name": p.get("project_name", "Unknown"),
            "versions": len(p.get("versions", [])),
            "status": p.get("status", "Active"),
            "last_analyzed": p.get("last_analyzed", ""),
            "capabilities": p.get("latest_capabilities", [])[:6],
            "technologies": p.get("latest_technologies", [])[:6],
            "memory_type": p.get("knowledge_type", "fact"),
            "trust": p.get("verification_status", "Unknown"),
        })
    return {"projects": rows, "count": len(projects)}


def adaptive_profile(kdt: Any) -> Dict[str, Any]:
    memory_file = getattr(kdt, "DECISION_MEMORY_FILE", None)
    memory = _read_json(memory_file, {}) if memory_file else {}
    return {
        "learning_style": memory.get("user_learning_style", [
            "Needs exact steps.",
            "Needs exact proof.",
            "Needs small quests that build toward larger goals.",
        ]),
        "rules": memory.get("rules", []),
        "patterns": memory.get("pattern_counts", {}),
        "recent_events": memory.get("adaptive_events", [])[:8],
    }


def intelligence_dashboard(kdt: Any) -> Dict[str, Any]:
    return {
        "mastery": mastery_map(kdt),
        "moves": next_best_moves(kdt),
        "projects": project_memory(kdt),
        "adaptive": adaptive_profile(kdt),
        "quest_summary": kdt.quest_maintenance_summary() if hasattr(kdt, "quest_maintenance_summary") else {},
    }


def install(kdt: Any) -> Any:
    app = getattr(kdt, "app", None)
    if app is None:
        return kdt

    # Avoid duplicate route registration when Flask debug reloader imports twice.
    if "mastery" not in app.view_functions:
        def mastery():
            return kdt.render_template("mastery.html", data=intelligence_dashboard(kdt), page="mastery")
        app.add_url_rule("/mastery", "mastery", mastery)

    if "system_intelligence" not in app.view_functions:
        def system_intelligence():
            return kdt.render_template("mastery.html", data=intelligence_dashboard(kdt), page="system_intelligence")
        app.add_url_rule("/system_intelligence", "system_intelligence", system_intelligence)

    kdt.mastery_map = lambda: mastery_map(kdt)
    kdt.next_best_moves = lambda: next_best_moves(kdt)
    kdt.project_memory_v21 = lambda: project_memory(kdt)
    kdt.adaptive_profile_v21 = lambda: adaptive_profile(kdt)
    kdt.intelligence_dashboard_v21 = lambda: intelligence_dashboard(kdt)
    return kdt
