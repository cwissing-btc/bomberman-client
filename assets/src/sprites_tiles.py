"""Boden, solide Wand und zerstoerbare Kiste (inkl. Zerfalls-Frames)."""

from pixelart import Canvas, c, mix, tile_noise


def floor_tile(variant=0):
    """Nahtlos kachelbarer Boden. variant streut das Korn."""
    cv = Canvas()
    cv.rect(0, 0, 63, 63, c("fl_m"))

    # Sehr schwache Schachbrett-Struktur: gibt Bewegung, ohne zu flimmern
    soft = mix("fl_m", "fl_l", 0.45)
    for y in range(64):
        for x in range(64):
            if ((x // 16) + (y // 16)) % 2 == 0:
                cv.set(x, y, soft)

    tile_noise(cv, 0, 0, 63, 63, c("fl_d"), seed=1337 + variant * 91, density=19)
    tile_noise(cv, 0, 0, 63, 63, c("fl_l"), seed=8821 + variant * 57, density=29)

    # Fugen an zwei Kanten -> ergibt beim Kacheln ein feines Gitter
    for x in range(64):
        cv.set(x, 0, mix("fl_d", "fl_m", 0.25))
        cv.set(x, 63, mix("fl_d", "fl_m", 0.7))
    for y in range(64):
        cv.set(0, y, mix("fl_d", "fl_m", 0.25))
        cv.set(63, y, mix("fl_d", "fl_m", 0.7))
    return cv


def wall_solid():
    """Unzerstoerbarer Block: Steinquader mit Fase."""
    cv = Canvas()
    cv.rect(0, 0, 63, 63, c("st_m"))

    # Fase: hell oben/links, dunkel unten/rechts
    for i in range(4):
        t = i / 4
        top = mix("st_xl", "st_l", t)
        bot = mix("st_d", "st_m", t)
        for x in range(i, 64 - i):
            cv.set(x, i, top)
            cv.set(x, 63 - i, bot)
        for y in range(i, 64 - i):
            cv.set(i, y, top)
            cv.set(63 - i, y, bot)

    # Mauerwerk im Inneren: versetzte Quader
    inner = (6, 6, 57, 57)
    rows = [(6, 21), (22, 37), (38, 53)]
    for ri, (ry0, ry1) in enumerate(rows):
        offset = 0 if ri % 2 == 0 else 13
        cv.line(inner[0], ry1 + 1, inner[2], ry1 + 1, c("st_d"))
        cv.line(inner[0], ry1 + 2, inner[2], ry1 + 2, c("st_l"))
        x = inner[0] + offset
        while x < inner[2]:
            cv.line(x, ry0, x, ry1, c("st_d"))
            cv.line(x + 1, ry0, x + 1, ry1, c("st_l"))
            x += 26

    tile_noise(cv, 8, 8, 55, 55, c("st_d"), seed=4711, density=17)
    tile_noise(cv, 8, 8, 55, 55, c("st_l"), seed=99117, density=23)
    return cv


def _crate_body():
    cv = Canvas()
    cv.rect(2, 2, 61, 61, c("wd_m"))

    # Vertikale Bretter
    for bx in (2, 17, 32, 47):
        cv.line(bx + 14, 3, bx + 14, 60, c("wd_d"))
        cv.line(bx + 15, 3, bx + 15, 60, c("wd_l"))
    tile_noise(cv, 3, 3, 60, 60, c("wd_d"), seed=777, density=13)

    # Rahmen oben/unten (Querlatten)
    for y0, y1 in ((2, 10), (53, 61)):
        cv.rect(2, y0, 61, y1, c("wd_l"))
        cv.line(2, y0, 61, y0, c("wd_xl"))
        cv.line(2, y1, 61, y1, c("wd_d"))
        tile_noise(cv, 3, y0 + 1, 60, y1 - 1, c("wd_m"), seed=555 + y0, density=9)

    # Diagonalstrebe
    for i in range(52):
        x = 6 + i
        y = 55 - i
        for k in range(-3, 4):
            cv.set(x + k, y, c("wd_l") if k < 1 else c("wd_m"))
        cv.set(x - 4, y, c("wd_xl"))
        cv.set(x + 4, y, c("wd_d"))

    # Aeussere Kante
    cv.frame(2, 2, 61, 61, c("wd_d"))
    cv.frame(1, 1, 62, 62, mix("wd_d", "outline", 0.5))
    cv.frame(0, 0, 63, 63, c("outline"))

    # Nieten in den Ecken
    for nx, ny in ((7, 6), (56, 6), (7, 57), (56, 57)):
        cv.circle(nx + 0.5, ny + 0.5, 2.4, c("gry_m"))
        cv.circle(nx, ny, 1.2, c("gry_l"))
    return cv


def crate():
    return _crate_body()


def crate_break(step):
    """Zerfalls-Frames 0..3 -- Risse, dann Splitter, dann fast leer."""
    cv = _crate_body()
    if step == 0:
        # Erste Risse -- deutlich sichtbar, damit der Frame etwas erzaehlt
        for (ax, ay, bx, by) in ((22, 4, 28, 26), (28, 26, 23, 40),
                                 (23, 40, 29, 60), (44, 4, 39, 22),
                                 (39, 22, 45, 38), (10, 30, 24, 33)):
            cv.line(ax, ay, bx, by, c("outline"))
            cv.line(ax + 1, ay, bx + 1, by, c("wd_xl"))
        return cv

    # Ab Schritt 1: in grobe Bloecke zerlegen -- 8px lesen sich als Bretter,
    # feineres Raster wuerde bei 64px nur als Rauschen ankommen.
    BS = 8
    N = 64 // BS
    keep = Canvas()
    thresholds = {}
    s = 20250923
    for by in range(N):
        for bx in range(N):
            s = (s * 1103515245 + 12345) & 0x7FFFFFFF
            # Rand zerfaellt frueher als die Mitte
            dist = max(abs(bx - (N - 1) / 2), abs(by - (N - 1) / 2)) / ((N - 1) / 2)
            thresholds[(bx, by)] = ((s >> 9) % 1000) / 1000.0 * 0.45 + dist * 0.55

    survive = {1: 0.68, 2: 0.38, 3: 0.14}[step]
    drop = {1: 2, 2: 5, 3: 9}[step]

    for y in range(64):
        for x in range(64):
            p = cv.get(x, y)
            if not p[3]:
                continue
            key = (x // BS, y // BS)
            t = thresholds[key]
            if t > survive:
                continue
            # Lockere Bloecke sacken nach unten und driften auseinander
            loose = t > survive * 0.5
            dy = drop if loose else 0
            dx = (1 if key[0] >= N / 2 else -1) * (drop // 2 if loose else 0)
            keep.set(x + dx, y + dy, p)

    # Wegfliegende Splitter
    shards = [(12, 16, 3, -1, -1), (50, 18, 2, 1, -1), (16, 46, 2, -1, 1),
              (48, 44, 3, 1, 1), (32, 6, 2, 0, -1), (30, 56, 2, 0, 1)]
    for i, (sx, sy, sr, dx, dy) in enumerate(shards):
        push = step * 4 + i
        px_, py_ = sx + dx * push, sy + dy * push
        keep.rect(px_, py_, px_ + sr, py_ + sr, c("wd_m"))
        keep.rect(px_, py_, px_ + sr - 1, py_, c("wd_l"))
    keep.outline(c("outline"), diagonal=False)
    return keep
