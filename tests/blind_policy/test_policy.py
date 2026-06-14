"""Pure-Logic-Tests der Blind-Policy-Decision-Engine (Lastenheft-konform)."""
from __future__ import annotations

import bbp_const as const
import bbp_policy as policy
import pytest

DECIDE_KW = dict(startup_ready=True, apply_enabled=True, manual_override_active=False)


def ctx(**over):
    """Default-Context, der ohne Override auf R11 (open) fällt."""
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


# --------------------------------------------------------------------------- #
# Positionen je Modus (Lastenheft §6)
# --------------------------------------------------------------------------- #
def test_default_position_profile_matches_lastenheft():
    p = const.DEFAULT_POSITION_PROFILE
    assert p[const.MODE_WINDOW_OPEN] == 100
    assert p[const.MODE_PRIVACY_BED] == 40
    assert p[const.MODE_PRIVACY] == 40
    assert p[const.MODE_ALARM_WAKEUP] == 100
    assert p[const.MODE_OPEN_WEEKDAY] == 100
    assert p[const.MODE_OPEN_WEEKEND] == 100
    assert p[const.MODE_SLEEP] == 40
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
# Prioritätskette R2..R11
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


def test_alarm_wakeup_prio3():
    d = decide(ctx(alarm_wakeup=True, bio_state=const.BIO_SLEEP,
                   day_state=const.PHASE_EARLY_NIGHT))
    assert d.mode == const.MODE_ALARM_WAKEUP
    assert d.target_position == 100


def test_open_weekday_after_8():
    d = decide(ctx(day_state=const.PHASE_LATE_MORNING,
                   day_context=const.DAY_CONTEXT_WERKTAG, now_minutes=8 * 60))
    assert d.mode == const.MODE_OPEN_WEEKDAY


def test_open_weekday_before_8_falls_through():
    # 07:59, late_morning werktag → R5 greift NICHT; bio awake → fällt auf open.
    d = decide(ctx(day_state=const.PHASE_LATE_MORNING,
                   day_context=const.DAY_CONTEXT_WERKTAG, now_minutes=7 * 60 + 59))
    assert d.mode == const.MODE_OPEN


def test_open_weekday_beats_sleep():
    # late_morning werktag 08:30, aber bio sleep → R5 schlägt R7 (natürlicher Wecker).
    d = decide(ctx(day_state=const.PHASE_LATE_MORNING,
                   day_context=const.DAY_CONTEXT_WERKTAG,
                   now_minutes=8 * 60 + 30, bio_state=const.BIO_SLEEP))
    assert d.mode == const.MODE_OPEN_WEEKDAY


def test_open_weekend_forenoon_after_930_frei():
    d = decide(ctx(day_state=const.PHASE_FORENOON,
                   day_context=const.DAY_CONTEXT_FREI, now_minutes=9 * 60 + 30))
    assert d.mode == const.MODE_OPEN_WEEKEND


def test_open_weekend_wochenende_equiv_frei():
    d = decide(ctx(day_state=const.PHASE_FORENOON,
                   day_context=const.DAY_CONTEXT_WOCHENENDE, now_minutes=10 * 60))
    assert d.mode == const.MODE_OPEN_WEEKEND


def test_sleep_bio():
    d = decide(ctx(bio_state=const.BIO_SLEEP))
    assert d.mode == const.MODE_SLEEP
    assert d.target_position == 40


def test_sleep_night_phase():
    d = decide(ctx(day_state=const.PHASE_LATE_NIGHT))
    assert d.mode == const.MODE_SLEEP


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
# R8 — Heat (in-policy, kein Lux-Gate)
# --------------------------------------------------------------------------- #
def test_heat_active():
    d = decide(ctx(day_state=const.PHASE_FORENOON, weather_condition="sunny",
                   outdoor_temp=25, sun_elevation=20))
    assert d.mode == const.MODE_HEAT
    assert d.target_position == 45


def test_heat_needs_sunny():
    d = decide(ctx(day_state=const.PHASE_FORENOON, weather_condition="rainy",
                   outdoor_temp=25, sun_elevation=20))
    assert d.mode != const.MODE_HEAT


def test_heat_needs_warm_enough():
    d = decide(ctx(day_state=const.PHASE_FORENOON, weather_condition="sunny",
                   outdoor_temp=23, sun_elevation=20))
    assert d.mode != const.MODE_HEAT


def test_heat_needs_sun_above_5():
    d = decide(ctx(day_state=const.PHASE_FORENOON, weather_condition="sunny",
                   outdoor_temp=25, sun_elevation=4))
    assert d.mode != const.MODE_HEAT


def test_heat_not_in_afternoon():
    d = decide(ctx(day_state=const.PHASE_AFTERNOON, weather_condition="sunny",
                   outdoor_temp=25, sun_elevation=20))
    assert d.mode != const.MODE_HEAT


def test_heat_not_when_sleep():
    d = decide(ctx(day_state=const.PHASE_FORENOON, weather_condition="sunny",
                   outdoor_temp=25, sun_elevation=20, bio_state=const.BIO_SLEEP))
    # sleep (R7) hat höhere Priorität als heat (R8)
    assert d.mode == const.MODE_SLEEP


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
# R11 — Fallback
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
def test_trace_has_all_eleven_rules_and_winner():
    d = decide(ctx(media_scenario=const.SCENARIO_TV), gate_on=True)
    assert len(d.trace) == 11
    matched = [e for e in d.trace if e.matched]
    # erster matched ist der Gewinner (glare_tv = R9)
    assert matched[0].rule == "R9"
    assert d.mode == matched[0].mode


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


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))


def test_manual_modes_have_profile_positions():
    """Jeder im Panel manuell wählbare Modus muss eine gültige Profil-Position
    (0..100) liefern — schützt vor Tippfehlern in MANUAL_MODES."""
    for mode in const.MANUAL_MODES:
        assert mode in const.DEFAULT_POSITION_PROFILE, mode
        pos = policy._position(mode, const.DEFAULT_POSITION_PROFILE)
        assert pos is not None and 0 <= pos <= 100, (mode, pos)
