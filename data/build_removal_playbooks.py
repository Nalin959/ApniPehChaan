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
