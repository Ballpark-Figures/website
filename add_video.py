#!/usr/bin/env python3
"""Add a video to the site — sources everything it can, asks only what needs judgment.

Right after publishing a video, run:

    python3 add_video.py                 # picks your newest video not on the site yet
    python3 add_video.py <url-or-id>     # or name one explicitly

It pulls the title + publish date from the YouTube Data API, proposes a slug and
topic, finds the matching Patreon post (or offers Substack), shows you the entry,
and on confirm inserts it into data/videos.json (newest-first) and reruns build.py.

Credentials come from the sibling analytics/.env (YOUTUBE_API_KEY for the Data API,
PATREON_* for the blog-post lookup) — the same store the rest of the tooling uses.
Nothing here is committed to this public repo; the .env stays gitignored in analytics/.
"""
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VIDEOS_JSON = ROOT / "data" / "videos.json"
# analytics/ is a sibling of this repo under the umbrella; its .env holds the keys.
ENV = ROOT.parent / "analytics" / ".env"
SUBSTACK = "https://ballparkfigures.substack.com/p/"
YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def load_env() -> dict:
    if not ENV.exists():
        sys.exit(f"Can't find {ENV} — needed for the YouTube/Patreon keys.")
    cfg = {}
    for line in ENV.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip().strip('"').strip("'")
    return cfg


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    got = input(f"{prompt}{suffix}: ").strip()
    return got or default


def parse_video_id(arg: str) -> str:
    if YT_ID_RE.match(arg):
        return arg
    m = re.search(r"(?:v=|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})", arg)
    if m:
        return m.group(1)
    sys.exit(f"Couldn't read a YouTube id from {arg!r}.")


# ── YouTube Data API ────────────────────────────────────────────────────────

def yt_get(path: str, params: dict, key: str) -> dict:
    params = {**params, "key": key}
    url = f"https://www.googleapis.com/youtube/v3/{path}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url) as r:
        return json.load(r)


def newest_uploads(cfg: dict) -> list[dict]:
    """Recent uploads for the channel behind YOUTUBE_API_KEY's owner (@bpkfigures)."""
    key = cfg["YOUTUBE_API_KEY"]
    ch = yt_get("channels", {"part": "contentDetails", "forHandle": "bpkfigures"}, key)
    items = ch.get("items")
    if not items:
        return []
    uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    pl = yt_get("playlistItems",
                {"part": "snippet,contentDetails", "playlistId": uploads, "maxResults": "10"},
                key)
    return [
        {"id": it["contentDetails"]["videoId"],
         "title": it["snippet"]["title"],
         "date": it["contentDetails"].get("videoPublishedAt", "")[:10]}
        for it in pl.get("items", [])
    ]


def video_snippet(video_id: str, cfg: dict) -> dict:
    data = yt_get("videos", {"part": "snippet", "id": video_id}, cfg["YOUTUBE_API_KEY"])
    items = data.get("items")
    if not items:
        sys.exit(f"YouTube returned no video for id {video_id}.")
    sn = items[0]["snippet"]
    return {"id": video_id, "title": sn["title"],
            "date": sn.get("publishedAt", "")[:10], "description": sn.get("description", "")}


# ── Patreon API v2 (own campaign) ───────────────────────────────────────────

def patreon_posts(cfg: dict) -> list[dict]:
    token = cfg.get("PATREON_ACCESS_TOKEN", "")
    if not token:
        return []

    def call(tok: str):
        url = ("https://www.patreon.com/api/oauth2/v2/campaigns/16154815/posts?"
               + urllib.parse.urlencode(
                   {"fields[post]": "title,url,published_at", "page[count]": "50"},
                   safe="[],"))
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
        with urllib.request.urlopen(req) as r:
            return json.load(r)

    try:
        data = call(token)
    except urllib.error.HTTPError as e:
        if e.code != 401:
            print(f"  (Patreon API error {e.code}; skipping post lookup)")
            return []
        token = refresh_patreon(cfg)          # token expired (~30d) — refresh once
        if not token:
            return []
        try:
            data = call(token)
        except urllib.error.HTTPError as e2:
            print(f"  (Patreon API error {e2.code} after refresh; skipping)")
            return []
    posts = []
    for p in data.get("data", []):
        a = p["attributes"]
        url = a.get("url", "")
        if url.startswith("/"):
            url = "https://www.patreon.com" + url
        posts.append({"title": a.get("title", ""), "url": url})
    return posts


def refresh_patreon(cfg: dict) -> str:
    """Exchange the refresh token for a fresh access token; persist it to .env."""
    body = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": cfg.get("PATREON_REFRESH_TOKEN", ""),
        "client_id": cfg.get("PATREON_CLIENT_ID", ""),
        "client_secret": cfg.get("PATREON_CLIENT_SECRET", ""),
    }).encode()
    try:
        req = urllib.request.Request("https://www.patreon.com/api/oauth2/token", data=body)
        with urllib.request.urlopen(req) as r:
            tok = json.load(r)
    except urllib.error.HTTPError as e:
        print(f"  (Patreon token refresh failed: {e.code}; skipping post lookup)")
        return ""
    access, refresh = tok.get("access_token", ""), tok.get("refresh_token", "")
    text = ENV.read_text()
    text = re.sub(r"PATREON_ACCESS_TOKEN=.*", f"PATREON_ACCESS_TOKEN={access}", text)
    if refresh:
        text = re.sub(r"PATREON_REFRESH_TOKEN=.*", f"PATREON_REFRESH_TOKEN={refresh}", text)
    ENV.write_text(text)
    print("  (refreshed the Patreon access token in analytics/.env)")
    return access


def best_patreon_match(topic: str, posts: list[dict]) -> str:
    t = topic.lower().strip()
    if not t:
        return ""
    # Whole-word match, then prefer the title closest to just the topic (shortest),
    # so "Yahtzee" picks "From the Archive: Yahtzee" over "...Yahtzee vs. Battleship".
    hits = [p for p in posts if re.search(rf"\b{re.escape(t)}\b", p["title"].lower())]
    if not hits:
        return ""
    hits.sort(key=lambda p: (p["title"].lower().strip() != t, len(p["title"])))
    return hits[0]["url"]


# ── blog-post link chooser ──────────────────────────────────────────────────

def choose_post_url(topic: str, slug: str, snippet: dict, cfg: dict) -> str:
    posts = patreon_posts(cfg)
    patreon_guess = best_patreon_match(topic, posts)
    # A "Blog post:" / "post:" URL in the YouTube description is a good fallback.
    desc_link = ""
    m = re.search(r"https?://\S*(?:patreon\.com|substack\.com)\S*", snippet["description"])
    if m:
        desc_link = m.group(0).rstrip(".,)")
    substack_guess = f"{SUBSTACK}{slug}"

    print("\nBlog-post link:")
    if patreon_guess:
        print(f"  [p] Patreon (matched):  {patreon_guess}")
    print(f"  [s] Substack (guess):   {substack_guess}")
    if desc_link and desc_link not in (patreon_guess, substack_guess):
        print(f"  [d] From description:   {desc_link}")
    print("  [u] paste a URL   [n] none")
    # Never DEFAULT to the Substack guess: it is a URL built from the slug, not one known
    # to exist, and accepting it put a dead link on the Wordle page (2026-10-12).
    default = "p" if patreon_guess else ("d" if desc_link else "n")
    while True:
        pick = ask("  choose", default).lower()
        if pick == "p" and patreon_guess:
            return patreon_guess
        if pick == "s":
            return substack_guess
        if pick == "d" and desc_link:
            return desc_link
        if pick == "u":
            return ask("  URL")
        if pick == "n":
            return ""
        print("  (pick p / s / d / u / n)")


# ── helpful links (the same rule as analytics' bpkanalytics/release.py) ──────

URL_RE = re.compile(r"https?://\S+")


def description_links(description: str, skip: set[str]) -> list[dict]:
    """One item per description line holding a URL, labelled with that line's text
    before its first URL; URLs in `skip` (this page, the button's link) are dropped.
    Keep in step with description_links in analytics/bpkanalytics/release.py."""
    out = []
    for line in (description or "").splitlines():
        urls = [u.rstrip(".,)") for u in URL_RE.findall(line)]
        urls = [u for u in urls if u.rstrip("/") not in skip]
        if not urls:
            continue
        label = line[:URL_RE.search(line).start()].strip().rstrip(":").strip()
        out.append({"label": label, "urls": urls})
    return out


# ── main ────────────────────────────────────────────────────────────────────

def suggest_slug(title: str) -> str:
    # last word of the title is usually the topic (Yahtzee, Battleship, Hangman)
    word = re.sub(r"[^a-z0-9]", "", title.lower().split()[-1]) if title.split() else ""
    return word


def main() -> None:
    cfg = load_env()
    videos = json.loads(VIDEOS_JSON.read_text(encoding="utf-8"))
    existing_ids = {v.get("youtube_id") for v in videos}

    if len(sys.argv) > 1:
        snippet = video_snippet(parse_video_id(sys.argv[1]), cfg)
    else:
        print("Finding your newest video not on the site yet…")
        fresh = [u for u in newest_uploads(cfg) if u["id"] not in existing_ids]
        if not fresh:
            sys.exit("Nothing new — every recent upload is already in videos.json.")
        snippet = video_snippet(fresh[0]["id"], cfg)

    if snippet["id"] in existing_ids:
        sys.exit(f"{snippet['id']} is already in videos.json ({snippet['title']!r}).")

    print(f"\nVideo:  {snippet['title']}")
    print(f"Id:     {snippet['id']}")
    print(f"Date:   {snippet['date']}\n")

    topic = ask("Topic (short label on the homepage)", snippet["title"].split()[-1].strip("*.,"))
    slug = ask("Slug (URL: /videos/<slug>/)", suggest_slug(topic) or suggest_slug(snippet["title"]))
    if any(v.get("slug") == slug for v in videos):
        sys.exit(f"Slug {slug!r} is already taken in videos.json.")
    post_url = choose_post_url(topic, slug, snippet, cfg)
    blurb = ask("Blurb (optional)", "")
    page = f"https://www.ballparkfigur.es/videos/{slug}"
    links = description_links(snippet["description"],
                              {page, page.replace("://www.", "://"), post_url.rstrip("/")})

    entry = {
        "slug": slug,
        "title": snippet["title"],
        "topic": topic,
        "date": snippet["date"],
        "youtube_id": snippet["id"],
        "post_url": post_url or "REPLACE_ME",
        "post_label": "See the Bonus Video",
        "blurb": blurb,
        "links": links,
    }
    print("\nAdding this entry:\n" + json.dumps(entry, indent=2, ensure_ascii=False))
    if ask("\nLooks right? (y/n)", "y").lower() not in ("y", "yes"):
        sys.exit("Aborted — nothing written.")

    videos.append(entry)
    videos.sort(key=lambda v: v.get("date", ""), reverse=True)   # newest-first
    VIDEOS_JSON.write_text(json.dumps(videos, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(f"Wrote {VIDEOS_JSON.relative_to(ROOT)}.  Rebuilding…\n")
    subprocess.run([sys.executable, str(ROOT / "build.py")], check=True)
    print("\nDone. Preview: python3 -m http.server -d _site 8000")
    print("Then commit data/videos.json and push to deploy.")


if __name__ == "__main__":
    main()
