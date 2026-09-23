"""
Kleines Pixel-Art-Framework fuer 64x64-Sprites.

Kernidee: alles wird direkt im Zielraster gezeichnet, ohne Anti-Aliasing.
Jede Zeichenfunktion arbeitet auf einem PixelAccess-Objekt, damit die
Kanten exakt so hart bleiben, wie Pixel-Art sie braucht.
"""

from PIL import Image

SIZE = 64
TRANSPARENT = (0, 0, 0, 0)


# ---------------------------------------------------------------- Palette ---
# Bewusst klein gehalten: jede Materialgruppe hat 3-4 Stufen
# (D = dark / Schatten, M = mid / Grundton, L = light, XL = Glanzlicht).

P = {
    "outline":  (24, 20, 36),
    "outline2": (40, 34, 56),
    "shadow":   (18, 16, 28, 90),      # halbtransparenter Bodenschatten

    # Spieler: blauer Anzug
    "blu_d":  (30, 58, 124),
    "blu_m":  (50, 100, 190),
    "blu_l":  (92, 154, 236),
    "blu_xl": (170, 214, 255),

    # Haut / Gesicht
    "skn_d":  (196, 124, 92),
    "skn_m":  (240, 176, 134),
    "skn_l":  (255, 216, 180),

    # Weiss / Metall
    "wht":   (246, 249, 255),
    "gry_l": (198, 208, 226),
    "gry_m": (134, 146, 172),
    "gry_d": (82, 92, 118),

    # Akzent Magenta (Schuhe, Details)
    "pnk_d": (166, 38, 88),
    "pnk_m": (226, 72, 126),
    "pnk_l": (255, 136, 178),

    # Bombe
    "bmb_d": (26, 26, 42),
    "bmb_m": (54, 56, 82),
    "bmb_l": (94, 98, 130),
    "bmb_xl": (150, 156, 190),

    # Feuer
    "fir_w":  (255, 252, 226),
    "fir_y":  (255, 214, 82),
    "fir_o":  (255, 142, 42),
    "fir_r":  (228, 62, 44),
    "fir_dr": (148, 32, 40),

    # Holzkiste
    "wd_d":  (100, 58, 32),
    "wd_m":  (148, 92, 48),
    "wd_l":  (190, 130, 72),
    "wd_xl": (222, 172, 112),

    # Steinwand
    "st_d":  (64, 70, 92),
    "st_m":  (102, 110, 136),
    "st_l":  (144, 154, 182),
    "st_xl": (188, 198, 220),

    # Boden
    "fl_d": (42, 76, 62),
    "fl_m": (58, 98, 78),
    "fl_l": (74, 118, 94),

    # Gruen (Speed)
    "grn_d": (32, 114, 70),
    "grn_m": (60, 172, 104),
    "grn_l": (124, 226, 156),

    # Violett (Fernzuender)
    "pur_d": (84, 42, 130),
    "pur_m": (132, 76, 194),
    "pur_l": (186, 140, 240),
}


def c(name, alpha=255):
    """Palettenfarbe als RGBA holen."""
    v = P[name]
    if len(v) == 4:
        return v
    return (v[0], v[1], v[2], alpha)


def mix(a, b, t):
    """Zwei Palettenfarben linear mischen (t=0 -> a, t=1 -> b)."""
    ca, cb = c(a), c(b)
    return tuple(int(round(ca[i] + (cb[i] - ca[i]) * t)) for i in range(4))


# ------------------------------------------------------------------ Canvas ---

class Canvas:
    """64x64-Zeichenflaeche mit direktem Pixelzugriff."""

    def __init__(self, size=SIZE):
        self.size = size
        self.img = Image.new("RGBA", (size, size), TRANSPARENT)
        self.px = self.img.load()

    # -- Grundoperationen --------------------------------------------------
    def set(self, x, y, color):
        if 0 <= x < self.size and 0 <= y < self.size and color is not None:
            if len(color) == 4 and color[3] < 255:
                self._blend(x, y, color)
            else:
                self.px[x, y] = color

    def _blend(self, x, y, color):
        dst = self.px[x, y]
        a = color[3] / 255.0
        if dst[3] == 0:
            self.px[x, y] = color
            return
        self.px[x, y] = (
            int(round(color[0] * a + dst[0] * (1 - a))),
            int(round(color[1] * a + dst[1] * (1 - a))),
            int(round(color[2] * a + dst[2] * (1 - a))),
            max(dst[3], color[3]),
        )

    def get(self, x, y):
        if 0 <= x < self.size and 0 <= y < self.size:
            return self.px[x, y]
        return TRANSPARENT

    def opaque(self, x, y):
        return self.get(x, y)[3] > 0

    # -- Formen ------------------------------------------------------------
    def rect(self, x0, y0, x1, y1, color):
        """Gefuelltes Rechteck, Koordinaten inklusiv."""
        for y in range(min(y0, y1), max(y0, y1) + 1):
            for x in range(min(x0, x1), max(x0, x1) + 1):
                self.set(x, y, color)

    def frame(self, x0, y0, x1, y1, color):
        """Rechteck-Umriss, 1px."""
        for x in range(x0, x1 + 1):
            self.set(x, y0, color)
            self.set(x, y1, color)
        for y in range(y0, y1 + 1):
            self.set(x0, y, color)
            self.set(x1, y, color)

    def ellipse(self, cx, cy, rx, ry, color):
        """Gefuellte Ellipse ohne Anti-Aliasing. cx/cy duerfen .5 sein."""
        if rx <= 0 or ry <= 0:
            return
        for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
            for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
                dx = (x + 0.5 - cx) / rx
                dy = (y + 0.5 - cy) / ry
                if dx * dx + dy * dy <= 1.0:
                    self.set(x, y, color)

    def circle(self, cx, cy, r, color):
        self.ellipse(cx, cy, r, r, color)

    def ellipse_arc_band(self, cx, cy, rx, ry, color, dxs, dys, width=2):
        """Sichelfoermiger Rand einer Ellipse -- fuer Schattenkanten.

        dxs/dys geben die Richtung an, in die der Band-Rand verschoben wird.
        """
        inner_rx = rx - width
        inner_ry = ry - width
        for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
            for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
                dx = (x + 0.5 - cx) / rx
                dy = (y + 0.5 - cy) / ry
                if dx * dx + dy * dy > 1.0:
                    continue
                if inner_rx <= 0 or inner_ry <= 0:
                    self.set(x, y, color)
                    continue
                ix = (x + 0.5 - cx - dxs) / inner_rx
                iy = (y + 0.5 - cy - dys) / inner_ry
                if ix * ix + iy * iy > 1.0:
                    self.set(x, y, color)

    def line(self, x0, y0, x1, y1, color):
        """Bresenham -- harte 1px-Linie."""
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.set(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def poly(self, points, color):
        """Gefuelltes Polygon per Scanline."""
        if len(points) < 3:
            return
        ys = [p[1] for p in points]
        for y in range(int(min(ys)), int(max(ys)) + 1):
            xs = []
            n = len(points)
            for i in range(n):
                x0, y0 = points[i]
                x1, y1 = points[(i + 1) % n]
                if y0 == y1:
                    continue
                if min(y0, y1) <= y + 0.5 < max(y0, y1):
                    t = (y + 0.5 - y0) / (y1 - y0)
                    xs.append(x0 + t * (x1 - x0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                for x in range(int(round(xs[i])), int(round(xs[i + 1]))):
                    self.set(x, y, color)

    # -- Effekte -----------------------------------------------------------
    def outline(self, color=None, diagonal=True):
        """Dunkle Kontur AUSSEN um die Silhouette legen.

        Aussen statt innen, damit die Form ihre Masse behaelt.
        """
        if color is None:
            color = c("outline")
        targets = []
        offs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        if diagonal:
            offs += [(-1, -1), (1, -1), (-1, 1), (1, 1)]
        for y in range(self.size):
            for x in range(self.size):
                if self.opaque(x, y):
                    continue
                for ox, oy in offs:
                    if self.opaque(x + ox, y + oy):
                        targets.append((x, y))
                        break
        for x, y in targets:
            self.px[x, y] = color

    def shade_bottom(self, amount=0.22, start=0.55):
        """Untere Sprite-Haelfte sanft abdunkeln -- billiges Volumen."""
        cols = {}
        for x in range(self.size):
            ys = [y for y in range(self.size) if self.opaque(x, y)]
            if ys:
                cols[x] = (min(ys), max(ys))
        for x, (top, bot) in cols.items():
            h = max(1, bot - top)
            for y in range(top, bot + 1):
                t = (y - top) / h
                if t < start:
                    continue
                k = (t - start) / (1 - start) * amount
                r, g, b, a = self.px[x, y]
                self.px[x, y] = (
                    int(r * (1 - k)), int(g * (1 - k)), int(b * (1 - k)), a
                )

    def snap_to_palette(self):
        """Volldeckende Pixel auf die naechste Palettenfarbe ziehen.

        shade_bottom() rechnet mit Fliesskomma und erzeugt dabei hunderte
        Zwischentoene -- fuer Pixel-Art ist das genau falsch. Nach dem
        Snappen hat jedes Sprite wieder nur Farben aus P.
        """
        pal = []
        for v in P.values():
            if len(v) == 3:
                pal.append(v)
        cache = {}
        for y in range(self.size):
            for x in range(self.size):
                r, g, b, a = self.px[x, y]
                if a != 255:
                    continue
                key = (r, g, b)
                hit = cache.get(key)
                if hit is None:
                    hit = min(pal, key=lambda p: (p[0] - r) ** 2
                              + (p[1] - g) ** 2 + (p[2] - b) ** 2)
                    cache[key] = hit
                self.px[x, y] = (hit[0], hit[1], hit[2], 255)

    def ground_shadow(self, cx, cy, rx, ry):
        """Weicher Ellipsenschatten UNTER dem Sprite (zeichnet zuerst)."""
        base = Canvas(self.size)
        base.ellipse(cx, cy, rx, ry, c("shadow"))
        base.img.alpha_composite(self.img)
        self.img = base.img
        self.px = self.img.load()

    def paste(self, other, ox=0, oy=0):
        self.img.alpha_composite(other.img, (ox, oy))
        self.px = self.img.load()

    def translated(self, dx, dy):
        out = Canvas(self.size)
        for y in range(self.size):
            for x in range(self.size):
                p = self.px[x, y]
                if p[3]:
                    out.set(x + dx, y + dy, p)
        return out

    def flipped_h(self):
        out = Canvas(self.size)
        out.img = self.img.transpose(Image.FLIP_LEFT_RIGHT)
        out.px = out.img.load()
        return out

    def save(self, path):
        self.img.save(path)


def tile_noise(canvas, x0, y0, x1, y1, color, seed, density=7):
    """Deterministisches Korn -- gleicher Seed, gleiches Muster."""
    s = seed
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            s = (s * 1103515245 + 12345) & 0x7FFFFFFF
            if (s >> 8) % density == 0:
                canvas.set(x, y, color)
