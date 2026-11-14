"""
Wire Now - news robot.

Every run it:
  1. reads the news feeds in feeds.json
  2. finds stories it has not posted before (Sri Lanka first, then world)
  3. for each one, reads the full article and has an AI write 4 short "story cards"
     (what happened / why it matters / key facts / what's next)
  4. checks the cards two ways before using them:
       a) code check: every number and name in the cards must appear in the article
       b) AI checker: a second AI pass must confirm every fact is in the article
     If a check fails, the AI tries once more; if it fails again, the cards are dropped
     and the story is posted with the news site's own summary instead.
  5. posts each story to Telegram with a link to its cards on the website
  6. updates docs/news.json, which the website shows

Secrets (GitHub -> Settings -> Secrets and variables -> Actions):
  TELEGRAM_BOT_TOKEN   from @BotFather
  TELEGRAM_CHANNEL     e.g. @wirenow_lk
  OPENROUTER_API_KEY   from openrouter.ai (optional - without it there are no AI cards)
  SITE_URL             e.g. https://yourname.github.io/wire-now/ (optional)
Without the Telegram secrets it runs in TEST MODE and only prints what it would post.
"""

import hashlib
import hmac
import places
import pulse
import social
import html
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.abspath(__file__))
FEEDS_FILE = os.path.join(ROOT, "feeds.json")
STATE_FILE = os.path.join(ROOT, "data", "posted.json")
CARDS_FILE = os.path.join(ROOT, "data", "cards.json")
MEANING_FILE = os.path.join(ROOT, "data", "meaning.json")
TRANSLATIONS_FILE = os.path.join(ROOT, "data", "translations.json")   # Sinhala and Tamil versions of headlines and summaries   # AI decisions: which other reports add something new
SITE_FILE = os.path.join(ROOT, "docs", "news.json")

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHANNEL = os.environ.get("TELEGRAM_CHANNEL", "").strip()
AI_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GROQ_KEY = os.environ.get("GROQ_API_KEY", "").strip()
SITE_URL = os.environ.get("SITE_URL", "").strip()
if SITE_URL and not SITE_URL.endswith("/"):
    SITE_URL += "/"
# accept the channel written as @name, t.me/name or https://t.me/name
_m = re.search(r"(?:t\.me/|@)+([A-Za-z0-9_]{4,})\s*$", CHANNEL)
if _m:
    CHANNEL = "@" + _m.group(1)

SECRET_PROBLEMS = []
if TOKEN and not re.fullmatch(r"\d{6,}:[A-Za-z0-9_-]{30,}", TOKEN):
    SECRET_PROBLEMS.append("TELEGRAM_BOT_TOKEN does not look like a BotFather token "
                           "(it should look like 7123456789:AAH...). Paste only the token.")
    TOKEN = ""
if CHANNEL and not re.fullmatch(r"@[A-Za-z0-9_]{4,}", CHANNEL):
    SECRET_PROBLEMS.append("TELEGRAM_CHANNEL should be just the channel username, e.g. @wirenow_lk")
    CHANNEL = ""
if AI_KEY and not re.fullmatch(r"sk-or-[A-Za-z0-9_-]{20,}", AI_KEY):
    SECRET_PROBLEMS.append("OPENROUTER_API_KEY does not look like an OpenRouter key "
                           "(it should start with sk-or-v1-). Paste only the key.")
    AI_KEY = ""
def valid_gemini_key(k):
    """Google AI Studio keys: the old kind starts with AIza, the newer kind with AQ. (both are fine)."""
    return bool(re.fullmatch(r"AIza[A-Za-z0-9_-]{30,}", k or "") or re.fullmatch(r"AQ\.[A-Za-z0-9_.-]{20,}", k or ""))


if GEMINI_KEY and not valid_gemini_key(GEMINI_KEY):
    SECRET_PROBLEMS.append("GEMINI_API_KEY does not look like a Google AI Studio key (it should start with AIza or AQ.).")
    GEMINI_KEY = ""
if GROQ_KEY and not re.fullmatch(r"gsk_[A-Za-z0-9]{20,}", GROQ_KEY):
    SECRET_PROBLEMS.append("GROQ_API_KEY does not look like a Groq key (it should start with gsk_).")
    GROQ_KEY = ""
ANY_AI = bool(AI_KEY or GEMINI_KEY or GROQ_KEY)
TEST_MODE = not (TOKEN and CHANNEL)
BOT_USERNAME = ""   # filled in at the start of a live run (getMe)

UA = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Mobile Safari/537.36"
TOPICS = ["Politics", "Economy", "Business", "Sports", "Tech", "Health", "Weather", "Entertainment", "Astrology", "Society"]


# ======================================================================
# small helpers
# ======================================================================

def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def story_id(link):
    return hashlib.sha1(link.encode()).hexdigest()[:10]


def strip_html(text):
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", text or "", flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"The post .{0,300}? appeared first on .{0,80}?\.?\s*$", "", text.strip())
    return re.sub(r"\s+", " ", text).strip()


def shorten(text, limit):
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",;:-") + "…"


def parse_date(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError, IndexError):
        d = None
    if d is None:
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone(timedelta(hours=5, minutes=30)))  # assume Sri Lanka time
    return d.astimezone(timezone.utc)


def http_get(url, timeout=25):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/rss+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


fetch = http_get  # (tests replace this)


def guess_topic(text):
    t = " " + text.lower() + " "
    rules = [
        ("Astrology", r" horoscope| zodiac| astrolog| star sign| birth chart| jathakaya| jathagam| nakath| auspicious time|"
                      r" palapala| rashi| raasi| mercury retrograde| tarot"),
        ("Entertainment", r" film| movie| box office| cinema| actor| actress| singer| song | songs| concert| album| bollywood| hollywood|"
                          r" kollywood| tv series| teledrama| celebrity| trailer| music| oscar| grammy| netflix| crore worldwide"),
        ("Sports", r" cricket| match | t20| odi | test series| football| rugby| olympic| tournament| wicket| fifa"),
        ("Weather", r" rain| flood| landslide| cyclone| monsoon| weather| storm| drought| met department"),
        ("Health", r" health| hospital| doctor| dengue| disease| vaccine| medicine| patients"),
        ("Tech", r" tech| digital| ai | artificial intelligence| app | apps | internet| cyber| startup| software| microsoft| google|"
                 r" apple | iphone| android| meta | facebook| whatsapp| openai| chatgpt| nvidia| outage| smartphone| laptop| 5g"),
        ("Economy", r" imf| economy| inflation| rupee| central bank| cbsl| tax| budget| debt| gdp| interest rate"),
        ("Business", r" company| shares| cse | profit| revenue| investment| bank | exports| tourism| business"),
        ("Politics", r" president| minister| parliament| election| government| cabinet| party| mp | opposition| court| police"),
    ]
    for topic, pattern in rules:
        if re.search(pattern, t):
            return topic
    return "Society"


# ======================================================================
# reading feeds
# ======================================================================

def local_name(tag):
    return tag.rsplit("}", 1)[-1].lower() if isinstance(tag, str) else ""


def child_text(el, *names):
    for c in el:
        if local_name(c.tag) in names and (c.text or "").strip():
            return c.text.strip()
    return ""


def find_image(el, desc_html):
    for c in el.iter():
        n = local_name(c.tag)
        if n in ("enclosure", "content", "thumbnail") and c.get("url"):
            if n != "enclosure" or (c.get("type") or "image").startswith("image"):
                return c.get("url")
    m = re.search(r'<img[^>]+src=["\']([^"\']+)', desc_html or "", re.I)
    return m.group(1) if m else ""


def google_news_url(site, days=1):
    q = urllib.parse.quote(f"site:{site} when:{days}d")
    return f"https://news.google.com/rss/search?q={q}&hl=en-LK&gl=LK&ceid=LK:en"


def feed_url(feed):
    if feed.get("google"):
        return google_news_url(feed["google"], feed.get("days", 1))
    if feed.get("google_q"):
        q = urllib.parse.quote(feed["google_q"] + f" when:{feed.get('days', 1)}d")
        return f"https://news.google.com/rss/search?q={q}&hl=en-LK&gl=LK&ceid=LK:en"
    return feed.get("google_feed") or feed["url"]


def parse_xml(xml_bytes):
    try:
        return ET.fromstring(xml_bytes)
    except ET.ParseError:
        # many sites send slightly broken feeds: fix loose "&" and stray control characters, then retry
        text = xml_bytes.decode("utf-8", errors="replace")
        text = re.sub(r"&(?!(?:[a-zA-Z]+|#\d+|#x[0-9a-fA-F]+);)", "&amp;", text)
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
        return ET.fromstring(text.encode())


def parse_feed(xml_bytes, source, region):
    root = parse_xml(xml_bytes)
    stories = []
    for el in root.iter():
        if local_name(el.tag) not in ("item", "entry"):
            continue
        title = strip_html(child_text(el, "title"))
        link = ""
        for c in el:
            if local_name(c.tag) == "link":
                link = (c.get("href") or c.text or "").strip()
                if link and c.get("rel") in (None, "alternate"):
                    break
        if not link:
            link = child_text(el, "guid")
        if not title or not link.startswith("http"):
            continue
        # junk "headlines" like "Other", "Sports" or "Latest News" are section links, not stories
        if len(title) < 20 or len(title.split()) < 4:
            continue
        desc_html = child_text(el, "description", "summary", "encoded", "content")
        summary = strip_html(desc_html)
        if summary.lower().startswith(title.lower()) and len(summary) < len(title) + 20:
            summary = ""
        d = parse_date(child_text(el, "pubdate", "published", "updated", "date"))
        item_source = source
        if "news.google.com" in link:
            # Google News headlines end with " - Outlet"; its summary only repeats the headline
            if " - " in title:
                title, outlet = title.rsplit(" - ", 1)
                title = title.strip()
                if source.startswith("Google"):   # a mixed feed: use the real outlet's name
                    item_source = outlet.strip()
        # some sites put their own name at the end of headlines too ("... - Daily Mirror")
        for name in {source, item_source}:
            if title.lower().endswith(" - " + name.lower()):
                title = title[: -len(name) - 3].strip()
            summary = ""
        # some sites glue their own name to the FRONT of headlines:
        # "Sri Lanka Latest Breaking News and Headlines - Print Edition Kadella Construction Exhibition 2026 opens"
        title = SITE_PREFIX.sub("", title).strip() or title
        if is_site_name({"title": title, "source": item_source}):
            continue                     # a website's name or slogan, not a story
        stories.append({
            "id": story_id(link),
            "title": title,
            "link": link,
            "summary": summary[:600],
            "image": find_image(el, desc_html),
            "source": item_source,
            "region": region,
            "date": d.isoformat() if d else None,
        })
    return stories


# ======================================================================
# reading the full article
# ======================================================================

class ArticleText(HTMLParser):
    """Collects the text of <p> paragraphs, skipping menus, headers and footers."""
    SKIP = {"script", "style", "nav", "header", "footer", "aside", "form", "noscript", "figure"}

    def __init__(self):
        super().__init__()
        self.skip_depth = 0
        self.in_p = False
        self.buf = []
        self.paras = []
        self.og_image = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta" and a.get("property") == "og:image" and not self.og_image:
            self.og_image = a.get("content", "")
        if tag in self.SKIP:
            self.skip_depth += 1
        elif tag == "p" and not self.skip_depth:
            self.in_p, self.buf = True, []

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip_depth:
            self.skip_depth -= 1
        elif tag == "p" and self.in_p:
            self.in_p = False
            t = re.sub(r"\s+", " ", "".join(self.buf)).strip()
            if len(t) > 40 and not re.search(r"cookie|subscribe|all rights reserved|copyright ©", t, re.I):
                self.paras.append(t)

    def handle_data(self, data):
        if self.in_p and not self.skip_depth:
            self.buf.append(data)


REPEAT_SKIP = set("the a an and or of to in on at for by with from as is are was were be been it its this that these those "
                  "says said after over amid into new sri lanka lankan".split())


OPPOSITES = [("increase", "decrease"), ("increase", "reduce"), ("rise", "fall"), ("rise", "drop"), ("up", "down"),
             ("raise", "cut"), ("hike", "cut"), ("higher", "lower"), ("more", "less"), ("approve", "reject"),
             ("pass", "reject"), ("win", "lose"), ("won", "lost"), ("open", "close"), ("start", "end"),
             ("ban", "allow"), ("lift", "impose"), ("support", "oppose"), ("accept", "reject"), ("gain", "loss")]
NEGATIONS = {"not", "no", "never", "denies", "deny", "denied", "rejects", "fake", "false", "won't", "cannot", "can't"}


def _words(t):
    return {x[:-1] if x.endswith("s") and len(x) > 4 else x
            for x in re.findall(r"[a-z0-9']+", t.lower()) if len(x) > 2 and x not in REPEAT_SKIP}


def _numbers(t):
    return set(re.findall(r"\d+(?:[.,]\d+)?", t.replace(",", "")))


def _stem(w):
    return re.sub(r"(ing|ed|es|s|d)$", "", w)


def repeats(x, y, limit=0.5):
    """True only when report y adds nothing new to x: almost the same headline, the same numbers,
    no opposite meaning, and (when both sites describe it) the same description. Any doubt -> keep it."""
    t1, t2 = (x["title"], y["title"]) if isinstance(x, dict) else (x, y)
    a, b = _words(t1), _words(t2)
    if not a or not b or len(a & b) / len(a | b) < limit:
        return False
    if _numbers(t1) != _numbers(t2):
        return False                                   # different amounts, dates or counts
    s1, s2 = {_stem(w) for w in re.findall(r"[a-z']+", t1.lower())}, {_stem(w) for w in re.findall(r"[a-z']+", t2.lower())}
    for p, q in OPPOSITES:
        p, q = _stem(p), _stem(q)
        if (p in s1 and q in s2) or (q in s1 and p in s2):
            return False                               # opposite meaning
    n1, n2 = set(re.findall(r"[a-z']+", t1.lower())) & NEGATIONS, set(re.findall(r"[a-z']+", t2.lower())) & NEGATIONS
    if n1 != n2:
        return False                                   # one says "not", the other doesn't
    if isinstance(x, dict):
        d1, d2 = x.get("summary") or "", y.get("summary") or ""
        if len(d1) >= 80 and len(d2) >= 80:
            w1, w2 = _words(d1), _words(d2)
            if w1 and w2 and len(w1 & w2) / len(w1 | w2) < 0.35:
                return False                           # the sites describe different things
    return True


MEANING_PROMPT = """You help a news app decide which extra reports to show under a story.
For each GROUP you get the MAIN report and some OTHER reports about the same event, from different news sites.
Each has a headline and sometimes a short description.

Judge by MEANING, not by wording. Two sites never use the same words, so ignore wording completely.
Go through the OTHER reports in order. KEEP a report only if it tells the reader something meaningfully different
from the main report and from the reports you already kept, for example:
- new facts or details, a different part of the story, a different side or person's view,
- different numbers, places or dates, or a claim that disagrees with or contradicts another report.
DROP a report if it only tells the same information again in different words.
When you are unsure, KEEP it.

Also: if two reports in a group CONTRADICT each other on a fact (different numbers, different claims about
what happened or who did it), write one short sentence saying what differs and which site says what, in "disagree".
Leave "disagree" as "" when they don't contradict. Only facts, never your opinion on who is right.

Reply with ONLY this JSON, nothing else:
{"groups": [{"g": 1, "keep": [ids of OTHER reports to keep, in order], "disagree": ""}, ...]}

%s
"""


def judge_meaning(queue, settings, cache):
    """Ask the AI which other reports add something new, for several stories in one request. Saves the answers."""
    if not queue or not (GEMINI_KEY or GROQ_KEY):
        return 0
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    used = cache.get("calls", {}).get(today, 0)
    per_day, per_run, per_call = settings.get("meaning_calls_per_day", 48), settings.get("meaning_calls_per_run", 2), 15
    done = 0
    for start in range(0, len(queue), per_call):
        if used >= per_day or done >= per_run:
            break
        batch = queue[start:start + per_call]
        blocks = []
        for gi, (key, main, cands) in enumerate(batch, 1):
            lines = [f"GROUP {gi}", f"MAIN: {main['title']}" + (f" | {main['summary'][:300]}" if len(main.get('summary') or '') >= 40 else "")]
            for ci, c in enumerate(cands, 1):
                lines.append(f"OTHER {ci} ({c['source']}): {c['title']}" + (f" | {c['summary'][:300]}" if len(c.get('summary') or '') >= 40 else ""))
            blocks.append("\n".join(lines))
        try:
            text, model = council_call("checkers", MEANING_PROMPT % "\n\n".join(blocks), settings)
            used += 1
            done += 1
            reply = parse_ai_json(text)
        except Exception as e:
            print(f"  meaning check failed ({str(e)[:80]})")
            break
        for g in reply.get("groups", []):
            try:
                key, main, cands = batch[int(g["g"]) - 1]
                keep = [int(i) - 1 for i in g.get("keep", []) if 0 < int(i) <= len(cands)]
                cache.setdefault("groups", {})[key] = {"keep": keep, "disagree": str(g.get("disagree") or "").strip()[:300],
                                                       "made": datetime.now(timezone.utc).isoformat()}
            except (KeyError, ValueError, IndexError, TypeError):
                continue
        print(f"  meaning check: {len(batch)} stories judged by {model}")
    cache.setdefault("calls", {})[today] = used
    cache["calls"] = {d: n for d, n in cache["calls"].items() if d == today}
    return done


# ---------------------------------------------------------------- Sinhala and Tamil
LANGS = {"si": "Sinhala", "ta": "Tamil"}

TITLES_PROMPT = """Translate these news headlines from English into Sinhala and Tamil for a Sri Lankan news app.
Translate the MEANING naturally, the way a Sri Lankan newspaper would write it, not word for word.
Keep every number, date and amount exactly. Keep names of people, places and organisations, written in the
Sinhala or Tamil script the way Sri Lankan media usually write them.

Also give each headline its topic, judged by MEANING: one of Politics, Economy, Business, Sports, Tech, Health,
Weather, Entertainment, Astrology, Society.

Reply with ONLY this JSON, nothing else:
{"items": [{"n": 1, "si": "...", "ta": "...", "topic": "..."}, ...]}

%s
"""

CARDS_PROMPT = """Translate this news story from English into %s for a Sri Lankan news app.
Translate the MEANING naturally, the way a Sri Lankan newspaper would write it, not word for word.
Keep every number, date and amount exactly. Keep names of people, places and organisations, written in
%s script the way Sri Lankan media usually write them. Do not add or remove any information.

Reply with ONLY this JSON (same keys, same number of items in each list), nothing else:
%s
"""


SCRIPTS = {"si": (0x0D80, 0x0DFF), "ta": (0x0B80, 0x0BFF)}


def right_script(text, lang):
    """A real Sinhala/Tamil translation is written in that script: at least 70% of its letters, none of the other
    script, and no English words except short acronyms (so no "Tamil headline" leftovers and names are written in
    the reader's script too). Catches garbage from weak AI models."""
    if lang not in SCRIPTS or not isinstance(text, str):
        return True
    lo, hi = SCRIPTS[lang]
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return False
    own = sum(1 for ch in letters if lo <= ord(ch) <= hi)
    other = sum(1 for l, (a, b) in SCRIPTS.items() if l != lang for ch in letters if a <= ord(ch) <= b)
    # every word in the reader's language: English words are allowed only as short acronyms (IMF, US, NBC)
    english = [w for w in re.findall(r"[A-Za-z]{2,}", text) if not (w.isupper() and len(w) <= 5)]
    return own / len(letters) >= 0.7 and other == 0 and not english


def good_translation(value, lang):
    if isinstance(value, dict):
        return all(good_translation(v, lang) for v in value.values())
    if isinstance(value, list):
        return all(good_translation(v, lang) for v in value)
    return right_script(value, lang)


def _same_numbers(a, b):
    nums = lambda t: sorted(re.findall(r"\d+(?:[.,]\d+)?", str(t).replace(",", "")))
    return nums(a) == nums(b)


def translate_site(site_stories, settings, cache):
    """Translate new headlines (many per request) and summaries (one story per request) into Sinhala and Tamil.
    Every number must survive the translation, or that translation is thrown away. Saved, so each is done once."""
    if not GEMINI_KEY:                       # only the strong AI translates (weak ones produced garbage)
        return 0
    settings = {**settings, "council": {**settings.get("council", {}), "writers": ["gemini:gemini-flash-latest", "gemini:gemini-2.5-flash"]}}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    used = cache.get("calls", {}).get(today, 0)
    per_day, per_run = settings.get("translate_calls_per_day", 80), settings.get("translate_calls_per_run", 4)
    titles, cards = cache.setdefault("titles", {}), cache.setdefault("cards", {})
    done = 0
    key = lambda t: hashlib.sha1(t.encode()).hexdigest()[:16]
    # 1. headlines, 30 per request, newest stories first
    todo = [s for s in site_stories if key(s["title"]) not in titles]
    for start in range(0, len(todo), 30):
        if used >= per_day or done >= per_run or minutes_used() > 9:
            break
        batch = todo[start:start + 30]
        try:
            text, model = council_call("writers", TITLES_PROMPT % "\n".join(f"{i}. {s['title']}" for i, s in enumerate(batch, 1)), settings)
            used += 1; done += 1
            for item in parse_ai_json(text).get("items", []):
                n = int(item.get("n", 0))
                if not 0 < n <= len(batch):
                    continue
                st = batch[n - 1]
                tr = {l: str(item.get(l, "")).strip() for l in LANGS if str(item.get(l, "")).strip() and _same_numbers(st["title"], item.get(l, ""))
                      and right_script(str(item.get(l, "")), l)}
                if item.get("topic") in TOPICS:
                    tr["topic"] = item["topic"]
                titles[key(st["title"])] = {**tr, "made": datetime.now(timezone.utc).isoformat()}
            print(f"  translated {len(batch)} headlines ({model})")
        except Exception as e:
            print(f"  headline translation failed ({str(e)[:80]})")
            break
    # 2. full summaries, one language per request, most-covered stories first
    order = {s["id"]: i for i, s in enumerate(site_stories)}          # keeps the order given (the Top 10 first)
    for st in sorted([s for s in site_stories if s.get("cards")], key=lambda s: order[s["id"]]):
        for lang, lname in LANGS.items():
            if used >= per_day or done >= per_run or minutes_used() > 9.5:
                break
            if lang in cards.get(st["id"], {}):
                continue
            c = st["cards"]
            fields = {k: c.get(k) for k in ("what_happened", "details", "why_it_matters", "key_facts", "whats_next", "blurb", "spoken") if c.get(k)}
            try:
                text, model = council_call("writers", CARDS_PROMPT % (lname, lname, json.dumps(fields, ensure_ascii=False, indent=1)), settings)
                used += 1; done += 1
                got = parse_ai_json(text)
                ok = all(k in got and (len(got[k]) == len(v) if isinstance(v, list) else True) for k, v in fields.items())
                if ok and _same_numbers(json.dumps(fields, ensure_ascii=False), json.dumps({k: got[k] for k in fields}, ensure_ascii=False)) \
                        and good_translation({k: got[k] for k in fields}, lang):
                    cards.setdefault(st["id"], {"made": datetime.now(timezone.utc).isoformat()})[lang] = {k: got[k] for k in fields}
                    print(f"  translated summary into {lname} ({model})")
                else:
                    cards.setdefault(st["id"], {"made": datetime.now(timezone.utc).isoformat()})[lang] = None   # don't retry a bad one
                    print(f"  {lname} summary dropped: numbers or parts didn't match")
            except Exception as e:
                print(f"  summary translation failed ({str(e)[:80]})")
                break
    cache.setdefault("calls", {})[today] = used
    cache["calls"] = {d: n for d, n in cache["calls"].items() if d == today}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=4)).isoformat()
    cache["titles"] = {k: v for k, v in titles.items() if v.get("made", "") > cutoff}
    cache["cards"] = {k: v for k, v in cards.items() if v.get("made", "") > cutoff}
    return done


def add_translations(site_stories, cache):
    """Put the Sinhala and Tamil versions next to each story on the website ("tr": {"si": {...}, "ta": {...}})."""
    key = lambda t: hashlib.sha1(t.encode()).hexdigest()[:16]
    for st in site_stories:
        t = cache.get("titles", {}).get(key(st["title"]), {})
        c = cache.get("cards", {}).get(st["id"], {})
        if t.get("topic") in TOPICS and not st.get("cards"):
            st["topic"] = t["topic"]          # the AI's topic (by meaning) beats the keyword guess
        tr = {}
        for lang in LANGS:
            entry = {}
            if t.get(lang) and right_script(t[lang], lang):
                entry["title"] = t[lang]
            if st.get("cards") and c.get(lang) and good_translation(c[lang], lang):
                entry["cards"] = c[lang]
            if entry:
                tr[lang] = entry
        if tr:
            st["tr"] = tr
        else:
            st.pop("tr", None)


def strip_boilerplate(stories, min_repeats=3):
    """Learns each site's repeated headline pieces (its name, a slogan, 'Print Edition'...) and removes them.
    A piece at the start or end of a headline (split at ' - ', ' | ', ': ') that appears in 3+ headlines from
    the same site is not news, it's the site's own label. Works for any site, including new ones."""
    from collections import Counter, defaultdict
    seps = r"\s+[-–|]\s+|:\s+"
    by_src = defaultdict(list)
    for s in stories:
        by_src[s["source"]].append(s)
    out = []
    for src, items in by_src.items():
        heads, tails = Counter(), Counter()
        for s in items:
            parts = re.split(seps, s["title"])
            if len(parts) > 1:
                heads[parts[0].strip().lower()] += 1
                tails[parts[-1].strip().lower()] += 1
        bad_heads = {h for h, n in heads.items() if n >= min_repeats and len(h.split()) >= 2}
        bad_tails = {t for t, n in tails.items() if n >= min_repeats and len(t.split()) >= 1}
        for s in items:
            parts = re.split(f"({seps})", s["title"])
            changed = True
            while changed and len(parts) >= 3:
                changed = False
                if parts[0].strip().lower() in bad_heads:
                    parts = parts[2:]; changed = True
                elif len(parts) >= 3 and parts[-1].strip().lower() in bad_tails:
                    parts = parts[:-2]; changed = True
            title = "".join(parts).strip()
            if title and title != s["title"]:
                s = {**s, "title": title}
            if not is_site_name(s):
                out.append(s)
    return out


SITE_PREFIX = re.compile(r"^[^-–|:]*\b(latest|breaking|online)\b[^-–|:]*\b(news|headlines)\b[^-–|:]*\s*[-–|:]\s*(print edition\s*[-–|:]?\s*)?"
                         r"|^print edition\s*[-–|:]\s*", re.I)
SITE_WORDS = set("""news breaking latest online live today daily headlines headline update updates 24 hours hour 24x7 portal
home homepage page official website site web the and of in on for from to sri lanka lankan lk english sinhala tamil
top stories story first entertainment sports section category""".split())


def is_site_name(story):
    """True when a 'headline' is really a website's name or slogan (e.g. 'Sri Lanka 24 Hours Online Breaking News'):
    it has no real words of its own beyond generic news-site words and the source's own name."""
    words = re.findall(r"[a-z0-9]+", story["title"].lower())
    own = set(re.findall(r"[a-z0-9]+", story.get("source", "").lower()))
    real = [w for w in words if w not in SITE_WORDS and w not in own]
    if len(real) < 2:
        return True
    # "Sri Lanka Sports News Today | Live Cricket, Rugby & Local Sports Updates": a site's name, then its slogan
    parts = re.split(r"\s[|–—]\s|\s-\s", story["title"])
    if len(parts) > 1:
        first = [w for w in re.findall(r"[a-z0-9]+", parts[0].lower()) if w not in SITE_WORDS and w not in own]
        return len(first) <= 1 and (story["title"].rstrip().endswith(("…", "...")) or bool(re.search(r"\b(live|updates?|latest)\b", parts[1], re.I)))
    return False

IMAGES_FILE = os.path.join(ROOT, "data", "images.json")
IMAGE_SIZES_FILE = os.path.join(ROOT, "data", "image_sizes.json")
MIN_PHOTO_W, MIN_PHOTO_H = 700, 400   # smaller photos get stretched and look blurry: use the clean cover instead


def bigger_image(url):
    """Many feeds give a tiny preview; the same photo usually exists in a big size. Ask for the big one."""
    u = url or ""
    u = re.sub(r"(ichef\.bbci\.co\.uk/(?:ace|news)/(?:standard|ws|branded_news|branded_sport)?/?)\d{2,4}/", r"\g<1>1024/", u)
    u = re.sub(r"-\d{2,4}x\d{2,4}(\.(?:jpe?g|png|webp))(\?|$)", r"\1\2", u, flags=re.I)          # WordPress thumbnails
    p = urllib.parse.urlsplit(u)
    if p.query:
        q = urllib.parse.parse_qsl(p.query, keep_blank_values=True)
        out, changed = [], False
        for k, v in q:
            if k.lower() in ("w", "width") and v.isdigit() and int(v) < 1000:
                out.append((k, "1200")); changed = True
            elif k.lower() in ("h", "height") and v.isdigit() and int(v) < 1000:
                changed = True                       # drop the small height: the site keeps the photo's shape
            else:
                out.append((k, v))
        if changed:
            u = urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, urllib.parse.urlencode(out), p.fragment))
    return u


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def image_size(url):
    """(width, height) from the first part of the file only; None if unknown."""
    try:
        from PIL import Image, ImageFile
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Range": "bytes=0-131071"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read(131072)
        return Image.open(io.BytesIO(data)).size
    except Exception:
        return None


def sharp_enough(size):
    return bool(size) and size[0] >= MIN_PHOTO_W and size[1] >= MIN_PHOTO_H


BAD_IMAGE = re.compile(r"logo|icon|favicon|placeholder|default|avatar|sprite|blank|\.svg|/ads?/|banner", re.I)


def _page_image(url):
    """The article's own photo: og:image from the page, or the first real picture via the reader service."""
    if "news.google.com" not in url and "bing.com" not in url:
        try:
            raw = fetch(url, timeout=12).decode("utf-8", errors="replace")[:200000]
            m = re.search(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)', raw, re.I) \
                or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\']', raw, re.I)
            if m and not BAD_IMAGE.search(m.group(1)):
                return html.unescape(m.group(1)).strip()
        except Exception:
            pass
    try:
        req = urllib.request.Request("https://r.jina.ai/" + url, headers={
            "User-Agent": UA, "Accept": "text/plain", "X-With-Images-Summary": "true", "X-Retain-Images": "none"})
        with urllib.request.urlopen(req, timeout=25) as r:
            text = r.read().decode("utf-8", errors="replace")
        for img in re.findall(r"!\[[^\]]*\]\((https?://[^)\s]+)\)", text):
            if not BAD_IMAGE.search(img) and re.search(r"\.(jpe?g|png|webp)(\?|$)", img, re.I):
                return img
    except Exception:
        pass
    return ""


def add_story_images(site_stories, settings):
    """Stories without a photo get their article's own photo (fetched once per story, saved).
    A picture that many stories from one site share is that site's logo, not a news photo: it's dropped."""
    from concurrent.futures import ThreadPoolExecutor
    cache = load_json(IMAGES_FILE, {})
    todo = [s for s in site_stories if not s.get("image") and s["id"] not in cache][:settings.get("images_per_run", 24)]
    if todo:
        with ThreadPoolExecutor(max_workers=6) as pool:
            for s, img in zip(todo, pool.map(lambda s: _page_image(s["link"]), todo)):
                cache[s["id"]] = img
        print(f"  photos: looked up {len(todo)}, found {sum(1 for s in todo if cache[s['id']])}")
    for s in site_stories:
        if not s.get("image") and cache.get(s["id"]):
            s["image"] = cache[s["id"]]
    # same picture on 3+ stories from one site = a logo or stock picture
    from collections import Counter
    used = Counter((s["source"], s.get("image")) for s in site_stories if s.get("image"))
    for s in site_stories:
        if s.get("image") and (used[(s["source"], s["image"])] >= 3 or BAD_IMAGE.search(s["image"])):
            s["image"] = ""
    ids = {s["id"] for s in site_stories}
    save_json(IMAGES_FILE, {k: v for k, v in cache.items() if k in ids})
    # big version first; a photo too small to look sharp is dropped (the clean topic cover is used instead)
    sizes = load_json(IMAGE_SIZES_FILE, {})
    for s in site_stories:
        if s.get("image"):
            s["image_small"] = s["image"]
            s["image"] = bigger_image(s["image"])
    day_ago = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    sizes = {k: v for k, v in sizes.items() if not (isinstance(v, dict) and v.get("failed", "") < day_ago) and v is not None}
    check = list({u for s in site_stories for u in (s.get("image"), s.get("image_small")) if u and u not in sizes})[:settings.get("image_checks_per_run", 60)]
    if check:
        with ThreadPoolExecutor(max_workers=8) as pool:
            for u, sz in zip(check, pool.map(image_size, check)):
                sizes[u] = list(sz) if sz else {"failed": now_iso()}       # a hiccup is retried tomorrow
    dropped = 0
    for s in site_stories:
        small = s.pop("image_small", "")
        if not s.get("image"):
            continue
        known = lambda u: isinstance(sizes.get(u), list)
        if s["image"] != small and s["image"] in sizes and not known(s["image"]):   # no big version: use the original
            s["image"] = small
        if known(s["image"]) and not sharp_enough(sizes[s["image"]]):
            s["image"] = ""; dropped += 1
    if dropped:
        print(f"  photos: {dropped} too small to look sharp, using the clean cover")
    keep = {s.get("image") for s in site_stories} | set(check)
    save_json(IMAGE_SIZES_FILE, {k: v for k, v in sizes.items() if k in keep})


SUBJECTS_FILE = os.path.join(ROOT, "data", "subjects.json")


def _subject_key(name):
    words = [w for w in re.findall(r"[a-z0-9]+", (name or "").lower()) if w not in ("the", "a", "of", "and", "in", "sri", "lanka", "lankan")]
    return " ".join(words)


def living_categories(site_list, now, settings):
    """Living categories: a subject people keep hearing about (5+ stories over 2+ days in the last week) grows into
    its own section with a "story so far"; a week without new stories sends it to the archive. Subjects are matched
    loosely (same words), so "2027 Budget" and "Budget 2027" are one subject. No extra AI: the summary names it."""
    data = load_json(SUBJECTS_FILE, {"subjects": {}})
    subs = data["subjects"]
    for st in site_list:
        name = ((st.get("cards") or {}).get("subject") or "").strip()
        key = _subject_key(name)
        if not key or len(key) < 3:
            continue
        kw = set(key.split())
        match = next((k for k in subs if set(k.split()) == kw or (len(kw) >= 2 and (kw <= set(k.split()) or set(k.split()) <= kw) and len(set(k.split()) & kw) >= 2)
                      or (len(set(k.split()) & kw) / max(1, len(set(k.split()) | kw))) >= 0.66), key)
        e = subs.setdefault(match, {"name": name, "stories": {}, "first": now.isoformat()})
        e["stories"][st["id"]] = (st.get("date") or now.isoformat())[:19]
        e["last"] = max(e.get("last", ""), e["stories"][st["id"]])
    week = (now - timedelta(days=7)).isoformat()
    active, archived = [], []
    for k, e in subs.items():
        recent = {i: d for i, d in e["stories"].items() if d >= week[:19]}
        days = {d[:10] for d in recent.values()}
        if len(recent) >= settings.get("living_min_stories", 5) and len(days) >= 2:
            active.append({"name": e["name"], "key": k, "stories": sorted(recent, key=lambda i: recent[i]), "count": len(recent),
                           "since": min(recent.values())[:10]})
        elif e.get("last", "") < week[:19] and len(e["stories"]) >= 5:
            archived.append({"name": e["name"], "key": k, "count": len(e["stories"]), "until": e.get("last", "")[:10]})
    # forget one-off subjects after a month; keep grown ones (their knowledge stays in the archive)
    month = (now - timedelta(days=30)).isoformat()[:19]
    data["subjects"] = {k: e for k, e in subs.items() if e.get("last", "") >= month or len(e["stories"]) >= 5}
    save_json(SUBJECTS_FILE, data)
    active.sort(key=lambda a: -a["count"])
    if active:
        print(f"  living categories: {', '.join(a['name'] + ' (' + str(a['count']) + ')' for a in active[:8])}")
    return active[:8], archived[-20:]


def send_facts(site_list, state, now):
    """Wire Now Fact Base: every checked summary's key facts go into our own database, each with who reported it
    and when (confirmed = 2+ outlets). Uses no AI. Only stories not sent before."""
    url = sb_base_url(os.environ.get("SUPABASE_URL", ""))
    if not (url.startswith("https://") and TOKEN):
        return
    sent = set(state.get("facts_sent", []))
    new = [s for s in site_list if s.get("cards") and s["id"] not in sent][:60]
    if not new:
        return
    facts, people = [], {}
    for s in new:
        c, loc = s["cards"], s.get("location") or {}
        srcs = [x for x in (c.get("sources") or [s["source"]]) if x][:20]
        for st in [c.get("what_happened", "")] + list(c.get("key_facts") or []):
            st = (st or "").strip()
            if len(st) < 15:
                continue
            facts.append({"key": hashlib.sha256((s["id"] + "|" + st).encode()).hexdigest()[:40], "story_id": s["id"],
                          "statement": st[:600], "topic": s.get("topic", ""), "country": loc.get("country", ""),
                          "place": loc.get("place", ""), "sources": srcs, "source_count": len(set(srcs)),
                          "link": s.get("link", ""), "reported_at": s.get("date") or now.isoformat()})
        if c.get("person"):
            p = people.setdefault(c["person"].lower(), {"display": c["person"], "role": c.get("role", ""),
                                                        "country": loc.get("country", ""), "stories": [], "mentions": 0})
            p["stories"].append(s["id"]); p["mentions"] += 1
    key = hashlib.sha256(("wire-now-robot|" + TOKEN).encode()).hexdigest()
    try:
        req = urllib.request.Request(url + "/functions/v1/facts", data=json.dumps({"facts": facts, "people": list(people.values())}).encode(),
                                     headers={"Content-Type": "application/json", "x-robot-key": key, "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            got = json.loads(r.read().decode())
        state["facts_sent"] = (list(sent) + [s["id"] for s in new])[-3000:]
        print(f"  Fact Base: {got.get('facts', 0)} facts and {got.get('people', 0)} people saved")
    except Exception as e:
        print(f"  Fact Base not reachable yet ({str(e)[:60]})")


def reader_stats():
    """The owner's private reader numbers (anonymous counts), through the robot-only "facts" helper."""
    url = sb_base_url(os.environ.get("SUPABASE_URL", ""))
    if not (url.startswith("https://") and TOKEN) or TEST_MODE:
        return {}
    key = hashlib.sha256(("wire-now-robot|" + TOKEN).encode()).hexdigest()
    try:
        req = urllib.request.Request(url + "/functions/v1/facts", data=b'{"stats": true}',
                                     headers={"Content-Type": "application/json", "x-robot-key": key, "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"  reader stats not reachable ({str(e)[:60]})")
        return {}


def world_pulse(site_list, state, settings, now):
    """🌍 The owner's private daily World Pulse (Level 2): every run adds today's stories to the trend memory (no AI);
    once a day in the evening (or when the owner sends /pulse) the AI explains where things are heading, with
    predictions that later briefings mark right or wrong. Sent only to the owner on Telegram, never published."""
    sl = now.astimezone(timezone(timedelta(hours=5, minutes=30)))
    today = sl.strftime("%Y-%m-%d")
    hist = pulse.record(private_load("pulse", {}), site_list, today)
    owner, force = state.get("owner_chat"), state.get("pulse_force")
    due = force or (sl.hour >= settings.get("pulse_hour", 19) and hist.get("last_sent") != today)
    if due and owner and ANY_AI and not TEST_MODE and minutes_used() < 10.5:
        titles = {s["id"]: s.get("title", "") for s in site_list}
        stats = pulse.stats_text(reader_stats(), titles)
        try:
            reply, model = council_call("writers", pulse.build_prompt(pulse.trends(hist, today), hist, today, stats), settings)
            body = pulse.apply_reply(hist, reply, today)
            msg = f"🌍 WORLD PULSE · {sl.strftime('%d %b %Y')} (private)\n\n{body}"
            msg += "".join("\n\n" + x for x in (pulse.score_line(hist), ("📊 READERS\n" + stats) if stats else "") if x)
            for i in range(0, len(msg), 3900):
                telegram("sendMessage", {"chat_id": owner, "text": msg[i:i + 3900], "disable_web_page_preview": "true"})
            hist["last_sent"] = today
            state.pop("pulse_force", None)
            print(f"\nWorld Pulse sent to the owner ({model})")
        except Exception as e:
            print(f"\nWorld Pulse not made this run: {str(e)[:100]}")
    private_save("pulse", hist)


def sb_base_url(u):
    """The bare project address, even if someone pasted it with /rest/v1/ on the end."""
    return re.sub(r"/(rest|auth|functions|storage|realtime)/v1/?$", "", (u or "").strip().rstrip("/")).rstrip("/")


def sb_headers(key):
    """New publishable keys (sb_publishable_...) are not JWTs, so they must not go in the Authorization header."""
    return {"apikey": key, "Authorization": "Bearer " + key} if key.startswith("eyJ") else {"apikey": key}


def reader_summaries():
    """Summaries written on request from the website (stored in the community database). {} if not set up."""
    url, key = sb_base_url(os.environ.get("SUPABASE_URL", "")), os.environ.get("SUPABASE_ANON_KEY", "").strip()
    if not url.startswith("https://") or not key:
        return {}
    since = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        req = urllib.request.Request(f"{url}/rest/v1/summaries?select=story_id,cards&status=eq.ready&updated_at=gte.{since}&limit=1000",
                                     headers={**sb_headers(key), "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            rows = json.loads(r.read().decode())
        out = {row["story_id"]: row["cards"] for row in rows if isinstance(row.get("cards"), dict) and row["cards"].get("what_happened")}
        print(f"  reader summaries from the website: {len(out)}")
        return out
    except Exception as e:
        print(f"  reader summaries not available ({str(e)[:80]})")
        return {}


def read_with_jina(url):
    """Free reader service: fetches the page from its own servers (some news sites block GitHub)
    and follows Google News redirects. Returns plain text or ''."""
    try:
        req = urllib.request.Request("https://r.jina.ai/" + url, headers={
            "User-Agent": UA, "Accept": "text/plain", "X-Return-Format": "text"})
        with urllib.request.urlopen(req, timeout=45) as r:
            raw = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"    reader service failed ({str(e)[:80]})")
        return ""
    body = raw.split("Markdown Content:", 1)[-1]
    # keep real sentences only (drop menus, links and short lines)
    lines = [l.strip() for l in body.splitlines()]
    paras = [l for l in lines if len(l) > 60 and l.count(" ") > 8 and not l.startswith(("[", "!", "*", "#", "|"))
             and not re.search(r"cookie|subscribe|all rights reserved|copyright ©|sign up|newsletter", l, re.I)]
    return "\n".join(dict.fromkeys(paras))[:9000]


read_jina = read_with_jina  # (tests replace this)


def read_article(url):
    text, og = "", ""
    if "news.google.com" not in url and "bing.com" not in url:
        try:
            raw = fetch(url).decode("utf-8", errors="replace")
            p = ArticleText()
            try:
                p.feed(raw)
            except Exception:
                pass
            text = "\n".join(dict.fromkeys(p.paras))[:9000]  # remove repeated paragraphs
            og = p.og_image
        except Exception as e:
            print(f"    site blocked us ({str(e)[:60]}) - trying the reader service")
    if len(text) < 300:
        jt = read_jina(url)
        if len(jt) > len(text):
            print(f"    reader service got {len(jt)} characters")
            text = jt
    if len(text) < 300 and GEMINI_KEY and GOOGLE_READS["left"] > 0 and "news.google.com" not in url:
        gt = read_with_google(url)                # Google's own servers open the page (sites rarely block Google)
        if len(gt) > len(text):
            print(f"    Google reader got {len(gt)} characters")
            text = gt
    return text, og


GOOGLE_READS = {"left": 3}                        # per run: each one uses one Gemini request


def read_with_google(url):
    """Ask Gemini to open the article itself (its 'URL context' tool) and copy out the article text.
    Used only when the site and the free reader service both failed."""
    GOOGLE_READS["left"] -= 1
    prompt = ("Open this news article and copy out its full text faithfully as plain paragraphs: every fact, number, "
              "name, date and quote, nothing added, no comments, no summary. If you cannot open it, reply only NONE.\n\n" + url)
    for model in ("gemini-flash-latest", "gemini-2.5-flash"):
        req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                     data=json.dumps({"contents": [{"parts": [{"text": prompt}]}], "tools": [{"url_context": {}}],
                                                      "generationConfig": {"temperature": 0}}).encode(),
                                     headers={"x-goog-api-key": GEMINI_KEY, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.load(r)
            parts = ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
            text = "\n".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
            USAGE["count"]["gemini"] = USAGE["count"].get("gemini", 0) + 1
            return "" if text.upper().startswith("NONE") else text[:9000]
        except urllib.error.HTTPError as e:
            if e.code != 404:
                print(f"    Google reader failed ({e.code})")
                return ""
        except Exception as e:
            print(f"    Google reader failed ({str(e)[:60]})")
            return ""
    return ""


# ======================================================================
# same event? + research across sites
# ======================================================================

STOP = set("""about after again also amid among before being between could during first from have into
just last more most news over said says should since some than that their them then there these they
this those through under until very were what when where which while will with would year years
today week sri lanka lankan says""".split())


def keywords(title):
    return {w for w in re.findall(r"[a-z0-9]+", title.lower()) if len(w) > 3 and w not in STOP}


def same_event(t1, t2):
    a, b = keywords(t1), keywords(t2)
    if not a or not b:
        return False
    common = len(a & b)
    return common >= 3 and common / min(len(a), len(b)) >= 0.5


def search_news(title, limit=6):
    """Free news search (Bing News RSS). Returns [{title, link, source}] with real article links."""
    words = sorted(keywords(title), key=len, reverse=True)[:6]
    if not words:
        return []
    url = "https://www.bing.com/news/search?format=rss&q=" + urllib.parse.quote(" ".join(words))
    try:
        root = parse_xml(fetch(url))
    except Exception as e:
        print(f"    search failed: {e}")
        return []
    out, total = [], 0
    for el in root.iter():
        if local_name(el.tag) != "item":
            continue
        total += 1
        link = child_text(el, "link")
        m = re.search(r"[?&]url=([^&]+)", link)
        if m:
            link = urllib.parse.unquote(m.group(1))
        t = strip_html(child_text(el, "title"))
        if link.startswith("http") and same_event(title, t):
            out.append({"title": t, "link": link, "source": child_text(el, "source") or urllib.parse.urlparse(link).netloc.replace("www.", "")})
        if len(out) >= limit:
            break
    print(f"    news search: {total} results, {len(out)} about this story")
    return out


SERIOUS = re.compile(r"\b(kill(?:s|ed|ing)?|dead|death|deaths|died|dies|murder\w*|shot|shoot\w*|stab\w*|attack\w*|"
                     r"bomb\w*|blast|explosion|explod\w*|fire|blaze|crash\w*|accident\w*|collapse\w*|flood\w*|"
                     r"landslide\w*|earthquake|tsunami|cyclone|storm|disaster|emergency|missing|kidnap\w*|"
                     r"arrest\w*|riot\w*|protest\w*|curfew|war|strike[sd]?|injur\w*|victim\w*|hostage\w*|"
                     r"resign\w*|impeach\w*|assassinat\w*|coup|outbreak|epidemic|evacuat\w*)\b", re.I)


WARN_WORDS = re.compile(r"\b(warning|warns?|alert|advisory|red notice|amber|evacuat\w*|precaution\w*)\b", re.I)
HAZARD_WORDS = re.compile(r"\b(landslide\w*|flood\w*|cyclone|tsunami|rain\w*|storm|thunder\w*|lightning|wind\w*|"
                          r"drought|heat|monsoon|depression|sea|tidal)\b", re.I)


def is_warning(story):
    """A disaster or weather warning for Sri Lanka (flood, landslide, cyclone, tsunami, heavy rain...)."""
    t = story["title"] + " " + story.get("summary", "")[:200]
    return story["region"] == "sri_lanka" and bool(WARN_WORDS.search(t) and HAZARD_WORDS.search(t))


def is_breaking(story, now, hours=2):
    """Serious Sri Lankan news from the last couple of hours."""
    if story["region"] != "sri_lanka" or not SERIOUS.search(story["title"]):
        return False
    if now - datetime.fromisoformat(story["date"]) > timedelta(hours=hours):
        return False
    loc = places.location_for(story)
    return not loc or loc.get("country") in ("", "Sri Lanka")


PRESS_RELEASE = re.compile(r"\b(launch(es|ed)?|unveil\w*|partners? with|partnership|joins hands|inaugurat\w*|opens new|"
                           r"felicitat\w*|celebrat\w*|anniversary|award\w*|wins? (gold|silver|bronze|best)|recogni[sz]ed|"
                           r"sponsor\w*|csr|donat\w*|showroom|outlet|promotion|offer|discount|brand ambassador|"
                           r"plc|pvt|\(pvt\)|ltd|holdings|group chairman|ceo of|records? (profit|growth)|"
                           r"delivers .{0,30}growth|interim results|quarterly results|"
                           r"posts? .{0,40}(profit|topline|bottom ?line|earnings|revenue|turnover)|"
                           r"(9|nine|six|6|three|3)[- ]months?|topline|bottom ?line|earnings|net profit|pat\b)\b", re.I)


def is_press_release(story):
    """Company announcements written like news (product launches, awards, profit results, CSR events)."""
    t = story["title"]
    return bool(PRESS_RELEASE.search(t)) and not SERIOUS.search(t)


def is_foreign(story):
    """A story from a Sri Lankan outlet that is clearly about another country."""
    loc = places.location_for(story)
    return bool(loc) and loc.get("country") not in ("", "Sri Lanka") and not (loc.get("also") and "Sri Lanka" in loc["also"])


def is_important(story):
    """Serious events, or anything several outlets are reporting, get researched and fully summarised."""
    return story.get("coverage", 1) >= 2 or bool(SERIOUS.search(story["title"] + " " + story.get("summary", "")[:300]))


def research(story, related, settings, important=True):
    """Read the story (plus, for important news, other coverage of the same event).
    Returns (combined_text, source_names, image)."""
    # every story is checked against other websites: up to 5 for important news, up to 3 for normal news
    max_articles = settings.get("research_max_articles", 5) if important else settings.get("normal_max_articles", 3)
    candidates = [story] + related
    if settings.get("research_search", True):  # look further than our own feeds
        for r in search_news(story["title"]):
            if not any(r["link"] == c["link"] for c in candidates):
                candidates.append({**r, "summary": "", "image": ""})
    parts, names, image, seen_sites = [], [], story.get("image", ""), set()
    for c in candidates:
        if len(parts) >= max_articles:
            break
        site = urllib.parse.urlparse(c["link"]).netloc.replace("www.", "")
        if site in seen_sites and c is not story:
            continue
        text, og = read_article(c["link"])
        if len(text) < 300 and len(c.get("summary", "")) > len(text):
            text = c.get("summary", "")
        if len(text) < 200:
            continue
        seen_sites.add(site)
        image = image or og or c.get("image", "")
        parts.append(f"[{len(parts) + 1}] SOURCE: {c['source']}\n{text[:6000]}")
        names.append(c["source"])
    return "\n\n".join(parts), names, image


# ======================================================================
# AI story cards + safety checks
# ======================================================================

WRITER_PROMPT = """You turn a news article into short story cards for a news app.

STRICT RULES - follow every one:
- Use ONLY facts written in the ARTICLE below. Do not add background, guesses or opinions.
- Copy every number, date, amount, name and place EXACTLY as the article writes it.
- NOTHING LEFT OUT: include EVERY piece of information the article gives (every number, name, place, date,
  statement, reason and next step), in simpler words. Not broad or wordy, but complete: a reader must learn
  everything the article says without opening it. A longer article needs a longer summary.
- If the article does not say why it matters, set "why_it_matters" to "".
- If the article does not say what happens next, set "whats_next" to "".
- Write in simple English, in your OWN words. Never copy whole sentences from the article.
- "what_happened": up to 3 sentences - the core of the story.
- "details": 2 to 4 short paragraphs (2-3 sentences each) that together explain EVERYTHING the article
  says: who is involved, what exactly happened, where, when, how and why, the numbers, any background,
  and what each side said. If the article is about a chart, report, budget or law, explain what it
  actually shows or contains and what it means - not just that it exists. A reader should not need
  to open the article to understand the story.
- "key_facts": 4 to 8 short points (each under 20 words) that together cover EVERY main point of the article,
  like a bullet-point summary: who, what, where, when, how many, what was said, what happens next.
- "blurb": one sentence (under 25 words) that makes people want to read more, using only article facts.
- "topic": one of: Politics, Economy, Business, Sports, Tech, Health, Weather, Entertainment, Astrology, Society.
- "country": the country the story mainly happens in (e.g. "Sri Lanka", "India", "United States"), "" if unclear.
- "place": the city, town or area where it happened, ONLY if the text names it (e.g. "Wellawatte, Colombo"), else "".

- "spoken": 80 to 150 words a friendly radio presenter would SAY to EXPLAIN this story to a listener who knows
  nothing about it: set the scene, explain what happened, why it matters and what happens next (only what the
  article says). Natural spoken sentences, no lists, no symbols, do not repeat the headline word for word.
- "person": the ONE main person the story is about, full name as the article writes it; "" if it is not mainly about one person.
- "role": that person's job or title as the article gives it (e.g. "President", "Health Minister"); "" if none.
- "subject": the ongoing news subject this story belongs to, 1 to 4 words, as a newspaper section would name it
  (e.g. "2027 Budget", "Gaza war", "Microsoft outage", "Dengue outbreak", "Asia Cup"); "" if it is a one-off story.
Reply with ONLY this JSON, nothing else:
{"topic": "...", "country": "...", "place": "...", "what_happened": "...", "details": ["...", "..."], "why_it_matters": "...", "key_facts": ["...", "..."], "whats_next": "...", "blurb": "...", "spoken": "...", "person": "...", "role": "...", "subject": "..."}

HEADLINE: %s

ARTICLE:
%s
"""

RESEARCH_PROMPT = """You turn SEVERAL news articles about the SAME event into short story cards for a news app.
The articles are numbered and each starts with its SOURCE name.

STRICT RULES - follow every one:
- Use ONLY facts written in the ARTICLES below. Do not add background, guesses or opinions.
- Combine the articles: use details from all of them to give the fullest picture.
- Copy every number, date, amount, name and place EXACTLY as the articles write them.
- NOTHING LEFT OUT: include EVERY piece of information the articles give (every number, name, place, date,
  statement, reason and next step), in simpler words. Not broad or wordy, but complete: a reader must learn
  everything the articles say without opening them. Longer articles need a longer summary.
- If articles DISAGREE on a fact (for example a number of people hurt), do not pick one:
  write both with their sources, e.g. "Ada Derana: 3 injured; Newswire: 5 injured".
- If the articles do not say why it matters, set "why_it_matters" to "".
- If the articles do not say what happens next, set "whats_next" to "".
- Write in simple English, in your OWN words. Never copy whole sentences from the articles.
- "what_happened": up to 3 sentences - the core of the story.
- "details": 2 to 4 short paragraphs (2-3 sentences each) that together explain EVERYTHING the article
  says: who is involved, what exactly happened, where, when, how and why, the numbers, any background,
  and what each side said. If the articles are about a chart, report, budget or law, explain what it
  actually shows or contains and what it means - not just that it exists. A reader should not need
  to open the articles to understand the story.
- "key_facts": 4 to 8 short points (each under 20 words) that together cover EVERY main point of the articles,
  like a bullet-point summary: who, what, where, when, how many, what was said, what happens next.
- "blurb": one sentence (under 25 words) that makes people want to read more, using only article facts.
- "topic": one of: Politics, Economy, Business, Sports, Tech, Health, Weather, Entertainment, Astrology, Society.
- "country": the country the story mainly happens in (e.g. "Sri Lanka", "India", "United States"), "" if unclear.
- "place": the city, town or area where it happened, ONLY if the text names it (e.g. "Wellawatte, Colombo"), else "".

- "spoken": 80 to 150 words a friendly radio presenter would SAY to EXPLAIN this story to a listener who knows
  nothing about it: set the scene, explain what happened, why it matters and what happens next (only what the
  article says). Natural spoken sentences, no lists, no symbols, do not repeat the headline word for word.
- "person": the ONE main person the story is about, full name as the article writes it; "" if it is not mainly about one person.
- "role": that person's job or title as the article gives it (e.g. "President", "Health Minister"); "" if none.
- "subject": the ongoing news subject this story belongs to, 1 to 4 words, as a newspaper section would name it
  (e.g. "2027 Budget", "Gaza war", "Microsoft outage", "Dengue outbreak", "Asia Cup"); "" if it is a one-off story.
Reply with ONLY this JSON, nothing else:
{"topic": "...", "country": "...", "place": "...", "what_happened": "...", "details": ["...", "..."], "why_it_matters": "...", "key_facts": ["...", "..."], "whats_next": "...", "blurb": "...", "spoken": "...", "person": "...", "role": "...", "subject": "..."}

HEADLINE: %s

ARTICLES:
%s
"""

SHORT_PROMPT = """You turn a news story into a short, complete summary for a news app.
There may be ONE article or SEVERAL articles about the same story, each starting with its SOURCE name.

STRICT RULES - follow every one:
- Use ONLY facts written in the ARTICLE(S) below. Combine details from all of them.
- If articles DISAGREE on a fact, write both with their sources, e.g. "Ada Derana: 3 injured; Newswire: 5 injured". Do not add background, guesses or opinions.
- Write in simple English, in your OWN words. Never copy whole sentences from the article.
- Copy every number, date, amount, name and place EXACTLY as the article writes it.
- NOTHING LEFT OUT: include EVERY piece of information the article gives (every number, name, place, date,
  statement, reason and next step), in simpler words. Not broad or wordy, but complete: a reader must learn
  everything the article says without opening it. A longer article needs a longer summary.
- "what_happened": ONE complete paragraph of 4 to 6 sentences that tells the whole story: who, what,
  where, when, how and why (as far as the article says). A reader should understand the story fully.
- "key_facts": 2 to 4 short facts from the article (numbers, names, places), each under 15 words.
- "blurb": one sentence (under 25 words) that makes people want to read more, using only article facts.
- "topic": one of: Politics, Economy, Business, Sports, Tech, Health, Weather, Entertainment, Astrology, Society.
- "country": the country the story mainly happens in, "" if unclear.
- "place": the city, town or area where it happened, ONLY if the article names it, else "".

- "spoken": 80 to 150 words a friendly radio presenter would SAY to EXPLAIN this story to a listener who knows
  nothing about it: set the scene, explain what happened, why it matters and what happens next (only what the
  article says). Natural spoken sentences, no lists, no symbols, do not repeat the headline word for word.
- "person": the ONE main person the story is about, full name as the article writes it; "" if it is not mainly about one person.
- "role": that person's job or title as the article gives it (e.g. "President", "Health Minister"); "" if none.
- "subject": the ongoing news subject this story belongs to, 1 to 4 words, as a newspaper section would name it
  (e.g. "2027 Budget", "Gaza war", "Microsoft outage", "Dengue outbreak", "Asia Cup"); "" if it is a one-off story.
Reply with ONLY this JSON, nothing else:
{"topic": "...", "country": "...", "place": "...", "what_happened": "...", "key_facts": ["...", "..."], "blurb": "...", "spoken": "...", "person": "...", "role": "...", "subject": "..."}

HEADLINE: %s

ARTICLE:
%s
"""

FIX_NOTE = """

IMPORTANT: Your last answer had these problems. Fix them by using ONLY words from the article:
%s
"""

CHECKER_PROMPT = """You are a strict fact-checker. Compare the CARDS with the ARTICLE.
For every statement in the cards, check it is clearly stated in the article.
Any number, name, date, place or claim that is not in the article, or is changed, is a problem.
Reply with ONLY this JSON:
{"all_supported": true or false, "problems": ["short description of each problem"]}

ARTICLE:
%s

CARDS:
%s
"""


PROVIDERS = {
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions", lambda: AI_KEY),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", lambda: GEMINI_KEY),
    "groq": ("https://api.groq.com/openai/v1/chat/completions", lambda: GROQ_KEY),
}


RUN_START = time.time()


def minutes_used():
    """How long this run has been going. GitHub stops the robot at 14 minutes, so slow extras stop earlier."""
    return (time.time() - RUN_START) / 60


def ai_chat(model, prompt):
    """model is "provider:model-name" (e.g. "gemini:gemini-2.5-flash"); plain names go to OpenRouter."""
    provider, _, name = model.partition(":") if ":" in model and model.split(":")[0] in PROVIDERS else ("openrouter", "", model)
    url, key = PROVIDERS[provider]
    if provider == "gemini":     # Google's own endpoint: works with both key kinds (AIza... and AQ....)
        def ask(fast):
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/{name}:generateContent",
                data=json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                                 "generationConfig": {"temperature": 0, **({"thinkingConfig": {"thinkingBudget": 0}} if fast else {})}}).encode(),
                headers={"x-goog-api-key": key(), "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=75) as r:
                return json.load(r)
        try:
            try:
                data = ask("flash" in name)                    # no "thinking" for quick jobs (faster)
            except urllib.error.HTTPError as e:
                body = e.read().decode(errors="replace")
                if e.code == 400 and "thinking" in body.lower():
                    data = ask(False)                         # a newer model wants its own thinking setting
                else:
                    raise RuntimeError(f"AI error {e.code}: {body[:300]}")
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"AI error {e.code}: {e.read().decode(errors='replace')[:300]}")
        parts = ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        if not text:
            raise RuntimeError(f"AI error: empty Gemini reply {str(data)[:200]}")
        return text
    body = json.dumps({
        "model": name,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    headers = {"Authorization": f"Bearer {key()}", "Content-Type": "application/json"}
    if provider == "openrouter":
        headers.update({"HTTP-Referer": SITE_URL or "https://github.com", "X-Title": "Wire Now"})
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="replace")[:300]
        raise RuntimeError(f"AI error {e.code}: {msg}")
    if "error" in data:
        raise RuntimeError(f"AI error: {data['error']}")
    return data["choices"][0]["message"]["content"] or ""


ai_call = ai_chat  # (tests replace this)


# ---------------------------------------------------------------- the AI council
COUNCIL_DEFAULT = {
    # "-latest" names follow Google's newest model (new keys can't use some older ones); the older name is the backup
    "writers": ["gemini:gemini-flash-latest", "gemini:gemini-2.5-flash", "openrouter:openrouter/free", "groq:llama-3.3-70b-versatile"],
    "checkers": ["groq:llama-3.3-70b-versatile", "gemini:gemini-flash-lite-latest", "gemini:gemini-2.5-flash-lite", "openrouter:openrouter/free"],
    "daily_requests": {"openrouter": 45, "gemini": 200, "groq": 600},
    "groq_max_chars": 20000,
}
USAGE = {"day": "", "count": {}}     # AI requests used today, per provider (saved in the state file)
DOWN = set()                         # providers that refused us this run (limit reached, bad key...)
DOWN_MODELS = set()                  # single models that don't exist (any more) for this key


def _provider_ok(model, council, prompt_len):
    p = model.split(":")[0] if ":" in model else "openrouter"
    if p in DOWN or not PROVIDERS.get(p, (None, lambda: ""))[1]():
        return False
    if USAGE["count"].get(p, 0) >= council["daily_requests"].get(p, 50):
        return False
    if p == "groq" and prompt_len > council.get("groq_max_chars", 20000):
        return False   # Groq's free plan can't take very long prompts
    return True


BRIEF_PROMPT = """You are a professional television news anchor reading the news bulletin for Wire Now, a Sri Lankan news service.
Write the bulletin script, in %s, for today's top news below, read as ONE bulletin by one anchor.

HOW A PROFESSIONAL ANCHOR READS THE NEWS:
- Formal, clear, confident and neutral. No chit-chat, no "I", no "welcome", no "I am glad to be here", no opinions.
- Each story starts with a strong lead sentence that gives the key fact, like a headline turned into a full sentence
  ("Microsoft has apologised after a global outage disrupted its services for almost a full day.").
- Attribute claims and numbers to who said them ("police said", "according to The Island", "Palestinian officials say").
- Then 1 or 2 more sentences ONLY if the facts give real extra details. If a story has only a headline, say it in ONE
  sentence and move on. NEVER repeat or rephrase something already said, never pad.
- Get who did what to whom EXACTLY right (who claims, who denies, who was hit). If unsure, use the headline's own wording.
- Anchor links between stories: "In other news...", "Turning to international news...", "Meanwhile...", "Back home...".
- Order: Sri Lanka first, then international news. Do NOT greet (the app adds the greeting by the listener's clock;
  it is %s in Sri Lanka). Start with the first story. End with one line: "That is the news from Wire Now."
- Use ONLY the facts below. Keep every number, amount, date and name exactly. No symbols, lists, headings or emojis.
- About %d to %d words. Write it the way a Sri Lankan news anchor naturally reads %s (names in %s script).

Reply with ONLY the script text.

TODAY'S TOP NEWS:
%s
"""

BRIEF_CHECK_PROMPT = """You are a strict news editor. Compare the BULLETIN SCRIPT with the FACTS.
Find any sentence that: (a) reverses who did what (e.g. who claims and who denies), (b) adds a fact, number or name that
is not in the FACTS, (c) repeats or just rephrases something already said, or (d) gives an opinion.
The script may be in another language: judge its meaning.
Reply with ONLY this JSON: {"ok": true or false, "problems": ["short description", ...]}

FACTS:
%s

BULLETIN SCRIPT:
%s
"""


def repeats_itself(text):
    """True if a sentence mostly repeats one of the 3 sentences before it (padding)."""
    stop = {"the", "a", "an", "and", "of", "in", "on", "at", "to", "is", "was", "has", "have", "had", "with", "for", "s",
            "it", "this", "that", "by", "from", "as", "be", "been", "are", "were", "its", "their"}
    sents = [set(re.findall(r"\w+", x.lower())) - stop for x in re.split(r"(?<=[.!?।])\s+", text) if x.strip()]
    for n, b in enumerate(sents):
        for a in sents[max(0, n - 3):n]:
            if len(b) >= 3 and len(a & b) / len(b) >= 0.7:
                return True
    return False



def top_brief(top, settings, old, now):
    """One spoken script that tells the Top 10 as one story, written separately in English, Sinhala and Tamil.
    Made again when the Top 10 changes (at most once an hour). Numbers must match the facts, or it's dropped."""
    ids = [s["id"] for s in top]
    if not top or not ANY_AI:
        return old or {}
    if old and not old.get("checked"):       # made before the editor check existed: replace it
        old = None
    if old and old.get("ids") == ids:
        return old
    if old and old.get("made", "") > (now - timedelta(minutes=settings.get("brief_every_minutes", 60))).isoformat():
        return old
    facts = []
    for i, s in enumerate(top, 1):
        c = s.get("cards") or {}
        body = " ".join([c.get("what_happened", "")] + list(c.get("details", []))[:2] + [c.get("why_it_matters", "")]).strip() or s.get("summary", "")
        facts.append(f"{i}. [{'Sri Lanka' if s['region'] == 'sri_lanka' else 'World'}] {s['title']} (source: {s['source']})\n{body[:900]}")
    facts = "\n\n".join(facts)
    part = {5: "morning", 12: "afternoon", 17: "evening", 21: "night"}
    h = now.astimezone(timezone(timedelta(hours=5, minutes=30))).hour
    daypart = [v for k, v in sorted(part.items()) if h >= k][-1] if h >= 5 else "night"
    allowed = set(re.findall(r"\d+(?:\.\d+)?", facts.replace(",", "")))
    allowed |= {str(i) for i in range(0, 13)}      # "two", "10 stories", "first"... small counting numbers are fine
    out = {"ids": ids, "made": now.isoformat(), "checked": True, "audio": (old or {}).get("audio", {})}
    if not GEMINI_KEY or minutes_used() > 10:   # only the strong AI writes it, and only with time left in this run
        return old or {}
    strong = {**settings, "council": {**settings.get("council", {}), "writers": ["gemini:gemini-flash-latest", "gemini:gemini-2.5-flash"]}}
    for code, name in (("en", "English"), ("si", "Sinhala"), ("ta", "Tamil")):
        try:
            text, model = council_call("writers", BRIEF_PROMPT % (name, daypart, 300, 600, name, name, facts), strong)
            text = re.sub(r"^[#*\-•\s]+", "", (text or "").strip(), flags=re.M).strip()
            # never a greeting or "welcome" inside the script: the app says exactly one greeting
            sents = re.split(r"(?<=[.!?।])\s+", text)
            while sents and re.search(r"^\s*(good (morning|afternoon|evening|night)|welcome|hello)|your host|glad to have you|வணக்கம்|ආයුබෝවන්|සුබ ", sents[0], re.I):
                sents.pop(0)
            text = " ".join(sents).strip()
            nums = set(re.findall(r"\d+(?:\.\d+)?", text.replace(",", "")))
            problem = ("too short" if len(text) <= 300 else "numbers not in the facts" if not nums <= allowed
                       else "repeats itself" if repeats_itself(text) else "")
            if not problem:
                verdict = parse_ai_json(council_call("checkers", BRIEF_CHECK_PROMPT % (facts, text), settings, avoid="gemini")[0])
                if not isinstance(verdict, dict) or verdict.get("ok") is not True:
                    problem = "editor found: " + "; ".join((verdict or {}).get("problems", ["no clear answer"]))[:200]
            if not problem:
                out[code] = text
                print(f"  Top 10 news bulletin written in {name} ({model}), checked by the editor")
            else:
                print(f"  {name} bulletin dropped: {problem}")
        except Exception as e:
            print(f"  radio script failed ({str(e)[:80]})")
            break
    if not any(k in out for k in ("en", "si", "ta")):
        return old or {}
    for k in ("en", "si", "ta"):              # keep the last good one for a language that failed this time
        if k not in out and old and old.get(k):
            out[k] = old[k]
    return out


RADIO_DIR = os.path.join(ROOT, "radio_out")          # audio files are NOT kept in the code: the workflow uploads them
RADIO_URL = "https://github.com/{repo}/releases/download/radio/brief-{lang}.mp3"
TTS_MODELS = ["gemini-3.1-flash-tts-preview", "gemini-2.5-flash-preview-tts"]
RADIO_STYLE = {"en": "a calm, warm, friendly Sri Lankan English news presenter",
               "si": "a calm, warm, friendly Sri Lankan news presenter speaking natural Sinhala",
               "ta": "a calm, warm, friendly Sri Lankan news presenter speaking natural Sri Lankan Tamil"}


def speak_gemini(text, lang, settings):
    """A human-sounding recording of the script (Google's Gemini speech). Returns raw 24 kHz 16-bit mono audio, or None."""
    import base64
    voice = settings.get("radio_voice", "Kore")
    for model in settings.get("tts_models", TTS_MODELS):
        body = {"contents": [{"parts": [{"text": f"Read this aloud like {RADIO_STYLE.get(lang, RADIO_STYLE['en'])}, "
                                                 f"at a relaxed pace, with natural pauses between stories:\n\n{text}"}]}],
                "generationConfig": {"responseModalities": ["AUDIO"],
                                     "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}
        req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                     data=json.dumps(body).encode(),
                                     headers={"x-goog-api-key": GEMINI_KEY, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.load(r)
            for part in ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []:
                if (part.get("inlineData") or {}).get("data"):
                    return base64.b64decode(part["inlineData"]["data"]), model
        except urllib.error.HTTPError as e:
            print(f"  voice {model}: {e.code} {e.read().decode(errors='replace')[:120]}")
        except Exception as e:
            print(f"  voice {model}: {str(e)[:120]}")
    return None, None


def radio_audio(brief, settings, now):
    """Turn the Top 10 radio script into a human-sounding MP3 per language (at most every few hours each,
    to stay inside the free limit). Files go to radio_out/; the workflow uploads them outside the code."""
    import shutil, subprocess
    # off until the website has its play button (otherwise it only uses up the free limit); turn on in feeds.json
    if not (settings.get("radio_recordings") and GEMINI_KEY and brief and shutil.which("ffmpeg")):
        return brief
    repo = os.environ.get("GITHUB_REPOSITORY", "wirenow-lk/wire-now")
    audio = dict(brief.get("audio") or {})
    every = timedelta(hours=settings.get("radio_every_hours", 4))
    os.makedirs(RADIO_DIR, exist_ok=True)
    started = time.time()
    for lang in ("en", "ta", "si"):
        if time.time() - started > settings.get("radio_seconds_per_run", 240):   # never let recordings run past the robot's time
            print("  radio: time budget used, the rest next run")
            break
        text = brief.get(lang)
        old = audio.get(lang) or {}
        if not text or (old.get("for") == brief.get("made")) or old.get("made", "") > (now - every).isoformat():
            continue
        pcm, model = speak_gemini(text, lang, settings)
        if not pcm:
            continue
        raw, mp3 = os.path.join(RADIO_DIR, f"{lang}.pcm"), os.path.join(RADIO_DIR, f"brief-{lang}.mp3")
        with open(raw, "wb") as f:
            f.write(pcm)
        ok = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", raw,
                             "-c:a", "libmp3lame", "-b:a", "40k", mp3]).returncode == 0
        os.remove(raw)
        if ok:
            secs = len(pcm) // 48000
            audio[lang] = {"url": RADIO_URL.format(repo=repo, lang=lang) + "?v=" + now.strftime("%Y%m%d%H%M"),
                           "made": now.isoformat(), "for": brief.get("made"), "seconds": secs,
                           "kb": os.path.getsize(mp3) // 1024}
            print(f"  🎙️ human-voice radio show in {lang}: {secs // 60}m{secs % 60:02d}s, {audio[lang]['kb']} KB ({model})")
    if audio:
        brief = {**brief, "audio": audio}
    return brief


def council_call(role, prompt, settings, avoid=None):
    """Ask the first available council member for this role. Returns (reply, model).
    Checkers prefer a different company from the writer, so they don't share the same blind spots."""
    council = {**COUNCIL_DEFAULT, **settings.get("council", {})}
    models = list(council[role])
    if avoid:
        models.sort(key=lambda m: (m.split(":")[0] if ":" in m else "openrouter") == avoid)
    last = None
    for m in models:
        if m in DOWN_MODELS or not _provider_ok(m, council, len(prompt)):
            continue
        p = m.split(":")[0]
        try:
            USAGE["count"][p] = USAGE["count"].get(p, 0) + 1
            return ai_call(m, prompt), m
        except Exception as e:
            last = e
            msg = str(e)
            if "AI error 404" in msg:                     # this one model is gone: the provider's other models still work
                DOWN_MODELS.add(m)
                print(f"    {m} not available ({msg[:80]})")
            elif any(code in msg for code in ("AI error 401", "AI error 402", "AI error 403", "AI error 429")):
                DOWN.add(p)
                print(f"    {p} unavailable this run ({msg[:80]})")
            else:
                print(f"    {p} failed ({msg[:80]})")
    raise RuntimeError(f"no AI available for {role}" + (f" (last error: {str(last)[:80]})" if last else ""))


def parse_ai_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("AI did not reply with JSON: " + repr(text[:200]))
    return json.loads(m.group(0))


def card_text(cards):
    parts = [cards.get("place", ""), cards.get("what_happened", ""), *cards.get("details", []), cards.get("why_it_matters", ""),
             *cards.get("key_facts", []), cards.get("whats_next", ""), cards.get("blurb", "")]
    return "\n".join(p for p in parts if p)


def _norm(s):
    s = s.lower().replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", s)


COMMON_CAPS = set("""a an the this that these those it its he she they we you i in on at of for to by with from as but and or
so if when while after before however also there here his her their our my your one two three four five six seven eight nine ten
first second third last new more most some many all no not yes mr mrs ms dr st monday tuesday wednesday thursday friday saturday
sunday january february march april may june july august september october november december today yesterday tomorrow
what why how who where which officials government police""".split())


NUM_WORDS = {w: str(i) for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve "
                                             "thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())}


def _digits(text):
    """'three people' -> '3 people', so a number counts as found whichever way it is written."""
    return re.sub(r"\b(" + "|".join(NUM_WORDS) + r")\b", lambda m: NUM_WORDS[m.group(1).lower()], text, flags=re.I)


def code_check(cards, article):
    """Every number and every capitalised name in the cards must appear in the article."""
    problems = []
    art = _norm(_digits(article))
    art_digits = re.sub(r"(?<=\d),(?=\d)", "", art)
    text = card_text(cards)

    for num in set(re.findall(r"\d[\d,]*(?:\.\d+)?", _digits(text))):
        n = re.sub(r",", "", num).rstrip(".")
        if n and n not in art_digits:
            problems.append(f"the number {num} is not in the article")

    for sentence in re.split(r"(?<=[.!?])\s+|\n", text):
        words = re.findall(r"[A-Za-z][A-Za-z'’\-]*", sentence)
        for i, w in enumerate(words):
            if i == 0 or not w[0].isupper() or w.lower() in COMMON_CAPS or len(w) < 3:
                continue
            w = re.sub(r"['’]s$", "", w)  # Lanka's -> Lanka
            if _norm(w) not in art:
                problems.append(f"the name/word '{w}' is not in the article")

    for key in ("what_happened", "blurb"):
        if not cards.get(key):
            problems.append(f"'{key}' is empty")
    if cards.get("topic") not in TOPICS:
        cards["topic"] = None
    return sorted(set(problems))


def completeness_check(cards, article):
    """A summary must carry all the information: it can't be much shorter than the article allows."""
    art_words = len(re.findall(r"\w+", article))
    got = len(re.findall(r"\w+", " ".join([cards.get("what_happened", ""), *cards.get("details", []), *cards.get("key_facts", [])])))
    need = min(200, max(min(80, int(art_words * 0.7)), int(art_words * 0.3)))   # short articles need less
    if got < need:
        return [f"the summary is too short ({got} words) for an article of {art_words} words: it is missing information. "
                f"Include EVERY fact the article gives (aim for at least {need} words in what_happened, details and key_facts)"]
    if len(cards.get("key_facts", [])) < 4:
        return ["key_facts must have 4 to 8 points covering every main point of the article"]
    return []


def ai_check(cards, article, settings, writer_model=""):
    to_check = {k: v for k, v in cards.items() if k not in ("topic", "country")}  # labels are not facts
    prompt = CHECKER_PROMPT % (article, json.dumps(to_check, ensure_ascii=False, indent=1))
    writer_p = writer_model.split(":")[0] if ":" in writer_model else "openrouter"
    text, model = council_call("checkers", prompt, settings, avoid=writer_p)
    reply = parse_ai_json(text)
    if reply.get("all_supported") is True:
        return []
    return [str(p) for p in reply.get("problems", [])] or ["checker said not all facts are supported"]


def make_cards(story, article, settings, multi=False, short=False):
    """Returns checked cards, or None if they could not be made safely."""
    base = SHORT_PROMPT if short else RESEARCH_PROMPT if multi else WRITER_PROMPT
    prompt = base % (story["title"], article)
    for attempt in (1, 2):
        try:
            text, writer = council_call("writers", prompt, settings)
            cards = parse_ai_json(text)
            cards["key_facts"] = [str(f) for f in cards.get("key_facts", []) if str(f).strip()][:8]
            cards["details"] = [str(d).strip() for d in cards.get("details", []) if str(d).strip()][:4]
            for k in ("what_happened", "why_it_matters", "whats_next", "blurb", "country", "place"):
                cards[k] = str(cards.get(k) or "").strip()
            problems = code_check(cards, article) + completeness_check(cards, article)
            if not problems:
                problems = ai_check(cards, article, settings, writer)
            if not problems:
                print(f"    cards OK (attempt {attempt}, written by {writer.split(':')[0]})")
                return cards
            print(f"    attempt {attempt} rejected: {'; '.join(problems)[:200]}")
            prompt = base % (story["title"], article) + FIX_NOTE % "\n".join("- " + p for p in problems)
        except Exception as e:
            print(f"    attempt {attempt} failed: {e}")
            if "no AI available" in str(e):
                break  # every council member is out for today
    return None


# ======================================================================
# Telegram
# ======================================================================

def _multipart(fields, files):
    boundary = "----wirenow" + hashlib.md5(str(time.time()).encode()).hexdigest()
    out = []
    for k, v in fields.items():
        out += [f"--{boundary}\r\n".encode(), f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode(),
                str(v).encode(), b"\r\n"]
    for name, data in files.items():
        out += [f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"; filename="{name}.jpg"\r\n'.encode(),
                b"Content-Type: image/jpeg\r\n\r\n", data, b"\r\n"]
    out.append(f"--{boundary}--\r\n".encode())
    return b"".join(out), f"multipart/form-data; boundary={boundary}"


def telegram(method, params, files=None):
    if files:
        data, ctype = _multipart(params, files)
    else:
        data, ctype = urllib.parse.urlencode(params).encode(), "application/x-www-form-urlencoded"
    req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/{method}", data=data,
                                 headers={"Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = json.loads(e.read() or b"{}")
        retry = body.get("parameters", {}).get("retry_after")
        if retry:  # Telegram says "slow down"
            time.sleep(int(retry) + 1)
            return telegram(method, params, files)
        raise RuntimeError(f"Telegram error: {body.get('description', e)}")


def build_caption(s, settings):
    flag = "🇱🇰" if s["region"] == "sri_lanka" else "🌍"
    tags = settings.get("hashtags_sri_lanka" if s["region"] == "sri_lanka" else "hashtags_world", "")
    cards = s.get("cards")
    blurb = cards["blurb"] if cards else s["summary"]
    loc = s.get("location") or {}
    head = f"{flag} <b>{html.escape(s['title'], quote=False)}</b>"
    if loc:
        head = f"📍 {html.escape(places.label(loc), quote=False)} {loc['flag']}\n" + head
    if s.get("warning"):
        head = "⚠️ <b>WARNING</b>\n" + head
    elif s.get("breaking"):
        head = "🚨 <b>BREAKING</b>\n" + head
    tail = []
    if cards:
        tail.append("👉 Swipe the cards for the full story")
    srcs = (cards or {}).get("sources") or []
    if len(srcs) > 1:
        tail.append(f"🔍 Researched from {len(srcs)} sources: " + html.escape(", ".join(srcs)))
    tail.append(f'🔗 Full story: <a href="{html.escape(s["link"], quote=True)}">{html.escape(s["source"])}</a>')
    site = SITE_URL or settings.get("website_url", "")
    if site:
        if not site.endswith("/"):
            site += "/"
        tail.append(f'🌐 <a href="{html.escape(site + "#s-" + s["id"], quote=True)}">Read on the Wire Now website</a>')
    if s.get("talk"):
        t = s["talk"][0]
        tail.append(f'💬 <a href="{html.escape(t["url"], quote=True)}">People are discussing this on Reddit</a> '
                    f'({t["comments"]} comments, not verified)')
    if BOT_USERNAME:
        tail.append(f'<a href="https://t.me/{BOT_USERNAME}?start=report_{s["id"]}">⚠️ Report a mistake</a>'
                    f' · <a href="https://t.me/{BOT_USERNAME}?start=tip">📣 Send us news</a>')
    if tags:
        tail.append(tags)
    # Telegram captions can be at most 1024 characters
    room = 1000 - len(head) - len("\n\n".join(tail)) - 4
    parts = [head]
    if blurb and room > 40:
        parts.append(html.escape(shorten(blurb, room), quote=False))
    return "\n\n".join(parts + tail)


PREVIEW_DIR = os.path.join(ROOT, "preview")


def post(s, settings):
    caption = build_caption(s, settings)
    images = []
    try:
        import cards as card_art
        srcs = (s.get("cards") or {}).get("sources") or []
        art_story = {**s, "source": f"{srcs[0]} +{len(srcs) - 1}" if len(srcs) > 1 else s["source"]}
        images = card_art.make_cards(art_story, s.get("cards"), CHANNEL if CHANNEL.startswith("@") else "")
    except Exception as e:
        print(f"    could not draw cards ({e}); posting text only")

    if TEST_MODE:
        print("\n--- WOULD POST ---\n" + caption)
        if images:
            os.makedirs(PREVIEW_DIR, exist_ok=True)
            for i, data in enumerate(images, 1):
                with open(os.path.join(PREVIEW_DIR, f"{s['id']}-{i}.jpg"), "wb") as f:
                    f.write(data)
            print(f"   ({len(images)} card pictures saved in the preview folder)")
        print()
        return

    if len(images) >= 2:   # swipeable album: caption goes on the first picture
        media = [{"type": "photo", "media": f"attach://p{i}"} for i in range(len(images))]
        media[0].update({"caption": caption, "parse_mode": "HTML"})
        telegram("sendMediaGroup", {"chat_id": CHANNEL, "media": json.dumps(media)},
                 files={f"p{i}": img for i, img in enumerate(images)})
    elif images:
        telegram("sendPhoto", {"chat_id": CHANNEL, "caption": caption, "parse_mode": "HTML"},
                 files={"photo": images[0]})
    else:
        telegram("sendMessage", {"chat_id": CHANNEL, "text": caption, "parse_mode": "HTML"})


# ======================================================================
# main
# ======================================================================

def add_coverage(stories):
    """For each story, count how many different outlets reported the same event."""
    kw = [keywords(s["title"]) for s in stories]
    for i, s in enumerate(stories):
        outlets = {s["source"]}
        a = kw[i]
        if len(a) >= 3:
            for j, t in enumerate(stories):
                if j != i and t["source"] not in outlets:
                    b = kw[j]
                    common = len(a & b)
                    if common >= 3 and common / min(len(a), len(b)) >= 0.5:
                        outlets.add(t["source"])
        s["coverage"] = len(outlets)


def take_turns(stories):
    """Newest story from each source, then the next from each, and so on."""
    groups = {}
    for s in stories:
        groups.setdefault(s["source"], []).append(s)
    queues = sorted(groups.values(), key=lambda q: q[0]["date"] or "", reverse=True)
    out, r = [], 0
    while len(out) < len(stories):
        for q in queues:
            if r < len(q):
                out.append(q[r])
        r += 1
    return out


def telegram_diagnose():
    """Write into the log what Telegram knows about this bot and the channel."""
    print("\n--- Telegram check ---")
    for method, params in (("getMe", {}), ("getChat", {"chat_id": CHANNEL}),
                           ("getChatMember", {"chat_id": CHANNEL, "user_id": TOKEN.split(":")[0]})):
        try:
            r = telegram(method, params).get("result", {})
            keep = {k: r.get(k) for k in ("id", "username", "title", "type", "status", "can_post_messages") if k in r}
            if "user" in r:
                keep["user"] = r["user"].get("username")
            print(f"{method}: {keep}")
        except Exception as e:
            print(f"{method}: {e}")
    try:
        ups = telegram("getUpdates", {"allowed_updates": json.dumps(["my_chat_member"])}).get("result", [])
        seen = {}
        for u in ups:
            m = u.get("my_chat_member")
            if m:
                c = m["chat"]
                seen[c["id"]] = (c.get("title"), c.get("username"), m["new_chat_member"].get("status"))
        print(f"channels/groups the bot was added to (recent): {seen or 'none recorded'}")
        return seen
    except Exception as e:
        print(f"getUpdates: {e}")
        return {}


def collect_fact_checks(cfg, now):
    """Latest articles from Sri Lanka's independent fact-checkers (headlines + links, last 30 days)."""
    got = []
    for feed in cfg.get("fact_checks", []):
        try:
            got += parse_feed(fetch(feed_url(feed)), feed["name"], "sri_lanka")
        except Exception as e:
            print(f"  fact check feed {feed['name']} failed ({str(e)[:60]})")
    seen, out = set(), []
    for s in sorted(got, key=lambda s: s.get("date") or "", reverse=True):
        if s["link"] in seen or not s.get("date") or now - datetime.fromisoformat(s["date"]) > timedelta(days=30):
            continue
        seen.add(s["link"])
        out.append({k: s[k] for k in ("id", "title", "link", "source", "date")})
    return out[:20]


def collect_countries(cfg, settings, now):
    """Fetch each country's national Top Stories and write docs/c/<CODE>.json. Headlines + links only."""
    from concurrent.futures import ThreadPoolExecutor
    countries = cfg.get("countries", {})
    if not countries:
        return
    out_dir = os.path.join(ROOT, "docs", "c")
    os.makedirs(out_dir, exist_ok=True)
    per = settings.get("stories_per_country", 60)
    max_age = timedelta(hours=48)

    def one(item):
        code, info = item
        got, fails = [], []
        for feed in info.get("feeds", []):
            try:
                got += parse_feed(fetch(feed_url(feed)), feed["name"], code)
            except Exception as e:
                fails.append(f"{feed['name']}: {str(e)[:60]}")
        return code, info, got, fails

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(one, countries.items()))

    index, summary = {}, []
    for code, info, got, fails in results:
        seen, stories = set(), []
        for s in got:
            if s["link"] in seen or not s["date"]:
                continue
            seen.add(s["link"])
            if now - datetime.fromisoformat(s["date"]) > max_age:
                continue
            stories.append(s)
        add_coverage(stories)
        stories.sort(key=lambda s: (s.get("coverage", 1), s["date"]), reverse=True)
        kept = []
        for s in stories:
            if len(kept) >= per:
                break
            if not any(same_event(s["title"], k["title"]) for k in kept):
                kept.append(s)
        kept.sort(key=lambda s: s["date"], reverse=True)
        name = info.get("name", code)
        rows = []
        for s in kept:
            loc = places.location_for(s)
            if not loc:   # a national feed: unless the headline names another country, it is about this one
                loc = {"country": name, "place": "", "flag": places.flag(name)}
            rows.append({"id": s["id"], "title": s["title"], "link": s["link"], "summary": s["summary"],
                         "image": s["image"], "source": s["source"], "region": code, "date": s["date"],
                         "coverage": s.get("coverage", 1), "location": loc,
                         "topic": guess_topic(s["title"] + " " + s["summary"])})
        if rows:
            save_json(os.path.join(out_dir, f"{code}.json"), {"updated": now.isoformat(), "code": code, "name": name, "stories": rows})
            index[code] = {"name": name, "count": len(rows)}
        summary.append(f"{code} {len(rows)}" + (" (FAIL)" if fails and not rows else ""))
    save_json(os.path.join(out_dir, "index.json"), {"updated": now.isoformat(), "countries": index})
    print("\nCountries: " + ", ".join(summary))


# PRIVATE things (the owner's chat, readers' chats, reader tips) never go into the public code. They are kept
# encrypted in GitHub's private cache (data/private/, never committed), locked with a key made from a secret.
PRIVATE_DIR = os.path.join(ROOT, "data", "private")
PRIVATE_KEYS = ("owner_chat", "bot_offset", "convo", "pulse_force")


def _keystream(key, nonce, n):
    out, i = b"", 0
    while len(out) < n:
        out += hmac.new(key, nonce + i.to_bytes(8, "big"), hashlib.sha256).digest(); i += 1
    return out[:n]


def private_load(name, default):
    """Read data/private/<name> (encrypted). Wrong key, missing or damaged file: the default."""
    key = hashlib.sha256(("wire-now-private|" + TOKEN).encode()).digest() if TOKEN else None
    try:
        raw = open(os.path.join(PRIVATE_DIR, name + ".bin"), "rb").read()
        nonce, tag, body = raw[:16], raw[16:48], raw[48:]
        if not key or not hmac.compare_digest(tag, hmac.new(key, nonce + body, hashlib.sha256).digest()):
            return default
        return json.loads(bytes(a ^ b for a, b in zip(body, _keystream(key, nonce, len(body)))).decode())
    except Exception:
        return default


def private_save(name, data):
    if not TOKEN:
        return
    key = hashlib.sha256(("wire-now-private|" + TOKEN).encode()).digest()
    os.makedirs(PRIVATE_DIR, exist_ok=True)
    nonce = os.urandom(16)
    plain = json.dumps(data, ensure_ascii=False).encode()
    body = bytes(a ^ b for a, b in zip(plain, _keystream(key, nonce, len(plain))))
    with open(os.path.join(PRIVATE_DIR, name + ".bin"), "wb") as f:
        f.write(nonce + hmac.new(key, nonce + body, hashlib.sha256).digest() + body)

WELCOME = ("👋 Hi! This is the Wire Now bot.\n\n"
           "📣 To send us news, tap: /tip\n"
           "⚠️ To report a mistake, use the \"Report a mistake\" link under any story.\n\n"
           "Note: I check messages every 15 minutes, so replies can take a little while.")


def handle_bot_messages(state, stories_by_id):
    """Read messages people sent to the bot since the last run: mistake reports and news tips.
    Each one is saved and forwarded to the owner. Runs every 15 minutes, so replies are not instant."""
    if TEST_MODE:
        return
    fb = private_load("feedback", {"items": []})
    convo = state.setdefault("convo", {})
    owner = state.get("owner_chat")
    try:
        updates = telegram("getUpdates", {"offset": state.get("bot_offset", 0), "timeout": 0,
                                          "allowed_updates": json.dumps(["message"])}).get("result", [])
    except Exception as e:
        print(f"bot inbox: {e}")
        return
    handled = 0
    for u in updates:
        state["bot_offset"] = u["update_id"] + 1
        m = u.get("message") or {}
        chat = m.get("chat", {})
        if chat.get("type") != "private":
            continue
        cid = str(chat["id"])
        text = (m.get("text") or m.get("caption") or "").strip()

        def reply(t):
            try:
                telegram("sendMessage", {"chat_id": cid, "text": t, "disable_web_page_preview": "true"})
            except Exception as e:
                print(f"bot reply failed: {e}")

        if text.startswith("/owner"):
            if not owner:
                owner = state["owner_chat"] = cid
                reply("✅ You are now the Wire Now owner. Mistake reports and news tips will be forwarded to you here.")
            elif owner == cid:
                reply("✅ You are already the owner.")
            continue
        if owner == cid and text.startswith("/stats"):         # owner only: anonymous reader numbers
            t = pulse.stats_text(reader_stats(), {k: v.get("title", "") for k, v in stories_by_id.items()})
            reply("📊 READERS\n\n" + (t or "No numbers yet (the counter starts once the community setup has run)."))
            continue
        if owner == cid and text.startswith("/pulse"):         # owner only: make today's World Pulse at the end of this run
            state["pulse_force"] = True
            reply("🌍 OK, today's World Pulse will arrive in a few minutes.")
            continue
        if text.startswith("/start report_"):
            sid = text.split("report_", 1)[1][:20]
            title = (stories_by_id.get(sid) or {}).get("title", "")
            convo[cid] = {"type": "report", "story": sid, "title": title}
            reply("⚠️ Thanks for helping keep Wire Now accurate!\n\n"
                  + (f"Story: {title}\n\n" if title else "")
                  + "Please send ONE message saying what is wrong, and the correct information if you know it.")
            continue
        if text.startswith("/start tip") or text.startswith("/tip"):
            convo[cid] = {"type": "tip"}
            reply("📣 Send us the news in ONE message: what happened, where and when. You can attach a photo.\n\n"
                  "Please only send things you saw yourself or know are true.")
            continue
        if text.startswith("/"):
            reply(WELCOME)
            continue
        c = convo.pop(cid, None)
        if not c:
            reply(WELCOME)
            continue
        item = {"type": c["type"], "date": datetime.now(timezone.utc).isoformat(), "text": text[:2000],
                "has_photo": bool(m.get("photo"))}
        if c["type"] == "report":
            item.update(story=c.get("story"), title=c.get("title"))
        fb["items"].append(item)
        handled += 1
        reply("✅ Received, thank you! Our team will look at it.")
        if owner:
            head = (f"⚠️ MISTAKE REPORT\nStory: {c.get('title') or c.get('story')}" if c["type"] == "report"
                    else "📣 NEWS TIP")
            try:
                telegram("sendMessage", {"chat_id": owner, "text": head})
                telegram("copyMessage", {"chat_id": owner, "from_chat_id": cid, "message_id": m["message_id"]})
            except Exception as e:
                print(f"forward to owner failed: {e}")
    fb["items"] = fb["items"][-500:]
    private_save("feedback", fb)
    if updates:
        print(f"bot inbox: {len(updates)} messages, {handled} reports/tips saved" + ("" if owner else " (no owner yet: send /owner to the bot)"))


def main():
    cfg = load_json(FEEDS_FILE, {})
    settings = cfg.get("settings", {})
    state = load_json(STATE_FILE, {})
    priv = private_load("state", None)
    if priv is not None:                         # private things come from the encrypted private store
        state = {**{k: v for k, v in state.items() if k not in PRIVATE_KEYS}, **priv}
    posted = set(state.get("posted", []))
    first_seen = state.get("first_seen", {})
    all_cards = load_json(CARDS_FILE, {})
    first_run = not state.get("live_runs")
    now = datetime.now(timezone.utc)
    today = now.astimezone(timezone(timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d")
    ai_used = state.get("ai_used", 0) if state.get("ai_day") == today else 0
    USAGE.update(state.get("ai_requests", {}) if state.get("ai_requests", {}).get("day") == today else {"day": today, "count": {}})
    USAGE["day"] = today
    members = [n for n, k in (("OpenRouter", AI_KEY), ("Gemini", GEMINI_KEY), ("Groq", GROQ_KEY)) if k]
    ai_limit = settings.get("ai_stories_per_day_council", 80) if (GEMINI_KEY or GROQ_KEY) else settings.get("ai_stories_per_day", 12)
    max_age = timedelta(hours=settings.get("max_story_age_hours", 12))

    global BOT_USERNAME
    if not TEST_MODE:
        try:
            BOT_USERNAME = telegram("getMe", {}).get("result", {}).get("username", "")
        except Exception as e:
            print(f"getMe failed: {e}")
    for p in SECRET_PROBLEMS:
        print("!! SECRET PROBLEM: " + p)
    print(f"Mode: {'TEST (nothing really posted)' if TEST_MODE else 'LIVE -> ' + CHANNEL} | "
          f"AI cards: {'on (' + ' + '.join(members) + '), ' + str(ai_used) + '/' + str(ai_limit) + ' used today' if ANY_AI else 'off (no AI keys)'}\n")

    # ---- 1. read feeds
    all_stories, failed = [], []
    for region in ("sri_lanka", "world"):
        for feed in cfg.get(region, []):
            try:
                got = parse_feed(fetch(feed_url(feed)), feed["name"], region)
                print(f"OK   {feed['name']}: {len(got)} stories")
                all_stories += got
            except Exception as e:  # one broken site must not stop the others
                failed.append(feed["name"])
                print(f"FAIL {feed['name']}: {e}")

    all_stories = strip_boilerplate(all_stories)

    seen_links, stories = set(), []
    for s in all_stories:
        if s["link"] in seen_links:
            continue
        seen_links.add(s["link"])
        if not s["date"]:
            s["date"] = first_seen.get(s["link"]) or now.isoformat()
        first_seen[s["link"]] = first_seen.get(s["link"]) or s["date"]
        stories.append(s)
    stories.sort(key=lambda s: s["date"], reverse=True)
    add_coverage(stories)
    big = []
    for s in sorted(stories, key=lambda s: s["coverage"], reverse=True):
        if len(big) < 5 and not any(same_event(s["title"], b["title"]) for b in big):
            big.append(s)
    print("\nBiggest stories right now: " + " | ".join(f"{s['title'][:45]} ({s['coverage']} outlets)" for s in big))

    # ---- 2. choose what to post: Sri Lanka first, then world
    posted_titles = state.get("posted_titles", [])
    to_post = []
    # 🚨 breaking Sri Lankan news and ⚠️ warnings jump the queue (up to 3 per run)
    if not first_run:
        urgent = [s for s in stories if s["link"] not in posted and (is_breaking(s, now) or
                  (is_warning(s) and now - datetime.fromisoformat(s["date"]) <= timedelta(hours=6)))]
        urgent.sort(key=lambda s: (is_warning(s), s.get("coverage", 1), s["date"]), reverse=True)
        for s in urgent:
            if len(to_post) >= settings.get("max_breaking_per_run", 3):
                break
            if any(same_event(s["title"], t) for t in posted_titles + [x["title"] for x in to_post]):
                posted.add(s["link"])
                continue
            s["breaking"] = True
            s["warning"] = is_warning(s)
            to_post.append(s)
    for region, key, first_limit in (("sri_lanka", "max_posts_per_run_sri_lanka", 3),
                                     ("world", "max_posts_per_run_world", 2)):
        fresh = [s for s in stories if s["region"] == region and s["link"] not in posted
                 and now - datetime.fromisoformat(s["date"]) <= max_age
                 and s.get("coverage", 1) >= settings.get(f"min_outlets_{region}", 1)
                 and not (region == "sri_lanka" and (is_press_release(s) or is_foreign(s)))]
        # main news first: stories reported by the most outlets, then the newest
        fresh.sort(key=lambda s: (s.get("coverage", 1), s["date"]), reverse=True)
        limit = first_limit if first_run else settings.get(key, 3)
        for s in fresh:
            if len([x for x in to_post if x["region"] == region and not x.get("breaking")]) >= limit:
                break
            if any(same_event(s["title"], t) for t in posted_titles + [x["title"] for x in to_post]):
                posted.add(s["link"])  # same event already covered: don't post it twice
                continue
            # prefer a version from a site we can actually read over a Google News headline
            if "news.google.com" in s["link"]:
                better = [x for x in fresh if "news.google.com" not in x["link"] and same_event(s["title"], x["title"])]
                if better:
                    continue
            to_post.append(s)
    urgent_first = sorted([s for s in to_post if s.get("breaking")], key=lambda s: s["date"], reverse=True)
    lk = sorted([s for s in to_post if s["region"] == "sri_lanka" and not s.get("breaking")], key=lambda s: s["date"])
    wd = sorted([s for s in to_post if s["region"] == "world" and not s.get("breaking")], key=lambda s: s["date"])
    ordered = urgent_first + lk + wd
    print(f"\n{len(ordered)} new stories to post\n")

    # ---- Top 10: the day's biggest stories always get the full explanation first.
    # Other news may never use the last part of the day's AI summaries that the Top 10 still needs.
    import site_extras
    top_now = site_extras.top_stories([s for s in stories if not (s["region"] == "sri_lanka" and is_press_release(s))],
                                      same_event, now, n=settings.get("top_count", 10))
    top_ids = {s["id"] for s in top_now}
    # stories whose summary failed (or whose article was too short) wait 6 hours before another try: no wasted AI
    card_failed = {k: v for k, v in state.get("card_failed", {}).items() if v > (now - timedelta(hours=6)).isoformat()}
    can_try = lambda s: s["id"] not in all_cards and s["id"] not in card_failed
    top_reserve = lambda: len([s for s in top_now if can_try(s)])

    # ---- 3. make cards, 4. post
    social.talk_for([s for s in ordered if is_important(s)], max_lookups=4)
    errors = 0
    for s in ordered:
        print(f"* {s['source']} [{s.get('coverage', 1)} outlets]: {s['title'][:70]}")
        important = is_important(s)
        # normal news may only use part of the day's AI summaries: the rest is kept for important news
        normal_cap = int(ai_limit * settings.get("ai_share_for_normal_news", 0.5))
        is_top = s["id"] in top_ids
        reserve = 0 if is_top else top_reserve()
        can_use_ai = ai_used < ai_limit - reserve and (important or is_top or ai_used < normal_cap) and minutes_used() < 6
        if ANY_AI and can_use_ai and can_try(s):
            related = [x for x in stories if x is not s and x["source"] != s["source"] and same_event(s["title"], x["title"])]
            if important:
                why = f"also on {', '.join(sorted({x['source'] for x in related}))}" if related else "serious news"
                print(f"    important ({why}) - researching")
            else:
                print("    normal news - one-paragraph summary")
            article, names, img = research(s, related, settings, important=important)
            if not s["image"] and img:
                s["image"] = img
            if len(names) > 1:
                print(f"    read {len(names)} articles: {', '.join(names)}")
            if len(article) >= 200:
                ai_used += 1
                cards = make_cards(s, article, settings, multi=len(names) > 1, short=False)   # always the complete format
                if cards and len(names) == 1:
                    cards["single_source"] = True   # shown as "Only reported by X so far"
                if cards:
                    all_cards[s["id"]] = {**cards, "sources": names, "mode": "full" if important else "short",
                                          "made": now.isoformat()}
                else:
                    card_failed[s["id"]] = now.isoformat()
                    print("    -> no cards; posting with the site's own summary")
            else:
                card_failed[s["id"]] = now.isoformat()
                print("    article too short for cards")
        elif ANY_AI and not can_use_ai and s["id"] not in all_cards:
            print(f"    no AI summary: {'daily limit reached' if ai_used >= ai_limit else 'saving the rest of today for important news'}")
        if s["id"] in all_cards:
            s["cards"] = all_cards[s["id"]]
        s["topic"] = (s.get("cards") or {}).get("topic") or guess_topic(s["title"] + " " + s["summary"])
        s["location"] = places.location_for(s, s.get("cards"))
        try:
            post(s, settings)
            posted.add(s["link"])
            posted_titles.append(s["title"])
            time.sleep(0 if TEST_MODE else 5)
        except Exception as e:
            errors += 1
            print(f"    could not post: {e}")
            if "not a member" in str(e) and errors == 1:
                telegram_diagnose()
            if errors >= 3:
                print("    stopping: too many errors (check the bot token, and that the bot is a channel admin)")
                break

    if TEST_MODE:  # a test run must not use up stories: forget what it "posted"
        posted = set(state.get("posted", []))
    elif first_run:  # don't flood the channel with old stories on day one
        posted.update(s["link"] for s in stories)

    # ---- Top 10 stories not posted this run still get their full explanation (a few per run)
    made_top = 0
    for s in [s for s in top_now if can_try(s)][:settings.get("top_summaries_per_run", 4)]:
        if not ANY_AI or ai_used >= ai_limit or minutes_used() > 7.5:
            break
        related = [x for x in stories if x is not s and x["source"] != s["source"] and same_event(s["title"], x["title"])]
        article, names, img = research(s, related, settings, important=True)
        if len(article) < 200:
            card_failed[s["id"]] = now.isoformat()
            continue
        ai_used += 1
        cards = make_cards(s, article, settings, multi=len(names) > 1, short=False)
        if not cards:
            card_failed[s["id"]] = now.isoformat()
        if cards:
            if len(names) == 1:
                cards["single_source"] = True
            all_cards[s["id"]] = {**cards, "sources": names, "mode": "full", "made": now.isoformat()}
            made_top += 1
    if top_now:
        print(f"\nTop {len(top_now)}: {len([s for s in top_now if s['id'] in all_cards])} fully explained"
              + (f" ({made_top} new this run)" if made_top else ""))

    # ---- read reports and news tips people sent to the bot
    handle_bot_messages(state, {s["id"]: s for s in stories})

    # ---- save memory (kept small)
    keep_links = {s["link"] for s in stories}
    keep_ids = {s["id"] for s in stories}
    save_json(STATE_FILE, {
        # things that must survive between runs
        **{k: state[k] for k in ("roundup_day",) if k in state},
        "posted": [l for l in posted if l in keep_links] + sorted(posted - keep_links)[-3000:],
        "first_seen": {l: d for l, d in first_seen.items() if l in keep_links},
        "ai_day": today,
        "ai_used": ai_used,
        "card_failed": card_failed,
        "facts_sent": state.get("facts_sent", []),
        "ai_requests": USAGE,
        "last_run": now.isoformat(),
        "live_runs": state.get("live_runs", 0) + (0 if TEST_MODE else 1),
        "posted_titles": (state.get("posted_titles", []) if TEST_MODE else posted_titles)[-300:],
        "failed_sources": failed,
    })
    private_save("state", {k: state[k] for k in PRIVATE_KEYS if k in state})
    all_cards = {k: v for k, v in all_cards.items() if k in keep_ids or v.get("made", "") > (now - timedelta(days=3)).isoformat()}
    save_json(CARDS_FILE, all_cards)
    # summaries that readers asked for on the website (double tap), checked by the same rules
    site_cards = {**reader_summaries(), **all_cards}
    meaning, meaning_queue = load_json(MEANING_FILE, {}), []

    # ---- 5. website data: Sri Lanka first, then world, mixed between sources
    def for_site(s):
        out = {k: s[k] for k in ("id", "title", "link", "summary", "image", "source", "region", "date")}
        out["coverage"] = s.get("coverage", 1)
        if s["region"] == "sri_lanka" and is_press_release(s):
            out["promo"] = True
        if s["region"] == "sri_lanka":
            if is_warning(s) and now - datetime.fromisoformat(s["date"]) <= timedelta(hours=24):
                out["warning"] = True
            elif is_breaking(s, now, hours=3):
                out["breaking"] = True
        c = site_cards.get(s["id"])
        if c:
            out["cards"] = {k: c.get(k, [] if k in ("details", "sources") else "") for k in
                            ("what_happened", "details", "why_it_matters", "key_facts", "whats_next", "blurb", "spoken", "person", "role", "subject", "sources", "mode")}
        out["topic"] = (c or {}).get("topic") or guess_topic(s["title"] + " " + s["summary"])
        out["location"] = places.location_for(s, c)
        # other outlets' reports of the same event (shown when a reader double-taps a story)
        # other sites' reports of the same event; only ones that add something new (judged by meaning)
        cands, seen_src = [], {s["source"]}
        for x in stories:
            if len(cands) >= 8:
                break
            if x is not s and x["source"] not in seen_src and x.get("link") and same_event(s["title"], x["title"]):
                seen_src.add(x["source"])
                cands.append(x)
        more = []
        if cands:
            key = hashlib.sha1("|".join([s["title"]] + sorted(c["title"] for c in cands)).encode()).hexdigest()[:16]
            decided = meaning.get("groups", {}).get(key)
            if decided is not None:
                picked = [cands[i] for i in decided["keep"] if i < len(cands)]
                if decided.get("disagree"):
                    out["disagree"] = decided["disagree"]          # shown in the Fact check section
            else:                              # not judged yet: careful word rules for now, the AI judges it next
                meaning_queue.append((key, s, cands))
                picked, kept = [], [s]
                for c in cands:
                    if not any(repeats(k, c) for k in kept):
                        kept.append(c)
                        picked.append(c)
            more = [{"source": c["source"], "title": c["title"], "link": c["link"]} for c in picked[:5]]
        if more:
            out["more"] = more
        return out

    def one_per_event(lst):
        """Show each event once on the website: keep the version with a full summary, else the first."""
        kept = []
        for s in sorted(lst, key=lambda s: s["id"] not in site_cards):
            if not any(same_event(s["title"], k["title"]) for k in kept):
                kept.append(s)
        ids = {k["id"] for k in kept}
        return [s for s in lst if s["id"] in ids]

    # the website shows fresh news only: nothing older than 3 days, and no "headlines" that are just a site's name
    site_max_age = timedelta(hours=settings.get("website_max_age_hours", 72))
    def fresh(s):
        if is_site_name(s):
            return False
        try:
            return now - datetime.fromisoformat(s["date"]) <= site_max_age
        except ValueError:
            return False
    lk_site = [s for s in stories if s["region"] == "sri_lanka" and not is_foreign(s) and fresh(s)]
    world_site = [s for s in stories if s["region"] == "world" and fresh(s)] + [s for s in stories if s["region"] == "sri_lanka" and is_foreign(s) and fresh(s)]
    world_site.sort(key=lambda s: s["date"], reverse=True)
    count = settings.get("website_story_count", 150)
    site = {
        "updated": now.isoformat(),
        "channel": CHANNEL if CHANNEL.startswith("@") else "",
        "bot": BOT_USERNAME,
        "sri_lanka": [for_site(s) for s in one_per_event(take_turns(lk_site))[:count]],
        "world": [for_site(s) for s in one_per_event(take_turns(world_site))[:count // 2]],
    }
    # ---- 6. extras: today's numbers, Top 10, one Google-friendly page per summarised story
    site_url = SITE_URL or settings.get("website_url", "")
    if site_url and not site_url.endswith("/"):
        site_url += "/"
    site_list = site["sri_lanka"] + site["world"]
    add_story_images(site_list, settings)
    site["numbers"] = site_extras.todays_numbers(load_json(SITE_FILE, {}).get("numbers"))
    top = site_extras.top_stories(site_list, same_event, now, n=settings.get("top_count", 10))
    big = sorted(site["sri_lanka"], key=lambda x: x.get("coverage", 1), reverse=True)[:8]
    social.talk_for(top + [b for b in big if b not in top], max_lookups=6)
    site["top"] = [s["id"] for s in top]
    if settings.get("voice_bulletin"):        # off (owner's decision, 14 Nov 2026): the AI requests go to summaries instead
        site["brief"] = top_brief(top, settings, load_json(SITE_FILE, {}).get("brief"), now)   # 🎧 the Top 10 as one spoken story
        site["brief"] = radio_audio(site["brief"], settings, now)                                 # 🎙️ and as a human-sounding recording
    site["fact_checks"] = collect_fact_checks(cfg, now) or load_json(SITE_FILE, {}).get("fact_checks", [])
    # Sinhala and Tamil: use what's already translated now, translate new ones for the next run
    translations = load_json(TRANSLATIONS_FILE, {})
    add_translations(site_list, translations)
    save_json(SITE_FILE, site)
    top_first = [s for s in site_list if s["id"] in site["top"]] + [s for s in site_list if s["id"] not in site["top"]]
    if translate_site(top_first, settings, translations):   # the Top 10 is translated first
        add_translations(site_list, translations)
        save_json(SITE_FILE, site)
    save_json(TRANSLATIONS_FILE, translations)
    # living categories: subjects people keep hearing about grow their own section (no AI needed)
    site["living"], site["archive"] = living_categories(site_list, now, settings)
    save_json(SITE_FILE, site)
    # our own Fact Base: the facts from every checked summary (no AI needed)
    send_facts(site_list, state, now)
    if state.get("facts_sent"):
        st = load_json(STATE_FILE, {}); st["facts_sent"] = state["facts_sent"]; save_json(STATE_FILE, st)
    # let the AI judge, by meaning, the stories it hasn't judged yet (used from the next run on)
    unique = list({k: (k, m, c) for k, m, c in meaning_queue}.values())
    if judge_meaning(unique, settings, meaning) or unique:
        cutoff = (now - timedelta(days=3)).isoformat()
        meaning["groups"] = {k: v for k, v in meaning.get("groups", {}).items() if v.get("made", "") > cutoff}
        save_json(MEANING_FILE, meaning)
    n_pages = site_extras.write_pages(site_list, site_url, site["channel"], now) if site_url else 0
    n_cards = sum(1 for s in site_list if "cards" in s)
    print(f"\nWebsite updated: {len(site['sri_lanka'])} Sri Lanka + {len(site['world'])} world stories "
          f"({n_cards} with cards, {n_pages} story pages for Google)")

    # ---- 6b. other countries: each country's own national news, for visitors from there (website only)
    collect_countries(cfg, settings, now)

    # ---- 7. daily Top 10 round-up on Telegram, once a day after 8 PM Sri Lanka time
    sl_now = now.astimezone(timezone(timedelta(hours=5, minutes=30)))
    st = load_json(STATE_FILE, {})
    if sl_now.hour >= settings.get("roundup_hour", 20) and st.get("roundup_day") != today and top:
        msg = site_extras.roundup_message(top, site_url, sl_now.strftime("%d %b"))
        if TEST_MODE:
            print("\n--- WOULD POST TOP 5 ---\n" + msg)
        else:
            try:
                telegram("sendMessage", {"chat_id": CHANNEL, "text": msg, "parse_mode": "HTML",
                                         "disable_web_page_preview": "true"})
                st["roundup_day"] = today
                save_json(STATE_FILE, st)
                print("\nPosted today's Top 10 round-up")
            except Exception as e:
                print(f"\nTop 10 round-up failed: {e}")
    # ---- 8. the owner's private World Pulse (trend memory every run, the briefing once a day)
    world_pulse(site_list, state, settings, now)
    private_save("state", {k: state[k] for k in PRIVATE_KEYS if k in state})
    if ordered and errors == len(ordered):
        sys.exit(1)


if __name__ == "__main__":
    main()
