from app.collectors.rss_collector import RSSCollector

# Direct test with clean XML
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

c = RSSCollector()
signals = c._parse_feed(rss, "test_feed")
print(f"signals: {len(signals)}")
for s in signals:
    print(f"  title={s.title} content={repr(s.content)}")
