"""KDT OS Shared Helpers V31

Pure utility helpers that future route/engine modules can safely import without
reaching back into the large Flask app.py file.

Rule: helpers in this file must not register routes, render templates, or depend
on Flask request/session context. Keep them boring, reusable, and easy to test.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any


def safe_int(value: Any, default: int = 0, minimum: int | None = None, maximum: int | None = None) -> int:
    """Convert a value to int safely and optionally clamp it."""
    try:
        number = int(value)
    except Exception:
        number = default
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


def safe_float(value: Any, default: float = 0.0, minimum: float | None = None, maximum: float | None = None) -> float:
    """Convert a value to float safely and optionally clamp it."""
    try:
        number = float(value)
    except Exception:
        number = default
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


def clamp_percent(value: Any, default: int = 0) -> int:
    """Return an integer percentage between 0 and 100."""
    return safe_int(value, default=default, minimum=0, maximum=100)


def truncate_text(text: Any, limit: int = 160, suffix: str = "...") -> str:
    """Shorten long text without crashing on non-string values."""
    text = "" if text is None else str(text).strip()
    if limit <= 0 or len(text) <= limit:
        return text
    return text[: max(0, limit - len(suffix))].rstrip() + suffix


def slugify_name(value: Any, fallback: str = "item") -> str:
    """Create a filesystem-safe slug for quest/project/report names."""
    text = "" if value is None else str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or fallback


def normalize_filename(value: Any, fallback: str = "file") -> str:
    """Return a safe filename stem while preserving readable words."""
    return slugify_name(value, fallback=fallback)


def format_timestamp(value: Any = None) -> str:
    """Return a stable timestamp for display/logging."""
    if value is None:
        return datetime.now().isoformat(timespec="seconds")
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    return str(value)


def file_size_label(path: Path) -> str:
    """Human-friendly file size label."""
    try:
        size = Path(path).stat().st_size
    except Exception:
        return "0 B"
    units = ["B", "KB", "MB", "GB"]
    amount = float(size)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{size} B"
