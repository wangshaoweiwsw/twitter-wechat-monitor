#!/usr/bin/env python3
"""
GitHub Actions: monitor @aleabitoreddit tweets via Nitter RSS,
push new ones to WeChat via Server酱.
"""
import json, os, sys, xml.etree.ElementTree as ET, urllib.request, hashlib, time

TARGET = "aleabitoreddit"
SENDKEY = os.environ["SERVERCHAN_SENDKEY"]

# Extensive list of Nitter instances
NITTERS = [
    "https://nitter.net",
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
    "https://xcancel.com",
    "https://nitter.catsarch.com",
    "https://nitter.tiekoetter.com",
    "https://nitter.space",
    "https://nitter.privacyredirect.com",
    "https://nitter.lucabased.xyz",
    "https://nitter.kareem.one",
    "https://twiiit.com",
    "https://nitter.1d4.us",
]

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; TwitterMonitor/1.0)"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read()
    except Exception as e:
        return None

def parse(xml_data):
    root = ET.fromstring(xml_data)
    tweets = []
    for item in root.findall(".//item"):
        title = (item.find("title").text or "").strip()
        link = (item.find("link").text or "").strip()
        pubdate = item.find("pubDate")
        pubdate = pubdate.text if pubdate is not None else ""
        text = title.split(": ", 1)[1] if ": " in title else title
        tweets.append({"text": text, "link": link, "pubdate": pubdate,
                       "id": hashlib.md5(link.encode()).hexdigest()[:16]})
    return tweets

def load_state():
    if os.path.exists("twitter_state.json"):
        with open("twitter_state.json") as f:
            return json.load(f)
    return {"last_ids": []}

def save_state(s):
    with open("twitter_state.json", "w") as f:
        json.dump(s, f)

def push_serverchan(title, content):
    data = json.dumps({"title": title, "desp": content}).encode()
    req = urllib.request.Request(f"https://sctapi.ftqq.com/{SENDKEY}.send",
        data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

state = load_state()
known = set(state.get("last_ids", []))

xml = None
for base in NITTERS:
    url = f"{base}/{TARGET}/rss"
    print(f"Trying {url}...")
    xml = fetch(url)
    if xml and len(xml) > 100:
        print(f"  OK ({len(xml)} bytes)")
        break
    print("  Failed")

if not xml:
    print("ERROR: All Nitter instances failed")
    sys.exit(1)

tweets = parse(xml)
print(f"Total: {len(tweets)}, known: {len(known)}")

new = [t for t in tweets if t["id"] not in known]
print(f"New: {len(new)}")

for t in reversed(new):
    title = f"🐦 @{TARGET} 发推了"
    content = f"{t['text']}\n\n🕐 {t['pubdate']}\n🔗 {t['link']}"
    try:
        r = push_serverchan(title, content)
        print(f"  Pushed: {r}")
    except Exception as e:
        print(f"  Push fail: {e}")
        continue
    known.add(t["id"])

state["last_ids"] = list(known)[-50:]
save_state(state)
print(f"Done. Tracking {len(state['last_ids'])} tweets.")
