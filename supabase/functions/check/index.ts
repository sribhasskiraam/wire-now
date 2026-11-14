// "🔍 Is this true?": a reader types or pastes a claim; Wire Now checks it against its own Fact Base, real
// fact-checkers and its own news. The AI never decides alone: no reliable source = "unverified".
import { createClient } from "npm:@supabase/supabase-js@2";

function serviceKey(): string {
  const old = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (old) return old;
  try { const k = JSON.parse(Deno.env.get("SUPABASE_SECRET_KEYS") ?? "{}"); const v = Array.isArray(k) ? k[0] : Object.values(k)[0]; if (typeof v === "string") return v; } catch (_) { /* fall through */ }
  return Deno.env.get("SUPABASE_SECRET_KEY") ?? "";
}
const DAILY_CAP = Number(Deno.env.get("CHECK_DAILY_CAP") ?? "100");
const SITE = (Deno.env.get("SITE_URL") ?? "").replace(/\/?$/, "/");
const LANGS: Record<string, string> = { en: "English", si: "Sinhala", ta: "Tamil", hi: "Hindi", bn: "Bengali", te: "Telugu",
  mr: "Marathi", ur: "Urdu", gu: "Gujarati", kn: "Kannada", ml: "Malayalam", pa: "Punjabi", ne: "Nepali", ar: "Arabic",
  he: "Hebrew", fa: "Persian", tr: "Turkish", ru: "Russian", uk: "Ukrainian", pl: "Polish", de: "German", fr: "French",
  es: "Spanish", pt: "Portuguese", it: "Italian", nl: "Dutch", ro: "Romanian", el: "Greek", sv: "Swedish", no: "Norwegian",
  da: "Danish", fi: "Finnish", hu: "Hungarian", cs: "Czech", sk: "Slovak", sr: "Serbian", hr: "Croatian", bg: "Bulgarian",
  zh: "Chinese (Simplified)", ja: "Japanese", ko: "Korean", vi: "Vietnamese", th: "Thai", id: "Indonesian", ms: "Malay",
  tl: "Filipino", sw: "Swahili" };
const cors = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
  "Access-Control-Allow-Methods": "POST, OPTIONS" };
const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json" } });
async function sha(t: string): Promise<string> {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(t));
  return [...new Uint8Array(d)].slice(0, 16).map((b) => b.toString(16).padStart(2, "0")).join("");
}
const clean = (t: unknown, n: number) => String(t ?? "").replace(/[<>]/g, "").trim().slice(0, n);

const GEMINI_MODELS = (Deno.env.get("GEMINI_MODELS") ?? "gemini-flash-latest,gemini-2.5-flash").split(",");
async function askGemini(prompt: string): Promise<string> {
  const key = Deno.env.get("GEMINI_API_KEY");
  if (!key) throw new Error("no gemini key");
  for (const model of GEMINI_MODELS) {
    for (const fast of [true, false]) {
      const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model.trim()}:generateContent`, {
        method: "POST", headers: { "Content-Type": "application/json", "x-goog-api-key": key },
        body: JSON.stringify({ contents: [{ parts: [{ text: prompt }] }],
          generationConfig: { temperature: 0, responseMimeType: "application/json", ...(fast ? { thinkingConfig: { thinkingBudget: 0 } } : {}) } }),
        signal: AbortSignal.timeout(50000),
      });
      if (r.ok) {
        const j = await r.json();
        return j?.candidates?.[0]?.content?.parts?.filter((p: { thought?: boolean }) => !p.thought).map((p: { text?: string }) => p.text ?? "").join("") ?? "";
      }
      if (r.status === 400 && fast) continue;
      break;
    }
  }
  throw new Error("gemini failed");
}

let siteCache: { at: number; items: { kind: string; text: string; source: string; link: string; date: string }[] } | null = null;
async function siteItems() {
  if (siteCache && Date.now() - siteCache.at < 600e3) return siteCache.items;
  const items: { kind: string; text: string; source: string; link: string; date: string }[] = [];
  try {
    const d = await (await fetch(SITE + "news.json", { signal: AbortSignal.timeout(10000) })).json();
    for (const f of d.fact_checks ?? []) items.push({ kind: "fact-checker", text: String(f.title ?? ""), source: String(f.source ?? ""), link: String(f.link ?? ""), date: String(f.date ?? "") });
    for (const s of [...(d.sri_lanka ?? []), ...(d.world ?? [])])
      items.push({ kind: "news", text: [s.title, s.cards?.what_happened ?? ""].join(". "), source: String(s.source ?? ""), link: String(s.link ?? ""), date: String(s.date ?? "") });
  } catch (_) { /* no site data */ }
  siteCache = { at: Date.now(), items };
  return items;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  let claim = "", lang = "en";
  try { const b = await req.json(); claim = clean(b.claim, 600); lang = LANGS[String(b.lang)] ? String(b.lang) : "en"; }
  catch (_) { return reply({ status: "bad" }, 400); }
  if (claim.length < 8) return reply({ status: "bad" }, 400);
  const sb = createClient(Deno.env.get("SUPABASE_URL")!, serviceKey());
  const key = await sha(claim.toLowerCase().replace(/\s+/g, " ") + "|" + lang);

  // asked before (last 24 hours): the saved answer, no AI used
  const { data: old } = await sb.from("claim_checks").select("*").eq("key", key).maybeSingle();
  if (old && Date.now() - new Date(old.created_at).getTime() < 864e5) {
    await sb.from("claim_checks").update({ asked: (old.asked ?? 1) + 1 }).eq("key", key);
    return reply({ status: "ok", verdict: old.verdict, explanation: old.explanation, sources: old.sources, cached: true });
  }
  const { data: ok } = await sb.rpc("ai_take_for", { kind: "check", cap: DAILY_CAP });
  if (!ok) return reply({ status: "busy" });

  // evidence: our Fact Base (word search) + fact-checkers + today's news
  const words = claim.replace(/[^\p{L}\p{N}\s]/gu, " ").split(/\s+/).filter((w) => w.length > 2).slice(0, 12).join(" or ");
  const { data: facts } = words ? await sb.from("facts").select("statement,sources,source_count,link,reported_at")
    .textSearch("search", words, { config: "simple", type: "websearch" }).order("reported_at", { ascending: false }).limit(25) : { data: [] };
  const evidence = [
    ...(facts ?? []).map((f: any) => ({ kind: f.source_count >= 2 ? "confirmed fact" : "reported fact", text: f.statement, source: (f.sources ?? []).join(", "), link: f.link ?? "", date: f.reported_at })),
    ...(await siteItems()),
  ].slice(0, 260);
  const list = evidence.map((e, i) => `${i + 1}. [${e.kind}, ${e.source}, ${String(e.date).slice(0, 10)}] ${e.text.slice(0, 400)}`).join("\n");

  const prompt = `You are a strict, neutral fact-checker for Wire Now, a Sri Lankan news service.
A reader asks whether this claim is true:
CLAIM: """${claim}"""

Judge it ONLY with the EVIDENCE below (fact-checkers, confirmed facts and news reports). Do not use outside knowledge.
- "false": a fact-checker or reliable reports clearly say the claim is wrong.
- "confirmed": reliable reports clearly say the same thing (prefer items marked confirmed or reported by 2+ outlets).
- "misleading": partly true, exaggerated, missing important context, or about a different time or place.
- "unverified": nothing in the evidence clearly confirms or denies it. When in doubt, choose "unverified".
Write the explanation in ${LANGS[lang]}: 1 to 3 short, neutral sentences saying what the evidence shows, and its date.
Reply with ONLY this JSON: {"verdict": "confirmed|false|misleading|unverified", "explanation": "...", "evidence": [item numbers you relied on]}

EVIDENCE:
${list || "(none)"}`;
  try {
    const m = (await askGemini(prompt)).match(/\{[\s\S]*\}/);
    const j = m ? JSON.parse(m[0]) : {};
    let verdict = ["confirmed", "false", "misleading", "unverified"].includes(j.verdict) ? j.verdict : "unverified";
    const used = (Array.isArray(j.evidence) ? j.evidence : []).map((n: unknown) => evidence[Number(n) - 1]).filter(Boolean).slice(0, 5);
    if (verdict !== "unverified" && !used.length) verdict = "unverified";            // never a verdict without a source
    const explanation = clean(j.explanation, 1200) || "";
    const sources = used.map((e: any) => ({ source: clean(e.source, 80), link: /^https?:\/\//.test(e.link) ? e.link : "", date: String(e.date).slice(0, 10), kind: e.kind }));
    await sb.from("claim_checks").upsert({ key, claim, lang, verdict, explanation, sources, asked: (old?.asked ?? 0) + 1, created_at: new Date().toISOString() });
    return reply({ status: "ok", verdict, explanation, sources });
  } catch (_) {
    return reply({ status: "failed" });
  }
});
