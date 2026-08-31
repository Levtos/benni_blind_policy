"""Pure-Logic-Tests der Blind-Policy-Decision-Engine (Lastenheft-konform)."""
from __future__ import annotations

import bbp_const as const
import bbp_policy as policy
import pytest

DECIDE_KW = dict(startup_ready=True, apply_enabled=True, manual_override_active=False)


def ctx(**over):
    """Default-Context, der ohne Override auf R9 (open) fällt."""
    base = dict(
        window_open=False,
        bio_state=const.BIO_AWAKE,
        day_state=const.PHASE_AFTERNOON,
        day_context=const.DAY_CONTEXT_WERKTAG,
        presence_household=const.HOUSEHOLD_NOT_EMPTY,
        privacy_bed=False,
        privacy_latch=False,
        alarm_wakeup=False,
        media_scenario=const.SCENARIO_IDLE,
        gaming_source=const.GAMING_NONE,
        lux=None,
        sun_elevation=None,
        weather_condition=None,
        outdoor_temp=None,
        now_minutes=12 * 60,
    )
    base.update(over)
    return policy.Context(**base)


def decide(c, *, gate_on=False, **kw):
    merged = {**DECIDE_KW, **kw}
    return policy.decide(c, gate_on=gate_on, **merged)


def protection(c, *, gate_on=False, **kw):
    return policy.evaluate_protection_demand(c, gate_on=gate_on, **kw)


# --------------------------------------------------------------------------- #
# Positionen je Modus (Lastenheft §6)
# --------------------------------------------------------------------------- #
def test_default_position_profile_matches_binding_issue59_contract():
    p = const.DEFAULT_POSITION_PROFILE
    assert p[const.MODE_WINDOW_OPEN] == 100
    assert p[const.MODE_PRIVACY_BED] == 40
    assert p[const.MODE_PRIVACY] == 40
    assert p[const.MODE_ALARM_WAKEUP] == 100
    assert p[const.MODE_OPEN_WEEKDAY] == 100
    assert p[const.MODE_OPEN_WEEKEND] == 100
    assert p[const.MODE_SLEEP] == 5
    assert const.DEFAULT_POSITION_PROFILE_INVERTED[const.MODE_SLEEP] == 5
    assert p[const.MODE_HEAT] == 45
    assert p[const.MODE_GLARE_TV] == 60
    assert p[const.MODE_GLARE_PC] == 75
    assert p[const.MODE_OPEN] == 100


# --------------------------------------------------------------------------- #
# R1 — Fenster offen ist absolut
# --------------------------------------------------------------------------- #
def test_window_open_wins_over_everything():
    d = decide(ctx(window_open=True, privacy_bed=True, bio_state=const.BIO_SLEEP))
    assert d.mode == const.MODE_WINDOW_OPEN
    assert d.target_position == 100


def test_window_open_clears_manual_override_and_applies():
    d = decide(ctx(window_open=True), manual_override_active=True)
    assert d.mode == const.MODE_WINDOW_OPEN
    assert d.manual_override_cleared is True
    assert d.apply_allowed is True  # ignoriert Override + Startup


def test_window_open_ignores_startup_block():
    d = decide(ctx(window_open=True), startup_ready=False)
    assert d.mode == const.MODE_WINDOW_OPEN
    assert d.apply_allowed is True
    assert "startup_block" not in d.blockers


def test_window_open_respects_apply_enabled_master():
    d = decide(ctx(window_open=True), apply_enabled=False)
    assert d.mode == const.MODE_WINDOW_OPEN
    assert d.apply_allowed is False
    assert "apply_disabled" in d.blockers


def test_window_unknown_treated_as_open_safety():
    d = decide(ctx(window_open=None))
    assert d.mode == const.MODE_WINDOW_OPEN
    assert "source_unknown:window" in d.blockers


# --------------------------------------------------------------------------- #
# Prioritätskette R2..R9
# --------------------------------------------------------------------------- #
def test_privacy_bed_prio1():
    d = decide(ctx(privacy_bed=True, presence_household=const.HOUSEHOLD_EMPTY))
    assert d.mode == const.MODE_PRIVACY_BED
    assert d.target_position == 40


def test_privacy_household_empty():
    d = decide(ctx(presence_household=const.HOUSEHOLD_EMPTY))
    assert d.mode == const.MODE_PRIVACY
    assert d.target_position == 40


def test_privacy_latch_active():
    d = decide(ctx(privacy_latch=True))
    assert d.mode == const.MODE_PRIVACY


def test_sleep_beats_privacy_latch():
    # Sleep gewinnt gegen Privacy, wenn der Bio-State tatsächlich `sleep` ist.
    d = decide(ctx(privacy_latch=True, bio_state=const.BIO_SLEEP,
                   day_state=const.PHASE_EARLY_NIGHT))
    assert d.mode == const.MODE_SLEEP


def test_privacy_wins_when_awake():
    # Wach + Latch (z. B. Haushalt leer) → Sleep inaktiv → Privacy greift weiter.
    d = decide(ctx(privacy_latch=True, bio_state=const.BIO_AWAKE,
                   day_state=const.PHASE_AFTERNOON))
    assert d.mode == const.MODE_PRIVACY


def test_alarm_wakeup_prio3():
    d = decide(ctx(alarm_wakeup=True, bio_state=const.BIO_SLEEP,
                   day_state=const.PHASE_EARLY_NIGHT))
    assert d.mode == const.MODE_ALARM_WAKEUP
    assert d.target_position == 100


def test_alarm_wakeup_beats_sleep():
    # Wecken schlägt Schlaf: alarm (R3) steht über sleep (R4).
    d = decide(ctx(alarm_wakeup=True, bio_state=const.BIO_SLEEP,
                   day_state=const.PHASE_LATE_NIGHT))
    assert d.mode == const.MODE_ALARM_WAKEUP


# Öffnen am Morgen ist jetzt bio-getrieben (Wake-Planner), nicht mehr zeitgebunden:
# die fixen open_weekday/-weekend-Regeln (08:00/09:30) sind entfernt. Wach + sonst
# nichts aktiv → Fallback open; noch schlafend → sleep hält zu, egal welche Uhrzeit.
def test_awake_morning_workday_is_open_not_timed_rule():
    # late_morning werktag, wach → kein fixer Zeit-Öffner mehr → Fallback open.
    d = decide(ctx(day_state=const.PHASE_LATE_MORNING,
                   day_context=const.DAY_CONTEXT_WERKTAG,
                   now_minutes=8 * 60 + 30, bio_state=const.BIO_AWAKE))
    assert d.mode == const.MODE_OPEN


def test_sleep_holds_in_morning_workday():
    # Gleiche Zeit, aber bio sleep → Sleep hält das Rollo zu (kein Uhr-Öffner).
    d = decide(ctx(day_state=const.PHASE_LATE_MORNING,
                   day_context=const.DAY_CONTEXT_WERKTAG,
                   now_minutes=8 * 60 + 30, bio_state=const.BIO_SLEEP))
    assert d.mode == const.MODE_SLEEP


def test_sleep_holds_in_weekend_forenoon():
    # forenoon frei, spät vormittags, aber bio sleep → Sleep hält (kein 09:30-Öffner).
    d = decide(ctx(day_state=const.PHASE_FORENOON,
                   day_context=const.DAY_CONTEXT_FREI,
                   now_minutes=10 * 60, bio_state=const.BIO_SLEEP))
    assert d.mode == const.MODE_SLEEP


def test_awake_weekend_forenoon_is_open():
    # forenoon wochenende, wach → Fallback open (kein zeitgebundener Öffner).
    d = decide(ctx(day_state=const.PHASE_FORENOON,
                   day_context=const.DAY_CONTEXT_WOCHENENDE,
                   now_minutes=10 * 60, bio_state=const.BIO_AWAKE))
    assert d.mode == const.MODE_OPEN


@pytest.mark.parametrize(
    "bio_state", [const.BIO_PROVISIONAL_SLEEP, const.BIO_SLEEP]
)
def test_effective_sleep_bio_selects_r4_with_five_percent(bio_state):
    d = decide(ctx(bio_state=bio_state))
    assert d.mode == const.MODE_SLEEP
    assert d.target_position == 5
    sleep_trace = next(entry for entry in d.trace if entry.rule == "R4")
    assert sleep_trace.matched is True


@pytest.mark.parametrize("day_state", [
    const.PHASE_EARLY_NIGHT,
    const.PHASE_LATE_NIGHT,
])
@pytest.mark.parametrize("bio_state", [const.BIO_AWAKE, const.BIO_WAKING])
def test_night_phase_uses_privacy_not_sleep(day_state, bio_state):
    d = decide(ctx(day_state=day_state, bio_state=bio_state, privacy_latch=True))
    assert d.mode == const.MODE_PRIVACY
    sleep_trace = next(entry for entry in d.trace if entry.rule == "R4")
    assert sleep_trace.matched is False
    assert sleep_trace.reason == "sleep:Bio-State provisional_sleep|sleep"


def test_early_morning_awake_is_not_sleep():
    # early_morning + awake → Sleep greift NICHT → open.
    d = decide(ctx(day_state=const.PHASE_EARLY_MORNING, bio_state=const.BIO_AWAKE))
    assert d.mode == const.MODE_OPEN


def test_early_morning_sleep_is_sleep():
    d = decide(ctx(day_state=const.PHASE_EARLY_MORNING, bio_state=const.BIO_SLEEP))
    assert d.mode == const.MODE_SLEEP


def test_waking_treated_like_awake_not_sleep():
    d = decide(ctx(day_state=const.PHASE_AFTERNOON, bio_state=const.BIO_WAKING))
    assert d.mode == const.MODE_OPEN


# --------------------------------------------------------------------------- #
# Heat (in-policy, mit bestehender direkter Solar-Eignung)
# --------------------------------------------------------------------------- #
def test_heat_active():
    d = decide(ctx(day_state=const.PHASE_FORENOON, lux=30000,
                   outdoor_temp=25, sun_elevation=20))
    assert d.mode == const.MODE_HEAT
    assert d.target_position == 45


def test_heat_active_partlycloudy_but_bright():
    """Live-Regression 2026-08-04: partlycloudy + 37 °C + 73k lx → Heat greift jetzt
    über die lokale Lux-Schwelle (DWD-Textlage ist keine Pflicht mehr)."""
    d = decide(ctx(day_state=const.PHASE_FORENOON, weather_condition="partlycloudy",
                   lux=73000, outdoor_temp=37, sun_elevation=51))
    assert d.mode == const.MODE_HEAT


def test_late_afternoon_warm_but_moderately_bright_stays_open():
    d = decide(
        ctx(
            day_state=const.PHASE_LATE_AFTERNOON,
            lux=5000,
            sun_elevation=20,
            outdoor_temp=30,
            presence_household=const.HOUSEHOLD_NOT_EMPTY,
        )
    )
    assert d.mode == const.MODE_OPEN
    assert d.target_position == 100
    assert d.protection_demand is not None
    assert d.protection_demand.thermal_active is False
    assert d.protection_demand.glare_active is False
    assert d.protection_demand.effective_target_position is None


def test_late_afternoon_cleared_auto_latch_allows_open_fallback():
    d = decide(
        ctx(
            day_state=const.PHASE_LATE_AFTERNOON,
            lux=5000,
            sun_elevation=20,
            outdoor_temp=30,
            privacy_latch=False,
        )
    )
    assert d.mode == const.MODE_OPEN
    assert d.reason.startswith("open:")


@pytest.mark.parametrize("day_state", [
    const.PHASE_LATE_MORNING,
    const.PHASE_FORENOON,
    const.PHASE_MIDDAY,
    const.PHASE_AFTERNOON,
])
def test_heat_active_from_late_morning_to_afternoon(day_state):
    d = decide(ctx(day_state=day_state, lux=30000,
                   outdoor_temp=25, sun_elevation=20))
    assert d.mode == const.MODE_HEAT


@pytest.mark.parametrize("day_state", [
    const.PHASE_MIDDAY,
    const.PHASE_AFTERNOON,
])
def test_heat_day_phases_stay_inactive_below_lux_floor(day_state):
    d = decide(ctx(day_state=day_state, lux=const.DEFAULT_HEAT_LUX_MIN - 1,
                   outdoor_temp=25, sun_elevation=20))
    assert d.mode == const.MODE_OPEN
    assert d.protection_demand is not None
    assert d.protection_demand.thermal_active is False


@pytest.mark.parametrize("day_state", [
    const.PHASE_MIDDAY,
    const.PHASE_AFTERNOON,
])
def test_heat_day_phases_stay_inactive_without_direct_sun(day_state):
    d = decide(ctx(day_state=day_state, lux=30000,
                   outdoor_temp=25, sun_elevation=const.HEAT_SUN_MIN_DEG))
    assert d.mode == const.MODE_OPEN
    assert d.protection_demand is not None
    assert d.protection_demand.thermal_active is False


def test_heat_requires_a_suitable_solar_phase_and_angle():
    d = decide(ctx(day_state=const.PHASE_EARLY_EVENING, lux=30000,
                   outdoor_temp=25, sun_elevation=0))
    assert d.mode == const.MODE_OPEN
    assert d.protection_demand is not None
    assert d.protection_demand.thermal_active is False


def test_heat_beats_daytime_open_workday():
    d = decide(ctx(day_state=const.PHASE_LATE_MORNING,
                   day_context=const.DAY_CONTEXT_WERKTAG,
                   now_minutes=8 * 60,
                   lux=30000, outdoor_temp=25, sun_elevation=20))
    assert d.mode == const.MODE_HEAT


def test_heat_beats_daytime_open_weekend():
    d = decide(ctx(day_state=const.PHASE_FORENOON,
                   day_context=const.DAY_CONTEXT_WOCHENENDE,
                   now_minutes=10 * 60,
                   lux=30000, outdoor_temp=25, sun_elevation=20))
    assert d.mode == const.MODE_HEAT


def test_heat_requires_direct_sun_even_when_weather_is_rainy():
    d = decide(ctx(day_state=const.PHASE_FORENOON, weather_condition="rainy",
                   lux=5000, outdoor_temp=30, sun_elevation=0))
    assert d.mode == const.MODE_OPEN
    assert d.protection_demand is not None
    assert d.protection_demand.thermal_active is False


def test_heat_does_not_create_state_without_solar_inputs():
    d = decide(ctx(day_state=const.PHASE_FORENOON, weather_condition="cloudy",
                   lux=None, outdoor_temp=25, sun_elevation=None))
    assert d.mode == const.MODE_OPEN
    assert d.protection_demand is not None
    assert d.protection_demand.thermal_active is False


def test_heat_needs_warm_enough():
    d = decide(ctx(day_state=const.PHASE_FORENOON, lux=30000,
                   outdoor_temp=23, sun_elevation=20))
    assert d.mode != const.MODE_HEAT


def test_heat_needs_sun_above_5():
    d = decide(ctx(day_state=const.PHASE_FORENOON, lux=30000,
                   outdoor_temp=25, sun_elevation=4))
    assert d.mode == const.MODE_OPEN


def test_heat_does_not_activate_in_late_evening():
    d = decide(ctx(day_state=const.PHASE_LATE_EVENING, lux=30000,
                   outdoor_temp=25, sun_elevation=20))
    assert d.mode == const.MODE_OPEN


def test_heat_beats_daytime_sleep():
    d = decide(ctx(day_state=const.PHASE_FORENOON, lux=30000,
                   outdoor_temp=25, sun_elevation=20, bio_state=const.BIO_SLEEP))
    # Sleep bleibt eine höhere bestehende Priorität vor der fusionierten Schutzschicht.
    assert d.mode == const.MODE_SLEEP


# --------------------------------------------------------------------------- #
# Bestehender Heat-Lux-Floor bleibt API-kompatibel und ist Teil der Solar-Eignung.
# --------------------------------------------------------------------------- #
def test_heat_lux_floor_controls_solar_eligibility():
    assert const.DEFAULT_HEAT_LUX_MIN == 10000
    warm = dict(day_state=const.PHASE_FORENOON, outdoor_temp=25, sun_elevation=20)
    assert decide(ctx(lux=9000, **warm), heat_lux_min=25000).mode == const.MODE_OPEN
    assert decide(ctx(lux=11000, **warm)).mode == const.MODE_HEAT


def test_heat_lux_floor_allows_sufficient_brightness():
    d = decide(ctx(day_state=const.PHASE_FORENOON, lux=17700,
                   outdoor_temp=35, sun_elevation=51), heat_lux_min=10000)
    assert d.mode == const.MODE_HEAT


def test_heat_lux_floor_zero_still_requires_sun_and_phase():
    d = decide(ctx(day_state=const.PHASE_FORENOON, lux=1,
                   outdoor_temp=25, sun_elevation=20), heat_lux_min=0)
    assert d.mode == const.MODE_HEAT


def test_heat_lux_floor_high_blocks_without_enough_brightness():
    d = decide(ctx(day_state=const.PHASE_FORENOON, lux=17000,
                   outdoor_temp=35, sun_elevation=50), heat_lux_min=25000)
    assert d.mode == const.MODE_OPEN


# --------------------------------------------------------------------------- #
# Issue #9 — gemeinsame ProtectionDemand
# --------------------------------------------------------------------------- #
def test_protection_demand_heat_and_glare_use_effective_heat_position():
    d = decide(
        ctx(
            day_state=const.PHASE_FORENOON,
            outdoor_temp=30,
            weather_condition="sunny",
            lux=50000,
            sun_elevation=30,
            media_scenario=const.SCENARIO_TV,
        ),
        gate_on=True,
    )
    demand = d.protection_demand
    assert demand is not None
    assert demand.thermal_active is True
    assert demand.glare_active is True
    assert demand.thermal_target_position == 45
    assert demand.glare_target_position == 60
    assert demand.effective_target_position == 45
    assert demand.effective_mode == const.MODE_HEAT
    assert d.mode == const.MODE_HEAT
    assert d.target_position == demand.effective_target_position


def test_protection_demand_heat_requires_solar_eligibility():
    d = decide(
        ctx(
            day_state=const.PHASE_EARLY_EVENING,
            outdoor_temp=30,
            weather_condition="rainy",
            lux=100,
            sun_elevation=0,
            media_scenario=const.SCENARIO_IDLE,
        ),
        gate_on=False,
    )
    assert d.mode == const.MODE_OPEN
    assert d.target_position == 100
    assert d.protection_demand is not None
    assert d.protection_demand.thermal_active is False
    assert d.protection_demand.glare_active is False


def test_protection_demand_holds_thermal_state_during_temperature_outage():
    demand = protection(
        ctx(outdoor_temp=None, lux=None, sun_elevation=None),
        previous_thermal_active=True,
    )
    assert demand.thermal_active is True
    assert demand.effective_mode == const.MODE_HEAT
    assert demand.diagnostics["thermal_state_held"] is True


def test_decision_holds_previous_thermal_state_when_temperature_is_unavailable():
    d = decide(
        ctx(outdoor_temp=None, lux=None, sun_elevation=None),
        gate_on=True,
        previous_thermal_active=True,
    )
    assert d.mode == const.MODE_HEAT
    assert d.target_position == 45
    assert d.protection_demand is not None
    assert d.protection_demand.diagnostics["thermal_state_held"] is True


def test_solar_input_outage_holds_previous_valid_thermal_state():
    d = decide(
        ctx(outdoor_temp=30, lux=None, sun_elevation=None),
        previous_thermal_active=True,
    )
    assert d.mode == const.MODE_HEAT
    assert d.protection_demand is not None
    assert d.protection_demand.diagnostics["thermal_state_held"] is True


def test_protection_demand_does_not_create_thermal_state_without_temperature():
    demand = protection(ctx(outdoor_temp=None), previous_thermal_active=None)
    assert demand.thermal_active is False
    assert demand.effective_mode is None


def test_low_temperature_direct_sun_tv_uses_only_glare_tv():
    d = decide(
        ctx(
            outdoor_temp=20,
            lux=50000,
            sun_elevation=30,
            media_scenario=const.SCENARIO_TV,
        ),
        gate_on=True,
    )
    assert d.mode == const.MODE_GLARE_TV
    assert d.target_position == 60
    assert d.protection_demand is not None
    assert d.protection_demand.thermal_active is False
    assert d.protection_demand.glare_active is True


def test_low_temperature_pc_gaming_uses_only_glare_pc():
    d = decide(
        ctx(
            outdoor_temp=20,
            lux=50000,
            sun_elevation=30,
            media_scenario=const.SCENARIO_GAMING,
            gaming_source=const.GAMING_PC,
        ),
        gate_on=True,
    )
    assert d.mode == const.MODE_GLARE_PC
    assert d.target_position == 75
    assert d.protection_demand is not None
    assert d.protection_demand.thermal_active is False
    assert d.protection_demand.glare_target_position == 75


def test_protection_demand_uses_axis_direction_for_inverted_profile():
    d = decide(
        ctx(
            day_state=const.PHASE_FORENOON,
            outdoor_temp=30,
            lux=30000,
            sun_elevation=30,
            media_scenario=const.SCENARIO_TV,
        ),
        gate_on=True,
        position_profile=const.DEFAULT_POSITION_PROFILE_INVERTED,
    )
    demand = d.protection_demand
    assert demand is not None
    assert demand.thermal_target_position == 55
    assert demand.glare_target_position == 40
    assert demand.effective_target_position == 55
    assert demand.effective_mode == const.MODE_HEAT
    assert d.target_position == 55


@pytest.mark.parametrize("day_state", [
    const.PHASE_FORENOON,
    const.PHASE_MIDDAY,
    const.PHASE_AFTERNOON,
])
def test_policy_and_diagnostic_trace_share_one_effective_protection_demand(day_state):
    d = decide(
        ctx(day_state=day_state, outdoor_temp=30, lux=30000,
            sun_elevation=30, media_scenario=const.SCENARIO_TV),
        gate_on=True,
    )
    payload = d.as_dict()
    protection_payload = payload["protection_demand"]
    protection_trace = next(entry for entry in payload["trace"] if entry["rule"] == "R6")
    assert protection_payload["effective_target_position"] == d.target_position == 45
    assert protection_trace["position"] == protection_payload["effective_target_position"]
    assert protection_trace["mode"] == protection_payload["effective_mode"] == const.MODE_HEAT


def test_higher_existing_priorities_still_beat_fused_protection():
    assert decide(ctx(window_open=True, outdoor_temp=30), gate_on=True).mode == const.MODE_WINDOW_OPEN
    assert decide(ctx(presence_household=const.HOUSEHOLD_EMPTY, outdoor_temp=30)).mode == const.MODE_PRIVACY
    assert decide(ctx(bio_state=const.BIO_SLEEP, outdoor_temp=30)).mode == const.MODE_SLEEP


def test_unavailable_glare_input_does_not_block_valid_thermal_protection():
    d = decide(ctx(outdoor_temp=30, media_scenario=None, lux=30000, sun_elevation=20))
    assert d.mode == const.MODE_HEAT
    assert d.protection_demand is not None
    assert d.protection_demand.thermal_active is True
    assert d.protection_demand.glare_active is False


# --------------------------------------------------------------------------- #
# R9/R10 — Glare (nur bei aktivem Lux-Gate)
# --------------------------------------------------------------------------- #
def test_glare_tv_with_gate():
    d = decide(ctx(media_scenario=const.SCENARIO_TV), gate_on=True)
    assert d.mode == const.MODE_GLARE_TV
    assert d.target_position == 60


def test_glare_tv_streaming_and_gaming_non_pc():
    for scen, src in [(const.SCENARIO_STREAMING, const.GAMING_NONE),
                      (const.SCENARIO_GAMING, const.GAMING_TV)]:
        d = decide(ctx(media_scenario=scen, gaming_source=src), gate_on=True)
        assert d.mode == const.MODE_GLARE_TV


def test_glare_blocked_without_gate():
    d = decide(ctx(media_scenario=const.SCENARIO_TV), gate_on=False)
    assert d.mode == const.MODE_OPEN


def test_glare_pc_with_gate():
    d = decide(ctx(media_scenario=const.SCENARIO_GAMING, gaming_source=const.GAMING_PC),
               gate_on=True)
    assert d.mode == const.MODE_GLARE_PC
    assert d.target_position == 75


def test_glare_pc_not_when_sleep():
    d = decide(ctx(media_scenario=const.SCENARIO_GAMING, gaming_source=const.GAMING_PC,
                   bio_state=const.BIO_SLEEP), gate_on=True)
    assert d.mode == const.MODE_SLEEP


# --------------------------------------------------------------------------- #
# R9 — Fallback
# --------------------------------------------------------------------------- #
def test_fallback_open():
    d = decide(ctx())
    assert d.mode == const.MODE_OPEN
    assert d.target_position == 100


# --------------------------------------------------------------------------- #
# Lux-Gate (Schmitt-Trigger §R-G)
# --------------------------------------------------------------------------- #
def test_lux_gate_opens_above_20k():
    assert policy.lux_gate(21000, False, sun_elevation=10,
                           day_state=const.PHASE_FORENOON) is True


def test_lux_gate_closes_below_15k():
    assert policy.lux_gate(14000, True, sun_elevation=10,
                           day_state=const.PHASE_FORENOON) is False


def test_lux_gate_grey_zone_holds_prev():
    assert policy.lux_gate(17000, True, sun_elevation=10,
                           day_state=const.PHASE_FORENOON) is True
    assert policy.lux_gate(17000, False, sun_elevation=10,
                           day_state=const.PHASE_FORENOON) is False


def test_lux_gate_unknown_holds_prev():
    assert policy.lux_gate(None, True, sun_elevation=10,
                           day_state=const.PHASE_FORENOON) is True


def test_lux_gate_unknown_inputs_hold_and_numeric_reassessment_is_immediate():
    assert policy.lux_gate(21000, True, sun_elevation=None,
                           day_state=const.PHASE_FORENOON) is True
    assert policy.lux_gate(21000, True, sun_elevation=10,
                           day_state=None) is True
    assert policy.lux_gate(21000, False, sun_elevation=10,
                           day_state=const.PHASE_FORENOON) is True
    assert policy.lux_gate(14000, True, sun_elevation=10,
                           day_state=const.PHASE_FORENOON) is False


def test_lux_gate_needs_sun_above_5():
    assert policy.lux_gate(50000, True, sun_elevation=3,
                           day_state=const.PHASE_FORENOON) is False


def test_lux_gate_needs_daytime_phase():
    assert policy.lux_gate(50000, True, sun_elevation=10,
                           day_state=const.PHASE_LATE_EVENING) is False


# --------------------------------------------------------------------------- #
# Gating-Overlay (verändert Modus nicht, nur apply_allowed/blockers)
# --------------------------------------------------------------------------- #
def test_apply_disabled_blocks_but_keeps_mode():
    d = decide(ctx(bio_state=const.BIO_SLEEP), apply_enabled=False)
    assert d.mode == const.MODE_SLEEP
    assert d.apply_allowed is False
    assert "apply_disabled" in d.blockers


def test_startup_block():
    d = decide(ctx(bio_state=const.BIO_SLEEP), startup_ready=False)
    assert d.apply_allowed is False
    assert "startup_block" in d.blockers


def test_manual_override_blocks():
    d = decide(ctx(bio_state=const.BIO_SLEEP), manual_override_active=True)
    assert d.mode == const.MODE_SLEEP
    assert d.apply_allowed is False
    assert "manual_override" in d.blockers


def test_day_state_unknown_blocks():
    d = decide(ctx(day_state=None))
    assert "source_unknown:day_state" in d.blockers
    assert d.apply_allowed is False


# --------------------------------------------------------------------------- #
# Decision-Trace (für Panel)
# --------------------------------------------------------------------------- #
def test_trace_has_all_rules_and_winner():
    d = decide(ctx(media_scenario=const.SCENARIO_TV), gate_on=True)
    assert len(d.trace) == 9
    matched = [e for e in d.trace if e.matched and e.candidate]
    # R6 ist die einzige konkurrierende Schutzregel; R7/R8 sind Diagnosezeilen.
    assert matched[0].rule == "R6"
    assert d.mode == matched[0].mode
    assert any(e.rule == "R7" and e.matched and not e.candidate for e in d.trace)


def test_privacy_trace_distinguishes_manual_and_automatic_reasons():
    manual = decide(ctx(privacy_bed=True))
    manual_trace = next(entry for entry in manual.trace if entry.rule == "R2")
    assert manual_trace.reason == "privacy:manual:privacy_bed"
    assert manual.reason == manual_trace.reason

    automatic = decide(ctx(privacy_latch=True))
    automatic_trace = next(entry for entry in automatic.trace if entry.rule == "R5")
    assert automatic_trace.reason == "privacy:evening:auto_latch"
    assert automatic.reason == automatic_trace.reason

    away = decide(ctx(presence_household=const.HOUSEHOLD_EMPTY))
    away_trace = next(entry for entry in away.trace if entry.rule == "R5")
    assert away_trace.reason == "privacy:away:household_empty"


# --------------------------------------------------------------------------- #
# R-PL — Privacy-Latch-Prädikate
# --------------------------------------------------------------------------- #
def test_latch_set_on_enter_early_night():
    assert policy.privacy_latch_should_set(
        const.PHASE_EARLY_NIGHT, const.PHASE_LATE_EVENING, None) is True


def test_latch_set_dark_late_evening():
    assert policy.privacy_latch_should_set(
        const.PHASE_LATE_EVENING, const.PHASE_LATE_EVENING, 300) is True
    assert policy.privacy_latch_should_set(
        const.PHASE_LATE_EVENING, const.PHASE_LATE_EVENING, 600) is False


def test_latch_no_set_on_same_early_night():
    assert policy.privacy_latch_should_set(
        const.PHASE_EARLY_NIGHT, const.PHASE_EARLY_NIGHT, None) is False


def test_latch_recovery():
    assert policy.privacy_latch_recovery(const.PHASE_EARLY_NIGHT, None) is True
    assert policy.privacy_latch_recovery(const.PHASE_LATE_EVENING, 100) is True
    assert policy.privacy_latch_recovery(const.PHASE_AFTERNOON, 100) is False


def test_latch_reset_on_sunrise():
    assert policy.privacy_latch_should_reset(const.BIO_SLEEP, const.BIO_SLEEP, True) is True


def test_latch_reset_on_wake():
    assert policy.privacy_latch_should_reset(const.BIO_AWAKE, const.BIO_SLEEP, False) is True
    assert policy.privacy_latch_should_reset(const.BIO_WAKING, const.BIO_SLEEP, False) is True


def test_latch_no_reset_while_sleeping():
    assert policy.privacy_latch_should_reset(const.BIO_SLEEP, const.BIO_SLEEP, False) is False


def test_manual_override_reset_on_sleep_entry():
    assert policy.manual_override_should_reset_on_sleep(
        const.BIO_SLEEP, const.BIO_AWAKE
    ) is True
    assert policy.manual_override_should_reset_on_sleep(
        const.BIO_SLEEP, const.BIO_WAKING
    ) is True
    assert policy.manual_override_should_reset_on_sleep(
        const.BIO_PROVISIONAL_SLEEP, const.BIO_AWAKE
    ) is True


def test_manual_override_no_reset_without_sleep_entry():
    assert policy.manual_override_should_reset_on_sleep(
        const.BIO_SLEEP, const.BIO_SLEEP
    ) is False
    assert policy.manual_override_should_reset_on_sleep(
        const.BIO_SLEEP, const.BIO_PROVISIONAL_SLEEP
    ) is False


def test_latch_never_sets_in_late_afternoon():
    assert policy.privacy_latch_should_set(
        const.PHASE_LATE_AFTERNOON, const.PHASE_LATE_EVENING, 5000
    ) is False


def test_latch_resets_for_bright_late_afternoon_only_with_numeric_lux():
    assert policy.privacy_latch_should_reset_for_daylight(
        const.PHASE_LATE_AFTERNOON, 5000
    ) is True
    assert policy.privacy_latch_should_reset_for_daylight(
        const.PHASE_LATE_AFTERNOON, 300
    ) is False
    assert policy.privacy_latch_should_reset_for_daylight(
        const.PHASE_LATE_AFTERNOON, None
    ) is False
    assert policy.manual_override_should_reset_on_sleep(
        const.BIO_AWAKE, const.BIO_SLEEP
    ) is False
    assert policy.manual_override_should_reset_on_sleep(
        const.BIO_SLEEP, None
    ) is False


# --------------------------------------------------------------------------- #
# R-OW — Override-Warden-Prädikate
# --------------------------------------------------------------------------- #
def test_position_within_tolerance():
    assert policy.position_within_tolerance(58, 60) is True   # ±3%
    assert policy.position_within_tolerance(55, 60) is False
    assert policy.position_within_tolerance(None, 60) is False


def test_warden_immediate_clear():
    assert policy.override_warden_immediate_clear(True, False) is True   # Race-Echo
    assert policy.override_warden_immediate_clear(False, True) is True   # schon auf Ziel
    assert policy.override_warden_immediate_clear(False, False) is False


def test_warden_sweep_clear():
    assert policy.override_warden_sweep_clear(301, False, True) is True
    assert policy.override_warden_sweep_clear(200, False, True) is False  # zu jung
    assert policy.override_warden_sweep_clear(301, True, True) is False   # fährt noch
    assert policy.override_warden_sweep_clear(301, False, False) is False  # nicht auf Ziel


# --------------------------------------------------------------------------- #
# Positions-Adapter — logische ↔ physische Cover-Achse (Invert)
# --------------------------------------------------------------------------- #
def test_mirror_position_off_is_identity():
    for p in (0, 40, 60, 100, 12.5, None):
        assert policy.mirror_position(p, False) == p


def test_mirror_position_on_flips_axis():
    assert policy.mirror_position(0, True) == 100
    assert policy.mirror_position(100, True) == 0
    assert policy.mirror_position(40, True) == 60      # privacy/sleep
    assert policy.mirror_position(75, True) == 25       # glare_pc
    assert policy.mirror_position(12.5, True) == 87.5   # float Ist-Position


def test_mirror_position_none_stays_none():
    assert policy.mirror_position(None, True) is None


def test_mirror_position_is_involution():
    # Zweimal spiegeln ergibt das Original.
    for p in (0, 33, 60, 100):
        assert policy.mirror_position(policy.mirror_position(p, True), True) == p


def test_default_inverted_profile_mirrors_except_direct_sleep_target():
    """Sleep is the same direct 5 % device target on either stored profile."""
    for mode, pos in const.DEFAULT_POSITION_PROFILE.items():
        expected = 5 if mode == const.MODE_SLEEP else 100 - pos
        assert const.DEFAULT_POSITION_PROFILE_INVERTED[mode] == expected
    # gleiche Modus-Menge, keine Lücken
    assert set(const.DEFAULT_POSITION_PROFILE_INVERTED) == set(const.DEFAULT_POSITION_PROFILE)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))


def test_manual_modes_have_profile_positions():
    """Jeder im Panel manuell wählbare Modus muss eine gültige Profil-Position
    (0..100) liefern — schützt vor Tippfehlern in MANUAL_MODES."""
    for mode in const.MANUAL_MODES:
        assert mode in const.DEFAULT_POSITION_PROFILE, mode
        pos = policy._position(mode, const.DEFAULT_POSITION_PROFILE)
        assert pos is not None and 0 <= pos <= 100, (mode, pos)
