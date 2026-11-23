# Local third-party assets

Runtime templates reference these local files so the event pages do not depend on a CDN connection. The URLs below are documented recovery sources only; they are not loaded by the pages.

| Local file | Version | Source / documented fallback |
| --- | --- | --- |
| `tailwind-browser.js` | Tailwind CSS browser / Play CDN 4.3.5 | [Tailwind Play CDN](https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4.3.5/dist/index.global.js) |
| `animate.min.css` | animate.css 4.1.1 | [animate.css 4.1.1](https://cdn.jsdelivr.net/npm/animate.css@4.1.1/animate.min.css) |
| `gsap.min.js` | GSAP 3.15.0 | [GSAP 3.15.0](https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js) |
| `confetti.browser.min.js` | canvas-confetti 1.9.4 | [canvas-confetti 1.9.4](https://cdn.jsdelivr.net/npm/canvas-confetti@1.9.4/dist/confetti.browser.min.js) |
| `fonts/*.ttf` | Baloo 2 400/700; Mountains of Christmas 400/700 | [Baloo 2](https://fonts.google.com/specimen/Baloo+2), [Mountains of Christmas](https://fonts.google.com/specimen/Mountains+of+Christmas) |

Keep the existing vendor filenames when refreshing assets; the templates load these paths directly. Verify the upstream license before redistributing any updated vendor asset.
