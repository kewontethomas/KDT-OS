# KDT OS V25 - Governance Intelligence

V25 improves V24 by reducing false positives and making governance actionable.

## Added

- `kdt_governance_intelligence_v25.py`
- Weighted quest scoring
- Duplicate topic clustering
- Safer metadata repair
- Cluster recommendations: keep strongest, archive weaker duplicates
- Grouped Auto Governance UI
- V25-powered Quest Governance audit inside Self Check

## Why this matters

V24 correctly found quest problems, but it treated too many quests as high risk.
V25 does not treat one generic phrase as automatic failure. It looks at proof, exact files, steps, success criteria, understanding checks, metadata, and duplicates together.

## Test

Run the app and open:

- `/auto_governance`
- `/self_check`
- `/auto_governance.json`

Use Preview first before Auto Repair.
