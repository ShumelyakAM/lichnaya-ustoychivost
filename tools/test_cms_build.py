"""Check that a newly saved CMS entry appears across the site."""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from lxml import html

project = Path(__file__).resolve().parents[1]
scratch = Path(tempfile.mkdtemp(prefix="site-cms-test-", dir=project.parent))
assert scratch.resolve().parent == project.parent.resolve()
try:
    for name in ("hub", "zapis", "site-content", "tools"):
        shutil.copytree(project / name, scratch / name)
    for name in ("index.html", "robots.txt", "sitemap.xml"):
        shutil.copy2(project / name, scratch / name)

    product_path = scratch / "site-content/products.json"
    products = json.loads(product_path.read_text(encoding="utf-8"))
    products.append({
        "slug": "test-product", "title": "Тестовый продукт", "category": "Другая тема",
        "format": "Самостоятельная программа", "status": "Готовится",
        "description": "Описание тестового продукта.", "audience": "Описание аудитории.",
        "includes": ["Материал"], "visible": True,
    })
    product_path.write_text(json.dumps(products, ensure_ascii=False), encoding="utf-8")

    article = {
        "slug": "test-article", "title": "Тестовая статья", "description": "Описание тестовой статьи.",
        "eyebrow": "Режим", "lead": "Вводный текст.", "date_iso": "2026-11-26",
        "category": "Режим", "body": "<h2>Раздел статьи</h2><p>Основной текст.</p>",
        "product": "test-product",
    }
    (scratch / "site-content/articles/test-article.json").write_text(
        json.dumps(article, ensure_ascii=False), encoding="utf-8"
    )

    subprocess.run([sys.executable, str(scratch / "tools/build_site.py")], check=True, capture_output=True)
    assert (scratch / "hub/products/test-product/index.html").exists()
    assert (scratch / "hub/blog/test-article.html").exists()
    shop = html.fromstring((scratch / "hub/shop/index.html").read_text(encoding="utf-8"))
    blog = html.fromstring((scratch / "hub/blog/index.html").read_text(encoding="utf-8"))
    assert "Тестовый продукт" in shop.text_content()
    assert "Тестовая статья" in blog.text_content()
    sitemap = (scratch / "sitemap.xml").read_text(encoding="utf-8")
    assert "test-product" in sitemap and "test-article" in sitemap
    print("OK: CMS article and product appear on pages and in sitemap")
finally:
    assert scratch.resolve().parent == project.parent.resolve()
    shutil.rmtree(scratch)
