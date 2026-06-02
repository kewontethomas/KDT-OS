"""KDT OS Action Engine V26

V26 turns governance reports into safer one-click actions.
It does not replace V25. It wraps V25 with an action console:
- preview safe repairs
- repair missing governance metadata
- archive weaker duplicate quests
- approve strong quests in-place
- run safe cleanup
- log every action to reports/governance_actions.json

Safety rule: V26 only changes active quest JSON files and archives copies.
It does not delete quest history.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

try:
    import kdt_governance_intelligence_v25 as v25
except Exception:  # pragma: no cover
    v25 = None


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _read_json(path: Path) -> Dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _action_log_path(kdt: Any) -> Path:
    report_dir = Path(kdt.REPORT_DIR)
    report_dir.mkdir(exist_ok=True)
    return report_dir / "governance_actions.json"


def _load_action_log(kdt: Any) -> List[Dict[str, Any]]:
    path = _action_log_path(kdt)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_action_log(kdt: Any, entries: List[Dict[str, Any]]) -> None:
    _write_json(_action_log_path(kdt), entries[:300])


def _append_log(kdt: Any, entry: Dict[str, Any]) -> None:
    entries = _load_action_log(kdt)
    entry.setdefault("created_at", _now())
    entry.setdefault("version", "V26")
    entries.insert(0, entry)
    _save_action_log(kdt, entries)


def _plan(kdt: Any) -> Dict[str, Any]:
    if v25 and hasattr(v25, "governance_intelligence_plan"):
        return v25.governance_intelligence_plan(kdt)
    if hasattr(kdt, "governance_intelligence_plan_v25"):
        return kdt.governance_intelligence_plan_v25()
    return {
        "version": "V26",
        "total_active_quests": 0,
        "average_score": 0,
        "items": [],
        "clean_items": [],
        "clusters": [],
        "categories": [],
        "scanner_note": "V25 governance scanner was not available.",
    }


def _active_path(kdt: Any, filename: str) -> Path:
    return Path(kdt.QUEST_DIR) / filename


def _archive_dirs(kdt: Any) -> tuple[Path, Path]:
    archive = Path(kdt.QUEST_ARCHIVE_DIR)
    post = Path(kdt.QUEST_POSTMORTEM_DIR)
    archive.mkdir(exist_ok=True)
    post.mkdir(exist_ok=True)
    return archive, post


def _repair_metadata(kdt: Any, item: Dict[str, Any], source: str = "action_center") -> Dict[str, Any]:
    filename = item.get("filename", "")
    path = _active_path(kdt, filename)
    q = _read_json(path)
    if not q:
        return {"ok": False, "file": filename, "action": "repair_metadata", "error": "Quest file not found or invalid JSON."}

    before_score = q.get("quest_quality")
    score = int(item.get("score", before_score or 0))
    q["quest_quality"] = max(score, int(q.get("quest_quality", 0) or 0))
    q.setdefault("governance", {})
    q["governance"].update({
        "engine": "V26 Action Engine",
        "last_checked_at": _now(),
        "score": score,
        "risk": item.get("risk", "unknown"),
        "status": item.get("status", "Unknown"),
        "recommended_actions": item.get("actions", []),
    })

    if "understanding_check" not in q:
        q["understanding_check"] = {
            "required": True,
            "prompt": "Explain what you built, what worked, what confused you, and what this proves."
        }

    if "proof_required" not in q and "proof" in q:
        q["proof_required"] = q.get("proof", [])

    if "proof_required" not in q:
        q["proof_required"] = [
            "Upload the finished project or screenshot.",
            "Include a short explanation of what the proof demonstrates."
        ]

    q["last_governance_action"] = {
        "at": _now(),
        "action": "repair_metadata",
        "source": source,
    }
    _write_json(path, q)
    return {"ok": True, "file": filename, "action": "repair_metadata", "before_score": before_score, "after_score": q.get("quest_quality")}


def _approve_strong(kdt: Any, item: Dict[str, Any], source: str = "action_center") -> Dict[str, Any]:
    filename = item.get("filename", "")
    path = _active_path(kdt, filename)
    q = _read_json(path)
    if not q:
        return {"ok": False, "file": filename, "action": "approve_strong", "error": "Quest file not found or invalid JSON."}

    score = int(item.get("score", q.get("quest_quality", 0) or 0))
    if score < 85:
        return {"ok": False, "file": filename, "action": "approve_strong", "error": f"Score {score} is below 85."}

    q["quest_quality"] = max(score, int(q.get("quest_quality", 0) or 0))
    q["governance_approved"] = True
    q["governance_approved_at"] = _now()
    q["governance_approved_by"] = "KDT OS V26 Action Engine"
    q.setdefault("governance", {})
    q["governance"].update({
        "engine": "V26 Action Engine",
        "approved": True,
        "score": score,
        "status": "Approved",
        "last_checked_at": _now(),
    })
    _write_json(path, q)
    return {"ok": True, "file": filename, "action": "approve_strong", "score": score}


def _cluster_archive_targets(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    targets: List[Dict[str, Any]] = []
    seen = set()
    for cluster in plan.get("clusters", []):
        for candidate in cluster.get("archive_candidates", []):
            if isinstance(candidate, str):
                filename = candidate
                reason = cluster.get("reason", "Weaker duplicate in governance cluster.")
            else:
                filename = candidate.get("filename", "")
                reason = candidate.get("reason") or cluster.get("reason", "Weaker duplicate in governance cluster.")
            if filename and filename not in seen:
                targets.append({"filename": filename, "reason": reason, "cluster": cluster.get("name", "Duplicate cluster")})
                seen.add(filename)
    return targets


def _archive_duplicate(kdt: Any, target: Dict[str, Any], source: str = "action_center") -> Dict[str, Any]:
    filename = target.get("filename", "")
    src = _active_path(kdt, filename)
    q = _read_json(src)
    if not q:
        return {"ok": False, "file": filename, "action": "archive_duplicate", "error": "Quest file not found or invalid JSON."}

    archive_dir, post_dir = _archive_dirs(kdt)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"{src.stem}_{stamp}_v26_archived.json"
    q["status"] = "Archived"
    q["archived_at"] = _now()
    q["archive_reason"] = target.get("reason", "Archived by V26 Action Engine.")
    q["archived_by"] = "KDT OS V26 Action Engine"
    _write_json(archive_dir / archive_name, q)

    post = {
        "created_at": _now(),
        "version": "V26",
        "quest": filename,
        "archive_file": archive_name,
        "reason": target.get("reason", "Weaker duplicate archived."),
        "cluster": target.get("cluster", ""),
        "lesson": "KDT OS should keep the strongest version and preserve weaker duplicates as history.",
    }
    post_name = f"{src.stem}_{stamp}_v26_postmortem.json"
    _write_json(post_dir / post_name, post)

    # remove active file only after archive/postmortem are written
    src.unlink(missing_ok=True)
    return {"ok": True, "file": filename, "action": "archive_duplicate", "archive": archive_name, "postmortem": post_name}


def _preview_actions(kdt: Any) -> Dict[str, Any]:
    plan = _plan(kdt)
    duplicate_targets = _cluster_archive_targets(plan)
    repair_targets = [
        i for i in plan.get("items", []) + plan.get("maintenance_items", [])
        if "repair_metadata" in i.get("actions", []) or "add_understanding_check" in i.get("actions", []) or i.get("score", 0) < 85
    ]
    approve_targets = [
        i for i in plan.get("clean_items", []) + plan.get("all_items", [])
        if i.get("score", 0) >= 90 and not i.get("is_issue")
    ]
    # dedupe approvals
    seen = set(); deduped_approve = []
    for item in approve_targets:
        fn = item.get("filename")
        if fn and fn not in seen:
            deduped_approve.append(item); seen.add(fn)

    return {
        "created_at": _now(),
        "version": "V26",
        "plan": plan,
        "proposed": {
            "repair_metadata": len(repair_targets),
            "archive_duplicates": len(duplicate_targets),
            "approve_strong": len(deduped_approve),
            "manual_review": len([i for i in plan.get("items", []) if i.get("score", 0) < 70]),
        },
        "repair_targets": repair_targets,
        "duplicate_targets": duplicate_targets,
        "approval_targets": deduped_approve,
        "recent_actions": _load_action_log(kdt)[:12],
    }


def run_action(kdt: Any, action: str) -> Dict[str, Any]:
    preview = _preview_actions(kdt)
    result = {
        "created_at": _now(),
        "version": "V26",
        "requested_action": action,
        "summary": {},
        "actions": [],
        "errors": [],
        "preview": preview,
    }

    def add(out: Dict[str, Any]) -> None:
        result["actions"].append(out)
        if not out.get("ok"):
            result["errors"].append(out)

    if action == "preview":
        result["summary"] = preview.get("proposed", {})
        _append_log(kdt, {"action": "preview", "result": result["summary"]})
        return result

    if action in ("repair_metadata", "safe_cleanup"):
        for item in preview.get("repair_targets", []):
            add(_repair_metadata(kdt, item))

    if action in ("archive_duplicates", "safe_cleanup"):
        for target in preview.get("duplicate_targets", []):
            add(_archive_duplicate(kdt, target))

    if action in ("approve_strong", "safe_cleanup"):
        # refresh plan after archive/repair so approvals are current
        approval_preview = _preview_actions(kdt)
        for item in approval_preview.get("approval_targets", []):
            add(_approve_strong(kdt, item))

    if action not in ("preview", "repair_metadata", "archive_duplicates", "approve_strong", "safe_cleanup"):
        result["errors"].append({"ok": False, "action": action, "error": "Unknown action."})

    ok_count = len([a for a in result["actions"] if a.get("ok")])
    result["summary"] = {
        "successful_actions": ok_count,
        "errors": len(result["errors"]),
        "metadata_repairs": len([a for a in result["actions"] if a.get("action") == "repair_metadata" and a.get("ok")]),
        "duplicates_archived": len([a for a in result["actions"] if a.get("action") == "archive_duplicate" and a.get("ok")]),
        "strong_approved": len([a for a in result["actions"] if a.get("action") == "approve_strong" and a.get("ok")]),
    }
    _append_log(kdt, {"action": action, "result": result["summary"], "errors": result["errors"][:5]})
    try:
        report = Path(kdt.REPORT_DIR) / f"v26_action_engine_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        _write_json(report, result)
        result["log_file"] = report.name
    except Exception as exc:
        result["errors"].append({"ok": False, "action": "write_report", "error": str(exc)})
    return result


def action_center_snapshot(kdt: Any) -> Dict[str, Any]:
    return _preview_actions(kdt)


def install(kdt: Any) -> Any:
    app = kdt.app

    def action_center():
        snapshot = action_center_snapshot(kdt)
        return kdt.render_template("action_center.html", snapshot=snapshot, result=None)

    def action_center_run():
        action = kdt.request.form.get("action", "preview")
        result = run_action(kdt, action)
        snapshot = action_center_snapshot(kdt)
        return kdt.render_template("action_center.html", snapshot=snapshot, result=result)

    def action_center_json():
        return kdt.jsonify(action_center_snapshot(kdt))

    if "action_center" in app.view_functions:
        app.view_functions["action_center"] = action_center
    else:
        app.add_url_rule("/action_center", "action_center", action_center)

    if "action_center_run" in app.view_functions:
        app.view_functions["action_center_run"] = action_center_run
    else:
        app.add_url_rule("/action_center/run", "action_center_run", action_center_run, methods=["POST"])

    if "action_center_json" in app.view_functions:
        app.view_functions["action_center_json"] = action_center_json
    else:
        app.add_url_rule("/action_center.json", "action_center_json", action_center_json)

    kdt.action_center_snapshot_v26 = lambda: action_center_snapshot(kdt)
    kdt.run_action_engine_v26 = lambda action="preview": run_action(kdt, action)
    return kdt
