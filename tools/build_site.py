"""Build the small static catalog from editable article and product content."""
import base64
import hashlib
import json
import posixpath
from datetime import date
from html import escape as html_escape
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from lxml import html

PROJECT = Path(__file__).resolve().parents[1]
SITE = PROJECT / "public-site" if (PROJECT / "public-site").exists() else PROJECT
CONTENT = PROJECT / "site-content"
BASE = "https://shumelyakam.github.io/lichnaya-ustoychivost/"
articles = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((CONTENT / "articles").glob("*.json"))]
products = [p for p in json.loads((CONTENT / "products.json").read_text(encoding="utf-8")) if p.get("visible")]
MONTHS = ("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря")


def display_date(value):
    day = date.fromisoformat(value)
    return f"{day.day} {MONTHS[day.month - 1]} {day.year}"


def esc(value):
    return html_escape(str(value), quote=True)


def fragment(markup):
    return html.fragment_fromstring(markup, create_parent="div")


def replace_children(node, markup):
    node.text = None
    for child in list(node):
        node.remove(child)
    wrapper = fragment(markup)
    for child in wrapper:
        node.append(child)


def href_from(rel, target):
    return posixpath.relpath(target, posixpath.dirname(rel) or ".")


def canonical(rel):
    if rel == "index.html":
        return BASE
    return BASE + (rel[:-10] if rel.endswith("index.html") else rel)


def page_for(product):
    landing = product.get("landing")
    return "index.html" if landing == "/" else landing.lstrip("/") if landing else f"hub/products/{product['slug']}/index.html"


def shell(tree, rel):
    head = tree.find("head")
    body = tree.find("body")
    for style_node in head.xpath("./style"):
        if style_node.text:
            style_node.text = style_node.text.replace(".ttf", ".woff2").replace('format("truetype")', 'format("woff2")')
            if rel == "zapis/index.html":
                style_node.text = style_node.text.replace(BASE + "hub/assets/fonts/", href_from(rel, "hub/assets/fonts/") + "/")
    for node in body.xpath("./header|./footer|./div[contains(concat(' ',normalize-space(@class),' '),' topbar ') or contains(concat(' ',normalize-space(@class),' '),' site-topbar ') or contains(concat(' ',normalize-space(@class),' '),' topline ')]|./a[contains(concat(' ',normalize-space(@class),' '),' skip ') or contains(concat(' ',normalize-space(@class),' '),' skip-link ') or contains(concat(' ',normalize-space(@class),' '),' site-skip ')]"):
        body.remove(node)
    links = [
        ("Главная", "hub/index.html"),
        ("Продукты", "hub/shop/index.html"),
        ("Блог", "hub/blog/index.html"),
        ("Личная устойчивость", "index.html"),
    ]
    def nav_links():
        return "".join(f'<a href="{href_from(rel, target)}"{ " aria-current=" + chr(34) + "page" + chr(34) if rel == target else ""}>{esc(label)}</a>' for label, target in links)
    header = fragment(f'''<div class="site-topbar">Наблюдение → Выбор → Действие</div>
      <header class="site-header"><div class="site-header-inner">
        <a class="site-brand" href="{href_from(rel, 'hub/index.html')}"><span class="site-brand-mark" aria-hidden="true"><i></i><i></i><i></i></span><span><strong>Андрей Шумеляк</strong><small>Практика личной устойчивости</small></span></a>
        <nav class="site-nav" aria-label="Основная навигация">{nav_links()}</nav>
        <a class="site-header-cta" href="{href_from(rel, 'zapis/index.html')}">Запись</a>
        <details class="site-mobile-menu"><summary>Меню</summary><nav aria-label="Мобильная навигация">{nav_links()}<a href="{href_from(rel, 'zapis/index.html')}">Запись</a></nav></details>
      </div></header>''')
    skip = html.fromstring('<a class="site-skip" href="#main">К содержанию</a>')
    body.insert(0, skip)
    for offset, child in enumerate(header, 1):
        body.insert(offset, child)
    footer = html.fromstring(f'''<footer class="site-footer"><div class="site-footer-inner"><div><strong>Андрей Шумеляк</strong><p>Спокойная ясность и посильные действия.</p></div><nav aria-label="Навигация внизу страницы">{nav_links()}<a href="{href_from(rel, 'zapis/index.html')}">Запись</a></nav><p class="site-disclaimer">Образовательные материалы. Не заменяют диагностику или лечение.</p></div></footer>''')
    body.append(footer)
    for node in head.xpath("./html|./link[@rel='canonical']|./link[@data-site-shell]|./meta[starts-with(@property,'og:')]"):
        head.remove(node)
    head.append(html.Element("link", rel="canonical", href=canonical(rel)))
    head.append(html.Element("link", rel="stylesheet", **{"data-site-shell": "true", "href": href_from(rel, "hub/assets/site-shell.css")}))
    title = head.xpath("./title")
    description = head.xpath("./meta[@name='description']")
    for property_name, content in [("og:type", "article" if "/blog/" in rel and rel != "hub/blog/index.html" else "website"), ("og:title", title[0].text if title else ""), ("og:description", description[0].get("content") if description else ""), ("og:url", canonical(rel))]:
        node = html.Element("meta", property=property_name, content=content)
        head.append(node)
    for node in body.xpath(".//span[@aria-hidden='true' and (normalize-space(.)='↗' or normalize-space(.)='→')]"):
        node.getparent().remove(node)
    for node in body.xpath(".//a|.//button"):
        if node.text and node.text.rstrip().endswith("↗"):
            node.text = node.text.rstrip().removesuffix("↗").rstrip()
    csp = head.xpath("./meta[@http-equiv='Content-Security-Policy']")
    if csp:
        policy = csp[0].get("content")
        if rel == "zapis/index.html":
            policy = policy.replace("font-src https://shumelyakam.github.io", "font-src 'self'")
        style_node = head.xpath("./style")
        if style_node:
            digest = base64.b64encode(hashlib.sha256((style_node[0].text or "").encode()).digest()).decode()
            import re
            policy = re.sub(r"style-src [^;]+", f"style-src 'self' 'sha256-{digest}'", policy)
        scripts = head.xpath("./script") + body.xpath("./script[not(@src)]")
        if scripts:
            digest = base64.b64encode(hashlib.sha256((scripts[0].text or "").encode()).digest()).decode()
            policy = re.sub(r"script-src [^;]+", f"script-src 'sha256-{digest}'", policy)
        csp[0].set("content", policy)
    return tree


def save(tree, rel):
    path = SITE / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<!doctype html>\n" + html.tostring(tree, encoding="unicode", method="html"), encoding="utf-8")


def article_page(item):
    rel = f"hub/blog/{item['slug']}.html"
    path = SITE / rel
    template = path if path.exists() else SITE / "hub/blog/rezim-kak-opora.html"
    tree = html.fromstring(template.read_text(encoding="utf-8"))
    head = tree.find("head")
    head.xpath("./title")[0].text = f"{item['title']} | Андрей Шумеляк"
    head.xpath("./meta[@name='description']")[0].set("content", item["description"])
    article = tree.xpath("//main/article")[0]
    article.xpath(".//h1")[0].text = item["title"]
    article.xpath(".//p[contains(@class,'eyebrow')]")[0].text = item["eyebrow"]
    article.xpath(".//p[contains(@class,'standfirst')]")[0].text = item["lead"]
    article.xpath(".//div[contains(@class,'article-meta')]")[0].text = f"Андрей Шумеляк · {display_date(item['date_iso'])}"
    replace_children(article.xpath(".//div[contains(@class,'article-body')]")[0], item["body"])
    ending = article.xpath(".//div[contains(@class,'article-end')]")[0]
    product = next((p for p in products if p["slug"] == item.get("product")), products[0])
    related = [a for a in articles if a["slug"] != item["slug"] and a["category"] == item["category"]][:2]
    if not related:
        related = [a for a in articles if a["slug"] != item["slug"]][:2]
    related_links = "".join(f'<a href="{esc(a["slug"])}.html">{esc(a["title"])}</a>' for a in related)
    replace_children(ending, f'''<p>Материал образовательный и не заменяет помощь специалиста при состоянии, которое мешает повседневной жизни.</p><a class="button" href="{href_from(rel, page_for(product))}">Посмотреть программу</a><div class="related-reading"><h2>Читайте также</h2>{related_links}</div>''')
    for node in head.xpath("./script[@type='application/ld+json']"):
        head.remove(node)
    schema = {"@context": "https://schema.org", "@type": "BlogPosting", "headline": item["title"], "description": item["description"], "datePublished": item["date_iso"], "author": {"@type": "Person", "name": "Андрей Шумеляк"}, "mainEntityOfPage": canonical(rel)}
    script = html.Element("script", type="application/ld+json")
    script.text = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
    head.append(script)
    save(shell(tree, rel), rel)


def card(item, rel):
    return f'''<a class="card" href="{href_from(rel, 'hub/blog/' + item['slug'] + '.html')}"><div class="card-top"><span class="card-type">{esc(item['category'])}</span></div><h3>{esc(item['title'])}</h3><p>{esc(item['description'])}</p><div class="card-foot">Читать статью</div></a>'''


def catalogs():
    rel = "hub/blog/index.html"
    tree = html.fromstring((SITE / rel).read_text(encoding="utf-8"))
    toolbar = tree.xpath("//nav[contains(@class,'toolbar')]")[0]
    categories = list(dict.fromkeys(a["category"] for a in articles))
    replace_children(toolbar, "".join(f'<a class="chip" href="#topic-{i}">{esc(cat)}</a>' for i, cat in enumerate(categories, 1)))
    catalog = tree.xpath("//section[contains(@class,'catalog')]")[0]
    replace_children(catalog, "".join(f'<div class="topic-group" id="topic-{i}"><h2 class="topic-title">{esc(cat)}</h2><div class="cards">{"".join(card(a, rel) for a in articles if a["category"] == cat)}</div></div>' for i, cat in enumerate(categories, 1)))
    save(shell(tree, rel), rel)

    rel = "hub/index.html"
    tree = html.fromstring((SITE / rel).read_text(encoding="utf-8"))
    cards = tree.xpath("//section[@id='articles']//div[contains(@class,'cards')]")
    if cards:
        replace_children(cards[0], "".join(card(a, rel) for a in sorted(articles, key=lambda x:x["date_iso"], reverse=True)[:3]))
    save(shell(tree, rel), rel)

    rel = "hub/shop/index.html"
    tree = html.fromstring((SITE / rel).read_text(encoding="utf-8"))
    lead = tree.xpath("//div[contains(@class,'page-intro')]/p[contains(@class,'lead')]")[0]
    lead.text = "Здесь собраны цифровые программы Андрея Шумеляка. Выберите тему и посмотрите содержание на странице продукта."
    catalog = tree.xpath("//section[contains(@class,'catalog')]")[0]
    categories = list(dict.fromkeys(p["category"] for p in products))
    def product_cards(items):
        return "".join(f'''<a class="catalog-product" href="{href_from(rel, page_for(p))}"><span class="catalog-status">{esc(p['status'])} · {esc(p['format'])}</span><h2>{esc(p['title'])}</h2><p>{esc(p['description'])}</p><span class="catalog-action">О программе</span></a>''' for p in items)
    if len(categories) == 1:
        groups = f'<div class="product-list">{product_cards(products)}</div>'
    else:
        groups = "".join(f'<div class="topic-group"><h2 class="topic-title">{esc(category)}</h2><div class="product-list">{product_cards([p for p in products if p["category"] == category])}</div></div>' for category in categories)
    replace_children(catalog, f'{groups}<p class="catalog-note">Оплата на сайте не оформляется. На странице программы можно узнать о содержании и способе записи.</p>')
    save(shell(tree, rel), rel)


def current_product():
    rel = "index.html"
    tree = html.fromstring((SITE / rel).read_text(encoding="utf-8"))
    section = tree.xpath("//section[@id='program']")[0]
    program_data = json.loads((CONTENT / "program.json").read_text(encoding="utf-8"))
    heading = section.xpath(".//div[contains(@class,'section-head')]//h2")[0]
    for child in list(heading):
        heading.remove(child)
    heading.text = program_data["heading"]
    section.xpath(".//div[contains(@class,'section-head')]/p[last()]")[0].text = program_data["introduction"]
    markup = "".join(f'<article class="module reveal"><div class="module-head"><span class="step-num">{esc(m["number"])}</span></div><h3>{esc(m["title"])}</h3><ul>{"".join(f"<li>{esc(point)}</li>" for point in m["points"])}</ul><p class="module-foot">{esc(m["practice"])}</p></article>' for m in program_data["modules"])
    replace_children(section.xpath(".//div[contains(@class,'program')]")[0], markup)
    save(shell(tree, rel), rel)


def new_products():
    for p in products:
        if p.get("landing"):
            continue
        rel = page_for(p)
        includes = "".join(f"<li>{esc(x)}</li>" for x in p["includes"])
        contact = f'<a class="button" href="{esc(p["contact_url"])}">Узнать о записи</a>' if p.get("contact_url") else ""
        markup = f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#18312e"><meta name="description" content="{esc(p['description'])}"><title>{esc(p['title'])} | Андрей Шумеляк</title><link rel="stylesheet" href="{href_from(rel, 'hub/assets/style.css')}"></head><body><main id="main"><article class="product-detail wrap"><p class="eyebrow">{esc(p['category'])} · {esc(p['status'])}</p><h1>{esc(p['title'])}</h1><p class="lead">{esc(p['description'])}</p><section><h2>Кому подходит</h2><p>{esc(p['audience'])}</p></section><section><h2>Что входит</h2><ul>{includes}</ul></section><section><h2>Формат</h2><p>{esc(p['format'])}</p></section><p class="product-note">Описание образовательного материала. Не заменяет диагностику или лечение.</p>{contact}</article></main></body></html>'''
        save(shell(html.fromstring(markup), rel), rel)


def sitemap():
    paths = ["index.html", "hub/index.html", "hub/blog/index.html", "hub/shop/index.html", "zapis/index.html"]
    paths += [f"hub/blog/{a['slug']}.html" for a in articles]
    paths += [page_for(p) for p in products if not p.get("landing")]
    urls = "\n".join(f"  <url><loc>{xml_escape(canonical(rel))}</loc></url>" for rel in dict.fromkeys(paths))
    (SITE / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}\n</urlset>\n', encoding="utf-8")
    (SITE / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE}sitemap.xml\n", encoding="utf-8")


for item in articles:
    article_page(item)
css_path = SITE / "hub/assets/style.css"
css = css_path.read_text(encoding="utf-8")
css_path.write_text(css.replace(".ttf", ".woff2").replace('format("truetype")', 'format("woff2")'), encoding="utf-8")
catalogs()
current_product()
tree = html.fromstring((SITE / "zapis/index.html").read_text(encoding="utf-8"))
for link in tree.xpath("//main//a[@href]"):
    if link.get("href") == BASE.rstrip("/") + "/":
        link.set("href", "../index.html")
save(shell(tree, "zapis/index.html"), "zapis/index.html")
new_products()
sitemap()
print(f"Built {len(articles)} articles and {len(products)} public products")
