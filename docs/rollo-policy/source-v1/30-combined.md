# Wohnzimmer Rollo — Combined Sensors

**Version:** 1.0 · Mai 2026
**Modul:** Wohnzimmer Rollo

---

## Übersicht

Dieses Modul definiert drei Template-Sensoren:

1. `sensor.living_rollo_mode` — Ziel-Modus (Prioritätskette + Lux-Gate)
2. `sensor.living_rollo_position` — Ziel-Position in %
3. `sensor.living_rollo_debug` — Debug-Sensor

Die Prioritätskette und der Lux-Gate Schmitt-Trigger leben vollständig in `sensor.living_rollo_mode`. Keine separaten Binary-Sensoren.

---

## R-G — Lux-Gate (Schmitt-Trigger)

Das Gate ist eine interne Template-Variable in `sensor.living_rollo_mode`, kein eigener Binary-Sensor.

**Gate-Logik:**
```
Gate öffnet wenn:  Außenhelligkeit > 20.000 lx
Gate schließt wenn: Außenhelligkeit < 15.000 lx
Grauzone 15.000–20.000 lx: vorheriger Gate-Zustand bleibt erhalten (this.state-basiert)
```

**Vollständige Gate-Bedingung:**
```
Schmitt-Trigger aktiv (20k/15k)
UND Sonnenhöhe > 5°
UND Day State in ['early_morning', 'late_morning', 'forenoon', 'afternoon']
```

**Zweck:** Verhindert Yo-Yo-Verhalten bei kurzen Wolkendurchzügen.

**Hinweis:** Heat (R8 in `40_automations.md`) verwendet dieses Gate **nicht** — Wetterkategorie `sunny` übernimmt dort die Filterfunktion.

**Schwellen:** Siehe `00_overview.md` §5.

---

## sensor.living_rollo_mode

**Typ:** Template-Sensor (Enum)
**Zweck:** Berechnet den aktiven Rollo-Modus über die Prioritätskette. Enthält den Lux-Gate Schmitt-Trigger als interne Variable (`this.state`-basiert).

**State:** Einer der Modus-Werte aus der Prioritätskette (siehe `00_overview.md` §4.1)

**Prioritätskette (Auswertungsreihenfolge):**

| Priorität | Modus | Bedingung (Kurzform) | Detail |
|---|---|---|---|
| ABSOLUT | `window_open` | Fensterstatus == 2 | Siehe R1 in `40_automations.md` — hier als Sensor-Fallback |
| 1 | `privacy_bed` | `living_rollo_privacy_bed` == on | — |
| 2 | `privacy` | Haushaltsanwesenheit == leer ODER `living_rollo_privacy_latch` == on | — |
| 3 | `alarm_wakeup` | `living_rollo_alarm_wakeup` == on | Immer inaktiv (Platzhalter) |
| 4 | `open_weekday` | Day State == late_morning UND Day Context == werktag UND Zeit >= 08:00 | — |
| 5 | `open_weekend` | Day State == forenoon UND Day Context in [wochenende, frei] UND Zeit >= 09:30 | — |
| 6 | `sleep` | Bio-State == sleep ODER Day State in [early_night, late_night] ODER (Day State == early_morning UND Bio-State == sleep) | — |
| 7 | `heat` | Wetterkategorie == sunny UND Temperaturklasse >= 12 UND Sonnenhöhe > 5° UND Day State in [late_morning, forenoon] UND Bio-State != sleep | — |
| 8 | `glare_tv` | Gate aktiv UND Media Scenario in [tv, streaming, gaming] UND Gaming Source != pc UND Bio-State != sleep | — |
| 9 | `glare_pc` | Gate aktiv UND Media Scenario == gaming UND Gaming Source == pc UND Bio-State != sleep | — |
| FALLBACK | `open` | Keine Bedingung trifft zu | — |

**Failure-Verhalten der Inputs:** Siehe `00_overview.md` §2 (Inputs-Tabelle).

**Hinweis Übergänge:** Stateless — bei jeder Zustandsänderung einer Quell-Komponente wird die Kette vollständig neu berechnet. Kein Debounce, kein Winner-Routing.

---

## sensor.living_rollo_position

**Typ:** Template-Sensor (Numerisch, %)
**Zweck:** Übersetzt den aktiven Modus aus `sensor.living_rollo_mode` in eine numerische Zielposition.

**Mapping:**

| Modus | Position |
|---|---|
| `window_open` | 100% |
| `privacy_bed` | 40% |
| `privacy` | 40% |
| `alarm_wakeup` | 100% |
| `open_weekday` | 100% |
| `open_weekend` | 100% |
| `sleep` | 40% |
| `heat` | 45% |
| `glare_tv` | 60% |
| `glare_pc` | 75% |
| `open` | 100% |

---

## sensor.living_rollo_debug

**Typ:** Template-Sensor
**Zweck:** Detaillierte Begründung des aktiven Modus für Debugging und Nachvollziehbarkeit.

**State:** Aktiver Modus-Name (identisch mit `sensor.living_rollo_mode`)

**Attribute (je Modus):**
- `active_mode` — Aktiver Modus
- `active_position` — Ziel-Position
- `gate_active` — Lux-Gate Zustand (true/false)
- `lux_current` — Aktueller Lux-Wert
- `sun_elevation` — Aktuelle Sonnenhöhe
- `privacy_latch` — Privacy-Latch Zustand
- `manual_override` — Override Zustand
- `bio_state` — Aktueller Bio-State
- `media_scenario` — Aktuelles Media Scenario
- `gaming_source` — Aktuelle Gaming Source
- `window_status` — Fensterstatus

**Hinweis:** Der Debug-Sensor kann in derselben Datei wie `sensor.living_rollo_mode` leben oder in einer separaten `rollo_living_debug.yaml` — siehe `naming.md` für Empfehlung.
