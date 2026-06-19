"""ConfigEntry migrations for Benni Blind Policy."""
from __future__ import annotations

from typing import Any

from .const import (
    CONF_WINDOW_OPEN,
    CORE_OPENINGS_MASTER_ENTITY,
    CORE_WINDOW_OPEN_ENTITY,
    LEGACY_WINDOW_OPEN_ENTITY,
)

WINDOW_SOURCE_REPLACEMENTS = {
    LEGACY_WINDOW_OPEN_ENTITY: CORE_OPENINGS_MASTER_ENTITY,
    CORE_WINDOW_OPEN_ENTITY: CORE_OPENINGS_MASTER_ENTITY,
}


def migrate_source_ids(
    data: dict[str, Any],
    options: dict[str, Any],
) -> tuple[bool, dict[str, Any], dict[str, Any]]:
    """Return migrated ConfigEntry data/options without mutating the inputs."""
    new_data = dict(data or {})
    new_options = dict(options or {})
    changed = False

    if new_data.get(CONF_WINDOW_OPEN) in WINDOW_SOURCE_REPLACEMENTS:
        new_data[CONF_WINDOW_OPEN] = WINDOW_SOURCE_REPLACEMENTS[new_data[CONF_WINDOW_OPEN]]
        changed = True
    if new_options.get(CONF_WINDOW_OPEN) in WINDOW_SOURCE_REPLACEMENTS:
        new_options[CONF_WINDOW_OPEN] = WINDOW_SOURCE_REPLACEMENTS[new_options[CONF_WINDOW_OPEN]]
        changed = True

    return changed, new_data, new_options
