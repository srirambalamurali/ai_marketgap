from app.collectors.rss_collector import RSSCollector
rss = '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>Test</title><item><title>Art1</title><link>https://x.com</link><description>First article about AI</description><pubDate>Mon, 06 Jan 2025 12:00:00 +0000</pubDate><author>A1</author></item></channel></rss>'
c = RSSCollector()
signals = c._parse_feed(rss, 'test')
print(f'count: {len(signals)}')
for s in signals:
    print(f'title={s.title} content={repr(s.content)}')
