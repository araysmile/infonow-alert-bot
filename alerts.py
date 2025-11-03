#!/usr/bin/env python3
import os, sys, requests, feedparser
from datetime import datetime, timedelta, timezone
from dateutil import parser as dateparser

TOKEN   = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
WINDOW_MINUTES = int(os.environ.get("WINDOW_MINUTES", "10"))

FEEDS = {
    "🧨 DataBreaches.net": "https://databreaches.net/feed/",
    "🧨 UpGuard Breaches": "https://www.upguard.com/breaches/rss.xml",
    "🧨 HIBP Latest": "https://feeds.feedburner.com/HaveIBeenPwnedLatestBreaches",
    "🌐 NetBlocks (Internet Disruptions)": "https://netblocks.org/feed",
}

NWS_URL = ("https://api.weather.gov/alerts/active"
           "?status=actual&message_type=Alert,Update&severity=Severe,Extreme")

def log(*a):
    print("[alerts]", *a, flush=True)

def send_tg(html_text, disable_preview=False):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {
            "chat_id": CHAT_ID,
            "text": html_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true" if disable_preview else "false",
        }
        r = requests.post(url, data=data, timeout=20)
        if r.status_code != 200:
            log("Telegram non-200:", r.status_code, r.text[:200])
    except Exception as e:
        log("Telegram error:", repr(e))

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
            for e in d.entries[:20]:
                published = e.get("published") or e.get("updated") or ""
                if not is_recent(published, WINDOW_MINUTES):
                    continue
                title = e.get("title", "New item")
                link  = e.get("link", "")
                if not link:
                    continue
                msg = f"{label}\n<a href=\"{link}\">{title}</a>"
                send_tg(msg)
        except Exception as ex:
            log("RSS error:", label, url, repr(ex))

def check_nws():
    try:
        r = requests.get(NWS_URL, headers={"User-Agent":"infonow-bot/1.0"}, timeout=25)
        if r.status_code != 200:
            log("NWS non-200:", r.status_code, r.text[:200])
            return
        data = r.json()
        for feat in data.get("features", []):
            p = feat.get("properties", {})
            ts = p.get("sent") or p.get("effective") or p.get("onset") or ""
            if not is_recent(ts, WINDOW_MINUTES):
                continue
            event = p.get("event", "NWS Alert")
            area  = p.get("areaDesc", "")
            link  = p.get("uri") or p.get("id") or "https://www.weather.gov/alerts"
            msg = f"⚠️ SEVERE WEATHER (US)\n<b>{event}</b> — {area[:140]}\n<a href=\"{link}\">Details</a>"
            send_tg(msg, disable_preview=True)
    except Exception as e:
        log("NWS error:", repr(e))

def main():
    log("Starting run. Window(minutes)=", WINDOW_MINUTES)
    check_rss()
    check_nws()
    log("Run complete.")

if __name__ == "__main__":
    try:
        main()
        sys.exit(0)
    except Exception as e:
        log("Fatal error:", repr(e))
        sys.exit(0)
