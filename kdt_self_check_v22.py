"""KDT OS Self Check V22

Adds a self-diagnostic center that checks the app before you trust it.
It is intentionally read-only: it reports exact problems and exact fixes,
without rewriting project files from inside the running Flask app.
"""
from __future__ import annotations

import ast
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(errors="ignore")
    except Exception:
        return ""


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


def _endpoint_names(app_py: Path) -> set[str]:
    source = _read(app_py)
    endpoints: set[str] = {"static"}
    try:
        tree = ast.parse(source)
    except Exception:
        return endpoints
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            for dec in node.decorator_list:
                try:
                    text = ast.unparse(dec)
                except Exception:
                    text = ""
                if text.startswith("app.route") or ".add_url_rule" in text:
                    endpoints.add(node.name)
    # Routes registered by install modules usually add view_functions directly.
    endpoints.update({"mastery", "system_intelligence", "self_check", "self_check_json"})
    return endpoints


def _url_for_calls(text: str) -> List[str]:
    # Handles url_for('endpoint') and url_for("endpoint").
    return re.findall(r"url_for\(\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]", text)


def _line_number(text: str, needle: str) -> int:
    idx = text.find(needle)
    if idx < 0:
        return 1
    return text[:idx].count("\n") + 1


def audit_routes(root: Path) -> Dict[str, Any]:
    endpoints = _endpoint_names(root / "app.py")
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
                    "exact_fix": f"Open {template.relative_to(root)} and replace url_for('{endpoint}') with the real Flask function name, or rename the Flask route function to {endpoint}.",
                })
    score = max(0, 100 - len(issues) * 18)
    return {
        "name": "Route Health",
        "score": score,
        "status": _status(score),
        "summary": f"Checked {total_calls} template route calls against {len(endpoints)} known endpoints.",
        "issues": issues,
    }


def audit_templates(root: Path) -> Dict[str, Any]:
    issues = []
    for template in _template_files(root):
        text = _read(template)
        rel = str(template.relative_to(root))
        if "{% include '_nav.html' %}" not in text and rel != "templates/_nav.html":
            issues.append({
                "severity": "Medium",
                "file": rel,
                "line": 1,
                "problem": "Template does not include the shared sidebar navigation.",
                "exact_fix": "Add {% include '_nav.html' %} right after the opening <main class=\"shell\"> tag.",
            })
        if '<main class="app-shell"' in text:
            issues.append({
                "severity": "High",
                "file": rel,
                "line": _line_number(text, '<main class="app-shell"'),
                "problem": "This template uses app-shell while the product layout uses shell.",
                "exact_fix": "Replace <main class=\"app-shell\"> with <main class=\"shell\">.",
            })
        if "<meta name=\"viewport\"" not in text and "<head" in text:
            issues.append({
                "severity": "Low",
                "file": rel,
                "line": _line_number(text, "<meta charset"),
                "problem": "Viewport meta tag is missing, so mobile/tablet scaling may look off.",
                "exact_fix": "Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"> under the charset meta tag.",
            })
    score = max(0, 100 - len([i for i in issues if i["severity"] == "High"]) * 15 - len([i for i in issues if i["severity"] == "Medium"]) * 7 - len([i for i in issues if i["severity"] == "Low"]) * 2)
    return {"name": "Template Consistency", "score": score, "status": _status(score), "summary": f"Checked {len(_template_files(root))} templates for shared layout rules.", "issues": issues[:20]}


def audit_css(root: Path) -> Dict[str, Any]:
    css = _read(root / "static" / "style.css")
    issues = []
    required = [".shell", ".kdt-sidebar", ".mobile-nav-strip", ".content-panel", ".mastery-bar", ".concept-pill", ".sidebar-footer"]
    for cls in required:
        if cls not in css:
            issues.append({
                "severity": "High",
                "file": "static/style.css",
                "line": 1,
                "problem": f"Missing required layout/style selector: {cls}",
                "exact_fix": f"Add a CSS block for {cls} so the UI does not fall back to browser defaults.",
            })
    if "transform: translateX(120px)" in css or "transform:translateX(120px)" in css:
        issues.append({
            "severity": "Medium",
            "file": "static/style.css",
            "line": _line_number(css, "translateX(120px)"),
            "problem": "Large-screen layout uses a manual transform that can make zoom levels look wrong.",
            "exact_fix": "Delete the @media (min-width: 1450px) transform block and rely on shell margin/padding instead.",
        })
    score = max(0, 100 - len([i for i in issues if i["severity"] == "High"]) * 18 - len([i for i in issues if i["severity"] == "Medium"]) * 8)
    return {"name": "UI / CSS Health", "score": score, "status": _status(score), "summary": "Checked core layout selectors and zoom-risk CSS.", "issues": issues}


def audit_json_dirs(root: Path) -> Dict[str, Any]:
    issues = []
    checked = 0
    for folder in ["quests", "quest_archive", "quest_postmortems", "projects", "reports", "goals", "paths"]:
        d = root / folder
        if not d.exists():
            issues.append({"severity": "Medium", "file": folder, "line": 1, "problem": f"Missing data folder: {folder}", "exact_fix": f"Create the {folder}/ folder so KDT OS can store and read its memory."})
            continue
        for path in d.glob("*.json"):
            checked += 1
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                issues.append({"severity": "High", "file": str(path.relative_to(root)), "line": 1, "problem": f"Invalid JSON: {exc}", "exact_fix": "Open this file, fix the JSON syntax, then run the app again."})
    score = max(0, 100 - len([i for i in issues if i["severity"] == "High"]) * 25 - len([i for i in issues if i["severity"] == "Medium"]) * 8)
    return {"name": "Data Integrity", "score": score, "status": _status(score), "summary": f"Checked {checked} JSON memory files.", "issues": issues[:20]}


def audit_quest_governance(root: Path) -> Dict[str, Any]:
    issues = []
    quests = []
    for path in sorted((root / "quests").glob("*.json")):
        try:
            q = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        q["_file"] = str(path.relative_to(root))
        quests.append(q)
    sigs = Counter()
    body_to_files = defaultdict(list)
    generic_markers = ["small project that demonstrates", "create original files", "requested skill", "one artifact that proves"]
    for q in quests:
        body = " ".join(str(q.get(k, "")) for k in ["title", "skill", "what_to_build", "requirements", "steps", "success_criteria", "proof_required"]).lower()
        collapsed = re.sub(r"[^a-z0-9]+", " ", body).strip()
        sig = collapsed[:350]
        sigs[sig] += 1
        body_to_files[sig].append(q["_file"])
        hits = [m for m in generic_markers if m in body]
        if hits:
            issues.append({
                "severity": "High",
                "file": q["_file"],
                "line": 1,
                "problem": f"Quest still contains generic template language: {', '.join(hits)}.",
                "exact_fix": "Regenerate this quest from Quest Intelligence. The replacement must name exact files, exact steps, exact proof, and an understanding check.",
            })
        if not q.get("quest_quality"):
            issues.append({
                "severity": "Medium",
                "file": q["_file"],
                "line": 1,
                "problem": "Quest is missing quest_quality metadata.",
                "exact_fix": "Open Quest Intelligence and regenerate or rescore this quest so it has governance metadata.",
            })
    for sig, count in sigs.items():
        if count > 1 and sig:
            issues.append({
                "severity": "High",
                "file": ", ".join(body_to_files[sig][:3]),
                "line": 1,
                "problem": f"Possible duplicate quest body detected across {count} active quests.",
                "exact_fix": "Archive duplicates with postmortems, then regenerate each from its specific skill and project gap.",
            })
    score = max(0, 100 - len([i for i in issues if i["severity"] == "High"]) * 12 - len([i for i in issues if i["severity"] == "Medium"]) * 5)
    return {"name": "Quest Governance", "score": score, "status": _status(score), "summary": f"Checked {len(quests)} active quest files for quality metadata, template language, and clones.", "issues": issues[:25]}


def audit_architecture(root: Path) -> Dict[str, Any]:
    app_py = root / "app.py"
    lines = _read(app_py).count("\n") + 1
    issues = []
    if lines > 2500:
        issues.append({
            "severity": "Medium",
            "file": "app.py",
            "line": 1,
            "problem": f"app.py is very large ({lines} lines). This increases break risk when adding features.",
            "exact_fix": "Start moving new systems into installable modules like kdt_quest_intelligence_v20.py, kdt_intelligence_v21.py, and kdt_self_check_v22.py before splitting old routes.",
        })
    for module in ["kdt_quest_intelligence_v20.py", "kdt_intelligence_v21.py"]:
        if not (root / module).exists():
            issues.append({"severity": "High", "file": module, "line": 1, "problem": f"Missing expected intelligence module: {module}", "exact_fix": f"Restore {module} or remove its install call from app.py."})
    score = max(0, 100 - len([i for i in issues if i["severity"] == "High"]) * 25 - len([i for i in issues if i["severity"] == "Medium"]) * 10)
    return {"name": "Architecture", "score": score, "status": _status(score), "summary": "Checked core app size and modular intelligence files.", "issues": issues}


def run_self_check(root: Path) -> Dict[str, Any]:
    audits = [
        audit_routes(root), audit_templates(root), audit_css(root), audit_json_dirs(root), audit_quest_governance(root), audit_architecture(root)
    ]
    score = int(sum(a["score"] for a in audits) / max(1, len(audits)))
    critical = sum(1 for a in audits for i in a.get("issues", []) if i.get("severity") == "High")
    return {
        "score": score,
        "status": _status(score),
        "critical_issues": critical,
        "audits": audits,
        "next_fix": next((i for a in audits for i in a.get("issues", []) if i.get("severity") == "High"), None),
    }


def _sidebar_stats(kdt: Any) -> Dict[str, Any]:
    try:
        quest_count = len([q for q in kdt.list_quests() if str(q.get("status", "")).lower() not in {"completed", "archived", "superseded"}])
    except Exception:
        quest_count = 0
    try:
        project_count = len(kdt.list_projects())
    except Exception:
        project_count = 0
    mastery_percent = 0
    try:
        if hasattr(kdt, "mastery_map"):
            skills = kdt.mastery_map().get("skills", [])
            mastery_percent = int(sum(s.get("score", 0) for s in skills) / max(1, len(skills)))
    except Exception:
        mastery_percent = 0
    return {"quest_count": quest_count, "project_count": project_count, "mastery_percent": mastery_percent}


def install(kdt: Any) -> Any:
    app = getattr(kdt, "app", None)
    if app is None:
        return kdt
    root = Path(getattr(kdt, "BASE_DIR", Path.cwd()))

    if not getattr(app, "_kdt_sidebar_context_v22", False):
        @app.context_processor
        def inject_kdt_sidebar_stats():
            return _sidebar_stats(kdt)
        app._kdt_sidebar_context_v22 = True

    if "self_check" not in app.view_functions:
        def self_check():
            return kdt.render_template("self_check.html", check=run_self_check(root))
        app.add_url_rule("/self_check", "self_check", self_check)

    if "self_check_json" not in app.view_functions:
        def self_check_json():
            return kdt.jsonify(run_self_check(root))
        app.add_url_rule("/self_check.json", "self_check_json", self_check_json)

    kdt.run_self_check_v22 = lambda: run_self_check(root)
    return kdt
