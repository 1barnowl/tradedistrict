"""
Score explanation engine.
Takes an opportunity + market context and produces a plain-English
reason for each sub-score, plus an overall verdict.
"""
from datetime import datetime, timezone


def explain_score(opp: dict, market_ctx: dict = None) -> dict:
    """Return a dict with 'value', 'freshness', 'actionability', 'completeness', 'overall' keys,
    each containing a short plain-English explanation."""
    return {
        'value':        _explain_value(opp, market_ctx),
        'freshness':    _explain_freshness(opp),
        'actionability':_explain_actionability(opp),
        'completeness': _explain_completeness(opp),
        'overall':      _explain_overall(opp),
    }


def _explain_value(opp, ctx):
    price = opp.get('price')
    score = opp.get('score_value', 0)
    cat   = (opp.get('category') or '').replace('_', ' ')

    if not price:
        return "No price listed — value cannot be assessed against market comps."

    if ctx and ctx.get('count', 0) >= 3:
        avg = ctx['avg']
        diff_pct = ((price - avg) / avg) * 100
        n = ctx['count']
        if diff_pct < -30:
            return f"Priced {abs(diff_pct):.0f}% below the average of ${avg:,.0f} across {n} comparable {cat} listings. Significant potential value."
        elif diff_pct < -15:
            return f"Priced {abs(diff_pct):.0f}% below the category average (${avg:,.0f} across {n} listings). Looks favorable."
        elif diff_pct < -5:
            return f"Slightly below the category average of ${avg:,.0f} across {n} comparable listings."
        elif diff_pct < 5:
            return f"Priced near the category average of ${avg:,.0f} (within 5%). Fair market value."
        elif diff_pct < 20:
            return f"Priced {diff_pct:.0f}% above the category average of ${avg:,.0f}. May be overpriced."
        else:
            return f"Priced {diff_pct:.0f}% above the category average of ${avg:,.0f}. Needs strong justification."
    else:
        # Heuristic fallback
        if score >= 85:
            return f"Price of ${price:,.0f} appears low for the {cat} category based on typical market ranges."
        elif score >= 65:
            return f"Price of ${price:,.0f} is reasonable relative to typical {cat} listings."
        elif score >= 45:
            return f"Price of ${price:,.0f} is in the mid-range for {cat} opportunities."
        else:
            return f"Price of ${price:,.0f} appears high for the {cat} category. Verify what's included."


def _explain_freshness(opp):
    posted = opp.get('posted_at') or opp.get('scraped_at', '')
    score  = opp.get('score_freshness', 0)
    if not posted:
        return "No post date available — freshness unknown."
    try:
        dt = datetime.fromisoformat(posted.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        if hours < 6:
            return f"Posted less than 6 hours ago. Very fresh — act quickly before other buyers."
        elif hours < 24:
            return f"Posted {hours:.0f} hours ago. Still very fresh."
        elif hours < 72:
            days = hours / 24
            return f"Posted {days:.1f} days ago. Recently listed, good timing."
        elif hours < 336:
            days = hours / 24
            return f"Posted {days:.0f} days ago. Active listing but getting older."
        elif hours < 720:
            days = hours / 24
            return f"Posted {days:.0f} days ago. Listing may be losing traction — could signal negotiation room."
        else:
            days = hours / 24
            return f"Posted {days:.0f} days ago. Stale listing — verify it's still available before reaching out."
    except Exception:
        return "Post date could not be parsed."


def _explain_actionability(opp):
    has_phone = bool(opp.get('contact_phone'))
    has_email = bool(opp.get('contact_email'))
    has_name  = bool(opp.get('contact_name'))
    has_url   = bool(opp.get('url'))
    score     = opp.get('score_actionability', 0)

    if has_phone and has_email and has_name:
        return f"Full contact details available: name, phone ({opp['contact_phone']}), and email. Easiest path to quick outreach."
    elif has_phone and has_email:
        return f"Phone and email both available. Strong actionability — call or email directly."
    elif has_phone:
        return f"Phone number available ({opp['contact_phone']}). No email listed — call is your best path."
    elif has_email:
        return f"Email available ({opp['contact_email']}). No phone listed — email first."
    elif has_url:
        return "No direct contact info extracted. Visit the original listing to find seller contact details."
    else:
        return "No contact information or listing URL available. Very difficult to act on without more research."


def _explain_completeness(opp):
    score = opp.get('score_completeness', 0)
    missing = []
    if not opp.get('price'):        missing.append('price')
    if not opp.get('location'):     missing.append('location')
    if not opp.get('description'):  missing.append('description')
    if not opp.get('url'):          missing.append('source URL')

    desc = opp.get('description') or ''
    images = opp.get('images', [])
    if isinstance(images, str):
        import json
        try: images = json.loads(images)
        except: images = []

    if score >= 85:
        return f"Well-documented listing with {len(desc)} characters of description{' and '+str(len(images))+' images' if images else ''}. High confidence in the data."
    elif score >= 65:
        parts = []
        if desc: parts.append(f"{len(desc)}-char description")
        if images: parts.append(f"{len(images)} images")
        suffix = (', '.join(parts) + '.') if parts else ''
        missing_str = (f" Missing: {', '.join(missing)}." if missing else '')
        return f"Moderately complete listing. {suffix}{missing_str}"
    elif score >= 40:
        return f"Sparse listing. Missing: {', '.join(missing) if missing else 'additional detail'}. Consider requesting more info from seller."
    else:
        return f"Very thin listing — almost no usable detail. Major missing fields: {', '.join(missing)}. Treat with caution."


def _explain_overall(opp):
    score = opp.get('score_overall', 0)
    cat   = (opp.get('category') or '').replace('_', ' ')
    sv    = opp.get('score_value', 0)
    sf    = opp.get('score_freshness', 0)
    sa    = opp.get('score_actionability', 0)
    sc    = opp.get('score_completeness', 0)

    strengths = []
    weaknesses = []
    if sv >= 70:  strengths.append('favorable pricing')
    elif sv < 40: weaknesses.append('high price vs. market')
    if sf >= 80:  strengths.append('recently posted')
    elif sf < 30: weaknesses.append('stale listing')
    if sa >= 70:  strengths.append('direct contact available')
    elif sa < 30: weaknesses.append('no contact info')
    if sc >= 70:  strengths.append('well-documented')
    elif sc < 40: weaknesses.append('incomplete listing')

    if score >= 75:
        s = f"Strong opportunity overall. " + (f"Key advantages: {', '.join(strengths)}." if strengths else '')
        if weaknesses: s += f" Watch out for: {', '.join(weaknesses)}."
        return s
    elif score >= 55:
        s = f"Solid {cat} opportunity with room to investigate further."
        if strengths: s += f" Positives: {', '.join(strengths)}."
        if weaknesses: s += f" Concerns: {', '.join(weaknesses)}."
        return s
    elif score >= 35:
        s = f"Fair listing — proceed with caution."
        if strengths: s += f" Positives: {', '.join(strengths)}."
        if weaknesses: s += f" Issues: {', '.join(weaknesses)}."
        return s
    else:
        s = f"Weak opportunity on current data."
        if weaknesses: s += f" Primary issues: {', '.join(weaknesses)}."
        s += " May improve if more information becomes available."
        return s
