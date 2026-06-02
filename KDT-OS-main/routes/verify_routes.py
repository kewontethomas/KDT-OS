"""KDT OS Verify Routes V28

This is the first real route-family extraction.

Before V28, app.py directly imported and installed every Verify/Governance
extension module. V28 moves the Verify-family registration behind one small
function so app.py no longer needs to know the internal order of these systems.

Route family owned here:
- Self Check V22
- Auto Governance V23
- Unified Governance V24
- Governance Intelligence V25
- Action Center V26

Rule: route files connect route families. Heavy scanning/repair logic stays in
engine/version modules.
"""
from __future__ import annotations

from typing import Any, Dict, List

from kdt_self_check_v22 import install as install_v22
from kdt_auto_governance_v23 import install as install_v23
from kdt_unified_governance_v24 import install as install_v24
from kdt_governance_intelligence_v25 import install as install_v25
from kdt_action_engine_v26 import install as install_v26

VERIFY_MODULES: List[Dict[str, str]] = [
    {"version": "V22", "name": "Self Check", "module": "kdt_self_check_v22"},
    {"version": "V23", "name": "Auto Governance", "module": "kdt_auto_governance_v23"},
    {"version": "V24", "name": "Unified Governance", "module": "kdt_unified_governance_v24"},
    {"version": "V25", "name": "Governance Intelligence", "module": "kdt_governance_intelligence_v25"},
    {"version": "V26", "name": "Action Engine", "module": "kdt_action_engine_v26"},
]


def register_verify_routes(kdt: Any) -> Dict[str, Any]:
    """Register the Verify route family in the correct dependency order."""
    installs = [install_v22, install_v23, install_v24, install_v25, install_v26]
    installed = []
    for meta, installer in zip(VERIFY_MODULES, installs):
        installer(kdt)
        installed.append(meta)
    return {
        "family": "Verify",
        "installed": installed,
        "note": "V28 extracted Verify-family route registration from app.py.",
    }
