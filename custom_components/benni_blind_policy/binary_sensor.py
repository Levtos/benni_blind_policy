"""Binary-Sensor-Plattform: Lux-Gate, Privacy-Latch, Manual-Override, Writing-Active, Apply-Blocked."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_COORDINATOR,
    DOMAIN,
    NAME_APPLY_BLOCKED,
    NAME_LUX_GATE,
    NAME_MANUAL_OVERRIDE,
    NAME_PRIVACY_LATCH,
    NAME_WRITING_ACTIVE,
    UID_APPLY_BLOCKED,
    UID_LUX_GATE,
    UID_MANUAL_OVERRIDE,
    UID_PRIVACY_LATCH,
    UID_WRITING_ACTIVE,
    unique_id,
)
from .entity import BlindPolicyEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coord = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([
        LuxGateBinarySensor(coord, entry),
        PrivacyLatchBinarySensor(coord, entry),
        ManualOverrideBinarySensor(coord, entry),
        WritingActiveBinarySensor(coord, entry),
        ApplyBlockedBinarySensor(coord, entry),
    ])


class LuxGateBinarySensor(BlindPolicyEntity, BinarySensorEntity):
    _attr_icon = "mdi:white-balance-sunny"

    def __init__(self, coord, entry):
        super().__init__(coord, entry)
        self._attr_unique_id = unique_id(entry.entry_id, UID_LUX_GATE)
        self._attr_name = NAME_LUX_GATE

    @property
    def is_on(self) -> bool:
        return self.coord.gate_on


class PrivacyLatchBinarySensor(BlindPolicyEntity, BinarySensorEntity):
    _attr_icon = "mdi:shield-lock-outline"

    def __init__(self, coord, entry):
        super().__init__(coord, entry)
        self._attr_unique_id = unique_id(entry.entry_id, UID_PRIVACY_LATCH)
        self._attr_name = NAME_PRIVACY_LATCH

    @property
    def is_on(self) -> bool:
        return self.coord.privacy_latch_active


class ManualOverrideBinarySensor(BlindPolicyEntity, BinarySensorEntity):
    _attr_icon = "mdi:hand-back-right-outline"

    def __init__(self, coord, entry):
        super().__init__(coord, entry)
        self._attr_unique_id = unique_id(entry.entry_id, UID_MANUAL_OVERRIDE)
        self._attr_name = NAME_MANUAL_OVERRIDE

    @property
    def is_on(self) -> bool:
        return self.coord.manual_override_active


class WritingActiveBinarySensor(BlindPolicyEntity, BinarySensorEntity):
    _attr_icon = "mdi:pencil-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coord, entry):
        super().__init__(coord, entry)
        self._attr_unique_id = unique_id(entry.entry_id, UID_WRITING_ACTIVE)
        self._attr_name = NAME_WRITING_ACTIVE

    @property
    def is_on(self) -> bool:
        return self.coord.writing_active


class ApplyBlockedBinarySensor(BlindPolicyEntity, BinarySensorEntity):
    """on = Decision darf gerade NICHT angewendet werden (Gating aktiv)."""

    _attr_icon = "mdi:lock-alert"

    def __init__(self, coord, entry):
        super().__init__(coord, entry)
        self._attr_unique_id = unique_id(entry.entry_id, UID_APPLY_BLOCKED)
        self._attr_name = NAME_APPLY_BLOCKED

    @property
    def is_on(self) -> bool:
        d = self.coord.last_decision
        return bool(d and not d.apply_allowed)

    @property
    def extra_state_attributes(self):
        d = self.coord.last_decision
        return {"blockers": list(d.blockers) if d else []}
