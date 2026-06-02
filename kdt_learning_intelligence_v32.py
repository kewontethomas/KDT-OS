"""KDT OS Learning Intelligence V32

V32 turns quest/project evidence into a practical learning map:
- what Kewonte appears to know
- what is still weak or unproven
- what skill is blocking current projects
- what to learn next today
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
    mapping = {
        "api / routes": "API / Routes",
        "api routes": "API / Routes",
        "apis": "API / Routes",
        "html css": "HTML/CSS",
        "html/css": "HTML/CSS",
        "sqlite": "SQLite",
        "python": "Python",
        "javascript": "JavaScript",
        "flask": "Flask",
        "testing": "Testing",
        "health monitoring": "Health Monitoring",
        "active directory": "Active Directory",
        "cpu usage": "CPU Usage",
    }
    key = text.lower().replace(".", "").strip()
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


def _is_completed(q: Dict[str, Any]) -> bool:
    status = str(q.get("status", "")).lower()
    submissions = _as_list(q.get("submissions"))
    return status in {"completed", "approved", "verified"} or any(str(s.get("status", "")).lower() in {"completed", "approved", "verified"} for s in submissions if isinstance(s, dict))


def _has_proof(q: Dict[str, Any]) -> bool:
    if _is_completed(q):
        return True
    submissions = _as_list(q.get("submissions"))
    return bool(submissions)


def _quest_text(q: Dict[str, Any]) -> str:
    parts = [q.get("title"), q.get("goal"), q.get("what_to_build"), q.get("user_gap"), q.get("skill")]
    parts += [str(x) for x in _as_list(q.get("requirements"))]
    parts += [str(x) for x in _as_list(q.get("success_criteria"))]
    return " ".join([str(p) for p in parts if p])


def _detect_concepts(text: str) -> List[str]:
    t = (text or "").lower()
    concepts = []
    checks = {
        "variables": ["variable", "assign", "value"],
        "functions": ["function", "def ", "return"],
        "forms": ["form", "input", "submit"],
        "events": ["addeventlistener", "click", "button"],
        "fetch/api": ["fetch", "api", "json", "endpoint"],
        "routes": ["route", "@app.route", "url_for"],
        "sqlite tables": ["sqlite", "table", "create table"],
        "crud": ["crud", "insert", "update", "delete"],
        "proof": ["proof", "screenshot", "upload"],
        "testing": ["pytest", "test", "assert"],
        "active directory ous": ["active directory", "ou", "organizational unit"],
        "cpu monitoring": ["cpu", "task manager", "usage"],
    }
    for name, needles in checks.items():
        if any(n in t for n in needles):
            concepts.append(name)
    return concepts


def _load_project_reports(root: Path, projects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    reports = []
    report_dir = root / "reports"
    for p in projects:
        current = p.get("current_report")
        if current:
            data = _read_json(report_dir / current, {})
            if isinstance(data, dict):
                data["project_name"] = p.get("project_name") or data.get("project_name")
                reports.append(data)
    return reports


def _skill_from_project_report(report: Dict[str, Any]) -> List[str]:
    skills = []
    for tech in _as_list(report.get("technologies")) + _as_list(report.get("latest_technologies")):
        skills.append(_skill_name(tech))
    for cap in _as_list(report.get("capabilities")) + _as_list(report.get("latest_capabilities")):
        cap = str(cap)
        if "database" in cap.lower():
            skills.append("SQLite")
        if "api" in cap.lower() or "route" in cap.lower():
            skills.append("API / Routes")
        if "dashboard" in cap.lower() or "ui" in cap.lower():
            skills.append("HTML/CSS")
        if "learning" in cap.lower() or "practice" in cap.lower():
            skills.append("Learning/Practice")
    return sorted(set([s for s in skills if s]))


def learning_intelligence_snapshot(kdt: Any) -> Dict[str, Any]:
    root = Path(kdt.APP_ROOT)
    quests = []
    for f in _json_files(root / "quests"):
        data = _read_json(f, {})
        if isinstance(data, dict):
            data["filename"] = f.name
            quests.append(data)

    projects = []
    for f in _json_files(root / "projects"):
        data = _read_json(f, {})
        if isinstance(data, dict):
            data["filename"] = f.name
            projects.append(data)

    skill_map: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "skill": "", "quest_count": 0, "completed": 0, "proof_count": 0, "score_total": 0,
        "quality_scores": [], "weak_quests": [], "strong_quests": [], "concepts": Counter(), "projects": set(),
    })

    for q in quests:
        skill = _skill_name(q.get("skill") or q.get("type") or "Unclassified")
        row = skill_map[skill]
        row["skill"] = skill
        row["quest_count"] += 1
        score = _quest_score(q)
        if score:
            row["quality_scores"].append(score)
            row["score_total"] += score
        if _is_completed(q):
            row["completed"] += 1
        if _has_proof(q):
            row["proof_count"] += 1
        if score >= 85:
            row["strong_quests"].append({"title": q.get("title", "Untitled"), "filename": q.get("filename"), "score": score})
        else:
            row["weak_quests"].append({"title": q.get("title", "Untitled"), "filename": q.get("filename"), "score": score})
        for c in _detect_concepts(_quest_text(q)):
            row["concepts"][c] += 1
        src = q.get("source_project") or q.get("resume_project") or q.get("connected_project")
        if src:
            row["projects"].add(str(src))

    # Add project evidence so skills that appear in uploaded projects but not quests still show up.
    for p in projects:
        pname = p.get("project_name") or p.get("name") or p.get("filename")
        project_skills = []
        project_skills += [_skill_name(x) for x in _as_list(p.get("latest_technologies"))]
        project_skills += [_skill_name(x) for x in _as_list(p.get("latest_capabilities"))]
        for s in project_skills:
            row = skill_map[s]
            row["skill"] = s
            row["projects"].add(str(pname))

    skills = []
    for skill, row in skill_map.items():
        q_count = row["quest_count"]
        avg_quality = int(sum(row["quality_scores"]) / len(row["quality_scores"])) if row["quality_scores"] else 0
        proof_rate = int((row["proof_count"] / q_count) * 100) if q_count else 0
        completion_rate = int((row["completed"] / q_count) * 100) if q_count else 0
        project_weight = min(len(row["projects"]) * 8, 24)
        # Learning score intentionally rewards proof more than generated quest quality.
        score = min(100, int((avg_quality * 0.45) + (proof_rate * 0.25) + (completion_rate * 0.20) + project_weight))
        status = "Proven" if proof_rate >= 70 and score >= 80 else "Practicing" if score >= 55 else "Needs proof" if q_count else "Seen in projects"
        blockers = []
        if q_count and proof_rate < 50:
            blockers.append("Not enough proof submitted")
        if row["weak_quests"]:
            blockers.append(f"{len(row['weak_quests'])} weak quest(s) need repair or replacement")
        if not q_count:
            blockers.append("Detected in project data but no focused quest yet")
        skills.append({
            "skill": skill,
            "score": score,
            "status": status,
            "quest_count": q_count,
            "proof_rate": proof_rate,
            "completion_rate": completion_rate,
            "average_quest_quality": avg_quality,
            "projects": sorted(row["projects"]),
            "concepts": [name for name, _ in row["concepts"].most_common(6)],
            "blockers": blockers[:3],
            "strong_quests": row["strong_quests"][:3],
            "weak_quests": sorted(row["weak_quests"], key=lambda x: x.get("score", 0))[:3],
        })

    skills = sorted(skills, key=lambda x: (x["score"], -x["quest_count"]))
    active_skills = [s for s in skills if s["quest_count"] or s["projects"]]
    weakest = active_skills[:5]
    strongest = sorted(active_skills, key=lambda x: x["score"], reverse=True)[:5]

    # Bottleneck: low score + active quests + connected projects preferred.
    bottleneck_candidates = sorted(active_skills, key=lambda s: (s["score"], -len(s["projects"]), -s["quest_count"]))
    bottleneck = bottleneck_candidates[0] if bottleneck_candidates else None

    recommended_quest = None
    if bottleneck:
        # Prefer a strong quest in the bottleneck skill; otherwise a weak one to repair/practice.
        recommended_quest = (bottleneck.get("strong_quests") or bottleneck.get("weak_quests") or [None])[0]

    project_gap_rows = []
    for p in projects[:8]:
        pname = p.get("project_name") or p.get("name") or p.get("filename")
        detected = [_skill_name(x) for x in _as_list(p.get("latest_technologies")) + _as_list(p.get("latest_capabilities"))]
        detected = sorted(set([x for x in detected if x]))
        gaps = []
        for s in detected:
            score = next((row["score"] for row in active_skills if row["skill"] == s), 0)
            if score < 70:
                gaps.append({"skill": s, "score": score})
        project_gap_rows.append({"project": pname, "detected_skills": detected[:8], "gaps": gaps[:5]})

    total_quests = len(quests)
    proofed = sum(1 for q in quests if _has_proof(q))
    completed = sum(1 for q in quests if _is_completed(q))
    avg_skill_score = int(sum(s["score"] for s in active_skills) / len(active_skills)) if active_skills else 0

    return {
        "version": "V32",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "totals": {
            "skills_tracked": len(active_skills),
            "active_quests": total_quests,
            "proofed_quests": proofed,
            "completed_quests": completed,
            "tracked_projects": len(projects),
            "average_skill_score": avg_skill_score,
        },
        "bottleneck": bottleneck,
        "recommended_quest": recommended_quest,
        "weakest_skills": weakest,
        "strongest_skills": strongest,
        "skills": sorted(active_skills, key=lambda x: x["score"], reverse=True),
        "project_gaps": project_gap_rows,
        "rule": "Learning Intelligence must prefer proof over assumptions. A skill is not mastered just because a quest exists.",
        "next_action": _next_action_text(bottleneck, recommended_quest),
    }


def _next_action_text(bottleneck: Dict[str, Any] | None, quest: Dict[str, Any] | None) -> str:
    if not bottleneck:
        return "Upload or complete more quests so KDT OS has evidence to learn from."
    if quest:
        return f"Work on {quest.get('title')} because it strengthens {bottleneck.get('skill')}, your current weakest useful skill."
    return f"Create one proof-backed quest for {bottleneck.get('skill')} because it is currently weak or unproven."


def install(kdt: Any) -> None:
    app = kdt.app

    def learning_intelligence():
        return kdt.render_template("learning_intelligence.html", data=learning_intelligence_snapshot(kdt))

    def learning_intelligence_json():
        return kdt.jsonify(learning_intelligence_snapshot(kdt))

    app.add_url_rule("/learning_intelligence", "learning_intelligence", learning_intelligence, methods=["GET"])
    app.add_url_rule("/learning_intelligence.json", "learning_intelligence_json", learning_intelligence_json, methods=["GET"])

    kdt.learning_intelligence_snapshot_v32 = lambda: learning_intelligence_snapshot(kdt)
