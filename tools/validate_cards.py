"""
Trinity Draft - card data validator + style guide generator
===========================================================

    python tools/validate_cards.py              check cards/*_database.json, write validation_report.txt
    python tools/validate_cards.py --guide      also refresh the keyword table in cards/style_guide.md

Checks (ERROR = must fix before rendering, WARN = wording differs from the usual form):
  * schema: field types, CardID format, Rarity / CardType / Traits / Color / Color Condition values
  * Shadow cards <-> Shadow Condition, Epic <-> [EPIC Rule], Burst starts with [Burst]
  * balanced brackets in every text field
  * every [Tag] / <Keyword> exists in cards/master_glossary.json
  * wording that is never used (e.g. 'Acquired Life' instead of 'Gained Life')
  * keyword phrasing against the canonical forms below (also printed in cards/style_guide.md)
  * singular / plural after numbers, spacing and punctuation
  * the card image exists
"""
import collections, json, os, re, sys
from card_data import (HERE, COLORS, load_cards, tokenize, bracket_balance, tag_base,
                       is_descriptive, segments, image_path)

GLOSSARY = os.path.join(HERE, "cards", "master_glossary.json")
DEFINITIONS = os.path.join(HERE, "cards", "glossary_definitions.json")
GUIDE = os.path.join(HERE, "cards", "style_guide.md")
REPORT = os.path.join(HERE, "validation_report.txt")

CARD_TYPES = ["Unit", "Shadow Unit", "[Shot] Spell", "[Set] Spell", "[Equip] Spell",
              "Shadow [Shot] Spell", "Shadow [Equip] Spell"]
TEXT_FIELDS = ["English Name", "Card Text", "Burst", "Shadow Condition", "FlavorText"]

SHOT_NOTE = "After resolving its effect, send this card to its owner's Graveyard."
SET_NOTE = "After use, it remains on the Battlefield and exerts its effects."
EQUIP_NOTE = ("Pay the Cost to put this onto the Battlefield. Then, pay the [Equip Cost] to equip it to a Unit. "
              "When the equipped Unit leaves the Battlefield, the Equipment remains on the Battlefield.")
COLORLESS_NOTE = "Colorless cards cannot be used for Color Charge."

# Wording that must never appear (common translation slips). Any hit is an ERROR.
DEPRECATED = [
    (r"Acquired Life", "Gained Life"), (r"Life Deck", "Life Zone"),
    (r"\[Counter\]", "[Trinity Counter]"), (r"Reduction Summon|Discount Summon", "Reduced Summon"),
    (r"ZERO Summon", "Zero Summon"), (r"Demon Charge", "Oni Charge"),
    (r"When Played|When Attacking|When Destroyed", "On Entry / On Attack / On Destroy"),
    (r"\[BURST\]", "[Burst]"), (r"->", "▶"), (r"<Turn \d>|Once per Turn", "(1/Turn)"),
    (r"Valkyria", "Valkyrie"), (r"Steel Aura", "Steal Aura"), (r"\[Always\]", "[Continuous]"),
    (r"Spell \[(Set|Equip|Shot)\]", "[Set] Spell (tag first)"), (r"not a destruction", "not destruction"),
    (r"\[Overdrive\]|\[Overcount\]", "<Overdrive> / <Overcount>"), (r"Attack Phase", "Combat Phase"),
]

# Canonical phrasing: (name, where it starts, full canonical regex). Every occurrence of the start
# pattern must match the canonical regex, otherwise WARN with the actual wording.
N = r"(\d+)"
CANON = [
    ("Shinra Summon", r"(?:^|(?<= / ))\[Shinra Summon \d", r"\[Shinra Summon (\d+)\] Instead of paying the Cost, you may place this card on top of Units on your Battlefield whose combined Cost is exactly \1\."),
    ("Color Shift", r"(?:^|(?<= / ))\[Color Shift \d", r"\[Color Shift (\d)\] When you pay a Summoning Cost, you may send this Unit on the Battlefield to the Graveyard\. If you do, it produces (?:\[(?:Red|Yellow|Blue|Purple)\])+\."),
    ("Oni Charge", r"(?:^|(?<= / ))\[Oni Charge\]", r"\[Oni Charge\] When you Color Charge using this card, do the following: "),
    ("Jigoku Back", r"(?:^|(?<= / ))\[Jigoku Back\]", r"\[Jigoku Back\] When this card is sent from your Deck to the Graveyard, do the following: "),
    ("Reduced Summon", r"(?:^|(?<= / ))\[Reduced Summon:", r"\[Reduced Summon: [^\]]+\] When you summon this, its Cost can be reduced by \d+ for (?:each|every)"),
    ("Zero Summon", r"(?:^|(?<= / ))\[Zero Summon:", r"\[Zero Summon: [^\]]+\] If .+?, this card loses its Color Condition and its Summoning Cost becomes 0\."),
    ("Soul Flare", r"<Soul Flare \d", r"<Soul Flare (\d+)> - Send \1 Souls? from this card to the Graveyard\."),
    ("Overcount", r"<Overcount \d", r"<Overcount (\d+)> - If you have \1 or more \[Trinity Counter\]s\."),
    ("Overdrive", r"<Overdrive \d", r"<Overdrive (\d+)> - If you have \1 or more Gained Life\."),
    ("Bloody Drive", r"<Bloody Drive \d", r"<Bloody Drive (\d+)> - Choose 1 \[Advantage\] Wall, and take \1 damage"),
    ("Life Eater", r"<Life Eater>", r"<Life Eater> - When this Unit's attack hits the Life Zone\."),
    ("Requiem", r"<Requiem \d", r"<Requiem (\d+)> - If \1 or more Units from the Battlefield have been sent to the Graveyard during this turn\."),
    ("Zero Summon: Requiem", r"\[Zero Summon: Requiem \d", r"\[Zero Summon: Requiem (\d+)\] If \1 or more Units from the Battlefield have been sent to the Graveyard during this turn,"),
    ("Counter Flare", r"<Counter Flare \d", r"<Counter Flare (\d+)> - Remove \1 \[Trinity Counter\]s? from your Reserve\."),
    ("Counter Vortex", r"<Counter Vortex>", r"<Counter Vortex> - Remove 10 \[Trinity Counter\]s from your Reserve\."),
    ("Abyss Gate", r"<Abyss Gate \d", r"<Abyss Gate (\d+)> - Put \1 .+? from your Graveyard into this card's Soul\."),
    ("Alchemy", r"<Alchemy>", r"<Alchemy> - Choose 1 of your \[Equip\] Spells or \[Set\] Spells and destroy it\."),
    ("Gattai", r"<Gattai>", r"<Gattai> \[(?:Set|Shadow|Equip) (\d)\] - Choose \1 Machines .+? and put them into this card's Soul\."),
    ("Trinity Counter reminder", r"\+\d+ \[Trinity Counter\] \(", r"\+(\d+) \[Trinity Counter\] \((?:Add \1 Trinity Counters? to your Reserve|Adds \1 Trinity Counters? to their Reserve)\)"),
    ("Equip cost", r"\[Equip: ", r"\[Equip: [^▶]+\]\. ▶ Equip, unequip, or re-equip\."),
]
PLURAL_NOUNS = ["Unit", "card", "Soul", "Spell", "Trinity Counter", "Machine", "Wall", "Color Card", "damage"]


def glossary_terms(g):
    """All English terms in the glossary, with brackets and 'N'/'X' placeholders removed."""
    terms = set()
    for sec, d in g.items():
        if sec.startswith("_"):
            continue
        for en in d.values():
            for part in re.split(r"\s*/\s*", en):
                terms.add(re.sub(r"[\[\]<>()]", "", part).replace(": X", "").replace(" N", "").strip())
                for inner in re.findall(r"[\[<]([^\]>]+)[\]>]", part):
                    terms.add(tag_base(inner.replace(": X", "").replace(" N", "")))
    return terms


def walk(toks):
    for t in toks:
        yield t
        yield from walk(t.kids)


def validate(cards, glossary, check_images=True):
    terms = glossary_terms(glossary)
    traits = set(glossary["traits"].values())
    rarities = set(glossary["rarities"].values())
    issues = []                                     # (level, card, message)
    canon_hits = collections.defaultdict(list)      # name -> [(card, ok, text)]
    tag_count = collections.Counter()

    def err(c, m): issues.append(("ERROR", c["CardID"], m))
    def warn(c, m): issues.append(("WARN", c["CardID"], m))

    for c in cards:
        cid, ctype = c["CardID"], c["CardType"]
        shadow, spell, unit = "Shadow" in ctype, "Spell" in ctype, "Unit" in ctype
        # ---- schema
        if not re.fullmatch(r"TD0\d_(?:[CUR]_\d{3}|LEG_\d\d|X\d\d)|TD_ACT1_VOID", cid):
            err(c, f"CardID format: {cid}")
        if c["Rarity"] not in rarities: err(c, f"Rarity '{c['Rarity']}' not in glossary")
        if ctype not in CARD_TYPES: err(c, f"CardType '{ctype}' unknown")
        if unit:
            for t in (c["Traits"] or "").split("/"):
                if t not in traits: err(c, f"Trait '{t}' not in glossary")
        elif c["Traits"]:
            err(c, "Spell has Traits")
        cc = c["Color Condition"]
        color = c.get("Color")
        if not re.fullmatch(r"Colorless|(?:Red|Yellow|Blue|Purple)(?:, (?:Red|Yellow|Blue|Purple))*", color or ""):
            err(c, f"Color {color!r}: one or more of Red, Yellow, Blue, Purple (comma separated), or Colorless")
        elif not shadow and cc:
            want = "Colorless" if cc == "Colorless" else ", ".join(p.split()[1] for p in cc.split(", "))
            if color != want: err(c, f"Color {color!r} does not match the Color Condition (expected {want!r})")
        if shadow:
            if cc: err(c, "Shadow card should have no Color Condition")
            if not c["Shadow Condition"]: err(c, "Shadow card without Shadow Condition")
        else:
            if c["Shadow Condition"]: err(c, "Shadow Condition on a non-Shadow card")
            if cc != "Colorless" and not re.fullmatch(r"\d (?:Red|Yellow|Blue|Purple)(?:, \d (?:Red|Yellow|Blue|Purple))*", cc or ""):
                err(c, f"Color Condition format: {cc!r}")
        if cc == "Colorless" and c["FlavorText"] != COLORLESS_NOTE:
            warn(c, f"Colorless card without the Colorless note in FlavorText")
        if not (shadow or isinstance(c["Cost"], int) or c["Cost"] == "X"):
            err(c, f"Cost {c['Cost']!r}")
        if unit and not (isinstance(c["Power"], int) or re.fullmatch(r"\d+\+", str(c["Power"]))):
            err(c, f"Power {c['Power']!r}")
        if c["Rarity"] == "Epic" and not (c["Burst"] or "").startswith("[EPIC Rule] "):
            err(c, "Epic without [EPIC Rule]")
        if c["Burst"] and not re.match(r"\[(Burst|EPIC Rule)\] ", c["Burst"]):
            err(c, "Burst must start with '[Burst] ' or '[EPIC Rule] '")
        segs = segments(c["Card Text"])
        if ctype.endswith("[Shot] Spell") and (not segs or segs[0] != SHOT_NOTE):
            warn(c, "[Shot] Spell does not start with the Shot reminder")
        if ctype.endswith("[Set] Spell") and (not segs or segs[0] != SET_NOTE):
            warn(c, "[Set] Spell does not start with the Set reminder")
        if ctype.endswith("[Equip] Spell") and (not segs or segs[0] != EQUIP_NOTE):
            warn(c, "[Equip] Spell does not start with the Equip reminder")
        if check_images:
            for s in c["_sets"]:
                if not os.path.exists(image_path(c, s)):
                    err(c, f"image missing: {os.path.relpath(image_path(c, s), HERE)}")

        # ---- text
        for f in TEXT_FIELDS:
            t = c.get(f)
            if not t:
                continue
            b = bracket_balance(t)
            if b: err(c, f"{f}: unbalanced bracket {b}")
            for bad, good in DEPRECATED:
                for m in re.finditer(bad, t):
                    err(c, f"{f}: write {good} instead of '{m.group(0)}'")
            for pat, lab in [(r"  ", "double space"), (r" [.,:)]", "space before punctuation"),
                             (r"[a-z]\.[A-Z]", "missing space after '.'"), (r"\.\.", "'..'"),
                             (r"^\s|\s$", "leading/trailing space")]:
                if re.search(pat, t): warn(c, f"{f}: {lab}")
            for noun in PLURAL_NOUNS:
                for m in re.finditer(rf"\b1 {noun}s\b", t):
                    warn(c, f"{f}: '{m.group(0)}' (singular after 1)")
                for m in re.finditer(rf"\b([2-9]|\d\d+) {noun}\b(?!s)(?! [A-Z])", t):
                    if noun == "damage": continue
                    warn(c, f"{f}: '{m.group(0)}' (plural after {m.group(1)}?)")
            for m in re.finditer(r"(\S)\s*▶(?!\.)", t):
                if m.group(1) not in ".":
                    warn(c, f"{f}: no '.' before ▶: …{t[max(0, m.start() - 40):m.end() + 5]}…")
            for tok in walk(tokenize(t)):
                if tok.kind in ("sq", "ang") and not is_descriptive(tok.text):
                    base = tag_base(tok.text)
                    tag_count[("[" if tok.kind == "sq" else "<") + base + ("]" if tok.kind == "sq" else ">")] += 1
                    if base not in terms:
                        err(c, f"{f}: tag {tok.text!r} ('{base}') not in cards/master_glossary.json")
            for name, start, canon in CANON:
                for m in re.finditer(start, t):
                    ok = re.match(canon, t[m.start():])
                    snippet = re.split(r" ▶| / ", t[m.start():])[0][:150]
                    canon_hits[name].append((cid, bool(ok), snippet))
                    if not ok:
                        warn(c, f"{name} wording differs: \"{snippet}\"")
    return issues, canon_hits, tag_count


# ------------------------------------------------------------- style guide --
def humanize(rx):
    """Turn a canonical regex into readable text: (\\d+) / \\1 -> N, s? -> (s), .+? -> …"""
    t = rx.replace(r"(\d+)", "N").replace(r"(\d)", "N").replace(r"\d+", "N").replace(r"\1", "N")
    t = t.replace(".+?", "…").replace("[^▶]+", "…").replace(r"[^\]]+", "X")
    t = re.sub(r"\(\?:\\\[\(\?:Red\|Yellow\|Blue\|Purple\)\\\]\)\+", "[Color]…", t)
    t = re.sub(r"\(\?:([^()]*)\)", r"\1", t).replace("s?", "(s)")
    t = t.replace("\\", "").replace("|", " / ")
    return t


def guide_auto(cards, canon_hits, tag_count):
    """The keyword table in style_guide.md (between the AUTO markers), built from CANON."""
    out = ["<!-- AUTO:START (generated by validate_cards.py --guide) -->", "",
           "| Keyword | Standard wording |", "|---|---|"]
    for name, _, canon in CANON:
        out.append(f"| {name} | `{humanize(canon)}` |")
    out += ["", "<!-- AUTO:END -->"]
    return "\n".join(out)


def write_guide(auto):
    text = open(GUIDE, encoding="utf-8").read()
    text = re.sub(r"<!-- AUTO:START.*?<!-- AUTO:END -->", lambda m: auto, text, flags=re.S)
    open(GUIDE, "w", encoding="utf-8").write(text)


def check_definitions(glossary):
    """Every glossary term (traits excepted) needs a description in glossary_definitions.json,
    and every description must belong to a term that is still in the glossary."""
    if not os.path.exists(DEFINITIONS):
        return [("WARN", "glossary", "glossary_definitions.json not found")]
    defs = json.load(open(DEFINITIONS, encoding="utf-8"))
    out = []
    for section, entries in glossary.items():
        if section.startswith("_"):
            continue
        for en in entries.values():
            if section != "traits" and not defs.get(section, {}).get(en):
                out.append(("WARN", "glossary", f"no definition for {section} / {en}"))
    for section, entries in defs.items():
        if section.startswith("_"):
            continue
        for en in entries:
            if en not in glossary.get(section, {}).values():
                out.append(("WARN", "glossary", f"definition for {section} / {en} has no glossary term"))
    return out


def main(argv):
    cards = load_cards()
    glossary = json.load(open(GLOSSARY, encoding="utf-8"))
    issues, canon_hits, tag_count = validate(cards, glossary, check_images="--no-images" not in argv)
    issues += check_definitions(glossary)
    lines = [f"{lvl:5}  {cid:13} {msg}" for lvl, cid, msg in sorted(issues, key=lambda x: (x[0], x[1]))]
    n_err = sum(1 for i in issues if i[0] == "ERROR")
    n_warn = len(issues) - n_err
    summary = f"{len(cards)} cards checked: {n_err} errors, {n_warn} warnings"
    open(REPORT, "w", encoding="utf-8").write(summary + "\n\n" + "\n".join(lines) + "\n")
    if "--guide" in argv:
        write_guide(guide_auto(cards, canon_hits, tag_count))
    print("\n".join(lines))
    print(summary, "->", os.path.basename(REPORT))
    return 1 if n_err else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
