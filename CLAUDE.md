# CLAUDE.md — Blind Policy

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
- FLEET-Board (Plane, Projekt FLEET) — Live-Status; FLEET-11 + Child-Cards 56-61
- `codex.md` — Codex-Pendant
