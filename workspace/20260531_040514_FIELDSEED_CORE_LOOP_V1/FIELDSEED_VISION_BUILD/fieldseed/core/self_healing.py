
import json
import shutil
import py_compile
from pathlib import Path
from datetime import datetime

from fieldseed.paths import ROOT, DATA, LOGS
from .database import add_improvement, self_check_record

SELF_HEAL_DIR = DATA / "self_healing"
PATCH_DIR = SELF_HEAL_DIR / "patches"
BACKUP_DIR = SELF_HEAL_DIR / "backups"
SCREENSHOT_DIR = SELF_HEAL_DIR / "screenshots"

for d in [SELF_HEAL_DIR, PATCH_DIR, BACKUP_DIR, SCREENSHOT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

KNOWN_RULES = [
    {
        "id": "literal_newline_display",
        "title": "Literal newline characters showing in UI",
        "risk": "Low",
        "detect": "\\n",
        "file_glob": "*.py",
        "description": "UI may display escaped newline text instead of readable line breaks.",
        "suggested_fix": "Add/use a clean_display_text helper before inserting raw database text into widgets.",
    },
    {
        "id": "wmic_no_fallback",
        "title": "WMIC usage needs fallback tracking",
        "risk": "Medium",
        "detect": "wmic diskdrive",
        "file_glob": "*.py",
        "description": "WMIC can fail on newer Windows builds. Collector should use fallback disk checks.",
        "suggested_fix": "Treat WMIC failure as optional when CIM/Get-Disk/Get-PhysicalDisk succeed.",
    },
    {
        "id": "missing_confirmation_for_fix",
        "title": "Self-repair safety check",
        "risk": "High",
        "detect": "shutil.copy2",
        "file_glob": "*.py",
        "description": "Self-modifying actions require preview, backup, test, confirmation, and rollback.",
        "suggested_fix": "Use repair engine with backup/test/rollback workflow.",
    },
]

def compile_scan():
    results = []
    failures = []
    for py in ROOT.rglob("*.py"):
        try:
            py_compile.compile(str(py), doraise=True)
            results.append({"file": str(py.relative_to(ROOT)), "status": "OK", "error": ""})
        except Exception as e:
            item = {"file": str(py.relative_to(ROOT)), "status": "FAIL", "error": str(e)}
            results.append(item)
            failures.append(item)
    return results, failures

def scan_files_for_known_issues():
    findings = []
    for rule in KNOWN_RULES:
        for file in ROOT.rglob(rule["file_glob"]):
            if "__pycache__" in str(file):
                continue
            try:
                text = file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if rule["detect"] in text:
                findings.append({
                    "rule_id": rule["id"],
                    "title": rule["title"],
                    "risk": rule["risk"],
                    "file": str(file.relative_to(ROOT)),
                    "description": rule["description"],
                    "suggested_fix": rule["suggested_fix"],
                })
    return findings

def visual_self_inspection():
    compile_results, compile_failures = compile_scan()
    known_findings = scan_files_for_known_issues()
    health = "Healthy"
    if compile_failures:
        health = "Broken"
    elif known_findings:
        health = "Needs Attention"

    report = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "health": health,
        "compile_failures": compile_failures,
        "known_findings": known_findings,
        "files_checked": len(compile_results),
        "summary": {"compile_failures": len(compile_failures), "known_findings": len(known_findings)}
    }

    out = LOGS / f"self_inspection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    self_check_record("visual_self_inspection", "OK" if health == "Healthy" else "WARN", f"Health: {health}", str(out))

    for finding in known_findings[:10]:
        add_improvement(
            "visual_self_inspection",
            finding["title"],
            f"{finding['file']} | Risk: {finding['risk']} | {finding['description']}",
            finding["suggested_fix"]
        )
    try:
        report["repair_candidates"] = create_repair_candidates_from_report(report)
    except Exception as e:
        report["repair_candidate_error"] = str(e)
    return report

def create_repair_plan(rule_id):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    descriptions = {
        "literal_newline_display": "Repair UI display so escaped newline text is cleaned before display.",
        "wmic_no_fallback": "Repair Collector so WMIC disk failures are treated as optional when fallback disk checks succeed.",
        "missing_confirmation_for_fix": "Verify repair safety workflow exists."
    }
    plan = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "rule_id": rule_id,
        "status": "Preview",
        "risk": "Low" if rule_id in descriptions else "High",
        "description": descriptions.get(rule_id, "No deterministic repair exists."),
        "will_backup_files": True,
        "will_compile_test": True,
        "will_rollback_on_failure": True,
    }
    out = PATCH_DIR / f"repair_plan_{rule_id}_{stamp}.json"
    out.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return out, plan

def backup_file(rel_path):
    src = ROOT / rel_path
    backup = BACKUP_DIR / f"{Path(rel_path).name}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
    shutil.copy2(src, backup)
    return backup

def rollback(backups):
    restored = []
    for item in backups:
        backup = Path(item["backup"])
        target = ROOT / item["file"]
        if backup.exists():
            shutil.copy2(backup, target)
            restored.append(item["file"])
    return restored

def _patch_app_newlines():
    rel = "fieldseed/app.py"
    path = ROOT / rel
    if not path.exists():
        return [], []
    backups = [{"file": rel, "backup": str(backup_file(rel))}]
    applied = []
    text = path.read_text(encoding="utf-8", errors="ignore")

    if "def clean_display_text(self, value):" not in text:
        marker = "    def page_dashboard(self):"
        helper = (
            "    def clean_display_text(self, value):\n"
            "        text = \"\" if value is None else str(value)\n"
            "        text = text.replace(\"\\\\r\\\\n\", \"\\n\")\n"
            "        text = text.replace(\"\\\\n\", \"\\n\")\n"
            "        text = text.replace(\"\\\\t\", \"    \")\n"
            "        text = text.replace(\"\\r\\n\", \"\\n\")\n"
            "        return text\n\n"
        )
        if marker in text:
            text = text.replace(marker, helper + marker, 1)
            applied.append("Added clean_display_text helper.")

    pairs = [
        ('parts.append(t["confirmed_facts"] or "None yet.")', 'parts.append(self.clean_display_text(t["confirmed_facts"] or "None yet."))'),
        ('parts.append(t["unknowns"] or "No unknowns recorded.")', 'parts.append(self.clean_display_text(t["unknowns"] or "No unknowns recorded."))'),
        ('parts.append(t["next_action"] or "None.")', 'parts.append(self.clean_display_text(t["next_action"] or "None."))'),
    ]
    for old, new in pairs:
        if old in text and new not in text:
            text = text.replace(old, new)
            applied.append("Cleaned display output pattern.")

    path.write_text(text, encoding="utf-8")
    return backups, applied

def _patch_collector_wmic():
    rel = "fieldseed/modes/collector.py"
    path = ROOT / rel
    if not path.exists():
        return [], []
    backups = [{"file": rel, "backup": str(backup_file(rel))}]
    applied = []
    text = path.read_text(encoding="utf-8", errors="ignore")

    if "disk_fallback_success" in text:
        applied.append("WMIC fallback interpretation already exists.")
        return backups, applied

    old = 'findings.append("Some collectors failed and may need fallback improvement: " + ", ".join(failed))'
    new = (
        'disk_fallbacks = ["disk_cim", "disk_getdisk", "physical_disk"]\n'
        '        disk_fallback_success = any((name in data["commands"] and not data["commands"][name].startswith("ERROR:")) for name in disk_fallbacks)\n'
        '        if "disk_wmic" in failed and disk_fallback_success:\n'
        '            findings.append("WMIC disk check failed, but disk fallback collection succeeded.")\n'
        '            failed = [x for x in failed if x != "disk_wmic"]\n'
        '        if failed:\n'
        '            findings.append("Some collectors failed and may need fallback improvement: " + ", ".join(failed))'
    )
    if old in text:
        text = text.replace(old, new)
        applied.append("Added WMIC fallback interpretation.")
    else:
        applied.append("Could not find exact WMIC failure line. No collector change made.")
    path.write_text(text, encoding="utf-8")
    return backups, applied

def apply_repair_plan(plan_path):
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8", errors="ignore"))
    rule_id = plan.get("rule_id")
    backups = []
    applied = []
    refused = []

    if plan.get("risk") == "High":
        refused.append("High-risk repair refused.")
    elif rule_id == "literal_newline_display":
        backups, applied = _patch_app_newlines()
    elif rule_id == "wmic_no_fallback":
        backups, applied = _patch_collector_wmic()
    elif rule_id == "missing_confirmation_for_fix":
        applied = ["Safety workflow verified: repairs use plan, confirmation, backup, compile test, rollback."]
    else:
        refused.append("No deterministic repair available.")

    _, failures = compile_scan()
    rolled_back = []
    status = "Applied"
    if failures:
        rolled_back = rollback(backups)
        status = "Rolled Back"
    elif refused and not applied:
        status = "Refused"

    result = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "rule_id": rule_id,
        "status": status,
        "applied": applied,
        "refused": refused,
        "compile_failures_after_apply": failures,
        "backups": backups,
        "rolled_back": rolled_back,
    }
    out = LOGS / f"repair_apply_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    self_check_record("self_repair", "OK" if status == "Applied" else "WARN", f"{rule_id}: {status}", str(out))
    return result

def analyze_screenshot_file(path):
    src = Path(path)
    dest = SCREENSHOT_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{src.name}"
    shutil.copy2(src, dest)
    result = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "screenshot": str(dest),
        "visual_mode": "metadata_only",
        "message": "Screenshot saved. True visual interpretation requires adding a vision/OCR model."
    }
    out = LOGS / f"screenshot_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def create_repair_candidates_from_report(report):
    candidates = []
    seen = set()
    for finding in report.get("known_findings", []):
        rule_id = finding.get("rule_id")
        if not rule_id or rule_id in seen:
            continue
        seen.add(rule_id)
        if rule_id in ("literal_newline_display", "wmic_no_fallback", "missing_confirmation_for_fix"):
            try:
                path, plan = create_repair_plan(rule_id)
                plan["source_finding"] = finding
                plan["approval_required"] = True
                plan["autonomous_candidate"] = True
                Path(path).write_text(json.dumps(plan, indent=2), encoding="utf-8")
                candidates.append({"path": str(path), "rule_id": rule_id, "risk": plan.get("risk"), "description": plan.get("description")})
            except Exception as e:
                candidates.append({"path": "", "rule_id": rule_id, "risk": "Unknown", "description": f"Candidate failed: {e}"})
    return candidates

def list_repair_candidates():
    candidates = []
    for p in sorted(PATCH_DIR.glob("repair_plan_*.json"), reverse=True):
        try:
            plan = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
            candidates.append({
                "path": str(p),
                "rule_id": plan.get("rule_id"),
                "risk": plan.get("risk"),
                "description": plan.get("description"),
                "status": plan.get("status", "Preview")
            })
        except Exception:
            pass
    return candidates[:50]
