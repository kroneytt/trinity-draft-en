// Reads the card database (../cards/*.json) at build time.
// The JSON files are the source of truth; nothing here changes wording.
import fs from "node:fs";
import path from "node:path";

const CARDS_DIR = path.resolve(process.cwd(), "..", "cards");

export interface RawCard {
  CardID: string;
  "Japanese Name": string;
  "English Name": string;
  Rarity: string;
  CardType: string;
  Traits: string | null;
  Color: string;            // the card's own color: "Red", "Red, Yellow", "Colorless"
  "Color Condition": string | null;
  Cost: number | string | null;
  "Shadow Condition": string | null;
  Power: number | null;
  Break: number | null;
  Burst: string | null;
  "Card Text": string | null;
  FlavorText: string | null;
}

export interface Card extends RawCard {
  id: string;
  set: "blaze" | "phantom" | "shared";
  setCode: string;          // TD-01 / TD-02 / TD
  setName: string;          // Blaze / Phantom / Blaze & Phantom
  number: string;           // printed number, e.g. "C 067/102"
  numberKey: number;        // order in the printed list
  rarityRank: number;       // 0 = Epic ... 5 = Void
  colors: { n: number; color: string }[];   // parsed Color Condition
  colorKeys: string[];      // parsed Color: Red / Yellow / Blue / Purple / Colorless
  traits: string[];
  abilities: string[];      // Card Text split on " / "
  image: string;            // relative to the site root
  thumb: string;
}

export const SETS = [
  { key: "blaze", code: "TD-01", name: "Blaze" },
  { key: "phantom", code: "TD-02", name: "Phantom" },
] as const;

export const RARITIES = ["Epic", "Legend", "Rare", "Uncommon", "Common", "Void"];
export const COLORS = ["Red", "Yellow", "Blue", "Purple"];
export const TYPES = [
  "Unit", "[Shot] Spell", "[Set] Spell", "[Equip] Spell",
  "Shadow Unit", "Shadow [Shot] Spell", "Shadow [Equip] Spell",
];

/** Split card text into abilities on " / " (never inside brackets). */
export function segments(text: string | null): string[] {
  if (!text) return [];
  const out: string[] = [];
  let depth = 0, cur = "";
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if ("[<(".includes(ch)) depth++;
    else if ("]>)".includes(ch)) depth = Math.max(0, depth - 1);
    if (depth === 0 && text.startsWith(" / ", i)) { out.push(cur.trim()); cur = ""; i += 2; continue; }
    cur += ch;
  }
  if (cur.trim()) out.push(cur.trim());
  return out;
}

function parseColors(cond: string | null) {
  if (!cond || cond === "Colorless" || cond === "None") return [];
  return cond.split(",").map((p) => {
    const m = p.trim().match(/^(\d+) (Red|Yellow|Blue|Purple)$/);
    return m ? { n: Number(m[1]), color: m[2] } : { n: 0, color: p.trim() };
  });
}

function numbering(id: string): { number: string; key: number } {
  if (id === "TD_ACT1_VOID") return { number: "ACT1 VOID", key: 900 };
  let m = id.match(/^TD\d\d_(C|U|R)_(\d+)$/);
  if (m) return { number: `${m[1]} ${m[2]}/102`, key: Number(m[2]) };
  m = id.match(/^TD\d\d_LEG_(\d+)$/);
  if (m) return { number: `LEG ${m[1]}/20`, key: 200 + Number(m[1]) };
  m = id.match(/^TD\d\d_X(\d+)$/);
  if (m) return { number: `X${m[1]}/04`, key: 300 + Number(m[1]) };
  return { number: id, key: 999 };
}

let cache: Card[] | null = null;

/** All cards, in the default order: rarity (Epic first), then set, then card number. */
export function loadCards(): Card[] {
  if (cache) return cache;
  const seen = new Map<string, Card>();
  for (const s of SETS) {
    const raw: RawCard[] = JSON.parse(fs.readFileSync(path.join(CARDS_DIR, `${s.key}_database.json`), "utf8"));
    for (const r of raw) {
      if (seen.has(r.CardID)) continue;                       // VOID is listed in both files
      const shared = r.CardID === "TD_ACT1_VOID";
      const set = shared ? "shared" : s.key;
      const colors = parseColors(r["Color Condition"]);
      const colorKeys = (r.Color || "").split(",").map((s) => s.trim()).filter(Boolean);
      const { number, key } = numbering(r.CardID);
      seen.set(r.CardID, {
        ...r,
        id: r.CardID,
        set,
        setCode: shared ? "TD" : s.code,
        setName: shared ? "Blaze & Phantom" : s.name,
        number,
        numberKey: key,
        rarityRank: RARITIES.indexOf(r.Rarity),
        colors,
        colorKeys,
        traits: r.Traits ? r.Traits.split("/") : [],
        abilities: segments(r["Card Text"]),
        image: `img/${set}/${r.CardID}.jpg`,
        thumb: `img/${set}/t/${r.CardID}.webp`,
      });
    }
  }
  const setRank = (c: Card) => (c.set === "phantom" ? 1 : c.set === "shared" ? 2 : 0);
  cache = [...seen.values()].sort(
    (a, b) => a.rarityRank - b.rarityRank || setRank(a) - setRank(b) || a.numberKey - b.numberKey,
  );
  return cache;
}

/** Short rules descriptions: { section: { English term: description } } */
export function loadDefinitions(): Record<string, Record<string, string>> {
  return JSON.parse(fs.readFileSync(path.join(CARDS_DIR, "glossary_definitions.json"), "utf8"));
}

export function loadGlossary(): Record<string, Record<string, string>> {
  return JSON.parse(fs.readFileSync(path.join(CARDS_DIR, "master_glossary.json"), "utf8"));
}

/** Everything a search should match: names, text, traits, type. */
export function searchText(c: Card): string {
  return [c["English Name"], c["Japanese Name"], c.id, c.number, c.CardType, c.Traits,
    c["Card Text"], c.Burst, c["Shadow Condition"], c.FlavorText].filter(Boolean).join(" \n ").toLowerCase();
}
