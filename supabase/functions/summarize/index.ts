// Wire Now: writes a summary for a headline-only story when a reader asks (double tap),
// or a little ahead of time for the stories a reader is about to see.
// Same rules as the robot: facts only from the article, every number and name checked.
import { createClient } from "npm:@supabase/supabase-js@2";

/* new projects may have only the new secret keys (SUPABASE_SECRET_KEYS), not the old service_role key */
function serviceKey(): string {
  const old = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (old) return old;
  try { const k = JSON.parse(Deno.env.get("SUPABASE_SECRET_KEYS") ?? "{}"); const v = Array.isArray(k) ? k[0] : Object.values(k)[0]; if (typeof v === "string") return v; } catch (_) { /* fall through */ }
  return Deno.env.get("SUPABASE_SECRET_KEY") ?? "";
}

const DAILY_CAP = Number(Deno.env.get("SUMMARY_DAILY_CAP") ?? "200");
const AHEAD_SHARE = 0.6; // writing ahead may use at most 60% of the day's allowance
const SITE = (Deno.env.get("SITE_URL") ?? "").replace(/\/?$/, "/");
const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const reply = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json" } });

const PROMPT = `You turn a news article into story cards for a news app. The reader must understand the WHOLE story
without opening the article.

STRICT RULES - follow every one:
- Use ONLY facts written in the ARTICLE below. Do not add background, guesses or opinions.
- Copy every number, date, amount, name and place EXACTLY as the article writes it.
- NOTHING LEFT OUT: include EVERY piece of information the article gives (every number, name, place, date,
  statement, reason and next step), in simpler words. Not broad or wordy, but complete. A longer article
  needs a longer summary.
- If the article does not say why it matters, set "why_it_matters" to "".
- If the article does not say what happens next, set "whats_next" to "".
- Write in simple English, in your OWN words. Never copy whole sentences from the article.
- "what_happened": 3 to 4 sentences that answer WHO, WHAT, WHEN, WHERE, HOW and WHY (as far as the article says).
- "details": 2 to 4 paragraphs (2-4 sentences each) that together explain EVERYTHING the article says:
  who is involved, exactly what happened and in what order, where, when, how and why, the numbers,
  descriptions of the people, places and things involved, any background the article gives, and what each
  side said. If the article is about a report, budget or law, explain what it actually contains and means.
- "key_facts": 4 to 8 short points (each under 20 words) that together cover EVERY main point of the article,
  like a bullet-point summary: who, what, where, when, how many, what was said, what happens next.
- "blurb": one sentence (under 25 words) that makes people want to read more, using only article facts.
- "topic": one of: Politics, Economy, Business, Sports, Tech, Health, Weather, Entertainment, Astrology, Society.

Reply with ONLY this JSON, nothing else:
{"topic": "...", "what_happened": "...", "details": ["...", "..."], "why_it_matters": "...", "key_facts": ["...", "..."], "whats_next": "...", "blurb": "..."}

HEADLINE: %H

ARTICLE:
%A
`;
const FIX = `

IMPORTANT: Your last answer had these problems. Fix them by using ONLY words from the article:
%P
`;

// ---------------------------------------------------------------- reading the article
async function readArticle(url: string): Promise<string> {
  try {
    const r = await fetch("https://r.jina.ai/" + url, {
      headers: { "Accept": "text/plain", "X-Return-Format": "text" },
      signal: AbortSignal.timeout(30000),
    });
    if (!r.ok) return "";
    const raw = await r.text();
    const body = raw.split("Markdown Content:").pop() ?? "";
    const keep = body.split("\n").map((l) => l.trim()).filter((l) =>
      l.length > 60 && (l.match(/ /g) ?? []).length > 8 && !/^[\[!*#|]/.test(l) &&
      !/cookie|subscribe|all rights reserved|copyright ©|sign up|newsletter/i.test(l));
    return [...new Set(keep)].join("\n").slice(0, 9000);
  } catch (_) {
    return "";
  }
}

// ---------------------------------------------------------------- the AI (Gemini first, Groq as backup)
// newest Google model first ("-latest"; new keys can't use some older ones), the older name as backup
const GEMINI_MODELS = (Deno.env.get("GEMINI_MODELS") ?? "gemini-flash-lite-latest,gemini-flash-latest").split(",");
async function askGemini(prompt: string): Promise<string> {
  const key = Deno.env.get("GEMINI_API_KEY");
  if (!key) throw new Error("no gemini key");
  let last = "";
  for (const model of GEMINI_MODELS) {
    for (const fast of [true, false]) {               // without "thinking" first (faster); some models refuse that setting
      const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model.trim()}:generateContent`, {
        method: "POST", headers: { "Content-Type": "application/json", "x-goog-api-key": key },
        body: JSON.stringify({ contents: [{ parts: [{ text: prompt }] }],
          generationConfig: { temperature: 0.2, responseMimeType: "application/json", ...(fast ? { thinkingConfig: { thinkingBudget: 0 } } : {}) } }),
        signal: AbortSignal.timeout(50000),
      });
      if (r.ok) {
        const j = await r.json();
        return j?.candidates?.[0]?.content?.parts?.filter((p: { thought?: boolean }) => !p.thought).map((p: { text?: string }) => p.text ?? "").join("") ?? "";
      }
      last = "gemini " + r.status;
      if (r.status === 400 && fast) continue;         // try again without the thinking setting
      break;                                          // 404 etc.: next model
    }
  }
  throw new Error(last || "gemini failed");
}
async function askGroq(prompt: string): Promise<string> {
  const key = Deno.env.get("GROQ_API_KEY");
  if (!key) throw new Error("no groq key");
  const r = await fetch("https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    headers: { "Content-Type": "application/json", "Authorization": "Bearer " + key },
    body: JSON.stringify({ model: "llama-3.3-70b-versatile", temperature: 0.2, response_format: { type: "json_object" },
      messages: [{ role: "user", content: prompt }] }),
    signal: AbortSignal.timeout(45000),
  });
  if (!r.ok) throw new Error("groq " + r.status);
  const j = await r.json();
  return j?.choices?.[0]?.message?.content ?? "";
}
async function ask(prompt: string): Promise<[string, string]> {
  try { return [await askGemini(prompt), "gemini-2.5-flash"]; } catch (_) { /* try the backup */ }
  return [await askGroq(prompt), "groq-llama-3.3-70b"];
}
function parseJson(t: string): Record<string, unknown> {
  const m = t.match(/\{[\s\S]*\}/);
  try { return m ? JSON.parse(m[0]) : {}; } catch (_) { return {}; }
}

// ---------------------------------------------------------------- the fact check (same as the robot's)
const NUM: Record<string, string> = Object.fromEntries(
  "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty"
    .split(" ").map((w, i) => [w, String(i)]));
const digits = (t: string) => t.replace(new RegExp(`\\b(${Object.keys(NUM).join("|")})\\b`, "gi"), (w) => NUM[w.toLowerCase()]);
const norm = (t: string) => t.toLowerCase().replace(/[’‘]/g, "'").replace(/[“”]/g, '"').replace(/\s+/g, " ");
const COMMON = new Set("a an the this that these those it its he she they we you i in on at of for to by with from as but and or so if when while after before however also there here his her their our my your one two three four five six seven eight nine ten first second third last new more most some many all no not yes mr mrs ms dr st monday tuesday wednesday thursday friday saturday sunday january february march april may june july august september october november december today yesterday tomorrow what why how who where which officials government police".split(" "));
function check(cards: Record<string, unknown>, article: string): string[] {
  const problems: string[] = [];
  const art = norm(digits(article)), artDigits = art.replace(/(?<=\d),(?=\d)/g, "");
  const list = (v: unknown) => (Array.isArray(v) ? v.map(String) : []);
  const text = [cards.what_happened, ...list(cards.details), cards.why_it_matters, ...list(cards.key_facts), cards.whats_next, cards.blurb]
    .filter(Boolean).join("\n");
  for (const num of new Set(digits(text).match(/\d[\d,]*(?:\.\d+)?/g) ?? [])) {
    const n = num.replace(/,/g, "").replace(/\.$/, "");
    if (n && !artDigits.includes(n)) problems.push(`the number ${num} is not in the article`);
  }
  for (const sentence of text.split(/(?<=[.!?])\s+|\n/)) {
    const words = sentence.match(/[A-Za-z][A-Za-z'’\-]*/g) ?? [];
    words.forEach((w, i) => {
      if (i === 0 || w[0] !== w[0].toUpperCase() || w.length < 3 || COMMON.has(w.toLowerCase())) return;
      const bare = w.replace(/['’]s$/, "");
      if (!art.includes(norm(bare))) problems.push(`the name/word '${bare}' is not in the article`);
    });
  }
  if (!cards.what_happened) problems.push("'what_happened' is empty");
  if (!list(cards.details).length) problems.push("'details' is empty: explain the whole story in 2 to 4 paragraphs");
  // complete: a summary can't be much shorter than the article allows
  const artWords = (article.match(/\w+/g) ?? []).length;
  const got = ([cards.what_happened, ...list(cards.details), ...list(cards.key_facts)].join(" ").match(/\w+/g) ?? []).length;
  const need = Math.min(200, Math.max(Math.min(80, Math.floor(artWords * 0.7)), Math.floor(artWords * 0.3)));   // short articles need less
  if (got < need) problems.push(`the summary is too short (${got} words) for an article of ${artWords} words: it is missing information. Include EVERY fact the article gives (aim for at least ${need} words)`);
  if (list(cards.key_facts).length < 4) problems.push("key_facts must have 4 to 8 points covering every main point of the article");
  return [...new Set(problems)];
}

// ---------------------------------------------------------------- finding the real story (no made-up links)
async function findStory(id: string, country: string) {
  const files = ["news.json"];
  if (/^[A-Z]{2}$/.test(country)) files.push(`c/${country}.json`);
  for (const f of files) {
    try {
      const r = await fetch(SITE + f, { signal: AbortSignal.timeout(10000) });
      if (!r.ok) continue;
      const d = await r.json();
      const all = [...(d.sri_lanka ?? []), ...(d.world ?? []), ...(d.stories ?? [])];
      const s = all.find((x: { id?: string }) => x.id === id);
      if (s) return s;
    } catch (_) { /* next file */ }
  }
  return null;
}

// ---------------------------------------------------------------- main
Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  let id = "", country = "", ahead = false;
  try { const b = await req.json(); id = String(b.id ?? "").slice(0, 80); country = String(b.country ?? ""); ahead = !!b.ahead; }
  catch (_) { return reply({ status: "bad" }, 400); }
  if (!id) return reply({ status: "bad" }, 400);
  const sb = createClient(Deno.env.get("SUPABASE_URL")!, serviceKey());

  const { data: have } = await sb.from("summaries").select("status,cards,updated_at").eq("story_id", id).maybeSingle();
  if (have?.status === "ready") return reply({ status: "ready", cards: have.cards });
  if (have?.status === "failed" && Date.now() - new Date(have.updated_at).getTime() < 6 * 3600e3) return reply({ status: "failed" });
  if (have?.status === "working" && Date.now() - new Date(have.updated_at).getTime() < 120e3) return reply({ status: "working" });

  const story = await findStory(id, country);
  if (!story) return reply({ status: "unknown" }, 404);
  if (story.cards) return reply({ status: "ready", cards: story.cards });

  const { data: ok } = await sb.rpc("ai_take_for", { kind: "summarize", cap: ahead ? Math.floor(DAILY_CAP * AHEAD_SHARE) : DAILY_CAP });
  if (!ok) return reply({ status: "busy" });   // today's free allowance is used up

  await sb.from("summaries").upsert({ story_id: id, status: "working", title: story.title, link: story.link,
                                      source: story.source, updated_at: new Date().toISOString() });
  const fail = async (reason: string) => {
    await sb.from("summaries").update({ status: "failed", reason, updated_at: new Date().toISOString() }).eq("story_id", id);
    return reply({ status: "failed" });
  };

  let article = await readArticle(story.link);
  if (article.length < 300 && story.summary && story.summary.length > 200) article = story.summary;
  if (article.length < 300) return fail("could not read the article");
  article = `SOURCE: ${story.source}\n${article}`;

  let prompt = PROMPT.replace("%H", story.title).replace("%A", article);
  for (const attempt of [1, 2]) {
    let text = "", model = "";
    try { [text, model] = await ask(prompt); } catch (e) { return fail("AI unavailable: " + String(e).slice(0, 80)); }
    const cards = parseJson(text);
    const problems = check(cards, article);
    if (!problems.length) {
      const list = (v: unknown) => (Array.isArray(v) ? v.map(String).filter((x) => x.trim()) : []);
      const out = { what_happened: String(cards.what_happened), details: list(cards.details).slice(0, 4),
        why_it_matters: String(cards.why_it_matters ?? ""), key_facts: list(cards.key_facts).slice(0, 8),
        whats_next: String(cards.whats_next ?? ""), blurb: String(cards.blurb ?? ""),
        sources: [story.source], mode: "full", topic: cards.topic ?? null };
      await sb.from("summaries").update({ status: "ready", cards: out, model, reason: null, updated_at: new Date().toISOString() }).eq("story_id", id);
      return reply({ status: "ready", cards: out });
    }
    if (attempt === 1) {
      if (!(await sb.rpc("ai_take_for", { kind: "summarize", cap: DAILY_CAP })).data) return fail("daily allowance used up");
      prompt += FIX.replace("%P", problems.slice(0, 8).join("\n"));
    } else return fail("failed the fact check: " + problems.slice(0, 3).join("; "));
  }
  return fail("unknown");
});
