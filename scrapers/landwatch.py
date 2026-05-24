"""
LandWatch scraper — land & rural property listings, free, no key needed.
LandWatch.com is one of the largest free land listing databases in the US.
"""
import requests
import re
import time
from bs4 import BeautifulSoup
from config import Config

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


class LandWatchScraper:
    BASE = 'https://www.landwatch.com'

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(Config.HEADERS)
        # LandWatch needs these extra headers to avoid bot detection
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.landwatch.com/',
        })

    def search(self, city: str, max_price: int = None) -> list:
        state = _STATE_SLUGS.get(city.lower(), 'united-states')
        url = f"{self.BASE}/land-for-sale/{state}/"
        params = {}
        if max_price:
            params['PriceMax'] = int(max_price)

        results = []
        try:
            resp = self.session.get(url, params=params,
                                    timeout=Config.REQUEST_TIMEOUT)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'lxml')
                results = self._parse(soup, city, state)
        except Exception as e:
            print(f"[LandWatch] Error: {e}")

        return results[:Config.MAX_RESULTS_PER_SEARCH]

    def _parse(self, soup, city, state):
        items = []

        # LandWatch uses structured listing cards
        cards = (soup.select('[class*="PropertyCard"]') or
                 soup.select('[class*="property-card"]') or
                 soup.select('[class*="listing-card"]') or
                 soup.select('article') or
                 soup.select('[data-listing-id]'))

        for card in cards:
            try:
                item = self._parse_card(card, city, state)
                if item and item.get('title'):
                    items.append(item)
            except Exception:
                continue

        return items

    def _parse_card(self, card, city, state):
        item = {
            'source': 'landwatch',
            'category': 'land',
            'city': city,
            'images': [],
            'extra': {},
        }

        # Title + URL
        a = (card.select_one('a[href*="/land/"]') or
             card.select_one('a[href*="/lot/"]') or
             card.select_one('h2 a') or card.select_one('h3 a') or
             card.select_one('a'))
        if not a:
            return None

        title = a.get_text(strip=True)
        if not title or len(title) < 5:
            # Try heading
            h = card.select_one('h2, h3, h4')
            title = h.get_text(strip=True) if h else ''
        if not title:
            return None
        item['title'] = title

        href = a.get('href', '')
        if href and not href.startswith('http'):
            href = self.BASE + href
        item['url'] = href

        # Source ID from URL
        m = re.search(r'/(\d+)/?(?:\?|$)', href)
        item['source_id'] = m.group(1) if m else href[-20:]

        # Price
        for sel in ['[class*="price"]', '[class*="Price"]',
                    '.price', '[class*="asking"]']:
            el = card.select_one(sel)
            if el:
                pt = el.get_text(strip=True)
                item['price_text'] = pt
                nums = re.sub(r'[^\d]', '', pt)
                if nums and len(nums) >= 3:
                    try:
                        item['price'] = float(nums)
                    except ValueError:
                        pass
                break

        # Location / address
        for sel in ['[class*="location"]', '[class*="address"]',
                    '[class*="city"]', '.location']:
            el = card.select_one(sel)
            if el:
                item['location'] = el.get_text(strip=True)
                break
        if not item.get('location'):
            item['location'] = f"{city.title()}, {state.replace('-', ' ').title()}"

        # Acreage and other details
        card_text = card.get_text(' ', strip=True)
        ac_m = re.search(r'([\d,\.]+)\s*(?:acres?|ac\.?)', card_text, re.I)
        if ac_m:
            item['extra']['acres'] = ac_m.group(0)

        # Description
        for sel in ['.description', '[class*="desc"]', 'p']:
            el = card.select_one(sel)
            if el and len(el.get_text(strip=True)) > 20:
                item['description'] = el.get_text(strip=True)[:600]
                break
        if not item.get('description') and len(card_text) > 30:
            item['description'] = card_text[:500]

        # Image
        img = card.select_one('img')
        if img:
            src = img.get('src') or img.get('data-src', '')
            if src and src.startswith('http') and 'placeholder' not in src.lower():
                item['images'] = [src]

        return item


landwatch_scraper = LandWatchScraper()
