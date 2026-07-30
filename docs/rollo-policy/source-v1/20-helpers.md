# Wohnzimmer Rollo — Helpers

**Version:** 1.0 · Mai 2026
**Modul:** Wohnzimmer Rollo

---

## input_boolean

Alle Helpers dieses Moduls sind `input_boolean`. Kein `input_number`, kein `timer`, kein `input_select`.

---

### living_rollo_privacy_bed

| Eigenschaft | Wert |
|---|---|
| Entity | `input_boolean.living_rollo_privacy_bed` |
| Zweck | Manueller Bett-Modus — höchste manuelle Priorität (Prio 1) |
| Standardwert | `off` |
| Gesetzt von | Hue Dimmer (große Sonne gedrückt halten) |
| Resettet von | Automatisch bei Privacy-Latch-Set; manuell via Hue Dimmer (kleine Sonne) |
| Konsumiert von | `sensor.living_rollo_mode` (R2), `automation.living_rollo_privacy_latch_set` |

---

### living_rollo_privacy_latch

| Eigenschaft | Wert |
|---|---|
| Entity | `input_boolean.living_rollo_privacy_latch` |
| Zweck | Privacy-Latch — stabilisiert Abend-Privacy-Modus gegen Lux-Schwankungen |
| Standardwert | `off` |
| Gesetzt von | `automation.living_rollo_privacy_latch_set` (siehe R-PL in `40_automations.md`) |
| Resettet von | `automation.living_rollo_privacy_latch_reset` (Sonnenaufgang oder Bio-State waking/awake) |
| Konsumiert von | `sensor.living_rollo_mode` (R3) |

---

### living_rollo_manual_override

| Eigenschaft | Wert |
|---|---|
| Entity | `input_boolean.living_rollo_manual_override` |
| Zweck | Manueller Override aktiv — Automation schreibt nicht auf das Cover |
| Standardwert | `off` |
| Gesetzt von | `automation.living_rollo_override_set` |
| Resettet von | `automation.living_rollo_override_reset` (Day State Wechsel); `automation.living_rollo_override_warden` |
| Konsumiert von | `automation.living_rollo_apply_position` (blockiert Cover-Befehl) |
| Ausnahme | R1 (Fenster offen) ignoriert diesen Override |

---

### living_rollo_writing_active

| Eigenschaft | Wert |
|---|---|
| Entity | `input_boolean.living_rollo_writing_active` |
| Zweck | Internes Flag: Automation schreibt gerade auf das Cover (verhindert false-positive Override-Erkennung) |
| Standardwert | `off` |
| Gesetzt von | `automation.living_rollo_apply_position` vor jedem Cover-Befehl |
| Resettet von | Nach Cover-Fahrt + 5s Grace automatisch; Timeout nach 90s |
| Konsumiert von | `automation.living_rollo_override_set` (R-MO Erkennungsmechanismus) |
| Hinweis | Ausschließlich intern — kein anderes Modul konsumiert diesen Helper. Ggf. als `living_rollo_internal_writing_active` klar als intern markieren (siehe `naming.md`) |

---

### living_rollo_alarm_wakeup

| Eigenschaft | Wert |
|---|---|
| Entity | `input_boolean.living_rollo_alarm_wakeup` |
| Zweck | Platzhalter für zukünftiges Wecker-Modul (Prio 3) |
| Standardwert | `off` |
| Gesetzt von | ⏳ Wake-Up-Modul (noch nicht implementiert) |
| Resettet von | ⏳ Wake-Up-Modul |
| Konsumiert von | `sensor.living_rollo_mode` (R4 — aktuell immer inaktiv) |
| Hinweis | Schnittstelle reserviert — siehe KH-3 in `00_overview.md` und OQ-1 |
