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
