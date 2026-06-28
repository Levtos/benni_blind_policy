"""Tests for ConfigEntry source migrations."""
from __future__ import annotations

import bbp_const as const
import bbp_migration as migration


def test_benni_prefill_uses_blind_master_contract():
    prefill = const.PROFILE_PREFILL[const.PROFILE_BENNI]

    assert const.SOURCE_KEYS == (const.CONF_BLIND_MASTER,)
    assert prefill[const.CONF_BLIND_MASTER] == const.CORE_BLIND_MASTER_ENTITY


def test_migrates_legacy_cover_source_in_data_and_options():
    changed, data, options = migration.migrate_source_ids(
        {const.CONF_COVER_ENTITY: const.LEGACY_COVER_ENTITY},
        {const.CONF_COVER_ENTITY: const.LEGACY_COVER_ENTITY},
    )

    assert changed is True
    assert data[const.CONF_BLIND_MASTER] == const.CORE_BLIND_MASTER_ENTITY
    assert data[const.CONF_COVER_ENTITY] == const.CORE_COVER_ENTITY
    assert options[const.CONF_COVER_ENTITY] == const.CORE_COVER_ENTITY


def test_migrates_legacy_window_open_source_in_data_and_options():
    changed, data, options = migration.migrate_source_ids(
        {const.CONF_WINDOW_OPEN: const.LEGACY_WINDOW_OPEN_ENTITY},
        {const.CONF_WINDOW_OPEN: const.LEGACY_WINDOW_OPEN_ENTITY},
    )

    assert changed is True
    assert data[const.CONF_BLIND_MASTER] == const.CORE_BLIND_MASTER_ENTITY
    assert data[const.CONF_WINDOW_OPEN] == const.CORE_OPENINGS_MASTER_ENTITY
    assert options[const.CONF_WINDOW_OPEN] == const.CORE_OPENINGS_MASTER_ENTITY


def test_migrates_previous_core_window_source_to_master():
    changed, data, options = migration.migrate_source_ids(
        {const.CONF_WINDOW_OPEN: const.CORE_WINDOW_OPEN_ENTITY},
        {},
    )

    assert changed is True
    assert data[const.CONF_BLIND_MASTER] == const.CORE_BLIND_MASTER_ENTITY
    assert data[const.CONF_WINDOW_OPEN] == const.CORE_OPENINGS_MASTER_ENTITY
    assert options == {}


def test_migration_is_noop_for_current_master_source():
    changed, data, options = migration.migrate_source_ids(
        {const.CONF_BLIND_MASTER: const.CORE_BLIND_MASTER_ENTITY},
        {},
    )

    assert changed is False
    assert data[const.CONF_BLIND_MASTER] == const.CORE_BLIND_MASTER_ENTITY
    assert options == {}
