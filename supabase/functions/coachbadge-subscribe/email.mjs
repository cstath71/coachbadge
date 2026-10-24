// Welcome email for CoachBadge. Plain JavaScript (no imports) so the Edge Function (Deno) and the tests (Node) share it.
// Copy rules: football only; never "official" or "mandatory"; logo and wordmark on the LEFT; plain text alongside HTML.

// Defaults only. The Edge Function overrides them from its secrets (SITE_URL, MAIL_FROM), so moving to coachbadge.com and
// hello@coachbadge.com is a settings change.
export const SITE = "https://coachbadge.com/";
export const FUNCTION_URL = "https://uufmlmwgvoqhhtqgrclu.supabase.co/functions/v1/coachbadge-subscribe";
export const FROM_ADDRESS = "hello@coachbadge.com";
export const FROM_NAME = "CoachBadge";
export const REPLY_TO = "hello@coachbadge.com";
export const DISCLAIMER = "Independent; not affiliated with UEFA or any association listed.";

const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

export function unsubscribeUrl(token, site = SITE) {
  return `${site}unsubscribe.html?t=${encodeURIComponent(token)}`;
}

// RFC 8058 one-click: mail providers POST "List-Unsubscribe=One-Click" to this URL; the token is in the query string.
export function listUnsubscribeHeaders(token, functionUrl = FUNCTION_URL) {
  return {
    "List-Unsubscribe": `<${functionUrl}?unsubscribe=${encodeURIComponent(token)}>`,
    "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
  };
}

// Same header as the weekly issue (templates/newsletter.html): logo and wordmark on the left.
export function headerHtml(SITE) {
  return `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0b1f33"><tr>` +
    `<td align="left" style="padding:14px 20px;text-align:left"><a href="${SITE}" style="color:#ffffff;text-decoration:none;font:700 20px Arial,Helvetica,sans-serif">` +
    `<img src="${SITE}email-logo.png" width="28" height="28" alt="" style="vertical-align:middle;border:0;margin-right:8px">` +
    `<span style="vertical-align:middle">Coach<span style="color:#c6f432">Badge</span></span></a></td></tr></table>`;
}

export function welcomeEmail(token, { site = SITE, functionUrl = FUNCTION_URL } = {}) {
  const SITE = site;
  const unsub = unsubscribeUrl(token, site);
  const subject = "Welcome to CoachBadge";
  const text = [
    "CoachBadge",
    "",
    "Thanks for signing up.",
    "",
    "What you will get: one short email a week with newly opened football coaching courses and deadlines coming up, each with a link to the provider's own page.",
    "",
    `Browse every open course now: ${SITE}`,
    "",
    "--",
    `You get this because this address was entered in the sign-up form on ${SITE}`,
    `Unsubscribe in one click: ${unsub}`,
    DISCLAIMER,
  ].join("\n");
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(subject)}</title></head>` +
    `<body style="margin:0;padding:0;background:#f4f6f8"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="left" style="padding:16px">` +
    `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border-radius:6px;overflow:hidden">` +
    `<tr><td>${headerHtml(SITE)}</td></tr>` +
    `<tr><td style="padding:20px;font:16px/1.5 Arial,Helvetica,sans-serif;color:#0b1f33;text-align:left">` +
    `<p style="margin:0 0 12px"><strong>Thanks for signing up.</strong></p>` +
    `<p style="margin:0 0 12px">What you will get: one short email a week with newly opened football coaching courses and deadlines coming up, each with a link to the provider's own page.</p>` +
    `<p style="margin:0 0 4px"><a href="${SITE}" style="color:#0b5cad">Browse every open course now</a></p>` +
    `</td></tr><tr><td style="padding:16px 20px;border-top:1px solid #e3e8ee;font:12px/1.5 Arial,Helvetica,sans-serif;color:#5b6b78;text-align:left">` +
    `<p style="margin:0 0 6px">You get this because this address was entered in the sign-up form on <a href="${SITE}" style="color:#5b6b78">CoachBadge</a>.</p>` +
    `<p style="margin:0 0 6px"><a href="${esc(unsub)}" style="color:#5b6b78">Unsubscribe in one click</a></p>` +
    `<p style="margin:0">${esc(DISCLAIMER)}</p></td></tr></table></td></tr></table></body></html>`;
  return { subject, text, html, headers: listUnsubscribeHeaders(token, functionUrl) };
}
