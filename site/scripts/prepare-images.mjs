// Copies the finished card images from ../out/tts into public/img and makes small WebP
// thumbnails for the card list. Nothing here is committed: it runs before every build.
//   public/img/<set>/<CardID>.jpg     744x1039, the same file the Tabletop Simulator mod uses
//   public/img/<set>/t/<CardID>.webp  480 px wide thumbnail
import fs from "node:fs";
import path from "node:path";
import sharp from "sharp";

const ROOT = path.resolve(import.meta.dirname, "..", "..");
const SRC = path.join(ROOT, "out", "tts");
const DST = path.resolve(import.meta.dirname, "..", "public", "img");
const THUMB_W = 480;

let copied = 0, thumbs = 0;
for (const set of ["blaze", "phantom", "shared", "singularity"]) {   // singularity: the Hole cards
  const dir = path.join(SRC, set);
  if (!fs.existsSync(dir)) { console.error(`missing ${dir}`); process.exit(1); }
  fs.mkdirSync(path.join(DST, set, "t"), { recursive: true });
  for (const f of fs.readdirSync(dir).filter((f) => f.endsWith(".jpg"))) {
    const src = path.join(dir, f);
    const mtime = fs.statSync(src).mtimeMs;
    const big = path.join(DST, set, f);
    const small = path.join(DST, set, "t", f.replace(/\.jpg$/, ".webp"));
    if (!fs.existsSync(big) || fs.statSync(big).mtimeMs < mtime) { fs.copyFileSync(src, big); copied++; }
    if (!fs.existsSync(small) || fs.statSync(small).mtimeMs < mtime) {
      await sharp(src).resize({ width: THUMB_W }).webp({ quality: 80 }).toFile(small);
      thumbs++;
    }
  }
}
console.log(`card images: ${copied} copied, ${thumbs} thumbnails made (public/img)`);
