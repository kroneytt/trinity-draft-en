"""
Trinity Draft: Singularity - English Hole cards and Singularity Reserve
=======================================================================

    pip install pillow pypdf
    python tools/render_holes.py --extract singularity-addition.pdf   cut the cards out of the official print sheet
    python tools/render_holes.py                                      overlay English on every Hole + the Reserve

Reads   cards/singularity_database.json            the Hole cards (source of truth, never rewritten)
        cards/singularity_cards_hq/<CardID>.png    the Japanese cards, cut from the print sheet by --extract
        images/components/reserve_card_en.jpg      the English Reserve Card (text style and layout)
Writes  out/tts/singularity/<CardID>.jpg           744x1039, the same format as the other TTS cards
        images/components/singularity_reserve_en.jpg

The print sheet (trinitydraft.com/singularity, "印刷PDFデータのダウンロード") is two A4 pages at 300 dpi,
3x3 cards each, with no gaps between the cards. The Hole art is only 744x1039, so the text is drawn
at 3x and scaled down.
"""
import json, os, sys
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_cards as rc
from card_data import HERE, segments

SRC = os.path.join(HERE, "cards", "singularity_cards_hq")
OUT = os.path.join(HERE, "out", "tts", "singularity")
COMP = os.path.join(HERE, "images", "components")
CARD_W, CARD_H = 744, 1039
SS = 3                                   # supersampling for the text

rc.TIMING.setdefault("On Reveal", (24, 142, 150))       # teal: not the green of [Activate]
HOLE_TINT = (176, 150, 236)                               # the lavender outline of the Hole frame

# Layout in the renderer's 859 x 1200 units (render_cards.REF_W / REF_H).
HOLE = dict(
    name=(110, 570, 750, 676), ruby_y=596, name_y=640,
    effect=(12, 694, 846, 1080),
    od_ruby=(624, 1088, 770, 1114),
)
GENESIS = dict(
    name=(88, 648, 690, 764), ruby_y=674, name_y=722,
    traits=(296, 768, 548, 800),
    effect=(12, 806, 846, 1066),
    rule=(326, 1074, 850, 1176),
)

# Sheet layout: (page, row, column) -> CardID.  Page 2 holds 3 alpha, 3 beta and 3 Reserves; we keep one of each.
SHEET = {
    (0, 0, 0): "SING_B_GENESIS", (0, 0, 1): "SING_B_ARMS",  (0, 0, 2): "SING_B_ALKES",
    (0, 1, 0): "SING_B_NOVAS",   (0, 1, 1): "SING_B_ZEROS", (0, 1, 2): "SING_B_LEGASIS",
    (0, 2, 0): "SING_B_ENERGIS", (0, 2, 1): "SING_B_DRAGOS", (0, 2, 2): "SING_B_IGNIS",
    (1, 0, 0): "SING_A_HOLE", (1, 1, 0): "SING_B_HOLE", (1, 2, 0): "SING_RESERVE",
}
GRID_X, GRID_Y, CELL_W, CELL_H = 124, 194, 2233 / 3, 1040    # card grid on the 2481 x 3508 page


def extract(pdf):
    from pypdf import PdfReader
    os.makedirs(SRC, exist_ok=True)
    for p, page in enumerate(PdfReader(pdf).pages[:2]):
        img = max(page.images, key=lambda i: i.image.width * i.image.height).image.convert("RGB")
        for (pg, r, c), cid in SHEET.items():
            if pg != p:
                continue
            x0, y0 = GRID_X + CELL_W * c, GRID_Y + CELL_H * r
            # a few px in from each edge: the sheet's cut lines sit on the cell borders
            box = (round(x0) + 2, y0 + 3, round(x0 + CELL_W) - 2, y0 + CELL_H - 3)
            img.crop(box).resize((CARD_W, CARD_H), Image.LANCZOS).save(os.path.join(SRC, cid + ".png"))
            print("cut", cid)


def name_block(cv, L, ruby, name, maxw_units):
    s, d = cv.s, cv.d
    cv.frost(L["name"], 12, 0.55, 18)
    cx = (L["name"][0] + L["name"][2]) / 2 * s
    d.text((cx, L["ruby_y"] * s), ruby, font=rc.font("semibold", 17 * s), fill=rc.GOLD_LIGHT, anchor="mm",
           stroke_width=max(1, int(1.5 * s)), stroke_fill=(0, 0, 0))
    name = name.replace('"β Hole"', "\u201cβ Hole\u201d")       # curly quotes on the card
    ns = rc.fit_text(name, "name", 46 * s, 22 * s, maxw_units * s)
    d.text((cx, L["name_y"] * s), name, font=rc.font("name", ns), fill=rc.WHITE, anchor="mm",
           stroke_width=max(2, int(2.5 * s)), stroke_fill=(0, 0, 0))


def effect_block(cv, box, text, report, label):
    s, d = cv.s, cv.d
    b = cv.frost(box, 12, 0.72, 16, tint=HOLE_TINT, tint_amt=0.16, outline=(*HOLE_TINT, 255))
    d.line((b[0] + 26 * s, b[1] + 3 * s, b[2] - 26 * s, b[1] + 3 * s), fill=(*rc.blend(HOLE_TINT, rc.WHITE, 0.4), 200),
           width=max(1, int(s)))
    rc.text_panel(cv, box, rc.split_abilities(segments(text)), report, label, smax=27, top_pad=16)


def render_hole(c, report):
    src = Image.open(os.path.join(SRC, c["CardID"] + ".png")).convert("RGBA")
    big = src.resize((CARD_W * SS, CARD_H * SS), Image.LANCZOS)
    cv = rc.Card(big)
    s, d = cv.s, cv.d
    if c["CardType"] == "Unit":                      # "β Hole" Genesis is laid out like a Unit
        L = GENESIS
        name_block(cv, L, c["Ruby"], c["English Name"], 580)
        rb = cv.frost(L["traits"], 6, 0.80, 8)
        traits = " / ".join(c["Traits"].split("/"))
        fr = rc.font("semibold", rc.fit_text(traits, "semibold", 19 * s, 12 * s, (rb[2] - rb[0]) - 24 * s))
        d.text(((rb[0] + rb[2]) / 2, (rb[1] + rb[3]) / 2), traits, font=fr, fill=rc.WHITE, anchor="mm")
        effect_block(cv, L["effect"], c["Card Text"], report, c["CardID"])
        b = cv.frost(L["rule"], 8, 0.86, 10)
        pad = 12 * s
        size = 19 * s
        while True:
            lines = rc.wrap([rc.build_atoms(c["Rule Text"], size)], (b[2] - b[0]) - 2 * pad)
            if rc.lines_h(lines, size) <= (b[3] - b[1]) - 2 * pad or size <= 11 * s:
                break
            size -= 0.5 * s
        y0 = (b[1] + b[3]) / 2 - rc.lines_h(lines, size) / 2
        rc.draw_lines(d, lines, b[0] + pad, y0, size)
    else:
        L = HOLE
        name_block(cv, L, c["Ruby"], c["English Name"], 620)
        effect_block(cv, L["effect"], c["Card Text"], report, c["CardID"])
        b = cv.frost(L["od_ruby"], 5, 0.85, 6)       # the small オーバードライブ ruby above the OVER DRIVE mark
        d.text(((b[0] + b[2]) / 2, (b[1] + b[3]) / 2), "OVERDRIVE MODIFIER", font=rc.font("bold", 12 * s),
               fill=rc.GOLD_LIGHT, anchor="mm")
    out = big.resize((CARD_W, CARD_H), Image.LANCZOS).convert("RGB")
    os.makedirs(OUT, exist_ok=True)
    out.save(os.path.join(OUT, c["CardID"] + ".jpg"), quality=90, subsampling=0)


def render_reserve():
    """The Singularity Reserve is the usual Reserve without Trinity Charge: start from the English
    Reserve Card, clear the text panel and put the Trinity Draw line back in the middle of it."""
    base = Image.open(os.path.join(COMP, "reserve_card_en.jpg")).convert("RGB")
    W, H = base.size                                  # 859 x 1200
    px = base.load()
    x0, x1, y0, y1 = 50, 236, 58, 1150                # inside the panel's frame
    bg = []                                           # the panel has a left-to-right gradient
    for x in range(W):
        col = sorted(px[x, y] for y in range(1100, 1140))
        bg.append(col[len(col) // 2])
    clean = base.copy()
    cp = clean.load()
    for x in range(x0, x1):
        for y in range(y0, y1):
            cp[x, y] = bg[x]
    # move the Trinity Draw column (x 70..128) to the centre of the panel, keeping its own text
    sx0, sx1 = 70, 128
    dx = round((x0 + x1) / 2 - (sx0 + sx1) / 2)
    for x in range(sx0, sx1):
        for y in range(y0, y1):
            p, b, t = px[x, y], bg[x], bg[x + dx]
            cp[x + dx, y] = tuple(max(0, min(255, t[i] + p[i] - b[i])) for i in range(3))
    clean.save(os.path.join(COMP, "singularity_reserve_en.jpg"), quality=92, subsampling=0)
    print("singularity_reserve_en.jpg")


def main(argv):
    if argv[:1] == ["--extract"]:
        extract(argv[1]); return
    cards = json.load(open(os.path.join(HERE, "cards", "singularity_database.json"), encoding="utf-8"))
    report = []
    for c in cards:
        render_hole(c, report)
        print("rendered", c["CardID"])
    render_reserve()
    for line in report:
        if not line.startswith("FIT"):
            print(line)


if __name__ == "__main__":
    main(sys.argv[1:])
