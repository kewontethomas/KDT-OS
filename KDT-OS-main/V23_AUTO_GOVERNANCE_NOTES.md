# KDT OS V23 — Auto Governance Gate

V23 adds a repair gate between quest generation and active learning.

## New files
- `kdt_auto_governance_v23.py`
- `templates/auto_governance.html`

## Updated files
- `app.py` wires V23 after V20, V21, and V22.
- `templates/_nav.html` adds **Auto Governance** under Verify.
- `static/style.css` adds the V23 UI cards.

## New routes
- `/auto_governance` — review repair plan
- `/auto_governance/run` — dry-run or execute governance repairs
- `/auto_governance.json` — JSON version of the repair plan

## What V23 repairs
- Quests missing `quest_quality` metadata are rescored.
- Generic or weak quests are regenerated through Quest Intelligence V20.
- Duplicate quest bodies are detected and sent through archive/regenerate flow.
- Repair logs are saved in `reports/auto_governance_v23_*.json`.

## Suggested test path
1. Start the app: `python app.py`
2. Open `http://127.0.0.1:5000/auto_governance`
3. Click **Preview Repair Plan** first.
4. Click **Auto Repair Quest Governance** only after reviewing the plan.
5. Return to `/self_check` and confirm quest governance improves.
