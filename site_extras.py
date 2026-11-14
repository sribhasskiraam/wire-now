"""
Extra website features, made fresh on every run:
  - one page per story that has a full summary (docs/s/<id>.html), so Google can find it
  - sitemap.xml and robots.txt
  - today's numbers: US dollar rate and Colombo weather (free services, no key)
  - the daily Top 10 list
"""

import html
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(ROOT, "docs")
PAGES = os.path.join(DOCS, "s")
INDEX = os.path.join(PAGES, "index.json")   # remembers when each page was made
KEEP_DAYS = 30

UA = "Mozilla/5.0 (WireNow news robot)"


def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


get_json = _get_json  # (tests replace this)


# ---------------------------------------------------------------- numbers

WEATHER = {0: "☀️ Clear", 1: "🌤️ Mostly clear", 2: "⛅ Partly cloudy", 3: "☁️ Cloudy", 45: "🌫️ Fog", 48: "🌫️ Fog",
           51: "🌦️ Drizzle", 53: "🌦️ Drizzle", 55: "🌦️ Drizzle", 61: "🌧️ Rain", 63: "🌧️ Rain", 65: "🌧️ Heavy rain",
           80: "🌦️ Showers", 81: "🌧️ Showers", 82: "⛈️ Heavy showers", 95: "⛈️ Thunderstorm", 96: "⛈️ Thunderstorm",
           99: "⛈️ Thunderstorm"}


def todays_numbers(old):
    """US dollar in rupees + Colombo weather. Keeps the last good value if a service is down."""
    out = dict(old or {})
    try:
        d = _rates()
        out["usd_lkr"] = round(float(d["rates"]["LKR"]), 2)
        out["usd_lkr_note"] = "market rate, not a bank's buying/selling rate"
        _all_rates(out, d)
    except Exception as e:
        print(f"numbers: dollar rate unavailable ({str(e)[:60]})")
    try:
        w = get_json("https://api.open-meteo.com/v1/forecast?latitude=6.93&longitude=79.85"
                     "&current=temperature_2m,weather_code&daily=temperature_2m_max,temperature_2m_min,"
                     "precipitation_probability_max&timezone=Asia%2FColombo&forecast_days=1")
        out["weather"] = {
            "now_c": round(w["current"]["temperature_2m"]),
            "text": WEATHER.get(w["current"]["weather_code"], "🌡️"),
            "max_c": round(w["daily"]["temperature_2m_max"][0]),
            "min_c": round(w["daily"]["temperature_2m_min"][0]),
            "rain_pct": w["daily"]["precipitation_probability_max"][0],
        }
    except Exception as e:
        print(f"numbers: weather unavailable ({str(e)[:60]})")
    return out


# currencies that matter to Sri Lankans: trade, tourism and the countries where Sri Lankans work
CURRENCIES = [("USD", "US Dollar", "🇺🇸"), ("EUR", "Euro", "🇪🇺"), ("GBP", "British Pound", "🇬🇧"), ("INR", "Indian Rupee", "🇮🇳"),
              ("SAR", "Saudi Riyal", "🇸🇦"), ("AED", "UAE Dirham", "🇦🇪"), ("QAR", "Qatari Riyal", "🇶🇦"), ("KWD", "Kuwaiti Dinar", "🇰🇼"),
              ("OMR", "Omani Rial", "🇴🇲"), ("JPY", "Japanese Yen", "🇯🇵"), ("KRW", "Korean Won", "🇰🇷"), ("AUD", "Australian Dollar", "🇦🇺"),
              ("CAD", "Canadian Dollar", "🇨🇦"), ("SGD", "Singapore Dollar", "🇸🇬"), ("MYR", "Malaysian Ringgit", "🇲🇾"), ("CNY", "Chinese Yuan", "🇨🇳")]


def _all_rates(out, d):
    """Rupees for one unit of each currency, the change since yesterday, and a 30-day history for charts."""
    lkr = float(d["rates"]["LKR"])
    today = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d")
    hist = out.get("history") or {"dates": []}
    rates = []
    for code, name, flag in CURRENCIES:
        if code not in d["rates"]:
            continue
        val = lkr / float(d["rates"][code])
        val = round(val, 4 if val < 1 else 2)
        series = hist.get(code, [])
        dates = hist["dates"]
        prev = None
        if dates and dates[-1] != today and series:
            prev = series[-1]
        elif len(dates) > 1 and len(series) > 1:
            prev = series[-2]
        rates.append({"code": code, "name": name, "flag": flag, "lkr": val, "prev": prev})
    if not hist["dates"] or hist["dates"][-1] != today:
        hist["dates"].append(today)
        for r in rates:
            hist.setdefault(r["code"], []).append(r["lkr"])
    else:
        for r in rates:
            ser = hist.setdefault(r["code"], [])
            if len(ser) < len(hist["dates"]):
                ser.extend([r["lkr"]] * (len(hist["dates"]) - len(ser)))
            ser[-1] = r["lkr"]
    keep = 30
    hist = {k: v[-keep:] for k, v in hist.items()}
    out["rates"] = rates
    out["history"] = hist


def _rates():
    return get_json("https://open.er-api.com/v6/latest/USD")


# ---------------------------------------------------------------- top 5

def top_five(stories, same_event, now):
    return top_stories(stories, same_event, now, n=5)


def top_stories(stories, same_event, now, n=10):
    """The n biggest events of the last 24 hours: 60% Sri Lanka, 40% world when possible."""
    n_lk = round(n * 0.6)
    recent = [s for s in stories if s.get("date") and now - datetime.fromisoformat(s["date"]) <= timedelta(hours=24)]
    recent.sort(key=lambda s: (s.get("coverage", 1), "cards" in s, s["date"]), reverse=True)
    picked = []
    for region, k in (("sri_lanka", n_lk), ("world", n - n_lk)):
        for s in recent:
            if len([p for p in picked if p["region"] == region]) >= k:
                break
            if s["region"] == region and not any(same_event(s["title"], p["title"]) for p in picked):
                picked.append(s)
    for s in recent:  # fill up if one region was quiet
        if len(picked) >= n:
            break
        if s not in picked and not any(same_event(s["title"], p["title"]) for p in picked):
            picked.append(s)
    return picked[:n]


def roundup_message(top, site_url, day_label):
    lines = [f"🗞️ <b>Wire Now: Today's Top {len(top)}</b> · {html.escape(day_label)}", ""]
    for i, s in enumerate(top, 1):
        flag = "🇱🇰" if s["region"] == "sri_lanka" else "🌍"
        link = f"{site_url}s/{s['id']}.html" if s.get("cards") and site_url else s["link"]
        cov = f" · {s['coverage']} outlets" if s.get("coverage", 1) > 1 else ""
        lines.append(f'{i}. {flag} <a href="{html.escape(link, quote=True)}">{html.escape(s["title"], quote=False)}</a>{cov}')
    lines += ["", "Catch up on everything in a minute 👉 " + (site_url or "t.me/wirenow_lk"), f"#WireNow #Top{len(top)}"]
    return "\n".join(lines)


# ---------------------------------------------------------------- story pages

PAGE = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} | Wire Now</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{url}">
<link rel="icon" type="image/png" href="../favicon.png">
<meta property="og:title" content="{title}"><meta property="og:description" content="{desc}">
<meta property="og:type" content="article"><meta property="og:url" content="{url}">{og_image}
<script type="application/ld+json">{ld}</script>
<style>
body{{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#FFF8F3;color:#1E1B2E;line-height:1.6}}
main{{max-width:720px;margin:0 auto;padding:18px 18px 60px}}
a{{color:#E5532F}} .top{{display:flex;align-items:center;gap:8px;font-weight:900;font-size:20px;text-decoration:none;color:#1E1B2E}}
.bolt{{width:32px;height:32px;border-radius:10px;background:linear-gradient(135deg,#FF6B4A,#FFB23F);display:grid;place-items:center}}
h1{{font-size:28px;line-height:1.25;margin:18px 0 6px}} .meta{{color:#6B6880;font-size:14px;font-weight:600}}
.tag{{display:inline-block;background:#FFE9E1;color:#E5532F;font-weight:800;font-size:12px;padding:3px 10px;border-radius:99px;margin-right:6px}}
img.hero{{width:100%;border-radius:18px;margin:14px 0;max-height:380px;object-fit:cover}}
h2{{font-size:15px;text-transform:uppercase;letter-spacing:.06em;color:#E5532F;margin:26px 0 6px}}
.card{{background:#fff;border-radius:18px;padding:16px 18px;box-shadow:0 2px 0 #F0E6DE}} li{{margin:6px 0}}
.btns{{display:flex;flex-wrap:wrap;gap:8px;margin:26px 0}} .btns a{{padding:10px 14px;border-radius:12px;font-weight:800;text-decoration:none;color:#fff}}
.note{{color:#6B6880;font-size:13px}}
</style></head><body><main>
<a class="top" href="../"><img src="../logo.png" alt="" class="bolt" style="object-fit:cover">Wire Now</a>
<h1>{title}</h1>
<div class="meta"><span class="tag">{topic}</span>{flag} · {date} · {coverage}</div>
{hero}
<div class="card"><h2>📌 What happened</h2><p>{what}</p>
{details}
{why}
{facts}
{next}</div>
{talk}
<div class="btns">
<a style="background:#E5532F" href="{link}" rel="noopener">Read the original at {source}</a>
<a style="background:#25D366" href="https://wa.me/?text={share_text}">WhatsApp</a>
<a style="background:#229ED9" href="https://t.me/share/url?url={share_url}&text={share_title}">Telegram</a>
<a style="background:#1877F2" href="https://www.facebook.com/sharer/sharer.php?u={share_url}">Facebook</a>
</div>
<p class="note"><a href="https://t.me/wirenow_news_bot?start=report_{sid}">⚠️ Report a mistake</a> · <a href="https://t.me/wirenow_news_bot?start=tip">📣 Send us news</a></p>
<p class="note">Summary written by AI using only facts from {sources}, then fact-checked by code and a second AI.
<a href="../">More news on Wire Now</a>{tg}</p>
</main></body></html>
"""


def _loc_label(s):
    loc = s.get("location") or {}
    if loc.get("also"):
        return " / ".join([loc["country"]] + loc["also"]) + " " + loc.get("flag", "")
    name = f"{loc['place']}, {loc['country']}" if loc.get("place") and loc.get("country") else (loc.get("place") or loc.get("country", ""))
    return f"{name} {loc.get('flag', '')}".strip()


def _p(text):
    return f"<p>{html.escape(text)}</p>" if text else ""


def story_page(s, site_url, channel):
    c = s["cards"]
    url = f"{site_url}s/{s['id']}.html"
    when = s["date"][:10] if s.get("date") else ""
    srcs = c.get("sources") or [s["source"]]
    q = urllib.parse.quote
    ld = {"@context": "https://schema.org", "@type": "NewsArticle", "headline": s["title"][:110],
          "datePublished": s.get("date"), "description": c.get("blurb", ""), "url": url,
          "isBasedOn": s["link"], "publisher": {"@type": "Organization", "name": "Wire Now"}}
    if s.get("image"):
        ld["image"] = [s["image"]]
    return PAGE.format(
        title=html.escape(s["title"]), desc=html.escape(c.get("blurb") or c.get("what_happened", ""))[:300],
        url=url, og_image=f'\n<meta property="og:image" content="{html.escape(s["image"], quote=True)}">' if s.get("image") else "",
        ld=json.dumps(ld, ensure_ascii=False).replace("</", "<\\/"),
        topic=html.escape(s.get("topic") or "News"),
        flag=html.escape(f"📍 {_loc_label(s)}") if s.get("location") else ("🇱🇰 Sri Lanka" if s["region"] == "sri_lanka" else "🌍 World"),
        date=when,
        coverage=f"📰 Reported by {s.get('coverage', 1)} outlets" if s.get("coverage", 1) > 1 else html.escape(s["source"]),
        hero=f'<img class="hero" src="{html.escape(s["image"], quote=True)}" alt="" loading="lazy">' if s.get("image") else "",
        what=html.escape(c.get("what_happened", "")),
        details=("<h2>📖 The full story</h2>" + "".join(_p(d) for d in c.get("details", []))) if c.get("details") else "",
        why=("<h2>💡 Why it matters</h2>" + _p(c["why_it_matters"])) if c.get("why_it_matters") else "",
        facts=("<h2>🔢 Key facts</h2><ul>" + "".join(f"<li>{html.escape(f)}</li>" for f in c.get("key_facts", [])) + "</ul>")
        if c.get("key_facts") else "",
        next=("<h2>➡️ What's next</h2>" + _p(c["whats_next"])) if c.get("whats_next") else "",
        link=html.escape(s["link"], quote=True), source=html.escape(s["source"]),
        share_text=q(s["title"] + " " + url), share_url=q(url), share_title=q(s["title"]),
        sources=html.escape(", ".join(srcs)),
        tg=f' · <a href="https://t.me/{channel.lstrip("@")}">Follow on Telegram</a>' if channel else "",
        sid=s["id"],
        talk=('<div class="card" style="margin-top:16px"><h2>💬 What people are saying</h2><p class="note">From Reddit. '
              'These are people\'s opinions and claims, not verified news.</p><ul>'
              + "".join(f'<li><a href="{html.escape(t["url"], quote=True)}" rel="nofollow noopener">{html.escape(t["title"])}</a> '
                        f'<span class="note">{html.escape(t["where"])} · {t["comments"]} comments</span></li>' for t in s.get("talk") or [])
              + "</ul></div>") if s.get("talk") else "",
    )


def write_pages(site_stories, site_url, channel, now):
    """Write a page for each story with a full summary, keep pages for 30 days, then rewrite the sitemap."""
    os.makedirs(PAGES, exist_ok=True)
    try:
        index = json.load(open(INDEX, encoding="utf-8"))
    except Exception:
        index = {}
    for s in site_stories:
        if not s.get("cards"):
            continue
        with open(os.path.join(PAGES, f"{s['id']}.html"), "w", encoding="utf-8") as f:
            f.write(story_page(s, site_url, channel))
        index.setdefault(s["id"], {"made": now.isoformat(), "title": s["title"]})
    cutoff = (now - timedelta(days=KEEP_DAYS)).isoformat()
    for sid in [k for k, v in index.items() if v["made"] < cutoff]:
        try:
            os.remove(os.path.join(PAGES, f"{sid}.html"))
        except FileNotFoundError:
            pass
        del index[sid]
    with open(INDEX, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=0)

    urls = [f"<url><loc>{site_url}</loc><changefreq>hourly</changefreq></url>",
            f"<url><loc>{site_url}about.html</loc></url>"]
    urls += [f"<url><loc>{site_url}s/{sid}.html</loc><lastmod>{v['made'][:10]}</lastmod></url>" for sid, v in index.items()]
    with open(os.path.join(DOCS, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                + "\n".join(urls) + "\n</urlset>\n")
    with open(os.path.join(DOCS, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {site_url}sitemap.xml\n")
    return len(index)
