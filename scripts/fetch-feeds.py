#!/usr/bin/env python3
"""Pull company RSS/Atom feeds and write data/posts.json."""

from __future__ import annotations

import json
import re
import ssl
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
UA = (
    "Mozilla/5.0 (compatible; EnggReads/1.0; +https://github.com/; company-blog aggregator) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
CONCURRENCY = 6
PER_FEED = 12
MAX_POSTS = 1000
TIMEOUT = 22

KEYWORDS = [
    (
        "ai",
        re.compile(
            r"\b(llm|gpt|transformer|diffusion|machine learning|deep learning|"
            r"neural|inference|fine-?tun|foundation model|genai|generative ai|mlops)\b",
            re.I,
        ),
    ),
    (
        "infrastructure",
        re.compile(
            r"\b(kubernetes|k8s|terraform|dns|cdn|vpc|load balanc|service mesh|"
            r"istio|envoy|networking|datacenter|data center)\b",
            re.I,
        ),
    ),
    (
        "reliability",
        re.compile(
            r"\b(sre|reliability|outage|incident|observability|prometheus|"
            r"on-call|postmortem|error budget)\b",
            re.I,
        ),
    ),
    (
        "security",
        re.compile(
            r"\b(security|cve|oauth|encryption|zero.?trust|vulnerability|"
            r"authn|authz|phishing|malware)\b",
            re.I,
        ),
    ),
    (
        "frontend",
        re.compile(
            r"\b(react|css|browser|frontend|front-end|design system|webkit|"
            r"accessibility|a11y)\b",
            re.I,
        ),
    ),
    ("mobile", re.compile(r"\b(android|ios|swiftui|\bswift\b|kotlin|mobile app)\b", re.I)),
    (
        "data",
        re.compile(
            r"\b(kafka|spark|flink|warehouse|analytics|etl|data pipeline|airflow|dbt)\b",
            re.I,
        ),
    ),
    (
        "databases",
        re.compile(
            r"\b(postgres|mysql|sqlite|dynamodb|cockroach|spanner|mongodb|redis|database)\b",
            re.I,
        ),
    ),
    (
        "devops",
        re.compile(
            r"\b(ci/cd|github actions|gitlab ci|docker|deploy|"
            r"platform engineering|developer experience|devex)\b",
            re.I,
        ),
    ),
    (
        "internal",
        re.compile(
            r"\b(how we|our stack|engineering culture|onboarding|rfc|"
            r"platform engineering|developer experience|production engineering|"
            r"incident review|postmortem|inside .{0,24}engineering)\b",
            re.I,
        ),
    ),
]

SKIP_TITLE = re.compile(
    r"("
    r"\bgenerally available\b|"
    r"\bnow available\b|"
    r"\bweekly roundup\b|"
    r"\bweek in review\b|"
    r"what.?s new\b|"
    r"we.?re hiring|"
    r"\bnow hiring\b|"
    r"join our team|"
    r"\binternship(s| program)?\b|"
    r"\bintern program\b|"
    r"\bhiring\b|"
    r"customer stor(?:y|ies)\b|"
    r"\bcase study\b|"
    r"register now|"
    r"join us at|"
    r"save your seat|"
    r"\bproduct launch(es)?\b|"
    r"\blaunch week\b|"
    r"\bpricing\b|"
    r"\bchangelog\b|"
    r"\bpatch notes\b|"
    r"\bintroducing\b|"
    r"\bannouncing\b|"
    r"everything we launched|"
    r"\bis now (in )?(public |open )?(beta|alpha|ga)\b|"
    r"\bnow in (public |open )?(beta|alpha|ga)\b"
    r")",
    re.I,
)

SKIP_EXCERPT = re.compile(
    r"("
    r"\bgenerally available\b|"
    r"\bnow generally available\b|"
    r"\bnow available\b|"
    r"\bweekly roundup\b|"
    r"\bweek in review\b|"
    r"we.?re hiring|"
    r"join our team|"
    r"\binternship program\b|"
    r"\bnew pricing\b|"
    r"\bpricing update\b|"
    r"\bproduct launch(es)?\b|"
    r"\blaunch week\b|"
    r"\bchangelog\b|"
    r"\bpatch notes\b|"
    r"\bis now (in )?(public |open )?(beta|alpha|ga)\b|"
    r"\bnow in (public |open )?(beta|alpha|ga)\b"
    r")",
    re.I,
)


def should_skip(title: str, excerpt: str) -> bool:
    if SKIP_TITLE.search(title or ""):
        return True
    return bool(SKIP_EXCERPT.search(excerpt or ""))

CTX = ssl.create_default_context()


def local_tag(tag: str) -> str:
    return tag.split("}", 1)[-1].lower()


def text_of(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return unescape("".join(el.itertext())).strip()


def child(el: ET.Element, *names: str) -> ET.Element | None:
    want = {n.lower() for n in names}
    for child_el in list(el):
        if local_tag(child_el.tag) in want:
            return child_el
    return None


def child_text(el: ET.Element, *names: str) -> str:
    return text_of(child(el, *names))


def strip_html(value: str) -> str:
    value = re.sub(r"(?is)<script.*?>.*?</script>", " ", value)
    value = re.sub(r"(?is)<style.*?>.*?</style>", " ", value)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", unescape(value)).strip()


def item_link(el: ET.Element) -> str:
    for link in el.iter():
        if local_tag(link.tag) != "link":
            continue
        rel = (link.attrib.get("rel") or "alternate").lower()
        href = link.attrib.get("href") or link.attrib.get("HREF")
        if href and rel in {"alternate", ""}:
            return href.strip()
        if href and "rel" not in link.attrib:
            return href.strip()
        body = (link.text or "").strip()
        if body.startswith("http"):
            return body
    guid = child(el, "guid", "id")
    if guid is not None and (guid.attrib.get("isPermaLink", "true").lower() != "false"):
        body = text_of(guid)
        if body.startswith("http"):
            return body
    return ""


def to_iso(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        return dt.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        pass
    try:
        iso = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        return None


def extra_tags(title: str, summary: str, base: list[str]) -> list[str]:
    tags = list(dict.fromkeys(base))
    hay = f"{title} {summary}"
    for tag, pattern in KEYWORDS:
        if pattern.search(hay) and tag not in tags:
            tags.append(tag)
    return tags


def tagged(item: dict, source: dict) -> list[str]:
    tags = extra_tags(item["title"], item["summary"], source.get("tags") or [])
    if source.get("recommended") and "recommended" not in tags:
        tags.insert(0, "recommended")
    return tags


def parse_feed(xml: str) -> list[dict]:
    xml = xml.lstrip("\ufeff")
    xml = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", xml)
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        xml = re.sub(r"&(?!#?\w+;)", "&amp;", xml)
        root = ET.fromstring(xml)

    items: list[ET.Element] = []
    for el in root.iter():
        if local_tag(el.tag) in {"item", "entry"}:
            items.append(el)

    posts = []
    for el in items:
        title = strip_html(child_text(el, "title"))
        link = item_link(el)
        date = child_text(el, "published", "updated", "pubdate", "date")
        summary = strip_html(
            child_text(el, "description", "summary", "content", "encoded")
        )
        if title and link:
            posts.append(
                {
                    "title": title,
                    "link": link,
                    "date": date,
                    "summary": summary,
                }
            )
    return posts


def fetch_one(source: dict) -> tuple[dict, str | None, list[dict]]:
    req = urllib.request.Request(
        source["feed"],
        headers={
            "User-Agent": UA,
            "Accept": "*/*",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=CTX) as res:
            xml = res.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as err:
        return source, f"HTTP {err.code}", []
    except Exception as err:  # noqa: BLE001 — keep fetching other feeds
        return source, str(err) or err.__class__.__name__, []

    try:
        parsed = parse_feed(xml)
    except ET.ParseError as err:
        return source, f"XML {err}", []

    posts = []
    for item in parsed:
        excerpt = item["summary"][:240]
        if should_skip(item["title"], excerpt):
            continue
        if len(posts) >= PER_FEED:
            break
        posts.append(
            {
                "id": f"{source['id']}:{item['link']}",
                "sourceId": source["id"],
                "title": item["title"],
                "url": item["link"],
                "publishedAt": to_iso(item["date"]),
                "excerpt": excerpt,
                "tags": tagged(item, source),
            }
        )
    return source, None, posts


def main() -> int:
    catalog = json.loads((ROOT / "data" / "sources.json").read_text(encoding="utf-8"))
    sources = catalog["sources"]
    print(f"Fetching {len(sources)} feeds…", flush=True)

    failed: list[tuple[str, str]] = []
    posts: list[dict] = []
    ok = 0

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = {pool.submit(fetch_one, source): source for source in sources}
        for fut in as_completed(futures):
            source, error, items = fut.result()
            if error:
                failed.append((source["id"], error))
                print(f"  skip {source['id']}: {error}", flush=True)
            else:
                ok += 1
                posts.extend(items)

    seen: set[str] = set()
    unique: list[dict] = []
    for post in posts:
        if post["url"] in seen:
            continue
        seen.add(post["url"])
        unique.append(post)

    unique.sort(
        key=lambda p: p["publishedAt"] or "",
        reverse=True,
    )
    unique = unique[:MAX_POSTS]

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "feedCount": len(sources),
        "fetchedOk": ok,
        "postCount": len(unique),
        "posts": unique,
    }
    out = ROOT / "data" / "posts.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(unique)} posts from {ok}/{len(sources)} feeds.", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
