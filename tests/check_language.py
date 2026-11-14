"""Never-again check (14 Nov 2026): in Tamil or Sinhala mode, NO English words may be shown.
Also checks the hard case the independent review found: a story whose HEADLINE is translated but whose SUMMARY isn't yet
(the list blurb, the story viewer, Today in numbers and the Top 10 must not fall back to English).
Opens the real site in a headless browser with the robot's data, picks the language, and looks for leftover English.
Brand names and short codes are the only allowed exceptions."""
import json, re, sys, subprocess, time, os
from playwright.sync_api import sync_playwright

ROOT = os.path.join(os.path.dirname(__file__), "..", "docs")
ALLOWED = {"wire", "now", "telegram", "whatsapp", "facebook", "rs", "usd", "lkr", "km", "ai", "en", "pm", "am", "x"}
CHROME = os.environ.get("CHROME_PATH") or None


def source_names():
    """News outlets' own names (brands, like "Wire Now") may stay as written until the translator transliterates them."""
    try:
        cfg = json.load(open(os.path.join(os.path.dirname(__file__), "..", "feeds.json")))
    except Exception:
        return set()
    names = set()
    def walk(x):
        if isinstance(x, dict):
            if isinstance(x.get("name"), str):
                names.update(w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'’-]+", x["name"]))
            for v in x.values(): walk(v)
        elif isinstance(x, list):
            for v in x: walk(v)
    walk(cfg)
    return names


ALLOWED |= source_names()

def leftovers(text):
    words = re.findall(r"[A-Za-z][A-Za-z'’-]{1,}", text)
    return [w for w in words if w.lower() not in ALLOWED]

def half_translated(route):
    """The robot's data, but every story with a summary gets ONLY its headline translated (summary not yet)."""
    r = route.fetch(); d = r.json()
    for s in d.get("sri_lanka", []) + d.get("world", []):
        if s.get("cards"):
            s["tr"] = {"si": {"title": "සිංහල මාතෘකාව"}, "ta": {"title": "தமிழ் தலைப்பு"}}
    route.fulfill(response=r, body=json.dumps(d))


def main():
    srv = subprocess.Popen([sys.executable, "-m", "http.server", "8766"], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    bad = {}
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(**({"executable_path": CHROME} if CHROME else {}))
            for lang in ("ta", "si"):
                pg = b.new_page(viewport={"width": 390, "height": 900})
                pg.add_init_script(f"localStorage.setItem('wn_lang','{lang}');localStorage.setItem('wn_country','LK');window.WN_SUPABASE={{}};")
                pg.route("**/config.js", lambda r: r.fulfill(body="", content_type="application/javascript"))
                pg.route("**/news.json*", half_translated)
                pg.goto("http://localhost:8766/index.html"); pg.wait_for_timeout(2500)
                text = "\n".join(pg.inner_text(sel) for sel in ("#list", "#top5", "#numgrid") if pg.is_visible(sel))
                if pg.locator(".story").count():                       # open a story: the viewer must have no English either
                    pg.locator(".story").first.click(); pg.wait_for_timeout(700)
                    text += "\n" + pg.inner_text("#viewer")
                found = leftovers(text)
                if found:
                    bad[lang] = sorted(set(found))[:25]
                pg.close()
            b.close()
    finally:
        srv.terminate()
    for lang, words in bad.items():
        print(f"FAIL  English left on the {lang} page: {', '.join(words)}")
    if bad:
        sys.exit(1)
    print("PASS  no English words left in Tamil or Sinhala mode")

if __name__ == "__main__":
    main()
