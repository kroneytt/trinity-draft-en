// The rulebooks in ../rules/, in the order (and with the names) of the tabs in the rulebook doc.
export const FORMATS = [
  {
    key: "three-player", page: "rulebook", label: "Trinity Draft", players: "Standard 3-Player",
    title: "Rulebook (Standard 3-Player)",
    description: "The complete Trinity Draft rules for the standard 3-player game: Draft, Build, Battle, combat and detailed rules.",
  },
  {
    key: "duel", page: "rulebook-duel", label: "DUEL", players: "2-Player",
    title: "DUEL Rulebook (2-Player)",
    description: "Trinity Draft DUEL, the official 2-player rules: the DUEL Draft, Long and Short Walls, banned cards and what changes from the Standard game.",
  },
  {
    key: "singularity", page: "rulebook-singularity", label: "Singularity", players: "Quick 3-Player",
    title: "Singularity Rulebook (Quick 3-Player)",
    description: "Trinity Draft: Singularity, the quick 3-player variant with 10-card Decks, 8 Life cards and Holes.",
  },
  {
    key: "unite", page: "rulebook-unite", label: "Unite", players: "",
    title: "Unite Rulebook",
    description: "Trinity Draft Unite: drafting from two boxes at once, with 702 Draft Cards and 8 Epics to choose from.",
  },
] as const;
