# Lastenheft · Wohnzimmer Rollo

**Status:** Review-abgeschlossen, implementierungsreif
**Version:** 1.0 · nach Review-Session Mai 2026
**Findings-Status:** Alle Findings geklärt

---

## FINDINGS (Review-Ergebnis)

| # | Severity | Finding | Entscheidung |
|---|---|---|---|
| K-1 | Kritisch | `blind_privacy_bed` Position: Code-Kommentar (50%) vs. Lastenheft (40%) | Lastenheft gilt: 40% |
| K-2 | Kritisch | Lux-Gate: `threshold`-Plattform vs. Template-Schmitt | Template-Schmitt — kein separater Binary-Sensor, kein Debouncing |
| K-3 | Kritisch | Override Warden fehlte im Lastenheft | Übernommen als eigenständiger Mechanismus |
| W-1 | Wichtig | `waking` Bio-State nicht im Lastenheft | `waking` wie `awake` behandelt |
| W-2 | Wichtig | Anwesenheit: persönlich vs. Haushalt für Privacy | Haushaltsanwesenheit (`leer`) ist die maßgebliche Quelle |
| W-3 | Wichtig | `blind_privacy_bed` Reset-Mechanismus unklar + Überschneidung mit `blind_tv_glare_bed` | `blind_tv_glare_bed` gestrichen, `blind_privacy_bed` bleibt als einziger manueller Bett-Modus; Reset automatisch bei Privacy-Latch-Set |
| W-4 | Wichtig | Dateistruktur: Atomic-Ebene nötig? | Nein — `10_helpers`, `20_sensors`, `30_automations` |
| N-1 | Nice-to-have | Debug-Sensor | Übernommen |
| N-2 | Nice-to-have | Heat-Position differenzieren | Heat → 45% |
| N-3 | Nice-to-have | Eltern-Präsenz beeinflusst Glare | Veralteter Kommentar, nicht übernommen |
| Nachklärung | — | Glare-Logik: direkte TV/PC-Abfrage vs. Media Scenario | Rollo konsumiert `media_scenario` + `gaming_source`; Media-LH um `Gaming Source` Enum erweitert |
| Nachklärung | — | `open_weekday`/`open_weekend`: intern vs. Day Context | Day Context Sensor wird konsumiert; `frei` = `wochenende` |
| Nachklärung | — | `glare_tv` bei `gaming_headset` | Ja, greift auch bei `gaming_headset` |
| Nachklärung | — | Abendlicher Glare ohne Gate | Nicht eingeführt — Rollo fährt auf Fallback `open` (100%), Privacy-Latch übernimmt später |

---

## 1. MODUL-IDENTITÄT

**Name:** Wohnzimmer Rollo

**Zweck:**
Automatisierte Steuerung des elektrischen Verdunklungsrollos im Wohnzimmer (Südost-Ausrichtung) auf Basis von Tagesphase, Sonneneinstrahlung, Medienkontext, Nutzerzustand und Anwesenheit. Die Logik berechnet stateless bei jeder relevanten Zustandsänderung den aktiven Modus und fährt das Rollo auf die entsprechende Zielposition.

**Scope:**
- Berechnung des aktiven Rollo-Modus über eine Prioritätskette
- Lux-Gate mit Schmitt-Trigger-Verhalten (Template-basiert, kein separater Binary-Sensor)
- Privacy-Latch für stabilen Abend-Privacy-Modus
- Manual Override mit Selbstheilung (Override Warden)
- Fenster-Sicherheitsregel (absolute Top-Priorität)
- Manueller Bett-Modus (`blind_privacy_bed`)

**Out-of-Scope:**
- Hue Dimmer Switch-Konfiguration (liegt im Switch Manager, außerhalb dieses Moduls)
- Wecker-Modul (`blind_alarm_wakeup` ist Platzhalter, nicht implementiert)
- Andere Räume oder Rollos
- Lichtsteuerung

---

## 2. INPUTS

| Logischer Bezeichner | Typ | Wertebereich | Bedeutung | Failure-Verhalten |
|---|---|---|---|---|
| Außenhelligkeit | Numerisch (lx) | 0 – ~120.000 | Sonneneinstrahlung auf Fensterhöhe | Bei unknown: letzten Wert halten; Gate bleibt im letzten bekannten Zustand |
| Day State | Enum | 8 Phasen | Aktuelle Tagesphase | Kein Fallback möglich, Pflicht |
| Day Context | Enum | werktag / wochenende / frei | Kalendarischer Tagestyp | Bei unknown: als `wochenende` behandeln (konservativ) |
| Media Scenario | Enum | idle / tv / streaming / gaming / private_time | Aktuelles Medienszenario | Bei unknown: als `idle` behandeln |
| Gaming Source | Enum | tv / pc / none | Quelle des Gaming-Szenarios | Bei unknown: als `none` behandeln |
| Bio-State | Enum | sleep / waking / awake | Schlaf-/Wachzustand | Bei unknown: als `awake` behandeln |
| Haushaltsanwesenheit | Enum | leer / nicht_leer | Ist jemand zuhause? | Bei unknown: als `nicht_leer` behandeln (konservativ) |
| Fensterstatus Wohnzimmer | Integer | 0 / 1 / 2 | 0=zu, 1=gekippt, 2=Flügel offen | Bei unknown: als 2 (offen) behandeln — Sicherheit |
| Sonnenhöhe | Float (°) | –90 bis +90 | Elevation der Sonne über dem Horizont | Bei unknown: als 0° behandeln (Gate inaktiv) |
| Wetterkategorie | Enum | sunny / wet / windy / neutral | Aggregierter Wetterzustand | Bei unknown: nicht `sunny` → Heat greift nicht |
| Temperaturklasse | Integer | 0–15 (je 2°C-Schritt) | Außentemperatur; ≥ 12 entspricht ≥ 24°C | Bei unknown: als 0 behandeln → Heat greift nicht |

---

## 3. OUTPUTS

| Logischer Bezeichner | Typ | Bedeutung | Wertebereich |
|---|---|---|---|
| Rollo Ziel-Modus | Enum | Aktiver Modus der Prioritätskette | Siehe Kapitel 4 |
| Rollo Ziel-Position | Numerisch (%) | Cover-Zielposition | 0–100 |
| Rollo Debug | Sensor | Detaillierte Begründung je Modus | Attribute pro Modus |

**Interne Helpers (keine Outputs nach außen):**
- Privacy-Latch Boolean
- Manual Override Boolean
- Writing-Active Flag
- Privacy Bed Boolean

---

## 4. STATE-DEFINITIONEN

### 4.1 Rollo-Modi (Prioritätskette)

| Priorität | Modus | Position | Beschreibung |
|---|---|---|---|
| ABSOLUT | `window_open` | 100% | Fenster offen — absolute Top-Regel |
| 1 | `privacy_bed` | 40% | Manueller Bett-Modus |
| 2 | `privacy` | 40% | Haushalt leer ODER Privacy-Latch aktiv |
| 3 | `alarm_wakeup` | 100% | Platzhalter Wecker-Modul (immer inaktiv) |
| 4 | `open_weekday` | 100% | Natürlicher Wecker werktags |
| 5 | `open_weekend` | 100% | Natürlicher Wecker wochenends/frei |
| 6 | `sleep` | 40% | Bio-State sleep oder Nachtphasen |
| 7 | `heat` | 45% | Direkter Sonnenschutz |
| 8 | `glare_tv` | 60% | Blendschutz TV/Streaming/Gaming (TV-Stack) |
| 9 | `glare_pc` | 75% | Blendschutz PC-Monitor |
| FALLBACK | `open` | 100% | Kein Modus aktiv |

### 4.2 Übergänge

Die Prioritätskette wird **stateless** bei jeder Zustandsänderung einer Quell-Komponente neu berechnet. Kein Debounce, kein Winner-Routing. Die erste zutreffende Bedingung (höchste Priorität) gewinnt.

### 4.3 Initial-State

Nach HA-Start wird die Prioritätskette sofort neu berechnet und auf das Cover angewendet, sofern kein Manual Override aktiv ist.

---

## 5. REGELN

### R1 — Fenster offen (ABSOLUT)

**Trigger:** Fensterstatus wechselt auf 2 (Flügel offen)
**Bedingung:** Fensterstatus == 2
**Aktion:** Rollo sofort auf 100%, ignoriert Manual Override
**Priorität:** Absolut — keine Ausnahmen

Fenster gekippt (1) oder geschlossen (0): kein Einfluss auf diese Regel.

---

### R2 — Privacy Bed (Prio 1)

**Bedingung:** `blind_privacy_bed` Boolean aktiv
**Zielposition:** 40%

Manuell vom Bett auslösbar (Hue Dimmer, große Sonne gedrückt halten). Höchste manuelle Priorität, schlägt alles außer Fenster-offen.

**Reset:** Automatisch wenn Privacy-Latch gesetzt wird — zu diesem Zeitpunkt fährt das Rollo sowieso auf 40%, der Boolean ist obsolet. Zusätzlich manuell via Hue Dimmer (kleine Sonne).

---

### R3 — Privacy (Prio 2)

**Bedingung:**
```
Haushaltsanwesenheit == leer
ODER Privacy-Latch aktiv
```
**Zielposition:** 40%

Der Haushalt-leer-Zweig wird nicht gelatcht — kurze Abwesenheit (Einkaufen etc.) soll nicht den Privacy-Modus bis zum nächsten Morgen einfrieren. Abend-Privacy läuft über den Latch (siehe R-PL).

---

### R4 — Alarm Wakeup (Prio 3) *(Platzhalter)*

**Bedingung:** `blind_alarm_wakeup` Boolean aktiv
**Zielposition:** 100%

Noch nicht implementiert. Zukünftiges Wecker-Modul setzt diesen Boolean um die Open-Phase vorzuziehen — auch wenn Sleep noch aktiv ist. Boolean ist aktuell immer inaktiv.

---

### R5 — Open Weekday (Prio 4)

**Bedingung:**
```
Day State == 'late_morning'
UND Day Context == 'werktag'
UND Uhrzeit >= 08:00
```
**Zielposition:** 100%

Schlägt Sleep bewusst — natürlicher Wecker an Wochentagen. Die Mindestuhrzeit 08:00 verhindert dass das Rollo hochfährt wenn `late_morning` im Sommer bereits um 06:00 beginnt.

---

### R6 — Open Weekend (Prio 5)

**Bedingung:**
```
Day State == 'forenoon'
UND Day Context in ['wochenende', 'frei']
UND Uhrzeit >= 09:30
```
**Zielposition:** 100%

Schlägt Sleep bewusst. `frei` wird wie `wochenende` behandelt.

---

### R7 — Sleep (Prio 6)

**Bedingung:**
```
Bio-State == 'sleep'
ODER Day State in ['early_night', 'late_night']
ODER (Day State == 'early_morning' UND Bio-State == 'sleep')
```
**Zielposition:** 40%

`waking` wird wie `awake` behandelt — greift hier nicht.

**Sonderfall `early_morning`:**
- `early_morning` + `sleep` → Sleep greift → 40%
- `early_morning` + `awake` oder `waking` → Sleep greift nicht → Fallback `open` → 100%

---

### R8 — Heat (Prio 7)

**Bedingung:**
```
Wetterkategorie == 'sunny'
UND Temperaturklasse >= 12 (≥ 24°C)
UND Sonnenhöhe > 5°
UND Day State in ['late_morning', 'forenoon']
UND Bio-State != 'sleep'
```
**Zielposition:** 45%

Heat ist direkter Sonnenschutz, kein allgemeiner Hitzeschutz. Verwendet kein Lux-Gate — Wetterkategorie `sunny` übernimmt diese Funktion. Wenn die Sonne weg ist (Day State wechselt auf `afternoon`), wird Heat inaktiv und das Rollo fährt automatisch hoch.

---

### R9 — Glare TV (Prio 8)

**Bedingung:**
```
Gate aktiv (siehe R-G)
UND Media Scenario in ['tv', 'streaming', 'gaming']
UND Gaming Source != 'pc'
UND Bio-State != 'sleep'
```
**Zielposition:** 60%

Deckt TV, Streaming, PS5, Switch und `gaming_headset` ab. PC-Gaming am Monitor ist explizit ausgenommen (→ Glare PC).

---

### R10 — Glare PC (Prio 9)

**Bedingung:**
```
Gate aktiv (siehe R-G)
UND Media Scenario == 'gaming'
UND Gaming Source == 'pc'
UND Bio-State != 'sleep'
```
**Zielposition:** 75%

PC-Monitor braucht weniger aggressiven Blendschutz als OLED-TV.

---

### R11 — Open (Fallback)

**Bedingung:** Keine der obigen Regeln trifft zu
**Zielposition:** 100%

---

### R-G — Lux-Gate (Schmitt-Trigger)

Das Gate ist eine interne Variable im Ziel-Modus-Sensor, kein eigener Binary-Sensor.

**Gate-Logik (Template-Schmitt):**
```
Gate öffnet wenn: Außenhelligkeit > 20.000 lx
Gate schließt wenn: Außenhelligkeit < 15.000 lx
Grauzone 15.000–20.000 lx: vorheriger Gate-Zustand bleibt erhalten (this.state-basiert)
```

**Vollständige Gate-Bedingung:**
```
Schmitt-Trigger aktiv (20k/15k)
UND Sonnenhöhe > 5°
UND Day State in ['early_morning', 'late_morning', 'forenoon', 'afternoon']
```

**Zweck:** Verhindert Yo-Yo-Verhalten bei kurzen Wolkendurchzügen. Heat verwendet kein Gate.

---

### R-PL — Privacy-Latch

**Problem:** `late_evening` kann im Sommer bereits gegen 20:00 Uhr eintreten wenn es draußen noch hell ist (~600 lx). Ein direkter Dayphase-Trigger für Privacy würde bei kurzen Lux-Schwankungen (Autoscheinwerfer, Mond, Wolken) ein Yo-Yo verursachen.

**Set-Bedingungen (einer muss zutreffen):**
- Day State wechselt auf `early_night`, ODER
- Außenhelligkeit fällt unter 400 lx während Day State == `late_evening`
- Recovery: beim HA-Start falls Bedingung bereits erfüllt

**Reset-Bedingungen (einer muss zutreffen):**
- Sonnenaufgang, ODER
- Bio-State wechselt auf `awake` oder `waking`

**Warum Sonnenaufgang statt Tagesphase:** Im Sommer ist Sonnenaufgang ~05:30 Uhr. Der Reset passiert zu diesem Zeitpunkt — Rollo bleibt aber auf 40% weil Sleep noch aktiv ist. Erst wenn der Bewohner aufwacht fällt Sleep weg und das Rollo fährt hoch.

**Seiteneffekt:** Privacy-Latch-Set triggert automatisch den Reset von `blind_privacy_bed` — zu diesem Zeitpunkt ist der Boolean obsolet.

---

### R-MO — Manual Override

Wenn der Bewohner das Rollo manuell bedient (App, physischer Taster, Sprachsteuerung), pausiert die Automation.

**Erkennungsmechanismus:**
Vor jedem automatischen Cover-Befehl wird ein Writing-Active-Flag für die Dauer des Fahrvorgangs + 5s Grace aktiviert. Eine Positionsänderung am Cover wird nur als manueller Eingriff gewertet wenn dieses Flag **nicht** aktiv ist UND das Cover nicht mehr in Bewegung ist.

**Override aktiv:** Automation schreibt nicht auf das Cover.
**Ausnahme:** Fenster-offen-Regel (R1) ignoriert den Override — Sicherheit hat Vorrang.
**Reset:** Automatisch beim nächsten Wechsel der Tagesphase (Day State).

---

### R-OW — Override Warden (Selbstheilung)

Schutz gegen false-positive Overrides durch Race-Conditions.

**Sofortprüfung bei Override-Set:**
Override wird sofort wieder gelöscht wenn eine der folgenden Bedingungen zutrifft:
- Writing-Active-Flag wurde innerhalb der letzten 30 Sekunden deaktiviert (Race-Echo während Cover noch nachfährt)
- Cover-Position liegt innerhalb ±3% der Ziel-Position (echter Eingriff will meist eine andere Position)

**Periodischer Sweep (alle 5 Minuten):**
Override wird gelöscht wenn:
- Override seit > 5 Minuten aktiv
- Cover steht still (nicht opening/closing)
- Cover-Position liegt innerhalb ±3% der Ziel-Position

**Parameter:**
| Parameter | Wert | Konfigurierbar |
|---|---|---|
| Race-Echo-Fenster | 30 Sekunden | Nein |
| Position-Toleranz | ±3% | Nein |
| Sweep-Intervall | 5 Minuten | Nein |
| Override-Mindestalter für Sweep | 5 Minuten | Nein |

---

## 6. SCHWELLEN & KONSTANTEN

| Parameter | Wert | Konfigurierbar | Quelle |
|---|---|---|---|
| Gate öffnet | > 20.000 lx | Ja | Alt bewährt |
| Gate schließt | < 15.000 lx | Ja | Alt bewährt |
| Sonnenhöhe Gate | > 5° | Ja | Alt bewährt |
| Privacy-Latch Lux-Schwelle | < 400 lx | Ja | Alt bewährt |
| Open Weekday Mindestzeit | 08:00 Uhr | Ja | Alt bewährt |
| Open Weekend Mindestzeit | 09:30 Uhr | Ja | Alt bewährt |
| Heat Temperaturklasse | ≥ 12 (≥ 24°C) | Ja | Alt bewährt |
| Heat Sonnenhöhe | > 5° | Ja | Alt bewährt |
| Writing-Active Grace | 5 Sekunden | Nein | Alt bewährt |
| Cover-Fahrt Timeout | 90 Sekunden | Nein | Alt bewährt |
| Race-Echo-Fenster | 30 Sekunden | Nein | Alt bewährt |
| Position-Toleranz Warden | ±3% | Nein | Alt bewährt |
| Warden Sweep-Intervall | 5 Minuten | Nein | Alt bewährt |

### Rollo-Positionen

| Modus | Position | Effekt |
|---|---|---|
| Offen | 100% | Rollo komplett oben, nur Plissees |
| Glare PC | 75% | Oberer Bereich leicht abgedunkelt |
| Glare TV | 60% | Obere Hälfte gut abgedeckt |
| Heat | 45% | Sonnenschutz mit leichtem Luftaustausch |
| Verdunkelt | 40% | Rollo + Plissees = vollständig lichtdicht |

---

## 7. ACTIVITY STATE VORARBEIT

→ Siehe `rollo_activity.md`

---

## 8. SCHNITTSTELLEN ZU ANDEREN MODULEN

### Inputs von anderen Modulen

| Modul | Logischer Bezeichner | Status |
|---|---|---|
| Day State | Day State (8 Phasen + Masterphase) | ✅ LH vorhanden |
| Day Context | Day Context Sensor (werktag/wochenende/frei) | ✅ LH vorhanden |
| Context State | Bio-State (sleep/waking/awake) | ✅ LH vorhanden |
| Context State | Haushaltsanwesenheit (leer/nicht_leer) | ✅ LH vorhanden |
| Medienlogik | Media Scenario | ✅ LH vorhanden |
| Medienlogik | Gaming Source | ✅ LH vorhanden (Mai 2026 ergänzt) |
| Fenster-Modul | Fensterstatus Wohnzimmer (0/1/2) | ⏳ LH ausstehend |
| Wetter-/Klima-Modul | Wetterkategorie (sunny/wet/windy/neutral) | ⏳ LH ausstehend |
| Wetter-/Klima-Modul | Temperaturklasse (0–15) | ⏳ LH ausstehend |
| Lux-Modul / Atomics | Außenhelligkeit (lx) | ⏳ LH ausstehend |
| Sun-Atomics | Sonnenhöhe (°) | ⏳ LH ausstehend |

### Outputs an andere Module

Dieses Modul produziert keine Outputs die andere Module konsumieren. Es ist ein reines Aktuator-Modul.

### Cross-Reference

| Abhängigkeit | Notiz |
|---|---|
| Medienlogik-LH | `Gaming Source` Enum wurde im Review dieses Moduls ergänzt (Mai 2026) |
| Wake-Up-Modul | `blind_alarm_wakeup` Boolean ist Platzhalter — Schnittstelle reserviert |
| Hue Dimmer / Switch Manager | Tastenbelegung liegt außerhalb dieses Moduls |

---

## 9. EDGE CASES & FAILURE MODES

| Szenario | Verhalten |
|---|---|
| Außenhelligkeit unknown beim Boot | Gate bleibt im letzten bekannten Zustand; bei erstem Boot: inaktiv |
| Day State unavailable | Kein Fallback möglich — Automation pausiert bis Day State verfügbar |
| Fensterstatus unknown | Wird als 2 (offen) behandelt → Rollo fährt hoch (Sicherheit) |
| Bio-State unknown | Wird als `awake` behandelt |
| Haushaltsanwesenheit unknown | Wird als `nicht_leer` behandelt (konservativ — kein unnötiges Privacy) |
| Media Scenario unknown | Wird als `idle` behandelt → kein Glare |
| Wetterkategorie unknown | Nicht als `sunny` behandelt → Heat greift nicht |
| Temperaturklasse unknown | Als 0 behandelt → Heat greift nicht |
| HA-Neustart mit offenem Fenster | Fenster-Regel (R1) greift sofort beim Start |
| HA-Neustart mit aktivem Privacy-Latch | Recovery-Bedingung in R-PL stellt Latch beim Start wieder her |
| False-positive Override | Override Warden (R-OW) räumt innerhalb von 2 Sekunden auf |
| Cover reagiert nicht auf Befehl | Writing-Active-Flag läuft nach 90s Timeout ab — keine Endlosblockierung |
| Privacy-Latch + Fenster offen | Fenster-Regel (R1) schlägt Privacy — Rollo fährt hoch |

---

## 10. OFFENE FRAGEN

**OQ-1 — Wecker-Modul-Schnittstelle** (Priorität: Niedrig)
`blind_alarm_wakeup` ist Platzhalter. Sobald Wake-Up-Modul-Lastenheft vorliegt, Schnittstelle konkretisieren.

**OQ-2 — Dynamische Glare-Position** (Priorität: Niedrig)
Idee: Glare-Position könnte anhand des aktuellen Sonnenstands dynamisch berechnet werden statt feste Prozentwerte. Je höher die Sonne, desto weniger muss das Rollo runter. Bewusst zurückgestellt.

**OQ-3 — Heat-Position bei geöffnetem Fenster** (Priorität: Niedrig)
Heat auf 45% erlaubt leichten Luftaustausch. Wenn Fenster gekippt ist (Status 1), könnte Heat auf 50% gehen für mehr Durchzug. Noch nicht entschieden.

---

## 11. KONSOLIDIERUNGSHINWEISE

**KH-1 — Gaming Source ist neu im Media-LH**
Das Medienlogik-LH wurde im Review dieses Moduls um den Output `Gaming Source` (tv/pc/none) erweitert. Alle anderen Module die `media_scenario = gaming` konsumieren sollten prüfen ob sie ebenfalls `gaming_source` benötigen.

**KH-2 — Haushaltsanwesenheit für Privacy**
Das Rollo-Modul verwendet Haushaltsanwesenheit (nicht persönliche Anwesenheit) für Privacy. Privacy greift wenn der Haushalt leer ist — unabhängig ob Benni bei den Eltern oder komplett weg ist. Andere Module die Anwesenheit für ähnliche Zwecke nutzen sollten diese Entscheidung kennen.

**KH-3 — Wake-Up-Modul: `blind_alarm_wakeup`**
Der Boolean ist vorbereitet. Wake-Up-Modul-LH muss diesen als Schnittstelle zum Rollo-Modul definieren.

**KH-4 — Day Context: `frei` = `wochenende` für Rollo**
Alle anderen Module die zwischen `frei` und `wochenende` unterscheiden: das Rollo-Modul tut das nicht — beide bedeuten „kein Wecker, spätere Öffnung".

**KH-5 — Lux-Gate: kein eigener Binary-Sensor**
Das Gate lebt als Template-Variable im Ziel-Modus-Sensor (`this.state`-basierter Schmitt). Kein `binary_sensor.blind_lux_gate_active` im Neubau. Module die einen solchen Gate-Sensor erwarten: nicht vorhanden.

---

## 12. DIFF-ANALYSE ALT VS. NEU

| Aspekt | Alt | Neu | Status |
|---|---|---|---|
| Lux-Gate Implementierung | `threshold`-Plattform Binary-Sensor | Template-Schmitt direkt im Ziel-Modus-Sensor | ✗ Geändert — kein Debouncing |
| `blind_tv_glare_bed` | Vorhanden (Prio 10) | Gestrichen | ✗ Von `blind_privacy_bed` übernommen |
| `blind_privacy_bed` Reset | Nur manuell | Automatisch bei Privacy-Latch-Set | ✨ Erweitert |
| Heat-Position | 40% | 45% | ✗ Geändert — Luftaustausch |
| Anwesenheit für Privacy | Persönliche Anwesenheit (nur Benni) | Haushaltsanwesenheit (Benni oder Eltern) | ✗ Geändert |
| Sleep-Erkennung | `sensor.user_sleep_state_combined` (sleep/awake) | Bio-State (sleep/waking/awake) | ✗ Aktualisiert — `waking` wie `awake` |
| `waking` State | Nicht vorhanden | Wie `awake` behandelt | ✨ Neu |
| Tagestyp | Wochentag + Feiertagskalender direkt | Day Context Sensor | ✗ Geändert |
| Feiertage | Wie Wochenende (direkte Bedingung) | `frei` und `wochenende` via Day Context | ✓ Gleiche Semantik, neue Quelle |
| Glare-Trigger | TV-Stack-Mode + PC-Power direkt | `media_scenario` + `gaming_source` | ✗ Geändert — sauberere Entkopplung |
| Eltern-Präsenz beeinflusst Glare | Kommentar im alten Code | Nicht übernommen | ✗ Veralteter Kommentar |
| Override Warden | 7. Automation im alten Code | Übernommen als R-OW | ✓ Übernommen |
| Debug-Sensor | Vorhanden | Übernommen | ✓ Übernommen |
| Tagesablauf-Beispiel | §11 im alten LH | Nicht übernommen (→ Akzeptanzkriterien) | ✗ Nicht übernommen |

---

## 13. INTEGRATIONS- & HACS-ABHÄNGIGKEITEN

| Integration | Typ | Zweck | Kritisch | Alternative |
|---|---|---|---|---|
| HA Template Platform | Core | Ziel-Modus-Sensor, Debug-Sensor, Schmitt-Trigger | Ja | Keine |
| HA Cover Platform | Core | Rollo-Steuerung | Ja | Keine |
| HA Input Boolean | Core | Privacy-Latch, Manual Override, Writing-Active, Privacy-Bed, Alarm-Wakeup | Ja | Keine |
| HA Sun Integration | Core | Sonnenhöhe (Elevation) | Ja | Sun2 HACS als präzisere Alternative |
| Sun2 (HACS) | HACS | Solar-Noon für Day State (indirekt via Day State Modul) | Nein | Native HA Sun |
| Matter / Zigbee (Cover) | Core/HACS | Physisches Rollo-Device | Ja | Keine |

**Hinweis:** Dieses Modul hat keine eigenen HACS-Abhängigkeiten. Alle Abhängigkeiten laufen über vorgelagerte Module (Day State, Day Context, Context State, Medienlogik).
