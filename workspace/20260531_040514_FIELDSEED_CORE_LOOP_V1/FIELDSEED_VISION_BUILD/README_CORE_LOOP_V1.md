# FieldSeed Core Loop V1

Adds the living technician-memory loop:

Observe -> Detect -> Learn -> Propose -> Repair -> Test -> Remember -> Improve

Added:
- Background Core Loop runs automatically every few minutes.
- Watches health, tickets, repairs, self-checks, repeated events, and repair candidates.
- Seed memory table stores strengths, flaws, repair outcomes, open work, repeated patterns, and confirmed resolutions.
- Observer events table records what Seed notices.
- Pattern detector turns repeated events into improvement ideas.
- Growth has Run Core Loop Now.
- Deep self-inspection still creates repair candidates.
- Repairs remain approval-gated with backup/test/rollback.
