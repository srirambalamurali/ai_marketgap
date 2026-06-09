from xml.etree import ElementTree
rss = '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>Test</title><item><title>Art1</title><link>https://x.com</link><description>First article about AI</description><pubDate>Mon, 06 Jan 2025 12:00:00 +0000</pubDate><author>A1</author></item></channel></rss>'
root = ElementTree.fromstring(rss)
items = root.findall('.//item')
print(f'items found: {len(items)}')
for item in items:
    title_el = item.find('title')
    print(f'title_el: {title_el}, text: {repr(title_el.text) if title_el is not None else None}')
    desc_el = item.find('description')
    print(f'desc_el: {desc_el}, text: {repr(desc_el.text) if desc_el is not None else None}')
    if desc_el is not None:
        print(f'desc el tag: {desc_el.tag}')
        print(f'desc el attrib: {desc_el.attrib}')
        print(f'desc children: {list(desc_el)}')
        raw = desc_el.text or ""
        print(f'raw from text: {repr(raw)}')
        if not raw:
            raw = ElementTree.tostring(desc_el, encoding="unicode")
            print(f'raw from tostring: {repr(raw)}')
