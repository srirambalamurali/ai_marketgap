from xml.etree import ElementTree

# Exact same XML as in test
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
items = root.findall(".//item")
print(f"items: {len(items)}")
for item in items:
    print(f"item children: {[c.tag for c in item]}")
    desc = item.find("description")
    print(f"find('description'): {desc}")
    # Try with full path
    for child in item:
        print(f"  child tag={child.tag} text={repr(child.text)}")
