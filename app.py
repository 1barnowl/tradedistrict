from flask import Flask, render_template, request, jsonify, redirect, url_for, Response
from flask_cors import CORS
import json, csv, io, threading, time
from datetime import datetime, timezone

import database as db
from config import Config
from intelligence.scorer import scorer, STRATEGY_LABELS
from intelligence.geocoder import geocode_opportunity, CITY_CENTRES
from scrapers.craigslist import CraigslistScraper
from scrapers.bizbuysell import bbs_scraper
from scrapers.landwatch import landwatch_scraper
from scrapers.govplanet import govplanet_scraper

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

import json as _json

@app.template_filter('fromjson')
def fromjson_filter(s):
    """Parse a JSON string from the DB back into a Python dict."""
    if isinstance(s, dict):
        return s  # already decoded
    try:
        return _json.loads(s)
    except Exception:
        return {}

scan_state = {'running': False, 'progress': '', 'last_run': None, 'count': 0, 'errors': []}


# ── Utility ───────────────────────────────────────────────────────────────────

def _decode(opp):
    for f in ['signals','images','extra']:
        if isinstance(opp.get(f), str):
            try: opp[f] = json.loads(opp[f])
            except: opp[f] = [] if f != 'extra' else {}
    return opp


def process_and_store(raw_items, city, geocode=False):
    strategy = db.get_setting('strategy_mode', 'balanced')
    stored = 0
    for item in raw_items:
        extra = item.pop('extra', {})
        if isinstance(extra, str):
            try: extra = json.loads(extra)
            except: extra = {}
        if not item.get('description') and extra.get('description'):
            item['description'] = extra.pop('description')
        if not item.get('contact_phone') and extra.get('contact_phone'):
            item['contact_phone'] = extra.pop('contact_phone')
        item['extra'] = extra
        item['city'] = item.get('city') or city

        # Geocode if requested & no coords yet
        if not item.get('lat'):
            # Try geocoding if requested
            if geocode:
                coords = geocode_opportunity(item)
                if coords:
                    item['lat'], item['lng'] = coords
            # Always fallback to city-center with small jitter so pins spread out
            if not item.get('lat'):
                import random
                center = CITY_CENTRES.get(item.get('city','').lower().replace(' ',''))
                if not center:
                    center = CITY_CENTRES.get(item.get('city','').lower())
                if center:
                    item['lat'] = center[0] + random.uniform(-0.08, 0.08)
                    item['lng'] = center[1] + random.uniform(-0.12, 0.12)

        scores = scorer.score(item, strategy=strategy)
        item.update({
            'score_overall':      scores['overall'],
            'score_value':        scores['value'],
            'score_freshness':    scores['freshness'],
            'score_actionability':scores['actionability'],
            'score_completeness': scores['completeness'],
            'signals':    scores['signals'],
            'next_action':scores['next_action'],
        })
        db.upsert_opportunity(item)
        stored += 1
    return stored


def run_scan(city, categories, query='', min_price=None, max_price=None, do_geocode=False):
    global scan_state
    scan_state.update({'running': True, 'count': 0, 'errors': []})
    cl = CraigslistScraper()

    # ── Craigslist (all selected categories) ─────────────────────────────────
    for cat in categories:
        if not scan_state['running']: break
        label = Config.CATEGORIES.get(cat, {}).get('label', cat)
        scan_state['progress'] = f"Craigslist → {label}..."
        try:
            items = cl.search(city, cat, query=query,
                              min_price=min_price, max_price=max_price)
            n = process_and_store(items, city, geocode=do_geocode)
            scan_state['count'] += n
        except Exception as e:
            scan_state['errors'].append(f"Craigslist {label}: {e}")
        time.sleep(Config.REQUEST_DELAY)

    # ── BizBuySell (businesses) ───────────────────────────────────────────────
    if 'business' in categories and scan_state['running']:
        scan_state['progress'] = "BizBuySell → Businesses for sale..."
        try:
            items = bbs_scraper.search(city, max_price=max_price)
            n = process_and_store(items, city, geocode=do_geocode)
            scan_state['count'] += n
        except Exception as e:
            scan_state['errors'].append(f"BizBuySell: {e}")
        time.sleep(Config.REQUEST_DELAY)

    # ── LandWatch (land & real estate) ────────────────────────────────────────
    if any(c in categories for c in ('land', 'real_estate')) and scan_state['running']:
        scan_state['progress'] = "LandWatch → Land & acreage listings..."
        try:
            items = landwatch_scraper.search(city, max_price=max_price)
            n = process_and_store(items, city, geocode=do_geocode)
            scan_state['count'] += n
        except Exception as e:
            scan_state['errors'].append(f"LandWatch: {e}")
        time.sleep(Config.REQUEST_DELAY)

    # ── GovPlanet + PublicSurplus (equipment auctions) ────────────────────────
    if 'equipment' in categories and scan_state['running']:
        scan_state['progress'] = "GovPlanet / PublicSurplus → Equipment auctions..."
        try:
            items = govplanet_scraper.search(city, max_price=max_price)
            n = process_and_store(items, city, geocode=do_geocode)
            scan_state['count'] += n
        except Exception as e:
            scan_state['errors'].append(f"GovPlanet: {e}")

    scan_state['running'] = False
    scan_state['progress'] = f"Complete — {scan_state['count']} live listings loaded"
    scan_state['last_run'] = datetime.now(timezone.utc).isoformat()


def _get_alerts(limit=20):
    conn = db.get_db()
    rows = conn.execute('''
        SELECT a.*, o.title as opp_title, o.category as opp_category
        FROM alerts a
        LEFT JOIN opportunities o ON a.opportunity_id = o.id
        ORDER BY a.created_at DESC LIMIT ?
    ''', (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Page Routes ───────────────────────────────────────────────────────────────


@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('favicon.svg'), 200, {'Content-Type': 'image/svg+xml'}

@app.route('/')
def dashboard():
    stats = db.get_stats()
    top_opps = [_decode(o) for o in db.get_opportunities({'sort':'score'}, limit=8)]
    recent   = [_decode(o) for o in db.get_opportunities({'sort':'newest'}, limit=6)]
    alerts   = _get_alerts(5)
    overdue  = db.get_overdue_reminders()
    upcoming = db.get_upcoming_reminders(7)
    saved_searches = db.get_saved_searches()
    strategy = db.get_setting('strategy_mode','balanced')
    return render_template('dashboard.html',
        stats=stats, top_opps=top_opps, recent=recent,
        alerts=alerts, overdue=overdue, upcoming=upcoming,
        saved_searches=saved_searches[:5],
        categories=Config.CATEGORIES, scan_state=scan_state,
        strategy=strategy, strategy_labels=STRATEGY_LABELS)


@app.route('/browse')
def browse():
    filters = {k: v for k, v in {
        'category':       request.args.get('category',''),
        'min_price':      request.args.get('min_price',''),
        'max_price':      request.args.get('max_price',''),
        'query':          request.args.get('q',''),
        'sort':           request.args.get('sort','score'),
        'min_score':      request.args.get('min_score',''),
        'city':           request.args.get('city',''),
        'has_contact':    request.args.get('has_contact',''),
        'hide_stale':     request.args.get('hide_stale',''),
        'hide_incomplete':request.args.get('hide_incomplete',''),
        'urgency':        request.args.get('urgency',''),
    }.items() if v}

    # compare mode
    compare_ids = request.args.getlist('compare')

    try:
        page = max(1, int(request.args.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    limit  = 24
    offset = (page-1)*limit

    opps = [_decode(o) for o in db.get_opportunities(filters, limit=limit+1, offset=offset)]
    has_next = len(opps) > limit
    opps = opps[:limit]

    compare_opps = []
    if compare_ids:
        for cid in compare_ids[:5]:
            try:
                o = db.get_opportunity(int(cid))
                if o: compare_opps.append(_decode(o))
            except: pass

    saved_searches = db.get_saved_searches()

    return render_template('browse.html',
        opps=opps, filters=filters, page=page, has_next=has_next,
        compare_opps=compare_opps, compare_ids=compare_ids,
        saved_searches=saved_searches,
        categories=Config.CATEGORIES, cities=Config.CL_CITIES,
        sort_options=[
            ('score','Best Match'),('newest','Newest First'),
            ('price_asc','Price: Low → High'),('price_desc','Price: High → Low'),
            ('freshness','Most Fresh'),('value','Best Value'),('actionable','Most Actionable'),
        ])


@app.route('/opportunity/<int:opp_id>')
def detail(opp_id):
    opp = db.get_opportunity(opp_id)
    if not opp: return redirect(url_for('browse'))
    _decode(opp)
    similar = [_decode(o) for o in db.get_opportunities(
        {'category': opp['category'], 'sort':'score'}, limit=4)
        if o['id'] != opp_id][:3]
    return render_template('detail.html', opp=opp, similar=similar,
        categories=Config.CATEGORIES, pipeline_stages=Config.PIPELINE_STAGES)


@app.route('/watchlist')
def watchlist():
    conn = db.get_db()
    rows = conn.execute('''
        SELECT o.*, w.added_at, w.notes as wl_notes,
               1 as in_watchlist, p.stage as pipeline_stage
        FROM watchlist w
        JOIN opportunities o ON o.id=w.opportunity_id
        LEFT JOIN pipeline p ON p.opportunity_id=o.id
        ORDER BY w.added_at DESC
    ''').fetchall()
    conn.close()
    opps = [_decode(dict(r)) for r in rows]
    return render_template('watchlist.html', opps=opps, categories=Config.CATEGORIES)


@app.route('/pipeline')
def pipeline():
    conn = db.get_db()
    rows = conn.execute('''
        SELECT o.*, p.stage, p.notes as pipeline_notes, p.updated_at as stage_updated,
               1 as in_pipeline, 1 as in_watchlist
        FROM pipeline p
        JOIN opportunities o ON o.id=p.opportunity_id
        ORDER BY p.updated_at DESC
    ''').fetchall()
    conn.close()
    opps = [_decode(dict(r)) for r in rows]
    stages = Config.PIPELINE_STAGES
    by_stage = {s:[] for s in stages}
    for o in opps:
        s = o.get('stage','discovered')
        if s in by_stage: by_stage[s].append(o)
    return render_template('pipeline.html', by_stage=by_stage, stages=stages,
        total=len(opps), categories=Config.CATEGORIES)


@app.route('/map')
def map_view():
    city = request.args.get('city') or db.get_setting('city', Config.DEFAULT_CITY)
    category = request.args.get('category','')
    opps_all = db.get_opportunities_for_map(city=city if city != 'all' else None)
    if category:
        opps_all = [o for o in opps_all if o['category'] == category]
    # City centre for initial map position
    city_key = city.lower().replace(' ','')
    centre = CITY_CENTRES.get(city_key, (39.5, -98.35))
    return render_template('map.html',
        opps_json=json.dumps(opps_all),
        centre=centre, city=city, category=category,
        categories=Config.CATEGORIES, cities=Config.CL_CITIES,
        total_mapped=len(opps_all))


@app.route('/compare')
def compare():
    ids = request.args.getlist('ids')
    opps = []
    for i in ids[:5]:
        try:
            o = db.get_opportunity(int(i))
            if o: opps.append(_decode(o))
        except: pass
    if len(opps) < 2:
        return redirect(url_for('browse'))
    # Build comparison matrix
    fields = [
        ('price','Price'),('location','Location'),('category','Category'),
        ('score_overall','Overall Score'),('score_value','Value Score'),
        ('score_freshness','Freshness'),('score_actionability','Actionability'),
        ('score_completeness','Completeness'),
        ('contact_quality','Contact Quality'),('urgency_tier','Urgency'),
        ('next_action','Recommended Action'),
    ]
    return render_template('compare.html', opps=opps, fields=fields,
        categories=Config.CATEGORIES)


@app.route('/alerts')
def alerts_page():
    alerts = _get_alerts(100)
    conn = db.get_db()
    conn.execute("UPDATE alerts SET is_read=1")
    conn.commit(); conn.close()
    return render_template('alerts.html', alerts=alerts)


@app.route('/reminders')
def reminders_page():
    overdue  = db.get_overdue_reminders()
    upcoming = db.get_upcoming_reminders(14)
    return render_template('reminders.html', overdue=overdue, upcoming=upcoming)


@app.route('/saved-searches')
def saved_searches_page():
    searches = db.get_saved_searches()
    return render_template('saved_searches.html', searches=searches, categories=Config.CATEGORIES)


@app.route('/settings')
def settings():
    s = {
        'city':         db.get_setting('city', Config.DEFAULT_CITY),
        'radius':       db.get_setting('radius', str(Config.DEFAULT_RADIUS_MILES)),
        'max_price':    db.get_setting('max_price', str(Config.DEFAULT_MAX_PRICE)),
        'ebay_api_key': db.get_setting('ebay_api_key',''),
        'categories':   json.loads(db.get_setting('categories','[]')),
        'strategy_mode':db.get_setting('strategy_mode','balanced'),
    }
    return render_template('settings.html', settings=s,
        categories=Config.CATEGORIES, cities=sorted(Config.CL_CITIES.keys()),
        strategy_labels=STRATEGY_LABELS)


# ── API ───────────────────────────────────────────────────────────────────────

@app.route('/api/scan', methods=['POST'])
def api_scan():
    if scan_state['running']:
        return jsonify({'status':'already_running'})
    data = request.get_json() or {}
    city = data.get('city') or db.get_setting('city', Config.DEFAULT_CITY)
    categories = data.get('categories') or json.loads(
        db.get_setting('categories', json.dumps(list(Config.CATEGORIES.keys()))))
    do_geocode = data.get('geocode', False)
    threading.Thread(
        target=run_scan,
        args=(city, categories, data.get('query',''),
              data.get('min_price'), data.get('max_price'), do_geocode),
        daemon=True
    ).start()
    return jsonify({'status':'started'})


@app.route('/api/scan/status')
def api_scan_status():
    return jsonify(scan_state)





@app.route('/api/geocode-all', methods=['POST'])
def api_geocode_all():
    """Background geocode all opportunities that lack coordinates."""
    def _run():
        import random
        conn = db.get_db()
        rows = conn.execute(
            "SELECT id, location, city FROM opportunities WHERE lat IS NULL AND is_active=1"
        ).fetchall()
        conn.close()
        # First pass: assign city-center coords immediately so map works right away
        for row in rows:
            city_key = (row['city'] or '').lower().replace(' ', '')
            center = CITY_CENTRES.get(city_key) or CITY_CENTRES.get((row['city'] or '').lower())
            if center:
                c = db.get_db()
                c.execute("UPDATE opportunities SET lat=?, lng=? WHERE id=? AND lat IS NULL",
                          (center[0] + random.uniform(-0.08, 0.08),
                           center[1] + random.uniform(-0.12, 0.12),
                           row['id']))
                c.commit(); c.close()
        # Second pass: refine with Nominatim for first 50 (rate-limited)
        for row in rows[:50]:
            opp = {'location': row['location'], 'city': row['city']}
            coords = geocode_opportunity(opp)
            if coords:
                c = db.get_db()
                c.execute("UPDATE opportunities SET lat=?, lng=? WHERE id=?",
                          (coords[0], coords[1], row['id']))
                c.commit(); c.close()
            time.sleep(1.1)
    threading.Thread(target=_run, daemon=True).start()
    return jsonify({'status':'started'})


@app.route('/api/opportunity/<int:opp_id>/watchlist', methods=['POST','DELETE'])
def api_watchlist(opp_id):
    conn = db.get_db()
    existing = conn.execute("SELECT id FROM watchlist WHERE opportunity_id=?", (opp_id,)).fetchone()
    if request.method == 'POST':
        if not existing:
            conn.execute("INSERT INTO watchlist(opportunity_id,added_at) VALUES(?,?)",
                         (opp_id, datetime.now(timezone.utc).isoformat()))
            conn.commit()
        conn.close()
        return jsonify({'status':'added','in_watchlist':True})
    else:
        conn.execute("DELETE FROM watchlist WHERE opportunity_id=?", (opp_id,))
        conn.commit(); conn.close()
        return jsonify({'status':'removed','in_watchlist':False})


@app.route('/api/opportunity/<int:opp_id>/pipeline', methods=['POST'])
def api_pipeline(opp_id):
    data = request.get_json() or {}
    stage = data.get('stage','discovered')
    if stage not in Config.PIPELINE_STAGES:
        return jsonify({'error':'Invalid stage'}), 400
    conn = db.get_db()
    now = datetime.now(timezone.utc).isoformat()
    if conn.execute("SELECT id FROM pipeline WHERE opportunity_id=?", (opp_id,)).fetchone():
        conn.execute("UPDATE pipeline SET stage=?, updated_at=? WHERE opportunity_id=?",
                     (stage, now, opp_id))
    else:
        conn.execute("INSERT INTO pipeline(opportunity_id,stage,updated_at) VALUES(?,?,?)",
                     (opp_id, stage, now))
    conn.commit(); conn.close()
    db.log_activity(opp_id, 'pipeline', f'Stage → {stage}')
    return jsonify({'status':'ok','stage':stage})


@app.route('/api/opportunity/<int:opp_id>/note', methods=['POST'])
def api_note(opp_id):
    data = request.get_json() or {}
    content = (data.get('content') or '').strip()
    if not content: return jsonify({'error':'Empty'}), 400
    conn = db.get_db()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("INSERT INTO notes(opportunity_id,content,created_at) VALUES(?,?,?)",
                 (opp_id, content, now))
    conn.commit(); conn.close()
    db.log_activity(opp_id, 'note', content[:80])
    return jsonify({'status':'ok','created_at':now})


@app.route('/api/opportunity/<int:opp_id>/reminder', methods=['POST'])
def api_reminder(opp_id):
    data = request.get_json() or {}
    remind_at = data.get('remind_at','')
    note      = data.get('note','')
    if not remind_at: return jsonify({'error':'No date'}), 400
    conn = db.get_db()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO reminders(opportunity_id,remind_at,note,created_at) VALUES(?,?,?,?)",
        (opp_id, remind_at, note, now)
    )
    conn.commit(); conn.close()
    return jsonify({'status':'ok'})


@app.route('/api/reminder/<int:rid>/done', methods=['POST'])
def api_reminder_done(rid):
    conn = db.get_db()
    conn.execute("UPDATE reminders SET is_done=1 WHERE id=?", (rid,))
    conn.commit(); conn.close()
    return jsonify({'status':'ok'})


@app.route('/api/opportunity/<int:opp_id>/dismiss', methods=['POST'])
def api_dismiss(opp_id):
    conn = db.get_db()
    conn.execute("UPDATE opportunities SET is_active=0 WHERE id=?", (opp_id,))
    conn.commit(); conn.close()
    return jsonify({'status':'dismissed'})


@app.route('/api/saved-search', methods=['POST'])
def api_save_search():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name: return jsonify({'error':'No name'}), 400
    params = {k:v for k,v in data.items() if k != 'name'}
    db.save_search(name, params)
    return jsonify({'status':'ok'})


@app.route('/api/saved-search/<int:sid>', methods=['DELETE'])
def api_delete_saved_search(sid):
    db.delete_saved_search(sid)
    return jsonify({'status':'ok'})


@app.route('/api/settings', methods=['POST'])
def api_settings():
    data = request.get_json() or {}
    for key in ['city','radius','max_price','ebay_api_key','strategy_mode']:
        if key in data: db.set_setting(key, data[key])
    if 'categories' in data:
        db.set_setting('categories', json.dumps(data['categories']))
    return jsonify({'status':'saved'})


@app.route('/api/clear-data', methods=['POST'])
def api_clear_data():
    db.clear_all_opportunities()
    return jsonify({'status': 'cleared'})


@app.route('/api/scan-all-cities', methods=['POST'])
def api_scan_all_cities():
    if scan_state['running']:
        return jsonify({'status': 'already_running'})
    data = request.get_json() or {}
    categories = data.get('categories') or json.loads(
        db.get_setting('categories', json.dumps(list(Config.CATEGORIES.keys()))))
    max_price = data.get('max_price')

    def _run_all():
        global scan_state
        cities = list(Config.CL_CITIES.keys())
        scan_state.update({'running': True, 'count': 0, 'errors': [], 'progress': ''})
        cl = CraigslistScraper()
        total = 0
        for i, city in enumerate(cities):
            scan_state['progress'] = f"Scanning {city.title()} ({i+1}/{len(cities)})..."
            # Craigslist per city
            for cat in categories:
                try:
                    items = cl.search(city, cat, max_price=max_price)
                    total += process_and_store(items, city, geocode=False)
                except Exception as e:
                    scan_state['errors'].append(f"CL {city}/{cat}: {e}")
                time.sleep(Config.REQUEST_DELAY)
            # BizBuySell
            if 'business' in categories:
                try:
                    items = bbs_scraper.search(city, max_price=max_price)
                    total += process_and_store(items, city, geocode=False)
                except Exception as e:
                    scan_state['errors'].append(f"BBS {city}: {e}")
                time.sleep(Config.REQUEST_DELAY)
            # LandWatch
            if any(c in categories for c in ('land', 'real_estate')):
                try:
                    items = landwatch_scraper.search(city, max_price=max_price)
                    total += process_and_store(items, city, geocode=False)
                except Exception as e:
                    scan_state['errors'].append(f"LW {city}: {e}")
                time.sleep(Config.REQUEST_DELAY)
            scan_state['count'] = total
        # GovPlanet once (national)
        if 'equipment' in categories:
            try:
                items = govplanet_scraper.search('', max_price=max_price)
                total += process_and_store(items, 'various', geocode=False)
            except Exception as e:
                scan_state['errors'].append(f"GovPlanet: {e}")
        scan_state['count'] = total
        scan_state['running'] = False
        scan_state['progress'] = f"Nationwide scan complete — {total} listings loaded"
        scan_state['last_run'] = datetime.now(timezone.utc).isoformat()

    threading.Thread(target=_run_all, daemon=True).start()
    return jsonify({'status': 'started'})


@app.route('/api/stats')
def api_stats():
    return jsonify(db.get_stats())


@app.route('/api/alerts/count')
def api_alert_count():
    conn = db.get_db()
    count = conn.execute("SELECT COUNT(*) FROM alerts WHERE is_read=0").fetchone()[0]
    overdue = conn.execute(
        "SELECT COUNT(*) FROM reminders WHERE is_done=0 AND remind_at<=datetime('now')"
    ).fetchone()[0]
    conn.close()
    return jsonify({'alerts': count, 'overdue': overdue, 'total': count + overdue})


@app.route('/api/map-data')
def api_map_data():
    city = request.args.get('city') or db.get_setting('city', Config.DEFAULT_CITY)
    category = request.args.get('category','')
    opps = db.get_opportunities_for_map(city=city if city != 'all' else None)
    if category:
        opps = [o for o in opps if o['category'] == category]
    return jsonify(opps)


@app.route('/api/export/csv')
def api_export_csv():
    filters = {k:v for k,v in request.args.items() if v and k != 'page'}
    opps = db.get_opportunities(filters, limit=500)
    si = io.StringIO()
    writer = csv.DictWriter(si, fieldnames=[
        'id','title','category','price','location','city',
        'score_overall','score_value','score_freshness','score_actionability',
        'contact_quality','urgency_tier','contact_phone','contact_email',
        'next_action','url','scraped_at'
    ])
    writer.writeheader()
    for o in opps:
        writer.writerow({k: o.get(k,'') for k in writer.fieldnames})
    output = si.getvalue()
    return Response(output, mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=tradedistrict_export.csv'})


@app.route('/opportunity/<int:opp_id>/memo')
def deal_memo(opp_id):
    opp = db.get_opportunity(opp_id)
    if not opp: return redirect(url_for('browse'))
    _decode(opp)
    return render_template('memo.html', opp=opp, categories=Config.CATEGORIES,
        generated_at=datetime.now(timezone.utc).strftime('%B %d, %Y at %H:%M UTC'))


# ── Template Filters ──────────────────────────────────────────────────────────

@app.template_filter('currency')
def currency_filter(v):
    if v is None: return 'N/A'
    try:
        v = float(v)
        if v>=1_000_000: return f'${v/1_000_000:.1f}M'
        if v>=1_000:     return f'${v:,.0f}'
        return f'${v:.0f}'
    except: return str(v)


@app.template_filter('score_color')
def score_color_filter(s):
    try:
        s=int(s)
        if s>=75: return '#20C997'
        if s>=55: return '#74C0FC'
        if s>=35: return '#FFD43B'
        return '#FF8787'
    except: return '#ADB5BD'


@app.template_filter('score_label')
def score_label_filter(s):
    try:
        s=int(s)
        if s>=75: return 'Strong'
        if s>=55: return 'Good'
        if s>=35: return 'Fair'
        return 'Weak'
    except: return '—'


@app.template_filter('timeago')
def timeago_filter(dt_str):
    if not dt_str: return '—'
    try:
        from datetime import timezone as tz
        dt = datetime.fromisoformat(dt_str.replace('Z','+00:00'))
        if dt.tzinfo is None: dt = dt.replace(tzinfo=tz.utc)
        s = (datetime.now(dt.tzinfo) - dt).total_seconds()
        if s<60: return 'just now'
        if s<3600: return f'{int(s/60)}m ago'
        if s<86400: return f'{int(s/3600)}h ago'
        if s<604800: return f'{int(s/86400)}d ago'
        return f'{int(s/604800)}w ago'
    except: return '—'


@app.template_filter('urgency_label')
def urgency_label_filter(t):
    return {'hot':'🔥 Hot','new':'🟢 New','stale':'⌛ Stale','normal':''}.get(t,'')


@app.template_filter('contact_label')
def contact_label_filter(q):
    return {
        'full':'Full (phone+email+name)',
        'good':'Good (phone+email)',
        'phone_only':'Phone only',
        'email_only':'Email only',
        'listing_only':'Listing only',
        'none':'No contact',
        'unknown':'Unknown',
    }.get(q, q or '—')


# ── Phase 3 imports & init ────────────────────────────────────────────────────
from intelligence.explainer import explain_score
from intelligence.outreach  import get_templates, template_label, CONTACT_METHODS, CONTACT_OUTCOMES, OUTCOME_LABELS

# Ensure Phase 3 tables exist
with app.app_context():
    db.init_phase3()
    db.normalise_city_codes()


# ── Analytics ─────────────────────────────────────────────────────────────────

@app.route('/analytics')
def analytics():
    data = db.get_analytics_data()
    return render_template('analytics.html', data=data, categories=Config.CATEGORIES)


# ── Outreach ──────────────────────────────────────────────────────────────────

@app.route('/opportunity/<int:opp_id>/outreach')
def outreach(opp_id):
    opp = db.get_opportunity(opp_id)
    if not opp:
        return redirect(url_for('browse'))
    _decode(opp)
    templates = get_templates(opp)
    contact_log = db.get_contact_log(opp_id)
    return render_template('outreach.html',
        opp=opp, templates=templates, template_label=template_label,
        contact_log=contact_log,
        contact_methods=CONTACT_METHODS,
        contact_outcomes=CONTACT_OUTCOMES,
        outcome_labels=OUTCOME_LABELS,
        categories=Config.CATEGORIES)


# ── Activity Feed ─────────────────────────────────────────────────────────────

@app.route('/api/opportunity/<int:opp_id>/activity')
def api_activity(opp_id):
    return jsonify(db.get_activity(opp_id))


# ── Contact Log ───────────────────────────────────────────────────────────────

@app.route('/api/opportunity/<int:opp_id>/contact-log', methods=['POST'])
def api_contact_log(opp_id):
    data = request.get_json() or {}
    method  = data.get('method', 'call')
    outcome = data.get('outcome', 'no_answer')
    notes   = data.get('notes', '')
    db.log_contact(opp_id, method, outcome, notes)
    # Also auto-advance pipeline if outcome suggests it
    if outcome in ('scheduled_visit', 'made_offer', 'deal_progressing'):
        stage_map = {
            'scheduled_visit': 'inspecting',
            'made_offer':      'negotiating',
            'deal_progressing':'pursuing',
        }
        stage = stage_map.get(outcome)
        if stage:
            conn = db.get_db()
            now = datetime.now(timezone.utc).isoformat()
            if conn.execute("SELECT id FROM pipeline WHERE opportunity_id=?", (opp_id,)).fetchone():
                conn.execute("UPDATE pipeline SET stage=?,updated_at=? WHERE opportunity_id=?", (stage,now,opp_id))
            else:
                conn.execute("INSERT INTO pipeline(opportunity_id,stage,updated_at) VALUES(?,?,?)", (opp_id,stage,now))
            conn.commit(); conn.close()
    return jsonify({'status': 'ok'})


# ── Score Explanation ─────────────────────────────────────────────────────────

@app.route('/api/opportunity/<int:opp_id>/explain')
def api_explain(opp_id):
    opp = db.get_opportunity(opp_id)
    if not opp:
        return jsonify({'error': 'not found'}), 404
    _decode(opp)
    ctx = db.get_market_context(opp.get('category'), opp.get('city'), exclude_id=opp_id)
    explanation = explain_score(opp, ctx)
    return jsonify({'explanation': explanation, 'market_context': ctx})


# ── Duplicates ────────────────────────────────────────────────────────────────

@app.route('/duplicates')
def duplicates():
    dupes = db.get_duplicate_candidates()
    return render_template('duplicates.html', dupes=dupes, categories=Config.CATEGORIES)


@app.route('/api/opportunity/<int:opp_id>/mark-duplicate', methods=['POST'])
def api_mark_duplicate(opp_id):
    """Dismiss one of a duplicate pair."""
    db_conn = db.get_db()
    db_conn.execute("UPDATE opportunities SET is_active=0 WHERE id=?", (opp_id,))
    db_conn.commit(); db_conn.close()
    return jsonify({'status': 'dismissed'})


if __name__ == '__main__':
    db.init_db()
    db.init_phase3()
    db.normalise_city_codes()
    print("[Trade District] → http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
