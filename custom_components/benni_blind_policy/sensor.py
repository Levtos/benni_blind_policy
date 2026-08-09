"""Sensor-Plattform: Mode, Position, Debug."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_COORDINATOR,
    DOMAIN,
    NAME_DEBUG,
    NAME_MODE,
    NAME_POSITION,
    UID_DEBUG,
    UID_MODE,
    UID_POSITION,
    unique_id,
)
from .entity import BlindPolicyEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coord = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([
        ModeSensor(coord, entry),
        PositionSensor(coord, entry),
        DebugSensor(coord, entry),
    ])


class ModeSensor(BlindPolicyEntity, SensorEntity):
    _attr_icon = "mdi:roller-shade"

    def __init__(self, coord, entry):
        super().__init__(coord, entry)
        self._attr_unique_id = unique_id(entry.entry_id, UID_MODE)
        self._attr_name = NAME_MODE

    @property
    def native_value(self):
        d = self.coord.last_decision
        return d.mode if d else None


class PositionSensor(BlindPolicyEntity, SensorEntity):
    _attr_icon = "mdi:roller-shade-closed"
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coord, entry):
        super().__init__(coord, entry)
        self._attr_unique_id = unique_id(entry.entry_id, UID_POSITION)
        self._attr_name = NAME_POSITION

    @property
    def native_value(self):
        d = self.coord.last_decision
        return d.target_position if d else None


class DebugSensor(BlindPolicyEntity, SensorEntity):
    """State = aktiver Modus; Attribute = volle Begründung + Trace + Gate-Internals."""

    _attr_icon = "mdi:bug-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coord, entry):
        super().__init__(coord, entry)
        self._attr_unique_id = unique_id(entry.entry_id, UID_DEBUG)
        self._attr_name = NAME_DEBUG

    @property
    def native_value(self):
        d = self.coord.last_decision
        return d.mode if d else None

    @property
    def extra_state_attributes(self):
        d = self.coord.last_decision
        ctx = self.coord.build_context()
        protection = d.protection_demand.as_dict() if d and d.protection_demand else None
        attrs = {
            "active_mode": d.mode if d else None,
            "active_position": d.target_position if d else None,
            "reason": d.reason if d else None,
            "gate_active": self.coord.gate_on,
            "lux_current": ctx.lux,
            "sun_elevation": ctx.sun_elevation,
            "privacy_latch": self.coord.privacy_latch_active,
            "privacy_bed": self.coord.privacy_bed_active,
            "manual_override": self.coord.manual_override_active,
            "writing_active": self.coord.writing_active,
            "bio_state": ctx.bio_state,
            "day_state": ctx.day_state,
            "day_context": ctx.day_context,
            "household": ctx.presence_household,
            "media_scenario": ctx.media_scenario,
            "gaming_source": ctx.gaming_source,
            "weather_condition": ctx.weather_condition,
            "outdoor_temp": ctx.outdoor_temp,
            "window_open": ctx.window_open,
            "profile": self.coord.profile_route,
            "apply_enabled": self.coord.apply_enabled,
            "blockers": list(d.blockers) if d else [],
            "protection_demand": protection,
        }
        if protection:
            attrs.update({
                "thermal_active": protection["thermal_active"],
                "glare_active": protection["glare_active"],
                "effective_protection_position": protection["effective_target_position"],
            })
        if d:
            attrs["trace"] = [e.__dict__ for e in d.trace]
        return attrs
