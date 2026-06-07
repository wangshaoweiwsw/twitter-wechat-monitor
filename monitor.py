#!/usr/bin/env python3
"""
GitHub Actions: monitor @aleabitoreddit tweets via multiple methods,
push new ones to WeChat via Server酱.
"""
import json, os, sys, urllib.request, hashlib, re, time

TARGET = "aleabitoreddit"
SENDKEY = os.environ["SERVERCHAN_SENDKEY"]

def fetch(url, headers=None):
    h = {"User-Agent": "Mozilla/5.0 (compatible; TwitterMonitor/1.0)"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode()
    except Exception as e:
        return None

def parse_tweets_html(html):
    """Parse tweets from Twitter embed HTML."""
    # Look for tweet text patterns in embedded content
    tweets = []
    # Pattern: tweet text in data or meta tags
    pattern = r'data-text="([^"]+)"'
    matches = list(re.finditer(pattern, html))
    seen = set()
    for m in matches[:20]:
        text = m.group(1)
        if len(text) < 3:
            continue
        tid_hash = hashlib.md5(text.encode()).hexdigest()[:16]
        if tid_hash not in seen:
            seen.add(tid_hash)
            tweets.append({"text": text, "id": tid_hash, "link": f"https://x.com/{TARGET}", "pubdate": ""})
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

# ==== Strategy 1: Twitter embed / syndication API ====
print("=== Strategy 1: Twitter syndication ===")
urls = [
    f"https://cdn.syndication.twimg.com/timeline/profile?screen_name={TARGET}",
    f"https://cdn.syndication.twimg.com/widgets/followbutton/info.json?screen_names={TARGET}",
]
html = None
for url in urls:
    print(f"  Trying {url[:60]}...")
    r = fetch(url)
    if r:
        html = r
        print(f"  OK ({len(r)} bytes)")
        break
    print("  Failed")

# ==== Strategy 2: Nitter instances ====
if not html:
    print("\n=== Strategy 2: Nitter RSS ===")
    import xml.etree.ElementTree as ET
    nitters = [
        "https://nitter.net", "https://nitter.poast.org",
        "https://nitter.privacydev.net", "https://xcancel.com",
        "https://nitter.1d4.us", "https://nitter.catsarch.com",
        "https://twiiit.com",
    ]
    for base in nitters:
        url = f"{base}/{TARGET}/rss"
        print(f"  Trying {url}...")
        r = fetch(url)
        if r and len(r) > 100 and r.strip().startswith("<?xml"):
            html = r
            print(f"  OK ({len(r)} bytes)")
            break
        print("  Failed")

if not html:
    print("ERROR: All strategies failed")
    sys.exit(1)

# Parse results
state = load_state()
known = set(state.get("last_ids", []))

if html.strip().startswith("{"):
    # JSON response
    data = json.loads(html)
    tweets = []
    # Handle syndication timeline format
    if "body" in data:
        body_html = data["body"]
        # Extract tweet text from HTML
        for m in re.finditer(r'<p[^>]*class="[^"]*tweet-text[^"]*"[^>]*>(.*?)</p>', body_html, re.DOTALL):
            text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            tid = hashlib.md5(text.encode()).hexdigest()[:16]
            tweets.append({"text": text, "id": tid, "link": f"https://x.com/{TARGET}", "pubdate": ""})
    print(f"Found {len(tweets)} tweets from JSON")
elif html.strip().startswith("<?xml"):
    # RSS XML
    import xml.etree.ElementTree as ET
    root = ET.fromstring(html)
    items = root.findall(".//item")
    tweets = []
    for item in items:
        title = (item.find("title").text or "").strip()
        link = (item.find("link").text or "").strip()
        pubdate = item.find("pubDate")
        pubdate = pubdate.text if pubdate is not None else ""
        text = title.split(": ", 1)[1] if ": " in title else title
        tweets.append({"text": text, "link": link, "pubdate": pubdate,
                       "id": hashlib.md5(link.encode()).hexdigest()[:16]})
    print(f"Found {len(tweets)} tweets from RSS")
else:
    tweets = parse_tweets_html(html)
    print(f"Found {len(tweets)} tweets from HTML")

new = [t for t in tweets if t["id"] not in known]
print(f"New tweets: {len(new)}")

for t in reversed(new):
    title = f"🐦 @{TARGET} 发推了"
    content = f"{t['text']}\n\n🕐 {t.get('pubdate', '')}\n🔗 {t.get('link', f'https://x.com/{TARGET}')}"
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
