"""
Trinity Draft - shared card data helpers
========================================
Used by validate_cards.py and render_cards.py so both read the cards the same way.

    from card_data import load_cards, tokenize, image_path

The JSON files in cards/ are the source of truth. Nothing here rewrites wording.
"""
import json, os, re

TOOLS = os.path.dirname(os.path.abspath(__file__))
HERE = os.path.dirname(TOOLS)          # project root (cards/, images/, out/ live here)
CARDS_DIR = os.path.join(HERE, "cards")
SETS = {"TD01": "blaze", "TD02": "phantom"}
COLORS = ("Red", "Yellow", "Blue", "Purple")
SHARED_IDS = {"TD_ACT1_VOID"}          # cards that belong to every set


# ------------------------------------------------------------------ loading --
def load_cards(cards_dir=CARDS_DIR):
    """Returns a list of card dicts (the raw JSON fields plus a few derived keys).

    Derived keys (prefixed with _):
      _set      'blaze' / 'phantom'
      _sets     sets the card appears in (VOID -> both)
      _colors   [(n, 'Red'), ...] parsed from Color Condition, [] for Colorless / None
    """
    cards, seen = [], {}
    for prefix, name in SETS.items():
        path = os.path.join(cards_dir, f"{name}_database.json")
        for c in json.load(open(path, encoding="utf-8")):
            cid = c["CardID"]
            if cid in seen:                         # shared card listed twice
                seen[cid]["_sets"].append(name)
                continue
            c["_set"] = name
            c["_sets"] = [name] + ([n for p, n in SETS.items() if n != name] if cid in SHARED_IDS else [])
            c["_colors"] = parse_colors(c.get("Color Condition"))
            seen[cid] = c
            cards.append(c)
    return cards


def parse_colors(cond):
    if not cond or cond == "Colorless":
        return []
    out = []
    for part in cond.split(","):
        m = re.fullmatch(r"\s*(\d+) (Red|Yellow|Blue|Purple)\s*", part)
        out.append((int(m.group(1)), m.group(2)) if m else (0, part.strip()))
    return out


def image_name(card_id):
    """TD01_C_067 -> TD-01_C067 ; TD01_LEG_01 -> TD-01_LEG01 ; TD01_X01 -> TD-01_X01."""
    if card_id in SHARED_IDS:
        return card_id
    m = re.fullmatch(r"TD(\d\d)_([A-Z]+)_?(\d+)", card_id)
    if not m:
        return card_id
    return f"TD-{m.group(1)}_{m.group(2)}{m.group(3)}"


def image_path(card, set_name=None, cards_dir=CARDS_DIR):
    s = set_name or card["_set"]
    return os.path.join(cards_dir, f"{s}_cards_hq", image_name(card["CardID"]) + ".webp")


def segments(text):
    """Split card text into abilities on ' / ' (never inside brackets)."""
    if not text:
        return []
    out, depth, cur, i = [], 0, "", 0
    while i < len(text):
        ch = text[i]
        if ch in "[<(":
            depth += 1
        elif ch in "]>)":
            depth = max(0, depth - 1)
        if depth == 0 and text.startswith(" / ", i):
            out.append(cur.strip()); cur = ""; i += 3; continue
        cur += ch; i += 1
    if cur.strip():
        out.append(cur.strip())
    return out


# ---------------------------------------------------------------- tokenizer --
PAIRS = {"[": "]", "<": ">", "(": ")"}


class Tok:
    """kind: 'word' | 'space' | 'arrow' | 'sq' | 'ang' | 'par'
    text: raw text (for brackets: the inner text), kids: tokens inside a bracket."""
    __slots__ = ("kind", "text", "kids")

    def __init__(self, kind, text, kids=None):
        self.kind, self.text, self.kids = kind, text, kids or []

    def __repr__(self):
        return f"{self.kind}:{self.text!r}" + (f"{self.kids}" if self.kids else "")


def match_close(text, i):
    """Index of the bracket closing text[i], respecting nesting; -1 if unbalanced."""
    stack = [PAIRS[text[i]]]
    j = i + 1
    while j < len(text):
        ch = text[j]
        if ch in PAIRS and not (ch == "<" and j + 1 < len(text) and text[j + 1] == " "):
            stack.append(PAIRS[ch])
        elif stack and ch == stack[-1]:
            stack.pop()
            if not stack:
                return j
        j += 1
    return -1


def tokenize(text):
    """Bracket-aware tokenizer. Nested brackets become child tokens."""
    toks, i, word = [], 0, ""

    def flush():
        nonlocal word
        if word:
            toks.append(Tok("word", word)); word = ""

    while i < len(text):
        ch = text[i]
        if ch in PAIRS:
            j = match_close(text, i)
            if j > 0:
                flush()
                inner = text[i + 1:j]
                kind = {"[": "sq", "<": "ang", "(": "par"}[ch]
                toks.append(Tok(kind, inner, tokenize(inner)))
                i = j + 1
                continue
        if ch.isspace():
            flush()
            if not toks or toks[-1].kind != "space":
                toks.append(Tok("space", " "))
        elif ch == "▶":
            flush(); toks.append(Tok("arrow", "▶"))
        else:
            word += ch
        i += 1
    flush()
    return toks


def bracket_balance(text):
    """Returns None if every bracket pair closes, else a short description."""
    stack = []
    for i, ch in enumerate(text):
        if ch in "[(":
            stack.append((ch, i))
        elif ch == "<" and not text[i + 1:i + 2] == " ":
            stack.append((ch, i))
        elif ch in "])>":
            if ch == ">" and (not stack or stack[-1][0] != "<"):
                continue                      # a bare '>' used as 'greater than'
            if not stack or PAIRS[stack[-1][0]] != ch:
                return f"unexpected '{ch}' at {i}: …{text[max(0, i - 30):i + 10]}…"
            stack.pop()
    if stack:
        ch, i = stack[-1]
        return f"unclosed '{ch}' at {i}: …{text[i:i + 40]}…"
    return None


def tag_base(inner):
    """'Shinra Summon 6' -> 'Shinra Summon'; 'Reduced Summon: Dragon' -> 'Reduced Summon';
    'Equip: Pay 2 Color' -> 'Equip'; 'Soul Flare 1' -> 'Soul Flare'."""
    base = inner.split(":", 1)[0].strip()
    return re.sub(r"\s+\d+$", "", base)


def is_descriptive(inner):
    """Descriptive brackets ([the number of your Trinity Counters], [1 card from your Graveyard])
    hold a phrase, not a keyword. A tag is Title Case words (optionally a number / ': X')."""
    base = inner.split(":", 1)[0]
    return not re.fullmatch(r"[A-Z][A-Za-z]*(?: [A-Z][A-Za-z]*)*(?: \d+)?", base.strip())
