import json
from pathlib import Path
from .database import connect, now
from fieldseed.paths import EVIDENCE

def import_evidence(path):
    p = Path(path)
    package = p / "evidence_package.json" if p.is_dir() else p
    if not package.exists():
        raise FileNotFoundError("No evidence_package.json found.")
    data = json.loads(package.read_text(encoding="utf-8", errors="ignore"))
    hostname = data.get("hostname", "")
    summary = f"{data.get('site','Unknown Site')} | {hostname} | {data.get('issue_type','Unknown')} | {data.get('platform','')}"
    con = connect()
    con.execute("INSERT INTO evidence_packages(created_at, package_path, hostname, summary) VALUES (?, ?, ?, ?)", (now(), str(package.parent), hostname, summary))
    con.commit()
    con.close()
    return summary

def find_packages():
    return list(EVIDENCE.glob("*/evidence_package.json"))
