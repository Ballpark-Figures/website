# website

The Ballpark Figures website, served at **[ballparkfigur.es](https://ballparkfigur.es)**
via GitHub Pages.

A tiny **Python static-site generator** — no dependencies, no framework, no build
service. `build.py` reads the data files, fills the templates, and writes plain HTML
to the repo root, which GitHub Pages serves as-is (`.nojekyll`).

## Build

    python3 build.py

Writes `index.html`, `about/index.html`, `404.html`, and `videos/<slug>/index.html`.
Rerun after any edit, then commit the changed source **and** generated HTML.

## Edit content (no code)

- **`data/site.json`** — channel name, tagline, About text, email, and social links
  (YouTube / Substack / GitHub). Fields left as `REPLACE_ME` render as tidy
  placeholders (dimmed link / "coming soon") until you fill them.
- **`data/videos.json`** — one object per video:

      {
        "slug": "battleship",          // URL: /videos/battleship/
        "title": "…",
        "date": "2026-01-15",          // YYYY-MM-DD
        "youtube_id": "abcdefghijk",   // 11-char YouTube id → embed + thumbnail
        "substack_url": "https://…",   // "Read the Substack post →" button
        "blurb": "…"                   // shown on the card and the page
      }

  Add a video = append an entry, rerun `build.py`, commit.

## Interactives (per video)

Add an interactive demo to any video page by dropping files named by that video's
`slug` — see [`interactives/README.md`](interactives/README.md). In short:

- `interactives/<slug>.html` — markup, injected below the video
- `assets/interactives/<slug>.css` / `.js` — auto-loaded (js as an ES module)

Anything client-side works (vanilla JS, `<canvas>`, D3, or a widget bundled to
static JS). No generator changes needed.

## Layout

    build.py               generator (stdlib only)
    data/                  site.json, videos.json
    templates/base.html    page shell (header, footer, meta)
    assets/                style.css, logo.svg  (+ interactives/ for demos)
    interactives/          per-video HTML partials
    CNAME, .nojekyll       GitHub Pages: custom domain + serve raw files
    index.html, about/, videos/, 404.html   ← generated (committed)
