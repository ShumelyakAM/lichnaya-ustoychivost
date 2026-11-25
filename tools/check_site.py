"""Focused checks for generated pages, links and content security policy."""
import base64
import hashlib
import json
import posixpath
import re
from pathlib import Path
from lxml import html

project = Path(__file__).resolve().parents[1]
site = project / "public-site" if (project / "public-site").exists() else project
pages = sorted([site / "index.html", *((site / "hub").rglob("*.html")), site / "zapis/index.html"])
assert pages, "No HTML pages"
for path in pages:
    rel = path.relative_to(site).as_posix()
    tree = html.fromstring(path.read_text(encoding="utf-8"))
    assert len(tree.xpath("//h1")) == 1, rel
    assert len(tree.xpath("//header[contains(@class,'site-header')]")) == 1, rel
    assert len(tree.xpath("//footer[contains(@class,'site-footer')]")) == 1, rel
    assert len(tree.xpath("/html/head/link[@rel='canonical']")) == 1, rel
    assert len(tree.xpath("/html/head/link[@data-site-shell]")) == 1, rel
    assert len(tree.xpath("/html/body/div[contains(@class,'site-topbar')]")) == 1, rel
    assert len(tree.xpath("/html/body/a[contains(@class,'site-skip')]")) == 1, rel
    for node in tree.xpath("//*[@href]|//*[@src]"):
        value = node.get("href") or node.get("src")
        if not value or value.startswith(("#", "http://", "https://", "data:", "mailto:", "tel:")):
            continue
        target = posixpath.normpath(posixpath.join(posixpath.dirname(rel), value.split("#")[0].split("?")[0]))
        assert (site / target).exists(), f"Broken link: {rel} -> {value}"
    for script in tree.xpath("//script[@type='application/ld+json']"):
        assert json.loads(script.text)["headline"], rel
    csp = tree.xpath("//meta[@http-equiv='Content-Security-Policy']")
    if csp:
        policy = csp[0].get("content")
        assert "style-src 'self'" in policy, rel
        for tag, directive in [("style", "style-src"), ("script", "script-src")]:
            nodes = tree.xpath(f"//{tag}[not(@src)]")
            if nodes:
                digest = base64.b64encode(hashlib.sha256((nodes[0].text or "").encode()).digest()).decode()
                assert f"'sha256-{digest}'" in policy, f"Invalid {directive} CSP: {rel}"

program = html.fromstring((site / "index.html").read_text(encoding="utf-8"))
assert len(program.xpath("//section[@id='program']//article[contains(@class,'module')]")) == 5
assert "Пять модулей" in program.text_content()
assert (site / "sitemap.xml").exists() and (site / "robots.txt").exists()
css = (site / "hub/assets/style.css").read_text(encoding="utf-8")
assert ".woff2" in css and "FiraSans-Light.ttf" not in css
print(f"OK: {len(pages)} pages, local links, CSP, five modules, sitemap, WOFF2")
