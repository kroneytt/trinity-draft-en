// Card text -> HTML. Same rules as tools/card_data.py (bracket-aware) and the colours of
// tools/render_cards.py, so the website reads like the printed English overlay.
import { loadGlossary } from "./cards";

type Tok = { kind: "word" | "space" | "arrow" | "sq" | "ang" | "par"; text: string; kids: Tok[] };
const PAIRS: Record<string, string> = { "[": "]", "<": ">", "(": ")" };

function matchClose(text: string, i: number): number {
  const stack = [PAIRS[text[i]]];
  for (let j = i + 1; j < text.length; j++) {
    const ch = text[j];
    if (ch in PAIRS && !(ch === "<" && text[j + 1] === " ")) stack.push(PAIRS[ch]);
    else if (stack.length && ch === stack[stack.length - 1]) {
      stack.pop();
      if (!stack.length) return j;
    }
  }
  return -1;
}

export function tokenize(text: string): Tok[] {
  const toks: Tok[] = [];
  let word = "";
  const flush = () => { if (word) { toks.push({ kind: "word", text: word, kids: [] }); word = ""; } };
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch in PAIRS) {
      const j = matchClose(text, i);
      if (j > 0) {
        flush();
        const inner = text.slice(i + 1, j);
        const kind = ({ "[": "sq", "<": "ang", "(": "par" } as const)[ch as "[" | "<" | "("];
        toks.push({ kind, text: inner, kids: tokenize(inner) });
        i = j;
        continue;
      }
    }
    if (/\s/.test(ch)) {
      flush();
      if (!toks.length || toks[toks.length - 1].kind !== "space") toks.push({ kind: "space", text: " ", kids: [] });
    } else if (ch === "▶") {
      flush();
      toks.push({ kind: "arrow", text: "▶", kids: [] });
    } else word += ch;
  }
  flush();
  return toks;
}

export const tagBase = (inner: string) => inner.split(":")[0].trim().replace(/\s+\d+$/, "");
const isDescriptive = (inner: string) =>
  !/^[A-Z][A-Za-z]*(?: [A-Z][A-Za-z]*)*(?: \d+)?$/.test(inner.split(":")[0].trim());

export const esc = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

export const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

// ------------------------------------------------------------------ glossary lookup --
export interface Term { jp: string; en: string; section: string; key: string }

/** "[Shinra Summon N]" -> "shinra summon", "<Soul Flare>" -> "soul flare", "(X/Turn)" -> "x/turn" */
export function termKey(en: string): string {
  let s = en.trim().replace(/^[[<(]|[\]>)]$/g, "");
  s = s.split(":")[0].trim().replace(/\s+(N|X|\d+)$/, "");
  return s.toLowerCase();
}

/** Glossary sections in page order: [json key, heading, intro] */
export const SECTIONS: [string, string, string][] = [
  ["timings", "Timings", "The icon at the start of an ability says when it happens or can be used."],
  ["keywords", "Keywords", "Named abilities. N is a number printed on each card; X is the condition written after the colon."],
  ["auras", "Auras", "Abilities a Unit has that change how it attacks or battles."],
  ["actions_states", "Actions and states", "Words the card text uses for what happens to cards and Walls."],
  ["mechanics", "Rules terms", "Game rules that card text refers to."],
  ["zones", "Zones", "The areas of the table."],
  ["card_types", "Card types", ""],
  ["attributes", "Card parts", "What the numbers and fields printed on a card mean."],
  ["stages", "Stages and phases", "A game has three stages; each turn of the Battle has these phases in order."],
  ["traits", "Traits", "Unit Traits. The number shows how many cards have the Trait."],
  ["colors", "Colors", "The number shows how many cards are that color."],
  ["rarities", "Rarities", "Copies per box are for one expansion's box of 27 packs."],
];

let terms: Map<string, Term> | null = null;
/** key -> the first glossary entry (in page order) with that English term; its row has the anchor */
export function glossaryTerms(): Map<string, Term> {
  if (terms) return terms;
  terms = new Map();
  const g = loadGlossary();
  for (const [section] of SECTIONS) {
    for (const [jp, en] of Object.entries(g[section] ?? {})) {
      const key = termKey(en);
      if (!terms.has(key)) terms.set(key, { jp, en, section, key });
    }
  }
  return terms;
}

// ------------------------------------------------------------------ styling classes --
const TIMING = new Set(["On Entry", "On Attack", "On Destroy", "Trigger", "Activate", "Continuous",
  "Graveyard Activate", "Oni Charge", "Jigoku Back", "Equip Cost", "Burst", "On Reveal"]);   // On Reveal: Singularity Holes
const GOLD = new Set(["Shinra Summon", "Reduced Summon", "Zero Summon", "Color Shift", "EPIC Rule"]);

function chipClass(base: string): string {
  if (TIMING.has(base)) return `chip t-${slug(base)}`;
  if (/ Aura$/.test(base)) return `chip a-${slug(base)}`;
  if (GOLD.has(base)) return "chip gold";
  return "kw";
}

function withTerm(html: string, base: string, root: string | null): string {
  if (root === null) return html;
  const t = glossaryTerms().get(base.toLowerCase());
  if (!t) return html;
  return `<a class="term" href="${root}glossary.html#${slug(t.key)}" data-jp="${esc(t.jp)}">${html}</a>`;
}

const hidden = (s: string) => `<span class="vh">${esc(s)}</span>`;

// root === null: inside a link already, so no nested glossary links
function render(toks: Tok[], root: string | null): string {
  let out = "";
  toks.forEach((t, i) => {
    switch (t.kind) {
      case "word": out += esc(t.text); break;
      case "space": out += " "; break;
      case "arrow": {
        const next = toks.slice(i + 1).find((k) => k.kind !== "space");
        const inline = next && next.kind === "word" && next.text.startsWith(".");
        out += (inline || i === 0 ? "" : '<span class="br"></span>') + '<span class="arrow">▶</span>';
        break;
      }
      case "par": out += `<span class="par">(${render(t.kids, root)})</span>`; break;
      case "ang": {
        const base = tagBase(t.text);
        out += withTerm(`<span class="kw ang">&lt;${render(t.kids, null)}&gt;</span>`, base, root);
        break;
      }
      case "sq": {
        if (isDescriptive(t.text)) { out += `<span class="phrase">[${render(t.kids, root)}]</span>`; break; }
        const base = tagBase(t.text);
        const cls = chipClass(base);
        const colon = t.text.indexOf(":");
        // a long "[Equip: ...]" style tag: chip for the name, normal text for the rest
        if (colon > 0 && t.text.length - colon > 26) {
          const head = t.text.slice(0, colon);
          const rest = t.text.slice(colon + 1).trim();
          out += withTerm(`<span class="${cls}">${hidden("[")}${esc(head)}:</span>`, base, root) +
            " " + render(tokenize(rest), root) + hidden("]");
        } else if (cls === "kw") {
          out += withTerm(`<span class="kw">[${render(t.kids, null)}]</span>`, base, root);
        } else {
          out += withTerm(`<span class="${cls}">${hidden("[")}${render(t.kids, null)}${hidden("]")}</span>`, base, root);
        }
        break;
      }
    }
  });
  return out;
}

/** One ability (or the Burst / Epic Rule line) as HTML. root = relative path to the site root. */
export function cardTextHtml(text: string, root: string | null = ""): string {
  return render(tokenize(text), root);
}
