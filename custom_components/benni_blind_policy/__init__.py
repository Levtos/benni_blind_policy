"""Benni Blind Policy — Wohnzimmer-Rollo (L2-Policy, eigene HACS-Integration).

Decision/Apply-Pattern wie cover_policy/light_policy: der Coordinator hört auf alle
Quell-Entities, rechnet die Prioritätskette (policy.decide) und fährt das Cover —
gated an ``apply_enabled`` (Default False = Shadow-safe).
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall

from .const import (
    CONFIG_ENTRY_VERSION,
    CONF_POSITION_PROFILE,
    DATA_COORDINATOR,
    DATA_SKIP_RELOAD_COUNT,
    DOMAIN,
    SERVICE_APPLY_NOW,
    SERVICE_CLEAR_MANUAL_OVERRIDE,
    SERVICE_SET_POSITION_PROFILE,
    SERVICE_SET_PRIVACY_BED,
)
from .coordinator import BlindPolicyCoordinator, all_coordinators
from .migration import migrate_source_ids
from .view import async_remove_view, async_setup_view
from .websocket_api import async_setup_websocket_api

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH]
_WS_FLAG = "_ws_registered"


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate existing entries to current source contracts."""
    if entry.version > CONFIG_ENTRY_VERSION:
        return False

    changed, data, options = migrate_source_ids(entry.data, entry.options)
    if changed or entry.version != CONFIG_ENTRY_VERSION:
        hass.config_entries.async_update_entry(
            entry,
            data=data,
            options=options,
            version=CONFIG_ENTRY_VERSION,
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coord = BlindPolicyCoordinator(hass, entry)
    await coord.async_load()
    coord.async_start()
    await coord.async_evaluate()

    data = hass.data.setdefault(DOMAIN, {})
    data[entry.entry_id] = {DATA_COORDINATOR: coord}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_register_services(hass)

    await async_setup_view(hass)
    if not data.get(_WS_FLAG):
        async_setup_websocket_api(hass)
        data[_WS_FLAG] = True

    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    data = hass.data.setdefault(DOMAIN, {})
    skip_count = int(data.get(DATA_SKIP_RELOAD_COUNT) or 0)
    if skip_count > 0:
        data[DATA_SKIP_RELOAD_COUNT] = skip_count - 1
        return
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        bucket = hass.data[DOMAIN].pop(entry.entry_id, None)
        if bucket:
            bucket[DATA_COORDINATOR].async_stop()
        if not all_coordinators(hass):
            async_remove_view(hass)
            for svc in (
                SERVICE_APPLY_NOW, SERVICE_SET_PRIVACY_BED,
                SERVICE_CLEAR_MANUAL_OVERRIDE, SERVICE_SET_POSITION_PROFILE,
            ):
                if hass.services.has_service(DOMAIN, svc):
                    hass.services.async_remove(DOMAIN, svc)
    return unloaded


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_APPLY_NOW):
        return

    async def _apply_now(_call: ServiceCall) -> None:
        for coord in all_coordinators(hass):
            await coord.async_apply_now()

    async def _set_privacy_bed(call: ServiceCall) -> None:
        value = bool(call.data.get("enabled", True))
        for coord in all_coordinators(hass):
            await coord.async_set_privacy_bed(value)

    async def _clear_override(_call: ServiceCall) -> None:
        for coord in all_coordinators(hass):
            await coord.async_clear_manual_override()

    async def _set_position_profile(call: ServiceCall) -> None:
        profile = call.data.get(CONF_POSITION_PROFILE) or call.data.get("profile") or {}
        for coord in all_coordinators(hass):
            await coord.async_set_position_profile(dict(profile))

    hass.services.async_register(DOMAIN, SERVICE_APPLY_NOW, _apply_now)
    hass.services.async_register(DOMAIN, SERVICE_SET_PRIVACY_BED, _set_privacy_bed)
    hass.services.async_register(DOMAIN, SERVICE_CLEAR_MANUAL_OVERRIDE, _clear_override)
    hass.services.async_register(DOMAIN, SERVICE_SET_POSITION_PROFILE, _set_position_profile)
