"""KDT OS Command Center V30

V30 shifts KDT OS from "more architecture pages" to daily usefulness.
It answers the key OS question:

    What should Kewonte do right now?

The Command Center combines quests, projects, goals, mastery, governance, and
system health into one ranked next-best-action view.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple
import json
import re


def _safe_call(obj: Any, name: str, default):
    fn = getattr(obj, name, None)
    if not callable(fn):
        return default
    try:
        return fn()
    except Exception:
        return default


def _read_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _list_json(folder: Path) -> List[Path]:
    try:
        return sorted(folder.glob("*.json"))
    except Exception:
        return []


def _quest_score(q: Dict[str, Any]) -> int:
    qq = q.get("quest_quality")
    if isinstance(qq, dict):
        try:
            return int(qq.get("score", 0))
        except Exception:
            return 0
    try:
        return int(q.get("score", 0))
    except Exception:
        return 0


def _status(q: Dict[str, Any]) -> str:
    return str(q.get("status") or "Assigned")


def _active(q: Dict[str, Any]) -> bool:
    return _status(q).lower() not in {"completed", "archived", "superseded", "replaced"}


def _filename(q: Dict[str, Any]) -> str:
    return str(q.get("filename") or q.get("_filename") or "")


def _clean_title(text: str) -> str:
    text = re.sub(r"[_\-]+", " ", text or "").strip()
    return re.sub(r"\s+", " ", text)


def _load_quests(kdt: Any) -> List[Dict[str, Any]]:
    quests = _safe_call(kdt, "list_quests", [])
    if quests:
        out = []
        for q in quests:
            if isinstance(q, dict):
                out.append(q)
        return out

    folder = Path(getattr(kdt, "QUEST_DIR", Path(getattr(kdt, "APP_ROOT", ".")) / "quests"))
    out = []
    for f in _list_json(folder):
        data = _read_json(f, {})
        if isinstance(data, dict):
            data["_filename"] = f.name
            out.append(data)
    return out


def _load_projects(kdt: Any) -> List[Dict[str, Any]]:
    projects = _safe_call(kdt, "list_projects", [])
    if projects:
        return [p for p in projects if isinstance(p, dict)]

    folder = Path(getattr(kdt, "PROJECT_DIR", Path(getattr(kdt, "APP_ROOT", ".")) / "projects"))
    out = []
    for f in _list_json(folder):
        data = _read_json(f, {})
        if isinstance(data, dict):
            data["_filename"] = f.name
            out.append(data)
    return out


def _load_goals(kdt: Any) -> List[Dict[str, Any]]:
    goals = _safe_call(kdt, "list_goals", [])
    if goals:
        return [g for g in goals if isinstance(g, dict)]

    folder = Path(getattr(kdt, "GOAL_DIR", Path(getattr(kdt, "APP_ROOT", ".")) / "goals"))
    out = []
    for f in _list_json(folder):
        data = _read_json(f, {})
        if isinstance(data, dict):
            data["_filename"] = f.name
            out.append(data)
    return out


def _storage_snapshot(kdt: Any) -> Dict[str, Any]:
    fn = getattr(kdt, "core_storage_snapshot_v29", None)
    if callable(fn):
        try:
            return fn()
        except Exception:
            return {}
    return {}


def _governance_snapshot(kdt: Any) -> Dict[str, Any]:
    # Prefer V25 if available.
    for name in ["governance_intelligence_snapshot_v25", "unified_governance_snapshot_v24", "auto_governance_plan_v23"]:
        fn = getattr(kdt, name, None)
        if callable(fn):
            try:
                return fn()
            except Exception:
                pass
    return {}


def _best_quest(quests: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    active = [q for q in quests if _active(q)]
    if not active:
        return None

    def rank(q: Dict[str, Any]) -> Tuple[int, int, str]:
        score = _quest_score(q)
        # Prefer strong, exact quests first. Avoid superseded/generic old ones.
        title = str(q.get("title") or "")
        penalty = 0
        if "I don't understand" in title or "Teach_Me_Mode" in _filename(q):
            penalty -= 15
        if q.get("proof_required") or q.get("proof"):
            penalty += 10
        if q.get("steps"):
            penalty += 10
        return (score + penalty, score, title)

    return sorted(active, key=rank, reverse=True)[0]


def _learning_gap(quests: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    weak = []
    for q in quests:
        if not _active(q):
            continue
        score = _quest_score(q)
        if score and score < 85:
            weak.append(q)
    if not weak:
        return None
    weak = sorted(weak, key=lambda q: _quest_score(q))
    q = weak[0]
    return {
        "title": q.get("title") or "Weak quest",
        "filename": _filename(q),
        "score": _quest_score(q),
        "skill": q.get("skill") or "Unknown",
        "why": "This quest may confuse your learning because its quality score is low."
    }


def _project_next_step(projects: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    if not projects:
        return None
    def pdate(p):
        return str(p.get("analyzed_at") or p.get("created_at") or p.get("updated_at") or "")
    p = sorted(projects, key=pdate, reverse=True)[0]
    name = p.get("project_name") or p.get("name") or p.get("title") or _clean_title(p.get("_filename", "Project"))
    caps = p.get("latest_capabilities") or p.get("capabilities") or []
    tech = p.get("latest_technologies") or p.get("technologies") or []
    return {
        "name": name,
        "capabilities": caps[:5] if isinstance(caps, list) else [],
        "technologies": tech[:5] if isinstance(tech, list) else [],
        "why": "Your most recent tracked project should drive the next skill quest."
    }


def command_center_snapshot(kdt: Any) -> Dict[str, Any]:
    quests = _load_quests(kdt)
    projects = _load_projects(kdt)
    goals = _load_goals(kdt)
    active_quests = [q for q in quests if _active(q)]
    strong_quests = [q for q in active_quests if _quest_score(q) >= 90]
    weak_gap = _learning_gap(quests)
    best = _best_quest(quests)
    project = _project_next_step(projects)
    storage = _storage_snapshot(kdt)
    governance = _governance_snapshot(kdt)

    if best:
        title = best.get("title") or "Continue current quest"
        best_action = {
            "type": "Quest",
            "title": title,
            "subtitle": best.get("skill") or best.get("type") or "Practice",
            "why": "This is the strongest active quest with proof, steps, and a high quality score.",
            "do_now": best.get("what_to_build") or "Open this quest and complete the next proof step.",
            "proof": (best.get("proof_required") or best.get("proof") or ["Upload proof or write what you did."]),
            "score": _quest_score(best),
            "filename": _filename(best),
            "url_endpoint": "view_quest",
        }
    else:
        best_action = {
            "type": "Setup",
            "title": "Create or upload a project",
            "subtitle": "No active quest found",
            "why": "KDT OS needs a real project or quest to guide your next move.",
            "do_now": "Upload a project folder or create a new quest from Teach Me Mode.",
            "proof": ["A project report or quest exists."],
            "score": 0,
            "filename": "",
            "url_endpoint": "",
        }

    today_steps = []
    if best:
        steps = best.get("steps") or []
        if isinstance(steps, list) and steps:
            today_steps = [str(s) for s in steps[:5]]
    if not today_steps:
        today_steps = [
            "Open the recommended quest.",
            "Create the exact file, folder, screenshot, or written proof it asks for.",
            "Do only the first visible step.",
            "Save or screenshot the proof.",
            "Submit proof back into KDT OS."
        ]

    blockers = []
    if weak_gap:
        blockers.append({
            "title": "Weak quest may need cleanup",
            "detail": f"{weak_gap['title']} is scored {weak_gap['score']}%.",
            "fix": "Use Action Center or Auto Governance before relying on this quest."
        })
    if storage.get("direct_storage_weight", 0) > 100:
        blockers.append({
            "title": "app.py still carries storage weight",
            "detail": f"{storage.get('direct_storage_weight')} raw storage calls remain.",
            "fix": "New modules should use core.storage instead of adding new raw JSON calls."
        })
    if not blockers:
        blockers.append({
            "title": "No urgent blocker detected",
            "detail": "Use the best action and submit proof.",
            "fix": "Complete the quest before adding another feature."
        })

    return {
        "version": "V30",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "headline": "Do the one thing that moves you forward today.",
        "counts": {
            "active_quests": len(active_quests),
            "strong_quests": len(strong_quests),
            "projects": len(projects),
            "goals": len(goals),
        },
        "best_action": best_action,
        "today_steps": today_steps,
        "project_context": project,
        "blockers": blockers[:4],
        "strong_quests": [
            {
                "title": q.get("title") or _clean_title(_filename(q)),
                "filename": _filename(q),
                "score": _quest_score(q),
                "skill": q.get("skill") or "",
            }
            for q in strong_quests[:6]
        ],
        "system_note": "V30 changes KDT OS from another architecture checkpoint into a daily operating view. It chooses a best action, explains why, and names proof.",
        "governance_available": bool(governance),
        "storage_ready": bool(storage.get("readiness", 0) >= 75) if storage else False,
    }


def install(kdt: Any) -> None:
    app = kdt.app

    def command_center():
        return kdt.render_template("command_center.html", snapshot=command_center_snapshot(kdt))

    def command_center_json():
        return kdt.jsonify(command_center_snapshot(kdt))

    app.add_url_rule("/command_center", "command_center", command_center, methods=["GET"])
    app.add_url_rule("/command_center.json", "command_center_json", command_center_json, methods=["GET"])

    kdt.command_center_snapshot_v30 = lambda: command_center_snapshot(kdt)
