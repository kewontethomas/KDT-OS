"""KDT OS Auto Governance V23

Adds a safer gate between quest creation and active learning.
V23 does not replace V20; it uses V20's scoring/regeneration helpers to:
- audit active quests
- rescore missing quest_quality metadata
- regenerate weak/generic quests
- archive duplicate quest bodies
- produce a repair report with exact actions taken

Install with install(sys.modules[__name__]) after V20/V21/V22.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

GENERIC_MARKERS = [
    "one artifact that proves",
    "small project that demonstrates",
    "small project that demonstrates the requested skill",
    "demonstrates the requested skill",
    "exact_skill_proof_drill",
    "requested skill one time",
    "create original files",
]


def _read_json(path: Path) -> Dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _as_text(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(_as_text(v) for v in value)
    if isinstance(value, dict):
        return "\n".join(f"{k}: {_as_text(v)}" for k, v in value.items())
    return str(value or "")


def _quest_text(q: Dict[str, Any]) -> str:
    fields = [
        q.get("title", ""),
        q.get("skill", ""),
        q.get("what_to_build", ""),
        q.get("requirements", []),
        q.get("steps", []),
        q.get("success_criteria", []),
        q.get("proof_required", []),
    ]
    return _as_text(fields).lower()


def _status_active(q: Dict[str, Any]) -> bool:
    return str(q.get("status", "Assigned")).lower() not in {"archived", "superseded", "rejected", "completed"}


def _canonical_for_duplicate(kdt: Any, q: Dict[str, Any]) -> str:
    if hasattr(kdt, "canonical_instruction_text"):
        try:
            return kdt.canonical_instruction_text(q)
        except Exception:
            pass
    text = _quest_text(q)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _generic_reasons(q: Dict[str, Any]) -> List[str]:
    text = _quest_text(q)
    return [m for m in GENERIC_MARKERS if m in text]


def active_quest_records(kdt: Any) -> List[Tuple[Path, Dict[str, Any]]]:
    rows: List[Tuple[Path, Dict[str, Any]]] = []
    for path in sorted(kdt.QUEST_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        q = _read_json(path)
        if not q or not _status_active(q):
            continue
        q["filename"] = path.name
        rows.append((path, q))
    return rows


def governance_plan(kdt: Any) -> Dict[str, Any]:
    rows = active_quest_records(kdt)
    signatures: Dict[str, List[str]] = {}
    for _path, q in rows:
        sig = _canonical_for_duplicate(kdt, q)
        signatures.setdefault(sig, []).append(q.get("filename", ""))

    items: List[Dict[str, Any]] = []
    for path, q in rows:
        filename = q.get("filename", path.name)
        q_working = dict(q)
        quality = q_working.get("quest_quality") if isinstance(q_working.get("quest_quality"), dict) else None
        if quality is None and hasattr(kdt, "quest_quality_check"):
            try:
                quality = kdt.quest_quality_check(q_working)
            except Exception:
                quality = None
        gov = None
        if hasattr(kdt, "quest_governance_decision"):
            try:
                gov = kdt.quest_governance_decision(q_working)
            except Exception:
                gov = None
        score = int((gov or {}).get("score", (quality or {}).get("score", 0)) or 0)
        generic = _generic_reasons(q_working)
        sig = _canonical_for_duplicate(kdt, q_working)
        dupes = [f for f in signatures.get(sig, []) if f != filename]

        actions: List[str] = []
        reasons: List[str] = []
        risk = "low"
        if quality is None or "quest_quality" not in q:
            actions.append("rescore")
            reasons.append("Quest is missing governance metadata.")
            risk = "medium"
        if generic:
            actions.append("regenerate")
            reasons.append("Generic template language detected: " + ", ".join(generic[:3]))
            risk = "high"
        if score and score < getattr(kdt, "QUEST_MINIMUM_SCORE", 85):
            actions.append("regenerate")
            reasons.append(f"Governance score is below minimum: {score}%.")
            risk = "high"
        if dupes:
            actions.append("dedupe")
            reasons.append("Duplicate instruction body detected with: " + ", ".join(dupes[:3]))
            risk = "high"
        actions = list(dict.fromkeys(actions))
        if actions:
            items.append({
                "filename": filename,
                "title": q.get("title", "Untitled Quest"),
                "skill": q.get("skill", "Unknown"),
                "score": score,
                "risk": risk,
                "actions": actions,
                "reasons": reasons,
                "dupes": dupes,
                "exact_fix": exact_fix_for(actions, filename),
            })
    high = sum(1 for i in items if i["risk"] == "high")
    medium = sum(1 for i in items if i["risk"] == "medium")
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "total_active_quests": len(rows),
        "issues": len(items),
        "high_risk": high,
        "medium_risk": medium,
        "ready_to_run": len(items) > 0,
        "items": items,
    }


def exact_fix_for(actions: List[str], filename: str) -> str:
    if "dedupe" in actions:
        return f"Archive the duplicate version of {filename}, create a postmortem, then regenerate from the specific skill/project gap."
    if "regenerate" in actions:
        return f"Regenerate {filename} through Quest Intelligence so the replacement has exact files, exact steps, exact proof, and an understanding check."
    if "rescore" in actions:
        return f"Open {filename}, run quest_quality_check(), save quest_quality and governance metadata back into the JSON file."
    return f"Review {filename} manually."


def run_auto_governance(kdt: Any, dry_run: bool = False) -> Dict[str, Any]:
    plan = governance_plan(kdt)
    result = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "dry_run": dry_run,
        "planned": plan,
        "actions_taken": [],
        "created_files": [],
        "rescored": [],
        "skipped": [],
        "errors": [],
    }
    if dry_run:
        return result

    processed: set[str] = set()
    # Rescore missing metadata first because it is safe and preserves files.
    for item in plan["items"]:
        filename = item["filename"]
        if filename in processed:
            continue
        path = kdt.QUEST_DIR / filename
        q = _read_json(path)
        if not q:
            continue
        try:
            if "rescore" in item["actions"] and not any(a in item["actions"] for a in ["regenerate", "dedupe"]):
                if hasattr(kdt, "apply_quest_quality"):
                    q = kdt.apply_quest_quality(q)
                elif hasattr(kdt, "quest_quality_check"):
                    q["quest_quality"] = kdt.quest_quality_check(q)
                if hasattr(kdt, "quest_governance_decision"):
                    q["governance"] = kdt.quest_governance_decision(q)
                _write_json(path, q)
                result["rescored"].append(filename)
                result["actions_taken"].append({"file": filename, "action": "rescored"})
                processed.add(filename)
        except Exception as exc:
            result["errors"].append({"file": filename, "error": str(exc)})
            processed.add(filename)

    # Regenerate weak/generic/duplicate active quests. V20's regenerate_quest archives old with postmortem.
    for item in plan["items"]:
        filename = item["filename"]
        if filename in processed:
            continue
        if not any(a in item["actions"] for a in ["regenerate", "dedupe"]):
            continue
        try:
            if hasattr(kdt, "regenerate_quest"):
                newfile, _newq = kdt.regenerate_quest(filename)
                if newfile:
                    result["created_files"].append(newfile)
                    result["actions_taken"].append({"file": filename, "action": "regenerated", "replacement": newfile})
                else:
                    result["skipped"].append({"file": filename, "reason": "regenerate_quest returned no replacement"})
            else:
                result["skipped"].append({"file": filename, "reason": "regenerate_quest is not available"})
        except Exception as exc:
            result["errors"].append({"file": filename, "error": str(exc)})
        processed.add(filename)

    log_dir = getattr(kdt, "REPORT_DIR", Path("reports"))
    try:
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"auto_governance_v23_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        _write_json(log_file, result)
        result["log_file"] = log_file.name
    except Exception:
        pass
    if hasattr(kdt, "governance_log"):
        try:
            kdt.governance_log({
                "type": "auto_governance_v23_run",
                "planned_issues": plan.get("issues", 0),
                "actions_taken": len(result["actions_taken"]),
                "created_files": result["created_files"],
                "errors": result["errors"],
            })
        except Exception:
            pass
    return result


def install(kdt: Any) -> Any:
    app = getattr(kdt, "app", None)
    if app is None:
        return kdt

    if "auto_governance" not in app.view_functions:
        def auto_governance():
            plan = governance_plan(kdt)
            return kdt.render_template("auto_governance.html", plan=plan, result=None)
        app.add_url_rule("/auto_governance", "auto_governance", auto_governance)

    if "auto_governance_run" not in app.view_functions:
        def auto_governance_run():
            dry_run = str(kdt.request.form.get("dry_run", "")).lower() in {"1", "true", "yes", "on"}
            result = run_auto_governance(kdt, dry_run=dry_run)
            plan = governance_plan(kdt)
            return kdt.render_template("auto_governance.html", plan=plan, result=result)
        app.add_url_rule("/auto_governance/run", "auto_governance_run", auto_governance_run, methods=["POST"])

    if "auto_governance_json" not in app.view_functions:
        def auto_governance_json():
            return kdt.jsonify(governance_plan(kdt))
        app.add_url_rule("/auto_governance.json", "auto_governance_json", auto_governance_json)

    kdt.auto_governance_plan_v23 = lambda: governance_plan(kdt)
    kdt.run_auto_governance_v23 = lambda dry_run=False: run_auto_governance(kdt, dry_run=dry_run)
    return kdt
