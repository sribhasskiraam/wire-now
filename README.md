# ⚡ Wire Now: Sri Lanka news in 30 seconds, on Telegram

A free robot that runs every 15 minutes. For every new story it:

1. reads Sri Lankan and world news sites (Sri Lanka first)
2. has an AI write short cards: **What happened · Why it matters · Key facts · What's next**
3. **fact-checks** the cards (see below)
4. draws them as colourful **picture cards** and posts them to your Telegram channel as a swipeable album, Deepstash style

Readers never leave Telegram. It costs nothing to run: GitHub runs the robot, Telegram hosts the channel, and OpenRouter supplies a free AI.

---

## Setup (about 20 minutes, works on a phone)

### 1. Telegram bot
1. In Telegram, open **@BotFather** and send `/newbot`.
2. Name it **Wire Now**, with a username ending in `bot` (e.g. `wirenow_news_bot`).
3. Copy the **token** it gives you. Keep it secret.

### 2. Telegram channel
1. Create a **New Channel** called **Wire Now**, make it **Public**, and give it a link such as `t.me/wirenow_lk`.
2. Open the channel → **Administrators → Add Admin**, search for your bot, and allow **Post messages**.
3. *(Optional)* To let people comment on each story: **Channel settings → Discussion → Add a group**.

### 3. AI key
1. Sign up at **openrouter.ai** (free).
2. Go to **Keys → Create Key** and copy it.

*Without this key, stories are still posted (cover picture + summary) but without the 4 cards.*

### 4. GitHub (this is what runs the robot)
1. Make a free account at github.com and create a **public repository** called `wire-now`.
2. Upload all of these files, keeping the folders (`.github/workflows/`, `fonts/`, `data/`, `docs/`).

### 5. Secrets
In the repository: **Settings → Secrets and variables → Actions → New repository secret**

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | the token from BotFather |
| `TELEGRAM_CHANNEL` | `@wirenow_lk` (your channel name) |
| `OPENROUTER_API_KEY` | the key from OpenRouter |

### 6. Start
Go to the **Actions** tab, enable workflows if asked, then **Post news → Run workflow**.
After 1–3 minutes, the first stories appear in your channel. From then on it runs by itself every 15 minutes.

---

## How the summaries stay correct
Before any cards are used, they must pass **two checks**:
1. **Code check:** every number and name in the cards must appear in the original article.
2. **AI checker:** a second AI pass confirms every fact is in the article.

If a check fails, the AI gets one more try. If it fails again, the story is posted **without cards**, using the news site's own summary. Every post links to the full original article.

## Daily AI limit
OpenRouter's free plan allows 50 AI requests a day, and each story uses 2–4. So the robot makes cards for **12 stories a day** (`ai_stories_per_day` in `feeds.json`), and stories after that get just a cover card.
**Later:** adding $10 to OpenRouter once raises the free limit to 1,000 requests a day.

## Changing things (`feeds.json`)
- **News sites:** edit the `sri_lanka` and `world` lists.
- **Posts per run:** `max_posts_per_run_sri_lanka` and `max_posts_per_run_world`.
- **Hashtags.**

The colours and layout of the cards are in `cards.py`.

## Later: website
The robot also keeps a ready-made website in `docs/`. When you want it, turn on **Settings → Pages → Branch `main`, folder `/docs`**. It's free at `YOUR-NAME.github.io/wire-now`.

## Good to know
- **First run:** it posts only a few stories, so the channel isn't flooded with old news.
- **A news site fails:** the others still work. The Actions run log shows `FAIL` next to that site.
- **Copyright:** cards are short summaries in new words, with a link to the original. Never copy full articles.
- **Fonts:** Inter (SIL Open Font License), free to use.
