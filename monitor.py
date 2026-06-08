#!/usr/bin/env python3
import json, os, sys, xml.etree.ElementTree as ET, urllib.request, hashlib, re

TARGET = "aleabitoreddit"
SENDKEY = os.environ["SERVERCHAN_SENDKEY"]
PROXY_URL = f"https://nitter-proxy-peach.vercel.app/api/rss?user={TARGET}"

def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; Monitor/1.0)",
        "Accept": "*/*",
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.read().decode()
    except Exception as e:
        print(f"FETCH ERROR: {e}")
        return None

def parse_rss(xml_text):
    root = ET.fromstring(xml_text)
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

def parse_syndication(data):
    tweets = []
    body = data.get("body", "")
    # Extract tweet text from HTML
    for m in re.finditer(r'<p[^>]*class="[^"]*tweet-text[^"]*"[^>]*>(.*?)</p>', body, re.DOTALL):
        text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if text:
            tid = hashlib.md5(text.encode()).hexdigest()[:16]
            tweets.append({"text": text, "link": f"https://x.com/{TARGET}", "pubdate": "", "id": tid})
    return tweets

def push(key, title, content):
    data = json.dumps({"title": title, "desp": content}).encode()
    req = urllib.request.Request(f"https://sctapi.ftqq.com/{key}.send",
        data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def load_state():
    if os.path.exists("twitter_state.json"):
        with open("twitter_state.json") as f:
            return json.load(f)
    return {"last_ids": []}

def save_state(s):
    with open("twitter_state.json", "w") as f:
        json.dump(s, f)

# --- main ---
print(f"Fetching: {PROXY_URL}")
raw = fetch(PROXY_URL)

if not raw:
    print("FATAL: no response")
    sys.exit(1)

print(f"Response ({len(raw)} bytes): {raw[:200]}")

# Try JSON (syndication)
if raw.strip().startswith("{"):
    try:
        j = json.loads(raw)
        if j.get("source") == "syndication":
            tweets = parse_syndication(j["data"])
        else:
            tweets = []
    except:
        tweets = []
# Try XML (RSS)
elif "<?xml" in raw or "<rss" in raw:
    tweets = parse_rss(raw)
else:
    tweets = []

print(f"Parsed {len(tweets)} tweets")

state = load_state()
known = set(state.get("last_ids", []))
new = [t for t in tweets if t["id"] not in known]
print(f"New: {len(new)}")

for t in reversed(new):
    title = f"🐦 @{TARGET} 发推了"
    content = f"{t['text']}\n\n🕐 {t.get('pubdate','')}\n🔗 {t['link']}"
    try:
        r = push(SENDKEY, title, content)
        print(f"  OK pushid={r['data']['pushid']}")
    except Exception as e:
        print(f"  FAIL: {e}")
        continue
    known.add(t["id"])

state["last_ids"] = list(known)[-50:]
save_state(state)
print(f"Done. Tracking {len(state['last_ids'])} tweets.")
