# Wohnzimmer Rollo — Activity State Vorarbeit

**Version:** 1.0 · Mai 2026
**Modul:** Wohnzimmer Rollo
**Zweck:** Vorarbeit für das spätere konsolidierte Activity State Lastenheft

---

## Benötigte Activity States

Das Rollo-Modul konsumiert den Activity Context aktuell **nicht direkt**. Die relevanten Kontexte werden indirekt über vorgelagerte Sensoren abgebildet:

- **Media-Kontext (free_time, gaming, streaming):** wird über `media_scenario` und `gaming_source` vom Medienlogik-Modul konsumiert — nicht direkt über Activity Context
- **Sleep-Kontext:** wird über Bio-State abgebildet
- **Anwesenheits-Kontext:** wird über Haushaltsanwesenheit abgebildet

Der Activity Context `private_time` könnte theoretisch als zusätzlicher Verdunkelungs-Trigger dienen, ist aber aktuell nicht eingebaut — `blind_privacy_bed` deckt den manuellen Use Case ab.

---

## Reaktion je Activity State

| Activity State | Reaktion Rollo-Modul | Begründung |
|---|---|---|
| `idle` | Keine direkte Reaktion | Fallback-Logik über Day State und Bio-State ausreichend |
| `free_time` | Keine direkte Reaktion | Media Scenario liefert präzisere Information für Glare-Logik |
| `work_home` | Keine direkte Reaktion | PC-Aktivität fließt via `gaming_source` in Glare-Logik ein |
| `work_away` | Keine direkte Reaktion | Haushaltsanwesenheit deckt den Privacy-Aspekt ab |
| `private_time` | Keine direkte Reaktion (bewusst) | `blind_privacy_bed` ist der manuelle Override für diesen Use Case |
| `household` | Keine direkte Reaktion | Kein Rollo-relevanter Kontext |

**Bewusste Entscheidung:** Das Rollo-Modul reagiert nicht direkt auf Activity Context. Die Glare-Logik ist an `media_scenario` + `gaming_source` gekoppelt (sauberere Entkopplung, Media-Modul ist die Single Source of Truth für Medienkontext).

---

## Anforderungen ans spätere AS-Lastenheft

### Keine zwingenden Anforderungen

Das Rollo-Modul stellt keine zwingenden Anforderungen an das Activity State Lastenheft. Die bestehende Architektur mit `media_scenario` als Glare-Trigger ist vollständig und benötigt keinen direkten AS-Konsum.

### Optionale Erweiterung (für späteres Review)

Falls das AS-Lastenheft einen `cinema`-Kontext oder einen `relaxing`-Kontext definiert, könnte das Rollo-Modul darauf reagieren:

- **`cinema`-Kontext** (Film schauen, Verdunkelung gewünscht): könnte als zusätzlicher Trigger für 60% ohne Gate dienen (abendlicher Glare ohne Sonnenlicht). Aktuell bewusst nicht eingebaut — Rollo fährt abends auf 100% (Fallback) und Privacy-Latch übernimmt später.
- **`private_time` als hochprioritärer Override**: falls `blind_privacy_bed` irgendwann abgelöst werden soll, wäre `private_time` der natürliche Ersatz. Aktuell kein Handlungsbedarf.

### Keine Hysterese/Cooldown-Anforderungen

Das Rollo-Modul hat keine spezifischen Anforderungen an AS-Übergangshysterese. Die eigene Schmitt-Trigger-Logik (Lux-Gate) und der Privacy-Latch decken die notwendige Stabilisierung intern ab.

### Keine State-Kombinationen die ausgeschlossen sein müssen

Aus Rollo-Sicht gibt es keine problematischen AS-State-Kombinationen. Das Modul ist robust gegen alle möglichen Eingaben (Failure-Verhalten dokumentiert in Kapitel 9 des Hauptlastenhefte).
