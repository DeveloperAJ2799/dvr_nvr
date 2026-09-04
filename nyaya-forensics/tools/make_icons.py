"""Generate the Tauri icon set referenced by src-tauri/tauri.conf.json.

Produces (in src-tauri/icons/): 32x32.png, 128x128.png, 128x128@2x.png,
icon.ico. The icon is a simple navy "scale of justice" tile — placeholder
until the team ships real branding.

Usage: python tools/make_icons.py
"""
import os
from PIL import Image, ImageDraw

OUT = os.path.join("src-tauri", "icons")
NAVY = (15, 23, 42)
BLUE = (30, 58, 138)
GOLD = (147, 197, 253)


def draw_icon(size):
    img = Image.new("RGBA", (size, size), NAVY)
    d = ImageDraw.Draw(img)
    # vertical beam
    bw = max(3, size // 32)
    x0 = size // 2 - bw // 2
    d.rectangle([x0, int(size * 0.18), x0 + bw, int(size * 0.82)], fill=GOLD)
    # horizontal crossbar
    d.rectangle([int(size * 0.1), int(size * 0.36), int(size * 0.9),
                 int(size * 0.36) + bw], fill=GOLD)
    # three point markers (camera lenses)
    for fy in (0.42, 0.62, 0.82):
        r = int(size * 0.05)
        cx = int(size * fy)
        d.ellipse([cx - r, int(size * 0.30) - r, cx + r, int(size * 0.30) + r],
                  fill=GOLD)
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    base = draw_icon(1024)
    base.resize((32, 32)).save(os.path.join(OUT, "32x32.png"))
    base.resize((128, 128)).save(os.path.join(OUT, "128x128.png"))
    base.resize((256, 256)).save(os.path.join(OUT, "128x128@2x.png"))
    base.resize((256, 256)).save(os.path.join(OUT, "icon.png"))
    ico = Image.new("RGBA", (256, 256), NAVY)
    ico.paste(base.resize((256, 256)))
    ico.save(os.path.join(OUT, "icon.ico"),
             sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128),
                    (256, 256)])
    print("icons written to", OUT)


if __name__ == "__main__":
    main()