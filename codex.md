# Codex Instructions — Blind Policy

Lies zuerst `CLAUDE.md`. MCP: `einhornzentrale` (HA), `plane` (FLEET-Board).

## Status

v0.1.0 Erstbau durch Claude (FLEET-11). Backend + 53 Pure-Logic-Tests grün, Live-Verify offen.

## Owner-Disziplin

FLEET-11 ist `owner:claude`. Nicht gleichzeitig dieselbe Integration bearbeiten.
Child-Cards FLEET-56..61 koordinieren den Feinschliff.

## Anti-Patterns

- ❌ Cross-Modul-Python-Import (Quellen nur als Entity-IDs aus dem Flow)
- ❌ HA-Imports in `policy.py` (sonst nicht pytest-testbar)
- ❌ Wetterkategorie/Temperaturklasse als Combined-Sensor faken — Heat ist in-policy
- ❌ `position_profile` (Modus→Position) mit `profile` (benni/eltern-Route) verwechseln
- ❌ Apply scharf schalten ohne Live-Verify (Default Shadow ist Absicht)
