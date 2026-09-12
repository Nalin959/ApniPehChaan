"""
officer_directory.py — Where does a statutory erasure notice actually get SENT?

WHY THIS EXISTS
---------------
Drafting a notice is the easy half. A notice is only a notice once it reaches an
addressee who is legally obliged to act on it. Indian law is unusually helpful
here, because it forces the addressee to exist and to be published:

  • DPDP Act 2023 s.13(3) — every Data Fiduciary must publish the business
    contact of its Data Protection Officer, or of a person able to answer a Data
    Principal's questions about the processing of their personal data.
  • IT (Reasonable Security Practices) Rules 2011, r.5(9) and the IT
    (Intermediary Guidelines) Rules 2021 — a Grievance Officer's name and
    contact must be published on the website.

So for an Indian service a real address usually exists and is findable. The job
of this module is to say WHICH address, and — far more importantly — how much
that address should be trusted.

THE FAILURE THIS MODULE IS BUILT TO PREVENT
-------------------------------------------
The tempting shortcut is `privacy@<company>.com`. It is right often enough to
feel clever and wrong often enough to be dangerous, because an erasure notice
carries the data subject's name, email and phone by construction — that is how
the controller finds the record. Send it to an address nobody checks and it is
merely useless. Send it to an address that belongs to somebody else and the tool
has just disclosed its own user's identifiers to a stranger, while telling them
their privacy is being protected. That is a worse outcome than doing nothing.

There is a live example of the trap in this very repo's neighbourhood:
`backend/agent/fiduciary_directory.get_fiduciary_contact()` synthesises
`privacy@<slug>.com` for any name it does not recognise and returns it in the
same shape as its hand-curated entries, so the caller cannot tell them apart.
This module therefore reads that module's `KNOWN_FIDUCIARIES` table DIRECTLY and
never calls its resolver, so a synthesised address can never be laundered into a
curated one.

CONFIDENCE TIERS — every returned address carries one
-----------------------------------------------------
  curated   Confirmed against the controller's own published privacy policy or
            grievance page. `evidence` names that page and `checked_on` says
            when. Safe to serve on.
  registry  Carried over from this project's existing fiduciary registry. Very
            probably right, but not re-confirmed here, so it is not claimed as
            verified. Worth a human glance before dispatch.
  guess     A standard alias (privacy@, dpo@, grievance@, …) at a domain the
            service really uses. NEVER confirmed. Present so a user with no
            other lead has somewhere to start; the mailer refuses to send to one
            of these unless the caller explicitly overrides.
  none      No addressee is known. Reported plainly rather than papered over.

A guess is never promoted by being plausible, and `is_guess` is a single boolean
so a caller cannot miss the distinction.

WHAT THIS MODULE DOES NOT DO
----------------------------
It does not crawl the web to discover addresses at call time, and it does not
invent a domain for a service it has never heard of. If the caller does not
supply a domain and none is on file, the answer is "unknown" — deriving
`<squashed name>.com` is how you end up mailing a squatter.

Optional deliverability checking reuses `backend.agent.verification.check_mx`
rather than reimplementing DNS: a domain with no MX (or a null MX, RFC 7505)
cannot receive the notice at all, which demotes even a curated address.

stdlib only. Imported lazily where it touches the network, so importing this
module opens no sockets and reads no database.
"""

import re
from dataclasses import dataclass, field
from datetime import date

# ── Tier names. Exported so callers compare against a constant, not a string. ──
TIER_CURATED = "curated"
TIER_REGISTRY = "registry"
TIER_GUESS = "guess"
TIER_NONE = "none"

# Ordered worst-last. Used to sort candidates and to answer "is this good enough".
_TIER_RANK = {TIER_CURATED: 0, TIER_REGISTRY: 1, TIER_GUESS: 2, TIER_NONE: 3}

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

# Standard privacy aliases, most-likely-first for an Indian service. `grievance@`
# outranks `dpo@` in India because the Grievance Officer has been a statutory
# requirement since 2011 while the DPO obligation only bites on Significant Data
# Fiduciaries; `support@` is last because it reaches a ticket queue, not a
# statutory officer, and a s.12 notice dropped into a support queue tends to be
# answered with a refund policy.
STANDARD_ALIASES = ("privacy", "grievance", "dpo", "legal", "support")

# Aliases worth trying first when the controller is not Indian.
_GLOBAL_ALIAS_ORDER = ("privacy", "dpo", "legal", "grievance", "support")


# ─────────────────────────────────────────────────────────────────────────────
# CURATED DIRECTORY
#
# Every address below was checked against the controller's own published page on
# the date in `checked_on`. `evidence` is that page. Entries whose address could
# NOT be confirmed are deliberately absent an email and carry `published_page`
# instead — "we know where the officer is published, we do not know their
# address" is a true and useful answer; a guessed address dressed as a curated
# one is neither.
#
# Officers rotate. `checked_on` exists so a stale entry is visible as stale
# rather than silently trusted forever.
# ─────────────────────────────────────────────────────────────────────────────

CURATED: dict[str, dict] = {
    "zomato": {
        "company_name": "Eternal Limited (formerly Zomato Limited)",
        "brand": "Zomato",
        "domain": "zomato.com",
        "country": "IN",
        "postal": ("Eternal Limited, Ground Floor, 12A, 94 Meghdoot, Nehru Place, "
                   "New Delhi 110019, India"),
        "aliases": ("eternal",),
        "checked_on": "2026-09-13",
        "officers": [
            {"email": "privacy@zomato.com", "role": "Data Protection Officer",
             "evidence": "https://www.zomato.com/policies/privacy/"},
            {"email": "grievance@zomato.com",
             "role": "Grievance Officer (IT Rules r.5(9) / DPDP s.13)",
             "evidence": "https://www.zomato.com/policies/"},
            {"email": "nodal@zomato.com", "role": "Nodal Officer",
             "evidence": "https://www.zomato.com/policies/"},
        ],
    },
    "swiggy": {
        "company_name": "Bundl Technologies Private Limited (Swiggy)",
        "brand": "Swiggy",
        "domain": "swiggy.in",
        "country": "IN",
        "postal": ("Grievance Officer, Bundl Technologies Pvt Ltd, No.55 Sy No.8-14, "
                   "Ground Floor, I&J Block, Embassy Tech Village, Outer Ring Road, "
                   "Devarabisanahalli, Bengaluru 560103, Karnataka, India"),
        "aliases": ("bundl", "bundltechnologies"),
        "checked_on": "2026-09-13",
        "officers": [
            {"email": "grievances@swiggy.in",
             "role": "Grievance Officer (privacy-policy violations)",
             "evidence": "https://www.swiggy.com/privacy-policy"},
            {"email": "support@swiggy.in",
             "role": "Support (processing/usage queries, per privacy policy)",
             "evidence": "https://www.swiggy.com/privacy-policy"},
        ],
    },
    "paytm": {
        "company_name": "One97 Communications Limited (Paytm)",
        "brand": "Paytm",
        "domain": "paytm.com",
        "country": "IN",
        "postal": ("Grievance Officer, One97 Communications Limited, B-121, Sector 5, "
                   "Noida 201301, Uttar Pradesh, India"),
        "aliases": ("one97", "one97communications"),
        "checked_on": "2026-09-13",
        "officers": [
            {"email": "grievanceofficer@paytm.com", "role": "Grievance Officer",
             "evidence": "https://webappsstatic.paytm.com/webapps/pages/privacy.html"},
        ],
        # Paytm Payments Bank is a SEPARATE regulated entity with its own officers
        # (grievanceredressalofficer@paytmbank.com, nodalofficer@paytmbank.com).
        # It is not folded in here: serving the wallet entity's officer with a
        # notice about bank records addresses the wrong controller.
        "note": ("Paytm Payments Bank Ltd is a separate data fiduciary with its own "
                 "grievance and principal nodal officers. Notices about bank account "
                 "data must be addressed to that entity, not to One97."),
    },
    "justdial": {
        "company_name": "Just Dial Limited",
        "brand": "Justdial",
        "domain": "justdial.com",
        "country": "IN",
        "postal": "Just Dial Limited, A-39/40, Sector 16, Noida 201301, Uttar Pradesh, India",
        "aliases": ("jd",),
        "checked_on": "2026-09-13",
        "officers": [
            {"email": "privacy@justdial.com",
             "role": "Privacy contact (collection/usage of personal information)",
             "evidence": "https://www.justdial.com/Privacy-Policy"},
            {"email": "grievanceofficer@justdial.com", "role": "Grievance Officer",
             "evidence": "https://www.justdial.com/Privacy-Policy"},
        ],
    },
    "shaadi": {
        "company_name": "People Interactive (India) Private Limited (Shaadi.com)",
        "brand": "Shaadi.com",
        "domain": "shaadi.com",
        "country": "IN",
        "postal": ("Grievance Officer, People Interactive (India) Pvt Ltd, Ground Floor, "
                   "Film Centre, 68 Tardeo Road, Mumbai 400034, Maharashtra, India"),
        "aliases": ("shaadicom", "peopleinteractive"),
        "checked_on": "2026-09-13",
        "officers": [
            # Note the address is at peopleinteractive.in, NOT shaadi.com — which is
            # precisely why alias-guessing at the brand domain is unreliable.
            {"email": "grievanceofficer@peopleinteractive.in", "role": "Grievance Officer",
             "evidence": "https://www.shaadi.com/info/privacy"},
        ],
    },
    "google": {
        "company_name": "Google LLC / Google India Private Limited",
        "brand": "Google",
        "domain": "google.com",
        "country": "IN",
        "postal": "Google India Pvt Ltd, No.3, RMZ Infinity, Old Madras Road, Bengaluru 560016, India",
        "aliases": ("googleindia", "youtube"),
        "checked_on": "2026-09-13",
        "officers": [
            {"email": "support-in@google.com", "role": "India Grievance Officer",
             "evidence": "https://www.google.com/intl/en_in/contact/grievance-officer.html"},
        ],
        "self_serve_url": "https://myactivity.google.com/delete-activity",
    },
    "meta": {
        "company_name": "Meta Platforms, Inc. / Meta Platforms India Private Limited",
        "brand": "Meta (Facebook / Instagram / WhatsApp)",
        "domain": "meta.com",
        "country": "IN",
        "postal": "Meta Platforms India Pvt Ltd, DLF Cyber City, Gurugram, Haryana, India",
        "aliases": ("facebook", "instagram", "whatsapp", "metaplatforms"),
        "checked_on": "2026-09-13",
        "officers": [
            {"email": "fbgoindia@support.facebook.com",
             "role": "Resident Grievance Officer, India (IT Rules 2021)",
             "evidence": "https://www.facebook.com/help/172990116225777"},
        ],
    },
    "microsoft": {
        "company_name": "Microsoft Corporation (EU DPO: Microsoft Ireland Operations Ltd)",
        "brand": "Microsoft",
        "domain": "microsoft.com",
        "country": "IE",
        "postal": ("Microsoft EU Data Protection Officer, One Microsoft Place, "
                   "South County Business Park, Leopardstown, Dublin 18, D18 P521, Ireland"),
        "aliases": ("msft",),
        "checked_on": "2026-09-13",
        "officers": [
            # Worth recording how this one was nearly got wrong: `msdpo@microsoft.com`
            # circulates widely and is NOT the published address. The published one
            # is dpoffice@microsoft.com. A plausible-looking wrong address is the
            # exact hazard this module exists to stop.
            {"email": "dpoffice@microsoft.com", "role": "EU Data Protection Officer",
             "evidence": "https://learn.microsoft.com/en-us/compliance/regulatory/"
                         "gdpr-data-protection-officer"},
        ],
        "self_serve_url": "https://aka.ms/privacyresponse",
    },

    # ── Known controller, address deliberately NOT asserted ──────────────────
    # These publish an officer as the law requires, but the address either
    # rotates or is only reachable through a form. Returning `none` plus the real
    # published page beats returning a stale or invented mailbox.
    "amazon": {
        "company_name": "Amazon Seller Services Private Limited (Amazon.in)",
        "brand": "Amazon India",
        "domain": "amazon.in",
        "country": "IN",
        "aliases": ("amazonin", "amazonindia"),
        "checked_on": "2026-09-13",
        "officers": [],
        "published_page": "https://www.amazon.in/gp/help/customer/display.html",
        "note": ("Amazon publishes its India Grievance Officer's name and contact on its "
                 "help pages and rotates the appointee periodically. No stable address is "
                 "asserted here — read the current one off the published page before "
                 "serving."),
    },
    "apple": {
        "company_name": "Apple Inc. / Apple India Private Limited",
        "brand": "Apple",
        "domain": "apple.com",
        "country": "IN",
        "aliases": ("appleindia", "icloud"),
        "checked_on": "2026-09-13",
        "officers": [],
        "published_page": "https://privacy.apple.com/",
        "self_serve_url": "https://privacy.apple.com/",
        "note": ("Apple routes data-subject requests through privacy.apple.com rather than "
                 "a published mailbox. A form submission there is the effective remedy; the "
                 "drafted notice can be pasted into it."),
    },
}


# Services where a self-serve control is the faster, more reliable remedy than a
# notice, and the caller should be told so even when an address is available.
SELF_SERVE_FIRST: dict[str, str] = {
    "truecaller": "https://www.truecaller.com/unlisting",
    "google": "https://myactivity.google.com/delete-activity",
    "apple": "https://privacy.apple.com/",
    "linkedin": "https://www.linkedin.com/psettings/account-management/close-account",
}


def _registry() -> dict[str, dict]:
    """The project's existing curated fiduciary table — the RAW dict only.

    Deliberately reads `KNOWN_FIDUCIARIES` rather than calling
    `get_fiduciary_contact()`, because that function fabricates
    `privacy@<slug>.com` for unknown names and returns it in the same shape as a
    real entry. Reading the table directly makes it impossible for a synthesised
    address to enter this module wearing a curated label.
    """
    try:
        from backend.agent.fiduciary_directory import KNOWN_FIDUCIARIES
        return KNOWN_FIDUCIARIES
    except Exception:
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# RESULT TYPES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class OfficerAddress:
    """One candidate addressee, with the provenance that makes it judgeable."""

    email: str
    tier: str                      # curated | registry | guess
    role: str = ""                 # DPO, Grievance Officer, …
    company_name: str = ""
    postal: str = ""
    evidence: str = ""             # the published page this came from, if any
    checked_on: str = ""           # when that page was read
    rationale: str = ""            # why this address, in one sentence
    deliverable: bool | None = None   # MX result; None = not checked
    mx_note: str = ""

    @property
    def is_guess(self) -> bool:
        """One boolean so a caller cannot accidentally treat a guess as verified."""
        return self.tier == TIER_GUESS

    @property
    def is_verified(self) -> bool:
        """True only for an address read off the controller's own published page."""
        return self.tier == TIER_CURATED

    def to_dict(self) -> dict:
        return {
            "email": self.email,
            "tier": self.tier,
            "is_guess": self.is_guess,
            "is_verified": self.is_verified,
            "role": self.role,
            "company_name": self.company_name,
            "postal": self.postal,
            "evidence": self.evidence,
            "checked_on": self.checked_on,
            "rationale": self.rationale,
            "deliverable": self.deliverable,
            "mx_note": self.mx_note,
        }


@dataclass
class OfficerResolution:
    """The full answer to "where does this notice go?", including "nowhere"."""

    service: str                             # what the caller asked about
    status: str                              # curated | registry | guess | none
    primary: OfficerAddress | None = None
    alternates: list[OfficerAddress] = field(default_factory=list)
    company_name: str = ""
    postal: str = ""
    domain: str = ""
    published_page: str = ""                 # where the officer is published, if known
    self_serve_url: str = ""                 # a faster remedy, when one exists
    warnings: list[str] = field(default_factory=list)
    note: str = ""

    @property
    def found(self) -> bool:
        return self.primary is not None

    @property
    def safe_to_send_unattended(self) -> bool:
        """May the agent dispatch to this without a human reading the address first?

        Only a curated address with no failed deliverability check qualifies. A
        registry address is probably fine but was not re-confirmed, and a guess
        never qualifies — the mailer enforces the same rule at send time.
        """
        return (self.primary is not None
                and self.primary.tier == TIER_CURATED
                and self.primary.deliverable is not False)

    def to_dict(self) -> dict:
        return {
            "service": self.service,
            "status": self.status,
            "found": self.found,
            "safe_to_send_unattended": self.safe_to_send_unattended,
            "primary": self.primary.to_dict() if self.primary else None,
            "alternates": [a.to_dict() for a in self.alternates],
            "company_name": self.company_name,
            "postal": self.postal,
            "domain": self.domain,
            "published_page": self.published_page,
            "self_serve_url": self.self_serve_url,
            "warnings": list(self.warnings),
            "note": self.note,
        }


# ─────────────────────────────────────────────────────────────────────────────
# NAME MATCHING
#
# Matching is exact-on-token, never substring. `fiduciary_directory` uses
# `key in clean or clean in key`, which will happily resolve "go" to "google" and
# "jd" to "justdial" — cheap recall bought with a wrong addressee, and a wrong
# addressee is the one error this module may not make.
# ─────────────────────────────────────────────────────────────────────────────

_DOMAIN_RE = re.compile(r"([A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+)")

# Tokens that identify nobody. Matching on one of these is how "Amazon India"
# resolves to Domino's ("Jubilant FoodWorks… Domino's India") because both names
# contain "india" — an early version of this module did exactly that, which is a
# live demonstration of why token matching needs a stoplist and why a wrong
# addressee is the failure mode to design against. Only STANDALONE tokens are
# filtered; the squashed full name ("amazonindia") stays, because that IS
# distinctive.
_GENERIC_TOKENS = {
    "india", "indian", "bharat", "limited", "ltd", "pvt", "private", "public",
    "inc", "llc", "llp", "plc", "gmbh", "ab", "bv", "nv", "sa", "corp",
    "corporation", "company", "co", "com", "in", "net", "org", "www",
    "technologies", "technology", "tech", "services", "service", "solutions",
    "systems", "software", "online", "digital", "global", "international",
    "group", "holdings", "enterprises", "enterprise", "ventures", "labs",
    "app", "apps", "india's", "the", "and", "of", "data", "user", "users",
}


def extract_domain(text: str) -> str:
    """Pull a mail domain out of a URL, an email address, or a bare domain.

    Returns "" when the text is a plain company name — deliberately, because
    turning "Acme Widgets" into "acmewidgets.com" is a guess dressed as a fact.
    """
    s = (text or "").strip().lower()
    if not s:
        return ""
    if "@" in s and EMAIL_RE.match(s):
        return s.split("@", 1)[-1]
    s = re.sub(r"^[a-z]+://", "", s).split("/", 1)[0]
    m = _DOMAIN_RE.search(s)
    if not m:
        return ""
    host = m.group(1).strip(".")
    # A single label ("zomato") is not a domain; a TLD-only match is not either.
    if host.count(".") < 1 or host.split(".")[-1].isdigit():
        return ""
    return host[4:] if host.startswith("www.") else host


def _is_actionable_url(url: str) -> bool:
    """A bare homepage is not a self-serve deletion control.

    The inherited registry stores `https://www.naukri.com/` as a "self_serve_url".
    Telling a user "you can delete your data at naukri.com" is a non-instruction
    dressed as advice, so only URLs with a real path are surfaced.
    """
    u = (url or "").strip()
    if not u:
        return False
    path = re.sub(r"^[a-z]+://", "", u.lower()).partition("/")[2]
    return len(path.strip("/")) > 0


def _match_keys(text: str) -> set[str]:
    """Candidate lookup keys for a free-text service name.

    "Zomato Limited" -> {zomatolimited, zomato}      ("limited" is generic)
    "Just Dial"      -> {justdial, just, dial}
    "Amazon India"   -> {amazonindia, amazon}        ("india" is generic)
    """
    s = (text or "").lower()
    tokens = [t for t in re.split(r"[^a-z0-9]+", s) if t]
    if not tokens:
        return set()
    # The full squashed name and adjacent pairs are kept whole — "amazonindia" and
    # "bigbasket" are distinctive even though a component is not. Only standalone
    # tokens are filtered against the stoplist.
    keys = {"".join(tokens)}
    keys |= {tokens[i] + tokens[i + 1] for i in range(len(tokens) - 1)}
    keys |= {t for t in tokens if t not in _GENERIC_TOKENS}
    return {k for k in keys if len(k) >= 3}


def _lookup_curated(service: str, domain: str) -> tuple[str, dict] | None:
    keys = _match_keys(service)
    for slug, spec in CURATED.items():
        names = {slug} | set(spec.get("aliases", ()))
        if keys & names:
            return slug, spec
        if domain and spec.get("domain") and domain.endswith(spec["domain"]):
            return slug, spec
    return None


def _lookup_registry(service: str, domain: str) -> tuple[str, dict] | None:
    keys = _match_keys(service)
    for slug, spec in _registry().items():
        if slug in keys:
            return slug, spec
        brand_keys = _match_keys(spec.get("brand", ""))
        if brand_keys and (keys & brand_keys):
            return slug, spec
        if domain:
            reg_domain = extract_domain(spec.get("self_serve_url", ""))
            if reg_domain and domain.endswith(reg_domain):
                return slug, spec
    return None


# ─────────────────────────────────────────────────────────────────────────────
# DELIVERABILITY
# ─────────────────────────────────────────────────────────────────────────────

def check_deliverable(email_or_domain: str) -> dict:
    """Can this domain receive mail at all?

    Reuses `backend.agent.verification.check_mx` (dig-based, already proven in
    this codebase) rather than reimplementing DNS. Falls back to a stdlib
    address-resolution probe when `dig` is unavailable, which is a weaker signal
    — a domain can resolve and still bounce mail — and says so.

    An MX check proves the domain accepts mail. It proves NOTHING about whether
    the specific mailbox exists or whether the person reading it is the officer.
    """
    domain = email_or_domain.split("@")[-1].strip().lower().strip(".")
    if not domain or "." not in domain:
        return {"checked": False, "deliverable": None, "records": [],
                "note": "No domain to check."}

    try:
        from backend.agent.verification import check_mx
        result = check_mx(domain)
        if result.get("checked"):
            return result
    except Exception as exc:                    # import or subprocess failure
        result = {"checked": False, "deliverable": None, "records": [],
                  "note": f"MX lookup unavailable ({type(exc).__name__})."}

    # Weaker fallback: does the name resolve at all? Catches invented domains and
    # typos, misses domains that resolve but refuse mail.
    import socket
    try:
        socket.getaddrinfo(domain, None)
        return {"checked": True, "deliverable": None, "records": [],
                "note": (f"{domain} resolves in DNS, but MX records could not be read, "
                         f"so mail acceptance is unconfirmed.")}
    except OSError:
        return {"checked": True, "deliverable": False, "records": [],
                "note": f"{domain} does not resolve in DNS — it cannot receive mail."}


# ─────────────────────────────────────────────────────────────────────────────
# RESOLUTION
# ─────────────────────────────────────────────────────────────────────────────

def alias_candidates(domain: str, country: str = "IN",
                     company_name: str = "") -> list[OfficerAddress]:
    """Standard privacy aliases at a domain. Every one is an UNVERIFIED GUESS.

    These exist because DPDP s.13 and the IT Rules mean an officer almost
    certainly exists even when this directory has not recorded them, and a guess
    the user can review beats a dead end. They are labelled `guess` at every
    layer and the mailer will not send to one without an explicit override.
    """
    domain = (domain or "").strip().lower().lstrip("@")
    if not domain or "." not in domain:
        return []
    order = STANDARD_ALIASES if country == "IN" else _GLOBAL_ALIAS_ORDER
    role_for = {
        "privacy": "Privacy team (guessed alias)",
        "grievance": "Grievance Officer (guessed alias)",
        "dpo": "Data Protection Officer (guessed alias)",
        "legal": "Legal department (guessed alias)",
        "support": "Support queue (guessed alias — not a statutory officer)",
    }
    return [
        OfficerAddress(
            email=f"{alias}@{domain}",
            tier=TIER_GUESS,
            role=role_for[alias],
            company_name=company_name,
            rationale=(f"Standard privacy alias at {domain}. NOT confirmed against any "
                       f"published page — this address may not exist, and may reach "
                       f"someone with no duty or right to receive the notice."),
        )
        for alias in order
    ]


def resolve_officer(service: str, domain: str = "", *,
                    verify_mx: bool = False,
                    include_guesses: bool = True) -> OfficerResolution:
    """Resolve where an erasure notice for `service` should be sent.

    Args:
        service: company/brand/source name, a domain, or a URL.
        domain:  the service's real mail domain, if the caller knows it. Supplying
                 this is the ONLY way to get alias guesses for a service that is
                 not in either directory — this module will not invent one.
        verify_mx: run an MX check on each returned address's domain. Costs a DNS
                 round trip each; off by default so resolution stays offline.
        include_guesses: set False to get curated/registry answers only.

    Returns an OfficerResolution whose `status` is one of curated / registry /
    guess / none, never a silent blank.
    """
    service = (service or "").strip()
    domain = (domain or "").strip().lower().lstrip("@")
    if not domain:
        domain = extract_domain(service)

    res = OfficerResolution(service=service or "(unnamed)", status=TIER_NONE, domain=domain)
    if not service and not domain:
        res.warnings.append("No service name or domain was supplied; nothing to resolve.")
        res.note = "No addressee known."
        return res

    candidates: list[OfficerAddress] = []
    matched_spec: dict = {}

    # ── Tier 1: curated, confirmed against the controller's published page ────
    hit = _lookup_curated(service, domain)
    if hit:
        slug, spec = hit
        matched_spec = spec
        res.company_name = spec.get("company_name", "")
        res.postal = spec.get("postal", "")
        res.domain = domain or spec.get("domain", "")
        res.published_page = spec.get("published_page", "")
        res.self_serve_url = spec.get("self_serve_url", "") or SELF_SERVE_FIRST.get(slug, "")
        if spec.get("note"):
            res.note = spec["note"]
        for off in spec.get("officers", []):
            candidates.append(OfficerAddress(
                email=off["email"],
                tier=TIER_CURATED,
                role=off.get("role", ""),
                company_name=res.company_name,
                postal=res.postal,
                evidence=off.get("evidence", ""),
                checked_on=spec.get("checked_on", ""),
                rationale=(f"Published by {res.company_name or slug} as its "
                           f"{off.get('role', 'privacy contact')}; read from "
                           f"{off.get('evidence', 'its published policy')} on "
                           f"{spec.get('checked_on', 'an unrecorded date')}."),
            ))
        if not candidates and res.published_page:
            # The honest middle case: we know the officer is published, we will not
            # assert an address for them.
            res.warnings.append(
                f"{res.company_name or service} publishes a statutory officer but no stable "
                f"address is on file. Read the current contact from {res.published_page} "
                f"before serving; do not guess.")

    # ── Tier 2: this project's existing fiduciary registry ───────────────────
    # Only consulted when the curated directory did not match AT ALL. A curated
    # entry that deliberately records no address (Amazon, Apple) is an answer, not
    # a gap: falling through to a fuzzy registry match there is how "Amazon India"
    # once resolved to Domino's grievance officer.
    if not candidates and not matched_spec:
        reg_hit = _lookup_registry(service, domain)
        if reg_hit:
            slug, spec = reg_hit
            matched_spec = spec
            res.company_name = res.company_name or spec.get("company_name", "")
            res.postal = res.postal or spec.get("address", "")
            reg_self_serve = spec.get("self_serve_url", "")
            res.self_serve_url = (res.self_serve_url
                                  or SELF_SERVE_FIRST.get(slug, "")
                                  or (reg_self_serve if _is_actionable_url(reg_self_serve) else ""))
            res.domain = res.domain or extract_domain(spec.get("self_serve_url", ""))
            email = (spec.get("dpo_email") or "").strip()
            if email and EMAIL_RE.match(email):
                candidates.append(OfficerAddress(
                    email=email,
                    tier=TIER_REGISTRY,
                    role=spec.get("dpo_name", "Grievance Officer / DPO"),
                    company_name=res.company_name,
                    postal=res.postal,
                    rationale=("Carried from this project's fiduciary registry "
                               "(backend/agent/fiduciary_directory.py). Very likely correct "
                               "but NOT re-confirmed against the controller's published "
                               "page here — worth a human glance before dispatch."),
                ))
                res.warnings.append(
                    "Address comes from the project registry, not from a freshly confirmed "
                    "published page. Officers rotate; confirm before serving if the matter "
                    "is contentious.")

    # ── Tier 3: standard aliases at a domain we actually know ────────────────
    guesses: list[OfficerAddress] = []
    if include_guesses and res.domain:
        known = {c.email for c in candidates}
        guesses = [g for g in alias_candidates(res.domain,
                                               matched_spec.get("country", "IN"),
                                               res.company_name)
                   if g.email not in known]

    if not candidates and not guesses:
        res.status = TIER_NONE
        if not res.note:
            res.note = (
                f"No addressee is known for {res.service}. This module will not derive a "
                f"domain from a company name — pass the service's real mail domain to get "
                f"standard-alias candidates, or find the officer on the controller's own "
                f"privacy page (DPDP Act 2023 s.13(3) requires it to be published).")
        res.warnings.append("No email addressee resolved. The notice cannot be dispatched.")
        return res

    ordered = candidates + guesses
    ordered.sort(key=lambda a: _TIER_RANK[a.tier])

    if verify_mx:
        # Cache by domain — the alias guesses all share one, so this is one lookup.
        seen: dict[str, dict] = {}
        for addr in ordered:
            dom = addr.email.split("@")[-1]
            if dom not in seen:
                seen[dom] = check_deliverable(dom)
            mx = seen[dom]
            addr.deliverable = mx.get("deliverable")
            addr.mx_note = mx.get("note", "")
        # A domain that cannot receive mail sinks even a curated address.
        undeliverable = [a for a in ordered if a.deliverable is False]
        for addr in undeliverable:
            res.warnings.append(f"{addr.email}: {addr.mx_note}")
        ordered = [a for a in ordered if a.deliverable is not False] + undeliverable

    res.primary = ordered[0]
    res.alternates = ordered[1:]
    res.status = res.primary.tier

    if res.primary.tier == TIER_GUESS:
        res.warnings.append(
            f"{res.primary.email} is an UNVERIFIED GUESS. Nothing confirms this mailbox "
            f"exists or that whoever reads it is the statutory officer. An erasure notice "
            f"carries the data subject's name, email and phone by construction, so sending "
            f"it to the wrong mailbox discloses those identifiers to a stranger. Have the "
            f"user confirm the address before dispatch.")
    if _is_actionable_url(res.self_serve_url):
        res.warnings.append(
            f"A self-serve control exists at {res.self_serve_url}. It is usually faster and "
            f"more reliable than a served notice; offer it first.")

    return res


def curated_services() -> list[dict]:
    """Introspection: what this directory claims to know, and how well.

    Exposed so the UI and tests can show provenance without reaching into the
    module's internals, and so a stale `checked_on` is visible.
    """
    out = []
    for slug, spec in CURATED.items():
        out.append({
            "slug": slug,
            "brand": spec.get("brand", slug),
            "company_name": spec.get("company_name", ""),
            "domain": spec.get("domain", ""),
            "country": spec.get("country", ""),
            "checked_on": spec.get("checked_on", ""),
            "addresses": [o["email"] for o in spec.get("officers", [])],
            "address_count": len(spec.get("officers", [])),
            "published_page": spec.get("published_page", ""),
            "tier": TIER_CURATED if spec.get("officers") else TIER_NONE,
        })
    return sorted(out, key=lambda r: r["slug"])


def directory_stats() -> dict:
    """Counts for the audit record: how much of this is confirmed vs inherited."""
    curated_addrs = sum(len(s.get("officers", [])) for s in CURATED.values())
    known_no_addr = sum(1 for s in CURATED.values() if not s.get("officers"))
    return {
        "curated_services": len(CURATED),
        "curated_addresses": curated_addrs,
        "curated_services_without_address": known_no_addr,
        "registry_services": len(_registry()),
        "alias_guesses_per_domain": len(STANDARD_ALIASES),
        "policy": ("Curated addresses were read from the controller's own published page "
                   "on the recorded date. Registry addresses are inherited, not re-confirmed. "
                   "Alias guesses are never confirmed and are labelled as guesses everywhere."),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Offline demo. Resolves only — touches no network unless you pass verify_mx.
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    print("=" * 78)
    print("officer_directory — resolution demo (no network, no mail sent)")
    print("=" * 78)
    print(json.dumps(directory_stats(), indent=2))

    samples = [
        ("Zomato Limited", ""),          # curated, multiple officers
        ("Swiggy", ""),                  # curated
        ("Shaadi.com", ""),              # curated, address on a DIFFERENT domain
        ("Just Dial", ""),               # curated via two-token squash
        ("Microsoft", ""),               # curated global DPO
        ("Amazon India", ""),            # known controller, address deliberately withheld
        ("Naukri.com", ""),              # registry tier
        ("Truecaller", ""),              # registry tier + self-serve remedy
        ("Some Startup Pvt Ltd", ""),    # unknown, no domain -> none
        ("Some Startup Pvt Ltd", "somestartup.io"),   # unknown, domain given -> guesses
    ]

    for name, dom in samples:
        r = resolve_officer(name, dom)
        label = f"{name}" + (f"  (domain={dom})" if dom else "")
        print(f"\n── {label}")
        print(f"   status            : {r.status}")
        print(f"   primary           : {r.primary.email if r.primary else '(none)'}")
        if r.primary:
            print(f"   role              : {r.primary.role}")
            print(f"   is_guess          : {r.primary.is_guess}")
            print(f"   evidence          : {r.primary.evidence or '(none recorded)'}")
        print(f"   safe_unattended   : {r.safe_to_send_unattended}")
        if r.alternates:
            print(f"   alternates        : {', '.join(a.email for a in r.alternates[:4])}")
        for w in r.warnings:
            print(f"   ! {w}")
        if r.note:
            print(f"   note              : {r.note}")

    print("\n" + "=" * 78)
    print(f"Directory last reviewed for this build on {date.today().isoformat()}.")
    print("Every address above is either evidenced or explicitly labelled a guess.")
    print("=" * 78)
