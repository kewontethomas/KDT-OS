"""KDT OS Proof Promotion Engine V34

V34 closes the loop created by V33:
- V33 creates verification quests.
- V34 turns completed/reviewed verification quests into proof-backed skill records.

This module is intentionally conservative. It does not auto-promote everything.
It creates a reviewable ledger and lets KDT OS mark a skill as verified after proof is reviewed.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


VERIFICATION_STATUS = {"verified", "completed", "approved", "done"}


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _json_files(folder: Path) -> List[Path]:
    try:
        return sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception:
        return []


def _slug(text: str) -> str:
    text = (text or "skill").lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text[:90] or "skill"


def _norm_skill(raw: Any) -> str:
    text = str(raw or "General").strip()
    low = text.lower()
    if "active directory" in low or "organizational unit" in low or re.search(r"\bou\b", low):
        return "Active Directory"
    if "cpu" in low or "task manager" in low:
        return "CPU Usage"
    if "weather" in low and "api" in low:
        return "API / Routes"
    if "api" in low or "route" in low:
        return "API / Routes"
    if "sqlite" in low or "database" in low:
        return "SQLite"
    if "javascript" in low or "dom" in low or "fetch" in low:
        return "JavaScript"
    if "html" in low or "css" in low:
        return "HTML/CSS"
    if "flask" in low:
        return "Flask"
    if "python" in low:
        return "Python"
    if "test" in low or "pytest" in low:
        return "Testing"
    return text[:80] or "General"


def _is_verification_quest(q: Dict[str, Any]) -> bool:
    joined = " ".join(str(q.get(k, "")) for k in ["quest_type", "type", "source_project", "title"]).lower()
    return "verification" in joined or "skill verification" in joined


def _quest_status(q: Dict[str, Any]) -> str:
    return str(q.get("status", "Assigned") or "Assigned")


def _is_promoted(q: Dict[str, Any]) -> bool:
    verification = q.get("verification") if isinstance(q.get("verification"), dict) else {}
    return bool(verification.get("verified_after_submission") or q.get("skill_promoted_at") or str(q.get("status", "")).lower() == "verified")


def _load_verification_quests(root: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in _json_files(root / "quests"):
        q = _read_json(path, {})
        if isinstance(q, dict) and _is_verification_quest(q):
            q = dict(q)
            q["filename"] = path.name
            q["skill"] = _norm_skill(q.get("skill") or q.get("title"))
            q["promoted"] = _is_promoted(q)
            status_low = _quest_status(q).lower()
            q["ready_for_promotion"] = q["promoted"] or status_low in VERIFICATION_STATUS or bool(q.get("reviewed_proof"))
            rows.append(q)
    return rows


def _load_skill_library(root: Path) -> Dict[str, Any]:
    path = root / "skill_library" / "skills.json"
    data = _read_json(path, {})
    return data if isinstance(data, dict) else {}


def _save_skill_library(root: Path, data: Dict[str, Any]) -> None:
    _write_json(root / "skill_library" / "skills.json", data)


def _verified_score(entry: Dict[str, Any]) -> int:
    completed = entry.get("completed_quests", []) if isinstance(entry.get("completed_quests"), list) else []
    submissions = entry.get("submissions", []) if isinstance(entry.get("submissions"), list) else []
    score = min(100, len(completed) * 25 + len(submissions) * 8)
    return max(0, min(100, int(score)))


def _status_from_score(score: int, completed_count: int) -> str:
    if score >= 90 and completed_count >= 4:
        return "Mastered"
    if score >= 75 and completed_count >= 3:
        return "Proficient"
    if score >= 50 and completed_count >= 2:
        return "Verified"
    if score >= 20 and completed_count >= 1:
        return "Practiced"
    return "Learning"


def _ledger_path(root: Path) -> Path:
    return root / "reports" / "verified_skill_ledger.json"


def _load_ledger(root: Path) -> List[Dict[str, Any]]:
    data = _read_json(_ledger_path(root), [])
    return data if isinstance(data, list) else []


def _save_ledger(root: Path, rows: List[Dict[str, Any]]) -> None:
    _write_json(_ledger_path(root), rows[:200])


def promote_verification_quest(root: Path, filename: str, note: str = "Manual V34 promotion after proof review.") -> Tuple[bool, str]:
    qpath = root / "quests" / filename
    quest = _read_json(qpath, {})
    if not isinstance(quest, dict) or not quest:
        return False, "Verification quest was not found."
    if not _is_verification_quest(quest):
        return False, "That quest is not a skill verification quest."

    now = datetime.now().isoformat(timespec="seconds")
    skill = _norm_skill(quest.get("skill") or quest.get("title"))
    skill_library = _load_skill_library(root)
    entry = skill_library.setdefault(skill, {
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
        "proof_note": "Skill confidence is based on verified quests/proof, not uploaded projects.",
    })

    event = {
        "at": now,
        "source": "KDT OS V34 Proof Promotion",
        "quest_title": quest.get("title", filename),
        "quest_filename": filename,
        "rule_score": 100,
        "build_verification": 100,
        "understanding_verification": 100,
        "verdict": "Completed",
        "note": note,
    }

    existing_filenames = {str(e.get("quest_filename")) for e in entry.get("submissions", []) if isinstance(e, dict)}
    if filename not in existing_filenames:
        entry.setdefault("submissions", []).append(event)
        entry.setdefault("completed_quests", []).append(event)
    entry["last_verified_at"] = now
    entry["last_seen"] = entry.get("last_seen") or now
    entry["verified_confidence"] = _verified_score(entry)
    entry["status"] = _status_from_score(entry["verified_confidence"], len(entry.get("completed_quests", [])))
    if "Skill Verification" not in entry.setdefault("projects", []):
        entry["projects"].append("Skill Verification")
    entry.setdefault("evidence", []).append({
        "project": "Skill Verification",
        "seen_at": now,
        "source": "V34 proof promotion",
        "score": 100,
        "explanation": f"{skill} was promoted from a completed verification quest.",
        "quest_filename": filename,
    })

    verification = quest.get("verification") if isinstance(quest.get("verification"), dict) else {}
    verification.update({
        "engine": "V34 Proof Promotion",
        "skill": skill,
        "verified_after_submission": True,
        "promoted_at": now,
    })
    quest["verification"] = verification
    quest["status"] = "Verified"
    quest["skill_promoted_at"] = now
    quest["verified_skill_event"] = event
    _write_json(qpath, quest)
    _save_skill_library(root, skill_library)

    ledger = _load_ledger(root)
    if filename not in {str(e.get("quest_filename")) for e in ledger if isinstance(e, dict)}:
        ledger.insert(0, {"at": now, "skill": skill, "quest_filename": filename, "quest_title": quest.get("title", filename), "result": "promoted", "note": note})
        _save_ledger(root, ledger)
    return True, f"Verified {skill} from {quest.get('title', filename)}."


def proof_promotion_snapshot(kdt: Any) -> Dict[str, Any]:
    root = Path(kdt.APP_ROOT)
    quests = _load_verification_quests(root)
    skill_library = _load_skill_library(root)
    ledger = _load_ledger(root)

    pending = [q for q in quests if not q.get("promoted")]
    ready = [q for q in pending if q.get("ready_for_promotion")]
    waiting = [q for q in pending if not q.get("ready_for_promotion")]

    verified_rows = []
    for name, entry in skill_library.items():
        if not isinstance(entry, dict):
            continue
        score = int(entry.get("verified_confidence") or _verified_score(entry))
        if score > 0 or entry.get("last_verified_at"):
            verified_rows.append({"skill": name, "score": score, "status": entry.get("status", _status_from_score(score, len(entry.get('completed_quests', [])))), "last_verified_at": entry.get("last_verified_at"), "completed": len(entry.get("completed_quests", []) if isinstance(entry.get("completed_quests"), list) else [])})
    verified_rows.sort(key=lambda x: (x.get("score", 0), x.get("completed", 0)), reverse=True)

    next_focus = pending[0] if pending else None
    return {
        "version": "V34",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verification_quests": len(quests),
        "pending_reviews": len(pending),
        "ready_to_promote": len(ready),
        "verified_skills": len(verified_rows),
        "pending": pending[:20],
        "ready": ready[:12],
        "waiting": waiting[:12],
        "verified": verified_rows[:16],
        "ledger": ledger[:12],
        "next_focus": next_focus,
        "rule": "V34 closes the verification loop: estimated skill does not become trusted skill until a verification quest is reviewed and promoted into the skill library.",
    }


def install(kdt: Any) -> None:
    app = kdt.app

    def proof_promotion():
        return kdt.render_template("proof_promotion.html", data=proof_promotion_snapshot(kdt))

    def proof_promotion_json():
        return kdt.jsonify(proof_promotion_snapshot(kdt))

    def promote_skill_proof(filename: str):
        ok, msg = promote_verification_quest(Path(kdt.APP_ROOT), filename)
        try:
            kdt.flash(msg)
        except Exception:
            pass
        return kdt.redirect(kdt.url_for("proof_promotion"))

    app.add_url_rule("/proof_promotion", "proof_promotion", proof_promotion, methods=["GET"])
    app.add_url_rule("/proof_promotion.json", "proof_promotion_json", proof_promotion_json, methods=["GET"])
    app.add_url_rule("/proof_promotion/promote/<path:filename>", "promote_skill_proof", promote_skill_proof, methods=["POST"])

    kdt.proof_promotion_snapshot_v34 = lambda: proof_promotion_snapshot(kdt)
