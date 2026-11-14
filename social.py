"""
"What people are saying": finds public Reddit discussions about a story.
Shown only as clearly labelled links (titles + comment counts), never mixed into the fact cards.
No AI is used, so it does not touch the daily AI limit.
"""

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(ROOT, "data", "social.json")
UA = "WireNow/1.0 (news summary site; contact via t.me/wirenow_lk)"

STOP = set("""about after again also amid among before being between could during first from have into just last more most
news over said says should since some than that their them then there these they this those through under until very
were what when where which while will with would year years today week""".split())


def _keywords(t):
    return [w for w in re.findall(r"[a-z0-9]+", t.lower()) if len(w) > 3 and w not in STOP]


BLOCKED = {"direct": False, "reader": False}


def _get(url):
    """Ask Reddit directly; if Reddit blocks us (it blocks many cloud servers), try the free reader service once.
    After both fail, stop trying for the rest of this run."""
    if not BLOCKED["direct"]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                BLOCKED["direct"] = True
            else:
                raise
    if not BLOCKED["reader"]:
        try:
            req = urllib.request.Request("https://r.jina.ai/" + url, headers={"User-Agent": UA, "Accept": "text/plain"})
            with urllib.request.urlopen(req, timeout=40) as r:
                raw = r.read().decode("utf-8", errors="replace")
            m = re.search(r"\{.*\}", raw, re.S)
            if m:
                return json.loads(m.group(0))
        except Exception:
            pass
        BLOCKED["reader"] = True
    raise RuntimeError("Reddit not reachable from here")


get = _get  # (tests replace this)


def reddit_threads(title, sri_lanka=True, limit=3):
    """Recent Reddit threads about the same story. Returns [] if Reddit can't be reached."""
    words = sorted(set(_keywords(title)), key=len, reverse=True)[:5]
    if len(words) < 2:
        return []
    q = urllib.parse.quote(" ".join(words))
    urls = []
    if sri_lanka:
        urls.append(f"https://www.reddit.com/r/srilanka/search.json?q={q}&restrict_sr=1&sort=new&t=week&limit=15")
    urls.append(f"https://www.reddit.com/search.json?q={q}&sort=relevance&t=week&limit=15")
    found, kw = {}, set(_keywords(title))
    for url in urls:
        try:
            data = get(url)
        except Exception as e:
            if not (BLOCKED["direct"] and BLOCKED["reader"]) or "not reachable" in str(e):
                print(f"    reddit: {str(e)[:60]}")
            break
        for child in data.get("data", {}).get("children", []):
            p = child.get("data", {})
            if p.get("over_18") or p.get("removed_by_category"):
                continue
            common = kw & set(_keywords(p.get("title", "")))
            if len(common) < 2:
                continue
            link = "https://www.reddit.com" + p.get("permalink", "")
            found[link] = {"title": p.get("title", "")[:160], "url": link, "where": "r/" + p.get("subreddit", ""),
                           "comments": int(p.get("num_comments", 0))}
        time.sleep(1.5)   # be gentle with Reddit
    threads = sorted(found.values(), key=lambda t: t["comments"], reverse=True)
    return [t for t in threads if t["comments"] >= 3][:limit]


def talk_for(stories, max_lookups=8, refresh_hours=3):
    """Look up discussions for the most important stories, using a cache so we don't ask Reddit too often."""
    try:
        cache = json.load(open(CACHE_FILE, encoding="utf-8"))
    except Exception:
        cache = {}
    now = time.time()
    looked = 0
    for s in stories:
        if BLOCKED["direct"] and BLOCKED["reader"]:
            break
        c = cache.get(s["id"])
        if c and now - c["at"] < refresh_hours * 3600:
            s["talk"] = c["threads"]
            continue
        if looked >= max_lookups:
            continue
        looked += 1
        threads = reddit_threads(s["title"], sri_lanka=s.get("region") == "sri_lanka")
        cache[s["id"]] = {"at": now, "threads": threads}
        s["talk"] = threads
    # forget old entries
    cache = {k: v for k, v in cache.items() if now - v["at"] < 3 * 86400}
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    found = sum(1 for s in stories if s.get("talk"))
    print(f"What people are saying: looked up {looked}, {found} stories with Reddit discussions")
