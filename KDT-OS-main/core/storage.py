"""KDT OS Core Storage V29

Safe JSON/text helpers for future route and engine extraction.
V29 introduces these helpers without forcing a risky app-wide rewrite yet.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def read_text(path: Path, default: str = "", max_chars: int | None = None) -> str:
    try:
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
        return text[:max_chars] if max_chars else text
    except Exception:
        return default


def write_text(path: Path, text: str) -> bool:
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return True
    except Exception:
        return False


def load_json(path: Path, default: Any = None) -> Any:
    if default is None:
        default = {}
    try:
        path = Path(path)
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data: Any, indent: int = 2) -> bool:
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=indent), encoding="utf-8")
        return True
    except Exception:
        return False


def list_json_files(folder: Path) -> List[Path]:
    try:
        return sorted(Path(folder).glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception:
        return []


def load_json_records(folder: Path, include_filename: bool = True) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for path in list_json_files(folder):
        data = load_json(path, {})
        if isinstance(data, dict):
            if include_filename:
                data.setdefault("filename", path.name)
            records.append(data)
    return records


def append_json_log(path: Path, item: Dict[str, Any], limit: int = 300) -> List[Dict[str, Any]]:
    current = load_json(path, [])
    if not isinstance(current, list):
        current = []
    current.insert(0, item)
    current = current[:limit]
    save_json(path, current)
    return current
