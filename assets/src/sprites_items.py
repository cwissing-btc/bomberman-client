"""Power-ups: gemeinsame Kapsel als Traeger, darauf je ein Symbol.

Alle Items teilen sich Silhouette und Rahmen -- so erkennt der Spieler auf
einen Blick "das ist ein Item", und die Farbe sagt, welches.
Jedes Item hat 2 Frames (schwebt leicht auf und ab).
"""

import math
from pixelart import Canvas, c, mix

ITEM_FRAMES = 2


def _round_rect(cv, x0, y0, x1, y1, r, color):
    cv.rect(x0 + r, y0, x1 - r, y1, color)
    cv.rect(x0, y0 + r, x1, y1 - r, color)
    for cx, cy in ((x0 + r, y0 + r), (x1 - r, y0 + r),
                   (x0 + r, y1 - r), (x1 - r, y1 - r)):
        cv.circle(cx + 0.5, cy + 0.5, r + 0.5, color)


def _capsule(cv, dark, mid, light, top):
    """Kapsel mit Fase: 44x44, zentriert, sitzt auf y=top."""
    x0, x1 = 10, 53
    y0, y1 = top, top + 43
    _round_rect(cv, x0 - 1, y0 - 1, x1 + 1, y1 + 1, 9, c("outline"))
    _round_rect(cv, x0, y0, x1, y1, 8, c(mid))
    # Lichtkante oben links, Schattenkante unten rechts
    _round_rect(cv, x0 + 1, y0 + 1, x1 - 1, y1 - 1, 7, c(light))
    _round_rect(cv, x0 + 2, y0 + 3, x1 - 1, y1 - 1, 7, c(mid))
    _round_rect(cv, x0 + 4, y0 + 6, x1 - 2, y1 - 2, 6, c(dark))
    _round_rect(cv, x0 + 5, y0 + 6, x1 - 4, y1 - 5, 5, c(mid))
    # Glanzstreifen
    cv.ellipse(24, y0 + 8, 8.5, 3.2, c(light))
    cv.ellipse(22, y0 + 7, 5.0, 1.8, c("wht"))


def _icon_bomb(cv, cy):
    cv.circle(32, cy + 3, 10.0, c("bmb_d"))
    cv.ellipse(28.5, cy - 0.5, 5.2, 4.6, c("bmb_l"))
    cv.ellipse(27, cy - 2, 2.4, 1.8, c("wht"))
    cv.rect(30, cy - 10, 34, cy - 6, c("gry_d"))
    cv.rect(30, cy - 10, 34, cy - 10, c("gry_l"))
    cv.line(33, cy - 11, 37, cy - 15, c("wd_m"))
    cv.circle(38, cy - 16, 2.6, c("fir_y"))
    cv.circle(38, cy - 16, 1.3, c("fir_w"))
    # Pluszeichen -> "mehr Bomben"
    cv.rect(38, cy + 4, 46, cy + 6, c("wht"))
    cv.rect(41, cy + 1, 43, cy + 9, c("wht"))


def _icon_fire(cv, cy):
    """Flamme: runder Bauch + spitze Zunge, drei Schichten uebereinander.
    Reine Polygone waren hier zu unruhig -- Ellipse plus Dreieck liest sich
    bei 64px eindeutig als Feuer."""
    shapes = [
        ("fir_r", 11.5, 9.5, 6, -17, 0.0),
        ("fir_o", 8.0, 6.8, 7, -10, 0.8),
        ("fir_y", 5.0, 4.4, 8, -4, 1.4),
    ]
    for col, rx, ry, by, tip_y, lean in shapes:
        cv.ellipse(32 + lean, cy + by, rx, ry, c(col))
        cv.poly([(32 - rx * 0.92 + lean, cy + by),
                 (32 + rx * 0.92 + lean, cy + by),
                 (32 + lean + 2.5, cy + tip_y)], c(col))
    cv.ellipse(30.5, cy + 9, 2.4, 3.0, c("fir_w"))


def _icon_speed(cv, cy):
    """Blitz als geschlossenes Polygon -- der Umriss ist bewusst breit,
    ein duenner Zickzack verschwindet bei 64px."""
    d = cy - 34
    bolt = [(34, 14 + d), (43, 14 + d), (35, 30 + d), (44, 30 + d),
            (24, 52 + d), (29, 36 + d), (21, 36 + d)]
    # Gelb auf Gruen -- ein gruener Blitz auf gruener Kapsel verschwindet
    cv.poly([(x + 2, y + 2) for x, y in bolt], c("grn_d"))
    cv.poly([(x - 1, y - 1) for x, y in bolt], c("outline"))
    cv.poly(bolt, c("fir_o"))
    cv.poly([(x + 0.5, y + 0.5) for x, y in bolt], c("fir_y"))
    cv.line(35, 18 + d, 28, 30 + d, c("fir_w"))


def _icon_kick(cv, cy):
    """Stiefel im Profil, der eine Bombe wegtritt."""
    # Schaft
    cv.rect(17, cy - 12, 28, cy + 4, c("pnk_m"))
    cv.rect(17, cy - 12, 19, cy + 4, c("pnk_l"))
    cv.ellipse(22.5, cy - 12, 5.8, 2.4, c("pnk_l"))       # Schaftrand
    cv.rect(17, cy - 8, 28, cy - 7, c("pnk_d"))
    # Fuss mit runder Spitze
    cv.rect(17, cy + 2, 36, cy + 11, c("pnk_m"))
    cv.ellipse(36, cy + 7, 5.0, 4.6, c("pnk_m"))
    cv.ellipse(24, cy + 4, 6.0, 2.0, c("pnk_l"))
    # Sohle
    cv.rect(16, cy + 11, 38, cy + 14, c("gry_l"))
    cv.rect(16, cy + 13, 38, cy + 14, c("gry_m"))
    # Getretene Bombe
    cv.circle(47, cy + 1, 6.6, c("bmb_d"))
    cv.ellipse(44.8, cy - 1.4, 3.2, 2.8, c("bmb_l"))
    cv.rect(46, cy - 9, 49, cy - 6, c("gry_d"))
    # Bewegungslinien
    for i, ly in enumerate((cy - 6, cy + 1, cy + 8)):
        cv.rect(54 - i % 2, ly, 58 - i % 2, ly + 1, c("wht"))


def _icon_remote(cv, cy):
    """Zuendkasten: dunkles Gehaeuse, damit er sich von der Kapsel abhebt."""
    cv.rect(21, cy - 2, 45, cy + 14, c("outline"))
    cv.rect(22, cy - 1, 44, cy + 13, c("gry_d"))
    cv.rect(22, cy - 1, 44, cy, c("gry_m"))
    cv.rect(22, cy - 1, 23, cy + 13, c("gry_m"))
    cv.rect(23, cy + 12, 44, cy + 13, c("outline2"))
    # Display
    cv.rect(26, cy + 4, 40, cy + 10, c("outline"))
    cv.rect(27, cy + 5, 39, cy + 8, c("fir_y"))
    cv.rect(27, cy + 5, 39, cy + 5, c("fir_w"))
    # Kolben
    cv.rect(31, cy - 8, 35, cy - 2, c("gry_l"))
    cv.rect(31, cy - 8, 32, cy - 2, c("wht"))
    cv.rect(26, cy - 12, 40, cy - 8, c("pnk_m"))
    cv.rect(26, cy - 12, 40, cy - 11, c("pnk_l"))
    cv.rect(26, cy - 9, 40, cy - 8, c("pnk_d"))
    # Antenne mit Funkwellen
    cv.line(44, cy - 2, 49, cy - 13, c("gry_l"))
    cv.circle(49, cy - 14, 1.8, c("pnk_l"))
    for r in (6, 10, 14):
        for a in range(-72, 6, 5):
            rad = math.radians(a)
            cv.set(int(49 + math.cos(rad) * r), int(cy - 14 + math.sin(rad) * r),
                   c("wht"))


ITEM_DEFS = {
    "item_bomb_up":  (("blu_d", "blu_m", "blu_l"), _icon_bomb),
    "item_fire_up":  (("fir_dr", "fir_r", "fir_o"), _icon_fire),
    "item_speed_up": (("grn_d", "grn_m", "grn_l"), _icon_speed),
    "item_kick":     (("gry_d", "gry_m", "gry_l"), _icon_kick),
    "item_remote":   (("pur_d", "pur_m", "pur_l"), _icon_remote),
}


def item(name, frame=0):
    """Ein Power-up. frame 0/1 laesst es leicht schweben."""
    dark, mid, light = ITEM_DEFS[name][0]
    icon = ITEM_DEFS[name][1]
    hover = [0, -2][frame % ITEM_FRAMES]

    cv = Canvas()
    # Schatten bleibt am Boden und wird beim Schweben kleiner
    cv.ground_shadow(32, 60, 17 + hover, 4 + hover * 0.5)

    top = 12 + hover
    _capsule(cv, dark, mid, light, top)
    icon(cv, top + 22)
    cv.outline(c("outline"))
    return cv


ITEM_NAMES = list(ITEM_DEFS.keys())
