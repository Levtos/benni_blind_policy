"""Pure Decision-Engine für die Blind-Policy (Wohnzimmer-Rollo) — HA-frei, voll testbar.

Implementiert das reviewte Lastenheft
``einhornzentrale/docs/lastenhefte/reviewed/rollo/`` 1:1:

  * ``lux_gate()``     — Schmitt-Trigger (20k/15k) mit Sonnenhöhe + Tagesphasen-Gate,
                         zustandsbehaftet via ``prev_gate`` (Hysterese hält der Coordinator).
  * ``evaluate_chain()`` — stateless Prioritätskette (R1..R11), liefert Gewinner + Trace.
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

from dataclasses import dataclass, field
from typing import Any

from .const import (
    BIO_AWAKE,
    BIO_SLEEP,
    BIO_WAKING,
    DAY_CONTEXT_FREI,
    DAY_CONTEXT_WERKTAG,
    DAY_CONTEXT_WOCHENENDE,
    DEFAULT_POSITION_PROFILE,
    GAMING_PC,
    GAMING_NONE,
    GATE_CLOSE_LUX,
    GATE_DAY_STATES,
    GATE_OPEN_LUX,
    GATE_SUN_MIN_DEG,
    HEAT_DAY_STATES,
    HEAT_SUN_MIN_DEG,
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
    OPEN_WEEKDAY_MIN_MINUTES,
    OPEN_WEEKEND_MIN_MINUTES,
    PHASE_EARLY_MORNING,
    PHASE_EARLY_NIGHT,
    PHASE_FORENOON,
    PHASE_LATE_EVENING,
    PHASE_LATE_MORNING,
    PHASE_LATE_NIGHT,
    PRIVACY_LATCH_LUX,
    SCENARIO_GAMING,
    SCENARIO_IDLE,
    SCENARIO_STREAMING,
    SCENARIO_TV,
    WARDEN_POSITION_TOLERANCE,
    WARDEN_SWEEP_MIN_AGE_SECONDS,
    WEATHER_SUNNY,
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
    weather_condition: str | None = None     # roh (sunny/rainy/…) — Heat in-policy
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

    rule: str          # R1 .. R11
    mode: str
    matched: bool
    position: int | None


@dataclass
class Decision:
    mode: str
    target_position: int | None
    reason: str
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
            "gate_on": self.gate_on,
            "blockers": list(self.blockers),
            "manual_override_cleared": self.manual_override_cleared,
            "apply_allowed": self.apply_allowed,
            "trace": [
                {"rule": e.rule, "mode": e.mode, "matched": e.matched, "position": e.position}
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
    if sun_elevation is None or sun_elevation <= GATE_SUN_MIN_DEG:
        return False
    if day_state not in GATE_DAY_STATES:
        return False
    if lux is None:
        return bool(prev_gate)
    if lux > GATE_OPEN_LUX:
        return True
    if lux < GATE_CLOSE_LUX:
        return False
    return bool(prev_gate)


# --------------------------------------------------------------------------- #
# Prioritätskette (Lastenheft §4.1 / §5)
# --------------------------------------------------------------------------- #
def _heat_active(n: _Norm) -> bool:
    """Direkter Sonnenschutz, in-policy aus Rohdaten (kein Lux-Gate)."""
    return (
        n.weather_condition == WEATHER_SUNNY
        and n.outdoor_temp is not None
        and n.outdoor_temp >= HEAT_TEMP_C
        and n.sun_elevation is not None
        and n.sun_elevation > HEAT_SUN_MIN_DEG
        and n.day_state in HEAT_DAY_STATES
    )


def _sleep_active(n: _Norm) -> bool:
    """Bio sleep, Nachtphasen, oder early_morning+sleep. `waking` zählt nicht."""
    return (
        n.bio_state == BIO_SLEEP
        or n.day_state in (PHASE_EARLY_NIGHT, PHASE_LATE_NIGHT)
        or (n.day_state == PHASE_EARLY_MORNING and n.bio_state == BIO_SLEEP)
    )


def evaluate_chain(n: _Norm, gate_on: bool) -> tuple[RuleEval, list[RuleEval]]:
    """Wertet die Prioritätskette R1..R11 aus.

    Returns (winner, full_trace). Erste zutreffende Regel (höchste Priorität)
    gewinnt; der Trace enthält ALLE Regeln mit ihrem matched-Flag (für das Panel).
    Window-open ist hier nur als regulärer Ketten-Top abgebildet; die Absolut-
    Semantik (Override ignorieren) macht ``decide`` im Gating-Overlay.
    """
    nm = n.now_minutes
    rules: list[tuple[str, str, bool]] = [
        ("R1", MODE_WINDOW_OPEN, n.window_open),
        ("R2", MODE_PRIVACY_BED, n.privacy_bed),
        ("R3", MODE_PRIVACY, n.presence_household == HOUSEHOLD_EMPTY or n.privacy_latch),
        ("R4", MODE_ALARM_WAKEUP, n.alarm_wakeup),
        ("R5", MODE_HEAT, _heat_active(n)),
        ("R6", MODE_OPEN_WEEKDAY,
         n.day_state == PHASE_LATE_MORNING
         and n.day_context == DAY_CONTEXT_WERKTAG
         and nm is not None and nm >= OPEN_WEEKDAY_MIN_MINUTES),
        ("R7", MODE_OPEN_WEEKEND,
         n.day_state == PHASE_FORENOON
         and n.day_context in (DAY_CONTEXT_WOCHENENDE, DAY_CONTEXT_FREI)
         and nm is not None and nm >= OPEN_WEEKEND_MIN_MINUTES),
        ("R8", MODE_SLEEP, _sleep_active(n)),
        ("R9", MODE_GLARE_TV,
         gate_on
         and n.media_scenario in TV_GLARE_SCENARIOS
         and n.gaming_source != GAMING_PC
         and n.bio_state != BIO_SLEEP),
        ("R10", MODE_GLARE_PC,
         gate_on
         and n.media_scenario == SCENARIO_GAMING
         and n.gaming_source == GAMING_PC
         and n.bio_state != BIO_SLEEP),
        ("R11", MODE_OPEN, True),  # Fallback — trifft immer zu
    ]

    trace: list[RuleEval] = []
    winner: RuleEval | None = None
    for rule_id, mode, matched in rules:
        ev = RuleEval(rule=rule_id, mode=mode, matched=bool(matched),
                      position=_position(mode, DEFAULT_POSITION_PROFILE))
        if winner is None and ev.matched:
            winner = ev
        trace.append(ev)
    assert winner is not None  # R11 ist immer True
    return winner, trace


def _position(mode: str, profile: dict[str, int]) -> int | None:
    raw = profile.get(mode, DEFAULT_POSITION_PROFILE.get(mode))
    if raw is None:
        return None
    try:
        return max(0, min(100, int(raw)))
    except (TypeError, ValueError):
        return None


_REASONS: dict[str, str] = {
    MODE_WINDOW_OPEN: "window_open: Fenster offen — absolute Top-Regel",
    MODE_PRIVACY_BED: "privacy_bed: manueller Bett-Modus",
    MODE_PRIVACY: "privacy: Haushalt leer oder Privacy-Latch aktiv",
    MODE_ALARM_WAKEUP: "alarm_wakeup: Wecker-Platzhalter aktiv",
    MODE_OPEN_WEEKDAY: "open_weekday: natürlicher Wecker werktags",
    MODE_OPEN_WEEKEND: "open_weekend: natürlicher Wecker wochenends/frei",
    MODE_SLEEP: "sleep: Bio sleep oder Nachtphase",
    MODE_HEAT: "heat: direkter Sonnenschutz (sunny + warm + Sonne hoch)",
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
) -> Decision:
    """Vollständige Entscheidung inkl. Gating-Overlay.

    Window-open (R1) ist absolut: ignoriert Startup-Block + Manual-Override,
    löscht einen aktiven Override und respektiert nur den apply_enabled-Master
    (Shadow-Mode = wirklich keine Schreibvorgänge).
    """
    profile = {**DEFAULT_POSITION_PROFILE, **(position_profile or {})}
    n = _normalized(ctx)
    winner, trace = evaluate_chain(n, gate_on)
    mode = winner.mode
    position = _position(mode, profile)
    reason = _REASONS.get(mode, mode)

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
            mode=mode, target_position=position, reason=reason, gate_on=gate_on,
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
        mode=mode, target_position=position, reason=reason, gate_on=gate_on,
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

    Adapter zwischen der *logischen* Policy-Koordinate (0 = unten/zu, 100 =
    oben/offen) und der *physischen* Cover-Achse, falls die Fahrtrichtung am Gerät
    invertiert ist. Der Coordinator nutzt ihn an genau einer Stelle in BEIDE
    Richtungen: beim Schreiben (logisch → physisch ans ``set_cover_position``) und
    beim Lesen der Ist-Position (physisch → logisch, vor jedem Tolerance-Vergleich).
    So bleiben Policy-Entscheidung + Decision-Trace immer in logischen Koordinaten
    (Shadow-Vergleich bleibt aussagekräftig), nur das I/O wird gedreht.

    Involution: zweimal angewandt liefert das Original. ``None`` (Position
    unbekannt) bleibt ``None``.
    """
    if position is None or not invert:
        return position
    return 100 - position
