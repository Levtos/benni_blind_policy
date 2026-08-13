# ADR-0001: Gemeinsame Protection Demand für Heat und Glare

- Status: accepted
- Version: 0.8.4
- Issue: [#25](https://github.com/Levtos/benni_blind_policy/issues/25)
- Vorgänger: [#23](https://github.com/Levtos/benni_blind_policy/issues/23)
- Historischer Vorgänger: [#21](https://github.com/Levtos/benni_blind_policy/issues/21)
- Parent: [#9](https://github.com/Levtos/benni_blind_policy/issues/9)

## Entscheidung

Thermischer Hitzeschutz und Glare-/Blendschutz werden vor der bestehenden
Prioritätskette unabhängig bewertet und anschließend in einer internen
`ProtectionDemand` zusammengeführt. Die Demand enthält mindestens die beiden
Aktivzustände, beide fachlichen Zielpositionen, die effektive Zielposition sowie
Gründe und Diagnosewerte. Es wird kein neuer öffentlicher Home-Assistant-Sensor
für diese interne Fusion eingeführt.

Der thermische Zustand benötigt den bereits verwendeten kanonischen
Temperatureingang oberhalb der unveränderten fachlichen Schwelle (`HEAT_TEMP_C`,
aktuell 24 °C) **und** die bestehende direkte-Sonne-/Solar-Eignung. Dafür werden
der numerische Luxwert mit dem bestehenden Heat-Lux-Floor, die Sonnenhöhe über
`HEAT_SUN_MIN_DEG` und die bestehende `HEAT_DAY_STATES`-Phasenmenge gemeinsam
bewertet. Diese Übergangsmenge umfasst `late_morning`, `forenoon`, `midday` und
`afternoon`; dadurch bleibt Heat beim kanonischen Wechsel nach `midday` bei
gültiger Solar-Eignung aktiv. Wetter, Regen oder Bewölkung sind kein Ersatz für
direkte Solar-Eignung; bei etwa 5.000 lx in `late_afternoon` wird Heat daher
nicht allein wegen der Temperatur aktiv. Die thermische Zielposition bleibt 45 %.

Core State berechnet die globalen, saisonal normalisierten Tagesphasen. Dieser
Hotfix führt keine eigene Monats-, Kalender-, Uhrzeit-, Sonnenstands- oder
Tageslängen-Normalisierung in der Blind Policy ein. Die Blind Policy konsumiert
den kanonischen `day_state` und entscheidet ausschließlich domänenspezifisch
über Heat/Glare, die gemeinsame `ProtectionDemand` und die Zielposition.

`late_afternoon` bleibt bewusst außerhalb der Heat-Phasenmenge. Das in Issue
[#23](https://github.com/Levtos/benni_blind_policy/issues/23) festgelegte helle
`late_afternoon`-Verhalten wird dadurch nicht zurückgebaut.

Glare bleibt eigenständig: Das bestehende Lux-Gate verwendet die Schmitt-Grenzen
20.000 lx zum Aktivieren und 15.000 lx zum Deaktivieren, die Zwischenzone hält
den letzten gültigen Zustand. Sonnenwinkel/Tagesphase und die vorhandenen
TV-/Streaming-/Gaming-Bedingungen wirken auf Glare; der Glare-Schmitt-Zustand
wird nicht als konkurrierender First-Match-Zweig gegen Thermal ausgewertet. Die
Glare-Zielpositionen bleiben 60 % für TV und 75 % für PC-Gaming.

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

`unknown`, `unavailable` und nichtnumerische Temperatur- oder Solarwerte
erzeugen keinen neuen gültigen thermischen Zustand. Ein zuvor gültiger Zustand
wird bei einem kurzzeitigen Ausfall gehalten; sobald die numerischen Eingänge
wieder verfügbar sind, erfolgt die normale sofortige Neubewertung. Ein einzelner
ausgefallener Glare-Eingang löscht daher keinen gültigen Thermal-Schutz. Der
Glare-Gate-Zustand wird bei transientem Start- oder Reload-Ausfall ebenfalls
gehalten.

Der automatische Evening-Privacy-Latch wird bei numerischem, erkennbarem
Tageslicht in `late_afternoon` zurückgesetzt und in derselben Phase nicht direkt
wieder gesetzt. Dieser Reset verändert weder `privacy_bed` noch die fachliche
Privacy bei leerem Haushalt oder einen expliziten manuellen Zustand. Der Trace
kennzeichnet Privacy als `privacy:evening:auto_latch`,
`privacy:manual:privacy_bed` oder `privacy:away:household_empty`.

Die aktive Policy und die Combined-/Diagnose-Auswertung verwenden dieselbe
`ProtectionDemand`. Dadurch können sie bei gleichzeitigem Heat und Glare nicht
mehr voneinander abweichende Zielpositionen melden.
