"""
Draws Wire Now story cards as pictures (1080 x 1350), Deepstash style.
Telegram shows several pictures in one post as a swipeable slideshow.
"""

import io
import re
import os
import urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1080, 1350
ROOT = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(ROOT, "fonts")

INK = (30, 27, 46)
MUTED = (107, 104, 128)
CREAM = (255, 248, 243)
WHITE = (255, 255, 255)

TOPIC_COLORS = {
    "Politics": (108, 99, 255), "Economy": (0, 168, 132), "Business": (0, 145, 234),
    "Sports": (255, 143, 0), "Tech": (124, 77, 255), "Health": (233, 30, 99),
    "Weather": (0, 151, 167), "Entertainment": (216, 27, 96), "Astrology": (94, 53, 177), "Society": (141, 110, 99),
}
# each card type gets its own colour, like Deepstash
CARD_STYLE = {
    "what_happened":  {"label": "WHAT HAPPENED",  "c1": (255, 107, 74), "c2": (255, 178, 63)},
    "why_it_matters": {"label": "WHY IT MATTERS", "c1": (108, 99, 255), "c2": (167, 139, 250)},
    "key_facts":      {"label": "KEY FACTS",      "c1": (0, 168, 132),  "c2": (102, 211, 160)},
    "whats_next":     {"label": "WHAT'S NEXT",    "c1": (0, 145, 234),  "c2": (99, 200, 255)},
    "details":        {"label": "THE FULL STORY", "c1": (232, 93, 140), "c2": (255, 154, 139)},
    "story":          {"label": "THE STORY",      "c1": (255, 107, 74), "c2": (255, 178, 63)},
    "site_summary":   {"label": "SUMMARY",        "c1": (96, 125, 139), "c2": (144, 164, 174)},
}


def font(weight, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, f"Inter-{weight}.otf"), size)


def gradient(c1, c2, w=W, h=H):
    """Diagonal two-colour background."""
    base = Image.new("RGB", (w, h), c1)
    top = Image.new("RGB", (w, h), c2)
    mask = Image.linear_gradient("L").resize((w, h))
    return Image.composite(top, base, mask)


def wrap(draw, text, fnt, max_w):
    words, lines, line = text.split(), [], ""
    for w in words:
        test = (line + " " + w).strip()
        if draw.textlength(test, font=fnt) <= max_w:
            line = test
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def fit_text(draw, text, weight, max_w, max_h, start=72, smallest=36, spacing=1.32):
    """Biggest font size where the text fits the box."""
    size = start
    while size >= smallest:
        f = font(weight, size)
        lines = wrap(draw, text, f, max_w)
        if len(lines) * size * spacing <= max_h:
            return f, lines, int(size * spacing)
        size -= 4
    f = font(weight, smallest)
    lines = wrap(draw, text, f, max_w)
    keep = max(1, int(max_h // (smallest * spacing)))
    if len(lines) > keep:
        lines = lines[:keep]
        lines[-1] = lines[-1].rstrip(".,;") + "…"
    return f, lines, int(smallest * spacing)


def rounded(img, box, radius, fill):
    ImageDraw.Draw(img).rounded_rectangle(box, radius=radius, fill=fill)


def shadowed_panel(img, box, radius=56):
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([box[0], box[1] + 18, box[2], box[3] + 18], radius=radius, fill=(30, 27, 46, 60))
    sh = sh.filter(ImageFilter.GaussianBlur(24))
    img.paste(sh, (0, 0), sh)
    rounded(img, box, radius, WHITE)


def pill(draw, xy, text, bg, fg=WHITE, size=34):
    f = font("Bold", size)
    tw = draw.textlength(text, font=f)
    x, y = xy
    draw.rounded_rectangle([x, y, x + tw + 44, y + size + 30], radius=(size + 30) // 2, fill=bg)
    draw.text((x + 22, y + 13), text, font=f, fill=fg)
    return x + tw + 44


def location_pill(draw, xy, text, size=32):
    """Dark pill with a map-pin shape and the place name (emoji can't be drawn with this font)."""
    f = font("Bold", size)
    while draw.textlength(text, font=f) > W - 260 and size > 22:
        size -= 2
        f = font("Bold", size)
    x, y = xy
    tw = draw.textlength(text, font=f)
    h = size + 30
    draw.rounded_rectangle([x, y, x + tw + 84, y + h], radius=h // 2, fill=INK)
    cx, cy = x + 34, y + h // 2 - 4
    draw.ellipse([cx - 12, cy - 12, cx + 12, cy + 12], fill=(255, 107, 74))
    draw.polygon([(cx - 10, cy + 6), (cx + 10, cy + 6), (cx, cy + 22)], fill=(255, 107, 74))
    draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=INK)
    draw.text((x + 62, y + 13), text, font=f, fill=WHITE)


_LOGO = None


def logo(size):
    global _LOGO
    if _LOGO is None:
        try:
            _LOGO = Image.open(os.path.join(ROOT, "logo-small.png")).convert("RGB")
        except Exception:
            _LOGO = False
    if not _LOGO:
        return None
    im = _LOGO.resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
    return im, mask


def footer(draw, source, page, total, dark=False):
    col = WHITE if dark else INK
    lg = logo(56)
    x = 70
    if lg:
        draw._image.paste(lg[0], (70, H - 100), lg[1])
        x = 70 + 56 + 14
    draw.text((x, H - 92), "Wire Now", font=font("Black", 40), fill=col)
    right = f"{source}  ·  {page}/{total}"
    f = font("Bold", 32)
    draw.text((W - 70 - draw.textlength(right, font=f), H - 86), right, font=f, fill=col)


def load_photo(url):
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            im = Image.open(io.BytesIO(r.read())).convert("RGB")
        # too small to fill the card sharply (it would be stretched and blurry): use the clean cover instead
        return im if im.width >= 700 and im.height >= 400 else None
    except Exception:
        return None


def cover_fill(photo, w, h):
    pw, ph = photo.size
    scale = max(w / pw, h / ph)
    photo = photo.resize((int(pw * scale) + 1, int(ph * scale) + 1), Image.LANCZOS)
    x, y = (photo.width - w) // 2, (photo.height - h) // 2
    return photo.crop((x, y, x + w, y + h))


# ---------------------------------------------------------------------

SUBJECTS = [(r"parliament|budget debate|speaker of", "PARLIAMENT"), (r"court|judge|verdict|bail|lawsuit", "COURT"),
            (r"flood|tsunami", "FLOODS"), (r"rain|weather|monsoon|storm|cyclone|met\. dept|thunder", "WEATHER"),
            (r"fire|blaze", "FIRE"), (r"crash|accident|collision|derail", "ACCIDENT"),
            (r"police|arrest|murder|suspect|shooting|robbery|drugs", "POLICE"), (r"cricket", "CRICKET"),
            (r"football|fifa", "FOOTBALL"), (r"election|vote|poll|ballot", "ELECTION"),
            (r"rupee|dollar|inflation|imf|central bank|cbsl|economy|tax|budget|price", "ECONOMY"),
            (r"hospital|health|dengue|virus|disease|doctor", "HEALTH"), (r"school|exam|university|student", "EDUCATION"),
            (r"airport|flight|airline", "TRAVEL"), (r"microsoft|google|apple|outage|\bai\b|software|internet|cyber", "TECHNOLOGY"),
            (r"peace talks|war|missile|military|army|strike on|ceasefire", "CONFLICT AND PEACE")]


def badge(story):
    """(circle text, label) for the story's icon badge: initials for a person, else the subject. Never a face."""
    c = story.get("cards") or {}
    if c.get("person"):
        words = [w for w in re.split(r"[\s.\-]+", re.sub(r"[^\w\s.\-]", "", c["person"])) if len(w) > 1]
        ini = (words[0][0] + (words[-1][0] if len(words) > 1 else "")).upper() if words else ""
        loc = (story.get("location") or {}).get("country", "")
        return ini, " · ".join(x for x in (loc, c.get("role", "")) if x).upper() or c["person"].upper()
    for pat, label in SUBJECTS:
        if re.search(pat, story.get("title", ""), re.I):
            return label[0], label
    t = (story.get("topic") or "NEWS").upper()
    return t[0], t


def draw_badge(img, story, x, y, light):
    """Round badge + label, on top of the cover (a dark shade underneath keeps it readable on any photo)."""
    ini, label = badge(story)
    d = ImageDraw.Draw(img)
    r = 58
    d.ellipse([x, y, x + 2 * r, y + 2 * r], fill=(255, 255, 255) if light else (255, 107, 74))
    f = font("Black", 52 if len(ini) == 1 else 44)
    tw = d.textlength(ini, font=f)
    d.text((x + r - tw / 2, y + r - 32), ini, font=f, fill=(255, 107, 74) if light else WHITE)
    f2 = font("Black", 40)
    while d.textlength(label, font=f2) > W - x - 2 * r - 90 and f2.size > 24:
        f2 = font("Black", f2.size - 2)
    d.text((x + 2 * r + 24, y + r - f2.size // 2 - 4), label, font=f2, fill=WHITE)


def cover_card(story, photo, total):
    topic = story.get("topic") or "Society"
    tc = TOPIC_COLORS.get(topic, (141, 110, 99))
    img = Image.new("RGB", (W, H), CREAM)
    photo_h = 700
    if photo:
        img.paste(cover_fill(photo, W, photo_h), (0, 0))
        # the photo is the wallpaper: a soft dark shade at the bottom, the icon badge on top
        shade = Image.linear_gradient("L").resize((W, 300)).point(lambda v: int(v * 0.75))
        img.paste((20, 18, 28), (0, 300), shade)
        draw_badge(img, story, 60, 460, light=True)
    else:
        img.paste(gradient((255, 107, 74), (255, 178, 63), W, photo_h), (0, 0))
        d = ImageDraw.Draw(img)
        lg = logo(220)
        if lg:
            img.paste(lg[0], ((W - 220) // 2, 150), lg[1])
        else:
            big = font("Black", 150)
            t = "WIRE NOW"
            d.text(((W - d.textlength(t, font=big)) / 2, 200), t, font=big, fill=(255, 255, 255))
        draw_badge(img, story, 60, 440, light=True)
    d = ImageDraw.Draw(img)
    # region badge
    loc = story.get("location") or {}
    where = (" / ".join([loc["country"]] + loc["also"]) if loc.get("also") else
             loc.get("place") + ", " + loc.get("country") if loc.get("place") and loc.get("country")
             else loc.get("place") or loc.get("country") or ("SRI LANKA" if story["region"] == "sri_lanka" else "WORLD"))
    location_pill(d, (60, 60), where.upper())
    # white panel overlapping the photo
    shadowed_panel(img, (40, 600, W - 40, H - 140))
    d = ImageDraw.Draw(img)
    pill(d, (90, 650), topic.upper(), tc, size=32)
    f, lines, lh = fit_text(d, story["title"], "Black", W - 180, 360, start=76, smallest=42, spacing=1.2)
    y = 750
    for ln in lines:
        d.text((90, y), ln, font=f, fill=INK)
        y += lh
    hint = "Swipe to read the full story  →" if total > 1 else "Read the story in the caption  ↓"
    d.text((90, H - 225), hint, font=font("Bold", 34), fill=(255, 107, 74))
    footer(d, story["source"], 1, total)
    return img


def text_card(kind, body, story, page, total):
    st = dict(CARD_STYLE[kind])
    start = 0
    if isinstance(body, tuple) and isinstance(body[1], int):  # (facts, number of the first fact - 1)
        body, start = body
    elif isinstance(body, tuple) and kind == "site_summary":  # (text, "FROM ADA DERANA")
        body, part = body
        st["label"] = f"{st['label']} {part}"
    elif isinstance(body, tuple):  # (text, "1/3") -> numbered label
        body, part = body
        st["label"] = f"{st['label']}  {part}"
    img = gradient(st["c1"], st["c2"])
    shadowed_panel(img, (60, 90, W - 60, H - 150))
    d = ImageDraw.Draw(img)
    # label with a coloured dot
    d.ellipse([120, 175, 150, 205], fill=st["c1"])
    d.text((170, 166), st["label"], font=font("Black", 42), fill=st["c1"])
    box_w, box_top, box_bottom = W - 240, 270, H - 230

    if isinstance(body, list):  # key facts
        f, size = None, 62
        while size >= 34:
            f = font("Bold", size)
            blocks = [wrap(d, b, f, box_w - 90) for b in body]
            need = sum(len(b) * size * 1.3 + 50 for b in blocks)
            if need <= box_bottom - box_top:
                break
            size -= 4
        y = box_top + max(0, int((box_bottom - box_top - need) / 2))
        for i, b in enumerate(blocks):
            d.rounded_rectangle([120, y + 4, 176, y + 60], radius=16, fill=st["c1"])
            n = str(start + i + 1)
            nf = font("Black", 34)
            d.text((148 - d.textlength(n, font=nf) / 2, y + 10), n, font=nf, fill=WHITE)
            for ln in b:
                d.text((206, y), ln, font=f, fill=INK)
                y += int(size * 1.3)
            y += 50
    else:
        f, lines, lh = fit_text(d, body, "Bold", box_w, box_bottom - box_top, start=84, smallest=MIN_TEXT_SIZE)
        y = box_top + max(0, (box_bottom - box_top - lh * len(lines)) // 2)
        for ln in lines:
            d.text((120, y), ln, font=f, fill=INK)
            y += lh

    footer(d, story["source"], page, total, dark=True)
    return img


def end_card(story, page, total, channel):
    img = gradient((30, 27, 46), (70, 60, 110))
    d = ImageDraw.Draw(img)
    big = font("Black", 96)
    for i, t in enumerate(["You're up", "to date!"]):
        d.text(((W - d.textlength(t, font=big)) / 2, 380 + i * 120), t, font=big, fill=WHITE)
    f = font("Bold", 40)
    for i, t in enumerate([f"Full story: {story['source']}", "(link in the caption)"]):
        d.text(((W - d.textlength(t, font=f)) / 2, 680 + i * 60), t, font=f, fill=(200, 196, 220))
    if channel:
        t = f"Follow {channel}"
        bf = font("Black", 44)
        tw = d.textlength(t, font=bf)
        x = (W - tw) / 2 - 40
        d.rounded_rectangle([x, 880, x + tw + 80, 980], radius=50, fill=(255, 107, 74))
        d.text((x + 40, 902), t, font=bf, fill=WHITE)
    note = "Written by AI from the article, then fact-checked"
    nf = font("Medium", 30)
    d.text(((W - d.textlength(note, font=nf)) / 2, 1080), note, font=nf, fill=(160, 156, 185))
    footer(d, story["source"], page, total, dark=True)
    return img


MIN_TEXT_SIZE = 40          # never smaller than this: still easy to read on a phone


def _fits(text, size=MIN_TEXT_SIZE):
    """Does this text fit one card at the given letter size?"""
    d = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    lines = wrap(d, text, font("Bold", size), W - 240)
    return len(lines) * size * 1.32 <= (H - 230) - 270


def split_text(text):
    """One card if the text fits at a readable size (letters shrink as needed, down to MIN_TEXT_SIZE).
    Only when it doesn't fit even then is it split, at sentence ends, into as few cards as possible."""
    text = (text or "").strip()
    if not text or _fits(text):
        return [text] if text else []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for n in range(2, len(sentences) + 1):
        target = len(text) / n                    # balanced pieces
        pieces, cur = [], ""
        for sn in sentences:
            if cur and len(cur) + 1 + len(sn) > target * 1.15 and len(pieces) < n - 1:
                pieces.append(cur)
                cur = sn
            else:
                cur = (cur + " " + sn).strip()
        pieces.append(cur)
        if all(_fits(pc) for pc in pieces):
            return pieces
    return sentences


def make_cards(story, cards, channel=""):
    """Returns a list of JPEG bytes: cover, then one picture per card, then an end card."""
    parts = []
    if cards:
        # every card holds an easy-to-read amount; long text continues on the next card ("1/2", "2/2")
        details = [piece for d in (cards.get("details") or []) for piece in split_text(d)]
        facts = list(cards.get("key_facts") or [])
        fact_cards = [facts[i:i + 3] for i in range(0, len(facts), 3)]
        def labelled(kind, text):
            pieces = split_text(text)
            return [(kind, pc if len(pieces) == 1 else (pc, f"{i + 1}/{len(pieces)}")) for i, pc in enumerate(pieces)]
        parts += labelled("what_happened", cards["what_happened"])
        n = len(details)
        for i, d in enumerate(details):
            parts.append(("details", d if n == 1 else (d, f"{i + 1}/{n}")))
        if cards.get("why_it_matters"):
            parts += labelled("why_it_matters", cards["why_it_matters"])
        for j, fc in enumerate(fact_cards):
            parts.append(("key_facts", (fc, j * 3)))
        if cards.get("whats_next"):
            parts += labelled("whats_next", cards["whats_next"])
        # Telegram albums hold at most 10 pictures: cover + end card leave 8 (the full story page shows the rest)
        parts = parts[:8]
    elif len(story.get("summary", "")) >= 80:
        # no AI summary: show the news site's own description, clearly labelled with its source
        parts.append(("site_summary", (story["summary"][:600], f"FROM {story['source'].upper()}")))
    total = 1 + len(parts) + (1 if cards else 0)

    images = [cover_card(story, load_photo(story.get("image")), total)]
    for i, (kind, body) in enumerate(parts):
        images.append(text_card(kind, body, story, i + 2, total))
    if cards:
        images.append(end_card(story, total, total, channel))

    out = []
    for im in images:
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=88, optimize=True)
        out.append(buf.getvalue())
    return out
