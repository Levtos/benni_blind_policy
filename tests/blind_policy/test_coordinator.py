"""Fokussierte Apply-Gates des Blind-Policy-Coordinators."""

from __future__ import annotations

import asyncio
import sys
import types
from types import SimpleNamespace


def _install_homeassistant_stubs() -> None:
    """Lädt den Coordinator ohne eine Home-Assistant-Installation."""
    homeassistant = types.ModuleType("homeassistant")
    homeassistant.__path__ = []
    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigEntry = object
    const = types.ModuleType("homeassistant.const")
    const.EVENT_HOMEASSISTANT_STARTED = "homeassistant_started"
    core = types.ModuleType("homeassistant.core")
    core.CALLBACK_TYPE = object
    core.Event = object
    core.HomeAssistant = object
    core.callback = lambda fn: fn
    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    event = types.ModuleType("homeassistant.helpers.event")

    def _unsubscribe(*_args, **_kwargs):
        return lambda: None

    event.async_call_later = _unsubscribe
    event.async_track_state_change_event = _unsubscribe
    event.async_track_time_interval = _unsubscribe
    storage = types.ModuleType("homeassistant.helpers.storage")
    storage.Store = object
    util = types.ModuleType("homeassistant.util")
    util.__path__ = []
    util_dt = types.ModuleType("homeassistant.util.dt")
    util_dt.now = lambda: None

    homeassistant.config_entries = config_entries
    homeassistant.const = const
    homeassistant.core = core
    homeassistant.helpers = helpers
    homeassistant.util = util
    helpers.event = event
    helpers.storage = storage
    util.dt = util_dt
    sys.modules.update(
        {
            "homeassistant": homeassistant,
            "homeassistant.config_entries": config_entries,
            "homeassistant.const": const,
            "homeassistant.core": core,
            "homeassistant.helpers": helpers,
            "homeassistant.helpers.event": event,
            "homeassistant.helpers.storage": storage,
            "homeassistant.util": util,
            "homeassistant.util.dt": util_dt,
        }
    )


_install_homeassistant_stubs()

from bbp_pure_pkg import const  # noqa: E402
from bbp_pure_pkg import coordinator as coordinator_module  # noqa: E402


def _run(awaitable):
    return asyncio.run(awaitable)


def _make_coordinator(monkeypatch):
    clock = {"now": 100.0}
    monkeypatch.setattr(coordinator_module.time, "monotonic", lambda: clock["now"])

    class Services:
        def __init__(self):
            self.calls = []

        async def async_call(self, domain, service, data, *, blocking):
            self.calls.append((domain, service, data, blocking))

    services = Services()
    tasks = []

    def create_task(coro):
        task = asyncio.create_task(coro)
        tasks.append(task)
        return task

    hass = SimpleNamespace(
        data={},
        services=services,
        async_create_task=create_task,
    )
    entry = SimpleNamespace(
        entry_id="test-entry",
        data={
            const.CONF_COVER_ENTITY: "cover.test",
            const.CONF_APPLY_ENABLED: True,
        },
        options={},
    )
    coord = object.__new__(coordinator_module.BlindPolicyCoordinator)
    coord.hass = hass
    coord.entry = entry
    coord._writing_active = False
    coord._writing_off_ts = None
    coord._writing_release_unsub = None
    coord._writing_timeout_unsub = None
    coord._automatic_recheck_unsub = None
    coord._last_auto_apply_ts = None
    coord._last_apply_ts = 0.0
    coord._last_target = None
    coord._rest_pos = None
    coord._manual_override = False
    coord._manual_explicit = False
    coord._manual_mode = None
    coord._manual_target = None
    coord._override_set_ts = None
    coord._listeners = []
    current = {"position": 0.0}
    coord._cover_position = lambda: current["position"]
    coord._cover_moving = lambda: False
    coord._schedule_writing_release = lambda: None
    scheduled = []
    coord._schedule_automatic_recheck = lambda delay: scheduled.append(delay)
    return coord, clock, services, scheduled, tasks, current


def test_identical_target_position_does_not_call_service(monkeypatch):
    coord, _clock, services, _scheduled, _tasks, current = _make_coordinator(monkeypatch)
    current["position"] = 40

    _run(coord._apply(40))

    assert services.calls == []


def test_automatic_apply_is_debounced_for_60_seconds(monkeypatch):
    coord, clock, services, scheduled, _tasks, _current = _make_coordinator(monkeypatch)

    _run(coord._apply(40))
    coord._writing_active = False
    clock["now"] = 110
    _run(coord._apply(45))

    assert [call[2]["position"] for call in services.calls] == [40]
    assert scheduled == [50]
    assert const.AUTOMATIC_APPLY_COOLDOWN_SECONDS == 60


def test_automatic_counter_command_is_suppressed_while_writing_active(monkeypatch):
    coord, _clock, services, _scheduled, _tasks, _current = _make_coordinator(monkeypatch)
    coord._writing_active = True

    _run(coord._apply(45))

    assert services.calls == []


def test_cooldown_rechecks_latest_policy_decision_without_queueing_target(monkeypatch):
    coord, clock, services, _scheduled, tasks, _current = _make_coordinator(monkeypatch)
    del coord._schedule_automatic_recheck
    pending = []

    def schedule(_hass, delay, callback):
        pending.append((delay, callback))
        return lambda: None

    monkeypatch.setattr(coordinator_module, "async_call_later", schedule)
    latest = {"target": 75}

    async def current_evaluation():
        await coord._apply(latest["target"])

    coord.async_evaluate = current_evaluation

    async def scenario():
        await coord._apply(40)
        coord._writing_active = False
        clock["now"] = 110
        await coord._apply(45)
        assert pending[0][0] == 50
        latest["target"] = 75
        clock["now"] = 160
        pending[0][1](None)
        await asyncio.gather(*tasks)

    _run(scenario())

    assert [call[2]["position"] for call in services.calls] == [40, 75]


def test_manual_panel_position_bypasses_cooldown_and_writing_guard(monkeypatch):
    coord, clock, services, _scheduled, _tasks, _current = _make_coordinator(monkeypatch)

    _run(coord._apply(40))
    clock["now"] = 110
    coord._writing_active = True
    force_flags = []

    async def manual_evaluation(*, force_apply=False):
        force_flags.append(force_apply)

    coord.async_evaluate = manual_evaluation
    _run(coord.async_set_manual_position(55))

    assert [call[2]["position"] for call in services.calls] == [40, 55]
    assert force_flags == [True]


def test_window_open_automatic_apply_bypasses_cooldown_and_writing(monkeypatch):
    coord, clock, services, _scheduled, _tasks, _current = _make_coordinator(monkeypatch)
    coord._last_auto_apply_ts = 100
    coord._writing_active = True
    clock["now"] = 110

    _run(coord._apply(100, immediate=True))

    assert [call[2]["position"] for call in services.calls] == [100]


def test_recent_apply_guard_keeps_its_eight_second_manual_override_semantics(monkeypatch):
    coord, clock, _services, _scheduled, _tasks, _current = _make_coordinator(monkeypatch)
    coord._rest_pos = 40
    coord._last_target = 60
    coord._last_apply_ts = 100
    coord._cover_moving = lambda: False

    def state(position):
        return SimpleNamespace(state="ready", attributes={"current_position": position})

    clock["now"] = 100 + const.RECENT_APPLY_GUARD_SECONDS
    coord._detect_manual_override(
        SimpleNamespace(data={"new_state": state(50), "entity_id": "cover.test"})
    )
    assert coord.manual_override_active is False

    clock["now"] += 1
    coord._detect_manual_override(
        SimpleNamespace(data={"new_state": state(55), "entity_id": "cover.test"})
    )
    assert coord.manual_override_active is True
