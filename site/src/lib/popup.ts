// Card popups outside the card list (the rulebook pages): everything the dialog shows,
// with the stats and card text already turned into HTML at build time.
import fs from "node:fs";
import path from "node:path";
import { loadCards, segments, type Card } from "./cards";
import { cardTextHtml } from "./text";

export interface PopupCard {
  id: string;
  name: string;
  jp: string;
  meta: string;
  type: string;
  stats: string;            // HTML
  traits: string[];
  text: string[];           // HTML per ability
  extra: string | null;     // Burst / rule box, HTML
  extraClass: string;
  img: string;
  thumb: string;
  library: boolean;         // true = also in the card list (index.html?card=ID)
}

const esc = (s: unknown) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const stat = (label: string, value: string, cls = "") => `<div class="stat ${cls}"><span>${label}</span><b>${value}</b></div>`;
const dots = (list: { color: string; label: string }[], cls: string) =>
  list.map((x) => `<span class="cv"><i class="dot ${cls} ${x.color.toLowerCase()}"></i>${esc(x.label)}</span>`).join("");

export function cardPopup(c: Card): PopupCard {
  let s = stat("Color", dots(c.colorKeys.map((x) => ({ color: x, label: x })), ""));
  if (c["Shadow Condition"]) s += stat("Shadow Condition", esc(c["Shadow Condition"]), "wide");
  else {
    s += stat("Cost", esc(c.Cost ?? "–"));
    s += stat("Color Condition", c["Color Condition"] === "Colorless"
      ? dots([{ color: "Colorless", label: "Colorless" }], "dia")
      : dots(c.colors.map((x) => ({ color: x.color, label: `${x.n} ${x.color}` })), "dia"));
  }
  if (c.Power !== null) s += stat("Power", esc(c.Power));
  if (c.Break !== null) s += stat("Break", esc(c.Break));
  return {
    id: c.id, name: c["English Name"], jp: c["Japanese Name"],
    meta: `${c.setCode} ${c.number} · ${c.Rarity} · ${c.setName}`,
    type: c.CardType.replace(/\[|\]/g, ""),
    stats: s, traits: c.traits,
    text: c.abilities.map((a) => cardTextHtml(a)),
    extra: c.Burst ? cardTextHtml(c.Burst) : null, extraClass: "burst",
    img: c.image, thumb: c.thumb, library: true,
  };
}

interface RawHole {
  CardID: string; "Japanese Name": string; "English Name": string; CardType: string; Traits: string | null;
  Cost: number; Power: number | null; Break: number | null; Overdrive: number | null;
  "Card Text": string; "Rule Text": string | null;
}

/** The Singularity Holes (cards/singularity_database.json). They are not part of the card list. */
export function holePopups(): PopupCard[] {
  const raw: RawHole[] = JSON.parse(fs.readFileSync(path.resolve(process.cwd(), "..", "cards", "singularity_database.json"), "utf8"));
  return raw.map((h, i) => {
    let s = stat("Cost", esc(h.Cost)) + stat("Color Condition", "None");
    if (h.Overdrive !== null) s += stat("Overdrive modifier", `+${h.Overdrive}`);
    if (h.Power !== null) s += stat("Power", esc(h.Power));
    if (h.Break !== null) s += stat("Break", esc(h.Break));
    return {
      id: h.CardID, name: h["English Name"], jp: h["Japanese Name"],
      meta: `Singularity Vol. 1 · ${h.CardType === "Hole" ? "Hole" : "Hole (Unit)"} · ${i + 1}/${raw.length}`,
      type: h.CardType,
      stats: s, traits: h.Traits ? h.Traits.split("/") : [],
      text: segments(h["Card Text"]).map((a) => cardTextHtml(a)),
      extra: h["Rule Text"] ? esc(h["Rule Text"]) : null, extraClass: "flavor",
      img: `img/singularity/${h.CardID}.jpg`, thumb: `img/singularity/t/${h.CardID}.webp`, library: false,
    };
  });
}

/** Every card a rulebook can show, by ID. */
export function popupIndex(): Map<string, PopupCard> {
  const m = new Map<string, PopupCard>();
  for (const c of loadCards()) m.set(c.id, cardPopup(c));
  for (const h of holePopups()) m.set(h.id, h);
  return m;
}
