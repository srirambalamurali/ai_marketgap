from xml.etree import ElementTree
import re

rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
    <title>Test Feed</title>
    <item>
        <title>Article One</title>
        <link>https://example.com/1</link>
        <description>First article about AI</description>
        <pubDate>Mon, 06 Jan 2025 12:00:00 +0000</pubDate>
        <author>Author One</author>
    </item>
</channel>
</rss>"""

root = ElementTree.fromstring(rss)
ns = {"atom": "http://www.w3.org/2005/Atom"}

items = root.findall(".//item")
if not items:
    items = root.findall(".//atom:entry", ns)

print(f"items found: {len(items)}")

for item in items:
    title_el = item.find("title")
    title = title_el.text.strip() if title_el is not None and title_el.text else ""
    print(f"title: {repr(title)}")

    desc_el = item.find("description") or item.find("atom:summary", ns) or item.find("atom:content", ns)
    print(f"desc_el: {desc_el}")
    if desc_el is not None:
        raw = desc_el.text or ""
        print(f"raw text: {repr(raw)}")
        if not raw:
            raw = ElementTree.tostring(desc_el, encoding="unicode")
            print(f"raw tostring: {repr(raw)}")
        description = re.sub(r"<[^>]+>", "", raw).strip()[:2000]
        print(f"description: {repr(description)}")
    else:
        print("desc_el is None!")
