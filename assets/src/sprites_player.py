"""Spielerfigur in vier Farbvarianten, mit BTC-Schriftzug auf dem Helm.

Vertikale Aufteilung (wichtig fuer die Lesbarkeit bei 64px):
  y  1..8   Antenne
  y  7..37  Helm / Kopf
  y 11..21  Helmband mit Schriftzug (BTC)
  y 21..38  Gesichtsflaeche (nur Front und Seite)
  y 34..51  Torso
  y 48..55  Beine
  y 53..61  Schuhe

Die Farbvariante wird ueber ein Modul-Level-Dict gesetzt (_S) statt durch
jede Zeichenfunktion gereicht -- das haelt die Signaturen kurz. Einstieg ist
immer player(); die Richtungsfunktionen setzen die Variante selbst.
"""

import math

from pixelart import Canvas, c, mix


# Laufzyklus: 0 und 2 sind Standposen, 1 und 3 die Durchgangsposen.
BOB = [0, -1, 0, -1]
LEG = [0, 1, 0, -1]           # 0 = geschlossen, 1 = links vor, -1 = rechts vor

HEAD_CY = 22
HEAD_RX = 18.0
HEAD_RY = 15.0
TORSO_TOP = 34
TORSO_BOT = 51

BAND_TOP = 11                 # Helmband
BAND_BOT = 21
TEXT_TOP = 13                 # Schriftzug innerhalb des Bands
FACE_CY = 30                  # Gesicht sitzt tief genug, um das Band freizulassen
FACE_RY = 8.0
EYE_CY = 29


# --------------------------------------------------------------- Varianten ---
# d/m/l/xl = Anzugrampe dunkel -> hell, ad/am/al = Akzent (Schuhe, Antenne).
# Die Akzentfarbe ist bewusst ein Kontrast zum Anzug: sie liegt an den Fuessen
# und an der Antennenspitze, also genau da, wo bei 64px die Silhouette endet.
SUITS = {
    "blue": {"d": "blu_d", "m": "blu_m", "l": "blu_l", "xl": "blu_xl",
             "ad": "pnk_d", "am": "pnk_m", "al": "pnk_l"},
    "red":  {"d": "red_d", "m": "red_m", "l": "red_l", "xl": "red_xl",
             "ad": "gry_d", "am": "gry_m", "al": "gry_l"},
    "yellow": {"d": "yel_d", "m": "yel_m", "l": "yel_l", "xl": "yel_xl",
               "ad": "pur_d", "am": "pur_m", "al": "pur_l"},
    "purple": {"d": "pur_d", "m": "pur_m", "l": "pur_l", "xl": "pur_xl",
               "ad": "grn_d", "am": "grn_m", "al": "grn_l"},
}
VARIANTS = list(SUITS.keys())

_S = SUITS["blue"]


def _use(variant):
    global _S
    _S = SUITS[variant]


def _c(key):
    """Farbe aus der aktiven Variante."""
    return c(_S[key])


def _mix(k1, k2, t):
    return mix(_S[k1], _S[k2], t)


# ------------------------------------------------------------- Bitmap-Font ---
# 5x7, ein Zeichen pro Eintrag. Versalien, weil B/T/C als Firmenkuerzel
# gelesen werden sollen und Kleinbuchstaben bei 7px Hoehe Unterlaengen
# und Punzen verlieren.
FONT = {
    "B": ["####.",
          "#...#",
          "#...#",
          "####.",
          "#...#",
          "#...#",
          "####."],
    "T": ["#####",
          "..#..",
          "..#..",
          "..#..",
          "..#..",
          "..#..",
          "..#.."],
    "C": [".###.",
          "#...#",
          "#....",
          "#....",
          "#....",
          "#...#",
          ".###."],
}
GLYPH_W = 5
GLYPH_H = 7


def text_width(s):
    return len(s) * GLYPH_W + (len(s) - 1)


def draw_text(cv, s, x, y, color):
    for ch in s:
        rows = FONT[ch]
        for ry, row in enumerate(rows):
            for rx, px in enumerate(row):
                if px == "#":
                    cv.set(x + rx, y + ry, color)
        x += GLYPH_W + 1


# ----------------------------------------------------------------- Bauteile ---

def _dome(cv, cx, cy, rx, ry):
    """Gewoelbte Helmflaeche, Licht von oben-links."""
    cv.ellipse(cx, cy, rx, ry, _c("m"))
    cv.ellipse_arc_band(cx, cy, rx, ry, _c("d"), dxs=-1.5, dys=-2.0, width=2)
    cv.ellipse(cx - rx * 0.22, cy - ry * 0.30, rx * 0.62, ry * 0.55, _c("l"))
    cv.ellipse(cx - rx * 0.40, cy - ry * 0.46, rx * 0.26, ry * 0.22, _c("xl"))


def _helmet(cv, cx, cy, rx=HEAD_RX, ry=HEAD_RY):
    _dome(cv, cx, cy, rx, ry)
    cv.ellipse_arc_band(cx, cy, rx, ry, _c("xl"), dxs=2.0, dys=2.6, width=1.6)


def _band_and_text(cv, cx, cy, rx, ry, dy=0, label="BTC"):
    """Weisses Band ueber die volle Helmbreite, darauf der Schriftzug.

    Das Band laeuft von Helmkante zu Helmkante statt als Schild in der Mitte
    zu stehen -- so wirkt es wie ein aufgeklebter Streifen und man muss die
    Plakette nicht in die schmalste Helmzeile quetschen.
    """
    def inside(x, y):
        dx = (x + 0.5 - cx) / rx
        dy = (y + 0.5 - cy) / ry
        return dx * dx + dy * dy <= 1.0

    # dy = Kopfwippen des aktuellen Frames. Ohne das bliebe das Band starr
    # stehen, waehrend der Helm darunter wegwippt.
    for y in range(BAND_TOP + dy, BAND_BOT + dy + 1):
        if y == BAND_TOP + dy or y == BAND_BOT + dy:
            col = c("outline")
        elif y == BAND_BOT + dy - 1:
            col = c("gry_l")
        else:
            col = c("wht")
        for x in range(cv.size):
            if inside(x, y):
                cv.set(x, y, col)

    draw_text(cv, label, int(round(cx - text_width(label) / 2)),
              TEXT_TOP + dy, c("outline"))


def _shoe(cv, cx, cy, rx=6.5, ry=3.8):
    cv.ellipse(cx, cy, rx, ry, _c("am"))
    cv.ellipse_arc_band(cx, cy, rx, ry, _c("ad"), dxs=-1, dys=-1.5, width=2)
    cv.ellipse(cx - 1, cy - 1.2, rx * 0.5, ry * 0.45, _c("al"))
    cv.ellipse(cx, cy + ry * 0.62, rx * 0.88, ry * 0.40, c("gry_l"))


def _leg(cv, cx, top, bottom):
    cv.rect(int(cx) - 3, top, int(cx) + 3, bottom, _c("d"))
    cv.rect(int(cx) - 3, top, int(cx) - 2, bottom, _c("m"))


def _glove(cv, cx, cy, r=4.2):
    cv.circle(cx, cy, r, c("wht"))
    cv.ellipse_arc_band(cx, cy, r, r, c("gry_l"), dxs=-1, dys=-1.2, width=1.6)
    cv.circle(cx - 1, cy - 1.2, r * 0.42, c("wht"))


def _arm(cv, shoulder_x, shoulder_y, hand_x, hand_y):
    steps = max(abs(hand_x - shoulder_x), abs(hand_y - shoulder_y), 1)
    for i in range(steps + 1):
        t = i / steps
        x = shoulder_x + (hand_x - shoulder_x) * t
        y = shoulder_y + (hand_y - shoulder_y) * t
        cv.circle(x, y, 3.4, _c("d"))
        cv.circle(x - 0.8, y - 0.8, 2.0, _c("m"))
    _glove(cv, hand_x, hand_y)


def _antenna(cv, cx):
    x = int(cx)
    cv.rect(x - 1, 5, x, 13, c("gry_m"))
    cv.rect(x - 1, 5, x - 1, 13, c("gry_l"))
    cv.circle(cx - 0.5, 3.2, 2.6, _c("am"))
    cv.ellipse_arc_band(cx - 0.5, 3.2, 2.6, 2.6, _c("ad"), dxs=-1, dys=-1, width=1.3)
    cv.set(x - 2, 2, _c("al"))


def _torso(cv, cx, top, bottom, half_w, emblem=True):
    cyc = (top + bottom) / 2
    ry = (bottom - top) / 2
    cv.ellipse(cx, cyc, half_w, ry, _c("m"))
    cv.ellipse_arc_band(cx, cyc, half_w, ry, _c("d"), dxs=-1.5, dys=-2, width=2)
    cv.ellipse(cx - half_w * 0.25, cyc - ry * 0.3, half_w * 0.55, ry * 0.6, _c("l"))

    cv.rect(int(cx - half_w) + 1, bottom - 5, int(cx + half_w) - 1, bottom - 3,
            _c("d"))
    cv.rect(int(cx - half_w) + 1, bottom - 5, int(cx + half_w) - 1, bottom - 5,
            _mix("d", "xl", 0.35))

    if emblem:
        cv.circle(cx, cyc - 2, 5.0, c("wht"))
        cv.circle(cx, cyc - 2, 3.2, _c("am"))
        cv.circle(cx - 1, cyc - 3, 1.4, _c("al"))


def _face_plate(cv, cx, cy, rx=12.0, ry=FACE_RY):
    cv.ellipse(cx, cy, rx, ry, c("skn_m"))
    cv.ellipse_arc_band(cx, cy, rx, ry, c("skn_d"), dxs=-1, dys=-1.5, width=2)
    cv.ellipse(cx - 3, cy - 2, rx * 0.45, ry * 0.42, c("skn_l"))


def _eyes_front(cv, cx, cy):
    for sx in (-7, 7):
        ex = cx + sx
        cv.ellipse(ex, cy, 4.0, 4.6, c("wht"))
        cv.ellipse(ex, cy + 0.6, 2.2, 2.9, c("outline"))
        cv.set(int(ex) - 1, int(cy) - 1, c("wht"))


def _finish(cv):
    cv.outline(c("outline"))
    cv.shade_bottom(amount=0.16, start=0.66)
    cv.snap_to_palette()
    return cv


# ------------------------------------------------------------------ Frames ---

def _player_down(frame):
    cv = Canvas()
    bob = BOB[frame % 4]
    leg = LEG[frame % 4]
    cx = 32
    cv.ground_shadow(32, 60, 16, 3.5)

    if leg == 0:
        _leg(cv, 25, 48 + bob, 55); _shoe(cv, 24, 57)
        _leg(cv, 39, 48 + bob, 55); _shoe(cv, 40, 57)
    elif leg == 1:
        _leg(cv, 24, 48 + bob, 56); _shoe(cv, 23, 58, rx=7.0)
        _leg(cv, 40, 48 + bob, 52); _shoe(cv, 41, 54, rx=5.6, ry=3.2)
    else:
        _leg(cv, 24, 48 + bob, 52); _shoe(cv, 23, 54, rx=5.6, ry=3.2)
        _leg(cv, 40, 48 + bob, 56); _shoe(cv, 41, 58, rx=7.0)

    sw = leg * 3
    _arm(cv, 22, 39 + bob, 15, 46 + bob + sw)
    _arm(cv, 42, 39 + bob, 49, 46 + bob - sw)

    _torso(cv, cx, TORSO_TOP + bob, TORSO_BOT + bob, 13.0)
    _helmet(cv, cx, HEAD_CY + bob)
    _antenna(cv, cx)
    _face_plate(cv, cx, FACE_CY + bob)
    _eyes_front(cv, cx, EYE_CY + bob)
    # Band zuletzt: es soll ueber der Helmwoelbung liegen, aber der Kopf darf
    # beim Laufen mitwippen, deshalb wandert es mit bob mit.
    _band_and_text(cv, cx, HEAD_CY + bob, HEAD_RX, HEAD_RY, dy=bob)
    return _finish(cv)


def _player_up(frame):
    cv = Canvas()
    bob = BOB[frame % 4]
    leg = LEG[frame % 4]
    cx = 32
    cv.ground_shadow(32, 60, 16, 3.5)

    if leg == 0:
        _leg(cv, 25, 48 + bob, 55); _shoe(cv, 24, 57)
        _leg(cv, 39, 48 + bob, 55); _shoe(cv, 40, 57)
    elif leg == 1:
        _leg(cv, 24, 48 + bob, 52); _shoe(cv, 23, 54, rx=5.6, ry=3.2)
        _leg(cv, 40, 48 + bob, 56); _shoe(cv, 41, 58, rx=7.0)
    else:
        _leg(cv, 24, 48 + bob, 56); _shoe(cv, 23, 58, rx=7.0)
        _leg(cv, 40, 48 + bob, 52); _shoe(cv, 41, 54, rx=5.6, ry=3.2)

    sw = leg * 3
    _arm(cv, 22, 39 + bob, 15, 46 + bob - sw)
    _arm(cv, 42, 39 + bob, 49, 46 + bob + sw)

    _torso(cv, cx, TORSO_TOP + bob, TORSO_BOT + bob, 13.0, emblem=False)
    cv.rect(cx - 1, TORSO_TOP + 3 + bob, cx, TORSO_BOT - 6 + bob, _c("d"))

    _helmet(cv, cx, HEAD_CY + bob)
    _antenna(cv, cx)
    # Nackenschutz statt Gesicht -- macht die Rueckansicht eindeutig
    cv.ellipse(cx, 32 + bob, 12.0, 6.2, _c("d"))
    cv.ellipse(cx, 31 + bob, 10.5, 4.6, _c("m"))
    cv.ellipse(cx - 2, 30 + bob, 6.0, 2.4, _c("l"))
    _band_and_text(cv, cx, HEAD_CY + bob, HEAD_RX, HEAD_RY, dy=bob)
    return _finish(cv)


def _player_side(frame, flip=False):
    """Profil. flip=True erzeugt die Linksvariante.

    Der Schriftzug wird erst NACH dem Spiegeln gezeichnet, sonst stuende
    auf dem nach links laufenden Sprite "CTB" in Spiegelschrift.
    """
    cv = Canvas()
    bob = BOB[frame % 4]
    leg = LEG[frame % 4]
    cx = 31
    rx, ry = 16.0, 15.0
    cv.ground_shadow(32, 60, 14, 3.5)

    back_x = 28 - leg * 6
    front_x = 36 + leg * 6
    _leg(cv, back_x, 47 + bob, 55)
    _shoe(cv, back_x - 1, 57, rx=5.8, ry=3.5)
    _leg(cv, front_x, 47 + bob, 55)
    _shoe(cv, front_x + 1, 57, rx=6.4, ry=3.7)

    _arm(cv, 27, 39 + bob, 23 - leg * 4, 46 + bob)

    _torso(cv, cx, TORSO_TOP + bob, TORSO_BOT + bob, 10.5, emblem=False)
    cv.ellipse(cx + 3, 42 + bob, 4.0, 5.2, _c("l"))

    _arm(cv, 36, 39 + bob, 40 + leg * 4, 46 + bob)

    _helmet(cv, cx, HEAD_CY + bob, rx=rx, ry=ry)
    _antenna(cv, cx - 1)

    # Profil: Gesichtsflaeche am rechten Helmrand, Nase steht vor
    fy = FACE_CY + bob
    cv.ellipse(cx + 7, fy, 8.6, 7.4, c("skn_m"))
    cv.ellipse_arc_band(cx + 7, fy, 8.6, 7.4, c("skn_d"), dxs=-1, dys=-1.5, width=2)
    cv.ellipse(cx + 5, fy - 2, 3.4, 3.0, c("skn_l"))
    cv.ellipse(cx + 13.5, fy + 1.5, 2.8, 2.2, c("skn_m"))
    cv.ellipse(cx + 13.0, fy + 0.9, 1.6, 1.1, c("skn_l"))
    cv.set(int(cx) + 15, int(fy) + 3, c("skn_d"))
    cv.line(int(cx) + 9, int(fy) + 5, int(cx) + 12, int(fy) + 5, c("skn_d"))

    cv.ellipse(cx + 7, fy - 3, 3.8, 4.4, c("wht"))
    cv.ellipse(cx + 8.4, fy - 2.6, 2.2, 2.8, c("outline"))
    cv.set(int(cx) + 7, int(fy) - 5, c("wht"))

    if flip:
        cv = cv.flipped_h()
        cx = cv.size - 1 - cx
    _band_and_text(cv, cx, HEAD_CY + bob, rx, ry, dy=bob)
    return _finish(cv)


# -------------------------------------------------------------- Oeffentlich ---

def player(variant, direction, frame):
    """Ein Spieler-Frame. variant aus VARIANTS, direction down/up/left/right."""
    _use(variant)
    if direction == "down":
        return _player_down(frame)
    if direction == "up":
        return _player_up(frame)
    if direction == "right":
        return _player_side(frame, flip=False)
    if direction == "left":
        return _player_side(frame, flip=True)
    raise ValueError(direction)


DIRECTION_NAMES = ["down", "up", "left", "right"]

# Rueckwaertskompatibel: die alten Aufrufe liefern weiter die blaue Figur.
DIRECTIONS = {
    d: (lambda f, _d=d: player("blue", _d, f)) for d in DIRECTION_NAMES
}
