"""Blind-Policy-Coordinator (Single-Instance pro Config-Entry).

Hält den gesamten persistenten State, den die pure Engine (policy.py) nicht
kennen kann:

  * Lux-Gate-Hysterese (prev_gate),
  * Privacy-Latch (R-PL: Set/Reset/Recovery, Sonnenaufgang-Flanke),
  * Manual-Override + Override-Warden (R-OW: Race-Echo, ±3%, 5-Min-Sweep),
  * Writing-Active-Flag (R-MO: Fahrt + 5s Grace, 90s Timeout),
  * gated Apply auf das Cover (apply_enabled = Shadow-Master).

Eigenständige Helfer-Booleans (privacy_bed, alarm_wakeup) leben hier und werden
über Switch-Entities von außen (Hue Dimmer / Wecker-Modul) gesetzt.
"""
from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

try:  # pragma: no cover - nur auf älteren Stubs nicht vorhanden
    from homeassistant.helpers.start import async_at_started
except Exception:  # pragma: no cover
    async_at_started = None  # type: ignore[assignment]

from . import policy
from .const import (
    CONF_APPLY_ENABLED,
    CONF_BLIND_MASTER,
    CONF_BIO_STATE,
    CONF_COVER_ENTITY,
    CONF_DAY_CONTEXT,
    CONF_DAY_STATE,
    CONF_GAMING_SOURCE,
    CONF_INVERT_POSITION,
    CONF_LUX,
    CONF_MEDIA_SCENARIO,
    CONF_OUTDOOR_TEMP,
    CONF_POSITION_PROFILE,
    CONF_POSITION_PROFILE_INVERTED,
    CONF_PRESENCE_HOUSEHOLD,
    CONF_PROFILE,
    CONF_STARTUP_BLOCK_SECONDS,
    CONF_SUN,
    CONF_WEATHER_CONDITION,
    CONF_WINDOW_OPEN,
    CORE_OPENINGS_MASTER_ENTITY,
    CORE_WINDOW_OPEN_ATTRIBUTE,
    DATA_SKIP_RELOAD_COUNT,
    DEFAULT_APPLY_ENABLED,
    DEFAULT_INVERT_POSITION,
    DEFAULT_POSITION_PROFILE,
    DEFAULT_POSITION_PROFILE_INVERTED,
    DEFAULT_PROFILE_ROUTE,
    DEFAULT_STARTUP_BLOCK_SECONDS,
    DOMAIN,
    RECENT_APPLY_GUARD_SECONDS,
    UPDATE_INTERVAL_SECONDS,
    WARDEN_RACE_ECHO_SECONDS,
    WARDEN_SWEEP_INTERVAL_SECONDS,
    WRITING_GRACE_SECONDS,
    WRITING_TIMEOUT_SECONDS,
)
from .storage import make_store

_LOGGER = logging.getLogger(__name__)


def _bool_state(s: str | None) -> bool | None:
    if s is None or s in ("unknown", "unavailable"):
        return None
    return s.lower() in ("on", "true", "1", "open", "home", "active", "playing", "unsafe")


def _float_or_none(s: str | None) -> float | None:
    if s in (None, "", "unknown", "unavailable"):
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


class BlindPolicyCoordinator:
    """Eine Instanz pro Config-Entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store = make_store(hass, entry.entry_id)
        self._unsub: list[CALLBACK_TYPE] = []
        self._listeners: list[CALLBACK_TYPE] = []

        self._started_at = time.monotonic()
        self._ha_started = False
        self._startup_unsub: CALLBACK_TYPE | None = None

        # --- persistenter / abgeleiteter State ---
        self._prev_gate: bool | None = None
        self._privacy_latch = False
        self._privacy_bed = False
        self._alarm_wakeup = False
        self._manual_override = False
        self._override_set_ts: float | None = None      # monotonic
        # Expliziter Manual-Override aus dem Panel (Position oder Modus). Hält bis
        # zur nächsten Bio-Sleep-Phase / Fenster-Safety / "Override löschen" — der
        # 5-Min-Warden-Sweep räumt ihn NICHT (der ist nur für auto-erkannte Eingriffe).
        self._manual_explicit = False
        self._manual_mode: str | None = None
        self._manual_target: int | None = None
        self._writing_active = False
        self._writing_off_ts: float | None = None        # monotonic (Race-Echo)
        self._writing_release_unsub: CALLBACK_TYPE | None = None
        self._writing_timeout_unsub: CALLBACK_TYPE | None = None
        self._last_apply_ts = 0.0
        self._last_target: int | None = None

        self._prev_day_state: str | None = None
        self._prev_bio: str | None = None
        self._prev_sun_above: bool | None = None

        self._last_decision: policy.Decision | None = None

    # ----- options / profile -----
    @property
    def _opts(self) -> dict[str, Any]:
        return {**self.entry.data, **self.entry.options}

    def _opt(self, key: str, default: Any = None) -> Any:
        return self._opts.get(key, default)

    @property
    def profile_route(self) -> str:
        return self._opt(CONF_PROFILE, DEFAULT_PROFILE_ROUTE)

    @property
    def blind_master_entity(self) -> str | None:
        return self._opt(CONF_BLIND_MASTER)

    def _has_blind_master_state(self) -> bool:
        eid = self.blind_master_entity
        return bool(eid) and self.hass.states.get(eid) is not None

    @property
    def cover_entity(self) -> str | None:
        if self._has_blind_master_state():
            master_cover = self._master_attr("cover_entity_id")
            if isinstance(master_cover, str) and master_cover:
                return master_cover
        return self._opt(CONF_COVER_ENTITY)

    @property
    def apply_enabled(self) -> bool:
        return bool(self._opt(CONF_APPLY_ENABLED, DEFAULT_APPLY_ENABLED))

    @property
    def startup_block_seconds(self) -> int:
        return int(self._opt(CONF_STARTUP_BLOCK_SECONDS, DEFAULT_STARTUP_BLOCK_SECONDS))

    @property
    def invert_position(self) -> bool:
        """True = physische Cover-Achse gespiegelt (0↔100) gegenüber der Policy."""
        return bool(self._opt(CONF_INVERT_POSITION, DEFAULT_INVERT_POSITION))

    @property
    def position_profile(self) -> dict[str, int]:
        raw = self._opt(CONF_POSITION_PROFILE) or {}
        merged = {**DEFAULT_POSITION_PROFILE, **(raw if isinstance(raw, dict) else {})}
        return merged

    @property
    def position_profile_inverted(self) -> dict[str, int]:
        raw = self._opt(CONF_POSITION_PROFILE_INVERTED) or {}
        merged = {**DEFAULT_POSITION_PROFILE_INVERTED, **(raw if isinstance(raw, dict) else {})}
        return merged

    @property
    def active_position_profile(self) -> dict[str, int]:
        """Aktives Profil je nach Schalter — zwei UNABHÄNGIGE Wertesätze, kein Mirror.
        Der gewählte Wert ist die direkte Geräteposition."""
        return self.position_profile_inverted if self.invert_position else self.position_profile

    # ----- öffentliche Status-Accessoren (Entities/Panel) -----
    @property
    def last_decision(self) -> policy.Decision | None:
        return self._last_decision

    @property
    def gate_on(self) -> bool:
        return bool(self._prev_gate)

    @property
    def privacy_latch_active(self) -> bool:
        return self._privacy_latch

    @property
    def privacy_bed_active(self) -> bool:
        return self._privacy_bed

    @property
    def alarm_wakeup_active(self) -> bool:
        return self._alarm_wakeup

    @property
    def manual_override_active(self) -> bool:
        return self._manual_override

    @property
    def manual_explicit(self) -> bool:
        return self._manual_explicit

    @property
    def manual_mode(self) -> str | None:
        return self._manual_mode

    @property
    def manual_target(self) -> int | None:
        return self._manual_target

    @property
    def writing_active(self) -> bool:
        return self._writing_active

    @property
    def cover_position_raw(self) -> float | None:
        """Rohe Geräteposition. Mit dem Zwei-Profile-Modell ist das zugleich die
        aktive Achse (das gewählte Profil schreibt direkt, kein Mirror)."""
        return self._cover_position()

    def _startup_ready(self) -> bool:
        if not self._ha_started:
            return False
        return (time.monotonic() - self._started_at) >= self.startup_block_seconds

    @property
    def startup_ready(self) -> bool:
        return self._startup_ready()

    # ----- lifecycle -----
    @callback
    def async_start(self) -> None:
        if async_at_started is not None:
            self._unsub.append(async_at_started(self.hass, self._on_started))
        elif self.hass.is_running:
            self._on_started(None)
        else:
            self._unsub.append(
                self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, self._on_started)
            )

        watch: set[str] = set()
        if self.blind_master_entity:
            watch.add(self.blind_master_entity)
        else:
            for key in (
                CONF_WINDOW_OPEN, CONF_BIO_STATE, CONF_DAY_STATE, CONF_DAY_CONTEXT,
                CONF_PRESENCE_HOUSEHOLD, CONF_LUX, CONF_SUN, CONF_MEDIA_SCENARIO,
                CONF_GAMING_SOURCE, CONF_WEATHER_CONDITION, CONF_OUTDOOR_TEMP,
            ):
                v = self._opt(key)
                if isinstance(v, str) and v:
                    watch.add(v)
            if self.cover_entity:
                watch.add(self.cover_entity)
        if watch:
            self._unsub.append(
                async_track_state_change_event(self.hass, list(watch), self._on_state_change)
            )
        self._unsub.append(
            async_track_time_interval(
                self.hass, self._on_interval, timedelta(seconds=UPDATE_INTERVAL_SECONDS)
            )
        )

    @callback
    def async_stop(self) -> None:
        for unsub in self._unsub:
            unsub()
        self._unsub.clear()
        for unsub in (self._startup_unsub, self._writing_release_unsub, self._writing_timeout_unsub):
            if unsub is not None:
                unsub()
        self._startup_unsub = None
        self._writing_release_unsub = None
        self._writing_timeout_unsub = None

    @callback
    def _on_started(self, _event) -> None:
        self._ha_started = True
        self._started_at = time.monotonic()
        self._schedule_startup_expiry()
        # Recovery: Latch beim Start setzen, falls Bedingung bereits erfüllt.
        ctx = self.build_context()
        if not self._privacy_latch and policy.privacy_latch_recovery(ctx.day_state, ctx.lux):
            self._privacy_latch = True
            self._privacy_bed = False
        self.hass.async_create_task(self.async_evaluate())

    def _schedule_startup_expiry(self) -> None:
        if self._startup_unsub is not None:
            self._startup_unsub()
        seconds = max(0, int(self.startup_block_seconds))

        @callback
        def _fire(_now) -> None:
            self._startup_unsub = None
            self.hass.async_create_task(self.async_evaluate())

        self._startup_unsub = async_call_later(self.hass, seconds + 1, _fire)

    @callback
    def _on_interval(self, _now) -> None:
        self.hass.async_create_task(self.async_evaluate())

    @callback
    def _on_state_change(self, event: Event) -> None:
        eid = event.data.get("entity_id")
        if eid == self.cover_entity or eid == self.blind_master_entity:
            self._detect_manual_override(event)
        self.hass.async_create_task(self.async_evaluate())

    # ----- persistence -----
    async def async_load(self) -> None:
        raw = await self._store.async_load() or {}
        self._prev_gate = raw.get("prev_gate")
        self._privacy_latch = bool(raw.get("privacy_latch", False))
        self._privacy_bed = bool(raw.get("privacy_bed", False))
        self._alarm_wakeup = bool(raw.get("alarm_wakeup", False))
        self._manual_override = bool(raw.get("manual_override", False))
        self._manual_explicit = bool(raw.get("manual_explicit", False))
        self._manual_mode = raw.get("manual_mode")
        self._manual_target = raw.get("manual_target")
        if self._manual_override:
            self._override_set_ts = time.monotonic()
        self._prev_day_state = raw.get("prev_day_state")
        self._prev_bio = raw.get("prev_bio")

    async def _async_save(self) -> None:
        await self._store.async_save({
            "prev_gate": self._prev_gate,
            "privacy_latch": self._privacy_latch,
            "privacy_bed": self._privacy_bed,
            "alarm_wakeup": self._alarm_wakeup,
            "manual_override": self._manual_override,
            "manual_explicit": self._manual_explicit,
            "manual_mode": self._manual_mode,
            "manual_target": self._manual_target,
            "prev_day_state": self._prev_day_state,
            "prev_bio": self._prev_bio,
            "last_decision": self._last_decision.as_dict() if self._last_decision else None,
        })

    # ----- context -----
    def _master_attr(self, attr: str) -> Any:
        eid = self._opt(CONF_BLIND_MASTER)
        if not eid:
            return None
        st = self.hass.states.get(eid)
        if st is None or st.state in ("unknown", "unavailable"):
            return None
        return st.attributes.get(attr)

    def _read(self, key: str) -> str | None:
        master_attrs = {
            CONF_BIO_STATE: "bio_state",
            CONF_DAY_STATE: "day_state",
            CONF_DAY_CONTEXT: "day_context",
            CONF_PRESENCE_HOUSEHOLD: "presence_household",
            CONF_LUX: "lux",
            CONF_MEDIA_SCENARIO: "media_scenario",
            CONF_GAMING_SOURCE: "gaming_source",
            CONF_WEATHER_CONDITION: "weather_condition",
            CONF_OUTDOOR_TEMP: "outdoor_temp",
        }
        if self._has_blind_master_state():
            if key == CONF_WINDOW_OPEN:
                value = self._master_attr("window_open")
                if isinstance(value, bool):
                    return "on" if value else "off"
                opening = self._master_attr("opening_state")
                if opening in ("closed", "open", "tilted"):
                    return "on" if opening == "open" else "off"
                return None
            attr = master_attrs.get(key)
            if attr:
                value = self._master_attr(attr)
                if value in (None, "", "unknown", "unavailable"):
                    return None
                return str(value)

        eid = self._opt(key)
        if not eid:
            return None
        st = self.hass.states.get(eid)
        if st is None or st.state in ("unknown", "unavailable"):
            return None
        if key == CONF_WINDOW_OPEN and eid == CORE_OPENINGS_MASTER_ENTITY:
            value = st.attributes.get(CORE_WINDOW_OPEN_ATTRIBUTE)
            if value in ("closed", "open", "tilted"):
                return "on" if value == "open" else "off"
            return None
        return st.state

    def _sun_elevation(self) -> float | None:
        if self._has_blind_master_state():
            return _float_or_none(self._master_attr("sun_elevation"))
        eid = self._opt(CONF_SUN)
        if not eid:
            return None
        st = self.hass.states.get(eid)
        if st is None:
            return None
        return _float_or_none(st.attributes.get("elevation"))

    def build_context(self) -> policy.Context:
        return policy.Context(
            window_open=_bool_state(self._read(CONF_WINDOW_OPEN)),
            bio_state=self._read(CONF_BIO_STATE),
            day_state=self._read(CONF_DAY_STATE),
            day_context=self._read(CONF_DAY_CONTEXT),
            presence_household=self._read(CONF_PRESENCE_HOUSEHOLD),
            privacy_bed=self._privacy_bed,
            privacy_latch=self._privacy_latch,
            alarm_wakeup=self._alarm_wakeup,
            media_scenario=self._read(CONF_MEDIA_SCENARIO),
            gaming_source=self._read(CONF_GAMING_SOURCE),
            lux=_float_or_none(self._read(CONF_LUX)),
            sun_elevation=self._sun_elevation(),
            weather_condition=self._read(CONF_WEATHER_CONDITION),
            outdoor_temp=_float_or_none(self._read(CONF_OUTDOOR_TEMP)),
            now_minutes=self._now_minutes(),
        )

    @staticmethod
    def _now_minutes() -> int:
        now = dt_util.now()
        return now.hour * 60 + now.minute

    # ----- cover helpers -----
    def _cover_position(self) -> float | None:
        if self._has_blind_master_state():
            return _float_or_none(self._master_attr("current_cover_position"))
        if not self.cover_entity:
            return None
        st = self.hass.states.get(self.cover_entity)
        if st is None:
            return None
        return _float_or_none(st.attributes.get("current_position"))

    def _cover_moving(self) -> bool:
        if self._has_blind_master_state():
            value = self._master_attr("cover_running")
            if isinstance(value, bool):
                return value
            return str(value).lower() in ("on", "true", "1")
        if not self.cover_entity:
            return False
        st = self.hass.states.get(self.cover_entity)
        return bool(st and st.state in ("opening", "closing"))

    # ----- R-PL Privacy-Latch -----
    def _update_privacy_latch(self, ctx: policy.Context) -> None:
        # Sonnenaufgangs-Flanke (below → above_horizon).
        sun_st = self.hass.states.get(self._opt(CONF_SUN)) if self._opt(CONF_SUN) else None
        if self._has_blind_master_state():
            sun_state = self._master_attr("sun_state")
            sun_st = None
        else:
            sun_state = sun_st.state if sun_st is not None else None
        sun_above = None
        if sun_state in ("above_horizon", "below_horizon"):
            sun_above = sun_state == "above_horizon"
        sunrise_crossed = bool(self._prev_sun_above is False and sun_above is True)

        if not self._privacy_latch:
            if policy.privacy_latch_should_set(ctx.day_state, self._prev_day_state, ctx.lux):
                self._privacy_latch = True
                # Seiteneffekt R-PL: Privacy-Bed-Reset (obsolet beim Latch-Set).
                self._privacy_bed = False
        else:
            if policy.privacy_latch_should_reset(ctx.bio_state, self._prev_bio, sunrise_crossed):
                self._privacy_latch = False

        self._prev_day_state = ctx.day_state
        self._prev_bio = ctx.bio_state
        if sun_above is not None:
            self._prev_sun_above = sun_above

    # ----- R-MO / R-OW Manual-Override + Warden -----
    @callback
    def _detect_manual_override(self, _event: Event) -> None:
        """Cover-State-Change außerhalb unseres Schreibfensters = Hand-Eingriff."""
        now = time.monotonic()
        if self._writing_active:
            return
        if (now - self._last_apply_ts) <= RECENT_APPLY_GUARD_SECONDS:
            return  # eigener Nachlauf-Echo
        if self._cover_moving():
            return  # Bewegung wird erst beim Stillstand bewertet
        if self._manual_override:
            return
        # Neuer Override — Sofortprüfung des Wardens (Race-Echo / schon auf Ziel).
        writing_recently_off = (
            self._writing_off_ts is not None
            and (now - self._writing_off_ts) <= WARDEN_RACE_ECHO_SECONDS
        )
        at_target = policy.position_within_tolerance(self._cover_position(), self._last_target)
        if policy.override_warden_immediate_clear(writing_recently_off, at_target):
            return  # false-positive — gar nicht erst setzen
        self._manual_override = True
        self._override_set_ts = now

    def _warden_sweep(self) -> None:
        """Periodischer Sweep (Alter>5min via Prädikat gegated)."""
        if self._manual_explicit:
            return  # expliziter Panel-Override hält bis Sleep/Fenster/Clear
        if not self._manual_override or self._override_set_ts is None:
            return
        age = time.monotonic() - self._override_set_ts
        at_target = policy.position_within_tolerance(self._cover_position(), self._last_target)
        if policy.override_warden_sweep_clear(age, self._cover_moving(), at_target):
            self._manual_override = False
            self._override_set_ts = None

    def _reset_override_on_sleep(self, ctx: policy.Context) -> None:
        """R-MO: Override löst sich beim Eintritt in die nächste Bio-Sleep-Phase.

        Der Reset läuft vor ``_update_privacy_latch``, solange ``self._prev_bio`` noch
        den Vorzyklus-Wert enthält. Dadurch kann die Sleep-Entscheidung im selben
        Evaluate direkt wieder anwenden.
        """
        if self._manual_override and policy.manual_override_should_reset_on_sleep(
            ctx.bio_state, self._prev_bio
        ):
            self._clear_manual_state()

    def _clear_manual_state(self) -> None:
        """Override + expliziten Manual-Ziel-State zurücksetzen (Auto übernimmt wieder)."""
        self._manual_override = False
        self._override_set_ts = None
        self._manual_explicit = False
        self._manual_mode = None
        self._manual_target = None

    # ----- evaluation -----
    async def async_evaluate(self) -> policy.Decision:
        ctx = self.build_context()

        # Override-Reset beim Eintritt in Bio-Sleep (vor Latch-Update, das prev_bio
        # fortschreibt) + periodischer Sweep.
        self._reset_override_on_sleep(ctx)
        self._warden_sweep()

        # Privacy-Latch aktualisieren (schreibt prev_day_state/prev_bio/sun fort).
        self._update_privacy_latch(ctx)
        # Context nach Latch-Update neu lesen (privacy_latch könnte gekippt sein).
        ctx = self.build_context()

        gate = policy.lux_gate(
            ctx.lux, self._prev_gate,
            sun_elevation=ctx.sun_elevation, day_state=ctx.day_state,
        )
        self._prev_gate = gate

        decision = policy.decide(
            ctx, self.active_position_profile,
            gate_on=gate,
            startup_ready=self._startup_ready(),
            apply_enabled=self.apply_enabled,
            manual_override_active=self._manual_override,
        )

        # R1 absolut: window_open darf einen Override löschen (auch expliziten).
        if decision.manual_override_cleared:
            self._clear_manual_state()

        self._last_decision = decision

        if decision.apply_allowed and decision.target_position is not None and self.cover_entity:
            await self._apply(decision.target_position)

        await self._async_save()
        for cb in self._listeners:
            cb()
        return decision

    # ----- apply (gated, R-MO Writing-Active) -----
    async def _apply(self, target: int) -> None:
        # Ziel ist die direkte Geräteposition (aktives Profil hat sie schon gewählt).
        target = max(0, min(100, int(target)))
        current = self._cover_position()
        # Nichts tun, wenn das Rollo schon (≈) auf Ziel steht — verhindert
        # unnötige Fahrten + Writing-Flag-Churn.
        if current is not None and abs(current - target) < 1:
            return
        self._last_target = target
        self._last_apply_ts = time.monotonic()
        self._set_writing_active(True)
        try:
            await self.hass.services.async_call(
                "cover", "set_cover_position",
                {"entity_id": self.cover_entity, "position": target},
                blocking=False,
            )
        except Exception as err:  # noqa: BLE001 - ein Fehlversuch darf den Loop nicht killen
            _LOGGER.warning("blind_policy: set_cover_position failed: %s", err)
            self._set_writing_active(False)
            return
        # Writing-Flag nach Fahrt + Grace bzw. spätestens nach 90s Timeout lösen.
        self._schedule_writing_release()

    def _set_writing_active(self, value: bool) -> None:
        if value == self._writing_active:
            return
        self._writing_active = value
        if not value:
            self._writing_off_ts = time.monotonic()

    def _schedule_writing_release(self) -> None:
        for unsub in (self._writing_release_unsub, self._writing_timeout_unsub):
            if unsub is not None:
                unsub()
        self._writing_release_unsub = None

        @callback
        def _release(_now) -> None:
            self._writing_release_unsub = None
            # Erst lösen, wenn Cover steht; sonst kurz nachfassen.
            if self._cover_moving():
                self._writing_release_unsub = async_call_later(
                    self.hass, WRITING_GRACE_SECONDS, _release
                )
                return
            self._set_writing_active(False)
            for cb in self._listeners:
                cb()

        @callback
        def _timeout(_now) -> None:
            self._writing_timeout_unsub = None
            self._set_writing_active(False)
            for cb in self._listeners:
                cb()

        # Grace ab jetzt (deckt kurze Fahrten); harter 90s-Cap als Backstop.
        self._writing_release_unsub = async_call_later(
            self.hass, WRITING_GRACE_SECONDS, _release
        )
        self._writing_timeout_unsub = async_call_later(
            self.hass, WRITING_TIMEOUT_SECONDS, _timeout
        )

    # ----- service / switch surface -----
    async def async_apply_now(self) -> policy.Decision:
        return await self.async_evaluate()

    async def async_set_privacy_bed(self, value: bool) -> None:
        self._privacy_bed = bool(value)
        await self.async_evaluate()

    async def async_set_alarm_wakeup(self, value: bool) -> None:
        self._alarm_wakeup = bool(value)
        await self.async_evaluate()

    async def async_clear_manual_override(self) -> None:
        self._clear_manual_state()
        await self.async_evaluate()

    async def async_set_manual_position(self, position: int) -> None:
        """Panel: Rollo manuell auf x % fahren + Override halten (auch im Shadow)."""
        pos = max(0, min(100, int(position)))
        self._manual_override = True
        self._manual_explicit = True
        self._manual_mode = None
        self._manual_target = pos
        self._override_set_ts = time.monotonic()
        await self._apply(pos)          # direkter Fahrbefehl, unabhängig vom apply_enabled-Gate
        await self.async_evaluate()

    async def async_set_manual_decision(self, mode: str) -> None:
        """Panel: Policy manuell auf einen Modus zwingen (Position aus dem Profil)."""
        if mode not in DEFAULT_POSITION_PROFILE:
            return
        pos = policy._position(mode, self.active_position_profile)
        self._manual_override = True
        self._manual_explicit = True
        self._manual_mode = mode
        self._manual_target = pos
        self._override_set_ts = time.monotonic()
        if pos is not None:
            await self._apply(pos)
        await self.async_evaluate()

    async def async_set_manual_override(self, value: bool) -> None:
        self._manual_override = bool(value)
        self._override_set_ts = time.monotonic() if value else None
        await self.async_evaluate()

    async def async_set_apply_enabled(self, value: bool) -> None:
        self._skip_next_entry_reload()
        new_options = {**self.entry.options, CONF_APPLY_ENABLED: bool(value)}
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)
        await self.async_evaluate()

    async def async_set_invert_position(self, value: bool) -> None:
        """Cover-Achse spiegeln (umgekehrte Fahrtrichtung kompensieren)."""
        self._skip_next_entry_reload()
        new_options = {**self.entry.options, CONF_INVERT_POSITION: bool(value)}
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)
        await self.async_evaluate()

    @staticmethod
    def _clean_profile(profile: dict[str, int] | None) -> dict[str, int]:
        return {
            str(k): max(0, min(100, int(v)))
            for k, v in (profile or {}).items()
            if k in DEFAULT_POSITION_PROFILE
        }

    async def async_set_position_profile(
        self,
        normal: dict[str, int] | None = None,
        inverted: dict[str, int] | None = None,
    ) -> dict[str, dict[str, int]]:
        """Beide Profile (partiell) setzen — normal und/oder invertiert."""
        new_options = {**self.entry.options}
        if normal is not None:
            new_options[CONF_POSITION_PROFILE] = {
                **self.position_profile, **self._clean_profile(normal)
            }
        if inverted is not None:
            new_options[CONF_POSITION_PROFILE_INVERTED] = {
                **self.position_profile_inverted, **self._clean_profile(inverted)
            }
        self._skip_next_entry_reload()
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)
        await self.async_evaluate()
        return {
            "position_profile": self.position_profile,
            "position_profile_inverted": self.position_profile_inverted,
        }

    async def async_reset_position_profiles(self) -> dict[str, dict[str, int]]:
        """Beide Profile auf die Defaults (Normal + gespiegeltes Default) zurücksetzen."""
        self._skip_next_entry_reload()
        new_options = {
            **self.entry.options,
            CONF_POSITION_PROFILE: dict(DEFAULT_POSITION_PROFILE),
            CONF_POSITION_PROFILE_INVERTED: dict(DEFAULT_POSITION_PROFILE_INVERTED),
        }
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)
        await self.async_evaluate()
        return {
            "position_profile": self.position_profile,
            "position_profile_inverted": self.position_profile_inverted,
        }

    def _skip_next_entry_reload(self) -> None:
        data = self.hass.data.setdefault(DOMAIN, {})
        data[DATA_SKIP_RELOAD_COUNT] = int(data.get(DATA_SKIP_RELOAD_COUNT) or 0) + 1

    # ----- listeners -----
    def add_listener(self, cb: CALLBACK_TYPE) -> None:
        self._listeners.append(cb)

    def remove_listener(self, cb: CALLBACK_TYPE) -> None:
        if cb in self._listeners:
            self._listeners.remove(cb)


# ------------------------------------------------------------------- lookups
def coordinator_from_hass(hass: HomeAssistant, entry_id: str) -> BlindPolicyCoordinator | None:
    bucket = hass.data.get(DOMAIN, {}).get(entry_id)
    if isinstance(bucket, dict):
        from .const import DATA_COORDINATOR
        return bucket.get(DATA_COORDINATOR)
    return None


def all_coordinators(hass: HomeAssistant) -> list[BlindPolicyCoordinator]:
    from .const import DATA_COORDINATOR
    return [
        b[DATA_COORDINATOR]
        for b in hass.data.get(DOMAIN, {}).values()
        if isinstance(b, dict) and DATA_COORDINATOR in b
    ]
