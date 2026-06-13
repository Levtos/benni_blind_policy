"""Config- und Options-Flow der Blind-Policy.

Single-Instance pro Profil-Route. Schritt 1 wählt die Route (benni/eltern,
Blaupause benni_core_state); Schritt 2 verdrahtet die Quellen (profil-prefilled,
greift nur wenn die Entity existiert); Schritt 3 die Optionen.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_APPLY_ENABLED,
    CONF_COVER_ENTITY,
    CONF_PROFILE,
    CONF_STARTUP_BLOCK_SECONDS,
    CONF_SUN,
    CONF_WINDOW_OPEN,
    DEFAULT_APPLY_ENABLED,
    DEFAULT_PROFILE_ROUTE,
    DEFAULT_STARTUP_BLOCK_SECONDS,
    DOMAIN,
    OPTION_KEYS,
    PROFILE_LABELS,
    PROFILE_PREFILL,
    PROFILES,
    SOURCE_KEYS,
)

_ENTITY = selector.EntitySelector(selector.EntitySelectorConfig())
_COVER = selector.EntitySelector(selector.EntitySelectorConfig(domain="cover"))
_BOOL = selector.BooleanSelector()
_INT = selector.NumberSelector(
    selector.NumberSelectorConfig(min=0, max=600, step=1, mode=selector.NumberSelectorMode.BOX)
)

# Spezial-Selektoren je Feld (Rest: generischer Entity-Selektor).
_FIELD_SELECTORS: dict[str, Any] = {
    CONF_COVER_ENTITY: _COVER,
    CONF_SUN: _ENTITY,
    CONF_WINDOW_OPEN: _ENTITY,
}


def _source_selector(key: str):
    return _FIELD_SELECTORS.get(key, _ENTITY)


def _exists(hass, eid: str | None) -> bool:
    return bool(eid) and hass.states.get(eid) is not None


def _prefilled_sources(profile: str, data: dict[str, Any], hass) -> dict[str, Any]:
    """Profil-Prefill, gefiltert auf real existierende Entities."""
    defaults = dict(data)
    prefill = PROFILE_PREFILL.get(profile, {})
    for key in SOURCE_KEYS:
        if key in defaults:
            continue
        cand = prefill.get(key)
        if cand and _exists(hass, cand):
            defaults[key] = cand
    return defaults


def _profile_schema(default: str) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_PROFILE, default=default): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(value=p, label=PROFILE_LABELS[p])
                    for p in PROFILES
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )
    })


def _sources_schema(defaults: dict[str, Any]) -> vol.Schema:
    fields: dict[Any, Any] = {}
    for key in SOURCE_KEYS:
        marker = (
            vol.Optional(key, default=defaults[key])
            if key in defaults and defaults[key] not in (None, "")
            else vol.Optional(key)
        )
        fields[marker] = _source_selector(key)
    return vol.Schema(fields)


def _options_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema({
        vol.Optional(
            CONF_APPLY_ENABLED,
            default=bool(defaults.get(CONF_APPLY_ENABLED, DEFAULT_APPLY_ENABLED)),
        ): _BOOL,
        vol.Optional(
            CONF_STARTUP_BLOCK_SECONDS,
            default=int(defaults.get(CONF_STARTUP_BLOCK_SECONDS, DEFAULT_STARTUP_BLOCK_SECONDS)),
        ): _INT,
    })


def _coerce_options(user_input: dict[str, Any]) -> dict[str, Any]:
    out = dict(user_input)
    if CONF_STARTUP_BLOCK_SECONDS in out and out[CONF_STARTUP_BLOCK_SECONDS] is not None:
        out[CONF_STARTUP_BLOCK_SECONDS] = int(out[CONF_STARTUP_BLOCK_SECONDS])
    return out


class BlindPolicyConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._profile: str = DEFAULT_PROFILE_ROUTE
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        # Single-Instance je Profil-Route.
        if user_input is not None:
            self._profile = user_input[CONF_PROFILE]
            await self.async_set_unique_id(f"{DOMAIN}_{self._profile}")
            self._abort_if_unique_id_configured()
            self._data[CONF_PROFILE] = self._profile
            return await self.async_step_sources()
        return self.async_show_form(
            step_id="user", data_schema=_profile_schema(DEFAULT_PROFILE_ROUTE)
        )

    async def async_step_sources(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_options()
        defaults = _prefilled_sources(self._profile, self._data, self.hass)
        return self.async_show_form(step_id="sources", data_schema=_sources_schema(defaults))

    async def async_step_options(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(_coerce_options(user_input))
            title = f"{PROFILE_LABELS.get(self._profile, 'Benni')} Blind Policy"
            return self.async_create_entry(title=title, data=self._data)
        return self.async_show_form(step_id="options", data_schema=_options_schema(self._data))

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return BlindPolicyOptionsFlow(entry)


class BlindPolicyOptionsFlow(OptionsFlow):
    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry

    def _defaults(self) -> dict[str, Any]:
        return {**self._entry.data, **self._entry.options}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return self.async_show_menu(step_id="init", menu_options=["sources", "options"])

    async def async_step_sources(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data={**self._entry.options, **user_input})
        return self.async_show_form(
            step_id="sources", data_schema=_sources_schema(self._defaults())
        )

    async def async_step_options(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title="", data={**self._entry.options, **_coerce_options(user_input)}
            )
        return self.async_show_form(
            step_id="options", data_schema=_options_schema(self._defaults())
        )
