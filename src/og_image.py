"""OG image generation — 1200×630 PNG with navy/red palette."""
from __future__ import annotations
import io
import logging
import textwrap
from typing import Optional

logger = logging.getLogger(__name__)

_W, _H = 1200, 630
_NAVY = (0, 43, 94)
_RED = (200, 16, 46)
_WHITE = (255, 255, 255)
_LIGHT = (230, 235, 242)


def _draw(title: str, subtitle: str = "") -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (_W, _H), _NAVY)
    draw = ImageDraw.Draw(img)

    # Red accent stripe at top
    draw.rectangle([0, 0, _W, 8], fill=_RED)

    # Branding row
    brand_y = 48
    try:
        font_brand = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
    except Exception:
        font_brand = ImageFont.load_default()
    draw.text((72, brand_y), "VA Claims Workspace", font=font_brand, fill=_WHITE)

    # Title — word-wrap at ~38 chars per line, up to 3 lines
    try:
        font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 64)
    except Exception:
        font_title = ImageFont.load_default()

    lines = textwrap.wrap(title, width=30)[:3]
    ty = 160
    for line in lines:
        draw.text((72, ty), line, font=font_title, fill=_WHITE)
        ty += 80

    # Subtitle
    if subtitle:
        try:
            font_sub = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
        except Exception:
            font_sub = ImageFont.load_default()
        draw.text((72, ty + 20), subtitle[:80], font=font_sub, fill=_LIGHT)

    # Bottom bar
    draw.rectangle([0, _H - 56, _W, _H], fill=_RED)
    try:
        font_footer = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
    except Exception:
        font_footer = ImageFont.load_default()
    draw.text((72, _H - 40), "vaclaimsworkspace.com", font=font_footer, fill=_WHITE)

    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def generate_og_image(title: str, subtitle: str = "") -> Optional[bytes]:
    try:
        return _draw(title, subtitle)
    except ImportError:
        logger.warning("og_image: Pillow not installed; skipping")
        return None
    except Exception as exc:
        logger.error("og_image: error generating %r: %s", title[:60], exc)
        return None


def backfill_og_images(force: bool = False, limit: int = 50) -> dict:
    from sqlalchemy.orm import Session
    from src.models import BlogPost, engine

    generated = 0
    skipped = 0
    errors = 0

    with Session(engine) as session:
        q = session.query(BlogPost)
        if not force:
            q = q.filter(
                (BlogPost.og_image_bytes == None) | (BlogPost.og_image_bytes == b"")
            )
        posts = q.order_by(BlogPost.published_date.desc()).limit(limit).all()

        for post in posts:
            data = generate_og_image(post.title, post.primary_sector or "")
            if data is None:
                errors += 1
                continue
            post.og_image_bytes = data
            session.add(post)
            generated += 1

        session.commit()

    logger.info("backfill_og_images: generated=%d skipped=%d errors=%d", generated, skipped, errors)
    return {"generated": generated, "skipped": skipped, "errors": errors}
