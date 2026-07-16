# CLAUDE.md — Blind Policy

## GitLab Workflow

- GitLab project `ha-platform/control` is the central workflow truth.
- Relevant work requires a GitLab issue in `ha-platform/control`.
- Before work starts, read the issue description and all issue notes.
- Document current state, decisions, scope changes, tests, commits, merge requests, blockers, and completion in the issue.
- Code changes happen in the matching GitLab repository. `origin` must point to GitLab.
- GitHub is only the public distribution and HACS mirror. Do not develop directly on GitHub and do not push manually to GitHub.
- Plane and Forgejo are historical sources only and are not used for active work.
- Full rules live in `ha-platform/control/AGENTS.md`, `ha-platform/control/CLAUDE.md`, and `ha-platform/control/docs/workflow/`.

## Project-Memory Bootstrap

- Before significant work, read the matching GitLab issue description and all notes, then `ha-platform/control/docs/workflow/README.md`, its linked workflow documents, and relevant `ha-platform/control` wiki pages.
- GitLab is the workflow truth. GitHub is only the distribution/HACS mirror; do not develop there directly. Plane is frozen historical context, and Forgejo is out of service.
- Stay inside the decided issue scope: no side quests and no overwriting foreign branches or dirty worktrees.
- Use the smallest sufficient verification for the risk tier. Stable changes to behavior, contracts, operations, or rules belong in the wiki; use live evidence when runtime behavior must be proved. Completion notes must document wiki impact, verification/tests, release state where applicable, and required live evidence.

## Safety

- Do not put secrets in issues, commits, logs, or reports.
- Do not touch production Home Assistant systems without explicit approval.
- No admin, delete, runner, or bulk actions without explicit approval.

**Status:** v0.1.0 Erstbau. Backend + Pure-Logic-Tests grün, Live-Verify offen.
**Letzte Aktualisierung:** 2026-06-13

## Was ist dieses Modul

Wohnzimmer-Rollo-Policy (L2). Konsolidiert die leeren Skelette `benni_rollo_policy` +
`benni_cover_policy` und extrahiert die `cover_policy` aus `bennis_toolbox` — neu
geschrieben nach dem reviewten Lastenheft. Berechnet stateless den Rollo-Modus
(Prioritätskette) und fährt das Cover gated an `apply_enabled`.

**Lastenheft:** `einhornzentrale/docs/lastenhefte/reviewed/rollo/` (führend).

## Architektur-Entscheidungen (2026-06-13, beim Bau)

- **Standalone-Integration**, Skeleton-Pattern aus `benni_light_policy` (manifest/__init__/
  view/websocket), Decision-Engine aus dem Lastenheft. Toolbox-`cover_policy` = Strangler-Quelle.
- **Profil-Modell (FLEET-16):** Slug `<profile>_blind_policy_<feature>` via `has_entity_name`
  + Device-Name `"{Label} Blind Policy"`. `CONF_PROFILE` (benni/eltern) ≠ `position_profile`
  (Modus→Position). Blaupause: `benni_core_state`.
- **Heat in-policy** aus Rohdaten (`weather_condition`==sunny + `temperature`≥24 °C + Sonne>5°),
  kein externer heat_protect-Sensor — die Wetterkategorie-/Temperaturklasse-Entities existieren
  (noch) nicht; diese Policy ist Owner der Ableitung. Heat nutzt das Lux-Gate NICHT.
- **Window** via `binary_sensor.opening_unsafe_for_rollo_combined` (canonical core_devices-Aggregation);
  on = Flügel offen → R1 (absolut, ignoriert Override, respektiert nur apply_enabled).
- **Lux-Gate** = Schmitt 20k/15k + Sonne>5° + Tagesphase, als Hysterese-State im Coordinator
  (kein eigener Binary-Sensor, aber als `binary_sensor.*_lux_gate` für Observability emittiert).
- **Helfer-Booleans:** privacy_bed/alarm_wakeup = Switch-Entities (extern setzbar: Hue Dimmer /
  Wecker-Modul). privacy_latch/manual_override/writing_active = Coordinator-State (binary_sensor).

## Arbeitsweise / Konventionen

- **Decision/Apply getrennt.** `policy.py` HA-frei + pytest. Coordinator = HA-Brücke.
- **Kein Cross-Modul-Import** — Quellen nur als Entity-IDs aus dem Config-Flow.
- **Git-Freigabe (stehend):** committen/PR/merge/Release frei, solange < v1.0.0.
- **Nur live verifizierbar:** lokal kein HA → `py_compile` + Pure-Logic-Tests; Rest in echtem HA.
  HA-MCP „Einhornzentrale": Lesen frei, Schreiben erst vorschlagen.

## Tests lokal

```
../benni-core-state/.venv/Scripts/python.exe -m pytest tests/blind_policy/test_policy.py -q
```

## Pendant-Briefings

- `D:\Dokumente\GitHub\CLAUDE.md` — Fleet-Orientierung
- `einhornzentrale/docs/lastenhefte/reviewed/rollo/` — Lastenheft (führend)
- Historical FLEET/Plane note only: FLEET-11 + child cards 56-61. Active workflow now lives in GitLab `ha-platform/control`.
- `codex.md` — Codex-Pendant
