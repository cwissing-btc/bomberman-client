"""Spielerfigur: grosser Helmkopf, kompakter Koerper, 4 Richtungen a 4 Frames.

Vertikale Aufteilung (wichtig fuer die Lesbarkeit bei 64px):
  y  1..8   Antenne
  y  7..37  Helm / Kopf
  y 34..51  Torso
  y 48..55  Beine
  y 53..61  Schuhe
So bleiben die Fuesse unterhalb der Torso-Silhouette und der Laufzyklus
ist auch bei 1:1-Darstellung zu erkennen.
"""

from pixelart import Canvas, c, mix


# Laufzyklus: 0 und 2 sind Standposen, 1 und 3 die Durchgangsposen.
BOB = [0, -1, 0, -1]
LEG = [0, 1, 0, -1]           # 0 = geschlossen, 1 = links vor, -1 = rechts vor

HEAD_CY = 22
HEAD_RX = 18.0
HEAD_RY = 15.0
TORSO_TOP = 34
TORSO_BOT = 51


def _dome(cv, cx, cy, rx, ry, base="blu_m", lo="blu_d", hi="blu_l", glint="blu_xl"):
    """Gewoelbte Flaeche, Licht von oben-links."""
    cv.ellipse(cx, cy, rx, ry, c(base))
    cv.ellipse_arc_band(cx, cy, rx, ry, c(lo), dxs=-1.5, dys=-2.0, width=2)
    cv.ellipse(cx - rx * 0.22, cy - ry * 0.30, rx * 0.62, ry * 0.55, c(hi))
    cv.ellipse(cx - rx * 0.40, cy - ry * 0.46, rx * 0.26, ry * 0.22, c(glint))


def _shoe(cv, cx, cy, rx=6.5, ry=3.8):
    cv.ellipse(cx, cy, rx, ry, c("pnk_m"))
    cv.ellipse_arc_band(cx, cy, rx, ry, c("pnk_d"), dxs=-1, dys=-1.5, width=2)
    cv.ellipse(cx - 1, cy - 1.2, rx * 0.5, ry * 0.45, c("pnk_l"))
    cv.ellipse(cx, cy + ry * 0.62, rx * 0.88, ry * 0.40, c("gry_l"))


def _leg(cv, cx, top, bottom):
    cv.rect(int(cx) - 3, top, int(cx) + 3, bottom, c("blu_d"))
    cv.rect(int(cx) - 3, top, int(cx) - 2, bottom, c("blu_m"))


def _glove(cv, cx, cy, r=4.2):
    cv.circle(cx, cy, r, c("wht"))
    cv.ellipse_arc_band(cx, cy, r, r, c("gry_l"), dxs=-1, dys=-1.2, width=1.6)
    cv.circle(cx - 1, cy - 1.2, r * 0.42, c("wht"))


def _arm(cv, shoulder_x, shoulder_y, hand_x, hand_y):
    """Oberarm als kurze Kapsel, Hand als Handschuh."""
    steps = max(abs(hand_x - shoulder_x), abs(hand_y - shoulder_y), 1)
    for i in range(steps + 1):
        t = i / steps
        x = shoulder_x + (hand_x - shoulder_x) * t
        y = shoulder_y + (hand_y - shoulder_y) * t
        cv.circle(x, y, 3.4, c("blu_d"))
        cv.circle(x - 0.8, y - 0.8, 2.0, c("blu_m"))
    _glove(cv, hand_x, hand_y)


def _antenna(cv, cx):
    """Stiel steht sichtbar ueber dem Helm, Kugel als Farbakzent."""
    x = int(cx)
    cv.rect(x - 1, 5, x, 13, c("gry_m"))
    cv.rect(x - 1, 5, x - 1, 13, c("gry_l"))
    cv.circle(cx - 0.5, 3.2, 2.6, c("pnk_m"))
    cv.ellipse_arc_band(cx - 0.5, 3.2, 2.6, 2.6, c("pnk_d"), dxs=-1, dys=-1, width=1.3)
    cv.set(x - 2, 2, c("pnk_l"))


def _torso(cv, cx, top, bottom, half_w, emblem=True):
    cyc = (top + bottom) / 2
    ry = (bottom - top) / 2
    cv.ellipse(cx, cyc, half_w, ry, c("blu_m"))
    cv.ellipse_arc_band(cx, cyc, half_w, ry, c("blu_d"), dxs=-1.5, dys=-2, width=2)
    cv.ellipse(cx - half_w * 0.25, cyc - ry * 0.3, half_w * 0.55, ry * 0.6, c("blu_l"))

    cv.rect(int(cx - half_w) + 1, bottom - 5, int(cx + half_w) - 1, bottom - 3,
            c("blu_d"))
    cv.rect(int(cx - half_w) + 1, bottom - 5, int(cx + half_w) - 1, bottom - 5,
            mix("blu_d", "blu_xl", 0.35))

    if emblem:
        cv.circle(cx, cyc - 2, 5.0, c("wht"))
        cv.circle(cx, cyc - 2, 3.2, c("pnk_m"))
        cv.circle(cx - 1, cyc - 3, 1.4, c("pnk_l"))


def _face_plate(cv, cx, cy, rx=12.0, ry=8.6):
    cv.ellipse(cx, cy, rx, ry, c("skn_m"))
    cv.ellipse_arc_band(cx, cy, rx, ry, c("skn_d"), dxs=-1, dys=-1.5, width=2)
    cv.ellipse(cx - 3, cy - 2, rx * 0.45, ry * 0.42, c("skn_l"))


def _eyes_front(cv, cx, cy):
    for sx in (-7, 7):
        ex = cx + sx
        cv.ellipse(ex, cy, 4.2, 5.2, c("wht"))
        cv.ellipse(ex, cy + 0.6, 2.3, 3.2, c("outline"))
        cv.set(int(ex) - 1, int(cy) - 1, c("wht"))


def _helmet(cv, cx, cy, rx=HEAD_RX, ry=HEAD_RY):
    _dome(cv, cx, cy, rx, ry)
    cv.ellipse_arc_band(cx, cy, rx, ry, c("blu_xl"), dxs=2.0, dys=2.6, width=1.6)


def _finish(cv):
    cv.outline(c("outline"))
    cv.shade_bottom(amount=0.16, start=0.66)
    cv.snap_to_palette()
    return cv


# ------------------------------------------------------------------ Frames ---

def player_down(frame):
    cv = Canvas()
    bob = BOB[frame % 4]
    leg = LEG[frame % 4]
    cx = 32
    cv.ground_shadow(32, 60, 16, 3.5)

    # Beine + Schuhe: bei Durchgangsposen ist ein Bein angehoben
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
    _face_plate(cv, cx, 29 + bob)
    _eyes_front(cv, cx, 28 + bob)
    return _finish(cv)


def player_up(frame):
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
    cv.rect(cx - 1, TORSO_TOP + 3 + bob, cx, TORSO_BOT - 6 + bob, c("blu_d"))

    _helmet(cv, cx, HEAD_CY + bob)
    _antenna(cv, cx)
    # Nackenschutz statt Gesicht -- macht die Rueckansicht eindeutig
    cv.ellipse(cx, 32 + bob, 12.0, 6.2, c("blu_d"))
    cv.ellipse(cx, 31 + bob, 10.5, 4.6, c("blu_m"))
    cv.ellipse(cx - 2, 30 + bob, 6.0, 2.4, c("blu_l"))
    return _finish(cv)


def player_side(frame):
    """Blick nach rechts. Die Linksvariante entsteht per Spiegelung."""
    cv = Canvas()
    bob = BOB[frame % 4]
    leg = LEG[frame % 4]
    cx = 31
    cv.ground_shadow(32, 60, 14, 3.5)

    # Hinteres Bein zuerst, damit sich die Beine ueberlappen
    back_x = 28 - leg * 6
    front_x = 36 + leg * 6
    _leg(cv, back_x, 47 + bob, 55)
    _shoe(cv, back_x - 1, 57, rx=5.8, ry=3.5)
    _leg(cv, front_x, 47 + bob, 55)
    _shoe(cv, front_x + 1, 57, rx=6.4, ry=3.7)

    # Hinterer Arm liegt hinter dem Torso
    _arm(cv, 27, 39 + bob, 23 - leg * 4, 46 + bob)

    _torso(cv, cx, TORSO_TOP + bob, TORSO_BOT + bob, 10.5, emblem=False)
    cv.ellipse(cx + 3, 42 + bob, 4.0, 5.2, c("blu_l"))

    # Vorderer Arm ueber dem Torso
    _arm(cv, 36, 39 + bob, 40 + leg * 4, 46 + bob)

    _helmet(cv, cx, HEAD_CY + bob, rx=16.0, ry=15.0)
    _antenna(cv, cx - 1)

    # Profil: Gesichtsflaeche sitzt rechts am Helmrand, Nase steht vor
    fy = 29 + bob
    cv.ellipse(cx + 7, fy, 8.6, 7.8, c("skn_m"))
    cv.ellipse_arc_band(cx + 7, fy, 8.6, 7.8, c("skn_d"), dxs=-1, dys=-1.5, width=2)
    cv.ellipse(cx + 5, fy - 2, 3.4, 3.0, c("skn_l"))
    # Nase: sitzt tiefer als das Auge und ueberlappt die Wange,
    # sonst liest sich das Profil als Schnabel.
    cv.ellipse(cx + 13.5, fy + 2.0, 2.8, 2.2, c("skn_m"))
    cv.ellipse(cx + 13.0, fy + 1.4, 1.6, 1.1, c("skn_l"))
    cv.set(int(cx) + 15, int(fy) + 3, c("skn_d"))
    # Mundlinie
    cv.line(int(cx) + 9, int(fy) + 5, int(cx) + 12, int(fy) + 5, c("skn_d"))

    # Nur ein Auge -- das macht die Seitenansicht eindeutig
    cv.ellipse(cx + 7, fy - 2, 3.8, 4.8, c("wht"))
    cv.ellipse(cx + 8.4, fy - 1.6, 2.2, 3.0, c("outline"))
    cv.set(int(cx) + 7, int(fy) - 4, c("wht"))
    return _finish(cv)


def player_left(frame):
    return player_side(frame).flipped_h()


def player_right(frame):
    return player_side(frame)


DIRECTIONS = {
    "down": player_down,
    "up": player_up,
    "left": player_left,
    "right": player_right,
}
