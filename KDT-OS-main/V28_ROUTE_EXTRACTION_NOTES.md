# KDT OS V28 - Route Extraction Engine

V28 starts the first real modular route extraction.

## What changed

- Added `routes/verify_routes.py`
- Added `routes/system_routes.py`
- Added `kdt_route_extraction_v28.py`
- Added `templates/route_extraction.html`
- Updated `app.py` so Verify/System version modules are registered through route-family registrars instead of many direct install calls.

## Why this matters

KDT OS had passed 4,000 lines in `app.py`. V28 proves the app can be split into safer route families without doing a risky full rewrite.

## Test

Open:

```text
http://127.0.0.1:5000/route_extraction
```

Also verify these still work:

```text
/self_check
/auto_governance
/action_center
/modular_core
```

## Next recommended extraction

V29 should extract shared storage/path helpers into `core/storage.py` and `core/paths.py`.
