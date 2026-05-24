import os

class Config:
    SECRET_KEY    = os.environ.get('SECRET_KEY', 'tradedistrict-dev-key-2024')
    # When frozen by PyInstaller, TD_DB_PATH is set by run.py to a persistent location
    # next to the executable. Fallback: same directory as this file (dev mode).
    DATABASE_PATH = (
        os.environ.get('TD_DB_PATH') or
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tradedistrict.db')
    )
    DEBUG = False

    # Default search settings
    DEFAULT_CITY       = 'miami'
    DEFAULT_RADIUS_MILES = 50
    DEFAULT_MAX_PRICE  = 500000

    # Scraping settings
    REQUEST_TIMEOUT    = 12
    REQUEST_DELAY      = 1.5  # seconds between requests
    MAX_RESULTS_PER_SEARCH = 40

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xhtml+xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    }

    # Craigslist cities
    CL_CITIES = {
        'miami': 'miami', 'new york': 'newyork', 'los angeles': 'losangeles',
        'chicago': 'chicago', 'houston': 'houston', 'phoenix': 'phoenix',
        'philadelphia': 'philadelphia', 'san antonio': 'sanantonio',
        'san diego': 'sandiego', 'dallas': 'dallas', 'austin': 'austin',
        'seattle': 'seattle', 'denver': 'denver', 'boston': 'boston',
        'atlanta': 'atlanta', 'nashville': 'nashville', 'portland': 'portland',
        'las vegas': 'lasvegas', 'orlando': 'orlando', 'tampa': 'tampa',
        'fort lauderdale': 'broward', 'jacksonville': 'jacksonville',
        'charlotte': 'charlotte', 'raleigh': 'raleigh', 'minneapolis': 'minneapolis',
        'st louis': 'stlouis', 'pittsburgh': 'pittsburgh', 'cleveland': 'cleveland',
        'columbus': 'columbus', 'indianapolis': 'indianapolis',
    }

    # Categories mapping
    CATEGORIES = {
        'real_estate': {'label': 'Real Estate', 'cl_code': 'rea', 'icon': '🏠', 'color': '#3B5BDB'},
        'business':    {'label': 'Business',    'cl_code': 'bfs', 'icon': '🏢', 'color': '#7048E8'},
        'vehicles':    {'label': 'Vehicles',    'cl_code': 'cta', 'icon': '🚗', 'color': '#1098AD'},
        'land':        {'label': 'Land',        'cl_code': 'lnd', 'icon': '🌍', 'color': '#20C997'},
        'equipment':   {'label': 'Equipment',   'cl_code': 'mab', 'icon': '⚙️', 'color': '#F59F00'},
        'general':     {'label': 'General',     'cl_code': 'sss', 'icon': '📦', 'color': '#868E96'},
    }

    PIPELINE_STAGES = [
        'discovered', 'reviewing', 'contacted', 'waiting',
        'inspecting', 'negotiating', 'passed', 'pursuing', 'closed'
    ]
