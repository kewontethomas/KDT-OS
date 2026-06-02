# KDT OS V26 — Governance Action Engine

V26 turns V25 governance intelligence into safe actions.

## New page

- `/action_center`
- `/action_center/run`
- `/action_center.json`

## What V26 can do

- Preview proposed repairs without changing files
- Repair quest governance metadata
- Archive weaker duplicate quests with postmortems
- Approve strong 90%+ clean quests in-place
- Run a safe cleanup sequence
- Log all actions to `reports/governance_actions.json`

## Safety rules

- V26 does not permanently delete quests.
- Duplicate cleanup archives a copy and creates a postmortem before removing the active duplicate.
- Strong quest approval updates metadata only.
- The active quest library remains the source of truth.

## Test

Open:

```text
http://127.0.0.1:5000/action_center
```

Try **Preview Only** first.

Then run:

```text
Repair Metadata
```

After that, re-check:

```text
http://127.0.0.1:5000/auto_governance
http://127.0.0.1:5000/self_check
```
