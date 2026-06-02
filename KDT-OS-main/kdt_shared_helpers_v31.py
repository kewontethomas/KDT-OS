"""KDT OS Shared Helper Layer V31

V31 extracts safe, pure utility helpers into core/helpers.py and exposes a page
that proves the helper layer exists before app.py relies on it heavily.
"""
from __future__ import annotations

import ast
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from core.storage import read_text
from core.helpers import (
    safe_int,
    safe_float,
    clamp_percent,
    truncate_text,
    slugify_name,
    normalize_filename,
    format_timestamp,
    file_size_label,
)


HELPER_NAMES = [
    "safe_int",
    "safe_float",
    "clamp_percent",
    "truncate_text",
    "slugify_name",
    "normalize_filename",
    "format_timestamp",
    "file_size_label",
]

PURE_HELPER_HINTS = [
    "slugify",
    "normalize",
    "format",
    "clean",
    "safe",
    "score",
    "summary",
    "snapshot",
    "read",
    "load",
    "save",
]

BAD_MOVE_HINTS = [
    "route", "render_template", "request", "redirect", "url_for", "flash", "jsonify", "send_from_directory"
]


def _line_count(path: Path) -> int:
    return len(read_text(path).splitlines())


def _core_file(root: Path, rel: str) -> Dict[str, Any]:
    p = root / rel
    return {
        "path": rel,
        "exists": p.exists(),
        "lines": _line_count(p) if p.exists() else 0,
        "size": file_size_label(p) if p.exists() else "0 B",
    }


def _function_candidates(app_py: Path) -> List[Dict[str, Any]]:
    source = read_text(app_py)
    try:
        tree = ast.parse(source)
    except Exception:
        return []
    lines = source.splitlines()
    candidates: List[Dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        name = node.name
        start = getattr(node, "lineno", 0)
        end = getattr(node, "end_lineno", start)
        body = "\n".join(lines[max(0, start - 1): end])
        lowered = body.lower()
        route_like = any(h in lowered for h in BAD_MOVE_HINTS) or any(
            getattr(d, "attr", "") == "route" for d in getattr(node, "decorator_list", [])
        )
        helper_like = any(h in name.lower() for h in PURE_HELPER_HINTS)
        risk = "Do not move yet" if route_like else ("Candidate" if helper_like else "Review later")
        if helper_like or route_like:
            candidates.append({
                "name": name,
                "line": start,
                "lines": max(1, end - start + 1),
                "risk": risk,
                "reason": "Uses Flask/rendering" if route_like else "Name looks like reusable utility logic",
            })
    return sorted(candidates, key=lambda x: (0 if x["risk"] == "Candidate" else 1, x["line"]))[:40]


def _usage_counts(root: Path) -> Dict[str, int]:
    files = [root / "app.py"] + list((root / "kdt_" ).parent.glob("kdt_*.py"))
    counts = {name: 0 for name in HELPER_NAMES}
    for file in files:
        if not file.exists() or not file.name.endswith(".py"):
            continue
        text = read_text(file)
        for name in HELPER_NAMES:
            counts[name] += len(re.findall(rf"\b{name}\s*\(", text))
    return counts


def shared_helpers_snapshot(kdt: Any) -> Dict[str, Any]:
    root = Path(kdt.APP_ROOT)
    app_py = root / "app.py"
    helper_file = root / "core/helpers.py"
    helper_counts = _usage_counts(root)
    helper_file_text = read_text(helper_file)
    extracted = [name for name in HELPER_NAMES if re.search(rf"def\s+{name}\s*\(", helper_file_text)]
    candidates = _function_candidates(app_py)
    candidate_count = len([c for c in candidates if c["risk"] == "Candidate"])
    readiness = 0
    readiness += 35 if helper_file.exists() else 0
    readiness += 25 if len(extracted) >= 6 else 0
    readiness += 20 if hasattr(kdt, "helper_slugify_name") else 0
    readiness += 20 if candidate_count >= 1 else 0
    return {
        "version": "V31",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "app_py_lines": _line_count(app_py),
        "readiness": readiness,
        "helpers_extracted": len(extracted),
        "candidate_count": candidate_count,
        "core_files": [
            _core_file(root, "core/helpers.py"),
            _core_file(root, "core/storage.py"),
            _core_file(root, "core/paths.py"),
            _core_file(root, "core/constants.py"),
        ],
        "helpers": [{"name": name, "available": name in extracted, "usage_count": helper_counts.get(name, 0)} for name in HELPER_NAMES],
        "candidates": candidates,
        "rule": "Only move pure utility helpers. Do not move routes, Flask request logic, render_template calls, or anything that changes user-facing behavior.",
        "next_targets": [
            {"phase": "V32", "title": "Adopt helpers in new modules", "move": "New route/engine modules should import safe_int, truncate_text, slugify_name, and format_timestamp from core.helpers.", "proof": "No new module should recreate these helpers."},
            {"phase": "V33", "title": "Extract quest store", "move": "Move quest list/load/save/archive helpers into engines/quest_store.py using core.storage and core.helpers.", "proof": "Quest pages still work and app.py loses quest file helper code."},
            {"phase": "V34", "title": "Extract Learn routes", "move": "Move Teach Me, quests, skills, growth, goals, and mastery routes into routes/learn_routes.py after storage/helpers are stable.", "proof": "Quest creation, proof submission, and mastery still work."},
        ],
    }


def install(kdt: Any) -> None:
    app = kdt.app

    # Expose pure helpers on the KDT module for future extracted systems.
    kdt.helper_safe_int = safe_int
    kdt.helper_safe_float = safe_float
    kdt.helper_clamp_percent = clamp_percent
    kdt.helper_truncate_text = truncate_text
    kdt.helper_slugify_name = slugify_name
    kdt.helper_normalize_filename = normalize_filename
    kdt.helper_format_timestamp = format_timestamp
    kdt.helper_file_size_label = file_size_label

    def shared_helpers():
        return kdt.render_template("shared_helpers.html", snapshot=shared_helpers_snapshot(kdt))

    def shared_helpers_json():
        return kdt.jsonify(shared_helpers_snapshot(kdt))

    app.add_url_rule("/shared_helpers", "shared_helpers", shared_helpers, methods=["GET"])
    app.add_url_rule("/shared_helpers.json", "shared_helpers_json", shared_helpers_json, methods=["GET"])

    kdt.shared_helpers_snapshot_v31 = lambda: shared_helpers_snapshot(kdt)
