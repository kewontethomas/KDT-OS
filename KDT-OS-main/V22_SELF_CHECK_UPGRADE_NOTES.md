# KDT OS V22 Self Check Upgrade

This version adds a System Health / Self Check Center.

## New files
- `kdt_self_check_v22.py`
- `templates/self_check.html`

## Updated files
- `app.py` now installs V22 with `install_v22(sys.modules[__name__])`.
- `templates/_nav.html` now links to Mastery and Self Check.
- `templates/mastery.html` now uses the shared `.shell` layout.
- `static/style.css` includes Self Check UI styles.

## New routes
- `/self_check`
- `/self_check.json`

## What Self Check audits
- Route health
- Template consistency
- UI/CSS health
- Data integrity
- Quest governance
- Architecture risk

## Important
If Flask is not installed in the environment, the app cannot be runtime-tested there. The Python files have been syntax-checked with `py_compile`.
