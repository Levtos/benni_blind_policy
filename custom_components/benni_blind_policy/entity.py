"""Gemeinsame Entity-Basis: abonniert den Coordinator, teilt das profil-benannte Device.

Slug-Schema (FLEET-16): ``has_entity_name`` + Device-Name ``"{Label} Blind Policy"``
⇒ ``sensor.benni_blind_policy_<feature>`` bzw. ``eltern_blind_policy_<feature>``.
"""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback

from .const import CONF_PROFILE, DEFAULT_PROFILE_ROUTE, DOMAIN, PROFILE_LABELS
from .coordinator import BlindPolicyCoordinator


def device_info(entry: ConfigEntry) -> dict[str, Any]:
    profile = entry.data.get(CONF_PROFILE, DEFAULT_PROFILE_ROUTE)
    label = PROFILE_LABELS.get(profile, "Benni")
    # Der Device-Name bestimmt bei has_entity_name den Entity-Slug:
    #   "Benni Blind Policy"  → sensor.benni_blind_policy_*
    #   "Eltern Blind Policy" → sensor.eltern_blind_policy_*
    return {
        "identifiers": {(DOMAIN, entry.entry_id)},
        "name": f"{label} Blind Policy",
        "manufacturer": "Benni",
        "model": f"Blind Policy · {label}",
    }


class BlindPolicyEntity:
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coord: BlindPolicyCoordinator, entry: ConfigEntry) -> None:
        self.coord = coord
        self._entry = entry
        self._attr_device_info = device_info(entry)

    async def async_added_to_hass(self) -> None:
        self.coord.add_listener(self._sched_update)

    async def async_will_remove_from_hass(self) -> None:
        self.coord.remove_listener(self._sched_update)

    @callback
    def _sched_update(self) -> None:
        self.async_write_ha_state()  # type: ignore[attr-defined]
