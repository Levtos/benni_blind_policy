"""Storage-Helper. Konvention: .storage/benni_blind_policy_state_<entry_id>."""
from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_VERSION, storage_suffix


def make_store(hass: HomeAssistant, entry_id: str) -> Store[dict[str, Any]]:
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}_{storage_suffix(entry_id)}")
