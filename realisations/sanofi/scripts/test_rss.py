import feedparser
from pipeline.config import GOOGLE_NEWS_RSS_URL
feed = feedparser.parse(GOOGLE_NEWS_RSS_URL)
e = feed.entries[0]
print('link:', e.get('link'))
print('links:', e.get('links'))
print('source:', e.get('source'))
print('summary:', e.get('summary', '')[:300])
