# KDT OS V31 - Shared Helper Layer

V31 adds a safe shared helper layer for pure utility functions.

## Added
- `core/helpers.py`
- `kdt_shared_helpers_v31.py`
- `templates/shared_helpers.html`
- `/shared_helpers`
- `/shared_helpers.json`

## Rule
Only move pure utility helpers first. Do not move routes, request logic, template rendering, or anything that changes user-facing behavior.

## Test
Open:

```text
http://127.0.0.1:5000/shared_helpers
```

Also test:

```text
/
/command_center
/core_storage
/route_extraction
/modular_core
/self_check
```
