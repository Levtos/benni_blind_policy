"""Tests for ConfigEntry source migrations."""
from __future__ import annotations

import bbp_const as const
import bbp_migration as migration


def test_window_open_prefill_uses_core_devices_contract():
    prefill = const.PROFILE_PREFILL[const.PROFILE_BENNI]

    assert prefill[const.CONF_WINDOW_OPEN] == const.CORE_WINDOW_OPEN_ENTITY


def test_migrates_legacy_window_open_source_in_data_and_options():
    changed, data, options = migration.migrate_source_ids(
        {const.CONF_WINDOW_OPEN: const.LEGACY_WINDOW_OPEN_ENTITY},
        {const.CONF_WINDOW_OPEN: const.LEGACY_WINDOW_OPEN_ENTITY},
    )

    assert changed is True
    assert data[const.CONF_WINDOW_OPEN] == const.CORE_WINDOW_OPEN_ENTITY
    assert options[const.CONF_WINDOW_OPEN] == const.CORE_WINDOW_OPEN_ENTITY


def test_migration_is_noop_for_current_source():
    changed, data, options = migration.migrate_source_ids(
        {const.CONF_WINDOW_OPEN: const.CORE_WINDOW_OPEN_ENTITY},
        {},
    )

    assert changed is False
    assert data[const.CONF_WINDOW_OPEN] == const.CORE_WINDOW_OPEN_ENTITY
    assert options == {}
