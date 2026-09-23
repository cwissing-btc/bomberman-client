<!--
Sync Impact Report
- Version: 1.2.1 → 2.0.0 (MAJOR: Prinzip IV auf den echten Contract BOT_GUIDE.md umgestellt –
  Keyframe/Delta statt Resync; Nachrichtenformate korrigiert: little-endian, seq-Nibble,
  Frame-Kopf mit Tick; Port 47800);
  1.2.0 → 1.2.1 (PATCH: binäres Nachrichtenformat Client → Server ergänzt);
  1.1.0 → 1.2.0 (MINOR: Prinzip IV um inkrementelle Updates/Resync erweitert;
  zuvor 1.0.0 → 1.1.0: Bot-Modus in Prinzip II ergänzt)
- Geänderte Prinzipien: alle Platzhalter ersetzt (Erstfassung)
  - I. Einfachheit / YAGNI
  - II. Server ist die einzige Quelle der Wahrheit
  - III. Abgestimmtes, dokumentiertes Protokoll
  - IV. UDP-Realität berücksichtigen
  - V. Pragmatisches Testen
- Hinzugefügte Abschnitte: Technische Rahmenbedingungen, Entwicklungsablauf, Governance
- Entfernte Abschnitte: keine
- Offene TODOs: keine
-->

# Bomberman Client Constitution

## Core Principles

### I. Einfachheit / YAGNI

- Es wird nur gebaut, was für das aktuelle Feature benötigt wird.
- Keine spekulativen Abstraktionen, Plugin-Systeme oder Konfigurationsoptionen „für später“.
- Eine neue Abhängigkeit (außer pygame und pytest) MUSS im Plan begründet werden.
- Bei zwei gleichwertigen Lösungen wird die mit weniger Code und weniger Konzepten gewählt.

**Begründung**: Lernprojekt mit begrenzter Zeit. Verständlicher Code ist wichtiger als
Erweiterbarkeit.

### II. Server ist die einzige Quelle der Wahrheit

- Der Client MUSS den Spielzustand ausschließlich aus Server-Updates ableiten.
- Der Client MUSS KEINE Spiellogik (Kollisionen, Explosionen, Treffer, Punkte) entscheiden.
- Eingaben des Spielers werden als Kommandos an den Server gesendet; der Client verändert
  den dargestellten Zustand nicht eigenständig (keine Client-Side-Prediction, solange nicht
  explizit per Spec beschlossen).
- Ein Bot-Modus ist erlaubt: Der Bot ist lediglich eine alternative Eingabequelle. Er wertet
  den empfangenen Zustand aus, um zu entscheiden, *welche* Kommandos gesendet werden, nutzt
  dafür dieselbe Kommando-Schnittstelle wie der menschliche Spieler und entscheidet keine
  Spielergebnisse.

**Begründung**: Vermeidet Inkonsistenzen zwischen Spielern und hält den Client schlank.

### III. Abgestimmtes, dokumentiertes Protokoll

- Das Nachrichtenformat zwischen Client und Server MUSS in einem Protokoll-Dokument
  (Contract) im Repository festgehalten sein.
- Änderungen am Protokoll erfolgen NUR in Absprache mit dem Server-Team und werden im
  Contract nachgezogen, bevor Code angepasst wird.
- Noch nicht abgestimmte Punkte (z. B. weitere Kommandos) werden im Contract explizit als
  „offen“ markiert statt vom Client eigenmächtig festgelegt.

**Begründung**: Server und Client werden von unterschiedlichen Personen entwickelt; die
Schnittstelle ist das größte Integrationsrisiko.

### IV. UDP-Realität berücksichtigen

- Der Client MUSS damit umgehen, dass UDP-Pakete verloren gehen, doppelt oder in falscher
  Reihenfolge ankommen.
- Der Server sendet vollständige Zustände (`KEYFRAME`, alle 30 Ticks) und dazwischen
  Änderungen (`DELTA`, an einen `base_tick` gebunden).
- Der Client MUSS ein `DELTA` NUR anwenden, wenn er den Zustand exakt zu dessen `base_tick`
  hält; andernfalls MUSS er es verwerfen und auf das nächste `KEYFRAME` warten.
- Der Client kann KEINEN Resync anfordern (die Uplink-Nachricht ist nur 2 Byte); die Erholung
  nach Verlust erfolgt ausschließlich über das nächste `KEYFRAME`.
- Frames mit älterem Tick als der gehaltene Zustand MÜSSEN verworfen werden.
- Ungültige oder nicht parsbare Pakete DÜRFEN den Client NICHT zum Absturz bringen; sie
  werden verworfen (und optional geloggt).
- Der Netzwerkempfang DARF die Darstellung (Game-Loop) NICHT blockieren.

**Begründung**: UDP garantiert weder Zustellung noch Reihenfolge; ein Delta auf falscher Basis
führt sonst zu einem stillen Desync. Der verbindliche Ablauf steht in `BOT_GUIDE.md`.

### V. Pragmatisches Testen

- Protokoll-Parsing/-Serialisierung und reine Logik (z. B. Sequenznummern-Prüfung) MÜSSEN
  mit pytest getestet werden.
- Darstellung (pygame-Rendering) und Eingabe werden manuell geprüft; automatisierte UI-Tests
  sind nicht erforderlich.
- Test-First ist erlaubt, aber nicht vorgeschrieben.

**Begründung**: Tests dort, wo Fehler schwer zu finden sind (Netzwerk/Protokoll), ohne
unverhältnismäßigen Aufwand bei der Grafik.

## Technische Rahmenbedingungen

- Sprache: Python 3 (aktuelle stabile Version), Grafik und Eingabe mit pygame.
- Darstellung: Jedes Element auf der Karte (Asset/Kachel) wird mit 64×64 Pixeln gerendert;
  die Spielfeldgröße (Breite × Höhe in Feldern) wird vom Server vorgegeben, die Fenstergröße
  ergibt sich daraus als Kartengröße × 64 px.
- Verbindlicher Protokoll-Contract: `BOT_GUIDE.md` im Projektwurzelverzeichnis (vom Team).
  Alle Byte-Formate, Frame-Typen und Regeln folgen diesem Dokument.
- Byte-Reihenfolge: little-endian für alle Mehrbyte-Felder. Koordinaten sind Feldindizes.
- Nachrichtenformat Client → Server (2 Byte): Byte 0 = Spieler-ID (0–3), Byte 1 =
  `(seq << 4) | Aktionscode`; `seq` ist ein bei jedem Paket erhöhter 4-Bit-Zähler.
- Nachrichtenformat Server → Client: 5-Byte-Kopf (Byte 0 = Frame-Typ, Byte 1–4 = Tick),
  danach frameabhängige Nutzdaten.
- Transport: UDP-Socket zum Server; Adresse und Port beim Start konfigurierbar
  (Standard-Port 47800).
- Kommunikationsmodell: 60 Ticks/s. Anmeldung per `HELLO` (`0xFF 0xFF`) → `ASSIGNED` mit
  Spieler-ID; Lobby bis Start durch den Moderator; dann `MATCH_INIT`, danach `KEYFRAME`/`DELTA`.
  Der Client sendet genau ein Paket pro Tick (Aktion oder `NOOP`).
- Netzwerkcode, Spielzustand und Darstellung liegen in getrennten Modulen, damit Protokoll-
  Logik ohne pygame testbar ist.
- Dokumentation (Specs, Pläne, Tasks, README) wird auf Deutsch verfasst.

## Entwicklungsablauf

- Jedes Feature durchläuft den Spec-Kit-Ablauf: specify → (clarify) → plan → tasks →
  implement.
- Pläne MÜSSEN einen Constitution-Check enthalten; Abweichungen werden dort begründet.
- Für Entwicklung und Tests ohne echten Server darf ein minimaler Test-Server bzw. Mock
  genutzt werden, der sich an den Protokoll-Contract hält.
- Vor dem Zusammenführen: pytest läuft grün, und das Feature wurde einmal manuell gegen den
  (Test-)Server ausprobiert.

## Governance

- Diese Constitution hat Vorrang vor anderen Konventionen im Projekt.
- Änderungen erfolgen über `/speckit-constitution` und werden mit Versionsnummer und Datum
  dokumentiert.
- Versionierung nach SemVer: MAJOR bei Entfernen/Umdeuten von Prinzipien, MINOR bei neuen
  Prinzipien oder Abschnitten, PATCH bei Klarstellungen.
- Bei Plan-Reviews und `/speckit-analyze` wird die Einhaltung der Prinzipien geprüft.

**Version**: 2.0.0 | **Ratified**: 2026-09-23 | **Last Amended**: 2026-09-23
