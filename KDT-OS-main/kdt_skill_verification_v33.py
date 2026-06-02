"""KDT OS Skill Verification Engine V33

V33 turns learning estimates into proof-backed verification.
It creates exact skill-check challenges and tracks estimated vs verified skill strength.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def _read_json(path: Path, default: Any):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _slug(text: str) -> str:
    text = (text or "skill").lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text[:80] or "skill"


def _quest_files(root: Path) -> List[Path]:
    qdir = root / "quests"
    return sorted(qdir.glob("*.json")) if qdir.exists() else []


def _submission_files(root: Path) -> List[Path]:
    sdir = root / "quest_submissions"
    return sorted(sdir.glob("*.json")) if sdir.exists() else []


def _load_quests(root: Path) -> List[Dict[str, Any]]:
    rows = []
    for p in _quest_files(root):
        q = _read_json(p, {})
        if isinstance(q, dict):
            q["filename"] = p.name
            rows.append(q)
    return rows


def _score_from_quest(q: Dict[str, Any]) -> int:
    for key in ("quest_quality", "governance_score", "score"):
        val = q.get(key)
        if isinstance(val, dict):
            val = val.get("score") or val.get("overall")
        try:
            if val is not None:
                return max(0, min(100, int(float(val))))
        except Exception:
            pass
    txt = " ".join(str(q.get(k, "")) for k in ["title", "what_to_build", "goal"])
    base = 50
    if q.get("requirements"): base += 10
    if q.get("steps"): base += 10
    if q.get("success_criteria"): base += 10
    if q.get("proof") or q.get("proof_required"): base += 10
    if "one artifact that proves" in txt.lower(): base -= 20
    return max(0, min(100, base))


def _is_verified(q: Dict[str, Any]) -> bool:
    status = str(q.get("status", "")).lower()
    if status in {"completed", "verified", "approved", "done"}:
        return True
    submissions = q.get("submissions") or []
    if isinstance(submissions, list):
        for s in submissions:
            if isinstance(s, dict) and str(s.get("status", "")).lower() in {"completed", "verified", "approved"}:
                return True
    return False


def _skill_name(q: Dict[str, Any]) -> str:
    skill = str(q.get("skill") or q.get("category") or q.get("topic") or "General").strip()
    if skill.lower().startswith("i don't understand"):
        skill = skill.replace("I don't understand", "").replace(".", "").strip() or "General"
    return skill[:60]


def _verification_template(skill: str) -> Dict[str, Any]:
    key = skill.lower()
    templates = {
        "python": {
            "title": "Python Function Verification: List Average",
            "what_to_build": "Create verify_python_average.py with a function named average_numbers(numbers) that returns the average of a list.",
            "requirements": ["Create verify_python_average.py", "Define average_numbers(numbers)", "Return the average", "Print the result of [10, 20, 30]", "Do not hardcode the answer only"],
            "success_criteria": ["Function exists", "Uses sum() and len() or equivalent logic", "Running the file prints 20", "Code can be reviewed"],
            "proof": ["Upload verify_python_average.py", "Include a screenshot or copied terminal output", "Answer: why does the function return 20?"],
            "steps": ["Create verify_python_average.py", "Write def average_numbers(numbers):", "Return sum(numbers) / len(numbers)", "Print average_numbers([10, 20, 30])", "Run python verify_python_average.py", "Capture proof"],
        },
        "sqlite": {
            "title": "SQLite Verification: Create Insert Select",
            "what_to_build": "Create a small SQLite proof with a table, one insert, and one select query.",
            "requirements": ["Create verify_sqlite.py", "Create a database file", "Create table skills", "Insert one row", "Select and print the row"],
            "success_criteria": ["Database file is created", "CREATE TABLE appears", "INSERT appears", "SELECT appears", "Terminal output shows the saved row"],
            "proof": ["Upload verify_sqlite.py", "Upload the database file or screenshot", "Answer: what is one row and one column in your table?"],
            "steps": ["Create verify_sqlite.py", "Import sqlite3", "Connect to verify_skills.db", "Create table skills", "Insert one skill row", "Select rows and print them", "Run the file", "Capture proof"],
        },
        "flask": {
            "title": "Flask Verification: One JSON Route",
            "what_to_build": "Create a Flask app with /verify that returns JSON containing status: ok and skill: Flask.",
            "requirements": ["Create verify_flask.py", "Import Flask and jsonify", "Create /verify route", "Return JSON", "Run the app and open the route"],
            "success_criteria": ["/verify loads", "Browser shows JSON", "JSON contains status and skill", "Code can be reviewed"],
            "proof": ["Upload verify_flask.py", "Screenshot /verify in browser", "Answer: what does the route return?"],
            "steps": ["Create verify_flask.py", "Create app = Flask(__name__)", "Add @app.route('/verify')", "Return jsonify({'status':'ok','skill':'Flask'})", "Run python verify_flask.py", "Open /verify", "Capture proof"],
        },
        "javascript": {
            "title": "JavaScript Verification: Button and Fetch Shape",
            "what_to_build": "Create a browser page where a button displays a fake API result object on screen.",
            "requirements": ["Create index.html", "Create script.js", "Add a button", "Use addEventListener", "Create a sample object", "Display object values in the page"],
            "success_criteria": ["Button works", "addEventListener is used", "Object data appears on click", "Code is understandable"],
            "proof": ["Upload ZIP", "Screenshot after clicking", "Answer: what line updates the page?"],
            "steps": ["Create folder js_verify", "Create index.html and script.js", "Add button id loadBtn", "Add div id result", "In script.js add click listener", "Create const data = {city:'Chicago', temp:72}", "Show data in result", "Capture proof"],
        },
        "api": {
            "title": "API Verification: Fetch and Display JSON",
            "what_to_build": "Create a page that fetches sample JSON and displays one value from it.",
            "requirements": ["Create index.html", "Create script.js", "Use fetch", "Parse JSON", "Display one value", "Handle an error"],
            "success_criteria": ["fetch appears in code", "JSON value displays", "Error message exists", "Proof shows the page working"],
            "proof": ["Upload ZIP", "Screenshot of displayed JSON value", "Answer: what does fetch return before .json()?"],
            "steps": ["Create files", "Use fetch('https://jsonplaceholder.typicode.com/todos/1')", "Call response.json()", "Display title", "Add catch error", "Capture proof"],
        },
    }
    selected = None
    for token, tmpl in templates.items():
        if token in key:
            selected = tmpl
            break
    if selected is None:
        selected = {
            "title": f"{skill} Verification: Single Proof Challenge",
            "what_to_build": f"Create one small artifact that proves you can use {skill} without step-by-step help.",
            "requirements": ["Create a clearly named proof folder", "Create README.md", f"Create one artifact using {skill}", "Explain what you made", "Explain what it proves"],
            "success_criteria": ["Proof folder exists", "README explains the skill", "Artifact is specific", "The proof can be reviewed"],
            "proof": ["Upload ZIP or screenshot", "Answer: what did this prove you can do?"],
            "steps": ["Create the proof folder", "Create README.md", f"Build one tiny proof using {skill}", "Run/open it if possible", "Write what it proves", "Upload proof"],
        }
    return selected


def _build_verification_quest(skill: str, root: Path) -> str:
    tmpl = _verification_template(skill)
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"skill_verification_{_slug(skill)}_{now}.json"
    data = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_project": "KDT OS Skill Verification V33",
        "resume_project": "Learning Intelligence",
        "skill": skill,
        "quest_type": "Skill Verification",
        "type": "Skill Verification Quest",
        "difficulty": "Verification",
        "estimated_time": "20-45 minutes",
        "status": "Assigned",
        "title": tmpl["title"],
        "goal": f"Verify that Kewonte can use {skill} through proof, not assumptions.",
        "what_to_build": tmpl["what_to_build"],
        "requirements": tmpl["requirements"],
        "steps": tmpl["steps"],
        "success_criteria": tmpl["success_criteria"],
        "proof": tmpl["proof"],
        "proof_required": True,
        "understanding_check": True,
        "quest_quality": 96,
        "governance": {"score": 96, "status": "approved", "reason": "V33 verification quest has exact build, proof, steps, and understanding check."},
        "verification": {"engine": "V33 Skill Verification", "skill": skill, "estimated_score_before": None, "verified_after_submission": False},
    }
    _write_json(root / "quests" / filename, data)
    return filename


def skill_verification_snapshot(kdt: Any) -> Dict[str, Any]:
    root = Path(kdt.APP_ROOT)
    quests = _load_quests(root)
    skill_map: Dict[str, Dict[str, Any]] = {}
    for q in quests:
        skill = _skill_name(q)
        rec = skill_map.setdefault(skill, {"skill": skill, "quests": [], "estimated_total": 0, "verified_count": 0, "verification_quests": 0})
        score = _score_from_quest(q)
        rec["quests"].append({"title": q.get("title", q.get("filename")), "filename": q.get("filename"), "score": score, "verified": _is_verified(q), "type": q.get("quest_type") or q.get("type")})
        rec["estimated_total"] += score
        if _is_verified(q):
            rec["verified_count"] += 1
        if "verification" in str(q.get("quest_type", "")).lower() or "verification" in str(q.get("type", "")).lower():
            rec["verification_quests"] += 1
    skills = []
    for rec in skill_map.values():
        count = len(rec["quests"])
        estimated = round(rec["estimated_total"] / count) if count else 0
        verified_score = min(100, rec["verified_count"] * 25 + rec["verification_quests"] * 10)
        gap = max(0, estimated - verified_score)
        rec.update({"estimated_score": estimated, "verified_score": verified_score, "verification_gap": gap})
        rec["status"] = "Verified" if verified_score >= 70 else ("Needs proof" if gap >= 30 else "Developing")
        rec["recommended_challenge"] = _verification_template(rec["skill"])["title"]
        skills.append(rec)
    skills.sort(key=lambda x: (x["verification_gap"], x["estimated_score"]), reverse=True)
    primary = skills[0] if skills else {"skill": "Python", "estimated_score": 0, "verified_score": 0, "verification_gap": 0, "recommended_challenge": "Python Function Verification"}
    strong = [s for s in skills if s["verified_score"] >= 70]
    needs = [s for s in skills if s["verification_gap"] >= 30]
    return {
        "version": "V33",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "total_skills": len(skills),
        "estimated_only": len([s for s in skills if s["estimated_score"] > 0 and s["verified_score"] == 0]),
        "verified_skills": len(strong),
        "needs_verification": len(needs),
        "primary_gap": primary,
        "skills": skills[:24],
        "strong_skills": strong[:8],
        "rule": "V33 separates estimated skill strength from proof-backed verification. A skill is not truly verified until KDT OS has reviewable proof.",
    }


def install(kdt: Any) -> None:
    app = kdt.app

    def skill_verification():
        return kdt.render_template("skill_verification.html", data=skill_verification_snapshot(kdt))

    def skill_verification_json():
        return kdt.jsonify(skill_verification_snapshot(kdt))

    def create_skill_verification(skill: str):
        filename = _build_verification_quest(skill, Path(kdt.APP_ROOT))
        try:
            kdt.flash(f"Created verification quest for {skill}.")
            return kdt.redirect(kdt.url_for("view_quest", filename=filename))
        except Exception:
            return kdt.redirect(kdt.url_for("skill_verification"))

    app.add_url_rule("/skill_verification", "skill_verification", skill_verification, methods=["GET"])
    app.add_url_rule("/skill_verification.json", "skill_verification_json", skill_verification_json, methods=["GET"])
    app.add_url_rule("/skill_verification/create/<path:skill>", "create_skill_verification", create_skill_verification, methods=["POST"])

    kdt.skill_verification_snapshot_v33 = lambda: skill_verification_snapshot(kdt)
