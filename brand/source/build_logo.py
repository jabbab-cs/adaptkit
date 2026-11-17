"""Build every AdaptKit logo file from one geometry definition.

    python -I brand/source/build_logo.py          (from the adaptkit folder)

Needs fontTools and the Manrope variable font (SIL Open Font License) at
workspace/fonts/Manrope-wght.ttf. The wordmark is converted to outlines, so the
finished SVGs contain no live text and need no font to display.
"""

import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

BRAND = Path(__file__).resolve().parents[1]
KIT = BRAND.parent
FONT = KIT / "workspace" / "fonts" / "Manrope-wght.ttf"

INK = "#0F1B2D"
GROW = "#0FA37F"
GROW_LIGHT = "#34D5A6"
PAPER = "#F7F7F2"
WHITE = "#FFFFFF"

WEIGHT = 760
TRACKING = -0.02   # of the font size
TAGLINE = "Interfaces that adapt to the person using them."

# --- the mark: a 3 x 3 kit grid (56 px tiles, 16 px gaps) where one piece has grown to 2 x 2 ---
TILE, GAP, R_SMALL, R_BIG = 56, 16, 13, 29
SMALL = [(0, 0), (0, 1), (0, 2), (1, 2), (2, 2)]          # (column, row)
BIG = (1, 0)                                              # top-left cell of the 2 x 2 tile
MARK = 3 * TILE + 2 * GAP                                 # 200


def rrect(x, y, w, h, r):
    return (f"M{x + r} {y}H{x + w - r}A{r} {r} 0 0 1 {x + w} {y + r}V{y + h - r}A{r} {r} 0 0 1 {x + w - r} {y + h}"
            f"H{x + r}A{r} {r} 0 0 1 {x} {y + h - r}V{y + r}A{r} {r} 0 0 1 {x + r} {y}Z")


def mark_paths(ox=0.0, oy=0.0, scale=1.0, small_tiles=SMALL, gap=GAP):
    """(small tiles path, big tile path) for a mark drawn at (ox, oy), MARK * scale wide."""
    s = scale
    step = (TILE + gap)
    smalls = "".join(rrect(round(ox + c * step * s, 2), round(oy + r * step * s, 2), round(TILE * s, 2), round(TILE * s, 2), round(R_SMALL * s, 2))
                     for c, r in small_tiles)
    big_size = 2 * TILE + gap
    c, r = BIG
    big = rrect(round(ox + c * step * s, 2), round(oy + r * step * s, 2), round(big_size * s, 2), round(big_size * s, 2), round(R_BIG * s, 2))
    return smalls, big


_FONT = None


def font():
    global _FONT
    if _FONT is None:
        f = TTFont(FONT)
        _FONT = instancer.instantiateVariableFont(f, {"wght": WEIGHT})
    return _FONT


def text_path(text, size, x, baseline, tracking=TRACKING):
    """Outlines of `text` at font size `size` (px), left edge x, on baseline. Returns (path d, width, cap height)."""
    f = font()
    upm = f["head"].unitsPerEm
    gs = f.getGlyphSet()
    cmap = f.getBestCmap()
    hmtx = f["hmtx"]
    k = size / upm
    pen = SVGPathPen(gs)
    cursor = 0.0
    for i, ch in enumerate(text):
        name = cmap[ord(ch)]
        tp = TransformPen(pen, (k, 0, 0, -k, x + cursor * k, baseline))
        gs[name].draw(tp)
        cursor += hmtx[name][0] + (tracking * upm if i < len(text) - 1 else 0)
    cap = f["OS/2"].sCapHeight * k
    return pen.getCommands(), cursor * k, cap


def svg(w, h, body, title="AdaptKit"):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {round(w, 2)} {round(h, 2)}" role="img" aria-label="{title}">\n'
            f"<title>{title}</title>\n{body}</svg>\n")


def write(name, content):
    (BRAND / name).write_text(content, encoding="utf-8")
    print("wrote brand/" + name)


def mark_file(small_colour, big_colour, pad=28, small_tiles=SMALL, gap=GAP, title="AdaptKit mark"):
    smalls, big = mark_paths(pad, pad, 1.0, small_tiles, gap)
    size = MARK + 2 * pad
    return svg(size, size, f'<path fill="{small_colour}" d="{smalls}"/>\n<path fill="{big_colour}" d="{big}"/>\n', title)


def horizontal(small_colour, big_colour, word_colour, bg=None):
    cap_target = MARK * 0.55
    probe_d, probe_w, probe_cap = text_path("AdaptKit", 100, 0, 0)
    size = 100 * cap_target / probe_cap
    baseline = (MARK + cap_target) / 2
    x_word = MARK + TILE
    d, width, _ = text_path("AdaptKit", size, x_word, baseline)
    smalls, big = mark_paths()
    w = x_word + width
    back = f'<rect width="{round(w, 2)}" height="{MARK}" fill="{bg}"/>\n' if bg else ""
    body = back + f'<path fill="{small_colour}" d="{smalls}"/>\n<path fill="{big_colour}" d="{big}"/>\n<path fill="{word_colour}" d="{d}"/>\n'
    return svg(w, MARK, body, "AdaptKit")


def stacked(small_colour, big_colour, word_colour):
    cap_target = MARK * 0.36
    _, _, probe_cap = text_path("AdaptKit", 100, 0, 0)
    size = 100 * cap_target / probe_cap
    _, width, _ = text_path("AdaptKit", size, 0, 0)
    w = max(width, MARK)
    gap = TILE * 0.85
    baseline = MARK + gap + cap_target
    d, _, _ = text_path("AdaptKit", size, (w - width) / 2, baseline)
    smalls, big = mark_paths((w - MARK) / 2, 0)
    body = f'<path fill="{small_colour}" d="{smalls}"/>\n<path fill="{big_colour}" d="{big}"/>\n<path fill="{word_colour}" d="{d}"/>\n'
    return svg(w, baseline + 8, body, "AdaptKit")


def wordmark(colour):
    _, _, probe_cap = text_path("AdaptKit", 100, 0, 0)
    size = 100 * 110 / probe_cap
    d, width, cap = text_path("AdaptKit", size, 0, 110)
    return svg(width, 140, f'<path fill="{colour}" d="{d}"/>\n', "AdaptKit")


def social_preview():
    """1280 x 640 card for the GitHub repository and link previews."""
    W, H, left, top = 1280, 640, 120, 130
    scale = 1.0
    mark_size = MARK * scale
    smalls, big = mark_paths(left, top, scale)
    _, _, probe_cap = text_path("AdaptKit", 100, 0, 0)
    cap = mark_size * 0.55
    d, width, _ = text_path("AdaptKit", 100 * cap / probe_cap, left + mark_size + TILE, top + (mark_size + cap) / 2)
    t_d, t_w, _ = text_path(TAGLINE, 100 * 30 / probe_cap, left, top + mark_size + 96, tracking=0)
    meta_d, _, _ = text_path("Open-source adaptive UI for the web  ·  MIT licence", 100 * 18 / probe_cap, left, H - 64, tracking=0)
    body = (f'<rect width="{W}" height="{H}" fill="{PAPER}"/>\n'
            f'<path fill="{INK}" d="{smalls}"/>\n<path fill="{GROW}" d="{big}"/>\n'
            f'<path fill="{INK}" d="{d}"/>\n<path fill="#52514E" d="{t_d}"/>\n<path fill="#8A8A80" d="{meta_d}"/>\n')
    return svg(W, H, body, "AdaptKit: interfaces that adapt to the person using them")


def app_icon(maskable=False):
    """Two-colour app icon: the dark-background mark on an Ink tile.

    maskable = full-bleed square with the mark inside the 80% safe zone (Android adaptive icons).
    """
    size = 256
    scale = 0.5 if maskable else 0.6
    off = (size - MARK * scale) / 2
    smalls, big = mark_paths(off, off, scale)
    tile = f'<rect width="{size}" height="{size}" fill="{INK}"/>' if maskable else f'<rect width="{size}" height="{size}" rx="56" fill="{INK}"/>'
    return svg(size, size, f'{tile}\n<path fill="{WHITE}" d="{smalls}"/>\n<path fill="{GROW_LIGHT}" d="{big}"/>\n', "AdaptKit app icon")


def main():
    if not FONT.exists():
        sys.exit(f"Missing font: {FONT}\nDownload Manrope[wght].ttf from https://github.com/google/fonts/tree/main/ofl/manrope")
    write("adaptkit-mark.svg", mark_file(INK, GROW))
    write("adaptkit-mark-dark.svg", mark_file(WHITE, GROW_LIGHT, title="AdaptKit mark (for dark backgrounds)"))
    write("adaptkit-mark-black.svg", mark_file("#000000", "#000000"))
    write("adaptkit-mark-white.svg", mark_file(WHITE, WHITE))
    # small-size cut: fewer tiles, wider gaps, for 16-24 px (favicon)
    write("adaptkit-mark-small.svg", mark_file(INK, GROW, pad=16, small_tiles=[(0, 0), (0, 2), (2, 2)], gap=22, title="AdaptKit mark, small sizes"))
    write("adaptkit-logo.svg", horizontal(INK, GROW, INK))
    write("adaptkit-logo-dark.svg", horizontal(WHITE, GROW_LIGHT, WHITE))
    write("adaptkit-logo-black.svg", horizontal("#000000", "#000000", "#000000"))
    write("adaptkit-logo-white.svg", horizontal(WHITE, WHITE, WHITE))
    write("adaptkit-logo-stacked.svg", stacked(INK, GROW, INK))
    write("adaptkit-wordmark.svg", wordmark(INK))
    write("social-preview.svg", social_preview())
    write("icons/adaptkit-app-icon.svg", app_icon())
    write("icons/adaptkit-app-icon-maskable.svg", app_icon(maskable=True))


if __name__ == "__main__":
    main()
