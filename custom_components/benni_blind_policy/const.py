"""Konstanten der Benni Blind Policy (Wohnzimmer-Rollo, L2-Policy).

Eigenständige HACS-Custom-Integration. Konsumiert Foundation-/Feeder-Sensoren
(benni_core_state, benni_core_devices, benni_media_state, DWD-Wetter) AUSSCHLIESSLICH
als HA-Entity-IDs aus dem Config-Flow — kein Python-Cross-Modul-Import.

Profil-Modell (FLEET-16): Slug-Schema ``<profile>_blind_policy_<type>`` via
``has_entity_name`` + profil-benanntem Device. Logik identisch je Profil, nur
Prefill-Defaults unterscheiden sich (Blaupause: benni_core_state).

Lastenheft: einhornzentrale/docs/lastenhefte/reviewed/rollo/
"""
from __future__ import annotations

from typing import Final

DOMAIN: Final[str] = "benni_blind_policy"
MODULE_ID: Final[str] = "blind_policy"
NAME: Final[str] = "Blind Policy"

STORAGE_VERSION: Final[int] = 1
CONFIG_ENTRY_VERSION: Final[int] = 3

# Datenwurzel in hass.data[DOMAIN].
DATA_COORDINATOR: Final[str] = "coordinator"
DATA_SKIP_RELOAD_COUNT: Final[str] = "skip_reload_count"
DATA_WS_REGISTERED: Final[str] = "_ws_registered"
DATA_VIEW_STATIC: Final[str] = "_view_static_registered"
DATA_VIEW_PANEL: Final[str] = "_view_panel_registered"


def unique_id(entry_id: str, suffix: str) -> str:
    """Stabile, kollisionsfreie unique_id (Domain + Entry + Suffix)."""
    return f"{DOMAIN}_{entry_id}_{suffix}"


def storage_suffix(entry_id: str) -> str:
    return f"state_{entry_id}"


# --------------------------------------------------------------------------- #
# Profile (Route benni / eltern) — FLEET-16, Blaupause benni_core_state
# --------------------------------------------------------------------------- #
CONF_PROFILE: Final = "profile"
PROFILE_BENNI: Final = "benni"
PROFILE_ELTERN: Final = "eltern"
PROFILES: Final = [PROFILE_BENNI, PROFILE_ELTERN]
DEFAULT_PROFILE_ROUTE: Final = PROFILE_BENNI
PROFILE_LABELS: Final = {PROFILE_BENNI: "Benni", PROFILE_ELTERN: "Eltern"}

# --------------------------------------------------------------------------- #
# Rollo-Modi (Prioritätskette, Lastenheft §4.1)
# --------------------------------------------------------------------------- #
MODE_WINDOW_OPEN: Final = "window_open"
MODE_PRIVACY_BED: Final = "privacy_bed"
MODE_PRIVACY: Final = "privacy"
MODE_ALARM_WAKEUP: Final = "alarm_wakeup"
MODE_OPEN_WEEKDAY: Final = "open_weekday"
MODE_OPEN_WEEKEND: Final = "open_weekend"
MODE_SLEEP: Final = "sleep"
MODE_HEAT: Final = "heat"
MODE_GLARE_TV: Final = "glare_tv"
MODE_GLARE_PC: Final = "glare_pc"
MODE_OPEN: Final = "open"
MODE_MANUAL: Final = "manual"  # nur Anzeige (Override aktiv); keine eigene Kettenregel

ALL_MODES: Final = (
    MODE_WINDOW_OPEN, MODE_PRIVACY_BED, MODE_PRIVACY, MODE_ALARM_WAKEUP,
    MODE_OPEN_WEEKDAY, MODE_OPEN_WEEKEND, MODE_SLEEP, MODE_HEAT,
    MODE_GLARE_TV, MODE_GLARE_PC, MODE_OPEN,
)

# Zielpositionen je Modus (0 = unten/zu, 100 = oben/offen). Lastenheft §6.
DEFAULT_POSITION_PROFILE: Final[dict[str, int]] = {
    MODE_WINDOW_OPEN: 100,
    MODE_PRIVACY_BED: 40,
    MODE_PRIVACY: 40,
    MODE_ALARM_WAKEUP: 100,
    MODE_OPEN_WEEKDAY: 100,
    MODE_OPEN_WEEKEND: 100,
    MODE_SLEEP: 40,
    MODE_HEAT: 45,
    MODE_GLARE_TV: 60,
    MODE_GLARE_PC: 75,
    MODE_OPEN: 100,
}

# Zweites, UNABHÄNGIGES Profil für die invertierte Achse (Schalter wählt, welches
# Profil aktiv ist — kein 100−x-Mirror mehr am Apply). Default = gespiegeltes
# Normal-Profil, damit die Out-of-Box-/Live-Verhalten unverändert bleiben; jeder
# Wert ist frei editierbar (z. B. sleep 40/40 statt 40/60).
DEFAULT_POSITION_PROFILE_INVERTED: Final[dict[str, int]] = {
    mode: 100 - pos for mode, pos in DEFAULT_POSITION_PROFILE.items()
}

# --------------------------------------------------------------------------- #
# Eingangs-Wertebereiche (konsumiert aus core_state / media_state / DWD)
# --------------------------------------------------------------------------- #
BIO_SLEEP: Final = "sleep"
BIO_WAKING: Final = "waking"
BIO_AWAKE: Final = "awake"

DAY_CONTEXT_WERKTAG: Final = "werktag"
DAY_CONTEXT_WOCHENENDE: Final = "wochenende"
DAY_CONTEXT_FREI: Final = "frei"

HOUSEHOLD_EMPTY: Final = "leer"
HOUSEHOLD_NOT_EMPTY: Final = "nicht_leer"

SCENARIO_IDLE: Final = "idle"
SCENARIO_TV: Final = "tv"
SCENARIO_STREAMING: Final = "streaming"
SCENARIO_GAMING: Final = "gaming"
SCENARIO_PRIVATE_TIME: Final = "private_time"

GAMING_TV: Final = "tv"
GAMING_PC: Final = "pc"
GAMING_NONE: Final = "none"

WEATHER_SUNNY: Final = "sunny"

# 8 Tagesphasen.
PHASE_EARLY_MORNING: Final = "early_morning"
PHASE_LATE_MORNING: Final = "late_morning"
PHASE_FORENOON: Final = "forenoon"
PHASE_AFTERNOON: Final = "afternoon"
PHASE_EARLY_EVENING: Final = "early_evening"
PHASE_LATE_EVENING: Final = "late_evening"
PHASE_EARLY_NIGHT: Final = "early_night"
PHASE_LATE_NIGHT: Final = "late_night"

# --------------------------------------------------------------------------- #
# Schwellen & Konstanten (Lastenheft §6)
# --------------------------------------------------------------------------- #
GATE_OPEN_LUX: Final = 20000          # Gate öffnet > 20.000 lx
GATE_CLOSE_LUX: Final = 15000         # Gate schließt < 15.000 lx
GATE_SUN_MIN_DEG: Final = 5           # Sonnenhöhe > 5° (Gate)
GATE_DAY_STATES: Final = frozenset(
    {PHASE_EARLY_MORNING, PHASE_LATE_MORNING, PHASE_FORENOON, PHASE_AFTERNOON}
)

HEAT_TEMP_C: Final = 24               # Temperaturklasse ≥ 12 ≙ ≥ 24 °C
HEAT_SUN_MIN_DEG: Final = 5           # Heat Sonnenhöhe > 5°
# Heat endet mit afternoon — fällt weg, sobald early_evening beginnt (User 2026-06-27:
# early_evening war zu lang). Phasen-Mengentest, keine Uhrzeit.
HEAT_DAY_STATES: Final = frozenset(
    {PHASE_LATE_MORNING, PHASE_FORENOON, PHASE_AFTERNOON}
)

PRIVACY_LATCH_LUX: Final = 400        # Latch-Set < 400 lx während late_evening

OPEN_WEEKDAY_MIN_MINUTES: Final = 8 * 60        # 08:00
OPEN_WEEKEND_MIN_MINUTES: Final = 9 * 60 + 30   # 09:30

WRITING_GRACE_SECONDS: Final = 5      # Writing-Active-Nachlauf
WRITING_TIMEOUT_SECONDS: Final = 90   # Cover-Fahrt-Timeout
WARDEN_RACE_ECHO_SECONDS: Final = 30  # Race-Echo-Fenster (Writing kürzlich aus)
WARDEN_POSITION_TOLERANCE: Final = 3  # ±3 %
WARDEN_SWEEP_INTERVAL_SECONDS: Final = 300       # 5-Min-Sweep
WARDEN_SWEEP_MIN_AGE_SECONDS: Final = 300        # Override-Mindestalter für Sweep

# Eigene Cover-Bewegung in diesem Fenster ≠ Manual-Eingriff (Backstop, falls das
# Writing-Active-Flag mal verpasst wird).
RECENT_APPLY_GUARD_SECONDS: Final = 8

# Evaluations-Intervall.
UPDATE_INTERVAL_SECONDS: Final = 30

# --------------------------------------------------------------------------- #
# Config-Keys — Quell-Entities (alle als Entity-IDs aus dem Flow)
# --------------------------------------------------------------------------- #
CONF_BLIND_MASTER: Final = "blind_master_entity"
CONF_COVER_ENTITY: Final = "cover_entity"
CONF_WINDOW_OPEN: Final = "window_open_entity"        # on = Flügel offen (Status 2)
CONF_BIO_STATE: Final = "bio_state_entity"
CONF_DAY_STATE: Final = "day_state_entity"
CONF_DAY_CONTEXT: Final = "day_context_entity"
CONF_PRESENCE_HOUSEHOLD: Final = "presence_household_entity"
CONF_LUX: Final = "lux_entity"
CONF_SUN: Final = "sun_entity"                        # sun.sun — Elevation aus Attribut
CONF_MEDIA_SCENARIO: Final = "media_scenario_entity"
CONF_GAMING_SOURCE: Final = "gaming_source_entity"
CONF_WEATHER_CONDITION: Final = "weather_condition_entity"   # R8 (sunny)
CONF_OUTDOOR_TEMP: Final = "outdoor_temp_entity"            # R8 (≥ 24 °C)

LEGACY_COVER_ENTITY: Final = "cover.living_blackout_blind"
CORE_COVER_ENTITY: Final = "cover.wohnbereich_thermo_verdunklungsrollo"
CORE_BLIND_MASTER_ENTITY: Final = "sensor.benni_master_living_rollo"
LEGACY_WINDOW_OPEN_ENTITY: Final = "binary_sensor.opening_unsafe_for_rollo_combined"
CORE_WINDOW_OPEN_ENTITY: Final = "sensor.benni_combined_opening_unsafe_for_rollo"
CORE_OPENINGS_MASTER_ENTITY: Final = "sensor.benni_combined_openings"
CORE_WINDOW_OPEN_ATTRIBUTE: Final = "living"

# Options.
CONF_APPLY_ENABLED: Final = "apply_enabled"
CONF_STARTUP_BLOCK_SECONDS: Final = "startup_block_seconds"
CONF_POSITION_PROFILE: Final = "position_profile"    # dict mode -> position (Normal-Achse)
CONF_POSITION_PROFILE_INVERTED: Final = "position_profile_inverted"  # dict mode -> position (Invert-Achse)
CONF_INVERT_POSITION: Final = "invert_position"      # True = invertiertes Profil aktiv

# Defaults.
DEFAULT_APPLY_ENABLED: Final = False                 # Shadow-safe out of the box
DEFAULT_STARTUP_BLOCK_SECONDS: Final = 15
DEFAULT_INVERT_POSITION: Final = False               # Richtung normal (logisch == physisch)

# --------------------------------------------------------------------------- #
# Per-Profil-Prefill: bekannte Live-IDs je Route (greift nur, WENN Entity existiert).
# Benni-Anlage (einhornzentrale) via HA-MCP ermittelt. "eltern" bewusst leer.
# Heat-Contract: weather_condition (DWD, sunny) + outdoor_temp (LOKAL, core_devices
# effective outdoor, °C, ≥24) + sun (Elevation) — in-policy kategorisiert (keine
# Wetterkategorie-/Temperaturklasse-Entity vorhanden; FLEET-16-Owner dieser Ableitung
# ist diese Policy). User 2026-06-27: outdoor_temp von DWD-Prognose (zu träge, lag
# 3 °C unter real) auf die lokale core_devices-Aggregation umgestellt; condition bleibt
# DWD (lokal gibt es keine sunny/cloudy-Lage).
# Window: openings master exposes per-room enum; living == open blocks this blind.
# --------------------------------------------------------------------------- #
PROFILE_PREFILL: Final[dict[str, dict[str, str]]] = {
    PROFILE_BENNI: {
        CONF_BLIND_MASTER: CORE_BLIND_MASTER_ENTITY,
        CONF_COVER_ENTITY: CORE_COVER_ENTITY,
        CONF_WINDOW_OPEN: CORE_OPENINGS_MASTER_ENTITY,
        CONF_BIO_STATE: "sensor.benni_core_state_bio_state",
        CONF_DAY_STATE: "sensor.benni_core_state_day_state",
        CONF_DAY_CONTEXT: "sensor.benni_core_state_day_context",
        CONF_PRESENCE_HOUSEHOLD: "sensor.benni_core_state_presence_household",
        CONF_LUX: "sensor.benni_device_garden_lux",
        CONF_SUN: "sun.sun",
        CONF_MEDIA_SCENARIO: "sensor.benni_media_state_media_context",
        CONF_GAMING_SOURCE: "sensor.benni_media_state_gaming_source",
        CONF_WEATHER_CONDITION: "sensor.benni_device_weather_condition",
        CONF_OUTDOOR_TEMP: "sensor.benni_combined_climate_effective_outdoor_temperature",
    },
    PROFILE_ELTERN: {},
}

# Reihenfolge der Quell-Felder im Config-Flow (ein Schritt) + Optionen.
LEGACY_SOURCE_KEYS: Final = (
    CONF_COVER_ENTITY, CONF_WINDOW_OPEN, CONF_BIO_STATE, CONF_DAY_STATE,
    CONF_DAY_CONTEXT, CONF_PRESENCE_HOUSEHOLD, CONF_LUX, CONF_SUN,
    CONF_MEDIA_SCENARIO, CONF_GAMING_SOURCE, CONF_WEATHER_CONDITION,
    CONF_OUTDOOR_TEMP,
)
SOURCE_KEYS: Final = (CONF_BLIND_MASTER,)
OPTION_KEYS: Final = (CONF_APPLY_ENABLED, CONF_STARTUP_BLOCK_SECONDS, CONF_INVERT_POSITION)

# --------------------------------------------------------------------------- #
# unique_id-Suffixe der Output-Entities
# --------------------------------------------------------------------------- #
UID_MODE: Final = "mode"
UID_POSITION: Final = "position"
UID_DEBUG: Final = "debug"
UID_LUX_GATE: Final = "lux_gate"
UID_PRIVACY_LATCH: Final = "privacy_latch"
UID_MANUAL_OVERRIDE: Final = "manual_override"
UID_WRITING_ACTIVE: Final = "writing_active"
UID_APPLY_BLOCKED: Final = "apply_blocked"
UID_PRIVACY_BED: Final = "privacy_bed"
UID_ALARM_WAKEUP: Final = "alarm_wakeup"
UID_APPLY_ENABLED: Final = "apply_enabled"
UID_INVERT_POSITION: Final = "invert_position"

# Entity-Feature-Slugs (→ <profile>_blind_policy_<feature> via has_entity_name).
NAME_MODE: Final = "Mode"
NAME_POSITION: Final = "Position"
NAME_DEBUG: Final = "Debug"
NAME_LUX_GATE: Final = "Lux Gate"
NAME_PRIVACY_LATCH: Final = "Privacy Latch"
NAME_MANUAL_OVERRIDE: Final = "Manual Override"
NAME_WRITING_ACTIVE: Final = "Writing Active"
NAME_APPLY_BLOCKED: Final = "Apply Blocked"
NAME_PRIVACY_BED: Final = "Privacy Bed"
NAME_ALARM_WAKEUP: Final = "Alarm Wakeup"
NAME_APPLY_ENABLED: Final = "Apply Enabled"
NAME_INVERT_POSITION: Final = "Invert Position"

# --------------------------------------------------------------------------- #
# Services
# --------------------------------------------------------------------------- #
SERVICE_APPLY_NOW: Final = "apply_now"
SERVICE_SET_PRIVACY_BED: Final = "set_privacy_bed"
SERVICE_CLEAR_MANUAL_OVERRIDE: Final = "clear_manual_override"
SERVICE_SET_POSITION_PROFILE: Final = "set_position_profile"

# --------------------------------------------------------------------------- #
# Panel / WebSocket-API
# --------------------------------------------------------------------------- #
PANEL_URL_PATH: Final = "benni_blind_policy"
PANEL_TITLE: Final = "Blind Policy"
PANEL_ICON: Final = "mdi:roller-shade"
FRONTEND_DIR_URL: Final = "/benni_blind_policy_app"
FRONTEND_ENTRY: Final = f"{FRONTEND_DIR_URL}/main.js"
PANEL_ELEMENT: Final = "bbp-app"

WS_GET_STATUS: Final = f"{DOMAIN}/get_status"
WS_SET_APPLY_ENABLED: Final = f"{DOMAIN}/set_apply_enabled"
WS_SET_PRIVACY_BED: Final = f"{DOMAIN}/set_privacy_bed"
WS_CLEAR_OVERRIDE: Final = f"{DOMAIN}/clear_manual_override"
WS_APPLY_NOW: Final = f"{DOMAIN}/apply_now"
WS_SET_POSITION_PROFILE: Final = f"{DOMAIN}/set_position_profile"
WS_SET_MANUAL_POSITION: Final = f"{DOMAIN}/set_manual_position"
WS_SET_MANUAL_DECISION: Final = f"{DOMAIN}/set_manual_decision"
WS_SET_INVERT_POSITION: Final = f"{DOMAIN}/set_invert_position"
WS_RESET_POSITION_PROFILE: Final = f"{DOMAIN}/reset_position_profile"

# Modi, die im Panel manuell als Decision erzwingbar sind (window_open bleibt
# absolut/safety-only, alarm_wakeup ist Platzhalter, open_weekday/-weekend sind
# zeitgebundene Open-Duplikate → hier die positions-distinkten Modi).
MANUAL_MODES: Final = (
    MODE_OPEN, MODE_SLEEP, MODE_PRIVACY, MODE_PRIVACY_BED,
    MODE_HEAT, MODE_GLARE_TV, MODE_GLARE_PC,
)
