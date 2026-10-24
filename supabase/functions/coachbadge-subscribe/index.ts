import { createClient } from "npm:@supabase/supabase-js@2";
import { FROM_ADDRESS, FROM_NAME, FUNCTION_URL, REPLY_TO, SITE, welcomeEmail } from "./email.mjs";

// CoachBadge newsletter endpoint (deploy with verify_jwt = false: browsers and mailbox providers call it without a key).
//   POST {email, cb_hp_note}                     sign up; a new address gets one welcome email
//   POST {action: "unsubscribe", token}          from unsubscribe.html (the link in every email)
//   POST ?unsubscribe=<token>                    RFC 8058 one-click (List-Unsubscribe-Post) from mailbox providers
// Settings (Supabase function secrets; nothing secret is in this file or in the site):
//   WELCOME_ENABLED   "true" / "false" forces the welcome email on / off. Unset: the Vault switch coachbadge_welcome_enabled
//                     (read through public.coachbadge_mail_config()) decides; if that cannot be read, no email is sent.
//   MAIL_PROVIDER     "resend" (default) or "agentmail"
//   MAIL_FROM         sender, "CoachBadge <hello@coachbadge.com>" (default) or a bare address
//   MAIL_REPLY_TO     reply-to address (default hello@coachbadge.com)
//   MAIL_API_BASE     default https://api.resend.com (resend) / https://api.agentmail.to/v0 (agentmail)
//   MAIL_API_KEY      provider API key; if unset, RESEND_API_KEY / AGENTMAIL_API_KEY, then the Vault secret read by public.coachbadge_mail_config()
//   SITE_URL / PUBLIC_FUNCTION_URL   links in the email (defaults: the GitHub Pages site and this function)
const env = (k: string) => (Deno.env.get(k) || "").trim();
const WELCOME_ENV = env("WELCOME_ENABLED");  // "true" | "false" | "" (unset: use the Vault switch)
const MAIL_PROVIDER = env("MAIL_PROVIDER") || "resend";
const MAIL_FROM = env("MAIL_FROM") || `${FROM_NAME} <${FROM_ADDRESS}>`;
const MAIL_FROM_ADDRESS = (MAIL_FROM.match(/<([^>]+)>/) || [, MAIL_FROM])[1].trim();  // bare address (AgentMail inbox id)
const MAIL_REPLY_TO = env("MAIL_REPLY_TO") || REPLY_TO;
const DEFAULT_API_BASE: Record<string, string> = { resend: "https://api.resend.com", agentmail: "https://api.agentmail.to/v0" };
const MAIL_API_BASE = (env("MAIL_API_BASE") || DEFAULT_API_BASE[MAIL_PROVIDER] || "").replace(/\/+$/, "");
const LINKS = { site: env("SITE_URL") || SITE, functionUrl: env("PUBLIC_FUNCTION_URL") || FUNCTION_URL };

const envKey = () => env("MAIL_API_KEY") || (MAIL_PROVIDER === "resend" ? env("RESEND_API_KEY") : env("AGENTMAIL_API_KEY"));

type Msg = { subject: string; text: string; html: string; headers: Record<string, string> };
// One function per provider, same shape. Resend carries the List-Unsubscribe headers as custom headers.
const SENDERS: Record<string, (key: string, to: string, m: Msg) => Promise<Response>> = {
  resend: (key, to, m) => fetch(`${MAIL_API_BASE}/emails`, {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify({ from: MAIL_FROM, to: [to], reply_to: MAIL_REPLY_TO, subject: m.subject, text: m.text, html: m.html,
      headers: m.headers, tags: [{ name: "type", value: "coachbadge-welcome" }] }),
  }),
  agentmail: (key, to, m) => fetch(`${MAIL_API_BASE}/inboxes/${encodeURIComponent(MAIL_FROM_ADDRESS)}/messages/send`, {
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

  // Mail settings from Vault (API key, welcome switch), read per request so the switch works without a redeploy.
  let cfg: { api_key?: string; welcome_enabled?: boolean } = {};
  if (created && (WELCOME_ENV === "" || !envKey())) {
    try { const { data } = await sb.rpc("coachbadge_mail_config"); cfg = (Array.isArray(data) ? data[0] : data) || {}; } catch { /* unreadable: no welcome */ }
  }
  const WELCOME_ENABLED = WELCOME_ENV === "true" || (WELCOME_ENV === "" && cfg.welcome_enabled === true);
  if (created && WELCOME_ENABLED && SENDERS[MAIL_PROVIDER] && !TEST_DOMAIN_RE.test(email)) {
    const key = envKey() || cfg.api_key || undefined;
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
