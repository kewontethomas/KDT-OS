"""KDT OS Core Storage Layer V29

V29 adds a shared core storage layer without rewriting the whole app at once.
It proves future route modules can depend on core.paths/core.storage instead of
importing everything from app.py.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from core import paths
from core.storage import load_json, save_json, read_text, list_json_files, load_json_records


def _find_storage_patterns(app_py: Path) -> Dict[str, int]:
    text = read_text(app_py)
    patterns = {
        "json.loads": text.count("json.loads"),
        "json.dumps": text.count("json.dumps"),
        "read_text": text.count("read_text"),
        "write_text": text.count("write_text"),
        "glob_json": text.count("glob(\"*.json\")") + text.count("glob('*.json')"),
    }
    return patterns


def _core_file(root: Path, rel: str) -> Dict[str, Any]:
    p = root / rel
    return {
        "path": rel,
        "exists": p.exists(),
        "lines": len(read_text(p).splitlines()) if p.exists() else 0,
    }


def _json_folder_status(name: str, folder: Path) -> Dict[str, Any]:
    files = list_json_files(folder)
    sample = []
    for f in files[:3]:
        data = load_json(f, {})
        sample.append({"file": f.name, "type": type(data).__name__, "ok": isinstance(data, (dict, list))})
    return {"name": name, "path": str(folder.name), "count": len(files), "sample": sample}


def core_storage_snapshot(kdt: Any) -> Dict[str, Any]:
    root = Path(kdt.APP_ROOT)
    app_py = root / "app.py"
    core_files = [
        _core_file(root, "core/paths.py"),
        _core_file(root, "core/storage.py"),
        _core_file(root, "core/constants.py"),
        _core_file(root, "core/__init__.py"),
    ]
    folder_status = [
        _json_folder_status("Quests", paths.QUEST_DIR),
        _json_folder_status("Projects", paths.PROJECT_DIR),
        _json_folder_status("Goals", paths.GOAL_DIR),
        _json_folder_status("Reports", paths.REPORT_DIR),
        _json_folder_status("Paths", paths.PATH_DIR),
        _json_folder_status("Archive", paths.QUEST_ARCHIVE_DIR),
    ]
    patterns = _find_storage_patterns(app_py)
    direct_storage_weight = sum(patterns.values())
    readiness = 0
    readiness += 30 if all(f["exists"] for f in core_files) else 0
    readiness += 20 if all(s["count"] >= 0 for s in folder_status) else 0
    readiness += 25 if hasattr(kdt, "core_load_json") and hasattr(kdt, "core_save_json") else 0
    readiness += 25 if "from core.storage" in read_text(app_py) or hasattr(kdt, "core_storage_snapshot_v29") else 0
    next_targets = [
        {"phase": "V30", "title": "Use core.storage in new modules first", "move": "New route and engine modules should import load_json, save_json, read_text, and list_json_files from core.storage.", "proof": "No new module should add raw json.loads(path.read_text()) unless there is a special reason."},
        {"phase": "V31", "title": "Extract quest storage helpers", "move": "Move quest load/save/list/archive helpers into engines/quest_store.py or core/quest_store.py.", "proof": "Quest pages still load and app.py loses quest file helper code."},
        {"phase": "V32", "title": "Extract project and report storage", "move": "Move project/report JSON access into engines/project_store.py.", "proof": "Project upload, reports, and project history still work."},
    ]
    return {
        "version": "V29",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "app_py_lines": len(read_text(app_py).splitlines()),
        "readiness": readiness,
        "core_files": core_files,
        "folder_status": folder_status,
        "storage_patterns_remaining": patterns,
        "direct_storage_weight": direct_storage_weight,
        "rule": "V29 creates the shared storage layer first. Do not replace every JSON call at once; future modules should adopt core.storage safely.",
        "next_targets": next_targets,
    }


def install(kdt: Any) -> None:
    app = kdt.app

    # Expose stable core helpers on the KDT module for future extracted modules.
    kdt.core_load_json = load_json
    kdt.core_save_json = save_json
    kdt.core_read_text = read_text
    kdt.core_list_json_files = list_json_files
    kdt.core_load_json_records = load_json_records
    kdt.core_paths = paths

    def core_storage():
        return kdt.render_template("core_storage.html", snapshot=core_storage_snapshot(kdt))

    def core_storage_json():
        return kdt.jsonify(core_storage_snapshot(kdt))

    app.add_url_rule("/core_storage", "core_storage", core_storage, methods=["GET"])
    app.add_url_rule("/core_storage.json", "core_storage_json", core_storage_json, methods=["GET"])

    kdt.core_storage_snapshot_v29 = lambda: core_storage_snapshot(kdt)
