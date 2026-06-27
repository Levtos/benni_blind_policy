"""WebSocket-API für das Blind-Policy-Panel.

Ein konsolidierter Status-Snapshot (Decision + Trace + Gate-Internals + Quell-
Bindings + Cover-Ist) plus Mutations-Commands (Apply, Privacy-Bed, Override-Reset,
Positions-Profil). Read-Commands ohne Admin, Schreib-Commands nur Admin.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import (
    CONF_COVER_ENTITY,
    DATA_COORDINATOR,
    DOMAIN,
    GATE_CLOSE_LUX,
    GATE_OPEN_LUX,
    GATE_SUN_MIN_DEG,
    HEAT_SUN_MIN_DEG,
    HEAT_TEMP_C,
    MANUAL_MODES,
    OPEN_WEEKDAY_MIN_MINUTES,
    OPEN_WEEKEND_MIN_MINUTES,
    PRIVACY_LATCH_LUX,
    SOURCE_KEYS,
    WS_APPLY_NOW,
    WS_CLEAR_OVERRIDE,
    WS_GET_STATUS,
    WS_SET_APPLY_ENABLED,
    WS_SET_INVERT_POSITION,
    WS_SET_MANUAL_DECISION,
    WS_SET_MANUAL_POSITION,
    WS_SET_POSITION_PROFILE,
    WS_SET_PRIVACY_BED,
)


def _coordinator(hass: HomeAssistant):
    for bucket in (hass.data.get(DOMAIN) or {}).values():
        if isinstance(bucket, dict) and DATA_COORDINATOR in bucket:
            return bucket[DATA_COORDINATOR]
    return None


def _source_bindings(hass: HomeAssistant, coord) -> dict[str, Any]:
    out: dict[str, Any] = {}
    opts = {**coord.entry.data, **coord.entry.options}
    for key in SOURCE_KEYS:
        eid = opts.get(key)
        st = hass.states.get(eid) if eid else None
        out[key] = {
            "entity_id": eid,
            "state": st.state if st else None,
            "available": st is not None and st.state not in ("unknown", "unavailable"),
        }
    return out


def _status(hass: HomeAssistant, coord) -> dict[str, Any]:
    d = coord.last_decision
    ctx = coord.build_context()
    cover_eid = coord.cover_entity
    cover_st = hass.states.get(cover_eid) if cover_eid else None
    return {
        "profile": coord.profile_route,
        "apply_enabled": coord.apply_enabled,
        "invert_position": coord.invert_position,
        "startup_ready": coord.startup_ready,
        "mode": d.mode if d else None,
        "target_position": d.target_position if d else None,
        "reason": d.reason if d else None,
        "apply_allowed": d.apply_allowed if d else None,
        "blockers": list(d.blockers) if d else [],
        "gate_on": coord.gate_on,
        "privacy_latch": coord.privacy_latch_active,
        "privacy_bed": coord.privacy_bed_active,
        "alarm_wakeup": coord.alarm_wakeup_active,
        "manual_override": coord.manual_override_active,
        "manual_explicit": coord.manual_explicit,
        "manual_mode": coord.manual_mode,
        "manual_target": coord.manual_target,
        "manual_modes": list(MANUAL_MODES),
        "thresholds": {
            "gate_open_lux": GATE_OPEN_LUX,
            "gate_close_lux": GATE_CLOSE_LUX,
            "gate_sun_min_deg": GATE_SUN_MIN_DEG,
            "heat_temp_c": HEAT_TEMP_C,
            "heat_sun_min_deg": HEAT_SUN_MIN_DEG,
            "privacy_latch_lux": PRIVACY_LATCH_LUX,
            "open_weekday_min_minutes": OPEN_WEEKDAY_MIN_MINUTES,
            "open_weekend_min_minutes": OPEN_WEEKEND_MIN_MINUTES,
        },
        "writing_active": coord.writing_active,
        "trace": [e.__dict__ for e in d.trace] if d else [],
        "position_profile": coord.position_profile,
        "context": {
            "window_open": ctx.window_open,
            "bio_state": ctx.bio_state,
            "day_state": ctx.day_state,
            "day_context": ctx.day_context,
            "presence_household": ctx.presence_household,
            "media_scenario": ctx.media_scenario,
            "gaming_source": ctx.gaming_source,
            "lux": ctx.lux,
            "sun_elevation": ctx.sun_elevation,
            "weather_condition": ctx.weather_condition,
            "outdoor_temp": ctx.outdoor_temp,
        },
        "cover": {
            "entity_id": cover_eid,
            "state": cover_st.state if cover_st else None,
            "current_position": (cover_st.attributes.get("current_position") if cover_st else None),
        },
        "source_bindings": _source_bindings(hass, coord),
    }


def async_setup_websocket_api(hass: HomeAssistant) -> None:
    @websocket_api.websocket_command({vol.Required("type"): WS_GET_STATUS})
    @websocket_api.async_response
    async def ws_get_status(hass, connection, msg) -> None:
        coord = _coordinator(hass)
        if coord is None:
            connection.send_error(msg["id"], "not_ready", "Blind Policy not loaded")
            return
        connection.send_result(msg["id"], _status(hass, coord))

    @websocket_api.websocket_command({vol.Required("type"): WS_APPLY_NOW})
    @websocket_api.require_admin
    @websocket_api.async_response
    async def ws_apply_now(hass, connection, msg) -> None:
        coord = _coordinator(hass)
        if coord is None:
            connection.send_error(msg["id"], "not_ready", "Blind Policy not loaded")
            return
        await coord.async_apply_now()
        connection.send_result(msg["id"], _status(hass, coord))

    @websocket_api.websocket_command({
        vol.Required("type"): WS_SET_APPLY_ENABLED,
        vol.Required("enabled"): bool,
    })
    @websocket_api.require_admin
    @websocket_api.async_response
    async def ws_set_apply_enabled(hass, connection, msg) -> None:
        coord = _coordinator(hass)
        if coord is None:
            connection.send_error(msg["id"], "not_ready", "Blind Policy not loaded")
            return
        await coord.async_set_apply_enabled(msg["enabled"])
        connection.send_result(msg["id"], _status(hass, coord))

    @websocket_api.websocket_command({
        vol.Required("type"): WS_SET_INVERT_POSITION,
        vol.Required("enabled"): bool,
    })
    @websocket_api.require_admin
    @websocket_api.async_response
    async def ws_set_invert_position(hass, connection, msg) -> None:
        coord = _coordinator(hass)
        if coord is None:
            connection.send_error(msg["id"], "not_ready", "Blind Policy not loaded")
            return
        await coord.async_set_invert_position(msg["enabled"])
        connection.send_result(msg["id"], _status(hass, coord))

    @websocket_api.websocket_command({
        vol.Required("type"): WS_SET_PRIVACY_BED,
        vol.Required("enabled"): bool,
    })
    @websocket_api.require_admin
    @websocket_api.async_response
    async def ws_set_privacy_bed(hass, connection, msg) -> None:
        coord = _coordinator(hass)
        if coord is None:
            connection.send_error(msg["id"], "not_ready", "Blind Policy not loaded")
            return
        await coord.async_set_privacy_bed(msg["enabled"])
        connection.send_result(msg["id"], _status(hass, coord))

    @websocket_api.websocket_command({vol.Required("type"): WS_CLEAR_OVERRIDE})
    @websocket_api.require_admin
    @websocket_api.async_response
    async def ws_clear_override(hass, connection, msg) -> None:
        coord = _coordinator(hass)
        if coord is None:
            connection.send_error(msg["id"], "not_ready", "Blind Policy not loaded")
            return
        await coord.async_clear_manual_override()
        connection.send_result(msg["id"], _status(hass, coord))

    @websocket_api.websocket_command({
        vol.Required("type"): WS_SET_POSITION_PROFILE,
        vol.Required("position_profile"): {str: vol.Any(int, float, str)},
    })
    @websocket_api.require_admin
    @websocket_api.async_response
    async def ws_set_position_profile(hass, connection, msg) -> None:
        coord = _coordinator(hass)
        if coord is None:
            connection.send_error(msg["id"], "not_ready", "Blind Policy not loaded")
            return
        cleaned = await coord.async_set_position_profile(msg["position_profile"])
        connection.send_result(msg["id"], {"position_profile": cleaned})

    @websocket_api.websocket_command({
        vol.Required("type"): WS_SET_MANUAL_POSITION,
        vol.Required("position"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    })
    @websocket_api.require_admin
    @websocket_api.async_response
    async def ws_set_manual_position(hass, connection, msg) -> None:
        coord = _coordinator(hass)
        if coord is None:
            connection.send_error(msg["id"], "not_ready", "Blind Policy not loaded")
            return
        await coord.async_set_manual_position(msg["position"])
        connection.send_result(msg["id"], _status(hass, coord))

    @websocket_api.websocket_command({
        vol.Required("type"): WS_SET_MANUAL_DECISION,
        vol.Required("mode"): vol.In(list(MANUAL_MODES)),
    })
    @websocket_api.require_admin
    @websocket_api.async_response
    async def ws_set_manual_decision(hass, connection, msg) -> None:
        coord = _coordinator(hass)
        if coord is None:
            connection.send_error(msg["id"], "not_ready", "Blind Policy not loaded")
            return
        await coord.async_set_manual_decision(msg["mode"])
        connection.send_result(msg["id"], _status(hass, coord))

    for cmd in (
        ws_get_status, ws_apply_now, ws_set_apply_enabled, ws_set_invert_position,
        ws_set_privacy_bed, ws_clear_override, ws_set_position_profile,
        ws_set_manual_position, ws_set_manual_decision,
    ):
        websocket_api.async_register_command(hass, cmd)
