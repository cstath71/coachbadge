import { createClient } from "npm:@supabase/supabase-js@2";

// Cookie-free page-view counter for coachbadge.com (same design as fut-hit / sbi-hit).
// Stores daily totals only: page path, referrer domain, utm_ tags, day (Zurich). It never reads or stores the IP address,
// user agent, cookies or any identifier. Requests with Do Not Track (DNT: 1) or Global Privacy Control (Sec-GPC: 1) are not counted.
// Deployed with verify_jwt = false (public beacon); the database write uses the service role inside the function only.
const SITE_ORIGINS = ["https://coachbadge.com", "https://www.coachbadge.com"];
const SELF = /(^|\.)coachbadge\.com$/i;
const PATH_RE = /^\/[A-Za-z0-9\/._-]{0,199}$/;
const TAG_RE = /^[a-z0-9._-]{1,64}$/;
const BOT_RE = /bot|crawl|spider|slurp|headless|preview|lighthouse|monitor/i;

const noContent = () => new Response(null, { status: 204, headers: { "Access-Control-Allow-Origin": "*" } });
const tag = (v: unknown) => { const s = String(v ?? "").trim().toLowerCase(); return TAG_RE.test(s) ? s : ""; };
function refDomain(v: unknown): string {
  try {
    const h = new URL(String(v ?? "")).hostname.toLowerCase().replace(/^www\./, "");
    if (!h) return "";
    return SELF.test(h) ? "(internal)" : h.slice(0, 100);
  } catch { return ""; }
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "POST", "Access-Control-Allow-Headers": "content-type" } });
  if (req.method !== "POST") return new Response(null, { status: 405 });
  // Count only real visits to the live site, and honour Do Not Track / Global Privacy Control.
  if (!SITE_ORIGINS.includes(req.headers.get("origin") || "")) return noContent();
  if (req.headers.get("dnt") === "1" || req.headers.get("sec-gpc") === "1") return noContent();
  if (BOT_RE.test(req.headers.get("user-agent") || "")) return noContent();  // checked, never stored
  let b: Record<string, unknown> = {};
  try { b = JSON.parse((await req.text()).slice(0, 2000)); } catch { return noContent(); }
  const path = String(b.p ?? "");
  if (!PATH_RE.test(path)) return noContent();
  const sb = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, { auth: { persistSession: false } });
  await sb.rpc("coachbadge_count_view", { p_path: path, p_ref: refDomain(b.r), p_us: tag(b.us), p_um: tag(b.um), p_uc: tag(b.uc) });
  return noContent();
});
