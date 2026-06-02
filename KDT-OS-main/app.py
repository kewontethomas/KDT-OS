from __future__ import annotations

import json
import hashlib
import re
import shutil
import zipfile
import subprocess
import time
import urllib.request
import urllib.error
import base64
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any
import sys

from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, jsonify

APP_ROOT = Path(__file__).parent.resolve()
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
SETTINGS_FILE = APP_ROOT / "kdt_settings.json"
AI_LOG_FILE = APP_ROOT / "ai_diagnostics_log.json"
UPGRADE_DIR = APP_ROOT / "upgrades"
DECISION_MEMORY_FILE = APP_ROOT / "decision_memory.json"
LANGUAGE_KB_FILE = APP_ROOT / "language_knowledge_base.json"
REDUNDANCY_LOG_FILE = APP_ROOT / "redundancy_log.json"
BOTTLENECK_DIR = APP_ROOT / "bottlenecks"
VISION_DIR = APP_ROOT / "vision_uploads"
MODEL_LOG_FILE = APP_ROOT / "model_manager_log.json"
QUEST_ARCHIVE_DIR = APP_ROOT / "quest_archive"
QUEST_POSTMORTEM_DIR = APP_ROOT / "quest_postmortems"
GOVERNANCE_LOG_FILE = APP_ROOT / "governance_log.json"
QUEST_MINIMUM_SCORE = 85

for folder in [UPLOAD_DIR, REPORT_DIR, WORK_DIR, DECISION_DIR, QUEST_DIR, GOAL_DIR, SUBMISSION_DIR, SKILL_DIR, PROJECT_DIR, PATH_DIR, UPGRADE_DIR, BOTTLENECK_DIR, VISION_DIR, QUEST_ARCHIVE_DIR, QUEST_POSTMORTEM_DIR]:
    folder.mkdir(exist_ok=True)

app = Flask(__name__)
app.secret_key = "change-this-secret-key"


# -----------------------------
# Universal Language / Stack Knowledge Base + Decision Memory
# -----------------------------
DEFAULT_DECISION_MEMORY = {
    "rules": [
        "KDT OS must never treat an inference as a fact.",
        "Every recommendation must include exact instructions, success criteria, and proof.",
        "Goals are funnels for projects; projects create skill needs; skills create quests.",
        "If a better long-term language or stack exists but Kewonte does not know it yet, build a bridge path instead of forcing the advanced stack immediately.",
        "Duplicate feature does not always mean useless; compare purpose before removing anything.",
        "For any project issue, classify the request as bug, feature, design improvement, performance problem, learning gap, or architecture decision."
    ],
    "user_learning_style": [
        "Needs exact, step-by-step directions.",
        "Learns best through small projects and repeated variations.",
        "Needs proof requirements and success criteria.",
        "Can get overwhelmed by vague tasks, so recommendations must break down to the smallest next action."
    ]
}

LANGUAGE_KB = {
    "Python": {"best_for": ["automation", "AI/data", "CLI tools", "Flask/FastAPI web backends", "file analysis"], "bridge": ["functions", "files", "JSON", "SQLite", "APIs", "testing"]},
    "JavaScript": {"best_for": ["browser apps", "interactive UI", "PWA", "API frontends", "simple games"], "bridge": ["DOM", "events", "fetch", "localStorage", "modules"]},
    "TypeScript": {"best_for": ["larger web apps", "safer JavaScript", "React/Next apps"], "bridge": ["JavaScript", "types", "interfaces", "React props"]},
    "React": {"best_for": ["component-based web apps", "dashboards", "interactive products"], "bridge": ["components", "props", "state", "lists", "forms", "API calls"]},
    "PowerShell": {"best_for": ["Windows admin", "server checks", "Active Directory scripts", "IT automation"], "bridge": ["cmdlets", "pipelines", "objects", "CSV/JSON export", "scheduled tasks"]},
    "C#": {"best_for": ["Windows desktop apps", "Unity games", ".NET APIs", "enterprise tools"], "bridge": ["classes", "methods", "WinForms/WPF", "Unity basics"]},
    "C++": {"best_for": ["Unreal Engine", "performance-heavy apps", "game engines", "systems programming"], "bridge": ["variables", "functions", "classes", "pointers basics", "Unreal Blueprints first"]},
    "Java": {"best_for": ["Android basics", "enterprise apps", "backend services"], "bridge": ["classes", "OOP", "Spring basics"]},
    "Kotlin": {"best_for": ["modern Android apps"], "bridge": ["Android Studio", "activities", "Compose", "state"]},
    "Swift": {"best_for": ["iPhone/iPad apps"], "bridge": ["Swift basics", "SwiftUI", "views", "state"]},
    "Dart/Flutter": {"best_for": ["cross-platform mobile apps"], "bridge": ["widgets", "state", "forms", "local storage"]},
    "SQL": {"best_for": ["databases", "reports", "data-backed apps"], "bridge": ["tables", "CRUD", "joins", "indexes"]},
    "HTML/CSS": {"best_for": ["web page structure", "layout", "landing pages", "UI practice"], "bridge": ["semantic HTML", "flex", "grid", "responsive design"]},
    "Rust": {"best_for": ["safe systems programming", "performance tools"], "bridge": ["ownership basics", "functions", "structs"]},
    "Go": {"best_for": ["cloud services", "small backend tools", "network services"], "bridge": ["functions", "structs", "HTTP server", "concurrency basics"]},
}

PROJECT_TYPE_DECISIONS = {
    "browser app": {"stacks": ["HTML/CSS/JavaScript", "React later"], "why": "Fastest to test on laptop and phone through a browser."},
    "mobile app": {"stacks": ["React Native", "Flutter", "Kotlin/Swift for native"], "why": "Best when the tool needs phone notifications, camera, microphone, watch, or daily mobile use."},
    "desktop app": {"stacks": ["Python", "C#", "Electron"], "why": "Best for local files, Windows tools, or offline workflows."},
    "cli tool": {"stacks": ["Python", "PowerShell", "Go"], "why": "Best for automation, admin tasks, and repeatable technical utilities."},
    "game": {"stacks": ["JavaScript Canvas for tiny practice", "Unity C#", "Unreal C++"], "why": "Games need an engine path; start small, then bridge to serious tools."},
    "automation script": {"stacks": ["PowerShell", "Python"], "why": "Best for IT workflows, scheduled checks, and repeatable work tasks."},
    "ai/data tool": {"stacks": ["Python", "Flask/FastAPI", "SQLite/PostgreSQL"], "why": "Python has the strongest AI/data ecosystem."},
}

def load_decision_memory() -> Dict[str, Any]:
    if DECISION_MEMORY_FILE.exists():
        try:
            data = json.loads(DECISION_MEMORY_FILE.read_text(encoding="utf-8"))
            merged = DEFAULT_DECISION_MEMORY.copy()
            merged.update(data)
            return merged
        except Exception:
            pass
    DECISION_MEMORY_FILE.write_text(json.dumps(DEFAULT_DECISION_MEMORY, indent=2), encoding="utf-8")
    return DEFAULT_DECISION_MEMORY.copy()

def save_decision_memory(memory: Dict[str, Any]) -> None:
    DECISION_MEMORY_FILE.write_text(json.dumps(memory, indent=2), encoding="utf-8")

def record_adaptive_event(event_type: str, summary: str, details: Dict[str, Any] | None = None) -> None:
    """Store lightweight learning events so KDT OS can adapt over time.
    This is not consciousness. It is evidence-based decision memory.
    """
    memory = load_decision_memory()
    event = {
        "at": datetime.now().isoformat(timespec="seconds"),
        "event_type": event_type,
        "summary": summary,
        "details": details or {},
    }
    events = memory.setdefault("adaptive_events", [])
    events.insert(0, event)
    memory["adaptive_events"] = events[:100]
    # Count patterns that can influence future recommendations.
    counts = memory.setdefault("pattern_counts", {})
    counts[event_type] = counts.get(event_type, 0) + 1
    save_decision_memory(memory)

def adaptive_profile_snapshot() -> Dict[str, Any]:
    memory = load_decision_memory()
    return {
        "rules": memory.get("rules", []),
        "user_learning_style": memory.get("user_learning_style", []),
        "pattern_counts": memory.get("pattern_counts", {}),
        "recent_events": memory.get("adaptive_events", [])[:8],
        "adaptive_note": "KDT OS learns from saved decisions, paths, quest submissions, blockers, and repeated user preferences. It must still label suggestions as suggestions."
    }

def language_kb_snapshot() -> str:
    lines = []
    for name, info in LANGUAGE_KB.items():
        lines.append(f"- {name}: best for {', '.join(info['best_for'])}; bridge skills: {', '.join(info['bridge'])}")
    return "\n".join(lines)

def project_type_snapshot() -> str:
    return "\n".join([f"- {k}: stacks={', '.join(v['stacks'])}; why={v['why']}" for k, v in PROJECT_TYPE_DECISIONS.items()])

def classify_request_type(text: str) -> str:
    """Universal intent classifier. Order matters: specific project/system intents first, broad words later."""
    t = (text or "").lower()
    if any(w in t for w in ["crash", "crashes", "broken", "bug", "error", "traceback", "doesn't work", "not working", "fix"]):
        return "fix_bug"
    if any(w in t for w in ["analyze local", "local project", "project folder", "folder path", "scan folder", "detect languages", "project health", "changes over time", "source manager"]):
        return "add_feature"
    if any(w in t for w in ["verify", "verification", "proof", "evidence", "screenshot", "code submissions", "skill graph"]):
        return "add_feature"
    if any(w in t for w in ["add", "feature", "include", "support", "should be able", "i want kdt os to"]):
        return "add_feature"
    if any(w in t for w in ["ugly", "design", "looks", "ui", "confusing", "off", "cleaner"]):
        return "improve_design"
    if any(w in t for w in ["slow", "performance", "lag", "optimize"]):
        return "optimize"
    if any(w in t for w in ["learn", "teach", "don't understand", "dont understand", "i don't know", "i dont know"]):
        return "learn_skill"
    if any(w in t for w in ["switch", "move to", "convert"]):
        return "switch_platform"
    return "new_or_extend_project"

def redundancy_scan_for_request(problem: str, selected_project: str = "") -> Dict[str, Any]:
    problem_l = (problem or "").lower()
    hits = []
    for p in list_projects():
        name = p.get("project_name", "")
        caps = p.get("latest_capabilities", []) or []
        tech = p.get("latest_technologies", []) or []
        score = 0
        matched = []
        for token in re.findall(r"[a-zA-Z]{4,}", problem_l):
            if token in name.lower():
                score += 3; matched.append(token)
            for c in caps:
                if token in str(c).lower():
                    score += 2; matched.append(str(c))
            for t in tech:
                if token in str(t).lower():
                    score += 1; matched.append(str(t))
        if selected_project and selected_project.lower() == name.lower():
            score += 10; matched.append("selected project")
        if score:
            hits.append({"project": name, "score": score, "matched": sorted(set(matched))[:8], "recommendation": "Review for reuse or extension before starting from scratch."})
    hits = sorted(hits, key=lambda x: x["score"], reverse=True)[:5]
    return {
        "rule": "Duplicate feature does not automatically mean useless. Compare purpose before merging or deleting.",
        "possible_reuse_matches": hits,
        "decision_options": ["Reuse existing project", "Extend existing project", "Start new project for different purpose", "Archive truly redundant duplicate"]
    }


# -----------------------------
# Ollama / AI Layer
# -----------------------------
def load_ai_settings() -> Dict[str, Any]:
    default = {
        "enabled": True,
        "provider": "ollama",
        "model": "llama3.1:8b",
        "reasoning_model": "llama3.1:8b",
        "code_model": "deepseek-coder:latest",
        "vision_model": "llava:latest",
        "auto_pull_models": False,
        "model_pull_policy": "ask_first",
        "host": "http://127.0.0.1:11434",
        "auto_start": True,
        "last_status": "Unknown",
    }
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            default.update(data)
        except Exception:
            pass
    return default


def save_ai_settings(settings: Dict[str, Any]) -> None:
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def load_ai_log() -> Dict[str, Any]:
    default = {
        "last_prompt": "",
        "last_response": "",
        "last_error": "",
        "last_feature": "None yet",
        "last_used_at": "",
        "last_parse_ok": False,
        "last_fallback_used": False,
        "calls": []
    }
    if AI_LOG_FILE.exists():
        try:
            data = json.loads(AI_LOG_FILE.read_text(encoding="utf-8"))
            default.update(data)
        except Exception:
            pass
    return default


def save_ai_log(event: Dict[str, Any]) -> None:
    log = load_ai_log()
    event = dict(event)
    event.setdefault("at", datetime.now().isoformat(timespec="seconds"))
    log["last_prompt"] = event.get("prompt", "")
    log["last_response"] = event.get("response", "")
    log["last_error"] = event.get("error", "")
    log["last_feature"] = event.get("feature", "Unknown")
    log["last_used_at"] = event.get("at")
    log["last_parse_ok"] = bool(event.get("parse_ok", False))
    log["last_fallback_used"] = bool(event.get("fallback_used", False))
    calls = log.setdefault("calls", [])
    calls.insert(0, event)
    log["calls"] = calls[:25]
    AI_LOG_FILE.write_text(json.dumps(log, indent=2), encoding="utf-8")



def ollama_tags(host: str) -> Dict[str, Any] | None:
    try:
        with urllib.request.urlopen(f"{host.rstrip('/')}/api/tags", timeout=1.5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def is_ollama_running(host: str) -> bool:
    return ollama_tags(host) is not None


def start_ollama_server() -> bool:
    """Start Ollama if the ollama command exists. Returns True if a start command was attempted."""
    try:
        kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        subprocess.Popen(["ollama", "serve"], **kwargs)
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


def ensure_ollama_ready(wait_seconds: float = 5.0) -> Dict[str, Any]:
    settings = load_ai_settings()
    host = settings.get("host", "http://127.0.0.1:11434")
    status = {
        "enabled": bool(settings.get("enabled", True)),
        "provider": settings.get("provider", "ollama"),
        "model": settings.get("model", "llama3.1:8b"),
        "host": host,
        "running": False,
        "started": False,
        "available": False,
        "message": "AI disabled or unavailable.",
        "models": [],
    }
    if not status["enabled"]:
        status["message"] = "AI layer is disabled. Core KDT OS still works."
        return status
    tags = ollama_tags(host)
    if tags is None and settings.get("auto_start", True):
        status["started"] = start_ollama_server()
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            tags = ollama_tags(host)
            if tags is not None:
                break
            time.sleep(0.35)
    if tags is not None:
        models = [m.get("name", "") for m in tags.get("models", []) if m.get("name")]
        status.update({"running": True, "available": True, "models": models, "message": "Ollama is running and ready."})
    else:
        status["message"] = "Ollama is not reachable. Install/start Ollama or disable AI layer in AI Settings."
    settings["last_status"] = status["message"]
    save_ai_settings(settings)
    return status


def ollama_generate(prompt: str, system: str = "", temperature: float = 0.2, max_chars: int = 6000, feature: str = "General AI Call") -> Dict[str, Any]:
    status = ensure_ollama_ready(wait_seconds=2.0)
    if not status.get("available"):
        save_ai_log({"feature": feature, "prompt": prompt[:2000], "response": "", "error": status.get("message", "Ollama unavailable."), "parse_ok": False, "fallback_used": True})
        return {"ok": False, "text": "", "error": status.get("message", "Ollama unavailable."), "status": status}
    settings = load_ai_settings()
    payload = {
        "model": settings.get("model", "llama3.1:8b"),
        "prompt": prompt[:max_chars],
        "system": system,
        "stream": False,
        "options": {"temperature": temperature},
    }
    try:
        req = urllib.request.Request(
            f"{settings.get('host', 'http://127.0.0.1:11434').rstrip('/')}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data.get("response", "").strip()
        save_ai_log({"feature": feature, "prompt": prompt[:2000], "response": text[:4000], "error": "", "parse_ok": None, "fallback_used": False})
        return {"ok": True, "text": text, "error": "", "status": status}
    except Exception as exc:
        save_ai_log({"feature": feature, "prompt": prompt[:2000], "response": "", "error": str(exc), "parse_ok": False, "fallback_used": True})
        return {"ok": False, "text": "", "error": str(exc), "status": status}



# -----------------------------
# Model Manager / Vision Helpers (v12)
# -----------------------------
MODEL_CATALOG = {
    "reasoning": {"recommended": "llama3.1:8b", "purpose": "planning, Teach Me Mode, path creation, upgrade reasoning"},
    "code": {"recommended": "deepseek-coder:latest", "purpose": "code review, implementation help, debugging guidance"},
    "vision": {"recommended": "llava:latest", "purpose": "screenshot understanding and visual proof verification"},
    "embedding": {"recommended": "nomic-embed-text", "purpose": "future semantic memory search across projects, quests, and notes"},
    "fast": {"recommended": "llama3.2:3b", "purpose": "quick low-cost summaries and simple tasks"},
}

MODEL_ROLE_CANDIDATES = {
    "vision": ["llama-vision", "llava:latest", "llava", "bakllava"],
    "code": ["deepseek-coder:latest", "deepseek-coder", "codellama", "qwen2.5-coder"],
    "embedding": ["nomic-embed-text", "mxbai-embed-large"],
    "reasoning": ["llama3.1:8b", "llama3.2:3b", "mistral:latest", "mistral", "qwen"],
    "fast": ["llama3.2:3b", "llama3.2", "mistral:latest"],
}

def installed_ollama_models() -> List[str]:
    settings = load_ai_settings()
    tags = ollama_tags(settings.get("host", "http://127.0.0.1:11434")) or {}
    return [m.get("name", "") for m in tags.get("models", []) if m.get("name")]

def model_installed(model_name: str, installed: List[str] | None = None) -> bool:
    installed = installed if installed is not None else installed_ollama_models()
    base = (model_name or "").split(":")[0]
    return any(m == model_name or m.split(":")[0] == base for m in installed)

def first_installed_model(candidates: List[str], installed: List[str]) -> str:
    for candidate in candidates:
        if model_installed(candidate, installed):
            base = candidate.split(":")[0]
            for m in installed:
                if m == candidate or m.split(":")[0] == base:
                    return m
    return ""

def auto_detect_model_roles(save: bool = False) -> Dict[str, Any]:
    installed = installed_ollama_models()
    settings = load_ai_settings()
    detected = {}
    role_to_setting = {"reasoning":"reasoning_model", "code":"code_model", "vision":"vision_model", "embedding":"embedding_model", "fast":"fast_model"}
    for role, setting_key in role_to_setting.items():
        detected_model = first_installed_model(MODEL_ROLE_CANDIDATES.get(role, []), installed)
        configured = settings.get(setting_key, "")
        should_replace = (not configured) or (not model_installed(configured, installed))
        detected[role] = {
            "setting_key": setting_key,
            "configured": configured,
            "detected": detected_model,
            "installed": bool(detected_model),
            "will_use": detected_model if should_replace and detected_model else configured,
            "changed": bool(should_replace and detected_model and detected_model != configured),
        }
        if save and detected[role]["changed"]:
            settings[setting_key] = detected_model
    # Keep legacy primary model aligned with reasoning model when auto detection improves it.
    if save and detected.get("reasoning", {}).get("will_use"):
        settings["model"] = detected["reasoning"]["will_use"]
        save_ai_settings(settings)
        record_adaptive_event("model_roles_auto_detected", "KDT OS auto-assigned Ollama model roles from installed models.", detected)
    return {"installed_models": installed, "roles": detected}

def recommended_model_for_task(task_type: str) -> str:
    settings = load_ai_settings()
    task_type = (task_type or "reasoning").lower()
    if task_type in ("vision", "image", "screenshot"):
        return settings.get("vision_model") or MODEL_CATALOG["vision"]["recommended"]
    if task_type in ("code", "debug", "review"):
        return settings.get("code_model") or MODEL_CATALOG["code"]["recommended"]
    if task_type in ("embedding", "embed", "search"):
        return settings.get("embedding_model") or MODEL_CATALOG["embedding"]["recommended"]
    if task_type in ("fast", "simple"):
        return settings.get("fast_model") or MODEL_CATALOG["fast"]["recommended"]
    return settings.get("reasoning_model") or settings.get("model") or MODEL_CATALOG["reasoning"]["recommended"]

def pull_ollama_model(model_name: str) -> Dict[str, Any]:
    result = {"model": model_name, "ok": False, "message": "", "at": datetime.now().isoformat(timespec="seconds")}
    try:
        completed = subprocess.run(["ollama", "pull", model_name], capture_output=True, text=True, timeout=900)
        result["ok"] = completed.returncode == 0
        result["message"] = (completed.stdout or completed.stderr or "").strip()[-2000:]
    except Exception as exc:
        result["message"] = str(exc)
    log = []
    if MODEL_LOG_FILE.exists():
        try: log = json.loads(MODEL_LOG_FILE.read_text(encoding="utf-8"))
        except Exception: log = []
    log.insert(0, result)
    MODEL_LOG_FILE.write_text(json.dumps(log[:25], indent=2), encoding="utf-8")
    return result

def model_manager_snapshot() -> Dict[str, Any]:
    # Auto-repair missing/invalid configured roles using installed models.
    auto = auto_detect_model_roles(save=True)
    installed = installed_ollama_models()
    settings = load_ai_settings()
    rows = []
    for task, info in MODEL_CATALOG.items():
        configured = recommended_model_for_task(task)
        rows.append({
            "task": task,
            "purpose": info["purpose"],
            "recommended": info["recommended"],
            "configured": configured,
            "installed": model_installed(configured, installed),
        })
    pull_log = []
    if MODEL_LOG_FILE.exists():
        try: pull_log = json.loads(MODEL_LOG_FILE.read_text(encoding="utf-8"))
        except Exception: pass
    return {"installed_models": installed, "settings": settings, "rows": rows, "pull_log": pull_log, "auto_detect": auto, "adaptive_profile": adaptive_profile_snapshot()}

def ollama_generate_with_model(prompt: str, model: str, system: str = "", temperature: float = 0.2, feature: str = "Model Manager Call") -> Dict[str, Any]:
    status = ensure_ollama_ready(wait_seconds=2.0)
    if not status.get("available"):
        return {"ok": False, "text": "", "error": status.get("message", "Ollama unavailable."), "status": status}
    settings = load_ai_settings()
    payload = {"model": model, "prompt": prompt, "system": system, "stream": False, "options": {"temperature": temperature}}
    try:
        req = urllib.request.Request(f"{settings.get('host','http://127.0.0.1:11434').rstrip('/')}/api/generate", data=json.dumps(payload).encode("utf-8"), headers={"Content-Type":"application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data.get("response", "").strip()
        save_ai_log({"feature": feature, "prompt": prompt[:2000], "response": text[:4000], "error": "", "parse_ok": None, "fallback_used": False})
        return {"ok": True, "text": text, "error": "", "status": status}
    except Exception as exc:
        save_ai_log({"feature": feature, "prompt": prompt[:2000], "response": "", "error": str(exc), "parse_ok": False, "fallback_used": True})
        return {"ok": False, "text": "", "error": str(exc), "status": status}

def ollama_vision_describe(image_path: Path, prompt: str) -> Dict[str, Any]:
    status = ensure_ollama_ready(wait_seconds=2.0)
    settings = load_ai_settings()
    model = settings.get("vision_model", "llava:latest")
    if not model_installed(model):
        auto = auto_detect_model_roles(save=True)
        settings = load_ai_settings()
        model = settings.get("vision_model", model)
    if not model_installed(model):
        return {"ok": False, "text": "", "error": f"No installed vision model found. Install llama-vision, llava, or bakllava from Model Manager first.", "model": model}
    try:
        image_b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        payload = {"model": model, "prompt": prompt, "images": [image_b64], "stream": False, "options": {"temperature": 0.1}}
        req = urllib.request.Request(f"{settings.get('host','http://127.0.0.1:11434').rstrip('/')}/api/generate", data=json.dumps(payload).encode("utf-8"), headers={"Content-Type":"application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data.get("response", "").strip()
        save_ai_log({"feature": "Vision Screenshot Verification", "prompt": prompt[:2000], "response": text[:4000], "error": "", "parse_ok": True, "fallback_used": False})
        return {"ok": True, "text": text, "error": "", "model": model}
    except Exception as exc:
        return {"ok": False, "text": "", "error": str(exc), "model": model}


def extract_json_object(text: str) -> Dict[str, Any] | None:
    if not text:
        return None
    candidates = []
    stripped = text.strip()
    candidates.append(stripped)
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if match:
        candidates.append(match.group(1))
    match = re.search(r"(\{.*\})", text, flags=re.DOTALL)
    if match:
        candidates.append(match.group(1))
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except Exception:
            continue
    return None





def _clean_ai_line(line: str) -> str:
    """Remove markdown bullets, numbering, quotes, and bold markers without destroying content."""
    line = (line or "").strip()
    # Remove common markdown wrappers and accidental quote markers from LLM output.
    line = line.replace("**", "").replace("__", "")
    line = line.strip("\"'` ")
    line = re.sub(r"^[-*•]+\s*", "", line)
    line = re.sub(r"^>\s*", "", line)
    line = re.sub(r"^\d+[.)]\s*", "", line)
    line = line.strip("\"'` ")
    return line.strip()


def _heading_name(line: str) -> str | None:
    """Return a normalized heading name for common Ollama/plain-text section headers.

    This intentionally accepts many label variations so KDT OS can use good
    plain-English Ollama responses instead of failing parse over wording.
    """
    cleaned = _clean_ai_line(line).lower().strip().strip(":").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    aliases = {
        "goal": "goal",
        "objective": "goal",
        "purpose": "goal",
        "mission": "goal",
        "what to do": "what_to_build",
        "what you must build": "what_to_build",
        "what to build": "what_to_build",
        "what you will build": "what_to_build",
        "build": "what_to_build",
        "task": "what_to_build",
        "assignment": "what_to_build",
        "next smallest action": "what_to_build",
        "exact steps": "steps",
        "steps": "steps",
        "step-by-step instructions": "steps",
        "step by step instructions": "steps",
        "instructions": "steps",
        "procedure": "steps",
        "requirements": "requirements",
        "required features": "requirements",
        "what is required": "requirements",
        "success criteria": "success_criteria",
        "done when": "success_criteria",
        "completion criteria": "success_criteria",
        "proof needed": "proof",
        "proof required": "proof",
        "proof": "proof",
        "verification": "proof",
        "evidence": "proof",
        "evidence needed": "proof",
        "difficulty": "difficulty",
        "difficulty level": "difficulty",
        "estimated time": "estimated_time",
        "time estimate": "estimated_time",
        "time needed": "estimated_time",
    }
    return aliases.get(cleaned)


def parse_plain_ai_breakdown(text: str) -> Dict[str, Any]:
    """Turn a normal LLM response into the fields KDT OS needs.

    Ollama often gives useful Markdown instead of JSON. This parser accepts many
    heading variations such as Goal, What to do, Exact Steps, Instructions, and
    Proof Needed. It also handles numbered steps under a heading.
    """
    sections: Dict[str, List[str]] = {
        "goal": [],
        "what_to_build": [],
        "requirements": [],
        "steps": [],
        "success_criteria": [],
        "proof": [],
        "difficulty": [],
        "estimated_time": [],
    }
    current = None
    heading_pattern = re.compile(
        r"^(goal|objective|purpose|mission|what to do|what you must build|what to build|what you will build|build|task|assignment|next smallest action|exact steps|steps|step-by-step instructions|step by step instructions|instructions|procedure|requirements|required features|what is required|success criteria|done when|completion criteria|proof needed|proof required|proof|verification|evidence|evidence needed|difficulty|difficulty level|estimated time|time estimate|time needed)\s*:\s*(.*)$",
        flags=re.I,
    )
    for raw in (text or "").splitlines():
        line = _clean_ai_line(raw)
        if not line:
            continue
        m = heading_pattern.match(line)
        if m:
            current = _heading_name(m.group(1))
            value = _clean_ai_line(m.group(2))
            if value and current:
                sections[current].append(value)
            continue
        heading = _heading_name(line)
        if heading:
            current = heading
            continue
        if current:
            sections[current].append(line)

    all_lines = [_clean_ai_line(ln) for ln in (text or "").splitlines() if _clean_ai_line(ln)]
    if not any(sections.values()):
        sections["steps"] = [ln for ln in all_lines if len(ln) < 240][:8]
    # If the model only gave Goal + Steps, infer build from first step.
    if not sections["what_to_build"] and sections["steps"]:
        sections["what_to_build"] = [sections["steps"][0]]
    return sections



def plain_sections_are_usable(sections: Dict[str, List[str]]) -> bool:
    """A parse is useful if it can produce at least a goal/build plus steps/proof."""
    if not sections:
        return False
    has_goal_or_build = bool(sections.get("goal") or sections.get("what_to_build"))
    has_action = bool(sections.get("steps") or sections.get("requirements") or sections.get("proof"))
    return has_goal_or_build and has_action


def coerce_ai_breakdown_from_text(text: str, quest: Dict[str, Any], obstacle: str) -> Dict[str, Any] | None:
    """Use useful Ollama plain text as a real quest breakdown.

    This is intentionally not called a fallback anymore. If Ollama gives a good
    plain-English response, KDT OS extracts Goal, Build, Steps, Success Criteria,
    and Proof instead of replacing it with a vague template.
    """
    cleaned = (text or "").strip()
    if len(cleaned) < 40:
        return None

    skill = quest.get("skill", "the skill")
    sections = parse_plain_ai_breakdown(cleaned)

    goal_text = " ".join(sections.get("goal") or []) or f"Break down the blocker: {obstacle}"
    what_to_build = " ".join(sections.get("what_to_build") or [])
    steps = sections.get("steps") or []
    requirements = sections.get("requirements") or []
    success = sections.get("success_criteria") or []
    proof = sections.get("proof") or []

    # Make sure each field is actually useful and specific.
    if not what_to_build:
        # Use a short plain-language action from the AI response, not the whole response.
        what_to_build = steps[0] if steps else f"Complete the next smallest step for {skill}: {obstacle}"
    if not steps:
        steps = [
            f"Read the AI-generated explanation for: {obstacle}",
            "Complete the smallest action it describes.",
            "Write one sentence explaining what changed or what clicked.",
            "Return to the parent quest."
        ]
    if not requirements:
        requirements = [
            "Follow the AI-generated next smallest step.",
            "Create visible proof that you did the step.",
            "Write one short explanation in your own words."
        ]
    if not success:
        success = [
            "Your proof matches the blocker you entered.",
            "Your explanation is specific and in your own words.",
            "You are less confused and can return to the parent quest."
        ]
    if not proof:
        proof = [
            "Upload a ZIP, screenshot, or written proof that matches the step.",
            "Include a short explanation of what you understood."
        ]

    # Keep title clean and avoid nested "Micro Quest" wording.
    title_obstacle = obstacle.strip() or skill
    if len(title_obstacle) > 55:
        title_obstacle = title_obstacle[:52].rstrip() + "..."
    title = f"Quest Breakdown: {skill} - {title_obstacle}"

    return {
        "title": title,
        "goal": goal_text,
        "what_to_build": what_to_build,
        "requirements": requirements[:8],
        "success_criteria": success[:8],
        "steps": steps[:10],
        "proof": proof[:6],
        "verification_patterns": [],
        "ai_generated": True,
        "ai_parse_mode": "sectioned_plain_text",
        "ai_raw_response": cleaned[:4000],
        "difficulty": "Beginner",
        "estimated_time": "5-20 minutes"
    }

def ai_practice_quest_from_teach(skill: str, confusion: str) -> Dict[str, Any] | None:
    """Create an exact quest from Teach Me Mode using Ollama, then parse it into KDT OS fields."""
    skill = normalize_skill(skill)
    prompt = f"""
You are KDT OS. Kewonte needs exact instructions and does not want vague tasks.
Create ONE beginner-friendly practice quest for this topic.

Skill/topic: {skill}
User blocker: {confusion}

Return plain text with these exact section labels if possible:
Goal:
What To Build:
Difficulty:
Estimated Time:
Requirements:
Exact Steps:
Success Criteria:
Proof Needed:

Rules:
- Make the task small enough to finish today.
- Give exact files, actions, or written proof needed.
- Do not be generic.
- If the topic is conceptual, use written answers or screenshot proof instead of forcing a ZIP.
"""
    result = ollama_generate(prompt, system="You are KDT OS Quest Generator. Be exact and beginner-friendly.", temperature=0.2, feature="Teach Me Quest Generator")
    raw = result.get("text", "")
    if not result.get("ok") or not raw.strip():
        save_ai_log({"feature": "Teach Me Quest Generator", "prompt": prompt[:2000], "response": raw[:4000], "error": result.get("error") or "AI unavailable.", "parse_ok": False, "fallback_used": True})
        return None
    fake_parent = {"skill": skill, "title": f"Teach Me: {skill}", "what_to_build": confusion}
    parsed = coerce_ai_breakdown_from_text(raw, fake_parent, confusion)
    if not parsed:
        save_ai_log({"feature": "Teach Me Quest Generator", "prompt": prompt[:2000], "response": raw[:4000], "error": "AI response was not structured enough for a quest.", "parse_ok": False, "fallback_used": True})
        return None
    sections = parse_plain_ai_breakdown(raw)
    parsed["title"] = f"Teach Me Quest: {skill}"
    parsed["difficulty"] = " ".join(sections.get("difficulty") or []) or parsed.get("difficulty", "Beginner")
    parsed["estimated_time"] = " ".join(sections.get("estimated_time") or []) or parsed.get("estimated_time", "15-45 minutes")
    parsed["ai_generated"] = True
    parsed["ai_parse_mode"] = "teach_me_sectioned_plain_text"
    parsed["ai_raw_response"] = raw[:4000]
    save_ai_log({"feature": "Teach Me Quest Generator", "prompt": prompt[:2000], "response": raw[:4000], "error": "AI generated an exact Teach Me quest.", "parse_ok": True, "fallback_used": False})
    return parsed

def ai_teach_response(skill: str, confusion: str, known: Dict[str, Any] | None) -> Dict[str, Any]:
    skill = normalize_skill(skill)
    evidence = "No uploaded project evidence yet."
    if known:
        evidence = f"Status: {known.get('status')}. Projects: {', '.join(known.get('projects', []))}. Confidence note: {known.get('confidence_label', '')}"
    prompt = f"""
You are KDT OS Teach Me Mode for Kewonte. He needs exact instructions and gets frustrated by vague tasks.
Skill/topic: {skill}
Blocker: {confusion}
Evidence KDT OS has: {evidence}

Give a practical explanation and the next smallest action. Do not be generic. Keep it beginner-friendly.
Return JSON only with these keys:
{{
  "plain_explanation": "...",
  "why_it_matters": "...",
  "next_smallest_action": "...",
  "practice_idea": "...",
  "questions_to_check_understanding": ["...", "...", "..."]
}}
"""
    result = ollama_generate(prompt, system="Return strict JSON only. No markdown.", feature="Teach Me Mode")
    parsed = extract_json_object(result.get("text", "")) if result.get("ok") else None
    if not parsed:
        return {
            "available": False,
            "error": result.get("error") or "AI response could not be parsed.",
            "plain_explanation": explain(skill, f"KDT OS does not have much evidence for {skill} yet."),
            "why_it_matters": "This skill matters because it may be required for the project or goal you are working toward.",
            "next_smallest_action": "Create an exact practice quest so KDT OS can guide you step by step.",
            "practice_idea": "Use the built-in quest generator.",
            "questions_to_check_understanding": [],
            "raw": result.get("text", ""),
        }
    parsed["available"] = True
    parsed["error"] = ""
    return parsed


def ai_breakdown_template(quest: Dict[str, Any], obstacle: str) -> Dict[str, Any] | None:
    prompt = f"""
You are KDT OS. Break a quest into a smaller Quest Breakdown for Kewonte.
Rules:
- The breakdown MUST be smaller than the parent quest.
- It MUST directly support the parent quest.
- It MUST include exact instructions, required files or written proof, success criteria, and proof requirements.
- Do not create a random unrelated exercise.
- If possible, make it doable in 5 to 20 minutes.

Parent quest title: {quest.get('title')}
Parent skill: {quest.get('skill')}
Parent build: {quest.get('what_to_build')}
Parent requirements: {json.dumps(quest.get('requirements', []))}
User obstacle: {obstacle}

Return JSON only with keys:
{{
  "title": "Quest Breakdown: ...",
  "goal": "...",
  "what_to_build": "...",
  "requirements": ["..."],
  "success_criteria": ["..."],
  "steps": ["..."],
  "proof": ["..."],
  "verification_patterns": ["optional regex strings for code proof"]
}}
"""
    result = ollama_generate(prompt, system="Return strict JSON only. No markdown.", feature="Quest Breakdown")
    raw_text = result.get("text", "")
    parsed = extract_json_object(raw_text) if result.get("ok") else None
    if parsed and parsed.get("title") and parsed.get("steps"):
        parsed["ai_generated"] = True
        parsed["ai_parse_mode"] = "json"
        parsed["ai_raw_response"] = raw_text[:4000]
        save_ai_log({"feature": "Quest Breakdown", "prompt": prompt[:2000], "response": raw_text[:4000], "error": "", "parse_ok": True, "fallback_used": False})
        return parsed
    coerced = coerce_ai_breakdown_from_text(raw_text, quest, obstacle) if result.get("ok") else None
    if coerced:
        save_ai_log({"feature": "Quest Breakdown", "prompt": prompt[:2000], "response": raw_text[:4000], "error": "AI returned plain text; KDT OS extracted structured sections into a breakdown.", "parse_ok": True, "fallback_used": False})
        return coerced
    save_ai_log({"feature": "Quest Breakdown", "prompt": prompt[:2000], "response": raw_text[:4000], "error": result.get("error") or "AI unavailable or unusable. Template fallback used.", "parse_ok": False, "fallback_used": True})
    return None




def micro_breakdown_for(skill: str, obstacle: str, parent: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic high-quality micro quests when AI is unavailable or vague.

    Micro quests must be just as strong as regular quests: exact, tiny,
    verifiable, and tied back to the parent quest.
    """
    skill = normalize_skill(skill)
    obstacle_text = obstacle or "I do not know where to start."
    if skill == "SQLite":
        return {
            "title": "Rows and Columns Before SQLite",
            "type": "Quest Breakdown",
            "goal": "Understand the table idea before writing database code.",
            "what_to_build": "A plain text file named table_practice.txt with a 3-column table: Name, Age, Favorite Food.",
            "requirements": ["Create folder sqlite_micro_table", "Create table_practice.txt", "Add columns Name, Age, Favorite Food", "Add exactly 3 rows", "Write one sentence defining row and column"],
            "success_criteria": ["table_practice.txt exists", "Three columns are visible", "Three rows are present", "Explanation mentions row and column"],
            "steps": ["Create folder sqlite_micro_table", "Open Notepad or VS Code", "Create table_practice.txt", "Type the header: Name | Age | Favorite Food", "Add three people as rows", "Under the table write: A row is...", "Under that write: A column is...", "Save the file", "Upload the folder or screenshot", "Return to the parent SQLite quest"],
            "proof": ["Upload table_practice.txt or a screenshot", "Answer: which part of your table would become a SQLite column?"],
            "verification_patterns": ["Name", "Age", "Favorite Food"],
            "difficulty": "Starter",
            "estimated_time": "5-10 minutes"
        }
    if skill in ("API / Routes", "JavaScript"):
        return {
            "title": "Button Changes Text Before API Calls",
            "type": "Quest Breakdown",
            "goal": "Prove you understand browser events before adding API requests.",
            "what_to_build": "A tiny browser page with one button that changes one sentence when clicked.",
            "requirements": ["Create folder button_text_micro", "Create index.html", "Create script.js", "Add button id actionBtn", "Add paragraph id result", "Use addEventListener", "Change result.textContent"],
            "success_criteria": ["index.html exists", "script.js exists", "Button is visible", "Clicking changes text", "addEventListener is used"],
            "steps": ["Create folder button_text_micro", "Create index.html", "Create script.js", "Link script.js in index.html", "Add a button with id actionBtn", "Add a paragraph with id result", "In script.js select both elements", "Add a click event listener", "Inside it set result.textContent to 'Button works'", "Open index.html and click the button", "Upload ZIP"],
            "proof": ["Upload ZIP with index.html and script.js", "Answer: what line changes the visible text?"],
            "verification_patterns": [r"addEventListener", r"textContent", r"actionBtn", r"result"],
            "difficulty": "Starter",
            "estimated_time": "10-15 minutes"
        }
    if skill == "Testing":
        return {
            "title": "One Assert Before Full Testing",
            "type": "Quest Breakdown",
            "goal": "Understand what a test proves before testing a whole app.",
            "what_to_build": "A file named test_math.py with one function that asserts 2 + 2 equals 4.",
            "requirements": ["Create folder testing_micro", "Create test_math.py", "Write one test function", "Use assert", "Run pytest or explain how you would run it"],
            "success_criteria": ["test_math.py exists", "def test_ appears", "assert appears", "The expected result is clear"],
            "steps": ["Create folder testing_micro", "Create test_math.py", "Type def test_addition():", "Under it type assert 2 + 2 == 4", "Install pytest if needed", "Run python -m pytest", "Copy the terminal result or screenshot it", "Write one sentence explaining what the assert checked", "Return to the parent testing quest"],
            "proof": ["Upload test_math.py or ZIP", "Include pytest output or screenshot", "Answer: what would make this test fail?"],
            "verification_patterns": [r"def test_", r"assert"],
            "difficulty": "Starter",
            "estimated_time": "5-10 minutes"
        }
    if skill == "Python":
        return {
            "title": "Print One Variable Before Python Functions",
            "type": "Quest Breakdown",
            "goal": "Prove you can create a value and display it before building larger Python logic.",
            "what_to_build": "A file named hello_value.py that stores your name in a variable and prints it in a sentence.",
            "requirements": ["Create folder python_micro_variable", "Create hello_value.py", "Create variable name", "Print a sentence using that variable", "Run the file"],
            "success_criteria": ["hello_value.py exists", "A variable is assigned", "print() is used", "Terminal output shows the sentence"],
            "steps": ["Create folder python_micro_variable", "Create hello_value.py", "Type name = 'Kewonte'", "Type print('Hello, ' + name)", "Open terminal in the folder", "Run python hello_value.py", "Confirm the sentence appears", "Take screenshot or copy output", "Return to the parent Python quest"],
            "proof": ["Upload hello_value.py or ZIP", "Include screenshot or copied terminal output", "Answer: what is the variable name?"],
            "verification_patterns": [r"name\s*=", r"print\("],
            "difficulty": "Starter",
            "estimated_time": "5-10 minutes"
        }
    if skill == "Health Monitoring":
        return {
            "title": "One OK/WARNING Check",
            "type": "Quest Breakdown",
            "goal": "Understand health monitoring by making one tiny check produce OK or WARNING.",
            "what_to_build": "A file named one_check.py that checks if a fake CPU value is above 80 and prints OK or WARNING.",
            "requirements": ["Create folder health_micro_check", "Create one_check.py", "Create variable cpu_usage", "Use if/else", "Print OK or WARNING"],
            "success_criteria": ["one_check.py exists", "cpu_usage variable exists", "if statement exists", "OK or WARNING prints"],
            "steps": ["Create folder health_micro_check", "Create one_check.py", "Type cpu_usage = 85", "Write if cpu_usage > 80:", "Print 'WARNING: CPU high'", "Add else and print 'OK: CPU normal'", "Run python one_check.py", "Change cpu_usage to 25 and run again", "Write what changed", "Return to the parent health quest"],
            "proof": ["Upload one_check.py or ZIP", "Include screenshot or copied output from both 85 and 25", "Answer: why did one run show WARNING?"],
            "verification_patterns": [r"cpu_usage", r"if .*80", r"WARNING", r"OK"],
            "difficulty": "Starter",
            "estimated_time": "10-15 minutes"
        }
    return {
        "title": f"Smallest First Proof: {skill}",
        "type": "Quest Breakdown",
        "goal": f"Break the blocker into one visible proof for {skill}.",
        "what_to_build": f"A tiny proof folder named {slugify(skill)}_micro_proof with README.md and one artifact showing the smallest part you understand.",
        "requirements": ["Create the micro proof folder", "Create README.md", "Create one visible artifact", "Write what confused you", "Write what you now understand"],
        "success_criteria": ["README.md exists", "One artifact exists", "Explanation is specific"],
        "steps": ["Create the micro proof folder", "Create README.md", "Write the blocker at the top", "Create one tiny artifact related to the skill", "Open or run the artifact", "Write one sentence explaining what worked", "Upload proof", "Return to the parent quest"],
        "proof": ["Upload ZIP or screenshot", "Answer: what did this prove?"],
        "verification_patterns": [],
        "difficulty": "Starter",
        "estimated_time": "5-15 minutes"
    }

def ai_evaluate_submission(quest: Dict[str, Any], submission: Dict[str, Any], text_blob: str, reflection: str) -> Dict[str, Any]:
    prompt = f"""
You are KDT OS Quest Evaluator. Be honest but encouraging. Kewonte needs exact feedback.
Quest title: {quest.get('title')}
Skill: {quest.get('skill')}
What he had to build: {quest.get('what_to_build')}
Requirements: {json.dumps(quest.get('requirements', []))}
Success criteria: {json.dumps(quest.get('success_criteria', []))}
Rule-check score: {submission.get('score')}%
Rule-check missing patterns: {json.dumps(submission.get('missing_patterns', []))}
User reflection/explanation: {reflection or 'No reflection entered.'}
Project text sample:
{text_blob[:3500]}

Evaluate whether the work seems legitimate and useful for learning. Return JSON only:
{{
  "build_verification": 0-100,
  "understanding_verification": 0-100,
  "verdict": "Completed" or "Needs Revision" or "Needs Explanation",
  "what_worked": ["..."],
  "what_is_missing": ["..."],
  "next_exact_step": "...",
  "questions_to_answer": ["...", "..."]
}}
"""
    result = ollama_generate(prompt, system="Return strict JSON only. No markdown.", temperature=0.1, max_chars=7000, feature="Quest Verification")
    parsed = extract_json_object(result.get("text", "")) if result.get("ok") else None
    if not parsed:
        return {"available": False, "error": result.get("error") or "AI evaluation unavailable.", "raw": result.get("text", "")}
    parsed["available"] = True
    parsed["error"] = ""
    return parsed


SUPPORTED_TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json", ".md", ".txt", ".yml", ".yaml",
    ".toml", ".ini", ".cfg", ".bat", ".ps1", ".sh", ".sql", ".env", ".gitignore"
}

IGNORE_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "env", "dist", "build", ".next", ".pytest_cache", ".mypy_cache", ".idea", ".vscode"}

TECH_RULES = {
    "Flask": [r"from flask import", r"import flask", r"Flask\("],
    "FastAPI": [r"from fastapi import", r"FastAPI\("],
    "Django": [r"django", r"manage\.py"],
    "SQLite": [r"sqlite3", r"\.sqlite", r"\.db", r"CREATE TABLE"],
    "SQLAlchemy": [r"sqlalchemy", r"create_engine"],
    "JavaScript": [r"addEventListener", r"querySelector", r"document\.getElementById", r"fetch\("],
    "React": [r"from ['\"]react['\"]", r"useState", r"\.jsx$", r"\.tsx$", r"ReactDOM", r"createRoot"],
    "Python": [r"\.py$", r"def ", r"class "],
    "PowerShell": [r"\.ps1$", r"Get-", r"Set-", r"New-"],
    "HTML/CSS": [r"<html", r"<body", r"\.css$", r"display:\s*flex"],
    "API / Routes": [r"@app\.route", r"@router\.", r"fetch\(", r"axios", r"requests\.get"],
    "GitHub/Versioning": [r"README", r"\.gitignore"],
}

CAPABILITY_RULES = {
    "Dashboard/UI": [r"dashboard", r"index\.html", r"render_template", r"<button", r"<form"],
    "Task Management": [r"task", r"todo", r"checklist", r"completed", r"status"],
    "Project Tracking": [r"project", r"milestone", r"roadmap", r"progress"],
    "Idea Capture": [r"idea", r"capture", r"vault", r"inbox"],
    "Knowledge Base": [r"knowledge", r"note", r"lesson", r"memory", r"wiki"],
    "Journal/Reflection": [r"journal", r"reflection", r"review", r"mood"],
    "Ticket System": [r"ticket", r"issue", r"incident", r"root cause", r"resolution"],
    "Evidence Collection": [r"evidence", r"screenshot", r"attachment", r"proof"],
    "Health Monitoring": [r"health", r"inspect", r"scan", r"diagnostic", r"status"],
    "Repair Planning": [r"repair", r"fix", r"backup", r"restore", r"patch"],
    "Authentication/Login": [r"login", r"logout", r"password", r"session", r"auth"],
    "Database Storage": [r"sqlite", r"database", r"db\.execute", r"CREATE TABLE", r"INSERT INTO"],
    "Notifications/Reminders": [r"reminder", r"notify", r"notification", r"smtp", r"email"],
    "Learning/Practice": [r"practice", r"drill", r"quiz", r"lesson", r"mastery", r"quest"],
    "File Handling": [r"open\(", r"read_text", r"write_text", r"shutil", r"zipfile", r"os\.walk"],
    "Automation/Scheduling": [r"schedule", r"cron", r"interval", r"datetime", r"timedelta"],
}

RISK_RULES = {
    "Hardcoded secret/key": [r"secret_key\s*=\s*[\"'][^\"']+", r"api_key\s*=\s*[\"'][^\"']+", r"password\s*=\s*[\"'][^\"']+"],
    "Debug mode enabled": [r"debug\s*=\s*True"],
    "Broad exception handling": [r"except Exception", r"except:"],
    "No tests detected": [],
}

EXPLANATIONS = {
    "Health Score": "A quick quality estimate based on detected risks. It is not a final grade. It tells you whether the project looks stable enough to keep building or needs cleanup first.",
    "Files": "How many files the analyzer found after ignoring folders like .git, node_modules, and virtual environments.",
    "Functions": "How many Python functions were detected. More functions usually means the project has more behavior and more pieces to understand.",
    "Routes": "How many Flask/FastAPI-style web routes were detected. A route usually means a page or API endpoint users can interact with.",
    "Broad exception handling": "The code catches errors too generally, usually with except Exception or bare except. This can hide real problems and make debugging harder. It does not mean the app is broken, but it means future repairs may be harder to trust.",
    "No tests detected": "The analyzer did not find obvious test files. This means the project may work, but it has no automatic proof that it still works after changes.",
    "Hardcoded secret/key": "A password, API key, or secret may be written directly in the code. That is risky if the project is shared or uploaded to GitHub.",
    "Debug mode enabled": "Debug mode is useful while learning, but should not be used in a real public deployment because it can expose sensitive details.",
    "Flask": "A Python web framework. If this is detected, the project probably has pages, routes, forms, or a local web dashboard.",
    "SQLite": "A lightweight database stored in a local file. Useful for personal apps because it does not require a separate database server.",
    "Python": "A general-purpose programming language. In your projects, it usually powers backend logic, automation, file scanning, or data processing.",
    "JavaScript": "Browser-side code used to make pages interactive, respond to clicks, update the screen, and handle dynamic UI behavior.",
    "React": "A JavaScript library for building reusable interface pieces called components. React is useful when a page has many changing parts.",
    "HTML/CSS": "The structure and styling of a web page. HTML creates the content; CSS controls how it looks.",
    "PowerShell": "Windows automation scripting. Useful for IT support, health checks, setup scripts, and admin tasks.",
    "API / Routes": "A way for apps to request or send data. Routes are endpoints your app exposes; API calls are requests your app makes to another service.",
    "Dashboard/UI": "The project has visible screens, forms, buttons, or dashboard pages. This means it is meant for a person to use, not just run silently.",
    "Task Management": "The project likely tracks tasks, statuses, checklists, or completions.",
    "Project Tracking": "The project likely stores project progress, milestones, roadmap items, or build status.",
    "Knowledge Base": "The project likely stores lessons, notes, memory, documentation, or reusable knowledge.",
    "Ticket System": "The project likely manages issues, incidents, root causes, resolutions, or support tickets.",
    "Health Monitoring": "The project likely checks whether something is working correctly, scans for issues, or reports status.",
    "Repair Planning": "The project likely suggests fixes, repairs files, creates backups, or plans recovery steps.",
    "Evidence Collection": "The project likely saves screenshots, attachments, proof, logs, or supporting evidence.",
    "Learning/Practice": "The project likely includes drills, lessons, quests, mastery tracking, or repeated practice.",
    "File Handling": "The project reads, writes, moves, scans, or extracts files. This is a major skill for tools like analyzers and automation apps.",
}

SKILL_MAP = {
    "Flask": ["Build routes", "Handle forms", "Render templates", "Create a dashboard"],
    "SQLite": ["Create tables", "Insert records", "Query records", "Update records", "Delete records"],
    "Python": ["Functions", "File scanning", "Error handling", "JSON reports"],
    "JavaScript": ["DOM selection", "Button clicks", "Input events", "Local storage", "fetch()"],
    "React": ["Components", "useState", "Props", "Lists with map()", "Search/filter UI"],
    "HTML/CSS": ["Page layout", "Cards", "Forms", "Responsive design"],
    "File Handling": ["Read files", "Write files", "Analyze folders", "Extract ZIPs"],
    "Health Monitoring": ["Create checks", "Score results", "Show warnings", "Recommend fixes"],
    "Task Management": ["Add tasks", "Mark complete", "Filter status", "Save progress"],
    "Learning/Practice": ["Create drills", "Track attempts", "Repeat weak concepts", "Show mastery"],
    "API / Routes": ["Call an API", "Read JSON", "Show data", "Handle errors"],
}

# Detailed quest templates. These are intentionally specific because Kewonte needs exact instructions.
PRACTICE_TEMPLATES = {
    "File Handling": {
        "title": "Mini File Scanner",
        "type": "Practice Quest",
        "goal": "Practice scanning a folder and summarizing what files are inside.",
        "what_to_build": "A Python command-line tool that scans a folder path and creates a summary report of file types.",
        "requirements": ["Create app.py", "Ask the user for a folder path", "Loop through files in the folder", "Count file extensions", "Print total files", "Save summary to report.json"],
        "success_criteria": ["app.py exists", "os.walk or pathlib is used", "report.json is created", "file extension counts appear in the output"],
        "steps": ["Create a new folder named mini_file_scanner", "Create app.py", "Write code to ask for a folder path", "Scan that folder", "Count file extensions", "Print the result", "Save the result to report.json", "Create README.md explaining how to run it"],
        "proof": ["Upload a ZIP of the project folder", "Include app.py", "Include report.json", "Include README.md"],
        "verification_patterns": [r"os\.walk", r"Path\(", r"\.suffix", r"json\.dump", r"report\.json"],
    },
    "SQLite": {
        "title": "Workout Database CRUD App",
        "type": "Practice Quest",
        "goal": "Practice saving, reading, updating, and deleting records in SQLite.",
        "what_to_build": "A small Python app that stores workouts with exercise name, sets, reps, and date.",
        "requirements": ["Create a workouts table", "Add a workout", "View all workouts", "Edit one workout", "Delete one workout"],
        "success_criteria": ["CREATE TABLE exists", "INSERT INTO exists", "SELECT exists", "UPDATE exists", "DELETE exists"],
        "steps": ["Create a folder named workout_database_crud", "Create app.py", "Import sqlite3", "Create workouts table with id, exercise, sets, reps, date", "Add a menu with choices 1 Add, 2 View, 3 Edit, 4 Delete, 5 Exit", "Make each choice work", "Create README.md with run instructions"],
        "proof": ["Upload project ZIP", "Include app.py", "Include README.md", "Include the .db file if one is created"],
        "verification_patterns": [r"sqlite3", r"CREATE TABLE", r"INSERT INTO", r"SELECT", r"UPDATE", r"DELETE"],
    },
    "Flask": {
        "title": "One Page Flask Goal Tracker",
        "type": "Practice Quest",
        "goal": "Practice routes, forms, templates, and saving a simple record.",
        "what_to_build": "A tiny Flask web app where you can add a goal and see all saved goals on the page.",
        "requirements": ["Create app.py", "Create templates/index.html", "Create a route for /", "Create a form with goal name", "Save submitted goals in a list or SQLite", "Display submitted goals"],
        "success_criteria": ["Flask is imported", "@app.route('/') exists", "render_template is used", "A form exists", "Submitted item appears on page"],
        "steps": ["Create folder flask_goal_tracker", "Create app.py", "Create templates folder", "Create index.html", "Add route for /", "Add form", "Handle POST request", "Show saved goals", "Create requirements.txt"],
        "proof": ["Upload ZIP", "Include app.py", "Include templates/index.html", "Include requirements.txt", "Include README.md"],
        "verification_patterns": [r"from flask import", r"@app\.route", r"render_template", r"request\.form", r"<form"],
    },
    "JavaScript": {
        "title": "API Weather Lookup App",
        "type": "Refresh Quest",
        "goal": "Practice fetch(), JSON data, button events, and DOM updates.",
        "what_to_build": "A small web app where the user types a city name, clicks a button, and sees weather data appear on the page.",
        "requirements": ["Create index.html", "Create style.css", "Create script.js", "Add a city input", "Add a Search button", "Use fetch()", "Parse JSON", "Display temperature or sample weather result", "Show an error message when needed"],
        "success_criteria": ["fetch() is used", "addEventListener is used", "JSON is parsed", "DOM text updates", "Error message exists"],
        "steps": ["Create folder weather_lookup_app", "Create index.html/style.css/script.js", "Connect script.js to HTML", "Add input with id cityInput", "Add button with id searchBtn", "Add result area with id result", "In JS, select all three elements", "Add click listener to the button", "Call fetch()", "Convert response to JSON", "Display result text", "Add error handling"],
        "proof": ["Upload project ZIP", "Include index.html", "Include style.css", "Include script.js", "Write in README what API or sample JSON you used"],
        "verification_patterns": [r"fetch\(", r"addEventListener", r"getElementById|querySelector", r"\.json\(\)", r"catch\("],
    },
    "API / Routes": {
        "title": "API Weather Lookup App",
        "type": "Refresh Quest",
        "goal": "Practice making an API request and displaying JSON data.",
        "what_to_build": "A browser app that fetches weather or sample API data after a button click and displays it in a result box.",
        "requirements": ["Input field", "Button", "fetch() request", "JSON parsing", "Display result", "Error message"],
        "success_criteria": ["fetch() detected", "JSON parsing detected", "Button event detected", "Data displayed in HTML"],
        "steps": ["Create index.html, style.css, script.js", "Create input field", "Create button", "Create result div", "Use fetch() in script.js", "Use response.json()", "Update result div", "Add try/catch or .catch()"],
        "proof": ["Upload ZIP with HTML/CSS/JS", "Include README", "Include screenshot if possible"],
        "verification_patterns": [r"fetch\(", r"\.json\(\)", r"addEventListener", r"innerText|textContent|innerHTML"],
    },
    "React": {
        "title": "Movie Explorer React Path - Quest 1: Movie Card",
        "type": "Quest Chain Start",
        "goal": "Practice React components with an exact small project that can grow into later quests.",
        "what_to_build": "A React page that displays one favorite movie card with title, year, genre, and a short description.",
        "requirements": ["Create React app", "Create MovieCard component", "Pass movie data as props", "Render MovieCard in App", "Style the card"],
        "success_criteria": ["MovieCard component exists", "props are used", "App renders MovieCard", "At least 4 movie fields display"],
        "steps": ["Create a React project", "Create src/components/MovieCard.jsx", "Inside MovieCard, accept props", "Display title, year, genre, description", "Import MovieCard into App.jsx", "Pass one movie object to MovieCard", "Add simple CSS"],
        "proof": ["Upload ZIP", "Include src/App.jsx", "Include src/components/MovieCard.jsx", "Include package.json", "Include README.md"],
        "verification_patterns": [r"MovieCard", r"props", r"export default", r"import .*MovieCard", r"\.jsx"],
    },
    "Testing": {
        "title": "Smoke Test Builder",
        "type": "Practice Quest",
        "goal": "Practice proving a project still runs after changes.",
        "what_to_build": "Add a tiny tests folder to a project and create at least one test that proves the app imports or starts.",
        "requirements": ["Create tests folder", "Create test_smoke.py", "Import the app or main module", "Run pytest", "Document test command"],
        "success_criteria": ["tests folder exists", "test file exists", "pytest or unittest detected", "README includes test command"],
        "steps": ["Create tests folder", "Create test_smoke.py", "Import your app module", "Write one assert", "Install pytest if needed", "Run pytest", "Put the command in README.md"],
        "proof": ["Upload updated ZIP", "Include tests folder", "Include README test command"],
        "verification_patterns": [r"pytest", r"unittest", r"def test_", r"assert ", r"tests/|tests\\"],
    }
}

# KDT OS v17: stronger templates for project-upload detected skills so weak auto quests do not enter the system.
PRACTICE_TEMPLATES.update({
    "HTML/CSS": {
        "title": "Responsive Card Layout",
        "type": "Practice Quest",
        "goal": "Prove you can create and style a clean responsive page section.",
        "what_to_build": "A browser page with three cards that stack on mobile and sit side-by-side on wider screens.",
        "requirements": ["Create index.html", "Create style.css", "Add three card sections", "Use CSS grid or flexbox", "Add a mobile layout", "Add README.md"],
        "success_criteria": ["index.html exists", "style.css exists", "At least three cards appear", "Grid or flexbox is used", "Layout changes on smaller screens"],
        "steps": ["Create folder responsive_card_layout", "Create index.html", "Create style.css", "Add a main container", "Add three cards with headings and short text", "Link style.css", "Use display:grid or display:flex", "Add a media query for small screens", "Open index.html in browser", "Write README.md with what you practiced"],
        "proof": ["Upload ZIP", "Include index.html", "Include style.css", "Include screenshot or README note"],
        "verification_patterns": ["index.html", "style.css", "display: grid|display:grid|display: flex|display:flex", "@media"]
    },
    "Dashboard/UI": {
        "title": "Clean Dashboard Metric Cards",
        "type": "Practice Quest",
        "goal": "Prove you can build a readable dashboard section.",
        "what_to_build": "A simple HTML/CSS dashboard with four metric cards and one explanation section.",
        "requirements": ["Create index.html", "Create style.css", "Create four metric cards", "Use readable labels", "Use spacing and alignment", "Create README.md"],
        "success_criteria": ["Four cards are visible", "Each card has a number and label", "CSS spacing is applied", "README explains the design choice"],
        "steps": ["Create folder dashboard_metric_cards", "Create index.html and style.css", "Add a dashboard header", "Add four metric cards", "Style cards with border radius and spacing", "Add an explanation section", "Open in browser", "Write README.md"],
        "proof": ["Upload ZIP", "Include HTML/CSS", "Include screenshot or README note"],
        "verification_patterns": ["metric", "card", "style.css", "display"]
    },
    "Project Tracking": {
        "title": "Mini Project Status Tracker",
        "type": "Practice Quest",
        "goal": "Prove you can track project status in a structured way.",
        "what_to_build": "A Python script that stores three project items with status and prints active vs completed work.",
        "requirements": ["Create app.py", "Create a list of project dictionaries", "Each project has name and status", "Print active projects", "Print completed projects", "Create README.md"],
        "success_criteria": ["app.py exists", "At least three project entries exist", "Status field exists", "Active and completed projects print separately"],
        "steps": ["Create folder mini_project_status_tracker", "Create app.py", "Create a list named projects", "Add three dictionaries with name and status", "Loop through projects", "Print active projects", "Print completed projects", "Run python app.py", "Write README.md"],
        "proof": ["Upload ZIP", "Include app.py", "Include README.md", "Include copied output or screenshot"],
        "verification_patterns": ["projects", "status", "for ", "print"]
    },
    "Learning/Practice": {
        "title": "Practice Attempt Logger",
        "type": "Practice Quest",
        "goal": "Prove you can track repeated practice attempts and what went wrong.",
        "what_to_build": "A Python script that saves three practice attempts with skill, result, and mistake notes to attempts.json.",
        "requirements": ["Create app.py", "Create attempts.json", "Store skill name", "Store result", "Store mistake note", "Print a summary"],
        "success_criteria": ["attempts.json exists", "At least three attempts are stored", "Each attempt has skill/result/mistake", "Summary prints"],
        "steps": ["Create folder practice_attempt_logger", "Create app.py", "Import json", "Create a list of three attempts", "Save the list to attempts.json", "Read the file back", "Print each attempt", "Write README.md"],
        "proof": ["Upload ZIP", "Include app.py", "Include attempts.json", "Include README.md"],
        "verification_patterns": ["json", "attempts", "mistake", "result"]
    },
    "Health Monitoring": {
        "title": "Mini Health Checker",
        "type": "Practice Quest",
        "goal": "Practice health monitoring by checking a tiny system and reporting whether it looks OK.",
        "what_to_build": "A Python command-line app that checks CPU, memory, and disk health and prints an OK/WARNING report.",
        "requirements": ["Create folder mini_health_checker", "Create app.py", "Create cpu_check()", "Create memory_check()", "Create disk_check()", "Print Overall Health", "Create README.md"],
        "success_criteria": ["app.py exists", "cpu_check function exists", "memory_check function exists", "disk_check function exists", "Output includes OK or WARNING", "README has run command"],
        "steps": ["Create a folder named mini_health_checker", "Create app.py", "Inside app.py, create cpu_check() that returns OK", "Create memory_check() that returns OK", "Create disk_check() that returns WARNING", "Call all three functions", "Print each result", "Print Overall Health: Needs Attention if any check is WARNING", "Run python app.py", "Create README.md with python app.py", "Zip and submit"],
        "proof": ["Upload project ZIP", "Include app.py", "Include README.md", "Include optional screenshot of output"],
        "verification_patterns": ["def cpu_check", "def memory_check", "def disk_check", "Overall Health", "WARNING"],
        "difficulty": "Beginner",
        "estimated_time": "25-45 minutes"
    }
})



# KDT OS v18.1: proof-ready, non-generic templates for real beginner quests.
PRACTICE_TEMPLATES.update({
    "Active Directory": {
        "title": "Active Directory OU Proof Quest",
        "type": "Teach Me Quest",
        "goal": "Prove you understand what an OU is by creating a visible OU structure in ADUC.",
        "what_to_build": "In Active Directory Users and Computers, create one OU named KDT_Practice, create a sub-OU named Workstations, and move one test user or computer object into the correct OU.",
        "requirements": ["Open Active Directory Users and Computers", "Create OU named KDT_Practice", "Create sub-OU named Workstations", "Move one test user or computer into an OU", "Take a screenshot showing the OU tree", "Write a short explanation in README.md"],
        "success_criteria": ["KDT_Practice OU is visible", "Workstations sub-OU is visible", "At least one object is shown inside the OU or explanation says why no object was available", "Screenshot clearly shows ADUC", "README explains why OUs are useful"],
        "steps": ["Open Server Manager or Start Menu", "Open Active Directory Users and Computers", "Expand your domain in the left tree", "Right-click the domain or a safe practice container", "Select New > Organizational Unit", "Name the OU KDT_Practice", "Right-click KDT_Practice and create a sub-OU named Workstations", "Move one safe test user or computer into KDT_Practice or Workstations", "Take a screenshot showing the domain tree and new OU", "Create README.md", "In README.md answer: What is an OU? Why not put everything in Users?", "Upload the screenshot and README.md"],
        "proof": ["Upload screenshot showing ADUC and KDT_Practice", "Include README.md", "Answer: What did the OU organize?", "Answer: How would a GPO use this OU later?"],
        "verification_patterns": ["KDT_Practice", "Workstations", "Organizational Unit", "ADUC", "README.md"],
        "difficulty": "Beginner",
        "estimated_time": "20-40 minutes"
    },
    "CPU Usage": {
        "title": "CPU Usage Task Manager Proof Quest",
        "type": "Teach Me Quest",
        "goal": "Prove you can find CPU usage and explain what it means during troubleshooting.",
        "what_to_build": "A screenshot-and-notes proof showing Task Manager CPU usage, the top CPU process, and a short explanation of what the percentage means.",
        "requirements": ["Open Task Manager", "Open the Processes or Performance tab", "Find CPU percentage", "Identify one process using CPU", "Take screenshot", "Create cpu_usage_notes.txt"],
        "success_criteria": ["Screenshot shows Task Manager", "CPU percentage is visible or written in notes", "One process name is identified", "Notes explain high vs low CPU", "Proof can be reviewed"],
        "steps": ["Press Ctrl + Shift + Esc", "Click More details if Task Manager opens small", "Click Processes", "Click the CPU column to sort by CPU usage", "Write down the top process name", "Click Performance", "Click CPU", "Write down the current CPU percentage", "Take a screenshot", "Create cpu_usage_notes.txt", "Write what CPU percentage means in one sentence", "Upload screenshot and notes"],
        "proof": ["Upload screenshot of Task Manager", "Include cpu_usage_notes.txt", "Answer: What was the CPU percentage?", "Answer: Which process used the most CPU?"],
        "verification_patterns": ["Task Manager", "CPU", "cpu_usage_notes", "process", "%"],
        "difficulty": "Beginner",
        "estimated_time": "10-15 minutes"
    },
    "Python": {
        "title": "Python Function Practice: Expense Totaler",
        "type": "Practice Quest",
        "goal": "Prove you can define a function, pass data into it, and return a result.",
        "what_to_build": "A command-line app named app.py that stores three expenses in a list and prints the total cost.",
        "requirements": ["Create folder python_expense_totaler", "Create app.py", "Create a function named calculate_total", "Create a list of three expense numbers", "Call calculate_total", "Print the final total", "Create README.md"],
        "success_criteria": ["app.py exists", "calculate_total function exists", "A list of expenses exists", "The total prints to terminal", "README explains what the function returns"],
        "steps": ["Create folder python_expense_totaler", "Create app.py", "Create a list named expenses with three numbers", "Define calculate_total(expenses)", "Inside the function, return sum(expenses)", "Call the function and store the result in total", "Print Final total: followed by the number", "Run python app.py", "Create README.md", "In README.md answer: What does return do?", "Zip the project folder"],
        "proof": ["Upload ZIP", "Include app.py", "Include README.md", "Include screenshot or copied terminal output", "Answer: what value did calculate_total return?"],
        "verification_patterns": ["def calculate_total", "return", "sum(", "expenses", "print"],
        "difficulty": "Beginner",
        "estimated_time": "20-40 minutes"
    }
})

DEFAULT_TEMPLATE = {
    "title": "Exact Skill Proof Drill",
    "type": "Practice Quest",
    "goal": "Prove one skill with a tiny, visible build that can be checked.",
    "what_to_build": "A small proof project with exact files: README.md plus one working file named practice_output.txt or app.py that demonstrates the target skill.",
    "requirements": [
        "Create a folder named exact_skill_proof_drill",
        "Create README.md",
        "Create app.py or practice_output.txt",
        "Write the skill name at the top of README.md",
        "Show one concrete result from using the skill",
        "Write what confused you and what you changed"
    ],
    "success_criteria": [
        "README.md exists and names the skill",
        "The working file exists",
        "The result is visible in output or text",
        "The proof explains what was practiced",
        "The project can be zipped and reviewed"
    ],
    "steps": [
        "Create a folder named exact_skill_proof_drill",
        "Create README.md",
        "Create app.py if this is a coding skill, otherwise create practice_output.txt",
        "Add one smallest possible example of the skill",
        "Run the file or review the output",
        "Write the exact command or action used in README.md",
        "Write one sentence explaining what confused you",
        "Zip the folder and submit it"
    ],
    "proof": [
        "Upload ZIP",
        "Include README.md",
        "Include the working file",
        "Include your explanation of what you practiced"
    ],
    "verification_patterns": ["README.md", "app.py", "practice_output"],
    "difficulty": "Beginner",
    "estimated_time": "20-40 minutes"
}



# KDT OS v0.4 learning loop helpers
# These helpers make the pages talk to each other: project analysis -> skills -> quests -> proof -> skill updates -> resume original project.
SKILL_ALIASES = {
    "apis": "API / Routes", "api": "API / Routes", "routes": "API / Routes",
    "js": "JavaScript", "javascript": "JavaScript",
    "sqlite3": "SQLite", "database": "SQLite", "databases": "SQLite",
    "files": "File Handling", "file handling": "File Handling",
    "test": "Testing", "tests": "Testing", "unit tests": "Testing",
    "flask": "Flask", "python": "Python", "react": "React", "powershell": "PowerShell",
}

def normalize_skill(skill: str) -> str:
    raw = (skill or "").strip()
    if not raw:
        return "JavaScript"
    low = raw.lower()
    # KDT OS should not store full confusion sentences as skills. Convert common Teach Me phrases to real skill names.
    if "active directory" in low or "organizational unit" in low or re.search(r"\bou\b", low):
        return "Active Directory"
    if "cpu" in low or "task manager" in low:
        return "CPU Usage"
    if "event log" in low or "event viewer" in low:
        return "Windows Event Logs"
    if "weather" in low and ("api" in low or "lookup" in low):
        return "API / Routes"
    if "sqlite" in low or "database" in low:
        return "SQLite"
    if "javascript" in low or "dom" in low or "fetch" in low:
        return "JavaScript"
    return SKILL_ALIASES.get(low, raw)

def verified_skill_score(entry: Dict[str, Any]) -> int:
    """Score only proof-backed skill evidence. Uploaded projects can discover skills, but do not prove mastery."""
    if not entry:
        return 0
    score = 0
    for sub in entry.get("submissions", []):
        try:
            rule = int(sub.get("rule_score", sub.get("score", 0)) or 0)
            build = int(sub.get("build_verification", 0) or 0)
            understand = int(sub.get("understanding_verification", 0) or 0)
        except Exception:
            rule = build = understand = 0
        combined = max(rule, int((build + understand) / 2) if (build or understand) else 0)
        if combined >= 90:
            score += 22
        elif combined >= 80:
            score += 16
        elif combined >= 60:
            score += 8
        elif combined >= 40:
            score += 4
        else:
            score += 1
    # Repeat success matters, but cap so one skill does not jump to 100 too fast.
    completed = len(entry.get("completed_quests", []))
    score += min(18, completed * 3)
    return max(0, min(100, score))

def skill_status(entry: Dict[str, Any]) -> str:
    """Human-readable skill state. Project uploads detect; quest proof verifies."""
    if not entry:
        return "Unknown"
    score = verified_skill_score(entry)
    completed = len(entry.get("completed_quests", []))
    submissions = entry.get("submissions", [])
    last_seen = entry.get("last_verified_at") or entry.get("last_seen")
    if last_seen and completed > 0:
        try:
            dt = datetime.fromisoformat(last_seen)
            if datetime.now() - dt > timedelta(days=90):
                return "Rusty"
        except Exception:
            pass
    if score >= 90 and completed >= 6:
        return "Mastered"
    if score >= 75 and completed >= 4:
        return "Proficient"
    if score >= 50 and completed >= 2:
        return "Verified"
    if score >= 20 and completed >= 1:
        return "Practiced"
    if submissions:
        return "Learning"
    if entry.get("evidence_count", 0) > 0:
        return "Detected"
    return "Unknown"

def skill_confidence_label(entry: Dict[str, Any]) -> str:
    status = skill_status(entry)
    if status == "Detected":
        return "Detected in project code only. This is exposure evidence, not proof you can rebuild it yet."
    if status == "Learning":
        return "Started practicing, but proof is not strong enough yet."
    if status == "Practiced":
        return "At least one proof-backed quest was submitted."
    if status == "Verified":
        return "Multiple proof-backed quest checks show usable skill."
    if status == "Proficient":
        return "Repeated verified proof suggests strong working ability."
    if status == "Mastered":
        return "High proof-backed confidence from repeated successful quests."
    if status == "Rusty":
        return "Previously verified, but needs a refresh due to inactivity."
    return "Unknown or unproven."

def slugify(value: str) -> str:
    value = (value or "project").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value or "project"

def project_record_path(project_name: str) -> Path:
    return PROJECT_DIR / f"{slugify(project_name)}.json"

def load_project_record(project_name: str) -> Dict[str, Any]:
    path = project_record_path(project_name)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"project_name": project_name, "created_at": datetime.now().isoformat(timespec="seconds"), "versions": [], "current_report": "", "status": "Active", "knowledge_type": "fact", "source_type": "Uploaded Project", "confidence": 100, "verification_status": "Verified", "source_note": "Created from an uploaded/analyzed project."}

def report_meaningful_signature(report: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback comparison for older reports that do not have file hashes yet."""
    return {
        "summary": report.get("summary", {}),
        "capabilities": sorted([c.get("name") for c in report.get("capabilities", []) if c.get("name")]),
        "technologies": sorted([t.get("name") for t in report.get("technologies", []) if t.get("name")]),
        "important_files": sorted(report.get("important_files", [])),
        "sample_files": sorted(report.get("sample_files", [])),
    }

def reports_are_duplicates(old: Dict[str, Any], new: Dict[str, Any]) -> bool:
    old_hash = old.get("project_signature", {}).get("project_hash")
    new_hash = new.get("project_signature", {}).get("project_hash")
    if old_hash and new_hash:
        return old_hash == new_hash
    return report_meaningful_signature(old) == report_meaningful_signature(new)

def compare_reports(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    def names(items): return {x.get("name") for x in items if x.get("name")}
    old_caps, new_caps = names(old.get("capabilities", [])), names(new.get("capabilities", []))
    old_tech, new_tech = names(old.get("technologies", [])), names(new.get("technologies", []))
    old_files, new_files = set(old.get("sample_files", []) + old.get("important_files", [])), set(new.get("sample_files", []) + new.get("important_files", []))
    duplicate = reports_are_duplicates(old, new)
    return {
        "compared_at": datetime.now().isoformat(timespec="seconds"),
        "duplicate_upload": duplicate,
        "change_level": "Duplicate" if duplicate else "Changed",
        "previous_health": old.get("summary", {}).get("health_score"),
        "current_health": new.get("summary", {}).get("health_score"),
        "health_change": (new.get("summary", {}).get("health_score",0) or 0) - (old.get("summary", {}).get("health_score",0) or 0),
        "new_capabilities": sorted(new_caps - old_caps),
        "removed_capabilities": sorted(old_caps - new_caps),
        "new_technologies": sorted(new_tech - old_tech),
        "removed_technologies": sorted(old_tech - new_tech),
        "new_files_seen": sorted(list(new_files - old_files))[:25],
        "removed_files_seen": sorted(list(old_files - new_files))[:25],
        "file_count_change": (new.get("summary", {}).get("file_count",0) or 0) - (old.get("summary", {}).get("file_count",0) or 0),
        "function_count_change": (new.get("summary", {}).get("functions_detected",0) or 0) - (old.get("summary", {}).get("functions_detected",0) or 0),
    }

def update_project_record(report: Dict[str, Any], report_filename: str) -> Dict[str, Any]:
    """Create a new version only when the upload actually changed."""
    project = report.get("project_name", "Unknown Project")
    record = load_project_record(project)
    previous_report_file = record.get("current_report")
    comparison = None
    if previous_report_file and (REPORT_DIR / previous_report_file).exists():
        try:
            previous = json.loads((REPORT_DIR / previous_report_file).read_text(encoding="utf-8"))
            comparison = compare_reports(previous, report)
            if comparison.get("duplicate_upload"):
                report["project_update"] = {
                    "matched_existing_project": True,
                    "duplicate_upload": True,
                    "previous_report": previous_report_file,
                    "comparison": comparison,
                    "message": "No meaningful changes detected. No new version, report, quests, or skill evidence were created."
                }
                record.setdefault("duplicate_uploads", []).append({
                    "attempted_at": report.get("analyzed_at"),
                    "previous_report": previous_report_file,
                    "message": "Duplicate upload detected. Existing project version kept."
                })
                project_record_path(project).write_text(json.dumps(record, indent=2), encoding="utf-8")
                return {"record": record, "created_new_version": False, "duplicate_upload": True, "previous_report": previous_report_file}
            report["project_update"] = {"matched_existing_project": True, "duplicate_upload": False, "previous_report": previous_report_file, "comparison": comparison}
        except Exception:
            report["project_update"] = {"matched_existing_project": True, "duplicate_upload": False, "previous_report": previous_report_file, "comparison_error": "Could not compare previous report."}
    else:
        report["project_update"] = {"matched_existing_project": False, "duplicate_upload": False, "previous_report": "", "message": "First known version of this project."}
    version_number = len(record.get("versions", [])) + 1
    version = {
        "version": version_number,
        "report_file": report_filename,
        "analyzed_at": report.get("analyzed_at"),
        "health_score": report.get("summary", {}).get("health_score"),
        "file_count": report.get("summary", {}).get("file_count"),
        "function_count": report.get("summary", {}).get("functions_detected"),
        "capabilities": [c.get("name") for c in report.get("capabilities", [])[:12]],
        "technologies": [t.get("name") for t in report.get("technologies", [])[:12]],
        "comparison": comparison,
    }
    record.setdefault("versions", []).append(version)
    record.setdefault("knowledge_type", "fact")
    record.setdefault("source_type", "Uploaded Project")
    record.setdefault("confidence", 100)
    record.setdefault("verification_status", "Verified")
    record.setdefault("source_note", "Created from an uploaded/analyzed project.")
    record["current_report"] = report_filename
    record["last_analyzed"] = report.get("analyzed_at")
    record["latest_capabilities"] = version["capabilities"]
    record["latest_technologies"] = version["technologies"]
    project_record_path(project).write_text(json.dumps(record, indent=2), encoding="utf-8")
    return {"record": record, "created_new_version": True, "duplicate_upload": False, "previous_report": previous_report_file}

def list_projects():
    out=[]
    for p in sorted(PROJECT_DIR.glob("*.json"), key=lambda x:x.stat().st_mtime, reverse=True):
        try:
            data=json.loads(p.read_text(encoding="utf-8"))
            data["filename"]=p.name
            out.append(data)
        except Exception: pass
    return out

def load_goal_names() -> List[str]:
    return [g.get("goal_name", "") for g in list_goals() if g.get("goal_name")]

def quest_why(skill: str, source: str, goal: str = "", user_gap: str = "") -> str:
    parts = []
    if goal:
        parts.append(f"You are working toward this goal: {goal}.")
    if source:
        parts.append(f"This quest came from: {source}.")
    parts.append(f"The skill being practiced is: {skill}.")
    if user_gap:
        parts.append(f"Your stated blocker is: {user_gap}")
    parts.append("This quest exists so practice connects back to something you care about instead of becoming random homework.")
    return " ".join(parts)

def exact_breakdown_for(skill: str) -> List[Dict[str, str]]:
    skill = normalize_skill(skill)
    maps = {
        "SQLite": [
            {"label":"What is a database?", "answer":"A database is a structured place where an app stores information so it can be used again later."},
            {"label":"What is a table?", "answer":"A table is like one spreadsheet tab. It stores one type of thing, such as workouts, contacts, or skills."},
            {"label":"What is a column?", "answer":"A column is one field, like Name, Age, Exercise, Sets, or Reps."},
            {"label":"What is a row?", "answer":"A row is one saved item. One contact or one workout is one row."},
            {"label":"What is CRUD?", "answer":"CRUD means Create, Read, Update, Delete. It is the basic full cycle for stored data."},
        ],
        "API / Routes": [
            {"label":"What is an API?", "answer":"An API is a way for one app to ask another app or service for data."},
            {"label":"What is fetch()?", "answer":"fetch() is JavaScript's way to make a web request from the browser."},
            {"label":"What is JSON?", "answer":"JSON is a data format that looks like JavaScript objects and is commonly returned by APIs."},
            {"label":"What is an endpoint?", "answer":"An endpoint is the URL you request, like /weather or /api/tasks."},
        ],
        "React": [
            {"label":"What is a component?", "answer":"A component is a reusable piece of UI, like a card, button, list, or form."},
            {"label":"What are props?", "answer":"Props are values passed into a component so it can display different data."},
            {"label":"What is state?", "answer":"State is data React remembers and updates while the user interacts with the page."},
            {"label":"What is map()?", "answer":"map() lets you turn an array of data into repeated UI elements."},
        ],
        "JavaScript": [
            {"label":"What is DOM selection?", "answer":"DOM selection means grabbing an HTML element with JavaScript so you can read or change it."},
            {"label":"What is an event listener?", "answer":"An event listener waits for an action like a click, typing, or submit."},
            {"label":"What is local storage?", "answer":"Local storage saves small data in the browser so it stays after refresh."},
        ],
    }
    return maps.get(skill, [
        {"label":"What is this skill?", "answer": f"{skill} is a skill KDT OS can practice through small exact quests."},
        {"label":"Why practice it?", "answer": "Practicing it in a tiny project makes it easier to use later in a larger project."},
    ])

def update_skill_after_submission(skill: str, score: int, source: str, ai_eval: Dict[str, Any] | None = None, quest_title: str = "") -> None:
    """Update skill confidence from quest proof only. Project uploads do not raise mastery."""
    path = SKILL_DIR / "skills.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    skill = normalize_skill(skill)
    now = datetime.now().isoformat(timespec="seconds")
    ai_eval = ai_eval or {}
    build = int(ai_eval.get("build_verification", 0) or 0) if ai_eval.get("available") else 0
    understand = int(ai_eval.get("understanding_verification", 0) or 0) if ai_eval.get("available") else 0
    verdict = ai_eval.get("verdict", "Completed" if score >= 80 else "Needs Revision")
    entry = data.setdefault(skill, {
        "skill": skill,
        "evidence_count": 0,
        "projects": [],
        "evidence": [],
        "last_seen": None,
        "last_verified_at": None,
        "status": "Unknown",
        "confidence": 0,
        "verified_confidence": 0,
        "completed_quests": [],
        "submissions": [],
        "proof_note": "Skill confidence is based on verified quests/proof, not uploaded projects."
    })
    if source and source not in entry.setdefault("projects", []):
        entry["projects"].append(source)
    submission_event = {
        "at": now,
        "source": source,
        "quest_title": quest_title,
        "rule_score": score,
        "build_verification": build,
        "understanding_verification": understand,
        "verdict": verdict,
    }
    entry.setdefault("submissions", []).append(submission_event)
    if verdict == "Completed" or score >= 80 or build >= 80:
        entry.setdefault("completed_quests", []).append(submission_event)
        entry["last_verified_at"] = now
    entry["last_seen"] = now
    entry["verified_confidence"] = verified_skill_score(entry)
    entry["confidence"] = entry["verified_confidence"]
    entry["status"] = skill_status(entry)
    entry["confidence_label"] = skill_confidence_label(entry)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def quest_identity(q: Dict[str, Any]) -> str:
    """Stable identity used to prevent duplicate auto-generated quests."""
    return "|".join([
        str(q.get("quest_type", "")),
        str(q.get("skill", "")),
        str(q.get("resume_project", "")),
        str(q.get("source_project", "")),
        str(q.get("title", "")),
    ]).lower()

def existing_auto_quest(project_name: str, skill: str) -> str:
    """Return an existing auto quest filename for this project/skill, if one exists."""
    project_name = (project_name or "").strip().lower()
    skill = normalize_skill(skill).strip().lower()
    for p in QUEST_DIR.glob("*.json"):
        try:
            q = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if q.get("quest_type") != "Auto Practice Quest":
            continue
        if normalize_skill(q.get("skill", "")).lower() != skill:
            continue
        source = (q.get("source_project", "") + " " + q.get("resume_project", "")).lower()
        if project_name and project_name in source:
            return p.name
    return ""

def auto_generate_quests_for_report(report: Dict[str, Any], report_filename: str) -> List[str]:
    created_or_existing = []
    project_name = report.get("project_name", "Project")
    candidates = report.get("learning_opportunities", [])[:4]
    for item in candidates:
        skill = normalize_skill(item.get("skill", ""))
        existing = existing_auto_quest(project_name, skill)
        if existing:
            created_or_existing.append(existing)
            continue
        qfile, q = make_quest(
            skill=skill,
            source=f"Project Analysis: {project_name}",
            user_gap=f"KDT OS detected {skill} in this uploaded project and created a ready practice quest.",
            goal="",
            quest_type="Auto Practice Quest",
            origin_report=report_filename,
            resume_project=project_name
        )
        created_or_existing.append(qfile)
    report["auto_generated_quests"] = created_or_existing
    return created_or_existing

def explain(name: str, fallback: str = "KDT OS detected this from keywords, files, and code patterns. Treat it as a clue, not a perfect conclusion.") -> str:
    return EXPLANATIONS.get(name, fallback)

def safe_extract_zip(zip_path: Path, extract_to: Path) -> None:
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            target = extract_to / member.filename
            if not str(target.resolve()).startswith(str(extract_to.resolve())):
                raise ValueError("Unsafe ZIP path detected.")
        zf.extractall(extract_to)

def read_text_file(path: Path, max_chars: int = 250_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except Exception:
        return ""

def iter_project_files(root: Path) -> List[Path]:
    files = []
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        files.append(path)
    return files


def project_file_signature(project_root: Path) -> Dict[str, Any]:
    """Create a stable fingerprint so KDT OS can tell duplicate uploads from real updates."""
    file_hashes = []
    combined = hashlib.sha256()
    for path in sorted(iter_project_files(project_root), key=lambda x: str(x.relative_to(project_root)).lower()):
        rel = str(path.relative_to(project_root)).replace("\\", "/")
        try:
            raw = path.read_bytes()
        except Exception:
            raw = b""
        item_hash = hashlib.sha256(raw).hexdigest()
        file_hashes.append({"path": rel, "sha256": item_hash, "size": len(raw)})
        combined.update(rel.encode("utf-8", errors="ignore"))
        combined.update(b"\0")
        combined.update(item_hash.encode("ascii"))
    return {
        "project_hash": combined.hexdigest(),
        "file_count": len(file_hashes),
        "file_hashes": file_hashes[:500],
    }

def match_rules(text: str, rel_path: str, rules: Dict[str, List[str]]) -> Dict[str, int]:
    haystack = f"{rel_path}\n{text}"
    found = {}
    for name, patterns in rules.items():
        count = 0
        for pattern in patterns:
            try:
                count += len(re.findall(pattern, haystack, flags=re.IGNORECASE))
            except re.error:
                pass
        if count:
            found[name] = count
    return found

def explain_recommendation(rec: str) -> str:
    if "tests" in rec.lower() or "smoke test" in rec.lower():
        return "This gives you proof that the app still starts or core functions still work after you change code. It reduces fear when improving the project."
    if "database" in rec.lower():
        return "Database storage helps the project remember information between sessions instead of losing progress when the page reloads."
    if "login" in rec.lower() or "pin" in rec.lower():
        return "If personal data is stored, even a simple PIN helps prevent casual access from other people using your device."
    if "practice" in rec.lower() or "mastery" in rec.lower():
        return "This supports your learning style: repetition, mistakes, review, and mastery tracking."
    if "reusable" in rec.lower() or "health" in rec.lower():
        return "This project contains a capability that can make KDT OS stronger later instead of being rebuilt from scratch."
    return "This recommendation is meant to make the project easier to understand, maintain, or use later."

def build_learning_opportunities(technologies: List[Dict[str, Any]], capabilities: List[Dict[str, Any]], risks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    names = [item["name"] for item in technologies + capabilities]
    risk_names = [item["name"] for item in risks]
    opportunities = []
    for name in names:
        if name in SKILL_MAP:
            opportunities.append({
                "skill": name,
                "why": f"This project uses {name}. Practicing it separately will make the project easier to understand and improve.",
                "practice_options": SKILL_MAP[name],
                "suggested_artifact": PRACTICE_TEMPLATES.get(name, DEFAULT_TEMPLATE),
            })
    if "No tests detected" in risk_names:
        opportunities.insert(0, {"skill": "Testing", "why": "This project has no obvious tests. Learning smoke tests will help you trust changes before building more.", "practice_options": ["Smoke tests", "Import tests", "Route tests"], "suggested_artifact": PRACTICE_TEMPLATES["Testing"]})
    seen, unique = set(), []
    for item in opportunities:
        if item["skill"] not in seen:
            unique.append(item); seen.add(item["skill"])
    return unique[:10]

def update_skill_library_from_report(report: Dict[str, Any]) -> None:
    """Add evidence from analyzed projects without pretending mastery is proven."""
    path = SKILL_DIR / "skills.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    project = report.get("project_name", "Unknown Project")
    now = datetime.now().isoformat(timespec="seconds")
    report_file = report.get("report_filename", "")
    for item in report.get("technologies", []) + report.get("capabilities", []):
        skill = normalize_skill(item.get("name"))
        if not skill:
            continue
        entry = data.setdefault(skill, {
            "skill": skill,
            "evidence_count": 0,
            "projects": [],
            "evidence": [],
            "last_seen": None,
            "status": "Evidence Found",
            "confidence": 0,
            "completed_quests": [],
            "submissions": [],
            "note": "Project evidence means the skill appeared in code. Quest submissions prove practice."
        })
        score = item.get("score", item.get("count", 1))
        if not isinstance(score, int): score = 1
        entry["evidence_count"] = entry.get("evidence_count", 0) + score
        if project not in entry.setdefault("projects", []):
            entry["projects"].append(project)
        entry.setdefault("evidence", []).append({
            "project": project,
            "report_file": report_file,
            "seen_at": now,
            "source": "project_analysis",
            "score": score,
            "explanation": item.get("explanation", "Detected by project analysis.")
        })
        entry["last_seen"] = now
        # Project uploads only detect exposure. They do not raise verified confidence.
        entry.setdefault("verified_confidence", verified_skill_score(entry))
        entry["confidence"] = entry.get("verified_confidence", 0)
        entry["status"] = skill_status(entry)
        entry["confidence_label"] = skill_confidence_label(entry)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def capability_confidence_label(score: int) -> str:
    if score >= 500:
        return "Strong evidence"
    if score >= 100:
        return "Moderate evidence"
    return "Light evidence"

def build_project_gap_analysis(report: Dict[str, Any]) -> Dict[str, Any]:
    """Translate raw counts into project strengths, missing pieces, and next useful build."""
    cap_names = {c.get("name") for c in report.get("capabilities", [])}
    tech_names = {t.get("name") for t in report.get("technologies", [])}
    risk_names = {r.get("name") for r in report.get("risks", [])}
    strengths = []
    for c in report.get("capabilities", [])[:6]:
        strengths.append({"name": c.get("name"), "reason": f"Detected as {capability_confidence_label(int(c.get('score',0) or 0))}. Treat this as project capability evidence, not personal mastery."})
    gaps = []
    if "No tests detected" in risk_names or not report.get("test_files"):
        gaps.append({"name":"Automated Testing", "why":"The project can break during upgrades without tests.", "next_action":"Create route/import smoke tests."})
    if report.get("summary", {}).get("routes_detected", 0) and "Testing" not in cap_names:
        gaps.append({"name":"Route Verification", "why":"Routes exist but may not be automatically checked.", "next_action":"Add a route health check or pytest route test."})
    if "Evidence Collection" in cap_names and "Vision Verification" not in cap_names:
        gaps.append({"name":"Proof Verification", "why":"The project collects evidence, but may not fully verify screenshots/code/explanations yet.", "next_action":"Create a proof verifier that checks uploaded files against quest requirements."})
    if "Broad exception handling" in risk_names:
        gaps.append({"name":"Error Transparency", "why":"Broad exception handling can hide real failures.", "next_action":"Replace broad except blocks with targeted exceptions or logged details."})
    if "Debug mode enabled" in risk_names:
        gaps.append({"name":"Deployment Safety", "why":"Debug mode should not be enabled in public deployment.", "next_action":"Move debug mode to a development setting."})
    if "Project Tracking" in cap_names and "Database Storage" not in cap_names:
        gaps.append({"name":"Persistent Project Memory", "why":"Tracking systems become stronger when stored in a durable database.", "next_action":"Add SQLite storage or structured JSON history."})
    if not gaps:
        gaps.append({"name":"Next Feature Definition", "why":"No critical gap was obvious from static analysis.", "next_action":"Choose the next feature and generate a governed quest."})
    recommended = gaps[0] if gaps else {"name":"Review", "next_action":"Review project manually."}
    return {
        "strengths": strengths[:6],
        "gaps": gaps[:8],
        "recommended_next_build": recommended,
        "note": "Gap analysis is a reasoning layer over detected code signals. It should guide the next quest, not replace human review."
    }

def analyze_project(project_root: Path, original_name: str = "") -> Dict[str, Any]:
    files = iter_project_files(project_root)
    ext_counts = Counter(path.suffix.lower() or "[no extension]" for path in files)
    file_count = len(files)
    total_size = sum(path.stat().st_size for path in files if path.exists())
    tech_scores, capability_scores, risk_scores = Counter(), Counter(), Counter()
    important_files, sample_files, test_files = [], [], []
    route_count = function_count = class_count = text_file_count = 0

    for path in files:
        rel = str(path.relative_to(project_root)).replace("\\", "/")
        if "test" in path.name.lower():
            test_files.append(rel)
        if path.suffix.lower() in SUPPORTED_TEXT_EXTENSIONS or path.name.lower() in {"readme", "dockerfile", "package.json"}:
            text_file_count += 1
            text = read_text_file(path)
            if len(sample_files) < 20:
                sample_files.append(rel)
            tech_scores.update(match_rules(text, rel, TECH_RULES))
            capability_scores.update(match_rules(text, rel, CAPABILITY_RULES))
            risk_scores.update(match_rules(text, rel, RISK_RULES))
            route_count += len(re.findall(r"@app\.route|@router\.", text))
            function_count += len(re.findall(r"^\s*def\s+\w+\(", text, flags=re.MULTILINE))
            class_count += len(re.findall(r"^\s*class\s+\w+", text, flags=re.MULTILINE))
            if path.name.lower() in {"readme.md", "requirements.txt", "package.json", "app.py", "main.py", "server.py"}:
                important_files.append(rel)
    if not test_files:
        risk_scores["No tests detected"] += 1

    health_score = 100 if file_count else 0
    health_score -= min(20, risk_scores.get("Hardcoded secret/key", 0) * 5)
    health_score -= 10 if risk_scores.get("Debug mode enabled", 0) else 0
    health_score -= 10 if risk_scores.get("No tests detected", 0) else 0
    health_score -= min(10, risk_scores.get("Broad exception handling", 0) * 2)
    health_score = max(0, health_score)

    recommendations = []
    if "No tests detected" in risk_scores:
        recommendations.append("Add a small tests folder or at least a basic smoke test so the project can prove it still runs.")
    if "Dashboard/UI" in capability_scores and "Database Storage" not in capability_scores:
        recommendations.append("If this app stores user progress, add database persistence instead of relying only on page state.")
    if "Database Storage" in capability_scores and "Authentication/Login" not in capability_scores:
        recommendations.append("If this will hold personal data, add a simple login or local PIN before expanding it.")
    if "Learning/Practice" in capability_scores:
        recommendations.append("Track repeated practice attempts, mistakes, and mastery level so learning becomes measurable.")
    if "Health Monitoring" in capability_scores or "Repair Planning" in capability_scores:
        recommendations.append("Preserve this as a reusable capability for KDT OS project inspection and self-health checks.")
    if not recommendations:
        recommendations.append("Write a README that clearly explains the project purpose, current features, and next step.")

    technologies = [{"name": k, "score": v, "explanation": explain(k)} for k, v in tech_scores.most_common()]
    capabilities = [{"name": k, "score": v, "explanation": explain(k)} for k, v in capability_scores.most_common()]
    risks = [{"name": k, "count": v, "explanation": explain(k)} for k, v in risk_scores.most_common()]
    learning_opportunities = build_learning_opportunities(technologies, capabilities, risks)

    # Add confidence labels to raw counts so users do not over-trust raw keyword totals.
    for c in capabilities:
        c["confidence_label"] = capability_confidence_label(int(c.get("score", 0) or 0))
    for t in technologies:
        t["confidence_label"] = capability_confidence_label(int(t.get("score", 0) or 0))

    signature = project_file_signature(project_root)

    report = {
        "project_name": original_name or project_root.name,
        "project_signature": signature,
        "analyzed_at": datetime.now().isoformat(timespec="seconds"),
        "root_folder": str(project_root),
        "summary": {"file_count": file_count, "text_file_count": text_file_count, "total_size_bytes": total_size, "health_score": health_score, "functions_detected": function_count, "classes_detected": class_count, "routes_detected": route_count},
        "summary_explanations": {"health_score": EXPLANATIONS["Health Score"], "file_count": EXPLANATIONS["Files"], "functions_detected": EXPLANATIONS["Functions"], "routes_detected": EXPLANATIONS["Routes"]},
        "extensions": dict(ext_counts.most_common()),
        "important_files": important_files[:30],
        "sample_files": sample_files,
        "technologies": technologies,
        "capabilities": capabilities,
        "risks": risks,
        "test_files": test_files[:30],
        "recommendations": [{"text": rec, "explanation": explain_recommendation(rec)} for rec in recommendations],
        "learning_opportunities": learning_opportunities,
        "gap_analysis": build_project_gap_analysis({"capabilities": capabilities, "technologies": technologies, "risks": risks, "test_files": test_files, "summary": {"routes_detected": route_count}}),
        "next_decision": {"question": "What do you want to do with this project?", "options": [
            {"id": "keep", "label": "Keep as its own project", "explanation": "Use this when the project has its own purpose and should remain separate."},
            {"id": "reuse", "label": "Reuse parts inside KDT OS", "explanation": "Use this when parts of this project should become KDT OS capabilities."},
            {"id": "skills", "label": "Find learning quests", "explanation": "Use this to extract small practice builds from the skills detected here."},
            {"id": "archive", "label": "Pause/archive it", "explanation": "Use this when the project is not important right now, but should not be forgotten."},
            {"id": "continue", "label": "Continue building the next feature", "explanation": "Use this when this project should stay active and receive the next upgrade."},
        ]},
        "decisions": []
    }
    return report

def report_path_for(filename: str) -> Path:
    return REPORT_DIR / filename

def load_report(filename: str) -> Dict[str, Any]:
    path = report_path_for(filename)
    if not path.exists(): raise FileNotFoundError(filename)
    return json.loads(path.read_text(encoding="utf-8"))

def save_report(filename: str, data: Dict[str, Any]) -> None:
    report_path_for(filename).write_text(json.dumps(data, indent=2), encoding="utf-8")

def list_reports(limit=10):
    """Dashboard reports are grouped by project so repeated uploads do not look like separate projects."""
    cards = []
    # Prefer project records because they know the current version.
    for project in list_projects():
        current = project.get("current_report")
        if not current or not (REPORT_DIR / current).exists():
            continue
        try:
            data = json.loads((REPORT_DIR / current).read_text(encoding="utf-8"))
            versions = len(project.get("versions", []))
            cards.append({
                "filename": current,
                "project_name": project.get("project_name", data.get("project_name", "Project")),
                "health_score": data.get("summary", {}).get("health_score", "?"),
                "capabilities": [c["name"] for c in data.get("capabilities", [])[:5]],
                "analyzed_at": data.get("analyzed_at", ""),
                "version_count": versions,
                "is_grouped_project": True,
            })
        except Exception:
            pass
    # Include old reports only when no project record exists for them.
    known_projects = {c["project_name"].lower() for c in cards}
    for report_path in sorted(REPORT_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        if len(cards) >= limit:
            break
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
            name = data.get("project_name", report_path.stem)
            if name.lower() in known_projects:
                continue
            cards.append({"filename": report_path.name, "project_name": name, "health_score": data.get("summary", {}).get("health_score", "?"), "capabilities": [c["name"] for c in data.get("capabilities", [])[:5]], "analyzed_at": data.get("analyzed_at", ""), "version_count": 1, "is_grouped_project": False})
        except Exception:
            pass
    return cards[:limit]

def list_goals():
    goals = []
    for p in sorted(GOAL_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            g = json.loads(p.read_text(encoding="utf-8"))
            g["filename"] = p.name
            goals.append(g)
        except Exception:
            pass
    return goals

def quest_card_type(q: Dict[str, Any]) -> str:
    qt = q.get("quest_type", "Practice Quest")
    if q.get("parent_quest"):
        return "Micro Quest"
    return qt

def cleanup_duplicate_auto_quests() -> int:
    """Delete duplicate auto-generated quests. Keep the oldest quest for each project + skill + type."""
    seen = {}
    deleted = 0
    for p in sorted(QUEST_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime):
        try:
            q = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if q.get("quest_type") != "Auto Practice Quest":
            continue
        key = quest_identity(q)
        if key in seen:
            try:
                p.unlink()
                deleted += 1
            except Exception:
                pass
        else:
            seen[key] = p.name
    return deleted

def list_quests(include_breakdowns: bool = False):
    """List top-level quests by default.

    Quest breakdowns/micro quests are attached to their parent quest so the
    Quest Center stays clean and the original quest never disappears.
    """
    cleanup_duplicate_auto_quests()
    quests = []
    for p in sorted(QUEST_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            q = json.loads(p.read_text(encoding="utf-8"))
            q["filename"] = p.name
            q["display_type"] = quest_card_type(q)
            q["short_reason"] = q.get("why_this_exists", "")[:180]
            q["is_breakdown"] = bool(q.get("parent_quest")) or q.get("quest_type") in ["Micro Quest", "Quest Breakdown"]
            if q.get("status") in ["Archived", "Superseded", "Rejected"] and not include_breakdowns:
                continue
            if q["is_breakdown"] and not include_breakdowns:
                continue
            q["breakdown_count"] = len(child_quests_for_parent(p.name)) if not q["is_breakdown"] else 0
            quests.append(q)
        except Exception:
            pass
    return quests

def child_quests_for_parent(parent_filename: str) -> List[Dict[str, Any]]:
    children = []
    for p in sorted(QUEST_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime):
        try:
            q = json.loads(p.read_text(encoding="utf-8"))
            if q.get("parent_quest") == parent_filename:
                q["filename"] = p.name
                q["display_type"] = "Quest Breakdown"
                q["is_breakdown"] = True
                children.append(q)
        except Exception:
            pass
    return children

def load_parent_quest(parent_filename: str) -> Dict[str, Any] | None:
    if not parent_filename:
        return None
    path = QUEST_DIR / parent_filename
    if not path.exists():
        return None
    try:
        q = json.loads(path.read_text(encoding="utf-8"))
        q["filename"] = parent_filename
        return q
    except Exception:
        return None

def load_skill_library():
    p = SKILL_DIR / "skills.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}



def quest_dna_text(quest: Dict[str, Any]) -> str:
    """Return the instructional DNA of a quest so KDT OS can detect template clones."""
    fields = []
    for key in ["title", "skill", "goal", "what_to_build", "user_gap"]:
        fields.append(str(quest.get(key, "")))
    for key in ["requirements", "success_criteria", "steps", "proof_required"]:
        value = quest.get(key, []) or []
        if isinstance(value, list):
            fields.extend(str(x) for x in value)
        else:
            fields.append(str(value))
    return " ".join(fields).lower()


def is_template_clone_quest(quest: Dict[str, Any]) -> bool:
    """Detect old quests that only changed the title/skill but kept generic instructions."""
    text = quest_dna_text(quest)
    generic_markers = [
        "small project that demonstrates the requested skill",
        "a small project that demonstrates",
        "create the required files",
        "use the skill directly",
        "show the result",
        "write what confused you",
        "create a project folder",
        "create the main file",
        "implement the smallest working version",
        "practice one skill with a small, clear build",
        "single proof quest",
        "one visible proof",
        "one artifact that proves",
        "exact_skill_proof_drill",
    ]
    hits = sum(1 for m in generic_markers if m in text)
    return hits >= 3


def quest_specificity_score(quest: Dict[str, Any]) -> int:
    """Score whether the quest is truly specific, not just complete-looking."""
    text = quest_dna_text(quest)
    specific_patterns = [
        r"\b(app\.py|index\.html|style\.css|script\.js|readme\.md|requirements\.txt|test_\w+\.py|\.ps1|\.jsx|\.db|\.json)\b",
        r"\b(create table|insert into|select|update|delete|pytest|unittest|fetch\(|addEventListener|@app\.route|flask|task manager|active directory|organizational unit|ou named|cpu usage)\b",
        r"\b(id|name|exercise|sets|reps|date|cityInput|searchBtn|result|Sales|Workstations|Servers)\b",
        r"\b(run python app\.py|run pytest|open index\.html|take a screenshot|upload zip|include app\.py)\b",
    ]
    return sum(1 for pat in specific_patterns if re.search(pat, text, flags=re.I))


def quest_quality_check(quest: Dict[str, Any]) -> Dict[str, Any]:
    """KDT OS 10/10 quest standard v2.

    The old standard accidentally rewarded quests for merely *having* sections.
    This version also punishes template clones, vague skeleton instructions,
    weak proof, and poor Kewonte compatibility.
    """
    checks = []
    def add(name, ok, fix, weight=10):
        checks.append({"name": name, "ok": bool(ok), "fix": fix, "weight": weight})

    title = quest.get("title", "")
    steps = quest.get("steps", []) or []
    requirements = quest.get("requirements", []) or []
    success = quest.get("success_criteria", []) or []
    proof = quest.get("proof_required", []) or []
    text = quest_dna_text(quest)

    exact_file_or_artifact = bool(re.search(r"\b(app\.py|index\.html|style\.css|script\.js|readme\.md|requirements\.txt|test_\w+\.py|\.json|\.db|\.ps1|\.jsx|folder named|file named|screenshot|zip)\b", text))
    exact_action = bool(re.search(r"\b(create|open|run|type|click|upload|save|write|add|import|print|test|verify|submit|move|select|enter|name|explain)\b", text))
    measurable_success = bool(re.search(r"\b(exists|appears|displays|prints|returns|saves|created|detected|runs|visible|screenshot|pass|fail|ok|warning|contains|matches|listed|successfully)\b", " ".join(success).lower()))
    proof_is_specific = bool(re.search(r"\b(upload zip|project zip|screenshot|include app\.py|include readme|include .*\.json|include .*\.db|explain|answer|include test_|pytest output|screenshot showing)\b", " ".join(proof).lower()))
    clone = is_template_clone_quest(quest)
    specificity = quest_specificity_score(quest)
    step_count = len(steps)
    has_named_outputs = bool(re.search(r"\b(output|result|report\.json|database|table|screenshot|pytest|terminal|browser|page|route|file)\b", text))
    has_understanding_check = bool(re.search(r"\b(explain|answer|why|what does|what changed|in your own words)\b", " ".join(proof + success + requirements).lower()))

    add("Exact blocker identified", bool(quest.get("user_gap")) and len(quest.get("user_gap", "")) > 8, "Add the specific thing the user does not understand or cannot do yet.", 8)
    add("Smallest visible action", bool(quest.get("what_to_build")) and len(quest.get("what_to_build", "")) > 35 and exact_action, "State the smallest visible thing to create, do, or prove.", 10)
    add("Exact file/artifact named", exact_file_or_artifact, "Name the exact file, folder, screenshot, database, or artifact required.", 12)
    add("Step-by-step instructions", step_count >= 7 and exact_action, "Add at least 7 exact steps from start to finish.", 12)
    add("Required features", len(requirements) >= 4, "List concrete files, fields, buttons, commands, or actions required.", 8)
    add("Measurable success criteria", len(success) >= 3 and measurable_success, "List measurable conditions that prove completion.", 10)
    add("Specific proof method", len(proof) >= 2 and proof_is_specific, "State exactly what to upload or answer as proof.", 10)
    add("Return path", bool(quest.get("resume_project") or quest.get("connected_goal") or quest.get("parent_quest") or quest.get("resume_rule")), "Connect this quest back to a project, goal, or parent quest.", 6)
    add("Not a template clone", not clone, "This quest looks like the same generic template under a different title. Regenerate from project/skill context.", 16)
    add("Project/skill specificity", specificity >= 2, "Add technology-specific files, commands, fields, outputs, or UI elements.", 10)
    add("Named output/result", has_named_outputs, "State what visible result, file, screen, or terminal output proves the work.", 4)
    add("Understanding check", has_understanding_check, "Require a short explanation so proof is not just uploaded blindly.", 4)

    total_weight = sum(c["weight"] for c in checks)
    earned = sum(c["weight"] for c in checks if c["ok"])
    score = int((earned / total_weight) * 100) if total_weight else 0

    penalties = []
    if clone:
        score = min(score, 62)
        penalties.append("Template clone detected: title changed but instructions stayed generic.")
    if specificity == 0:
        score = min(score, 68)
        penalties.append("No project/technology-specific details detected.")
    if step_count < 7:
        score = min(score, 82)
        penalties.append("Too few exact steps for Kewonte's current learning style.")
    if not proof_is_specific:
        score = min(score, 80)
        penalties.append("Proof is not specific enough to verify.")
    # A quest is not 10/10 just because it has sections. Penalize generic wording heavily.
    vague_phrases = [
        "small project that demonstrates", "create the required files", "use the skill directly",
        "show the result", "write what confused you", "create a project folder",
        "create the main file", "implement the smallest working version", "single proof quest",
        "one artifact that proves"
    ]
    vague_hits = sum(1 for phrase in vague_phrases if phrase in text)
    if vague_hits >= 2:
        score = min(score, 72)
        penalties.append("Generic quest language detected: this would not give Kewonte enough exact direction.")
    if len(set([s.strip().lower() for s in steps if str(s).strip()])) < len(steps):
        score = min(score, 84)
        penalties.append("Repeated step text detected.")

    if score >= 95:
        rating = "10/10 Ready"
    elif score >= QUEST_MINIMUM_SCORE:
        rating = "Approved"
    elif score >= 70:
        rating = "Needs upgrade"
    else:
        rating = "Reject / regenerate"
    return {"score": score, "rating": rating, "checks": checks, "passed": sum(1 for c in checks if c["ok"]), "total": len(checks), "penalties": penalties, "specificity_score": specificity, "template_clone": clone}

def apply_quest_quality(quest: Dict[str, Any]) -> Dict[str, Any]:
    quest["quest_quality"] = quest_quality_check(quest)
    quest.setdefault("quest_standard", {
        "rule": "Every KDT OS quest must include exact steps, proof, success criteria, and a return path.",
        "minimum_fields": ["Goal", "Blocker", "What to build/do", "Steps", "Success criteria", "Proof", "Return point"]
    })
    return quest

def skill_graph_summary() -> Dict[str, Any]:
    skills = load_skill_library()
    rows = []
    for name, entry in skills.items():
        entry = dict(entry)
        entry["status"] = skill_status(entry)
        entry["verified_confidence"] = verified_skill_score(entry)
        entry["confidence_label"] = skill_confidence_label(entry)
        rows.append({"name": name, **entry})
    rows.sort(key=lambda x: (x.get("verified_confidence", 0), x.get("evidence_count", 0)), reverse=True)
    return {
        "skills": rows,
        "verified": sum(1 for r in rows if r.get("status") in ["Verified", "Proficient", "Mastered"]),
        "detected_only": sum(1 for r in rows if r.get("status") == "Detected"),
        "learning": sum(1 for r in rows if r.get("status") in ["Learning", "Practiced"]),
        "rusty": sum(1 for r in rows if r.get("status") == "Rusty"),
    }

def make_quest(skill: str, source: str, user_gap: str = "", goal: str = "", quest_type: str = "Practice Quest", origin_report: str = "", resume_project: str = ""):
    skill = normalize_skill(skill)
    template = PRACTICE_TEMPLATES.get(skill, DEFAULT_TEMPLATE)
    q = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_project": source,
        "origin_report": origin_report,
        "resume_project": resume_project,
        "connected_goal": goal,
        "skill": skill,
        "user_gap": user_gap or f"I want exact practice with {skill}.",
        "title": template["title"],
        "quest_type": quest_type or template.get("type", "Practice Quest"),
        "why_this_exists": quest_why(skill, source, goal, user_gap),
        "goal": template["goal"],
        "what_to_build": template.get("what_to_build", "A small project."),
        "requirements": template.get("requirements", []),
        "success_criteria": template.get("success_criteria", []),
        "steps": template.get("steps", []),
        "proof_required": template.get("proof", []),
        "verification_patterns": template.get("verification_patterns", []),
        "difficulty": template.get("difficulty", "Beginner"),
        "estimated_time": template.get("estimated_time", "30-60 minutes"),
        "ai_generated": False,
        "ai_parse_mode": "template",
        "ai_raw_response": "",
        "teach_me_breakdown": exact_breakdown_for(skill),
        "status": "Assigned",
        "submissions": [],
        "resume_rule": "After this quest is complete, return to the original project or goal that caused this quest unless you intentionally choose a different path.",
    }
    apply_quest_quality(q)
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", f"{source}_{skill}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")[:160]
    filename = f"{slug}.json"
    (QUEST_DIR / filename).write_text(json.dumps(q, indent=2), encoding="utf-8")
    return filename, q


# -----------------------------
# KDT OS v15 Governance Core
# -----------------------------
# These templates repair older vague quests and raise future quest quality.
PRACTICE_TEMPLATES.update({
    "Health Monitoring": {
        "title": "Mini Health Checker",
        "type": "Practice Quest",
        "goal": "Practice health monitoring by checking a tiny system and reporting whether it looks OK.",
        "what_to_build": "A Python command-line app that checks three fake or simple health values and prints a clear OK/WARNING report.",
        "requirements": [
            "Create a folder named mini_health_checker",
            "Create app.py",
            "Create three checks: cpu_check, memory_check, and disk_check",
            "Each check must return OK or WARNING",
            "Print a final health summary",
            "Create README.md explaining how to run it"
        ],
        "success_criteria": [
            "app.py exists",
            "At least three health checks exist",
            "Output clearly shows OK or WARNING",
            "README.md includes the run command",
            "The project can be uploaded as proof"
        ],
        "steps": [
            "Create a new folder named mini_health_checker",
            "Create a file named app.py",
            "Inside app.py, create a function named cpu_check() that returns OK",
            "Create memory_check() that returns OK",
            "Create disk_check() that returns WARNING",
            "Create a main section that calls all three functions",
            "Print each result on its own line",
            "Print a final line that says Overall Health: Needs Attention if any check is WARNING",
            "Run python app.py",
            "Create README.md with the exact command: python app.py",
            "Zip the folder and submit it"
        ],
        "proof": [
            "Upload project ZIP",
            "Include app.py",
            "Include README.md",
            "Optional screenshot of terminal output"
        ],
        "verification_patterns": ["def cpu_check", "def memory_check", "def disk_check", "Overall Health", "WARNING"],
        "difficulty": "Beginner",
        "estimated_time": "25-45 minutes"
    },
    "Python": {
        "title": "Python Function Practice: Expense Totaler",
        "type": "Practice Quest",
        "goal": "Practice Python functions, lists, loops, and simple output with an exact beginner build.",
        "what_to_build": "A command-line app that stores three expenses in a list and prints the total cost.",
        "requirements": [
            "Create a folder named python_expense_totaler",
            "Create app.py",
            "Create a function named add_expense",
            "Create a function named calculate_total",
            "Store at least three expenses",
            "Print the final total"
        ],
        "success_criteria": [
            "app.py exists",
            "add_expense function exists",
            "calculate_total function exists",
            "At least three expenses are added",
            "Final total prints correctly"
        ],
        "steps": [
            "Create a folder named python_expense_totaler",
            "Create app.py",
            "Create an empty list named expenses",
            "Create add_expense(amount) that appends amount to expenses",
            "Create calculate_total() that loops through expenses and returns the total",
            "Call add_expense three times with different numbers",
            "Call calculate_total()",
            "Print the result as Total: $X",
            "Run python app.py",
            "Create README.md with what you practiced",
            "Zip the project folder and submit it"
        ],
        "proof": [
            "Upload project ZIP",
            "Include app.py",
            "Include README.md"
        ],
        "verification_patterns": ["def add_expense", "def calculate_total", "expenses", "for ", "print"],
        "difficulty": "Beginner",
        "estimated_time": "20-40 minutes"
    }
})

def governance_log(event: Dict[str, Any]) -> None:
    data = []
    if GOVERNANCE_LOG_FILE.exists():
        try:
            data = json.loads(GOVERNANCE_LOG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = []
    event.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
    data.insert(0, event)
    GOVERNANCE_LOG_FILE.write_text(json.dumps(data[:300], indent=2), encoding="utf-8")

def quest_governance_decision(quest: Dict[str, Any]) -> Dict[str, Any]:
    q = apply_quest_quality(dict(quest))
    quality = q.get("quest_quality", {})
    score = quality.get("score", 0)
    failed = [c for c in quality.get("checks", []) if not c.get("ok")]
    if score >= 90:
        action = "Keep"
    elif score >= QUEST_MINIMUM_SCORE:
        action = "Keep with warning"
    elif score >= 70:
        action = "Upgrade"
    else:
        action = "Regenerate"
    return {
        "score": score,
        "action": action,
        "rating": quality.get("rating", "Unknown"),
        "failed_checks": failed,
        "minimum_score": QUEST_MINIMUM_SCORE,
        "approved": score >= QUEST_MINIMUM_SCORE,
    }

def quest_postmortem_for(quest: Dict[str, Any], filename: str, replacement: str = "") -> Dict[str, Any]:
    review = quest_governance_decision(quest)
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "original_file": filename,
        "quest_title": quest.get("title", filename),
        "skill": quest.get("skill", "Unknown"),
        "original_score": review["score"],
        "action": review["action"],
        "replacement_file": replacement,
        "failure_reasons": [
            {"check": c.get("name"), "fix": c.get("fix")} for c in review.get("failed_checks", [])
        ],
        "lesson_learned": "Future quests must include exact blocker, smallest action, steps, success criteria, proof, and return path before becoming active.",
    }

def archive_quest(filename: str, reason: str, replacement_file: str = "") -> Dict[str, Any] | None:
    path = QUEST_DIR / filename
    if not path.exists():
        return None
    quest = json.loads(path.read_text(encoding="utf-8"))
    quest["status"] = "Superseded" if replacement_file else "Archived"
    quest["archived_at"] = datetime.now().isoformat(timespec="seconds")
    quest["archive_reason"] = reason
    quest["superseded_by"] = replacement_file
    postmortem = quest_postmortem_for(quest, filename, replacement_file)
    archive_name = filename.replace(".json", "") + "_archived.json"
    post_name = filename.replace(".json", "") + "_postmortem.json"
    (QUEST_ARCHIVE_DIR / archive_name).write_text(json.dumps(quest, indent=2), encoding="utf-8")
    (QUEST_POSTMORTEM_DIR / post_name).write_text(json.dumps(postmortem, indent=2), encoding="utf-8")
    path.write_text(json.dumps(quest, indent=2), encoding="utf-8")
    governance_log({"type": "quest_archived", "quest": filename, "replacement": replacement_file, "score": postmortem["original_score"], "reason": reason})
    return postmortem


def intelligent_replacement_template(old: Dict[str, Any]) -> Dict[str, Any]:
    """Create a context-specific replacement instead of another generic practice quest."""
    skill = normalize_skill(old.get("skill", "Python"))
    title = old.get("title", "")
    source = old.get("source_project", "Quest Maintenance")
    resume_project = old.get("resume_project", "") or old.get("source_project", "")
    gap = old.get("user_gap", f"I need exact practice with {skill}.")
    base = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_project": source,
        "origin_report": old.get("origin_report", ""),
        "resume_project": resume_project,
        "connected_goal": old.get("connected_goal", ""),
        "skill": skill,
        "user_gap": gap,
        "quest_type": old.get("quest_type", "Practice Quest"),
        "difficulty": "Beginner",
        "estimated_time": "30-60 minutes",
        "ai_generated": False,
        "ai_parse_mode": "governance_context_template_v2",
        "ai_raw_response": "",
        "submissions": [],
        "status": "Assigned",
        "resume_rule": old.get("resume_rule") or "After this quest is complete, return to the original project or goal that caused it.",
    }

    # Project-aware replacements for common detected skills.
    if skill in ("Active Directory", "CPU Usage", "Python"):
        tpl = PRACTICE_TEMPLATES.get(skill)
        if tpl:
            base.update(tpl)
            base["proof_required"] = base.pop("proof", base.get("proof_required", []))
            return apply_quest_quality(base)
    if skill in ("Testing",) or "smoke" in title.lower():
        base.update({
            "title": "Route Smoke Test Suite",
            "goal": "Prove the Flask project still opens its important pages after changes.",
            "what_to_build": "A pytest smoke test file named tests/test_routes.py that checks key Flask routes return HTTP 200 instead of crashing.",
            "requirements": ["Create folder tests", "Create tests/test_routes.py", "Import the Flask app object", "Create a test client", "Test at least three routes", "Document the pytest command in README.md"],
            "success_criteria": ["tests/test_routes.py exists", "At least three test functions exist", "pytest runs without import errors", "Each tested route returns status code 200", "README.md includes the test command"],
            "steps": ["Create a folder named tests", "Inside it create test_routes.py", "Open app.py and identify the Flask app variable name", "In test_routes.py import that app variable", "Create a pytest fixture or simple test client", "Write test_dashboard_route() for / or /dashboard", "Write test_quests_route() for /quests", "Write test_projects_route() for /projects", "Run pytest in the terminal", "If a route fails, write the failing route name in README.md", "Add the command python -m pytest to README.md", "Zip and upload the updated project"],
            "proof_required": ["Upload project ZIP", "Include tests/test_routes.py", "Include README.md with test command", "Include screenshot or copied terminal output showing pytest results", "Answer: which route would have caught the last navigation bug?"],
            "verification_patterns": [r"def test_", r"test_client", r"status_code", r"pytest", r"/quests|/projects|/dashboard"],
        })
    elif skill in ("API / Routes", "Flask"):
        base.update({
            "title": "Flask Route Inventory Checker",
            "goal": "Practice understanding routes by listing and checking the routes in a Flask project.",
            "what_to_build": "A Python script named route_inventory.py that imports the Flask app and prints every route rule and endpoint.",
            "requirements": ["Create route_inventory.py", "Import the Flask app", "Loop through app.url_map.iter_rules()", "Print rule, endpoint, and allowed methods", "Save the output to routes_report.txt"],
            "success_criteria": ["route_inventory.py exists", "app.url_map.iter_rules() is used", "routes_report.txt is created", "At least one route is listed", "README.md explains how to run it"],
            "steps": ["Create route_inventory.py in the project root", "Import the app object from app.py", "Create an empty list named route_lines", "Loop through app.url_map.iter_rules()", "For each rule, format endpoint, URL rule, and methods", "Print each formatted line", "Write all lines into routes_report.txt", "Run python route_inventory.py", "Open routes_report.txt and confirm routes appear", "Add run instructions to README.md", "Zip and upload the project"],
            "proof_required": ["Upload ZIP", "Include route_inventory.py", "Include routes_report.txt", "Include README.md", "Answer: which route surprised you or seems most important?"],
            "verification_patterns": [r"url_map\.iter_rules", r"routes_report\.txt", r"endpoint", r"methods"],
        })
    elif skill == "SQLite":
        base.update(PRACTICE_TEMPLATES.get("SQLite", {}))
        base["title"] = "SQLite CRUD Quest: Workout Database"
        base["proof_required"] = base.pop("proof", base.get("proof_required", []))
        base["requirements"] = ["Create folder workout_database_crud", "Create app.py", "Create workouts.db", "Create workouts table", "Add menu options for Create, Read, Update, Delete", "Add README.md with run steps"]
        base["proof_required"] = ["Upload ZIP", "Include app.py", "Include README.md", "Include workouts.db if created", "Answer: what is the difference between a row and a table?"]
    elif skill == "Python":
        base.update(PRACTICE_TEMPLATES.get("Python", {}))
        base["proof_required"] = base.pop("proof", base.get("proof_required", []))
        base["proof_required"] = ["Upload ZIP", "Include app.py", "Include README.md", "Include screenshot or copied terminal output", "Answer: what does calculate_total() return?"]
    elif skill == "Health Monitoring":
        base.update(PRACTICE_TEMPLATES.get("Health Monitoring", {}))
        base["proof_required"] = base.pop("proof", base.get("proof_required", []))
        base["proof_required"] = ["Upload ZIP", "Include app.py", "Include README.md", "Include screenshot or copied terminal output showing OK/WARNING", "Answer: what makes a check become WARNING?"]
    elif skill == "JavaScript":
        base.update(PRACTICE_TEMPLATES.get("JavaScript", {}))
        base["proof_required"] = base.pop("proof", base.get("proof_required", []))
        base["proof_required"] = ["Upload ZIP", "Include index.html, style.css, script.js", "Include README.md", "Answer: what does fetch() return before .json() is called?"]
    elif skill == "HTML/CSS":
        base.update(PRACTICE_TEMPLATES.get("HTML/CSS", {}))
        base["proof_required"] = base.pop("proof", base.get("proof_required", []))
        base["proof_required"] = ["Upload ZIP", "Include index.html", "Include style.css", "Include screenshot or README note explaining the mobile layout"]
    else:
        # Generic but still non-cloned: exact single-file concept proof.
        safe = slugify(skill) or "skill"
        base.update({
            "title": f"{skill} Single Proof Quest",
            "goal": f"Create one visible proof that you can use {skill} in a tiny controlled task.",
            "what_to_build": f"A folder named {safe}_single_proof with one README.md and one artifact that proves {skill} one time.",
            "requirements": [f"Create folder {safe}_single_proof", "Create README.md", f"Create one visible artifact for {skill}", "Write exactly what you practiced", "Write one thing still confusing"],
            "success_criteria": ["Folder exists", "README.md exists", "Artifact exists", "Explanation is specific", "Proof can be reviewed"],
            "steps": [f"Create folder {safe}_single_proof", "Create README.md", f"Create one small artifact showing {skill}", "Run/open/show the artifact", "Write three bullet points in README.md: what I did, what worked, what confused me", "Zip the folder", "Upload it as proof"],
            "proof_required": ["Upload ZIP", "Include README.md", "Include the artifact", "Answer: what did this prove?"],
            "verification_patterns": [],
        })
    base["why_this_exists"] = f"This replaces an older quest that looked too generic. KDT OS regenerated it using the skill ({skill}), source ({source}), and your need for exact, verifiable steps."
    base["teach_me_breakdown"] = exact_breakdown_for(skill)
    return apply_quest_quality(base)


def regenerate_quest(filename: str) -> tuple[str, Dict[str, Any]] | tuple[str, None]:
    path = QUEST_DIR / filename
    if not path.exists():
        return "", None
    old = json.loads(path.read_text(encoding="utf-8"))
    newq = intelligent_replacement_template(old)
    newq["regenerated_from"] = filename
    newq["version"] = int(old.get("version", 1)) + 1
    newq["governance_note"] = "Generated by Quest Governance v2 because the previous quest was weak, vague, cloned, or below the 85% quality standard."
    apply_quest_quality(newq)
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", f"{newq.get('title','quest')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")[:160]
    qfile = f"{slug}.json"
    (QUEST_DIR / qfile).write_text(json.dumps(newq, indent=2), encoding="utf-8")
    archive_quest(filename, "Quest failed Quest Intelligence v2 review and was regenerated with a specific replacement.", qfile)
    governance_log({"type": "quest_regenerated_v2", "old": filename, "new": qfile, "old_score": quest_governance_decision(old).get("score"), "new_score": newq.get("quest_quality", {}).get("score")})
    return qfile, newq

def list_archived_quests() -> List[Dict[str, Any]]:
    rows = []
    for p in sorted(QUEST_ARCHIVE_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            q = json.loads(p.read_text(encoding="utf-8"))
            q["filename"] = p.name
            rows.append(q)
        except Exception:
            pass
    return rows

def list_quest_postmortems() -> List[Dict[str, Any]]:
    rows = []
    for p in sorted(QUEST_POSTMORTEM_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            q = json.loads(p.read_text(encoding="utf-8"))
            q["filename"] = p.name
            rows.append(q)
        except Exception:
            pass
    return rows

def quest_instruction_signature(quest: Dict[str, Any]) -> str:
    """Detect clones by comparing instructions, not title. Titles can differ while the quest body stays generic."""
    parts = [
        str(quest.get("what_to_build", "")),
        "|".join(str(x) for x in quest.get("requirements", []) or []),
        "|".join(str(x) for x in quest.get("steps", []) or []),
        "|".join(str(x) for x in quest.get("proof_required", []) or []),
    ]
    clean = re.sub(r"\b(python|sqlite|testing|health monitoring|active directory|cpu usage|javascript|html/css|api / routes)\b", "skill", " ".join(parts).lower())
    clean = re.sub(r"\s+", " ", clean).strip()
    return hashlib.sha1(clean.encode("utf-8", errors="ignore")).hexdigest()

def quest_maintenance_summary() -> Dict[str, Any]:
    active = []
    signature_counts = {}
    raw = []
    for p in sorted(QUEST_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            q = json.loads(p.read_text(encoding="utf-8"))
            q["filename"] = p.name
            if q.get("status") in ["Archived", "Superseded", "Rejected"]:
                continue
            sig = quest_instruction_signature(q)
            q["instruction_signature"] = sig
            signature_counts[sig] = signature_counts.get(sig, 0) + 1
            raw.append(q)
        except Exception:
            pass
    for q in raw:
        review = quest_governance_decision(q)
        if signature_counts.get(q.get("instruction_signature"), 0) > 1:
            q.setdefault("quest_quality", quest_quality_check(q))
            q["quest_quality"]["template_clone"] = True
            q["quest_quality"].setdefault("penalties", []).append("Instruction clone detected across multiple active quests.")
            review["score"] = min(review.get("score", 0), 76)
            review["action"] = "Regenerate"
            review["approved"] = False
            review.setdefault("failed_checks", []).append({"name": "Duplicate instructional body", "fix": "Regenerate into a project/skill-specific quest instead of reusing the same body."})
        q["governance"] = review
        active.append(q)
    return {
        "quests": active,
        "total": len(active),
        "approved": sum(1 for q in active if q["governance"]["approved"]),
        "needs_work": sum(1 for q in active if not q["governance"]["approved"]),
        "archive_count": len(list_archived_quests()),
        "postmortem_count": len(list_quest_postmortems()),
        "minimum_score": QUEST_MINIMUM_SCORE,
    }



# KDT OS v0.6 goal-skill brain helpers
GOAL_SKILL_RULES = {
    "developer": ["HTML/CSS", "JavaScript", "Python", "Flask", "SQLite", "API / Routes", "Testing", "File Handling", "GitHub/Versioning"],
    "build anything": ["HTML/CSS", "JavaScript", "Python", "Flask", "SQLite", "API / Routes", "Testing", "React", "File Handling"],
    "kdt os": ["Python", "Flask", "SQLite", "File Handling", "Project Tracking", "Learning/Practice", "Testing", "Dashboard/UI"],
    "fieldseed": ["Python", "File Handling", "Health Monitoring", "Repair Planning", "Evidence Collection", "Testing"],
    "timora": ["HTML/CSS", "JavaScript", "Flask", "SQLite", "Authentication/Login", "Dashboard/UI"],
    "ab coach": ["HTML/CSS", "JavaScript", "Task Management", "Learning/Practice", "Database Storage"],
    "fitness": ["JavaScript", "Task Management", "Database Storage", "Dashboard/UI"],
    "it": ["PowerShell", "Python", "Health Monitoring", "Automation/Scheduling", "Knowledge Base", "File Handling"],
    "business": ["Dashboard/UI", "Database Storage", "Project Tracking", "Authentication/Login"],
    "ai": ["Python", "API / Routes", "JSON", "File Handling", "Database Storage"],
}

SKILL_DESCRIPTIONS = {
    "HTML/CSS": "Build the visible structure and style of web apps.",
    "JavaScript": "Make pages interactive with clicks, inputs, state, and browser behavior.",
    "Python": "Write backend logic, automation, file tools, and analyzers.",
    "Flask": "Create web routes, forms, dashboards, and local apps.",
    "SQLite": "Store and retrieve real app data in a local database.",
    "Database Storage": "Persist information so your apps remember progress and history.",
    "API / Routes": "Connect apps to data or create endpoints other pages can use.",
    "Testing": "Prove your app still works after changes.",
    "File Handling": "Read, write, scan, and analyze files or folders.",
    "React": "Build reusable UI components for larger interactive apps.",
    "PowerShell": "Automate Windows and IT support tasks.",
    "Health Monitoring": "Check systems/projects and explain status or issues.",
    "Repair Planning": "Turn detected issues into safe repair steps.",
    "Evidence Collection": "Save proof, screenshots, logs, or submissions.",
    "Project Tracking": "Track project status, versions, progress, and history.",
    "Learning/Practice": "Create repeated quests and skill-building reps.",
    "Dashboard/UI": "Create usable screens that show important information clearly.",
    "Task Management": "Add, complete, filter, and track tasks or habits.",
    "Authentication/Login": "Protect personal data with login or PIN access.",
    "Automation/Scheduling": "Run actions on a schedule or trigger reminders.",
    "Knowledge Base": "Store lessons, fixes, notes, and reusable understanding.",
    "GitHub/Versioning": "Track changes and preserve project history.",
    "JSON": "Store and exchange structured data in a simple file format.",
}

def skill_entry_for(skill_name: str) -> Dict[str, Any]:
    return load_skill_library().get(normalize_skill(skill_name), {})

def requirement_status(skill_name: str) -> Dict[str, Any]:
    skill_name = normalize_skill(skill_name)
    entry = skill_entry_for(skill_name)
    status = skill_status(entry) if entry else "Unknown"
    if status in {"Evidence Found"}:
        action = "Prove with a quest"
        reason = "KDT OS found this in code, but you have not proven you can rebuild it yet."
    elif status == "Rusty":
        action = "Refresh before using"
        reason = "You practiced it before, but it has not appeared recently."
    elif status in {"Practiced", "Proficient"}:
        action = "Ready, but refresh if unsure"
        reason = "You have submitted enough evidence to use this skill with more confidence."
    elif status == "Learning":
        action = "Continue practice"
        reason = "You have started practicing, but should complete more proof."
    else:
        action = "Start beginner quest"
        reason = "KDT OS does not have evidence for this skill yet."
    return {
        "skill": skill_name,
        "status": status,
        "action": action,
        "reason": reason,
        "description": SKILL_DESCRIPTIONS.get(skill_name, "A skill KDT OS can turn into exact quests."),
        "projects": entry.get("projects", []) if entry else [],
        "evidence_count": entry.get("evidence_count", 0) if entry else 0,
    }

def required_skills_for_text(text: str) -> List[str]:
    t = (text or "").lower()
    skills = []
    for key, vals in GOAL_SKILL_RULES.items():
        if key in t:
            skills.extend(vals)
    if not skills:
        skills = ["HTML/CSS", "JavaScript", "Python", "Flask", "SQLite", "Testing"]
    # preserve order, normalize, unique
    out=[]
    for s in skills:
        ns=normalize_skill(s)
        if ns not in out:
            out.append(ns)
    return out[:12]

def analyze_goal_gap(goal: Dict[str, Any]) -> Dict[str, Any]:
    text = " ".join([goal.get("goal_name", ""), goal.get("why", ""), goal.get("what_i_want_to_build", "")])
    required = [requirement_status(s) for s in required_skills_for_text(text)]
    blockers = [r for r in required if r["status"] in {"Unknown", "Evidence Found", "Rusty", "Learning"}]
    ready = [r for r in required if r["status"] in {"Practiced", "Proficient"}]
    next_skill = blockers[0]["skill"] if blockers else (required[0]["skill"] if required else "JavaScript")
    return {
        "required_skills": required,
        "blockers": blockers,
        "ready_skills": ready,
        "next_skill": next_skill,
        "summary": f"KDT OS found {len(required)} likely skills for this goal. {len(blockers)} need proof, refresh, or beginner practice.",
    }

def quests_for_skill(skill_name: str) -> List[Dict[str, Any]]:
    skill_name = normalize_skill(skill_name)
    matches=[]
    for q in list_quests():
        if normalize_skill(q.get("skill", "")) == skill_name:
            matches.append(q)
    return matches




# -----------------------------
# Knowledge Trust / Fact-Inference-Suggestion helpers
# -----------------------------
def project_names_set() -> set[str]:
    return {str(p.get("project_name", "")).strip().lower() for p in list_projects() if p.get("project_name")}


def build_project_context(project_mode: str, selected_project: str = "", new_project_name: str = "") -> Dict[str, Any]:
    """Classify whether a project is known fact, user-confirmed, or AI-suggested.
    KDT OS should never treat an inference as a fact.
    """
    project_mode = (project_mode or "unknown").strip()
    selected_project = (selected_project or "").strip()
    new_project_name = (new_project_name or "").strip()
    known = project_names_set()
    if project_mode == "existing" and selected_project:
        return {
            "mode": "existing",
            "name": selected_project,
            "knowledge_type": "fact" if selected_project.lower() in known else "inference",
            "source_type": "Uploaded Project" if selected_project.lower() in known else "User Selected Unverified Project",
            "confidence": 100 if selected_project.lower() in known else 60,
            "verification_status": "Verified" if selected_project.lower() in known else "Unverified",
            "source_note": "This project was selected from tracked uploaded projects." if selected_project.lower() in known else "User selected a project name that is not currently backed by an uploaded project record."
        }
    if project_mode == "new" and new_project_name:
        return {
            "mode": "new",
            "name": new_project_name,
            "knowledge_type": "fact",
            "source_type": "User Confirmed New Project",
            "confidence": 85,
            "verification_status": "Confirmed by User, Not Uploaded Yet",
            "source_note": "You named this as a new project. It becomes verified after you upload/analyze its files."
        }
    return {
        "mode": "unknown",
        "name": "",
        "knowledge_type": "suggestion",
        "source_type": "AI Suggestion Allowed",
        "confidence": 15,
        "verification_status": "Suggested / Needs Confirmation",
        "source_note": "You did not choose an existing or named new project, so KDT OS may suggest a project but must label it as unverified."
    }


def apply_trust_metadata_to_path(plan: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    project = plan.setdefault("project", {})
    if context.get("name"):
        project["name"] = context["name"]
    # If AI invented a project because user chose unknown, mark it clearly as suggested.
    if context.get("mode") == "unknown":
        project.setdefault("name", project.get("name") or "Suggested Project")
        project["knowledge_type"] = "suggestion"
        project["source_type"] = "AI Suggestion"
        project["confidence"] = 15
        project["verification_status"] = "Suggested / Needs Confirmation"
        project["source_note"] = "KDT OS suggested this project. It is not a verified project until you confirm it or upload/analyze files."
    else:
        project["knowledge_type"] = context.get("knowledge_type", "inference")
        project["source_type"] = context.get("source_type", "Unknown")
        project["confidence"] = context.get("confidence", 0)
        project["verification_status"] = context.get("verification_status", "Unverified")
        project["source_note"] = context.get("source_note", "")
    plan["trust"] = {
        "rule": "KDT OS must never treat an inference or suggestion as a fact.",
        "project": {
            "knowledge_type": project.get("knowledge_type"),
            "source_type": project.get("source_type"),
            "confidence": project.get("confidence"),
            "verification_status": project.get("verification_status"),
            "source_note": project.get("source_note"),
        },
        "known_vs_inferred": [
            "Facts come from uploaded/analyzed projects or direct user confirmation.",
            "Inferences come from AI reasoning and require review.",
            "Suggestions are ideas only until confirmed."
        ]
    }
    return plan


def trust_summary() -> Dict[str, int]:
    verified_projects = inferred_projects = suggested_paths = verified_skills = unverified_skills = 0
    for p in list_projects():
        kt = p.get("knowledge_type", "fact")
        status = p.get("verification_status", "Verified")
        if kt == "fact" and "Verified" in status:
            verified_projects += 1
        elif kt == "suggestion":
            suggested_paths += 1
        else:
            inferred_projects += 1
    for path in list_paths(200):
        project = path.get("project", {})
        kt = project.get("knowledge_type", "")
        if kt == "suggestion":
            suggested_paths += 1
        elif kt == "inference":
            inferred_projects += 1
    for _, entry in load_skill_library().items():
        if entry.get("completed_quests") or entry.get("submissions"):
            verified_skills += 1
        else:
            unverified_skills += 1
    return {
        "verified_projects": verified_projects,
        "inferred_projects": inferred_projects,
        "suggested_projects_or_paths": suggested_paths,
        "verified_skills": verified_skills,
        "unverified_skills": unverified_skills,
    }

# -----------------------------
# Universal Goal -> Project -> Skill -> Quest Path Engine
# -----------------------------
def path_record_path(path_id: str) -> Path:
    return PATH_DIR / f"{slugify(path_id)}.json"


def list_paths(limit: int = 20) -> List[Dict[str, Any]]:
    paths = []
    for path in sorted(PATH_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["filename"] = path.name
            paths.append(data)
        except Exception:
            pass
    return paths


def load_path(filename: str) -> Dict[str, Any]:
    path = PATH_DIR / filename
    if not path.exists():
        raise FileNotFoundError(filename)
    return json.loads(path.read_text(encoding="utf-8"))


def save_path(data: Dict[str, Any], filename: str | None = None) -> str:
    if not filename:
        base = data.get("project", {}).get("name") or data.get("goal", {}).get("name") or "path"
        filename = f"{slugify(base)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    (PATH_DIR / filename).write_text(json.dumps(data, indent=2), encoding="utf-8")
    return filename


def known_skill_snapshot() -> str:
    skills = load_skill_library()
    if not skills:
        return "No uploaded skill evidence yet."
    lines = []
    for name, entry in list(skills.items())[:30]:
        projects = ", ".join(entry.get("projects", [])[:4]) or "none"
        lines.append(f"- {name}: {entry.get('status', 'Unknown')} | projects: {projects} | note: {entry.get('confidence_label', '')}")
    return "\n".join(lines)


def existing_project_snapshot() -> str:
    projects = list_projects()
    if not projects:
        return "No tracked projects yet."
    lines = []
    for project in projects[:20]:
        caps = ", ".join(project.get("latest_capabilities", [])[:8])
        tech = ", ".join(project.get("latest_technologies", [])[:8])
        lines.append(f"- {project.get('project_name')}: versions={len(project.get('versions', []))}; capabilities={caps}; technologies={tech}")
    return "\n".join(lines)


def goal_snapshot() -> str:
    goals = list_goals()
    if not goals:
        return "No saved goals yet."
    lines = []
    for goal in goals[:20]:
        lines.append(f"- {goal.get('goal_name')}: {goal.get('what_i_want_to_build','')}")
    return "\n".join(lines)


def parse_path_json(raw: str) -> Dict[str, Any] | None:
    data = extract_json_object(raw)
    if not isinstance(data, dict):
        return None
    data.setdefault("goal", {})
    data.setdefault("project", {})
    data.setdefault("required_skills", [])
    data.setdefault("quest_plan", [])
    data.setdefault("proof_strategy", [])
    data.setdefault("return_rule", "Finish a quest, update evidence, then return to the project that caused the quest.")
    if isinstance(data.get("goal"), str):
        data["goal"] = {"name": data.get("goal"), "why": ""}
    if isinstance(data.get("project"), str):
        data["project"] = {"name": data.get("project"), "purpose": ""}
    return data


def fallback_path_plan(problem: str) -> Dict[str, Any]:
    return {
        "goal": {"name": "Turn this problem into a buildable path", "why": "KDT OS could not get a full AI plan, so it created a safe starter path."},
        "project": {"name": "Starter Practice Project", "purpose": problem, "is_new_project_needed": True, "reuse_existing_project": "", "reason": "Fallback plan created."},
        "problem_summary": problem,
        "required_skills": [
            {"skill": "Planning", "status": "Unknown", "why_needed": "Break the problem into smaller pieces.", "next_action": "Write the smallest possible version of what you want."},
            {"skill": "File Handling", "status": "Unknown", "why_needed": "Most KDT OS projects need files or saved proof.", "next_action": "Create one project folder and README."}
        ],
        "quest_plan": [
            {
                "title": "Define the Smallest Working Version",
                "skill": "Planning",
                "difficulty": "Beginner",
                "estimated_time": "15-20 minutes",
                "why": "Before building, KDT OS needs a clear smallest version.",
                "what_to_build": "A README.md that explains the exact smallest version of the project.",
                "requirements": ["Create a folder", "Create README.md", "Write the project name", "Write 3 required features", "Write what proof would show it works"],
                "steps": ["Create the project folder", "Open VS Code", "Create README.md", "Add Purpose, Required Features, Proof Needed", "Save it"],
                "success_criteria": ["README.md exists", "Purpose is written", "At least 3 features are listed", "Proof needed is listed"],
                "proof_required": ["Upload the project ZIP with README.md"]
            }
        ],
        "proof_strategy": ["Every quest must require proof", "Proof must include the work plus a short explanation"],
        "return_rule": "After each quest, return to the original project path and choose the next step."
    }



# -----------------------------
# Universal Decision Engine v2
# -----------------------------
def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9+#.]+", (text or "").lower()))


def _blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, list):
        return len(value) == 0 or all(_blank(x) for x in value)
    if isinstance(value, dict):
        return len(value) == 0 or all(_blank(v) for v in value.values())
    return False


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return [x for x in value if not _blank(x)]
    if isinstance(value, str):
        # Split simple newline/bullet responses into a usable list.
        parts = [re.sub(r"^[-*\d.\s]+", "", x).strip() for x in value.splitlines()]
        parts = [x for x in parts if x]
        return parts or [value.strip()]
    return [value]


def _quest(title, skill, difficulty, estimated_time, why, what_to_build, requirements, steps, success_criteria, proof_required):
    return {
        "title": title,
        "skill": skill,
        "difficulty": difficulty,
        "estimated_time": estimated_time,
        "why": why,
        "what_to_build": what_to_build,
        "requirements": requirements,
        "steps": steps,
        "success_criteria": success_criteria,
        "proof_required": proof_required,
    }


def infer_domain_profile(problem: str, context_goal: str = "", project_context: Dict[str, Any] | None = None, request_type: str = "auto") -> Dict[str, Any]:
    """Universal-ish decision engine. It does not need to know the exact project.
    It detects tool type, stack, bottleneck, and bridge path from intent/category.
    """
    project_context = project_context or {}
    text = f"{problem} {context_goal} {project_context.get('name','')}".lower()
    req_type = request_type if request_type and request_type != "auto" else classify_request_type(problem)
    selected_name = project_context.get("name", "").strip()

    def base(project_name, purpose, goal_name="Build a useful project", goal_why="Turn the idea into a working tool with proof."):
        return {
            "goal": {"name": context_goal or goal_name, "why": goal_why},
            "project": {"name": selected_name or project_name, "purpose": purpose, "is_new_project_needed": not bool(selected_name), "reuse_existing_project": selected_name if project_context.get("mode") == "existing" else "", "reason": "Use the selected existing project." if selected_name else "New or suggested project may be useful."},
            "request_type": req_type,
            "problem_summary": problem,
            "tool_decision": {},
            "bottleneck": {},
            "redundancy_review": {"should_reuse_existing": bool(selected_name), "reuse_project": selected_name, "keep_separate_reason": "Keep separate only if the purpose is different from existing tracked work.", "redundant_items_to_remove": []},
            "required_skills": [],
            "quest_plan": [],
            "proof_strategy": [],
            "return_rule": "Complete one quest, submit proof, update skill evidence, then return to this path and choose the next quest."
        }


    # Project Source Manager / folder analysis / project intelligence feature
    if any(k in text for k in ["analyze local", "local project", "project folder", "folder path", "scan folder", "detect languages", "framework", "project health", "changes over time", "source manager"]):
        plan = base(selected_name or "Project Source Manager", "Allow KDT OS to attach and rescan local project folders so it can detect languages, frameworks, health, and changes over time.", "Build KDT OS Into My Personal Operating System", "KDT OS should observe real projects instead of requiring manual explanation every time.")
        plan["request_type"] = "add_feature"
        plan["tool_decision"] = {"best_tool_type":"KDT OS core feature", "best_stack_now":["Python", "Flask", "pathlib", "JSON project records", "Jinja UI"], "best_stack_later":["SQLite project index", "Git diff integration", "background scans"], "why_this_stack":"KDT OS already runs locally in Flask/Python, so folder analysis should use Python file-system scanning first instead of requiring ZIP uploads.", "bridge_needed": False}
        plan["bottleneck"] = {"current_bottleneck":"KDT OS depends too much on ZIP uploads and manual descriptions", "why_it_blocks_progress":"Living projects change in folders. If KDT OS cannot rescan folders, project memory becomes stale.", "next_smallest_action":"Store a project source type and local folder path, then scan that path for files, languages, and changed signatures."}
        plan["required_skills"] = [
            {"skill":"File Handling", "status":"Needs Proof", "why_needed":"Folder scanning requires safely reading local directories and ignoring junk folders.", "next_action":"Build a folder scanner with pathlib."},
            {"skill":"Project Tracking", "status":"Needs Proof", "why_needed":"Each project needs source type, path, last scan, and version history.", "next_action":"Add source fields to project records."},
            {"skill":"Gap Analysis", "status":"Missing", "why_needed":"KDT OS must turn scan results into useful next actions.", "next_action":"Create strengths/gaps/recommended next build output."}
        ]
        plan["quest_plan"] = [
            _quest("Store Project Source Paths", "Project Tracking", "Beginner", "45-60 minutes", "This lets KDT OS remember where a living project folder is located.", "Add source_type and source_path fields to project records and display them on the project page.", ["Update project JSON schema", "Add source_type", "Add source_path", "Display source on project page", "Preserve existing ZIP projects"], ["Open app.py", "Find project record creation", "Add source_type default", "Add source_path default", "Update project template", "Test with KDT OS folder path", "Confirm old projects still load"], ["Existing projects still load", "Project page shows source type", "Folder path can be saved", "No data folders are deleted"], ["Upload updated ZIP", "Include screenshot of project source section", "Explain how old projects are preserved"]),
            _quest("Build Local Folder Scanner", "File Handling", "Beginner", "60-90 minutes", "This replaces constant ZIP re-uploads for active projects.", "Create a Python function that scans a folder path, counts files, detects extensions, and ignores cache/data folders.", ["Create scan_project_folder function", "Use pathlib", "Ignore __pycache__", "Ignore uploads/workspace if needed", "Return file count and extensions", "Display result"], ["Open app.py", "Create scan_project_folder(path)", "Use Path(path).rglob('*')", "Skip folders like __pycache__", "Count file extensions", "Return a dictionary", "Call it from Sources page", "Display scan result"], ["Scanner accepts folder path", "Scanner counts files", "Scanner ignores junk folders", "Result appears in UI"], ["Upload ZIP", "Include screenshot of folder scan result", "Explain one ignored folder rule"]),
            _quest("Compare Folder Scans", "Project Tracking", "Intermediate", "75-120 minutes", "This lets KDT OS understand project evolution over time.", "Save a scan signature and compare current scan against the previous scan for added/removed files and changed health.", ["Save scan signature", "Store last_scan", "Compare file counts", "Compare technologies", "Show changes"], ["Create scan signature dict", "Save it in project record", "On next scan, load previous signature", "Calculate added/removed files or count changes", "Show comparison on project page"], ["First scan saves baseline", "Second scan compares changes", "UI shows what changed", "Duplicate unchanged scan is not treated as progress"], ["Upload ZIP", "Include screenshot showing scan comparison", "Explain what changed between scans"])
        ]
        plan["proof_strategy"] = ["Use a real local folder path", "Proof must show scan result and saved project source", "Second proof should show comparison after a change"]
        return plan

    # Add feature / screenshot verification / evidence verification
    if any(k in text for k in ["screenshot", "image verification", "verify screenshots", "evidence verification", "photo proof"]):
        plan = base(selected_name or "Evidence Verification Tool", "Add or build screenshot/evidence verification so uploaded proof can be checked before increasing skill confidence.", "Improve project proof and verification", "Make project progress harder to fake and easier to trust.")
        plan["tool_decision"] = {"best_tool_type":"Existing web/tool project" if selected_name else "Browser/web tool", "best_stack_now":["Python", "Flask", "HTML forms", "file uploads", "Pillow metadata check"], "best_stack_later":["OpenCV", "OCR if needed", "LLM vision or image model"], "why_this_stack":"This fits KDT OS/FieldSeed-style projects because screenshot proof starts with upload, storage, metadata, and human/AI review before advanced image analysis.", "bridge_needed": True}
        plan["bottleneck"] = {"current_bottleneck":"No screenshot proof workflow", "why_it_blocks_progress":"KDT OS cannot verify visual evidence until it can accept, store, display, and review screenshot uploads.", "next_smallest_action":"Create a screenshot upload route and display uploaded proof on the quest/report page."}
        plan["required_skills"] = [
            {"skill":"Flask File Uploads", "status":"Needs Proof", "why_needed":"Screenshots must be uploaded and saved safely.", "next_action":"Build a small upload form that accepts PNG/JPG files."},
            {"skill":"Evidence Verification", "status":"Missing", "why_needed":"The system needs rules for what valid proof looks like.", "next_action":"Create a checklist for screenshot filename, file type, size, and user explanation."},
            {"skill":"Image Handling", "status":"Missing", "why_needed":"Later verification may inspect image metadata or content.", "next_action":"Use Pillow to read file size and dimensions."},
        ]
        plan["quest_plan"] = [
            _quest("Add Screenshot Upload Proof", "Flask File Uploads", "Beginner", "45-75 minutes", "This creates the foundation for visual proof verification.", "Add a form to upload a screenshot and save it in a proof folder.", ["Create proof_uploads folder", "Add route /proof/upload", "Accept .png, .jpg, .jpeg", "Save file with timestamp", "Show uploaded screenshot on a page"], ["Open app.py", "Create proof_uploads directory", "Add allowed_file helper", "Add upload route", "Create upload form in template", "Upload a test screenshot", "Confirm the image appears"], ["Route accepts screenshots", "Invalid file types are rejected", "Uploaded image is visible", "No duplicate filename overwrite"], ["Upload updated project ZIP", "Include screenshot of upload page", "Explain what validation was added"]),
            _quest("Create Screenshot Proof Checklist", "Evidence Verification", "Beginner", "30-45 minutes", "KDT OS needs to know what counts as acceptable screenshot evidence.", "Create a checklist that a screenshot submission must satisfy before it can increase skill confidence.", ["List proof requirements", "Require user explanation", "Store checklist result", "Show Pass/Needs Review"], ["Create proof_rules.json", "Add fields: file_type, screenshot_visible, explanation_present, reviewer_status", "Display checklist on proof page", "Test with one uploaded screenshot"], ["Checklist exists", "Explanation is required", "Status can be Pass or Needs Review"], ["Upload ZIP", "Include proof_rules.json", "Submit one screenshot proof example"]),
        ]
        plan["proof_strategy"] = ["Upload updated project ZIP", "Show screenshot proof page working", "Explain how invalid proof is rejected"]
        return plan

    # Serious / 3D / game
    if any(k in text for k in ["3d", "fantasy game", "open world", "game", "unreal", "unity", "rpg"]):
        plan = base(selected_name or "Game Prototype Path", "Create a game development path that starts small and bridges toward the correct long-term engine.", "Become a developer who can build games", "Learn the coding and engine skills needed to build game ideas over time.")
        serious = any(k in text for k in ["serious", "3d", "open world", "realistic", "unreal", "fantasy"])
        plan["tool_decision"] = {"best_tool_type":"Game", "best_stack_now":["JavaScript Canvas for tiny mechanics", "Unity C# for early 3D prototypes"], "best_stack_later":["Unreal Engine", "C++", "Blueprints", "C# if Unity path is chosen"], "why_this_stack":"A serious 3D game should eventually use a real engine. The bridge path prevents jumping straight into C++/Unreal before core game-loop skills are proven.", "bridge_needed": True}
        plan["bottleneck"] = {"current_bottleneck":"Game scope is too large for the current first step", "why_it_blocks_progress":"A serious 3D fantasy game has movement, camera, world scale, assets, collision, AI, UI, saving, and performance. Starting with all of it will overwhelm the project.", "next_smallest_action":"Build one tiny movement prototype and prove you understand the game loop."}
        plan["required_skills"] = [
            {"skill":"Game Loop", "status":"Missing", "why_needed":"Every game updates input, movement, and drawing repeatedly.", "next_action":"Build a tiny 2D movement prototype."},
            {"skill":"C# / Unity or Unreal Blueprint", "status":"Missing", "why_needed":"3D games need engine fundamentals before advanced systems.", "next_action":"Create a simple 3D scene with a controllable character."},
            {"skill":"C++ / Unreal", "status":"Advanced Bridge", "why_needed":"Useful for serious Unreal systems later, not the first beginner step.", "next_action":"Learn Unreal Blueprint first, then C++ classes."},
        ]
        plan["quest_plan"] = [
            _quest("Build a Tiny 2D Movement Prototype", "JavaScript Game Loop", "Beginner", "60-90 minutes", "This teaches input and movement without engine complexity.", "A browser canvas where a square/character moves with WASD or arrow keys.", ["index.html", "script.js", "canvas", "keyboard input", "movement on screen"], ["Create game_movement_prototype folder", "Create index.html and script.js", "Add canvas", "Draw a square", "Track key presses", "Move square each frame", "Write README with controls"], ["Character moves smoothly", "Movement stops when key released", "README explains game loop"], ["Upload ZIP", "Include screenshot or short note showing movement works"]),
            _quest("Create a First 3D Engine Scene", "Unity C# or Unreal Blueprint", "Intermediate", "2-4 hours", "This begins the real 3D bridge path.", "A simple 3D scene with floor, camera, lighting, and controllable character/cube.", ["Install/use chosen engine", "Create floor", "Create player object", "Add movement", "Add camera"], ["Choose Unity or Unreal", "Create new 3D project", "Add floor", "Add player", "Add basic movement", "Run scene", "Record what worked/failed"], ["Scene runs", "Player/cube moves", "Camera follows or views player", "You can explain which engine you used and why"], ["Upload screenshots", "Upload project notes/README", "Optional small project ZIP if reasonable"]),
            _quest("Write the Smallest Game Design Slice", "Game Architecture", "Beginner", "30-45 minutes", "This prevents the project from becoming too massive too early.", "A one-page design slice for the smallest playable fantasy world demo.", ["Define player action", "Define world area", "Define one obstacle", "Define one success condition"], ["Create README.md", "Write One-Minute Game Pitch", "Write Smallest Playable Demo", "List 5 features NOT allowed yet", "List proof that demo works"], ["Scope is one page", "Demo has one clear win condition", "Future features are parked"], ["Upload README.md or ZIP containing it"]),
        ]
        plan["proof_strategy"] = ["Proof must show a playable mechanic, not just a plan", "Screenshots/video notes are okay for engine work", "Return to the game path after each bridge skill"]
        return plan

    # Guitar / singing / music tools
    if any(k in text for k in ["guitar", "chord", "singing", "voice", "vocal", "piano", "violin", "music"]):
        is_singing = any(k in text for k in ["singing", "voice", "vocal"])
        project = "Singing Practice Tool" if is_singing else "Guitar Chord Trainer"
        skill1 = "Voice Practice Tracking" if is_singing else "Chord Practice"
        plan = base(selected_name or project, "Build a practice tool for music improvement instead of giving direct coaching only.", "Improve music skills through tools", "Use software to guide practice, track progress, and create repeatable routines.")
        plan["tool_decision"] = {"best_tool_type":"Browser app first, mobile/PWA later", "best_stack_now":["HTML/CSS/JavaScript", "localStorage"], "best_stack_later":["React", "PWA", "Web Audio API", "React Native if phone-native features matter"], "why_this_stack":"A browser/PWA tool is fastest to build and can run on laptop or phone. Audio analysis can be added later with Web Audio.", "bridge_needed": True}
        plan["bottleneck"] = {"current_bottleneck":"No repeatable practice system", "why_it_blocks_progress":"Without a tool, practice is easy to forget and hard to measure.", "next_smallest_action":"Build a tiny practice tracker with one exercise and one completion button."}
        plan["required_skills"] = [
            {"skill":"HTML/CSS/JavaScript", "status":"Known/Needs Proof", "why_needed":"The first version should be a simple browser app.", "next_action":"Build one interactive practice card."},
            {"skill": skill1, "status":"Missing", "why_needed":"The tool needs practice items that match the skill.", "next_action":"Define 5 beginner practice items."},
            {"skill":"Progress Tracking", "status":"Missing", "why_needed":"The app should remember completed practice sessions.", "next_action":"Save completions in localStorage."},
        ]
        if is_singing:
            quest = _quest("Build a Singing Practice Tracker", "JavaScript", "Beginner", "60-90 minutes", "This creates a tool to support singing practice without pretending KDT OS directly teaches singing technique.", "A browser app with one daily vocal warmup card, a timer, and a completion log.", ["index.html", "style.css", "script.js", "Warmup title", "Start timer button", "Mark complete button", "localStorage history"], ["Create project folder", "Create HTML/CSS/JS files", "Add one warmup card", "Add 60-second timer", "Add Mark Complete", "Save completion date to localStorage", "Display last 5 completions"], ["Timer works", "Completion saves after refresh", "History displays", "README explains how it helps singing practice"], ["Upload project ZIP", "Include screenshot", "Explain what routine it tracks"])
        else:
            quest = _quest("Build a Guitar Chord Trainer", "JavaScript", "Beginner", "60-90 minutes", "This builds a tool you can use repeatedly to practice chords.", "A browser app that shows one chord at a time and tracks correct/incorrect attempts.", ["index.html", "style.css", "script.js", "Array of at least 5 chords", "Next Chord button", "Correct button", "Missed button", "Score display"], ["Create guitar_chord_trainer folder", "Create files", "Add chord array: G, C, D, Em, Am", "Show first chord", "Add Next button", "Add Correct/Missed buttons", "Update score", "Save score in localStorage"], ["At least 5 chords appear", "Buttons work", "Score updates", "Score remains after refresh"], ["Upload project ZIP", "Include screenshot", "Explain which chords you practiced"])
        plan["quest_plan"] = [quest]
        plan["proof_strategy"] = ["Proof is the working practice tool, not just a statement that you practiced", "Upload ZIP and a short explanation of how the tool supports the music goal"]
        return plan

    # Stock bot / trading/data analysis
    if any(k in text for k in ["stock", "trading", "bot", "invest", "market", "options"]):
        plan = base(selected_name or "Stock Bot Project", "Build a data-driven stock analysis tool through safe learning steps.", "Build useful financial analysis tools", "Learn APIs, data handling, and analysis while avoiding blind trading decisions.")
        plan["tool_decision"] = {"best_tool_type":"AI/data tool with dashboard later", "best_stack_now":["Python", "requests", "JSON", "CSV", "SQLite"], "best_stack_later":["Pandas", "FastAPI/Flask", "charts", "broker/data APIs", "machine learning only after data basics"], "why_this_stack":"Stock tools require data collection before prediction. Python is the best first stack for APIs and analysis.", "bridge_needed": True}
        plan["bottleneck"] = {"current_bottleneck":"No proven market data pipeline", "why_it_blocks_progress":"A stock bot cannot analyze anything until it can reliably fetch or load price/news data.", "next_smallest_action":"Make one API-style data request or load sample stock JSON and display price fields."}
        plan["required_skills"] = [
            {"skill":"Python APIs", "status":"Missing/Needs Proof", "why_needed":"The bot needs market data.", "next_action":"Fetch one stock quote or sample JSON."},
            {"skill":"Data Analysis", "status":"Missing", "why_needed":"The bot must calculate useful signals from data.", "next_action":"Calculate daily change from sample prices."},
            {"skill":"Risk Rules", "status":"Missing", "why_needed":"Trading tools need warnings and guardrails.", "next_action":"Write rules that say this is analysis, not financial advice."},
        ]
        plan["quest_plan"] = [
            _quest("Fetch or Load One Stock Quote", "Python APIs", "Beginner", "45-75 minutes", "This proves the data pipeline exists before any bot logic.", "A Python script that loads sample stock JSON or fetches one quote and prints symbol, price, and timestamp.", ["main.py", "sample_stock.json OR API request", "Print symbol", "Print price", "Handle missing data"], ["Create stock_quote_fetcher folder", "Create main.py", "Create sample_stock.json with symbol, price, timestamp", "Load JSON in Python", "Print the fields", "Add error handling for missing price", "Write README"], ["Script runs", "Symbol and price display", "README explains data source", "No buy/sell recommendation yet"], ["Upload ZIP", "Include main.py", "Include sample JSON or API notes"]),
            _quest("Calculate Simple Price Change", "Data Analysis", "Beginner", "45-60 minutes", "This starts analysis without pretending prediction is solved.", "A script that compares yesterday price vs today price and prints percent change.", ["prices list", "percent change calculation", "positive/negative output", "README explanation"], ["Create prices list", "Calculate difference", "Calculate percent", "Print result", "Add simple test values"], ["Percent formula works", "Output is readable", "You can explain the formula"], ["Upload ZIP", "Include calculation code", "Explain one example result"]),
        ]
        plan["proof_strategy"] = ["No real-money trading automation until data, testing, and risk rules are proven", "Proof should show data loading and calculations working"]
        return plan

    # Server / IT / Windows / AD / PowerShell
    if any(k in text for k in ["server", "windows", "active directory", "ad", "powershell", "it professional", "health tool", "monitor"]):
        plan = base(selected_name or "Server Health Tool", "Build an IT tool for monitoring, documenting, or automating Windows/server tasks.", "Become an Advanced IT Professional", "Build practical tools that improve troubleshooting and server support.")
        plan["tool_decision"] = {"best_tool_type":"Automation script plus dashboard", "best_stack_now":["PowerShell", "CSV/JSON", "Python or Flask dashboard later"], "best_stack_later":["Scheduled Tasks", "Windows Event Logs", "Ninja/ServiceNow style reporting", "web dashboard"], "why_this_stack":"Windows/server work is best started with PowerShell evidence collection, then visualized with Python/Flask later.", "bridge_needed": True}
        plan["bottleneck"] = {"current_bottleneck":"No repeatable server evidence collection", "why_it_blocks_progress":"You need reliable data before a dashboard or alert system matters.", "next_smallest_action":"Create one PowerShell script that exports CPU, RAM, disk, and uptime to JSON."}
        plan["required_skills"] = [
            {"skill":"PowerShell", "status":"Needs Proof", "why_needed":"Windows health checks are easiest in PowerShell.", "next_action":"Run one script that collects system info."},
            {"skill":"JSON Export", "status":"Missing", "why_needed":"KDT OS/dashboard can read structured output.", "next_action":"Export health result to JSON."},
            {"skill":"Dashboard/UI", "status":"Later", "why_needed":"A dashboard makes results easier to review.", "next_action":"Use Flask after script output works."},
        ]
        plan["quest_plan"] = [
            _quest("Create a PowerShell Health Snapshot", "PowerShell", "Beginner", "45-60 minutes", "This creates the evidence layer for any server health tool.", "A PowerShell script that displays computer name, uptime, CPU load, RAM usage, and disk free space.", ["health_check.ps1", "Computer name", "Uptime", "CPU load", "RAM usage", "Disk free space"], ["Create server_health_tool folder", "Create health_check.ps1", "Use Get-CimInstance for OS/computer info", "Use Get-PSDrive for disk", "Print readable output", "Run script in PowerShell", "Save screenshot"], ["Script runs without error", "Shows at least 4 health values", "Screenshot proves output"], ["Upload ZIP", "Include health_check.ps1", "Include screenshot or copied output"]),
            _quest("Export Health Snapshot to JSON", "PowerShell JSON", "Beginner", "30-45 minutes", "JSON output lets KDT OS or a dashboard read the result later.", "Modify the health script so it saves results to health_report.json.", ["Create object", "ConvertTo-Json", "Save health_report.json", "README command"], ["Create a PowerShell object", "Pipe to ConvertTo-Json", "Save with Out-File", "Run script", "Open JSON file"], ["health_report.json exists", "JSON contains CPU/RAM/disk fields", "README has run command"], ["Upload ZIP", "Include .ps1 and .json"]),
        ]
        plan["proof_strategy"] = ["Proof should include the script and output", "Later dashboard work should only start after JSON output works"]
        return plan

    # Workout / fitness app
    if any(k in text for k in ["workout", "fitness", "ab coach", "calorie", "nutrition", "meal", "weight loss", "exercise"]):
        plan = base(selected_name or "Workout Tracker", "Build a self-tracking tool for workouts and progress.", "Improve My Health And Fitness", "Use software to make fitness progress visible and repeatable.")
        plan["tool_decision"] = {"best_tool_type":"Browser/PWA first, mobile later", "best_stack_now":["HTML/CSS/JavaScript", "localStorage", "SQLite later"], "best_stack_later":["React", "PWA", "React Native", "SQLite/PostgreSQL"], "why_this_stack":"A browser app is the fastest MVP and can be used on phone before building a native app.", "bridge_needed": True}
        plan["bottleneck"] = {"current_bottleneck":"Saving progress", "why_it_blocks_progress":"A tracker is not useful if workouts disappear after refresh.", "next_smallest_action":"Save one workout entry to localStorage or SQLite."}
        plan["required_skills"] = [
            {"skill":"JavaScript Events", "status":"Known/Needs Proof", "why_needed":"The app needs buttons and forms.", "next_action":"Build an Add Workout form."},
            {"skill":"Local Storage or SQLite", "status":"Missing/Needs Proof", "why_needed":"Workout progress must persist.", "next_action":"Save and reload one workout."},
        ]
        plan["quest_plan"] = [
            _quest("Build a Saved Workout Form", "JavaScript Local Storage", "Beginner", "60-90 minutes", "This solves the core tracker blocker: saving progress.", "A browser page where you enter exercise, sets, reps, and save it so it remains after refresh.", ["index.html", "script.js", "Exercise input", "Sets input", "Reps input", "Save button", "localStorage", "Workout list"], ["Create folder", "Create files", "Build form", "On submit create workout object", "Save array to localStorage", "Load workouts on page load", "Display workouts"], ["Workout saves", "Workout remains after refresh", "List displays saved entries"], ["Upload ZIP", "Include screenshot", "Explain where data is saved"])
        ]
        plan["proof_strategy"] = ["Proof must show data persists after refresh", "Upload ZIP and screenshot of saved workout list"]
        return plan

    # Generic robust fallback based on request type
    plan = base(selected_name or "Adaptive Tool Project", "Create or improve a tool based on the user request using the best stack KDT OS can justify.")
    best_type = "browser app" if req_type in {"new_or_extend_project", "add_feature", "improve_design", "learn_skill"} else "cli tool"
    decision = PROJECT_TYPE_DECISIONS.get(best_type, PROJECT_TYPE_DECISIONS["browser app"])
    plan["tool_decision"] = {"best_tool_type": best_type, "best_stack_now": decision["stacks"][:2], "best_stack_later": decision["stacks"][1:], "why_this_stack": decision["why"], "bridge_needed": True}
    plan["bottleneck"] = {"current_bottleneck":"Unclear smallest working version", "why_it_blocks_progress":"The request must be narrowed into one testable tool feature before coding.", "next_smallest_action":"Write a one-page README defining the smallest version, required features, and proof."}
    plan["required_skills"] = [
        {"skill":"Planning", "status":"Known/Needs Proof", "why_needed":"The system needs a clear build target.", "next_action":"Define smallest working version."},
        {"skill":"Implementation", "status":"Unknown", "why_needed":"The chosen stack must be applied to the project.", "next_action":"Build the first visible feature."},
    ]
    plan["quest_plan"] = [
        _quest("Define the Smallest Working Version", "Planning", "Beginner", "20-30 minutes", "This prevents vague work and makes the first build testable.", "A README.md that defines the exact smallest version of the requested tool or feature.", ["Project name", "Purpose", "3 required features", "What is not included yet", "Proof needed"], ["Create project folder", "Create README.md", "Write purpose", "List 3 features", "List excluded features", "List proof needed"], ["README exists", "Scope is clear", "Proof is listed"], ["Upload ZIP containing README.md"])
    ]
    plan["proof_strategy"] = ["Every quest must produce proof", "If proof is unclear, create a smaller quest first"]
    return plan


def path_quality_score(plan: Dict[str, Any]) -> int:
    score = 0
    if not _blank(plan.get("tool_decision")): score += 20
    if not _blank(plan.get("bottleneck")): score += 20
    if len(plan.get("required_skills", []) or []) >= 2: score += 20
    if len(plan.get("quest_plan", []) or []) >= 1: score += 20
    qp = plan.get("quest_plan", []) or []
    if qp and all(not _blank(q.get("steps")) and not _blank(q.get("proof_required")) for q in qp): score += 20
    return min(score, 100)


def merge_plan(ai_plan: Dict[str, Any] | None, heuristic_plan: Dict[str, Any], problem: str, context_goal: str, project_context: Dict[str, Any]) -> Dict[str, Any]:
    """Use AI when it is good; repair it with the universal decision engine when it is vague."""
    plan = ai_plan if isinstance(ai_plan, dict) else {}
    # If AI output is mostly empty, trust deterministic universal engine.
    if path_quality_score(plan) < 60:
        plan = heuristic_plan
    else:
        # Fill missing sections from heuristic without overwriting useful AI content.
        for key in ["goal", "project", "request_type", "problem_summary", "tool_decision", "bottleneck", "redundancy_review", "proof_strategy", "return_rule"]:
            if _blank(plan.get(key)):
                plan[key] = heuristic_plan.get(key)
        if len(plan.get("required_skills", []) or []) < 2:
            plan["required_skills"] = heuristic_plan.get("required_skills", [])
        if len(plan.get("quest_plan", []) or []) < 1:
            plan["quest_plan"] = heuristic_plan.get("quest_plan", [])
    # Normalize lists and guarantee exact quest fields.
    for q in plan.get("quest_plan", []) or []:
        q["requirements"] = _as_list(q.get("requirements")) or ["Create the required project files", "Implement the requested feature", "Document what you changed"]
        q["steps"] = _as_list(q.get("steps")) or ["Create the project folder", "Create the required file", "Build the smallest working version", "Run it", "Write proof notes"]
        q["success_criteria"] = _as_list(q.get("success_criteria")) or ["The feature works", "Proof is included", "You can explain what you built"]
        q["proof_required"] = _as_list(q.get("proof_required")) or ["Upload project ZIP", "Include README.md", "Explain what worked"]
        q.setdefault("difficulty", "Beginner")
        q.setdefault("estimated_time", "30-90 minutes")
    plan["decision_engine_score"] = path_quality_score(plan)
    plan["decision_engine_note"] = "KDT OS repaired or filled this path using the Universal Decision Engine when AI output was vague."
    plan["decision_audit"] = {
        "classified_request_type": plan.get("request_type"),
        "selected_project": (project_context or {}).get("name", ""),
        "why_this_is_not_generic": "KDT OS chose tool type, stack, bottleneck, skills, quests, proof, and return rule before saving the path.",
        "quality_gate": "Path should include a tool decision, bottleneck, at least two skills, at least one exact quest, and proof.",
        "score": plan.get("decision_engine_score")
    }
    return plan

def ai_universal_path(problem: str, context_goal: str = "", project_context: Dict[str, Any] | None = None, request_type: str = "auto") -> Dict[str, Any]:
    project_context = project_context or build_project_context("unknown")
    detected_request_type = request_type if request_type and request_type != "auto" else classify_request_type(problem)
    redundancy = redundancy_scan_for_request(problem, project_context.get("name", ""))
    memory = load_decision_memory()
    heuristic = infer_domain_profile(problem, context_goal, project_context, detected_request_type)
    prompt = f"""
You are KDT OS Universal Decision Engine for Kewonte.
Your job is NOT to give vague advice. Your job is to convert any request into a buildable software/tool path.

Kewonte's operating principle:
Life Goal -> Project -> Required Skills -> Current Bottleneck -> Exact Quests -> Proof -> Return Rule.

User problem / idea:
{problem}

Detected request type:
{detected_request_type}

Project selection/trust context from user:
{json.dumps(project_context, indent=2)}

Deterministic decision engine draft you may improve, but do not make worse:
{json.dumps(heuristic, indent=2)}

Decision memory / user rules:
{json.dumps(memory, indent=2)}

Universal language knowledge base:
{language_kb_snapshot()}

Project type / stack decision guide:
{project_type_snapshot()}

Older project / redundancy scan:
{json.dumps(redundancy, indent=2)}

Optional selected goal/context:
{context_goal}

Saved goals:
{goal_snapshot()}

Tracked projects:
{existing_project_snapshot()}

Known skill evidence:
{known_skill_snapshot()}

Return JSON only with this exact structure:
{{
  "goal": {{"name": "", "why": ""}},
  "project": {{"name": "", "purpose": "", "is_new_project_needed": true, "reuse_existing_project": "", "reason": ""}},
  "request_type": "new_project|add_feature|fix_bug|improve_design|optimize|learn_skill|switch_platform|unknown",
  "tool_decision": {{"best_tool_type": "", "best_stack_now": [""], "best_stack_later": [""], "why_this_stack": "", "bridge_needed": true}},
  "bottleneck": {{"current_bottleneck": "", "why_it_blocks_progress": "", "next_smallest_action": ""}},
  "redundancy_review": {{"should_reuse_existing": false, "reuse_project": "", "keep_separate_reason": "", "redundant_items_to_remove": [""]}},
  "problem_summary": "",
  "required_skills": [
    {{"skill": "", "status": "Known|Missing|Rusty|Needs Proof|Unknown|Advanced Bridge", "why_needed": "", "next_action": ""}}
  ],
  "quest_plan": [
    {{
      "title": "",
      "skill": "",
      "difficulty": "Beginner|Intermediate|Advanced",
      "estimated_time": "",
      "why": "",
      "what_to_build": "",
      "requirements": [""],
      "steps": [""],
      "success_criteria": [""],
      "proof_required": [""]
    }}
  ],
  "proof_strategy": [""],
  "return_rule": ""
}}
Rules:
- Universal first: work for future unknown topics, not only examples.
- For singing/guitar/fitness/language/music requests, create a software/tool project to support practice unless the user explicitly asks for direct coaching.
- For serious games, choose a real game engine path but create bridge quests from simpler skills.
- For IT/server/Windows requests, prefer PowerShell/Python and proof-based automation.
- For web/mobile/product requests, choose browser/PWA first if fastest, mobile/native later when needed.
- If the best long-term language is above Kewonte's current skill level, create bridge quests that lead there.
- If existing project selected, do not start over; create feature/fix/improvement path for that project.
- Never claim a project is verified unless project context says it is verified.
- Avoid empty fields. Avoid generic quests. Include exact files, features, steps, success criteria, and proof.
- 2 to 4 quests is enough.
"""
    result = ollama_generate(prompt, system="You are KDT OS Universal Decision Engine. Return strict JSON only.", temperature=0.15, max_chars=10000, feature="Universal Decision Engine")
    raw = result.get("text", "")
    parsed = parse_path_json(raw) if result.get("ok") else None
    plan = merge_plan(parsed, heuristic, problem, context_goal, project_context)
    plan = apply_trust_metadata_to_path(plan, project_context)
    plan["ai_generated"] = bool(parsed)
    plan["ai_raw_response"] = raw[:8000]
    plan["ai_parse_ok"] = bool(parsed)
    plan["request_type"] = plan.get("request_type") or detected_request_type
    save_ai_log({
        "feature": "Universal Decision Engine",
        "prompt": prompt[:3000],
        "response": raw[:5000],
        "error": "Path JSON parsed and merged." if parsed else "AI path unavailable or vague; Universal Decision Engine filled the path.",
        "parse_ok": bool(parsed),
        "fallback_used": not bool(parsed)
    })
    return plan


def make_quest_from_path_item(plan: Dict[str, Any], item_index: int) -> tuple[str, Dict[str, Any]]:
    quests = plan.get("quest_plan", [])
    if item_index < 0 or item_index >= len(quests):
        raise IndexError("Quest index out of range")
    item = quests[item_index]
    goal_name = plan.get("goal", {}).get("name", "")
    project_name = plan.get("project", {}).get("name", "Path Project")
    skill = normalize_skill(item.get("skill") or "Planning")
    qfile, quest = make_quest(
        skill=skill,
        source=f"Path Builder: {project_name}",
        user_gap=item.get("why") or plan.get("problem_summary", ""),
        goal=goal_name,
        quest_type="Path Quest",
        origin_report="",
        resume_project=project_name,
    )
    quest["title"] = item.get("title") or quest.get("title")
    quest["goal"] = item.get("why") or quest.get("goal")
    quest["what_to_build"] = item.get("what_to_build") or quest.get("what_to_build")
    quest["requirements"] = item.get("requirements") or quest.get("requirements", [])
    quest["steps"] = item.get("steps") or quest.get("steps", [])
    quest["success_criteria"] = item.get("success_criteria") or quest.get("success_criteria", [])
    quest["proof_required"] = item.get("proof_required") or quest.get("proof_required", [])
    quest["difficulty"] = item.get("difficulty", "Beginner")
    quest["estimated_time"] = item.get("estimated_time", "15-45 minutes")
    quest["path_source"] = plan.get("filename", "")
    reason = item.get("why") or plan.get("problem_summary", "")
    quest["why_this_exists"] = f"This quest came from a KDT OS path. Goal: {goal_name}. Project: {project_name}. Reason: {reason}. After this quest, return to the project path and continue the next step."
    apply_quest_quality(quest)
    (QUEST_DIR / qfile).write_text(json.dumps(quest, indent=2), encoding="utf-8")
    return qfile, quest

@app.route("/")
def index():
    ai_status = ensure_ollama_ready(wait_seconds=0.8)
    return render_template("index.html", reports=list_reports(), goals=list_goals(), quests=list_quests()[:6], skills=load_skill_library(), skill_graph=skill_graph_summary(), projects=list_projects(), paths=list_paths(4), ai_status=ai_status, trust=trust_summary())

@app.route("/analyze", methods=["POST"])
def analyze():
    project_name = request.form.get("project_name", "").strip()
    uploaded = request.files.get("project_zip")
    if not uploaded or not uploaded.filename.lower().endswith(".zip"):
        flash("Upload a .zip project file."); return redirect(url_for("index"))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"{timestamp}_{uploaded.filename}"
    zip_path = UPLOAD_DIR / zip_name
    uploaded.save(zip_path)
    extract_root = WORK_DIR / zip_name.replace(".zip", "")
    if extract_root.exists(): shutil.rmtree(extract_root)
    extract_root.mkdir(parents=True)
    try:
        safe_extract_zip(zip_path, extract_root)
        children = [p for p in extract_root.iterdir()]
        project_root = children[0] if len(children) == 1 and children[0].is_dir() else extract_root
        report = analyze_project(project_root, project_name or Path(uploaded.filename).stem)
        report_filename = f"{timestamp}_{report['project_name'].replace(' ', '_')}.json"
        report["report_filename"] = report_filename
        project_update = update_project_record(report, report_filename)
        if project_update.get("duplicate_upload"):
            # Do not create a duplicate report, version, quest, or skill evidence.
            try:
                zip_path.unlink(missing_ok=True)
                shutil.rmtree(extract_root, ignore_errors=True)
            except Exception:
                pass
            flash(f"Duplicate upload detected for {report['project_name']}. No new version, report, quests, or skill evidence were created.")
            previous = project_update.get("previous_report")
            if previous:
                return redirect(url_for("view_report", filename=previous))
            return redirect(url_for("projects"))
        auto_generate_quests_for_report(report, report_filename)
        save_report(report_filename, report)
        update_skill_library_from_report(report)
        return redirect(url_for("view_report", filename=report_filename))
    except Exception as exc:
        flash(f"Analysis failed: {exc}"); return redirect(url_for("index"))

@app.route("/reports/<filename>")
def view_report(filename: str):
    try: data = load_report(filename)
    except FileNotFoundError:
        flash("Report not found."); return redirect(url_for("index"))
    return render_template("report.html", report=data, filename=filename)

@app.route("/decision/<filename>", methods=["POST"])
def save_decision(filename: str):
    try: report = load_report(filename)
    except FileNotFoundError:
        flash("Report not found."); return redirect(url_for("index"))
    entry = {"made_at": datetime.now().isoformat(timespec="seconds"), "decision_id": request.form.get("decision_id", ""), "decision_label": request.form.get("decision_label", ""), "reason": request.form.get("reason", "").strip() or "No reason entered yet."}
    report.setdefault("decisions", []).append(entry)
    save_report(filename, report)
    (DECISION_DIR / f"{filename.replace('.json','')}_decisions.json").write_text(json.dumps(report.get("decisions", []), indent=2), encoding="utf-8")
    flash(f"Decision saved: {entry['decision_label']}")
    return redirect(url_for("view_report", filename=filename))

@app.route("/quest/<filename>", methods=["POST"])
def create_quest(filename: str):
    try: report = load_report(filename)
    except FileNotFoundError:
        flash("Report not found."); return redirect(url_for("index"))
    skill = request.form.get("skill", "").strip()
    gap = request.form.get("user_gap", "").strip()
    quest_type = request.form.get("quest_type", "Practice Quest").strip()
    qfile, quest = make_quest(skill, report.get("project_name", "Project"), gap, "", quest_type)
    flash(f"Learning quest created: {quest['title']}")
    return redirect(url_for("view_quest", filename=qfile))

@app.route("/quests")
def quests():
    deleted = cleanup_duplicate_auto_quests()
    message = ""
    if deleted:
        message = f"KDT OS removed {deleted} duplicate auto-generated quest(s). Future repeated uploads will not recreate them."
    return render_template("quests.html", quests=list_quests(), cleanup_message=message)

@app.route("/quests/<filename>")
def view_quest(filename: str):
    path = QUEST_DIR / filename
    if not path.exists(): flash("Quest not found."); return redirect(url_for("index"))
    quest = apply_quest_quality(json.loads(path.read_text(encoding="utf-8")))
    child_quests = [apply_quest_quality(c) for c in child_quests_for_parent(filename)]
    parent_quest = load_parent_quest(quest.get("parent_quest", ""))
    return render_template("quest.html", quest=quest, filename=filename, child_quests=child_quests, parent_quest=parent_quest)

@app.route("/quests/<filename>/submit", methods=["POST"])
def submit_quest(filename: str):
    qpath = QUEST_DIR / filename
    if not qpath.exists(): flash("Quest not found."); return redirect(url_for("index"))
    quest = json.loads(qpath.read_text(encoding="utf-8"))
    uploaded = request.files.get("submission_zip")
    if not uploaded or not uploaded.filename.lower().endswith(".zip"):
        flash("Upload your quest work as a .zip file."); return redirect(url_for("view_quest", filename=filename))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_name = f"{stamp}_{uploaded.filename}"
    zip_path = SUBMISSION_DIR / save_name
    uploaded.save(zip_path)
    extract_root = SUBMISSION_DIR / save_name.replace(".zip", "")
    if extract_root.exists(): shutil.rmtree(extract_root)
    extract_root.mkdir(parents=True)
    safe_extract_zip(zip_path, extract_root)
    files = iter_project_files(extract_root)
    text_blob = "\n".join([str(p.relative_to(extract_root)).replace("\\", "/") + "\n" + read_text_file(p, 50000) for p in files if p.suffix.lower() in SUPPORTED_TEXT_EXTENSIONS])
    patterns = quest.get("verification_patterns", [])
    found = []
    missing = []
    for pat in patterns:
        try:
            (found if re.search(pat, text_blob, flags=re.IGNORECASE) else missing).append(pat)
        except re.error:
            missing.append(pat)
    percent = 100 if not patterns else int((len(found) / len(patterns)) * 100)
    status = "Completed" if percent >= 80 else "Needs Revision"
    reflection = request.form.get("reflection", "").strip()
    submission = {"submitted_at": datetime.now().isoformat(timespec="seconds"), "zip": save_name, "score": percent, "status": status, "found_patterns": found, "missing_patterns": missing, "file_count": len(files), "reflection": reflection}
    ai_eval = ai_evaluate_submission(quest, submission, text_blob, reflection)
    submission["ai_evaluation"] = ai_eval
    if ai_eval.get("available"):
        verdict = ai_eval.get("verdict", status)
        # AI can request explanation/revision even when rule patterns pass.
        if verdict in {"Needs Revision", "Needs Explanation", "Completed"}:
            status = verdict
            submission["status"] = status
    quest.setdefault("submissions", []).append(submission)
    quest["status"] = status
    update_skill_after_submission(quest.get("skill", "Unknown Skill"), percent, quest.get("source_project", "Quest Submission"), ai_eval, quest.get("title", ""))
    qpath.write_text(json.dumps(quest, indent=2), encoding="utf-8")
    record_adaptive_event("quest_submission", f"Quest proof submitted for {quest.get('title','quest')}: {status}", {"skill": quest.get("skill"), "score": percent, "status": status})
    flash(f"Quest submission checked: {percent}% — {status}. Skill library updated.")
    return redirect(url_for("view_quest", filename=filename))

@app.route("/goals", methods=["GET", "POST"])
def goals():
    if request.method == "POST":
        name = request.form.get("goal_name", "").strip()
        why = request.form.get("why", "").strip()
        build = request.form.get("build_want", "").strip()
        if not name:
            flash("Goal name is required."); return redirect(url_for("goals"))
        goal = {"created_at": datetime.now().isoformat(timespec="seconds"), "goal_name": name, "why": why, "what_i_want_to_build": build, "status": "Active"}
        filename = re.sub(r"[^a-zA-Z0-9_-]+", "_", f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}") + ".json"
        (GOAL_DIR / filename).write_text(json.dumps(goal, indent=2), encoding="utf-8")
        flash("Goal saved. KDT OS can now generate quests from it.")
        return redirect(url_for("view_goal", filename=filename))
    return render_template("goals.html", goals=list_goals())

@app.route("/goals/<filename>")
def view_goal(filename: str):
    path = GOAL_DIR / filename
    if not path.exists(): flash("Goal not found."); return redirect(url_for("goals"))
    goal = json.loads(path.read_text(encoding="utf-8"))
    skills = load_skill_library()
    goal_gap = analyze_goal_gap(goal)
    return render_template("goal.html", goal=goal, filename=filename, skills=skills, goal_gap=goal_gap)

@app.route("/goals/<filename>/generate", methods=["POST"])
def generate_goal_quest(filename: str):
    path = GOAL_DIR / filename
    if not path.exists(): flash("Goal not found."); return redirect(url_for("goals"))
    goal = json.loads(path.read_text(encoding="utf-8"))
    requested_skill = request.form.get("skill", "").strip() or "JavaScript"
    gap = request.form.get("gap", "").strip() or f"I need exact practice so I can continue goal: {goal.get('goal_name')}"
    qfile, quest = make_quest(requested_skill, f"Goal: {goal.get('goal_name')}", gap, goal.get("goal_name", ""), "Goal Quest")
    flash("Goal quest generated.")
    return redirect(url_for("view_quest", filename=qfile))

@app.route("/teach", methods=["GET", "POST"])
def teach():
    answer = None
    ai_status = ensure_ollama_ready(wait_seconds=0.8)
    if request.method == "POST":
        skill = request.form.get("skill", "").strip() or "Unknown Skill"
        confusion = request.form.get("confusion", "").strip() or "I don't know where to start."
        skill = normalize_skill(skill)
        known = load_skill_library().get(skill)
        ai_help = ai_teach_response(skill, confusion, known)
        answer = {
            "skill": skill,
            "confusion": confusion,
            "known": known,
            "explanation": ai_help.get("plain_explanation") or explain(skill, f"KDT OS does not have much evidence for {skill} yet. It can still create a beginner quest and mark this as a new skill."),
            "why_it_matters": ai_help.get("why_it_matters"),
            "next_smallest_action": ai_help.get("next_smallest_action"),
            "practice_idea": ai_help.get("practice_idea"),
            "questions_to_check_understanding": ai_help.get("questions_to_check_understanding", []),
            "ai_help": ai_help,
            "breakdown": exact_breakdown_for(skill),
            "actions": ["Explain the concept", "Create exact practice quest", "Break this down further", "Show related uploaded projects"]
        }
    return render_template("teach.html", answer=answer, skills=load_skill_library(), ai_status=ai_status)

@app.route("/teach/create", methods=["POST"])
def teach_create():
    skill = request.form.get("skill", "").strip() or "JavaScript"
    confusion = request.form.get("confusion", "").strip() or "I need exact practice and do not know where to start."
    qfile, quest = make_quest(skill, "Teach Me Mode", confusion, "", "Teach Me Quest")

    ai_quest = ai_practice_quest_from_teach(skill, confusion)
    if ai_quest:
        quest["title"] = ai_quest.get("title", quest["title"])
        quest["goal"] = ai_quest.get("goal", quest.get("goal", ""))
        quest["what_to_build"] = ai_quest.get("what_to_build", quest.get("what_to_build", ""))
        quest["requirements"] = ai_quest.get("requirements", quest.get("requirements", []))
        quest["success_criteria"] = ai_quest.get("success_criteria", quest.get("success_criteria", []))
        quest["steps"] = ai_quest.get("steps", quest.get("steps", []))
        quest["proof_required"] = ai_quest.get("proof", quest.get("proof_required", []))
        quest["verification_patterns"] = ai_quest.get("verification_patterns", quest.get("verification_patterns", []))
        quest["difficulty"] = ai_quest.get("difficulty", "Beginner")
        quest["estimated_time"] = ai_quest.get("estimated_time", "15-45 minutes")
        quest["ai_generated"] = True
        quest["ai_parse_mode"] = ai_quest.get("ai_parse_mode", "teach_me_sectioned_plain_text")
        quest["ai_raw_response"] = ai_quest.get("ai_raw_response", "")
        quest["why_this_exists"] = f"You asked Teach Me Mode for help with {normalize_skill(skill)}. Your blocker was: {confusion}. Ollama generated this exact quest so you can practice the next achievable step."
        apply_quest_quality(quest)
        (QUEST_DIR / qfile).write_text(json.dumps(quest, indent=2), encoding="utf-8")
        flash("AI Teach Me quest created with exact instructions.")
    else:
        flash("Teach Me quest created with template instructions because AI generation was unavailable.")
    return redirect(url_for("view_quest", filename=qfile))


@app.route("/quests/<filename>/breakdown", methods=["POST"])
def breakdown_quest(filename: str):
    qpath = QUEST_DIR / filename
    if not qpath.exists():
        flash("Quest not found."); return redirect(url_for("quests"))
    quest = json.loads(qpath.read_text(encoding="utf-8"))
    obstacle = request.form.get("obstacle", "I do not understand this yet.").strip()
    skill = quest.get("skill", "Unknown Skill")
    # Try AI-powered breakdown first. If Ollama is unavailable, fall back to deterministic templates.
    ai_micro = ai_breakdown_template(quest, obstacle)
    if ai_micro:
        micro = ai_micro
    else:
        micro = micro_breakdown_for(skill, obstacle, quest)
    qfile, newq = make_quest(skill, f"Breakdown of: {quest.get('title')}", obstacle, quest.get("connected_goal", ""), "Quest Breakdown", quest.get("origin_report", ""), quest.get("resume_project", ""))
    # overwrite generated generic content with micro template but preserve relationship fields
    for key in ["title", "quest_type", "goal", "what_to_build", "requirements", "success_criteria", "steps", "proof_required", "verification_patterns", "difficulty", "estimated_time"]:
        src_key = "type" if key == "quest_type" else "proof" if key == "proof_required" else key
        if src_key in micro:
            newq[key] = micro[src_key]
    newq["parent_quest"] = filename
    newq["quest_type"] = "Quest Breakdown"
    newq["ai_generated"] = bool(micro.get("ai_generated"))
    newq["ai_parse_mode"] = micro.get("ai_parse_mode", "template")
    newq["ai_raw_response"] = micro.get("ai_raw_response", "")
    title_text = str(newq.get("title", skill)).replace("Micro Quest:", "").strip()
    if not title_text.lower().startswith("quest breakdown"):
        newq["title"] = f"Quest Breakdown: {title_text}"
    else:
        newq["title"] = title_text
    newq["why_this_exists"] = f"You clicked I Don't Know How on {quest.get('title')}. Obstacle: {obstacle}. This breakdown is a smaller step that directly supports the parent quest. Complete it, then return to the parent quest."
    quest["status"] = "Blocked - Breakdown Created"
    quest.setdefault("breakdown_history", []).append({"created_at": datetime.now().isoformat(timespec="seconds"), "breakdown_file": qfile, "obstacle": obstacle})
    apply_quest_quality(newq)
    qpath.write_text(json.dumps(quest, indent=2), encoding="utf-8")
    (QUEST_DIR / qfile).write_text(json.dumps(newq, indent=2), encoding="utf-8")
    flash("Quest breakdown created and attached to the original quest.")
    return redirect(url_for("view_quest", filename=qfile))




# -----------------------------
# Bottlenecks, bridge chains, upgrade workflow (v12)
# -----------------------------
def load_upgrade_plan(filename: str) -> Dict[str, Any]:
    path = UPGRADE_DIR / filename
    if not path.exists():
        raise FileNotFoundError(filename)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["filename"] = filename
    return data

def save_upgrade_plan(filename: str, data: Dict[str, Any]) -> None:
    (UPGRADE_DIR / filename).write_text(json.dumps(data, indent=2), encoding="utf-8")

def bottleneck_file(project_name: str) -> Path:
    return BOTTLENECK_DIR / f"{slugify(project_name)}.json"

def load_bottlenecks(project_name: str) -> List[Dict[str, Any]]:
    f = bottleneck_file(project_name)
    if f.exists():
        try: return json.loads(f.read_text(encoding="utf-8"))
        except Exception: return []
    return []

def save_bottlenecks(project_name: str, items: List[Dict[str, Any]]) -> None:
    bottleneck_file(project_name).write_text(json.dumps(items, indent=2), encoding="utf-8")

def exact_quest_standard_dict() -> Dict[str, Any]:
    return {
        "minimum_fields": ["goal", "why_this_exists", "connected_goal", "resume_project", "skill", "difficulty", "estimated_time", "what_to_build", "requirements", "steps", "success_criteria", "proof_required", "verification_method", "return_point"],
        "rule": "Every quest must give exact instructions up front because Kewonte follows exact instructions and may not know the first step yet.",
    }

def make_bridge_quest(skill: str, project_name: str, goal_name: str, reason: str) -> tuple[str, Dict[str, Any]]:
    qfile, q = make_quest(skill=skill, source=f"Bridge Path: {project_name}", user_gap=reason, goal=goal_name, quest_type="Bridge Quest", resume_project=project_name)
    q["title"] = f"Bridge Quest: {skill} First Step"
    q["why_this_exists"] = f"This bridge quest exists because the best long-term stack for {project_name} requires {skill}, but your skill bank does not prove you are ready yet. Reason: {reason}"
    q["difficulty"] = q.get("difficulty") or "Beginner"
    q["estimated_time"] = q.get("estimated_time") or "30-60 minutes"
    q["quest_standard"] = exact_quest_standard_dict()
    (QUEST_DIR / qfile).write_text(json.dumps(q, indent=2), encoding="utf-8")
    return qfile, q

def issue_mode_prompt(project_name: str, issue_text: str) -> Dict[str, Any]:
    prompt = f"""
You are KDT OS Project Issue Mentor. Classify this project issue and create an exact improvement path.
Project: {project_name}
Issue/request: {issue_text}
Return JSON only:
{{
  "issue_type": "bug|feature|design|performance|architecture|learning_gap|unknown",
  "current_bottleneck": "",
  "why_it_matters": "",
  "likely_files": [""],
  "first_quest": {{"title":"", "skill":"", "what_to_build":"", "requirements":[""], "steps":[""], "success_criteria":[""], "proof_required":[""]}}
}}
"""
    result = ollama_generate(prompt, system="Return strict JSON only. Be exact and practical.", feature="Project Issue Mentor")
    parsed = extract_json_object(result.get("text", "")) if result.get("ok") else None
    if not parsed:
        parsed = {"issue_type":"unknown", "current_bottleneck": issue_text, "why_it_matters":"KDT OS could not classify this perfectly, but it can still turn it into an exact improvement quest.", "likely_files":["app.py", "templates", "static/style.css"], "first_quest":{"title":"Diagnose Project Issue", "skill":"Project Tracking", "what_to_build":"A short issue note that explains what feels wrong and what evidence shows it.", "requirements":["Write the problem", "List expected behavior", "List actual behavior"], "steps":["Open the project", "Reproduce the issue", "Write what happened", "Upload updated project or screenshot"], "success_criteria":["Problem is clearly defined"], "proof_required":["Text explanation or screenshot"]}}
    return parsed


@app.route("/path", methods=["GET", "POST"])
def path_builder():
    plan = None
    if request.method == "POST":
        problem = request.form.get("problem", "").strip()
        context_goal = request.form.get("context_goal", "").strip()
        project_mode = request.form.get("project_mode", "unknown").strip()
        selected_project = request.form.get("selected_project", "").strip()
        new_project_name = request.form.get("new_project_name", "").strip()
        project_context = build_project_context(project_mode, selected_project, new_project_name)
        if not problem:
            flash("Tell KDT OS what problem, goal, or project idea you want to turn into a path.")
            return redirect(url_for("path_builder"))
        request_type = request.form.get("request_type", "auto").strip()
        plan = ai_universal_path(problem, context_goal, project_context, request_type)
        plan["created_at"] = datetime.now().isoformat(timespec="seconds")
        plan["request_type"] = plan.get("request_type") or (request.form.get("request_type", "auto") or classify_request_type(problem))
        plan["project_selection"] = project_context
        plan["original_input"] = problem
        record_adaptive_event("path_created", f"Created path for: {problem[:120]}", {"request_type": plan.get("request_type"), "project": plan.get("project", {}).get("name"), "goal": plan.get("goal", {}).get("name"), "score": plan.get("decision_engine_score")})
        filename = save_path(plan)
        plan["filename"] = filename
        save_path(plan, filename)
        flash("KDT OS created a Goal → Project → Skills → Quests path.")
        return redirect(url_for("view_path", filename=filename))
    return render_template("path_builder.html", paths=list_paths(), goals=list_goals(), projects=list_projects(), skills=load_skill_library(), trust=trust_summary())


@app.route("/path/<filename>")
def view_path(filename: str):
    try:
        plan = load_path(filename)
    except FileNotFoundError:
        flash("Path not found.")
        return redirect(url_for("path_builder"))
    return render_template("path.html", plan=plan, filename=filename)


@app.route("/path/<filename>/quest/<int:item_index>", methods=["POST"])
def create_path_quest(filename: str, item_index: int):
    try:
        plan = load_path(filename)
    except FileNotFoundError:
        flash("Path not found.")
        return redirect(url_for("path_builder"))
    plan["filename"] = filename
    try:
        qfile, quest = make_quest_from_path_item(plan, item_index)
    except Exception as exc:
        flash(f"Could not create path quest: {exc}")
        return redirect(url_for("view_path", filename=filename))
    plan.setdefault("created_quests", []).append({"created_at": datetime.now().isoformat(timespec="seconds"), "quest_file": qfile, "item_index": item_index, "title": quest.get("title")})
    save_path(plan, filename)
    flash("Path quest created. Complete it, submit proof, then return to this path.")
    return redirect(url_for("view_quest", filename=qfile))



def parse_upgrade_json(raw: str) -> Dict[str, Any] | None:
    data = extract_json_object(raw)
    if not isinstance(data, dict):
        return None
    data.setdefault("upgrade_name", "KDT OS Upgrade")
    data.setdefault("why_needed", "")
    data.setdefault("affected_systems", [])
    data.setdefault("likely_files", [])
    data.setdefault("data_changes", [])
    data.setdefault("redundancy_check", {})
    data.setdefault("skill_gaps", [])
    data.setdefault("implementation_steps", [])
    data.setdefault("verification_plan", [])
    data.setdefault("first_exact_quest", {})
    return data

def ai_upgrade_proposal(desired: str) -> Dict[str, Any]:
    prompt = f"""
You are KDT OS Self-Upgrade Mentor.
Create a highly practical upgrade plan for KDT OS. Kewonte needs exact instructions, not vague advice.

Requested upgrade:
{desired}

Current KDT OS context:
Goals:\n{goal_snapshot()}
Projects:\n{existing_project_snapshot()}
Skills:\n{known_skill_snapshot()}
Decision memory:\n{json.dumps(load_decision_memory(), indent=2)}

Return JSON only:
{{
  "upgrade_name": "",
  "why_needed": "",
  "current_gap": "",
  "affected_systems": [""],
  "likely_files": ["app.py", "templates/...", "static/style.css"],
  "data_changes": ["new json/db files or fields"],
  "redundancy_check": {{"possible_overlap": "", "keep_or_remove": "", "reason": ""}},
  "skill_gaps": [{{"skill": "", "status": "known|missing|rusty", "bridge_quest": ""}}],
  "implementation_steps": ["exact step"],
  "verification_plan": ["exact test"],
  "first_exact_quest": {{"title":"", "what_to_build":"", "requirements":[""], "steps":[""], "success_criteria":[""], "proof_required":[""]}}
}}
Rules:
- Be an excellent planner, teacher, and verifier.
- Include impacted pages/routes/data.
- Include how to verify the upgrade works.
- If Kewonte may not know a skill, create a bridge quest.
- Do not claim KDT OS can magically code itself. It can propose, guide, verify, and eventually draft changes with approval.
"""
    result = ollama_generate(prompt, system="Return JSON only. You are a careful software upgrade architect.", temperature=0.2, max_chars=8000, feature="Self Upgrade Mentor")
    raw = result.get("text", "")
    parsed = parse_upgrade_json(raw) if result.get("ok") else None
    if parsed:
        parsed["requested"] = desired
        parsed["ai_generated"] = True
        parsed["ai_raw_response"] = raw[:6000]
        parsed["created_at"] = datetime.now().isoformat(timespec="seconds")
        return parsed
    return {
        "requested": desired,
        "upgrade_name": re.sub(r"[^A-Za-z0-9 ]", "", desired).title()[:60] or "KDT OS Upgrade",
        "why_needed": "This upgrade may improve KDT OS, but AI planning failed so KDT OS created a safe fallback.",
        "current_gap": f"KDT OS does not fully support this yet: {desired}",
        "affected_systems": ["app.py", "templates", "static/style.css", "data folders"],
        "likely_files": ["app.py", "templates/upgrade.html", "static/style.css"],
        "data_changes": ["Add or update JSON storage if the feature must remember anything."],
        "redundancy_check": {"possible_overlap": "Unknown", "keep_or_remove": "Keep until reviewed", "reason": "Do not remove useful systems without comparing purpose."},
        "skill_gaps": [{"skill": "Flask", "status": "known/maybe rusty", "bridge_quest": "Create one route and one template page."}],
        "implementation_steps": ["Define the exact user flow", "Add storage if data must be remembered", "Add route in app.py", "Add template section", "Add verification test"],
        "verification_plan": ["Start Flask", "Open the new page", "Use the feature once", "Confirm data persists", "Re-run after restart"],
        "first_exact_quest": {"title": "Create the smallest version", "what_to_build": "One page, one form, one saved JSON record.", "requirements": ["Route", "Template", "Save file"], "steps": ["Add route", "Add form", "Save JSON", "Test"], "success_criteria": ["Page opens", "Form submits", "JSON exists"], "proof_required": ["Upload updated KDT OS ZIP"]},
        "ai_generated": False,
        "ai_raw_response": raw[:6000],
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

@app.route("/upgrade", methods=["GET", "POST"])
def upgrade():
    proposal = None
    if request.method == "POST":
        desired = request.form.get("desired", "").strip() or "Help me better"
        proposal = ai_upgrade_proposal(desired)
        fname = f"{slugify(proposal.get('upgrade_name','upgrade'))}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        (UPGRADE_DIR / fname).write_text(json.dumps(proposal, indent=2), encoding="utf-8")
        proposal["filename"] = fname
    recent_upgrades = []
    for f in sorted(UPGRADE_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:8]:
        try:
            item = json.loads(f.read_text(encoding="utf-8")); item["filename"] = f.name; recent_upgrades.append(item)
        except Exception:
            pass
    return render_template("upgrade.html", proposal=proposal, recent_upgrades=recent_upgrades)



@app.route("/projects")
def projects():
    return render_template("projects.html", projects=list_projects())

@app.route("/projects/<filename>")
def view_project(filename: str):
    path = PROJECT_DIR / filename
    if not path.exists():
        flash("Project not found.")
        return redirect(url_for("projects"))
    project = json.loads(path.read_text(encoding="utf-8"))
    return render_template("project.html", project=project, filename=filename, bottlenecks=load_bottlenecks(project.get("project_name", filename.replace(".json", ""))))

@app.route("/skills/<path:skill_name>")
def view_skill(skill_name: str):
    skill_name = normalize_skill(skill_name)
    skills = load_skill_library()
    skill = skills.get(skill_name, {"skill": skill_name, "status": "Unknown", "evidence_count": 0, "projects": [], "evidence": [], "confidence_label": "KDT OS does not have evidence for this skill yet."})
    return render_template("skill.html", skill_name=skill_name, skill=skill, quests=quests_for_skill(skill_name))

@app.route("/goals/<filename>/recommended_quest", methods=["POST"])
def generate_recommended_goal_quest(filename: str):
    path = GOAL_DIR / filename
    if not path.exists():
        flash("Goal not found.")
        return redirect(url_for("goals"))
    goal = json.loads(path.read_text(encoding="utf-8"))
    skill = request.form.get("skill", "JavaScript")
    gap = request.form.get("gap", "") or f"I need exact practice with {skill} so I can move forward with: {goal.get('goal_name')}"
    qfile, quest = make_quest(skill, f"Goal Gap: {goal.get('goal_name')}", gap, goal.get("goal_name", ""), "Goal Gap Quest")
    flash("KDT OS created an exact quest from this goal gap.")
    return redirect(url_for("view_quest", filename=qfile))



@app.route("/skill_graph")
def skill_graph():
    return render_template("skill_graph.html", graph=skill_graph_summary())

@app.route("/quests/<filename>/quality")
def quest_quality(filename: str):
    path = QUEST_DIR / filename
    if not path.exists():
        flash("Quest not found."); return redirect(url_for("quests"))
    quest = apply_quest_quality(json.loads(path.read_text(encoding="utf-8")))
    return render_template("quest_quality.html", quest=quest, filename=filename)

@app.route("/ai", methods=["GET", "POST"])
def ai_settings():
    settings = load_ai_settings()
    if request.method == "POST":
        settings["enabled"] = request.form.get("enabled") == "on"
        settings["auto_start"] = request.form.get("auto_start") == "on"
        settings["model"] = request.form.get("model", settings.get("model", "llama3.1:8b")).strip() or "llama3.1:8b"
        settings["host"] = request.form.get("host", settings.get("host", "http://127.0.0.1:11434")).strip() or "http://127.0.0.1:11434"
        save_ai_settings(settings)
        flash("AI settings saved.")
        return redirect(url_for("ai_settings"))
    status = ensure_ollama_ready(wait_seconds=1.0)
    return render_template("ai.html", settings=settings, ai_status=status)


@app.route("/ai/diagnostics", methods=["GET", "POST"])
def ai_diagnostics():
    status = ensure_ollama_ready(wait_seconds=1.0)
    settings = load_ai_settings()
    test_result = None
    if request.method == "POST":
        prompt_text = request.form.get("prompt", "I don't understand Python functions.").strip() or "I don't understand Python functions."
        test_prompt = f"""
You are KDT OS. Kewonte needs exact beginner-friendly steps.
User blocker: {prompt_text}
Return a short exact breakdown with:
1. Goal
2. What to do
3. 3 exact steps
4. Proof needed
Plain text is okay for this diagnostic.
"""
        result = ollama_generate(test_prompt, system="You are KDT OS Teach Me Mode.", temperature=0.2, feature="AI Diagnostics Test")
        if result.get("ok"):
            sections = parse_plain_ai_breakdown(result.get("text", ""))
            result["parsed_sections"] = sections
            result["parse_ok"] = plain_sections_are_usable(sections)
            result["parse_note"] = "Plain-English response parsed into usable quest sections." if result["parse_ok"] else "Ollama replied, but KDT OS could not find enough quest sections yet."
            save_ai_log({
                "feature": "AI Diagnostics Test",
                "prompt": test_prompt[:2000],
                "response": result.get("text", "")[:4000],
                "error": result["parse_note"],
                "parse_ok": result["parse_ok"],
                "fallback_used": False,
            })
        test_result = result
    return render_template("ai_diagnostics.html", ai_status=status, settings=settings, log=load_ai_log(), test_result=test_result)


@app.route("/models", methods=["GET", "POST"])
def model_manager():
    if request.method == "POST":
        action = request.form.get("action", "")
        settings = load_ai_settings()
        if action == "save":
            settings["reasoning_model"] = request.form.get("reasoning_model", settings.get("reasoning_model", "llama3.1:8b")).strip()
            settings["code_model"] = request.form.get("code_model", settings.get("code_model", "deepseek-coder:latest")).strip()
            settings["vision_model"] = request.form.get("vision_model", settings.get("vision_model", "llava:latest")).strip()
            settings["embedding_model"] = request.form.get("embedding_model", settings.get("embedding_model", "nomic-embed-text")).strip()
            settings["fast_model"] = request.form.get("fast_model", settings.get("fast_model", "llama3.2:3b")).strip()
            settings["auto_pull_models"] = request.form.get("auto_pull_models") == "on"
            save_ai_settings(settings)
            flash("Model Manager settings saved.")
        elif action == "auto_detect":
            auto_detect_model_roles(save=True)
            flash("Model roles auto-detected from installed Ollama models.")
        elif action == "pull":
            model_name = request.form.get("model_name", "").strip()
            if model_name:
                result = pull_ollama_model(model_name)
                flash(("Model pulled: " if result.get("ok") else "Model pull failed: ") + model_name)
        return redirect(url_for("model_manager"))
    return render_template("models.html", snapshot=model_manager_snapshot(), catalog=MODEL_CATALOG)

@app.route("/vision", methods=["GET", "POST"])
def vision_test():
    result = None
    if request.method == "POST":
        uploaded = request.files.get("image")
        prompt = request.form.get("prompt", "Describe this screenshot and tell me whether it matches the requested proof.").strip()
        if uploaded and uploaded.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            fname = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded.filename}"
            path = VISION_DIR / fname
            uploaded.save(path)
            result = ollama_vision_describe(path, prompt)
            result["filename"] = fname
        else:
            flash("Upload a PNG/JPG/WEBP screenshot.")
    return render_template("vision.html", result=result, snapshot=model_manager_snapshot())

@app.route("/upgrade/<filename>")
def view_upgrade_plan(filename: str):
    try:
        plan = load_upgrade_plan(filename)
    except FileNotFoundError:
        flash("Upgrade plan not found.")
        return redirect(url_for("upgrade"))
    return render_template("upgrade_plan.html", plan=plan, filename=filename)

@app.route("/upgrade/<filename>/quest", methods=["POST"])
def create_upgrade_quest(filename: str):
    try:
        plan = load_upgrade_plan(filename)
    except FileNotFoundError:
        flash("Upgrade plan not found.")
        return redirect(url_for("upgrade"))
    first = plan.get("first_exact_quest", {}) or {}
    skill = (plan.get("skill_gaps") or [{}])[0].get("skill", "Flask") if isinstance(plan.get("skill_gaps"), list) else "Flask"
    qfile, q = make_quest(skill=skill, source=f"Upgrade Plan: {plan.get('upgrade_name','KDT OS Upgrade')}", user_gap=plan.get("current_gap", "Upgrade KDT OS"), goal="Improve KDT OS", quest_type="Upgrade Quest", resume_project="KDT OS")
    for k_src, k_dest in [("title","title"), ("what_to_build","what_to_build"), ("requirements","requirements"), ("steps","steps"), ("success_criteria","success_criteria"), ("proof_required","proof_required")]:
        if first.get(k_src): q[k_dest] = first[k_src]
    q["why_this_exists"] = plan.get("why_needed", q.get("why_this_exists"))
    q["quest_standard"] = exact_quest_standard_dict()
    (QUEST_DIR / qfile).write_text(json.dumps(q, indent=2), encoding="utf-8")
    plan.setdefault("created_quests", []).append({"quest_file": qfile, "title": q.get("title"), "created_at": datetime.now().isoformat(timespec="seconds")})
    save_upgrade_plan(filename, plan)
    flash("Upgrade quest created.")
    return redirect(url_for("view_quest", filename=qfile))

@app.route("/upgrade/<filename>/verify", methods=["POST"])
def verify_upgrade_plan(filename: str):
    try:
        plan = load_upgrade_plan(filename)
    except FileNotFoundError:
        flash("Upgrade plan not found.")
        return redirect(url_for("upgrade"))
    uploaded = request.files.get("upgrade_zip")
    if not uploaded or not uploaded.filename.lower().endswith(".zip"):
        flash("Upload the updated KDT OS project ZIP.")
        return redirect(url_for("view_upgrade_plan", filename=filename))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zpath = UPLOAD_DIR / f"upgrade_{stamp}_{uploaded.filename}"
    uploaded.save(zpath)
    extract_root = WORK_DIR / f"upgrade_verify_{stamp}"
    if extract_root.exists(): shutil.rmtree(extract_root)
    extract_root.mkdir(parents=True)
    safe_extract_zip(zpath, extract_root)
    files = iter_project_files(extract_root)
    file_names = [str(f.relative_to(extract_root)).replace("\\", "/") for f in files]
    likely = plan.get("likely_files", []) or []
    found_likely = [lf for lf in likely if any(str(lf).lower().replace("templates/","") in fn.lower() or str(lf).lower() in fn.lower() for fn in file_names)]
    verification = {"submitted_at": datetime.now().isoformat(timespec="seconds"), "file_count": len(files), "likely_files_found": found_likely, "likely_files_expected": likely, "status": "Verified Enough" if found_likely or len(files)>5 else "Needs Review"}
    plan.setdefault("verification_submissions", []).append(verification)
    save_upgrade_plan(filename, plan)
    flash(f"Upgrade proof checked: {verification['status']}")
    return redirect(url_for("view_upgrade_plan", filename=filename))

@app.route("/path/<filename>/bridge", methods=["POST"])
def create_bridge_chain(filename: str):
    try:
        plan = load_path(filename)
    except FileNotFoundError:
        flash("Path not found.")
        return redirect(url_for("path_builder"))
    project_name = plan.get("project", {}).get("name", "Path Project")
    goal_name = plan.get("goal", {}).get("name", "")
    created = []
    for skill_item in plan.get("required_skills", [])[:6]:
        status = str(skill_item.get("status", "")).lower()
        if any(word in status for word in ["missing", "unknown", "rusty", "not ready", "gap"]):
            qfile, q = make_bridge_quest(skill_item.get("skill", "Practice"), project_name, goal_name, skill_item.get("why_needed", "Bridge skill needed."))
            created.append({"quest_file": qfile, "title": q.get("title"), "skill": q.get("skill")})
    if not created:
        # create at least first path quest as bridge if no missing flags exist
        if plan.get("quest_plan"):
            qfile, q = make_quest_from_path_item(plan, 0)
            created.append({"quest_file": qfile, "title": q.get("title"), "skill": q.get("skill")})
    plan.setdefault("bridge_quests", []).extend(created)
    save_path(plan, filename)
    flash(f"Bridge quest chain created: {len(created)} quest(s).")
    return redirect(url_for("view_path", filename=filename))

@app.route("/projects/<filename>/issue", methods=["POST"])
def create_project_issue(filename: str):
    try:
        project = json.loads((PROJECT_DIR / filename).read_text(encoding="utf-8"))
    except Exception:
        flash("Project not found.")
        return redirect(url_for("projects"))
    issue_text = request.form.get("issue", "").strip()
    if not issue_text:
        flash("Describe the issue, feature, bug, or improvement you want.")
        return redirect(url_for("view_project", filename=filename))
    project_name = project.get("project_name", filename.replace(".json", ""))
    issue = issue_mode_prompt(project_name, issue_text)
    item = {"created_at": datetime.now().isoformat(timespec="seconds"), "issue_text": issue_text, "analysis": issue, "status": "Open"}
    items = load_bottlenecks(project_name)
    items.insert(0, item)
    save_bottlenecks(project_name, items)
    first = issue.get("first_quest", {})
    skill = first.get("skill") or "Project Tracking"
    qfile, q = make_quest(skill, f"Project Issue: {project_name}", issue_text, "", f"{issue.get('issue_type','Issue').title()} Quest", resume_project=project_name)
    for src,dst in [("title","title"),("what_to_build","what_to_build"),("requirements","requirements"),("steps","steps"),("success_criteria","success_criteria"),("proof_required","proof_required")]:
        if first.get(src): q[dst]=first[src]
    q["why_this_exists"] = issue.get("why_it_matters", q.get("why_this_exists"))
    (QUEST_DIR / qfile).write_text(json.dumps(q, indent=2), encoding="utf-8")
    flash("Project issue saved and exact improvement quest created.")
    return redirect(url_for("view_quest", filename=qfile))





# -----------------------------
# Product OS Navigation / Sources / Growth Routes
# -----------------------------
@app.route("/sources")
def sources():
    """Project Source Manager: connect living folders, ZIPs, and manual project ideas."""
    return render_template("sources.html", projects=list_projects())

@app.route("/analyze_folder", methods=["POST"])
def analyze_folder():
    """Analyze a local project folder without requiring a ZIP upload."""
    project_name = request.form.get("project_name", "").strip()
    folder_text = request.form.get("project_folder_path", "").strip()

    if not folder_text:
        flash("Enter a project folder path.")
        return redirect(url_for("sources"))

    project_root = Path(folder_text).expanduser()
    if not project_root.exists() or not project_root.is_dir():
        flash(f"Folder not found or not a folder: {folder_text}")
        return redirect(url_for("sources"))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        report = analyze_project(project_root, project_name or project_root.name)
        report["source_type"] = "Local Folder"
        report["source_path"] = str(project_root)
        report["report_filename"] = f"{timestamp}_{report['project_name'].replace(' ', '_')}.json"

        project_update = update_project_record(report, report["report_filename"])
        if project_update.get("duplicate_upload"):
            flash(f"No meaningful changes detected for {report['project_name']}. Existing project history was kept clean.")
            previous = project_update.get("previous_report")
            if previous:
                return redirect(url_for("view_report", filename=previous))
            return redirect(url_for("projects"))

        auto_generate_quests_for_report(report, report["report_filename"])
        save_report(report["report_filename"], report)
        update_skill_library_from_report(report)
        flash(f"KDT OS scanned folder project: {report['project_name']}")
        return redirect(url_for("view_report", filename=report["report_filename"]))
    except Exception as exc:
        flash(f"Folder analysis failed: {exc}")
        return redirect(url_for("sources"))

@app.route("/growth")
def growth():
    """One place for goals, verified skills, progress, and the memory graph."""
    goals = list_goals()
    projects = list_projects()
    graph = skill_graph_summary()
    quests = list_quests()
    active_quests = [q for q in quests if q.get("status", "").lower() not in ["completed", "archived", "superseded"]]
    return render_template(
        "growth.html",
        goals=goals,
        projects=projects,
        graph=graph,
        quests=quests,
        active_quests=active_quests[:8],
        trust=trust_summary(),
    )


@app.route("/quest_maintenance")
def quest_maintenance():
    return render_template("quest_maintenance.html", summary=quest_maintenance_summary(), postmortems=list_quest_postmortems()[:12])

@app.route("/quest_maintenance/regenerate", methods=["POST"])
def regenerate_weak_quests():
    count = 0
    created = []
    for q in quest_maintenance_summary().get("quests", []):
        if q.get("governance", {}).get("score", 0) < QUEST_MINIMUM_SCORE:
            newfile, _ = regenerate_quest(q.get("filename"))
            if newfile:
                count += 1
                created.append(newfile)
    flash(f"Quest Governance regenerated {count} weak quest(s).")
    return redirect(url_for("quest_maintenance"))

@app.route("/quests/<filename>/regenerate", methods=["POST"])
def regenerate_single_quest(filename: str):
    newfile, newq = regenerate_quest(filename)
    if not newfile:
        flash("Quest not found.")
        return redirect(url_for("quests"))
    flash("Quest regenerated. Original archived with postmortem.")
    return redirect(url_for("view_quest", filename=newfile))

@app.route("/quest_archive")
def quest_archive():
    return render_template("quest_archive.html", archived=list_archived_quests(), postmortems=list_quest_postmortems())

@app.route("/download/<filename>")
def download_report(filename: str):
    return send_from_directory(REPORT_DIR, filename, as_attachment=True)

import sys
from kdt_quest_intelligence_v20 import install as install_v20
from kdt_intelligence_v21 import install as install_v21
from routes.verify_routes import register_verify_routes
from routes.system_routes import register_system_routes

# V28 modular extraction: app.py now delegates route-family registration.
# Keep V20/V21 direct for now because they still touch core learning/mastery systems.
install_v20(sys.modules[__name__])
install_v21(sys.modules[__name__])
register_verify_routes(sys.modules[__name__])
register_system_routes(sys.modules[__name__])

try:
    from kdt_route_extraction_v28 import install as install_v28
    install_v28(sys.modules[__name__])
except Exception as exc:
    print(f"KDT OS V28 Route Extraction failed to install: {exc}")

try:
    from kdt_core_storage_v29 import install as install_v29
    install_v29(sys.modules[__name__])
except Exception as exc:
    print(f"KDT OS V29 Core Storage failed to install: {exc}")


try:
    from kdt_command_center_v30 import install as install_v30
    install_v30(sys.modules[__name__])
except Exception as exc:
    print(f"KDT OS V30 Command Center failed to install: {exc}")

try:
    from kdt_shared_helpers_v31 import install as install_v31
    install_v31(sys.modules[__name__])
except Exception as exc:
    print(f"KDT OS V31 Shared Helpers failed to install: {exc}")

try:
    from kdt_learning_intelligence_v32 import install as install_v32
    install_v32(sys.modules[__name__])
except Exception as exc:
    print(f"KDT OS V32 Learning Intelligence failed to install: {exc}")

if __name__ == "__main__":
    ensure_ollama_ready(wait_seconds=3.0)
    app.run(debug=True)