import sqlite3
import json
from datetime import datetime, timezone
from config import Config


def get_db():
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS opportunities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            source_id TEXT,
            url TEXT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL,
            price_text TEXT,
            location TEXT,
            city TEXT,
            lat REAL,
            lng REAL,
            description TEXT,
            contact_name TEXT,
            contact_phone TEXT,
            contact_email TEXT,
            posted_at TEXT,
            scraped_at TEXT NOT NULL,
            updated_at TEXT,
            images TEXT DEFAULT '[]',
            extra TEXT DEFAULT '{}',
            score_overall INTEGER DEFAULT 0,
            score_value INTEGER DEFAULT 0,
            score_freshness INTEGER DEFAULT 0,
            score_actionability INTEGER DEFAULT 0,
            score_completeness INTEGER DEFAULT 0,
            signals TEXT DEFAULT '[]',
            next_action TEXT,
            is_active INTEGER DEFAULT 1,
            contact_quality TEXT DEFAULT 'unknown',
            urgency_tier TEXT DEFAULT 'normal',
            UNIQUE(source, source_id)
        );
        CREATE INDEX IF NOT EXISTS idx_opp_category ON opportunities(category);
        CREATE INDEX IF NOT EXISTS idx_opp_score    ON opportunities(score_overall);
        CREATE INDEX IF NOT EXISTS idx_opp_city     ON opportunities(city);
        CREATE INDEX IF NOT EXISTS idx_opp_price    ON opportunities(price);
        CREATE INDEX IF NOT EXISTS idx_opp_active   ON opportunities(is_active);
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id INTEGER NOT NULL,
            added_at TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
        );
        CREATE TABLE IF NOT EXISTS pipeline (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id INTEGER NOT NULL UNIQUE,
            stage TEXT NOT NULL DEFAULT 'discovered',
            updated_at TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
        );
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
        );
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id INTEGER,
            type TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
        );
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id INTEGER NOT NULL,
            remind_at TEXT NOT NULL,
            note TEXT,
            is_done INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
        );
        CREATE INDEX IF NOT EXISTS idx_reminder_date ON reminders(remind_at);
        CREATE TABLE IF NOT EXISTS saved_searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            params TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_run TEXT,
            last_count INTEGER DEFAULT 0,
            alert_enabled INTEGER DEFAULT 1,
            run_count INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    ''')
    # Safe migration — add new columns to existing installs
    for col, defn in [
        ('lat','REAL'), ('lng','REAL'),
        ("contact_quality","TEXT DEFAULT 'unknown'"),
        ("urgency_tier","TEXT DEFAULT 'normal'"),
    ]:
        try: c.execute(f"ALTER TABLE opportunities ADD COLUMN {col} {defn}")
        except: pass
    for col, defn in [('last_count','INTEGER DEFAULT 0'),('run_count','INTEGER DEFAULT 0')]:
        try: c.execute(f"ALTER TABLE saved_searches ADD COLUMN {col} {defn}")
        except: pass

    defaults = {
        'city': Config.DEFAULT_CITY,
        'radius': str(Config.DEFAULT_RADIUS_MILES),
        'max_price': str(Config.DEFAULT_MAX_PRICE),
        'categories': json.dumps(list(Config.CATEGORIES.keys())),
        'ebay_api_key': '',
        'strategy_mode': 'balanced',
    }
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v))
    conn.commit()
    conn.close()


def get_setting(key, default=None):
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row['value'] if row else default


def set_setting(key, value):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, str(value)))
    conn.commit()
    conn.close()


def _calc_contact_quality(data):
    has_phone = bool(data.get('contact_phone'))
    has_email = bool(data.get('contact_email'))
    has_name  = bool(data.get('contact_name'))
    if has_phone and has_email and has_name: return 'full'
    if has_phone and has_email:              return 'good'
    if has_phone:                            return 'phone_only'
    if has_email:                            return 'email_only'
    if data.get('url'):                      return 'listing_only'
    return 'none'


def _calc_urgency_tier(data):
    text = ((data.get('title') or '') + ' ' + (data.get('description') or '')).lower()
    hot_terms = ['must sell','price reduced','motivated','urgent','estate sale',
                 'liquidat','retiring','price drop','relocation','divorce']
    if any(t in text for t in hot_terms):
        return 'hot'
    posted = data.get('posted_at') or data.get('scraped_at', '')
    if posted:
        try:
            from datetime import timezone
            dt = datetime.fromisoformat(posted.replace('Z','+00:00'))
            if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
            hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
            if hours < 12:  return 'new'
            if hours > 480: return 'stale'
        except: pass
    return 'normal'


def upsert_opportunity(data):
    conn = get_db()
    c = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    contact_quality = _calc_contact_quality(data)
    urgency_tier    = _calc_urgency_tier(data)

    existing = c.execute(
        "SELECT id, price FROM opportunities WHERE source=? AND source_id=?",
        (data.get('source',''), data.get('source_id',''))
    ).fetchone()

    if existing:
        old_price = existing['price']
        new_price = data.get('price')
        c.execute('''
            UPDATE opportunities SET
                title=?, price=?, price_text=?, location=?, description=?,
                contact_name=?, contact_phone=?, contact_email=?,
                images=?, extra=?, updated_at=?, is_active=1,
                score_overall=?, score_value=?, score_freshness=?,
                score_actionability=?, score_completeness=?,
                signals=?, next_action=?, contact_quality=?, urgency_tier=?,
                lat=COALESCE(?,lat), lng=COALESCE(?,lng)
            WHERE id=?
        ''', (
            data.get('title'), data.get('price'), data.get('price_text'),
            data.get('location'), data.get('description'),
            data.get('contact_name'), data.get('contact_phone'), data.get('contact_email'),
            json.dumps(data.get('images',[])), json.dumps(data.get('extra',{})),
            now,
            data.get('score_overall',0), data.get('score_value',0),
            data.get('score_freshness',0), data.get('score_actionability',0),
            data.get('score_completeness',0),
            json.dumps(data.get('signals',[])), data.get('next_action',''),
            contact_quality, urgency_tier,
            data.get('lat'), data.get('lng'),
            existing['id']
        ))
        if new_price and old_price and new_price < old_price * 0.95:
            add_alert(existing['id'], 'price_drop',
                      f"Price dropped from ${old_price:,.0f} to ${new_price:,.0f}", conn)
        conn.commit()
        opp_id, is_new = existing['id'], False
    else:
        c.execute('''
            INSERT INTO opportunities (
                source, source_id, url, title, category, price, price_text,
                location, city, lat, lng, description,
                contact_name, contact_phone, contact_email,
                posted_at, scraped_at, images, extra,
                score_overall, score_value, score_freshness,
                score_actionability, score_completeness,
                signals, next_action, contact_quality, urgency_tier
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            data.get('source'), data.get('source_id'), data.get('url'),
            data.get('title'), data.get('category'), data.get('price'),
            data.get('price_text'), data.get('location'), data.get('city'),
            data.get('lat'), data.get('lng'),
            data.get('description'), data.get('contact_name'),
            data.get('contact_phone'), data.get('contact_email'),
            data.get('posted_at'), now,
            json.dumps(data.get('images',[])), json.dumps(data.get('extra',{})),
            data.get('score_overall',0), data.get('score_value',0),
            data.get('score_freshness',0), data.get('score_actionability',0),
            data.get('score_completeness',0),
            json.dumps(data.get('signals',[])), data.get('next_action',''),
            contact_quality, urgency_tier
        ))
        opp_id = c.lastrowid
        add_alert(opp_id, 'new_listing',
                  f"New {data.get('category')} listing: {data.get('title','')[:60]}", conn)
        conn.commit()
        is_new = True

    conn.close()
    return opp_id, is_new


def add_alert(opportunity_id, alert_type, message, conn=None):
    close_after = conn is None
    if conn is None: conn = get_db()
    conn.execute(
        "INSERT INTO alerts(opportunity_id, type, message, created_at) VALUES(?,?,?,?)",
        (opportunity_id, alert_type, message, datetime.now(timezone.utc).isoformat())
    )
    if close_after:
        conn.commit()
        conn.close()


def get_opportunities(filters=None, limit=60, offset=0):
    conn = get_db()
    where = ["o.is_active=1"]
    params = []

    if filters:
        if filters.get('category'):
            where.append("o.category=?"); params.append(filters['category'])
        if filters.get('min_price'):
            try:
                where.append("o.price>=?"); params.append(float(filters['min_price']))
            except (ValueError, TypeError): pass
        if filters.get('max_price'):
            try:
                where.append("o.price<=?"); params.append(float(filters['max_price']))
            except (ValueError, TypeError): pass
        if filters.get('city'):
            where.append("o.city=?"); params.append(filters['city'])
        if filters.get('query'):
            where.append("(o.title LIKE ? OR o.description LIKE ? OR o.location LIKE ?)")
            q = f"%{filters['query']}%"; params.extend([q, q, q])
        if filters.get('min_score'):
            try:
                where.append("o.score_overall>=?"); params.append(int(filters['min_score']))
            except (ValueError, TypeError): pass
        if filters.get('watchlist_only'):
            where.append("w.id IS NOT NULL")
        if filters.get('pipeline_only'):
            where.append("p.id IS NOT NULL")
        if filters.get('has_contact'):
            where.append("o.contact_quality NOT IN ('none','listing_only','unknown')")
        if filters.get('hide_stale'):
            where.append("o.urgency_tier != 'stale'")
        if filters.get('hide_incomplete'):
            where.append("o.score_completeness >= 40")
        if filters.get('urgency'):
            where.append("o.urgency_tier=?"); params.append(filters['urgency'])
        if filters.get('has_location'):
            where.append("o.lat IS NOT NULL AND o.lng IS NOT NULL")

    sort = (filters.get('sort','score') if filters else 'score')
    order = {
        'score':      'o.score_overall DESC',
        'newest':     'o.scraped_at DESC',
        'price_asc':  'o.price ASC NULLS LAST',
        'price_desc': 'o.price DESC',
        'freshness':  'o.score_freshness DESC',
        'value':      'o.score_value DESC',
        'actionable': 'o.score_actionability DESC',
    }.get(sort, 'o.score_overall DESC')

    sql = f'''
        SELECT o.*,
               CASE WHEN w.id IS NOT NULL THEN 1 ELSE 0 END as in_watchlist,
               CASE WHEN p.id IS NOT NULL THEN 1 ELSE 0 END as in_pipeline,
               p.stage as pipeline_stage
        FROM opportunities o
        LEFT JOIN watchlist w ON o.id = w.opportunity_id
        LEFT JOIN pipeline p  ON o.id = p.opportunity_id
        WHERE {" AND ".join(where)}
        ORDER BY {order}
        LIMIT ? OFFSET ?
    '''
    params.extend([limit, offset])
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_opportunity(opp_id):
    conn = get_db()
    row = conn.execute('''
        SELECT o.*,
               CASE WHEN w.id IS NOT NULL THEN 1 ELSE 0 END as in_watchlist,
               p.stage as pipeline_stage,
               p.notes as pipeline_notes
        FROM opportunities o
        LEFT JOIN watchlist w ON o.id = w.opportunity_id
        LEFT JOIN pipeline p  ON o.id = p.opportunity_id
        WHERE o.id=?
    ''', (opp_id,)).fetchone()
    notes = conn.execute(
        "SELECT * FROM notes WHERE opportunity_id=? ORDER BY created_at DESC", (opp_id,)
    ).fetchall()
    reminders = conn.execute(
        "SELECT * FROM reminders WHERE opportunity_id=? AND is_done=0 ORDER BY remind_at ASC",
        (opp_id,)
    ).fetchall()
    conn.close()
    if not row: return None
    result = dict(row)
    result['notes_list']     = [dict(n) for n in notes]
    result['reminders_list'] = [dict(r) for r in reminders]
    return result


def get_opportunities_for_map(city=None, limit=300):
    conn = get_db()
    where = ["o.is_active=1"]
    params = []
    if city:
        where.append("o.city=?"); params.append(city)
    rows = conn.execute(f'''
        SELECT o.id, o.title, o.category, o.price, o.price_text, o.location,
               o.lat, o.lng, o.score_overall, o.urgency_tier, o.contact_quality,
               CASE WHEN w.id IS NOT NULL THEN 1 ELSE 0 END as in_watchlist
        FROM opportunities o
        LEFT JOIN watchlist w ON o.id = w.opportunity_id
        WHERE {" AND ".join(where)}
        ORDER BY o.score_overall DESC LIMIT ?
    ''', params + [limit]).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_overdue_reminders():
    conn = get_db()
    rows = conn.execute('''
        SELECT r.*, o.title as opp_title, o.category as opp_category
        FROM reminders r JOIN opportunities o ON r.opportunity_id=o.id
        WHERE r.is_done=0 AND r.remind_at <= datetime('now')
        ORDER BY r.remind_at ASC LIMIT 20
    ''').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_upcoming_reminders(days=7):
    conn = get_db()
    rows = conn.execute('''
        SELECT r.*, o.title as opp_title, o.category as opp_category
        FROM reminders r JOIN opportunities o ON r.opportunity_id=o.id
        WHERE r.is_done=0
          AND r.remind_at > datetime('now')
          AND r.remind_at <= datetime('now', ?||' days')
        ORDER BY r.remind_at ASC LIMIT 20
    ''', (str(days),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_search(name, params_dict):
    conn = get_db()
    conn.execute(
        "INSERT INTO saved_searches(name,params,created_at) VALUES(?,?,?)",
        (name, json.dumps(params_dict), datetime.now(timezone.utc).isoformat())
    )
    conn.commit(); conn.close()


def get_saved_searches():
    conn = get_db()
    rows = conn.execute("SELECT * FROM saved_searches ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_saved_search(search_id):
    conn = get_db()
    conn.execute("DELETE FROM saved_searches WHERE id=?", (search_id,))
    conn.commit(); conn.close()


def update_saved_search_run(search_id, count):
    conn = get_db()
    conn.execute(
        "UPDATE saved_searches SET last_run=?, last_count=?, run_count=run_count+1 WHERE id=?",
        (datetime.now(timezone.utc).isoformat(), count, search_id)
    )
    conn.commit(); conn.close()


def get_stats():
    conn = get_db()
    stats = {}
    def q(sql, *p): return conn.execute(sql, p).fetchone()[0]
    stats['total']            = q("SELECT COUNT(*) FROM opportunities WHERE is_active=1")
    stats['new_today']        = q("SELECT COUNT(*) FROM opportunities WHERE date(scraped_at)=date('now') AND is_active=1")
    stats['watchlist']        = q("SELECT COUNT(*) FROM watchlist")
    stats['pipeline']         = q("SELECT COUNT(*) FROM pipeline")
    stats['unread_alerts']    = q("SELECT COUNT(*) FROM alerts WHERE is_read=0")
    stats['overdue_reminders']= q("SELECT COUNT(*) FROM reminders WHERE is_done=0 AND remind_at<=datetime('now')")
    stats['hot']              = q("SELECT COUNT(*) FROM opportunities WHERE is_active=1 AND urgency_tier='hot'")
    stats['mapped']           = q("SELECT COUNT(*) FROM opportunities WHERE is_active=1 AND lat IS NOT NULL")
    stats['avg_score']        = conn.execute(
        "SELECT AVG(score_overall) FROM opportunities WHERE is_active=1 AND score_overall>0"
    ).fetchone()[0] or 0
    rows = conn.execute(
        "SELECT category, COUNT(*) as c FROM opportunities WHERE is_active=1 GROUP BY category"
    ).fetchall()
    stats['by_category'] = {r['category']: r['c'] for r in rows}
    conn.close()
    return stats


# ── Phase 3: Contact Log, Activity Feed, Duplicates ──────────────────────────

def init_phase3(conn=None):
    """Create Phase 3 tables. Safe to call multiple times."""
    close = conn is None
    if conn is None:
        conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS contact_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id INTEGER NOT NULL,
            method TEXT NOT NULL DEFAULT 'call',
            outcome TEXT NOT NULL DEFAULT 'no_answer',
            notes TEXT,
            contacted_at TEXT NOT NULL,
            FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
        );
        CREATE INDEX IF NOT EXISTS idx_contact_opp ON contact_log(opportunity_id);

        CREATE TABLE IF NOT EXISTS activity_feed (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            detail TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
        );
        CREATE INDEX IF NOT EXISTS idx_activity_opp ON activity_feed(opportunity_id);
        CREATE INDEX IF NOT EXISTS idx_activity_time ON activity_feed(created_at);

        CREATE TABLE IF NOT EXISTS duplicate_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opp_id_a INTEGER NOT NULL,
            opp_id_b INTEGER NOT NULL,
            reason TEXT,
            confidence INTEGER DEFAULT 50,
            detected_at TEXT NOT NULL,
            UNIQUE(opp_id_a, opp_id_b)
        );
    ''')
    if close:
        conn.commit()
        conn.close()


def log_activity(opportunity_id, action_type, detail='', conn=None):
    close = conn is None
    if conn is None:
        conn = get_db()
    conn.execute(
        "INSERT INTO activity_feed(opportunity_id,action_type,detail,created_at) VALUES(?,?,?,?)",
        (opportunity_id, action_type, detail, datetime.now(timezone.utc).isoformat())
    )
    if close:
        conn.commit()
        conn.close()


def get_activity(opportunity_id, limit=30):
    conn = get_db()
    rows = conn.execute('''
        SELECT * FROM activity_feed
        WHERE opportunity_id=?
        ORDER BY created_at DESC LIMIT ?
    ''', (opportunity_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def log_contact(opportunity_id, method, outcome, notes=''):
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO contact_log(opportunity_id,method,outcome,notes,contacted_at) VALUES(?,?,?,?,?)",
        (opportunity_id, method, outcome, notes, now)
    )
    label = f"{method.title()} → {outcome.replace('_',' ').title()}"
    if notes:
        label += f": {notes[:60]}"
    conn.execute(
        "INSERT INTO activity_feed(opportunity_id,action_type,detail,created_at) VALUES(?,?,?,?)",
        (opportunity_id, 'contact', label, now)
    )
    conn.commit()
    conn.close()


def get_contact_log(opportunity_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM contact_log WHERE opportunity_id=? ORDER BY contacted_at DESC",
        (opportunity_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_analytics_data():
    """Return rich analytics payload for the analytics page."""
    conn = get_db()
    data = {}

    # Score distribution buckets
    buckets = [(0,25,'Weak'),(25,50,'Fair'),(50,75,'Good'),(75,101,'Strong')]
    data['score_dist'] = []
    for lo, hi, label in buckets:
        c = conn.execute(
            "SELECT COUNT(*) FROM opportunities WHERE is_active=1 AND score_overall>=? AND score_overall<?",
            (lo, hi)
        ).fetchone()[0]
        data['score_dist'].append({'label': label, 'count': c, 'range': f'{lo}–{hi}'})

    # Category breakdown with avg score and avg price
    rows = conn.execute('''
        SELECT category,
               COUNT(*) as count,
               AVG(score_overall) as avg_score,
               AVG(price) as avg_price,
               MIN(price) as min_price,
               MAX(price) as max_price,
               SUM(CASE WHEN urgency_tier='hot' THEN 1 ELSE 0 END) as hot_count
        FROM opportunities WHERE is_active=1
        GROUP BY category
    ''').fetchall()
    data['by_category'] = [dict(r) for r in rows]

    # Daily inflow (last 14 days)
    rows = conn.execute('''
        SELECT date(scraped_at) as day, COUNT(*) as count
        FROM opportunities WHERE is_active=1
          AND scraped_at >= datetime('now', '-14 days')
        GROUP BY day ORDER BY day ASC
    ''').fetchall()
    data['daily_inflow'] = [dict(r) for r in rows]

    # Price range distribution (non-null prices)
    price_ranges = [
        (0, 10000, 'Under $10k'),
        (10000, 50000, '$10k–$50k'),
        (50000, 100000, '$50k–$100k'),
        (100000, 250000, '$100k–$250k'),
        (250000, 500000, '$250k–$500k'),
        (500000, 1000000, '$500k–$1M'),
        (1000000, 999999999, 'Over $1M'),
    ]
    data['price_dist'] = []
    for lo, hi, label in price_ranges:
        c = conn.execute(
            "SELECT COUNT(*) FROM opportunities WHERE is_active=1 AND price>=? AND price<?",
            (lo, hi)
        ).fetchone()[0]
        if c > 0:
            data['price_dist'].append({'label': label, 'count': c})

    # Contact quality breakdown
    rows = conn.execute('''
        SELECT contact_quality, COUNT(*) as count
        FROM opportunities WHERE is_active=1
        GROUP BY contact_quality ORDER BY count DESC
    ''').fetchall()
    data['contact_quality'] = [dict(r) for r in rows]

    # Urgency tier breakdown
    rows = conn.execute('''
        SELECT urgency_tier, COUNT(*) as count
        FROM opportunities WHERE is_active=1
        GROUP BY urgency_tier ORDER BY count DESC
    ''').fetchall()
    data['urgency_breakdown'] = [dict(r) for r in rows]

    # Top opportunities (for table)
    rows = conn.execute('''
        SELECT id, title, category, price, score_overall, urgency_tier,
               contact_quality, scraped_at
        FROM opportunities WHERE is_active=1
        ORDER BY score_overall DESC LIMIT 10
    ''').fetchall()
    data['top_opps'] = [dict(r) for r in rows]

    # Summary stats
    data['summary'] = {
        'total':     conn.execute("SELECT COUNT(*) FROM opportunities WHERE is_active=1").fetchone()[0],
        'avg_score': conn.execute("SELECT AVG(score_overall) FROM opportunities WHERE is_active=1").fetchone()[0] or 0,
        'with_price':conn.execute("SELECT COUNT(*) FROM opportunities WHERE is_active=1 AND price IS NOT NULL").fetchone()[0],
        'with_contact':conn.execute("SELECT COUNT(*) FROM opportunities WHERE is_active=1 AND contact_quality NOT IN ('none','unknown','listing_only')").fetchone()[0],
        'hot':       conn.execute("SELECT COUNT(*) FROM opportunities WHERE is_active=1 AND urgency_tier='hot'").fetchone()[0],
        'sources':   conn.execute("SELECT COUNT(DISTINCT source) FROM opportunities WHERE is_active=1").fetchone()[0],
        'cities':    conn.execute("SELECT COUNT(DISTINCT city) FROM opportunities WHERE is_active=1").fetchone()[0],
        'pipeline':  conn.execute("SELECT COUNT(*) FROM pipeline").fetchone()[0],
        'contacts_logged': conn.execute("SELECT COUNT(*) FROM contact_log").fetchone()[0] if _table_exists(conn, 'contact_log') else 0,
    }

    conn.close()
    return data


def _table_exists(conn, name):
    return conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()[0] > 0


def get_duplicate_candidates():
    """Find potential duplicates by matching phone, email, or title similarity."""
    conn = get_db()
    dupes = []

    # Same phone number across different sources
    rows = conn.execute('''
        SELECT a.id as id_a, b.id as id_b,
               a.title as title_a, b.title as title_b,
               a.source as source_a, b.source as source_b,
               a.price as price_a, b.price as price_b,
               a.contact_phone as phone,
               'same_phone' as reason, 90 as confidence
        FROM opportunities a
        JOIN opportunities b ON a.contact_phone = b.contact_phone
          AND a.id < b.id
          AND a.contact_phone IS NOT NULL
          AND a.contact_phone != ''
        WHERE a.is_active=1 AND b.is_active=1
        LIMIT 50
    ''').fetchall()
    dupes.extend([dict(r) for r in rows])

    # Same email
    rows = conn.execute('''
        SELECT a.id as id_a, b.id as id_b,
               a.title as title_a, b.title as title_b,
               a.source as source_a, b.source as source_b,
               a.price as price_a, b.price as price_b,
               a.contact_email as email,
               'same_email' as reason, 85 as confidence
        FROM opportunities a
        JOIN opportunities b ON a.contact_email = b.contact_email
          AND a.id < b.id
          AND a.contact_email IS NOT NULL
          AND a.contact_email != ''
        WHERE a.is_active=1 AND b.is_active=1
        LIMIT 50
    ''').fetchall()
    dupes.extend([dict(r) for r in rows])

    conn.close()
    # Deduplicate by (id_a, id_b)
    seen = set()
    unique = []
    for d in dupes:
        key = (d['id_a'], d['id_b'])
        if key not in seen:
            seen.add(key)
            unique.append(d)
    return unique


def get_market_context(category, city=None, exclude_id=None):
    """Return price stats for comparable listings."""
    conn = get_db()
    where = ["is_active=1", "category=?", "price IS NOT NULL", "price > 0"]
    params = [category]
    if city:
        where.append("city=?")
        params.append(city)
    if exclude_id:
        where.append("id != ?")
        params.append(exclude_id)

    rows = conn.execute(
        f"SELECT price, score_overall FROM opportunities WHERE {' AND '.join(where)} ORDER BY price ASC",
        params
    ).fetchall()
    conn.close()

    if not rows:
        return None

    prices = [r['price'] for r in rows]
    n = len(prices)
    avg = sum(prices) / n
    prices_sorted = sorted(prices)
    median = prices_sorted[n // 2]
    p25 = prices_sorted[int(n * 0.25)]
    p75 = prices_sorted[int(n * 0.75)]

    return {
        'count': n,
        'avg': avg,
        'median': median,
        'min': prices_sorted[0],
        'max': prices_sorted[-1],
        'p25': p25,
        'p75': p75,
        'prices': prices_sorted[:50],  # for chart
    }


# ── City normalisation (fixes CL subdomain → display name) ────────────────────

# Reverse map: subdomain code → display name
_CL_CODE_TO_DISPLAY = {
    'miami':'miami','newyork':'new york','losangeles':'los angeles',
    'chicago':'chicago','houston':'houston','phoenix':'phoenix',
    'philadelphia':'philadelphia','sanantonio':'san antonio',
    'sandiego':'san diego','dallas':'dallas','austin':'austin',
    'seattle':'seattle','denver':'denver','boston':'boston',
    'atlanta':'atlanta','nashville':'nashville','portland':'portland',
    'lasvegas':'las vegas','orlando':'orlando','tampa':'tampa',
    'broward':'fort lauderdale','jacksonville':'jacksonville',
    'charlotte':'charlotte','raleigh':'raleigh','minneapolis':'minneapolis',
    'stlouis':'st louis','pittsburgh':'pittsburgh','cleveland':'cleveland',
    'columbus':'columbus','indianapolis':'indianapolis',
}

def normalise_city_codes():
    """One-time migration: convert stored CL subdomain codes to display names."""
    conn = get_db()
    for code, display in _CL_CODE_TO_DISPLAY.items():
        if code != display:  # only update where they differ
            conn.execute(
                "UPDATE opportunities SET city=? WHERE city=?",
                (display, code)
            )
    conn.commit()
    conn.close()


def clear_all_opportunities():
    """Delete all scraped listings and related data. Keeps settings, pipeline notes, saved searches."""
    conn = get_db()
    conn.executescript('''
        DELETE FROM alerts;
        DELETE FROM reminders;
        DELETE FROM notes;
        DELETE FROM watchlist;
        DELETE FROM pipeline;
        DELETE FROM contact_log;
        DELETE FROM activity_feed;
        DELETE FROM duplicate_links;
        DELETE FROM opportunities;
    ''')
    conn.commit()
    conn.close()
