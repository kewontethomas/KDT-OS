"""KDT OS Learning Intelligence V32

V32 turns KDT OS toward the user: it reads projects, quests, quest quality,
and proof history to answer what Kewonte knows, what is weak, and what to do next.
"""
from __future__ import annotations

from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import re

try:
    from core.storage import load_json, list_json_files, read_text
except Exception:
    load_json = None
    list_json_files = None
    read_text = None


def _slugish(text: str) -> str:
    text = (text or "Unknown").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:80] or "Unknown"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if isinstance(value, bool):
            return default
        return int(float(value))
    except Exception:
        return default


def _read_json(path: Path, default: Any) -> Any:
    if load_json:
        return load_json(path, default)
    try:
        import json
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _json_files(folder: Path) -> List[Path]:
    if list_json_files:
        return list_json_files(folder)
    return sorted(folder.glob("*.json")) if folder.exists() else []


def _quest_score(q: Dict[str, Any]) -> int:
    qq = q.get("quest_quality") or {}
    if isinstance(qq, dict):
        score = _safe_int(qq.get("score"), -1)
        if score >= 0:
            return max(0, min(100, score))
    return max(0, min(100, _safe_int(q.get("score"), 50)))


def _is_complete(q: Dict[str, Any]) -> bool:
    status = str(q.get("status", "")).lower()
    return any(word in status for word in ["complete", "completed", "approved", "verified", "done"])


def _is_archived_or_superseded(q: Dict[str, Any]) -> bool:
    status = str(q.get("status", "")).lower()
    return any(word in status for word in ["archive", "archived", "superseded"])


def _load_quests(root: Path) -> List[Dict[str, Any]]:
    quests = []
    qdir = root / "quests"
    for path in _json_files(qdir):
        data = _read_json(path, {})
        if isinstance(data, dict):
            data["filename"] = path.name
            data["_path"] = str(path)
            quests.append(data)
    return quests


def _load_projects(root: Path) -> List[Dict[str, Any]]:
    projects = []
    pdir = root / "projects"
    for path in _json_files(pdir):
        data = _read_json(path, {})
        if isinstance(data, dict):
            data["filename"] = path.name
            projects.append(data)
    return projects


def _skill_from_quest(q: Dict[str, Any]) -> str:
    skill = q.get("skill") or q.get("topic") or q.get("category")
    if not skill:
        title = q.get("title", "")
        if ":" in title:
            skill = title.split(":", 1)[0]
        else:
            skill = "General Practice"
    skill = str(skill).strip()
    noisy = ["i don't understand", "i dont understand", "single proof quest"]
    low = skill.lower()
    if any(n in low for n in noisy):
        # Keep the skill readable when old Teach Me quests used the whole confusion as skill.
        title = str(q.get("title", skill))
        if "active directory" in title.lower():
            return "Active Directory"
        if "cpu" in title.lower():
            return "CPU Usage"
    return _slugish(skill)


def _project_name(q: Dict[str, Any]) -> str:
    return _slugish(q.get("source_project") or q.get("resume_project") or q.get("project") or q.get("connected_goal") or "Unassigned")


def _skill_profiles(quests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    bucket: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for q in quests:
        if _is_archived_or_superseded(q):
            continue
        bucket[_skill_from_quest(q)].append(q)

    rows = []
    for skill, items in bucket.items():
        scores = [_quest_score(q) for q in items]
        avg = round(sum(scores) / max(1, len(scores)))
        complete = sum(1 for q in items if _is_complete(q))
        strong = sum(1 for q in items if _quest_score(q) >= 85)
        weak = sum(1 for q in items if _quest_score(q) < 70)
        proof_ready = sum(1 for q in items if q.get("proof_required") or q.get("verification_patterns"))
        mastery = avg
        # If a skill has no completed proof yet, do not let it look mastered only because quest text is strong.
        if complete == 0 and proof_ready:
            mastery = min(mastery, 78)
        if weak:
            mastery = min(mastery, 68)
        status = "Strong" if mastery >= 85 else "Building" if mastery >= 65 else "Needs practice"
        rows.append({
            "skill": skill,
            "score": mastery,
            "quest_count": len(items),
            "strong_count": strong,
            "weak_count": weak,
            "completed_count": complete,
            "proof_ready_count": proof_ready,
            "status": status,
            "best_quest": max(items, key=_quest_score).get("title", ""),
            "weakest_quest": min(items, key=_quest_score).get("title", ""),
            "recommended_action": "Complete a proof-backed quest" if complete == 0 else "Add another variation to prove retention",
        })
    return sorted(rows, key=lambda r: (r["score"], -r["quest_count"]))


def _project_gaps(projects: List[Dict[str, Any]], skill_rows: List[Dict[str, Any]], quests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    skill_score = {r["skill"].lower(): r["score"] for r in skill_rows}
    rows = []
    for p in projects:
        name = p.get("project_name") or p.get("name") or p.get("filename", "Project")
        techs = p.get("latest_technologies") or []
        caps = p.get("latest_capabilities") or []
        missing = []
        for tech in techs[:10]:
            score = skill_score.get(str(tech).lower())
            if score is None:
                missing.append({"skill": tech, "reason": "Project uses this but no active proof-backed skill score exists yet.", "score": 0})
            elif score < 70:
                missing.append({"skill": tech, "reason": "Project uses this and current learning score is low.", "score": score})
        blockers = []
        lname = str(name).lower()
        for q in quests:
            if lname in str(q.get("source_project", "")).lower() or lname in str(q.get("resume_project", "")).lower():
                if _quest_score(q) < 85:
                    blockers.append({"title": q.get("title", q.get("filename", "Quest")), "score": _quest_score(q)})
        rows.append({
            "project": name,
            "technologies": techs[:8],
            "capabilities": caps[:8],
            "gap_count": len(missing),
            "missing_skills": missing[:6],
            "quest_blockers": sorted(blockers, key=lambda x: x["score"])[:4],
            "recommendation": "Pick one missing skill and complete a proof quest before adding more features." if missing else "Keep building; current project skills look supported by existing evidence.",
        })
    return sorted(rows, key=lambda r: r["gap_count"], reverse=True)


def _bottleneck(skill_rows: List[Dict[str, Any]], quests: List[Dict[str, Any]]) -> Dict[str, Any]:
    weak_skills = [r for r in skill_rows if r["score"] < 70]
    if weak_skills:
        target = sorted(weak_skills, key=lambda r: (r["score"], -r["quest_count"]))[0]
    elif skill_rows:
        target = sorted(skill_rows, key=lambda r: (r["completed_count"], r["score"]))[0]
    else:
        target = {"skill": "Unknown", "score": 0, "quest_count": 0, "weakest_quest": "No active quest yet"}
    related = [q for q in quests if _skill_from_quest(q).lower() == target["skill"].lower()]
    related = sorted(related, key=lambda q: (_quest_score(q), q.get("title", "")))
    quest = related[0] if related else {}
    evidence = []
    if target.get("score", 0) < 70:
        evidence.append("Skill score is below 70, so this likely needs deliberate practice.")
    if target.get("completed_count", 0) == 0:
        evidence.append("No completed proof has been found for this skill yet.")
    if target.get("weak_count", 0):
        evidence.append(f"{target.get('weak_count')} related quest(s) are weak or incomplete.")
    if not evidence:
        evidence.append("This is the next weakest available area based on active quest evidence.")
    return {
        "skill": target.get("skill", "Unknown"),
        "score": target.get("score", 0),
        "evidence": evidence,
        "recommended_quest": quest.get("title") or target.get("weakest_quest") or "Create a new proof quest",
        "quest_filename": quest.get("filename", ""),
        "next_action": "Open the recommended quest, complete the smallest proof step, and submit evidence.",
    }


def _recommended_next(skill_rows: List[Dict[str, Any]], projects: List[Dict[str, Any]]) -> Dict[str, Any]:
    project_techs = Counter()
    for p in projects:
        for t in p.get("latest_technologies") or []:
            project_techs[str(t)] += 1
    if skill_rows:
        ranked = sorted(skill_rows, key=lambda r: (r["score"] - project_techs.get(r["skill"], 0) * 8, -r["quest_count"]))
        pick = ranked[0]
        reason = "This skill is weak and/or appears in tracked project technology lists."
        return {"skill": pick["skill"], "score": pick["score"], "reason": reason, "action": pick["recommended_action"]}
    return {"skill": "Add a real project or quest", "score": 0, "reason": "KDT OS needs evidence before it can recommend a learning path.", "action": "Upload or analyze a project."}


def learning_intelligence_snapshot(kdt: Any) -> Dict[str, Any]:
    root = Path(kdt.APP_ROOT)
    quests = _load_quests(root)
    projects = _load_projects(root)
    active = [q for q in quests if not _is_archived_or_superseded(q)]
    skill_rows = _skill_profiles(active)
    strong = [r for r in skill_rows if r["score"] >= 85]
    needs = [r for r in skill_rows if r["score"] < 70]
    avg = round(sum(r["score"] for r in skill_rows) / max(1, len(skill_rows))) if skill_rows else 0
    bottleneck = _bottleneck(skill_rows, active)
    project_gaps = _project_gaps(projects, skill_rows, active)
    recommended = _recommended_next(skill_rows, projects)
    return {
        "version": "V32",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "active_quests": len(active),
        "tracked_projects": len(projects),
        "skills_tracked": len(skill_rows),
        "average_learning_score": avg,
        "strong_skills": len(strong),
        "needs_practice": len(needs),
        "skill_rows": sorted(skill_rows, key=lambda r: r["score"]),
        "top_skills": sorted(skill_rows, key=lambda r: r["score"], reverse=True)[:6],
        "bottleneck": bottleneck,
        "project_gaps": project_gaps[:6],
        "recommended_next": recommended,
        "rule": "KDT OS should recommend learning based on evidence: quests, proof, project technology, and repeated blockers—not guesses.",
        "next_targets": [
            {"phase": "V33", "title": "Proof Memory", "move": "Use quest submissions and uploaded proof to update skill scores after each completed quest.", "proof": "Completing a quest changes the Learning Intelligence score."},
            {"phase": "V34", "title": "Project Skill Gap Quests", "move": "Let project gaps generate exact quests directly from the Learning Intelligence page.", "proof": "A missing project skill can create a new proof quest."},
            {"phase": "V35", "title": "Adaptive Study Plan", "move": "Create a 7-day learning plan from weak skills and active project goals.", "proof": "KDT OS recommends daily practice in the Command Center."},
        ],
    }


def install(kdt: Any) -> None:
    app = kdt.app

    def learning_intelligence():
        return kdt.render_template("learning_intelligence.html", snapshot=learning_intelligence_snapshot(kdt))

    def learning_intelligence_json():
        return kdt.jsonify(learning_intelligence_snapshot(kdt))

    app.add_url_rule("/learning_intelligence", "learning_intelligence", learning_intelligence, methods=["GET"])
    app.add_url_rule("/learning_intelligence.json", "learning_intelligence_json", learning_intelligence_json, methods=["GET"])
    kdt.learning_intelligence_snapshot_v32 = lambda: learning_intelligence_snapshot(kdt)
