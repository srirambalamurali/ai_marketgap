from xml.etree import ElementTree
import re

rss = '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>Test</title><item><title>Art1</title><link>https://x.com</link><description>First article about AI</description><pubDate>Mon, 06 Jan 2025 12:00:00 +0000</pubDate><author>A1</author></item></channel></rss>'

root = ElementTree.fromstring(rss)
ns = {"atom": "http://www.w3.org/2005/Atom"}
items = root.findall(".//item")
print(f"items from .//item: {len(items)}")
items2 = root.findall(".//atom:entry", ns)
print(f"items from atom:entry: {len(items2)}")

for item in items:
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
