"""
Outreach template generator.
Produces ready-to-use message drafts for each opportunity type.
No API calls — purely template-based, instant.
"""

TEMPLATES = {
    'real_estate': {
        'initial_call': (
            "Hi, my name is [YOUR NAME] and I'm calling about the property you have listed"
            " at {location}. I saw your listing and I'm interested in learning more."
            " Is it still available? I'm a cash buyer and can move quickly."
        ),
        'initial_email': (
            "Subject: Inquiry — Property at {location}\n\n"
            "Hi {contact_name_or_there},\n\n"
            "I came across your listing for the property at {location} priced at {price_text}.\n\n"
            "I'm actively looking in this area and would love to schedule a quick call or visit"
            " to learn more. A few questions:\n\n"
            "• Is the property still available?\n"
            "• Is the price negotiable?\n"
            "• What is your preferred timeline for closing?\n\n"
            "I can work around your schedule. Please let me know a good time.\n\n"
            "Thank you,\n[YOUR NAME]\n[YOUR PHONE]"
        ),
        'follow_up': (
            "Hi {contact_name_or_there}, following up on my earlier message about the property"
            " at {location}. Still very interested — just wanted to make sure you received my note."
            " Happy to discuss terms. Best number to reach me: [YOUR PHONE]."
        ),
        'offer_opener': (
            "Hi {contact_name_or_there},\n\n"
            "After reviewing the listing and doing some research on comparables in the area,"
            " I'd like to present an offer. I'm prepared to move quickly with [CASH/FINANCING].\n\n"
            "Would you be open to a brief call this week to discuss terms?\n\n"
            "Best,\n[YOUR NAME]"
        ),
    },
    'business': {
        'initial_call': (
            "Hi, I'm calling about the business you have listed — {title}. I saw the listing"
            " and I'm interested in learning more about the opportunity. Is now a good time"
            " for a brief conversation?"
        ),
        'initial_email': (
            "Subject: Inquiry — {title}\n\n"
            "Hi {contact_name_or_there},\n\n"
            "I came across your listing for {title} at {price_text} and I'm very interested"
            " in learning more.\n\n"
            "A few initial questions:\n\n"
            "• Is the business still available?\n"
            "• Can you share a brief overview of revenue and cash flow?\n"
            "• What is prompting the sale?\n"
            "• Is seller financing a possibility?\n\n"
            "I'm a serious buyer and happy to sign an NDA to review financials.\n\n"
            "Thank you,\n[YOUR NAME]\n[YOUR PHONE]"
        ),
        'follow_up': (
            "Hi {contact_name_or_there}, I wanted to follow up on my inquiry about {title}."
            " I remain very interested and would love to schedule a call when you have time."
            " Please reach me at [YOUR PHONE] or reply to this email."
        ),
        'nda_request': (
            "Hi {contact_name_or_there},\n\n"
            "I've done some initial research on {title} and I'm ready to move forward with"
            " a deeper look. I'd like to request a copy of your NDA so we can discuss"
            " financials and operational details.\n\n"
            "Please send it over at your earliest convenience.\n\n"
            "Best,\n[YOUR NAME]"
        ),
    },
    'vehicles': {
        'initial_call': (
            "Hi, I'm calling about the {title} you have listed. Is it still available?"
            " I'd love to come take a look — when would be a good time?"
        ),
        'initial_email': (
            "Subject: Inquiry — {title}\n\n"
            "Hi {contact_name_or_there},\n\n"
            "I'm interested in your {title} listed at {price_text}.\n\n"
            "A few quick questions:\n"
            "• Still available?\n"
            "• Any known issues, accidents, or recent repairs?\n"
            "• Is the price firm or is there flexibility?\n\n"
            "Happy to meet at your convenience for a test drive.\n\n"
            "Thanks,\n[YOUR NAME]\n[YOUR PHONE]"
        ),
        'follow_up': (
            "Hi, just following up on the {title} listing. Still interested if it's available."
            " Can reach me at [YOUR PHONE] any time."
        ),
    },
    'equipment': {
        'initial_email': (
            "Subject: Inquiry — {title}\n\n"
            "Hi {contact_name_or_there},\n\n"
            "I came across your listing for {title} at {price_text} and I'm interested.\n\n"
            "• Is it still available?\n"
            "• What condition is it in?\n"
            "• Can you share photos of any wear, damage, or key components?\n"
            "• What are the hours/usage stats?\n\n"
            "I can arrange pickup/transport if we reach an agreement.\n\n"
            "Thank you,\n[YOUR NAME]"
        ),
        'initial_call': (
            "Hi, calling about the {title} you have listed at {price_text}."
            " Is it still available? Can you tell me more about the condition?"
        ),
    },
    'land': {
        'initial_email': (
            "Subject: Land Inquiry — {location}\n\n"
            "Hi {contact_name_or_there},\n\n"
            "I'm interested in the land parcel listed at {location} for {price_text}.\n\n"
            "A few questions:\n"
            "• Is it still available?\n"
            "• Do you have a recent survey on file?\n"
            "• What utilities are available at the road?\n"
            "• Is owner financing an option?\n\n"
            "I'm a serious buyer and can move quickly with cash if the terms work.\n\n"
            "Best,\n[YOUR NAME]"
        ),
    },
    'general': {
        'initial_email': (
            "Subject: Inquiry — {title}\n\n"
            "Hi {contact_name_or_there},\n\n"
            "I saw your listing for {title} at {price_text} and I'm very interested.\n\n"
            "Is it still available? I'd love to learn more and can arrange to meet"
            " at your convenience.\n\n"
            "Thank you,\n[YOUR NAME]\n[YOUR PHONE]"
        ),
        'initial_call': (
            "Hi, I'm calling about your listing for {title}. Is it still available?"
            " I'm very interested and would love to discuss further."
        ),
    },
}

CONTACT_METHODS = ['call', 'email', 'text', 'visit', 'message']
CONTACT_OUTCOMES = [
    'no_answer', 'left_voicemail', 'spoke_briefly', 'full_conversation',
    'sent_email', 'email_bounced', 'scheduled_visit', 'made_offer',
    'deal_progressing', 'not_interested', 'already_sold', 'follow_up_needed',
]
OUTCOME_LABELS = {
    'no_answer':        '📵 No Answer',
    'left_voicemail':   '📨 Left Voicemail',
    'spoke_briefly':    '💬 Spoke Briefly',
    'full_conversation':'✅ Full Conversation',
    'sent_email':       '📧 Email Sent',
    'email_bounced':    '⚠️ Email Bounced',
    'scheduled_visit':  '📅 Visit Scheduled',
    'made_offer':       '🤝 Offer Made',
    'deal_progressing': '🚀 Deal Progressing',
    'not_interested':   '❌ Seller Not Interested',
    'already_sold':     '🔒 Already Sold',
    'follow_up_needed': '⏰ Follow-Up Needed',
}


def get_templates(opp: dict) -> dict:
    """Return available message templates for this opportunity."""
    cat = opp.get('category', 'general')
    templates = TEMPLATES.get(cat, TEMPLATES['general'])

    # Fill in placeholders
    contact_name = opp.get('contact_name') or ''
    filled = {}
    for key, tmpl in templates.items():
        filled[key] = tmpl.format(
            title=opp.get('title', ''),
            location=opp.get('location') or opp.get('city', ''),
            price_text=opp.get('price_text') or _fmt_price(opp.get('price')),
            contact_name_or_there=contact_name if contact_name else 'there',
            contact_name=contact_name,
        )
    return filled


def _fmt_price(p):
    if not p: return 'N/A'
    try:
        v = float(p)
        if v >= 1_000_000: return f'${v/1_000_000:.1f}M'
        if v >= 1_000: return f'${v:,.0f}'
        return f'${v:.0f}'
    except: return str(p)


def template_label(key: str) -> str:
    return {
        'initial_call':   '📞 Initial Call Script',
        'initial_email':  '📧 Initial Email',
        'follow_up':      '🔄 Follow-up Message',
        'offer_opener':   '🤝 Offer Opener',
        'nda_request':    '📋 NDA Request',
    }.get(key, key.replace('_', ' ').title())
