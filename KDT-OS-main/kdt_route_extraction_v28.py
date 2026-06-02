"""KDT OS Route Extraction V28

V28 performs the first real route-family extraction:
- Verify route registration moved from app.py into routes/verify_routes.py
- System architecture route registration moved into routes/system_routes.py
- app.py now calls two family registrars instead of importing every system directly

This version is intentionally conservative. It does not move old route function
bodies yet. It proves KDT OS can extract a route family without breaking pages.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _line_count(path: Path) -> int:
    return len(_read(path).splitlines())


def _family_for(rule: str, endpoint: str) -> str:
    text = f"{rule} {endpoint}".lower()
    if any(k in text for k in ["self_check", "governance", "action_center", "vision", "archive", "quality", "quest_maintenance"]):
        return "Verify"
    if any(k in text for k in ["modular", "route_extraction", "upgrade", "ai", "model"]):
        return "System"
    if any(k in text for k in ["teach", "quest", "skill", "mastery", "growth", "goal"]):
        return "Learn"
    if any(k in text for k in ["project", "source", "path", "report", "analyze"]):
        return "Build"
    return "Core"


def _route_rows(flask_app) -> List[Dict[str, Any]]:
    rows = []
    for rule in sorted(flask_app.url_map.iter_rules(), key=lambda r: str(r.rule)):
        if rule.endpoint == "static":
            continue
        rows.append({
            "rule": str(rule.rule),
            "endpoint": rule.endpoint,
            "methods": sorted([m for m in rule.methods if m not in {"HEAD", "OPTIONS"}]),
            "family": _family_for(str(rule.rule), rule.endpoint),
        })
    return rows


def _import_snapshot(app_py: Path) -> Dict[str, Any]:
    source = _read(app_py)
    return {
        "uses_verify_registrar": "register_verify_routes" in source,
        "uses_system_registrar": "register_system_routes" in source,
        "direct_verify_installs_removed": all(token not in source for token in [
            "install_v22(sys.modules[__name__])",
            "install_v23(sys.modules[__name__])",
            "install_v24(sys.modules[__name__])",
            "install_v25(sys.modules[__name__])",
            "install_v26(sys.modules[__name__])",
        ]),
        "direct_system_install_removed": "install_v27(sys.modules[__name__])" not in source,
    }


def _module_file(root: Path, rel: str) -> Dict[str, Any]:
    path = root / rel
    return {"path": rel, "exists": path.exists(), "lines": _line_count(path)}


def route_extraction_snapshot(kdt: Any) -> Dict[str, Any]:
    root = Path(kdt.APP_ROOT)
    app_py = root / "app.py"
    routes = _route_rows(kdt.app)
    family_counts: Dict[str, int] = {}
    for row in routes:
        family_counts[row["family"]] = family_counts.get(row["family"], 0) + 1

    extracted_modules = [
        _module_file(root, "routes/verify_routes.py"),
        _module_file(root, "routes/system_routes.py"),
        _module_file(root, "kdt_route_extraction_v28.py"),
    ]

    import_status = _import_snapshot(app_py)
    health_points = 0
    health_points += 25 if import_status["uses_verify_registrar"] else 0
    health_points += 25 if import_status["uses_system_registrar"] else 0
    health_points += 25 if import_status["direct_verify_installs_removed"] else 0
    health_points += 25 if all(m["exists"] for m in extracted_modules) else 0

    next_targets = [
        {"phase": "V29", "title": "Extract shared storage helpers", "move": "Move JSON read/write, slugify, path constants, and directory setup into core/storage.py and core/paths.py.", "success": "app.py loses shared helper code without changing user pages."},
        {"phase": "V30", "title": "Extract Learn routes", "move": "Move Teach Me, quests, skills, growth, goals, and mastery routes into routes/learn_routes.py.", "success": "Quest creation, proof submission, and mastery pages still work."},
        {"phase": "V31", "title": "Extract Build routes", "move": "Move projects, sources, analyzer, reports, and path builder into routes/build_routes.py.", "success": "Project upload/analyze/report flow still works."},
    ]

    return {
        "version": "V28",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "app_py_lines": _line_count(app_py),
        "total_routes": len(routes),
        "family_counts": family_counts,
        "extraction_health": health_points,
        "architecture_risk": "High" if _line_count(app_py) > 3500 else "Medium",
        "import_status": import_status,
        "extracted_modules": extracted_modules,
        "verify_routes": [r for r in routes if r["family"] == "Verify"],
        "system_routes": [r for r in routes if r["family"] == "System"],
        "next_targets": next_targets,
        "rule": "V28 proves route families can be extracted safely. Do not move every route at once.",
    }


def install(kdt: Any) -> None:
    app = kdt.app

    def route_extraction():
        snapshot = route_extraction_snapshot(kdt)
        return kdt.render_template("route_extraction.html", snapshot=snapshot)

    def route_extraction_json():
        return kdt.jsonify(route_extraction_snapshot(kdt))

    app.add_url_rule("/route_extraction", "route_extraction", route_extraction, methods=["GET"])
    app.add_url_rule("/route_extraction.json", "route_extraction_json", route_extraction_json, methods=["GET"])

    kdt.route_extraction_snapshot_v28 = lambda: route_extraction_snapshot(kdt)
