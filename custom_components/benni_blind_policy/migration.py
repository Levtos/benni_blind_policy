"""ConfigEntry migrations for Benni Blind Policy."""
from __future__ import annotations

from typing import Any

from .const import CONF_WINDOW_OPEN, CORE_WINDOW_OPEN_ENTITY, LEGACY_WINDOW_OPEN_ENTITY


def migrate_source_ids(
    data: dict[str, Any],
    options: dict[str, Any],
) -> tuple[bool, dict[str, Any], dict[str, Any]]:
    """Return migrated ConfigEntry data/options without mutating the inputs."""
    new_data = dict(data or {})
    new_options = dict(options or {})
    changed = False

    if new_data.get(CONF_WINDOW_OPEN) == LEGACY_WINDOW_OPEN_ENTITY:
        new_data[CONF_WINDOW_OPEN] = CORE_WINDOW_OPEN_ENTITY
        changed = True
    if new_options.get(CONF_WINDOW_OPEN) == LEGACY_WINDOW_OPEN_ENTITY:
        new_options[CONF_WINDOW_OPEN] = CORE_WINDOW_OPEN_ENTITY
        changed = True

    return changed, new_data, new_options
