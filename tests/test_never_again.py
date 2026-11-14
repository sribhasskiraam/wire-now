"""
Wire Now: "never again" tests.
Every mistake the owner has reported becomes a test here, so it can never come back unnoticed.
RULE: when a new mistake is reported, add a test for it in this file in the same change as the fix.
Run: python tests/test_never_again.py   (GitHub runs it on every change and emails the owner if one fails)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bot      # noqa: E402
import cards    # noqa: E402

failures = []


def check(name, ok):
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok:
        failures.append(name)


# ---- 13 Nov 2026: a website's name or slogan shown as if it were news
for title, src in [("Sri Lanka 24 Hours Online Breaking News", "Daily Mirror"),
                   ("Times online - Latest news and headlines from Sri Lanka and the world", "Sunday Times"),
                   ("Daily Mirror - Sri Lanka Latest Breaking News and Headlines", "Daily Mirror"),
                   ("Ada Derana - First in Sri Lanka", "Ada Derana"),
                   ("Entertainment", "Hiru News")]:
    check(f"site name is not news: {title}", bot.is_site_name({"title": title, "source": src}))
for title, src in [("Breaking: Floods in Colombo", "Hiru News"), ("World Bank approves loan", "Daily Mirror"),
                   ("Local elections next month", "Ada Derana"), ("Sri Lanka beat India by 5 wickets", "Newsfirst")]:
    check(f"real headline kept: {title}", not bot.is_site_name({"title": title, "source": src}))

# ---- 13 Nov 2026: site name glued to the FRONT of a headline (Daily Mirror print edition)
t = "Sri Lanka Latest Breaking News and Headlines - Print Edition Kadella Construction Exhibition 2026 opens"
check("site-name prefix removed", bot.SITE_PREFIX.sub("", t).strip() == "Kadella Construction Exhibition 2026 opens")
check("normal headline untouched by prefix rule", bot.SITE_PREFIX.sub("", "Fuel prices cut - official").strip() == "Fuel prices cut - official")

# ---- any site's repeated label is learned and removed automatically
st = [{"title": f"Story number {i} happened today - Hiru News Online", "source": "Hiru News", "link": f"l{i}"} for i in range(4)]
cleaned = bot.strip_boilerplate(st)
check("repeated site label learned and removed", all(not s["title"].endswith("Hiru News Online") for s in cleaned))
check("cleaned stories kept", len(cleaned) == 4)

# ---- 13 Nov 2026: wrong topics
for title, topic in [("Horoscope for Friday, November 13, 2026", "Astrology"),
                     ("Ramayana part 1 crosses Rs. 1,000 crore worldwide in 8 Days", "Entertainment"),
                     ("Microsoft reports additional recovery progress as services gradually return in Europe", "Tech"),
                     ("Heavy rain and floods expected in the Western Province", "Weather"),
                     ("Sri Lanka beat India by 5 wickets", "Sports")]:
    check(f"topic {topic}: {title[:40]}", bot.guess_topic(title) == topic)

# ---- 13 Nov 2026: 'other reports' must add something new; different meaning must stay
check("opposite meaning kept", not bot.repeats("Three-wheeler fares to increase from Monday", "Three-wheeler fares to decrease from Monday"))
check("different numbers kept", not bot.repeats("Three-wheeler fares raised by Rs. 100", "Three-wheeler fares raised by Rs. 150"))
check("'not' kept", not bot.repeats("Government to ban three-wheelers on expressways", "Government will not ban three-wheelers on expressways"))
check("different angle kept", not bot.repeats("Budget 2027: What are the new proposals for vehicles?", "SEC welcomes key proposals in Budget 2027 to boost capital market"))
check("true repeat removed", bot.repeats("Budget 2027: What are the new proposals for vehicles?", "Budget 2027: New proposals for vehicles announced"))

# ---- 13 Nov 2026: summaries must contain everything the article says
art = " ".join(["word"] * 400)
check("thin summary rejected", bool(bot.completeness_check({"what_happened": "Something happened.", "details": ["One line."], "key_facts": ["a", "b"]}, art)))
check("complete summary accepted", not bot.completeness_check({"what_happened": " ".join(["x"] * 60), "details": [" ".join(["y"] * 50)] * 2, "key_facts": ["f g h i j"] * 5}, art))

# ---- 13 Nov 2026: translations must not change numbers
check("translation with changed number rejected", not bot._same_numbers("Fuel prices cut by Rs. 20", "எரிபொருள் விலை ரூ. 25 குறைப்பு"))
check("translation with same numbers accepted", bot._same_numbers("Fuel prices cut by Rs. 20", "எரிபொருள் விலை ரூ. 20 குறைப்பு"))

# ---- 13 Nov 2026: cards: letters shrink, split only when needed (few cards)
para = ("Police arrested three men in Galle on Tuesday after seizing 12 kilograms of heroin from a multi-day fishing trawler. "
        "The Navy said the trawler had sailed from Dikkowita harbour two days earlier and was intercepted off the southern coast. "
        "Officers said the drugs were worth about Rs. 300 million.")
check("normal paragraph fits one card", len(cards.split_text(para)) == 1)
check("very long text split into few cards", 2 <= len(cards.split_text(para * 5)) <= 4)

# 14 Nov 2026: owner pasted the URL with /rest/v1/ on the end; new Supabase projects only have sb_publishable_ keys (not JWTs)
check("Supabase URL with /rest/v1/ is cleaned", bot.sb_base_url("https://abc.supabase.co/rest/v1/") == "https://abc.supabase.co")
check("publishable key is not sent as Bearer", "Authorization" not in bot.sb_headers("sb_publishable_x"))
check("old anon key still sent as Bearer", bot.sb_headers("eyJabc").get("Authorization") == "Bearer eyJabc")

# 14 Nov 2026: Telegram photos were blurry: feeds gave 240px previews that were stretched to 1080px
check("BBC preview asks for the big photo", "/1024/" in bot.bigger_image("https://ichef.bbci.co.uk/ace/standard/240/cpsprodpb/x.jpg"))
check("WordPress thumbnail asks for the full photo", bot.bigger_image("https://a.lk/wp-content/uploads/p-300x200.jpg") == "https://a.lk/wp-content/uploads/p.jpg")
check("small photo is not sharp enough", not bot.sharp_enough((240, 135)))
check("big photo is sharp enough", bot.sharp_enough((1024, 576)))
check("unknown size is not trusted", not bot.sharp_enough(None))

# 14 Nov 2026: Top 10 (was Top 5): 6 Sri Lanka + 4 world, no two about the same event
import site_extras
from datetime import datetime as _dt, timezone as _tz, timedelta as _td
_now = _dt.now(_tz.utc)
_st = [{"id": str(i), "title": f"Story number {i} about topic {i}", "region": "sri_lanka" if i < 12 else "world",
        "date": (_now - _td(hours=1)).isoformat(), "coverage": 1} for i in range(20)]
_top = site_extras.top_stories(_st, lambda a, b: a == b, _now, n=10)
check("Top list has 10 stories", len(_top) == 10)
check("Top 10 is 6 Sri Lanka + 4 world", sum(s["region"] == "sri_lanka" for s in _top) == 6)

# 14 Nov 2026: the new Gemini key (AQ....) was rejected because the check only knew the old AIza format
check("new Gemini key format accepted", bot.valid_gemini_key("AQ." + "Ab3_x-Y.z" * 6))
check("old Gemini key format accepted", bot.valid_gemini_key("AIza" + "B" * 35))
check("random text is not a Gemini key", not bot.valid_gemini_key("my gemini key"))

# 14 Nov 2026: the radio script padded a headline-only story by repeating it
check("bulletin padding is caught", bot.repeats_itself("A truck and bus crash in India's Assam state has killed at least 24 people. The crash happened in Assam state. The crash involved a truck and a bus."))
check("normal bulletin is not flagged", not bot.repeats_itself("Microsoft has apologised after a global outage. In other news, Parliament debated the 2027 Budget for a second day."))

# 14 Nov 2026 (independent review): photo links, site slogans, private data
check("photo link with ?h=..&w=.. stays a valid link", bot.bigger_image("https://x.lk/a.jpg?h=200&w=300") == "https://x.lk/a.jpg?w=1200")
check("site slogan is not news", bot.is_site_name({"title": "Sri Lanka Sports News Today | Live Cricket, Rugby & Local Sports Updat…", "source": "Newsfirst"}))
check("real headline with a dash is news", not bot.is_site_name({"title": "Floods in Colombo - police warn residents", "source": "Ada Derana"}))
_tok, _dir = bot.TOKEN, bot.PRIVATE_DIR
bot.TOKEN, bot.PRIVATE_DIR = "123:test", "/tmp/wn_private_test"
bot.private_save("t", {"owner_chat": "1"})
check("private notes round-trip", bot.private_load("t", None) == {"owner_chat": "1"})
check("private notes are not readable as text", b"owner_chat" not in open("/tmp/wn_private_test/t.bin", "rb").read())
bot.TOKEN = "other"
check("private notes need the right key", bot.private_load("t", "no") == "no")
bot.TOKEN, bot.PRIVATE_DIR = _tok, _dir

# 14 Nov 2026: a weak AI saved garbage Tamil/Sinhala headlines (mixed scripts, "Tamil headline")
check("real Tamil headline accepted", bot.right_script("நுவரெலியா பேருந்து நிலையத்தருகே கொலைச் சந்தேகநபர் கைது", "ta"))
check("real Sinhala headline accepted", bot.right_script("නුවරඑළිය බස් නැවතුම්පොළ අසල ඝාතන සැකකරු අත්අඩංගුවට", "si"))
check("mixed-script garbage rejected", not bot.right_script("India ச்ஸா රයිල් 24 ඉලෙකුත් ඉල්ල්", "ta"))
check("leftover instruction rejected", not bot.right_script("டிரம்ப் பிரதமர் செய்தி மாநாடு Tamil headline", "ta"))
check("English left untranslated rejected", not bot.right_script("Microsoft services begin recovering after outage", "si"))
check("English name inside a translation rejected", not bot.right_script("මයික්‍රොසොෆ්ට් සේවා යළි ආරම්භ වේ Microsoft officials", "si"))
check("short acronym allowed", bot.right_script("IMF ණය වාරිකය ශ්‍රී ලංකාවට ලැබේ", "si"))

# 14 Nov 2026: World Pulse (owner-only analysis) and the anonymous reader counter
import pulse
_h = {}
pulse.record(_h, [{"id": "a1", "title": "T", "cards": {"subject": "Fuel"}}], "2026-11-14")
pulse.record(_h, [{"id": "a1", "title": "T", "cards": {"subject": "Fuel"}}], "2026-11-14")
check("a story is counted once per day", _h["days"]["2026-11-14"]["subject"] == {"Fuel": 1})
pulse.apply_reply(_h, "P: X happens | high | 2099-01-01", "2026-11-14")
check("a prediction's check date is kept within 45 days", _h["predictions"][0]["by"] <= "2026-12-29")
check("the World Pulse is only sent to the owner, never posted", "CHANNEL" not in bot.world_pulse.__code__.co_names)
_src = open(os.path.join(os.path.dirname(__file__), "..", "community", "schema.sql")).read()
check("readers can't read the reader numbers", "grant execute on function public.reader_stats(integer) to anon" not in _src
      and "revoke all on public.visitors, public.visits from anon, authenticated" in _src)

print(f"\n{'ALL PASSED' if not failures else str(len(failures)) + ' FAILED'}: {len(failures)} of the never-again checks failed")
sys.exit(1 if failures else 0)
