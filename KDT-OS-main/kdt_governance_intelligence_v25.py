"""KDT OS Governance Intelligence V25

V25 improves V24 by making governance less noisy and more useful.
It adds:
- weighted quest quality scoring instead of one generic phrase = high risk
- duplicate clustering with keep/archive recommendations
- grouped Auto Governance UI data
- safer metadata repair
- Self Check quest audit powered by the same V25 scanner
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import kdt_unified_governance_v24 as v24
except Exception:  # pragma: no cover
    v24 = None

V25_MIN_SCORE = 85

GENERIC_MARKERS = [
    "one artifact that proves",
    "small project that demonstrates the requested skill",
    "demonstrates the requested skill",
    "requested skill one time",
    "create original files",
    "create a project folder",
    "create the main file",
    "implement the smallest working version",
    "run/open/show the artifact",
    "what i did, what worked, what confused me",
]

LEGACY_TITLE_MARKERS = [
    "teach_me_mode_i_don_t_understand",
    "i_don_t_understand_",
    "single_proof_quest",
]

REQUIRED_LIST_FIELDS = ["requirements", "steps", "success_criteria"]


def _read_json(path: Path) -> Dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _text(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(_text(v) for v in value)
    if isinstance(value, dict):
        return "\n".join(f"{k}: {_text(v)}" for k, v in value.items())
    return str(value or "")


def _as_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    if value in (None, "", {}, []):
        return []
    return [str(value)]


def _norm(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"20\d{6}_\d{6}", " ", text)
    text = re.sub(r"[_\-]+", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _slug(text: str) -> str:
    return (_norm(text).replace(" ", "_")[:90].strip("_") or "quest")


def _quest_text(q: Dict[str, Any]) -> str:
    return _text([
        q.get("title", ""),
        q.get("skill", ""),
        q.get("goal", ""),
        q.get("what_to_build", ""),
        q.get("requirements", []),
        q.get("steps", []),
        q.get("success_criteria", []),
        q.get("proof_required", []),
        q.get("proof", []),
        q.get("verification_patterns", []),
    ])


def _body_signature(q: Dict[str, Any]) -> str:
    body = _norm(_text([
        q.get("skill", ""),
        q.get("what_to_build", ""),
        q.get("requirements", []),
        q.get("steps", []),
        q.get("success_criteria", []),
        q.get("proof_required", []),
        q.get("proof", []),
    ]))
    return hashlib.sha1(body.encode("utf-8")).hexdigest() if body else ""


def _topic_key(q: Dict[str, Any]) -> str:
    title = _norm(str(q.get("title", "")))
    skill = _norm(str(q.get("skill", "")))
    text = title + " " + skill
    if "cpu" in text:
        return "cpu_usage"
    if "active directory" in text or "organizational unit" in text or re.search(r"\bou\b", text):
        return "active_directory_ou"
    if "api" in text or "weather" in text or "route" in text:
        return "api_weather"
    if "sqlite" in text or "crud" in text or "database" in text:
        return "sqlite_crud"
    if "expense" in text or "totaler" in text:
        return "python_expense_totaler"
    if "weather" in text or "api" in text:
        return "api_weather"
    if "test" in text or "smoke" in text:
        return "testing_smoke"
    if "health" in text:
        return "health_monitoring"
    if "card" in text or "html" in text or "css" in text:
        return "html_css"
    return skill or title[:50] or "unknown"


def _status_active(q: Dict[str, Any]) -> bool:
    status = str(q.get("status", "Assigned")).lower()
    return status not in {"archived", "superseded", "rejected", "completed"}


def _quest_records(kdt: Any) -> List[Tuple[Path, Dict[str, Any]]]:
    rows = []
    for path in sorted(Path(kdt.QUEST_DIR).glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        q = _read_json(path)
        if not q:
            continue
        q["filename"] = path.name
        if _status_active(q) or q.get("archived_at") or q.get("superseded_by"):
            rows.append((path, q))
    return rows


def _generic_hits(q: Dict[str, Any]) -> List[str]:
    text = _quest_text(q).lower()
    return [m for m in GENERIC_MARKERS if m in text]


def _has_understanding_check(q: Dict[str, Any]) -> bool:
    text = _quest_text(q).lower()
    return any(w in text for w in ["answer:", "explain", "why", "what does", "what did", "in your own words", "understand"])


def _has_proof(q: Dict[str, Any]) -> bool:
    text = _text([q.get("proof_required", []), q.get("proof", []), q.get("success_criteria", [])]).lower()
    return any(w in text for w in ["upload", "screenshot", "zip", "readme", "proof", "terminal", "answer:"])


def _has_specific_files(q: Dict[str, Any]) -> bool:
    text = _quest_text(q).lower()
    return bool(re.search(r"\b(index\.html|style\.css|script\.js|app\.py|readme\.md|\.py|\.json|\.db|\.txt|screenshot|task manager|aduc|pytest)\b", text))


def _missing_fields(q: Dict[str, Any]) -> List[str]:
    missing = []
    for field in ["title", "skill", "what_to_build"]:
        if q.get(field) in (None, "", [], {}):
            missing.append(field)
    for field in REQUIRED_LIST_FIELDS:
        if not _as_list(q.get(field)):
            missing.append(field)
    if not (q.get("proof_required") or q.get("proof")):
        missing.append("proof_required")
    if not isinstance(q.get("quest_quality"), dict):
        missing.append("quest_quality")
    if not isinstance(q.get("governance"), dict) and not isinstance(q.get("governance_v24"), dict) and not isinstance(q.get("governance_v25"), dict):
        missing.append("governance")
    return missing


def _quest_age_label(path: Path) -> str:
    try:
        age_days = (datetime.now().timestamp() - path.stat().st_mtime) / 86400
    except Exception:
        age_days = 0
    if age_days < 2:
        return "new"
    if age_days < 14:
        return "recent"
    return "old"


def _score_quest(path: Path, q: Dict[str, Any], duplicate_body: List[str], duplicate_topic: List[str]) -> Dict[str, Any]:
    score = 100
    penalties: List[Dict[str, Any]] = []
    strengths: List[str] = []
    filename = path.name
    title_norm = _norm(q.get("title", ""))
    file_norm = _norm(filename)

    def penalty(points: int, category: str, reason: str, action: str):
        nonlocal score
        score -= points
        penalties.append({"points": points, "category": category, "reason": reason, "action": action})

    missing = _missing_fields(q)
    structural = [m for m in missing if m not in {"quest_quality", "governance"}]
    metadata = [m for m in missing if m in {"quest_quality", "governance"}]
    if structural:
        penalty(14 * len(structural), "Missing Structure", "Missing required quest structure: " + ", ".join(structural), "regenerate")
    if metadata:
        penalty(4 * len(metadata), "Missing Metadata", "Missing governance metadata: " + ", ".join(metadata), "repair_metadata")

    generic = _generic_hits(q)
    strong_specific = _has_specific_files(q) and len(_as_list(q.get("steps"))) >= 5 and _has_proof(q)
    if generic:
        # Generic language is a warning by itself, not an automatic high-risk failure.
        points = 5 * min(len(generic), 3)
        if not strong_specific:
            points += 15
        penalty(points, "Generic Language", "Generic wording found: " + ", ".join(generic[:3]), "rewrite_or_regenerate")

    if duplicate_body:
        penalty(45, "Duplicate Body", "Same or nearly identical body as: " + ", ".join(duplicate_body[:4]), "dedupe")
    elif duplicate_topic:
        # Similar topic is not always bad. Penalize old Teach Me / I don't understand duplicates harder.
        is_legacy = any(m in file_norm for m in LEGACY_TITLE_MARKERS) or any(m.replace("_", " ") in title_norm for m in LEGACY_TITLE_MARKERS)
        if is_legacy:
            penalty(28, "Duplicate Topic", "Older learning quest overlaps with stronger quest(s): " + ", ".join(duplicate_topic[:4]), "archive_if_weaker")
        else:
            penalty(8, "Similar Topic", "Shares a topic cluster with other active quest(s): " + ", ".join(duplicate_topic[:4]), "review_cluster")

    if len(_as_list(q.get("steps"))) < 5:
        penalty(15, "Weak Steps", "Quest has fewer than 5 step-by-step instructions.", "regenerate")
    if len(_as_list(q.get("success_criteria"))) < 3:
        penalty(12, "Weak Success Criteria", "Quest has fewer than 3 success criteria.", "regenerate")
    if not _has_proof(q):
        penalty(20, "Missing Proof", "Quest does not clearly require upload/screenshot/README/written proof.", "regenerate")
    if not _has_understanding_check(q):
        penalty(10, "Missing Understanding Check", "Quest does not ask the user to explain what they understood.", "add_understanding_check")

    if q.get("archived_at") or q.get("superseded_by"):
        penalty(40, "Archived Copy", "Archived/superseded quest is still inside active quests.", "move_archived_copy")

    if _has_specific_files(q):
        score += 6
        strengths.append("names exact files or proof artifacts")
    if _has_proof(q):
        score += 6
        strengths.append("requires proof")
    if _has_understanding_check(q):
        score += 4
        strengths.append("checks understanding")
    if len(_as_list(q.get("steps"))) >= 7:
        score += 4
        strengths.append("has detailed steps")

    score = max(0, min(100, int(score)))
    if score >= 90:
        rating = "Excellent"
        risk = "clean"
    elif score >= V25_MIN_SCORE:
        rating = "Strong"
        risk = "clean"
    elif score >= 75:
        rating = "Warning"
        risk = "warning"
    elif score >= 55:
        rating = "Needs Work"
        risk = "medium"
    else:
        rating = "High Risk"
        risk = "high"

    actions = []
    for p in penalties:
        actions.append(p["action"])
    actions = list(dict.fromkeys(actions))

    # Do not call a strong quest broken just because it needs metadata or shares a broad topic.
    lightweight_actions = {"repair_metadata", "review_cluster"}
    content_actions = [a for a in actions if a not in lightweight_actions]
    if score >= V25_MIN_SCORE and not content_actions:
        actions = [a for a in actions if a == "repair_metadata"]

    exact_fix = "No repair needed."
    if actions:
        if "move_archived_copy" in actions:
            exact_fix = "Move this archived/superseded copy out of active quests and keep its history in quest_archive."
        elif "dedupe" in actions or "archive_if_weaker" in actions:
            exact_fix = "Keep the strongest quest in this cluster, archive weaker duplicates with postmortems, then only regenerate if the kept quest is missing proof or exact steps."
        elif "repair_metadata" in actions and len(actions) == 1:
            exact_fix = "Add quest_quality and governance_v25 metadata. Do not regenerate because the quest content is probably usable."
        elif "add_understanding_check" in actions and len(actions) == 1:
            exact_fix = "Add one proof question such as: Explain what this quest proved in your own words."
        else:
            exact_fix = "Regenerate or rewrite this quest with exact files, exact steps, exact proof, success criteria, and an understanding check."

    return {
        "filename": filename,
        "title": q.get("title", "Untitled Quest"),
        "skill": q.get("skill", "Unknown"),
        "score": score,
        "rating": rating,
        "risk": risk,
        "age": _quest_age_label(path),
        "topic_key": _topic_key(q),
        "body_signature": _body_signature(q),
        "actions": actions,
        "penalties": penalties,
        "strengths": strengths,
        "duplicate_body": duplicate_body,
        "duplicate_topic": duplicate_topic,
        "exact_fix": exact_fix,
        "repairable": bool(actions),
        "maintenance_only": bool(actions) and score >= V25_MIN_SCORE and all(a in {"repair_metadata", "review_cluster"} for a in actions),
        "is_issue": (score < V25_MIN_SCORE) or any(a not in {"repair_metadata", "review_cluster"} for a in actions),
    }


def _cluster_recommendations(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in items:
        groups[item["topic_key"]].append(item)
    clusters = []
    for key, group in groups.items():
        if len(group) < 2:
            continue
        sorted_group = sorted(group, key=lambda x: (x["score"], -len(x.get("penalties", []))), reverse=True)
        keep = sorted_group[0]
        archive = [g for g in sorted_group[1:] if g["score"] < keep["score"] or g["risk"] in {"high", "medium"}]
        clusters.append({
            "key": key,
            "title": key.replace("_", " ").title(),
            "count": len(group),
            "keep": keep,
            "archive": archive,
            "all": sorted_group,
            "summary": f"Keep {keep['filename']} unless you intentionally want multiple practice variations. Archive weaker duplicates only.",
        })
    clusters.sort(key=lambda c: (len(c["archive"]), c["count"]), reverse=True)
    return clusters


def governance_intelligence_plan(kdt: Any) -> Dict[str, Any]:
    rows = _quest_records(kdt)
    body_map: Dict[str, List[str]] = defaultdict(list)
    topic_map: Dict[str, List[str]] = defaultdict(list)
    for path, q in rows:
        sig = _body_signature(q)
        if sig:
            body_map[sig].append(path.name)
        topic_map[_topic_key(q)].append(path.name)

    scored = []
    for path, q in rows:
        sig = _body_signature(q)
        topic = _topic_key(q)
        duplicate_body = [f for f in body_map.get(sig, []) if f != path.name]
        duplicate_topic = [f for f in topic_map.get(topic, []) if f != path.name]
        scored.append(_score_quest(path, q, duplicate_body, duplicate_topic))

    issues = [i for i in scored if i["is_issue"]]
    issues.sort(key=lambda x: (x["score"], x["risk"]), reverse=False)
    maintenance = [i for i in scored if i.get("maintenance_only")]
    clean = [i for i in scored if not i["is_issue"]]
    high = [i for i in issues if i["risk"] == "high"]
    medium = [i for i in issues if i["risk"] == "medium"]
    warning = [i for i in issues if i["risk"] == "warning"]
    clusters = _cluster_recommendations(scored)

    categories: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in issues:
        if not item.get("penalties"):
            categories["Other"].append(item)
        else:
            for p in item["penalties"]:
                categories[p["category"]].append(item)
    category_rows = []
    for name, values in categories.items():
        # Deduplicate per category by filename.
        seen = set(); unique = []
        for v in values:
            if v["filename"] not in seen:
                unique.append(v); seen.add(v["filename"])
        category_rows.append({"name": name, "count": len(unique), "items": unique})
    category_rows.sort(key=lambda c: c["count"], reverse=True)

    average = int(sum(i["score"] for i in scored) / len(scored)) if scored else 100
    return {
        "version": "V25",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "total_active_quests": len(scored),
        "issues": len(issues),
        "clean_count": len(clean),
        "maintenance_count": len(maintenance),
        "high_risk": len(high),
        "medium_risk": len(medium),
        "warning_count": len(warning),
        "average_score": average,
        "score_label": "Excellent" if average >= 90 else "Strong" if average >= 85 else "Needs polish" if average >= 70 else "Needs repair",
        "items": issues,
        "all_items": scored,
        "clean_items": sorted(clean, key=lambda x: x["score"], reverse=True),
        "maintenance_items": sorted(maintenance, key=lambda x: x["score"], reverse=True),
        "clusters": clusters,
        "categories": category_rows,
        "ready_to_run": bool(issues),
        "scanner_note": "V25 uses weighted scoring, duplicate clustering, and safer repair actions to reduce false positives.",
    }


def _archive_with_postmortem(kdt: Any, filename: str, reason: str) -> str:
    src = Path(kdt.QUEST_DIR) / filename
    q = _read_json(src)
    if not q:
        return ""
    archive_dir = Path(kdt.QUEST_ARCHIVE_DIR); archive_dir.mkdir(exist_ok=True)
    post_dir = Path(kdt.QUEST_POSTMORTEM_DIR); post_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"{src.stem}_{stamp}_v25_archived.json"
    q["status"] = "Archived"
    q["archived_at"] = datetime.now().isoformat(timespec="seconds")
    q["archive_reason"] = reason
    _write_json(archive_dir / archive_name, q)
    postmortem = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "quest": filename,
        "archive_file": archive_name,
        "reason": reason,
        "lesson": "V25 archived this quest to reduce duplicate or weak active learning data.",
    }
    _write_json(post_dir / f"{src.stem}_{stamp}_v25_postmortem.json", postmortem)
    src.unlink(missing_ok=True)
    return archive_name


def _repair_metadata(kdt: Any, item: Dict[str, Any]) -> bool:
    path = Path(kdt.QUEST_DIR) / item["filename"]
    q = _read_json(path)
    if not q:
        return False
    now = datetime.now().isoformat(timespec="seconds")
    q["quest_quality"] = {
        "score": item["score"],
        "rating": item["rating"],
        "checked_at": now,
        "checked_by": "KDT OS Governance Intelligence V25",
        "note": "Weighted score based on structure, proof, understanding check, duplicates, and specificity.",
    }
    q["governance_v25"] = {
        "score": item["score"],
        "rating": item["rating"],
        "risk": item["risk"],
        "actions": item.get("actions", []),
        "penalties": item.get("penalties", []),
        "strengths": item.get("strengths", []),
        "checked_at": now,
    }
    if not (q.get("proof_required") or q.get("proof")):
        q["proof_required"] = ["Upload proof that matches the quest.", "Write one sentence explaining what the quest proved."]
    if not _has_understanding_check(q):
        existing = _as_list(q.get("proof_required") or q.get("proof"))
        existing.append("Answer: what did this quest prove in your own words?")
        q["proof_required"] = existing
    _write_json(path, q)
    return True


def _cluster_archive_targets(plan: Dict[str, Any]) -> List[Dict[str, str]]:
    targets = []
    for cluster in plan.get("clusters", []):
        for item in cluster.get("archive", []):
            if item.get("risk") in {"high", "medium"} or item.get("score", 100) < 75:
                targets.append({"filename": item["filename"], "reason": f"Weaker duplicate in {cluster['title']} cluster. Kept {cluster['keep']['filename']}."})
    # Deduplicate targets.
    seen = set(); unique = []
    for t in targets:
        if t["filename"] not in seen:
            unique.append(t); seen.add(t["filename"])
    return unique


def run_governance_intelligence(kdt: Any, dry_run: bool = False, mode: str = "safe") -> Dict[str, Any]:
    plan = governance_intelligence_plan(kdt)
    result = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "version": "V25",
        "dry_run": dry_run,
        "mode": mode,
        "planned": plan,
        "actions_taken": [],
        "rescored": [],
        "archived": [],
        "regenerated": [],
        "skipped": [],
        "errors": [],
    }
    if dry_run:
        result["planned_archive_targets"] = _cluster_archive_targets(plan)
        result["planned_metadata_repairs"] = [i["filename"] for i in (plan.get("items", []) + plan.get("maintenance_items", [])) if "repair_metadata" in i.get("actions", []) or "add_understanding_check" in i.get("actions", [])]
        return result

    # 1) Always safe: repair metadata / understanding check without changing the quest purpose.
    for item in (plan.get("items", []) + plan.get("maintenance_items", [])):
        try:
            actions = item.get("actions", [])
            if "repair_metadata" in actions or "add_understanding_check" in actions or item.get("score", 0) >= 75:
                if _repair_metadata(kdt, item):
                    result["rescored"].append(item["filename"])
                    result["actions_taken"].append({"file": item["filename"], "action": "metadata_repaired"})
        except Exception as exc:
            result["errors"].append({"file": item.get("filename"), "error": str(exc)})

    # 2) Safe duplicate cleanup: archive weaker duplicates only.
    for target in _cluster_archive_targets(plan):
        try:
            archived = _archive_with_postmortem(kdt, target["filename"], target["reason"])
            if archived:
                result["archived"].append(archived)
                result["actions_taken"].append({"file": target["filename"], "action": "archived_weaker_duplicate", "archive": archived})
        except Exception as exc:
            result["errors"].append({"file": target["filename"], "error": str(exc)})

    # 3) Only regenerate high-risk non-duplicates if the existing app exposes a regeneration function.
    for item in plan.get("items", []):
        if item["filename"] in {t["filename"] for t in _cluster_archive_targets(plan)}:
            continue
        if item.get("risk") != "high" or "rewrite_or_regenerate" not in item.get("actions", []):
            continue
        if not hasattr(kdt, "regenerate_quest"):
            result["skipped"].append({"file": item["filename"], "reason": "No regenerate_quest function available."})
            continue
        try:
            newfile, _newq = kdt.regenerate_quest(item["filename"])
            if newfile:
                result["regenerated"].append(newfile)
                result["actions_taken"].append({"file": item["filename"], "action": "regenerated_high_risk", "replacement": newfile})
        except Exception as exc:
            result["errors"].append({"file": item["filename"], "error": str(exc)})

    try:
        report_dir = Path(kdt.REPORT_DIR); report_dir.mkdir(exist_ok=True)
        log_name = f"v25_governance_intelligence_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        _write_json(report_dir / log_name, result)
        result["log_file"] = log_name
    except Exception as exc:
        result["errors"].append({"file": "reports", "error": str(exc)})
    return result


def _status(score: int) -> str:
    if score >= 95:
        return "10/10"
    if score >= 85:
        return "Strong"
    if score >= 70:
        return "Needs polish"
    return "Needs repair"


def audit_quest_governance_v25(kdt: Any) -> Dict[str, Any]:
    plan = governance_intelligence_plan(kdt)
    issues = []
    for item in plan["items"]:
        if item["risk"] == "warning":
            sev = "Low"
        elif item["risk"] == "medium":
            sev = "Medium"
        else:
            sev = "High"
        reasons = [p["reason"] for p in item.get("penalties", [])] or [item.get("exact_fix", "Review quest.")]
        issues.append({
            "severity": sev,
            "file": "quests\\" + item["filename"],
            "line": 1,
            "problem": f"{item['title']} scored {item['score']}% ({item['rating']}). " + "; ".join(reasons[:3]),
            "exact_fix": item["exact_fix"],
        })
    score = max(0, min(100, plan["average_score"] - plan["high_risk"] * 2 - plan["medium_risk"]))
    return {
        "name": "Quest Governance",
        "score": score,
        "status": _status(score),
        "summary": f"V25 weighted scanner checked {plan['total_active_quests']} active quest files. Average governance score: {plan['average_score']}%. Issues are grouped by real risk to reduce false positives.",
        "issues": issues,
    }


def run_self_check_v25(kdt: Any) -> Dict[str, Any]:
    if v24 and hasattr(v24, "run_self_check_v24"):
        check = v24.run_self_check_v24(kdt)
    elif hasattr(kdt, "run_self_check_v24"):
        check = kdt.run_self_check_v24()
    else:
        check = {"audits": [], "score": 0, "status": "Needs repair", "critical_issues": 0, "next_fix": None}

    audits = check.get("audits", [])
    replaced = False
    new_audits = []
    for audit in audits:
        if audit.get("name") == "Quest Governance":
            new_audits.append(audit_quest_governance_v25(kdt))
            replaced = True
        else:
            new_audits.append(audit)
    if not replaced:
        new_audits.append(audit_quest_governance_v25(kdt))
    score = int(sum(a.get("score", 0) for a in new_audits) / len(new_audits)) if new_audits else 0
    all_issues = [i for a in new_audits for i in a.get("issues", [])]
    weights = {"High": 3, "Medium": 2, "Low": 1}
    all_issues.sort(key=lambda i: weights.get(i.get("severity"), 0), reverse=True)
    return {
        "version": "V25",
        "score": score,
        "status": _status(score),
        "critical_issues": sum(1 for i in all_issues if i.get("severity") == "High"),
        "audits": new_audits,
        "next_fix": all_issues[0] if all_issues else None,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def install(kdt: Any) -> Any:
    app = getattr(kdt, "app", None)
    if app is None:
        return kdt

    def self_check():
        return kdt.render_template("self_check.html", check=run_self_check_v25(kdt))

    def self_check_json():
        return kdt.jsonify(run_self_check_v25(kdt))

    def auto_governance():
        plan = governance_intelligence_plan(kdt)
        return kdt.render_template("auto_governance.html", plan=plan, result=None)

    def auto_governance_run():
        dry_run = str(kdt.request.form.get("dry_run", "")).lower() in {"1", "true", "yes", "on"}
        mode = str(kdt.request.form.get("mode", "safe"))
        result = run_governance_intelligence(kdt, dry_run=dry_run, mode=mode)
        plan = governance_intelligence_plan(kdt)
        return kdt.render_template("auto_governance.html", plan=plan, result=result)

    def auto_governance_json():
        return kdt.jsonify(governance_intelligence_plan(kdt))

    if "self_check" in app.view_functions:
        app.view_functions["self_check"] = self_check
    else:
        app.add_url_rule("/self_check", "self_check", self_check)
    if "self_check_json" in app.view_functions:
        app.view_functions["self_check_json"] = self_check_json
    else:
        app.add_url_rule("/self_check.json", "self_check_json", self_check_json)
    if "auto_governance" in app.view_functions:
        app.view_functions["auto_governance"] = auto_governance
    else:
        app.add_url_rule("/auto_governance", "auto_governance", auto_governance)
    if "auto_governance_run" in app.view_functions:
        app.view_functions["auto_governance_run"] = auto_governance_run
    else:
        app.add_url_rule("/auto_governance/run", "auto_governance_run", auto_governance_run, methods=["POST"])
    if "auto_governance_json" in app.view_functions:
        app.view_functions["auto_governance_json"] = auto_governance_json
    else:
        app.add_url_rule("/auto_governance.json", "auto_governance_json", auto_governance_json)

    kdt.governance_intelligence_plan_v25 = lambda: governance_intelligence_plan(kdt)
    kdt.run_governance_intelligence_v25 = lambda dry_run=False, mode="safe": run_governance_intelligence(kdt, dry_run=dry_run, mode=mode)
    kdt.run_self_check_v25 = lambda: run_self_check_v25(kdt)
    return kdt
