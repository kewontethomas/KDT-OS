# FieldSeed Vision Build

This is a clean FieldSeed rebuild around the actual vision:

- Brain Mode
- Collector Mode
- Rescue Mode
- Truth-locked AI
- Conversational tickets
- No guessing / no hallucination-first design
- Active background health agent
- Confirmed-knowledge-only learning

## Main Rule

FieldSeed does not assume. It separates:

- Confirmed facts
- Unknowns
- Next investigation steps

Example:

"Customer says cameras are not working. They don't know what system they have. I am connecting through LogMeIn."

FieldSeed should create:

- Category: Video / Camera
- Confirmed System: Unknown
- Access: Remote via LogMeIn
- Next: identify VMS/platform

It should NOT guess OpenEye unless you explicitly say OpenEye or evidence confirms OpenEye.
