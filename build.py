#!/usr/bin/env python3
"""Ballpark Figures static-site generator.

Reads data/site.json + data/videos.json, renders templates/base.html into
static HTML at the repo root. No dependencies — just `python3 build.py`.

Add a video: append an entry to data/videos.json, then rerun this script and
commit. Fields with "REPLACE_ME" render as tidy placeholders until filled in.
"""
import html
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "_site"          # assembled site (gitignored; CI publishes this)
BASE_URL = "https://ballparkfigur.es"

YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

ICONS = {
    "youtube": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M23.5 6.2a3 3 0 0 0-2.1-2.1C19.6 3.6 12 3.6 12 3.6s-7.6 0-9.4.5A3 3 0 0 0 .5 6.2 31 31 0 0 0 0 12a31 31 0 0 0 .5 5.8 3 3 0 0 0 2.1 2.1c1.8.5 9.4.5 9.4.5s7.6 0 9.4-.5a3 3 0 0 0 2.1-2.1A31 31 0 0 0 24 12a31 31 0 0 0-.5-5.8zM9.6 15.6V8.4l6.4 3.6-6.4 3.6z"/></svg>',
    "substack": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M1.5 0h21v2.6h-21zM1.5 4.9h21v2.6h-21zM1.5 9.8v14.2l10.5-5.9 10.5 5.9V9.8z"/></svg>',
    "github": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 .5C5.7.5.5 5.7.5 12a11.5 11.5 0 0 0 7.9 10.9c.6.1.8-.2.8-.5v-1.7c-3.2.7-3.9-1.5-3.9-1.5-.5-1.3-1.3-1.7-1.3-1.7-1.1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1 1.8 2.8 1.3 3.5 1 .1-.8.4-1.3.7-1.6-2.6-.3-5.3-1.3-5.3-5.7 0-1.3.5-2.3 1.2-3.1-.1-.3-.5-1.5.1-3.1 0 0 1-.3 3.3 1.2a11.5 11.5 0 0 1 6 0C17 4.6 18 4.9 18 4.9c.6 1.6.2 2.8.1 3.1.8.8 1.2 1.8 1.2 3.1 0 4.4-2.7 5.4-5.3 5.7.4.4.8 1.1.8 2.2v3.3c0 .3.2.6.8.5A11.5 11.5 0 0 0 23.5 12C23.5 5.7 18.3.5 12 .5z"/></svg>',
    "email": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M22 4H2a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h20a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2zm0 4-10 6L2 8V6l10 6 10-6z"/></svg>',
}


def missing(value: str) -> bool:
    """True if a data field is empty or an unfilled REPLACE_ME placeholder."""
    return (not value) or str(value).strip().upper().startswith("REPLACE")


def esc(value: str) -> str:
    return html.escape(str(value), quote=True)


def fmt_date(value: str) -> str:
    try:
        d = datetime.strptime(value, "%Y-%m-%d")
    except (ValueError, TypeError):
        return ""
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def social_block(site: dict) -> str:
    email = site.get("email", "")
    items = [
        # key, label, href, opens_in_new_tab
        ("youtube", "YouTube", site.get("youtube_url", ""), True),
        ("substack", "Substack", site.get("substack_url", ""), True),
        ("github", "GitHub", site.get("github_url", ""), True),
        ("email", "Email", "" if missing(email) else f"mailto:{email}", False),
    ]
    out = []
    for key, label, href, new_tab in items:
        icon = ICONS[key]
        if missing(href):
            out.append(
                f'        <span style="display:flex;align-items:center;gap:.45rem;opacity:.45">{icon}<span>{label}</span></span>'
            )
        else:
            tab = ' target="_blank" rel="noopener"' if new_tab else ""
            out.append(
                f'        <a href="{esc(href)}"{tab}>{icon}<span>{label}</span></a>'
            )
    return "\n".join(out)


def render_page(base: str, site: dict, *, title: str, description: str,
                content: str, canonical: str, og_image: str,
                extra_head: str = "") -> str:
    tokens = {
        "title": esc(title),
        "description": esc(description),
        "name": esc(site["name"]),
        "canonical": esc(canonical),
        "og_image": esc(og_image),
        "social": social_block(site),
        "year": str(datetime.now(timezone.utc).year),
        "extra_head": extra_head,
        "content": content,  # already-built HTML, not escaped
    }
    page = base
    for key, value in tokens.items():
        page = page.replace("{{" + key + "}}", value)
    return page


def thumb_html(video: dict) -> str:
    vid = video.get("youtube_id", "")
    if YOUTUBE_ID_RE.match(vid or ""):
        return (f'<img class="thumb" loading="lazy" alt="" '
                f'src="https://img.youtube.com/vi/{vid}/hqdefault.jpg">')
    label = "Coming soon" if missing(video.get("title")) else esc(video["title"])
    return f'<div class="thumb placeholder">{label}</div>'


def card_html(video: dict) -> str:
    parts = [f'      <a class="card" href="/videos/{esc(video["slug"])}/">',
             f'        {thumb_html(video)}',
             '        <div class="card-body">',
             f'          <h3>{esc(video["title"])}</h3>']
    date = fmt_date(video.get("date", ""))
    if date:
        parts.append(f'          <div class="date">{date}</div>')
    if not missing(video.get("blurb")):
        parts.append(f'          <p>{esc(video["blurb"])}</p>')
    parts += ['        </div>', '      </a>']
    return "\n".join(parts)


def about_html(site: dict) -> str:
    cls = "about-text placeholder" if missing(site.get("about")) else "about-text"
    return f'<p class="{cls}">{esc(site["about"])}</p>'


def build_index(base, site, videos) -> str:
    cards = "\n".join(card_html(v) for v in videos) or \
        '      <p class="about-text">No videos yet — check back soon.</p>'
    content = f"""
    <section class="hero">
      <img src="/assets/logo.svg" alt="{esc(site['name'])} logo">
      <h1>{esc(site['name'])}</h1>
      <p>{esc(site['tagline'])}</p>
    </section>

    <section id="about">
      <div class="wrap">
        <h2 class="section-title">About</h2>
        {about_html(site)}
      </div>
    </section>

    <section id="videos">
      <div class="wrap">
        <h2 class="section-title">Videos</h2>
        <div class="grid">
{cards}
        </div>
      </div>
    </section>
"""
    return render_page(base, site, title=site["name"],
                       description=site["tagline"], content=content,
                       canonical=BASE_URL + "/",
                       og_image=BASE_URL + "/assets/logo.svg")


def build_about(base, site) -> str:
    content = f"""
    <section class="video-page">
      <div class="wrap">
        <h1>About</h1>
        {about_html(site)}
      </div>
    </section>
"""
    return render_page(base, site, title=f"About — {site['name']}",
                       description=f"About {site['name']}", content=content,
                       canonical=BASE_URL + "/about/",
                       og_image=BASE_URL + "/assets/logo.svg")


def build_video(base, site, video) -> str:
    vid = video.get("youtube_id", "")
    valid_vid = bool(YOUTUBE_ID_RE.match(vid or ""))
    if valid_vid:
        embed = (f'<div class="embed"><iframe loading="lazy" '
                 f'src="https://www.youtube.com/embed/{vid}" '
                 f'title="{esc(video["title"])}" allowfullscreen '
                 f'allow="accelerometer; autoplay; clipboard-write; encrypted-media; '
                 f'gyroscope; picture-in-picture"></iframe></div>')
        og_image = f"https://img.youtube.com/vi/{vid}/maxresdefault.jpg"
    else:
        embed = '<div class="embed placeholder"><span>Video coming soon</span></div>'
        og_image = BASE_URL + "/assets/logo.svg"

    sub = video.get("substack_url", "")
    if missing(sub):
        button = '<a class="btn disabled">Substack post coming soon</a>'
    else:
        button = f'<a class="btn" href="{esc(sub)}" target="_blank" rel="noopener">Read the Substack post →</a>'

    date = fmt_date(video.get("date", ""))
    date_html = f'<div class="date">{date}</div>' if date else ""
    desc_html = "" if missing(video.get("blurb")) else \
        f'<p class="desc">{esc(video["blurb"])}</p>'

    # Optional per-video interactive. Drop an HTML partial at
    # interactives/<slug>.html and it is injected below the video; matching
    # assets/interactives/<slug>.{css,js} auto-load (js as an ES module).
    slug = video["slug"]
    extra_head, interactive_html, js_tag = "", "", ""
    partial = ROOT / "interactives" / f"{slug}.html"
    if partial.exists():
        interactive_html = (
            '\n    <section class="interactive">\n      <div class="wrap">\n'
            + partial.read_text(encoding="utf-8").rstrip()
            + "\n      </div>\n    </section>"
        )
    if (ROOT / "assets" / "interactives" / f"{slug}.css").exists():
        extra_head = f'<link rel="stylesheet" href="/assets/interactives/{slug}.css">'
    if (ROOT / "assets" / "interactives" / f"{slug}.js").exists():
        js_tag = f'\n    <script type="module" src="/assets/interactives/{slug}.js"></script>'

    content = f"""
    <section class="video-page">
      <div class="wrap">
        <a class="back" href="/#videos">← All videos</a>
        <h1>{esc(video['title'])}</h1>
        {date_html}
        {embed}
        {desc_html}
        {button}
      </div>
    </section>{interactive_html}{js_tag}
"""
    return render_page(base, site, title=f"{video['title']} — {site['name']}",
                       description=video.get("blurb", site["tagline"]),
                       content=content, extra_head=extra_head,
                       canonical=f"{BASE_URL}/videos/{video['slug']}/",
                       og_image=og_image)


def build_404(base, site) -> str:
    content = """
    <section class="notfound">
      <h1>404</h1>
      <p>That page doesn't exist.</p>
      <p><a href="/">← Back home</a></p>
    </section>
"""
    return render_page(base, site, title=f"Not found — {site['name']}",
                       description="Page not found", content=content,
                       canonical=BASE_URL + "/404.html",
                       og_image=BASE_URL + "/assets/logo.svg")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)}")


def main() -> None:
    site = json.loads((ROOT / "data" / "site.json").read_text(encoding="utf-8"))
    videos = json.loads((ROOT / "data" / "videos.json").read_text(encoding="utf-8"))
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")

    print("Building site…")
    if OUT.exists():
        shutil.rmtree(OUT)
    write(OUT / "index.html", build_index(base, site, videos))
    write(OUT / "about" / "index.html", build_about(base, site))
    write(OUT / "404.html", build_404(base, site))
    for video in videos:
        write(OUT / "videos" / video["slug"] / "index.html",
              build_video(base, site, video))

    # Copy static files into the output as-is.
    shutil.copytree(ROOT / "assets", OUT / "assets")
    for name in ("CNAME", ".nojekyll"):
        shutil.copy(ROOT / name, OUT / name)
    print(f"  copied assets/, CNAME, .nojekyll")
    print(f"Done — {len(videos)} video page(s) → {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
