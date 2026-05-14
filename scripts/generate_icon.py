#!/usr/bin/env python
"""Generate the StayAwake application icon.

Produces a high-quality multi-resolution `icon.ico` at the project root,
which `build.py` picks up automatically for the Windows .exe. Also writes
a 1024x1024 `icon.png` next to it for use elsewhere (.icns conversion,
README assets, etc.).

Run:
    python scripts/generate_icon.py
"""
from __future__ import annotations
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_ICO = PROJECT_ROOT / "icon.ico"
OUT_PNG = PROJECT_ROOT / "icon.png"

# Palette
TOP    = (88,  28, 170, 255)   # deep purple
MID    = (37, 99, 235, 255)    # vivid blue
BOTTOM = (6, 182, 212, 255)    # cyan
ACCENT = (255, 255, 255, 255)
GLOW   = (165, 243, 252, 255)


def _gradient(size: int) -> Image.Image:
    """Vertical 3-stop gradient: purple → blue → cyan, smoothstep blended."""
    grad = Image.new("RGBA", (size, size))
    px = grad.load()
    for y in range(size):
        t = y / max(1, size - 1)
        t = t * t * (3 - 2 * t)  # smoothstep
        if t < 0.5:
            u = t * 2
            a, b = TOP, MID
        else:
            u = (t - 0.5) * 2
            a, b = MID, BOTTOM
        r = int(a[0] + (b[0] - a[0]) * u)
        g = int(a[1] + (b[1] - a[1]) * u)
        b_ = int(a[2] + (b[2] - a[2]) * u)
        for x in range(size):
            px[x, y] = (r, g, b_, 255)
    return grad


def make_icon(size: int = 1024) -> Image.Image:
    """Render the StayAwake badge at `size`x`size` pixels.

    Composition:
      - Rounded-square (squircle-ish) gradient background
      - Outer soft glow ring
      - Crisp inner ring
      - Glowing center dot with catchlight highlight
    """
    # Render at 4x for anti-aliased downsample
    scale = 2
    s = size * scale

    base = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    # Rounded-square mask (Windows 11 / iOS squircle radius ~22%)
    radius = int(s * 0.22)
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, s, s), radius=radius, fill=255)

    # Gradient body
    grad = _gradient(s)
    base.paste(grad, mask=mask)

    # Subtle inner shadow at the bottom (depth)
    shadow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (0, int(s * 0.55), s, s), radius=radius, fill=(0, 0, 0, 60)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(s // 30))
    base = Image.alpha_composite(base, shadow)

    cx, cy = s // 2, s // 2

    # Outer soft glow ring
    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    r_out = int(s * 0.40)
    r_in = int(s * 0.30)
    gd.ellipse((cx - r_out, cy - r_out, cx + r_out, cy + r_out), fill=(*GLOW[:3], 130))
    gd.ellipse((cx - r_in, cy - r_in, cx + r_in, cy + r_in), fill=(0, 0, 0, 0))
    glow = glow.filter(ImageFilter.GaussianBlur(s // 45))
    base = Image.alpha_composite(base, glow)

    # Crisp white ring
    ring = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    stroke = max(2, int(s * 0.028))
    r_ring = int(s * 0.32)
    rd.ellipse(
        (cx - r_ring, cy - r_ring, cx + r_ring, cy + r_ring),
        outline=ACCENT,
        width=stroke,
    )
    base = Image.alpha_composite(base, ring)

    # Center dot glow halo
    halo = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    hd = ImageDraw.Draw(halo)
    r_halo = int(s * 0.18)
    hd.ellipse((cx - r_halo, cy - r_halo, cx + r_halo, cy + r_halo), fill=(*GLOW[:3], 220))
    halo = halo.filter(ImageFilter.GaussianBlur(s // 40))
    base = Image.alpha_composite(base, halo)

    # Solid center dot
    dot = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    dd = ImageDraw.Draw(dot)
    r_dot = int(s * 0.115)
    dd.ellipse((cx - r_dot, cy - r_dot, cx + r_dot, cy + r_dot), fill=ACCENT)
    # Catchlight highlight (top-left)
    hl_r = int(r_dot * 0.45)
    hl_x = cx - r_dot // 3
    hl_y = cy - r_dot // 3
    dd.ellipse(
        (hl_x - hl_r, hl_y - hl_r, hl_x + hl_r, hl_y + hl_r),
        fill=(220, 245, 255, 235),
    )
    base = Image.alpha_composite(base, dot)

    # Downsample to final size with LANCZOS
    return base.resize((size, size), Image.LANCZOS)


def main() -> int:
    print("[icon] Rendering 1024×1024 master…")
    master = make_icon(1024)
    master.save(OUT_PNG, format="PNG", optimize=True)
    print(f"[icon] PNG  → {OUT_PNG}  ({OUT_PNG.stat().st_size // 1024} KB)")

    # Render each ICO sub-size individually for maximum sharpness at small sizes
    sizes = [16, 24, 32, 48, 64, 128, 256]
    print(f"[icon] Rendering ICO sub-sizes: {sizes}")
    frames = [make_icon(sz) for sz in sizes]
    frames[-1].save(
        OUT_ICO,
        format="ICO",
        sizes=[(sz, sz) for sz in sizes],
        append_images=frames[:-1],
    )
    print(f"[icon] ICO  → {OUT_ICO}  ({OUT_ICO.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
