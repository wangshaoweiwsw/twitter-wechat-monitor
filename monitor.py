#!/usr/bin/env python3
"""
Monitor @aleabitoreddit tweets via Nitter Proxy (Vercel Edge Function),
push new ones to WeChat via Server酱.
"""
import json, os, sys, xml.etree.ElementTree as ET, urllib.request, hashlib

TARGET = "aleabitoreddit"
SENDKEY = os.environ["SERVERCHAN_SENDKEY"]
PROXY_URL = f"https://nitter-proxy-peach.vercel.app/api/rss?user={TARGET}"

def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; TwitterMonitor/1.0)",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode()
    except Exception as e:
        print(f"ERROR: {e}")
        return None

def parse(xml_text):
    root = ET.fromstring(xml_text)
    tweets = []
    for item in root.findall(".//item"):
        title = (item.find("title").text or "").strip()
        link = (item.find("link").text or "").strip()
        pubdate = item.find("pubDate")
        pubdate = pubdate.text if pubdate is not None else ""
        text = title.split(": ", 1)[1] if ": " in title else title
        tweets.append({
            "text": text, "link": link, "pubdate": pubdate,
            "id": hashlib.md5(link.encode()).hexdigest()[:16],
        })
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

# Main
print(f"Fetching: {PROXY_URL}")
xml_text = fetch(PROXY_URL)

if not xml_text:
    print("FATAL: Could not fetch RSS")
    sys.exit(1)

if not xml_text.strip().startswith("<?xml"):
    print(f"Not XML response: {xml_text[:300]}")
    sys.exit(1)

tweets = parse(xml_text)
print(f"Found {len(tweets)} tweets")

state = load_state()
known = set(state.get("last_ids", []))

new = [t for t in tweets if t["id"] not in known]
print(f"New: {len(new)}")

for t in reversed(new):
    title = f"🐦 @{TARGET} 发推了"
    content = f"{t['text']}\n\n🕐 {t['pubdate']}\n🔗 {t['link']}"
    try:
        r = push_serverchan(title, content)
        print(f"  Pushed OK: pushid={r['data']['pushid']}")
    except Exception as e:
        print(f"  Push fail: {e}")
        continue
    known.add(t["id"])

state["last_ids"] = list(known)[-50:]
save_state(state)
print(f"Done. Tracking {len(state['last_ids'])} tweets.")
