"""Generate a simple system-tray icon at runtime (no external asset required)."""

from __future__ import annotations

from PIL import Image, ImageDraw


def create_icon(size: int = 64) -> Image.Image:
    """Simple camera/image-style tray icon on a dark rounded square."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = size // 10
    draw.rounded_rectangle(
        [margin, margin, size - margin - 1, size - margin - 1],
        radius=size // 6,
        fill=(32, 120, 200, 255),
    )

    # White "PNG" arrow / image frame
    pad = size // 4
    draw.rectangle(
        [pad, pad + size // 16, size - pad - 1, size - pad - 1],
        outline=(255, 255, 255, 255),
        width=max(2, size // 20),
    )
    # Small mountain / image motif
    peak = [
        (pad + size // 16, size - pad - 1),
        (size // 2, pad + size // 8),
        (size - pad - 1 - size // 16, size - pad - 1),
    ]
    draw.polygon(peak, fill=(255, 255, 255, 220))
    # Sun dot
    r = max(2, size // 14)
    cx, cy = size - pad - r * 2, pad + r * 2 + size // 16
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 220, 80, 255))

    return img
