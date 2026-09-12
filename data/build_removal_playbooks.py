"""
build_removal_playbooks.py — How to actually get your data removed, per service.

THE PROBLEM THIS FIXES
----------------------
The earlier build drafted a formal statutory erasure notice for every source.
That is the wrong first move almost every time. Truecaller has an unlisting page.
GitHub has a Delete Account button. Naukri lets you delete your profile from
settings. Serving a DPDP Section 12 notice on a company that offers a two-click
deletion is theatre: it takes weeks, needs a grievance officer to read it, and
achieves what the user could have done in thirty seconds.

So removal now follows a ladder, cheapest effective route first:

  1. self_serve       The service has a delete/unlist page. Go there. Done in
                      minutes, no lawyer, no waiting.
  2. privacy_form     A data-subject-request portal exists. Submit through it.
  3. email_request    No portal, but a privacy/grievance contact is published.
                      A plain written request, not a legal threat.
  4. statutory_notice Nothing above exists, OR the steps above were tried and
                      ignored. NOW the formal notice, citing the statute and
                      starting the compliance clock.
  5. not_removable    Erasure does not lie at all (court records, statutory
                      registers). Explain the real route instead.

Every entry also carries `escalation`: what to do when the cheap route fails.
That is how a real identity-protection service behaves, and it is the difference
between a tool that helps and a tool that performs helpfulness.
"""

import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))

PLAYBOOKS = [
    # ── Indian services: self-serve available ────────────────────────────────
    {
        "id": "truecaller", "service": "Truecaller", "country": "IN",
        "method": "self_serve",
        "url": "https://www.truecaller.com/unlisting",
        "effort_minutes": 5,
        "steps": [
            "Open the Truecaller app and deactivate your account first "
            "(Settings → Privacy Centre → Deactivate). Unlisting before "
            "deactivating lets the number be re-indexed later.",
            "Go to truecaller.com/unlisting.",
            "Enter your number in international format (+91...).",
            "Complete the captcha and submit.",
            "Allow up to 24 hours, then search your own number to confirm.",
        ],
        "escalation": ("If the number reappears after unlisting, that is fresh processing "
                       "after withdrawal of consent — escalate to a DPDP s.12 notice to the "
                       "grievance officer."),
        "legal_class": "dpdp_erasure",
    },
    {
        "id": "naukri", "service": "Naukri.com", "country": "IN",
        "method": "self_serve",
        "url": "https://www.naukri.com/",
        "effort_minutes": 5,
        "steps": [
            "Log in and open your profile settings.",
            "Choose 'Delete my profile' (or set visibility to private as an interim step).",
            "Confirm by email.",
            "Note: recruiters who already downloaded your CV keep their copy. "
            "Deleting the profile stops NEW downloads; it does not recall old ones.",
        ],
        "escalation": ("To reach CVs already distributed to recruiters, a s.12 notice is "
                       "needed asking Naukri to identify downstream recipients under "
                       "s.12(3) and direct their deletion."),
        "legal_class": "dpdp_erasure",
    },
    {
        "id": "shaadi", "service": "Shaadi.com", "country": "IN",
        "method": "self_serve",
        "url": "https://www.shaadi.com/",
        "effort_minutes": 10,
        "steps": [
            "Log in → Settings → Profile Settings.",
            "Choose 'Delete Profile' — NOT 'Hide Profile'. Hiding leaves the record intact.",
            "Select a reason and confirm.",
            "Afterwards, search your name on Google to check for cached copies.",
        ],
        "escalation": ("If the profile is only hidden rather than erased, or cached copies "
                       "persist, serve a s.12 notice — this data includes caste, religion "
                       "and income and warrants firm handling."),
        "legal_class": "dpdp_erasure",
    },
    {
        "id": "justdial", "service": "JustDial", "country": "IN",
        "method": "email_request",
        "url": "https://www.justdial.com/",
        "effort_minutes": 15,
        "steps": [
            "JustDial publishes a Grievance Officer under the IT Rules 2021 — "
            "find the contact on their Privacy Policy page.",
            "Write asking for deletion of your listing and of call/enquiry records "
            "tied to your number.",
            "Quote your registered number and any listing URL.",
            "Keep the sent copy — it starts the clock for escalation.",
        ],
        "escalation": "No reply in 30 days → DPDP s.12 notice, then a DPBI complaint under s.27.",
        "legal_class": "dpdp_erasure",
    },
    {
        "id": "indiamart", "service": "IndiaMART", "country": "IN",
        "method": "email_request",
        "url": "https://www.indiamart.com/",
        "effort_minutes": 15,
        "steps": [
            "Contact the Grievance Officer listed in their Privacy Policy.",
            "Ask for deletion of your buyer/supplier record and for your contact "
            "details to stop being distributed as leads.",
            "State that consent for lead distribution is withdrawn.",
        ],
        "escalation": ("Lead resale is their revenue, so expect pushback. Escalate to a "
                       "s.12 notice citing purpose exhaustion, then the DPBI."),
        "legal_class": "dpdp_erasure",
    },

    # ── Indian: no erasure right ─────────────────────────────────────────────
    {
        "id": "indiankanoon", "service": "Indian Kanoon", "country": "IN",
        "method": "not_removable",
        "url": "https://indiankanoon.org/",
        "effort_minutes": 0,
        "steps": [
            "Do NOT send a privacy notice — a court record has no addressee for one.",
            "The route is an application to the court that issued the judgment, "
            "seeking redaction of your name.",
            "Delhi High Court granted this in Jorawer Singh Mundy v. Union of India "
            "(2021) for a party who had been acquitted.",
            "This needs a lawyer. Indian Kanoon will generally de-index once the "
            "court orders redaction at source.",
        ],
        "escalation": "None available through privacy law. This is litigation, not a DSR.",
        "legal_class": "judicial_record",
    },
    {
        "id": "mca21", "service": "MCA21 / Director Registry", "country": "IN",
        "method": "not_removable",
        "url": "https://www.mca.gov.in/",
        "effort_minutes": 0,
        "steps": [
            "Director particulars are published under the Companies Act 2013.",
            "DPDP s.3(c)(ii) excludes data published under a legal obligation, so "
            "the s.12 erasure right is not engaged.",
            "You can CORRECT details via form DIR-3 KYC / DIR-6.",
            "Commercial mirrors (Zauba Corp, Tofler) re-host this for profit and "
            "can be asked to de-index, even though the MCA source stays.",
        ],
        "escalation": "Target the commercial mirrors, not the statutory register.",
        "legal_class": "statutory_publication",
    },
    {
        "id": "credit_bureaus_in", "service": "CIBIL / Experian / Equifax India",
        "country": "IN", "method": "not_removable",
        "url": "https://www.cibil.com/",
        "effort_minutes": 20,
        "steps": [
            "Retention is mandated by the Credit Information Companies "
            "(Regulation) Act 2005 — erasure is not available.",
            "What you CAN do: raise a dispute for anything inaccurate, free of charge.",
            "Under RBI rules the bureau must resolve a dispute within 30 days.",
            "Consider a credit freeze to block new enquiries.",
        ],
        "escalation": "Unresolved dispute → RBI Ombudsman for Credit Information Companies.",
        "legal_class": "dpdp_limited",
    },

    # ── Global services found by account discovery ───────────────────────────
    {
        "id": "github", "service": "GitHub", "country": "US", "method": "self_serve",
        "url": "https://github.com/settings/admin", "effort_minutes": 3,
        "steps": ["Settings → Account → Delete your account.",
                  "Transfer or delete repositories and organisations you own first.",
                  "Note that commits already pushed to other repos keep your email "
                  "in their history unless you had email privacy enabled."],
        "escalation": "Self-serve is definitive; no escalation needed.",
        "legal_class": "gdpr_erasure",
    },
    {
        "id": "keybase", "service": "Keybase", "country": "US", "method": "self_serve",
        "url": "https://keybase.io/account/delete_me", "effort_minutes": 3,
        "steps": ["Log in and open the delete-account page.", "Confirm deletion."],
        "escalation": "Self-serve is definitive.",
        "legal_class": "gdpr_erasure",
    },
    {
        "id": "gravatar", "service": "Gravatar", "country": "US", "method": "self_serve",
        "url": "https://gravatar.com/", "effort_minutes": 5,
        "steps": ["Gravatar is part of your WordPress.com account.",
                  "Remove the image and profile fields, or delete the WordPress.com "
                  "account entirely.",
                  "Your avatar is keyed to the MD5 of your email — anyone who knows "
                  "your address can look it up until it is removed."],
        "escalation": "Self-serve is definitive.",
        "legal_class": "gdpr_erasure",
    },
    {
        "id": "aboutme", "service": "About.me", "country": "US", "method": "self_serve",
        "url": "https://about.me/", "effort_minutes": 3,
        "steps": ["Log in → Account settings → Delete account."],
        "escalation": "Self-serve is definitive.",
        "legal_class": "gdpr_erasure",
    },
    {
        "id": "linktree", "service": "Linktree", "country": "AU", "method": "self_serve",
        "url": "https://linktr.ee/", "effort_minutes": 3,
        "steps": ["Log in → Account settings → Delete account."],
        "escalation": "Self-serve is definitive.",
        "legal_class": "gdpr_erasure",
    },
    {
        "id": "behance", "service": "Behance", "country": "US", "method": "self_serve",
        "url": "https://www.behance.net/", "effort_minutes": 5,
        "steps": ["Behance is an Adobe service — deleting it may affect your Adobe ID.",
                  "Settings → Account → Delete Behance profile."],
        "escalation": "If the Adobe account blocks it, use Adobe's privacy request form.",
        "legal_class": "gdpr_erasure",
    },
    {
        "id": "soundcloud", "service": "SoundCloud", "country": "DE", "method": "self_serve",
        "url": "https://soundcloud.com/settings/account", "effort_minutes": 3,
        "steps": ["Settings → Account → Delete account."],
        "escalation": "SoundCloud is EU-based; a GDPR Art.17 request is the fallback.",
        "legal_class": "gdpr_erasure",
    },
    {
        "id": "dockerhub", "service": "Docker Hub", "country": "US", "method": "self_serve",
        "url": "https://hub.docker.com/settings/general", "effort_minutes": 5,
        "steps": ["Account Settings → Deactivate account.",
                  "Leave or delete any organisations you own first."],
        "escalation": "Self-serve is definitive.",
        "legal_class": "gdpr_erasure",
    },
    {
        "id": "replit", "service": "Replit", "country": "US", "method": "self_serve",
        "url": "https://replit.com/account", "effort_minutes": 3,
        "steps": ["Account → Delete account.",
                  "Public Repls stay visible until the account is deleted."],
        "escalation": "Self-serve is definitive.",
        "legal_class": "gdpr_erasure",
    },
    {
        "id": "devto", "service": "Dev.to", "country": "US", "method": "self_serve",
        "url": "https://dev.to/settings/account", "effort_minutes": 3,
        "steps": ["Settings → Account → Delete account."],
        "escalation": "Self-serve is definitive.",
        "legal_class": "gdpr_erasure",
    },
    {
        "id": "chesscom", "service": "Chess.com", "country": "US", "method": "self_serve",
        "url": "https://www.chess.com/settings", "effort_minutes": 3,
        "steps": ["Settings → Privacy → Close account."],
        "escalation": "Self-serve is definitive.",
        "legal_class": "gdpr_erasure",
    },
    {
        "id": "buymeacoffee", "service": "Buy Me a Coffee", "country": "US",
        "method": "self_serve", "url": "https://www.buymeacoffee.com/", "effort_minutes": 5,
        "steps": ["Settings → Account → Delete account.",
                  "Payment records may be retained for tax purposes."],
        "escalation": "Retention of payment records is lawful; the profile still goes.",
        "legal_class": "gdpr_erasure",
    },
    {
        "id": "huggingface", "service": "Hugging Face", "country": "US", "method": "self_serve",
        "url": "https://huggingface.co/settings/profile", "effort_minutes": 3,
        "steps": ["Settings → Account → Delete account.",
                  "Remove public models and spaces first if you want backups."],
        "escalation": "Self-serve is definitive.",
        "legal_class": "gdpr_erasure",
    },
    {
        "id": "kaggle", "service": "Kaggle", "country": "US", "method": "self_serve",
        "url": "https://www.kaggle.com/account", "effort_minutes": 3,
        "steps": ["Account Settings → Close account.",
                  "Datasets remain unless deleted prior to account closure."],
        "escalation": "Google/Kaggle privacy grievance portal.",
        "legal_class": "ccpa_erasure",
    },
    {
        "id": "lichess", "service": "Lichess", "country": "FR", "method": "self_serve",
        "url": "https://lichess.org/account/close", "effort_minutes": 2,
        "steps": ["Profile → Close account.",
                  "Confirm password to permanently wipe profile."],
        "escalation": "GDPR Art 17 request to Lichess association contact.",
        "legal_class": "gdpr_erasure",
    },
    {
        "id": "foundit", "service": "Foundit (Monster India)", "country": "IN", "method": "self_serve",
        "url": "https://www.foundit.in/", "effort_minutes": 5,
        "steps": ["Log in → Profile Settings → Account Settings → Delete Account.",
                  "Confirm verification code via email.",
                  "Check recruiter search visibility is toggled off."],
        "escalation": "Serve DPDP s.12 notice requiring notice to downstream recruiters under s.12(3).",
        "legal_class": "dpdp_erasure",
    },
    {
        "id": "internshala", "service": "Internshala", "country": "IN", "method": "self_serve",
        "url": "https://internshala.com/", "effort_minutes": 4,
        "steps": ["Manage Account → Delete Account.",
                  "Enter reason and confirm deletion."],
        "escalation": "Write to grievance officer under IT Rules 2021 / DPDP.",
        "legal_class": "dpdp_erasure",
    },
    {
        "id": "timesjobs", "service": "TimesJobs", "country": "IN", "method": "self_serve",
        "url": "https://www.timesjobs.com/", "effort_minutes": 5,
        "steps": ["My Profile → Account Settings → Delete profile.",
                  "Confirm removal via OTP."],
        "escalation": "Serve DPDP Section 12 erasure demand on Times Business Solutions.",
        "legal_class": "dpdp_erasure",
    },
    {
        "id": "hirist", "service": "Hirist", "country": "IN", "method": "self_serve",
        "url": "https://www.hirist.tech/", "effort_minutes": 3,
        "steps": ["Account Settings → Delete profile.",
                  "Confirm via email link."],
        "escalation": "DPDP Section 12 notice to Info Edge grievance officer.",
        "legal_class": "dpdp_erasure",
    },
    {
        "id": "jeevansathi", "service": "Jeevansathi", "country": "IN", "method": "self_serve",
        "url": "https://www.jeevansathi.com/", "effort_minutes": 5,
        "steps": ["Settings → Profile Settings → Delete Profile.",
                  "Choose 'Delete permanently' instead of temporary hide."],
        "escalation": "DPDP notice citing sensitive demographic and caste data.",
        "legal_class": "dpdp_erasure",
    },
    {
        "id": "communitymatrimony", "service": "CommunityMatrimony", "country": "IN", "method": "self_serve",
        "url": "https://www.communitymatrimony.com/", "effort_minutes": 5,
        "steps": ["Settings → Deactivate/Delete Profile.",
                  "Confirm OTP verification."],
        "escalation": "DPDP Section 12 notice to Matrimony.com grievance officer.",
        "legal_class": "dpdp_erasure",
    },
    {
        "id": "housing", "service": "Housing.com", "country": "IN", "method": "self_serve",
        "url": "https://housing.com/", "effort_minutes": 5,
        "steps": ["My Activity → Listed Properties → Mark as Sold / De-list.",
                  "Profile → Delete Account."],
        "escalation": "Serve DPDP notice to purge cached owner phone and listing details.",
        "legal_class": "dpdp_erasure",
    },
    {
        "id": "nobroker", "service": "NoBroker", "country": "IN", "method": "self_serve",
        "url": "https://www.nobroker.in/", "effort_minutes": 5,
        "steps": ["Dashboard → Listed Properties → Close Listing.",
                  "Account Settings → Delete Account."],
        "escalation": "Email grievance officer to purge contact records from brokerage team.",
        "legal_class": "dpdp_erasure",
    },
    {
        "id": "tradeindia", "service": "TradeIndia", "country": "IN", "method": "email_request",
        "url": "https://www.tradeindia.com/", "effort_minutes": 15,
        "steps": ["Find Grievance Officer details on TradeIndia privacy page.",
                  "Submit written withdrawal of consent for business listing and buyer enquiries."],
        "escalation": "Statutory notice under DPDP Act 2023 s.12(1).",
        "legal_class": "dpdp_erasure",
    },
    {
        "id": "commonfloor", "service": "CommonFloor", "country": "IN", "method": "email_request",
        "url": "https://www.commonfloor.com/", "effort_minutes": 15,
        "steps": ["Contact CommonFloor resident community support.",
                  "Request de-listing of apartment and resident directory profile."],
        "escalation": "DPDP s.12 statutory demand.",
        "legal_class": "dpdp_erasure",
    },
    {
        "id": "instafinancials", "service": "InstaFinancials", "country": "IN", "method": "not_removable",
        "url": "https://www.instafinancials.com/", "effort_minutes": 0,
        "steps": ["Corporate records are statutory filings under the Companies Act 2013.",
                  "DPDP Act s.3(c)(ii) excludes data made publicly available under legal obligation.",
                  "To correct details, submit Form DIR-6 on the MCA21 portal."],
        "escalation": "No erasure right lies against an MCA mirror; correct the source record at MCA.",
        "legal_class": "statutory_publication",
    },
    {
        "id": "quickcompany", "service": "QuickCompany", "country": "IN", "method": "not_removable",
        "url": "https://www.quickcompany.in/", "effort_minutes": 0,
        "steps": ["Statutory corporate mirror. Erasure does not apply under DPDP s.3(c)(ii).",
                  "File correction on MCA portal."],
        "escalation": "Correction only via Ministry of Corporate Affairs.",
        "legal_class": "statutory_publication",
    },
    {
        "id": "crif_highmark", "service": "CRIF High Mark", "country": "IN", "method": "not_removable",
        "url": "https://www.crifhighmark.com/", "effort_minutes": 15,
        "steps": ["Retention is mandated by the Credit Information Companies (Regulation) Act 2005.",
                  "Erasure is not available; dispute and correction are.",
                  "File online dispute for erroneous credit enquiries or loan defaults."],
        "escalation": "Escalate unresolved disputes to RBI Banking Ombudsman.",
        "legal_class": "dpdp_limited",
    },
    {
        "id": "ckyc_cersai", "service": "Central KYC Registry (CKYCR)", "country": "IN", "method": "not_removable",
        "url": "https://www.ckycindia.in/", "effort_minutes": 20,
        "steps": ["KYC records maintained under Prevention of Money Laundering Act (PMLA).",
                  "Statutory retention duty overrides DPDP erasure.",
                  "Request KYC profile update through your primary banking institution."],
        "escalation": "Correction via reporting financial entity.",
        "legal_class": "dpdp_limited",
    },
    {
        "id": "epfo_uan", "service": "EPFO / UAN Member Portal", "country": "IN", "method": "not_removable",
        "url": "https://unifiedportal-mem.epfindia.gov.in/", "effort_minutes": 15,
        "steps": ["Statutory social security records under EPF Act 1952. Non-erasable.",
                  "Corrections submitted via Joint Declaration Form counter-signed by employer."],
        "escalation": "Grievance through EPFiGMS portal.",
        "legal_class": "statutory_publication",
    },
    {
        "id": "gstin_search", "service": "GST Public Portal", "country": "IN", "method": "not_removable",
        "url": "https://www.gst.gov.in/", "effort_minutes": 15,
        "steps": ["Taxpayer registration is public by statute under CGST Act 2017.",
                  "Cancellation of GSTIN is available via Form GST REG-16 upon business closure."],
        "escalation": "Surrender registration through Jurisdictional Tax Officer.",
        "legal_class": "statutory_publication",
    },
    {
        "id": "casemine", "service": "Casemine India", "country": "IN", "method": "not_removable",
        "url": "https://www.casemine.com/", "effort_minutes": 0,
        "steps": ["Judicial record mirror. DPDP does not apply.",
                  "Redaction requires an application to the High Court or Supreme Court that issued the verdict."],
        "escalation": "Formal petition for redaction of identity under Article 226/32.",
        "legal_class": "judicial_record",
    },
    {
        "id": "livelaw", "service": "LiveLaw Court Archives", "country": "IN", "method": "not_removable",
        "url": "https://www.livelaw.in/", "effort_minutes": 0,
        "steps": ["Journalistic reporting of public judicial proceedings.",
                  "Removal requires certified court order granting anonymity."],
        "escalation": "Judicial application to trial/appellate court.",
        "legal_class": "judicial_record",
    },
    {
        "id": "mahabhulekh", "service": "Mahabhulekh (Maharashtra Land Records)", "country": "IN", "method": "not_removable",
        "url": "https://bhulekh.mahabhumi.gov.in/", "effort_minutes": 0,
        "steps": ["Land ownership records are statutory public records under Maharashtra Land Revenue Code.",
                  "DPDP s.3(c)(ii) excludes statutory publications. Mutation entry required for change of ownership."],
        "escalation": "Talathi / Tahsildar revenue office for statutory record correction.",
        "legal_class": "statutory_publication",
    },
    {
        "id": "bhoomi_karnataka", "service": "Bhoomi Karnataka", "country": "IN", "method": "not_removable",
        "url": "https://landrecords.karnataka.gov.in/", "effort_minutes": 0,
        "steps": ["Statutory land record under Karnataka Land Revenue Act. Non-erasable."],
        "escalation": "Revenue officer dispute filing.",
        "legal_class": "statutory_publication",
    },
    {
        "id": "dharani_telangana", "service": "Dharani Telangana", "country": "IN", "method": "not_removable",
        "url": "https://dharani.telangana.gov.in/", "effort_minutes": 0,
        "steps": ["Statutory record under Telangana Rights in Land Act. Non-erasable."],
        "escalation": "District Collector revenue grievance.",
        "legal_class": "statutory_publication",
    },
    {
        "id": "sarathi_morth", "service": "Sarathi Driving License Portal", "country": "IN", "method": "not_removable",
        "url": "https://sarathi.parivahan.gov.in/", "effort_minutes": 15,
        "steps": ["Statutory vehicle driving registry under Motor Vehicles Act 1988.",
                  "Corrections go through Parivahan portal with RTO verification."],
        "escalation": "RTO grievance officer.",
        "legal_class": "statutory_publication",
    },
    {
        "id": "mobikwik_leak", "service": "Mobikwik Leak Archive", "country": "IN", "method": "statutory_notice",
        "url": "https://www.mobikwik.com/", "effort_minutes": 15,
        "steps": ["Historical dark-web leak cannot be erased from peer-to-peer torrents/dumps.",
                  "Serve DPDP erasure request to One Mobikwik Systems to purge internal legacy records.",
                  "Immediately rotate banking passwords, enable 2FA, and monitor CIBIL reports."],
        "escalation": "File complaint with Data Protection Board of India (DPBI) and CERT-In.",
        "legal_class": "dpdp_erasure",
    },
    {
        "id": "dominos_india_leak", "service": "Domino's India Leak Archive", "country": "IN", "method": "email_request",
        "url": "https://www.dominos.co.in/", "effort_minutes": 10,
        "steps": ["Submit account and delivery address purge request to Jubilant FoodWorks grievance officer.",
                  "Cite DPDP s.12(1) withdrawal of consent for historical customer database."],
        "escalation": "Formal DPDP Section 12 erasure notice.",
        "legal_class": "dpdp_erasure",
    },
    {
        "id": "bigbasket_leak", "service": "BigBasket Leak Archive", "country": "IN", "method": "self_serve",
        "url": "https://www.bigbasket.com/", "effort_minutes": 5,
        "steps": ["Delete customer account in BigBasket mobile app.",
                  "Reset passwords on all accounts sharing the same email/password."],
        "escalation": "DPDP s.12 notice to grievance officer.",
        "legal_class": "dpdp_erasure",
    },
    {
        "id": "air_india_leak", "service": "Air India SITA Leak Archive", "country": "IN", "method": "email_request",
        "url": "https://www.airindia.com/", "effort_minutes": 15,
        "steps": ["Write to Air India DPO requesting audit and purge of compromised frequent flyer profile.",
                  "Monitor passport number usage for identity theft."],
        "escalation": "DPBI supervisory authority complaint.",
        "legal_class": "dpdp_erasure",
    },
    {
        "id": "railyatri_leak", "service": "RailYatri Leak Archive", "country": "IN", "method": "email_request",
        "url": "https://www.railyatri.in/", "effort_minutes": 10,
        "steps": ["Email RailYatri grievance officer requesting complete customer ledger deletion under DPDP s.12."],
        "escalation": "DPBI complaint for non-compliance.",
        "legal_class": "dpdp_erasure",
    },
    {
        "id": "upstox_leak", "service": "Upstox Security Incident", "country": "IN", "method": "statutory_only",
        "url": "https://upstox.com/", "effort_minutes": 15,
        "steps": ["SEBI regulations require 5-year post-account-closure retention of KYC data.",
                  "Formally close trading and demat accounts to start the 5-year statutory countdown clock."],
        "escalation": "SEBI SCORES portal grievance.",
        "legal_class": "dpdp_limited",
    },
    {
        "id": "star_health_leak", "service": "Star Health Leak Archive", "country": "IN", "method": "statutory_only",
        "url": "https://www.starhealth.in/", "effort_minutes": 15,
        "steps": ["IRDAI health insurance regulations govern policy data retention.",
                  "File security inquiry with Star Health Grievance Officer requesting fraud monitoring."],
        "escalation": "IRDAI Bima Bharosa grievance.",
        "legal_class": "dpdp_limited",
    },
]

METHOD_ORDER = ["self_serve", "privacy_form", "email_request", "statutory_notice", "not_removable"]

METHOD_INFO = {
    "self_serve": {
        "label": "Delete it yourself",
        "why": "The service offers deletion directly. Fastest route, no waiting, no lawyer.",
        "typical_time": "minutes",
    },
    "privacy_form": {
        "label": "Submit a privacy request",
        "why": "A data-subject-request portal exists; use it rather than writing a letter.",
        "typical_time": "days",
    },
    "email_request": {
        "label": "Write to the privacy contact",
        "why": "No self-serve route, but a grievance officer or DPO is published. "
               "A plain written request, not a legal threat.",
        "typical_time": "1-4 weeks",
    },
    "statutory_notice": {
        "label": "Serve a statutory notice",
        "why": "Used when nothing simpler exists, or the simpler routes were tried and "
               "ignored. Cites the statute and starts the compliance clock.",
        "typical_time": "30-45 days",
    },
    "not_removable": {
        "label": "Erasure does not apply",
        "why": "A privacy request has no addressee in law here. The real route is stated instead.",
        "typical_time": "n/a",
    },
}


def build():
    dest = os.path.join(BASE, "removal_playbooks.json")
    payload = {"playbooks": PLAYBOOKS, "method_order": METHOD_ORDER, "method_info": METHOD_INFO}
    with open(dest, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    counts: dict = {}
    for pb in PLAYBOOKS:
        counts[pb["method"]] = counts.get(pb["method"], 0) + 1
    print(f"    ✓ Wrote {len(PLAYBOOKS)} removal playbooks → {dest}")
    for m in METHOD_ORDER:
        if m in counts:
            print(f"        {m:18s} {counts[m]}")
    return len(PLAYBOOKS)


if __name__ == "__main__":
    build()
