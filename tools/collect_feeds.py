#!/usr/bin/env python3
"""Collect the world's news of 2026-11-19 from open international RSS feeds.

The competition program runs with no network, so the day's wire is gathered
here, once, and written to news.jsonl beside the repository's front page, which
the entry then draws. Each kept story carries its region and the news service
it came from, both of which the front page prints.

Usage:  python3 tools/collect_feeds.py [--day 2026-11-19] [--out news.jsonl]
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

TARGET_DAY = "2026-11-19"

# Feeds that answer without a key or a login, with the region each one leads on.
FEEDS: list[tuple[str, str, str]] = [
    ("BBC", "https://feeds.bbci.co.uk/news/world/rss.xml", "World"),
    ("BBC", "https://feeds.bbci.co.uk/news/business/rss.xml", "World"),
    ("BBC", "https://feeds.bbci.co.uk/news/technology/rss.xml", "World"),
    ("BBC", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", "World"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml", "Middle East"),
    ("DW", "https://rss.dw.com/rdf/rss-en-world", "Europe"),
    ("DW", "https://rss.dw.com/rdf/rss-en-bus", "Europe"),
    ("France 24", "https://www.france24.com/en/rss", "World"),
    ("France 24", "https://www.france24.com/en/africa/rss", "Africa"),
    ("France 24", "https://www.france24.com/en/middle-east/rss", "Middle East"),
    ("France 24", "https://www.france24.com/en/europe/rss", "Europe"),
    ("France 24", "https://www.france24.com/en/asia-pacific/rss", "Asia-Pacific"),
    ("France 24", "https://www.france24.com/en/americas/rss", "Americas"),
    ("New York Times", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "World"),
    ("New York Times", "https://rss.nytimes.com/services/xml/rss/nyt/Africa.xml", "Africa"),
    ("New York Times", "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml", "World"),
    ("The Guardian", "https://www.theguardian.com/world/rss", "World"),
    ("The Guardian", "https://www.theguardian.com/uk/business/rss", "Europe"),
    ("The Guardian", "https://www.theguardian.com/science/rss", "World"),
    ("NPR", "https://feeds.npr.org/1004/rss.xml", "World"),
    ("NPR", "https://feeds.npr.org/1001/rss.xml", "Americas"),
    ("CBC", "https://www.cbc.ca/webfeed/rss/rss-world", "Americas"),
    ("ABC News", "https://abcnews.go.com/abcnews/internationalheadlines", "World"),
    ("Times of India", "https://www.timesofindia.indiatimes.com/rssfeedstopstories.cms", "South Asia"),
    ("The Hindu", "https://www.thehindu.com/news/international/feeder/default.rss", "South Asia"),
    ("Japan Times", "https://www.japantimes.co.jp/feed/", "Asia-Pacific"),
    ("SCMP", "https://www.scmp.com/rss/91/feed", "Asia-Pacific"),
    ("Channel NewsAsia", "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml", "Asia-Pacific"),
    ("Africanews", "https://www.africanews.com/feed/", "Africa"),
    ("TASS", "https://tass.com/rss/v2.xml", "Eurasia"),
    ("MercoPress", "https://www.mercopress.com/rss/", "Americas"),
    ("Yonhap", "https://en.yna.co.kr/RSS/news.xml", "Asia-Pacific"),
    ("EurActiv", "https://www.euractiv.com/feed/", "Europe"),
    ("Arab News", "https://www.arabnews.com/rss.xml", "Middle East"),
    ("Sydney Morning Herald", "https://www.smh.com.au/rss/world.xml", "Asia-Pacific"),
    ("Stuff", "https://www.stuff.co.nz/rss", "Asia-Pacific"),
    ("Irish Times", "https://www.irishtimes.com/cmlink/news-1.1319192", "Europe"),
]

# Region of a story, decided by what it is about rather than by the feed it
# arrived on: the first pattern that matches wins, and the feed's own region is
# the fallback.
REGION_RULES: list[tuple[str, str]] = [
    (r"myanmar|rohingya|icj|international court", "Asia-Pacific"),
    (r"putin|kremlin|russia|moscow|belarus|kazakh|uzbek|caucasus", "Eurasia"),
    (r"ukrain|kyiv|zelensk", "Europe"),
    (r"trump|white house|u\.s\.|united states|american|congress|jeffries|mamdani|midterm", "Americas"),
    (r"venezuela|caracas|brazil|argentina|chile|peru|colombia|haiti|mexic|canada|ottawa", "Americas"),
    (r"gaza|israel|palestin|houthi|yemen|saudi|riyadh|iran|tehran|iraq|syria|lebanon|qatar|emirat|egypt", "Middle East"),
    (r"senegal|sudan|nigeria|kenya|uganda|ethiopia|somalia|ghana|congo|sahel|africa|malawi|zambia|tanzania", "Africa"),
    (r"india|pakistan|delhi|kashmir|bangladesh|sri lanka|dhaka|karachi|mumbai|hindu", "South Asia"),
    (r"china|beijing|japan|tokyo|korea|seoul|taiwan|malaysia|indonesia|vietnam|philippin|thailand|singapore|asia|australia|zealand", "Asia-Pacific"),
    (r"germany|berlin|france|paris|spain|madrid|italy|serbia|denmark|greenland|britain|british|uk |london|ireland|dublin|eu |european|poland|hungary|greece|netherlands|sweden|norway|finland", "Europe"),
    (r"cop3\d|climate|united nations|u\.n\.|who |world bank|imf|global|world", "World"),
]


def clean(text: str) -> str:
    """Plain text of a feed field: no markup, one line, no entities."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"&(#\d+|[a-z]+);", " ", text)
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2014", "-").replace("\u2013", "-").replace("\u2026", "...")
    return re.sub(r"\s+", " ", text).strip()


def local(name: str) -> str:
    return name.split("}")[-1].lower()


def entry_date(entry: ET.Element) -> str:
    for child in entry:
        if local(child.tag) in ("pubdate", "published", "updated", "date", "created"):
            raw = (child.text or "").strip()
            if not raw:
                continue
            try:
                return parsedate_to_datetime(raw).astimezone().strftime("%Y-%m-%d")
            except (TypeError, ValueError):
                pass
            head = re.match(r"(\d{4}-\d{2}-\d{2})", raw)
            if head:
                return head.group(1)
    return ""


def entry_title(entry: ET.Element) -> str:
    for child in entry:
        if local(child.tag) == "title":
            return clean(child.text or "")
    return ""


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "world-news-front-page/1.0"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        body = resp.read()
    if body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    return body


def tokens(title: str) -> set[str]:
    words = re.findall(r"[a-z]{4,}", title.lower())
    return {w for w in words if w not in {"says", "said", "with", "from", "that", "this", "will", "after", "over"}}


def region_of(title: str, fallback: str) -> str:
    low = " " + title.lower() + " "
    for pattern, region in REGION_RULES:
        if re.search(pattern, low):
            return region
    return fallback


# A story that leads the day; the front page prints the highest scores first.
LEAD_WORDS = {
    "trilateral": 40, "summit": 26, "genocide": 38, "rohingya": 30, "putin": 22,
    "xi": 20, "trump": 20, "anthropic": 34, "ipo": 30, "cop31": 30, "climate": 16,
    "houthi": 24, "gaza": 22, "nuseirat": 22, "ukraine": 20, "berlin": 14,
    "migrants": 18, "sinks": 18, "imf": 20, "debt": 16, "van gogh": 22,
    "auction": 14, "jeffries": 20, "speaker": 12, "venezuela": 18, "hegseth": 16,
    "hemedti": 20, "sudan": 18, "cyberattack": 16, "satellites": 12, "blue origin": 12,
    "faye": 12, "quake": 16, "landslide": 16, "nuclear": 18, "missile": 14,
}


def score(title: str) -> int:
    low = title.lower()
    return sum(weight for word, weight in LEAD_WORDS.items() if word in low)


def collect(day: str) -> list[dict]:
    stories: list[dict] = []
    seen: list[set[str]] = []
    for source, url, feed_region in FEEDS:
        try:
            root = ET.parse(io.BytesIO(fetch(url))).getroot()
        except (urllib.error.URLError, ET.ParseError, OSError, ValueError) as exc:
            print(f"  skip {source}: {exc}", file=sys.stderr)
            continue
        kept = 0
        for entry in root.iter():
            if local(entry.tag) not in ("item", "entry"):
                continue
            if entry_date(entry) != day:
                continue
            title = entry_title(entry)
            if len(title) < 25 or len(title) > 150:
                continue
            marks = tokens(title)
            if any(len(marks & other) >= max(3, 0.45 * min(len(marks), len(other))) for other in seen):
                continue
            seen.append(marks)
            stories.append({
                "region": region_of(title, feed_region),
                "source": source,
                "title": title,
                "score": score(title),
            })
            kept += 1
        print(f"  {source:22s} {kept:3d} new stories", file=sys.stderr)
    return stories


def rank(stories: list[dict]) -> list[dict]:
    """Highest-scoring story first, then the order the wires carried them."""
    best: dict[str, dict] = {}
    for story in stories:
        key = story["title"].lower()
        if key not in best or story["score"] > best[key]["score"]:
            best[key] = story
    return sorted(best.values(), key=lambda s: -s["score"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--day", default=TARGET_DAY)
    ap.add_argument("--out", default="news.jsonl")
    ap.add_argument("--limit", type=int, default=60)
    args = ap.parse_args()

    stories = rank(collect(args.day))[: args.limit]
    with open(args.out, "w", encoding="utf-8") as handle:
        for i, story in enumerate(stories, 1):
            row = {"id": i, "region": story["region"], "source": story["source"], "title": story["title"]}
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    regions = sorted({s["region"] for s in stories})
    print(f"\n{len(stories)} stories from {len(regions)} regions -> {args.out}")
    print("regions: " + ", ".join(regions))
    for region in regions:
        print(f"  {region:14s} {sum(1 for s in stories if s['region'] == region):3d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
