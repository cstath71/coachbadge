import { createClient } from "npm:@supabase/supabase-js@2";
import { FROM_ADDRESS, FUNCTION_URL, SITE, welcomeEmail } from "./email.mjs";

// CoachBadge newsletter endpoint (deploy with verify_jwt = false: browsers and mailbox providers call it without a key).
//   POST {email, cb_hp_note}                     sign up; a new address gets one welcome email
//   POST {action: "unsubscribe", token}          from unsubscribe.html (the link in every email)
//   POST ?unsubscribe=<token>                    RFC 8058 one-click (List-Unsubscribe-Post) from mailbox providers
// Settings (Supabase function secrets; nothing secret is in this file or in the site):
//   WELCOME_ENABLED   "true" to send the welcome email. Anything else (or unset): sign-ups are stored, no email is sent.
//   MAIL_PROVIDER     "agentmail" (default; the only one wired up)
//   MAIL_FROM         sender address = AgentMail inbox id (default coachbadge@agentmail.to; later hello@coachbadge.com)
//   MAIL_API_BASE     default https://api.agentmail.to/v0
//   MAIL_API_KEY      provider API key; if unset, AGENTMAIL_API_KEY, then the Vault secret read by public.coachbadge_mail_config()
//   SITE_URL / PUBLIC_FUNCTION_URL   links in the email (defaults: the GitHub Pages site and this function)
const env = (k: string) => (Deno.env.get(k) || "").trim();
const WELCOME_ENABLED = env("WELCOME_ENABLED") === "true";
const MAIL_PROVIDER = env("MAIL_PROVIDER") || "agentmail";
const MAIL_FROM = env("MAIL_FROM") || FROM_ADDRESS;
const MAIL_API_BASE = (env("MAIL_API_BASE") || "https://api.agentmail.to/v0").replace(/\/+$/, "");
const LINKS = { site: env("SITE_URL") || SITE, functionUrl: env("PUBLIC_FUNCTION_URL") || FUNCTION_URL };

type Msg = { subject: string; text: string; html: string; headers: Record<string, string> };
// One function per provider, same shape. Only AgentMail is wired up.
const SENDERS: Record<string, (key: string, to: string, m: Msg) => Promise<Response>> = {
  agentmail: (key, to, m) => fetch(`${MAIL_API_BASE}/inboxes/${encodeURIComponent(MAIL_FROM)}/messages/send`, {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify({ to: [to], subject: m.subject, text: m.text, html: m.html, headers: m.headers, labels: ["coachbadge-welcome"] }),
  }),
};
const ALLOWED = ["https://cstath71.github.io", "https://coachbadge.com", "https://www.coachbadge.com", "http://localhost:4321"];
const EMAIL_RE = /^[^\s@<>()\[\],;:"]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/;
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const TEST_DOMAIN_RE = /@(example\.(com|net|org)|[^@]+\.(test|example|invalid|localhost))$/i;
const MAX_PER_IP_PER_HOUR = 5;      // sign-up attempts per IP per clock hour
const MAX_WELCOMES_PER_HOUR = 30;   // all welcome emails together, to protect the sending quota

function cors(origin: string | null) {
  const o = origin && ALLOWED.includes(origin) ? origin : ALLOWED[0];
  return { "Access-Control-Allow-Origin": o, "Access-Control-Allow-Methods": "POST, OPTIONS", "Access-Control-Allow-Headers": "content-type", "Vary": "Origin" };
}
const json = (b: unknown, s: number, h: Record<string, string>) => new Response(JSON.stringify(b), { status: s, headers: { ...h, "Content-Type": "application/json" } });

async function sha256(s: string) {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return Array.from(new Uint8Array(d)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

Deno.serve(async (req) => {
  const origin = req.headers.get("origin");
  const h = cors(origin);
  if (req.method === "OPTIONS") return new Response("ok", { headers: h });
  if (req.method !== "POST") return json({ ok: false, error: "method" }, 405, h);
  if (origin && !ALLOWED.includes(origin)) return json({ ok: false, error: "origin" }, 403, h);

  const sb = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, { auth: { persistSession: false } });
  const unsubscribe = async (raw: unknown) => {
    const t = String(raw ?? "").trim().toLowerCase();
    if (!UUID_RE.test(t)) return json({ ok: false, error: "bad_token" }, 400, h);
    const { data, error } = await sb.rpc("coachbadge_unsubscribe", { p_token: t });
    if (error) return json({ ok: false, error: "failed" }, 500, h);
    return json({ ok: true, removed: data === true }, 200, h);
  };

  // One-click unsubscribe from a mailbox provider: token in the query string, body "List-Unsubscribe=One-Click".
  const q = new URL(req.url).searchParams.get("unsubscribe");
  if (q !== null) return await unsubscribe(q);

  let body: Record<string, unknown> = {};
  try {
    const ct = req.headers.get("content-type") || "";
    if (ct.includes("application/json")) body = await req.json();
    else body = Object.fromEntries((await req.formData()).entries());
  } catch { return json({ ok: false, error: "bad_request" }, 400, h); }

  if (body.action === "unsubscribe") return await unsubscribe(body.token);

  // Honeypot: people never fill the hidden cb_hp_note field. Pretend success, store nothing, send nothing.
  if (String(body.cb_hp_note ?? "").trim() !== "") return json({ ok: true }, 200, h);

  const email = String(body.email ?? "").trim().toLowerCase();
  if (email.length > 254 || !EMAIL_RE.test(email)) return json({ ok: false, error: "invalid_email" }, 400, h);

  // Rate limit per IP and clock hour. The IP is hashed together with the hour, so hashes cannot be linked across hours,
  // and rows older than two hours are deleted on every call.
  const ip = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim() || "unknown";
  const hour = new Date().toISOString().slice(0, 13);
  const ipHash = await sha256(`coachbadge:${hour}:${ip}`);
  await sb.from("coachbadge_signup_attempts").delete().lt("created_at", new Date(Date.now() - 2 * 3600_000).toISOString());
  const { count } = await sb.from("coachbadge_signup_attempts").select("id", { count: "exact", head: true }).eq("ip_hash", ipHash);
  if ((count ?? 0) >= MAX_PER_IP_PER_HOUR) return json({ ok: false, error: "rate_limited" }, 429, h);
  await sb.from("coachbadge_signup_attempts").insert({ ip_hash: ipHash });

  // The before-insert trigger lowercases the address and silently skips duplicates (no row comes back),
  // so the response never reveals whether an address was already on the list.
  const { data: rows, error } = await sb.from("coachbadge_subscribers").insert({ email }).select("id, token");
  if (error) return json({ ok: false, error: "store_failed" }, 500, h);
  const created = rows && rows.length ? rows[0] : null;

  if (created && WELCOME_ENABLED && SENDERS[MAIL_PROVIDER] && !TEST_DOMAIN_RE.test(email)) {
    let key = env("MAIL_API_KEY") || env("AGENTMAIL_API_KEY");
    if (!key) {
      try { const { data } = await sb.rpc("coachbadge_mail_config"); key = (Array.isArray(data) ? data[0]?.api_key : data?.api_key) || undefined; } catch { /* no key: row kept, no welcome */ }
    }
    const since = new Date(Date.now() - 3600_000).toISOString();
    const { count: sentLastHour } = await sb.from("coachbadge_subscribers").select("id", { count: "exact", head: true }).gte("welcomed_at", since);
    if (key && (sentLastHour ?? 0) < MAX_WELCOMES_PER_HOUR) {
      try {
        const r = await SENDERS[MAIL_PROVIDER](key, email, welcomeEmail(created.token, LINKS));
        if (r.ok) await sb.from("coachbadge_subscribers").update({ welcomed_at: new Date().toISOString() }).eq("id", created.id);
        else console.error("welcome send failed", r.status);
      } catch (err) { console.error("welcome send error", String(err)); }
    }
  }
  return json({ ok: true }, 200, h);
});
