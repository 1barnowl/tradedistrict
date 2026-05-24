### trade.explorearoundme.online




# Trade District 1.0 — Opportunity Intelligence Platform

A location-aware deal discovery and tracking platform for real estate, businesses, vehicles, equipment, and more.

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the app
```bash
python app.py
```

Then open: **http://localhost:5000**

The app will auto-seed with realistic demo data on first launch.

---

## Features

### ✅ Phase 1 (Current)
- **Multi-category search** — Real Estate, Business, Vehicles, Land, Equipment, General
- **Craigslist scraper** — Free, no API key required, searches 30+ cities
- **Intelligence scoring** — Value, Freshness, Actionability, Completeness scores
- **Signal detection** — Motivated seller, below market, contact quality, urgency flags
- **Next-action recommendations** — Context-aware "what to do next" suggestions
- **Watchlist** — Save and monitor opportunities
- **Pipeline / Kanban** — Track deal stages (discovered → reviewing → contacted → closed)
- **Alerts** — New listings, price drops, stale listings
- **Notes** — Per-opportunity private notes
- **Demo data** — 14 realistic South Florida opportunities pre-loaded

### 🔮 Planned (Phase 2+)
- eBay sold listings for vehicle comp analysis (free API key)
- Business-for-sale marketplace scraping
- Email/SMS alert delivery
- Saved search profiles with recurring scans
- Deal memo / export to PDF
- Comparison mode (side-by-side)
- Map view with opportunity pins

---

## Data Sources

| Source | API Key Required | Cost |
|--------|-----------------|------|
| Craigslist | ❌ None | Free |
| eBay Browse API | ✅ Optional | Free tier |
| Demo data | ❌ None | Free |

---

## Project Structure

```
tradedistrict/
├── app.py              — Flask app, routes, API endpoints
├── config.py           — Settings, cities, categories
├── database.py         — SQLite ORM layer
├── intelligence/
│   └── scorer.py       — Opportunity scoring engine
├── scrapers/
│   ├── craigslist.py   — Craigslist search + detail scraper
│   └── demo.py         — Demo/seed data
├── templates/          — Jinja2 HTML templates
├── static/
│   ├── css/main.css    — Design system
│   └── js/main.js      — Frontend logic
└── tradedistrict.db        — SQLite database (auto-created)
```

---

## Cities Supported (Craigslist)

Miami, New York, Los Angeles, Chicago, Houston, Phoenix, Philadelphia, San Antonio, San Diego, Dallas, Austin, Seattle, Denver, Boston, Atlanta, Nashville, Portland, Las Vegas, Orlando, Tampa, Fort Lauderdale, Jacksonville, Charlotte, Raleigh, Minneapolis, St. Louis, Pittsburgh, Cleveland, Columbus, Indianapolis

---

## Keyboard Shortcuts

- `/` — Focus search bar
- `Escape` — Blur/close

---

## Settings

Visit **Settings** page to:
- Change default city
- Set default max price
- Toggle active categories
- Add optional eBay API key (free at developer.ebay.com)

---

## Notes on Scraping

Trade District scrapes Craigslist respectfully with:
- 1.5 second delays between requests
- Standard browser User-Agent headers
- Limited result sets (40 per search)

For personal/research use only. Always respect site Terms of Service.
