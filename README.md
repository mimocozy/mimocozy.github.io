# Creative Pages Coloring

Landing page for Seoul Between Scenes.

## Store (loja-mimocozy)

- `data/books.json` — single source of truth for every book (text copied verbatim from the site copy).
- `python3 tools/build_books.py` — regenerates `books/<slug>/index.html` (one static page per book, from
  `tools/book-template.html`), stamps the homepage cards with their "Explore Book" link and filter data,
  regenerates the theme filter pills, syncs `assets/site.css` from the `<style>` in `index.html`,
  writes `sitemap.xml` and checks that every local image/link exists.
- `assets/mimocozy.js` — shared PT/EN memory (localStorage) + book-page gallery/lightbox. `assets/book.css` — book-page extras.
