"""Bombe (Pulsieren + Zuendschnur) und Explosion (Kern, Arme, Spitzen).

Die Explosion ist in Teile zerlegt, damit die Engine beliebig lange
Feuerbalken aus denselben 64x64-Kacheln zusammensetzen kann:
    expl_center | expl_arm_h | expl_tip_right   usw.
"""

import math
from pixelart import Canvas, c, mix


BOMB_FRAMES = 4
EXPL_FRAMES = 5

# Skalierung und Deckkraft ueber die Explosionsdauer
EXPL_SCALE = [0.50, 0.88, 1.00, 0.82, 0.52]
EXPL_ALPHA = [255, 255, 255, 220, 150]

# Aussen nach innen: rot -> orange -> gelb -> weisser Kern
FIRE_LAYERS = [("fir_r", 1.00), ("fir_o", 0.80), ("fir_y", 0.56), ("fir_w", 0.30)]


# -------------------------------------------------------------------- Bombe --

def bomb(frame):
    """Pulsierende Bombe. frame 0..3, Schnur brennt sichtbar ab."""
    cv = Canvas()
    pulse = [1.00, 1.07, 1.00, 0.94][frame % BOMB_FRAMES]
    r = 19.0 * pulse
    cy = 40 - (r - 19.0) * 0.5

    cv.ground_shadow(32, 59, 17, 3.5)

    # Koerper
    cv.circle(32, cy, r, c("bmb_m"))
    cv.ellipse_arc_band(32, cy, r, r, c("bmb_d"), dxs=-2.0, dys=-2.5, width=3)
    cv.ellipse(32 - r * 0.22, cy - r * 0.26, r * 0.60, r * 0.58, c("bmb_l"))
    # Zwei Glanzlichter -- lesen sich als glatte Metallkugel
    cv.ellipse(32 - r * 0.42, cy - r * 0.44, r * 0.20, r * 0.15, c("bmb_xl"))
    cv.ellipse(32 - r * 0.30, cy - r * 0.50, r * 0.09, r * 0.07, c("wht"))
    # Reflex vom Boden unten rechts
    cv.ellipse(32 + r * 0.34, cy + r * 0.50, r * 0.26, r * 0.12, c("bmb_l"))

    # Zuendkappe
    cap_y = int(cy - r) - 2
    cv.rect(28, cap_y - 3, 36, cap_y + 3, c("gry_d"))
    cv.rect(28, cap_y - 3, 36, cap_y - 2, c("gry_l"))
    cv.rect(28, cap_y + 2, 36, cap_y + 3, c("outline2"))
    cv.rect(28, cap_y - 3, 29, cap_y + 3, c("gry_m"))

    # Zuendschnur: wird von Frame zu Frame kuerzer
    burn = frame % BOMB_FRAMES
    length = 13 - burn
    px, py = 33, cap_y - 4
    pts = []
    for i in range(length):
        px += 1 if i % 2 == 0 else 0
        py -= 1
        pts.append((px + int(1.5 * math.sin(i * 0.7)), py))
    for i, (x, y) in enumerate(pts):
        cv.set(x, y, c("wd_d"))
        cv.set(x + 1, y, c("wd_m"))

    # Funke am Ende
    if pts:
        sx, sy = pts[-1]
        size = [3.4, 4.6, 3.8, 5.2][frame % BOMB_FRAMES]
        cv.circle(sx + 1, sy - 1, size, c("fir_o"))
        cv.circle(sx + 1, sy - 1, size * 0.62, c("fir_y"))
        cv.circle(sx + 1, sy - 1, size * 0.30, c("fir_w"))
        for ang in range(0, 360, 45):
            a = math.radians(ang + frame * 22)
            ex = sx + 1 + math.cos(a) * (size + 2.5)
            ey = sy - 1 + math.sin(a) * (size + 2.5)
            cv.set(int(ex), int(ey), c("fir_y"))

    cv.outline(c("outline"))
    return cv


# ---------------------------------------------------------------- Explosion --
#
# Wichtig fuer den Look: die Farbschichten werden AUSSEN NACH INNEN ueber die
# gesamte Form gezogen, nicht pro Teilblase. Sonst bekommt jede Blase einen
# eigenen weissen Kern und das Ganze sieht aus wie eine Blumenwiese statt wie
# ein Feuerball.

def _render_fire(cv, alpha, inside):
    """inside(x, y, scale) -> bool. Zeichnet rot, orange, gelb, weiss."""
    for name, scale in FIRE_LAYERS:
        col = c(name, alpha)
        for y in range(64):
            for x in range(64):
                if inside(x + 0.5, y + 0.5, scale):
                    cv.set(x, y, col)


def _blob_union(blobs, wobble=0.11):
    """blobs: Liste (cx, cy, r, lobes, phase) -> inside-Funktion."""
    def inside(x, y, scale):
        for bx, by, br, lobes, ph in blobs:
            dx, dy = x - bx, y - by
            d = math.hypot(dx, dy)
            r = br * scale
            if d > r * (1 + wobble):
                continue
            ang = math.atan2(dy, dx)
            if d <= r * (1.0 + wobble * math.sin(ang * lobes + ph)):
                return True
        return False
    return inside


def _beam_inside(thickness, frame, ripple=0.10):
    """Waagerechter Balken. Jede Farbschicht bekommt eine eigene Welle,
    damit die Raender flackern statt wie ein Farbverlauf zu wirken."""
    def inside(x, y, scale):
        base = thickness(x)
        if base <= 0:
            return False
        # Phase haengt an der Schicht (ueber scale) -> Baender wogen gegeneinander
        wave = 1.0 + ripple * math.sin(x / 64.0 * 2 * math.pi * 2
                                       + frame * 0.9 + scale * 6.0)
        return abs(y - 32) <= base * scale * wave
    return inside


def expl_arm_h(frame):
    """Mittelstueck, waagerecht. Die Welle hat volle Perioden ueber 64px,
    damit mehrere Kacheln nahtlos aneinanderpassen."""
    cv = Canvas()
    s = EXPL_SCALE[frame % EXPL_FRAMES]
    a = EXPL_ALPHA[frame % EXPL_FRAMES]
    _render_fire(cv, a, _beam_inside(lambda x: 22 * s, frame))
    return cv


def expl_arm_v(frame):
    return _rot90(expl_arm_h(frame))


def expl_center(frame):
    """Kreuzungspunkt. Enthaelt beide Balken in voller Staerke plus einen
    dickeren Feuerball -- sonst schnuert die Mitte die Arme ein."""
    cv = Canvas()
    s = EXPL_SCALE[frame % EXPL_FRAMES]
    a = EXPL_ALPHA[frame % EXPL_FRAMES]
    ball = _blob_union([(32, 32, 30 * s, 5, frame * 1.3)], wobble=0.10)
    beam_h = _beam_inside(lambda x: 22 * s, frame)

    def inside(x, y, scale):
        # beam_v ist beam_h mit vertauschten Achsen
        return (ball(x, y, scale)
                or beam_h(x, y, scale)
                or beam_h(y, x, scale))

    _render_fire(cv, a, inside)
    return cv


def expl_tip_right(frame):
    """Auslaufendes Ende des Feuerbalkens, zeigt nach rechts."""
    cv = Canvas()
    s = EXPL_SCALE[frame % EXPL_FRAMES]
    a = EXPL_ALPHA[frame % EXPL_FRAMES]
    tip_x = 24 + 34 * s

    def th(x):
        if x > tip_x:
            return 0.0
        taper = tip_x - 24 * s
        if x <= taper:
            return 22 * s
        t = (x - taper) / max(1e-6, tip_x - taper)
        return 22 * s * math.sqrt(max(0.0, 1.0 - t * t))

    beam = _beam_inside(th, frame)
    # Zuengelnde Flammen an der Spitze -- als Teil derselben Schichtfolge
    licks = [(tip_x - 2, 32 + math.sin(frame * 1.4) * 4, 9 * s, 5, frame),
             (tip_x + 4, 32 + math.sin(frame * 1.4 + 2.0) * 7, 6 * s, 4, frame + 1),
             (tip_x + 8, 32 + math.sin(frame * 1.4 + 4.0) * 3, 4 * s, 4, frame + 2)]
    lick = _blob_union(licks, wobble=0.18)

    def inside(x, y, scale):
        return beam(x, y, scale) or lick(x, y, scale)

    _render_fire(cv, a, inside)
    return cv


def _rot90(cv_in, turns=1):
    from PIL import Image
    out = Canvas()
    img = cv_in.img
    for _ in range(turns % 4):
        img = img.transpose(Image.ROTATE_270)   # im Uhrzeigersinn
    out.img = img.copy()
    out.px = out.img.load()
    return out


def expl_tip_left(frame):
    return expl_tip_right(frame).flipped_h()


def expl_tip_down(frame):
    return _rot90(expl_tip_right(frame), 1)


def expl_tip_up(frame):
    return _rot90(expl_tip_right(frame), 3)


EXPLOSION_PARTS = {
    "expl_center": expl_center,
    "expl_arm_h": expl_arm_h,
    "expl_arm_v": expl_arm_v,
    "expl_tip_right": expl_tip_right,
    "expl_tip_left": expl_tip_left,
    "expl_tip_up": expl_tip_up,
    "expl_tip_down": expl_tip_down,
}
