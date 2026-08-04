# Wohnzimmer Rollo — Atomics

**Version:** 1.0 · Mai 2026
**Modul:** Wohnzimmer Rollo

---

## Übersicht

Das Rollo-Modul hat keine eigene Sensor-Hardware direkt angebunden. Die folgenden Atomics werden von diesem Modul **benötigt** und müssen bei der Konsolidierung erzeugt werden — entweder in diesem Modul oder in einem dedizierten Atomics-Modul.

---

## Benötigte Atomics

### A-1 — Fensterstatus Wohnzimmer

| Eigenschaft | Wert |
|---|---|
| Logischer Bezeichner | Fensterstatus Wohnzimmer |
| Vorgeschlagener Entity-Name | `sensor.living_window_contact` |
| Typ | Integer |
| Wertebereich | 0 = geschlossen, 1 = gekippt, 2 = Flügel offen |
| Physische Quelle | Zigbee Kontakt-/Öffnungssensor am Wohnzimmerfenster |
| Failure-Verhalten | Bei `unknown`: als 2 (offen) behandeln — Sicherheit hat Vorrang |
| Konsumiert von | R1 (Fenster offen, ABSOLUT), Edge-Case-Handling |
| Hinweis | Kein dediziertes Fenster-Modul vorhanden — Atomic liegt im Rollo-Modul |

---

### A-2 — Außenhelligkeit

| Eigenschaft | Wert |
|---|---|
| Logischer Bezeichner | Außenhelligkeit |
| Vorgeschlagener Entity-Name | `sensor.outdoor_illuminance` |
| Typ | Numerisch (lx) |
| Wertebereich | 0 – ~120.000 lx |
| Physische Quelle | Zigbee oder anderer Außen-Lux-Sensor |
| Failure-Verhalten | Bei `unknown`: letzten Wert halten; Gate bleibt im letzten bekannten Zustand; bei erstem Boot: Gate inaktiv |
| Konsumiert von | R-G (Lux-Gate Schmitt-Trigger), R-PL (Privacy-Latch Lux-Schwelle) |
| Hinweis | Kein eigenes Lux-Modul-LH vorhanden — Atomic liegt im Rollo-Modul bis ein übergeordnetes Lux-Modul definiert wird |

---

### A-3 — Sonnenhöhe

| Eigenschaft | Wert |
|---|---|
| Logischer Bezeichner | Sonnenhöhe |
| Vorgeschlagener Entity-Name | `sensor.home_sun_elevation` |
| Typ | Float (°) |
| Wertebereich | –90 bis +90 |
| Physische Quelle | HA Sun Integration oder Sun2 (HACS) |
| Failure-Verhalten | Bei `unknown`: als 0° behandeln → Gate inaktiv |
| Konsumiert von | R-G (Gate-Bedingung), R8 (Heat), R9/R10 (Glare indirekt via Gate) |
| Hinweis | Naming-Präfix `sensor.home_sun_*` konsistent mit bestehendem System |

---

## Hinweis zur Konsolidierung

Bei der Modul-Konsolidierung prüfen:
- **A-2 Außenhelligkeit** und **A-3 Sonnenhöhe** könnten in ein übergeordnetes `sun_lux`-Atomics-Modul wandern, falls andere Module dieselben Sensoren benötigen.
- **A-1 Fensterstatus** ist aktuell exklusiv für das Rollo-Modul — kein anderes Modul konsumiert diesen Sensor laut bekanntem Stand.
