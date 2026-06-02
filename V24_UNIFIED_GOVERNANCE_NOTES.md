# KDT OS V24 - Unified Governance Engine

V24 fixes the mismatch where Self Check could report quest problems while Auto Governance showed 0 issues.

## What changed

- Added `kdt_unified_governance_v24.py`
- Self Check and Auto Governance now share the same active quest scanner
- V24 overrides the V22/V23 route handlers after they install
- Auto Governance now catches:
  - generic template quest language
  - duplicate quest bodies
  - missing governance metadata
  - missing required quest structure
  - archived/superseded quests still sitting in `quests/`
- Auto Repair can:
  - move stale archived copies out of active quests
  - archive weak active quests
  - create postmortems
  - generate stronger replacement quests
  - rescore metadata-only issues
  - log actions in `reports/`

## Test pages

- `/self_check`
- `/auto_governance`
- `/auto_governance.json`
- `/self_check.json`

## Expected behavior

If Self Check says quest governance has issues, Auto Governance should now show the same repairable issue count.
