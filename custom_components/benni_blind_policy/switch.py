"""Switch-Plattform: extern setzbare Helfer-Booleans + Apply-Master.

- Privacy Bed (R2):      vom Hue Dimmer (große Sonne) gesetzt; manueller Bett-Modus.
- Alarm Wakeup (R4):     Platzhalter, vom künftigen Wecker-Modul gesetzt.
- Manual Override (R-MO): vom Coordinator auto-erkannt; hier manuell löschbar.
- Apply Enabled:         Shadow-Master (OFF = keine Schreibvorgänge).
"""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_COORDINATOR,
    DOMAIN,
    NAME_ALARM_WAKEUP,
    NAME_APPLY_ENABLED,
    NAME_MANUAL_OVERRIDE,
    NAME_PRIVACY_BED,
    UID_ALARM_WAKEUP,
    UID_APPLY_ENABLED,
    UID_MANUAL_OVERRIDE,
    UID_PRIVACY_BED,
    unique_id,
)
from .entity import BlindPolicyEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coord = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([
        PrivacyBedSwitch(coord, entry),
        AlarmWakeupSwitch(coord, entry),
        ManualOverrideSwitch(coord, entry),
        ApplyEnabledSwitch(coord, entry),
    ])


class PrivacyBedSwitch(BlindPolicyEntity, SwitchEntity):
    _attr_icon = "mdi:bed"

    def __init__(self, coord, entry):
        super().__init__(coord, entry)
        self._attr_unique_id = unique_id(entry.entry_id, UID_PRIVACY_BED)
        self._attr_name = NAME_PRIVACY_BED

    @property
    def is_on(self) -> bool:
        return self.coord.privacy_bed_active

    async def async_turn_on(self, **kwargs) -> None:
        await self.coord.async_set_privacy_bed(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coord.async_set_privacy_bed(False)


class AlarmWakeupSwitch(BlindPolicyEntity, SwitchEntity):
    _attr_icon = "mdi:alarm"

    def __init__(self, coord, entry):
        super().__init__(coord, entry)
        self._attr_unique_id = unique_id(entry.entry_id, UID_ALARM_WAKEUP)
        self._attr_name = NAME_ALARM_WAKEUP

    @property
    def is_on(self) -> bool:
        return self.coord.alarm_wakeup_active

    async def async_turn_on(self, **kwargs) -> None:
        await self.coord.async_set_alarm_wakeup(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coord.async_set_alarm_wakeup(False)


class ManualOverrideSwitch(BlindPolicyEntity, SwitchEntity):
    _attr_icon = "mdi:hand-back-right"

    def __init__(self, coord, entry):
        super().__init__(coord, entry)
        self._attr_unique_id = unique_id(entry.entry_id, UID_MANUAL_OVERRIDE)
        self._attr_name = NAME_MANUAL_OVERRIDE

    @property
    def is_on(self) -> bool:
        return self.coord.manual_override_active

    async def async_turn_on(self, **kwargs) -> None:
        await self.coord.async_set_manual_override(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coord.async_clear_manual_override()


class ApplyEnabledSwitch(BlindPolicyEntity, SwitchEntity):
    _attr_icon = "mdi:flash"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coord, entry):
        super().__init__(coord, entry)
        self._attr_unique_id = unique_id(entry.entry_id, UID_APPLY_ENABLED)
        self._attr_name = NAME_APPLY_ENABLED

    @property
    def is_on(self) -> bool:
        return self.coord.apply_enabled

    async def async_turn_on(self, **kwargs) -> None:
        await self.coord.async_set_apply_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coord.async_set_apply_enabled(False)
