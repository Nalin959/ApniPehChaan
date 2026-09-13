"""
verifiers.py — Checks that actually query something and return proof.

THE RULE THIS FILE ENFORCES
---------------------------
Never assert that a source holds a person's data unless we actually checked and
something came back. Every claim carries the endpoint that was queried, when,
what the HTTP status was, and the raw evidence — so the user can re-run the
same check by hand and get the same answer.

An earlier build synthesised breach membership: it picked real breaches at
random and told the user they were in them. Labelling that "simulated" in a
JSON payload did not make it honest, because on screen it read as a finding.
It is gone.

WHAT CAN GENUINELY BE CHECKED, AND FOR FREE
-------------------------------------------
  Pwned Passwords  api.pwnedpasswords.com/range/{prefix}
                   Free, unauthenticated, k-anonymous. Real evidence that a
                   specific password appears in breach corpora.

  Gravatar         gravatar.com/avatar/{md5}?d=404
                   Free, unauthenticated. A 200 proves a public profile is
                   attached to that email address.

  HIBP breaches    haveibeenpwned.com/api/v3/breaches
                   Free catalog of breach metadata. Real facts ABOUT breaches
                   — not about whether a given person is in one.

  HIBP account     haveibeenpwned.com/api/v3/breachedaccount/{email}
                   Returns 401 without a subscription key. THE authoritative
                   answer to "is this address in a breach". Set HIBP_API_KEY
                   and it runs for real; without it we report "not checked"
                   rather than guessing.

WHAT CANNOT BE CHECKED, AND IS NOT GUESSED
------------------------------------------
  Whether Truecaller, JustDial, Naukri or any Indian people-search site holds a
  given person. None publish an API for this. Querying them by scraping, or
  probing signup/reset endpoints to enumerate accounts, would violate their
  terms and is not something this tool does. So the product asks the user
  instead — a person knows which services they signed up for, and that
  knowledge is itself valid grounds for a DPDP s.12 request.
"""

import hashlib
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

USER_AGENT = "ApniPehChaan/2.0 (privacy self-service tool)"
TIMEOUT = 15


@dataclass
class Evidence:
    """One check, one verifiable answer."""
    check: str                # machine name of the check
    target: str               # what was checked (never the raw secret)
    endpoint: str             # the exact URL queried
    queried_at: str
    http_status: int | None
    result: str               # hit | clear | unavailable | not_checked
    proof: str                # the raw evidence, quotable
    interpretation: str       # what it does and does NOT prove
    reproduce: str = ""       # a command the user can run themselves
    metadata: dict | None = None

    def to_dict(self):
        d = asdict(self)
        if d.get("metadata") is None:
            d["metadata"] = {}
        return d


def _now():
    return datetime.now(timezone.utc).isoformat()


def _get(url: str, headers: dict | None = None):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    return urllib.request.urlopen(req, timeout=TIMEOUT)


# ── 1. Pwned Passwords (free, k-anonymous, genuinely real) ───────────────────

def check_password_pwned(password: str) -> Evidence:
    """
    Real breach check for a password, using k-anonymity.

    Only the first 5 characters of the SHA-1 are transmitted. The API returns
    every suffix sharing that prefix (~800 hashes) and the match is done here,
    locally. The server therefore cannot learn which password was checked.
    """
    if not password:
        return Evidence("hibp_pwned_passwords", "(none supplied)", "", _now(), None,
                        "not_checked", "", "No password supplied.", "")

    sha1 = hashlib.sha1(password.encode()).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]
    url = f"https://api.pwnedpasswords.com/range/{prefix}"

    try:
        resp = _get(url, {"Add-Padding": "true"})
        body = resp.read().decode()
        status = resp.status
    except urllib.error.HTTPError as e:
        return Evidence("hibp_pwned_passwords", f"SHA-1 prefix {prefix}", url, _now(),
                        e.code, "unavailable", str(e),
                        "The service returned an error; nothing is claimed.", "")
    except Exception as e:
        return Evidence("hibp_pwned_passwords", f"SHA-1 prefix {prefix}", url, _now(),
                        None, "unavailable", str(e),
                        "Could not reach the service; nothing is claimed.", "")

    count = 0
    for line in body.splitlines():
        parts = line.strip().split(":")
        if len(parts) == 2 and parts[0] == suffix:
            count = int(parts[1])
            break

    reproduce = f"curl -s https://api.pwnedpasswords.com/range/{prefix} | grep -i {suffix[:12]}"

    if count:
        return Evidence(
            "hibp_pwned_passwords", f"SHA-1 prefix {prefix} (k-anonymous)", url, _now(),
            status, "hit",
            f"Hash suffix {suffix} returned with a breach count of {count:,}.",
            f"CONFIRMED: this exact password appears {count:,} times in known breach corpora. "
            f"It does not tell you which of your accounts used it — it tells you the password "
            f"itself is burned and must not be reused anywhere.",
            reproduce)

    return Evidence(
        "hibp_pwned_passwords", f"SHA-1 prefix {prefix} (k-anonymous)", url, _now(),
        status, "clear",
        f"Hash suffix {suffix} was not present among {len(body.splitlines())} returned hashes.",
        "This password does not appear in the Pwned Passwords corpus. That is not proof it is "
        "strong, only that it has not turned up in a catalogued breach.",
        reproduce)


# ── 2. Gravatar (free, real proof of a public profile) ───────────────────────

def check_gravatar(email: str) -> Evidence:
    """A 200 proves a public Gravatar profile is attached to this address."""
    if not email:
        return Evidence("gravatar", "(none supplied)", "", _now(), None,
                        "not_checked", "", "No email supplied.", "")

    md5 = hashlib.md5(email.strip().lower().encode()).hexdigest()
    url = f"https://www.gravatar.com/avatar/{md5}?d=404"
    profile_url = f"https://gravatar.com/{md5}"
    json_url = f"https://en.gravatar.com/{md5}.json"
    reproduce = f"curl -sI '{url}'"

    try:
        resp = _get(url)
        status = resp.status
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return Evidence("gravatar", email, url, _now(), 404, "clear",
                            "HTTP 404 — no avatar registered for this address hash.",
                            "No public Gravatar profile is attached to this email.", reproduce)
        return Evidence("gravatar", email, url, _now(), e.code, "unavailable", str(e),
                        "The service returned an error; nothing is claimed.", reproduce)
    except Exception as e:
        return Evidence("gravatar", email, url, _now(), None, "unavailable", str(e),
                        "Could not reach the service; nothing is claimed.", reproduce)

    meta = {}
    username = ""
    display_name = ""
    try:
        req = urllib.request.Request(json_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=4) as jresp:
            jdata = json.loads(jresp.read().decode())
            entry = (jdata.get("entry") or [{}])[0]
            username = entry.get("preferredUsername", "")
            display_name = entry.get("displayName", "")
            if entry.get("profileUrl"):
                profile_url = entry.get("profileUrl")
            meta = {
                "username": username,
                "displayName": display_name,
                "profileUrl": profile_url,
            }
    except Exception:
        meta = {"username": "", "displayName": "", "profileUrl": profile_url}

    details = []
    if username:
        details.append(f"handle: @{username}")
    if display_name:
        details.append(f"name: {display_name}")
    detail_str = f" ({', '.join(details)})" if details else ""

    return Evidence(
        "gravatar", email, url, _now(), status, "hit",
        f"HTTP {status} — active public profile{detail_str}: {profile_url}",
        f"CONFIRMED: a public Gravatar profile exists for this address and is visible to anyone "
        f"who knows it. Profile URL: {profile_url}",
        reproduce,
        metadata=meta)


# ── 3. HIBP breached account (real, requires a paid key) ─────────────────────

def check_hibp_account(email: str, api_key: str | None = None) -> Evidence:
    """
    The authoritative answer to "is this address in a known breach".

    Requires an HIBP subscription key. Without one this returns `not_checked` —
    it does NOT guess, and it does not substitute a domain heuristic for a real
    answer.
    """
    api_key = api_key or os.environ.get("HIBP_API_KEY", "")
    if not email:
        return Evidence("hibp_breached_account", "(none supplied)", "", _now(), None,
                        "not_checked", "", "No email supplied.", "")

    url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{urllib.request.quote(email)}?truncateResponse=false"
    reproduce = f"curl -s -H 'hibp-api-key: $HIBP_API_KEY' '{url}'"

    if not api_key:
        return Evidence(
            "hibp_breached_account", email, url, _now(), None, "not_checked", "",
            "NOT CHECKED. Breach membership for a specific address requires a Have I Been Pwned "
            "subscription key (about $3.95/month). Set HIBP_API_KEY to run this for real. "
            "No claim is made about this address in the meantime.",
            reproduce)

    try:
        resp = _get(url, {"hibp-api-key": api_key})
        breaches = json.loads(resp.read().decode())
        status = resp.status
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return Evidence("hibp_breached_account", email, url, _now(), 404, "clear",
                            "HTTP 404 — HIBP has no breach containing this address.",
                            "CONFIRMED CLEAR: this address does not appear in any breach "
                            "catalogued by HIBP.", reproduce)
        if e.code == 401:
            return Evidence("hibp_breached_account", email, url, _now(), 401, "unavailable",
                            "HTTP 401 — the API key was rejected.",
                            "The configured HIBP_API_KEY is invalid. Nothing is claimed.", reproduce)
        return Evidence("hibp_breached_account", email, url, _now(), e.code, "unavailable",
                        str(e), "The service returned an error; nothing is claimed.", reproduce)
    except Exception as e:
        return Evidence("hibp_breached_account", email, url, _now(), None, "unavailable",
                        str(e), "Could not reach the service; nothing is claimed.", reproduce)

    names = [b.get("Name") or b.get("Title") for b in breaches]
    return Evidence(
        "hibp_breached_account", email, url, _now(), status, "hit",
        f"HIBP returned {len(breaches)} breach record(s): {', '.join(names)}",
        f"CONFIRMED: this address appears in {len(breaches)} breach(es) catalogued by HIBP. "
        f"Each named company held this address at the time of its breach.",
        reproduce)


# ── 4. Email domain fact (real, but says nothing about the individual) ───────

def check_email_domain_breached(email: str, catalog: list[dict]) -> Evidence:
    """
    Was the domain of this address itself a breached organisation?

    This is a real fact about the DOMAIN. It is NOT evidence about the person —
    'someone@adobe.com' tells you Adobe was breached, not that this mailbox was
    in the dump. Phrased accordingly so it is never mistaken for a finding.
    """
    if not email or "@" not in email:
        return Evidence("email_domain_breached", "(none supplied)", "(local catalog)", _now(),
                        None, "not_checked", "", "No email supplied.", "")

    domain = email.split("@")[-1].lower()
    hits = [b for b in catalog if (b.get("domain") or "").lower() == domain]
    endpoint = "local copy of https://haveibeenpwned.com/api/v3/breaches"
    reproduce = (f"curl -s https://haveibeenpwned.com/api/v3/breaches "
                 f"| jq '.[] | select(.Domain==\"{domain}\")'")

    if not hits:
        return Evidence("email_domain_breached", domain, endpoint, _now(), 200, "clear",
                        f"No breach in the {len(catalog)}-record catalog has domain '{domain}'.",
                        f"The domain '{domain}' does not itself appear as a breached "
                        f"organisation. This says nothing about the individual mailbox.",
                        reproduce)

    names = [h.get("name") or h.get("title") for h in hits]
    return Evidence(
        "email_domain_breached", domain, endpoint, _now(), 200, "hit",
        f"Catalog entries with domain '{domain}': {', '.join(names)}",
        f"The organisation behind '{domain}' was breached ({', '.join(names)}). "
        f"IMPORTANT: this does not prove this particular mailbox was in the dump — it means "
        f"the operator of this domain suffered a breach. Treat it as a reason to check, "
        f"not as a finding.",
        reproduce)


def network_available() -> bool:
    try:
        _get("https://api.pwnedpasswords.com/range/00000")
        return True
    except Exception:
        return False


# ── 5. XposedOrNot breached account (real, free, no key) ─────────────────────

def check_xposedornot(email: str) -> Evidence:
    """
    Breach membership for a specific address, from a free public dataset.

    This exists because the authoritative answer — Have I Been Pwned — needs a
    paid subscription, and without one `check_hibp_account` correctly refuses to
    guess and returns `not_checked`. That left the single most important
    question in the product unanswered for anyone without a card on file.

    XposedOrNot indexes breach corpora and answers the same question for free.
    It is a different dataset, so it is reported under its own name and never
    presented as an HIBP result: agreement between them is corroboration, and
    absence here is not proof of absence there.
    """
    if not email:
        return Evidence("xposedornot_breached_account", "(none supplied)", "", _now(), None,
                        "not_checked", "", "No email supplied.", "")

    url = f"https://api.xposedornot.com/v1/breach-analytics?email={urllib.request.quote(email)}"
    reproduce = f"curl -s '{url}'"

    try:
        resp = _get(url)
        status = resp.status
        data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return Evidence("xposedornot_breached_account", email, url, _now(), 404, "clear",
                            "HTTP 404 — the address is not present in any indexed breach.",
                            "CONFIRMED CLEAR by this dataset: the address does not appear in any "
                            "breach XposedOrNot indexes. Other datasets may still hold it.",
                            reproduce)
        return Evidence("xposedornot_breached_account", email, url, _now(), e.code, "unavailable",
                        str(e), "The service returned an error; nothing is claimed.", reproduce)
    except Exception as e:
        return Evidence("xposedornot_breached_account", email, url, _now(), None, "unavailable",
                        str(e), "Could not reach the service; nothing is claimed.", reproduce)

    # A clean address comes back with an Error body saying "not found". ONLY
    # that phrasing means clear. Any other error — a rate limit, an outage — is
    # the service declining to answer, and reading it as "no breaches found"
    # would tell somebody they are clean at the exact moment the check stopped
    # working. The record would even quote the rate-limit text under the words
    # CONFIRMED CLEAR.
    err = str((data or {}).get("Error") or "") if isinstance(data, dict) else ""
    if err:
        if "not found" in err.lower():
            return Evidence("xposedornot_breached_account", email, url, _now(), status, "clear",
                            f"The service reports: {err}.",
                            "CONFIRMED CLEAR by this dataset: the address does not appear in any "
                            "breach XposedOrNot indexes. Other datasets may still hold it.",
                            reproduce)
        return Evidence("xposedornot_breached_account", email, url, _now(), status, "unavailable",
                        f"The service declined to answer: {err}.",
                        "NOT CHECKED. The service returned an error rather than a result, so "
                        "nothing is claimed either way — this is not a clean bill of health.",
                        reproduce)

    # A well-formed answer always carries the breach container. Its absence is
    # schema drift or a partial outage, not an empty result set.
    if not isinstance(data, dict) or "ExposedBreaches" not in data:
        return Evidence("xposedornot_breached_account", email, url, _now(), status, "unavailable",
                        "The response did not contain the expected breach container.",
                        "NOT CHECKED. The service answered in a shape this check does not "
                        "recognise, so nothing is claimed either way.",
                        reproduce)

    exposed = (data.get("ExposedBreaches") or {}).get("breaches_details") or []
    pastes = (data.get("ExposedPastes") or {}).get("pastes_details") or []
    if not exposed and not pastes:
        return Evidence("xposedornot_breached_account", email, url, _now(), status, "clear",
                        "The service returned no breach or paste records for this address.",
                        "CONFIRMED CLEAR by this dataset. Other datasets may still hold it.",
                        reproduce)
    if not exposed and pastes:
        # Indexed in the paste corpus but no named breach. Previously read as
        # clear, because only ExposedBreaches was ever inspected.
        return Evidence(
            "xposedornot_breached_account", email, url, _now(), status, "hit",
            f"XposedOrNot lists this address in {len(pastes)} paste dump(s).",
            "CONFIRMED: this address appears in pasted credential dumps indexed by this "
            "dataset, though not in a named corporate breach. Rotate any password reused "
            "across those accounts and turn on two-factor authentication.",
            reproduce, metadata={"pastes": pastes})

    names = [b.get("breach", "") for b in exposed if b.get("breach")]
    return Evidence(
        "xposedornot_breached_account", email, url, _now(), status, "hit",
        f"XposedOrNot lists this address in {len(names)} breach(es): {', '.join(names)}",
        "CONFIRMED: this exact address appears in the breach records named above. A breach "
        "record cannot be un-published — rotate any password reused from these services and "
        "turn on two-factor authentication.",
        reproduce,
        metadata={"breaches": exposed})


# ── 6. Infostealer-malware infection (real, free, no key) ────────────────────

def check_infostealer(email: str) -> Evidence:
    """
    Whether this address was harvested from a computer infected by info-stealer
    malware.

    This is a different and more severe exposure than a site breach. A breach
    leaks what one company held. An info-stealer infection means everything
    saved in that computer's browser — every password, cookie and session token
    — was taken at once, and the credentials are current rather than historic.

    Hudson Rock publishes a free lookup over the infection corpora their
    Cavalier product indexes. Values come back already masked at source; nothing
    here unmasks them, and no password is ever stored.
    """
    if not email:
        return Evidence("infostealer_infection", "(none supplied)", "", _now(), None,
                        "not_checked", "", "No email supplied.", "")

    url = ("https://cavalier.hudsonrock.com/api/json/v2/osint-tools/search-by-email"
           f"?email={urllib.request.quote(email)}")
    reproduce = f"curl -s '{url}'"

    try:
        resp = _get(url)
        status = resp.status
        data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return Evidence("infostealer_infection", email, url, _now(), e.code, "unavailable",
                        str(e), "The service returned an error; nothing is claimed.", reproduce)
    except Exception as e:
        return Evidence("infostealer_infection", email, url, _now(), None, "unavailable",
                        str(e), "Could not reach the service; nothing is claimed.", reproduce)

    # Same discipline: an error body is not an absence of infections.
    if not isinstance(data, dict) or ("stealers" not in data and "message" not in data):
        return Evidence("infostealer_infection", email, url, _now(), status, "unavailable",
                        f"Unexpected response shape: {str(data)[:200]}",
                        "NOT CHECKED. The service answered in a shape this check does not "
                        "recognise, so nothing is claimed either way.", reproduce)
    if isinstance(data, dict) and data.get("error"):
        return Evidence("infostealer_infection", email, url, _now(), status, "unavailable",
                        f"The service declined to answer: {data.get('error')}",
                        "NOT CHECKED. The service returned an error rather than a result, so "
                        "nothing is claimed either way — this is not a clean bill of health.",
                        reproduce)

    stealers = data.get("stealers") or []
    if not stealers:
        return Evidence("infostealer_infection", email, url, _now(), status, "clear",
                        (data or {}).get("message", "No infection associated with this address."),
                        "CONFIRMED CLEAR by this dataset: no computer known to this corpus was "
                        "infected while this address was saved on it.",
                        reproduce)

    dates = [s.get("date_compromised", "") for s in stealers if s.get("date_compromised")]
    machines = [s.get("computer_name", "?") for s in stealers]
    return Evidence(
        "infostealer_infection", email, url, _now(), status, "hit",
        f"{len(stealers)} infected machine(s) carried this address — "
        f"{', '.join(machines[:4])}; compromised {', '.join(d[:10] for d in dates[:4])}.",
        "CONFIRMED, AND THIS IS THE URGENT ONE: a computer holding this address was infected by "
        "info-stealer malware, so every credential saved in its browser was taken together — not "
        "one site's password, all of them. Change every password saved in that browser, starting "
        "with email and banking, and sign out of all sessions everywhere. Turn on two-factor "
        "authentication; a stolen session cookie can otherwise be replayed without a password.",
        reproduce,
        metadata={"stealers": stealers,
                  "total_user_services": (data or {}).get("total_user_services"),
                  "total_corporate_services": (data or {}).get("total_corporate_services")})
