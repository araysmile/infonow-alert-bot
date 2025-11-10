#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Alert Wire bot: fetch selected cyber/disaster feeds and post new items to Telegram.

Env vars required:
  - TELEGRAM_TOKEN       (from @BotFather)
  - TELEGRAM_CHAT_ID     (numeric id, e.g. -100xxxxxxxxxx)
  - WINDOW_MINUTES       (optional; default 30)

CLI flags:
  --debug   -> send a couple of sample items from each source even if they're old
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime, timedelta, timezone

import requests
import feedparser
from dateutil import parser as dateparser

# --------- Configuration ---------

# FEEDS: label -> RSS/Atom URL
FEEDS = {
    # ============ CYBERSECURITY ============
    # Cyber Security News (Very Active)
    "🔥 The Hacker News": "https://feeds.feedburner.com/TheHackersNews",
    "🔥 BleepingComputer": "https://www.bleepingcomputer.com/feed/",
    "🔥 Krebs on Security": "https://krebsonsecurity.com/feed/",
    "🔥 Dark Reading": "https://www.darkreading.com/rss.xml",
    "🔥 SecurityWeek": "https://www.securityweek.com/feed/",
    "🔥 The Record": "https://therecord.media/feed",
    "🔥 Threatpost": "https://threatpost.com/feed/",
    "🔥 SecurityAffairs": "https://securityaffairs.com/feed",
    "🔥 Graham Cluley": "https://grahamcluley.com/feed/",
    "🔥 Schneier on Security": "https://www.schneier.com/feed/atom/",
    
    # Breaches & Incidents (Active)
    "🧨 DataBreaches.net": "https://databreaches.net/feed/",
    "🧨 UpGuard Breaches": "https://www.upguard.com/breaches/rss.xml",
    "🧨 HIBP Latest": "https://feeds.feedburner.com/HaveIBeenPwnedLatestBreaches",
    "🧨 Ransomware.live": "https://www.ransomware.live/rss.xml",
    "🧨 Troy Hunt": "https://www.troyhunt.com/rss/",
    
    # Government & Critical Infrastructure (Medium Activity)
    "🛡️ CISA Advisories": "https://www.cisa.gov/cybersecurity-advisories/all.xml",
    "🛡️ CISA Current Activity": "https://www.cisa.gov/news-events/cybersecurity-advisories/current-activity.xml",
    "🛡️ US-CERT Alerts": "https://www.cisa.gov/news-events/alerts.xml",
    "🛡️ ICS-CERT": "https://www.cisa.gov/news-events/ics-advisories.xml",
    
    # Threat Intelligence (Active)
    "⚡ Malwarebytes Labs": "https://www.malwarebytes.com/blog/feed/index.xml",
    "⚡ Talos Intelligence": "https://blog.talosintelligence.com/rss/",
    "⚡ Unit 42": "https://unit42.paloaltonetworks.com/feed/",
    "⚡ Mandiant": "https://www.mandiant.com/resources/blog/rss.xml",
    "⚡ CrowdStrike": "https://www.crowdstrike.com/blog/feed/",
    "⚡ Microsoft Security": "https://www.microsoft.com/en-us/security/blog/feed/",
    
    # Vulnerabilities (Very Active)
    "🐛 VulDB Recent": "https://vuldb.com/?rss.recent",
    "🐛 Packet Storm": "https://packetstormsecurity.com/feeds/news/",
    "🐛 Exploit-DB": "https://www.exploit-db.com/rss.xml",
    
    # Malware Analysis
    "🦠 Malware Traffic Analysis": "https://www.malware-traffic-analysis.net/blog-entries.rss",
    "🦠 ANY.RUN": "https://any.run/cybersecurity-blog/feed/",
    "🦠 Abuse.ch": "https://urlhaus.abuse.ch/rss/",
    
    # Internet Infrastructure
    "🌐 NetBlocks": "https://netblocks.org/feed",
    "🌐 Cloudflare Radar": "https://blog.cloudflare.com/rss/",
    "🌐 SANS ISC": "https://isc.sans.edu/rssfeed.xml",
    
    # Reddit Communities
    "💬 r/netsec": "https://www.reddit.com/r/netsec/.rss",
    "💬 r/cybersecurity": "https://www.reddit.com/r/cybersecurity/.rss",
    
    # ============ AI / MACHINE LEARNING ============
    "🤖 OpenAI Blog": "https://openai.com/blog/rss.xml",
    "🤖 Anthropic News": "https://www.anthropic.com/news/rss.xml",
    "🤖 Google DeepMind": "https://deepmind.google/blog/rss.xml",
    "🤖 Meta AI": "https://ai.meta.com/blog/rss/",
    "🤖 Hugging Face": "https://huggingface.co/blog/feed.xml",
    "🤖 Stability AI": "https://stability.ai/blog/rss.xml",
    "🤖 VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
    "🤖 TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "🤖 MIT Tech Review AI": "https://www.technologyreview.com/topic/artificial-intelligence/feed",
    "🤖 The Batch (DeepLearning.AI)": "https://www.deeplearning.ai/the-batch/feed/",
    
    # ============ OPEN SOURCE ============
    "⭐ GitHub Trending": "https://mshibanami.github.io/GitHubTrendingRSS/daily/all.xml",
    "⭐ GitHub Python": "https://mshibanami.github.io/GitHubTrendingRSS/daily/python.xml",
    "⭐ GitHub Java": "https://mshibanami.github.io/GitHubTrendingRSS/daily/java.xml",
    "⭐ Linux Kernel": "https://www.kernel.org/feeds/kdist.xml",
    "⭐ Python Insider": "https://blog.python.org/feeds/posts/default",
    "⭐ OpenSSF Blog": "https://openssf.org/blog/feed/",
    "⭐ The Linux Foundation": "https://www.linuxfoundation.org/feed",
    
    # ============ HARDWARE HACKING ============
    "🔧 Hackaday": "https://hackaday.com/feed/",
    "🔧 Raspberry Pi Blog": "https://www.raspberrypi.com/news/feed/",
    "🔧 Arduino Blog": "https://blog.arduino.cc/feed/",
    "🔧 Adafruit Blog": "https://blog.adafruit.com/feed/",
    "🔧 SparkFun News": "https://www.sparkfun.com/feeds/news",
    "🔧 CNX Software": "https://www.cnx-software.com/feed/",
    "🔧 Hackster.io": "https://www.hackster.io/blog.rss",
    
    # ============ CRYPTO SECURITY ============
    "₿ Rekt News": "https://rekt.news/rss.xml",
    "₿ CertiK Alerts": "https://www.certik.com/resources/blog/rss.xml",
    "₿ SlowMist": "https://slowmist.medium.com/feed",
    "₿ Blockchain Graveyard": "https://magoo.github.io/Blockchain-Graveyard/feed.xml",
    "₿ Coindesk Security": "https://www.coindesk.com/arc/outboundfeeds/rss/category/tech/security/",
    "₿ The Block Security": "https://www.theblock.co/rss.xml",
    
    # ============ FINANCIAL CRIMES ============
    "💰 SEC Enforcement": "https://www.sec.gov/news/pressreleases.rss",
    "💰 DOJ Financial Crimes": "https://www.justice.gov/feeds/opa/financial-fraud.xml",
    "💰 FBI White Collar": "https://www.fbi.gov/feeds/fbi-in-the-news/fbi-in-the-news.xml",
    "💰 FTC Consumer Alerts": "https://www.consumer.ftc.gov/feeds/articles.xml",
    "💰 CFTC Press Releases": "https://www.cftc.gov/rss/PressReleases/rss.xml",
    
    # ============ NATURAL DISASTERS ============
    "🌋 USGS Significant Earthquakes": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_hour.atom",
    "🌊 NOAA Tsunami Alerts": "https://www.tsunami.gov/events/xml/atom10.xml",
    "🌀 NHC Atlantic Advisories": "https://www.nhc.noaa.gov/nhc_at.xml",
    "🌀 NHC Eastern Pacific Advisories": "https://www.nhc.noaa.gov/nhc_ep.xml",
}

# NWS severe/extreme alerts (US)
NWS_URL = (
    "https://api.weather.gov/alerts/active"
    "?status=actual&message_type=Alert,Update&severity=Severe,Extreme"
)

USER_AGENT = "infonow-alert-bot/1.0 (+https://github.com)"

# --------- Utilities ---------

def log(*args):
    print("[alerts]", *args, flush=True)


def getenv_required(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


def send_telegram(token: str, chat_id: str, html_text: str, disable_preview: bool = False) -> None:
    """Fire-and-forget Telegram message; log errors but don't raise."""
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": html_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true" if disable_preview else "false",
        }
        r = requests.post(url, data=data, timeout=20)
        if r.status_code != 200:
            log("Telegram non-200:", r.status_code, r.text[:300])
        else:
            log("✓ Sent message successfully")
    except Exception as e:
        log("Telegram error:", repr(e))


def is_recent(dt_str: str, window_minutes: int) -> bool:
    """Return True if dt_str is within the last window_minutes; lenient parsing."""
    if not dt_str:
        return False
    try:
        dt = dateparser.parse(dt_str)
        if not dt:
            return False
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        age_minutes = (now - dt).total_seconds() / 60
        is_new = age_minutes <= window_minutes
        if is_new:
            log(f"  → Item age: {age_minutes:.1f} min (RECENT)")
        return is_new
    except Exception as e:
        log(f"  → Date parse error: {repr(e)}")
        return False


def entry_id(entry) -> str:
    """Best-effort stable id for an RSS entry (used for de-duping within a run)."""
    return (
        getattr(entry, "id", None)
        or getattr(entry, "guid", None)
        or getattr(entry, "link", None)
        or getattr(entry, "title", "")
    ) or ""


# --------- Sources ---------

def check_rss_sources(token: str, chat_id: str, window_minutes: int, debug: bool) -> None:
    """Fetch all configured RSS/Atom feeds and post items."""
    seen = set()
    total_sent = 0
    
    for label, url in FEEDS.items():
        try:
            log(f"Checking: {label}")
            d = feedparser.parse(url)
            entries = d.entries or []
            log(f"  Fetched {len(entries)} items")

            if debug:
                # Send up to 2 sample items, even if old.
                for e in entries[:2]:
                    link = getattr(e, "link", "") or ""
                    title = getattr(e, "title", "") or "New item"
                    published = getattr(e, "published", "") or getattr(e, "updated", "") or "No date"
                    if link:
                        msg = f"[DEBUG SAMPLE] {label}\n<b>{title}</b>\n📅 {published}\n<a href=\"{link}\">Read more</a>"
                        send_telegram(token, chat_id, msg)
                        total_sent += 1
                continue

            # Normal mode: only items within window, de-dup by id within this run.
            recent_count = 0
            for e in entries:
                eid = entry_id(e)
                if eid in seen:
                    continue
                seen.add(eid)

                published = getattr(e, "published", "") or getattr(e, "updated", "") or ""
                if not is_recent(published, window_minutes):
                    continue

                recent_count += 1
                title = getattr(e, "title", "") or "New item"
                link = getattr(e, "link", "") or ""
                if not link:
                    continue

                msg = f"{label}\n<b>{title}</b>\n<a href=\"{link}\">Read more</a>"
                send_telegram(token, chat_id, msg)
                total_sent += 1
            
            if recent_count > 0:
                log(f"  Found {recent_count} recent items")

        except Exception as ex:
            log(f"  ERROR: {repr(ex)}")
    
    log(f"RSS check complete. Sent {total_sent} alerts.")


def check_nws_severe(token: str, chat_id: str, window_minutes: int, debug: bool) -> None:
    """Fetch US severe/extreme weather alerts from NWS."""
    try:
        log("Checking: ⚠️ NWS Severe Weather")
        r = requests.get(
            NWS_URL,
            headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json"},
            timeout=25,
        )
        if r.status_code != 200:
            log(f"  NWS non-200: {r.status_code}")
            return

        data = r.json()
        feats = data.get("features", []) if isinstance(data, dict) else []
        log(f"  Active severe/extreme alerts: {len(feats)}")

        # Debug: send up to 2 samples (if any exist)
        if debug:
            for feat in feats[:2]:
                p = feat.get("properties", {}) if isinstance(feat, dict) else {}
                event = p.get("event", "NWS Alert")
                area = p.get("areaDesc", "")
                ts = p.get("sent") or p.get("effective") or "Unknown time"
                link = p.get("uri") or p.get("id") or "https://www.weather.gov/alerts"
                msg = f"[DEBUG SAMPLE] ⚠️ SEVERE WEATHER (US)\n<b>{event}</b>\n📍 {area[:140]}\n📅 {ts}\n<a href=\"{link}\">Details</a>"
                send_telegram(token, chat_id, msg, disable_preview=True)
            return

        # Normal: only alerts whose timestamps are within window
        recent_count = 0
        for feat in feats:
            p = feat.get("properties", {}) if isinstance(feat, dict) else {}
            ts = p.get("sent") or p.get("effective") or p.get("onset") or ""
            if not is_recent(ts, window_minutes):
                continue
            
            recent_count += 1
            event = p.get("event", "NWS Alert")
            area = p.get("areaDesc", "")
            link = p.get("uri") or p.get("id") or "https://www.weather.gov/alerts"
            msg = f"⚠️ SEVERE WEATHER (US)\n<b>{event}</b>\n📍 {area[:140]}\n<a href=\"{link}\">Details</a>"
            send_telegram(token, chat_id, msg, disable_preview=True)
        
        if recent_count > 0:
            log(f"  Found {recent_count} recent alerts")

    except Exception as e:
        log(f"  ERROR: {repr(e)}")


# --------- Main ---------

def parse_args():
    ap = argparse.ArgumentParser(description="Send alerts to Telegram.")
    ap.add_argument(
        "--debug",
        action="store_true",
        help="Send a couple of sample items per source even if they are old.",
    )
    return ap.parse_args()


def main():
    args = parse_args()

    try:
        token = getenv_required("TELEGRAM_TOKEN")
        chat_id = getenv_required("TELEGRAM_CHAT_ID")
    except Exception as e:
        log("Missing envs:", repr(e))
        # Exit 0 to avoid failing the workflow; but nothing else to do.
        return 0

    try:
        window_minutes = int(os.environ.get("WINDOW_MINUTES", "30"))
    except Exception:
        window_minutes = 30

    log("=" * 60)
    log(f"Alert Bot Starting")
    log(f"Window: {window_minutes} minutes | Debug: {args.debug}")
    log(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    log("=" * 60)

    # RSS / Atom sources
    check_rss_sources(token, chat_id, window_minutes, args.debug)

    # US severe/extreme weather
    check_nws_severe(token, chat_id, window_minutes, args.debug)

    log("=" * 60)
    log("Run complete.")
    log("=" * 60)
    return 0


if __name__ == "__main__":
    # Never crash the workflow: log any top-level error and exit 0.
    try:
        sys.exit(main())
    except Exception as e:
        log("Fatal error:", repr(e))
        sys.exit(0)
