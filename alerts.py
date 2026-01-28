#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Alert Wire Bot v2.1 - Baltimore Edition
Real-time alerts for: Black culture, hip-hop, ALL tech/AI launches, cybersecurity

Env vars required:
  - TELEGRAM_TOKEN
  - TELEGRAM_CHAT_ID
  - WINDOW_MINUTES (default: 45)
"""

import os, sys, json, argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests, feedparser
from dateutil import parser as dateparser

# ========== FILTERS ==========

PAYWALL_DOMAINS = [
    "washingtonpost.com", "nytimes.com", "wsj.com", "ft.com",
    "economist.com", "bloomberg.com", "thetimes.co.uk", "telegraph.co.uk",
]

SPORTS_KEYWORDS = [
    "nfl game", "nba game", "mlb game", "nhl game", "uefa match",
    "premier league score", "final score", "game recap", "playoff bracket"
]

# TRASH - Skip this garbage immediately
TRASH_KEYWORDS = [
    "gay pride march", "pride parade budapest", "hungarian politics",
    "brexit deal", "eu summit", "g7 meeting", "bilateral talks",
    "baby bump", "pregnancy announcement", "gender reveal",
    "new puppy", "adopted dog", "rescue cat", "fur baby",
    "holding hands", "date night", "romantic stroll",
    "goes shirtless", "shows off abs", "beach body",
    "weight loss journey", "hair transformation",
    "spotted shopping", "runs errands", "grabs coffee",
    "love island uk", "towie", "molly mae", "katie price",
]

# JUICE - Always keep (overrides trash)
JUICE_KEYWORDS = [
    # Black culture
    "black twitter", "black tiktok", "black community", "african american",
    "baltimore", "bmore", "dmv", "charm city",
    
    # Music
    "hip hop", "hip-hop", "rap", "trap", "drill", "r&b", "rnb",
    
    # Drama/viral
    "viral", "trending", "breaking internet", "beef", "diss track",
    "shots fired", "responds to", "claps back", "calls out", "drama",
    "feud", "fight", "receipts", "exposed", "tea",
    
    # Getting dragged
    "dragged", "roasted", "clowned", "backlash", "cancelled",
    "ratio", "getting ratio'd",
    
    # Scandals/crime
    "arrested", "charges", "lawsuit", "indicted", "mugshot",
    "leaked", "scandal", "investigation", "sentenced",
    "cheating", "affair", "caught", "side chick", "baby mama",
    
    # Music releases
    "new album", "drops album", "new single", "tour announcement",
    "collab", "featuring", "freestyle", "cypher", "diss",
    
    # Violence (awareness)
    "shooting", "shot dead", "killed", "murder", "stabbed",
    
    # Deaths
    "died", "dead", "death", "passed away", "rip", "funeral",
    
    # Tech/AI (EXPANDED)
    "launches", "announces", "releases", "open source",
    "github release", "new tool", "new model", "beta access",
    "free tier", "waitlist open", "early access",
]

HIGH_PRIORITY_KEYWORDS = [
    # Cyber
    "zero-day", "critical vulnerability", "ransomware", "data breach",
    "hack", "exploit", "leaked data",
    
    # Tech launches
    "announces", "launches", "unveils", "releases", "open source",
    
    # Crime
    "arrested", "indicted", "sentenced", "charges", "mugshot",
    
    # Breaking
    "breaking", "urgent", "developing", "just in",
    
    # Violence
    "shooting", "killed", "stabbed", "attack",
    
    # Deaths
    "died", "dead", "passed away",
]

# Black artists to boost
BLACK_ARTISTS = [
    "jay-z", "beyonce", "kanye", "ye", "drake", "kendrick", "j cole",
    "nicki minaj", "cardi b", "megan thee stallion", "doja cat",
    "travis scott", "future", "metro boomin", "21 savage",
    "lil baby", "lil durk", "polo g", "rod wave", "nba youngboy",
    "kodak black", "moneybagg yo", "est gee", "youngboy",
    "usher", "chris brown", "trey songz", "summer walker",
    "sza", "jhene aiko", "kehlani", "bryson tiller",
    "king von", "pop smoke", "chief keef", "quando rondo",
    "ice spice", "sexyy red", "latto", "glorilla", "doechii",
    "joe budden", "akademiks", "dj vlad", "adam22", "boosie",
]

# ========== FEEDS ==========

FEEDS = {
    # === BLACK CULTURE & HIP-HOP ===
    "🎤 The Shade Room": "https://theshaderoom.com/feed/",
    "🎤 Media Take Out": "https://mediatakeout.com/feed/",
    "🎤 WorldStarHipHop": "https://worldstarhiphop.com/videos/rss.php",
    "🎤 Hot 97": "https://hot97.com/feed/",
    "🎤 The Jasmine Brand": "https://thejasminebrand.com/feed/",
    "🎤 Bossip": "https://bossip.com/feed/",
    "🎤 The YBF": "https://www.theybf.com/feed",
    "🎤 Neighborhood Talk": "https://theneighborhoodtalk.com/feed/",
    "🎤 Hollywood Unlocked": "https://hollywoodunlocked.com/feed/",
    "🎤 Urban Islandz": "https://urbanislandz.com/feed/",
    
    # === HIP-HOP MUSIC ===
    "🎵 Rap Radar": "https://rapradar.com/feed/",
    "🎵 Hot New Hip Hop": "https://www.hotnewhiphop.com/rss",
    "🎵 HipHopWired": "https://hiphopwired.com/feed/",
    "🎵 XXL Magazine": "https://www.xxlmag.com/feed/",
    "🎵 HipHopDX": "https://hiphopdx.com/feed",
    "🎵 Complex Music": "https://www.complex.com/music/rss",
    "🎵 AllHipHop": "https://allhiphop.com/feed/",
    "🎵 Rap-Up": "https://www.rap-up.com/feed/",
    "🎵 The Source": "https://thesource.com/feed/",
    "🎵 Rated R&B": "https://www.rated-rnb.com/feed/",
    
    # YouTube hip-hop
    "📺 DJ Akademiks": "https://www.youtube.com/feeds/videos.xml?channel_id=UCWWbKkz0hS-w3VMkhS2t05g",
    "📺 No Jumper": "https://www.youtube.com/feeds/videos.xml?channel_id=UC3mBYU96-qGd5FKkDS0frLQ",
    "📺 Say Cheese TV": "https://www.youtube.com/feeds/videos.xml?channel_id=UCVg-jP2FvMNPPHZhp4D1dKA",
    
    # === TRENDING/VIRAL ===
    "📱 Pop Crave": "https://popcrave.com/feed/",
    "📱 TMZ": "https://www.tmz.com/rss.xml",
    
    # === AI & TECH (COMPREHENSIVE) ===
    "🤖 OpenAI": "https://openai.com/blog/rss.xml",
    "🤖 Anthropic": "https://www.anthropic.com/news/rss.xml",
    "🤖 Google DeepMind": "https://deepmind.google/blog/rss.xml",
    "🤖 Meta AI": "https://ai.meta.com/blog/rss/",
    "🤖 Hugging Face": "https://huggingface.co/blog/feed.xml",
    "🤖 TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "🤖 VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
    "🤖 The Verge AI": "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
    "🤖 Ars Technica": "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "🤖 MIT Tech Review AI": "https://www.technologyreview.com/topic/artificial-intelligence/feed",
    
    # === TECH GEEK SOURCES ===
    "⭐ Hacker News Front": "https://hnrss.org/frontpage",
    "⭐ Hacker News Show": "https://hnrss.org/show",
    "⭐ Product Hunt": "https://www.producthunt.com/feed",
    "⭐ GitHub Trending": "https://rsshub.app/github/trending/daily",
    "⭐ Reddit r/programming": "https://www.reddit.com/r/programming/.rss",
    "⭐ Reddit r/netsec": "https://www.reddit.com/r/netsec/.rss",
    "⭐ Reddit r/technology": "https://www.reddit.com/r/technology/.rss",
    "⭐ Dev.to": "https://dev.to/feed",
    
    # === OPEN SOURCE ===
    "🔧 Privacy Guides": "https://www.privacyguides.org/blog/feed.xml",
    "🔧 AlternativeTo": "https://alternativeto.net/news/feed/",
    "🔧 Self-Hosted": "https://selfhosted.libhunt.com/newsletter/feed",
    
    # === CYBERSECURITY ===
    "🔥 Krebs on Security": "https://krebsonsecurity.com/feed/",
    "🔥 BleepingComputer": "https://www.bleepingcomputer.com/feed/",
    "🔥 The Hacker News": "https://feeds.feedburner.com/TheHackersNews",
    "🔥 The Record": "https://therecord.media/feed",
    "🔥 Dark Reading": "https://www.darkreading.com/rss.xml",
    "🔥 Schneier on Security": "https://www.schneier.com/feed/atom/",
    
    # Breaches
    "🧨 DataBreaches.net": "https://databreaches.net/feed/",
    "🧨 HIBP": "https://feeds.feedburner.com/HaveIBeenPwnedLatestBreaches",
    "🧨 Ransomware.live": "https://www.ransomware.live/rss.xml",
    "🧨 Troy Hunt": "https://www.troyhunt.com/rss/",
    
    # Government
    "🛡️ CISA Advisories": "https://www.cisa.gov/cybersecurity-advisories/all.xml",
    "🛡️ CISA Current": "https://www.cisa.gov/news-events/cybersecurity-advisories/current-activity.xml",
    
    # Threat Intel
    "⚡ Mandiant": "https://www.mandiant.com/resources/blog/rss.xml",
    "⚡ CrowdStrike": "https://www.crowdstrike.com/blog/feed/",
    "⚡ Microsoft Security": "https://www.microsoft.com/en-us/security/blog/feed/",
    
    # === CRIME & LEGAL ===
    "⚖️ Crime Online": "https://www.crimeonline.com/feed/",
    "⚖️ Law & Crime": "https://lawandcrime.com/feed/",
    
    # === FINANCIAL CRIMES ===
    "💰 SEC Enforcement": "https://www.sec.gov/news/pressreleases.rss",
    "💰 DOJ Financial Fraud": "https://www.justice.gov/feeds/opa/topic/financial-fraud.xml",
    
    # === LAW ENFORCEMENT ===
    "🚔 FBI Press": "https://www.fbi.gov/feeds/press-releases/press-releases.xml",
    "🚔 DEA Press": "https://www.dea.gov/rss/press-releases.xml",
    
    # === BREAKING NEWS (US) ===
    "📰 Reuters US": "https://rsshub.app/reuters/us",
    "📰 AP News": "https://rsshub.app/apnews/topics/apf-topnews",
    
    # === INVESTIGATIVE ===
    "🔍 ProPublica": "https://www.propublica.org/feeds/propublica/main",
    "🔍 The Intercept": "https://theintercept.com/feed/?rss",
}

USER_AGENT = "AlertBot/2.1"
SEEN_FILE = Path.home() / ".alert_bot_seen.json"

# ========== FUNCTIONS ==========

def log(*args):
    print("[alerts]", *args, flush=True)

def getenv_required(name):
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Missing: {name}")
    return v

def load_seen():
    if not SEEN_FILE.exists():
        return set()
    try:
        with open(SEEN_FILE) as f:
            data = json.load(f)
            cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).timestamp()
            return set(k for k, v in data.items() if v > cutoff)
    except:
        return set()

def save_seen(seen):
    try:
        existing = {}
        if SEEN_FILE.exists():
            with open(SEEN_FILE) as f:
                existing = json.load(f)
        
        now = datetime.now(timezone.utc).timestamp()
        for item_id in seen:
            if item_id not in existing:
                existing[item_id] = now
        
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).timestamp()
        cleaned = {k: v for k, v in existing.items() if v > cutoff}
        
        SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SEEN_FILE, 'w') as f:
            json.dump(cleaned, f)
    except Exception as e:
        log(f"Save error: {e}")

def is_paywall(url):
    return any(d in url.lower() for d in PAYWALL_DOMAINS)

def contains_sports(text):
    return any(k in text.lower() for k in SPORTS_KEYWORDS)

def is_trash(text):
    text_lower = text.lower()
    if any(k in text_lower for k in JUICE_KEYWORDS):
        return False
    return any(k in text_lower for k in TRASH_KEYWORDS)

def mentions_black_artist(text):
    text_lower = text.lower()
    return any(artist in text_lower for artist in BLACK_ARTISTS)

def calculate_priority(title, content=""):
    text = (title + " " + content).lower()
    score = 0
    
    for k in HIGH_PRIORITY_KEYWORDS:
        if k in text:
            score += 10
    
    if mentions_black_artist(text):
        score += 30
    
    for k in JUICE_KEYWORDS:
        if k in text:
            score += 15
    
    if any(w in text for w in ["breaking", "urgent", "just in"]):
        score += 20
    
    if any(w in text for w in ["beef", "drama", "diss", "responds"]):
        score += 15
    
    if any(w in text for w in ["died", "dead", "death", "rip"]):
        score += 25
    
    if any(w in text for w in ["arrested", "charges", "sentenced"]):
        score += 20
    
    return score

def send_telegram(token, chat_id, html_text, disable_preview=False):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": html_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true" if disable_preview else "false",
        }
        r = requests.post(url, data=data, timeout=20)
        if r.status_code == 200:
            log("✓ Sent")
        else:
            log(f"Telegram error: {r.status_code}")
    except Exception as e:
        log(f"Send error: {e}")

def is_recent(dt_str, window_minutes):
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
    except:
        return False

def entry_id(entry):
    return (
        getattr(entry, "id", None)
        or getattr(entry, "guid", None)
        or getattr(entry, "link", None)
        or getattr(entry, "title", "")
    ) or ""

# ========== MAIN ==========

def check_feeds(token, chat_id, window_minutes, debug, seen):
    total_sent = 0
    new_items = []
    
    for label, url in FEEDS.items():
        try:
            log(f"Checking: {label}")
            d = feedparser.parse(url)
            entries = d.entries or []
            log(f"  Found {len(entries)} items")

            if debug:
                for e in entries[:2]:
                    link = getattr(e, "link", "")
                    title = getattr(e, "title", "New item")
                    published = getattr(e, "published", "") or getattr(e, "updated", "") or "No date"
                    if link:
                        msg = f"[DEBUG] {label}\n<b>{title}</b>\n📅 {published}\n<a href=\"{link}\">Read</a>"
                        send_telegram(token, chat_id, msg)
                        total_sent += 1
                continue

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
                
                if is_paywall(link):
                    log(f"  ⊗ Paywall: {title[:40]}")
                    continue
                
                if contains_sports(title + " " + summary):
                    log(f"  ⊗ Sports: {title[:40]}")
                    continue
                
                if not is_recent(published, window_minutes):
                    continue
                
                priority = calculate_priority(title, summary)
                
                if is_trash(title + " " + summary):
                    log(f"  ⊗ Trash: {title[:40]}")
                    continue
                
                seen.add(eid)
                new_items.append({
                    'label': label,
                    'title': title,
                    'link': link,
                    'priority': priority
                })

        except Exception as ex:
            log(f"  ERROR: {ex}")
    
    # Sort by priority, send
    new_items.sort(key=lambda x: x['priority'], reverse=True)
    
    for item in new_items:
        marker = "🔥 " if item['priority'] >= 20 else ""
        msg = f"{marker}{item['label']}\n<b>{item['title']}</b>\n<a href=\"{item['link']}\">Read</a>"
        send_telegram(token, chat_id, msg)
        total_sent += 1
    
    if new_items:
        log(f"Sent {len(new_items)} alerts")
    
    return total_sent

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    try:
        token = getenv_required("TELEGRAM_TOKEN")
        chat_id = getenv_required("TELEGRAM_CHAT_ID")
    except Exception as e:
        log(f"Missing env: {e}")
        return 1

    window_minutes = int(os.environ.get("WINDOW_MINUTES", "45"))

    log("=" * 60)
    log(f"Alert Bot v2.1 - Baltimore Edition")
    log(f"Window: {window_minutes} min | Debug: {args.debug}")
    log(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    log("=" * 60)

    seen = load_seen()
    log(f"Loaded {len(seen)} seen items")

    total = check_feeds(token, chat_id, window_minutes, args.debug, seen)

    if not args.debug:
        save_seen(seen)

    log("=" * 60)
    log(f"Sent {total} alerts")
    log("=" * 60)
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"Fatal: {e}")
        sys.exit(1)
