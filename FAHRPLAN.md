# FAHRPLAN — benni_blind_policy

**FLEET-11** · L2-Policy · owner:claude · Lastenheft `einhornzentrale/docs/lastenhefte/reviewed/rollo/`

## Erledigt (v0.1.0, Erstbau)

- [x] Repo-Konsolidierung: `benni_rollo_policy` + `benni_cover_policy` (leer) gelöscht, neu `benni_blind_policy`.
- [x] Pure-Logic `policy.py` nach Lastenheft neu geschrieben: Prioritätskette R1..R11 mit
      korrekten Positionen, Lux-Gate-Schmitt, in-policy Heat, Privacy-Latch- + Override-Warden-Prädikate.
- [x] `coordinator.py`: Lux-Gate-Hysterese, Privacy-Latch (Set/Reset/Recovery, Sonnenaufgang-Flanke),
      Manual-Override-Detection + Override-Warden (30s Race-Echo, ±3 %, 5-Min-Sweep),
      Writing-Active-Flag (Fahrt + 5s Grace, 90s Timeout), Window-Open-Sofortpfad, gated Apply.
- [x] Entities: sensor (mode/position/debug), binary_sensor (lux_gate/privacy_latch/manual_override/
      writing_active/apply_blocked), switch (privacy_bed/alarm_wakeup/manual_override/apply_enabled).
- [x] Profil-Mechanik (FLEET-16): `<profile>_blind_policy_*` via Device-Name, `PROFILE_PREFILL` (benni live).
- [x] config_flow (Profil → Quellen → Optionen) + options_flow, services, diagnostics, strings/translations.
- [x] WS-API + Panel (Diagnose/Trace nach Screenshot-Referenz).
- [x] 53 Pure-Logic-Tests grün, `py_compile` clean.

## Offen / nur live verifizierbar (kein HA lokal)

- [ ] **Live-Verify in HA:** Config-Entry anlegen (Profil benni), Quellen bestätigen,
      Apply scharf schalten und Modus-Wechsel beobachten. Override-Warden + Writing-Active
      sind reine HA-Pfade.
- [ ] **Heat-Contract festzurren:** aktuell in-policy aus `weather_condition` (sunny) +
      `weather_temperature` (≥ 24 °C) + Sonnenhöhe. Sobald ein Wetter-/Klima-LH eine echte
      Wetterkategorie/Temperaturklasse liefert → Config repointen (Logik bleibt gültig).
- [ ] **Window-Contract:** konsumiert `binary_sensor.opening_unsafe_for_rollo_combined`
      (core_devices-Aggregation) als „Flügel offen". Falls Tilt mitzählt → prüfen.
- [ ] **Strangler:** Toolbox-`cover_policy` bleibt Quelle bis Live-Verify, dann löschen.
- [ ] **FLEET-54 Konsumenten-Cutover:** alte YAML-Konsumenten von `sensor.living_rollo_*_combined`
      auf `sensor.benni_blind_policy_*` umstellen, alte YAML-Shims (`packages/rollo/*`,
      `packages/combined/rollo.yaml`) entfernen.
- [ ] **Eltern-Profil:** `PROFILE_PREFILL[eltern]` befüllen, sobald Eltern-Anlage real.

## Review-Punkte (beim Live-Test gezielt prüfen)

- [ ] **Override-Reset-Ordering (R-MO):** `_prev_day_state` wird in `coordinator.py` von zwei
      Stellen gelesen/geschrieben — `_reset_override_on_dayphase` (Vergleich) und
      `_update_privacy_latch` (Fortschreiben), Reset bewusst VOR Latch-Update. Funktional
      korrekt, aber subtil. Wenn ein Override nach Tagesphasen-Wechsel nicht löst → hier ansetzen.
- [ ] **Window-Contract-Semantik:** R1 verlangt „Flügel offen (Status 2)", NICHT Kipp (Status 1).
      Prüfen, ob `binary_sensor.opening_unsafe_for_rollo_combined` exakt das meint (Kipp ausschließt).
      Falls nicht → tilt-ausschließendes Wing-Open-Combined in FLEET-54 anlegen (siehe dort).

## Child-Cards (Codex-Board)

FLEET-56 Contracts/Bindings · 57 Engine/Debug · 58 Apply/Safety/Latch · 59 Override/Warden ·
60 Diagnose-UX · 61 Migration/Tests/Live/YAML-Retire.
