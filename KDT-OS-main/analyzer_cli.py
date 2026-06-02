
from __future__ import annotations

import json
import re
import shutil
import sys
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

SUPPORTED_TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".html", ".css", ".json", ".md", ".txt", ".yml", ".yaml",
    ".toml", ".ini", ".cfg", ".bat", ".ps1", ".sh", ".sql", ".env", ".gitignore"
}

IGNORE_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", "env", "dist", "build",
    ".next", ".pytest_cache", ".mypy_cache", ".idea", ".vscode"
}

TECH_RULES = {
    "Flask": [r"from flask import", r"import flask", r"Flask\("],
    "FastAPI": [r"from fastapi import", r"FastAPI\("],
    "SQLite": [r"sqlite3", r"\.sqlite", r"\.db", r"CREATE TABLE"],
    "JavaScript": [r"addEventListener", r"querySelector", r"document\.getElementById"],
    "Python": [r"\.py$", r"def ", r"class "],
    "PowerShell": [r"\.ps1$", r"Get-", r"Set-", r"New-"],
    "HTML/CSS": [r"<html", r"<body", r"\.css$", r"display:\s*flex"],
    "API / Routes": [r"@app\.route", r"@router\.", r"fetch\(", r"axios"],
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
    "Learning/Practice": [r"practice", r"drill", r"quiz", r"lesson", r"mastery"],
    "File Handling": [r"open\(", r"read_text", r"write_text", r"shutil", r"zipfile"],
    "Automation/Scheduling": [r"schedule", r"cron", r"interval", r"datetime", r"timedelta"],
}

RISK_RULES = {
    "Hardcoded secret/key": [r"secret_key\s*=\s*[\"'][^\"']+", r"api_key\s*=\s*[\"'][^\"']+", r"password\s*=\s*[\"'][^\"']+"],
    "Debug mode enabled": [r"debug\s*=\s*True"],
    "Broad exception handling": [r"except Exception", r"except:"],
}

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

def match_rules(text: str, rel_path: str, rules: Dict[str, List[str]]) -> Dict[str, int]:
    haystack = f"{rel_path}\n{text}"
    found = {}
    for name, patterns in rules.items():
        count = 0
        for pattern in patterns:
            count += len(re.findall(pattern, haystack, flags=re.IGNORECASE))
        if count:
            found[name] = count
    return found

def analyze_project(project_root: Path, original_name: str = "") -> Dict[str, Any]:
    files = iter_project_files(project_root)
    ext_counts = Counter(path.suffix.lower() or "[no extension]" for path in files)
    tech_scores = Counter()
    capability_scores = Counter()
    risk_scores = Counter()
    important_files = []
    route_count = function_count = class_count = text_file_count = 0
    sample_files = []

    for path in files:
        rel = str(path.relative_to(project_root)).replace("\\", "/")
        if path.suffix.lower() in SUPPORTED_TEXT_EXTENSIONS or path.name.lower() in {"readme", "dockerfile"}:
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

    test_files = [str(p.relative_to(project_root)).replace("\\", "/") for p in files if "test" in p.name.lower()]
    if not test_files:
        risk_scores["No tests detected"] += 1

    health_score = 100
    if len(files) == 0:
        health_score = 0
    health_score -= min(20, risk_scores.get("Hardcoded secret/key", 0) * 5)
    health_score -= 10 if risk_scores.get("Debug mode enabled", 0) else 0
    health_score -= 10 if risk_scores.get("No tests detected", 0) else 0
    health_score -= min(10, risk_scores.get("Broad exception handling", 0) * 2)
    health_score = max(0, health_score)

    recommendations = []
    if "No tests detected" in risk_scores:
        recommendations.append("Add a basic smoke test so the project can prove it still runs.")
    if "Learning/Practice" in capability_scores:
        recommendations.append("Track repetitions, mistakes, and mastery level so learning becomes measurable.")
    if "Health Monitoring" in capability_scores or "Repair Planning" in capability_scores:
        recommendations.append("Preserve this as a reusable KDT OS inspection/self-health capability.")
    if not recommendations:
        recommendations.append("Write a README with purpose, current features, and next step.")

    return {
        "project_name": original_name or project_root.name,
        "analyzed_at": datetime.now().isoformat(timespec="seconds"),
        "root_folder": str(project_root),
        "summary": {
            "file_count": len(files),
            "text_file_count": text_file_count,
            "total_size_bytes": sum(p.stat().st_size for p in files),
            "health_score": health_score,
            "functions_detected": function_count,
            "classes_detected": class_count,
            "routes_detected": route_count,
        },
        "extensions": dict(ext_counts.most_common()),
        "important_files": important_files[:30],
        "sample_files": sample_files,
        "technologies": [{"name": k, "score": v} for k, v in tech_scores.most_common()],
        "capabilities": [{"name": k, "score": v} for k, v in capability_scores.most_common()],
        "risks": [{"name": k, "count": v} for k, v in risk_scores.most_common()],
        "test_files": test_files[:30],
        "recommendations": recommendations,
        "next_decision": {
            "question": "What do you want to do with this project?",
            "options": [
                "Keep as its own project",
                "Reuse parts inside KDT OS",
                "Turn into a 1-day build / skill artifact",
                "Pause/archive it",
                "Continue building the next feature"
            ]
        }
    }

def main():
    if len(sys.argv) < 2:
        print("Usage: python analyzer_cli.py <project-folder-or-zip> [Project Name]")
        raise SystemExit(1)

    input_path = Path(sys.argv[1]).resolve()
    project_name = sys.argv[2] if len(sys.argv) >= 3 else input_path.stem

    workspace = Path("workspace_cli")
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir()

    if input_path.suffix.lower() == ".zip":
        safe_extract_zip(input_path, workspace)
        children = [p for p in workspace.iterdir()]
        root = children[0] if len(children) == 1 and children[0].is_dir() else workspace
    else:
        root = input_path

    report = analyze_project(root, project_name)
    reports = Path("reports")
    reports.mkdir(exist_ok=True)
    out = reports / f"{project_name.replace(' ', '_')}_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nSaved report to: {out}")

if __name__ == "__main__":
    main()
