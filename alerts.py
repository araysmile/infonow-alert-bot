#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Alert Wire Bot v2.0: Upgraded with smart filtering, paywall blocking, and curated feeds

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
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import feedparser
from dateutil import parser as dateparser

# --------- Configuration ---------

# Paywall domains to auto-skip
PAYWALL_DOMAINS = [
    "washingtonpost.com",
    "nytimes.com",
    "wsj.com",
    "ft.com",
    "economist.com",
    "bloomberg.com",
    "thetimes.co.uk",
    "telegraph.co.uk",
]

# Sports keywords to filter out (case-insensitive)
SPORTS_KEYWORDS = [
    "nfl", "nba", "mlb", "nhl", "fifa", "uefa", "premier league",
    "champions league", "world cup", "super bowl", "playoffs",
    "football", "basketball", "baseball", "hockey", "soccer",
    "espn", "sports", "game", "match", "score", "team wins",
    "quarterback", "touchdown", "goal", "championship"
]

# Boring/generic keywords to filter (unless high priority)
BORING_KEYWORDS = [
    "trade deal", "economic summit", "diplomatic visit",
    "bilateral talks", "policy speech", "routine meeting",
    "annual report", "quarterly earnings", "market update",
]

# High-priority keywords (for severity scoring)
HIGH_PRIORITY_KEYWORDS = [
    "zero-day", "critical vulnerability", "ransomware attack", "data breach",
    "arrested", "indicted", "sentenced", "convicted", "corruption",
    "earthquake", "tsunami", "hurricane", "tornado", "disaster",
    "emergency", "breaking", "major incident", "explosion", "shooting",
    "fraud", "scam", "hack", "exploit", "leaked", "exposed"
]

# FEEDS: Organized and curated
FEEDS = {
    # ============ BREAKING NEWS & INVESTIGATIVE ============
    "📰 Reuters US": "https://rsshub.app/reuters/us",
    "📰 AP News Top": "https://rsshub.app/apnews/topics/apf-topnews",
    
    # Investigative Journalism (NO HOLDS BARRED!)
    "🔍 ProPublica": "https://www.propublica.org/feeds/propublica/main",
    "🔍 ProPublica - Criminal Justice": "https://www.propublica.org/topics/criminal-justice.rss",
    "🔍 The Intercept": "https://theintercept.com/feed/?rss",
    "🔍 Bellingcat": "https://www.bellingcat.com/feed/",
    "🔍 MotherJones Investigations": "https://www.motherjones.com/politics/feed/",
    "🔍 Wired Security": "https://www.wired.com/feed/category/security/latest/rss",
    "🔍 Vice Motherboard": "https://www.vice.com/en/rss/topic/tech",
    "🔍 Rolling Stone Politics": "https://www.rollingstone.com/politics/feed/",
    "🔍 The Daily Beast": "https://www.thedailybeast.com/feed",
    
    # ============ CYBERSECURITY (Curated - Best Sources) ============
    "🔥 Krebs on Security": "https://krebsonsecurity.com/feed/",
    "🔥 BleepingComputer": "https://www.bleepingcomputer.com/feed/",
    "🔥 The Hacker News": "https://feeds.feedburner.com/TheHackersNews",
    "🔥 The Record": "https://therecord.media/feed",
    "🔥 Dark Reading": "https://www.darkreading.com/rss.xml",
    "🔥 Schneier on Security": "https://www.schneier.com/feed/atom/",
    
    # Breaches & Incidents
    "🧨 DataBreaches.net": "https://databreaches.net/feed/",
    "🧨 HIBP Latest": "https://feeds.feedburner.com/HaveIBeenPwnedLatestBreaches",
    "🧨 Ransomware.live": "https://www.ransomware.live/rss.xml",
    "🧨 Troy Hunt": "https://www.troyhunt.com/rss/",
    
    # Government & Critical Infrastructure
    "🛡️ CISA Advisories": "https://www.cisa.gov/cybersecurity-advisories/all.xml",
    "🛡️ CISA Current Activity": "https://www.cisa.gov/news-events/cybersecurity-advisories/current-activity.xml",
    "🛡️ US-CERT Alerts": "https://www.cisa.gov/news-events/alerts.xml",
    
    # Threat Intelligence (Top Tier Only)
    "⚡ Mandiant": "https://www.mandiant.com/resources/blog/rss.xml",
    "⚡ CrowdStrike": "https://www.crowdstrike.com/blog/feed/",
    "⚡ Microsoft Security": "https://www.microsoft.com/en-us/security/blog/feed/",
    
    # Vulnerabilities
    "🐛 Packet Storm": "https://packetstormsecurity.com/feeds/news/",
    "🐛 Exploit-DB": "https://www.exploit-db.com/rss.xml",
    
    # ============ AI / MACHINE LEARNING ============
    "🤖 OpenAI Blog": "https://openai.com/blog/rss.xml",
    "🤖 Anthropic News": "https://www.anthropic.com/news/rss.xml",
    "🤖 Google DeepMind": "https://deepmind.google/blog/rss.xml",
    "🤖 Meta AI": "https://ai.meta.com/blog/rss/",
    "🤖 Hugging Face": "https://huggingface.co/blog/feed.xml",
    "🤖 VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
    "🤖 TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "🤖 MIT Tech Review AI": "https://www.technologyreview.com/topic/artificial-intelligence/feed",
    "🤖 The Mirror Tech": "https://www.themirror.com/all-about/tech-news?service=rss",
    
    # ============ OPEN SOURCE & TOOLS ============
    "⭐ Product Hunt": "https://www.producthunt.com/feed",
    "⭐ Hacker News (Show HN)": "https://hnrss.org/show",
    "⭐ Privacy Guides": "https://www.privacyguides.org/blog/feed.xml",
    "⭐ AlternativeTo News": "https://alternativeto.net/news/feed/",
    "⭐ Self-Hosted": "https://selfhosted.libhunt.com/newsletter/feed",
    "⭐ OpenSSF Blog": "https://openssf.org/blog/feed/",
    
    # ============ ENTERTAINMENT & DRAMA (JUICY GOSSIP!) ============
    "🎤 The Shade Room": "https://theshaderoom.com/feed/",
    "🎤 Media Take Out": "https://mediatakeout.com/feed/",
    "🎤 WorldStarHipHop": "https://worldstarhiphop.com/videos/rss.php",
    "🎤 Hot 97": "https://hot97.com/feed/",
    "🎤 TMZ": "https://www.tmz.com/rss.xml",
    "🎤 Page Six": "https://pagesix.com/feed/",
    "🎤 The Mirror (Celebrity)": "https://www.themirror.com/all-about/celebrity-news?service=rss",
    "🎤 The Jasmine Brand": "https://thejasminebrand.com/feed/",
    "🎤 Bossip": "https://bossip.com/feed/",
    "🎤 The YBF": "https://www.theybf.com/feed",
    "🎤 Vibe Magazine": "https://www.vibe.com/feed/",
    "🎤 The Source": "https://thesource.com/feed/",
    "🎤 XXL Magazine": "https://www.xxlmag.com/feed/",
    "🎤 HipHopDX": "https://hiphopdx.com/feed",
    "🎤 Complex Music": "https://www.complex.com/music/rss",
    "🎤 AllHipHop": "https://allhiphop.com/feed/",
    "🎤 Rap-Up": "https://www.rap-up.com/feed/",
    "🎤 The Breakfast Club": "https://www.iheart.com/podcast/the-breakfast-club-24992238/rss/",
    "🎤 Perez Hilton": "https://perezhilton.com/feed/",
    "🎤 Daily Mail Celebrity": "https://www.dailymail.co.uk/tvshowbiz/index.rss",
    "🎤 Crazy Days and Nights": "https://www.crazydaysandnights.net/feeds/posts/default",
    "🎤 Dlisted": "https://dlisted.com/feed/",
    
    # ============ SOCIAL MEDIA DRAMA ============
    "📱 Pop Crave": "https://popcrave.com/feed/",
    "📱 The Neighborhood Talk": "https://theneighborhoodtalk.com/feed/",
    "📱 Hollywood Unlocked": "https://hollywoodunlocked.com/feed/",
    
    # ============ TRUE CRIME & LEGAL DRAMA ============
    "⚖️ Crime Online": "https://www.crimeonline.com/feed/",
    "⚖️ Law & Crime": "https://lawandcrime.com/feed/",
    "⚖️ Oxygen True Crime": "https://www.oxygen.com/feed",
    
    # ============ FINANCIAL CRIMES & WHITE COLLAR ============
    "💰 SEC Enforcement": "https://www.sec.gov/news/pressreleases.rss",
    "💰 DOJ Financial Fraud": "https://www.justice.gov/feeds/opa/topic/financial-fraud.xml",
    "💰 FBI Financial Fraud": "https://www.fbi.gov/feeds/fbi-in-the-news/fbi-in-the-news.xml",
    "💰 FTC Consumer Alerts": "https://www.consumer.ftc.gov/feeds/articles.xml",
    "💰 CFTC Press Releases": "https://www.cftc.gov/rss/PressReleases/rss.xml",
    "💰 IRS Criminal Investigation": "https://www.irs.gov/rss/irs-criminal-investigation-newsroom",
    "💰 OpenSecrets": "https://www.opensecrets.org/news/feed/",
    
    # ============ LAW ENFORCEMENT & CORRUPTION ============
    "🚔 DEA Press Releases": "https://www.dea.gov/rss/press-releases.xml",
    "🚔 DOJ Drug Enforcement": "https://www.justice.gov/feeds/opa/topic/drug-enforcement.xml",
    "🚔 FBI Press Releases": "https://www.fbi.gov/feeds/press-releases/press-releases.xml",
    "🚔 DOJ Public Integrity": "https://www.justice.gov/feeds/opa/topic/public-integrity.xml",
    "🚔 DOJ Organized Crime": "https://www.justice.gov/feeds/opa/topic/organized-crime.xml",
    "🚔 Courthouse News": "https://www.courthousenews.com/feed/",
    "🚔 The Appeal": "https://theappeal.org/feed/",
    
    # ============ CRYPTO (Only Major Scams/Hacks) ============
    "₿ Rekt News": "https://rekt.news/rss.xml",
    
    # ============ NATURAL DISASTERS ============
    "🌋 USGS Significant Earthquakes": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_hour.atom",
    "🌊 NOAA Tsunami Alerts": "https://www.tsunami.gov/events/xml/atom10.xml",
    "🌀 NHC Atlantic": "https://www.nhc.noaa.gov/nhc_at.xml",
    "🌀 NHC Eastern Pacific": "https://www.nhc.noaa.gov/nhc_ep.xml",
    "🌍 ReliefWeb Disasters": "https://reliefweb.int/rss.xml",
}

# NWS severe/extreme alerts (US)
NWS_URL = (
    "https://api.weather.gov/alerts/active"
    "?status=actual&message_type=Alert,Update&severity=Severe,Extreme"
)

USER_AGENT = "infonow-alert-bot/2.0 (+https://github.com)"

# Persistent storage for seen items (to avoid duplicates across runs)
SEEN_FILE = Path.home() / ".alert_bot_seen.json"

# --------- Utilities ---------

def log(*args):
    print("[alerts]", *args, flush=True)


def getenv_required(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


def load_seen_items() -> set:
    """Load previously seen item IDs from disk."""
    if not SEEN_FILE.exists():
        return set()
    try:
        with open(SEEN_FILE, 'r') as f:
            data = json.load(f)
            # Clean old items (older than 7 days)
            cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).timestamp()
            cleaned = {k: v for k, v in data.items() if v > cutoff}
            return set(cleaned.keys())
    except Exception as e:
        log(f"Error loading seen items: {e}")
        return set()


def save_seen_items(seen: set) -> None:
    """Save seen item IDs to disk with timestamps."""
    try:
        # Load existing data
        existing = {}
        if SEEN_FILE.exists():
            with open(SEEN_FILE, 'r') as f:
                existing = json.load(f)
        
        # Add new items with current timestamp
        now = datetime.now(timezone.utc).timestamp()
        for item_id in seen:
            if item_id not in existing:
                existing[item_id] = now
        
        # Clean old items (older than 7 days)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).timestamp()
        cleaned = {k: v for k, v in existing.items() if v > cutoff}
        
        # Save
        SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SEEN_FILE, 'w') as f:
            json.dump(cleaned, f)
    except Exception as e:
        log(f"Error saving seen items: {e}")


def is_paywall(url: str) -> bool:
    """Check if URL is from a known paywall site."""
    url_lower = url.lower()
    return any(domain in url_lower for domain in PAYWALL_DOMAINS)


def contains_sports(text: str) -> bool:
    """Check if text contains sports-related keywords."""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in SPORTS_KEYWORDS)


def is_boring(text: str, priority: int) -> bool:
    """Check if text is boring/generic (unless it's high priority)."""
    if priority >= 20:  # High priority overrides boring filter
        return False
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in BORING_KEYWORDS)


def calculate_priority(title: str, content: str = "") -> int:
    """Calculate priority score (higher = more important)."""
    text = (title + " " + content).lower()
    score = 0
    
    for keyword in HIGH_PRIORITY_KEYWORDS:
        if keyword in text:
            score += 10
    
    # Boost for certain source indicators
    if any(word in text for word in ["breaking", "urgent", "critical", "emergency"]):
        score += 20
    
    return score


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
            log("✓ Sent message")
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
        return age_minutes <= window_minutes
    except Exception as e:
        return False


def entry_id(entry) -> str:
    """Best-effort stable id for an RSS entry."""
    return (
        getattr(entry, "id", None)
        or getattr(entry, "guid", None)
        or getattr(entry, "link", None)
        or getattr(entry, "title", "")
    ) or ""


# --------- Sources ---------

def check_rss_sources(token: str, chat_id: str, window_minutes: int, debug: bool, seen: set) -> int:
    """Fetch all configured RSS/Atom feeds and post items. Returns count of sent messages."""
    total_sent = 0
    new_items = []  # Collect items with priority scores
    
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
                        msg = f"[DEBUG] {label}\n<b>{title}</b>\n📅 {published}\n<a href=\"{link}\">Read more</a>"
                        send_telegram(token, chat_id, msg)
                        total_sent += 1
                continue

            # Normal mode: filter and score items
            for e in entries:
                eid = entry_id(e)
                if eid in seen:
                    continue

                title = getattr(e, "title", "") or "New item"
                link = getattr(e, "link", "") or ""
                published = getattr(e, "published", "") or getattr(e, "updated", "") or ""
                summary = getattr(e, "summary", "") or ""
                
                if not link:
                    continue
                
                # Filter paywall sites
                if is_paywall(link):
                    log(f"  ⊗ Skipped (paywall): {title[:50]}")
                    continue
                
                # Filter sports
                if contains_sports(title + " " + summary):
                    log(f"  ⊗ Skipped (sports): {title[:50]}")
                    continue
                
                # Check if recent
                if not is_recent(published, window_minutes):
                    continue
                
                # Calculate priority
                priority = calculate_priority(title, summary)
                
                # Filter boring content (unless high priority)
                if is_boring(title + " " + summary, priority):
                    log(f"  ⊗ Skipped (boring): {title[:50]}")
                    continue
                
                # Add to new items
                seen.add(eid)
                new_items.append({
                    'label': label,
                    'title': title,
                    'link': link,
                    'priority': priority
                })

        except Exception as ex:
            log(f"  ERROR: {repr(ex)}")
    
    # Sort by priority (highest first) and send
    new_items.sort(key=lambda x: x['priority'], reverse=True)
    
    for item in new_items:
        priority_marker = "🔥 " if item['priority'] >= 20 else ""
        msg = f"{priority_marker}{item['label']}\n<b>{item['title']}</b>\n<a href=\"{item['link']}\">Read more</a>"
        send_telegram(token, chat_id, msg)
        total_sent += 1
    
    if new_items:
        log(f"Found {len(new_items)} recent items (after filtering)")
    
    return total_sent


def check_nws_severe(token: str, chat_id: str, window_minutes: int, debug: bool) -> int:
    """Fetch US severe/extreme weather alerts from NWS. Returns count of sent messages."""
    total_sent = 0
    try:
        log("Checking: ⚠️ NWS Severe Weather")
        r = requests.get(
            NWS_URL,
            headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json"},
            timeout=25,
        )
        if r.status_code != 200:
            log(f"  NWS non-200: {r.status_code}")
            return 0

        data = r.json()
        feats = data.get("features", []) if isinstance(data, dict) else []
        log(f"  Active severe/extreme alerts: {len(feats)}")

        if debug:
            for feat in feats[:2]:
                p = feat.get("properties", {}) if isinstance(feat, dict) else {}
                event = p.get("event", "NWS Alert")
                area = p.get("areaDesc", "")
                ts = p.get("sent") or p.get("effective") or "Unknown time"
                link = p.get("uri") or p.get("id") or "https://www.weather.gov/alerts"
                msg = f"[DEBUG] ⚠️ SEVERE WEATHER (US)\n<b>{event}</b>\n📍 {area[:140]}\n📅 {ts}\n<a href=\"{link}\">Details</a>"
                send_telegram(token, chat_id, msg, disable_preview=True)
                total_sent += 1
            return total_sent

        # Normal: only recent alerts
        for feat in feats:
            p = feat.get("properties", {}) if isinstance(feat, dict) else {}
            ts = p.get("sent") or p.get("effective") or p.get("onset") or ""
            if not is_recent(ts, window_minutes):
                continue
            
            event = p.get("event", "NWS Alert")
            area = p.get("areaDesc", "")
            link = p.get("uri") or p.get("id") or "https://www.weather.gov/alerts"
            msg = f"🔥 ⚠️ SEVERE WEATHER (US)\n<b>{event}</b>\n📍 {area[:140]}\n<a href=\"{link}\">Details</a>"
            send_telegram(token, chat_id, msg, disable_preview=True)
            total_sent += 1

    except Exception as e:
        log(f"  ERROR: {repr(e)}")
    
    return total_sent


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
        return 0

    try:
        window_minutes = int(os.environ.get("WINDOW_MINUTES", "30"))
    except Exception:
        window_minutes = 30

    log("=" * 60)
    log(f"Alert Bot v2.0 Starting")
    log(f"Window: {window_minutes} minutes | Debug: {args.debug}")
    log(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    log("=" * 60)

    # Load seen items
    seen = load_seen_items()
    log(f"Loaded {len(seen)} previously seen items")

    # Check all sources
    rss_sent = check_rss_sources(token, chat_id, window_minutes, args.debug, seen)
    nws_sent = check_nws_severe(token, chat_id, window_minutes, args.debug)
    
    total_sent = rss_sent + nws_sent

    # Save seen items
    if not args.debug:
        save_seen_items(seen)

    log("=" * 60)
    log(f"Run complete. Sent {total_sent} alerts.")
    log("=" * 60)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log("Fatal error:", repr(e))
        sys.exit(0)
