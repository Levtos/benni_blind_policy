# benni_blind_policy

Wohnzimmer-Rollo-Policy (L2) als eigenständige HACS-Custom-Integration. Berechnet
stateless den aktiven Rollo-Modus über eine Prioritätskette und fährt das
Verdunklungsrollo auf die Zielposition — gated an `apply_enabled` (Shadow-safe).

**Konsolidiert** die zwei leeren Skelett-Repos `benni_rollo_policy` + `benni_cover_policy`
und extrahiert die ~80 % fertige `cover_policy` aus `bennis_toolbox`, neu geschrieben
nach dem reviewten Lastenheft `einhornzentrale/docs/lastenhefte/reviewed/rollo/`.

## Architektur

```
Quellen (core_state · core_devices · media_state · DWD)
   → policy.decide()  (pure, Prioritätskette R1..R11 + Lux-Gate)
   → coordinator      (Latch · Override-Warden · Writing-Active · gated Apply)
   → cover.set_cover_position
```

- **Decision/Apply getrennt.** `policy.py` ist HA-frei und vollständig pytest-getestet
  (72 Tests). Der Coordinator hält den persistenten State (Lux-Gate-Hysterese,
  Privacy-Latch, Override-Warden, Writing-Active-Flag) und wendet gated an.
- **Kein Cross-Modul-Python-Import.** Quellen werden ausschließlich als HA-Entity-IDs
  aus dem Config-Flow konsumiert (Entity-State-Contracts als Grenze).
- **Profil-Modell (FLEET-16).** Slug-Schema `<profile>_blind_policy_<feature>` via
  `has_entity_name` + profil-benanntem Device (Blaupause `benni_core_state`).

## Prioritätskette (Lastenheft §4.1)

| Prio | Modus | Position | Bedingung (Kurz) |
|---|---|---|---|
| ABS | `window_open` | 100 | Fenster offen — absolut, ignoriert Override |
| 1 | `privacy_bed` | 40 | Manueller Bett-Modus |
| 2 | `privacy` | 40 | Haushalt leer ODER Privacy-Latch |
| 3 | `alarm_wakeup` | 100 | Wecker-Platzhalter |
| 4 | `open_weekday` | 100 | late_morning · werktag · ≥ 08:00 |
| 5 | `open_weekend` | 100 | forenoon · wochenende/frei · ≥ 09:30 |
| 6 | `sleep` | 40 | Bio sleep / Nachtphasen |
| 7 | `heat` | 45 | sunny · ≥ 24 °C · Sonne > 5° · (late_morning/forenoon) |
| 8 | `glare_tv` | 60 | Lux-Gate · TV-Stack · nicht PC |
| 9 | `glare_pc` | 75 | Lux-Gate · Gaming auf PC |
| FB | `open` | 100 | Fallback |

**Lux-Gate** = Template-Schmitt 20k/15k + Sonne > 5° + Tagesphase (kein eigener
Binary-Sensor; lebt als Hysterese-State im Coordinator). Heat nutzt das Gate **nicht**.

## Output-Entities (Profil benni)

`sensor.benni_blind_policy_mode` · `_position` · `_debug`,
`binary_sensor.benni_blind_policy_lux_gate` · `_privacy_latch` · `_manual_override`
· `_writing_active` · `_apply_blocked`,
`switch.benni_blind_policy_privacy_bed` · `_alarm_wakeup` · `_manual_override` · `_apply_enabled`.

## Status

**v0.1.1 — FLEET-54 source migration.** Default/Migration für den Window-Open-
Contract zeigt auf `sensor.benni_combined_opening_unsafe_for_rollo` aus
`benni_core_devices`; Apply bleibt default **aus** (Shadow). Siehe `FAHRPLAN.md`.
