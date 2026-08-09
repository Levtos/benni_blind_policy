# ADR-0001: Gemeinsame Protection Demand für Heat und Glare

- Status: accepted
- Version: 0.8.2
- Datum: 2026-08-09
- Issue: [#21](https://github.com/Levtos/benni_blind_policy/issues/21)
- Parent: [#9](https://github.com/Levtos/benni_blind_policy/issues/9)

## Entscheidung

Thermischer Hitzeschutz und Glare-/Blendschutz werden vor der bestehenden
Prioritätskette unabhängig bewertet und anschließend in einer internen
`ProtectionDemand` zusammengeführt. Die Demand enthält mindestens die beiden
Aktivzustände, beide fachlichen Zielpositionen, die effektive Zielposition sowie
Gründe und Diagnosewerte. Es wird kein neuer öffentlicher Home-Assistant-Sensor
für diese interne Fusion eingeführt.

Der thermische Zustand wird ausschließlich aus dem bereits verwendeten
kanonischen Temperatureingang und der unveränderten fachlichen Schwelle
(`HEAT_TEMP_C`, aktuell 24 °C) abgeleitet. Wetter, Regen, Bewölkung, Lux,
Sonnenwinkel, Medien-Szenario und Glare-Gate dürfen diesen Zustand weder
blockieren noch abschalten. Die thermische Zielposition bleibt 45 %.

Glare bleibt eigenständig: Das bestehende Lux-Gate verwendet die Schmitt-Grenzen
20.000 lx zum Aktivieren und 15.000 lx zum Deaktivieren, die Zwischenzone hält
den letzten gültigen Zustand. Sonnenwinkel/Tagesphase und die vorhandenen
TV-/Streaming-/Gaming-Bedingungen wirken nur auf Glare. Die Glare-Zielpositionen
bleiben 60 % für TV und 75 % für PC-Gaming.

Sind Heat und Glare gleichzeitig aktiv, gewinnt die stärker schließende Position.
Die Richtung wird aus dem aktiven Positionsprofil abgeleitet; die Fusion setzt
nicht blind `min` oder `max` voraus. Mit dem bestehenden Normalprofil ergibt
das Heat 45 % gegenüber Glare 60 % bzw. 75 % und damit effektiv 45 %.

## Unveränderte Prioritäten und Ausfälle

Die bestehenden übergeordneten Regeln bleiben vor der fusionierten Demand:
`window_open` bleibt absolut und unmittelbar wirksam; Privacy-Bett, Wecker,
Sleep und Privacy behalten ihre bestehende Reihenfolge. Die allgemeine
Prioritätskette wird nicht neu sortiert. Der Debounce-/Cooldown-Hotfix aus
Issue #19 bleibt separat und unverändert.

`unknown`, `unavailable` und nichtnumerische Temperaturwerte erzeugen keinen
neuen gültigen thermischen Zustand. Ein zuvor gültiger thermischer Zustand wird
bis zur nächsten numerischen Temperaturbewertung gehalten. Gleiches gilt für
den Lux-/Glare-Gate-Zustand bei transientem Start- oder Reload-Ausfall; sobald
die numerischen Eingänge wieder verfügbar sind, erfolgt die normale sofortige
Neubewertung. Ein nicht verfügbarer Glare-Eingang löscht daher keinen gültigen
Thermal-Schutz.

Die aktive Policy und die Combined-/Diagnose-Auswertung verwenden dieselbe
`ProtectionDemand`. Dadurch können sie bei gleichzeitigem Heat und Glare nicht
mehr voneinander abweichende Zielpositionen melden.
