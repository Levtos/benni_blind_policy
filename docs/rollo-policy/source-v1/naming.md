# Wohnzimmer Rollo — Naming & Struktur (Vorschlag)

**Version:** 1.0 · Mai 2026
**Modul:** Wohnzimmer Rollo
**Hinweis:** Dies sind Vorschläge, keine Festlegungen. Finale Naming-Struktur ergibt sich aus der Konsolidierung aller Modul-Naming-Dateien.

---

## Verzeichnis-Empfehlung

```
packages/40_covers/
```

Begründung: `40` als Präfix ordnet Covers nach Medien (30) und vor User-State (90+). Der alte Code verwendete `40_covers_neu` als Übergangsname — im Neubau entfällt das `_neu`-Suffix. Einziges Cover-Modul aktuell, daher kein weiterer Unterordner nötig.

---

## Datei-Aufteilung

```
packages/40_covers/
├── 10_helpers/
│   └── rollo_living_helpers.yaml       — input_boolean, interne Flags
├── 20_sensors/
│   ├── rollo_living_mode.yaml          — Ziel-Modus-Sensor + Ziel-Positions-Sensor
│   └── rollo_living_debug.yaml         — Debug-Sensor (optional, kann in mode.yaml leben)
└── 30_automations/
    ├── rollo_living_apply.yaml         — Apply Position + Window Open
    ├── rollo_living_override.yaml      — Manual Override Set/Reset + Override Warden
    └── rollo_living_privacy_latch.yaml — Privacy Latch Set/Reset
```

**Begründung der Aufteilung:**
- `10_helpers`: nur reine Helpers (input_boolean), keine Logik
- `20_sensors`: Template-Sensoren mit der gesamten Berechnungslogik
- `30_automations`: aufgeteilt nach fachlichem Verantwortungsbereich (Apply, Override, Privacy-Latch) statt einer monolithischen Datei — erleichtert spätere Wartung

Alternativ können alle Automations in einer Datei `30_automations/rollo_living_automations.yaml` leben, falls Opus oder Claude Code das für die Konsolidierung bevorzugt.

---

## Entity-Naming-Patterns

### Bereich-Bezeichner

| Bereich | Bezeichner |
|---|---|
| Wohnzimmer | `living` |

### Helper-Entities

```
input_boolean.living_rollo_privacy_bed        — Manueller Bett-Modus
input_boolean.living_rollo_privacy_latch      — Privacy-Latch (Abend-Stabilisierung)
input_boolean.living_rollo_manual_override    — Manueller Override aktiv
input_boolean.living_rollo_writing_active     — Internes Flag: Automation schreibt gerade
input_boolean.living_rollo_alarm_wakeup       — Platzhalter: Wecker-Modul
```

### Sensor-Entities

```
sensor.living_rollo_mode          — Aktiver Modus (Enum-State)
sensor.living_rollo_position      — Ziel-Position (%)
sensor.living_rollo_debug         — Debug-Sensor (State = Modus, Attribute = Begründungen)
```

### Automations

```
automation.living_rollo_apply_position        — Überträgt Ziel-Position auf Cover
automation.living_rollo_window_open           — Fenster-offen-Sofortreaktion
automation.living_rollo_override_set          — Erkennt manuellen Eingriff
automation.living_rollo_override_reset        — Reset bei Tagesphase-Wechsel
automation.living_rollo_override_warden       — Selbstheilung false-positive Overrides
automation.living_rollo_privacy_latch_set     — Setzt Privacy-Latch
automation.living_rollo_privacy_latch_reset   — Resettet Privacy-Latch
```

---

## Breadcrumb-Verortung

Von einem Entity-Namen lässt sich die Hierarchie ableiten:

```
sensor.living_rollo_mode
  → Bereich:  living       (Wohnzimmer)
  → Gerät:    rollo        (Verdunklungsrollo)
  → Feature:  mode         (Aktiver Modus)
  → Datei:    packages/40_covers/20_sensors/rollo_living_mode.yaml
  → Modul:    40_covers
```

```
input_boolean.living_rollo_privacy_latch
  → Bereich:  living
  → Gerät:    rollo
  → Feature:  privacy_latch
  → Datei:    packages/40_covers/10_helpers/rollo_living_helpers.yaml
  → Modul:    40_covers
```

---

## Besonderheiten dieses Moduls

**Cover-Domain statt Sensor-Domain:** Das Aktuator-Entity ist `cover.living_roller` — dieses liegt außerhalb des Modul-Ordners (Matter/Zigbee-Integration). Das Modul schreibt auf dieses Cover, besitzt es aber nicht.

**Internes Flag als Helper:** `living_rollo_writing_active` ist ein Helper der ausschließlich intern verwendet wird (kein Consume durch andere Module). Das ist ungewöhnlich für ein Helper und sollte beim Konsolidierungs-Trichter bekannt sein — ggf. als `input_boolean.living_rollo_internal_writing_active` klar als intern markieren.

**Keine Atomics:** Dieses Modul hat keine eigene Atomic-Ebene. Alle Rohdaten kommen aus vorgelagerten Modulen.

**Naming-Kollision mit altem System:** Im alten Code existierten Entities mit Präfix `blind_*` (z.B. `blind_privacy_latch`, `blind_manual_override`). Im Neubau wird auf `living_rollo_*` umgestellt — keine Backward-Kompatibilität geplant (Big-Bang-Switchover).

---

## Trichter-Hinweise

**Präfix-Konsistenz:** `living_rollo_*` ist der vorgeschlagene Präfix für alle Entities dieses Moduls. Wenn andere Räume später eigene Rollos bekommen, würde das Schema `<bereich>_rollo_<feature>` konsistent bleiben (z.B. `bedroom_rollo_mode`).

**`40_covers` vs. `40_cover`:** Singular oder Plural im Ordnernamen ist eine modulübergreifende Entscheidung. Vorschlag: Plural (`covers`) wenn mehrere Räume/Geräte absehbar sind.

**Automation-IDs:** Im alten Code hatten Automations IDs wie `living_blind_apply_position`. Im Neubau Vorschlag: `living_rollo_apply_position` — konsistent mit dem neuen Naming-Schema.

**Debug-Sensor-Platzierung:** Der Debug-Sensor könnte in `rollo_living_mode.yaml` mitlaufen (ein Package-Key) oder in einer separaten Datei `rollo_living_debug.yaml`. Empfehlung: separate Datei damit der Mode-Sensor nicht aufgebläht wird — aber das ist eine stilistische Entscheidung für die Konsolidierung.
