"""KDT OS System Routes V28

System-family registration for architecture and self-evolution tools.
This starts small: V27 Modular Core plus V28 Route Extraction.
"""
from __future__ import annotations

from typing import Any, Dict, List

from kdt_modular_core_v27 import install as install_v27
from kdt_route_extraction_v28 import install as install_v28

SYSTEM_MODULES: List[Dict[str, str]] = [
    {"version": "V27", "name": "Modular Core", "module": "kdt_modular_core_v27"},
    {"version": "V28", "name": "Route Extraction", "module": "kdt_route_extraction_v28"},
]


def register_system_routes(kdt: Any) -> Dict[str, Any]:
    installed = []
    for meta, installer in zip(SYSTEM_MODULES, [install_v27, install_v28]):
        installer(kdt)
        installed.append(meta)
    return {
        "family": "System",
        "installed": installed,
        "note": "V28 extracted System-family route registration from app.py.",
    }
