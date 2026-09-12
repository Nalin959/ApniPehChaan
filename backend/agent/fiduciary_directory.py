"""
fiduciary_directory.py — Registry of Operating Data Fiduciaries & Statutory Contacts.

WHY THIS EXISTS
---------------
When a data breach occurs at an operating company (IIMjobs, Zomato, Yatra, LinkedIn,
Canva, etc.), personal data was exposed. While dark-web leak dumps cannot be
un-published from illicit repositories, the operating entity itself remains a
legally accountable Data Fiduciary under:
  - India: DPDP Act 2023 Section 12 (Erasure) & Section 13 (Grievance Redressal)
  - EU: GDPR Article 17 (Right to erasure)
  - US: CCPA / CPRA § 1798.105 (Consumer deletion right)

This directory provides verified Grievance Officer / DPO email addresses,
registered corporate headquarters, self-serve privacy URLs, and identifies
which leak records represent identifiable corporate controllers vs. unattributed
aggregate dumps.
"""

import re

# Verified corporate directory for Indian and global Data Fiduciaries
KNOWN_FIDUCIARIES: dict[str, dict] = {
    "iimjobs": {
        "company_name": "Info Edge (India) Limited (IIMjobs)",
        "brand": "IIMjobs",
        "dpo_email": "grievance@iimjobs.com",
        "dpo_name": "Grievance Officer, Info Edge",
        "address": "B-8, Sector 132, Noida, Uttar Pradesh 201301, India",
        "self_serve_url": "https://www.iimjobs.com/settings",
        "country": "IN",
        "jurisdiction": "dpdp",
        "legal_class": "dpdp_erasure",
    },
    "zomato": {
        "company_name": "Zomato Limited",
        "brand": "Zomato",
        "dpo_email": "grievance@zomato.com",
        "dpo_name": "Grievance Officer, Zomato",
        "address": "Ground Floor, 12A, 94 Meghdoot, Nehru Place, New Delhi 110019, India",
        "self_serve_url": "https://www.zomato.com/privacy",
        "country": "IN",
        "jurisdiction": "dpdp",
        "legal_class": "dpdp_erasure",
    },
    "yatra": {
        "company_name": "Yatra Online Limited",
        "brand": "Yatra",
        "dpo_email": "grievance@yatra.com",
        "dpo_name": "Grievance Officer, Yatra Online",
        "address": "Gulf Adiba, 4th Floor, Plot No. 272, Phase II, Udyog Vihar, Gurugram, Haryana 122008, India",
        "self_serve_url": "https://www.yatra.com/",
        "country": "IN",
        "jurisdiction": "dpdp",
        "legal_class": "dpdp_erasure",
    },
    "linkedin": {
        "company_name": "LinkedIn Ireland UC / LinkedIn Technology Information Pvt Ltd",
        "brand": "LinkedIn",
        "dpo_email": "linkedin_dpo@linkedin.com",
        "dpo_name": "Data Protection Officer, LinkedIn",
        "address": "Tower A, Global Technology Park, Outer Ring Road, Devarabeesanahalli, Bengaluru 560103, Karnataka, India",
        "self_serve_url": "https://www.linkedin.com/psettings/account-management/close-account",
        "country": "IN",
        "jurisdiction": "dpdp",
        "legal_class": "dpdp_erasure",
    },
    "canva": {
        "company_name": "Canva Pty Ltd",
        "brand": "Canva",
        "dpo_email": "privacy@canva.com",
        "dpo_name": "Privacy Officer, Canva",
        "address": "110 Kippax St, Surry Hills NSW 2010, Australia",
        "self_serve_url": "https://www.canva.com/settings/your-account",
        "country": "AU",
        "jurisdiction": "gdpr",
        "legal_class": "dpdp_erasure",
    },
    "bigbasket": {
        "company_name": "Supermarket Grocery Supplies Pvt. Ltd. (BigBasket / Tata Enterprise)",
        "brand": "BigBasket",
        "dpo_email": "grievance@bigbasket.com",
        "dpo_name": "Grievance Officer, BigBasket",
        "address": "2nd Floor, Fairway Business Park, Challaghatta Village, Domlur, Bengaluru 560071, Karnataka, India",
        "self_serve_url": "https://www.bigbasket.com/",
        "country": "IN",
        "jurisdiction": "dpdp",
        "legal_class": "dpdp_erasure",
    },
    "naukri": {
        "company_name": "Info Edge (India) Limited (Naukri.com)",
        "brand": "Naukri.com",
        "dpo_email": "grievance@naukri.com",
        "dpo_name": "Grievance Officer, Naukri",
        "address": "B-8, Sector 132, Noida, Uttar Pradesh 201301, India",
        "self_serve_url": "https://www.naukri.com/",
        "country": "IN",
        "jurisdiction": "dpdp",
        "legal_class": "dpdp_erasure",
    },
    "jeevansathi": {
        "company_name": "Info Edge (India) Limited (Jeevansathi)",
        "brand": "Jeevansathi",
        "dpo_email": "grievance@jeevansathi.com",
        "dpo_name": "Grievance Officer, Jeevansathi",
        "address": "B-8, Sector 132, Noida, Uttar Pradesh 201301, India",
        "self_serve_url": "https://www.jeevansathi.com/",
        "country": "IN",
        "jurisdiction": "dpdp",
        "legal_class": "dpdp_erasure",
    },
    "shaadi": {
        "company_name": "People Interactive (India) Private Limited (Shaadi.com)",
        "brand": "Shaadi.com",
        "dpo_email": "grievanceofficer@peopleinteractive.in",
        "dpo_name": "Grievance Officer, Shaadi.com",
        "address": "Ground Floor, Film Centre, 68 Tardeo Road, Mumbai 400034, Maharashtra, India",
        "self_serve_url": "https://www.shaadi.com/",
        "country": "IN",
        "jurisdiction": "dpdp",
        "legal_class": "dpdp_erasure",
    },
    "bharatmatrimony": {
        "company_name": "Matrimony.com Limited (BharatMatrimony)",
        "brand": "BharatMatrimony",
        "dpo_email": "grievanceofficer@matrimony.com",
        "dpo_name": "Grievance Officer, Matrimony.com",
        "address": "No.94, TVH Beliciaa Towers, MRC Nagar, Chennai 600028, Tamil Nadu, India",
        "self_serve_url": "https://www.bharatmatrimony.com/",
        "country": "IN",
        "jurisdiction": "dpdp",
        "legal_class": "dpdp_erasure",
    },
    "dominos": {
        "company_name": "Jubilant FoodWorks Limited (Domino's Pizza India)",
        "brand": "Domino's India",
        "dpo_email": "grievance@jublfood.com",
        "dpo_name": "Grievance Officer, Jubilant FoodWorks",
        "address": "Plot 1A, Sector 16A, Noida 201301, Uttar Pradesh, India",
        "self_serve_url": "https://pizzaonline.dominos.co.in/",
        "country": "IN",
        "jurisdiction": "dpdp",
        "legal_class": "dpdp_erasure",
    },
    "airindia": {
        "company_name": "Air India Limited (Tata Group)",
        "brand": "Air India",
        "dpo_email": "grievance@airindia.com",
        "dpo_name": "Grievance Officer, Air India",
        "address": "Airlines House, 113 Gurudwara Rakabganj Road, New Delhi 110001, India",
        "self_serve_url": "https://www.airindia.com/",
        "country": "IN",
        "jurisdiction": "dpdp",
        "legal_class": "dpdp_erasure",
    },
    "upstox": {
        "company_name": "RKSV Securities India Private Limited (Upstox)",
        "brand": "Upstox",
        "dpo_email": "grievance@upstox.com",
        "dpo_name": "Grievance Officer, Upstox",
        "address": "807, New Delhi House, Barakhamba Road, Connaught Place, New Delhi 110001, India",
        "self_serve_url": "https://upstox.com/",
        "country": "IN",
        "jurisdiction": "dpdp",
        "legal_class": "dpdp_limited",
    },
    "apollo247": {
        "company_name": "Apollo Hospitals Enterprise Limited (Apollo 24|7)",
        "brand": "Apollo 24|7",
        "dpo_email": "grievance@apollo247.com",
        "dpo_name": "Grievance Officer, Apollo",
        "address": "19 Bishop Gardens, Raja Annamalaipuram, Chennai 600028, Tamil Nadu, India",
        "self_serve_url": "https://www.apollo247.com/",
        "country": "IN",
        "jurisdiction": "dpdp",
        "legal_class": "dpdp_erasure",
    },
    "adobe": {
        "company_name": "Adobe Systems India Pvt. Ltd.",
        "brand": "Adobe",
        "dpo_email": "dpo@adobe.com",
        "dpo_name": "Data Protection Officer, Adobe",
        "address": "Adobe Towers, Sector 132, Expressway, Noida 201305, Uttar Pradesh, India",
        "self_serve_url": "https://account.adobe.com/privacy",
        "country": "IN",
        "jurisdiction": "dpdp",
        "legal_class": "dpdp_erasure",
    },
    "dropbox": {
        "company_name": "Dropbox, Inc.",
        "brand": "Dropbox",
        "dpo_email": "privacy@dropbox.com",
        "dpo_name": "Privacy Officer, Dropbox",
        "address": "1800 Owens Street, San Francisco, CA 94158, USA",
        "self_serve_url": "https://www.dropbox.com/account/delete",
        "country": "US",
        "jurisdiction": "ccpa",
        "legal_class": "dpdp_erasure",
    },
    "truecaller": {
        "company_name": "Truecaller AB / True Software Scandinavia",
        "brand": "Truecaller",
        "dpo_email": "dpo@truecaller.com",
        "dpo_name": "Data Protection Officer, Truecaller",
        "address": "Mäster Samuelsgatan 56, 111 21 Stockholm, Sweden",
        "self_serve_url": "https://www.truecaller.com/unlisting",
        "country": "IN",
        "jurisdiction": "dpdp",
        "legal_class": "dpdp_erasure",
    },
    "gravatar": {
        "company_name": "Automattic Inc. (Gravatar)",
        "brand": "Gravatar",
        "dpo_email": "privacypolicy@automattic.com",
        "dpo_name": "Privacy Counsel, Automattic",
        "address": "60 29th Street #343, San Francisco, CA 94110, USA",
        "self_serve_url": "https://en.gravatar.com/profiles/edit",
        "country": "US",
        "jurisdiction": "ccpa",
        "legal_class": "dpdp_erasure",
    },
    "github": {
        "company_name": "GitHub, Inc. (Microsoft)",
        "brand": "GitHub",
        "dpo_email": "privacy@github.com",
        "dpo_name": "Privacy Officer, GitHub",
        "address": "88 Colin P Kelly Jr St, San Francisco, CA 94107, USA",
        "self_serve_url": "https://github.com/settings/admin",
        "country": "US",
        "jurisdiction": "ccpa",
        "legal_class": "dpdp_erasure",
    },
}

# Aggregate/dark-web dump patterns that have no single legal controller
_DARKWEB_DUMP_KEYWORDS = {
    "collection", "combo", "paste", "dump", "exploit", "naz.api",
    "breach compilation", "breachcompilation", "dark web", "darkweb",
    "leak base", "leakbase", "antipublic", "anti public", "synth_paste",
    "sandbox", "compilation", "credential leak", "infostealer",
}


def is_darkweb_dump(name_or_id: str) -> bool:
    """Return True if the source is an unattributed dump with no legal addressee."""
    s = (name_or_id or "").strip().lower()
    return any(k in s for k in _DARKWEB_DUMP_KEYWORDS)


def get_fiduciary_contact(name_or_id: str) -> dict:
    """Resolve contact and statutory details for an operating Data Fiduciary.

    Returns a dict with company_name, brand, dpo_email, address, self_serve_url,
    and statutory metadata. If not in the pre-curated directory, derives a sensible,
    usable fallback instead of returning blanks.
    """
    clean = re.sub(r"[^a-zA-Z0-9]", "", (name_or_id or "").lower())
    # Exact first, then containment — and longest key first, so a short key
    # cannot claim a longer name it merely appears inside. Loose substring
    # matching is how "Amazon India" resolved to Domino's grievance officer on
    # the shared token "india".
    if clean in KNOWN_FIDUCIARIES:
        return dict(KNOWN_FIDUCIARIES[clean], contact_tier="curated", dpo_email_is_guess=False)
    for key in sorted(KNOWN_FIDUCIARIES, key=len, reverse=True):
        if len(key) >= 5 and (key in clean or clean in key):
            return dict(KNOWN_FIDUCIARIES[key], contact_tier="curated", dpo_email_is_guess=False)

    raw_name = (name_or_id or "").strip()
    if not raw_name or is_darkweb_dump(raw_name):
        return {}

    # Fallback for an entity that is not in the directory.
    #
    # It GUESSES, and it must say so. This returned privacy@<slug>.com in the
    # same shape as a curated entry, so a caller could not tell a researched
    # grievance-officer address from a string built out of a breach's name:
    # "SomeRandomLeak2021" produced privacy@somerandomleak2021.com, and
    # "Amazon India" produced privacy@amazonindia.com, which is not Amazon's
    # domain. An erasure notice carries the data subject's name, email and
    # phone — sending one to an invented domain hands their identifiers to
    # whoever happens to own it. A privacy tool causing that disclosure is the
    # exact harm it exists to prevent.
    #
    # The guess is still returned, because a plausible starting point is useful
    # to a human who will check it. It is flagged so that nothing can dispatch
    # to it unattended: backend/remediation/mailer.py refuses a recipient whose
    # tier is a guess unless explicitly overridden.
    domain_slug = re.sub(r"[^a-zA-Z0-9]", "", raw_name.lower())
    return {
        "company_name": f"{raw_name} Data Fiduciary",
        "brand": raw_name,
        "dpo_email": f"privacy@{domain_slug}.com",
        "dpo_email_is_guess": True,
        "contact_tier": "synthesised",
        "contact_warning": (
            f"This address was CONSTRUCTED from the name '{raw_name}', not looked up. "
            f"It may not exist, and may belong to an unrelated party. Confirm the "
            f"controller's published grievance-officer address (DPDP Act 2023 s.13 "
            f"requires one to be published) before serving anything on it."),
        "dpo_name": f"Grievance Officer, {raw_name}",
        "address": f"Corporate Grievance Office, {raw_name} Operations Centre",
        "self_serve_url": f"https://www.{domain_slug}.com/privacy",
        "country": "IN",
        "jurisdiction": "dpdp",
        "legal_class": "dpdp_erasure",
    }
