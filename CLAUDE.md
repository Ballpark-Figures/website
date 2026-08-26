# website — working rules

The shared conventions load via the two imports below — the same wiring the video
repos and the `analytics`/`notion` service repos use. `CLAUDE.shared.md` and
`CLAUDE.private.md` are **real files in this repo** — gitignored copies of
`bpkfigures/CLAUDE.md` and `dotclaude/CLAUDE.md`, refreshed at every session start
by `dotclaude/hooks/refresh-claude-imports.py`. They cannot be symlinks: a CLAUDE.md
`@import` will not resolve to a target outside the project directory, by any route.

@CLAUDE.shared.md
@CLAUDE.private.md

> **Import canary — check this first.** If you cannot see the tokens
> `SHARED-RULES-LOADED` and `PRIVATE-RULES-LOADED` in your context, the imports
> above **silently failed** and you are missing every shared and private
> convention. The copies are machine-local and gitignored, so the usual cause is a
> repo where they were never created — a fresh clone that has not had `/sync-videos`
> run in it, so `.claude/settings.local.json` (and therefore the refreshing hook)
> does not exist yet. Recover by reading `bpkfigures/CLAUDE.md` and
> `dotclaude/CLAUDE.md` directly for this session, then regenerate the copies with
> `python3 ../../dotclaude/hooks/refresh-claude-imports.py .` and tell the user to
> run `/sync-videos`.
>
> Do **not** trust a hook that claims to inject the rules as context: a
> SessionStart hook emitting the full ~121KB gets capped by the harness, saved to a
> file, and replaced with a ~2KB preview — which contains `SHARED-RULES-LOADED` and
> so reads as success while almost everything is missing. The tokens only mean
> anything when they come from the imports.

This is **not** a video repo. The GENERAL working rules from `bpkfigures/CLAUDE.md`
apply here (following instructions, disagreeing-vs-silently-overriding, recording
decisions in a CLAUDE.md instead of empty promises, the git / concurrent-branch /
allowlist-friendly-shell conventions, where instructions live). Its VIDEO-specific
conventions — scenes, subscenes, manim, the `render` script, solvers, "never invent
a calculation" — do NOT apply to a static website; ignore those. **This repo is
PUBLIC**, so never write the user's real name or any private identifier into a
tracked file here (see the shared rule). Read `README.md` first.

## What this repo is
- The Ballpark Figures website at **[ballparkfigur.es](https://ballparkfigur.es)** —
  a tiny **stdlib-only** Python static-site generator. `build.py` reads the data
  files, fills the templates, and assembles plain HTML into `_site/`.
- **Commit SOURCE only, never the generated `_site/`** (it's gitignored). On every
  push to `main`, **Cloudflare Pages** (git-connected) runs `build.py` and publishes
  `_site/`.
- Build + preview: `python3 build.py` then `python3 -m http.server -d _site 8000`.

## Content lives in `data/` (edit these, then rerun `build.py`)
- `data/site.json` — channel name, tagline, About, email, social links. `REPLACE_ME`
  fields render as tidy placeholders until filled.
- `data/videos.json` — one object per video (`slug`, `title`, `topic`, `date`,
  `youtube_id`, `substack_url`, `blurb`). Add a video = append an entry, rerun,
  commit.
- Per-video interactives: `interactives/<slug>.html` +
  `assets/interactives/<slug>.{css,js}` (see `interactives/README.md`).
