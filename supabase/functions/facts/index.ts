// Wire Now Fact Base: the robot sends the facts from each checked summary here (only the robot: it proves itself
// with a key made from its own secret). Each fact keeps who reported it and when.
import { createClient } from "npm:@supabase/supabase-js@2";

function serviceKey(): string {
  const old = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (old) return old;
  try { const k = JSON.parse(Deno.env.get("SUPABASE_SECRET_KEYS") ?? "{}"); const v = Array.isArray(k) ? k[0] : Object.values(k)[0]; if (typeof v === "string") return v; } catch (_) { /* fall through */ }
  return Deno.env.get("SUPABASE_SECRET_KEY") ?? "";
}
const clip = (v: unknown, n: number) => String(v ?? "").replace(/[<>]/g, "").trim().slice(0, n);

Deno.serve(async (req) => {
  const robot = Deno.env.get("ROBOT_KEY") ?? "";
  if (!robot || req.headers.get("x-robot-key") !== robot) return new Response("no", { status: 401 });
  let b: { facts?: unknown[]; people?: unknown[] };
  try { b = await req.json(); } catch (_) { return new Response("bad", { status: 400 }); }
  const sb = createClient(Deno.env.get("SUPABASE_URL")!, serviceKey());
  const facts = (Array.isArray(b.facts) ? b.facts : []).slice(0, 500).map((f: any) => ({
    key: clip(f.key, 64), story_id: clip(f.story_id, 20), statement: clip(f.statement, 600), topic: clip(f.topic, 40),
    country: clip(f.country, 60), place: clip(f.place, 120), link: clip(f.link, 600),
    sources: (Array.isArray(f.sources) ? f.sources : []).slice(0, 20).map((s: unknown) => clip(s, 80)),
    source_count: Math.max(1, Math.min(50, Number(f.source_count) || 1)),
    reported_at: f.reported_at || new Date().toISOString(), updated_at: new Date().toISOString(),
  })).filter((f) => f.key && f.story_id && f.statement);
  const people = (Array.isArray(b.people) ? b.people : []).slice(0, 200).map((p: any) => ({
    name: clip(p.display, 120).toLowerCase(), display: clip(p.display, 120), role: clip(p.role, 120), country: clip(p.country, 60),
    stories: (Array.isArray(p.stories) ? p.stories : []).slice(-20).map((s: unknown) => clip(s, 20)),
    mentions: Math.max(1, Math.min(100000, Number(p.mentions) || 1)), last_seen: new Date().toISOString(),
  })).filter((p) => p.name);
  if (facts.length) await sb.from("facts").upsert(facts);
  if (people.length) await sb.from("people").upsert(people);
  return new Response(JSON.stringify({ facts: facts.length, people: people.length }), { headers: { "Content-Type": "application/json" } });
});
