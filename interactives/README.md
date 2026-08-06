# interactives/

Drop an HTML partial here named `<slug>.html` (matching a video's `slug` in
`data/videos.json`) and `build.py` injects it into that video's page, in a
full-width section below the embedded video.

Auto-loaded companions (optional), by the same slug:

- `assets/interactives/<slug>.css` → linked in that page's `<head>`
- `assets/interactives/<slug>.js`  → loaded at end of body as an ES module
  (`<script type="module">`), so you can `import` and use top-level modern JS.

The partial is raw HTML — put your `<div id="...">`, `<canvas>`, controls, etc.
here; wire them up from the JS file. Anything client-side works (vanilla JS,
`<canvas>`, D3, three.js, or a widget compiled to static JS with your own
bundler — just output the built files into `assets/interactives/`).

Example — for a video with `"slug": "battleship"`:

    interactives/battleship.html          <- markup (a <div>, a <canvas>, buttons)
    assets/interactives/battleship.css    <- its styles (optional)
    assets/interactives/battleship.js     <- its behavior (optional, ES module)

Then rerun `python3 build.py`.
