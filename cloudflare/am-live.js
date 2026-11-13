// Adoração Mundial: which church is live on YouTube right now.
// Cloudflare Worker "am-live" at https://live.wwchurches.com/live.json
// Runs every minute (cron). Checks one church per run, round-robin, and keeps the result in KV (binding LIVE).
// Free-plan friendly: about 150 KV writes a day (on change, plus a heartbeat every 10 minutes).
// The website reads /live.json (CORS open) and shows the live service at the top of every page.
// Channel list comes from the site's own settings (locations[].youtube in index.html).
const SITE = "https://ksales373.github.io/adoracaomundial/";
const FALLBACK = { southriver: "@adoracaomundialsouthriver", newark: "@adoracaomundialnewark", longbranch: "@IgrejaAdoracaoMundial" };
const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36";

async function channels(env) {
  const cached = await env.LIVE.get("channels", "json");
  if (cached && Date.now() - cached.at < 6 * 3600e3) return cached.list;
  let list = FALLBACK;
  try {
    const html = await (await fetch(SITE, { redirect: "follow" })).text();
    const m = html.match(/id="site-config">([\s\S]*?)<\/script>/);
    if (m) {
      const cfg = JSON.parse(m[1]);
      const l = {};
      for (const loc of cfg.locations || []) if (loc.youtube) l[loc.id] = loc.youtube.trim();
      if (Object.keys(l).length) list = l;
    }
  } catch (e) {}
  await env.LIVE.put("channels", JSON.stringify({ at: Date.now(), list }));
  return list;
}

async function check(handle) {
  const url = handle.startsWith("http") ? handle.replace(/\/$/, "") + "/live" : "https://www.youtube.com/@" + handle.replace(/^@/, "") + "/live";
  const res = await fetch(url, { headers: { "User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8", "Cookie": "CONSENT=YES+cb; SOCS=CAI" } });
  if (!res.ok) return { error: res.status };
  const p = await res.text();
  // Look only inside the player data (ytInitialPlayerResponse), not the whole 1+ MB page.
  let base = p.indexOf("ytInitialPlayerResponse");
  if (base < 0) base = 0;
  let at = p.indexOf('"videoDetails":{', base), esc = false;
  if (at < 0) { at = p.indexOf('\\"videoDetails\\":{', base); esc = at >= 0; }
  if (at < 0) return null; // channel page: not live
  const norm = t => (esc ? t.split('\\"').join('"') : t);
  const det = norm(p.slice(at, at + 15000));
  const ps = p.indexOf("playabilityStatus", base);
  const head = ps >= 0 ? norm(p.slice(ps, ps + 6000)) : "";  // playabilityStatus
  const micro = norm(p.slice(at, at + 80000));        // microformat.liveBroadcastDetails
  const vid = (det.match(/"videoId":"([\w-]{11})"/) || [])[1];
  if (!vid) return null;
  const upcoming = det.includes('"isUpcoming":true');
  const ended = micro.includes('"endTimestamp"');
  const offline = head.includes("LIVE_STREAM_OFFLINE");
  const liveFlag = micro.includes('"isLiveNow":true') || det.includes('"isLive":true');
  if (upcoming || ended || offline || !liveFlag) return null;
  let title = "";
  try { const o = await (await fetch("https://www.youtube.com/oembed?format=json&url=https://www.youtube.com/watch?v=" + vid)).json(); if (o.title) title = o.title; } catch (e) {}
  const started = (micro.match(/"startTimestamp":"([^"]+)"/) || [])[1] || "";
  return { videoId: vid, title, started };
}

async function runOne(env, which) {
  const list = await channels(env);
  const ids = Object.keys(list);
  if (!ids.length) return;
  // round-robin by the clock (no KV write): each church is checked every ids.length minutes
  let i = which != null ? ids.indexOf(which) : Math.floor(Date.now() / 60000) % ids.length;
  if (i < 0) i = 0;
  const id = ids[i];
  const state = (await env.LIVE.get("state", "json")) || { live: {}, checked: {} };
  let r;
  try { r = await check(list[id]); } catch (e) { r = { error: String(e) }; }
  const before = JSON.stringify(state.live[id] || null);
  if (r && r.error) { state.checked[id] = { at: new Date().toISOString(), error: r.error }; }
  else { if (r) state.live[id] = r; else delete state.live[id]; state.checked[id] = { at: new Date().toISOString() }; }
  for (const k of Object.keys(state.live)) if (!ids.includes(k)) delete state.live[k];
  state.updated = new Date().toISOString();
  const changed = before !== JSON.stringify(state.live[id] || null);
  // keep KV writes low: write on change, otherwise at most every 10 minutes
  const last = Date.parse(state.saved || 0);
  if (changed || Date.now() - last > 10 * 60e3) { state.saved = state.updated; await env.LIVE.put("state", JSON.stringify(state)); }
  return { id, result: r, changed };
}

export default {
  async scheduled(event, env, ctx) { ctx.waitUntil(runOne(env)); },
  async fetch(request, env) {
    const url = new URL(request.url);
    const cors = { "Access-Control-Allow-Origin": "*", "Content-Type": "application/json; charset=utf-8", "Cache-Control": "public, max-age=30" };
    const nostore = { ...cors, "Cache-Control": "no-store" };
    if (url.searchParams.get("probe")) { // test any channel: ?probe=@handle
      let r; try { r = await check(url.searchParams.get("probe")); } catch (e) { r = { error: String(e) }; }
      return new Response(JSON.stringify(r), { headers: nostore });
    }
    if (url.searchParams.get("check")) { // run a check now: ?check=1 (next church) or ?check=newark
      const out = await runOne(env, url.searchParams.get("check") === "1" ? null : url.searchParams.get("check"));
      return new Response(JSON.stringify(out), { headers: nostore });
    }
    const st = (await env.LIVE.get("state", "json")) || { live: {} };
    // the site ignores data older than 45 min; the every-minute cron keeps "updated" fresh while anything is live
    return new Response(JSON.stringify({ updated: st.saved || st.updated || new Date(0).toISOString(), live: st.live || {}, checked: st.checked || {} }), { headers: cors });
  }
};
