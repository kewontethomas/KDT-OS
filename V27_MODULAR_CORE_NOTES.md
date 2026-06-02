# KDT OS V27 Modular Core

V27 begins the architecture cleanup without breaking the existing app.

## What changed

- Added `kdt_modular_core_v27.py`
- Added `/modular_core`
- Added `/modular_core.json`
- Added `templates/modular_core.html`
- Added `routes/`, `engines/`, and `core/` package scaffolds
- Added Modular Core link under System
- Added V27 CSS styles
- Wired V27 after V26 in `app.py`

## Why this matters

KDT OS is now large enough that `app.py` has become a long-term risk. V27 does not perform a dangerous one-shot refactor. It creates a safe modularization map and prepares the app for gradual extraction.

## Next safe extraction order

1. Move shared paths and JSON helpers into `core/`
2. Move governance and self-check logic into `engines/`
3. Move Verify routes into `routes/verify_routes.py`
4. Move Learn routes into `routes/learn_routes.py`
5. Move Build routes into `routes/build_routes.py`
6. Keep `app.py` as a launcher and registry

## Test

Open:

```text
http://127.0.0.1:5000/modular_core
```
