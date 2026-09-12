"""
build_indian_sources.py — Registry of Indian data sources that expose personal data.

WHY THIS EXISTS
---------------
The Optery directory shipped with this project is 956 brokers with no country
field, and only four of them are India-related. For a project built around the
DPDP Act 2023 that is backwards: it surfaced Alabama court-record sites to an
Indian user and had nothing to say about Truecaller, JustDial or the MCA
registry.

This registry covers the Indian exposure surface, and — more importantly —
encodes the LEGAL POSITION for each one, because in India they are not all the
same. A commercial people-search site and a High Court judgment both contain
your name, but you have a statutory erasure right against exactly one of them.

LEGAL CLASSIFICATION USED HERE
------------------------------
  dpdp_erasure      DPDP Act 2023 s.12(1). Commercial processing, erasure
                    available on withdrawal of consent / purpose exhaustion.

  dpdp_limited      DPDP applies but the controller has a competing retention
                    basis (KYC under PMLA, telecom licence conditions, tax
                    records). Erasure is arguable, not automatic.

  statutory_publication
                    Published under a legal mandate — Companies Act 2013 (MCA
                    filings), Representation of the People Act 1950 (electoral
                    rolls), state land-revenue codes (Bhulekh). DPDP s.3(c)(ii)
                    excludes personal data made publicly available pursuant to
                    a legal obligation. An erasure notice does NOT lie here.

  judicial_record   Court judgments and case records. Not reachable by a DPDP
                    notice. Indian courts have granted limited redaction in
                    specific cases (Delhi HC, Jorawer Singh Mundy v. Union of
                    India, 2021; Karnataka HC 2017), but it requires an
                    application to the court, not a letter to a website.

The agent uses this classification to refuse to draft notices that cannot land.
"""

import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))

SOURCES = [
    # ── Commercial people-search / directory (full DPDP erasure right) ────────
    {
        "id": "truecaller", "name": "Truecaller",
        "website": "https://www.truecaller.com/",
        "category": "Phone Directory",
        "operator": "True Software Scandinavia AB",
        "data_exposed": ["name", "phone", "email", "city", "employer"],
        "how_collected": "Crowdsourced from contact books uploaded by other users, plus partner data.",
        "legal_class": "dpdp_erasure",
        "removal_mechanism": "self_serve",
        "removal_url": "https://www.truecaller.com/unlisting",
        "removal_notes": "Unlisting removes the number from search. Deactivate the account first, or it is re-indexed.",
        "severity": "high",
        "reach_note": "The largest reverse phone-lookup surface in India.",
    },
    {
        "id": "justdial", "name": "JustDial",
        "website": "https://www.justdial.com/",
        "category": "Local Search / Directory",
        "operator": "Just Dial Limited",
        "data_exposed": ["name", "phone", "address", "city", "business_details"],
        "how_collected": "Business listings, user enquiries, and call records from its search service.",
        "legal_class": "dpdp_erasure",
        "removal_mechanism": "written_request",
        "removal_url": "https://www.justdial.com/",
        "removal_notes": "Grievance officer contact is published under the IT Rules 2021; serve the DPDP notice there.",
        "severity": "high",
        "reach_note": "Suffered a breach exposing ~100M user records (2020).",
    },
    {
        "id": "indiamart", "name": "IndiaMART",
        "website": "https://www.indiamart.com/",
        "category": "B2B Lead Generation",
        "operator": "IndiaMART InterMESH Limited",
        "data_exposed": ["name", "phone", "email", "address", "employer"],
        "how_collected": "Buyer and supplier registrations; contact details are exposed to paying sellers as leads.",
        "legal_class": "dpdp_erasure",
        "removal_mechanism": "written_request",
        "removal_url": "https://www.indiamart.com/",
        "removal_notes": "Supplier contact data is the product; expect resistance and be ready to escalate to the DPBI.",
        "severity": "high",
        "reach_note": "HIBP-listed breach: 20.1M records.",
    },
    {
        "id": "sulekha", "name": "Sulekha",
        "website": "https://www.sulekha.com/",
        "category": "Local Services Marketplace",
        "operator": "Sulekha.com New Media Pvt Ltd",
        "data_exposed": ["name", "phone", "email", "city", "service_enquiries"],
        "how_collected": "Service enquiry forms; contact details are sold on to service providers as leads.",
        "legal_class": "dpdp_erasure",
        "removal_mechanism": "written_request",
        "removal_url": "https://www.sulekha.com/",
        "removal_notes": "Lead resale is the business model — cite purpose exhaustion under s.12(1).",
        "severity": "high",
    },
    {
        "id": "99acres", "name": "99acres",
        "website": "https://www.99acres.com/",
        "category": "Property Listings",
        "operator": "Info Edge (India) Limited",
        "data_exposed": ["name", "phone", "email", "address", "property_details"],
        "how_collected": "Property listings and buyer enquiries; owner contact details are published on listings.",
        "legal_class": "dpdp_erasure",
        "removal_mechanism": "self_serve",
        "removal_url": "https://www.99acres.com/",
        "removal_notes": "Delisting a property does not always remove the cached contact record; verify afterwards.",
        "severity": "high",
    },
    {
        "id": "magicbricks", "name": "MagicBricks",
        "website": "https://www.magicbricks.com/",
        "category": "Property Listings",
        "operator": "Times Internet Limited",
        "data_exposed": ["name", "phone", "email", "address", "property_details"],
        "how_collected": "Property listings and enquiry forms.",
        "legal_class": "dpdp_erasure",
        "removal_mechanism": "self_serve",
        "removal_url": "https://www.magicbricks.com/",
        "removal_notes": "Same caveat as 99acres — verify the listing is gone, not just hidden.",
        "severity": "medium",
    },

    # ── Employment / resume databases ────────────────────────────────────────
    {
        "id": "naukri", "name": "Naukri.com",
        "website": "https://www.naukri.com/",
        "category": "Resume Database",
        "operator": "Info Edge (India) Limited",
        "data_exposed": ["name", "phone", "email", "address", "employer", "salary", "date_of_birth"],
        "how_collected": "Uploaded CVs. Recruiters holding a subscription can search and download full profiles.",
        "legal_class": "dpdp_erasure",
        "removal_mechanism": "self_serve",
        "removal_url": "https://www.naukri.com/",
        "removal_notes": "Setting a profile private stops new searches but does not recall CVs already downloaded by recruiters.",
        "severity": "critical",
        "reach_note": "CVs carry the densest PII of any source here — DOB, salary, address and employer in one document.",
    },
    {
        "id": "shine", "name": "Shine.com",
        "website": "https://www.shine.com/",
        "category": "Resume Database",
        "operator": "HT Media Limited",
        "data_exposed": ["name", "phone", "email", "employer", "salary"],
        "how_collected": "Uploaded CVs, searchable by subscribing recruiters.",
        "legal_class": "dpdp_erasure",
        "removal_mechanism": "self_serve",
        "removal_url": "https://www.shine.com/",
        "severity": "high",
    },
    {
        "id": "iimjobs", "name": "IIMJobs",
        "website": "https://www.iimjobs.com/",
        "category": "Resume Database",
        "operator": "Info Edge (India) Limited",
        "data_exposed": ["name", "phone", "email", "employer", "salary"],
        "how_collected": "Uploaded CVs for mid-to-senior roles.",
        "legal_class": "dpdp_erasure",
        "removal_mechanism": "self_serve",
        "removal_url": "https://www.iimjobs.com/",
        "severity": "high",
        "reach_note": "HIBP-listed breach: 4.2M records.",
    },

    # ── Matrimonial (highly sensitive) ───────────────────────────────────────
    {
        "id": "shaadi", "name": "Shaadi.com",
        "website": "https://www.shaadi.com/",
        "category": "Matrimonial",
        "operator": "People Interactive (I) Pvt Ltd",
        "data_exposed": ["name", "photo", "date_of_birth", "city", "caste", "religion", "income", "employer"],
        "how_collected": "Self-created matrimonial profiles, visible to other members and often to search engines.",
        "legal_class": "dpdp_erasure",
        "removal_mechanism": "self_serve",
        "removal_url": "https://www.shaadi.com/",
        "removal_notes": "Hiding a profile is not deletion. Request full erasure and verify the cached copy is gone.",
        "severity": "critical",
        "reach_note": "Caste, religion and income in one profile — among the most sensitive combinations in the Indian context.",
    },
    {
        "id": "bharatmatrimony", "name": "BharatMatrimony",
        "website": "https://www.bharatmatrimony.com/",
        "category": "Matrimonial",
        "operator": "Matrimony.com Limited",
        "data_exposed": ["name", "photo", "date_of_birth", "city", "caste", "religion", "income"],
        "how_collected": "Self-created matrimonial profiles.",
        "legal_class": "dpdp_erasure",
        "removal_mechanism": "self_serve",
        "removal_url": "https://www.bharatmatrimony.com/",
        "severity": "critical",
    },

    # ── Corporate registry mirrors (statutory publication — NOT erasable) ────
    {
        "id": "zaubacorp", "name": "Zauba Corp",
        "website": "https://www.zaubacorp.com/",
        "category": "Corporate Registry Mirror",
        "operator": "Zauba Technologies",
        "data_exposed": ["name", "din", "address", "date_of_birth", "directorships"],
        "how_collected": "Scraped from MCA21 filings under the Companies Act 2013.",
        "legal_class": "statutory_publication",
        "removal_mechanism": "not_removable",
        "removal_url": "https://www.zaubacorp.com/",
        "removal_notes": ("Director particulars are published under a statutory mandate. DPDP s.3(c)(ii) "
                          "excludes data made public pursuant to a legal obligation, so an erasure notice "
                          "does not lie. A mirror may be asked to de-index, but the MCA source record remains."),
        "severity": "high",
        "reach_note": "Directors' residential addresses and DOB are exposed here — a common and under-appreciated leak.",
    },
    {
        "id": "tofler", "name": "Tofler",
        "website": "https://www.tofler.in/",
        "category": "Corporate Registry Mirror",
        "operator": "Tofler",
        "data_exposed": ["name", "din", "address", "directorships"],
        "how_collected": "Scraped from MCA21 filings.",
        "legal_class": "statutory_publication",
        "removal_mechanism": "not_removable",
        "removal_url": "https://www.tofler.in/",
        "removal_notes": "Same statutory-publication position as Zauba Corp.",
        "severity": "medium",
    },
    {
        "id": "thecompanycheck", "name": "The Company Check",
        "website": "https://www.thecompanycheck.com/",
        "category": "Corporate Registry Mirror",
        "operator": "TCC Information Private Limited",
        "data_exposed": ["name", "din", "address", "directorships"],
        "how_collected": "Scraped from MCA21 filings.",
        "legal_class": "statutory_publication",
        "removal_mechanism": "not_removable",
        "removal_url": "https://www.thecompanycheck.com/",
        "severity": "medium",
    },
    {
        "id": "mca21", "name": "MCA21 (Ministry of Corporate Affairs)",
        "website": "https://www.mca.gov.in/",
        "category": "Government Registry",
        "operator": "Government of India",
        "data_exposed": ["name", "din", "address", "date_of_birth", "directorships"],
        "how_collected": "Mandatory filings by companies under the Companies Act 2013.",
        "legal_class": "statutory_publication",
        "removal_mechanism": "statutory_only",
        "removal_url": "https://www.mca.gov.in/",
        "removal_notes": ("The source of truth for director data. Correction is possible via the prescribed "
                          "forms; erasure is not, while the directorship subsists."),
        "severity": "high",
    },

    # ── Judicial records (court application only) ────────────────────────────
    {
        "id": "indiankanoon", "name": "Indian Kanoon",
        "website": "https://indiankanoon.org/",
        "category": "Judicial Records",
        "operator": "Indian Kanoon",
        "data_exposed": ["name", "address", "case_details", "judgment_text"],
        "how_collected": "Full text of Indian court judgments, indexed and searchable by name.",
        "legal_class": "judicial_record",
        "removal_mechanism": "statutory_only",
        "removal_url": "https://indiankanoon.org/",
        "removal_notes": ("Not reachable by a DPDP notice. Indian courts have granted redaction in narrow "
                          "cases — Delhi HC in Jorawer Singh Mundy v. Union of India (2021) ordered removal "
                          "of a judgment naming an acquitted party — but it requires an application to the "
                          "court that issued the judgment."),
        "severity": "critical",
        "reach_note": "A name in an old case, including an acquittal, stays searchable indefinitely.",
    },
    {
        "id": "ecourts", "name": "eCourts Services",
        "website": "https://services.ecourts.gov.in/",
        "category": "Judicial Records",
        "operator": "eCommittee, Supreme Court of India",
        "data_exposed": ["name", "case_details", "hearing_dates", "party_details"],
        "how_collected": "Case status records published by district and high courts.",
        "legal_class": "judicial_record",
        "removal_mechanism": "statutory_only",
        "removal_url": "https://services.ecourts.gov.in/",
        "removal_notes": "Court record. Redaction requires an application to the concerned court.",
        "severity": "high",
    },

    # ── Government public records (statutory publication) ────────────────────
    {
        "id": "electoral_roll", "name": "Electoral Roll (CEO state portals)",
        "website": "https://voters.eci.gov.in/",
        "category": "Government Registry",
        "operator": "Election Commission of India / State CEOs",
        "data_exposed": ["name", "address", "age", "relation_name", "epic_number"],
        "how_collected": "Published under the Representation of the People Act 1950 and mirrored by scrapers.",
        "legal_class": "statutory_publication",
        "removal_mechanism": "statutory_only",
        "removal_url": "https://voters.eci.gov.in/",
        "removal_notes": ("Publication is statutorily mandated; erasure is not available. Corrections go "
                          "through Form 8. The real exposure is third-party MIRRORS that re-host rolls — "
                          "those are commercial republishers and CAN be served."),
        "severity": "critical",
        "reach_note": "Name, full address and a relative's name in one public record.",
    },
    {
        "id": "vahan_parivahan", "name": "VAHAN / Parivahan",
        "website": "https://parivahan.gov.in/",
        "category": "Government Registry",
        "operator": "Ministry of Road Transport and Highways",
        "data_exposed": ["name", "address", "vehicle_registration", "engine_chassis"],
        "how_collected": "Vehicle registration records. Bulk data was historically sold before the 2020 policy withdrawal.",
        "legal_class": "statutory_publication",
        "removal_mechanism": "statutory_only",
        "removal_url": "https://parivahan.gov.in/",
        "removal_notes": "Registration data is statutory. Resellers holding historically purchased bulk data can be served.",
        "severity": "high",
    },
    {
        "id": "bhulekh", "name": "Bhulekh / State Land Records",
        "website": "https://dolr.gov.in/",
        "category": "Government Registry",
        "operator": "State revenue departments",
        "data_exposed": ["name", "address", "land_holdings", "relation_name"],
        "how_collected": "Digitised land-revenue records published by state portals.",
        "legal_class": "statutory_publication",
        "removal_mechanism": "not_removable",
        "removal_url": "https://dolr.gov.in/",
        "removal_notes": "Land records are statutory public records. Erasure is not available.",
        "severity": "medium",
    },

    # ── Telecom / financial (DPDP applies but retention obligations compete) ─
    {
        "id": "credit_bureaus_in", "name": "CIBIL / Experian / Equifax India",
        "website": "https://www.cibil.com/",
        "category": "Credit Bureau",
        "operator": "TransUnion CIBIL / Experian / Equifax",
        "data_exposed": ["name", "pan", "address", "phone", "credit_history", "date_of_birth"],
        "how_collected": "Reported by member banks and NBFCs under the CICRA 2005 framework.",
        "legal_class": "dpdp_limited",
        "removal_mechanism": "statutory_only",
        "removal_url": "https://www.cibil.com/",
        "removal_notes": ("Retention is mandated by the Credit Information Companies (Regulation) Act 2005. "
                          "Erasure is not available; DISPUTE and CORRECTION are. A credit freeze limits new "
                          "enquiries."),
        "severity": "critical",
        "reach_note": "PAN, address and full credit history in one record.",
    },
    {
        "id": "telecom_kyc", "name": "Telecom KYC records",
        "website": "https://www.trai.gov.in/",
        "category": "Telecom",
        "operator": "Licensed telecom operators",
        "data_exposed": ["name", "address", "aadhaar_last4", "phone", "photo"],
        "how_collected": "Mandatory subscriber verification under the telecom licence conditions.",
        "legal_class": "dpdp_limited",
        "removal_mechanism": "statutory_only",
        "removal_url": "https://www.trai.gov.in/",
        "removal_notes": "Licence conditions require retention for the subscription period plus a statutory tail.",
        "severity": "high",
    },

    # ── Additional Corporate Registry Mirrors (statutory publication) ────────
    {
        "id": "instafinancials", "name": "InstaFinancials",
        "website": "https://www.instafinancials.com/",
        "category": "Corporate Registry Mirror",
        "operator": "Insta Information Technologies Pvt Ltd",
        "data_exposed": ["name", "din", "address", "directorships", "financial_filings"],
        "how_collected": "Aggregated from MCA21 corporate filings.",
        "legal_class": "statutory_publication",
        "removal_mechanism": "not_removable",
        "removal_url": "https://www.instafinancials.com/",
        "removal_notes": "Statutory MCA mirror under s.3(c)(ii). Direct statutory correction required via MCA portal.",
        "severity": "medium",
    },
    {
        "id": "quickcompany", "name": "QuickCompany",
        "website": "https://www.quickcompany.in/",
        "category": "Corporate Registry Mirror",
        "operator": "QuickCompany Technologies",
        "data_exposed": ["name", "din", "address", "directorships"],
        "how_collected": "Scraped from MCA21 database.",
        "legal_class": "statutory_publication",
        "removal_mechanism": "not_removable",
        "removal_url": "https://www.quickcompany.in/",
        "removal_notes": "Statutory corporate publication. Correction only via MCA Form DIR-6.",
        "severity": "medium",
    },

    # ── Additional Directories & B2B Portals (DPDP erasure applies) ──────────
    {
        "id": "tradeindia", "name": "TradeIndia",
        "website": "https://www.tradeindia.com/",
        "category": "B2B Lead Generation",
        "operator": "Infocom Network Private Limited",
        "data_exposed": ["name", "phone", "email", "address", "business_details"],
        "how_collected": "Buyer and supplier registrations exposed to trade enquiries.",
        "legal_class": "dpdp_erasure",
        "removal_mechanism": "written_request",
        "removal_url": "https://www.tradeindia.com/",
        "removal_notes": "Grievance officer published under IT Rules 2021. DPDP s.12 notice applies.",
        "severity": "high",
    },

    # ── Additional Employment & Career Databases (DPDP erasure applies) ───────
    {
        "id": "foundit", "name": "Foundit (Monster India)",
        "website": "https://www.foundit.in/",
        "category": "Resume Database",
        "operator": "Monster.com India Pvt Ltd",
        "data_exposed": ["name", "phone", "email", "address", "employer", "salary", "date_of_birth"],
        "how_collected": "Uploaded candidate CVs searched by recruiters.",
        "legal_class": "dpdp_erasure",
        "removal_mechanism": "self_serve",
        "removal_url": "https://www.foundit.in/",
        "removal_notes": "Delete profile from user account settings. Request downstream recipient notification under s.12(3).",
        "severity": "critical",
    },
    {
        "id": "internshala", "name": "Internshala",
        "website": "https://internshala.com/",
        "category": "Resume Database",
        "operator": "Scholiverse Educare Pvt Ltd",
        "data_exposed": ["name", "phone", "email", "college", "education_records"],
        "how_collected": "Student application profiles and resumes.",
        "legal_class": "dpdp_erasure",
        "removal_mechanism": "self_serve",
        "removal_url": "https://internshala.com/",
        "removal_notes": "Self-serve account deactivation in account settings.",
        "severity": "high",
    },
    {
        "id": "timesjobs", "name": "TimesJobs",
        "website": "https://www.timesjobs.com/",
        "category": "Resume Database",
        "operator": "Times Business Solutions",
        "data_exposed": ["name", "phone", "email", "employer", "salary", "resume"],
        "how_collected": "Candidate resume uploads.",
        "legal_class": "dpdp_erasure",
        "removal_mechanism": "self_serve",
        "removal_url": "https://www.timesjobs.com/",
        "removal_notes": "Account settings -> delete profile.",
        "severity": "high",
    },
    {
        "id": "hirist", "name": "Hirist",
        "website": "https://www.hirist.tech/",
        "category": "Resume Database",
        "operator": "Info Edge (India) Limited",
        "data_exposed": ["name", "phone", "email", "tech_skills", "salary_history"],
        "how_collected": "Tech candidate profile registrations.",
        "legal_class": "dpdp_erasure",
        "removal_mechanism": "self_serve",
        "removal_url": "https://www.hirist.tech/",
        "removal_notes": "Delete account in profile settings.",
        "severity": "high",
    },

    # ── Additional Matrimonial Services ──────────────────────────────────────
    {
        "id": "jeevansathi", "name": "Jeevansathi",
        "website": "https://www.jeevansathi.com/",
        "category": "Matrimonial",
        "operator": "Info Edge (India) Limited",
        "data_exposed": ["name", "photo", "date_of_birth", "caste", "religion", "income", "family_details"],
        "how_collected": "Matrimonial profile registration.",
        "legal_class": "dpdp_erasure",
        "removal_mechanism": "self_serve",
        "removal_url": "https://www.jeevansathi.com/",
        "removal_notes": "Settings -> Delete Profile permanently.",
        "severity": "critical",
    },
    {
        "id": "communitymatrimony", "name": "CommunityMatrimony",
        "website": "https://www.communitymatrimony.com/",
        "category": "Matrimonial",
        "operator": "Matrimony.com Limited",
        "data_exposed": ["name", "photo", "date_of_birth", "caste", "horoscope", "income"],
        "how_collected": "Caste-specific matrimonial portals.",
        "legal_class": "dpdp_erasure",
        "removal_mechanism": "self_serve",
        "removal_url": "https://www.communitymatrimony.com/",
        "removal_notes": "Delete profile via account settings.",
        "severity": "critical",
    },

    # ── Additional Real Estate Portals ───────────────────────────────────────
    {
        "id": "housing", "name": "Housing.com",
        "website": "https://housing.com/",
        "category": "Property Listings",
        "operator": "REA India Pte Ltd",
        "data_exposed": ["name", "phone", "email", "property_address"],
        "how_collected": "Property listings and landlord contacts.",
        "legal_class": "dpdp_erasure",
        "removal_mechanism": "self_serve",
        "removal_url": "https://housing.com/",
        "removal_notes": "De-list property and request contact deletion.",
        "severity": "medium",
    },
    {
        "id": "nobroker", "name": "NoBroker",
        "website": "https://www.nobroker.in/",
        "category": "Property Listings",
        "operator": "NoBroker Technologies Solutions Pvt Ltd",
        "data_exposed": ["name", "phone", "email", "rental_property_details"],
        "how_collected": "Property listings and direct owner contact information.",
        "legal_class": "dpdp_erasure",
        "removal_mechanism": "self_serve",
        "removal_url": "https://www.nobroker.in/",
        "removal_notes": "Close listing and delete account from profile settings.",
        "severity": "medium",
    },
    {
        "id": "commonfloor", "name": "CommonFloor",
        "website": "https://www.commonfloor.com/",
        "category": "Property Listings",
        "operator": "Quikr India Pvt Ltd",
        "data_exposed": ["name", "phone", "apartment_number", "society_name"],
        "how_collected": "Gated society resident directory and property postings.",
        "legal_class": "dpdp_erasure",
        "removal_mechanism": "written_request",
        "removal_url": "https://www.commonfloor.com/",
        "removal_notes": "Request removal from society resident ledger via grievance contact.",
        "severity": "medium",
    },

    # ── Additional Credit & Financial KYC Registries ─────────────────────────
    {
        "id": "crif_highmark", "name": "CRIF High Mark",
        "website": "https://www.crifhighmark.com/",
        "category": "Credit Bureau",
        "operator": "CRIF High Mark Credit Information Services",
        "data_exposed": ["name", "pan", "phone", "address", "loan_accounts", "credit_score"],
        "how_collected": "Mandatory lender credit reporting under CICRA 2005.",
        "legal_class": "dpdp_limited",
        "removal_mechanism": "statutory_only",
        "removal_url": "https://www.crifhighmark.com/",
        "removal_notes": "Retention mandated by CICRA 2005. File dispute for inaccurate records; erasure is not statutory.",
        "severity": "critical",
    },
    {
        "id": "ckyc_cersai", "name": "Central KYC Registry (CKYCR / CERSAI)",
        "website": "https://www.ckycindia.in/",
        "category": "Financial KYC Registry",
        "operator": "CERSAI (Govt of India)",
        "data_exposed": ["name", "pan", "aadhaar_ref", "kyc_documents", "photograph", "permanent_address"],
        "how_collected": "Mandatory KYC reporting by all regulated financial institutions under PMLA.",
        "legal_class": "dpdp_limited",
        "removal_mechanism": "statutory_only",
        "removal_url": "https://www.ckycindia.in/",
        "removal_notes": "PMLA statutory retention overrides DPDP erasure. Modifications go through reporting bank.",
        "severity": "critical",
    },
    {
        "id": "epfo_uan", "name": "EPFO / UAN Member Portal",
        "website": "https://unifiedportal-mem.epfindia.gov.in/",
        "category": "Government Registry",
        "operator": "Employees' Provident Fund Organisation",
        "data_exposed": ["name", "uan", "pan", "aadhaar_linked", "bank_account", "employment_tenure"],
        "how_collected": "Statutory social security contributions under EPF Act 1952.",
        "legal_class": "statutory_publication",
        "removal_mechanism": "statutory_only",
        "removal_url": "https://unifiedportal-mem.epfindia.gov.in/",
        "removal_notes": "Statutory pension registry; non-erasable. Correction via joint declaration.",
        "severity": "critical",
    },
    {
        "id": "gstin_search", "name": "GST Public Portal / GSTIN Search",
        "website": "https://www.gst.gov.in/",
        "category": "Government Registry",
        "operator": "Goods and Services Tax Network (GSTN)",
        "data_exposed": ["name", "pan", "trade_name", "business_address", "filing_status"],
        "how_collected": "Public taxpayer search by PAN under Central Goods and Services Tax Act 2017.",
        "legal_class": "statutory_publication",
        "removal_mechanism": "statutory_only",
        "removal_url": "https://www.gst.gov.in/",
        "removal_notes": "Taxpayer master data is public by statute under CGST Act. Non-erasable while registration subsists.",
        "severity": "high",
    },

    # ── Additional Judicial Records ──────────────────────────────────────────
    {
        "id": "casemine", "name": "Casemine India",
        "website": "https://www.casemine.com/",
        "category": "Judicial Records",
        "operator": "Gauge Data Solutions Pvt Ltd",
        "data_exposed": ["name", "case_details", "court_orders", "judgment_text"],
        "how_collected": "Judicial verdicts indexed from High Courts and Supreme Court.",
        "legal_class": "judicial_record",
        "removal_mechanism": "statutory_only",
        "removal_url": "https://www.casemine.com/",
        "removal_notes": "Court record mirror. DPDP does not apply; court redaction order required.",
        "severity": "high",
    },
    {
        "id": "livelaw", "name": "LiveLaw Court Archives",
        "website": "https://www.livelaw.in/",
        "category": "Judicial Records",
        "operator": "LiveLaw Media Pvt Ltd",
        "data_exposed": ["name", "case_citations", "litigant_names", "order_extracts"],
        "how_collected": "Legal journalism and court reporting.",
        "legal_class": "judicial_record",
        "removal_mechanism": "statutory_only",
        "removal_url": "https://www.livelaw.in/",
        "removal_notes": "Journalistic court reporting. Redaction requires court order.",
        "severity": "medium",
    },

    # ── Additional State Land Records (Statutory Publication) ────────────────
    {
        "id": "mahabhulekh", "name": "Mahabhulekh (Maharashtra Land Records)",
        "website": "https://bhulekh.mahabhumi.gov.in/",
        "category": "Government Registry",
        "operator": "Revenue Department, Government of Maharashtra",
        "data_exposed": ["name", "address", "land_survey_number", "7_12_extract", "crop_details"],
        "how_collected": "Statutory Maharashtra Land Revenue Code 1966.",
        "legal_class": "statutory_publication",
        "removal_mechanism": "statutory_only",
        "removal_url": "https://bhulekh.mahabhumi.gov.in/",
        "removal_notes": "Land revenue records are public under state statute. DPDP s.3(c)(ii) excludes them.",
        "severity": "high",
    },
    {
        "id": "bhoomi_karnataka", "name": "Bhoomi Karnataka",
        "website": "https://landrecords.karnataka.gov.in/",
        "category": "Government Registry",
        "operator": "Revenue Department, Government of Karnataka",
        "data_exposed": ["name", "address", "rtc_details", "land_mutation_history"],
        "how_collected": "Karnataka Land Revenue Act 1964 records.",
        "legal_class": "statutory_publication",
        "removal_mechanism": "statutory_only",
        "removal_url": "https://landrecords.karnataka.gov.in/",
        "removal_notes": "Statutory land register. Non-erasable under DPDP.",
        "severity": "high",
    },
    {
        "id": "dharani_telangana", "name": "Dharani Telangana",
        "website": "https://dharani.telangana.gov.in/",
        "category": "Government Registry",
        "operator": "Government of Telangana",
        "data_exposed": ["name", "pattadar_passbook", "land_extent", "survey_number"],
        "how_collected": "Telangana Rights in Land and Pattadar Passbooks Act 2020.",
        "legal_class": "statutory_publication",
        "removal_mechanism": "statutory_only",
        "removal_url": "https://dharani.telangana.gov.in/",
        "removal_notes": "Statutory land portal. DPDP s.3(c)(ii) exclusion applies.",
        "severity": "high",
    },
    {
        "id": "sarathi_morth", "name": "Sarathi Driving License Portal",
        "website": "https://sarathi.parivahan.gov.in/",
        "category": "Government Registry",
        "operator": "Ministry of Road Transport and Highways (MoRTH)",
        "data_exposed": ["name", "dl_number", "address", "blood_group", "date_of_birth", "rto_jurisdiction"],
        "how_collected": "Motor Vehicles Act 1988 statutory licensing.",
        "legal_class": "statutory_publication",
        "removal_mechanism": "statutory_only",
        "removal_url": "https://sarathi.parivahan.gov.in/",
        "removal_notes": "Statutory driver registry. Corrections via Form 7; non-erasable while license is active.",
        "severity": "critical",
    },

    # ── Major Indian Historical Leaks (Catalogued for identification match) ────
    {
        "id": "mobikwik_leak", "name": "Mobikwik 2021 Data Leak",
        "website": "https://www.mobikwik.com/",
        "category": "Historical Breach",
        "operator": "One Mobikwik Systems Ltd",
        "data_exposed": ["name", "phone", "email", "pan", "aadhaar_card_copies", "bank_account", "passwords"],
        "how_collected": "100M user KYC database leaked and circulated on dark web paste archives.",
        "legal_class": "dpdp_erasure",
        "removal_mechanism": "statutory_only",
        "removal_url": "https://www.mobikwik.com/",
        "removal_notes": "Breach dump cannot be un-published from paste archives; rotate credentials and activate 2FA immediately.",
        "severity": "critical",
    },
    {
        "id": "dominos_india_leak", "name": "Domino's India 2021 Order Leak",
        "website": "https://www.dominos.co.in/",
        "category": "Historical Breach",
        "operator": "Jubilant FoodWorks Ltd",
        "data_exposed": ["name", "phone", "email", "delivery_address", "gps_coordinates", "order_history"],
        "how_collected": "180M order records leaked via compromised support portal.",
        "legal_class": "dpdp_erasure",
        "removal_mechanism": "written_request",
        "removal_url": "https://www.dominos.co.in/",
        "removal_notes": "Request full account erasure and purge of historical order archives under DPDP s.12.",
        "severity": "high",
    },
    {
        "id": "bigbasket_leak", "name": "BigBasket 2020 User Leak",
        "website": "https://www.bigbasket.com/",
        "category": "Historical Breach",
        "operator": "Supermarket Grocery Supplies Pvt Ltd",
        "data_exposed": ["name", "phone", "email", "password_hashes", "date_of_birth", "residential_address"],
        "how_collected": "20M customer records leaked on dark web.",
        "legal_class": "dpdp_erasure",
        "removal_mechanism": "self_serve",
        "removal_url": "https://www.bigbasket.com/",
        "removal_notes": "Delete account in profile settings; reset password across reused services.",
        "severity": "critical",
    },
    {
        "id": "air_india_leak", "name": "Air India / SITA 2021 Passenger Leak",
        "website": "https://www.airindia.com/",
        "category": "Historical Breach",
        "operator": "Air India Ltd",
        "data_exposed": ["name", "passport_number", "phone", "date_of_birth", "frequent_flyer_number", "ticket_details"],
        "how_collected": "Cyberattack on SITA Passenger Service System affecting 4.5M flyers.",
        "legal_class": "dpdp_erasure",
        "removal_mechanism": "written_request",
        "removal_url": "https://www.airindia.com/",
        "removal_notes": "Request Flying Returns frequent flyer account closure and data audit under DPDP.",
        "severity": "critical",
    },
    {
        "id": "railyatri_leak", "name": "RailYatri 2020 Travel Leak",
        "website": "https://www.railyatri.in/",
        "category": "Historical Breach",
        "operator": "Stelling Technologies Pvt Ltd",
        "data_exposed": ["name", "phone", "email", "upi_ids", "train_booking_locations"],
        "how_collected": "Unprotected Elasticsearch cluster exposed 31M user records.",
        "legal_class": "dpdp_erasure",
        "removal_mechanism": "written_request",
        "removal_url": "https://www.railyatri.in/",
        "removal_notes": "Send DPDP notice to grievance officer for complete account and travel history deletion.",
        "severity": "high",
    },
    {
        "id": "upstox_leak", "name": "Upstox 2021 Security Incident",
        "website": "https://upstox.com/",
        "category": "Historical Breach",
        "operator": "RKSV Securities India Pvt Ltd",
        "data_exposed": ["name", "pan", "bank_account", "aadhaar_last4", "kyc_details"],
        "how_collected": "Compromised AWS key exposed 2.5M trading user KYC records.",
        "legal_class": "dpdp_limited",
        "removal_mechanism": "statutory_only",
        "removal_url": "https://upstox.com/",
        "removal_notes": "Broking accounts bound by SEBI 5-year post-closure retention rules. Close demat account to trigger retention clock.",
        "severity": "critical",
    },
    {
        "id": "star_health_leak", "name": "Star Health 2024 Policy Leak",
        "website": "https://www.starhealth.in/",
        "category": "Historical Breach",
        "operator": "Star Health and Allied Insurance Co Ltd",
        "data_exposed": ["name", "phone", "pan", "medical_claims", "diagnostic_reports", "nominee_details"],
        "how_collected": "31M policyholder and claim records circulated online.",
        "legal_class": "dpdp_limited",
        "removal_mechanism": "statutory_only",
        "removal_url": "https://www.starhealth.in/",
        "removal_notes": "IRDAI health insurance regulations require policy retention. Serve grievance notice requesting enhanced fraud monitoring.",
        "severity": "critical",
    },
]


def build():
    dest = os.path.join(BASE, "brokers", "indian_sources.json")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    for s in SOURCES:
        s["country"] = "IN"
        s["jurisdiction"] = "dpdp"
    with open(dest, "w") as f:
        json.dump(SOURCES, f, indent=2, ensure_ascii=False)

    by_class: dict = {}
    for s in SOURCES:
        by_class[s["legal_class"]] = by_class.get(s["legal_class"], 0) + 1
    print(f"    ✓ Wrote {len(SOURCES)} Indian sources → {dest}")
    for k, v in sorted(by_class.items()):
        print(f"        {k:24s} {v}")
    return len(SOURCES)


if __name__ == "__main__":
    build()
