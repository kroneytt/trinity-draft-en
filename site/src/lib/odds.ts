// Box contents and draft odds for the standard 3-player game.
// A box (one expansion) = 27 packs x 13 cards = 351 cards, with a fixed number of copies of
// each card by rarity. A game opens 9 of the packs (3 per player) = 117 cards.
// The odds treat the box as shuffled together, which is how a reshuffled box (and the
// Tabletop Simulator mod) deals packs.
import { loadCards } from "./cards";

export const COPIES: Record<string, number> = { Legend: 1, Rare: 2, Uncommon: 3, Common: 4, Void: 9 };
export const PACKS_PER_BOX = 27;
export const PACK_SIZE = 13;
export const BOX = PACKS_PER_BOX * PACK_SIZE;        // 351
export const PLAYERS = 3;
export const PACKS_PER_GAME = 9;
export const GAME = PACKS_PER_GAME * PACK_SIZE;       // 117

// log of n choose k, through log-gamma (Lanczos)
function lgamma(x: number): number {
  const g = 7, c = [0.99999999999980993, 676.5203681218851, -1259.1392167224028, 771.32342877765313,
    -176.61502916214059, 12.507343278686905, -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7];
  if (x < 0.5) return Math.log(Math.PI / Math.sin(Math.PI * x)) - lgamma(1 - x);
  x -= 1;
  let a = c[0];
  const t = x + g + 0.5;
  for (let i = 1; i < g + 2; i++) a += c[i] / (x + i);
  return 0.5 * Math.log(2 * Math.PI) + (x + 0.5) * Math.log(t) - t + Math.log(a);
}
const lchoose = (n: number, k: number) => (k < 0 || k > n ? -Infinity : lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1));

/** P(exactly x of the K "special" cards among n drawn from N) */
export const hyper = (N: number, K: number, n: number, x: number) =>
  Math.exp(lchoose(K, x) + lchoose(N - K, n - x) - lchoose(N, n));

/** P(at least one of K copies among n drawn from N) */
export const atLeastOne = (N: number, K: number, n: number) => 1 - hyper(N, K, n, 0);

export interface RarityRow {
  rarity: string; distinct: number; copies: number; inBox: number;
  perPack: number; perGame: number; perPlayer: number;
  oneCardInGame: number;   // a given card (any copy) is in the game
  packHasOne: number;      // a pack has at least one card of this rarity
}

/** Rows per rarity for one expansion (both expansions are built the same way). */
export function rarityRows(): RarityRow[] {
  const blaze = loadCards().filter((c) => c.set === "blaze" || c.set === "shared");
  return ["Legend", "Rare", "Uncommon", "Common", "Void"].map((rarity) => {
    const distinct = blaze.filter((c) => c.Rarity === rarity).length;
    const copies = COPIES[rarity];
    const inBox = distinct * copies;
    return {
      rarity, distinct, copies, inBox,
      perPack: (inBox * PACK_SIZE) / BOX,
      perGame: (inBox * GAME) / BOX,
      perPlayer: (inBox * GAME) / BOX / PLAYERS,
      oneCardInGame: atLeastOne(BOX, copies, GAME),
      packHasOne: atLeastOne(BOX, inBox, PACK_SIZE),
    };
  });
}

/** Distribution of how many cards of a rarity are in one game (P(x) for x = 0..max). */
export function gameDistribution(inBox: number) {
  const rows: { x: number; p: number; atLeast: number }[] = [];
  for (let x = 0; x <= Math.min(inBox, GAME); x++) rows.push({ x, p: hyper(BOX, inBox, GAME, x), atLeast: 0 });
  let tail = 0;
  for (let i = rows.length - 1; i >= 0; i--) { tail += rows[i].p; rows[i].atLeast = Math.min(1, tail); }
  return rows;
}
