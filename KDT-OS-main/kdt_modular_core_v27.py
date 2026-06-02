from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List


def _count_lines(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
    except Exception:
        return 0


def _ensure_modular_scaffold(app_root: Path) -> None:
    """Create safe modular folders without moving working code yet.

    V27 is intentionally non-destructive. It prepares the platform for route and
    engine extraction while keeping the current app.py stable.
    """
    folders = [
        app_root / "routes",
        app_root / "engines",
        app_root / "core",
    ]
    for folder in folders:
        folder.mkdir(exist_ok=True)
        init_file = folder / "__init__.py"
        if not init_file.exists():
            init_file.write_text('"""KDT OS modular package scaffold."""\n', encoding="utf-8")

    readmes = {
        app_root / "routes" / "README.md": """# KDT OS Routes

V27 scaffold.

Future route modules:
- build_routes.py
- learn_routes.py
- verify_routes.py
- system_routes.py

Rule: route files should only connect URLs/forms/templates to engine functions.
Heavy logic belongs in `engines/`.
""",
        app_root / "engines" / "README.md": """# KDT OS Engines

V27 scaffold.

Future engine modules:
- quest_engine.py
- governance_engine.py
- mastery_engine.py
- project_engine.py
- selfcheck_engine.py
- action_engine.py

Rule: engines should be reusable Python logic with minimal Flask dependencies.
""",
        app_root / "core" / "README.md": """# KDT OS Core

V27 scaffold.

Future core modules:
- paths.py
- storage.py
- settings.py
- models.py

Rule: core owns shared paths, JSON helpers, and low-level storage rules.
""",
    }
    for path, content in readmes.items():
        if not path.exists():
            path.write_text(content, encoding="utf-8")


def _categorize_route(rule: str, endpoint: str) -> str:
    text = f"{rule} {endpoint}".lower()
    if any(k in text for k in ["project", "source", "path", "report", "analyze"]):
        return "Build"
    if any(k in text for k in ["teach", "quest", "skill", "mastery", "growth", "goal"]):
        return "Learn"
    if any(k in text for k in ["governance", "action_center", "self_check", "vision", "archive", "quality"]):
        return "Verify"
    if any(k in text for k in ["upgrade", "ai", "model", "modular", "download"]):
        return "System"
    return "Core"


def _route_snapshot(flask_app) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for rule in sorted(flask_app.url_map.iter_rules(), key=lambda r: str(r.rule)):
        endpoint = rule.endpoint
        if endpoint == "static":
            continue
        methods = sorted([m for m in rule.methods if m not in {"HEAD", "OPTIONS"}])
        category = _categorize_route(str(rule.rule), endpoint)
        rows.append({
            "rule": str(rule.rule),
            "endpoint": endpoint,
            "methods": methods,
            "category": category,
        })

    counts: Dict[str, int] = {}
    for row in rows:
        counts[row["category"]] = counts.get(row["category"], 0) + 1

    return {
        "total_routes": len(rows),
        "category_counts": counts,
        "routes": rows,
    }


def _module_snapshot(app_root: Path) -> Dict[str, Any]:
    modules = []
    for path in sorted(app_root.glob("kdt_*_v*.py")):
        modules.append({
            "file": path.name,
            "lines": _count_lines(path),
            "role": _infer_module_role(path.name),
        })
    return {
        "count": len(modules),
        "modules": modules,
    }


def _infer_module_role(name: str) -> str:
    n = name.lower()
    if "quest" in n:
        return "Quest Intelligence"
    if "governance" in n:
        return "Governance"
    if "self_check" in n:
        return "System Health"
    if "action" in n:
        return "Action Engine"
    if "intelligence" in n:
        return "Mastery / Intelligence"
    return "Extension"


def modular_core_snapshot(kdt) -> Dict[str, Any]:
    app_root = getattr(kdt, "APP_ROOT", Path(__file__).parent.resolve())
    flask_app = getattr(kdt, "app")
    _ensure_modular_scaffold(app_root)

    app_py = app_root / "app.py"
    app_lines = _count_lines(app_py)
    route_data = _route_snapshot(flask_app)
    module_data = _module_snapshot(app_root)

    current_risk = "Low"
    if app_lines >= 4000:
        current_risk = "High"
    elif app_lines >= 2500:
        current_risk = "Medium"

    extraction_plan = [
        {
            "phase": "Phase 1",
            "name": "Stabilize extension modules",
            "status": "Ready",
            "move": "Keep V20-V26 as installable modules and stop adding large features directly to app.py.",
            "proof": "New version files install cleanly without editing existing core routes."
        },
        {
            "phase": "Phase 2",
            "name": "Extract shared storage helpers",
            "status": "Recommended Next",
            "move": "Move JSON read/write, slugify, path constants, and directory setup into core/storage.py and core/paths.py.",
            "proof": "app.py imports storage helpers and all existing pages still open."
        },
        {
            "phase": "Phase 3",
            "name": "Extract verify routes",
            "status": "Planned",
            "move": "Move Self Check, Auto Governance, Action Center, Quest Maintenance, Archive, and Vision routes into routes/verify_routes.py.",
            "proof": "Verify menu pages still open and action buttons still work."
        },
        {
            "phase": "Phase 4",
            "name": "Extract learn routes",
            "status": "Planned",
            "move": "Move Teach Me, Quests, Skills, Mastery, Growth, and Goals into routes/learn_routes.py.",
            "proof": "Quest creation, proof submission, and mastery pages still work."
        },
        {
            "phase": "Phase 5",
            "name": "Extract build routes",
            "status": "Planned",
            "move": "Move Projects, Sources, Project Reports, and Path Builder into routes/build_routes.py.",
            "proof": "Project upload, scan, report, and path creation still work."
        },
    ]

    target = {
        "app_py_current_lines": app_lines,
        "app_py_target_lines": 1000,
        "line_reduction_needed": max(0, app_lines - 1000),
        "risk": current_risk,
        "rule": "Do not perform a massive one-shot rewrite. Extract one route family at a time and test after each move.",
    }

    return {
        "version": "V27 Modular Core",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "target": target,
        "routes": route_data,
        "modules": module_data,
        "scaffold": {
            "created": ["routes/", "engines/", "core/"],
            "safe": True,
            "note": "V27 creates the modular structure and route map without breaking the existing app.py."
        },
        "extraction_plan": extraction_plan,
        "next_best_action": "Extract shared storage/path helpers first, because every route family depends on them.",
    }


def install(kdt):
    app = kdt.app

    @app.route("/modular_core")
    def modular_core():
        snapshot = modular_core_snapshot(kdt)
        return kdt.render_template("modular_core.html", data=snapshot)

    @app.route("/modular_core.json")
    def modular_core_json():
        return kdt.jsonify(modular_core_snapshot(kdt))
