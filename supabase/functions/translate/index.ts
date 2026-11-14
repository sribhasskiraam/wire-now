// Wire Now: translates the site's menus, headlines and summaries into any language a reader picks.
// Each text is translated once and saved for everyone. Only text that is really on the Wire Now site
// is translated, and a translation that changes any number is thrown away.
import { createClient } from "npm:@supabase/supabase-js@2";

/* new projects may have only the new secret keys (SUPABASE_SECRET_KEYS), not the old service_role key */
function serviceKey(): string {
  const old = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (old) return old;
  try { const k = JSON.parse(Deno.env.get("SUPABASE_SECRET_KEYS") ?? "{}"); const v = Array.isArray(k) ? k[0] : Object.values(k)[0]; if (typeof v === "string") return v; } catch (_) { /* fall through */ }
  return Deno.env.get("SUPABASE_SECRET_KEY") ?? "";
}

const DAILY_CAP = Number(Deno.env.get("TRANSLATE_DAILY_CAP") ?? "150");
// ONLY these languages (the same list as the website). The name sent to the AI comes from here, never from the browser.
const LANGS: Record<string, string> = { si: "Sinhala", ta: "Tamil", hi: "Hindi", bn: "Bengali", te: "Telugu", mr: "Marathi",
  ur: "Urdu", gu: "Gujarati", kn: "Kannada", ml: "Malayalam", pa: "Punjabi", ne: "Nepali", ar: "Arabic", he: "Hebrew",
  fa: "Persian", tr: "Turkish", ru: "Russian", uk: "Ukrainian", pl: "Polish", de: "German", fr: "French", es: "Spanish",
  pt: "Portuguese", it: "Italian", nl: "Dutch", ro: "Romanian", el: "Greek", sv: "Swedish", no: "Norwegian", da: "Danish",
  fi: "Finnish", hu: "Hungarian", cs: "Czech", sk: "Slovak", sr: "Serbian", hr: "Croatian", bg: "Bulgarian",
  zh: "Chinese (Simplified)", ja: "Japanese", ko: "Korean", vi: "Vietnamese", th: "Thai", id: "Indonesian", ms: "Malay",
  tl: "Filipino", sw: "Swahili" };
const UNSAFE = /[<>]|javascript:|on\w+\s*=|\bsrc\s*=/i;            // a translation must never contain code
const SITE = (Deno.env.get("SITE_URL") ?? "").replace(/\/?$/, "/");
const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const reply = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json" } });

async function sha(t: string): Promise<string> {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(t));
  return [...new Uint8Array(d)].slice(0, 16).map((b) => b.toString(16).padStart(2, "0")).join("");
}
const numbers = (t: string) => (t.replace(/,/g, "").match(/\d+(?:\.\d+)?/g) ?? []).sort().join("|");

// the site's own text, so only real Wire Now text is translated (cached for 10 minutes, per country)
const siteCache = new Map<string, { text: string; at: number }>();
async function loadSite(country: string): Promise<string> {
  const hit = siteCache.get(country);
  if (hit && Date.now() - hit.at < 600e3) return hit.text;
  const files = ["index.html", "news.json"];
  if (/^[A-Z]{2}$/.test(country)) files.push(`c/${country}.json`);
  const parts = await Promise.all(files.map(async (f) => {
    try { const r = await fetch(SITE + f, { signal: AbortSignal.timeout(10000) }); return r.ok ? await r.text() : ""; } catch (_) { return ""; }
  }));
  const text = parts.join("\n");
  siteCache.set(country, { text, at: Date.now() });
  return text;
}
const onSite = (t: string, site: string) => site.includes(t) || site.includes(JSON.stringify(t).slice(1, -1));

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

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  let lang = "", name = "", country = "", texts: string[] = [];
  try {
    const b = await req.json();
    lang = String(b.lang ?? ""); name = LANGS[lang] ?? ""; country = String(b.country ?? "").slice(0, 2);
    texts = (Array.isArray(b.texts) ? b.texts : []).map(String).filter((t: string) => t.trim() && t.length <= 3000).slice(0, 40);
  } catch (_) { return reply({ status: "bad" }, 400); }
  if (!name || !texts.length) return reply({ status: "bad" }, 400);                 // only supported languages

  const sb = createClient(Deno.env.get("SUPABASE_URL")!, serviceKey());
  const keys = await Promise.all(texts.map(sha));
  const out: Record<string, string> = {};
  const { data: have } = await sb.from("translations").select("key,text").eq("lang", lang).in("key", keys);
  for (const h of have ?? []) out[h.key] = h.text;
  const site = await loadSite(country);
  for (const k in out) if (UNSAFE.test(out[k])) delete out[k];                      // never hand out anything that looks like code
  const since = new Date(Date.now() - 864e5).toISOString();
  const { data: failed } = await sb.from("translation_fails").select("key").eq("lang", lang).in("key", keys).gt("at", since);
  const skip = new Set((failed ?? []).map((f: { key: string }) => f.key));
  const todo = texts.map((t, i) => ({ t, k: keys[i] })).filter((x) => !out[x.k] && !skip.has(x.k) && onSite(x.t, site));
  if (!todo.length) return reply({ status: "ok", out });

  const { data: ok } = await sb.rpc("ai_take_for", { kind: "translate", cap: DAILY_CAP });
  if (!ok) return reply({ status: "busy", out });

  const prompt = `Translate each item from English into ${name} (language code "${lang}") for a news website.
Translate the MEANING naturally, the way a newspaper or app in that language would say it, not word for word.
Keep every number, date and amount exactly. Keep names of people, places and organisations, written the way
that language usually writes them. Keep placeholders like {n}, {s}, {t} exactly as they are. Keep emoji.
Reply with ONLY this JSON: {"items": [{"n": 1, "text": "..."}, ...]}

${todo.map((x, i) => `${i + 1}. ${x.t}`).join("\n")}`;
  try {
    const m = (await askGemini(prompt)).match(/\{[\s\S]*\}/);
    const items = m ? JSON.parse(m[0]).items ?? [] : [];
    const rows = [], good = new Set<string>();
    for (const it of items) {
      const x = todo[Number(it.n) - 1];
      const text = String(it.text ?? "").trim();
      if (!x || !text || text.length > 8000) continue;
      if (UNSAFE.test(text)) continue;                                      // looks like code: never saved
      if (numbers(text) !== numbers(x.t)) continue;                       // a changed number: not safe
      if ((x.t.match(/\{\w+\}/g) ?? []).some((ph) => !text.includes(ph))) continue;   // lost a placeholder
      out[x.k] = text; good.add(x.k);
      rows.push({ key: x.k, lang, text });
    }
    if (rows.length) await sb.from("translations").upsert(rows, { ignoreDuplicates: true });
    const bad = todo.filter((x) => !good.has(x.k)).map((x) => ({ key: x.k, lang, at: new Date().toISOString() }));
    if (bad.length) await sb.from("translation_fails").upsert(bad);
    return reply({ status: "ok", out });
  } catch (_) {
    return reply({ status: "failed", out });
  }
});
