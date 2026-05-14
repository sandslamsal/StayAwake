"""Procedural icon generation — no image files shipped in the binary."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image as _ImageT  # noqa: F401


def make_icon(active: bool = True, size: int = 64):
    """Build a small SyncStruct-branded icon: gradient ring + center dot.

    Green when active, gray when inactive.
    """
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    accent = (34, 197, 94, 255) if active else (148, 163, 184, 255)
    dim = (15, 23, 42, 255)

    pad = max(2, size // 16)
    d.ellipse((pad, pad, size - pad, size - pad), fill=dim, outline=accent, width=max(2, size // 16))
    cpad = size // 3
    d.ellipse((cpad, cpad, size - cpad, size - cpad), fill=accent)
    return img
