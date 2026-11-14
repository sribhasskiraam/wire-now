# Wire Now: Master Index

## 🌱 The vision (owner, 14 Nov 2026)

**Wire Now is a living, self-contained ecosystem that grows with people, the way a plant grows with the sun.** People are the sun: what they read, search, ask, discuss and need is what makes it grow. Every feature and every decision is checked against one question: **does this help Wire Now grow with its people?**

What that means in practice:
- **Grows where people are**: start general, then follow how people actually use it (the "wax" idea); any subject people care about can grow into its own category, and fade into the archive when interest ends.
- **Learns and remembers**: a knowledge base, not just news: background, the story so far, what it means for you, Sri Lanka and the world.
- **Speaks each person's language**: every word in the reader's language, by country and area, explained like a presenter.
- **Heals itself**: never-again tests, a weekly health check, mistakes fixed once and for all.
- **Protects and sustains itself**: backups, mirrors, own domain and, later, own server and own AI (the independence plan); no single company can kill it.
- **Open to everyone**: cheap phones, low data, free; and every feature is an option each reader controls.

Goal #1: **every Sri Lankan uses Wire Now.** Then the world, country by country.

**Long-term company roadmap (owner, 14 Nov 2026): from an automatic service to a real news company, at BBC level.**
1. **Now (free):** automatic news, knowledge base, our own Fact Base, "Is this true?", community. Reach every Sri Lankan.
2. **First revenue:** own domain and server, paid AI, much bigger storage for the Fact Base (own storage/data centre later), a real presenter's voice if wanted.
3. **A small newsroom:** the first real journalists and editors in Sri Lanka doing original reporting, not only summaries.
4. **Regional company:** reporters across Sri Lanka and South Asia, many languages.
5. **BBC level:** a trusted international news brand with its own reporters worldwide.
What that needs beyond technology: people (journalists, editors, fact-checkers), published standards (ethics code, corrections policy, editorial independence), legal setup (company registration, Sri Lankan media rules, defamation protection) and steady income (ads, memberships, licensing the Fact Base). Everything built now (trust rules, fact-checking, never-again tests, the Fact Base) is that foundation.

**Read this first.** This file explains everything about Wire Now: what it is, how it works, every rule, every decision the owner has made, and what is still planned. It is written so that **any AI assistant or any person** can pick up the work without other notes.

> **Never-again rule:** every mistake the owner reports gets a test in `tests/test_never_again.py` in the same change as the fix. GitHub runs these tests (and a check that the website's code has no errors) on every change and emails the owner if one fails.
>
> **Rule for whoever works on Wire Now (person or AI):** keep this file up to date. Whenever you change how something works, add a feature, or the owner makes a decision, update the matching section **and** add a line to the [Decision log](#13-decision-log) in the same change. If this file and the code disagree, the code is what actually runs. Fix this file.
>
> **This project is public on GitHub.** Never put passwords, API keys, tokens, email addresses or the owner's personal details in this file or anywhere in the code. Secrets live only in GitHub → Settings → Secrets (see [section 3](#3-accounts-and-where-things-live)).

Last full review: **13 November 2026** (vision added 14 November 2026).

> **Core rule:** Wire Now must be **accessible to anyone**: cheap phones, old phones, slow or expensive data. Check every change against it.
>
> **Core principle: Wire Now is a knowledge base, not just news.** Every story, number and section should leave the reader *understanding* more (the why, the background, the story so far), and knowledge builds up over time. The goal: **reading Wire Now teaches you more about how the world works than reading the news alone.** Every story answers "🌍 What does this mean?" as a chain of effects: for you (prices, jobs, loans), for Sri Lanka, for the world. Example: gold price falling → what it says about investor fear, the US dollar and interest rates → what it means for Sri Lankan jewellery buyers, gold loans and the rupee.
>
> **Owner rule: check the terms first.** Before the owner signs up for or connects any service (hosting, AI, payments, accounts), look up its terms of service and tell him plainly: who owns his content, what it costs (now and later), what data it collects, and any risks. Only then accept.
>
> **Core principle: everything is an option.** Each reader can switch features on or off for themselves (⚙️ Settings, remembered on their phone).

---

## Contents
1. [What Wire Now is](#1-what-wire-now-is)
2. [The owner's ground rules](#2-the-owners-ground-rules)
3. [Accounts and where things live](#3-accounts-and-where-things-live)
4. [How the news robot works](#4-how-the-news-robot-works)
5. [Which stories are chosen (selection rules)](#5-which-stories-are-chosen)
6. [Summaries: how they are written and checked](#6-summaries-how-they-are-written-and-checked)
7. [The AI council and free limits](#7-the-ai-council-and-free-limits)
8. [Telegram posts](#8-telegram-posts)
9. [The news website](#9-the-news-website)
10. [The community (social app)](#10-the-community-social-app)
11. [Privacy and security](#11-privacy-and-security)
12. [Files in this project](#12-files-in-this-project)
13. [Decision log](#13-decision-log)
14. [Planned, pending and deferred](#14-planned-pending-and-deferred)
15. [How to change common things](#15-how-to-change-common-things)
16. [If something breaks](#16-if-something-breaks)

---

## 1. What Wire Now is

Wire Now is an **automatic news service: Sri Lankan news first, then world news**. It has three parts:

| Part | What it is | Address |
|---|---|---|
| **Telegram channel** | Posts news automatically as picture "story cards" you swipe through | `@wirenow_lk` (bot: `@wirenow_news_bot`) |
| **News website** | Endless, Instagram-like feed of stories with swipe cards | https://wirenow-lk.github.io/wire-now/ |
| **Community** | A calm, text-only social app for introverts and ambiverts (posts, topics, chats) | https://wirenow-lk.github.io/wire-now/community/ |

Style: like **Deepstash**, short swipeable cards that still tell the **complete** story. Everything is written in **simple English**.

Everything runs for **free** on GitHub (robot and website) and Supabase (community database). The owner's phone does **not** need to be on.

---

## 2. The owner's ground rules

These come directly from the owner. Follow them unless the owner changes them (and then update this section).

1. **Sri Lanka first, then the world.** Visitors from other countries see **their own country's national news** first (not world news filtered by country).
2. **Free wherever possible.** No paid services until there is revenue. Expand only after revenue.
3. **Summaries must be complete:** what, who, when, where, how, why, all the details and descriptions. A reader should not need to open the article. At least a full paragraph.
4. **Important news is researched across many sources** and summaries combine several websites.
5. **Facts only from the articles.** Never invent, never guess. If a fact can't be checked, it isn't published.
6. **Location labels** on every story (country, and the town or area when known).
7. **Less noise:** no company press releases or adverts in the Sri Lanka section; foreign stories go to World, not Sri Lanka.
8. **The story viewer shows only the headline, then the summary.** Nothing in between. A headline-only story is one card; the next tap goes to the next headline.
9. **Judge meaning, not words** when deciding if two reports say the same thing. Reports with a different meaning (opposite claims, different numbers, another side) must both stay.
10. **Ownership:** everything created for a project belongs to the owner (accounts, files, data). Protect it.
11. **Anonymous brand:** projects should appear publicly under a company or brand name, not the owner's personal name. (Currently still under the owner's GitHub name; moving to a company identity is planned, see [section 14](#14-planned-pending-and-deferred).)
12. **Private things are encrypted; public things are not.** Private chats are end-to-end encrypted.
13. **Calm community:** built for introverts and ambiverts. No public popularity numbers, no pressure, silent notifications.
14. **Text only for now** in the community. Photos and videos later, after revenue (storage costs).
15. **Own database later:** after revenue, move the community database from Supabase to a server the owner controls (a rented VPS). The database is plain PostgreSQL, so moving is easy.
16. **AI-independent:** this file must let any AI assistant continue the work.
17. **CORE RULE: accessible to anyone.** Every feature must work on cheap, old phones and slow, expensive mobile data. No big downloads, no "needs a new phone". If a feature can't meet this, it's optional and something that works for everyone must exist too.
18. **Sri Lanka has three languages: Sinhala, Tamil and English.** Sinhala and Tamil are the main ones, and most people also know English; many know only one of Sinhala or Tamil plus English. All three are equally first-class on Wire Now: menus, news and community in all three, and translation between them comes first.
19. **Translation for everyone:** people chat and read in their own language; the **meaning** is carried across, not word-for-word.

---

## 3. Accounts and where things live

| What | Where | Notes |
|---|---|---|
| Code, robot, website | GitHub repository `wirenow-lk/wire-now` (public, owned by the wirenow-lk organization) | Robot runs on GitHub Actions; website served by GitHub Pages from the `docs/` folder |
| Telegram channel | `@wirenow_lk` | Owned by the owner's Telegram account |
| Telegram bot | `@wirenow_news_bot` | Made with @BotFather; it is an admin of the channel. Token is a GitHub secret |
| Community database | Supabase (free plan) | Planned: a project in the **Mumbai** region under the company email. An empty test project in **Sydney** exists and should be deleted |
| Google Search Console | Owner's Google account | Site verified with a meta tag in `docs/index.html`; sitemap submitted |
| AI providers | OpenRouter (now), Gemini and Groq (keys to be added) | Free tiers |

### GitHub secrets (names only; values are never written anywhere else)

| Secret | Used for | Status |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Posting to Telegram | Set |
| `TELEGRAM_CHANNEL` | Channel name (`@wirenow_lk`; any t.me form is accepted) | Set |
| `OPENROUTER_API_KEY` | AI (starts `sk-or-`) | Set |
| `GEMINI_API_KEY` | AI (free, starts `AIza` or `AQ.`) | Added 14 Nov 2026 |
| `GROQ_API_KEY` | AI (free, starts `gsk_`) | Optional |
| `SUPABASE_URL` | Community + double-tap summaries (`https://xxxx.supabase.co`) | **To add** |
| `SUPABASE_ANON_KEY` | Public "anon"/"publishable" key (safe to be public) | **To add** |
| `SUPABASE_DB_URL` | "Session pooler" connection string, used only by the set-up workflow | **To add** |
| `SUPABASE_ACCESS_TOKEN` | Lets the set-up workflow deploy server functions (pop-ups, summaries) | **To add** |
| `COMMUNITY_ADMIN_EMAIL` | Whoever logs in with this email becomes community admin | **To add** (company email) |

After adding or changing secrets, run **Actions → "Set up community" → Run workflow** once.

---

## 4. How the news robot works

The robot is `bot.py`. GitHub Actions runs it **every 15 minutes** (workflow `.github/workflows/news.yml`), and also whenever its code changes. Each run:

1. **Collects** news from the feeds in `feeds.json`: 15 Sri Lankan sources (Google Top Stories LK, Ada Derana, Newswire, The Island, EconomyNext, Daily Mirror, Hiru News, Newsfirst, Daily News, Sunday Times, Lanka Business Online, Lanka Puvath, Colombo Gazette, Ceylon Today, Google Warnings LK) and 7 world sources (Google Top Stories World, BBC, Guardian, Al Jazeera, CNN, Reuters, AP), plus national news for 24 other countries. Sites that block GitHub are read through Google News feeds.
2. **Groups** reports of the same event (`same_event`) and counts how many outlets cover it (`coverage`).
3. **Chooses** what to post (see [section 5](#5-which-stories-are-chosen)).
4. **Researches and summarises** chosen stories with AI, then **fact-checks** them (see [section 6](#6-summaries-how-they-are-written-and-checked)).
5. **Posts** to Telegram as an album of picture cards (`cards.py`).
6. **Reads bot messages** (reader reports and news tips) and forwards them to the owner.
7. **Builds the website data**: `docs/news.json`, one file per country in `docs/c/`, story pages in `docs/s/` (kept 30 days), `sitemap.xml`, `robots.txt`.
8. **Saves its memory** (`data/`) and commits everything back to GitHub.

At **8 PM Sri Lanka time** it posts a daily **Top 10** round-up to Telegram (once per day).

---

## 5. Which stories are chosen

Order of posting each run:
1. **Urgent first**: breaking news and safety warnings (up to 3 per run).
   - **Breaking** = Sri Lankan, serious (deaths, attacks, accidents, arrests and similar words), less than 2 hours old, not happening abroad.
   - **Warning** = warning/alert/evacuation words together with a hazard (flood, landslide, cyclone, storm, heavy rain and similar).
2. **Sri Lanka**: up to 3 per run, most-covered first. Skips company press releases and stories that happen in another country.
3. **World**: up to 2 per run, only if at least 2 outlets cover it.

Other rules:
- Each event is posted **once** (headlines already posted are remembered).
- Stories older than **12 hours** are not posted.
- **Important** = covered by 2+ outlets, or serious. Important stories get a full researched summary; others get a shorter one, depending on the AI allowance.
- **Press release filter**: launches, partnerships, awards, sponsorships, offers, profit announcements and similar go to "Company news", not the main Sri Lanka list.
- **Foreign filter**: a story from a Sri Lankan site about another country goes to World.
- **Location**: Sri Lanka only when there's a real Sri Lankan sign (place names etc.); up to 3 other countries are listed.

---

## 6. Summaries: how they are written and checked

### Card format (full story)
- 📌 **What happened**: who, what, when, where, how and why
- 📖 **The full story**: 2 to 4 paragraphs with every detail, descriptions, background and what each side said
- 💡 **Why it matters** (only if the article says)
- 🔢 **Key facts**: 4 to 8 bullet points that together cover every main point (like a bullet-point summary)
- ➡️ **What's next** (only if the article says)
- a one-line **blurb** for Telegram

**Owner's rule: nothing left out.** Every summary carries ALL the information in the article (every number, name, place, date, statement, reason and next step) in simpler words: not broad or wordy, but complete. A longer article needs a longer summary. Every story uses the complete format (the old thin "short" version is no longer used).

### Research
- Important news: reads up to **5** articles from different sites (and searches for more coverage).
- Normal news: up to **3**.
- Articles are read directly, or through a free reader service (`r.jina.ai`) for sites that block GitHub.

### Fact checks (all must pass)
0. **Completeness check**: the summary (what happened + full story + key facts) must have at least 30% as many words as the article (minimum 80 for normal articles, less for very short ones, capped at 200), and at least 4 key points. Otherwise it goes back to the AI once with "it is missing information".
1. **Code check**: every number and every capitalised name in the summary must appear in the articles. ("three" and "3" count as the same.)
2. **Second AI check**: a different AI reviews the cards against the articles.
3. If something fails, the AI gets **one retry** with the list of problems. If it still fails, **nothing is published** for that story.

### Summaries on request (double tap)
- On the website, double-tapping a headline-only story asks a server function (`supabase/functions/summarize`) to write a full summary on the spot, with the same rules and the same code check.
- Each summary is written **once** and saved, so later readers get it instantly. The robot also adds saved summaries to the website and story pages.
- **Written ahead:** while someone reads a story for a few seconds, the next two stories in their feed are prepared quietly.
- Every story open is counted, so the most-wanted stories get summaries.
- Daily allowance: 200 summaries by default; writing ahead may use at most 60% of it.
- Only stories that are actually on the Wire Now site can be summarised (no random links).

---

## 7. The AI council and free limits

The robot uses several free AI services as a **council**: writers write, checkers check, and a checker prefers a different company from the writer.

| Role | Order of preference |
|---|---|
| Writers | Gemini 2.5 Flash → OpenRouter free → Groq Llama 3.3 70B |
| Checkers | Groq Llama 3.3 70B → Gemini 2.5 Flash-Lite → OpenRouter free |

Daily request caps per service: OpenRouter 45, Gemini 200, Groq 600. If a service fails it is skipped for that run.

Stories summarised per day: **12** with only OpenRouter; **80** once Gemini or Groq is added. Normal (not important) news may use at most half.

**Meaning check for "other reports":** the AI judges, by meaning, which other sites' reports add something new (see [section 9](#9-the-news-website)). About 15 stories per request, answers saved, at most 48 requests per day. Needs Gemini or Groq.

---

## 8. Telegram posts

Each post is an album of 1080×1350 picture cards (Inter font) plus a caption with:
- ⚠️ WARNING or 🚨 BREAKING label when it applies
- 📍 location, the flag and the **bold headline**
- the blurb and a "swipe" hint
- 🔍 the sources used
- 🔗 the full story page and 🌐 website link
- "Report a mistake" and "Send us news" links (they open the bot)
- hashtags (`#WireNow #SriLanka` or `#WireNow #WorldNews`)

**Bot conversations:** `/owner` (first sender becomes the owner), `/start report_<id>` (report a mistake), `/tip` (send news). Reader messages are saved in `data/feedback.json` and copied to the owner.

---

## 9. The news website

Main page `docs/index.html`:
- Tabs: ✨ For you · All · (your country) · 🌍 World · ❤️ Saved · 👥 Community.
- **Your country first:** detected from the phone's time zone and language; can be changed. 24 countries have their own national news.
- Today's numbers (USD/LKR rate, Colombo weather), warnings box, **Top 10** (6 Sri Lanka + 4 world). The Top 10 always gets the complete explanation first: other news can't use the last part of the day's AI summaries that the Top 10 still needs, up to 4 Top-10 stories are explained per run even if not posted, and the Top 10 is translated first.
- **"For you"**: learns from what you open, read to the end, save or skip (stored only on your phone).
- Only **fresh news**: nothing older than 3 days, and no "headlines" that are just a website's name.
- **Photos**: a story's own photo. If the news feed has none, the robot fetches the article's own photo once (`data/images.json`, up to 24 per run). A picture shared by 3+ stories from one site is that site's logo/stock picture and is dropped, as are logos and icons. **No clip-art**: a story without a real photo shows a clean band in its topic colour with the news site's name.
- Topics: Politics, Economy, Business, Sports, Tech, Health, Weather, **Entertainment** (films, music, TV, celebrities), **Astrology** (horoscopes, zodiac, nakath, birth charts), Society.
- Each event appears once.

### Languages: English, සිංහල, தமிழ்
- A language switch at the top (EN / සිංහල / தமிழ்). Each person picks **their** language and sees **everything** in it: menus, buttons, labels, headlines and summaries. A Tamil reader never needs English. The choice is remembered on that phone; the first visit guesses from the phone's language.
- Menus and labels are written into the page (`TXT` in `docs/index.html`). They should be checked once by native Sinhala and Tamil speakers.
- **News content** is translated by the robot (`translate_site` in `bot.py`): headlines 30 per AI request, full summaries one language per request, newest and most-covered first. Translated meaning, not word for word. **Every number must survive** the translation, or it is thrown away. Saved in `data/translations.json` (each text translated once), added to stories as `"tr": {"si": {...}, "ta": {...}}`. Up to 80 translation requests a day (`translate_calls_per_day`), 4 per run. Needs a Gemini (best for Sinhala and Tamil) or Groq key.
- A story not translated yet shows in English with a small note "translation coming".
- **Any language, based on the visitor's country** (owner's rule): the language button lists **every language people use in the visitor's country** first (e.g. Germany: German, Turkish, Russian, Polish, Arabic, Ukrainian, Italian, English; India: Hindi, Bengali, Telugu, Marathi, Tamil, Urdu, Gujarati, Kannada, Malayalam, Odia, Punjabi, Assamese, English), then all ~70 languages (`COUNTRY_LANGS`, `LANG_NAMES` in `docs/index.html`). Sinhala and Tamil are translated ahead by the robot; any other language is translated **when a reader first picks it** (menus, the headlines on screen, the story they open) by `supabase/functions/translate`, saved in the `translations` table and shared with everyone (each text translated once). Only text that is really on the Wire Now site is translated; translations that change a number or lose a placeholder are thrown away; daily cap 150 requests (`TRANSLATE_DAILY_CAP`). Right-to-left languages (Arabic, Urdu, Hebrew…) switch the page direction. Which languages people pick is counted (no personal data) in `language_use`, to decide which languages the Meaning Engine learns first. Needs the community database + Gemini key.
- Not yet translated: Telegram posts (English), the community app, weather words from the weather service.

### Sections and tools (batch 1)
- **💱 Exchange rates**: tap the US Dollar box. 16 currencies that matter to Sri Lankans (USD, EUR, GBP, INR, SAR, AED, QAR, KWD, OMR, JPY, KRW, AUD, CAD, SGD, MYR, CNY) in rupees for 1 unit, ▲▼ change since yesterday, and a **📊 30-day chart** per currency. Free data (open.er-api.com), market rates (not bank rates). History is kept in `news.json → numbers.history`.
- **📊 Today in numbers**: one fact with a number from each of the biggest summarised stories.
- **Icon covers (14 Nov 2026)**: a story without a good photo gets a neutral cover in its topic colour: a person story shows the person's INITIALS with country and role (AI cards now include "person" and "role"); other stories get a subject icon (Parliament, court, police, weather, floods, economy, cricket… matched from the headline) with the place. Never a drawn or generated face of a real person (trust, legal risk). Labels translated.
- **Photo as wallpaper**: when a story has a good photo, the icon badge (initials or subject + place/country) sits on top of it with a soft dark shade, on the website (list and viewer) and on Telegram cards (`cards.badge`, `cards.draw_badge`).
- **Greeting by the listener's clock**: the radio script never greets; the app adds good morning / afternoon / evening / night from the reader's own phone time, in their language.
- **Headlines are never read aloud (14 Nov 2026)**: Listen only speaks full written sentences: the checked anchor bulletin, a story's spoken script, or its summary ("what happened" + "why it matters"), with anchor links ("In other news…", "Turning to international news…"). If none exist yet, it says "Today's bulletin is being prepared. Please try again in a few minutes."
- **🗃️ Wire Now Fact Base (14 Nov 2026)**: our own database of facts about the world (Supabase tables `facts`, `people`, `claim_checks`, schema PART 7). After each run the robot sends the "what happened" line and key facts of every checked summary (no extra AI) to the `facts` helper, which only accepts the robot (header `x-robot-key` = sha256("wire-now-robot|" + Telegram token), set as the helper's `ROBOT_KEY` by "Set up community"). Each fact keeps its outlets, link and date; 2+ outlets = confirmed. People (from "person"/"role") are counted with their stories. Grows into knowledge pages, living categories, "story so far" and the owner's Level 2 analysis.
- **🔍 "Is this true?" (14 Nov 2026)**: a button on the home page opens a box where anyone pastes a claim or WhatsApp rumour (any supported language). The `check` helper compares it with our Fact Base (word search), the fact-checkers list and today's news, and Gemini answers ✅ confirmed / ❌ false / ⚠️ misleading / ❓ can't verify, in the reader's language, with the sources used. Rules: judged ONLY with that evidence; no source = "can't verify", never a guess; the same claim within 24 h gets the saved answer (no AI); its own daily allowance (`ai_take_for('check')`, 100/day).
- **A news company's app, not a printed paper (owner, 14 Nov 2026)**: Wire Now must look like a modern app/website of a real news company, with our theme "the key information first". So every summarised story opens with the headline and a byline ("✍️ Wire Now Desk · from N reports"), then 🗝️ **Key information** (the key facts) BEFORE "what happened", the full story, why it matters and what's next. `docs/about.html` is the company page in English, Sinhala and Tamil (follows the reader's language): about, how it works, editorial standards, corrections, what we are not, contact.
- **📰 Front page like a news channel (14 Nov 2026)**: the "All" view is a newspaper-style front page (`renderFront`): a big lead story (first Top-10 story with a summary) with its "what happened"; then a section per topic (Politics, Economy, Business, Sports…) showing the best 3 (Sri Lanka first, summaries first, then photo, outlets, freshness) with a one-line summary and "See all ›"; then "⏱️ Latest", every other story in time order like a live feed. Other tabs and topics keep the full list.
- **AI order (14 Nov 2026)**: Gemini's lighter model (`gemini-flash-lite-latest`, the biggest free limit) writes first, then Gemini Flash, Groq (as soon as a GROQ_API_KEY secret exists: ~1,000 free requests a day, no card), then OpenRouter. The Google article reader is used at most 3 times per run.
- **🌱 Living categories + 📖 story so far (14 Nov 2026)**: every AI summary names its ongoing "subject" (1–4 words, e.g. "2027 Budget"); the robot (`living_categories`, data/subjects.json) groups subjects by their words, and one with 5+ stories over 2+ days in the last week appears as a 🌱 chip under the topics; tapping it shows only that subject, with a "📖 The story so far" timeline (oldest first). A week with no new stories moves it to the archive; one-off subjects are forgotten after a month. No extra AI.
- **Translation quality guard (14 Nov 2026)**: only Gemini translates (a weak free model produced garbage: mixed Tamil/Sinhala/English, "Tamil headline"). Every Sinhala/Tamil translation must be ≥70% its own script, contain none of the other script and no leftover instructions (`right_script`), or it is dropped; bad saved ones were purged.
- **Gemini models and reading articles (14 Nov 2026)**: new Google keys can't use `gemini-2.5-flash` (404), so the robot and both helpers use `gemini-flash-latest` / `gemini-flash-lite-latest` first, with the 2.5 names as backup (helpers: `GEMINI_MODELS` env); if a model refuses the "no thinking" setting it is retried without. When a news site and the free reader (r.jina.ai, now often 403) both fail, Gemini opens the page itself ("URL context" tool), at most 6 per run. The save step puts only the run's own commit on top of the latest code (`git rebase --onto origin/main HEAD~1`), so it can never replay old history.
- **🔇 Voice switched OFF (owner's decision, 14 Nov 2026)**: no Listen / Voice buttons on the site (`VOICE_ON = false` in docs/index.html) and the robot no longer writes the news-anchor bulletin (`"voice_bulletin"` setting, off by default), so those AI requests go to summaries and translations. All the voice code (anchor bulletin, editor check, phone voices, Gemini recordings) is kept, switched off, so it can come back with one switch.
- **Feels like WhatsApp (14 Nov 2026)**: the news site is an installable app (`docs/manifest.json`, "📲 Install" button on Android, full screen, own icon) and works offline with the last news (`docs/sw-news.js`: network first, saved copy when offline; the community keeps its own worker). No tap flashes, no double-tap zoom, no browser menus on long-press, no accidental pull-to-refresh; only the news text can be selected. Long-press a story for a WhatsApp-style bar: Copy (headline + summary + link) · Share · Save.
- **Run time budget (14 Nov 2026)**: GitHub stops a run at 14 minutes, and a stopped run used to lose everything (the first Gemini run did). Now: AI summaries only in the first 6 minutes, Top-10 summaries until 7.5, translations until 9–9.5, the bulletin only if under 10 minutes; Gemini Flash runs without "thinking" (faster) with a 75 s limit; the log is written as it goes (`python -u`).
- **Private data stays private (14 Nov 2026)**: the owner's Telegram chat, readers' chat ids (`owner_chat`, `convo`, `bot_offset`) and reader tips/mistake reports are no longer in the public repository. They are stored encrypted (key derived from the Telegram bot token secret; HMAC-SHA256 keystream + tag) in `data/private/`, which is never committed and is carried between runs by GitHub's Actions cache. On 14 Nov 2026 (owner's decision) the public git history was replaced with one fresh commit, removing the owner's personal name, email and old private data from it.
- **Independent review fixes (14 Nov 2026)**: translator only accepts the supported language list (name taken from a fixed list, never from the browser) and rejects anything that looks like code; the website strips < > from every translation; separate daily AI allowances for summaries and translations (`ai_take_for`); failed translations remembered for a day (`translation_fails`); site text cached per country; summaries that aren't translated yet are hidden (never English); failed or too-short Top-10 summaries wait 6 hours (`card_failed`); a missing Gemini model no longer switches off all of Gemini; Top 10 really translated first; photo links rebuilt correctly and failed size checks retried after a day; site slogans ("… | Live Cricket… Updates") dropped; icons match whole words only; the list uses the small photo; no news reloads in a hidden tab or with cache-busting; `story_opened` / `language_picked` accept only real ids / supported languages; only the news itself can be selected and copied.
- **🎙️ Human-voice recordings (built, switched off)**: `radio_audio` can record the bulletin with Google's Gemini speech (EN/TA/SI, MP3 40 kbps, uploaded to the GitHub release "radio", never into the code). It is OFF (`"radio_recordings": false` in feeds.json settings) until the website gets its play button; time budget 240 s per run, 90 s per recording, at most every 4 hours per language.
- **📺 News-anchor bulletin (14 Nov 2026)**: the Top 10 script is written like a professional TV news anchor (formal, neutral, strong lead sentence per story, attribution, "In other news… / Turning to international news…", ends "That is the news from Wire Now."). Only Gemini writes it (never the weak free backup). Then an editor AI (a different company) checks every sentence against the facts: reversed meaning, invented facts, repetition or opinion means the script is dropped and the last good one is kept. A code check also drops scripts that repeat themselves (`repeats_itself`). Only bulletins marked "checked" are played.
- **🎧 Top 10 radio script (14 Nov 2026)**: the robot writes the Top 10 as ONE flowing spoken story (greeting for the time of day, 2–4 full sentences per story, natural links, sign-off), separately in English, Sinhala and Tamil (`top_brief`, `news.json → brief`), when the Top 10 changes, at most once an hour. Only given facts; any number not in the facts drops that script. Headlines become sentences ("Microsoft 'deeply sorry'…" → "Microsoft says it is deeply sorry…"). Other languages get the English script translated.
- **🎧 Listen explains, not reads (14 Nov 2026)**: every AI summary now includes a "spoken" script (80–150 words, how a friendly radio presenter would explain the story), translated like the rest. Listen uses it; without it, Listen adds spoken links ("Here's what happened… Why does this matter?… What happens next?"). "Listen to today's top news" is a mini show with an intro, "Next story / Now, around the world" links and a goodbye. If the phone has no voice for the reader's language, it never falls back to English: it opens the 🔊 Voice sheet with a free "get a better, natural voice" guide (Google voice data works offline; on Android a button opens the voice settings).
- **🎧 Listen**: the phone's own voice reads a story (🎧 in the story viewer) or today's Top 10 ("Listen to today's top news"), with a **🔊 Voice** button to pick any voice on the phone (tap to hear it) and the speed (0.8×–1.25×), remembered per language on the phone (natural/neural voices are chosen first by default), in the reader's language when the phone has that voice (Sinhala/Tamil voices: Settings → Google Text-to-speech), otherwise English. No audio files are downloaded, so it uses almost no data.
- **🔍 Fact check tab**: (1) stories where news sites **contradict** each other, from the meaning check (one factual sentence, no opinion on who is right); (2) the latest articles from Sri Lanka's independent fact-checkers (Factcheck.lk, Fact Crescendo Sri Lanka, Watchdog, AFP Fact Check), listed in `feeds.json → fact_checks`.

### Roadmap: ideas from the best news services (owner asked to take every good idea)
- **Next (owner's priorities)**: ⚙️ **Settings**: every feature is an option per reader (language, country, photos/data saver, dark mode, text size, show/hide listen, numbers, rates, fact check, topics, "For you" learning). 📚 **Knowledge base**: background ("what you need to know first") on stories, knowledge pages that grow from the news (topics, people, places, terms), search across everything explained so far, explained data (weather and prices with the why), and a "🌍 What this means" panel on every story and number (effects for you → Sri Lanka → the world).
- **Setup status (14 Nov 2026)**: DONE: company Gmail, GitHub organization wirenow-lk (repo moved), Supabase project in Mumbai (company email), all 6 GitHub secrets, "Set up community" ran green (database, admin, pop-ups, summaries, translation live). LEFT: (1) Google login: Google Cloud Auth Platform (External, app name Wire Now) → Web client with origin https://wirenow-lk.github.io and redirect https://<project>.supabase.co/auth/v1/callback → paste Client ID/secret into Supabase → Authentication → Providers → Google; Site URL https://wirenow-lk.github.io/wire-now/community/ plus redirect https://wirenow-lk.github.io/wire-now/**; publish the app. (2) Test: sign in, username, chat password, authenticator, first post. (3) Safety paper check. (4) Phone security check. Then delete the old Sydney project in the owner's personal Supabase account.
- **Waiting for the owner's decision**: weekly health check robot (private Telegram report); "tell me before doing anything" as a rule for all projects; matching, recent photos of people/places from free sources (Wikimedia Commons, official photos) with credit and year; "start general, follow how people use it" principle with anonymous usage counts, a suggestion button and a monthly needs report; growing the community toward a Telegram-style app; daily encrypted database backup + code mirror; own domain.
- **Every word in the reader's language (14 Nov 2026)**: in Sinhala, Tamil or any other language, the site never shows English text. Order: the robot's translation (data/translations.json) → the live translator (Supabase function, shared cache) → otherwise the story is hidden with a "N more stories appear once translated" note, and other texts show "Translating…". Place names, source names, other reports, fact checks and source descriptions are translated too. Test: `tests/check_language.py` (headless browser, Tamil and Sinhala pages must have no English words except brand names).
- **Independence plan (long-term goal)**: after a certain level (revenue), Wire Now stops depending on outside services and runs on a system the owner controls: (1) own server (rented VPS first, later own hardware) running Postgres + the website + the robot; (2) own open AI model instead of Gemini/Groq/OpenRouter; (3) own domain (e.g. wirenow.lk) and own email; (4) own backups. Every piece built now must stay portable: plain Postgres SQL, plain HTML/JS, no lock-in features without a self-hosted equivalent. Supabase itself is open source and can be self-hosted.
- **Admin deep analysis (Level 2)**: the public gets Level 1 ("🌍 What this means"); the owner gets a deeper Level 2 version of everything: connections across stories, causes, scenarios ("if this continues…"), risks and opportunities for Sri Lanka, trends over weeks. Delivered privately (admin-only table behind the authenticator, or a private bot message), **never** in the public repo or docs/.
- **Batch 2**: ⚖️ Different sides (how each site reports a story, like Ground News / Particle "Opposite Sides") · 🧒 Explain simply (like Particle "Explain Like I'm 5") · ❓ Ask about this story (AI answers only from the articles) · 🧵 Story so far (timeline of an ongoing story, like Google News Full Coverage).
- **Batch 3**: 🇱🇰 daily life: gold prices, fuel prices, stock market (ASPI), power-cut and weather warnings, pulled from the news.
- **Batch 4**: 📴 data saver + offline reading (like SmartNews) · 🌙 dark mode, text size · ☀️ morning/evening briefings · 🧩 weekly news quiz · 📊 community polls.
All must follow the core rule (any phone, little data) and stay free.

### The story viewer (owner's rules)
- **Only the headline, then the summary. Nothing in between.**
- Headline-only story = one card. Tap = next card or next story (endless, like Instagram). Swipe up/down = next/previous story.
- ❤️ Save and 📤 Share are small buttons at the top.
- **Double tap** = more from the source: the source's own description, the original article, other reports on the same event, and (when the community database is set up) a summary written on the spot.

### "Other reports on this" (owner's rules)
- Up to 5 reports from **different** sites about the same event.
- **Judged by meaning, not words.** A report is shown only if it adds something new: new facts, another part of the story, another side, different numbers or places, or a contradicting claim. Reports that only repeat the same information are dropped. When unsure, keep it.
- The AI makes this judgement (once per story). Before it has judged, careful word rules are used: never drop a report that has different numbers, opposite words (increase/decrease, up/down, approve/reject…), a different "not", or a different description.

---

## 10. The community (social app)

Address: `/community/`. Code: `docs/community/`. Database plan: `community/schema.sql`.

### Spirit
Made for **introverts and ambiverts**: calm, quiet, no pressure, no popularity contest.

### Features
- **🏠 Home**: short thoughts ("status posts", up to 1000 characters) from people you follow, or everyone.
- **🗂️ Topics**: Reddit-style discussions. 10 official topics (Wire Now News, Politics, Economy, Business, Sports, Tech, Health, Weather & Alerts, Local Area, Society) plus communities made by readers. Up/down votes, threaded replies, Popular / Newest / Top this week.
- **✉️ Chats**: private 1-to-1 and group chats (up to 50 people), live, **end-to-end encrypted**.
- **🔔 Alerts**: replies, new followers, shares. Optional **silent** phone pop-ups (no sound, no vibration).
- **🪴 Workshop**: each person's own page: name, bio, their words and what they shared.

### Calm-design rules (owner's decisions)
- **No public numbers**: follower counts and like counts on thoughts are only visible to their owner.
- **No "seen", no "online", no "typing…".**
- **Who can message you**: only people you follow (default), everyone, or nobody.
- **Silent alerts**; one alert per chat until it's read.
- **Text only** for now.

### Moderation and limits
- Log in with **Google**; everyone picks a username (it doesn't need to be their real name). Emails are never shown.
- Bad-word filter on public posts, replies, usernames and community names.
- Limits: 5 posts an hour, 30 replies an hour, 20 messages a minute, 100 follows an hour, 10 reports an hour, 5 new groups a day; communities only after the account is 1 day old, at most 3 each.
- **Block** (stops messages and follows), **Report** (posts, replies, people, messages), **Admin**: remove/restore, ban, review reports. Admin powers require the authenticator code.

---

## 11. Privacy and security

- **Private chats are end-to-end encrypted.** Each person's phone makes a key pair (ECDH P-256); messages are locked with AES-256-GCM. The private key is locked with the person's **chat password** and a second copy with a **12-word recovery code** (PBKDF2, 310,000 rounds) before it is stored. The database **refuses** unlocked messages. Someone who only reads the database (a leak, a copy) cannot read chats. Honest limit (independent review, 14 Nov 2026): public keys come from the server and are not yet verified by the people chatting, so someone who can CHANGE the database could swap a key and read NEW messages. Planned: safety numbers (key fingerprints people can compare) and a pinned, self-hosted copy of the Supabase library (it is still loaded from jsdelivr as `@2`, because pinning needs network access to fetch and check the file).
  - Change the chat password any time: nothing is lost.
  - New phone: type the chat password once.
  - Forgot it: use the 12 words, then choose a new password.
  - Lost both: start again with new keys; each chat reopens when another member next opens it.
  - Reporting a message attaches that one message's readable text so an admin can check it.
  - The bad-word filter cannot check private chats (it can't read them).
- **Authenticator app (6-digit codes)**: anyone can add one in Settings. Once added, private data (chats, keys, alerts, follows, blocks, votes) stays shut until the code is entered (enforced by the database). **Admin powers always need it.**
- Database rules (row-level security) decide what each person can see and change; tested with 141 automatic checks.
- Phone pop-ups never contain message text, only "New message from …".
- Public things (posts, topics, Workshop pages) are not encrypted on purpose: they are meant to be read.
- Everything travels over HTTPS; Supabase encrypts the stored database.
- **Owner's safety sheet (on paper, at home):** Google backup codes, GitHub recovery codes, Telegram password, chat recovery code, Supabase database password. Turn on Google Authenticator's cloud backup.

---

## 11b. Translation and the Wire Now Meaning Engine

### Goal
Anyone can read and chat in **their own language**. A Sinhala speaker and a Hindi speaker can talk; each sees the other's words in their own language, with the meaning kept.

### Design (one translation layer, engines can be swapped)
All translation goes through **one translation layer**. It picks the best engine available for each person, in this order:
1. **Meaning Engine on the phone** (long-term, see below): private and free.
2. **The phone's own built-in translator**, where the browser has one (today only desktop Chrome/Edge): private and free.
3. **Server AI translation** (Gemini etc.): works on **every** phone, all languages including Sinhala. Uses the free AI allowance.

Rules:
- **Public content** (posts, topics, replies, Workshop pages, news summaries) is translated automatically and saved, so each piece is translated once per language.
- **Private chats** are translated by the server **only when both people switch on "Translate this chat"**, with a clear note that the messages pass through the translation service. Server translations of private messages are **never saved or logged**. Chats without it stay fully end-to-end encrypted. When a private on-phone engine exists for both people's languages, it is used instead.
- The original is always one tap away ("show original").
- Daily translation limits apply while on free AI plans.

### The Meaning Engine (long-term goal, built in the background)
The owner's idea: a **language of pure meaning** in the middle (an "interlingua"). It must cover **every language people use** (Sinhala, Tamil, English, Hindi, Japanese, Arabic… all of them), and **every phone carries the engine** with its own language's part. Every language only needs to go **into** meaning and **out of** meaning: 10 languages need 20 parts instead of 90 pair translators. Each phone downloads **only its own language's part** (small enough for any phone), and messages travel as encrypted meaning, so translation is private and free.

How it grows in the background:
1. **Collecting examples:** every server translation of **public** content is saved as an example pair (original + translation, language codes). Never private chats.
2. **When enough examples exist and there is revenue:** train language parts on rented GPUs, in order of how many Wire Now users read or write each language (**Sri Lanka's three languages first: Sinhala, Tamil and English together**, as Sri Lanka comes first; the site records which languages people use, without storing what they write), using open tools (e.g. Mozilla's translation training pipeline / Bergamot, or a shared multilingual model split into per-language parts).
3. **Switch on gradually:** the translation layer uses a language's phone part as soon as it is ready; nothing else changes.
4. **Give back:** consider contributing the Sinhala model to open projects (e.g. Mozilla) so every Sinhala speaker benefits.

Status: **vision recorded; translation layer and example collection to be built next.**

## 12. Files in this project

| File / folder | What it does |
|---|---|
| `MASTER_INDEX.md` | This file |
| `AGENTS.md`, `CLAUDE.md` | Short notes that send any AI assistant here |
| `bot.py` | The news robot (collect, choose, summarise, check, post, build website data) |
| `cards.py` | Draws the picture cards for Telegram |
| `places.py` | Countries and Sri Lankan places; location labels |
| `site_extras.py` | Today's numbers, Top 10, story pages, sitemap |
| `social.py` | Reddit discussions (not working: Reddit blocks GitHub) |
| `feeds.json` | News sources and **all settings** (see section 15) |
| `data/` | The robot's memory: posted stories, cards, state, reader feedback, meaning decisions, last run log |
| `docs/` | The website (GitHub Pages). `docs/community/` is the community app |
| `community/schema.sql` | The whole community database: tables, rules, limits, encryption, authenticator. Safe to run again |
| `supabase/functions/push` | Sends silent phone pop-ups |
| `supabase/functions/summarize` | Writes summaries on request (double tap) |
| `.github/workflows/news.yml` | Runs the robot every 15 minutes |
| `.github/workflows/community.yml` | Sets up the community database and server functions; daily keep-awake check |
| `fonts/`, `logo-small.png`, `docs/logo.png` | Inter fonts (open licence) and the logo (white cable "W" with a spark, on orange) |

---

## 13. Decision log

Newest last. Add a line for every new decision.

| Date | Decision |
|---|---|
| Nov 2026 | Name chosen: **Wire Now**. Telegram channel + free website. Sri Lanka first, then world. English. |
| Nov 2026 | Deepstash-style swipe cards; summaries must be complete (what/who/when/where/how/why, all details). |
| Nov 2026 | Important news researched across several sources; summaries combine websites. |
| Nov 2026 | AI council: Gemini and Groq added beside OpenRouter. $10 OpenRouter top-up postponed (decide later). |
| Nov 2026 | Location labels on stories. Instagram-like endless feed. National news per country, visitor's country first. |
| Nov 2026 | Breaking news and warnings first; reader reports and news tips through the bot; "For you" feed. |
| Nov 2026 | Logo A chosen: white cable "W" with a spark on orange. |
| Nov 2026 | Press releases out of the Sri Lanka list; foreign stories go to World. |
| Nov 2026 | Google Search Console verified; sitemap submitted. |
| 13 Nov 2026 | Community: a Reddit-like service (not Reddit's data). Google login; text and link posts; fixed topics + reader communities + one shared feed. |
| 13 Nov 2026 | Community database on Supabase free plan now; move to own server (VPS) after revenue. |
| 13 Nov 2026 | Community becomes a calm social app for introverts and ambiverts: Instagram + WhatsApp style, mainly text. Profiles called "Workshop". |
| 13 Nov 2026 | Silent phone pop-ups (no sound). No public counts, no seen/online/typing. |
| 13 Nov 2026 | Photos and videos: not now (storage costs, moderation). Text only. |
| 13 Nov 2026 | Story viewer: only the headline, then the summary. Headline-only = one card. |
| 13 Nov 2026 | Double tap = more from the source; on-demand summaries in the full format, written ahead for the reader's next stories. |
| 13 Nov 2026 | "Other reports" must add new information, judged by **meaning** (AI), not words. |
| 13 Nov 2026 | Private chats end-to-end encrypted; chat password (changeable) + 12-word recovery code. Public things not encrypted. |
| 13 Nov 2026 | Authenticator app for logins; required for admin powers. |
| 13 Nov 2026 | Projects should appear under an anonymous company identity (company email + GitHub organization), still owned by the owner. Own name used until then. |
| 13 Nov 2026 | Website shows only fresh news (3 days). |
| 13 Nov 2026 | This Master Index created; it must work with any AI assistant. |
| 13 Nov 2026 | **Core rule: accessible to anyone.** A 600 MB on-phone translator was rejected for breaking it. |
| 13 Nov 2026 | Translation: people chat and read in their own language. Server translation now (public automatic; private chats only with both people's consent, never saved). |
| 13 Nov 2026 | News website in English, Sinhala and Tamil: each person picks one language and sees everything in it (many readers asked for Tamil). |
| 13 Nov 2026 | Summaries must contain everything the article says, simplified (like Daily Mirror's "Mirror AI" bullet summary, but complete). Short format dropped; completeness check added; key facts 4–8 bullets. The source's own short description is labelled "From <site>", not "Summary". |
| 13 Nov 2026 | Fake "headlines" that are only a website's name or slogan are skipped when news is collected. |
| 13 Nov 2026 | New sections like modern news sites: exchange rates + charts, today in numbers, listen (phone voice), fact check. Roadmap of batches 2–4 recorded. |
| 13 Nov 2026 | No mismatched clip-art pictures: real article photos fetched, shared logo pictures dropped, clean colour band when there's no photo. New topics: Entertainment, Astrology. |
| 13 Nov 2026 | Language choice based on the visitor's country, listing every language used there (e.g. Germany, India), translated on demand and shared. |
| 13 Nov 2026 | Never-again system: self-learning headline cleaner (repeated site labels removed for any site), AI picks topics by meaning, every reported mistake becomes an automatic test. |
| 13 Nov 2026 | "Every word" in the chosen language: country names now translated too (browser's built-in names, Sinhala safety list). |
| 13 Nov 2026 | Two levels of understanding: Level 1 for the public, deeper Level 2 analysis only for the owner, kept private. |
| 13 Nov 2026 | Core principles added: Wire Now is a knowledge base (understanding, background, knowledge that builds up); everything is an option for each reader (Settings). |
| 13 Nov 2026 | Sri Lanka's three languages (Sinhala, Tamil, English) are equally first-class and come first in translation. |
| 13 Nov 2026 | Meaning Engine must cover **every language** people use, and every phone carries it (its own language's part). Languages are trained in order of how many users use them; Sri Lanka's three languages (Sinhala, Tamil, English) first. |
| 13 Nov 2026 | **Wire Now Meaning Engine** (a language of pure meaning in the middle) is the long-term goal and part of the system in the background: one translation layer, example collection from public content only, per-language phone parts trained after revenue, Sinhala first. |

---

## 14. Planned, pending and deferred

### Next steps (owner)
1. Create the **company email** (recovery = owner's phone).
2. Create a **GitHub organization** and move `wire-now` into it; then update `website_url` in `feeds.json`, the Search Console property and links.
3. **Supabase** with the company email: new project in **Mumbai**; delete the Sydney test project.
4. Add the GitHub secrets marked "To add" in [section 3](#3-accounts-and-where-things-live); run "Set up community".
5. Set up **Google login** (Google Cloud OAuth client → Supabase Auth → Google provider; Site URL = the community address).
6. Check Supabase has the authenticator (TOTP) option switched on.
7. Test: log in, choose a username, turn on private chats, add the authenticator, make the first post.
8. Write the **safety sheet** on paper; run Google's phone checks (Security Checkup, Play Protect, Privacy dashboard, Find My Device, device-admin apps).
9. Telegram: turn on reactions, set the channel photo to the logo, invite people (goal: 1,000 subscribers).

### Next build
- Translation layer + server translation (public automatic, private with consent) + example collection for the Meaning Engine (section 11b).

### Deferred (decided to do later)
- Community app in Sinhala and Tamil (the news website is done).
- Training the Meaning Engine's language parts for every language people use (after revenue; Sinhala, Tamil and English first, then by number of users).
- More countries beyond the current 24.
- Photos and videos in the community (after revenue).
- Own database server (after revenue).
- A domain name (after revenue).
- Revenue: Telegram ads once the channel has 1,000+ subscribers.
- $10 OpenRouter top-up decision.
- A separate personal "AI council" web app for the owner (separate project).

### Known limitations
- Reddit discussions don't work (Reddit blocks GitHub's servers).
- Free AI limits cap how many stories get summaries each day.
- Some news sites block reading; those stories fall back to source links.

---

## 15. How to change common things

Most settings are in **`feeds.json` → `settings`**:

| Setting | Meaning | Now |
|---|---|---|
| `max_posts_per_run_sri_lanka` / `_world` | Telegram posts per 15-minute run | 3 / 2 |
| `max_story_age_hours` | Oldest story the robot will post | 12 |
| `max_breaking_per_run` | Urgent posts per run | 3 |
| `min_outlets_world` | World stories need this many outlets | 2 |
| `ai_stories_per_day` / `_council` | Summaries per day without / with Gemini or Groq | 12 / 80 |
| `ai_share_for_normal_news` | Share of the allowance normal news may use | 0.5 |
| `research_max_articles` / `normal_max_articles` | Articles read for important / normal news | 5 / 3 |
| `website_story_count` | Stories on the website | 150 |
| `stories_per_country` | Stories per country file | 60 |
| `website_url` | The website address (change after moving to the organization) | GitHub Pages address |
| `hashtags_sri_lanka` / `hashtags_world` | Telegram hashtags | `#WireNow #SriLanka` / `#WireNow #WorldNews` |
| `council` | AI models, order and daily caps | see section 7 |

Optional settings with defaults: `translate_calls_per_day` (80), `translate_calls_per_run` (4), `website_max_age_hours` (72), `meaning_calls_per_day` (48), `meaning_calls_per_run` (2), `roundup_hour` (20).

- **Add a news source:** add an entry to the `sri_lanka` or `world` list in `feeds.json` (`url` for a normal RSS feed, or `google` with the site address for sites that block GitHub).
- **Community limits and rules:** edit `community/schema.sql`, then run "Set up community". The file is safe to run again.
- **Bad words:** add rows to the `banned_words` table in Supabase (Table Editor).
- **Make someone admin:** set `COMMUNITY_ADMIN_EMAIL`, or set `is_admin` on their row in the `profiles` table.

---

## 16. If something breaks

- **See what the robot did:** `data/last_run.log`, or GitHub → Actions → "Post news" → the latest run.
- **Nothing posted:** check the secrets (the log lists "SECRET PROBLEMS"), and that the bot is still an admin of the channel.
- **"bot is not a member of the channel":** remove the bot from the channel and add it again as admin with "Post messages".
- **No summaries:** the daily AI allowance may be used up (the log says "daily limit reached"); it resets each day.
- **Community says "almost ready":** the Supabase secrets are missing; add them and run "Set up community".
- **Community database asleep:** the free plan pauses after a week without visitors; the daily check in "Set up community" keeps it awake, or press "Restore" in Supabase.
- **Testing changes:** the community database rules can be tested on any PostgreSQL 16 with small stand-ins for Supabase's `auth` functions; the website can be tested in a phone-sized browser with a pretend database.
