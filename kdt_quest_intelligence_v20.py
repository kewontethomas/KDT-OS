"""KDT OS Quest Intelligence V20

This module hardens quest generation without deleting history.
It is designed as a compatibility patch for the current single-file app.py.

What it fixes:
- Same-title/same-body active quest duplication
- Generic quest bodies passing as high-quality quests
- Weak regenerated quests that only change the card title
- Micro quests that are weaker than regular quests
- Existing old quests that need archive + postmortem + replacement

Use through run_kdt_os.py or repair_current_quests_v20.py.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


GENERIC_PHRASES = [
    "a small project that demonstrates",
    "small project that demonstrates the requested skill",
    "create the required files",
    "use the skill directly",
    "show the result",
    "write what confused you",
    "implement the smallest working version",
    "one artifact that proves",
    "single proof quest",
    "exact_skill_proof_drill",
    "practice one skill with a small, clear build",
]

SKILL_WORDS = [
    "python", "sqlite", "testing", "health monitoring", "active directory", "cpu usage",
    "javascript", "html/css", "api / routes", "flask", "file handling", "dashboard/ui",
    "project tracking", "learning/practice",
]


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _slug(value: str) -> str:
    value = (value or "quest").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value or "quest"


def normalize_skill_local(skill: str) -> str:
    low = (skill or "").lower()
    if "active directory" in low or "organizational unit" in low or re.search(r"\bou\b", low):
        return "Active Directory"
    if "cpu" in low or "task manager" in low:
        return "CPU Usage"
    if "sqlite" in low or "database" in low or "crud" in low:
        return "SQLite"
    if "api" in low or "route" in low or "weather" in low or "fetch" in low:
        return "API / Routes"
    if "test" in low or "pytest" in low or "smoke" in low:
        return "Testing"
    if "health" in low or "warning" in low or "diagnostic" in low:
        return "Health Monitoring"
    if "html" in low or "css" in low or "responsive" in low or "layout" in low:
        return "HTML/CSS"
    if "javascript" in low or "dom" in low:
        return "JavaScript"
    if "flask" in low:
        return "Flask"
    if "python" in low or "function" in low or "expense" in low:
        return "Python"
    return (skill or "Python").strip()


def quest_body_text(q: Dict[str, Any]) -> str:
    parts = [
        q.get("title", ""), q.get("skill", ""), q.get("goal", ""),
        q.get("what_to_build", ""), q.get("user_gap", ""),
    ]
    for key in ("requirements", "steps", "success_criteria", "proof_required", "proof"):
        parts.extend(_as_list(q.get(key)))
    return "\n".join(str(x) for x in parts if str(x).strip()).lower()


def canonical_instruction_text(q: Dict[str, Any]) -> str:
    """Instruction-only text for duplicate detection.

    This intentionally removes titles/skill words so KDT OS catches quests that
    only changed the card label while keeping the same generic body.
    """
    parts: List[str] = []
    parts.append(str(q.get("what_to_build", "")))
    for key in ("requirements", "steps", "success_criteria", "proof_required", "proof"):
        parts.extend(_as_list(q.get(key)))
    text = " ".join(parts).lower()
    for word in SKILL_WORDS:
        text = text.replace(word, " skill ")
    text = re.sub(r"\b(kdt|fieldseed|workout|weather|expense|cpu|aduc|ou|route|flask|sqlite|python)\b", " item ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def instruction_signature(q: Dict[str, Any]) -> str:
    text = canonical_instruction_text(q)
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()


def token_similarity(a: str, b: str) -> float:
    aw = set(re.findall(r"[a-z0-9_]{3,}", a.lower()))
    bw = set(re.findall(r"[a-z0-9_]{3,}", b.lower()))
    if not aw or not bw:
        return 0.0
    return len(aw & bw) / max(1, len(aw | bw))


def generic_hits(q: Dict[str, Any]) -> int:
    text = quest_body_text(q)
    return sum(1 for phrase in GENERIC_PHRASES if phrase in text)


def specificity_markers(skill: str) -> List[str]:
    skill = normalize_skill_local(skill)
    if skill == "SQLite":
        return ["sqlite3", "workouts.db", "CREATE TABLE", "INSERT", "SELECT", "UPDATE", "DELETE", "exercise", "sets", "reps"]
    if skill == "Python":
        return ["def calculate_total", "expenses", "return", "sum(", "print", "app.py"]
    if skill == "Testing":
        return ["tests", "test_routes.py", "pytest", "def test_", "assert", "status_code", "test client"]
    if skill == "API / Routes":
        return ["fetch", "response.json", "result", "endpoint", "error", "loading", "script.js"]
    if skill == "HTML/CSS":
        return ["index.html", "style.css", "card", "grid", "flex", "@media", "responsive"]
    if skill == "JavaScript":
        return ["index.html", "script.js", "addEventListener", "textContent", "querySelector", "button"]
    if skill == "Health Monitoring":
        return ["cpu_check", "memory_check", "disk_check", "OK", "WARNING", "health_log"]
    if skill == "Active Directory":
        return ["ADUC", "KDT_Practice", "Workstations", "Organizational Unit", "screenshot", "GPO"]
    if skill == "CPU Usage":
        return ["Task Manager", "CPU", "process", "percentage", "screenshot", "cpu_usage_notes"]
    if skill == "Flask":
        return ["app.py", "@app.route", "render_template", "templates", "request", "route"]
    return ["README.md", "specific artifact", "screenshot", "explain"]


def specificity_score(q: Dict[str, Any]) -> int:
    text = quest_body_text(q)
    markers = specificity_markers(q.get("skill", ""))
    hits = 0
    for marker in markers:
        if marker.lower() in text:
            hits += 1
    return hits


def quality_review(q: Dict[str, Any], duplicate_note: str = "") -> Dict[str, Any]:
    steps = _as_list(q.get("steps"))
    requirements = _as_list(q.get("requirements"))
    success = _as_list(q.get("success_criteria"))
    proof = _as_list(q.get("proof_required") or q.get("proof"))
    text = quest_body_text(q)
    skill = normalize_skill_local(q.get("skill", ""))

    checks = []
    def add(name: str, ok: bool, fix: str, weight: int) -> None:
        checks.append({"name": name, "ok": bool(ok), "fix": fix, "weight": weight})

    spec = specificity_score(q)
    gen = generic_hits(q)
    exact_artifact = bool(re.search(r"\b(app\.py|index\.html|style\.css|script\.js|readme\.md|test_\w+\.py|workouts\.db|\.db|\.txt|screenshot|aduc|task manager)\b", text, re.I))
    useful_steps = len(steps) >= 8 and len(set(s.lower() for s in steps)) == len(steps)
    step_verbs = sum(1 for s in steps if re.search(r"\b(create|open|type|write|run|click|add|save|test|take|upload|explain|verify|change|confirm)\b", s, re.I))
    measurable = len(success) >= 4 and bool(re.search(r"\b(exists|visible|prints|returns|saves|created|shows|includes|runs|passes|appears|contains)\b", " ".join(success), re.I))
    proof_specific = len(proof) >= 3 and bool(re.search(r"\b(upload|include|screenshot|answer|terminal output|readme|\.py|\.html|\.db|\.txt|zip)\b", " ".join(proof), re.I))
    understanding = bool(re.search(r"\b(answer|explain|why|what does|difference between|in your own words|what changed)\b", " ".join(proof + success + requirements), re.I))

    add("Specific skill normalized", bool(skill), "Normalize confusion text into a real skill name.", 6)
    add("Exact artifact named", exact_artifact, "Name exact files, screenshots, database, or proof artifact.", 12)
    add("Skill-specific details", spec >= 3, "Add technology-specific commands, fields, functions, UI IDs, or outputs.", 18)
    add("No generic template language", gen == 0, "Remove generic language that could fit any skill.", 18)
    add("Useful step-by-step guide", useful_steps and step_verbs >= 7, "Give at least 8 exact steps that move from start to proof.", 16)
    add("Required features are concrete", len(requirements) >= 5, "List concrete files, fields, buttons, functions, or actions.", 8)
    add("Measurable success criteria", measurable, "Success criteria must prove the quest worked.", 10)
    add("Proof is specific", proof_specific, "Proof must name exactly what to upload and answer.", 8)
    add("Understanding check included", understanding, "Require an explanation so proof is not blind copying.", 4)
    add("Not semantically duplicated", not duplicate_note, "Archive or regenerate duplicate active quests.", 14)

    total = sum(c["weight"] for c in checks)
    earned = sum(c["weight"] for c in checks if c["ok"])
    score = int((earned / total) * 100) if total else 0
    penalties = []
    if gen:
        score = min(score, 68)
        penalties.append(f"Generic quest language detected ({gen} marker(s)).")
    if spec < 3:
        score = min(score, 76)
        penalties.append("Not enough skill-specific implementation details.")
    if duplicate_note:
        score = min(score, 62)
        penalties.append(duplicate_note)
    if not useful_steps:
        score = min(score, 82)
        penalties.append("Step-by-step guide is not strong enough yet.")
    if not proof_specific:
        score = min(score, 80)
        penalties.append("Proof requirements are too vague.")

    if score >= 95:
        rating = "10/10 Ready"
    elif score >= 85:
        rating = "Approved"
    elif score >= 70:
        rating = "Needs upgrade"
    else:
        rating = "Reject / regenerate"

    return {
        "score": score,
        "rating": rating,
        "checks": checks,
        "passed": sum(1 for c in checks if c["ok"]),
        "total": len(checks),
        "penalties": penalties,
        "specificity_score": spec,
        "generic_hits": gen,
        "template_clone": bool(duplicate_note or gen >= 2),
        "duplicate_note": duplicate_note,
    }


def quest_templates() -> Dict[str, Dict[str, Any]]:
    """Specific quest templates that are step-by-step useful from start to proof."""
    return {
        "SQLite": {
            "title": "SQLite CRUD Quest: Workout Database",
            "goal": "Build a real SQLite CRUD app so database practice creates lasting proof.",
            "what_to_build": "A command-line Python app named app.py that creates workouts.db, saves workouts, lists them, updates one, and deletes one.",
            "requirements": ["Create folder workout_database_crud", "Create app.py", "Import sqlite3", "Create workouts.db", "Create workouts table with id, exercise, sets, reps, date", "Add menu options: Add, List, Update, Delete, Exit", "Create README.md"],
            "steps": ["Create a folder named workout_database_crud", "Create a file named app.py", "At the top import sqlite3", "Connect to workouts.db", "Create a workouts table with id INTEGER PRIMARY KEY, exercise TEXT, sets INTEGER, reps INTEGER, date TEXT", "Write add_workout() that inserts one workout", "Write list_workouts() that selects and prints all rows", "Write update_workout() that updates sets or reps by id", "Write delete_workout() that deletes by id", "Create a while loop menu with choices 1 Add, 2 List, 3 Update, 4 Delete, 5 Exit", "Run python app.py and add at least two workouts", "Close and rerun the app to prove saved rows still exist", "Create README.md with the run command and one sentence explaining what a row is", "Zip and submit the folder"],
            "success_criteria": ["app.py exists", "workouts.db is created after running", "CREATE TABLE is used", "INSERT, SELECT, UPDATE, and DELETE are used", "At least two workouts can be listed after restart", "README.md explains row vs table"],
            "proof_required": ["Upload ZIP", "Include app.py", "Include README.md", "Include workouts.db if it was created", "Include screenshot or copied terminal output showing rows listed after restart", "Answer: what is the difference between a table and a row?"],
            "verification_patterns": ["sqlite3", "CREATE TABLE", "INSERT", "SELECT", "UPDATE", "DELETE", "workouts.db"],
            "difficulty": "Beginner", "estimated_time": "45-75 minutes",
        },
        "Python": {
            "title": "Python Function Practice: Expense Totaler",
            "goal": "Practice functions, lists, return values, and terminal output with one complete mini app.",
            "what_to_build": "A command-line app named app.py with calculate_total(expenses) and print_summary(expenses) using at least three expenses.",
            "requirements": ["Create folder python_expense_totaler", "Create app.py", "Create expenses list", "Create calculate_total(expenses)", "Create print_summary(expenses)", "Use return", "Create README.md"],
            "steps": ["Create folder python_expense_totaler", "Create app.py", "Create a list named expenses with three numbers", "Define calculate_total(expenses)", "Inside calculate_total, return sum(expenses)", "Define print_summary(expenses)", "Inside print_summary, call calculate_total and store it in total", "Print each expense on its own line", "Print Final total: followed by the total", "Call print_summary(expenses) at the bottom", "Run python app.py", "Create README.md and answer: what does return send back?", "Zip and submit the folder"],
            "success_criteria": ["app.py exists", "calculate_total function exists", "print_summary function exists", "expenses list has at least three numbers", "Final total prints correctly", "README.md explains return"],
            "proof_required": ["Upload ZIP", "Include app.py", "Include README.md", "Include screenshot or copied terminal output", "Answer: what value did calculate_total return?"],
            "verification_patterns": ["def calculate_total", "def print_summary", "return", "sum(", "expenses"],
            "difficulty": "Beginner", "estimated_time": "25-45 minutes",
        },
        "Testing": {
            "title": "Flask Route Smoke Test Suite",
            "goal": "Prove a Flask project still opens its important pages after changes.",
            "what_to_build": "A pytest file named tests/test_routes.py that imports the Flask app and checks at least three routes return HTTP 200 or redirect safely.",
            "requirements": ["Create tests folder", "Create tests/test_routes.py", "Import the Flask app", "Create a test client", "Test /", "Test /quests or /projects", "Run python -m pytest", "Document failures in README.md"],
            "steps": ["Create a folder named tests", "Create tests/test_routes.py", "Open app.py and confirm the Flask object is named app", "In test_routes.py write from app import app", "Create client = app.test_client() inside each test or a fixture", "Write test_home_route() that requests /", "Assert the status code is 200 or 302", "Write test_quests_route() for /quests", "Write test_projects_route() for /projects", "Run python -m pytest", "If an import fails, write the exact error in README.md", "Add the test command to README.md", "Zip and submit the updated project"],
            "success_criteria": ["tests/test_routes.py exists", "At least three route tests exist", "app.test_client() is used", "pytest runs and shows pass/fail output", "README.md includes the test command"],
            "proof_required": ["Upload ZIP", "Include tests/test_routes.py", "Include README.md", "Include screenshot or copied pytest output", "Answer: which route would have caught the broken nav issue?"],
            "verification_patterns": ["def test_", "test_client", "status_code", "pytest", "/quests"],
            "difficulty": "Beginner", "estimated_time": "45-75 minutes",
        },
        "API / Routes": {
            "title": "API Weather Lookup App",
            "goal": "Practice API requests, JSON parsing, button events, loading state, and error handling.",
            "what_to_build": "A browser app with index.html, style.css, and script.js where a button fetches sample weather JSON and displays city, temperature, and condition.",
            "requirements": ["Create index.html", "Create style.css", "Create script.js", "Add input id cityInput", "Add button id searchBtn", "Add result div id result", "Use fetch()", "Use response.json()", "Show loading and error text"],
            "steps": ["Create folder api_weather_lookup", "Create index.html, style.css, and script.js", "In index.html add an input with id cityInput", "Add a button with id searchBtn", "Add a div with id result", "Link script.js at the bottom of the HTML body", "In script.js select cityInput, searchBtn, and result", "Add a click event listener to searchBtn", "Inside the click handler set result.textContent to Loading...", "Use fetch() to request sample JSON or a real weather endpoint", "Use response.json() to parse the data", "Display city, temperature, and condition inside result", "Add catch() or try/catch to show an error message", "Open index.html and test the button", "Create README.md explaining which API or sample JSON you used", "Zip and submit the folder"],
            "success_criteria": ["index.html, style.css, and script.js exist", "searchBtn click triggers JavaScript", "fetch() is used", "response.json() is used", "result area changes after the request", "Error text appears if request fails"],
            "proof_required": ["Upload ZIP", "Include index.html, style.css, script.js, README.md", "Include screenshot of result area after clicking", "Answer: what does response.json() do?"],
            "verification_patterns": ["fetch(", ".json()", "addEventListener", "cityInput", "searchBtn", "result"],
            "difficulty": "Beginner", "estimated_time": "45-75 minutes",
        },
        "Health Monitoring": {
            "title": "Mini Health Checker",
            "goal": "Practice health monitoring by turning values into OK/WARNING decisions.",
            "what_to_build": "A Python app named app.py that checks fake CPU, memory, and disk values, prints OK/WARNING, and saves health_log.txt.",
            "requirements": ["Create folder mini_health_checker", "Create app.py", "Create cpu_check(value)", "Create memory_check(value)", "Create disk_check(value)", "Print OK/WARNING", "Save health_log.txt", "Create README.md"],
            "steps": ["Create folder mini_health_checker", "Create app.py", "Define cpu_check(value) that returns WARNING if value > 80 else OK", "Define memory_check(value) that returns WARNING if value > 85 else OK", "Define disk_check(value) that returns WARNING if value > 90 else OK", "Create sample values cpu=82, memory=45, disk=93", "Call all three checks", "Print each result as CPU: WARNING or Memory: OK", "Create an overall status of Needs Attention if any check is WARNING", "Write the same output to health_log.txt", "Run python app.py", "Change CPU to 25 and run again", "Create README.md explaining the warning thresholds", "Zip and submit the folder"],
            "success_criteria": ["app.py exists", "cpu_check, memory_check, and disk_check exist", "OK and WARNING can both appear", "health_log.txt is created", "README.md explains thresholds"],
            "proof_required": ["Upload ZIP", "Include app.py", "Include health_log.txt", "Include README.md", "Include screenshot or copied output", "Answer: what value caused WARNING?"],
            "verification_patterns": ["def cpu_check", "def memory_check", "def disk_check", "health_log.txt", "WARNING", "OK"],
            "difficulty": "Beginner", "estimated_time": "35-60 minutes",
        },
        "HTML/CSS": {
            "title": "Responsive Card Layout",
            "goal": "Practice creating a clean responsive section that works on desktop and mobile.",
            "what_to_build": "A browser page with three project cards that stack on mobile and sit side-by-side on wider screens.",
            "requirements": ["Create index.html", "Create style.css", "Add three cards", "Use CSS grid or flex", "Add @media rule", "Create README.md"],
            "steps": ["Create folder responsive_card_layout", "Create index.html", "Create style.css", "Link style.css in index.html", "Add a main section with class card-grid", "Add three article elements with class card", "Give each card a heading and short paragraph", "In CSS style card-grid with display:grid or display:flex", "Add gap between cards", "Add border radius and padding to cards", "Add a media query so cards stack on small screens", "Open index.html and resize the browser", "Create README.md explaining the layout", "Zip and submit"],
            "success_criteria": ["index.html exists", "style.css exists", "Three cards are visible", "Grid or flex is used", "A media query exists", "Layout changes on narrow width"],
            "proof_required": ["Upload ZIP", "Include index.html and style.css", "Include screenshot or README note about mobile layout", "Answer: what CSS made the cards responsive?"],
            "verification_patterns": ["index.html", "style.css", "display: grid", "display:flex", "@media"],
            "difficulty": "Beginner", "estimated_time": "30-60 minutes",
        },
        "Active Directory": {
            "title": "Active Directory OU Proof Quest",
            "goal": "Prove you understand what an OU is and how it organizes users/computers.",
            "what_to_build": "In ADUC, create a safe practice OU named KDT_Practice, add a Workstations sub-OU, and document what it organizes.",
            "requirements": ["Open Active Directory Users and Computers", "Create OU KDT_Practice", "Create sub-OU Workstations", "Move or identify one safe object", "Take screenshot", "Create README.md"],
            "steps": ["Open Server Manager or the Start Menu", "Open Active Directory Users and Computers", "Expand your domain in the left tree", "Right-click the domain or a safe practice container", "Choose New > Organizational Unit", "Name the OU KDT_Practice", "Right-click KDT_Practice", "Choose New > Organizational Unit again", "Name the sub-OU Workstations", "Move one safe test computer/user into the OU if available, or write why no safe object was available", "Take a screenshot showing KDT_Practice and Workstations", "Create README.md", "In README.md answer: What is an OU?", "In README.md answer: How could a GPO use this OU later?", "Upload screenshot and README.md"],
            "success_criteria": ["KDT_Practice OU is visible", "Workstations sub-OU is visible", "Screenshot clearly shows ADUC", "README.md explains OU purpose", "README.md mentions GPO relationship"],
            "proof_required": ["Upload screenshot showing ADUC", "Include README.md", "Answer: what did the OU organize?", "Answer: why not put everything in Users?"],
            "verification_patterns": ["KDT_Practice", "Workstations", "ADUC", "Organizational Unit", "GPO"],
            "difficulty": "Beginner", "estimated_time": "20-40 minutes",
        },
        "CPU Usage": {
            "title": "CPU Usage Task Manager Proof Quest",
            "goal": "Prove you can find CPU usage and explain it during troubleshooting.",
            "what_to_build": "A screenshot-and-notes proof showing Task Manager CPU usage, top CPU process, and what the percentage means.",
            "requirements": ["Open Task Manager", "Sort by CPU", "Identify top process", "Open Performance > CPU", "Take screenshot", "Create cpu_usage_notes.txt"],
            "steps": ["Press Ctrl + Shift + Esc", "Click More details if Task Manager opens small", "Click Processes", "Click the CPU column to sort by CPU usage", "Write down the top process name", "Click Performance", "Click CPU", "Write down the current CPU percentage", "Take a screenshot", "Create cpu_usage_notes.txt", "Write the CPU percentage you saw", "Write the top process name", "Write one sentence explaining what high CPU can mean", "Upload screenshot and notes"],
            "success_criteria": ["Screenshot shows Task Manager", "CPU percentage is visible or written in notes", "One process name is identified", "Notes explain high vs low CPU", "Proof can be reviewed"],
            "proof_required": ["Upload screenshot of Task Manager", "Include cpu_usage_notes.txt", "Answer: what was the CPU percentage?", "Answer: which process used the most CPU?"],
            "verification_patterns": ["Task Manager", "CPU", "cpu_usage_notes", "process", "%"],
            "difficulty": "Beginner", "estimated_time": "10-20 minutes",
        },
    }


def build_specific_quest(old: Dict[str, Any], kdt: Any) -> Dict[str, Any]:
    skill = normalize_skill_local(old.get("skill") or old.get("title") or old.get("user_gap") or "Python")
    templates = quest_templates()
    tpl = templates.get(skill) or templates.get("Python")
    source = old.get("source_project", "Quest Intelligence V20")
    resume_project = old.get("resume_project") or old.get("connected_goal") or source
    q = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_project": source,
        "origin_report": old.get("origin_report", ""),
        "resume_project": resume_project,
        "connected_goal": old.get("connected_goal", ""),
        "skill": skill,
        "user_gap": old.get("user_gap") or f"I need exact practice with {skill}.",
        "quest_type": old.get("quest_type") or tpl.get("type", "Practice Quest"),
        "title": tpl["title"],
        "goal": tpl["goal"],
        "what_to_build": tpl["what_to_build"],
        "requirements": list(tpl["requirements"]),
        "steps": list(tpl["steps"]),
        "success_criteria": list(tpl["success_criteria"]),
        "proof_required": list(tpl["proof_required"]),
        "verification_patterns": list(tpl.get("verification_patterns", [])),
        "difficulty": tpl.get("difficulty", "Beginner"),
        "estimated_time": tpl.get("estimated_time", "30-60 minutes"),
        "ai_generated": False,
        "ai_parse_mode": "quest_intelligence_v20_specific_template",
        "ai_raw_response": "",
        "teach_me_breakdown": kdt.exact_breakdown_for(skill) if hasattr(kdt, "exact_breakdown_for") else [],
        "status": "Assigned",
        "submissions": [],
        "why_this_exists": f"Quest Intelligence V20 replaced or created this as a specific {skill} quest with exact steps, measurable proof, and a return path.",
        "resume_rule": "After this quest is complete, submit proof, update skill evidence, then return to the project or goal that caused this quest.",
    }
    q["quest_quality"] = quality_review(q)
    q["quest_standard"] = {
        "rule": "Every KDT OS quest must be specific, non-duplicated, beginner-safe, step-by-step useful, measurable, and proof-backed.",
        "minimum_fields": ["Specific skill", "Exact artifact", "Useful steps", "Success criteria", "Proof", "Understanding check", "Return point"],
    }
    return q


def install(kdt: Any) -> Any:
    """Monkeypatch the current app.py module with stronger V20 behavior."""

    def patched_quest_quality_check(quest: Dict[str, Any]) -> Dict[str, Any]:
        return quality_review(quest)

    def patched_apply_quest_quality(quest: Dict[str, Any]) -> Dict[str, Any]:
        quest["quest_quality"] = quality_review(quest)
        quest.setdefault("quest_standard", {
            "rule": "Every quest must be exact, skill-specific, non-duplicated, measurable, and proof-backed.",
            "minimum_fields": ["Exact artifact", "Concrete steps", "Success criteria", "Proof", "Understanding check"],
        })
        return quest

    def patched_quest_governance_decision(quest: Dict[str, Any]) -> Dict[str, Any]:
        q = dict(quest)
        review = quality_review(q)
        failed = [c for c in review.get("checks", []) if not c.get("ok")]
        score = review.get("score", 0)
        if score >= 95:
            action = "Keep"
        elif score >= kdt.QUEST_MINIMUM_SCORE:
            action = "Keep with warning"
        elif score >= 70:
            action = "Upgrade"
        else:
            action = "Regenerate"
        return {"score": score, "action": action, "rating": review.get("rating"), "failed_checks": failed, "minimum_score": kdt.QUEST_MINIMUM_SCORE, "approved": score >= kdt.QUEST_MINIMUM_SCORE}

    def patched_regenerate_quest(filename: str) -> Tuple[str, Dict[str, Any] | None]:
        path = kdt.QUEST_DIR / filename
        if not path.exists():
            return "", None
        old = json.loads(path.read_text(encoding="utf-8"))
        newq = build_specific_quest(old, kdt)
        newq["regenerated_from"] = filename
        newq["version"] = int(old.get("version", 1) or 1) + 1
        newq["governance_note"] = "Generated by Quest Intelligence V20 because the previous quest was duplicated, generic, or not step-by-step useful enough."
        qfile = f"{_slug(newq.get('title', 'quest'))}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        (kdt.QUEST_DIR / qfile).write_text(json.dumps(newq, indent=2), encoding="utf-8")
        if hasattr(kdt, "archive_quest"):
            kdt.archive_quest(filename, "Quest failed V20 anti-duplicate/specificity review and was regenerated.", qfile)
        if hasattr(kdt, "governance_log"):
            kdt.governance_log({"type": "quest_regenerated_v20", "old": filename, "new": qfile, "new_score": newq.get("quest_quality", {}).get("score")})
        return qfile, newq

    def patched_quest_maintenance_summary() -> Dict[str, Any]:
        raw: List[Dict[str, Any]] = []
        for p in sorted(kdt.QUEST_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                q = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            q["filename"] = p.name
            if q.get("status") in ["Archived", "Superseded", "Rejected"]:
                continue
            raw.append(q)

        signatures: Dict[str, List[str]] = {}
        titles: Dict[str, List[str]] = {}
        canon_texts: Dict[str, str] = {}
        for q in raw:
            sig = instruction_signature(q)
            q["instruction_signature"] = sig
            signatures.setdefault(sig, []).append(q["filename"])
            title_key = f"{q.get('title','').strip().lower()}|{normalize_skill_local(q.get('skill','')).lower()}"
            titles.setdefault(title_key, []).append(q["filename"])
            canon_texts[q["filename"]] = canonical_instruction_text(q)

        active: List[Dict[str, Any]] = []
        for q in raw:
            duplicate_reasons: List[str] = []
            if len(signatures.get(q["instruction_signature"], [])) > 1:
                duplicate_reasons.append("Exact instruction clone detected across active quests.")
            title_key = f"{q.get('title','').strip().lower()}|{normalize_skill_local(q.get('skill','')).lower()}"
            if len(titles.get(title_key, [])) > 1:
                duplicate_reasons.append("Same title and skill exists more than once.")
            # semantic near-duplicate check
            for other in raw:
                if other.get("filename") == q.get("filename"):
                    continue
                sim = token_similarity(canon_texts.get(q["filename"], ""), canon_texts.get(other.get("filename"), ""))
                if sim >= 0.86:
                    duplicate_reasons.append(f"Near-duplicate body detected ({int(sim*100)}% similar to {other.get('filename')}).")
                    break
            duplicate_note = " ".join(dict.fromkeys(duplicate_reasons))
            review = quality_review(q, duplicate_note=duplicate_note)
            q["quest_quality"] = review
            q["governance"] = {
                "score": review["score"],
                "action": "Keep" if review["score"] >= 95 else ("Keep with warning" if review["score"] >= kdt.QUEST_MINIMUM_SCORE else "Regenerate"),
                "rating": review["rating"],
                "failed_checks": [c for c in review["checks"] if not c.get("ok")],
                "minimum_score": kdt.QUEST_MINIMUM_SCORE,
                "approved": review["score"] >= kdt.QUEST_MINIMUM_SCORE,
            }
            active.append(q)

        return {
            "quests": active,
            "total": len(active),
            "approved": sum(1 for q in active if q["governance"]["approved"]),
            "needs_work": sum(1 for q in active if not q["governance"]["approved"]),
            "archive_count": len(kdt.list_archived_quests()) if hasattr(kdt, "list_archived_quests") else 0,
            "postmortem_count": len(kdt.list_quest_postmortems()) if hasattr(kdt, "list_quest_postmortems") else 0,
            "minimum_score": kdt.QUEST_MINIMUM_SCORE,
        }

    def patched_micro_breakdown_for(skill: str, obstacle: str, parent: Dict[str, Any]) -> Dict[str, Any]:
        skill = normalize_skill_local(skill)
        if skill == "SQLite":
            q = {
                "title": "SQLite Micro Quest: Table Rows and Columns",
                "goal": "Understand the table idea before writing SQLite CRUD code.",
                "what_to_build": "A text file named table_practice.txt that shows a workouts table with columns exercise, sets, reps, and date plus exactly three rows.",
                "requirements": ["Create folder sqlite_micro_table", "Create table_practice.txt", "Add header exercise | sets | reps | date", "Add exactly three workout rows", "Write one row definition", "Write one column definition"],
                "steps": ["Create folder sqlite_micro_table", "Open Notepad or VS Code", "Create table_practice.txt", "Type the header: exercise | sets | reps | date", "Add row 1 with Pushups, 3, 10, today's date", "Add row 2 with Squats, 3, 12, today's date", "Add row 3 with Plank, 2, 30 seconds, today's date", "Under the table write: A row is...", "Under that write: A column is...", "Save the file", "Upload the file or screenshot", "Return to the parent SQLite quest"],
                "success_criteria": ["table_practice.txt exists", "Four columns are visible", "Exactly three rows are present", "Row explanation exists", "Column explanation exists"],
                "proof_required": ["Upload table_practice.txt or screenshot", "Answer: which part becomes a SQLite column?", "Answer: which part becomes a SQLite row?"],
                "verification_patterns": ["exercise", "sets", "reps", "date"],
                "difficulty": "Starter", "estimated_time": "5-10 minutes",
            }
        elif skill == "Python":
            q = {
                "title": "Python Micro Quest: Variable to Function",
                "goal": "Prove you understand how a value moves into a function before building a larger app.",
                "what_to_build": "A file named function_micro.py with greet(name) that returns a sentence and prints it.",
                "requirements": ["Create folder python_micro_function", "Create function_micro.py", "Define greet(name)", "Use return", "Print the returned result"],
                "steps": ["Create folder python_micro_function", "Create function_micro.py", "Type def greet(name):", "Inside it return 'Hello, ' + name", "Below the function type message = greet('Kewonte')", "Print message", "Run python function_micro.py", "Confirm the sentence appears", "Change Kewonte to another name and run again", "Write one sentence explaining what return did", "Upload the file", "Return to the parent Python quest"],
                "success_criteria": ["function_micro.py exists", "greet(name) exists", "return is used", "print output appears", "Explanation mentions return"],
                "proof_required": ["Upload function_micro.py or ZIP", "Include screenshot/copied output", "Answer: what did greet() return?"],
                "verification_patterns": ["def greet", "return", "print"],
                "difficulty": "Starter", "estimated_time": "5-15 minutes",
            }
        else:
            old = {"skill": skill, "source_project": parent.get("source_project", "Quest Breakdown"), "user_gap": obstacle, "quest_type": "Quest Breakdown"}
            q = build_specific_quest(old, kdt)
            q["title"] = f"Micro Quest: {q['title']}"
            q["estimated_time"] = "10-20 minutes"
        q["skill"] = skill
        q["quest_type"] = "Quest Breakdown"
        q["parent_quest"] = parent.get("filename", "")
        q["status"] = "Assigned"
        q["submissions"] = []
        q["why_this_exists"] = f"This micro quest breaks down the parent blocker: {obstacle or 'I do not know where to start.'}"
        q["quest_quality"] = quality_review(q)
        return q

    kdt.quest_quality_check = patched_quest_quality_check
    kdt.apply_quest_quality = patched_apply_quest_quality
    kdt.quest_governance_decision = patched_quest_governance_decision
    kdt.regenerate_quest = patched_regenerate_quest
    kdt.quest_maintenance_summary = patched_quest_maintenance_summary
    kdt.micro_breakdown_for = patched_micro_breakdown_for
    kdt.instruction_signature = instruction_signature
    kdt.canonical_instruction_text = canonical_instruction_text
    kdt.quality_review_v20 = quality_review
    kdt.build_specific_quest_v20 = build_specific_quest
    return kdt
