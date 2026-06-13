"""Diagnostics-Dump für die Blind-Policy (State + Decision + Quell-Bindings)."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DATA_COORDINATOR, DOMAIN, SOURCE_KEYS


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    bucket = hass.data.get(DOMAIN, {}).get(entry.entry_id) or {}
    coord = bucket.get(DATA_COORDINATOR)
    if coord is None:
        return {"error": "coordinator not loaded", "entry_data": dict(entry.data)}

    opts = {**entry.data, **entry.options}
    bindings = {}
    for key in SOURCE_KEYS:
        eid = opts.get(key)
        st = hass.states.get(eid) if eid else None
        bindings[key] = {
            "entity_id": eid,
            "state": st.state if st else None,
            "available": st is not None and st.state not in ("unknown", "unavailable"),
        }

    d = coord.last_decision
    return {
        "profile": coord.profile_route,
        "apply_enabled": coord.apply_enabled,
        "startup_ready": coord.startup_ready,
        "gate_on": coord.gate_on,
        "privacy_latch": coord.privacy_latch_active,
        "privacy_bed": coord.privacy_bed_active,
        "alarm_wakeup": coord.alarm_wakeup_active,
        "manual_override": coord.manual_override_active,
        "writing_active": coord.writing_active,
        "position_profile": coord.position_profile,
        "decision": d.as_dict() if d else None,
        "source_bindings": bindings,
    }
