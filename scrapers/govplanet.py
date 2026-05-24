"""
GovPlanet scraper — government surplus equipment auctions, free, no key needed.
GovPlanet sells retired government/municipal equipment publicly.
Also scrapes PublicSurplus.com for additional government auction listings.
"""
import requests
import re
import json
import time
from bs4 import BeautifulSoup
from config import Config


class GovPlanetScraper:
    BASE = 'https://www.govplanet.com'

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(Config.HEADERS)

    def search(self, city: str = '', max_price: int = None) -> list:
        results = []
        results.extend(self._scrape_govplanet(max_price))
        time.sleep(Config.REQUEST_DELAY)
        results.extend(self._scrape_publicsurplus(city, max_price))
        return results[:Config.MAX_RESULTS_PER_SEARCH]

    def _scrape_govplanet(self, max_price=None) -> list:
        url = f"{self.BASE}/for-sale/"
        params = {'category': 'Construction', 'sort': 'endDate'}
        if max_price:
            params['maxPrice'] = int(max_price)

        items = []
        try:
            resp = self.session.get(url, params=params,
                                    timeout=Config.REQUEST_TIMEOUT)
            if resp.status_code != 200:
                return items
            soup = BeautifulSoup(resp.text, 'lxml')

            cards = (soup.select('[class*="item-card"]') or
                     soup.select('[class*="listing"]') or
                     soup.select('.item') or
                     soup.select('article'))

            for card in cards:
                try:
                    item = self._parse_govplanet_card(card)
                    if item and item.get('title'):
                        items.append(item)
                except Exception:
                    continue
        except Exception as e:
            print(f"[GovPlanet] Error: {e}")

        return items

    def _parse_govplanet_card(self, card) -> dict:
        item = {
            'source': 'govplanet',
            'category': 'equipment',
            'city': 'various',
            'images': [],
            'extra': {'auction': True, 'seller_type': 'government'},
        }

        a = card.select_one('a[href*="/item/"]') or card.select_one('h2 a') or card.select_one('a')
        if not a:
            return None
        item['title'] = a.get_text(strip=True)
        href = a.get('href', '')
        if href and not href.startswith('http'):
            href = self.BASE + href
        item['url'] = href
        m = re.search(r'/item/[^/]+-(\d+)', href)
        item['source_id'] = f"gp-{m.group(1)}" if m else href[-20:]

        # Current bid or buy-now price
        for sel in ['[class*="price"]', '[class*="bid"]',
                    '[class*="current"]', '.price']:
            el = card.select_one(sel)
            if el:
                pt = el.get_text(strip=True)
                item['price_text'] = pt
                nums = re.sub(r'[^\d]', '', pt)
                if nums and len(nums) >= 2:
                    try:
                        item['price'] = float(nums)
                    except ValueError:
                        pass
                break

        # Location
        for sel in ['[class*="location"]', '[class*="city"]', '[class*="state"]']:
            el = card.select_one(sel)
            if el:
                item['location'] = el.get_text(strip=True)
                item['city'] = el.get_text(strip=True).split(',')[0].strip().lower()
                break

        # Auction end date
        for sel in ['[class*="end"]', '[class*="time"]', 'time']:
            el = card.select_one(sel)
            if el:
                item['extra']['auction_ends'] = el.get_text(strip=True)
                break

        # Image
        img = card.select_one('img')
        if img:
            src = img.get('src') or img.get('data-src', '')
            if src and src.startswith('http'):
                item['images'] = [src]

        return item

    def _scrape_publicsurplus(self, city: str = '', max_price=None) -> list:
        """PublicSurplus.com — government surplus auctions across the US."""
        url = 'https://www.publicsurplus.com/sms/browse/home'
        params = {'catid': '0', 'keywords': ''}

        items = []
        try:
            resp = self.session.get(url, params=params,
                                    timeout=Config.REQUEST_TIMEOUT)
            if resp.status_code != 200:
                return items
            soup = BeautifulSoup(resp.text, 'lxml')

            rows = soup.select('tr.auctionRow, tr[class*="auction"]')
            if not rows:
                rows = soup.select('table tr')[1:]  # skip header

            for row in rows[:20]:
                try:
                    cols = row.select('td')
                    if len(cols) < 3:
                        continue

                    a = row.select_one('a[href*="/sms/auction"]') or row.select_one('a')
                    if not a:
                        continue
                    title = a.get_text(strip=True)
                    if not title:
                        continue

                    href = a.get('href', '')
                    if href and not href.startswith('http'):
                        href = 'https://www.publicsurplus.com' + href
                    m = re.search(r'auc=(\d+)', href)
                    source_id = f"ps-{m.group(1)}" if m else href[-20:]

                    # Price from columns
                    price, price_text = None, ''
                    for col in cols:
                        t = col.get_text(strip=True)
                        if '$' in t:
                            price_text = t
                            try:
                                price = float(re.sub(r'[^\d.]', '', t))
                            except ValueError:
                                pass
                            break

                    if max_price and price and price > max_price:
                        continue

                    item = {
                        'source': 'publicsurplus',
                        'source_id': source_id,
                        'category': 'equipment',
                        'city': city or 'various',
                        'title': title,
                        'url': href,
                        'price': price,
                        'price_text': price_text,
                        'location': city or 'Government Auction',
                        'images': [],
                        'extra': {'auction': True, 'seller_type': 'government'},
                    }
                    items.append(item)
                except Exception:
                    continue
        except Exception as e:
            print(f"[PublicSurplus] Error: {e}")

        return items


govplanet_scraper = GovPlanetScraper()
