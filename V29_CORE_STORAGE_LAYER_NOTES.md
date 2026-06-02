# KDT OS V29 - Core Storage Layer

V29 adds the first shared core layer so future modules can stop depending on a giant `app.py`.

## Added

- `core/paths.py`
- `core/storage.py`
- `core/constants.py`
- `kdt_core_storage_v29.py`
- `templates/core_storage.html`
- `/core_storage`
- `/core_storage.json`

## Rule

Do not rewrite every JSON call at once. New modules should use `core.storage` first, then future versions can move quest/project/report stores safely.

## Test

Open:

```text
http://127.0.0.1:5000/core_storage
```

Also verify existing pages still load:

```text
/
/self_check
/action_center
/route_extraction
```
