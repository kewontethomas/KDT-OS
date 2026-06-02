"""KDT OS Core Paths V29

Central place for project directories. This lets future route modules import paths
without depending on the giant app.py file.
"""
from __future__ import annotations

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = APP_ROOT / "uploads"
REPORT_DIR = APP_ROOT / "reports"
WORK_DIR = APP_ROOT / "workspace"
DECISION_DIR = APP_ROOT / "decisions"
QUEST_DIR = APP_ROOT / "quests"
GOAL_DIR = APP_ROOT / "goals"
SUBMISSION_DIR = APP_ROOT / "quest_submissions"
SKILL_DIR = APP_ROOT / "skill_library"
PROJECT_DIR = APP_ROOT / "projects"
PATH_DIR = APP_ROOT / "paths"
UPGRADE_DIR = APP_ROOT / "upgrades"
BOTTLENECK_DIR = APP_ROOT / "bottlenecks"
VISION_DIR = APP_ROOT / "vision_uploads"
QUEST_ARCHIVE_DIR = APP_ROOT / "quest_archive"
QUEST_POSTMORTEM_DIR = APP_ROOT / "quest_postmortems"

SETTINGS_FILE = APP_ROOT / "kdt_settings.json"
AI_LOG_FILE = APP_ROOT / "ai_diagnostics_log.json"
DECISION_MEMORY_FILE = APP_ROOT / "decision_memory.json"
LANGUAGE_KB_FILE = APP_ROOT / "language_knowledge_base.json"
REDUNDANCY_LOG_FILE = APP_ROOT / "redundancy_log.json"
MODEL_LOG_FILE = APP_ROOT / "model_manager_log.json"
GOVERNANCE_LOG_FILE = APP_ROOT / "governance_log.json"

DATA_DIRS = [
    UPLOAD_DIR, REPORT_DIR, WORK_DIR, DECISION_DIR, QUEST_DIR, GOAL_DIR,
    SUBMISSION_DIR, SKILL_DIR, PROJECT_DIR, PATH_DIR, UPGRADE_DIR,
    BOTTLENECK_DIR, VISION_DIR, QUEST_ARCHIVE_DIR, QUEST_POSTMORTEM_DIR,
]

def ensure_data_dirs() -> None:
    for folder in DATA_DIRS:
        folder.mkdir(exist_ok=True)
