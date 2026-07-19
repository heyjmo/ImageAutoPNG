"""
Generate branded assets with Pillow (exact text — not AI image models):

  assets/jmo_logo.png          — installer banner / about logo
  assets/app_icon.ico          — multi-size Windows icon for the .exe
  assets/app_icon_256.png      — high-res source for tray / docs
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates += [
            r"C:\Windows\Fonts\segoeuib.ttf",
            r"C:\Windows\Fonts\arialbd.ttf",
            r"C:\Windows\Fonts\calibrib.ttf",
        ]
    candidates += [
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_logo(path: Path, width: int = 640, height: int = 200) -> None:
    """Installer banner: dark slate + product mark."""
    img = Image.new("RGB", (width, height), (18, 28, 42))
    draw = ImageDraw.Draw(img)

    # Accent bar
    draw.rectangle([0, 0, 10, height], fill=(32, 140, 220))

    # Rounded emblem
    pad = 28
    box = [pad + 8, height // 2 - 48, pad + 104, height // 2 + 48]
    draw.rounded_rectangle(box, radius=18, fill=(32, 120, 200))
    # Mini "image → PNG" motif
    draw.rectangle([box[0] + 22, box[1] + 28, box[2] - 22, box[3] - 22], outline=(255, 255, 255), width=3)
    peak = [
        (box[0] + 28, box[3] - 26),
        ((box[0] + box[2]) // 2, box[1] + 34),
        (box[2] - 28, box[3] - 26),
    ]
    draw.polygon(peak, fill=(255, 255, 255))
    r = 7
    cx, cy = box[2] - 34, box[1] + 40
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 210, 70))

    title_font = _font(44, bold=True)
    sub_font = _font(18)
    draw.text((pad + 128, height // 2 - 42), "ImageAutoPNG", font=title_font, fill=(245, 248, 252))
    draw.text((pad + 128, height // 2 + 14), "Free utility by heyjmo  ·  optional donations welcome", font=sub_font, fill=(150, 170, 195))

    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")
    print(f"Wrote {path}")


def make_app_icon_png(path: Path, size: int = 256) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    m = size // 12
    draw.rounded_rectangle([m, m, size - m - 1, size - m - 1], radius=size // 6, fill=(32, 120, 200, 255))
    pad = size // 4
    draw.rectangle(
        [pad, pad + size // 16, size - pad - 1, size - pad - 1],
        outline=(255, 255, 255, 255),
        width=max(2, size // 18),
    )
    peak = [
        (pad + size // 16, size - pad - 1),
        (size // 2, pad + size // 8),
        (size - pad - 1 - size // 16, size - pad - 1),
    ]
    draw.polygon(peak, fill=(255, 255, 255, 230))
    r = max(3, size // 12)
    cx, cy = size - pad - r * 2, pad + r * 2 + size // 16
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 220, 80, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")
    print(f"Wrote {path}")
    return img


def make_ico(png: Image.Image, ico_path: Path) -> None:
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    icons = [png.resize(s, Image.Resampling.LANCZOS) for s in sizes]
    ico_path.parent.mkdir(parents=True, exist_ok=True)
    icons[0].save(ico_path, format="ICO", sizes=sizes, append_images=icons[1:])
    print(f"Wrote {ico_path}")


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    make_logo(ASSETS / "jmo_logo.png")
    png = make_app_icon_png(ASSETS / "app_icon_256.png", 256)
    make_ico(png, ASSETS / "app_icon.ico")
    print("Assets ready.")


if __name__ == "__main__":
    main()
