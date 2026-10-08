#!/usr/bin/env python3
"""Mimocozy store builder.  Usage:  python3 tools/build_books.py

Single source of truth: data/books.json
  1. assets/site.css      <- verbatim copy of the <style> block in index.html (book pages look identical)
  2. index.html           <- stamps each existing homepage card (matched by its data-t copy key) with
                             data-slug / data-status / data-themes, a title link and the "Explore Book" link,
                             and regenerates the theme filter pills.  Nothing else in index.html is touched.
  3. books/<slug>/index.html  <- one static page per book from tools/book-template.html
  4. sitemap.xml
  5. validation: every local src/href in index.html + generated pages must exist.
Standard library only.
"""
import html, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = json.load(open(os.path.join(ROOT, "data", "books.json"), encoding="utf-8"))
SITE = DATA["site"].rstrip("/")
BOOKS = DATA["books"]
BY_SLUG = {b["slug"]: b for b in BOOKS}
COLS, THEMES = DATA["collections"], DATA["themes"]
E = lambda s: html.escape(s or "", quote=True)

def T(pt, en, tag="span", cls="", extra=""):
    c = f' class="{cls}"' if cls else ""
    return f'<{tag}{c}{extra} data-pt="{E(pt)}" data-en="{E(en)}">{E(pt)}</{tag}>'

def local(p):  # strip cache-busting query
    return p.split("?")[0].split("#")[0]

def full_title(b, lang="en"):
    return b["title"] + (" — " + b["subtitle"][lang] if b.get("subtitle") else "")

def status_text(b):
    if b["status"] == "published":
        return "Disponível", "Available"
    r = b["release"]
    return "Em breve · " + r["pt"], "Coming soon · " + r["en"]

def img_tag(src, size, alt_pt, alt_en, prefix="../../", lazy=True, extra=""):
    wh = f' width="{size[0]}" height="{size[1]}"' if size else ""
    ld = ' loading="lazy" decoding="async"' if lazy else ' fetchpriority="high"'
    return (f'<img src="{E(prefix + src)}"{wh}{ld} alt="{E(alt_pt)}" data-i18n-attr="alt" '
            f'data-pt="{E(alt_pt)}" data-en="{E(alt_en)}"{extra} />')

# ---------------------------------------------------------------- related books
def related(b, n=4):
    out, seen = [], {b["slug"]}
    def add(x, why):
        if x["slug"] not in seen and len(out) < n:
            seen.add(x["slug"]); out.append((x, why))
    if b.get("series"):
        sib = sorted([x for x in BOOKS if x.get("series") == b["series"]], key=lambda x: x["seriesOrder"])
        o = b["seriesOrder"]
        for x in sib:
            if x["seriesOrder"] == o - 1: add(x, ("Parte anterior", "Previous part"))
        for x in sib:
            if x["seriesOrder"] == o + 1: add(x, ("Parte seguinte", "Next part"))
        for x in sib: add(x, ("Mesma série", "Same series"))
    idx = BOOKS.index(b)
    same = [x for x in BOOKS if x["collection"] == b["collection"]]
    same.sort(key=lambda x: (x["status"] != "published", abs(BOOKS.index(x) - idx)))
    for x in same: add(x, ("Mesma coleção", "Same collection"))
    sim = [x for x in BOOKS if set(x["themes"]) & set(b["themes"])]
    sim.sort(key=lambda x: (-len(set(x["themes"]) & set(b["themes"])), x["status"] != "published", abs(BOOKS.index(x) - idx)))
    for x in sim: add(x, ("Tema parecido", "Similar theme"))
    for x in BOOKS:
        if x["status"] == "published": add(x, ("Já disponível", "Available now"))
    return out

def long_paras(b):
    """'Discover the Story' text: a blank line in data/books.json starts a new paragraph (PT and EN must match)."""
    pt = [x.strip() for x in b["long"]["pt"].split("\n\n") if x.strip()]
    en = [x.strip() for x in b["long"]["en"].split("\n\n") if x.strip()]
    if len(pt) != len(en):
        sys.exit(f"{b['slug']}: long.pt has {len(pt)} paragraphs but long.en has {len(en)}")
    return "".join(f'<p data-pt="{E(a)}" data-en="{E(c)}"{" style=\"margin-top:10px\"" if i else ""}>{E(a)}</p>' for i, (a, c) in enumerate(zip(pt, en)))

def cover_or_placeholder(x, prefix, lazy=True):
    if x.get("cover"):
        return img_tag(x["cover"], x.get("coverSize"), x["coverAlt"], x["coverAlt"], prefix, lazy)
    return f'<div class="cover-ph" role="img" aria-label="{E(x["title"])}">{E(x["title"])}</div>'

# ---------------------------------------------------------------- book page
def render_page(b, tpl):
    col = COLS[b["collection"]]
    spt, sen = status_text(b)
    url = f"{SITE}/books/{b['slug']}/"
    og_img = SITE + "/" + local(b["cover"]) if b.get("cover") else SITE + "/og.jpg"
    meta_desc = b["short"]["en"]
    if b["status"] != "published":
        meta_desc += " Coming soon (" + b["release"]["en"] + ")."
    title_en = full_title(b, "en")
    amazon = b.get("amazon")
    pub = b["status"] == "published" and amazon

    sub = (f'<p class="lede">{T(b["subtitle"]["pt"], b["subtitle"]["en"])}</p>' if b.get("subtitle") else "")
    facts = []
    if b.get("format"): facts.append(T(b["format"]["pt"], b["format"]["en"]))
    if b.get("pages"): facts.append(T(f'{b["pages"]} páginas', f'{b["pages"]} pages'))
    if b.get("ages"): facts.append(T(b["ages"]["pt"], b["ages"]["en"]))
    facts_block = f'<div class="perks">{"".join(facts)}</div>' if facts else ""

    if pub:
        cta = (f'<a class="btn" href="{E(amazon)}" target="_blank" rel="noopener" data-pt="Comprar na Amazon →" data-en="Buy on Amazon →">Comprar na Amazon →</a>'
               f'<a class="btn soft" href="#peek" data-pt="Espreitar o interior ↓" data-en="Take a peek inside ↓">Espreitar o interior ↓</a>')
    else:
        cta = (T(spt, sen, "span", "pill")
               + '<a class="btn soft" href="#peek" data-pt="Espreitar o interior ↓" data-en="Take a peek inside ↓">Espreitar o interior ↓</a>')

    # gallery: cover + slides + other interior images that exist in the repo
    gal = []
    if b.get("cover"):
        gal.append((b["cover"], b.get("coverSize"), f'{full_title(b,"pt")} — capa', f'{title_en} — cover'))
    for i, s in enumerate(b["slides"] + b["interior"], 1):
        gal.append((s["src"], s["size"], f'{full_title(b,"pt")} — página do interior {i}', f'{title_en} — inside page {i}'))
    if b.get("cover"):
        hero_cover = (f'<button type="button" id="cover-btn" data-i18n-attr="aria-label" data-pt="Ampliar capa" data-en="Enlarge cover" aria-label="Ampliar capa">'
                      + img_tag(b["cover"], b.get("coverSize"), b["coverAlt"], b["coverAlt"], lazy=False) + '</button>')
    else:
        hero_cover = cover_or_placeholder(b, "../../")
    if gal:
        thumbs = "".join(
            f'<button type="button" data-gallery-index="{i}" data-full="{E("../../" + src)}" aria-current="{str(i == 0).lower()}">'
            + img_tag(src, size, apt, aen) + '</button>' for i, (src, size, apt, aen) in enumerate(gal))
        src, size, apt, aen = gal[0]
        peek = f'''<section id="peek">
      <h2 data-pt="Espreita o interior" data-en="Take a Peek Inside">Espreita o interior</h2>
      <p class="sub" data-pt="Toca numa imagem para a ver em grande. Usa as setas ou desliza para mudar." data-en="Tap an image to see it large. Use the arrows or swipe to browse.">Toca numa imagem para a ver em grande. Usa as setas ou desliza para mudar.</p>
      <div class="g-wrap">
        <div class="g-main"><button type="button" id="g-main-btn" data-i18n-attr="aria-label" data-pt="Ver imagem em grande" data-en="View image large" aria-label="Ver imagem em grande">{img_tag(src, size, apt, aen, extra=' id="g-main-img"')}</button></div>
        <div class="peeks bk-thumbs">{thumbs}</div>
      </div>
    </section>'''
    else:
        peek = ('<section id="peek"><h2 data-pt="Espreita o interior" data-en="Take a Peek Inside">Espreita o interior</h2>'
                '<p class="sub" data-pt="As imagens deste livro chegam em breve." data-en="Images for this book are coming soon.">As imagens deste livro chegam em breve.</p></section>')

    # C. Bring Your Pages to Life: shown only when the book has real coloured examples.
    # data/books.json -> "colorExamples": [{"lineart": {"src", "size"}, "colored": {"src", "size"}}, ...]
    color = ""
    pairs = b.get("colorExamples") or []
    for n, c in enumerate(pairs, 1):
        if not (isinstance(c, dict) and c.get("lineart", {}).get("src") and c.get("colored", {}).get("src")):
            sys.exit(f"{b['slug']}: colorExamples[{n}] must be {{'lineart': {{'src','size'}}, 'colored': {{'src','size'}}}}")
    if pairs:
        tpt, ten = full_title(b, "pt"), title_en
        cells = "".join(
            '<div class="cx-pair">'
            f'<figure>{img_tag(c["lineart"]["src"], c["lineart"].get("size"), f"{tpt} — página original {n}, a preto e branco", f"{ten} — original page {n}, black and white")}'
            '<figcaption data-pt="Página original" data-en="Original page">Página original</figcaption></figure>'
            f'<figure>{img_tag(c["colored"]["src"], c["colored"].get("size"), f"{tpt} — exemplo de pintura {n}", f"{ten} — coloring example {n}")}'
            '<figcaption data-pt="Exemplo de pintura" data-en="Coloring example">Exemplo de pintura</figcaption></figure>'
            '</div>' for n, c in enumerate(pairs, 1))
        color = f'''<section id="colors">
      <h2 data-pt="Dá vida às tuas páginas" data-en="Bring Your Pages to Life">Dá vida às tuas páginas</h2>
      <p class="sub" data-pt="Exemplos de pintura: a mesma página do livro, antes e depois de colorida. O livro traz as páginas a preto e branco." data-en="Coloring examples: the same page from the book, before and after coloring. The book contains the black-and-white pages.">Exemplos de pintura: a mesma página do livro, antes e depois de colorida. O livro traz as páginas a preto e branco.</p>
      <div class="cx-grid">{cells}</div>
    </section>'''

    series_block = ""
    if b.get("series"):
        sib = sorted([x for x in BOOKS if x.get("series") == b["series"]], key=lambda x: x["seriesOrder"])
        items = []
        for x in sib:
            xs_pt, xs_en = status_text(x)
            label_pt = full_title(x, "pt"); label_en = full_title(x, "en")
            if x is b:
                items.append(f'<li><strong>{T(label_pt, label_en)}</strong> {T("(este livro)", "(this book)")}</li>')
            else:
                items.append(f'<li><a href="../{x["slug"]}/" style="text-decoration:underline">{T(label_pt, label_en)}</a> · {T(xs_pt, xs_en)}</li>')
        series_block = (f'<article><h3 data-pt="Nesta série" data-en="In this series">Nesta série</h3>'
                        f'<ul style="margin:0;padding-left:18px;color:var(--muted);line-height:1.8">{"".join(items)}</ul></article>')

    rows = [("Título", "Title", E(b["title"]))]
    if b.get("subtitle"): rows.append(("Volume", "Volume", T(b["subtitle"]["pt"], b["subtitle"]["en"])))
    rows.append(("Coleção", "Collection", T(col["pt"], col["en"])))
    rows.append(("Temas", "Themes", T(", ".join(THEMES[t]["pt"] for t in b["themes"]), ", ".join(THEMES[t]["en"] for t in b["themes"]))))
    rows.append(("Tipo", "Type", T("Livro para colorir", "Coloring book")))
    if b.get("format"): rows.append(("Formato", "Format", T(b["format"]["pt"], b["format"]["en"])))
    if b.get("pages"): rows.append(("Páginas", "Pages", str(b["pages"])))
    if b.get("ages"): rows.append(("Idade", "Ages", T(b["ages"]["pt"], b["ages"]["en"])))
    if pub:
        rows.append(("Disponibilidade", "Availability", f'<a href="{E(amazon)}" target="_blank" rel="noopener" style="text-decoration:underline">{T("Disponível na Amazon", "Available on Amazon")}</a>'))
    else:
        rows.append(("Disponibilidade", "Availability", T("Em breve", "Coming soon")))
        rows.append(("Lançamento", "Release", T(b["release"]["pt"], b["release"]["en"])))
    details = "".join(f'<dt data-pt="{p}" data-en="{e}">{p}</dt><dd>{v}</dd>' for p, e, v in rows)

    cards = []
    for x, why in related(b):
        xs_pt, xs_en = status_text(x)
        href = f"../{x['slug']}/"
        sub_x = f'<p class="sub" style="margin:0 0 4px;font-weight:800">{T(x["subtitle"]["pt"], x["subtitle"]["en"])}</p>' if x.get("subtitle") else ""
        cards.append(f'''<article class="book">
          <div class="carousel"><a href="{href}" tabindex="-1" aria-hidden="true">{cover_or_placeholder(x, "../../")}</a></div>
          <div><span class="pill" style="margin-bottom:6px" data-pt="{E(why[0])}" data-en="{E(why[1])}">{E(why[0])}</span><h3><a href="{href}">{E(x["title"])}</a></h3>{sub_x}{T(x["short"]["pt"], x["short"]["en"], "p")}
          <div class="acts">{T(xs_pt, xs_en, "span", "pill")}<a class="btn soft" href="{href}" data-pt="Explorar livro →" data-en="Explore Book →">Explorar livro →</a></div></div>
        </article>''')

    buy = ""
    if pub:
        buy = f'''<section class="letter">
      <div><strong>{E(full_title(b, "pt"))}</strong><div class="sub" data-pt="Disponível na Amazon. Pega nos lápis e começa a colorir." data-en="Available on Amazon. Grab your pencils and start coloring.">Disponível na Amazon. Pega nos lápis e começa a colorir.</div></div>
      <a class="btn" href="{E(amazon)}" target="_blank" rel="noopener" data-pt="Comprar na Amazon →" data-en="Buy on Amazon →">Comprar na Amazon →</a>
    </section>'''

    ld = {"@context": "https://schema.org", "@type": "Book", "name": title_en, "url": url,
          "description": b["short"]["en"], "image": og_img, "genre": "Coloring book"}
    # (no "brand": it is not a schema.org property of Book; no author/offers: not stated on the site / no prices)
    if b.get("pages"): ld["numberOfPages"] = b["pages"]
    if pub: ld["sameAs"] = amazon

    rep = {
        "page_title": E(f"{title_en} | Mimocozy"), "meta_description": E(meta_desc), "canonical": url,
        "og_title": E(f"{title_en} — Mimocozy"), "og_image": E(og_img),
        "jsonld": json.dumps(ld, ensure_ascii=False).replace("</", "<\\/"),
        "collection_key": b["collection"], "collection_pt": E(col["pt"]), "collection_en": E(col["en"]),
        "title_html": E(b["title"]), "title_attr": E(title_en),
        "status_pt": E(spt), "status_en": E(sen), "subtitle_block": sub,
        "short_pt": E(b["short"]["pt"]), "short_en": E(b["short"]["en"]),
        "long_pt": E(b["long"]["pt"]), "long_en": E(b["long"]["en"]),
        "long_paras": long_paras(b),
        "collection_blurb_pt": E(col["blurb"]["pt"]), "collection_blurb_en": E(col["blurb"]["en"]),
        "facts_block": facts_block, "hero_cta": cta, "hero_cover": hero_cover,
        "peek_section": peek, "color_section": color, "series_block": series_block,
        "details_rows": details, "related_cards": "\n        ".join(cards), "buy_band": buy,
    }
    out = re.sub(r"\{\{(\w+)\}\}", lambda m: rep[m.group(1)], tpl)
    left = re.findall(r"\{\{\w+\}\}", out)
    assert not left, left
    return out

# ---------------------------------------------------------------- homepage stamping
FEATURED_UPCOMING = 4  # how many upcoming releases the homepage features (the rest sit under "See all upcoming releases")

def lisbon_today():
    import datetime
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo("Europe/Lisbon")).date().isoformat()
    except Exception:
        return datetime.date.today().isoformat()

def next_releases():
    """Slugs of the FEATURED_UPCOMING nearest upcoming books whose release date is today or later (Europe/Lisbon)."""
    today = lisbon_today()
    up = []
    for b in BOOKS:
        if b["status"] == "published":
            continue
        d = (b.get("release") or {}).get("date", "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d or ""):
            sys.exit(f"{b['slug']}: release.date must be YYYY-MM-DD (got {d!r})")
        if d >= today:
            up.append((d, BOOKS.index(b), b["slug"]))
    return {slug for _, _, slug in sorted(up)[:FEATURED_UPCOMING]}

def stamp_homepage():
    p = os.path.join(ROOT, "index.html")
    s = open(p, encoding="utf-8").read()
    css = re.search(r"<style>\n(.*?)\n  </style>", s, re.S).group(1)
    css = "\n".join(l[4:] if l.startswith("    ") else l for l in css.split("\n"))
    open(os.path.join(ROOT, "assets", "site.css"), "w", encoding="utf-8").write(
        "/* AUTO-GENERATED by tools/build_books.py: verbatim copy of the <style> block in index.html.\n"
        "   Edit index.html, not this file. Book pages load this + assets/book.css. */\n" + css + "\n")
    next_up = next_releases()
    for b in BOOKS:
        key = b["legacyCopyKey"]
        pat = re.compile(r'<article class="book"[^>]*>(?:(?!</article>).)*?data-t="' + key + r'"(?:(?!</article>).)*?</article>', re.S)
        m = pat.search(s)
        if not m:
            sys.exit(f"homepage card for {b['slug']} (copy key {key}) not found")
        a = m.group(0)
        head = re.match(r'<article class="book"[^>]*>', a).group(0)
        soon = b["status"] != "published"
        strip = r'\s+data-(slug|status|themes|theme-names|date|feat)="[^"]*"' if soon else r'\s+data-(slug|status|themes|theme-names)="[^"]*"'
        new_head = re.sub(strip, "", head)
        names = " ".join(THEMES[t]["pt"] + " " + THEMES[t]["en"] for t in b["themes"])
        # upcoming cards: data-date (YYYY-MM-DD) drives the automatic "next 4 releases" rotation in index.html;
        # data-feat="1" on the 4 nearest future releases at build time is the no-JS fallback.
        upc = (f' data-date="{b["release"]["date"]}"' + (' data-feat="1"' if b["slug"] in next_up else "")) if soon else ""
        new_head = new_head[:-1] + (f' data-slug="{b["slug"]}" data-status="{"published" if b["status"] == "published" else "soon"}"'
                                    f' data-themes="{" ".join(b["themes"])}" data-theme-names="{E(names.lower())}"{upc}>')
        a2 = a.replace(head, new_head, 1)
        a2 = re.sub(r'<h3>(?:<a href="books/[^"]*/">)?(.*?)(?:</a>)?</h3>', lambda mm: f'<h3><a href="books/{b["slug"]}/">{mm.group(1)}</a></h3>', a2, count=1)
        a2 = re.sub(r' <a class="btn soft" data-explore[^>]*>.*?</a>', "", a2)
        i = a2.rfind("</div>")
        a2 = a2[:i] + f' <a class="btn soft" data-explore href="books/{b["slug"]}/" data-t="explorebook">Explore Book →</a>' + a2[i:]
        if b.get("amazon") and b["amazon"] not in a2:
            sys.exit(f"Amazon link mismatch for {b['slug']}")
        if b.get("card"):
            a2 = re.sub(r'(<p data-t="' + key + r'">)[^<]*(</p>)', lambda mm: mm.group(1) + E(b["card"]["en"]) + mm.group(2), a2, count=1)
        s = s.replace(a, a2, 1)
        if b.get("card"):
            for lang in ("pt", "en"):
                line = re.search(r"\n      " + lang + r": \{.*\n", s).group(0)
                val = json.dumps(b["card"][lang], ensure_ascii=False)
                new, n = re.subn(r'((?:\{|, ) ?)' + key + r':"(?:[^"\\]|\\.)*"', lambda mm: mm.group(1) + key + ":" + val, line, count=1)
                if n != 1:
                    sys.exit(f"copy key {key} not found in the {lang} dictionary")
                s = s.replace(line, new, 1)
    used = [t for t in THEMES if any(t in b["themes"] for b in BOOKS)]
    pills = ['<button class="pill" type="button" data-theme="all" aria-pressed="true" data-t="fthall">All themes</button>']
    pills += [f'<button class="pill" type="button" data-theme="{t}" aria-pressed="false" data-pt="{E(THEMES[t]["pt"])}" data-en="{E(THEMES[t]["en"])}">{E(THEMES[t]["en"])}</button>' for t in used]
    s = re.sub(r"(<!-- THEME-FILTERS:START[^>]*-->).*?(\s*<!-- THEME-FILTERS:END -->)",
               lambda m: m.group(1) + "\n        " + "\n        ".join(pills) + m.group(2), s, flags=re.S)
    open(p, "w", encoding="utf-8").write(s)

# ---------------------------------------------------------------- validation
# Images for "The Letter the Tide Kept" were added on 2026-10-08, so nothing is known-missing any more.
KNOWN_MISSING = set()

def check_refs(files):
    bad = []
    for f in files:
        s = open(f, encoding="utf-8").read()
        refs = re.findall(r'(?:src|href|data-full)="([^"]+)"', s)
        refs += [r for v in re.findall(r'data-imgs="([^"]+)"', s) for r in v.split(",")]
        for r in refs:
            r = html.unescape(r.strip())
            if re.match(r"^(https?:|mailto:|#|data:)", r) or not r:
                continue
            path = os.path.normpath(os.path.join(os.path.dirname(f), local(r)))
            if os.path.isdir(path): path = os.path.join(path, "index.html")
            if not os.path.isfile(path) and local(r) not in KNOWN_MISSING:
                bad.append((os.path.relpath(f, ROOT), r))
    return bad

def lastmod(rel):
    """Real last-change date of a page for sitemap.xml: today if the file differs from the last
    commit (it is about to be committed), otherwise the date of the last commit that touched it."""
    import datetime, subprocess
    run = lambda *a: subprocess.run(["git", "-C", ROOT, *a], capture_output=True, text=True)
    if run("diff", "--quiet", "HEAD", "--", rel).returncode != 0 or not run("ls-files", rel).stdout.strip():
        return datetime.date.today().isoformat()
    return run("log", "-1", "--format=%cs", "--", rel).stdout.strip() or datetime.date.today().isoformat()

def main():
    stamp_homepage()
    tpl = open(os.path.join(ROOT, "tools", "book-template.html"), encoding="utf-8").read()
    files = [os.path.join(ROOT, "index.html")]
    for b in BOOKS:
        d = os.path.join(ROOT, "books", b["slug"]); os.makedirs(d, exist_ok=True)
        f = os.path.join(d, "index.html")
        open(f, "w", encoding="utf-8").write(render_page(b, tpl)); files.append(f)
    entries = [(SITE + "/", "index.html")] + [(f"{SITE}/books/{b['slug']}/", f"books/{b['slug']}/index.html") for b in BOOKS]
    open(os.path.join(ROOT, "sitemap.xml"), "w").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc><lastmod>{lastmod(f)}</lastmod></url>\n" for u, f in entries) + "</urlset>\n")
    bad = check_refs(files)
    print(f"built {len(BOOKS)} book pages; checked {len(files)} html files")
    if bad:
        print("MISSING local references:")
        for f, r in bad: print("  ", f, "->", r)
        sys.exit(1)
    print("all local references exist")

if __name__ == "__main__":
    main()
