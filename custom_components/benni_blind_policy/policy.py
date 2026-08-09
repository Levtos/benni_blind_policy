"""Pure Decision-Engine für die Blind-Policy (Wohnzimmer-Rollo) — HA-frei, voll testbar.

Implementiert das reviewte Lastenheft
``einhornzentrale/docs/lastenhefte/reviewed/rollo/`` 1:1:

  * ``lux_gate()``     — Schmitt-Trigger (20k/15k) mit Sonnenhöhe + Tagesphasen-Gate,
                         zustandsbehaftet via ``prev_gate`` (Hysterese hält der Coordinator).
  * ``ProtectionDemand`` — fusioniert Thermal und Glare vor der Policy-Auswahl.
  * ``evaluate_chain()`` — stateless Prioritätskette (R1..R9), liefert Gewinner + Trace.
  * ``decide()``       — Kette + Gating-Overlay (apply_enabled/startup/override/source).
  * Privacy-Latch- und Override-Warden-Prädikate (R-PL / R-OW) als pure Helfer,
    die der Coordinator mit seinem persistenten State füttert.

Strikte Trennung: ``decide`` ermittelt den *gewünschten* Modus + Position rein aus
dem Context; Gating setzt nur ``apply_allowed``/``blockers`` ohne den Modus zu
verändern (Phase-4-Shadow-Vergleich bleibt aussagekräftig). Einzige Ausnahme:
``window_open`` (R1) ist absolut, ignoriert Override + Startup-Block und darf einen
aktiven Manual-Override löschen.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .const import (
    BIO_AWAKE,
    BIO_SLEEP,
    BIO_WAKING,
    DAY_CONTEXT_WOCHENENDE,
    DEFAULT_HEAT_LUX_MIN,
    DEFAULT_POSITION_PROFILE,
    GAMING_NONE,
    GAMING_PC,
    GATE_CLOSE_LUX,
    GATE_DAY_STATES,
    GATE_OPEN_LUX,
    GATE_SUN_MIN_DEG,
    HEAT_TEMP_C,
    HOUSEHOLD_EMPTY,
    HOUSEHOLD_NOT_EMPTY,
    MODE_ALARM_WAKEUP,
    MODE_GLARE_PC,
    MODE_GLARE_TV,
    MODE_HEAT,
    MODE_OPEN,
    MODE_OPEN_WEEKDAY,
    MODE_OPEN_WEEKEND,
    MODE_PRIVACY,
    MODE_PRIVACY_BED,
    MODE_SLEEP,
    MODE_WINDOW_OPEN,
    PHASE_EARLY_MORNING,
    PHASE_EARLY_NIGHT,
    PHASE_LATE_EVENING,
    PHASE_LATE_NIGHT,
    PRIVACY_LATCH_LUX,
    SCENARIO_GAMING,
    SCENARIO_IDLE,
    SCENARIO_STREAMING,
    SCENARIO_TV,
    WARDEN_POSITION_TOLERANCE,
    WARDEN_SWEEP_MIN_AGE_SECONDS,
)

# Glare-Szenarien, in denen der TV-Stack blendet (TV/Streaming/Gaming außer PC).
TV_GLARE_SCENARIOS: frozenset[str] = frozenset({SCENARIO_TV, SCENARIO_STREAMING, SCENARIO_GAMING})


@dataclass(frozen=True)
class Context:
    """Snapshot aller Quell-Inputs für eine Entscheidung. None = unknown.

    Failure-Defaults (Lastenheft §2) werden in ``_normalized()`` angewandt, nicht
    hier — so bleibt der Roh-Context für den Debug-Sensor unverfälscht.
    """

    window_open: bool | None = None          # True = Flügel offen (Status 2)
    bio_state: str | None = None             # sleep / waking / awake
    day_state: str | None = None             # 8 Tagesphasen — Pflichtquelle
    day_context: str | None = None           # werktag / wochenende / frei
    presence_household: str | None = None    # leer / nicht_leer
    privacy_bed: bool = False                # input_boolean (Hue Dimmer)
    privacy_latch: bool = False              # Coordinator-State (R-PL)
    alarm_wakeup: bool = False               # Platzhalter Wecker-Modul (R4)
    media_scenario: str | None = None        # idle / tv / streaming / gaming / private_time
    gaming_source: str | None = None         # tv / pc / none
    lux: float | None = None                 # Außenhelligkeit
    sun_elevation: float | None = None       # Sonnenhöhe °
    weather_condition: str | None = None     # roh (sunny/rainy/…) — nur Diagnose/Glare-Kontext
    outdoor_temp: float | None = None        # °C; ≥ HEAT_TEMP_C ≙ Temperaturklasse ≥ 12
    now_minutes: int | None = None           # Minuten seit Mitternacht (für Open-Regeln)


@dataclass
class _Norm:
    """Failure-bereinigter Context (Lastenheft §2 Defaults)."""

    window_open: bool
    bio_state: str
    day_state: str | None
    day_context: str
    presence_household: str
    media_scenario: str
    gaming_source: str
    privacy_bed: bool
    privacy_latch: bool
    alarm_wakeup: bool
    lux: float | None
    sun_elevation: float | None
    weather_condition: str | None
    outdoor_temp: float | None
    now_minutes: int | None


def _normalized(ctx: Context) -> _Norm:
    return _Norm(
        # Fenster unknown → als offen behandeln (Sicherheit).
        window_open=True if ctx.window_open is None else bool(ctx.window_open),
        bio_state=ctx.bio_state or BIO_AWAKE,
        day_state=ctx.day_state,  # kein Fallback — Pflichtquelle
        day_context=ctx.day_context or DAY_CONTEXT_WOCHENENDE,
        presence_household=ctx.presence_household or HOUSEHOLD_NOT_EMPTY,
        media_scenario=ctx.media_scenario or SCENARIO_IDLE,
        gaming_source=ctx.gaming_source or GAMING_NONE,
        privacy_bed=bool(ctx.privacy_bed),
        privacy_latch=bool(ctx.privacy_latch),
        alarm_wakeup=bool(ctx.alarm_wakeup),
        lux=ctx.lux,
        sun_elevation=ctx.sun_elevation,
        weather_condition=ctx.weather_condition,
        outdoor_temp=ctx.outdoor_temp,
        now_minutes=ctx.now_minutes,
    )


@dataclass
class RuleEval:
    """Eine Zeile der Prioritätskette für den Decision-Trace (Frontend)."""

    rule: str          # R1 .. R9
    mode: str
    matched: bool
    position: int | None
    candidate: bool = True


@dataclass(frozen=True)
class ProtectionDemand:
    """Gemeinsame, nicht konkurrierende Schutzanforderung für Heat und Glare.

    Die Positionen sind bereits aus dem aktiven Positionsprofil abgeleitet und
    damit Gerätepositionen. Die Auswahl der stärker schließenden Anforderung
    erfolgt trotzdem über die erkannte Achsenrichtung, nicht über ein blindes
    ``min``/``max``.
    """

    thermal_active: bool
    glare_active: bool
    thermal_target_position: int | None
    glare_target_position: int | None
    effective_target_position: int | None
    effective_mode: str | None
    glare_mode: str | None = None
    reasons: tuple[str, ...] = ()
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @property
    def active(self) -> bool:
        return self.thermal_active or self.glare_active

    @property
    def thermal_target(self) -> int | None:
        """Kurzer Alias für interne Verbraucher und Diagnose."""
        return self.thermal_target_position

    @property
    def glare_target(self) -> int | None:
        """Kurzer Alias für interne Verbraucher und Diagnose."""
        return self.glare_target_position

    @property
    def effective_target(self) -> int | None:
        """Kurzer Alias für die fusionierte effektive Zielposition."""
        return self.effective_target_position

    def as_dict(self) -> dict[str, Any]:
        return {
            "thermal_active": self.thermal_active,
            "glare_active": self.glare_active,
            "thermal_target_position": self.thermal_target_position,
            "glare_target_position": self.glare_target_position,
            "effective_target_position": self.effective_target_position,
            "effective_mode": self.effective_mode,
            "glare_mode": self.glare_mode,
            "reasons": list(self.reasons),
            "diagnostics": dict(self.diagnostics),
        }


@dataclass
class Decision:
    mode: str
    target_position: int | None
    reason: str
    protection_demand: ProtectionDemand | None = None
    gate_on: bool = False
    blockers: list[str] = field(default_factory=list)
    manual_override_cleared: bool = False
    apply_allowed: bool = True
    trace: list[RuleEval] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "target_position": self.target_position,
            "reason": self.reason,
            "protection_demand": (
                self.protection_demand.as_dict() if self.protection_demand else None
            ),
            "gate_on": self.gate_on,
            "blockers": list(self.blockers),
            "manual_override_cleared": self.manual_override_cleared,
            "apply_allowed": self.apply_allowed,
            "trace": [
                {
                    "rule": e.rule,
                    "mode": e.mode,
                    "matched": e.matched,
                    "position": e.position,
                    "candidate": e.candidate,
                }
                for e in self.trace
            ],
        }


# --------------------------------------------------------------------------- #
# R-G — Lux-Gate (Schmitt-Trigger, Lastenheft §R-G)
# --------------------------------------------------------------------------- #
def lux_gate(
    lux: float | None,
    prev_gate: bool | None,
    *,
    sun_elevation: float | None,
    day_state: str | None,
) -> bool:
    """True = Gate offen (Glare-Schutz erlaubt).

    Vollständige Bedingung: Schmitt-Trigger (20k/15k) UND Sonnenhöhe > 5° UND
    Day State in {early_morning, late_morning, forenoon, afternoon}. Grauzone
    15–20k lx hält den vorherigen Zustand (``this.state``-basiert); Lux unknown
    hält ebenfalls. Heat nutzt dieses Gate NICHT.
    """
    # Transiente HA-Ausfälle dürfen keinen gültigen Gate-Zustand löschen. Eine
    # Neubewertung erfolgt beim nächsten State-Event mit vollständigen Inputs.
    try:
        numeric_sun = sun_elevation is not None and math.isfinite(float(sun_elevation))
        numeric_lux = lux is not None and math.isfinite(float(lux))
    except (TypeError, ValueError):
        numeric_sun = False
        numeric_lux = False
    if not numeric_sun or not numeric_lux or day_state is None:
        return bool(prev_gate)
    sun_value = float(sun_elevation)
    lux_value = float(lux)
    if sun_value <= GATE_SUN_MIN_DEG:
        return False
    if day_state not in GATE_DAY_STATES:
        return False
    if lux_value > GATE_OPEN_LUX:
        return True
    if lux_value < GATE_CLOSE_LUX:
        return False
    return bool(prev_gate)


# --------------------------------------------------------------------------- #
# Schutzanforderung und Prioritätskette (Issue #9)
# --------------------------------------------------------------------------- #
def _position(mode: str, profile: dict[str, int]) -> int | None:
    raw = profile.get(mode, DEFAULT_POSITION_PROFILE.get(mode))
    if raw is None:
        return None
    try:
        return max(0, min(100, int(raw)))
    except (TypeError, ValueError):
        return None


def _merged_profile(position_profile: dict[str, int] | None) -> dict[str, int]:
    return {**DEFAULT_POSITION_PROFILE, **(position_profile or {})}


def _higher_values_are_more_open(profile: dict[str, int]) -> bool:
    """Ermittelt die Richtung der aktiven Geräteachse aus Open vs. Privacy."""
    open_position = _position(MODE_OPEN, profile)
    closed_position = _position(MODE_PRIVACY, profile)
    if open_position is None or closed_position is None or open_position == closed_position:
        return True
    return open_position > closed_position


def _closing_rank(position: int | None, profile: dict[str, int]) -> float | None:
    """Liefert einen vergleichbaren Rang; ein höherer Rang schließt stärker."""
    if position is None:
        return None
    open_position = _position(MODE_OPEN, profile)
    if open_position is None:
        return None
    if _higher_values_are_more_open(profile):
        return float(open_position - position)
    return float(position - open_position)


def _valid_temperature(value: float | None) -> bool:
    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _thermal_state(
    n: _Norm,
    previous_thermal_active: bool | None,
) -> tuple[bool, str]:
    """Thermal ausschließlich aus dem kanonischen Temperatureingang ableiten."""
    if not _valid_temperature(n.outdoor_temp):
        if previous_thermal_active:
            return True, "thermal:temperature_unavailable — letzter gültiger Zustand gehalten"
        return False, "thermal:temperature_unavailable — kein gültiger Zustand erzeugt"
    if float(n.outdoor_temp) >= HEAT_TEMP_C:
        return True, f"thermal:temperature >= {HEAT_TEMP_C} °C"
    return False, f"thermal:temperature < {HEAT_TEMP_C} °C"


def _heat_active(
    n: _Norm,
    heat_lux_min: int = DEFAULT_HEAT_LUX_MIN,
    *,
    previous_thermal_active: bool | None = None,
) -> bool:
    """Kompatibilitäts-Wrapper: Heat hängt nicht mehr von Lux oder Sonne ab."""
    del heat_lux_min  # Legacy-Parameter bleibt für alte interne Aufrufer erhalten.
    return _thermal_state(n, previous_thermal_active)[0]


def _sleep_active(n: _Norm) -> bool:
    """Bio sleep, Nachtphasen, oder early_morning+sleep. `waking` zählt nicht."""
    return (
        n.bio_state == BIO_SLEEP
        or n.day_state in (PHASE_EARLY_NIGHT, PHASE_LATE_NIGHT)
        or (n.day_state == PHASE_EARLY_MORNING and n.bio_state == BIO_SLEEP)
    )


def _build_protection_demand(
    n: _Norm,
    gate_on: bool,
    profile: dict[str, int],
    previous_thermal_active: bool | None,
) -> ProtectionDemand:
    thermal_active, thermal_reason = _thermal_state(n, previous_thermal_active)

    glare_tv_active = bool(
        gate_on
        and n.media_scenario in TV_GLARE_SCENARIOS
        and n.gaming_source != GAMING_PC
        and n.bio_state != BIO_SLEEP
    )
    glare_pc_active = bool(
        gate_on
        and n.media_scenario == SCENARIO_GAMING
        and n.gaming_source == GAMING_PC
        and n.bio_state != BIO_SLEEP
    )
    glare_mode = MODE_GLARE_PC if glare_pc_active else MODE_GLARE_TV if glare_tv_active else None

    thermal_target = _position(MODE_HEAT, profile)
    glare_target = _position(glare_mode, profile) if glare_mode else None
    candidates: list[tuple[str, int | None]] = []
    if thermal_active:
        candidates.append((MODE_HEAT, thermal_target))
    if glare_mode is not None:
        candidates.append((glare_mode, glare_target))

    effective_mode: str | None = None
    effective_target: int | None = None
    if candidates:
        effective_mode, effective_target = candidates[0]
        effective_rank = _closing_rank(effective_target, profile)
        for candidate_mode, candidate_target in candidates[1:]:
            candidate_rank = _closing_rank(candidate_target, profile)
            if (
                candidate_rank is not None
                and (effective_rank is None or candidate_rank > effective_rank)
            ):
                effective_mode, effective_target = candidate_mode, candidate_target
                effective_rank = candidate_rank

    reasons: list[str] = [thermal_reason]
    if glare_tv_active:
        reasons.append("glare:tv — Lux-Gate und TV-Stack aktiv")
    elif glare_pc_active:
        reasons.append("glare:pc — Lux-Gate und PC-Gaming aktiv")
    else:
        reasons.append("glare:inactive")
    if effective_mode is None:
        reasons.append("effective:none")
    elif thermal_active and glare_mode is not None:
        reasons.append(f"fusion:effective={effective_mode} — stärker schließend")
    else:
        reasons.append(f"effective={effective_mode}")

    axis = "open_high" if _higher_values_are_more_open(profile) else "open_low"
    diagnostics = {
        "thermal_input": n.outdoor_temp,
        "thermal_input_available": _valid_temperature(n.outdoor_temp),
        "thermal_threshold_c": HEAT_TEMP_C,
        "thermal_state_held": not _valid_temperature(n.outdoor_temp)
        and bool(previous_thermal_active),
        "glare_gate_on": bool(gate_on),
        "glare_tv_active": glare_tv_active,
        "glare_pc_active": glare_pc_active,
        "glare_lux": n.lux,
        "glare_sun_elevation": n.sun_elevation,
        "position_axis": axis,
        "thermal_target_position": thermal_target,
        "glare_target_position": glare_target,
        "effective_target_position": effective_target,
    }
    return ProtectionDemand(
        thermal_active=thermal_active,
        glare_active=glare_tv_active or glare_pc_active,
        thermal_target_position=thermal_target,
        glare_target_position=glare_target,
        effective_target_position=effective_target,
        effective_mode=effective_mode,
        glare_mode=glare_mode,
        reasons=tuple(reasons),
        diagnostics=diagnostics,
    )


def evaluate_protection_demand(
    ctx: Context,
    *,
    gate_on: bool,
    position_profile: dict[str, int] | None = None,
    previous_thermal_active: bool | None = None,
    heat_lux_min: int = DEFAULT_HEAT_LUX_MIN,
) -> ProtectionDemand:
    """Bewertet Thermal und Glare unabhängig und fusioniert sie einmalig."""
    del heat_lux_min  # Legacy-Option darf Thermal nicht mehr beeinflussen.
    return _build_protection_demand(
        _normalized(ctx),
        gate_on,
        _merged_profile(position_profile),
        previous_thermal_active,
    )


# Lesbarer Alias für interne/diagnostische Verbraucher.
protection_demand = evaluate_protection_demand


def evaluate_chain(
    n: _Norm,
    gate_on: bool,
    heat_lux_min: int = DEFAULT_HEAT_LUX_MIN,
    *,
    position_profile: dict[str, int] | None = None,
    previous_thermal_active: bool | None = None,
    demand: ProtectionDemand | None = None,
) -> tuple[RuleEval, list[RuleEval]]:
    """Wertet die bestehende Prioritätskette mit einer Schutzregel aus.

    Returns (winner, full_trace). Erste zutreffende Regel (höchste Priorität)
    gewinnt; der Trace enthält ALLE Regeln mit ihrem matched-Flag (für das Panel).
    R7/R8 bleiben als nicht konkurrierende Glare-Diagnosezeilen sichtbar; die
    tatsächliche Schutzentscheidung kommt ausschließlich aus R6/ProtectionDemand.
    """
    del heat_lux_min  # Legacy-Parameter; Schutz wird zentral fusioniert.
    profile = _merged_profile(position_profile)
    demand = demand or _build_protection_demand(
        n, gate_on, profile, previous_thermal_active
    )
    protection_mode = demand.effective_mode or "protection"
    rules: list[RuleEval] = [
        RuleEval("R1", MODE_WINDOW_OPEN, bool(n.window_open), _position(MODE_WINDOW_OPEN, profile)),
        RuleEval("R2", MODE_PRIVACY_BED, bool(n.privacy_bed), _position(MODE_PRIVACY_BED, profile)),
        RuleEval(
            "R3", MODE_ALARM_WAKEUP, bool(n.alarm_wakeup),
            _position(MODE_ALARM_WAKEUP, profile),
        ),
        RuleEval("R4", MODE_SLEEP, _sleep_active(n), _position(MODE_SLEEP, profile)),
        RuleEval(
            "R5", MODE_PRIVACY,
            n.presence_household == HOUSEHOLD_EMPTY or n.privacy_latch,
            _position(MODE_PRIVACY, profile),
        ),
        RuleEval(
            "R6", protection_mode, demand.active,
            demand.effective_target_position,
        ),
        # Nur Diagnose: Diese Einträge sind keine zusätzlichen Policy-Zweige.
        RuleEval(
            "R7", MODE_GLARE_TV, demand.glare_mode == MODE_GLARE_TV,
            _position(MODE_GLARE_TV, profile), candidate=False,
        ),
        RuleEval(
            "R8", MODE_GLARE_PC, demand.glare_mode == MODE_GLARE_PC,
            _position(MODE_GLARE_PC, profile), candidate=False,
        ),
        RuleEval("R9", MODE_OPEN, True, _position(MODE_OPEN, profile)),  # Fallback
    ]

    trace: list[RuleEval] = []
    winner: RuleEval | None = None
    for ev in rules:
        if winner is None and ev.matched and ev.candidate:
            winner = ev
        trace.append(ev)
    assert winner is not None  # R9 ist immer True
    return winner, trace


_REASONS: dict[str, str] = {
    MODE_WINDOW_OPEN: "window_open: Fenster offen — absolute Top-Regel",
    MODE_PRIVACY_BED: "privacy_bed: manueller Bett-Modus",
    MODE_PRIVACY: "privacy: Haushalt leer oder Privacy-Latch aktiv",
    MODE_ALARM_WAKEUP: "alarm_wakeup: Wecker-Platzhalter aktiv",
    MODE_OPEN_WEEKDAY: "open_weekday: natürlicher Wecker werktags",
    MODE_OPEN_WEEKEND: "open_weekend: natürlicher Wecker wochenends/frei",
    MODE_SLEEP: "sleep: Bio sleep oder Nachtphase",
    MODE_HEAT: f"heat: thermischer Hitzeschutz ab {HEAT_TEMP_C} °C",
    MODE_GLARE_TV: "glare_tv: Blendschutz TV-Stack bei aktivem Lux-Gate",
    MODE_GLARE_PC: "glare_pc: Blendschutz PC-Monitor bei aktivem Lux-Gate",
    MODE_OPEN: "open: kein Modus aktiv (Fallback)",
}


def decide(
    ctx: Context,
    position_profile: dict[str, int] | None = None,
    *,
    gate_on: bool,
    startup_ready: bool,
    apply_enabled: bool,
    manual_override_active: bool,
    heat_lux_min: int = DEFAULT_HEAT_LUX_MIN,
    previous_thermal_active: bool | None = None,
) -> Decision:
    """Vollständige Entscheidung inkl. Gating-Overlay.

    Window-open (R1) ist absolut: ignoriert Startup-Block + Manual-Override,
    löscht einen aktiven Override und respektiert nur den apply_enabled-Master
    (Shadow-Mode = wirklich keine Schreibvorgänge).
    """
    profile = _merged_profile(position_profile)
    n = _normalized(ctx)
    demand = _build_protection_demand(
        n, gate_on, profile, previous_thermal_active
    )
    winner, trace = evaluate_chain(
        n,
        gate_on,
        heat_lux_min,
        position_profile=profile,
        previous_thermal_active=previous_thermal_active,
        demand=demand,
    )
    mode = winner.mode
    position = _position(mode, profile)
    reason = (
        "protection: " + " | ".join(demand.reasons)
        if demand.active and mode == demand.effective_mode
        else _REASONS.get(mode, mode)
    )

    blockers: list[str] = []
    apply_allowed = True
    if not apply_enabled:
        blockers.append("apply_disabled")
        apply_allowed = False

    # R1 — Fenster offen: absolut. Nur apply_enabled bremst (Shadow-Safety).
    if mode == MODE_WINDOW_OPEN:
        if ctx.window_open is None:
            blockers.append("source_unknown:window")
        return Decision(
            mode=mode, target_position=position, reason=reason,
            protection_demand=demand, gate_on=gate_on,
            blockers=blockers, manual_override_cleared=manual_override_active,
            apply_allowed=apply_allowed, trace=trace,
        )

    # Reguläres Gating-Overlay.
    if not startup_ready:
        blockers.append("startup_block")
        apply_allowed = False
    if n.day_state is None:
        blockers.append("source_unknown:day_state")
        apply_allowed = False
    if manual_override_active:
        blockers.append("manual_override")
        apply_allowed = False

    return Decision(
        mode=mode, target_position=position, reason=reason,
        protection_demand=demand, gate_on=gate_on,
        blockers=blockers, apply_allowed=apply_allowed, trace=trace,
    )


# --------------------------------------------------------------------------- #
# R-PL — Privacy-Latch-Prädikate (Coordinator hält den State)
# --------------------------------------------------------------------------- #
def privacy_latch_should_set(
    day_state: str | None,
    prev_day_state: str | None,
    lux: float | None,
) -> bool:
    """Set: Eintritt in early_night ODER lux < 400 während late_evening."""
    entered_early_night = (
        day_state == PHASE_EARLY_NIGHT and prev_day_state != PHASE_EARLY_NIGHT
    )
    dark_late_evening = (
        day_state == PHASE_LATE_EVENING and lux is not None and lux < PRIVACY_LATCH_LUX
    )
    return entered_early_night or dark_late_evening


def privacy_latch_recovery(day_state: str | None, lux: float | None) -> bool:
    """HA-Start: Latch sofort setzen, falls Set-Bedingung bereits erfüllt ist."""
    if day_state == PHASE_EARLY_NIGHT:
        return True
    return day_state == PHASE_LATE_EVENING and lux is not None and lux < PRIVACY_LATCH_LUX


def privacy_latch_should_reset(
    bio_state: str | None,
    prev_bio_state: str | None,
    sunrise_crossed: bool,
) -> bool:
    """Reset: Sonnenaufgang ODER Bio-Übergang auf awake/waking."""
    bio_woke = (
        prev_bio_state not in (BIO_AWAKE, BIO_WAKING)
        and bio_state in (BIO_AWAKE, BIO_WAKING)
    )
    return bool(sunrise_crossed) or bio_woke


def manual_override_should_reset_on_sleep(
    bio_state: str | None,
    prev_bio_state: str | None,
) -> bool:
    """Reset active manual override when a new sleep bio phase starts."""
    return (
        prev_bio_state is not None
        and prev_bio_state != BIO_SLEEP
        and bio_state == BIO_SLEEP
    )


# --------------------------------------------------------------------------- #
# R-OW — Override-Warden-Prädikate (Coordinator hält die Timer)
# --------------------------------------------------------------------------- #
def position_within_tolerance(
    current: float | None,
    target: float | None,
    *,
    tolerance: int = WARDEN_POSITION_TOLERANCE,
) -> bool:
    return (
        current is not None
        and target is not None
        and abs(float(current) - float(target)) <= tolerance
    )


def override_warden_immediate_clear(
    writing_recently_off: bool,
    position_at_target: bool,
) -> bool:
    """Sofortprüfung bei Override-Set: Race-Echo (Writing-Flag kürzlich aus)
    ODER Cover steht bereits ±3% auf Ziel → kein echter Eingriff."""
    return bool(writing_recently_off) or bool(position_at_target)


def override_warden_sweep_clear(
    override_age_seconds: float,
    cover_moving: bool,
    position_at_target: bool,
    *,
    min_age_seconds: int = WARDEN_SWEEP_MIN_AGE_SECONDS,
) -> bool:
    """Periodischer 5-Min-Sweep: Override > 5 min alt, Cover steht, ±3% auf Ziel."""
    return (
        override_age_seconds > min_age_seconds
        and not cover_moving
        and position_at_target
    )


# --------------------------------------------------------------------------- #
# Positions-Adapter — logische Policy-Achse ↔ physische Cover-Achse
# --------------------------------------------------------------------------- #
def mirror_position(position: float | None, invert: bool) -> float | None:
    """Spiegelt eine Position an der Achse 0↔100, wenn ``invert``.

    Reiner Helfer (Involution). Seit dem Zwei-Profile-Modell wird die Invertierung
    NICHT mehr als Mirror am Apply gerechnet — stattdessen gibt es zwei unabhängige
    Positions-Profile (normal / invertiert), und der Schalter wählt das aktive. Diese
    Funktion liefert nur noch den Default-Spiegel zum Vorbelegen des Invert-Profils
    (``DEFAULT_POSITION_PROFILE_INVERTED``). ``None`` bleibt ``None``.
    """
    if position is None or not invert:
        return position
    return 100 - position
