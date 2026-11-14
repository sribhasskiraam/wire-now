"""World Pulse: the owner's private daily analysis of where the world is heading (Level 2).

Every run, record() adds today's stories to a running memory: how often each subject, person, place and topic
came up each day. Once a day, trends() compares the last 7 days with the 7 before (rising, new, fading), and the
AI turns that into a short private briefing with predictions. Each prediction has a confidence and a check-by
date, and later briefings mark them right or wrong, so the analysis stays honest. Nothing here is public.
"""
import re
from datetime import date, timedelta

KEEP_DAYS = 60          # how much history the trend memory keeps
WINDOW = 7              # "this week" vs "the week before"


def _day(d):
    return date.fromisoformat(d)


def record(hist, site_list, today):
    """Count each story once per day it appears: topic, subject, person, place. No AI."""
    days = hist.setdefault("days", {})
    d = days.setdefault(today, {"ids": [], "topic": {}, "subject": {}, "person": {}, "place": {}, "heads": []})
    seen = set(d["ids"])
    for s in site_list:
        if s["id"] in seen:
            continue
        seen.add(s["id"])
        d["ids"].append(s["id"])
        c, loc = s.get("cards") or {}, s.get("location") or {}
        for kind, val in (("topic", s.get("topic")), ("subject", c.get("subject")), ("person", c.get("person")),
                          ("place", loc.get("place") or loc.get("country"))):
            val = re.sub(r"\s+", " ", str(val or "")).strip()[:60]
            if val:
                d[kind][val] = d[kind].get(val, 0) + 1
        if c and len(d["heads"]) < 60:
            d["heads"].append(f"{s.get('title', '')[:140]} — {(c.get('what_happened') or '')[:200]}")
    cutoff = (_day(today) - timedelta(days=KEEP_DAYS)).isoformat()
    for k in [k for k in days if k < cutoff]:
        del days[k]
    for k, v in days.items():                      # story ids are only needed for today and yesterday
        if k < (_day(today) - timedelta(days=1)).isoformat():
            v["ids"] = []
    return hist


def _window(days, today, start, length):
    """Total counts per kind over `length` days, ending `start` days before today."""
    out = {"topic": {}, "subject": {}, "person": {}, "place": {}}
    for i in range(start, start + length):
        d = days.get((_day(today) - timedelta(days=i)).isoformat())
        if not d:
            continue
        for kind in out:
            for k, n in d.get(kind, {}).items():
                out[kind][k] = out[kind].get(k, 0) + n
    return out


def trends(hist, today):
    """Rising, brand-new and fading things: this week vs last week. Plain counting, no AI."""
    days = hist.get("days", {})
    now, before = _window(days, today, 0, WINDOW), _window(days, today, WINDOW, WINDOW)
    ever = _window(days, today, WINDOW, KEEP_DAYS)
    res = {"rising": [], "new": [], "fading": [], "biggest": [], "history_days": len(days)}
    for kind in now:
        for k, n in now[kind].items():
            p = before[kind].get(k, 0)
            if n >= 2 and not ever[kind].get(k):
                res["new"].append((kind, k, n))
            elif n >= 3 and p and n / p >= 1.5:
                res["rising"].append((kind, k, p, n))
        for k, p in before[kind].items():
            n = now[kind].get(k, 0)
            if p >= 4 and n <= p / 3:
                res["fading"].append((kind, k, p, n))
        if kind != "topic":
            res["biggest"] += [(kind, k, n) for k, n in now[kind].items()]
    res["rising"].sort(key=lambda x: -(x[3] / max(1, x[2])) * x[3])
    res["new"].sort(key=lambda x: -x[2])
    res["fading"].sort(key=lambda x: -x[2])
    res["biggest"].sort(key=lambda x: -x[2])
    for k in ("rising", "new", "fading", "biggest"):
        res[k] = res[k][:12]
    return res


def due_predictions(hist, today):
    """Earlier predictions whose check-by date has come and that haven't been judged yet."""
    return [p for p in hist.get("predictions", []) if not p.get("judged") and p.get("by", "9999") <= today][:8]


def build_prompt(tr, hist, today, stats_text):
    heads = (hist.get("days", {}).get(today) or {}).get("heads", [])[:40]
    lines = []
    if tr["history_days"] < WINDOW * 2:
        lines.append(f"NOTE: only {tr['history_days']} days of history so far, so trends are early and weak. Say so.")
    lines.append("BIGGEST THIS WEEK (stories): " + "; ".join(f"{k} [{kind}] {n}" for kind, k, n in tr["biggest"]) or "none")
    lines.append("RISING (last week -> this week): " + ("; ".join(f"{k} [{kind}] {p}->{n}" for kind, k, p, n in tr["rising"]) or "none"))
    lines.append("NEW THIS WEEK: " + ("; ".join(f"{k} [{kind}] {n}" for kind, k, n in tr["new"]) or "none"))
    lines.append("FADING: " + ("; ".join(f"{k} [{kind}] {p}->{n}" for kind, k, p, n in tr["fading"]) or "none"))
    due = due_predictions(hist, today)
    if due:
        lines.append("EARLIER PREDICTIONS TO JUDGE NOW:\n" + "\n".join(f"#{i+1} (made {p['made']}, {p['conf']}): {p['text']}" for i, p in enumerate(due)))
    return f"""You are the private analyst of Wire Now, a Sri Lankan news service. Write today's WORLD PULSE for the owner only.
Today is {today}. Use ONLY the data below. Never invent events, numbers or quotes. Plain text, no markdown symbols like ** or #.
Short sentences, simple English (the owner is not an expert). At most 450 words.

Write these sections, each starting with its emoji heading on its own line:
📈 RISING — what is growing and why it might be (2-4 points)
🆕 NEW — anything that just appeared and could become big
📉 FADING — what is dying down
🔗 CONNECTIONS — links between different stories (e.g. oil prices -> bus fares). Only links the data supports.
🇱🇰 FOR SRI LANKA — what all of this could mean for people in Sri Lanka
🔮 WHERE IT'S HEADING — 2 to 4 predictions. Each on its own line, exactly like this:
P: <prediction in one sentence> | <low/medium/high> | <check-by date YYYY-MM-DD, 3 to 30 days from today>
""" + ("""✅ CHECKING OLD PREDICTIONS — for each earlier prediction listed, one line exactly like this:
J: #<number> | <right/wrong/too early> | <one short reason from today's data>
""" if due else "") + "\nDATA:\n" + "\n".join(lines) + "\n\nTODAY'S STORIES:\n" + "\n".join(f"- {h}" for h in heads) + \
        ("\n\nREADERS (for your information only, don't analyse them): " + stats_text if stats_text else "")


def apply_reply(hist, text, today):
    """Keep the new predictions; mark the judged ones. Returns the text to send (without the machine lines)."""
    preds, due = hist.setdefault("predictions", []), due_predictions(hist, today)
    shown = []
    for line in text.splitlines():
        m = re.match(r"\s*P:\s*(.+?)\s*\|\s*(low|medium|high)\s*\|\s*(\d{4}-\d{2}-\d{2})", line, re.I)
        if m:
            by = m.group(3)
            if not (today < by <= (_day(today) + timedelta(days=45)).isoformat()):
                by = (_day(today) + timedelta(days=14)).isoformat()
            preds.append({"made": today, "text": m.group(1)[:300], "conf": m.group(2).lower(), "by": by})
            shown.append(f"• {m.group(1)} ({m.group(2).lower()} confidence, check by {by})")
            continue
        j = re.match(r"\s*J:\s*#?(\d+)\s*\|\s*(right|wrong|too early)\s*\|\s*(.*)", line, re.I)
        if j:
            i = int(j.group(1)) - 1
            if 0 <= i < len(due):
                verdict = j.group(2).lower()
                if verdict != "too early":
                    due[i]["judged"], due[i]["result"] = today, verdict
                else:
                    due[i]["by"] = (_day(today) + timedelta(days=7)).isoformat()
                mark = {"right": "✅", "wrong": "❌"}.get(verdict, "⏳")
                shown.append(f"{mark} {due[i]['text']} — {j.group(3).strip()}")
            continue
        shown.append(line.replace("**", "").lstrip("#").rstrip())
    hist["predictions"] = preds[-200:]
    return "\n".join(shown).strip()


def score_line(hist):
    """How good the predictions have been so far (the honesty score)."""
    judged = [p for p in hist.get("predictions", []) if p.get("result")]
    if not judged:
        return ""
    right = sum(1 for p in judged if p["result"] == "right")
    return f"🎯 Prediction score so far: {right} of {len(judged)} came true."


def stats_text(stats, titles):
    """Readers in plain words, from the anonymous counter."""
    if not stats or not isinstance(stats, dict) or stats.get("error"):
        return ""
    days = stats.get("days") or []
    last = days[-1] if days else {}
    week = days[-7:]
    out = [f"Today: {last.get('people', 0)} people ({last.get('returning', 0)} came back from an earlier day)." if last else "No visits recorded yet.",
           f"Last 7 days: {sum(d.get('people', 0) for d in week)} visits, {sum(d.get('returning', 0) for d in week)} by returning readers.",
           f"All-time different readers: {stats.get('total_people', 0)}."]
    langs = stats.get("langs") or {}
    if langs:
        out.append("Languages this week: " + ", ".join(f"{k} {v}" for k, v in sorted(langs.items(), key=lambda x: -x[1])))
    tops = [t for t in (stats.get("top_stories") or []) if t.get("id") in titles][:5]
    if tops:
        out.append("Most opened: " + "; ".join(f"{titles[t['id']][:70]} ({t['opens']})" for t in tops))
    return "\n".join(out)
