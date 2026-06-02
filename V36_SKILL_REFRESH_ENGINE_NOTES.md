# KDT OS V36 - Skill Decay & Refresh Engine

V36 adds a long-term refresh layer to the learning system.

## Added

- `kdt_skill_refresh_v36.py`
- `templates/skill_refresh.html`
- `/skill_refresh`
- `/skill_refresh.json`
- `reports/skill_decay.json`
- `reports/refresh_queue.json`
- Skill Refresh link under Verify

## Purpose

V35 remembers verified skills.
V36 decides when those skills need review.

The learning loop is now:

Learn -> Verify -> Promote -> Remember -> Refresh

## Test

Open:

- `/skill_refresh`
- `/learning_memory`
- `/proof_promotion`
- `/skill_verification`
- `/command_center`
