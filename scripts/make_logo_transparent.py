"""Strip the dark navy background from the UAP Explorer logo.

Reads frontend/public/uap-explorer-logo.png, converts pixels whose RGB
luminance is below a threshold to fully transparent, and writes the result
back to the same path.
"""
from pathlib import Path
from PIL import Image

SRC = Path(__file__).resolve().parents[1] / "frontend" / "public" / "uap-explorer-logo.png"
LUMA_THRESHOLD = 55  # pixels darker than this become transparent
FEATHER = 25         # pixels with luma in [THRESHOLD, THRESHOLD+FEATHER) get partial alpha

def luma(r: int, g: int, b: int) -> float:
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def main() -> None:
    im = Image.open(SRC).convert("RGBA")
    w, h = im.size
    px = im.load()
    cleared = 0
    feathered = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            l = luma(r, g, b)
            if l < LUMA_THRESHOLD:
                px[x, y] = (r, g, b, 0)
                cleared += 1
            elif l < LUMA_THRESHOLD + FEATHER:
                # smooth ramp 0..255 across the feather range
                t = (l - LUMA_THRESHOLD) / FEATHER
                new_a = int(round(a * t))
                px[x, y] = (r, g, b, new_a)
                feathered += 1
    im.save(SRC, format="PNG")
    total = w * h
    print(f"Saved {SRC}")
    print(f"  size: {w}x{h} ({total} px)")
    print(f"  fully transparent: {cleared} ({cleared*100/total:.1f}%)")
    print(f"  feathered:         {feathered} ({feathered*100/total:.1f}%)")

if __name__ == "__main__":
    main()
