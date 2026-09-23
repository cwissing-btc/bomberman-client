# Feature Specification: Bomberman-Spielclient (Anmeldung, Spielfeld, Steuerung, Bot-Modus)

**Feature Branch**: `001-game-client`

**Created**: 2026-09-23

**Status**: Draft

**Input**: pygame-Client für die Bomberman-Arena des Teams. Verbindlicher Protokoll-Contract:
`BOT_GUIDE.md` (Projektwurzel). Zusammenfassung für den Client: [contracts/protocol.md](./contracts/protocol.md).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Anmelden, Lobby, Spielfeld sehen (Priority: P1)

Der Spieler startet den Client mit Serveradresse (Host, Port; Standard-Port 47800). Der Client
meldet sich per `HELLO` an und bekommt eine Spieler-ID (0–3) zugeteilt. Bis der Moderator das
Match startet, zeigt der Client die Lobby an (belegte Plätze, Countdown). Sobald das Match
beginnt, empfängt der Client die statischen Matchdaten und danach 60-mal pro Sekunde
Zustandsframes und zeigt das Spielfeld in 64×64-Kacheln mit den Team-Assets an: Boden, Wände,
Kisten, Spieler (in Blickrichtung), Bomben, Flammen und Power-ups.

**Why this priority**: Ohne Anmeldung, Lobby und Anzeige ist kein Spielen möglich. Diese Story
beweist, dass Client und Server nach `BOT_GUIDE.md` zusammenspielen.

**Independent Test**: Client gegen die Arena starten, in der Lobby erscheinen, Match starten
lassen und prüfen, dass das Spielfeld korrekt und flüssig dargestellt wird.

**Acceptance Scenarios**:

1. **Given** eine laufende Arena, **When** der Client startet, **Then** sendet er `HELLO` und
   zeigt nach `ASSIGNED` seine Spieler-ID und die Lobby an.
2. **Given** der Client wartet in der Lobby, **When** `LOBBY_STATUS` eintrifft, **Then** zeigt
   er belegte Plätze und ggf. den Countdown an.
3. **Given** der Moderator startet das Match, **When** `MATCH_INIT` und danach `KEYFRAME`
   eintreffen, **Then** öffnet der Client das Fenster in Kartengröße × 64 px und zeigt das
   Spielfeld an.
4. **Given** ein angezeigter Zustand zum Tick *t*, **When** ein `DELTA` mit `base_tick = t`
   eintrifft, **Then** wendet der Client die Änderungen an und hält nun Tick *t+1*.
5. **Given** ein angezeigter Zustand, **When** ein `DELTA` mit `base_tick ≠` gehaltenem Tick
   eintrifft (Paketverlust), **Then** verwirft der Client es und wartet auf das nächste
   `KEYFRAME`.
6. **Given** der Client verpasst `MATCH_INIT`, **When** 1 s ohne verwertbaren Zustand vergeht,
   **Then** sendet er erneut `HELLO`, um `MATCH_INIT` anzufordern.
7. **Given** die Lobby ist voll oder gesperrt, **When** nach 5 s kein `ASSIGNED` kommt,
   **Then** zeigt der Client eine verständliche Meldung an.

---

### User Story 2 - Figur manuell steuern (Priority: P2)

Im manuellen Modus steuert der Spieler mit den Pfeiltasten und legt mit der Leertaste eine
Bombe. Der Client sendet pro Tick genau ein Paket: die zuletzt gedrückte Aktion, sonst `NOOP`,
jeweils mit erhöhtem Sequenz-Nibble. Die Figur bewegt sich, sobald der Server den neuen Zustand
zurückmeldet.

**Why this priority**: Macht aus der Anzeige ein spielbares Spiel. Baut auf Story 1 auf.

**Independent Test**: Angemeldet im Match Tasten drücken und prüfen, dass die Figur sich
entsprechend bewegt und Bomben erscheinen.

**Acceptance Scenarios**:

1. **Given** ein laufendes Match im manuellen Modus, **When** eine Pfeiltaste gedrückt ist,
   **Then** sendet der Client im nächsten Tick den passenden Bewegungscode.
2. **Given** dasselbe, **When** die Leertaste gedrückt ist, **Then** sendet der Client `BOMB`
   (bzw. eine Kombi-Aktion, falls gleichzeitig eine Richtung anliegt).
3. **Given** keine Taste ist gedrückt, **When** ein Tick vergeht, **Then** sendet der Client
   `NOOP` mit erhöhtem Sequenz-Nibble.
4. **Given** ein laufendes Match, **When** der Client ein Kommando sendet, **Then** verändert er
   die Anzeige nicht selbst, sondern erst mit dem nächsten Server-Zustand.

---

### User Story 3 - Bot-Modus: Computer spielt selbst (Priority: P3)

Der Spieler aktiviert den Bot-Modus (beim Start oder mit Taste `B`). Der Bot wertet jeden neuen
Zustand aus und sendet eigenständig Aktionen. Einfache Strategie: Flammenzellen und den
Wirkungsbereich zündender Bomben meiden; Bomben (per Kombi-Aktion, um sofort wegzulaufen) neben
Kisten oder Gegnern legen; Power-ups einsammeln, wenn sicher erreichbar.

**Why this priority**: Gutes Lernthema, aber für ein spielbares Spiel nicht notwendig. Setzt
Story 1 und die Aktionen aus Story 2 voraus.

**Independent Test**: Client im Bot-Modus laufen lassen; beobachten, dass die Figur überlebt,
Kisten sprengt und meist nicht in Flammen läuft.

**Acceptance Scenarios**:

1. **Given** der Bot-Modus ist aktiv, **When** ein neuer Zustand eintrifft, **Then** sendet der
   Client ohne Tastatureingabe eine passende Aktion (oder `NOOP`).
2. **Given** die Figur steht auf/neben einer Flammen- oder bald brennenden Zelle, **When** ein
   sicherer Nachbarweg existiert, **Then** bewegt der Bot die Figur aus der Gefahr.
3. **Given** die Figur steht neben einer Kiste oder einem Gegner, **When** danach ein sicheres
   Feld erreichbar ist, **Then** legt der Bot per Kombi-Aktion eine Bombe und läuft weg.
4. **Given** der Bot-Modus ist aktiv, **When** der Spieler Pfeiltasten/Leertaste drückt,
   **Then** werden diese ignoriert (der Bot steuert).
5. **Given** ein laufendes Match, **When** der Spieler die Taste `B` drückt, **Then** wechselt
   der Client zwischen Bot- und manuellem Modus; der aktive Modus ist im Fenster sichtbar.

---

### Edge Cases

- Kein `ASSIGNED` (Lobby voll/gesperrt oder falscher Port) → nach 5 s verständliche Meldung;
  `HELLO` wird bis dahin alle 500 ms wiederholt.
- `MATCH_INIT` ganz verpasst → erneutes `HELLO` fordert es an.
- Einzelnes `DELTA` verloren → nächstes `KEYFRAME` (≤ 0,5 s) stellt den Zustand wieder her.
- Frames in falscher Reihenfolge / ältere Ticks → werden verworfen.
- Beschädigtes oder zu kurzes Paket → wird ignoriert, der Client läuft weiter.
- Unbekannter Kachel-/Frame-/Power-up-Code → neutrale Platzhalter-Kachel bzw. Ignorieren.
- 3 s lang kein Frame → Hinweis „Verbindung verloren“.
- Eigene Figur gestorben (`PLAYER_DEATH`) → Statusanzeige; im Bot-Modus werden keine sinnvollen
  Aktionen mehr gesendet (nur `NOOP`).
- `MATCH_END` → Ergebnis/Gewinner anzeigen; danach zurück in die Lobby-Anzeige.
- Fenster geschlossen → Client beendet sich sauber.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Der Client MUSS beim Start Serveradresse (Host, Port; Standard 47800), den
  Anfangsmodus (manuell/Bot) und einen Anzeigenamen (Standard „Carsten") entgegennehmen und
  den Namen im `HELLO` an den Server übertragen (max. 24 Byte UTF-8).
- **FR-002**: Der Client MUSS sich per `HELLO` (`0xFF 0xFF`) anmelden und die Spieler-ID aus
  `ASSIGNED` übernehmen; ohne Antwort MUSS er `HELLO` alle 500 ms wiederholen.
- **FR-003**: Kommt innerhalb von 5 s kein `ASSIGNED`, MUSS der Client eine Fehlermeldung
  anzeigen.
- **FR-004**: Der Client MUSS die Lobby (`LOBBY_STATUS`) anzeigen und beim Matchstart
  `MATCH_INIT` sowie die folgenden `KEYFRAME`/`DELTA`-Frames verarbeiten.
- **FR-005**: Der Client MUSS ein `DELTA` nur anwenden, wenn er den Zustand exakt zu dessen
  `base_tick` hält; sonst MUSS er es verwerfen und auf das nächste `KEYFRAME` warten.
- **FR-005a**: Ein `KEYFRAME` ersetzt den Zustand vollständig; Frames mit älterem Tick als der
  gehaltene Zustand MÜSSEN verworfen werden.
- **FR-005b**: Erhält der Client nach dem Start 1 s lang keinen verwertbaren Zustand, MUSS er
  erneut `HELLO` senden, um `MATCH_INIT` anzufordern. Ein anforderbarer Resync existiert nicht.
- **FR-006**: Der Client MUSS beschädigte, zu kurze oder unbekannte Nachrichten ignorieren,
  ohne abzustürzen.
- **FR-007**: Der Client MUSS die vom Server vorgegebene Kartengröße übernehmen, jedes Element
  als 64×64-Kachel darstellen und das Fenster erst nach `MATCH_INIT` in Größe Kartengröße × 64
  px öffnen.
- **FR-008**: Der Client MUSS unterscheidbar darstellen: freies Feld, feste Wand, Kiste,
  Spieler (in Blickrichtung laut `facing`), Bombe, Flamme, Power-up.
- **FR-009**: Der Client MUSS pro Tick genau ein 2-Byte-Paket senden: Byte 0 = eigene
  Spieler-ID, Byte 1 = `(seq << 4) | Aktion`, mit bei jedem Paket erhöhtem `seq`-Nibble.
- **FR-010**: Ohne Eingabe MUSS der Client `NOOP` senden; im manuellen Modus MUSS er die aktuell
  gedrückten Tasten in einen Aktionscode (inkl. Kombi-Aktionen 6–9) umsetzen.
- **FR-011**: Der Client DARF den angezeigten Spielzustand NICHT selbst verändern; Änderungen
  kommen ausschließlich aus Server-Frames.
- **FR-012**: Im Bot-Modus MUSS der Client nach jedem neuen Zustand eigenständig eine Aktion
  wählen und ausschließlich die Aktionscodes aus `BOT_GUIDE.md` verwenden.
- **FR-013**: Der Bot MUSS aktive Flammenzellen (`FLAME_ADD`) sowie den zu erwartenden
  Wirkungsbereich zündender Bomben meiden, sofern ein sicherer Zug existiert.
- **FR-014**: Der Bot SOLL per Kombi-Aktion eine Bombe legen und ausweichen, wenn er neben einer
  Kiste oder einem Gegner steht und danach ein sicheres Feld erreichbar ist.
- **FR-014b**: Der Bot MUSS rechtzeitig vor Sudden Death (mind. 20 s) randnahe Ziele meiden,
  bevorzugt Felder aufsuchen, die noch lange offen bleiben, und ohne Ziel von bald schließenden
  Feldern nach innen ziehen (Schließ-Reihenfolge des Servers).
- **FR-015**: Der Client MUSS „Verbindung verloren“ anzeigen, wenn 3 s lang kein Frame eintraf.
- **FR-016**: Der Client MUSS Spielstatus anzeigen: eigener Tod (`PLAYER_DEATH`), Matchende
  (`MATCH_END`) mit Gewinner/Platzierung, danach Rückkehr in die Lobby-Anzeige.
- **FR-017**: Die gesamte Byte-Kodierung/-Dekodierung MUSS zentral in einem Modul liegen und
  `BOT_GUIDE.md` folgen (little-endian, Frame-Formate, 2-Bit-Kachelgitter, Regelblock).
- **FR-018**: Der Spieler MUSS während des Matches mit Taste `B` zwischen Bot- und manuellem
  Modus wechseln können.
- **FR-019**: Der Client MUSS den aktiven Modus, die Verbindung und den Spielstatus im Fenster
  anzeigen.

### Key Entities

- **Verbindungskonfiguration**: Host, Port, Anfangsmodus, optionaler lokaler Anzeigename.
- **Frame** (Server → Client): Typ + Tick + Nutzdaten; Typen `ASSIGNED`, `LOBBY_STATUS`,
  `MATCH_INIT`, `KEYFRAME`, `DELTA`, `MATCH_END`.
- **Statische Matchdaten** (`MATCH_INIT`): Kartengröße, Kachelgitter, Startzellen, Regelblock.
- **Kachel**: frei / feste Wand / Kiste (2-Bit-Gitter).
- **Spieler**: ID (0–3), Position, `facing`, lebendig/bewegt, Bomben-Max, Reichweite, Tempo,
  Punkte; einer davon ist der eigene.
- **Bombe / Flamme / Power-up**: Position und Eigenschaften laut `BOT_GUIDE.md` §5 (Flammenzellen
  sind tödlich; Power-up-Arten: extra Bombe, größere Flamme, Tempo).
- **Aktion**: `NOOP, UP, DOWN, LEFT, RIGHT, BOMB, UP+BOMB … RIGHT+BOMB, HELLO` mit Sequenz-Nibble.
- **Spielmodus**: manuell oder Bot.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Ein Spieler ist nach dem Start in unter 5 s in der Lobby sichtbar (bei laufender
  Arena).
- **SC-002**: Eine Tasteneingabe wird spätestens im nächsten Tick (≈ 16,6 ms) gesendet und wird
  mit dem folgenden Server-Zustand sichtbar.
- **SC-003**: Bei simuliertem Paketverlust von 10 % der Frames stimmt das angezeigte Spielfeld
  nach jedem Verlust spätestens 0,5 s später (nächstes `KEYFRAME`) wieder mit dem Server überein;
  die Anzeige zeigt nie einen älteren Zustand als gehalten.
- **SC-004**: Der Client läuft ein komplettes Match (mehrere Minuten) ohne Absturz, auch bei
  beschädigten Paketen.
- **SC-005**: Im Bot-Modus überlebt die Figur in mindestens 80 % der Fälle die eigene gelegte
  Bombe.
- **SC-006**: Der Client funktioniert gegen die Team-Arena, ohne dass `BOT_GUIDE.md` geändert
  werden muss.

## Clarifications

### Session 2026-09-23

- Q: Soll der Spieler während des Spiels zwischen Bot- und manuellem Modus umschalten können?
  → A: Ja, jederzeit per Taste `B`; im Bot-Modus werden Steuertasten ignoriert.
- Q: Wer legt die Spielfeldgröße fest? → A: Der Server (in `MATCH_INIT`).
- Q: Wie sieht das echte Protokoll aus? → A: Verbindlich in `BOT_GUIDE.md`; Uplink 2 Byte
  (Spieler-ID, seq+Aktion), Downlink Frame-Kopf (Typ + Tick), little-endian, Keyframe/Delta,
  kein Resync, Anmeldung per `HELLO`.
- Q: Wird ein Spielername übertragen? → A: Ursprünglich nein (Slot-ID 0–3). Seit dem
  Server-Update vom 2026-09-23 kann das HELLO einen Namen tragen (`FF FF len name`, ≤ 24 Byte);
  der Client sendet ihn, Standard „Carsten". Ein Moderator-Rename gewinnt.

## Assumptions

- Verbindlicher Contract ist `BOT_GUIDE.md`; die Team-Arena ist zum Testen verfügbar
  (`just server`, Web-UI auf Port 8080).
- Die Spielfeldgröße kommt vom Server; das Fenster wird erst nach `MATCH_INIT` geöffnet.
- Für die Darstellung werden die Team-Assets in `assets/` genutzt (64×64). Von den fünf
  Power-up-Sprites bildet der Server nur drei Arten ab (`kick`/`remote` bleiben ungenutzt).
- Regelkonstanten werden aus dem Regelblock in `MATCH_INIT` gelesen, nicht hartkodiert.
- Ein optionaler Test-Server/Mock darf zur Entwicklung dienen, muss sich aber an `BOT_GUIDE.md`
  halten; primär wird gegen die echte Arena getestet.
- Nicht Teil dieses Features: Sound, Chat, Statistiken, ein grafisches Startmenü.
- Die Bot-Strategie ist bewusst einfach; ein „starker“ oder lernender Bot ist nicht Ziel.
