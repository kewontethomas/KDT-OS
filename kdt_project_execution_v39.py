"""KDT OS Project Execution Coach V39

V39 turns Project Coach recommendations into executable build plans.
It answers: how do I build the recommended project, what step comes next,
and what proof is required for each step?
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _slug(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "_", str(text or "project").strip()).strip("_")
    return text.lower()[:80] or "project"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _execution_file(root: Path) -> Path:
    return root / "reports" / "project_execution.json"


def _progress_file(root: Path) -> Path:
    return root / "reports" / "project_progress.json"


def _load_execution_state(root: Path) -> Dict[str, Any]:
    data = _read_json(_execution_file(root), {})
    if not isinstance(data, dict):
        data = {}
    data.setdefault("version", "V39")
    data.setdefault("created_at", _now())
    data.setdefault("active_projects", {})
    data.setdefault("history", [])
    return data


def _save_execution_state(root: Path, state: Dict[str, Any]) -> None:
    state["updated_at"] = _now()
    _write_json(_execution_file(root), state)


def _project_recommendations(root: Path) -> List[Dict[str, Any]]:
    report = _read_json(root / "reports" / "project_recommendations.json", {})
    if isinstance(report, dict):
        projects = report.get("recommended_projects") or report.get("all_projects") or []
        if isinstance(projects, list) and projects:
            return [p for p in projects if isinstance(p, dict)]
    # Last-resort starter recommendations if the V38 report has not been opened yet.
    return [
        {"name": "Workout Database App", "difficulty": "Beginner", "time": "2-4 hours", "skills": ["SQLite", "Python", "CRUD"], "why": "Practice SQLite CRUD with a useful personal project.", "first_step": "Create a project folder and write down the fields for a workout record.", "proof": "Upload code and screenshots showing create, list, update, and delete."},
        {"name": "API Weather Lookup App", "difficulty": "Beginner", "time": "2-4 hours", "skills": ["JavaScript", "API / Routes", "HTML/CSS"], "why": "Practice fetching and displaying API-style data in the browser.", "first_step": "Create index.html, style.css, and script.js.", "proof": "Upload a screenshot showing weather data displayed after a button click."},
        {"name": "Flask Route Smoke Test Suite", "difficulty": "Beginner", "time": "1-2 hours", "skills": ["Flask", "Testing", "Python"], "why": "Protect KDT OS from route breakage as it grows.", "first_step": "Create tests/test_routes.py and check the home route returns 200.", "proof": "Upload pytest output and the test file."},
    ]


def _base_steps(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    name = str(project.get("name", "Project"))
    skills = [str(s) for s in project.get("skills", [])]
    skill_text = ", ".join(skills[:4]) or "the target skill"
    lower = name.lower()

    if "workout database" in lower or "sqlite" in skill_text.lower():
        raw = [
            ("Create project folder", "Create a folder named workout_database_app with README.md and app.py.", "Folder exists with README.md and app.py.", "Screenshot or ZIP showing the folder."),
            ("Design the workout record", "Write the fields you will store: exercise, sets, reps, date, and notes.", "README.md lists the fields and explains each one.", "README.md included in ZIP."),
            ("Create the database/table", "Use SQLite or a JSON starter file to create storage for workout records.", "Storage file exists and has a workouts structure/table.", "Screenshot or code showing the table/structure."),
            ("Add create behavior", "Add one function or form action that saves a workout record.", "At least one workout can be added.", "Code plus screenshot/output showing the added workout."),
            ("Add list behavior", "Display all saved workout records.", "Saved workouts appear in terminal/browser/output.", "Screenshot of listed workouts."),
            ("Add update behavior", "Change one saved workout record.", "An existing workout can be edited.", "Before/after screenshot or terminal output."),
            ("Add delete behavior", "Remove one workout record.", "A workout can be deleted and no longer appears.", "Screenshot or output proving deletion."),
            ("Submit final proof", "Zip the folder and write what this project proved about SQLite/CRUD.", "ZIP and explanation are ready.", "Upload ZIP and 3-5 sentence reflection."),
        ]
    elif "weather" in lower or "api" in lower:
        raw = [
            ("Create browser files", "Create index.html, style.css, and script.js in one project folder.", "All three files exist.", "Screenshot or ZIP showing the files."),
            ("Build the page structure", "Add a title, button, and result box to index.html.", "Button and result box are visible.", "Screenshot of the page."),
            ("Connect JavaScript", "Link script.js and select the button/result elements.", "Console has no missing-file errors.", "Code snippet or screenshot."),
            ("Add click event", "Use addEventListener so the button changes the result text.", "Clicking the button changes text.", "Screenshot before and after click."),
            ("Load sample weather data", "Create a sample weather object or fetch sample JSON and display city, temperature, and condition.", "The three weather fields display on the page.", "Screenshot showing displayed data."),
            ("Style the card", "Make the result box readable and clean on desktop and narrow width.", "Page is readable at normal and narrow sizes.", "Two screenshots: desktop and narrow."),
            ("Write explanation", "In README.md, explain what fetch/API-style data means and what your button does.", "README answers both questions.", "README included."),
            ("Submit final proof", "Zip the project and include screenshots.", "ZIP is ready with files and proof.", "Upload ZIP and reflection."),
        ]
    elif "flask" in lower or "route" in lower:
        raw = [
            ("Create test folder", "Create a tests folder and a test_routes.py file.", "tests/test_routes.py exists.", "Screenshot or ZIP."),
            ("Identify routes", "Write down 3 important routes that should return successfully.", "README or test file lists the routes.", "README or screenshot."),
            ("Create first smoke test", "Write one test that checks the home page returns status code 200.", "One passing test exists.", "test_routes.py."),
            ("Add second route test", "Add a second route test for a key page like /command_center or /project_coach.", "Two tests exist.", "test_routes.py."),
            ("Run pytest", "Run python -m pytest or document the exact command you would use.", "Terminal shows test result or README explains blocker.", "Screenshot or copied output."),
            ("Record failures", "If any route fails, write the route and error in README.md.", "Failures are documented or marked none.", "README.md."),
            ("Add proof summary", "Write what smoke tests protect against.", "README explains route breakage prevention.", "README.md."),
            ("Submit final proof", "Zip tests and README.", "ZIP is ready.", "Upload ZIP and reflection."),
        ]
    elif "ticket" in lower:
        raw = [
            ("Define ticket fields", "Write fields: title, device, issue type, priority, status, resolution notes.", "README lists ticket fields.", "README.md."),
            ("Create project folder", "Create ticket_tracker with app.py or index.html.", "Folder and starter files exist.", "ZIP/screenshot."),
            ("Build create form", "Create a form for a new help desk ticket.", "Form has required fields.", "Screenshot."),
            ("Save ticket data", "Save one sample ticket to JSON, SQLite, or localStorage.", "Sample ticket persists after refresh/restart.", "Screenshot or code."),
            ("List tickets", "Show saved tickets in a table or cards.", "At least one ticket displays.", "Screenshot."),
            ("Update ticket status", "Change ticket status from Open to In Progress or Resolved.", "Status update is visible.", "Before/after proof."),
            ("Add resolution notes", "Add notes explaining the fix or next step.", "Resolution notes save with ticket.", "Screenshot/code."),
            ("Submit final proof", "Zip the project and explain the workflow.", "ZIP and reflection are ready.", "Upload ZIP and reflection."),
        ]
    else:
        raw = [
            ("Create project folder", f"Create a folder named {_slug(name)} with README.md and starter files.", "Folder exists with README.md.", "Screenshot or ZIP."),
            ("Write project purpose", f"In README.md, explain what {name} does and which skills it trains: {skill_text}.", "README explains purpose and skills.", "README.md."),
            ("Build the smallest working version", str(project.get("first_step") or "Complete the first tiny working feature."), "A small feature works visibly.", "Screenshot, terminal output, or code."),
            ("Add one real input", "Let the user enter or change at least one piece of data.", "Input changes the output or saved data.", "Screenshot/code."),
            ("Save or display result", "Show the result clearly or save it to a file/database/localStorage.", "Result is visible or persistent.", "Screenshot or saved file."),
            ("Clean the UI/output", "Make the output readable and label the important values.", "Output is easy to understand.", "Screenshot."),
            ("Write proof summary", "Write 3-5 sentences explaining what worked and what skill improved.", "Reflection is specific.", "README or submission text."),
            ("Submit final proof", "Zip the project and include proof artifacts.", "ZIP is ready.", "Upload ZIP and reflection."),
        ]

    return [
        {"index": i + 1, "title": title, "instructions": instructions, "expected_output": expected, "proof_required": proof, "status": "incomplete"}
        for i, (title, instructions, expected, proof) in enumerate(raw)
    ]


def _plan_from_project(project: Dict[str, Any]) -> Dict[str, Any]:
    name = str(project.get("name", "Untitled Project"))
    steps = _base_steps(project)
    return {
        "project_id": _slug(name),
        "name": name,
        "source": "Project Coach V38",
        "difficulty": project.get("difficulty", "Beginner"),
        "estimated_time": project.get("time", project.get("estimated_time", "2-4 hours")),
        "skills": project.get("skills", []),
        "why": project.get("why", "This project builds useful skills through proof."),
        "first_step": project.get("first_step", steps[0]["instructions"] if steps else "Start the first step."),
        "proof": project.get("proof", "Upload ZIP, screenshot, and short reflection."),
        "score": int(project.get("score", 0) or 0),
        "steps": steps,
        "created_at": _now(),
        "status": "recommended",
    }


def _active_plan_map(root: Path) -> Dict[str, Any]:
    state = _load_execution_state(root)
    active = state.get("active_projects", {})
    return active if isinstance(active, dict) else {}


def _progress_for(plan: Dict[str, Any], active: Dict[str, Any]) -> Dict[str, Any]:
    project_id = plan.get("project_id")
    saved = active.get(project_id, {}) if isinstance(active, dict) else {}
    saved_steps = saved.get("steps", []) if isinstance(saved, dict) else []
    completed_indices = set()
    for s in saved_steps:
        if isinstance(s, dict) and s.get("status") == "complete":
            completed_indices.add(int(s.get("index", 0)))
    steps = []
    for step in plan.get("steps", []):
        step = dict(step)
        if int(step.get("index", 0)) in completed_indices:
            step["status"] = "complete"
        steps.append(step)
    total = len(steps)
    complete = sum(1 for s in steps if s.get("status") == "complete")
    percent = round((complete / total) * 100) if total else 0
    next_step = next((s for s in steps if s.get("status") != "complete"), None)
    return {"steps": steps, "total": total, "complete": complete, "percent": percent, "next_step": next_step, "started": bool(saved)}


def _all_execution_plans(root: Path, limit: int = 12) -> List[Dict[str, Any]]:
    recommendations = _project_recommendations(root)
    return [_plan_from_project(p) for p in recommendations[:limit]]


def _enriched_plans(root: Path, limit: int = 12) -> List[Dict[str, Any]]:
    active = _active_plan_map(root)
    enriched = []
    for plan in _all_execution_plans(root, limit=limit):
        progress = _progress_for(plan, active)
        # Keep the dashboard light. The full step list is only displayed on the detail page.
        next_step = progress.get("next_step")
        enriched.append({
            **plan,
            "progress": {
                "total": progress.get("total", 0),
                "complete": progress.get("complete", 0),
                "percent": progress.get("percent", 0),
                "started": progress.get("started", False),
                "next_step": next_step,
            },
        })
    return enriched


def project_execution_snapshot(kdt: Any) -> Dict[str, Any]:
    root = Path(kdt.APP_ROOT)
    enriched = _enriched_plans(root, limit=10)
    active_projects = [p for p in enriched if p["progress"].get("started")]
    completed_projects = [p for p in enriched if p["progress"].get("percent") == 100]
    open_steps = sum(p["progress"].get("total", 0) - p["progress"].get("complete", 0) for p in active_projects)
    avg_progress = round(sum(p["progress"].get("percent", 0) for p in active_projects) / len(active_projects)) if active_projects else 0
    recommended_focus = active_projects[0] if active_projects else (enriched[0] if enriched else None)
    snapshot = {
        "version": "V39.1",
        "created_at": _now(),
        "recommended_focus": recommended_focus,
        "plans": enriched,
        "active_count": len(active_projects),
        "completed_count": len(completed_projects),
        "open_steps": open_steps,
        "average_progress": avg_progress,
        "available_count": len(enriched),
        "rule": "The dashboard shows projects only. Open one project to work through its steps without a giant wall of cards.",
    }
    _write_json(root / "reports" / "project_progress.json", snapshot)
    return snapshot


def project_execution_detail_snapshot(kdt: Any, project_id: str) -> Dict[str, Any]:
    root = Path(kdt.APP_ROOT)
    active = _active_plan_map(root)
    plans = _all_execution_plans(root, limit=20)
    plan = next((p for p in plans if p.get("project_id") == project_id), None)
    if plan is None and project_id in active:
        plan = active.get(project_id)
    if not isinstance(plan, dict):
        return {"found": False, "project_id": project_id, "version": "V39.1"}
    progress = _progress_for(plan, active)
    steps = progress.get("steps", [])
    next_step = progress.get("next_step")
    completed_steps = [s for s in steps if s.get("status") == "complete"]
    upcoming_steps = [s for s in steps if s.get("status") != "complete"]
    return {
        "found": True,
        "version": "V39.1",
        "created_at": _now(),
        "plan": {**plan, "progress": progress},
        "steps": steps,
        "next_step": next_step,
        "completed_steps": completed_steps,
        "upcoming_steps": upcoming_steps,
        "rule": "Work one current step, prove it, then mark it complete.",
    }


def start_project(kdt: Any, project_id: str) -> bool:
    root = Path(kdt.APP_ROOT)
    plans = [_plan_from_project(p) for p in _project_recommendations(root)[:12]]
    plan = next((p for p in plans if p.get("project_id") == project_id), None)
    if not plan:
        return False
    state = _load_execution_state(root)
    active = state.setdefault("active_projects", {})
    if project_id not in active:
        active[project_id] = {**plan, "status": "active", "started_at": _now()}
        state.setdefault("history", []).insert(0, {"at": _now(), "action": "started_project", "project_id": project_id, "project": plan.get("name")})
        _save_execution_state(root, state)
    return True


def toggle_step(kdt: Any, project_id: str, step_index: int) -> bool:
    root = Path(kdt.APP_ROOT)
    state = _load_execution_state(root)
    active = state.setdefault("active_projects", {})
    if project_id not in active:
        if not start_project(kdt, project_id):
            return False
        state = _load_execution_state(root)
        active = state.setdefault("active_projects", {})
    plan = active.get(project_id)
    if not isinstance(plan, dict):
        return False
    steps = plan.get("steps", [])
    changed = False
    for step in steps:
        if isinstance(step, dict) and int(step.get("index", 0)) == int(step_index):
            step["status"] = "incomplete" if step.get("status") == "complete" else "complete"
            step["updated_at"] = _now()
            changed = True
            state.setdefault("history", []).insert(0, {"at": _now(), "action": "toggle_step", "project_id": project_id, "step_index": step_index, "status": step["status"]})
            break
    if changed:
        complete = sum(1 for s in steps if isinstance(s, dict) and s.get("status") == "complete")
        total = len(steps)
        plan["progress_percent"] = round((complete / total) * 100) if total else 0
        plan["status"] = "complete" if plan["progress_percent"] == 100 else "active"
        _save_execution_state(root, state)
    return changed


def install(kdt: Any) -> None:
    app = kdt.app

    def project_execution():
        snapshot = project_execution_snapshot(kdt)
        return kdt.render_template("project_execution.html", snapshot=snapshot)

    def project_execution_json():
        return kdt.jsonify(project_execution_snapshot(kdt))

    def project_execution_detail(project_id: str):
        detail = project_execution_detail_snapshot(kdt, project_id)
        return kdt.render_template("project_execution_detail.html", detail=detail)

    def project_execution_detail_json(project_id: str):
        return kdt.jsonify(project_execution_detail_snapshot(kdt, project_id))

    def start_project_route():
        project_id = kdt.request.form.get("project_id", "")
        start_project(kdt, project_id)
        return kdt.redirect(kdt.url_for("project_execution_detail", project_id=project_id))

    def toggle_project_step_route():
        project_id = kdt.request.form.get("project_id", "")
        try:
            step_index = int(kdt.request.form.get("step_index", "0"))
        except Exception:
            step_index = 0
        toggle_step(kdt, project_id, step_index)
        return kdt.redirect(kdt.url_for("project_execution_detail", project_id=project_id))

    app.add_url_rule("/project_execution", "project_execution", project_execution, methods=["GET"])
    app.add_url_rule("/project_execution.json", "project_execution_json", project_execution_json, methods=["GET"])
    app.add_url_rule("/project_execution/<project_id>", "project_execution_detail", project_execution_detail, methods=["GET"])
    app.add_url_rule("/project_execution/<project_id>.json", "project_execution_detail_json", project_execution_detail_json, methods=["GET"])
    app.add_url_rule("/project_execution/start", "start_project_execution", start_project_route, methods=["POST"])
    app.add_url_rule("/project_execution/toggle_step", "toggle_project_step", toggle_project_step_route, methods=["POST"])

    kdt.project_execution_snapshot_v39 = lambda: project_execution_snapshot(kdt)
    kdt.project_execution_detail_snapshot_v39 = lambda project_id: project_execution_detail_snapshot(kdt, project_id)
