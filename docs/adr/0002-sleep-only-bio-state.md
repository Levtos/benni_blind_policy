# ADR-0002: R4 ausschließlich aus dem effektiven Bio-Schlafkontext ableiten

- Status: accepted
- Version: 0.8.6
- Issue: [#28](https://github.com/Levtos/benni_blind_policy/issues/28)
- Superseding contract: [benni-core-state#59](https://github.com/Levtos/benni-core-state/issues/59)
- Parent: [#9](https://github.com/Levtos/benni_blind_policy/issues/9)

## Kontext

Die ältere `_sleep_active()`-Regel behandelte `early_night` und `late_night`
als alternatives Schlafsignal. Dadurch konnte die Policy bei `bio_state=awake`
oder `waking` den Modus `sleep` wählen. v0.8.5 beschränkte R4 deshalb zunächst
auf den exakten Bio-State `sleep`.

Der verbindliche Live-Audit in Core-State-Issue #59 präzisiert den
Consumer-Vertrag: `provisional_sleep` ist bereits ein Schlafkontext, obwohl der
Schlaf noch nicht bestätigt ist. Die Tagesphase allein bleibt weiterhin kein
Schlafsignal.

## Entscheidung

- R4 `sleep` ist ausschließlich aktiv, wenn der kanonische `bio_state` den Wert
  `provisional_sleep` oder `sleep` liefert:
  `effective_sleep = bio_state in {provisional_sleep, sleep}`.
- `awake` und `waking` aktivieren R4 nie, unabhängig von der Tagesphase.
- `early_night` und `late_night` aktivieren R4 nie selbst; sie bleiben dem
  bestehenden Privacy-Latch überlassen.
- Der Trace-Grund lautet `sleep:Bio-State provisional_sleep|sleep`.
- Das Benni-R4-Profil löst in normalem und invertiertem Direktprofil auf 5 %
  Geräteposition auf.
- Explizit gespeicherte Profilwerte bleiben bewusste Overrides. Ein vorhandener
  Wert 40 wird nicht pauschal auf 5 migriert, weil Default-Herkunft und bewusste
  Benutzeranpassung im gespeicherten Wert nicht unterscheidbar sind.

## Konsequenzen

Bei wachendem Bio-State kann nachts weiterhin `privacy` gewinnen, sofern der
Privacy-Latch aktiv ist. Bei PS oder S gewinnt R4 gemäß der vorhandenen
Prioritätskette; `waking` beendet den Schlafkontext. Der Override-Reset erfolgt
einmal beim Eintritt in PS/S und nicht erneut bei PS→S.

Die v1-Quelldokumente unter `docs/rollo-policy/source-v1/` bleiben als
historischer Review-Stand unverändert. Diese ADR und Issue #59 sind für das
aktuelle Verhalten verbindlich.

Core State kennt weder Cover-Position noch Cover-Aktion. Keine
Home-Assistant-Live-Änderung, neue Entity, Änderung an `blind_control` oder
verdeckter zweiter Apply-Pfad ist Bestandteil dieser Entscheidung.
