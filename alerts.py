FEEDS = {
    "🧨 DataBreaches.net": "https://databreaches.net/feed/",
    "🧨 UpGuard Breaches": "https://www.upguard.com/breaches/rss.xml",
    "🧨 HIBP Latest": "https://feeds.feedburner.com/HaveIBeenPwnedLatestBreaches",
    "🌐 NetBlocks (Internet Disruptions)": "https://netblocks.org/feed",

    # Highly active add-ons:
    "🌋 USGS Significant Earthquakes": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_hour.atom",
    "🌊 NOAA Tsunami Alerts": "https://www.tsunami.gov/events/xml/atom10.xml",
    "🌀 NHC Atlantic Advisories": "https://www.nhc.noaa.gov/nhc_at.xml",
    "🌀 NHC Eastern Pacific Advisories": "https://www.nhc.noaa.gov/nhc_ep.xml",
    "🛡️ CISA Current Activity": "https://www.cisa.gov/cybersecurity-advisories/all.xml",
}        log("Telegram error:", repr(e))

def is_recent(dt_str, window_minutes):
    if not dt_str:
        return False
    try:
        dt = dateparser.parse(dt_str)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return now - dt <= timedelta(minutes=window_minutes)
    except Exception:
        return False

def check_rss():
    for label, url in FEEDS.items():
        try:
            d = feedparser.parse(url)
            entries = d.entries[:20]
            log(f"RSS {label}: got {len(entries)} items")
            if DEBUG:
                # Send 1-2 sample items even if old
                for e in entries[:2]:
                    title = e.get("title","New item")
                    link  = e.get("link","")
                    if link:
                        send_tg(f"[DEBUG SAMPLE] {label}\n<a href=\"{link}\">{title}</a>")
                continue

            # Normal mode: only recent items
            for e in entries:
                published = e.get("published") or e.get("updated") or ""
                if not is_recent(published, WINDOW_MINUTES):
                    continue
                title = e.get("title","New item")
                link  = e.get("link","")
                if link:
                    send_tg(f"{label}\n<a href=\"{link}\">{title}</a>")
        except Exception as ex:
            log("RSS error:", label, url, repr(ex))

def check_nws():
    try:
        r = requests.get(NWS_URL, headers={"User-Agent":"infonow-bot/1.0"}, timeout=25)
        if r.status_code != 200:
            log("NWS non-200:", r.status_code, r.text[:200])
            return
        data = r.json()
        feats = data.get("features", [])
        log(f"NWS: got {len(feats)} active severe/extreme alerts")
        if DEBUG:
            # Send up to 2 sample alerts
            for feat in feats[:2]:
                p = feat.get("properties", {})
                event = p.get("event","NWS Alert")
                area  = p.get("areaDesc","")
                link  = p.get("uri") or p.get("id") or "https://www.weather.gov/alerts"
                send_tg(f"[DEBUG SAMPLE] ⚠️ SEVERE WEATHER (US)\n<b>{event}</b> — {area[:140]}\n<a href=\"{link}\">Details</a>", True)
            return

        # Normal mode: recent only
        for feat in feats:
            p = feat.get("properties", {})
            ts = p.get("sent") or p.get("effective") or p.get("onset") or ""
            if not is_recent(ts, WINDOW_MINUTES):
                continue
            event = p.get("event","NWS Alert")
            area  = p.get("areaDesc","")
            link  = p.get("uri") or p.get("id") or "https://www.weather.gov/alerts"
            send_tg(f"⚠️ SEVERE WEATHER (US)\n<b>{event}</b> — {area[:140]}\n<a href=\"{link}\">Details</a>", True)
    except Exception as e:
        log("NWS error:", repr(e))

def main():
    log("Starting run. Window(min)=", WINDOW_MINUTES, "DEBUG=", DEBUG)
    check_rss()
    check_nws()
    log("Run complete.")

if __name__ == "__main__":
    main()
