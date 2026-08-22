# Wohnzimmer Rollo — Automations

**Version:** 1.0 · Mai 2026
**Modul:** Wohnzimmer Rollo

---

## Übersicht

| Automation | Zweck |
|---|---|
| `living_rollo_apply_position` | Überträgt Ziel-Position auf Cover |
| `living_rollo_window_open` | Fenster-offen-Sofortreaktion (R1) |
| `living_rollo_override_set` | Erkennt manuellen Eingriff (R-MO) |
| `living_rollo_override_reset` | Reset Override bei Day State Wechsel (R-MO) |
| `living_rollo_override_warden` | Selbstheilung false-positive Overrides (R-OW) |
| `living_rollo_privacy_latch_set` | Setzt Privacy-Latch (R-PL) |
| `living_rollo_privacy_latch_reset` | Resettet Privacy-Latch (R-PL) |

**Hinweis:** Alle Automations können alternativ in einer einzigen Datei `rollo_living_automations.yaml` leben — siehe `naming.md`.

---

## R1 — Fenster offen (ABSOLUT)

**Automation:** `living_rollo_window_open`

**Trigger:** Fensterstatus wechselt auf 2 (Flügel offen)

**Bedingung:** Fensterstatus == 2

**Aktion:**
- Cover sofort auf 100% setzen
- Ignoriert `living_rollo_manual_override` — keine Override-Prüfung

**Priorität:** Absolut — keine Ausnahmen. Schlägt alle anderen Regeln und den Manual Override.

**Cooldown:** Keiner — sofortige Reaktion erforderlich.

**Hinweis:** Fenster gekippt (1) oder geschlossen (0) löst diese Automation nicht aus.

---

## R2 — Privacy Bed (Prio 1)

Bedingung und Zielposition werden durch `sensor.living_rollo_mode` (siehe `30_combined.md`) berechnet. Diese Prio-Stufe hat keine eigene Automation — sie wird über `living_rollo_apply_position` angewendet.

**Boolean-Management:** `input_boolean.living_rollo_privacy_bed`
- Gesetzt von: Hue Dimmer (große Sonne gedrückt halten) — liegt im Switch Manager
- Reset: Automatisch durch `living_rollo_privacy_latch_set` (R-PL)

---

## R3 — Privacy (Prio 2)

Bedingung und Zielposition werden durch `sensor.living_rollo_mode` berechnet (siehe `30_combined.md`). Angewendet über `living_rollo_apply_position`.

**Hinweis:** Der Haushalt-leer-Zweig wird nicht gelatcht. Abend-Privacy läuft über den Latch (R-PL).

---

## R4 — Alarm Wakeup (Prio 3) *(Platzhalter)*

Bedingung wird durch `sensor.living_rollo_mode` berechnet. `input_boolean.living_rollo_alarm_wakeup` ist aktuell immer inaktiv. Schnittstelle reserviert für zukünftiges Wake-Up-Modul (siehe OQ-1 in `00_overview.md`).

---

## R5 — Open Weekday (Prio 4)

**Trigger:** Day State wechselt auf `late_morning` UND Day Context == `werktag`

**Bedingung:**
```
Day State == 'late_morning'
UND Day Context == 'werktag'
UND Uhrzeit >= 08:00
```

**Zielposition:** 100% (via `sensor.living_rollo_mode` → `living_rollo_apply_position`)

**Hinweis:** Schlägt Sleep bewusst — natürlicher Wecker an Wochentagen. Mindestuhrzeit 08:00 verhindert frühes Hochfahren wenn `late_morning` im Sommer bereits um 06:00 beginnt.

---

## R6 — Open Weekend (Prio 5)

**Trigger:** Day State wechselt auf `forenoon` UND Day Context in [`wochenende`, `frei`]

**Bedingung:**
```
Day State == 'forenoon'
UND Day Context in ['wochenende', 'frei']
UND Uhrzeit >= 09:30
```

**Zielposition:** 100% (via `sensor.living_rollo_mode` → `living_rollo_apply_position`)

**Hinweis:** `frei` wird wie `wochenende` behandelt (siehe KH-4 in `00_overview.md`).

---

## R7 — Sleep (Prio 6)

**Trigger:** Bio-State wechselt auf `sleep`

**Bedingung:**
```
Bio-State == 'sleep'
```

**Zielposition:** 40% (via `sensor.living_rollo_mode` → `living_rollo_apply_position`)

**Hinweis:** `waking` und alle Tagesphasen werden wie `awake` behandelt — sie aktivieren Sleep nicht. Die Nachtphase aktiviert stattdessen ausschließlich den bestehenden Privacy-Latch.

---

## R8 — Heat (Prio 7)

**Trigger:** Wetterkategorie wechselt auf `sunny` ODER Temperaturklasse überschreitet 12 ODER Day State wechselt

**Bedingung:**
```
Wetterkategorie == 'sunny'
UND Temperaturklasse >= 12 (≥ 24°C)
UND Sonnenhöhe > 5°
UND Day State in ['late_morning', 'forenoon']
UND Bio-State != 'sleep'
```

**Zielposition:** 45% (via `sensor.living_rollo_mode` → `living_rollo_apply_position`)

**Hinweis:** Heat ist direkter Sonnenschutz, kein allgemeiner Hitzeschutz. Verwendet **kein** Lux-Gate (siehe R-G in `30_combined.md`). Wenn Day State auf `afternoon` wechselt, wird Heat inaktiv und das Rollo fährt automatisch hoch.

---

## R9 — Glare TV (Prio 8)

**Trigger:** Media Scenario wechselt ODER Gate-Zustand wechselt

**Bedingung:**
```
Gate aktiv (siehe R-G in 30_combined.md §R-G)
UND Media Scenario in ['tv', 'streaming', 'gaming']
UND Gaming Source != 'pc'
UND Bio-State != 'sleep'
```

**Zielposition:** 60% (via `sensor.living_rollo_mode` → `living_rollo_apply_position`)

**Hinweis:** Deckt TV, Streaming, PS5, Switch und `gaming_headset` ab. PC-Gaming am Monitor explizit ausgenommen (→ R10). Greift auch bei `gaming_headset`.

---

## R10 — Glare PC (Prio 9)

**Trigger:** Gaming Source wechselt auf `pc` ODER Gate-Zustand wechselt

**Bedingung:**
```
Gate aktiv (siehe R-G in 30_combined.md §R-G)
UND Media Scenario == 'gaming'
UND Gaming Source == 'pc'
UND Bio-State != 'sleep'
```

**Zielposition:** 75% (via `sensor.living_rollo_mode` → `living_rollo_apply_position`)

**Hinweis:** PC-Monitor braucht weniger aggressiven Blendschutz als OLED-TV.

---

## R11 — Open (Fallback)

Kein eigener Trigger — ergibt sich automatisch wenn keine andere Regel in `sensor.living_rollo_mode` greift. Zielposition: 100%.

---

## R-PL — Privacy-Latch

### living_rollo_privacy_latch_set

**Trigger (einer muss zutreffen):**
- Day State wechselt auf `early_night`, ODER
- Außenhelligkeit fällt unter 400 lx während Day State == `late_evening`

**Bedingung:** Latch noch nicht aktiv

**Aktion:**
1. `input_boolean.living_rollo_privacy_latch` → `on`
2. `input_boolean.living_rollo_privacy_bed` → `off` (automatischer Reset — zu diesem Zeitpunkt obsolet)

**Recovery beim HA-Start:** Falls Set-Bedingung beim Start bereits erfüllt ist, Latch sofort setzen.

**Cooldown:** Keiner.

---

### living_rollo_privacy_latch_reset

**Trigger (einer muss zutreffen):**
- Sonnenaufgang (sun.sun elevation == 0, rising), ODER
- Bio-State wechselt auf `awake` oder `waking`

**Bedingung:** Latch aktiv

**Aktion:** `input_boolean.living_rollo_privacy_latch` → `off`

**Hinweis:** Reset bei Sonnenaufgang statt Tagesphase — im Sommer ist Sonnenaufgang ~05:30 Uhr. Rollo bleibt danach auf 40% weil Sleep noch aktiv ist. Erst wenn Bewohner aufwacht fällt Sleep weg und Rollo fährt hoch. Siehe `00_overview.md` §R-PL für Begründung.

---

## R-MO — Manual Override

### living_rollo_apply_position

**Trigger:** `sensor.living_rollo_position` ändert sich

**Bedingung:** `input_boolean.living_rollo_manual_override` == `off`

**Aktion:**
1. `input_boolean.living_rollo_writing_active` → `on`
2. Cover auf Ziel-Position setzen
3. Nach Cover-Fahrt + 5s Grace: `input_boolean.living_rollo_writing_active` → `off`
4. Timeout nach 90s: `input_boolean.living_rollo_writing_active` → `off` (Sicherheit gegen Endlosblockierung)

**Ausnahme:** R1 (Fenster offen) umgeht diese Automation komplett — eigene Automation `living_rollo_window_open`.

---

### living_rollo_override_set

**Trigger:** Cover-Position ändert sich

**Bedingung:**
```
`living_rollo_writing_active` == off
UND Cover ist nicht in Bewegung (not opening/closing)
```

**Aktion:** `input_boolean.living_rollo_manual_override` → `on`

**Hinweis:** Erkennungsmechanismus — nur als manueller Eingriff gewertet wenn Writing-Active-Flag nicht aktiv ist.

---

### living_rollo_override_reset

**Trigger:** Day State ändert sich (jeder Wechsel)

**Bedingung:** `living_rollo_manual_override` == `on`

**Aktion:** `input_boolean.living_rollo_manual_override` → `off`

**Cooldown:** Keiner.

---

## R-OW — Override Warden (Selbstheilung)

**Automation:** `living_rollo_override_warden`

### Sofortprüfung bei Override-Set

**Trigger:** `living_rollo_manual_override` wechselt auf `on`

**Aktion — Override sofort löschen wenn:**
- Writing-Active-Flag wurde innerhalb der letzten 30 Sekunden deaktiviert (Race-Echo während Cover noch nachfährt), ODER
- Cover-Position liegt innerhalb ±3% der Ziel-Position (echter Eingriff will meist eine andere Position)

### Periodischer Sweep

**Trigger:** Zeitbasiert, alle 5 Minuten

**Aktion — Override löschen wenn alle drei zutreffen:**
- Override seit > 5 Minuten aktiv
- Cover steht still (nicht `opening`/`closing`)
- Cover-Position liegt innerhalb ±3% der Ziel-Position

**Parameter:** Siehe `00_overview.md` §5 (Schwellen & Konstanten).
