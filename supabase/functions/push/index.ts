// Wire Now: sends silent pop-ups to people's phones when something happens for them.
// Called by the database (only with the secret). The pop-up never contains private message text.
import webpush from "npm:web-push@3.6.7";
import { createClient } from "npm:@supabase/supabase-js@2";

/* new projects may have only the new secret keys (SUPABASE_SECRET_KEYS), not the old service_role key */
function serviceKey(): string {
  const old = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (old) return old;
  try { const k = JSON.parse(Deno.env.get("SUPABASE_SECRET_KEYS") ?? "{}"); const v = Array.isArray(k) ? k[0] : Object.values(k)[0]; if (typeof v === "string") return v; } catch (_) { /* fall through */ }
  return Deno.env.get("SUPABASE_SECRET_KEY") ?? "";
}

Deno.serve(async (req) => {
  try {
    const secret = req.headers.get("x-push-secret") ?? "";
    const { id } = await req.json();
    const sb = createClient(Deno.env.get("SUPABASE_URL")!, serviceKey());
    const { data, error } = await sb.rpc("push_job", { nid: id, secret });
    if (error || !data) return new Response("denied", { status: 403 });
    webpush.setVapidDetails(data.vapid_subject, data.vapid_public, data.vapid_private);
    const payload = JSON.stringify({ title: data.title, body: data.body, link: data.link });
    let sent = 0;
    for (const sub of data.subs ?? []) {
      try {
        await webpush.sendNotification(sub, payload, { TTL: 6 * 3600, urgency: "low" });
        sent++;
      } catch (e) {
        const code = (e as { statusCode?: number }).statusCode;
        if (code === 404 || code === 410) await sb.rpc("push_gone", { endpoint_url: sub.endpoint, secret });
      }
    }
    return new Response(JSON.stringify({ sent }), { headers: { "Content-Type": "application/json" } });
  } catch (_e) {
    return new Response("bad request", { status: 400 });
  }
});
