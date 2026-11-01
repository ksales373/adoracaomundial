"""Checks each church's YouTube channel and writes live.json for the website.

The channel handles come from the site's own settings (locations[].youtube in index.html),
so changing a channel in the manager is enough. Runs on a schedule from GitHub Actions.
"""
import datetime, html, json, re, urllib.request

HEARTBEAT_MIN = 20  # while a church is live, refresh live.json at least this often


def site_config():
    page = open("index.html", encoding="utf-8").read()
    m = re.search(r'id="site-config">(.*?)</script>', page, re.S)
    return json.loads(m.group(1)) if m else {}


def check(handle):
    handle = handle.strip()
    if not handle:
        return None
    if handle.startswith("http"):
        url = handle.rstrip("/") + "/live"
    else:
        url = "https://www.youtube.com/" + ("@" + handle.lstrip("@")) + "/live"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Cookie": "CONSENT=YES+cb; SOCS=CAI",
    })
    try:
        page = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")
    except Exception as e:  # network hiccup: treat as unknown, keep going
        print("error", handle, e)
        return "error"
    vid = re.search(r'<link rel="canonical" href="https://www\.youtube\.com/watch\?v=([\w-]{11})"', page)
    if not vid or '"isLiveNow":true' not in page:
        return None
    title = re.search(r'<meta name="title" content="([^"]*)"', page)
    start = re.search(r'"startTimestamp":"([^"]+)"', page)
    return {"videoId": vid.group(1),
            "title": html.unescape(title.group(1)) if title else "",
            "started": start.group(1) if start else ""}


def main():
    cfg = site_config()
    try:
        old = json.load(open("live.json", encoding="utf-8"))
    except Exception:
        old = {"live": {}}
    live = {}
    for loc in cfg.get("locations", []):
        r = check(loc.get("youtube", ""))
        if r == "error":
            if loc["id"] in old.get("live", {}):
                live[loc["id"]] = old["live"][loc["id"]]
        elif r:
            live[loc["id"]] = r
    now = datetime.datetime.now(datetime.timezone.utc)
    last = old.get("updated", "")
    try:
        age = (now - datetime.datetime.fromisoformat(last.replace("Z", "+00:00"))).total_seconds() / 60
    except Exception:
        age = 1e9
    changed = live != old.get("live", {})
    if changed or (live and age >= HEARTBEAT_MIN):
        json.dump({"updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "live": live},
                  open("live.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("live.json updated:", live)
    else:
        print("no change:", live)


if __name__ == "__main__":
    main()
