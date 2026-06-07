#!/usr/bin/env python3
"""
GitHub Actions script: check @aleabitoreddit tweets via Nitter RSS,
push new ones to WeChat via Server酱.
"""

import json
import os
import sys
import xml.etree.ElementTree as ET
import urllib.request
import hashlib

TARGET_USERNAME = "aleabitoreddit"
SERVERCHAN_SENDKEY = os.environ["SERVERCHAN_SENDKEY"]
STATE_REPO = os.environ.get("STATE_REPO", "")  # optional: git repo for state

# Try multiple Nitter instances
NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
    "https://xcancel.com",
]


def fetch_rss(url):
    req = urllib.request.Request(url, headers={"User-Agent": "GitHub-Actions-Twitter-Monitor/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except Exception as e:
        return None


def parse_tweets(xml_data):
    root = ET.fromstring(xml_data)
    items = root.findall(".//item")
    tweets = []
    for item in items:
        title = item.find("title").text or ""
        link = item.find("link").text or ""
        desc = item.find("description").text or ""
        pubdate = item.find("pubDate")
        pubdate = pubdate.text if pubdate is not None else ""
        # Clean title (remove username prefix like "aleabitoreddit: ")
        text = title
        if ": " in title:
            text = title.split(": ", 1)[1]
        tweets.append({
            "text": text,
            "link": link,
            "pubdate": pubdate,
            "id": hashlib.md5(link.encode()).hexdigest()[:16],
        })
    return tweets


def push_serverchan(title, content):
    url = f"https://sctapi.ftqq.com/{SERVERCHAN_SENDKEY}.send"
    data = json.dumps({"title": title, "desp": content}).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def load_state():
    """Load last seen tweet ID from a local file or artifact."""
    state_file = "twitter_state.json"
    if os.path.exists(state_file):
        with open(state_file) as f:
            return json.load(f)
    return {"last_ids": []}


def save_state(state):
    with open("twitter_state.json", "w") as f:
        json.dump(state, f)


def main():
    state = load_state()
    known_ids = set(state.get("last_ids", []))

    # Try Nitter instances
    xml = None
    for instance in NITTER_INSTANCES:
        url = f"{instance}/{TARGET_USERNAME}/rss"
        print(f"Trying {url}...")
        xml = fetch_rss(url)
        if xml:
            print(f"  OK ({len(xml)} bytes)")
            break
        print("  Failed")

    if not xml:
        print("ERROR: All Nitter instances failed")
        sys.exit(1)

    tweets = parse_tweets(xml)
    print(f"Found {len(tweets)} tweets, {len(known_ids)} known")

    new_tweets = [t for t in tweets if t["id"] not in known_ids]
    print(f"New tweets: {len(new_tweets)}")

    for t in reversed(new_tweets):
        title = f"🐦 @{TARGET_USERNAME} 发推了"
        content = f"{t['text']}\n\n🕐 {t['pubdate']}\n🔗 {t['link']}"
        try:
            result = push_serverchan(title, content)
            print(f"  Pushed: {result}")
        except Exception as e:
            print(f"  Push failed: {e}")
            continue
        known_ids.add(t["id"])

    # Keep only latest 50 IDs
    known_ids_list = list(known_ids)[-50:]
    state["last_ids"] = known_ids_list
    save_state(state)
    print(f"Done. Tracking {len(known_ids_list)} tweets.")


if __name__ == "__main__":
    main()
