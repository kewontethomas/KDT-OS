from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TOOLS = ROOT / "tools"
DB = DATA / "fieldseed.db"
EVIDENCE = DATA / "evidence_packages"
LOGS = DATA / "logs"
EXPORTS = DATA / "exports"
for p in [DATA, EVIDENCE, LOGS, EXPORTS]:
    p.mkdir(parents=True, exist_ok=True)
