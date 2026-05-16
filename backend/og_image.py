"""OG image generation for shared analyses (`/a/<id>/og.png`).

Renders a 1200x630 PNG card showing:
- Yarrr.Tech wordmark in gold (top-left)
- ENS / Basename if resolved, else short address (hero row)
- Top 1-2 archetype tags with confidence buckets
- Mainnet + testnet count + total tx (compact stat row)
- Decorative gold accent line + grid background

Design language matches the dark + gold theme of the live site. Pure Pillow,
no headless browser, no node — generates in <100ms per card.

Cached in-process via the `lru_cache` on `_load_font` (fonts are reused).
PNG bytes themselves are cached by `persistence.get_og_png` / `set_og_png`.
"""
from __future__ import annotations

import io
import logging
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger("yarrr-tech.og")

# Card dimensions follow the OG/Twitter card 1.91:1 spec.
W, H = 1200, 630

# Theme colors — match Tailwind config.
INK_900 = (10, 11, 16)
INK_800 = (20, 22, 30)
INK_700 = (32, 36, 48)
INK_500 = (110, 115, 135)
INK_300 = (180, 185, 205)
INK_50 = (240, 242, 250)
GOLD_400 = (251, 191, 36)
GOLD_500 = (245, 158, 11)
GOLD_DIM = (110, 80, 20)
RED_400 = (248, 113, 113)

FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_MONO_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"


@lru_cache(maxsize=32)
def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _short_addr(addr: str) -> str:
    if not addr or len(addr) < 12:
        return addr
    return f"{addr[:6]}…{addr[-4:]}"


def _draw_grid(draw: ImageDraw.ImageDraw, color: tuple) -> None:
    """Subtle dotted grid background — same vibe as the site."""
    step = 32
    for x in range(0, W, step):
        for y in range(0, H, step):
            draw.point((x, y), fill=color)


def _bucket_color(bucket: str) -> tuple:
    if bucket == "strong":
        return GOLD_400
    if bucket == "moderate":
        return GOLD_500
    if bucket == "tentative":
        return INK_500
    return INK_700


def _bucket_score_color(bucket: str) -> tuple:
    """Color for the reputation score gauge — same buckets as reputation.py."""
    if bucket == "high":
        return GOLD_400
    if bucket == "good":
        return GOLD_500
    if bucket == "neutral":
        return INK_300
    if bucket == "low":
        return (160, 160, 160)
    return RED_400  # poor


def render_og_png(
    address: str,
    name: str | None,
    archetypes: list[dict],
    total_txs: int,
    mainnet_count: int,
    testnet_count: int,
    reputation: dict | None = None,
) -> bytes:
    """Render a 1200×630 OG card and return raw PNG bytes."""
    img = Image.new("RGB", (W, H), INK_900)
    draw = ImageDraw.Draw(img)

    # Background grid + diagonal gold glow accent (top-right).
    _draw_grid(draw, (28, 30, 40))
    # Corner accent — solid gold L on top-left
    draw.rectangle([(0, 0), (W, 6)], fill=GOLD_400)
    draw.rectangle([(0, 0), (6, 220)], fill=GOLD_400)

    # Header — Yarrr.Tech wordmark
    f_brand = _load_font(FONT_BOLD, 36)
    f_brand_dot = _load_font(FONT_BOLD, 36)
    draw.text((48, 38), "Yarrr", font=f_brand, fill=INK_50)
    yarrr_w = draw.textlength("Yarrr", font=f_brand)
    draw.text((48 + yarrr_w, 38), ".", font=f_brand_dot, fill=GOLD_400)
    dot_w = draw.textlength(".", font=f_brand_dot)
    draw.text((48 + yarrr_w + dot_w, 38), "Tech", font=f_brand, fill=INK_50)

    # Sub-label — onchain identity intelligence
    f_sub = _load_font(FONT_MONO, 16)
    draw.text((48, 90), "ONCHAIN IDENTITY INTELLIGENCE", font=f_sub, fill=INK_500)

    # Hero — ENS name (if any) + address
    cursor_y = 170
    if name:
        f_name = _load_font(FONT_BOLD, 64)
        draw.text((48, cursor_y), name, font=f_name, fill=INK_50)
        cursor_y += 80
        f_addr = _load_font(FONT_MONO, 22)
        draw.text((48, cursor_y), address, font=f_addr, fill=INK_500)
        cursor_y += 38
    else:
        f_name = _load_font(FONT_MONO_BOLD, 44)
        draw.text((48, cursor_y), _short_addr(address), font=f_name, fill=INK_50)
        cursor_y += 64
        f_addr = _load_font(FONT_MONO, 18)
        draw.text((48, cursor_y), address, font=f_addr, fill=INK_500)
        cursor_y += 32

    # Gold divider
    cursor_y += 24
    draw.rectangle([(48, cursor_y), (W - 48, cursor_y + 1)], fill=GOLD_DIM)
    cursor_y += 26

    # Archetype tags (top 2)
    f_tag_label = _load_font(FONT_MONO, 14)
    f_tag = _load_font(FONT_MONO_BOLD, 26)
    f_bucket = _load_font(FONT_MONO, 16)
    draw.text((48, cursor_y), "PRIMARY ARCHETYPES", font=f_tag_label, fill=INK_500)
    cursor_y += 30

    if archetypes:
        x = 48
        for a in archetypes[:2]:
            label = a.get("name", "?")
            bucket = a.get("bucket", "weak")
            conf = a.get("confidence", 0.0)
            color = _bucket_color(bucket)

            label_w = draw.textlength(label, font=f_tag)
            bucket_text = f" · {bucket} {conf:.2f}"
            bucket_w = draw.textlength(bucket_text, font=f_bucket)
            tag_w = label_w + bucket_w + 32
            tag_h = 50

            # Pill background
            draw.rounded_rectangle(
                [(x, cursor_y), (x + tag_w, cursor_y + tag_h)],
                radius=12,
                fill=INK_800,
                outline=color,
                width=2,
            )
            draw.text((x + 16, cursor_y + 9), label, font=f_tag, fill=color)
            draw.text(
                (x + 16 + label_w, cursor_y + 17),
                bucket_text,
                font=f_bucket,
                fill=INK_300,
            )
            x += tag_w + 16
            if x > W - 200:
                break
        cursor_y += 76
    else:
        f_none = _load_font(FONT_MONO, 18)
        draw.text((48, cursor_y), "no dominant archetype", font=f_none, fill=INK_500)
        cursor_y += 50

    # Stats row (bottom). If reputation is present, replace the "ARCHETYPES"
    # column with a prominent reputation score in its own color.
    stats_y = H - 100
    f_stat_num = _load_font(FONT_MONO_BOLD, 36)
    f_stat_label = _load_font(FONT_MONO, 14)
    f_rep_num = _load_font(FONT_MONO_BOLD, 44)

    base_stats = [
        (f"{total_txs}", "TOTAL TX"),
        (f"{mainnet_count}", "MAINNETS"),
        (f"{testnet_count}", "TESTNETS"),
    ]
    if reputation and reputation.get("score") is not None:
        rep_score = reputation["score"]
        rep_bucket = reputation.get("bucket", "neutral")
        rep_color = _bucket_score_color(rep_bucket)
        # Reputation gets a wider column with bigger numerals to land as the
        # hero stat.
        col_w = (W - 96) // 4
        for i, (num, label) in enumerate(base_stats):
            cx = 48 + i * col_w
            draw.text((cx, stats_y + 8), num, font=f_stat_num, fill=GOLD_400)
            draw.text((cx, stats_y + 54), label, font=f_stat_label, fill=INK_500)
        # Last column: REP X/100
        cx = 48 + 3 * col_w
        draw.text((cx, stats_y), f"{rep_score}", font=f_rep_num, fill=rep_color)
        denom_w = draw.textlength(f"{rep_score}", font=f_rep_num)
        f_denom = _load_font(FONT_MONO, 18)
        draw.text((cx + denom_w + 4, stats_y + 22), "/100", font=f_denom, fill=INK_500)
        draw.text((cx, stats_y + 54), f"REPUTATION · {rep_bucket.upper()}", font=f_stat_label, fill=rep_color)
    else:
        col_w = (W - 96) // 4
        full_stats = base_stats + [(f"{len(archetypes)}", "ARCHETYPES")]
        for i, (num, label) in enumerate(full_stats):
            cx = 48 + i * col_w
            draw.text((cx, stats_y + 8), num, font=f_stat_num, fill=GOLD_400)
            draw.text((cx, stats_y + 54), label, font=f_stat_label, fill=INK_500)

    # Footer URL
    f_url = _load_font(FONT_MONO, 14)
    draw.text((48, H - 28), "yarrr-node.com", font=f_url, fill=INK_500)

    # Output
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
