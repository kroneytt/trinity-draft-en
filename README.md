# Trinity Draft — English

An unofficial, fan-made English translation of **[Trinity Draft](https://trinitydraft.com/)**, a Japanese trading card game for three players built around a booster draft.

**Browse the cards: <https://kroneytt.github.io/trinity-draft-en/>**

This repo contains:
- the **English card database**,
- the **translated card images**,
- the **overlay tool** that turns the original Japanese cards into English ones,
- the **card database website** (search, filters, glossary, box and draft odds).

> Trinity Draft and all card art, names and rules © 2025 Mikiseishindo / AsobiDays. This project is not affiliated with the publisher. See [NOTICE.md](NOTICE.md).

| Expansion | Code | Cards |
|---|---|---|
| Blaze | TD-01 | 126 + VOID |
| Phantom | TD-02 | 126 + VOID |

Each expansion has 102 draft cards (Common / Uncommon / Rare), 20 Legends and 4 Epics. The VOID card is shared by both sets.

---

## Play it in Tabletop Simulator

The English Trinity Draft mod for Tabletop Simulator is on the **Steam Workshop** *(link coming soon)*. It uses the card images from this repo.

## Card database

[`cards/blaze_database.json`](cards/blaze_database.json) and [`cards/phantom_database.json`](cards/phantom_database.json) are the source of truth. Every card image is generated from them.

```json
{
  "CardID": "TD01_C_067",
  "Japanese Name": "赤眼竜オロチ",
  "English Name": "Red-Eyed Dragon, Orochi",
  "Rarity": "Common",
  "CardType": "Unit",
  "Traits": "Dragon/Beast",
  "Color": "Red",
  "Color Condition": "1 Red",
  "Cost": 6,
  "Shadow Condition": null,
  "Power": 6000,
  "Break": 3,
  "Burst": null,
  "Card Text": "[Continuous] All your Units on the Battlefield that have Souls gain [Quick Aura]. … / [Shinra Summon 6] …",
  "FlavorText": null
}
```

- **`Color`:** the card's own color (what it gives when used for Color Charge), e.g. `Red`, `Red, Yellow` or `Colorless`. Shadow cards have a Color but no Color Condition.
- **`Card Text`:** abilities are separated by ` / `.
- **`Burst`:** starts with `[Burst]`, or with `[EPIC Rule]` on Epic cards.
- **Terminology:** follows [`cards/master_glossary.json`](cards/master_glossary.json) (Japanese → English), with a short rules description of each term in [`cards/glossary_definitions.json`](cards/glossary_definitions.json).
- **Wording conventions:** in [`cards/style_guide.md`](cards/style_guide.md).


## Card images

| Folder | Contents |
|---|---|
| `out/tts/blaze/`, `out/tts/phantom/`, `out/tts/shared/` | every card with the English overlay, `<CardID>.jpg`, 744×1039 (63×88 mm at 300 dpi) |
| `out/tts/singularity/` | the Singularity Hole cards (α, β, the 8 special β Holes and "β Hole" Genesis), same size |
| `out/tts/card_back.jpg` | card back |
| `images/` | table, playmat and game components (Reserve, Singularity Reserve, Walls, Basic Color Cards, Trinity Counter) |

These are the images the Tabletop Simulator mod loads, so keep their paths unchanged.

## Overlay tool

You need Python 3.10+ and `pip install -r tools/requirements.txt`. The original Japanese card art is not included. The tool expects it as `cards/blaze_cards_hq/TD-01_C067.webp`, `cards/phantom_cards_hq/TD-02_C067.webp`, and so on, for each card.

| Step | Command | Result |
|---|---|---|
| 1. Check the data | `python tools/validate_cards.py` | report of errors and wording differences (`--guide` refreshes the keyword table in `cards/style_guide.md`) |
| 2. Render | `python tools/render_cards.py` | `out/master/`: full-resolution English cards, lossless (`--check-fit` checks text fit without the art) |
| 3. Export | `python tools/export_cards.py` | `out/tts/` JPG cards, plus `out/web/` AVIF/WebP images for websites |

To change or fix a translation: edit the JSON, then run steps 1 → 3.

**Singularity Holes.** `cards/singularity_database.json` holds the Hole cards. Cut the Japanese cards out of the official print sheet once with `python tools/render_holes.py --extract singularity-addition.pdf` (needs `pip install pypdf`), then `python tools/render_holes.py` writes `out/tts/singularity/` and `images/components/singularity_reserve_en.jpg`.

## Rulebooks

English rulebooks for every official format, in [`rules/`](rules/):

| Format | File |
|---|---|
| Trinity Draft (Standard 3-Player) | [`rules/three-player.md`](rules/three-player.md) |
| DUEL (2-Player) | [`rules/duel.md`](rules/duel.md) |
| Singularity (Quick 3-Player) | [`rules/singularity.md`](rules/singularity.md) |
| Unite (two boxes combined) | [`rules/unite.md`](rules/unite.md) |

They are unofficial translations. Where they disagree with the official Japanese rules, the official rules are correct.

## Website

The site in `site/` is built from `cards/*.json`, the rulebooks in `rules/` and the images in `out/tts/`, so a fix to the JSON shows up on the site at the next release. It is published to GitHub Pages only when a Release is published (or by hand from the Actions tab), never on an ordinary push.

To preview it on your computer (Node.js 22.22 or newer):

```
cd site
npm install
npm run dev
```

## Folder layout

```
cards/                card database (JSON), singularity_database.json (Hole cards), master_glossary.json (Japanese → English terms),
                      glossary_definitions.json (what each term means),
                      style_guide.md (how the English card text is worded)
rules/                English rulebooks: Standard, DUEL, Singularity, Unite
images/               table, playmat, card back and game components
out/tts/              finished English card images
tools/                overlay tool: validate_cards, render_cards, render_holes, export_cards, card_data (shared loader)
tools/fonts/          Inter (SIL OFL) used for the English overlay
site/                 card database and rulebook website (Astro)
```

## Credits

- **Game:** Trinity Draft by Mikiseishindo / AsobiDays. Please support the official release.
- **Translation, tools and TTS mod:** kroneytt.
- **Font:** Inter by Rasmus Andersson (SIL Open Font License).
