"""
Trinity Draft - English card renderer (v3, Pillow only)
=======================================================

    pip install pillow
    python tools/render_cards.py                          all cards
    python tools/render_cards.py TD01_C_067 TD02_X01      only these cards
    python tools/render_cards.py --set phantom            one expansion
    python tools/render_cards.py --format png             master format: webp (default, lossless) | png
    python tools/render_cards.py --force                  render even if validate_cards.py reports errors
    python tools/render_cards.py --check-fit              lay out every card without the art and report text sizes

Reads   cards/blaze_database.json, cards/phantom_database.json   (source of truth, never rewritten)
        cards/<set>_cards_hq/TD-0x_*.webp                         (original art, PNG data inside)
        cards/master_glossary.json, tools/fonts/                               (Inter, SIL OFL)
Writes  out/master/<set>/<CardID>.webp     translated card (shared cards such as VOID go to out/master/shared/) at the ORIGINAL resolution, lossless, with
                                           the transparent rounded corners kept
        out/render_report.txt              validation result + cards whose text had to shrink a lot

Exports for TTS / web / print are made from out/master by a separate step (export_cards.py).

What changed from v2
--------------------
* Data comes from the uniform JSON: Color Condition, Shadow Condition, Burst / [EPIC Rule] and
  FlavorText are fields, so nothing is regex-parsed out of the effect text any more.
* No wording is changed by the renderer (the old TERM_FIXES table and the VOID override are gone).
* Bracket-aware text: nested brackets such as [Unit or [Set] Spell] render correctly.
* Colors are drawn as colored diamonds: the Color Condition line, [Red] in Color Shift text and
  "Basic Red Color Card" in Burst / effect text.  "Basic Color Card of your choice" gets a
  four-color diamond.
* Panel tint comes from the Color Condition (frame colour sampled only for Shadow cards).
* Renders at the art's own resolution (2520x3520, 1860x2596 or 1488x2079); layout coordinates are
  still in 859x1200 units and scale automatically.
* Oni Charge, Jigoku Back, Color Shift, Shinra / Reduced / Zero Summon sit at the bottom of the box.
* (1/Turn), (2/Turn), (No Cost) are small badges; (Optional) is an outlined chip.
"""
import json, os, re, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from card_data import HERE, COLORS, load_cards, image_path, segments, tokenize, is_descriptive

OUT = os.path.join(HERE, "out")
REF_W, REF_H = 859, 1200            # layout units (the old 859x1200 card size)

# ------------------------------------------------------------------ fonts --
FONT_DIRS = [os.path.join(HERE, "tools", "fonts"), "/usr/share/fonts/opentype/inter"]
FONTS = {"regular": "Inter-Medium", "bold": "Inter-Bold", "semibold": "Inter-SemiBold",
         "italic": "Inter-Italic", "name": "InterDisplay-BlackItalic"}
_fc = {}
def font(kind, size):
    key = (kind, max(6, int(round(size))))
    if key not in _fc:
        for d in FONT_DIRS:
            p = os.path.join(d, FONTS[kind] + ".otf")
            if os.path.exists(p):
                _fc[key] = ImageFont.truetype(p, key[1]); break
        else:
            raise FileNotFoundError(f"{FONTS[kind]}.otf not found - put Inter in {FONT_DIRS[0]}")
    return _fc[key]

# ---------------------------------------------------------------- colours --
WHITE, BLACK = (255, 255, 255), (15, 15, 15)
DIM = (186, 186, 200)
KEYWORD = (255, 216, 120)
SPAN = (170, 220, 255)                       # descriptive [phrases]
GOLD, GOLD_LIGHT, GOLD_DARK = (214, 172, 74), (240, 212, 140), (120, 88, 28)
PANEL = (14, 14, 18)
COST_BG = (40, 40, 54)
BADGE_BG = (70, 70, 84)
COLOR_RGB = {"Red": (215, 40, 48), "Yellow": (240, 196, 30), "Blue": (40, 120, 225),
             "Purple": (150, 70, 205), "Colorless": (150, 150, 160)}
TIMING = {
    "On Entry": (46, 96, 196), "On Attack": (128, 62, 196), "On Destroy": (92, 92, 104),
    "Trigger": (206, 118, 34), "Activate": (38, 148, 88), "Continuous": (196, 36, 44),
    "Graveyard Activate": (110, 84, 40), "Oni Charge": (150, 36, 48), "Jigoku Back": (70, 120, 60),
    "Equip Cost": (96, 96, 118), "Burst": (236, 236, 240),
}
AURA = (172, 42, 52)                   # Quick Aura (and any other aura)
AURAS = {                              # lighter versions of the matching timing colours
    "Steal Aura": (78, 146, 232),      # lighter than On Entry
    "Bad Aura": (164, 108, 224),       # lighter than On Attack
    "Sky Aura": (226, 178, 40),        # lighter / yellower than Trigger
}
ARROW_BREAK = True                     # each ▶ starts a new line (except "effect from ▶.")
GOLD_TAGS = ("Shinra Summon", "Reduced Summon", "Zero Summon", "Color Shift", "EPIC Rule")
FOOTER_TAGS = ("Shinra Summon", "Reduced Summon", "Zero Summon", "Oni Charge", "Color Shift", "Jigoku Back")
GLOSSARY = json.load(open(os.path.join(HERE, "cards", "master_glossary.json"), encoding="utf-8"))
TRAITS = set(GLOSSARY["traits"].values())

SHOT_NOTE = "After resolving its effect, send this card to its owner's Graveyard."
COST_X_SEG = re.compile(r"^\[Cost X pays any number of Colors when used\]$")

def blend(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))

# ----------------------------------------------------------------- layout --
STD = dict(
    pay_note=(84, 104, 272, 132), color_cond=(264, 80, 612, 132), shadow_hdr=(200, 38, 790, 134),
    cost_x=(24, 132, 442, 164), colorless=(68, 260, 106, 678),
    tag=(40, 722, 162, 752), tag_shadow=(40, 722, 218, 752),
    name_parts=[(165, 676, 712, 754), (712, 700, 805, 754)], name_box=(170, 674, 800, 756),
    traits=(170, 755, 690, 787),
    effect=(12, 789, 846, 1066), spell=(12, 755, 846, 1066), spell_tall=(12, 755, 846, 1158),
    spell_corner=(12, 1062, 376, 1160),
    burst_parts=[(380, 1068, 822, 1158), (790, 1126, 848, 1160)], burst=(380, 1068, 822, 1158),
    equip_label=(20, 1066, 332, 1108),
)
EPIC = dict(STD,
    name_parts=[(98, 606, 830, 688)], name_box=(132, 608, 828, 690),
    tag=(0, 688, 136, 718), traits=(282, 702, 572, 734),
    effect=(12, 736, 846, 1066), epic_parts=[(348, 1062, 828, 1180)],
    epic_rule=(348, 1066, 828, 1180),
)

# ------------------------------------------------------------ rich text --
class Atom:
    __slots__ = ("kind", "text", "w", "font", "color", "bg", "fg")
    def __init__(self, kind, text, w, font=None, color=WHITE, bg=None, fg=None):
        self.kind, self.text, self.w, self.font, self.color, self.bg, self.fg = kind, text, w, font, color, bg, fg

def tag_style(tag):
    base = next((k for k in sorted(TIMING, key=len, reverse=True) if tag == k or tag.startswith(k + ":")), None)
    if base:
        return TIMING[base], (BLACK if base == "Burst" else WHITE), "chip"
    if any(tag.startswith(g) for g in GOLD_TAGS):
        return GOLD, BLACK, "gold"
    if tag.endswith("Aura"):
        return AURAS.get(tag, AURA), WHITE, "chip"
    return None

def chip(text, size, bg, fg, kind):
    if kind == "gold":
        f = font("bold", size * 0.78); text = text.upper()
    elif kind in ("opt", "badge_s"):
        f = font("semibold", size * 0.72)
    else:
        f = font("bold", size * 0.78)
    pad = size * (0.55 if kind == "cost" else 0.30 if kind == "badge_s" else 0.38)
    return Atom(kind, text, f.getlength(text) + 2 * pad + size * 0.16, font=f, bg=bg, fg=fg)

def diamond_atom(size, colors):
    return Atom("diamond", "", size * 0.92, bg=colors)

def _color_card_prefix(toks, i):
    """'Basic Red Color Card(s)' -> [Red];  'Basic Color Card(s)' -> four colours; else None."""
    words = [t.text for t in toks[i:i + 7] if t.kind != "space"]
    if len(words) >= 4 and words[0] == "Basic" and words[1] in COLORS and words[2] == "Color" and words[3].startswith("Card"):
        return [words[1]]
    if len(words) >= 3 and words[0] == "Basic" and words[1] == "Color" and words[2].startswith("Card"):
        return list(COLORS)
    return None

def atoms_from(toks, size, color=WHITE, f_word=None):
    f_reg, f_bold, f_it = font("regular", size), font("bold", size), font("italic", size * 0.9)
    f_word = f_word or f_reg
    sp = f_reg.getlength(" ")
    out = []
    for i, t in enumerate(toks):
        if t.kind == "space":
            out.append(Atom("space", " ", sp))
        elif t.kind == "arrow":
            nxt = toks[i + 1] if i + 1 < len(toks) else None
            ref = nxt is None or (nxt.kind == "word" and nxt.text[:1] in ".,")   # "effect from ▶."
            out.append(Atom("arrow", "ref" if ref else "sep", size * 0.72))
        elif t.kind == "word":
            cols = _color_card_prefix(toks, i)
            if cols:
                out += [diamond_atom(size, cols), Atom("space", " ", sp * 0.6)]
            text = t.text
            prev = toks[i - 1] if i else None
            if prev is not None and prev.kind == "sq" and text.startswith("s") and out and out[-1].color == KEYWORD:
                # '[Trinity Counter]s' -> the plural s belongs to the keyword
                out.append(Atom("word", "s", f_bold.getlength("s"), font=f_bold, color=KEYWORD))
                text = text[1:]
            if text:
                out.append(Atom("word", text, f_word.getlength(text), font=f_word, color=color))
        elif t.kind == "sq":
            inner = t.text.strip()
            nested = any(k.kind in ("sq", "ang", "par") for k in t.kids)
            if inner in COLORS:
                out.append(diamond_atom(size, [inner]))
            elif inner.startswith("Equip: "):
                # [Equip: Pay 2 Color] -> grey EQUIP COST chip + the cost as normal text
                out.append(chip("Equip Cost", size, *tag_style("Equip Cost")))
                out.append(Atom("space", " ", sp))
                out += atoms_from(tokenize(inner[len("Equip: "):]), size, color, f_word)
            elif nested or is_descriptive(inner):
                # descriptive [phrase]: dim brackets, light-blue text, nested tags still styled
                out.append(Atom("word", "[", f_bold.getlength("["), font=f_bold, color=DIM))
                out += atoms_from(t.kids, size, SPAN, f_bold)
                out.append(Atom("word", "]", f_bold.getlength("]"), font=f_bold, color=DIM))
            elif tag_style(inner):
                out.append(chip(inner, size, *tag_style(inner)))
            else:   # plain keyword tag: bold gold, brackets dropped
                for j, w in enumerate(inner.split(" ")):
                    if j: out.append(Atom("space", " ", sp))
                    out.append(Atom("word", w, f_bold.getlength(w), font=f_bold, color=KEYWORD))
        elif t.kind == "ang":
            inner = t.text.strip()
            if inner in TRAITS:
                out.append(Atom("word", inner, f_bold.getlength(inner), font=f_bold, color=KEYWORD))
            else:
                out.append(chip(inner, size, COST_BG, WHITE, "cost"))
        elif t.kind == "par":
            inner = t.text.strip()
            if inner.lower() == "optional":
                out.append(chip("Optional", size, None, DIM, "opt"))
            elif inner == "s":          # 'Unit(s)' is ordinary text
                out.append(Atom("word", "(s)", f_word.getlength("(s)"), font=f_word, color=color))
            elif re.fullmatch(r"\d+/(?:Turn|Game)|No Cost", inner):
                out.append(chip(inner, size, BADGE_BG, WHITE, "badge_s"))
            else:
                words = ("(" + inner + ")").split(" ")
                for j, w in enumerate(words):
                    if j: out.append(Atom("space", " ", f_it.getlength(" ")))
                    out.append(Atom("word", w, f_it.getlength(w), font=f_it, color=DIM))
    return out

def build_atoms(text, size, lead=None):
    sp = font("regular", size).getlength(" ")
    atoms = [lead, Atom("space", " ", sp)] if lead else []
    bullet = text.startswith("- ")
    if bullet:
        atoms.append(Atom("bullet", "", size * 0.9))
        text = text[2:]
    atoms += atoms_from(tokenize(text), size)
    return atoms, bullet

def wrap(paras, width):
    """paras: list of (atoms, bullet). Returns list of (line, first_of_para, bullet)."""
    lines = []
    for atoms, bullet in paras:
        line, x, first = [], 0.0, True
        hang = atoms[0].w if bullet else 0
        for a in atoms:
            if a.kind == "space":
                if line:
                    line.append((a, x)); x += a.w
                continue
            # keep closing punctuation / brackets on the same line as the previous atom
            glue = a.kind == "word" and a.text[:1] in ".,:;)]" and line and line[-1][0].kind != "space"
            if ARROW_BREAK and a.kind == "arrow" and a.text == "sep" and any(l[0].kind != "space" for l in line):
                while line and line[-1][0].kind == "space":
                    line.pop()
                lines.append((line, first, bullet)); line, x, first = [], hang, False
            elif line and x + a.w > width and not glue:
                while line and line[-1][0].kind == "space":
                    line.pop()
                carry = []
                if len(line) > 1 and line[-1][0].kind == "arrow":      # never end a line with ▶
                    carry = [line.pop()[0]]
                    while line and line[-1][0].kind == "space":
                        line.pop()
                lines.append((line, first, bullet)); line, x, first = [], hang, False
                for ca in carry:
                    line.append((ca, x)); x += ca.w
                    sp_ = next((b for b in atoms if b.kind == "space"), None)
                    if sp_: line.append((sp_, x)); x += sp_.w
            line.append((a, x)); x += a.w
        while line and line[-1][0].kind == "space":
            line.pop()
        if line:
            lines.append((line, first, bullet))
    return lines

LH, PGAP, BGAP = 1.30, 0.38, 0.10
def lines_h(lines, size):
    h = 0
    for i, (_, first, bullet) in enumerate(lines):
        if first and i > 0:
            h += size * (BGAP if bullet else PGAP)
        h += size * LH
    return h

def draw_diamond(d, cx, cy, r, colors, outline=(245, 245, 250), lw=1):
    top, right, bot, left = (cx, cy - r), (cx + r * 0.78, cy), (cx, cy + r), (cx - r * 0.78, cy)
    if len(colors) == 1:
        d.polygon([top, right, bot, left], fill=COLOR_RGB.get(colors[0], COLOR_RGB["Colorless"]))
    else:   # four-colour diamond: one triangle per colour
        c = (cx, cy)
        for (a, b), col in zip([(top, right), (right, bot), (bot, left), (left, top)], colors):
            d.polygon([a, b, c], fill=COLOR_RGB[col])
    if outline:
        d.line([top, right, bot, left, top], fill=outline, width=lw, joint="curve")

def draw_atom(d, a, x, cy, size):
    if a.kind == "space":
        return
    if a.kind == "word":
        d.text((x, cy), a.text, font=a.font, fill=a.color, anchor="lm")
    elif a.kind == "arrow":
        s = size
        d.polygon([(x + s * 0.10, cy - s * 0.30), (x + s * 0.10, cy + s * 0.30), (x + s * 0.58, cy)], fill=WHITE)
    elif a.kind == "bullet":
        r = size * 0.13
        d.ellipse((x + size * 0.25 - r, cy - r, x + size * 0.25 + r, cy + r), fill=DIM)
    elif a.kind == "diamond":
        draw_diamond(d, x + a.w / 2, cy, size * 0.42, a.bg, lw=max(1, int(size * 0.06)))
    else:
        h = size * (0.92 if a.kind == "badge_s" else 1.12)
        x1 = x + a.w - size * 0.16
        box = [x, cy - h / 2, x1, cy + h / 2]
        lw = max(int(size * 0.07), 1)
        if a.kind == "cost":
            k = h * 0.32
            pts = [(x, cy), (x + k, box[1]), (x1 - k, box[1]), (x1, cy), (x1 - k, box[3]), (x + k, box[3])]
            d.polygon(pts, fill=a.bg)
            d.line(pts + [pts[0]], fill=(205, 205, 220), width=lw)
        elif a.kind == "opt":
            d.rounded_rectangle(box, radius=h * 0.3, outline=a.fg, width=lw)
        else:
            d.rounded_rectangle(box, radius=h * (0.18 if a.kind in ("badge", "badge_s") else 0.28), fill=a.bg,
                                outline=GOLD_DARK if a.kind == "gold" else None, width=lw)
        light = a.bg is not None and a.fg == WHITE and (0.299 * a.bg[0] + 0.587 * a.bg[1] + 0.114 * a.bg[2]) > 150
        d.text(((x + x1) / 2, cy), a.text, font=a.font, fill=a.fg, anchor="mm",
               stroke_width=max(1, int(size * 0.06)) if light else 0, stroke_fill=(70, 50, 10))

def draw_lines(d, lines, x0, y0, size):
    y = y0
    for i, (line, first, bullet) in enumerate(lines):
        if first and i > 0:
            y += size * (BGAP if bullet else PGAP)
        for a, x in line:
            draw_atom(d, a, x0 + x, y + size * LH / 2, size)
        y += size * LH
    return y

def split_abilities(segs):
    """' - ' option lists become bullets ('Choose 1 of the following: - A - B')."""
    out = []
    for p in segs:
        bits = re.split(r"(?<=[.:)])\s+-\s+(?=[A-Z\[<+])", p.strip())
        out.append(bits[0]); out += ["- " + b for b in bits[1:]]
    return out

def is_footer(seg):
    m = re.match(r"^\[([^\]]+)\]", seg)
    return bool(m) and any(m.group(1).startswith(t) for t in FOOTER_TAGS)

def fit_box(main, foot, width, height, smax, smin, step):
    """Largest size where main (top) + footer (bottom insets) fit."""
    size = smax
    while True:
        ml = wrap([build_atoms(p, size) for p in main], width)
        fl = [wrap([build_atoms(p, size)], width - size * 1.0) for p in foot]
        fh = sum(lines_h(l, size) + size * 0.75 for l in fl) + (size * 0.35 * (len(fl) - 1) if fl else 0)
        total = lines_h(ml, size) + (size * 0.5 if ml and fl else 0) + fh
        if total <= height or size <= smin:
            return size, ml, fl, total > height
        size -= step

# ---------------------------------------------------------------- canvas --
class Card:
    def __init__(self, img):
        self.img, self.s = img, img.width / REF_W
        self.d = ImageDraw.Draw(img, "RGBA")
    def P(self, b):
        return tuple(v * self.s for v in b)
    def frost(self, boxes, radius=8, dark=0.66, blur=14, tint=None, tint_amt=0.0, outline=None, ow=2.2):
        if isinstance(boxes[0], (int, float)):
            boxes = [boxes]
        bs = [tuple(int(round(v)) for v in self.P(b)) for b in boxes]
        U = (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs))
        region = self.img.crop(U).filter(ImageFilter.GaussianBlur(blur * self.s))
        col = blend(PANEL, tint, tint_amt) if tint else PANEL
        region = Image.alpha_composite(region, Image.new("RGBA", region.size, (*col, int(255 * dark))))
        mask = Image.new("L", region.size, 0)
        md = ImageDraw.Draw(mask)
        r = int(radius * self.s)
        for b in bs:
            md.rounded_rectangle((b[0] - U[0], b[1] - U[1], b[2] - U[0] - 1, b[3] - U[1] - 1), r, fill=255)
        # keep the card's own alpha (rounded corners) where the panel touches the edge
        a = self.img.crop(U).getchannel("A")
        region.putalpha(a)
        self.img.paste(region, U[:2], mask)
        if outline:
            for b in bs:
                self.d.rounded_rectangle(b, r, outline=outline, width=max(1, int(ow * self.s)))
        return bs[0]

def frame_tint(img):
    """Shadow cards have no Color Condition: read the frame colour from the right border."""
    w, h = img.size
    strip = img.convert("RGB").crop((int(w * 0.975), int(h * 0.30), int(w * 0.99), int(h * 0.70))).resize((1, 40))
    px = sorted((strip.getpixel((0, y)) for y in range(40)), key=lambda p: sum(p))[20]
    r, g, b = px
    if r > 150 and g < 100: return COLOR_RGB["Red"]
    if r > 150 and g > 130 and b < 110: return COLOR_RGB["Yellow"]
    if b > 140 and r < 120: return COLOR_RGB["Blue"]
    if r > 90 and b > 120 and g < 110: return COLOR_RGB["Purple"]
    return COLOR_RGB["Colorless"]

def card_tint(c, img):
    if c["Color Condition"] == "Colorless":
        return COLOR_RGB["Colorless"]
    if c["_colors"]:
        return COLOR_RGB[c["_colors"][0][1]]
    return frame_tint(img)

def fit_text(text, kind, start, minimum, maxw):
    size = start
    while size > minimum and font(kind, size).getlength(text) > maxw:
        size -= 0.5
    return size

def split_name(name):
    """('Orochi', 'Red-Eyed Dragon') for 'Red-Eyed Dragon, Orochi' - epithet goes small above."""
    if ", " in name:
        a, b = name.split(", ", 1)
        return (a, b) if b.lower().startswith("the ") else (b, a)
    return name, None

def spell_kind(t):
    return "EQUIP" if "Equip" in t else "SET" if "Set" in t else "SHOT"

# ---------------------------------------------------------------- render --
def text_panel(cv, box, segs, report, label, smax=26, smin=15, pad=16, top_pad=None):
    """Top-aligned main text, footer abilities anchored to the bottom in insets."""
    s, d = cv.s, cv.d
    x0, y0, x1, y1 = cv.P(box)
    tp = (top_pad if top_pad is not None else pad) * s
    w, h = (x1 - x0) - 2 * pad * s, (y1 - y0) - tp - pad * 0.8 * s
    main = [p for p in segs if not is_footer(p)]
    foot = [p for p in segs if is_footer(p)]
    size, ml, fl, over = fit_box(main, foot, w, h, smax * s, smin * s, 0.5 * s)
    if over and foot:   # footers don't fit at the bottom - let everything flow from the top
        size, ml, fl, over = fit_box(segs, [], w, h, smax * s, smin * s, 0.5 * s)
    draw_lines(d, ml, x0 + pad * s, y0 + tp, size)
    yb = y1 - pad * 0.8 * s
    for l in reversed(fl):
        ih = lines_h(l, size) + size * 0.75
        bx = (x0 + pad * s * 0.55, yb - ih, x1 - pad * s * 0.55, yb)
        d.rounded_rectangle(bx, int(6 * s), fill=(0, 0, 0, 120), outline=(255, 255, 255, 40), width=max(1, int(s)))
        draw_lines(d, l, bx[0] + size * 0.5, bx[1] + size * 0.375, size)
        yb -= ih + size * 0.35
    report.append(f"FIT\t{label}\teffect\t{size / s:.1f}\t{int(over)}")
    if over:
        report.append(f"{label}: text does not fit even at the minimum size")
    elif size < (smin + 2) * s:
        report.append(f"{label}: text fits but is small ({size / s:.1f} at 859 wide) - consider shortening")

def color_condition(cv, c, box):
    """'COLOR CONDITION' + one diamond per colour (replaces the JP 'カラー条件・上記を含める' line)."""
    s, d = cv.s, cv.d
    b = cv.frost(box, 10, 0.82, 10)
    cy = (b[1] + b[3]) / 2 + 3 * s
    lab_f = font("semibold", 15 * s)
    if c["Color Condition"] == "Colorless":
        items, tail = [], "Colorless"
    else:
        items, tail = [col for n, col in c["_colors"] for _ in range(n)], None
    label = "COLOR CONDITION"
    r = 11 * s
    step = r * 1.75
    tail_w = font("bold", 17 * s).getlength(tail) + 8 * s if tail else 0
    total = lab_f.getlength(label) + 12 * s + max(len(items), 1) * step + tail_w
    x = (b[0] + b[2]) / 2 - total / 2
    d.text((x, cy), label, font=lab_f, fill=(225, 225, 232), anchor="lm")
    x += lab_f.getlength(label) + 12 * s + step / 2
    if items:
        for col in items:
            draw_diamond(d, x, cy, r, [col], lw=max(1, int(1.4 * s)))
            x += step
    else:
        draw_diamond(d, x, cy, r, ["Colorless"], lw=max(1, int(1.4 * s)))
        d.text((x + step / 2 + 4 * s, cy), tail, font=font("bold", 17 * s), fill=WHITE, anchor="lm")

def render(c, set_name, report, blank=False):
    """blank=True lays the card out on an empty 2520x3520 canvas (fit check without the art)."""
    if blank:
        orig = Image.new("RGBA", (2520, 3520), (40, 40, 48, 255))
    else:
        orig = Image.open(image_path(c, set_name)).convert("RGBA")
    ss = 2 if orig.width < 2000 else 1                     # supersample the smaller art
    base = orig.resize((orig.width * ss, orig.height * ss), Image.LANCZOS) if ss > 1 else orig.copy()
    cv = Card(base)
    s, d = cv.s, cv.d
    ctype = c["CardType"]
    epic = c["Rarity"] == "Epic"
    L = EPIC if epic else STD
    spell = "Spell" in ctype
    shadow = "Shadow" in ctype
    tint = card_tint(c, orig)
    lab = c["CardID"]

    segs = segments(c["Card Text"])
    spell_note = cost_x = None
    if spell and segs and (segs[0].startswith("After use, it remains") or segs[0].startswith("Pay the Cost to put this")
                           or segs[0] == SHOT_NOTE):
        spell_note = segs.pop(0)
    if segs and COST_X_SEG.match(segs[0]):
        cost_x = segs.pop(0)[1:-1]
    segs = split_abilities(segs)

    # ---- header
    if shadow:
        b = cv.frost(L["shadow_hdr"], 8, 0.74, 10)
        d.text(((b[0] + b[2]) / 2, b[1] + 26 * s), "After setting in the Shadow Zone, it can be used:",
               font=font("semibold", 18 * s), fill=(232, 232, 236), anchor="mm")
        cond = (c["Shadow Condition"] or "-").rstrip(".")
        sz = fit_text(cond, "bold", 24 * s, 14 * s, (b[2] - b[0]) - 24 * s)
        d.text(((b[0] + b[2]) / 2, b[1] + 64 * s), cond, font=font("bold", sz), fill=KEYWORD, anchor="mm")
    else:
        color_condition(cv, c, L["color_cond"])
        b = cv.frost(L["pay_note"], 6, 0.84, 8)
        d.text((b[0] + 6 * s, (b[1] + b[3]) / 2), "Pay Color to play this card", font=font("regular", 13 * s),
               fill=(225, 225, 230), anchor="lm")
    if cost_x:
        b = cv.frost(L["cost_x"], 6, 0.84, 8)
        d.text((b[0] + 8 * s, (b[1] + b[3]) / 2), cost_x, font=font("semibold", fit_text(cost_x, "semibold", 15 * s, 10 * s, (b[2] - b[0]) - 16 * s)),
               fill=WHITE, anchor="lm")
    if c["Color Condition"] == "Colorless":
        bx = [int(v) for v in cv.P(L["colorless"])]
        cv.frost(L["colorless"], 8, 0.84, 8)
        txt = c["FlavorText"] or "Colorless cards cannot be used for Color Charge."
        strip = Image.new("RGBA", (bx[3] - bx[1], bx[2] - bx[0]), (0, 0, 0, 0))
        sd = ImageDraw.Draw(strip)
        sz = fit_text(txt, "semibold", 17 * s, 10 * s, strip.width - 16 * s)
        sd.text((strip.width / 2, strip.height / 2), txt, font=font("semibold", sz), fill=WHITE, anchor="mm")
        base.alpha_composite(strip.rotate(-90, expand=True), (bx[0], bx[1]))

    # ---- name (epithet small & gold above the main name, like the JP ruby line)
    cv.frost(L["name_parts"], 10, 0.58, 18)
    nb = list(cv.P(L["name_box"]))
    if shadow and not epic:
        nb[0] = 228 * s
    main_name, epithet = split_name(c["English Name"].strip())
    maxw = (nb[2] - nb[0]) - 16 * s
    cx = (nb[0] + nb[2]) / 2
    if epithet:
        es = fit_text(epithet, "semibold", 19 * s, 12 * s, maxw)
        d.text((cx, nb[1] + 15 * s), epithet, font=font("semibold", es), fill=GOLD_LIGHT, anchor="mm",
               stroke_width=max(1, int(1.5 * s)), stroke_fill=(0, 0, 0))
        ns = fit_text(main_name, "name", 44 * s, 22 * s, maxw)
        d.text((cx, nb[1] + 52 * s), main_name, font=font("name", ns), fill=WHITE, anchor="mm",
               stroke_width=max(2, int(2.5 * s)), stroke_fill=(0, 0, 0))
    else:
        ns = fit_text(main_name, "name", 44 * s, 22 * s, maxw)
        d.text((cx, (nb[1] + nb[3]) / 2 + 4 * s), main_name, font=font("name", ns), fill=WHITE, anchor="mm",
               stroke_width=max(2, int(2.5 * s)), stroke_fill=(0, 0, 0))

    # ---- type tag
    tb = cv.P(L["tag_shadow"] if (shadow and not epic) else L["tag"])
    d.rounded_rectangle(tb, int(5 * s), fill=(236, 236, 240), outline=(60, 60, 70), width=max(1, int(1.5 * s)))
    tag = ("SHADOW " if shadow else "") + ("SPELL" if spell else "UNIT")
    sz = fit_text(tag, "bold", 18 * s, 10 * s, (tb[2] - tb[0]) - 10 * s)
    d.text(((tb[0] + tb[2]) / 2, (tb[1] + tb[3]) / 2), tag, font=font("bold", sz), fill=BLACK, anchor="mm")

    # ---- traits pill (units)
    if not spell:
        rb = cv.frost(L["traits"], 4, 0.88, 8)
        traits = " / ".join(t for t in (c["Traits"] or "").split("/") if t)
        fr = font("semibold", fit_text(traits, "semibold", 19 * s, 12 * s, (rb[2] - rb[0]) - 30 * s))
        pw = fr.getlength(traits) + 34 * s
        mid = (rb[0] + rb[2]) / 2
        d.rounded_rectangle((mid - pw / 2, rb[1] + 3 * s, mid + pw / 2, rb[3] - 3 * s), int(6 * s),
                            fill=(*blend(PANEL, tint, 0.62), 255))
        d.text((mid, (rb[1] + rb[3]) / 2), traits, font=fr, fill=WHITE, anchor="mm")

    # ---- effect panel
    burst = epic_rule = None
    if c["Burst"]:
        m = re.match(r"^\[(Burst|EPIC Rule)\]\s*(.*)$", c["Burst"], re.S)
        if m and m.group(1) == "EPIC Rule":
            epic_rule = m.group(2)
        elif m:
            burst = m.group(2)
    if spell:
        kind = spell_kind(ctype)
        box = L["spell_tall"] if (kind != "EQUIP" and not burst) else L["spell"]
        if kind != "EQUIP" and burst:
            cv.frost(L["spell_corner"], 10, 0.74, 14)
        b = cv.frost(box, 12, 0.72, 16, tint=tint, tint_amt=0.14, outline=(*tint, 255))
        d.line((b[0] + 26 * s, b[1] + 3 * s, b[2] - 26 * s, b[1] + 3 * s), fill=(*blend(tint, WHITE, 0.4), 200), width=max(1, int(s)))
        pf = font("name", 30 * s)
        pw = pf.getlength(kind) + 26 * s
        px0, py0 = b[0] + 14 * s, b[1] + 12 * s
        d.polygon([(px0 + 8 * s, py0), (px0 + pw, py0), (px0 + pw - 8 * s, py0 + 40 * s), (px0, py0 + 40 * s)], fill=(245, 245, 245))
        d.text((px0 + pw / 2, py0 + 20 * s), kind, font=pf, fill=BLACK, anchor="mm")
        note = spell_note or SHOT_NOTE
        nx0, nx1 = px0 + pw + 12 * s, b[2] - 14 * s
        nsz = 15 * s
        while True:
            nf = font("italic", nsz)
            words, lines, cur = note.replace("[Equip Cost]", "Equip Cost").split(), [], ""
            for wd in words:
                t = (cur + " " + wd).strip()
                if nf.getlength(t) > nx1 - nx0 and cur:
                    lines.append(cur); cur = wd
                else:
                    cur = t
            lines.append(cur)
            if len(lines) * nsz * 1.2 <= 48 * s or nsz <= 10 * s:
                break
            nsz -= 0.5 * s
        ty = py0 + 20 * s - (len(lines) - 1) * nsz * 0.6
        for i, ln in enumerate(lines):
            d.text((nx0, ty + i * nsz * 1.2), ln, font=nf, fill=DIM, anchor="lm")
        d.line((b[0] + 16 * s, py0 + 52 * s, b[2] - 16 * s, py0 + 52 * s), fill=(*tint, 150), width=max(1, int(s)))
        if segs:
            text_panel(cv, box, segs, report, lab, top_pad=76)
    elif segs:
        b = cv.frost(L["effect"], 12, 0.72, 16, tint=tint, tint_amt=0.14, outline=(*tint, 255))
        d.line((b[0] + 26 * s, b[1] + 3 * s, b[2] - 26 * s, b[1] + 3 * s), fill=(*blend(tint, WHITE, 0.4), 200), width=max(1, int(s)))
        text_panel(cv, L["effect"], segs, report, lab, top_pad=14)

    # ---- equip modifiers label
    if "Equip" in ctype:
        b = cv.frost(L["equip_label"], 6, 0.84, 8)
        d.text((b[0] + 8 * s, (b[1] + b[3]) / 2), "The equipped Unit gets:", font=font("semibold", 16 * s), fill=WHITE, anchor="lm")

    # ---- burst / epic rule
    def lead_panel(parts, box, body, lead_chip, outline):
        cv.frost(parts, 8, 0.82, 14, outline=None)
        bx = cv.P(box)
        d.rounded_rectangle(bx, int(8 * s), outline=outline, width=max(1, int(1.6 * s)))
        pad = 9 * s
        w, h = (bx[2] - bx[0]) - 2 * pad, (bx[3] - bx[1]) - 2 * pad
        size = 21 * s
        while True:
            lines = wrap([build_atoms(body, size, lead=lead_chip(size))], w)
            if lines_h(lines, size) <= h or size <= 11 * s:
                break
            size -= 0.5 * s
        draw_lines(d, lines, bx[0] + pad, bx[1] + pad, size)
        report.append(f"FIT\t{lab}\tburst\t{size / s:.1f}\t{int(lines_h(lines, size) > h)}")
        if lines_h(lines, size) > h:
            report.append(f"{lab}: burst/epic text overflows")
        elif size < 13 * s:
            report.append(f"{lab}: burst/epic text is small ({size / s:.1f})")
    if epic and epic_rule:
        lead_panel(L["epic_parts"], L["epic_rule"], epic_rule,
                   lambda sz: chip("EPIC RULE", sz, GOLD, BLACK, "gold"), (*GOLD, 255))
    elif burst:
        lead_panel(L["burst_parts"], L["burst"], burst,
                   lambda sz: chip("BURST", sz, WHITE, BLACK, "badge"), (210, 210, 220, 255))

    if ss > 1:
        base = base.resize(orig.size, Image.LANCZOS)
    return base

# ---------------------------------------------------------------- output --
def save_master(img, path, fmt):
    if fmt == "png":
        img.save(path, compress_level=6)
    else:   # lossless WebP: same pixels as PNG, ~30% smaller. method 2 = good speed/size balance
        img.save(path, lossless=True, quality=50, method=2)

def _job(job):
    c, set_name, fmt, folder = job
    report = []
    if fmt == "fit":                                  # --check-fit: layout only, nothing saved
        render(c, set_name, report, blank=True)
        return set_name, c["CardID"], report
    od = os.path.join(OUT, "master", folder); os.makedirs(od, exist_ok=True)
    p = os.path.join(od, f"{c['CardID']}.{fmt}")
    save_master(render(c, set_name, report), p, fmt)
    return set_name, c["CardID"], report

def fit_summary(lines):
    """Turn the FIT lines into a readable table: smallest text size per card (859-wide units)."""
    rows = [l.split("\t")[1:] for l in lines if l.startswith("FIT\t")]
    eff = {r[0]: float(r[2]) for r in rows if r[1] == "effect"}
    bur = {r[0]: float(r[2]) for r in rows if r[1] == "burst"}
    over = sorted({r[0] for r in rows if r[3] == "1"})
    out = ["Text size per card (859-wide units; effect box max 26, min 15; burst/epic max 21, min 11)", "",
           f"effect boxes: {len(eff)}  full size (26): {sum(1 for v in eff.values() if v >= 26)}  "
           f"smallest: {min(eff.values(), default=0):.1f}",
           f"burst boxes:  {len(bur)}  full size (21): {sum(1 for v in bur.values() if v >= 21)}  "
           f"smallest: {min(bur.values(), default=0):.1f}",
           f"overflowing: {', '.join(over) or 'none'}", "", "Smallest 25 effect boxes:"]
    out += [f"  {k:13} {v:.1f}" for k, v in sorted(eff.items(), key=lambda x: x[1])[:25]]
    out += ["", "Smallest 10 burst/epic boxes:"]
    out += [f"  {k:13} {v:.1f}" for k, v in sorted(bur.items(), key=lambda x: x[1])[:10]]
    return out

def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    opts = {a.split("=")[0]: (a.split("=", 1)[1] if "=" in a else True) for a in argv if a.startswith("--")}
    for i, a in enumerate(argv):                     # allow "--set phantom" as well as "--set=phantom"
        if a in ("--set", "--format", "--jobs") and i + 1 < len(argv):
            opts[a] = argv[i + 1]; args = [x for x in args if x != argv[i + 1]]
    fmt = "fit" if "--check-fit" in opts else opts.get("--format", "webp")
    only_set = opts.get("--set")
    jobs = int(opts.get("--jobs", max(1, (os.cpu_count() or 2) - 1)))

    import validate_cards
    cards = load_cards()
    issues, _, _ = validate_cards.validate(cards, GLOSSARY, check_images=False)
    todo = []
    for c in cards:
        if args and c["CardID"] not in args:
            continue
        if only_set and only_set not in c["_sets"]:
            continue
        if len(c["_sets"]) > 1:            # shared card (VOID): render once from whichever set has the art
            have = [sn for sn in c["_sets"] if os.path.exists(image_path(c, sn))]
            if have or fmt == "fit":
                todo.append((c, (have or c["_sets"])[0], fmt, "shared"))
            else:
                issues.append(("ERROR", c["CardID"], "image missing in every set folder"))
        elif fmt == "fit":
            todo.append((c, c["_set"], fmt, c["_set"]))
        elif not os.path.exists(image_path(c, c["_set"])):
            issues.append(("ERROR", c["CardID"], f"image missing: {os.path.relpath(image_path(c, c['_set']), HERE)}"))
        else:
            todo.append((c, c["_set"], fmt, c["_set"]))
    errors = [i for i in issues if i[0] == "ERROR"]
    report = [f"validation: {len(errors)} errors, {len(issues) - len(errors)} warnings (details: python tools/validate_cards.py)"]
    report += [f"  {lvl} {cid}: {msg}" for lvl, cid, msg in errors]
    if errors and "--force" not in opts:
        print("\n".join(report)); print("Fix the errors above (or use --force)."); return 1

    os.makedirs(OUT, exist_ok=True)
    print(f"rendering {len(todo)} cards with {jobs} worker(s) ...")
    if jobs > 1 and len(todo) > 1:
        from multiprocessing import Pool
        with Pool(jobs) as pool:
            results = list(pool.imap_unordered(_job, todo))
    else:
        results = [_job(t) for t in todo]
    for set_name, cid, rep in sorted(results, key=lambda r: (r[0], r[1])):
        report += rep
    fits = fit_summary(report)
    report = [l for l in report if not l.startswith("FIT\t")]
    name = "fit_report.txt" if fmt == "fit" else "render_report.txt"
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write("\n".join(report + [""] + fits) + "\n")
    if fmt == "fit":
        print(f"{len(results)} cards laid out (no images written) -> out/fit_report.txt")
    else:
        print(f"{len(results)} cards rendered -> out/master/<set>/<CardID>.{fmt}")
    print("\n".join(report + [""] + fits[:6]))
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
