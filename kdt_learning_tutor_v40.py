"""KDT OS Learning Tutor Engine V40

V40 turns quests from instructions into training.
It creates beginner-readable tutor guides with:
- what you are building
- why it matters
- a real-world analogy
- step-by-step explanation
- common mistakes
- proof checklist
- reflection questions

This version is intentionally safe and deterministic first. It can use the
existing Ollama layer later, but it must still teach when AI is unavailable.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

try:
    from core.storage import load_json, save_json, list_json_files, read_text
except Exception:  # fallback for older checkpoints
    def load_json(path, default=None):
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            return default
    def save_json(path, data):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
    def list_json_files(folder):
        return sorted(Path(folder).glob("*.json"))
    def read_text(path):
        try:
            return Path(path).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""


def _slug(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "quest"


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        parts = [p.strip(" -\t") for p in value.splitlines() if p.strip()]
        return parts or ([value.strip()] if value.strip() else [])
    return [str(value)]


def _quest_files(kdt: Any) -> List[Path]:
    folder = Path(getattr(kdt, "QUEST_DIR", Path(kdt.APP_ROOT) / "quests"))
    return sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def _load_quests(kdt: Any) -> List[Dict[str, Any]]:
    quests: List[Dict[str, Any]] = []
    for path in _quest_files(kdt):
        data = load_json(path, {}) or {}
        if isinstance(data, dict):
            data["filename"] = path.name
            quests.append(data)
    return quests


def _skill_family(skill: str, title: str = "") -> str:
    text = f"{skill} {title}".lower()
    if any(w in text for w in ["sqlite", "database", "crud", "sql"]):
        return "SQLite"
    if any(w in text for w in ["flask", "route", "server", "backend"]):
        return "Flask"
    if any(w in text for w in ["javascript", "api", "fetch", "dom", "weather"]):
        return "JavaScript / API"
    if any(w in text for w in ["html", "css", "responsive", "layout", "card"]):
        return "HTML/CSS"
    if any(w in text for w in ["python", "function", "file", "cli", "health"]):
        return "Python"
    if any(w in text for w in ["active directory", "ou", "aduc", "group policy"]):
        return "Active Directory"
    if any(w in text for w in ["cpu", "task manager", "monitoring"]):
        return "Troubleshooting"
    if any(w in text for w in ["test", "pytest", "smoke"]):
        return "Testing"
    return skill or "General"


SKILL_TEACHING = {
    "SQLite": {
        "plain_definition": "SQLite is a small database saved as a file. Your Python program can open the file, create tables, store rows, read rows, update rows, and delete rows.",
        "analogy": "Think of the database file as a filing cabinet. A table is one drawer. A row is one sheet of paper in that drawer. A column is one label on every sheet, like Exercise, Sets, or Reps.",
        "why_it_matters": "Almost every serious app needs to remember information after the program closes. SQLite teaches the basic database skills used later in bigger apps.",
        "mental_model": ["Database file = storage container", "Table = organized category", "Row = one saved item", "Column = one detail about each item", "Query = instruction you give the database"],
        "common_mistakes": ["Forgetting conn.commit(), so changes do not save.", "Creating a table but never inserting data.", "Thinking a database is the same thing as a spreadsheet. It is similar, but code talks to it with SQL.", "Not checking the database file after running the program."],
        "reflection": ["What is the difference between a database and a table?", "What does one row represent in your project?", "Why does commit matter?"],
    },
    "Flask": {
        "plain_definition": "Flask is a Python tool for making web pages and web endpoints. A route tells Flask what to do when someone visits a URL.",
        "analogy": "Think of Flask as a building. A route is a labeled door. When someone knocks on /hello, Flask checks which function owns that door and sends back the response.",
        "why_it_matters": "Flask lets your Python code become an app other people can use through a browser.",
        "mental_model": ["URL = address someone visits", "Route = rule that listens for that address", "Function = code that runs", "Return value = what the browser receives", "Template = HTML page Flask fills in"],
        "common_mistakes": ["Forgetting to restart Flask after changing code.", "Changing a URL in HTML but not creating a matching Flask route.", "Forgetting to return something from the route function.", "Putting templates in the wrong folder."],
        "reflection": ["What does a route do?", "What happens if a user visits a route that does not exist?", "Why does Flask need a function under the route?"],
    },
    "JavaScript / API": {
        "plain_definition": "JavaScript makes a web page respond to clicks, inputs, and outside data. An API request asks another service for data, usually in JSON form.",
        "analogy": "Think of an API like a restaurant counter. Your app places an order with fetch(). The API returns a bag of data. JavaScript opens the bag and puts the useful parts on the page.",
        "why_it_matters": "Modern apps constantly request data, update the screen, and react to users without reloading the whole page.",
        "mental_model": ["Button click = user action", "fetch() = request for data", "response.json() = unpack the returned data", "DOM update = change what the user sees", "catch/error handling = what happens if the request fails"],
        "common_mistakes": ["Trying to use API data before it finishes loading.", "Forgetting to connect script.js to index.html.", "Using the wrong element id.", "Not showing an error message when fetch fails."],
        "reflection": ["What does fetch() do?", "Why do we convert a response to JSON?", "What should the user see if the API fails?"],
    },
    "HTML/CSS": {
        "plain_definition": "HTML creates the structure of a page. CSS controls how that structure looks, moves, spaces out, and responds to screen size.",
        "analogy": "HTML is the skeleton of a house. CSS is the paint, furniture, spacing, lighting, and room layout.",
        "why_it_matters": "A project that works but looks confusing is hard to use. HTML/CSS makes your software readable and usable.",
        "mental_model": ["HTML tag = page object", "Class = reusable style name", "Flex/Grid = layout system", "Padding = inside space", "Margin = outside space", "Media query = screen-size rule"],
        "common_mistakes": ["Styling the wrong class name.", "Forgetting the dot before a CSS class selector.", "Using fixed widths that break on small screens.", "Not checking the page at multiple screen sizes."],
        "reflection": ["What is the difference between margin and padding?", "Why use a class instead of styling every element separately?", "What makes a layout responsive?"],
    },
    "Python": {
        "plain_definition": "Python lets you give the computer step-by-step instructions. It is useful for automation, data, web backends, scripts, and tools.",
        "analogy": "A Python script is like a recipe. Variables are ingredients, functions are reusable recipe steps, and running the file is like cooking the recipe.",
        "why_it_matters": "Python is one of the best languages for building practical tools quickly, especially for IT automation and AI/data projects.",
        "mental_model": ["Variable = named value", "Function = reusable action", "List = ordered group of values", "Dictionary = labeled group of values", "File I/O = reading or writing files"],
        "common_mistakes": ["Not saving the file before running it.", "Running the command from the wrong folder.", "Misspelling variable names.", "Confusing strings and numbers."],
        "reflection": ["What is a variable?", "Why would you use a function?", "What does the terminal output prove?"],
    },
    "Active Directory": {
        "plain_definition": "Active Directory organizes users, computers, groups, and permissions in a Windows domain.",
        "analogy": "Think of Active Directory as a company filing system. OUs are folders. Users and computers are files inside the folders. Policies can be applied to folders.",
        "why_it_matters": "IT support uses Active Directory to manage accounts, computers, permissions, and organization structure.",
        "mental_model": ["Domain = managed environment", "OU = organizational folder", "User object = account", "Computer object = managed machine", "Group Policy = rule applied to users/computers"],
        "common_mistakes": ["Confusing groups with OUs.", "Creating an OU but not placing objects inside it.", "Assuming moving an object changes permissions automatically.", "Not documenting the OU path."],
        "reflection": ["What is an OU for?", "How is an OU different from a group?", "Why would IT organize computers into OUs?"],
    },
    "Troubleshooting": {
        "plain_definition": "Troubleshooting means finding what is wrong, proving it with evidence, testing a fix, and documenting the result.",
        "analogy": "It is like being a detective. You do not guess first. You collect clues, test theories, and write down what solved the case.",
        "why_it_matters": "Good IT work depends on evidence. You need to know what happened, why it happened, and how to prevent it from happening again.",
        "mental_model": ["Symptom = what user sees", "Evidence = proof from logs/screenshots", "Hypothesis = possible cause", "Test = action to confirm/deny", "Resolution = verified fix"],
        "common_mistakes": ["Guessing before collecting evidence.", "Changing multiple things at once.", "Not writing down what fixed the issue.", "Ignoring screenshots or logs."],
        "reflection": ["What evidence did you collect?", "What was the likely cause?", "How would you explain the issue to a non-technical person?"],
    },
    "Testing": {
        "plain_definition": "Testing proves that code still works after changes. A test is a small automatic check with an expected result.",
        "analogy": "A test is like checking if a light switch still turns on the light after you repair wiring.",
        "why_it_matters": "As projects grow, tests help you avoid breaking old features when adding new ones.",
        "mental_model": ["Test file = place for checks", "Assert = expected truth", "Pass = behavior matched expectation", "Fail = behavior changed or bug exists", "Smoke test = quick basic check"],
        "common_mistakes": ["Testing too much at once.", "Writing a test that does not actually assert anything.", "Not running tests after changing code.", "Ignoring failing tests instead of reading the error."],
        "reflection": ["What did your test prove?", "What would make it fail?", "Why is a small test better than no test?"],
    },
}


def _teaching_pack(skill: str, title: str) -> Dict[str, Any]:
    family = _skill_family(skill, title)
    return SKILL_TEACHING.get(family, {
        "plain_definition": f"{family} is the main concept this quest is helping you practice.",
        "analogy": "Think of this quest like a small training drill. You are not trying to master everything at once. You are proving one small ability with visible evidence.",
        "why_it_matters": "Small proof builds confidence. It also gives KDT OS evidence that you understand the concept instead of only reading about it.",
        "mental_model": ["Concept = what you are learning", "Action = what you build or do", "Proof = visible evidence", "Reflection = explanation in your own words"],
        "common_mistakes": ["Trying to do too much at once.", "Skipping proof.", "Copying without explaining what happened.", "Not saving files before testing."],
        "reflection": ["What did this quest prove?", "What part still feels confusing?", "How would you explain this to someone new?"],
    })


def _step_objects(quest: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_steps = _as_list(quest.get("steps"))
    if not raw_steps:
        raw_steps = _as_list(quest.get("requirements"))
    if not raw_steps:
        raw_steps = [quest.get("what_to_build") or quest.get("goal") or "Complete the smallest visible proof for this quest."]
    objects = []
    for i, step in enumerate(raw_steps, 1):
        title = step.strip()
        if len(title) > 90:
            title = title[:87].rstrip() + "..."
        objects.append({
            "number": i,
            "title": title,
            "instruction": step,
            "why": _why_for_step(step),
            "expected_result": _expected_for_step(step),
            "proof_hint": _proof_for_step(step),
            "beginner_tip": _tip_for_step(step),
        })
    return objects


def _why_for_step(step: str) -> str:
    s = step.lower()
    if "folder" in s:
        return "The folder keeps all files for this quest together so you do not lose track of what belongs to this project."
    if "file" in s or ".py" in s or ".html" in s or ".js" in s or ".css" in s:
        return "The file gives your project a place to store the code or notes for this part of the quest."
    if "run" in s or "python" in s:
        return "Running the file proves that the computer can execute your work, not just that the code exists."
    if "screenshot" in s or "proof" in s or "upload" in s:
        return "Proof gives KDT OS evidence that the quest was completed and gives you something to review later."
    if "table" in s or "database" in s or "sqlite" in s:
        return "This creates the storage structure that lets your app remember information."
    if "button" in s or "click" in s or "addEventListener" in s:
        return "This proves the page can react to a user action instead of just sitting still."
    if "route" in s or "flask" in s:
        return "This creates a browser-accessible path that connects a URL to Python code."
    if "readme" in s:
        return "A README forces you to explain how the project works, which builds understanding and makes the project reusable."
    return "This step is a small piece of the final proof. Completing it reduces the quest into something manageable."


def _expected_for_step(step: str) -> str:
    s = step.lower()
    if "folder" in s:
        return "You should see a new folder with the requested name."
    if "create" in s and "file" in s:
        return "You should see the new file inside your project folder."
    if "run" in s:
        return "You should see terminal output, a created file, or no errors."
    if "screenshot" in s:
        return "You should have an image that clearly shows the completed work."
    if "readme" in s:
        return "README.md should explain what you built, how to run it, and what it proves."
    if "table" in s:
        return "The table should exist and contain the columns the quest asked for."
    return "You should be able to point to a visible result or explain what changed."


def _proof_for_step(step: str) -> str:
    s = step.lower()
    if "run" in s or "terminal" in s:
        return "Copy the terminal output or take a screenshot."
    if "file" in s or ".py" in s or ".html" in s or ".js" in s:
        return "Keep the file in your project folder and include it in your uploaded proof."
    if "database" in s or "table" in s:
        return "Screenshot the database/table or include the database file if the quest asks for it."
    if "explain" in s or "write" in s:
        return "Write the answer in README.md or in your submission reflection."
    return "Take a screenshot or write one sentence explaining how you know this step is complete."


def _tip_for_step(step: str) -> str:
    s = step.lower()
    if "terminal" in s or "run" in s:
        return "Make sure your terminal is opened inside the project folder before running commands."
    if "id" in s and ("html" in s or "button" in s or "input" in s):
        return "IDs must match exactly between HTML and JavaScript. One misspelled letter can break the feature."
    if "sqlite" in s or "database" in s:
        return "After changing data, remember that many database actions require saving/committing before the change is permanent."
    if "route" in s:
        return "If the browser says Not Found, check that the URL matches the route exactly."
    return "Do this step slowly. The goal is understanding, not speed."


def _beginner_score(quest: Dict[str, Any]) -> int:
    score = 0
    score += 20 if quest.get("goal") else 0
    score += 20 if quest.get("what_to_build") else 0
    score += 20 if len(_as_list(quest.get("steps"))) >= 3 else 0
    score += 15 if _as_list(quest.get("proof")) or _as_list(quest.get("proof_required")) else 0
    score += 15 if _as_list(quest.get("success_criteria")) else 0
    score += 10 if quest.get("estimated_time") else 0
    return min(score, 100)


def build_tutor_guide(quest: Dict[str, Any]) -> Dict[str, Any]:
    skill = quest.get("skill", "General")
    title = quest.get("title", "Untitled Quest")
    family = _skill_family(skill, title)
    teaching = _teaching_pack(skill, title)
    proof = _as_list(quest.get("proof")) or _as_list(quest.get("proof_required")) or ["Upload the files/screenshots that prove the expected result worked."]
    success = _as_list(quest.get("success_criteria")) or ["You can show visible proof that the quest goal was completed.", "You can explain what you did in your own words."]
    guide = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "quest_title": title,
        "filename": quest.get("filename", ""),
        "skill": skill,
        "skill_family": family,
        "difficulty": quest.get("difficulty", "Beginner"),
        "estimated_time": quest.get("estimated_time", "15-45 minutes"),
        "beginner_readiness": _beginner_score(quest),
        "objective": quest.get("goal") or quest.get("what_to_build") or f"Complete a small proof for {skill}.",
        "what_to_build": quest.get("what_to_build") or quest.get("goal") or "A small visible proof artifact.",
        "why_this_matters": teaching["why_it_matters"],
        "plain_definition": teaching["plain_definition"],
        "real_world_analogy": teaching["analogy"],
        "mental_model": teaching["mental_model"],
        "steps": _step_objects(quest),
        "common_mistakes": teaching["common_mistakes"],
        "success_criteria": success,
        "proof_required": proof,
        "reflection_questions": teaching["reflection"],
        "study_rule": "Do not only copy the step. Before marking the quest complete, explain what the step did in your own words.",
    }
    return guide


def tutor_snapshot(kdt: Any) -> Dict[str, Any]:
    quests = _load_quests(kdt)
    guides = [build_tutor_guide(q) for q in quests]
    families: Dict[str, int] = {}
    for g in guides:
        families[g["skill_family"]] = families.get(g["skill_family"], 0) + 1
    weakest = sorted(guides, key=lambda g: g["beginner_readiness"])
    recommended = weakest[0] if weakest else None
    report = {
        "version": "V40",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "quest_count": len(quests),
        "guide_count": len(guides),
        "skill_families": families,
        "average_beginner_readiness": round(sum(g["beginner_readiness"] for g in guides) / len(guides), 1) if guides else 0,
        "recommended_tutor_guide": recommended,
        "guides": guides[:12],
        "rule": "Every quest should teach what to do, why it matters, how to verify it, and how to explain it back.",
    }
    reports = Path(getattr(kdt, "REPORT_DIR", Path(kdt.APP_ROOT) / "reports"))
    save_json(reports / "tutor_guides.json", report)
    return report


def install(kdt: Any) -> None:
    app = kdt.app

    def tutor_engine():
        snapshot = tutor_snapshot(kdt)
        return kdt.render_template("tutor_engine.html", snapshot=snapshot)

    def tutor_engine_json():
        return kdt.jsonify(tutor_snapshot(kdt))

    def tutor_quest(filename: str):
        quest_path = Path(getattr(kdt, "QUEST_DIR", Path(kdt.APP_ROOT) / "quests")) / filename
        quest = load_json(quest_path, {}) or {}
        if not quest:
            kdt.flash("Quest not found.")
            return kdt.redirect(kdt.url_for("tutor_engine"))
        quest["filename"] = filename
        guide = build_tutor_guide(quest)
        return kdt.render_template("tutor_quest.html", guide=guide, quest=quest)

    def tutor_quest_json(filename: str):
        quest_path = Path(getattr(kdt, "QUEST_DIR", Path(kdt.APP_ROOT) / "quests")) / filename
        quest = load_json(quest_path, {}) or {}
        quest["filename"] = filename
        return kdt.jsonify(build_tutor_guide(quest))

    app.add_url_rule("/tutor_engine", "tutor_engine", tutor_engine, methods=["GET"])
    app.add_url_rule("/tutor_engine.json", "tutor_engine_json", tutor_engine_json, methods=["GET"])
    app.add_url_rule("/tutor_engine/<path:filename>", "tutor_quest", tutor_quest, methods=["GET"])
    app.add_url_rule("/tutor_engine/<path:filename>.json", "tutor_quest_json", tutor_quest_json, methods=["GET"])

    kdt.tutor_snapshot_v40 = lambda: tutor_snapshot(kdt)
    kdt.build_tutor_guide_v40 = build_tutor_guide
