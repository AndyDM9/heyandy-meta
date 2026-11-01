"""The examples for "Andy's eyes" on the public demo (screen/eyes.html), for a visitor with no photo to hand: a cup to
show Andy, then one picture of four cups (that cup, from its other side, among look-alikes), and the same without it.

Photos from The Metropolitan Museum of Art's Open Access (CC0: public domain), fetched by object number and put side
by side here. Never a home.

    uv run python scripts/eyes_samples.py      # -> heyandy_meta/screen/eyes/
"""
import io
import json
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "heyandy_meta" / "screen" / "eyes"
API = "https://collectionapi.metmuseum.org/public/collection/v1/objects/"
# object number -> which of its photos (0: the main one); the cup is shown from one side, found from another
YOURS = (2109, 0)  # a porcelain cup with a painted flower spray
OTHER_SIDE = (2109, 2)  # the same cup, from its other side
LOOKALIKES = [(191578, 0), (207670, 0), (385, 0)]  # a floral cup, a black cup, a silver beaker
ALSO = (240140, 0)  # a jug, in the picture without the cup


def photo(obj: int, view: int) -> Image.Image:
    with urllib.request.urlopen(urllib.request.Request(API + str(obj), headers={"User-Agent": "heyandy"}), timeout=30) as r:
        o = json.load(r)
    if not o.get("isPublicDomain"):
        raise SystemExit(f"{obj} isn't public domain")
    url = [o["primaryImageSmall"], *[u.replace("/original/", "/web-large/") for u in o["additionalImages"]]][view]
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "heyandy"}), timeout=60) as r:
        return Image.open(io.BytesIO(r.read())).convert("RGB")


def middle(img: Image.Image, keep: float = 0.86) -> Image.Image:
    w, h = img.size
    return img.crop((round(w * (1 - keep) / 2), round(h * (1 - keep) / 2), round(w * (1 + keep) / 2), round(h * (1 + keep) / 2)))


def collage(things: list[Image.Image], side: int = 1080, gap: int = 14) -> Image.Image:
    """The photos in one picture, two by two, each cut square from its middle: four cups, one photo."""
    cell = (side - 3 * gap) // 2
    out = Image.new("RGB", (side, side), (38, 36, 33))
    for k, img in enumerate(things):
        w, h = img.size
        m = min(w, h)
        sq = img.crop(((w - m) // 2, (h - m) // 2, (w + m) // 2, (h + m) // 2)).resize((cell, cell), Image.LANCZOS)
        out.paste(sq, (gap + (k % 2) * (cell + gap), gap + (k // 2) * (cell + gap)))
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    yours = middle(photo(*YOURS), 0.92)
    yours.thumbnail((720, 720))
    yours.save(OUT / "cup.webp", "WEBP", quality=86)
    look = [photo(*o) for o in LOOKALIKES]
    collage([look[0], look[1], photo(*OTHER_SIDE), look[2]]).save(OUT / "cups.webp", "WEBP", quality=84)
    collage([look[0], look[1], photo(*ALSO), look[2]]).save(OUT / "cups-without.webp", "WEBP", quality=84)
    (OUT / "CREDITS.txt").write_text(
        "Photos: The Metropolitan Museum of Art, Open Access (CC0, public domain), object numbers "
        + ", ".join(str(o) for o, _ in [YOURS, *LOOKALIKES, ALSO]) + " (metmuseum.org/art/collection/search/<number>).\n"
        "Put side by side by scripts/eyes_samples.py.\n")
    for f in sorted(OUT.glob("*.webp")):
        print(f, f.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
