# ADR-0002: Sleep ausschließlich aus dem Bio-State ableiten

- Status: accepted
- Version: 0.8.5
- Issue: [#28](https://github.com/Levtos/benni_blind_policy/issues/28)
- Parent: [#9](https://github.com/Levtos/benni_blind_policy/issues/9)

## Kontext

Die bisherige `_sleep_active()`-Regel behandelte `early_night` und `late_night`
als alternatives Schlafsignal. Dadurch konnte die Policy bei `bio_state=awake`
oder `waking` den Modus `sleep` wählen. Das vermischt die globale Tagesphase
mit dem persönlichen Schlafzustand und erklärt die Nacht-Privacy fälschlich als
Schlafen.

Die Nachtphase besitzt bereits einen eigenen fachlichen Pfad: Der bestehende
Privacy-Latch wird beim Übergang nach `early_night` beziehungsweise bei dunklem
`late_evening` gesetzt.

## Entscheidung

- `sleep` ist ausschließlich aktiv, wenn der kanonische `bio_state` den Wert
  `sleep` liefert.
- `awake` und `waking` aktivieren `sleep` nie, unabhängig von der Tagesphase.
- `early_night` und `late_night` aktivieren `sleep` nie; sie bleiben dem
  bestehenden Privacy-Latch überlassen.
- Der Privacy-Latch, die Prioritätskette, Apply-/Cooldown-Guards und die
  Core-State-Eigentümerschaft werden nicht verändert.
- Der Trace-Grund für Sleep lautet ausschließlich `sleep:Bio-State sleep`.

## Konsequenzen

Die Policy kann in einer Nachtphase bei wachendem Bio-State `privacy` gewinnen,
sofern der bestehende Privacy-Latch aktiv ist. Erst der kanonische Bio-Übergang
auf `sleep` darf den Sleep-Modus gewinnen. Die bisherige Lastenheftformulierung
„Bio-State sleep oder Nachtphasen“ ist damit für diese Integration superseded;
die verhaltensrelevante Spezifikation und die Regressionstests werden
entsprechend aktualisiert.

Keine Home-Assistant-Live-Änderung, neue Entity, neue Konfiguration oder
Änderung an der Apply-Schicht ist Bestandteil dieser Entscheidung.
