from datetime import datetime, timezone

STRATEGY_WEIGHTS = {
    'balanced':     {'freshness':0.20,'value':0.35,'actionability':0.25,'completeness':0.20},
    'bargain':      {'freshness':0.10,'value':0.55,'actionability':0.15,'completeness':0.20},
    'quick_flip':   {'freshness':0.30,'value':0.40,'actionability':0.20,'completeness':0.10},
    'long_hold':    {'freshness':0.05,'value':0.50,'actionability':0.10,'completeness':0.35},
    'low_risk':     {'freshness':0.15,'value':0.25,'actionability':0.25,'completeness':0.35},
    'high_contact': {'freshness':0.20,'value':0.20,'actionability':0.50,'completeness':0.10},
}

STRATEGY_LABELS = {
    'balanced':     '⚖️ Balanced',
    'bargain':      '💰 Bargain Hunter',
    'quick_flip':   '⚡ Quick Flip',
    'long_hold':    '🏦 Long Hold',
    'low_risk':     '🛡️ Low Risk',
    'high_contact': '📞 High Contact',
}


class OpportunityScorer:
    def score(self, opp, peers=None, strategy='balanced'):
        weights = STRATEGY_WEIGHTS.get(strategy, STRATEGY_WEIGHTS['balanced'])
        subs = {
            'freshness':     self._freshness(opp),
            'actionability': self._actionability(opp),
            'completeness':  self._completeness(opp),
            'value':         self._value(opp, peers or []),
        }
        overall = int(sum(subs[k] * weights[k] for k in subs))
        return {**subs, 'overall': overall,
                'signals': self._signals(opp, subs),
                'next_action': self._next_action(opp, {**subs, 'overall': overall})}

    def _freshness(self, opp):
        posted = opp.get('posted_at') or opp.get('scraped_at','')
        if not posted: return 30
        try:
            dt = datetime.fromisoformat(posted.replace('Z','+00:00'))
            if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
            h = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
            if h<6: return 100
            if h<24: return 90
            if h<48: return 78
            if h<72: return 65
            if h<168: return 52
            if h<336: return 35
            if h<720: return 20
            return 10
        except: return 30

    def _actionability(self, opp):
        s = 0
        if opp.get('contact_phone'): s += 45
        if opp.get('contact_email'): s += 30
        if opp.get('contact_name'):  s += 15
        if opp.get('url'):           s += 10
        return min(s, 100)

    def _completeness(self, opp):
        fields = ['title','price','location','description','category','url']
        base = int(sum(1 for f in fields if opp.get(f)) / len(fields) * 70)
        desc = opp.get('description','') or ''
        if len(desc)>200: base+=20
        elif len(desc)>80: base+=10
        imgs = opp.get('images',[])
        if isinstance(imgs,str):
            import json
            try: imgs=json.loads(imgs)
            except: imgs=[]
        if len(imgs)>=3: base+=10
        elif len(imgs)>=1: base+=5
        return min(base,100)

    def _value(self, opp, peers):
        price = opp.get('price')
        if not price or price<=0: return 40
        cat = opp.get('category','')
        prices = [p['price'] for p in peers if p.get('price') and p['price']>0
                  and p.get('category')==cat and p.get('id')!=opp.get('id')]
        if len(prices)>=3:
            avg = sum(prices)/len(prices); r = price/avg
            if r<0.60: return 95
            if r<0.75: return 85
            if r<0.85: return 75
            if r<0.95: return 65
            if r<1.05: return 55
            if r<1.20: return 40
            return 25
        tiers = {
            'real_estate':[(50000,85),(100000,75),(250000,65),(500000,50),(1000000,35)],
            'business':   [(50000,85),(100000,75),(250000,60),(500000,45)],
            'vehicles':   [(5000,80),(15000,68),(30000,55),(50000,40)],
            'land':       [(20000,85),(80000,70),(200000,55)],
            'equipment':  [(1000,80),(5000,65),(20000,50)],
            'general':    [(500,80),(2000,65),(10000,50)],
        }.get(cat,[(2000,65),(10000,50)])
        for t,s in tiers:
            if price<=t: return s
        return 35

    def _signals(self, opp, scores):
        signals=[]
        text=((opp.get('title') or '')+(opp.get('description') or '')).lower()
        if scores.get('freshness',0)>=90: signals.append({'type':'positive','icon':'🟢','text':'Posted today'})
        elif scores.get('freshness',0)<=20: signals.append({'type':'warning','icon':'🔴','text':'Stale listing'})
        if scores.get('value',0)>=85: signals.append({'type':'positive','icon':'💰','text':'Significantly below market'})
        elif scores.get('value',0)>=70: signals.append({'type':'positive','icon':'📉','text':'Below market price'})
        if opp.get('contact_phone') and opp.get('contact_email'):
            signals.append({'type':'positive','icon':'📞','text':'Full contact details'})
        elif not opp.get('contact_phone') and not opp.get('contact_email'):
            signals.append({'type':'warning','icon':'⚠️','text':'No direct contact'})
        urgent=['motivated','must sell','urgent','relocation','estate','retiring','liquidat','price reduced','price drop']
        if any(t in text for t in urgent):
            signals.append({'type':'positive','icon':'⚡','text':'Motivated seller signals'})
        if any(t in text for t in ['as-is','as is','cash only']):
            signals.append({'type':'warning','icon':'🔍','text':'Verify condition carefully'})
        cat=opp.get('category','')
        if cat=='real_estate':
            if any(t in text for t in ['fixer','handyman','tlc']): signals.append({'type':'neutral','icon':'🔨','text':'Fixer-upper potential'})
            if any(t in text for t in ['tenant','rented','income','cash flow']): signals.append({'type':'positive','icon':'💵','text':'Income-generating'})
        if cat=='business' and any(t in text for t in ['owner financ','seller financ']):
            signals.append({'type':'positive','icon':'🤝','text':'Owner financing available'})
        return signals[:5]

    def _next_action(self, opp, scores):
        if scores.get('actionability',0)>=70:
            if scores.get('overall',0)>=70: return "📞 Contact seller — high-priority opportunity"
            elif scores.get('overall',0)>=50: return "📞 Reach out and request more details"
            return "🔍 Review listing before contacting"
        if scores.get('value',0)>=75: return "🔬 Research comps, then find contact info"
        if scores.get('freshness',0)<=20: return "⏳ Listing may be stale — verify still available"
        if scores.get('completeness',0)<40: return "📋 Request full details from seller"
        return "👀 Save to watchlist and monitor"


scorer = OpportunityScorer()
