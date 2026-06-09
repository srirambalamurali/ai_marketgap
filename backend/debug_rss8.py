from xml.etree import ElementTree

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
item = items[0]

desc = item.find("description")
print(f"desc element: {desc}")
print(f"desc bool: {bool(desc)}")
print(f"desc text: {repr(desc.text)}")
print(f"desc children: {list(desc)}")

# Test the or chain
result = item.find("description") or item.find("atom:summary") or item.find("atom:content")
print(f"or chain result: {result}")
