"""KDT OS Unified Governance V24

One shared governance brain for Self Check and Auto Governance.

V24 fixes the V23 mismatch where Self Check could see weak/duplicate quests
but Auto Governance reported 0 issues. Both pages now use the same active
quest scanner and the same exact repair plan.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


GENERIC_MARKERS = [
    "one artifact that proves",
    "small project that demonstrates",
    "small project that demonstrates the requested skill",
    "demonstrates the requested skill",
    "requested skill one time",
    "create original files",
    "create a project folder",
    "create the main file",
    "implement the smallest working version",
    "test it",
    "upload zip",
    "run/open/show the artifact",
    "what i did, what worked, what confused me",
]

REQUIRED_FIELDS = [
    "title",
    "skill",
    "what_to_build",
    "requirements",
    "steps",
    "success_criteria",
    "proof_required",
]

V24_MIN_SCORE = 85


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(errors="ignore")
    except Exception:
        return ""


def _read_json(path: Path) -> Dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _as_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    if value is None:
        return []
    return [str(value)]


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
        q.get("goal", ""),
        q.get("what_to_build", ""),
        q.get("requirements", []),
        q.get("steps", []),
        q.get("success_criteria", []),
        q.get("proof_required", []),
        q.get("verification_patterns", []),
    ]
    return _as_text(fields)


def _norm(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"20\d{6}_\d{6}", " ", text)
    text = re.sub(r"[_\-]+", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _body_signature(q: Dict[str, Any]) -> str:
    # Exclude title and filename so same instructions under different names are caught.
    text = _as_text([
        q.get("skill", ""),
        q.get("what_to_build", ""),
        q.get("requirements", []),
        q.get("steps", []),
        q.get("success_criteria", []),
        q.get("proof_required", []),
    ])
    text = _norm(text)
    return hashlib.sha1(text.encode("utf-8")).hexdigest() if text else ""


def _status_active(q: Dict[str, Any]) -> bool:
    status = str(q.get("status", "Assigned")).lower()
    return status not in {"archived", "superseded", "rejected", "completed"}


def _is_legacy_archived_copy(q: Dict[str, Any]) -> bool:
    # Some old archived quests are still physically sitting in quests/.
    return bool(q.get("archived_at") or q.get("archive_reason") or q.get("superseded_by"))


def _generic_hits(q: Dict[str, Any]) -> List[str]:
    text = _quest_text(q).lower()
    return [m for m in GENERIC_MARKERS if m in text]


def _missing_metadata(q: Dict[str, Any]) -> List[str]:
    missing = []
    for field in REQUIRED_FIELDS:
        value = q.get(field)
        if value in (None, "", [], {}):
            missing.append(field)
    if not isinstance(q.get("quest_quality"), dict):
        missing.append("quest_quality")
    if not isinstance(q.get("governance"), dict) and not isinstance(q.get("governance_v24"), dict):
        missing.append("governance")
    return missing


def _basic_quality_score(q: Dict[str, Any]) -> int:
    score = 100
    missing = _missing_metadata(q)
    for field in missing:
        if field in {"quest_quality", "governance"}:
            score -= 5
        else:
            score -= 12
    score -= 15 * len(_generic_hits(q))
    if len(_as_list(q.get("steps"))) < 5:
        score -= 12
    if len(_as_list(q.get("success_criteria"))) < 3:
        score -= 10
    if len(_as_list(q.get("proof_required"))) < 2:
        score -= 10
    if _is_legacy_archived_copy(q):
        score -= 30
    return max(0, min(100, score))


def _risk_for(reasons: List[str], score: int) -> str:
    text = " ".join(reasons).lower()
    if "duplicate" in text or "generic" in text or "legacy archived" in text:
        return "high"
    if score < V24_MIN_SCORE:
        return "high"
    if reasons:
        return "medium"
    return "low"


def _exact_fix(actions: List[str], filename: str) -> str:
    if "move_archived_copy" in actions:
        return f"Move {filename} out of active quests and into quest_archive because it already has archive/superseded metadata."
    if "dedupe" in actions and "regenerate" in actions:
        return f"Archive the duplicate weak active quest {filename}, create a postmortem, then generate a specific replacement from its actual skill gap."
    if "regenerate" in actions:
        return f"Archive {filename}, create a postmortem explaining why it was weak, then generate a replacement with exact files, exact steps, exact proof, and an understanding check."
    if "rescore" in actions:
        return f"Add quest_quality and governance_v24 metadata to {filename} so future systems can trust or reject it consistently."
    return f"Review {filename} manually."


def _quest_records(kdt: Any, folder: Path | None = None) -> List[Tuple[Path, Dict[str, Any]]]:
    folder = folder or kdt.QUEST_DIR
    rows = []
    for path in sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        q = _read_json(path)
        if not q:
            continue
        q["filename"] = path.name
        rows.append((path, q))
    return rows


def unified_quest_governance_plan(kdt: Any, include_archive_summary: bool = True) -> Dict[str, Any]:
    rows = [(p, q) for p, q in _quest_records(kdt, kdt.QUEST_DIR) if _status_active(q) or _is_legacy_archived_copy(q)]
    signatures: Dict[str, List[str]] = defaultdict(list)
    for path, q in rows:
        sig = _body_signature(q)
        if sig:
            signatures[sig].append(path.name)

    items: List[Dict[str, Any]] = []
    for path, q in rows:
        filename = path.name
        score = _basic_quality_score(q)
        generic = _generic_hits(q)
        missing = _missing_metadata(q)
        sig = _body_signature(q)
        dupes = [f for f in signatures.get(sig, []) if f != filename]

        reasons: List[str] = []
        actions: List[str] = []

        if _is_legacy_archived_copy(q):
            reasons.append("Legacy archived/superseded quest is still inside the active quests folder.")
            actions.append("move_archived_copy")

        if generic:
            reasons.append("Quest still contains generic template language: " + ", ".join(generic[:4]))
            actions.append("regenerate")

        if dupes:
            reasons.append("Possible duplicate quest body detected across active quests: " + ", ".join(dupes[:3]))
            actions.append("dedupe")
            if generic or score < V24_MIN_SCORE:
                actions.append("regenerate")

        # Missing quality/governance is repairable, but generic/duplicates should regenerate instead.
        meaningful_missing = [m for m in missing if m in {"quest_quality", "governance"}]
        structural_missing = [m for m in missing if m not in {"quest_quality", "governance"}]
        if structural_missing:
            reasons.append("Quest is missing required structure: " + ", ".join(structural_missing))
            actions.append("regenerate")
        elif meaningful_missing and not any(a in actions for a in ["regenerate", "dedupe", "move_archived_copy"]):
            reasons.append("Quest is missing governance metadata: " + ", ".join(meaningful_missing))
            actions.append("rescore")

        if score < V24_MIN_SCORE and not any(a in actions for a in ["regenerate", "move_archived_copy"]):
            reasons.append(f"Governance score is below {V24_MIN_SCORE}%: {score}%.")
            actions.append("regenerate")

        actions = list(dict.fromkeys(actions))
        if actions:
            risk = _risk_for(reasons, score)
            items.append({
                "filename": filename,
                "title": q.get("title", "Untitled Quest"),
                "skill": q.get("skill", "Unknown"),
                "score": score,
                "risk": risk,
                "actions": actions,
                "reasons": reasons,
                "dupes": dupes,
                "exact_fix": _exact_fix(actions, filename),
            })

    high = sum(1 for i in items if i["risk"] == "high")
    medium = sum(1 for i in items if i["risk"] == "medium")
    archive_count = 0
    if include_archive_summary:
        archive_dir = getattr(kdt, "QUEST_ARCHIVE_DIR", None)
        if archive_dir:
            archive_count = len(list(Path(archive_dir).glob("*.json")))

    return {
        "version": "V24",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "total_active_quests": len(rows),
        "archive_count": archive_count,
        "issues": len(items),
        "high_risk": high,
        "medium_risk": medium,
        "ready_to_run": len(items) > 0,
        "items": items,
        "scanner_note": "Self Check and Auto Governance use this same V24 scanner."
    }


def _slugify(text: str) -> str:
    text = _norm(text)
    text = text.replace(" ", "_")
    return text[:80].strip("_") or "quest"


def _specific_replacement(q: Dict[str, Any]) -> Dict[str, Any]:
    skill = str(q.get("skill") or q.get("title") or "General Practice")
    skill_l = skill.lower()
    title_l = str(q.get("title", "")).lower()
    now = datetime.now().isoformat(timespec="seconds")

    def base(title, what, req, steps, success, proof, patterns=None):
        return {
            "created_at": now,
            "source_project": q.get("source_project", "KDT OS"),
            "origin_report": q.get("origin_report", ""),
            "resume_project": q.get("resume_project", q.get("source_project", "KDT OS")),
            "connected_goal": q.get("connected_goal", "Become a developer who can build anything"),
            "skill": skill,
            "quest_type": "Auto Governance Replacement Quest",
            "difficulty": "Beginner",
            "estimated_time": "20-45 minutes",
            "status": "Assigned",
            "title": title,
            "goal": f"Replace a weak legacy quest with a specific proof-backed quest for {skill}.",
            "what_to_build": what,
            "requirements": req,
            "steps": steps,
            "success_criteria": success,
            "proof_required": proof,
            "verification_patterns": patterns or [],
            "why_this_exists": "V24 Auto Governance archived a weak, duplicated, or generic quest and created a stronger replacement.",
            "resume_rule": "Complete this quest, submit proof, then return to KDT OS mastery or the related project.",
            "regenerated_from": q.get("filename"),
            "version": "v24",
            "submissions": [],
        }

    if "cpu" in skill_l or "cpu" in title_l:
        return base(
            "CPU Usage Task Manager Proof Quest",
            "A screenshot-and-notes proof showing Task Manager CPU usage, the top CPU process, and a short explanation of what the percentage means.",
            ["Open Task Manager", "Open the Performance tab", "Open the Processes tab", "Identify current CPU percentage", "Identify the top CPU process", "Write a short explanation in README.md"],
            ["Press Ctrl + Shift + Esc", "Click Performance", "Write down the CPU percentage", "Click Processes", "Sort by CPU", "Write the top process name", "Create folder cpu_usage_proof", "Create README.md", "Add CPU percent, top process, and explanation", "Take or save a screenshot if possible", "Zip the folder"],
            ["README.md includes CPU percentage", "README.md names the top CPU process", "Explanation says CPU usage means how much processor work is being used", "Proof is uploaded"],
            ["Upload cpu_usage_proof ZIP or screenshot", "Answer: what does CPU usage percentage represent?"],
            [r"CPU", r"Task Manager", r"percentage|percent|%"],
        )

    if "active directory" in skill_l or "ou" in skill_l or "active directory" in title_l:
        return base(
            "Active Directory OU Proof Quest",
            "A screenshot-and-notes proof showing one OU concept: what an OU is, where it appears, and how a user/computer would be organized into it.",
            ["Create folder ad_ou_proof", "Create README.md", "Define OU in your own words", "Identify one example OU name", "Explain what object belongs inside it", "Include a screenshot or diagram if available"],
            ["Create folder ad_ou_proof", "Create README.md", "Write: An OU is...", "Write one example OU name such as Sales, Workstations, or Servers", "Write what object would go inside it", "If you have ADUC available, take a screenshot of the OU area", "If not, draw a simple text diagram", "Write one sentence explaining why OUs help administrators", "Zip the folder"],
            ["README.md defines OU", "Example OU is named", "A user/computer/group placement is explained", "Screenshot or diagram is included"],
            ["Upload ad_ou_proof ZIP", "Answer: why would an admin put users or computers into an OU?"],
            [r"OU|Organizational Unit", r"Sales|Workstations|Servers|Users"],
        )

    if "sqlite" in skill_l:
        return base(
            "SQLite CRUD Proof Quest",
            "A small Python SQLite app with create, read, update, and delete actions for workout records.",
            ["Create app.py", "Use sqlite3", "Create workouts table", "Add INSERT", "Add SELECT", "Add UPDATE", "Add DELETE", "Create README.md"],
            ["Create folder sqlite_crud_proof", "Create app.py", "Import sqlite3", "Connect to workouts.db", "Create workouts table", "Write add_workout()", "Write list_workouts()", "Write update_workout()", "Write delete_workout()", "Run each function once", "Create README.md with run steps"],
            ["CREATE TABLE exists", "INSERT INTO exists", "SELECT exists", "UPDATE exists", "DELETE exists", "README explains how to run it"],
            ["Upload sqlite_crud_proof ZIP", "Include app.py, README.md, and workouts.db if created"],
            [r"sqlite3", r"CREATE TABLE", r"INSERT INTO", r"SELECT", r"UPDATE", r"DELETE"],
        )

    if "python" in skill_l and "expense" in title_l:
        return base(
            "Python Function Practice: Expense Totaler",
            "A command-line Python app that stores three expenses in a list and prints the total cost.",
            ["Create app.py", "Create expenses list", "Create total_expenses function", "Use sum()", "Print total", "Create README.md"],
            ["Create folder expense_totaler", "Create app.py", "Create expenses = [12.50, 8.25, 20.00]", "Create function total_expenses(items)", "Return sum(items)", "Print the total", "Run python app.py", "Create README.md with expected output"],
            ["app.py exists", "A function exists", "sum() is used", "Terminal output shows total", "README explains expected output"],
            ["Upload expense_totaler ZIP", "Answer: what does the function return?"],
            [r"def\s+total", r"sum\(", r"print\("],
        )

    if "testing" in skill_l:
        return base(
            "Flask Route Smoke Test Suite",
            "A tiny pytest smoke test that proves the Flask app imports and one route responds.",
            ["Create tests folder", "Create test_smoke.py", "Import app", "Use test_client", "Assert status code is 200 or 302", "Document test command"],
            ["Create tests folder", "Create tests/test_smoke.py", "Import your Flask app", "Create client = app.test_client()", "Call client.get('/')", "Assert response.status_code in (200, 302)", "Run python -m pytest", "Add test command to README.md"],
            ["tests/test_smoke.py exists", "pytest or unittest is used", "test_client is used", "An assert checks status code", "README includes test command"],
            ["Upload updated ZIP", "Include tests/test_smoke.py", "Include terminal output or screenshot"],
            [r"def test_", r"test_client", r"assert", r"pytest"],
        )

    if "html" in skill_l or "css" in skill_l:
        return base(
            "Responsive Card Layout",
            "A browser page with three cards that stack on small screens and sit side-by-side on wider screens.",
            ["Create index.html", "Create style.css", "Add three cards", "Use CSS grid or flexbox", "Add media query", "Create README.md"],
            ["Create folder responsive_cards", "Create index.html", "Create style.css", "Link CSS", "Add a main section", "Add three card divs", "Use grid or flexbox", "Add @media rule for small screens", "Open in browser", "Resize the browser to test"],
            ["Three cards appear", "Grid or flexbox is used", "Media query exists", "Layout changes on smaller screen"],
            ["Upload responsive_cards ZIP", "Include screenshot if possible"],
            [r"display:\s*(grid|flex)", r"@media", r"<div"],
        )

    if "api" in skill_l or "javascript" in skill_l:
        return base(
            "API Weather Lookup App",
            "A browser app with index.html, style.css, and script.js where a button fetches sample weather JSON and displays city, temperature, and condition.",
            ["Create index.html", "Create style.css", "Create script.js", "Add button", "Use fetch()", "Use response.json()", "Update result text", "Handle error"],
            ["Create folder api_weather_lookup", "Create index.html/style.css/script.js", "Add input id cityInput", "Add button id searchBtn", "Add div id result", "In script.js select elements", "Add click listener", "Call fetch using sample JSON or public endpoint", "Use response.json()", "Display result.textContent", "Add catch error message"],
            ["fetch() exists", "addEventListener exists", "json() exists", "DOM text updates", "Error handling exists"],
            ["Upload api_weather_lookup ZIP", "Include README explaining API/sample JSON"],
            [r"fetch\(", r"addEventListener", r"\.json\(\)", r"textContent|innerText|innerHTML"],
        )

    if "health" in skill_l:
        return base(
            "Mini Health Checker",
            "A Python command-line app that checks three fake health values and prints OK/WARNING for each.",
            ["Create app.py", "Create health values", "Use if/else checks", "Print OK/WARNING", "Create README.md"],
            ["Create folder mini_health_checker", "Create app.py", "Set cpu_usage = 85", "Set disk_free = 12", "Set memory_usage = 60", "Write if/else checks", "Print WARNING for bad values and OK for good values", "Run python app.py", "Create README.md explaining thresholds"],
            ["app.py exists", "At least three checks exist", "OK appears", "WARNING appears", "README explains thresholds"],
            ["Upload mini_health_checker ZIP", "Include screenshot or copied terminal output"],
            [r"if ", r"WARNING", r"OK", r"cpu|disk|memory"],
        )

    return base(
        f"{skill} Specific Proof Quest",
        f"A small proof folder for {skill} with README.md and one specific artifact that proves the exact concept, not a generic upload.",
        ["Create a named project folder", "Create README.md", "Name the exact concept", "Create one specific artifact", "Write what the artifact proves", "Upload proof"],
        ["Create a folder named " + _slugify(skill) + "_proof", "Create README.md", "Write the exact skill/concept", "Create one small artifact related to that concept", "Open or run the artifact", "Write what worked", "Write what still confuses you", "Zip the folder"],
        ["README.md exists", "Artifact is specific", "Proof explains what was learned"],
        ["Upload ZIP or screenshot", "Answer: what did this prove?"],
        [],
    )


def _archive_with_postmortem(kdt: Any, path: Path, q: Dict[str, Any], reason: str) -> str:
    archive_dir = Path(kdt.QUEST_ARCHIVE_DIR)
    post_dir = Path(kdt.QUEST_POSTMORTEM_DIR)
    archive_dir.mkdir(exist_ok=True)
    post_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = path.stem + f"_v24_archived_{stamp}.json"
    archive_path = archive_dir / archive_name
    q = dict(q)
    q["status"] = "Archived"
    q["archived_at"] = datetime.now().isoformat(timespec="seconds")
    q["archive_reason"] = reason
    _write_json(archive_path, q)
    post = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "original_file": path.name,
        "archive_file": archive_name,
        "reason": reason,
        "lesson": "Weak, duplicate, or generic quests should not remain active because they corrupt mastery data.",
        "replacement_rule": "Replacement must name exact files, exact steps, exact success criteria, and exact proof.",
    }
    _write_json(post_dir / (path.stem + f"_v24_postmortem_{stamp}.json"), post)
    try:
        path.unlink()
    except Exception:
        pass
    return archive_name


def _save_replacement(kdt: Any, original: Dict[str, Any]) -> str:
    q = _specific_replacement(original)
    if hasattr(kdt, "quest_quality_check"):
        try:
            q["quest_quality"] = kdt.quest_quality_check(q)
        except Exception:
            pass
    q["governance_v24"] = {
        "score": _basic_quality_score(q),
        "rating": "approved" if _basic_quality_score(q) >= V24_MIN_SCORE else "needs review",
        "minimum_score": V24_MIN_SCORE,
        "checked_at": datetime.now().isoformat(timespec="seconds"),
    }
    filename = f"{_slugify(q.get('title','quest'))}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path = Path(kdt.QUEST_DIR) / filename
    _write_json(path, q)
    return filename


def run_unified_auto_governance(kdt: Any, dry_run: bool = False) -> Dict[str, Any]:
    plan = unified_quest_governance_plan(kdt)
    result = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "dry_run": dry_run,
        "planned": plan,
        "actions_taken": [],
        "created_files": [],
        "rescored": [],
        "archived": [],
        "skipped": [],
        "errors": [],
    }
    if dry_run:
        return result

    processed: set[str] = set()
    for item in plan["items"]:
        filename = item["filename"]
        if filename in processed:
            continue
        path = Path(kdt.QUEST_DIR) / filename
        q = _read_json(path)
        if not q:
            result["skipped"].append({"file": filename, "reason": "file not found or invalid JSON"})
            processed.add(filename)
            continue
        try:
            actions = item.get("actions", [])
            if "move_archived_copy" in actions and not any(a in actions for a in ["regenerate", "dedupe"]):
                archived = _archive_with_postmortem(kdt, path, q, "Legacy archived/superseded quest was still in active quests folder.")
                result["archived"].append(archived)
                result["actions_taken"].append({"file": filename, "action": "moved_archived_copy", "archive": archived})
            elif any(a in actions for a in ["regenerate", "dedupe"]):
                reason = "; ".join(item.get("reasons", []))
                archived = _archive_with_postmortem(kdt, path, q, reason)
                newfile = _save_replacement(kdt, q)
                result["archived"].append(archived)
                result["created_files"].append(newfile)
                result["actions_taken"].append({"file": filename, "action": "archived_and_replaced", "archive": archived, "replacement": newfile})
            elif "rescore" in actions:
                q["quest_quality"] = q.get("quest_quality") if isinstance(q.get("quest_quality"), dict) else {
                    "score": _basic_quality_score(q),
                    "rating": "rescored by V24",
                    "checked_at": datetime.now().isoformat(timespec="seconds")
                }
                q["governance_v24"] = {
                    "score": _basic_quality_score(q),
                    "rating": "approved" if _basic_quality_score(q) >= V24_MIN_SCORE else "needs review",
                    "minimum_score": V24_MIN_SCORE,
                    "checked_at": datetime.now().isoformat(timespec="seconds"),
                }
                _write_json(path, q)
                result["rescored"].append(filename)
                result["actions_taken"].append({"file": filename, "action": "rescored"})
            processed.add(filename)
        except Exception as exc:
            result["errors"].append({"file": filename, "error": str(exc)})
            processed.add(filename)

    log_name = f"v24_unified_governance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        report_dir = Path(kdt.REPORT_DIR)
        report_dir.mkdir(exist_ok=True)
        _write_json(report_dir / log_name, result)
        result["log_file"] = log_name
    except Exception as exc:
        result["errors"].append({"file": "reports", "error": str(exc)})
    return result


# -----------------------------
# Self Check V24 uses same quest governance plan
# -----------------------------
def _status(score: int) -> str:
    if score >= 95:
        return "10/10"
    if score >= 85:
        return "Strong"
    if score >= 70:
        return "Needs polish"
    return "Needs repair"


def _template_files(root: Path) -> List[Path]:
    return sorted((root / "templates").glob("*.html"))


def _url_for_calls(text: str) -> List[str]:
    return re.findall(r"url_for\(\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]", text)


def _line_number(text: str, needle: str) -> int:
    idx = text.find(needle)
    if idx < 0:
        return 1
    return text[:idx].count("\n") + 1


def audit_routes_v24(kdt: Any, root: Path) -> Dict[str, Any]:
    endpoints = set(getattr(kdt.app, "view_functions", {}).keys()) if getattr(kdt, "app", None) else {"static"}
    endpoints.update({"static", "mastery", "self_check", "self_check_json", "auto_governance", "auto_governance_run", "auto_governance_json"})
    issues = []
    total_calls = 0
    for template in _template_files(root):
        text = _read(template)
        for endpoint in _url_for_calls(text):
            total_calls += 1
            if endpoint not in endpoints:
                issues.append({
                    "severity": "High",
                    "file": str(template.relative_to(root)),
                    "line": _line_number(text, f"url_for('{endpoint}'"),
                    "problem": f"Template calls url_for('{endpoint}') but no matching endpoint was found.",
                    "exact_fix": f"Open {template.relative_to(root)} and replace url_for('{endpoint}') with the real Flask function name, or add a route function named {endpoint}.",
                })
    score = max(0, 100 - len(issues) * 20)
    return {"name": "Route Health", "score": score, "status": _status(score), "summary": f"Checked {total_calls} template route calls against {len(endpoints)} installed endpoints.", "issues": issues}


def audit_templates_v24(root: Path) -> Dict[str, Any]:
    issues = []
    for template in _template_files(root):
        text = _read(template)
        rel = str(template.relative_to(root))
        if "{% include '_nav.html' %}" not in text and template.name not in {"_nav.html"}:
            issues.append({"severity": "Medium", "file": rel, "line": 1, "problem": "Template does not include the shared sidebar navigation.", "exact_fix": "Add {% include '_nav.html' %} right after the opening <main class=\"shell\"> tag."})
        if '<meta name="viewport"' not in text:
            issues.append({"severity": "Low", "file": rel, "line": 2, "problem": "Viewport meta tag is missing, so mobile/tablet scaling may look off.", "exact_fix": "Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"> under the charset meta tag."})
    score = max(0, 100 - len([i for i in issues if i["severity"] == "Medium"]) * 10 - len([i for i in issues if i["severity"] == "Low"]) * 2)
    return {"name": "Template Consistency", "score": score, "status": _status(score), "summary": f"Checked {len(_template_files(root))} templates for shared layout rules.", "issues": issues}


def audit_css_v24(root: Path) -> Dict[str, Any]:
    css = _read(root / "static" / "style.css")
    required = [".shell", ".kdt-sidebar", ".mobile-nav-strip", ".self-check-grid", ".mastery-bar"]
    issues = []
    for token in required:
        if token not in css:
            issues.append({"severity": "High", "file": "static/style.css", "line": 1, "problem": f"Required UI class {token} is missing from CSS.", "exact_fix": f"Add styling for {token} to static/style.css."})
    score = max(0, 100 - len(issues) * 18)
    return {"name": "UI / CSS Health", "score": score, "status": _status(score), "summary": "Checked core layout classes used across the app.", "issues": issues}


def audit_data_v24(root: Path) -> Dict[str, Any]:
    folders = ["quests", "goals", "projects", "paths", "quest_archive", "quest_postmortems"]
    issues = []
    checked = 0
    for folder in folders:
        d = root / folder
        if not d.exists():
            issues.append({"severity": "High", "file": folder, "line": 1, "problem": "Expected data folder is missing.", "exact_fix": f"Create the {folder} folder."})
            continue
        for path in d.glob("*.json"):
            checked += 1
            if _read_json(path) is None:
                issues.append({"severity": "High", "file": str(path.relative_to(root)), "line": 1, "problem": "JSON file cannot be parsed.", "exact_fix": "Open this file, fix invalid JSON syntax, or restore from backup."})
    score = max(0, 100 - len(issues) * 20)
    return {"name": "Data Integrity", "score": score, "status": _status(score), "summary": f"Checked {checked} JSON memory files.", "issues": issues}


def audit_quest_governance_v24(kdt: Any) -> Dict[str, Any]:
    plan = unified_quest_governance_plan(kdt)
    issues = []
    for item in plan["items"]:
        severity = "High" if item["risk"] == "high" else "Medium"
        issues.append({
            "severity": severity,
            "file": "quests\\" + item["filename"],
            "line": 1,
            "problem": "; ".join(item["reasons"]),
            "exact_fix": item["exact_fix"],
        })
    score = max(0, 100 - plan["high_risk"] * 12 - plan["medium_risk"] * 6)
    return {"name": "Quest Governance", "score": score, "status": _status(score), "summary": f"Unified V24 scanner checked {plan['total_active_quests']} active quest files. Auto Governance will see these same {plan['issues']} issue(s).", "issues": issues}


def audit_architecture_v24(root: Path) -> Dict[str, Any]:
    app_py = root / "app.py"
    text = _read(app_py)
    line_count = text.count("\n") + 1 if text else 0
    issues = []
    if line_count > 3000:
        issues.append({"severity": "Medium", "file": "app.py", "line": 1, "problem": f"app.py is very large ({line_count} lines). This increases break risk when adding features.", "exact_fix": "Start moving new systems into installable modules like kdt_quest_intelligence_v20.py, kdt_intelligence_v21.py, kdt_self_check_v22.py, kdt_auto_governance_v23.py, and kdt_unified_governance_v24.py before splitting old routes."})
    score = 90 if issues else 100
    return {"name": "Architecture", "score": score, "status": _status(score), "summary": "Checked core app size and modular intelligence files.", "issues": issues}


def run_self_check_v24(kdt: Any) -> Dict[str, Any]:
    root = Path(getattr(kdt, "APP_ROOT", Path.cwd()))
    audits = [
        audit_routes_v24(kdt, root),
        audit_templates_v24(root),
        audit_css_v24(root),
        audit_data_v24(root),
        audit_quest_governance_v24(kdt),
        audit_architecture_v24(root),
    ]
    score = int(sum(a["score"] for a in audits) / len(audits)) if audits else 0
    all_issues = [i for a in audits for i in a.get("issues", [])]
    severity_weight = {"High": 3, "Medium": 2, "Low": 1}
    all_issues.sort(key=lambda i: severity_weight.get(i.get("severity"), 0), reverse=True)
    critical = sum(1 for i in all_issues if i.get("severity") == "High")
    return {
        "version": "V24",
        "score": score,
        "status": _status(score),
        "critical_issues": critical,
        "audits": audits,
        "next_fix": all_issues[0] if all_issues else None,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def install(kdt: Any) -> Any:
    app = getattr(kdt, "app", None)
    if app is None:
        return kdt

    # Override V22/V23 view functions so pages use the unified V24 logic.
    def self_check():
        return kdt.render_template("self_check.html", check=run_self_check_v24(kdt))

    def self_check_json():
        return kdt.jsonify(run_self_check_v24(kdt))

    def auto_governance():
        plan = unified_quest_governance_plan(kdt)
        return kdt.render_template("auto_governance.html", plan=plan, result=None)

    def auto_governance_run():
        dry_run = str(kdt.request.form.get("dry_run", "")).lower() in {"1", "true", "yes", "on"}
        result = run_unified_auto_governance(kdt, dry_run=dry_run)
        plan = unified_quest_governance_plan(kdt)
        return kdt.render_template("auto_governance.html", plan=plan, result=result)

    def auto_governance_json():
        return kdt.jsonify(unified_quest_governance_plan(kdt))

    # If routes exist from old modules, replacing app.view_functions is enough.
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

    kdt.unified_quest_governance_plan_v24 = lambda: unified_quest_governance_plan(kdt)
    kdt.run_unified_auto_governance_v24 = lambda dry_run=False: run_unified_auto_governance(kdt, dry_run=dry_run)
    kdt.run_self_check_v24 = lambda: run_self_check_v24(kdt)
    return kdt
