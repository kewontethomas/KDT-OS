# KDT OS V34 Proof Promotion Engine

V34 closes the loop created by V33 Skill Verification.

## Added
- `kdt_proof_promotion_v34.py`
- `templates/proof_promotion.html`
- `/proof_promotion`
- `/proof_promotion.json`
- `/proof_promotion/promote/<filename>`
- Sidebar link under Verify
- Verified skill ledger at `reports/verified_skill_ledger.json`

## Purpose
V33 creates skill verification quests. V34 lets KDT OS review and promote completed verification quests into `skill_library/skills.json` so skills become trusted memory.

## Rule
Estimated skill is not trusted skill. Proof must become memory.
