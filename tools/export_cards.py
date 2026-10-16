"""
Trinity Draft - export rendered cards for TTS and the web
=========================================================

    python tools/export_cards.py                 everything in out/master
    python tools/export_cards.py TD01_C_067      only some cards
    python tools/export_cards.py --tts-width 1024

Reads   out/master/<set>/<CardID>.webp     (made by render_cards.py, lossless, transparent corners)
        images/card_back_hd.jpg
Writes  out/tts/<set>/<CardID>.jpg         744x1039 JPEG q90, 4:4:4 colour (no chroma blur on red text).
                                           One image per card, the same way the old TTS save loaded
                                           them (CustomDeck NumWidth/NumHeight = 1). TTS can't load
                                           WebP/AVIF, so JPEG it is.
        out/tts/card_back.jpg              the card back at the same size
        out/web/<set>/<CardID>.avif        1000 px wide, AVIF q80 4:4:4, corners kept transparent
                                           (falls back to WebP q88 if this Pillow has no AVIF)
        out/web/<set>/thumb/<CardID>.webp  360 px wide thumbnail for the card list
        out/export_report.txt              sizes per folder

Shared cards (VOID) are written to out/tts/shared and out/web/shared.
"""
import os, sys, glob
from PIL import Image, features

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # project root
OUT = os.path.join(HERE, "out")
MASTER = os.path.join(OUT, "master")
RATIO = 3520 / 2520


def fill_corners(img):
    """JPEG has no transparency: fill the transparent rounded corners with the colour of the
    nearby frame instead of black/white, so TTS's own rounded card edge looks clean."""
    small = img.resize((max(1, img.width // 24), max(1, img.height // 24)), Image.BOX)
    bg = small.resize(img.size, Image.BILINEAR)
    bg.putalpha(255)
    bg.alpha_composite(img)
    return bg.convert("RGB")


def export_one(args):
    path, tts_w, web_w, thumb_w, avif = args
    folder = os.path.basename(os.path.dirname(path))
    cid = os.path.splitext(os.path.basename(path))[0]
    im = Image.open(path).convert("RGBA")
    out = []
    # TTS
    d = os.path.join(OUT, "tts", folder); os.makedirs(d, exist_ok=True)
    t = im.resize((tts_w, round(tts_w * RATIO)), Image.LANCZOS)
    p = os.path.join(d, cid + ".jpg")
    fill_corners(t).save(p, "JPEG", quality=90, subsampling=0, optimize=True, progressive=True)
    out.append(p)
    # web full size
    d = os.path.join(OUT, "web", folder); os.makedirs(d, exist_ok=True)
    w = im.resize((web_w, round(web_w * RATIO)), Image.LANCZOS)
    if avif:
        p = os.path.join(d, cid + ".avif")
        w.save(p, "AVIF", quality=80, subsampling="4:4:4", speed=6)
    else:
        p = os.path.join(d, cid + ".webp")
        w.save(p, "WEBP", quality=88, method=5)
    out.append(p)
    # web thumbnail
    d = os.path.join(OUT, "web", folder, "thumb"); os.makedirs(d, exist_ok=True)
    p = os.path.join(d, cid + ".webp")
    im.resize((thumb_w, round(thumb_w * RATIO)), Image.LANCZOS).save(p, "WEBP", quality=80, method=5)
    out.append(p)
    return out


def folder_size(pattern):
    fs = glob.glob(pattern, recursive=True)
    return len(fs), sum(os.path.getsize(f) for f in fs) / 1024 / 1024


def main(argv):
    ids = [a for a in argv if not a.startswith("--")]
    opts = {}
    for i, a in enumerate(argv):
        if a.startswith("--") and i + 1 < len(argv) and not argv[i + 1].startswith("--"):
            opts[a] = argv[i + 1]
    ids = [a for a in ids if a not in opts.values()]
    tts_w = int(opts.get("--tts-width", 744))
    web_w = int(opts.get("--web-width", 1000))
    thumb_w = int(opts.get("--thumb-width", 360))
    jobs = int(opts.get("--jobs", max(1, (os.cpu_count() or 2) - 1)))
    avif = features.check("avif")
    if not avif:
        print("This Pillow has no AVIF support (pip install -U pillow) - web images will be WebP.")

    masters = sorted(glob.glob(os.path.join(MASTER, "*", "*.webp")))
    if ids:
        masters = [m for m in masters if os.path.splitext(os.path.basename(m))[0] in ids]
    if not masters:
        print("Nothing in out/master - run render_cards.py first."); return 1

    back = os.path.join(HERE, "images", "card_back_hd.jpg")
    if os.path.exists(back):
        os.makedirs(os.path.join(OUT, "tts"), exist_ok=True)
        Image.open(back).convert("RGB").resize((tts_w, round(tts_w * RATIO)), Image.LANCZOS).save(
            os.path.join(OUT, "tts", "card_back.jpg"), "JPEG", quality=90, subsampling=0, optimize=True)

    todo = [(m, tts_w, web_w, thumb_w, avif) for m in masters]
    print(f"exporting {len(todo)} cards with {jobs} worker(s) ...")
    if jobs > 1 and len(todo) > 1:
        from multiprocessing import Pool
        with Pool(jobs) as pool:
            for _ in pool.imap_unordered(export_one, todo):
                pass
    else:
        for t in todo:
            export_one(t)

    lines = [f"tts width {tts_w}, web width {web_w} ({'AVIF' if avif else 'WebP'}), thumbs {thumb_w}", ""]
    for lab, pat in [("TTS jpg", "tts/*/*.jpg"), ("web full", "web/*/*.*"), ("web thumbs", "web/*/thumb/*.webp")]:
        n, mb = folder_size(os.path.join(OUT, pat))
        lines.append(f"{lab:11} {n:4} files  {mb:7.1f} MB  (avg {mb * 1024 / max(n, 1):.0f} KB)")
    open(os.path.join(OUT, "export_report.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
