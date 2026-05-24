"""
Craigslist scraper — HTML-based only.
RSS endpoint is globally blocked (403). This scraper uses the standard
search HTML page and handles both the current and legacy Craigslist layouts.
"""
import requests
import re
import time
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from config import Config


class CraigslistScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

    def search(self, city: str, category_key: str, query: str = '',
               min_price: int = None, max_price: int = None) -> list:
        cat = Config.CATEGORIES.get(category_key)
        if not cat:
            return []

        cl_city = Config.CL_CITIES.get(city.lower(), city.lower().replace(' ', ''))
        cl_code = cat['cl_code']

        url = f"https://{cl_city}.craigslist.org/search/{cl_code}"
        params = {'sort': 'date'}
        if query:
            params['query'] = query
        if min_price is not None:
            params['min_price'] = int(min_price)
        if max_price is not None:
            params['max_price'] = int(max_price)

        results = []
        try:
            resp = self.session.get(url, params=params, timeout=Config.REQUEST_TIMEOUT)
            resp.raise_for_status()
            results = self._parse_html(resp.text, city, category_key, cl_city)
            if results:
                print(f"[Craigslist] {cl_city}/{cl_code}: {len(results)} listings")
            else:
                print(f"[Craigslist] {cl_city}/{cl_code}: 0 results parsed")
        except Exception as e:
            print(f"[Craigslist] Failed ({cl_city}/{cl_code}): {e}")

        return results[:Config.MAX_RESULTS_PER_SEARCH]

    def _parse_html(self, html: str, city: str, category_key: str, cl_city: str) -> list:
        soup = BeautifulSoup(html, 'lxml')
        items = []

        # New Craigslist layout (2023+)
        nodes = soup.select('li.cl-static-search-result')
        if nodes:
            for node in nodes:
                try:
                    item = self._parse_new(node, city, category_key, cl_city)
                    if item and item.get('title') and item.get('source_id'):
                        items.append(item)
                except Exception:
                    continue
            return items

        # Intermediate layout
        nodes = soup.select('li[data-pid]')
        if nodes:
            for node in nodes:
                try:
                    item = self._parse_old(node, city, category_key, cl_city)
                    if item and item.get('title') and item.get('source_id'):
                        items.append(item)
                except Exception:
                    continue
            return items

        # Legacy layout
        nodes = soup.select('li.result-row')
        for node in nodes:
            try:
                item = self._parse_old(node, city, category_key, cl_city)
                if item and item.get('title') and item.get('source_id'):
                    items.append(item)
            except Exception:
                continue

        return items

    def _parse_new(self, node, city, category_key, cl_city):
        now = datetime.now(timezone.utc).isoformat()
        item = {
            'source': 'craigslist',
            'category': category_key,
            'city': city,
            'images': [],
            'extra': {},
            'scraped_at': now,
        }

        pid = node.get('data-pid', '')
        if pid:
            item['source_id'] = pid

        a = (node.select_one('a.posting-title') or
             node.select_one('div.title a') or
             node.select_one('a'))
        if not a:
            return None

        label = a.select_one('.label')
        item['title'] = (label or a).get_text(strip=True)
        if not item['title']:
            return None

        href = a.get('href', '')
        if href and not href.startswith('http'):
            href = f"https://{cl_city}.craigslist.org{href}"
        item['url'] = href

        if not item.get('source_id'):
            m = re.search(r'/(\d{10,})', href)
            if m:
                item['source_id'] = m.group(1)
        if not item.get('source_id'):
            return None

        price_el = node.select_one('.priceinfo') or node.select_one('[class*="price"]')
        if price_el:
            pt = price_el.get_text(strip=True)
            item['price_text'] = pt
            nums = re.sub(r'[^\d]', '', pt)
            if nums:
                try:
                    item['price'] = float(nums)
                except ValueError:
                    pass

        hood = (node.select_one('.hood') or
                node.select_one('[class*="location"]') or
                node.select_one('[class*="hood"]'))
        if hood:
            item['location'] = hood.get_text(strip=True).strip('() ')

        time_el = node.select_one('time')
        item['posted_at'] = time_el.get('datetime', now) if time_el else now

        return item

    def _parse_old(self, node, city, category_key, cl_city):
        now = datetime.now(timezone.utc).isoformat()
        item = {
            'source': 'craigslist',
            'category': category_key,
            'city': city,
            'images': [],
            'extra': {},
            'scraped_at': now,
        }

        pid = node.get('data-pid', '') or node.get('data-id', '')
        if pid:
            item['source_id'] = pid

        a = (node.select_one('a.result-title') or
             node.select_one('a.hdrlnk') or
             node.select_one('a'))
        if not a:
            return None

        item['title'] = a.get_text(strip=True)
        if not item['title']:
            return None

        href = a.get('href', '')
        if href and not href.startswith('http'):
            href = f"https://{cl_city}.craigslist.org{href}"
        item['url'] = href

        if not item.get('source_id'):
            m = re.search(r'/(\d{10,})', href)
            if m:
                item['source_id'] = m.group(1)
        if not item.get('source_id'):
            return None

        price_el = node.select_one('.result-price') or node.select_one('[class*="price"]')
        if price_el:
            pt = price_el.get_text(strip=True)
            item['price_text'] = pt
            nums = re.sub(r'[^\d]', '', pt)
            if nums:
                try:
                    item['price'] = float(nums)
                except ValueError:
                    pass

        hood = (node.select_one('.result-hood') or
                node.select_one('[class*="hood"]') or
                node.select_one('[class*="location"]'))
        if hood:
            item['location'] = hood.get_text(strip=True).strip('() ')

        time_el = node.select_one('time')
        item['posted_at'] = time_el.get('datetime', now) if time_el else now

        return item


scraper = CraigslistScraper()
