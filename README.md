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
   → policy.decide()  (pure, Prioritätskette R1..R9 + Lux-Gate + ProtectionDemand)
   → coordinator      (Latch · Override-Warden · Writing-Active · gated Apply)
   → cover.set_cover_position
```

- **Decision/Apply getrennt.** `policy.py` ist HA-frei und vollständig pytest-getestet.
  `ProtectionDemand` bewertet Thermal und Glare unabhängig und fusioniert die
  Zielposition vor der bestehenden Prioritätskette. Der Coordinator hält den persistenten State (Lux-Gate-Hysterese,
  Privacy-Latch, Override-Warden, Writing-Active-Flag) und wendet gated an.
- **Kein Cross-Modul-Python-Import.** Quellen werden ausschließlich als HA-Entity-IDs
  aus dem Config-Flow konsumiert (Entity-State-Contracts als Grenze).
- **Profil-Modell (FLEET-16).** Slug-Schema `<profile>_blind_policy_<feature>` via
  `has_entity_name` + profil-benanntem Device (Blaupause `benni_core_state`).

## Prioritätskette

| Regel | Modus | Position | Bedingung (Kurz) |
|---|---|---|---|
| R1 | `window_open` | 100 | Fenster offen — absolut, ignoriert Override |
| R2 | `privacy_bed` | 40 | Manueller Bett-Modus |
| R3 | `alarm_wakeup` | 100 | Wecker-Platzhalter |
| R4 | `sleep` | 40 | Bio sleep / Nachtphasen |
| R5 | `privacy` | 40 | Haushalt leer ODER Privacy-Latch |
| R6 | `ProtectionDemand` | 45/60/75 | Heat und Glare unabhängig, danach stärker schließend fusioniert |
| R7/R8 | `glare_tv` / `glare_pc` | 60/75 | Diagnosezeilen, keine konkurrierenden Policy-Zweige |
| R9 | `open` | 100 | Fallback |

**ProtectionDemand**: Thermal benötigt den bestehenden kanonischen
Temperatureingang ab der unveränderten Schwelle sowie direkte Solar-Eignung aus
Heat-Lux-Floor, Sonnenwinkel und Heat-Phasen. Glare nutzt weiterhin Lux-Schmitt
(20.000/15.000 lx), Sonnenwinkel, Tagesphase und Media-/Gaming-Kontext. Ein
transienter `unknown`-/`unavailable`-Wert löscht keinen gültigen Gate- oder
Thermal-Zustand; numerische Werte lösen die Neubewertung sofort aus. Helles
`late_afternoon` löscht nur den automatischen Evening-Privacy-Latch. Die
ausführliche Entscheidung steht in
[`docs/adr/0001-heat-glare-protection-demand.md`](docs/adr/0001-heat-glare-protection-demand.md).

## Output-Entities (Profil benni)

`sensor.benni_blind_policy_mode` · `_position` · `_debug`,
`binary_sensor.benni_blind_policy_lux_gate` · `_privacy_latch` · `_manual_override`
· `_writing_active` · `_apply_blocked`,
`switch.benni_blind_policy_privacy_bed` · `_alarm_wakeup` · `_manual_override` · `_apply_enabled`.

## Status

**v0.1.1 — FLEET-54 source migration.** Default/Migration für den Window-Open-
Contract zeigt auf `sensor.benni_combined_opening_unsafe_for_rollo` aus
`benni_core_devices`; Apply bleibt default **aus** (Shadow). Siehe `FAHRPLAN.md`.
