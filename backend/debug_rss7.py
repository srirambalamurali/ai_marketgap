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

# Direct find
result1 = item.find("description")
print(f"find('description'): {result1}")

# Check all children
for child in item:
    print(f"  tag={child.tag} text={repr(child.text)}")
    if child.tag == "description":
        print(f"  FOUND! text={repr(child.text)}")

# Try different approaches
print(f"\nfind with .// : {item.find('.//description')}")
print(f"findtext: {item.findtext('description')}")
