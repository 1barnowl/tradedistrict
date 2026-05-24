"""
BizBuySell scraper — real businesses for sale, no API key needed.
Scrapes search results and individual listing pages for full details.
"""
import requests
import re
import time
from bs4 import BeautifulSoup
from config import Config

# State abbreviation map for URL building
_STATE_SLUGS = {
    'miami': 'florida', 'orlando': 'florida', 'tampa': 'florida',
    'fort lauderdale': 'florida', 'jacksonville': 'florida',
    'new york': 'new-york', 'los angeles': 'california',
    'chicago': 'illinois', 'houston': 'texas', 'dallas': 'texas',
    'austin': 'texas', 'san antonio': 'texas', 'phoenix': 'arizona',
    'philadelphia': 'pennsylvania', 'san diego': 'california',
    'seattle': 'washington', 'denver': 'colorado', 'boston': 'massachusetts',
    'atlanta': 'georgia', 'nashville': 'tennessee', 'portland': 'oregon',
    'las vegas': 'nevada', 'charlotte': 'north-carolina',
    'raleigh': 'north-carolina', 'minneapolis': 'minnesota',
    'st louis': 'missouri', 'pittsburgh': 'pennsylvania',
    'cleveland': 'ohio', 'columbus': 'ohio', 'indianapolis': 'indiana',
}


class BizBuySellScraper:
    BASE = 'https://www.bizbuysell.com'

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(Config.HEADERS)

    def search(self, city: str, max_price: int = None) -> list:
        city_lower = city.lower()
        state = _STATE_SLUGS.get(city_lower, 'united-states')
        city_slug = city_lower.replace(' ', '-')

        # Try city-specific URL first, fall back to state
        urls = [
            f"{self.BASE}/businesses-for-sale/{state}/{city_slug}-businesses/",
            f"{self.BASE}/businesses-for-sale/{state}/",
        ]

        results = []
        for url in urls:
            params = {}
            if max_price:
                params['price_to'] = int(max_price)
            try:
                resp = self.session.get(url, params=params,
                                        timeout=Config.REQUEST_TIMEOUT)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'lxml')
                    results = self._parse(soup, city)
                    if results:
                        break
            except Exception as e:
                print(f"[BizBuySell] {url}: {e}")
            time.sleep(0.5)

        return results[:Config.MAX_RESULTS_PER_SEARCH]

    def _parse(self, soup, city):
        items = []
        cards = (soup.select('div.listing') or
                 soup.select('[data-id]') or
                 soup.select('.bizListingCard') or
                 soup.select('article') or
                 soup.select('[class*="listing"]'))

        for card in cards:
            try:
                item = self._parse_card(card, city)
                if item and item.get('title') and len(item['title']) > 5:
                    items.append(item)
            except Exception:
                continue
        return items

    def _parse_card(self, card, city):
        item = {
            'source': 'bizbuysell',
            'category': 'business',
            'city': city,
            'images': [],
            'extra': {},
        }

        # Title + URL
        a = (card.select_one('a[href*="/business-for-sale/"]') or
             card.select_one('h2 a') or card.select_one('h3 a') or
             card.select_one('a.title') or card.select_one('a'))
        if not a:
            return None
        item['title'] = a.get_text(strip=True)
        href = a.get('href', '')
        if href and not href.startswith('http'):
            href = self.BASE + href
        item['url'] = href
        m = re.search(r'/(\d+)/?$', href)
        item['source_id'] = m.group(1) if m else href[-20:]

        # Price — asking price
        for sel in ['[class*="price"]', '[class*="asking"]',
                    '.price', '[class*="Price"]']:
            el = card.select_one(sel)
            if el:
                pt = el.get_text(strip=True)
                item['price_text'] = pt
                nums = re.sub(r'[^\d]', '', pt)
                if nums:
                    try:
                        item['price'] = float(nums)
                    except ValueError:
                        pass
                break

        # Location
        for sel in ['[class*="location"]', '[class*="city"]',
                    '.location', '[class*="Location"]']:
            el = card.select_one(sel)
            if el:
                item['location'] = el.get_text(strip=True)
                break
        if not item.get('location'):
            item['location'] = city

        # Description snippet
        for sel in ['.description', '[class*="desc"]', '.snippet', 'p']:
            el = card.select_one(sel)
            if el and len(el.get_text(strip=True)) > 20:
                item['description'] = el.get_text(strip=True)[:600]
                break

        # Revenue / cash flow data
        extra_labels = {
            'revenue': ['revenue', 'gross', 'sales'],
            'cash_flow': ['cash flow', 'cashflow', 'sde', 'profit'],
            'ff_e': ['ff&e', 'furniture', 'equipment'],
            'inventory': ['inventory'],
            'employees': ['employees', 'staff'],
        }
        card_text = card.get_text(' ', strip=True).lower()
        for key, keywords in extra_labels.items():
            for kw in keywords:
                idx = card_text.find(kw)
                if idx != -1:
                    snippet = card_text[idx:idx+40]
                    m = re.search(r'\$[\d,]+[km]?', snippet)
                    if m:
                        item['extra'][key] = m.group(0)
                    break

        # Image
        img = card.select_one('img')
        if img:
            src = img.get('src') or img.get('data-src', '')
            if src and src.startswith('http') and 'placeholder' not in src.lower():
                item['images'] = [src]

        return item


bbs_scraper = BizBuySellScraper()
