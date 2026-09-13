"""
extra_sources.py — Additional free, keyless exposure checks.

Every source in this file was tested by hand before it was written in, with a
real-looking identifier AND with an invented one that cannot exist. A source
that answers the same way to both cannot tell "you are in the data" from "you
are not", so it is worthless for this product no matter how impressive its
output looks. Those are listed under REJECTED below, with the evidence.

None of these need an API key, an account, or a payment method.

=============================================================================
IMPLEMENTED — each verified to distinguish a real hit from an invented value
=============================================================================

1. Hudson Rock, by username
   cavalier.hudsonrock.com/.../search-by-username?username=
   Proves: a machine infected by info-stealer malware had this username saved
   on it. Discrimination verified: "john" -> stealers[] populated with machine
   names and dates; "zxqvwplmnbtrfghjk9928374qq" -> {"stealers":[], ...} and a
   "not associated" message. Two clearly different answers.
   Limit: a username is not a person. A common handle collides with strangers.

2. Hudson Rock, by IP
   .../search-by-ip?ip=
   Proves: this IP address appears in info-stealer logs.
   Discrimination verified: 1.1.1.1 -> one stealer record, machine "JOHN-PC",
   compromised 2020-01-29; 203.0.113.77 (reserved, cannot be routed) -> empty.
   Limit: THIS IS ABOUT AN ADDRESS, NOT A PERSON. Home IPs are dynamic and
   carrier-grade NAT shares one address among thousands. A hit here says the
   address was seen, never that this user's device was the infected one. The
   interpretation string says so, and must not be shortened in the UI.

3. Hudson Rock, by domain
   .../search-by-domain?domain=
   Proves: employees and users of a given company appear in stealer logs, and
   which of its login URLs show up most.
   Discrimination verified: infosys.com -> 46,469 records, 4,455 employees,
   real internal URLs (stsakaash.infosys.com/adfs/ls); an invented domain ->
   {"total":0,"employees":0,"users":0}. Different answers.
   Limit: free-mail domains are refused — gmail.com returns HTTP 400 "Cannot
   complete search for that domain". Only ask this about an employer or a
   service, never about the user's own mail provider.

4. LeakCheck public API                                   <- the strongest find
   leakcheck.io/api/public?check=
   Proves: the identifier appears in named breaches, and WHICH ones, with
   dates and which field types were exposed. Accepts email, phone, or
   username. A genuinely different corpus from XposedOrNot, so agreement
   between the two is corroboration.
   Discrimination verified, all three input types:
     email    test@example.com -> found:1371, sources Mathway/Bookmate/...
              invented address -> {"success": false, "error": "Not found"}
     username "john"           -> found:1000 with named sources
              invented handle  -> "Not found"
     phone    919876543210     -> found:80, sources Zacks/Paidwork/1Win
              918888777766     -> "Not found"
   Rate limit: 12 rapid requests all returned 200; no throttling observed.
   Limit on phones: placeholder numbers people type into forms (000000000000
   -> found:1000) are genuinely in the corpus. The hit is true but says
   nothing about the person. _phone_is_placeholder guards this.

5. ProxyNova COMB                       <- usable ONLY with an exact-match pass
   api.proxynova.com/comb?query=
   Proves: this exact address appears in a combo list next to a plaintext
   password. That is worse than "you were breached" — the password is public.
   THE TRAP: the API substring-matches. Querying the invented address
   "zxqvwplmnbtrfghjk9928374qq@nonexistentdomain-xyz9999.com" returned
   "count": 10000 and rows for xyz9999@eyou.com, xyz9999@mail.ru and so on —
   it had matched the fragment "xyz9999". Reporting that count would have
   invented a breach for a person who has none. So the raw count is discarded
   and only rows whose address is character-for-character the query are
   counted. Verified both ways: real address -> 20 of 20 rows exact; an
   invented address with no shared fragment -> "count": 0.
   The API returns at most 20 rows, so if all 20 come back and none are exact,
   a real match could be buried further down: that is reported as
   "unavailable", never as "clear". Passwords are masked before storage.

6. Wayback Machine CDX
   web.archive.org/cdx/search/cdx?url=...&output=json
   Proves: the Internet Archive holds a dated, still-servable copy of a page.
   This is the answer to "I deleted my profile, so it's gone" — it is not.
   Discrimination verified: github.com/torvalds -> capture rows from 2013
   onward with timestamps and HTTP status; github.com/<invented> -> "[]".
   Limit: absence means the Archive never crawled it, not that the page never
   existed.

7. GitHub, email to account
   api.github.com/search/users?q=<email>+in:email
   Proves: a public GitHub account carries this email address in its profile.
   Discrimination verified, and the match is EXACT rather than tokenised —
   which was checked specifically, because a fuzzy match here would have been
   the same trap as ProxyNova:
     torvalds@linux-foundation.org  -> total_count 1, account "libJNI", whose
                                       profile really does publish that exact
                                       address (confirmed via /users/libJNI)
     someone@linux-foundation.org   -> total_count 0   (same domain, no match)
     torvalds@example.org           -> total_count 0   (same local part)
     invented address               -> total_count 0
   Changing either half of the address kills the match, so it is not matching
   on fragments.
   Limit: the account found need not belong to the user — libJNI above is not
   Linus Torvalds. The finding is "this address is published on GitHub", not
   "you have a GitHub account".
   Rate limit: 10 searches/minute unauthenticated. A 403 here is "could not
   check" and is never downgraded to "clear".

8. XposedOrNot breach catalogue
   api.xposedornot.com/v1/breaches
   Proves: a named service the user has an account with was itself breached,
   with the date and the exact field types taken. This answers a different
   question from the others: not "are you in the dump" but "was the company
   you trusted breached at all". Catalogue is fetched once and cached.
   Limit: A BREACH OF A SERVICE IS NOT PROOF THE USER IS IN IT. The result
   is deliberately never labelled a personal hit; see the interpretation.

9. RDAP domain registration
   rdap.org/domain/<domain>
   Proves: for a user with a personal domain, what the public registration
   record exposes. Discrimination verified: example.com -> full RDAP object;
   an invented domain -> HTTP 404.

10. Certificate Transparency (crt.sh)
    crt.sh/?q=<domain>&output=json
    Proves: every TLS certificate issued for a domain is public forever,
    including subdomains that were never meant to be found.
    Discrimination verified: hudsonrock.com -> certificate records;
    an invented domain -> "[]".
    Limit: crt.sh is genuinely unreliable — 2 of 3 calls returned HTTP 502
    during testing. Retried, and a persistent 502 is "unavailable".

=============================================================================
REJECTED — tested, and could not tell a real value from an invented one
=============================================================================

  Common Crawl index (index.commoncrawl.org)
    Reachable and keyless, and it does return data for a bare domain
    (example.com -> a real WARC record). But for the thing this product
    actually needs — a page about a person — it cannot discriminate:
      github.com/torvalds                 -> 404 "No Captures found"
      github.com/<invented>               -> 404 "No Captures found"
      news.ycombinator.com/user?id=pg     -> 404 "No Captures found"
      news.ycombinator.com/user?id=<fake> -> 404 "No Captures found"
    Real and invented give the identical response, because the sites worth
    searching exclude the crawler in robots.txt. Same failure mode as
    tellows.in. Not implemented.

  XposedOrNot /v1/domain-breaches/<domain>
    HTTP 405: "Use POST /v1/domain-breaches/ with x-api-key header."
    Key-walled. Not implemented.

  XposedOrNot password endpoint (passwords.xposedornot.com/v1/pass/anon/)
    HTTP 404 for a SHA-1 prefix; it wants a different hash. Redundant anyway —
    verifiers.check_password_pwned already does this k-anonymously against
    Pwned Passwords, which is the better-known corpus. Not implemented.

  GitHub public events, for author emails
    api.github.com/users/<user>/events/public returns 30 events but every
    payload.commits[].author.email came back empty across several accounts.
    GitHub redacts them now. No signal. Not implemented.

  XposedOrNot /v1/check-email/<email>
    Works and discriminates correctly, but returns a strict subset of
    /v1/breach-analytics, which the product already calls. Redundant, so it is
    not added as a separate finding.

=============================================================================
THE THREE STATES, AND WHY THEY ARE NEVER COLLAPSED
=============================================================================
  "hit"         the source affirmatively returned this identifier
  "clear"       the source was reached, answered, and holds nothing
  "unavailable" the source errored, timed out, or rate-limited
  "not_checked" nothing was supplied to check

An HTTP 429, a 502 or a timeout is "unavailable". It is never reported as
"clear". Telling someone they are safe when the lookup never happened is the
worst thing this product could do, and it is the one bug that would not look
like a bug on screen.
"""

import json
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone

USER_AGENT = "ApniPehChaan/2.0 (privacy self-service tool)"
TIMEOUT = 20

# Seconds of backoff between crt.sh retries, multiplied by the attempt number.
CRTSH_BACKOFF_S = 0.75

# ProxyNova caps its response at 20 rows. Needed to tell "nothing matched" from
# "the page filled up before we got to a match" — see _check_proxynova.
PROXYNOVA_ROW_CAP = 20


@dataclass
class Finding:
    """One check, one verifiable answer. Mirrors verifiers.Evidence."""
    check: str
    target: str
    endpoint: str
    queried_at: str
    http_status: int | None
    result: str               # hit | clear | unavailable | not_checked
    proof: str
    interpretation: str
    reproduce: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self):
        d = asdict(self)
        if d.get("metadata") is None:
            d["metadata"] = {}
        return d


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fetch(url: str, headers: dict | None = None) -> tuple[int | None, str, str | None]:
    """
    GET a URL and always come back with something describable.

    Returns (status, body, error). An HTTPError still carries a body worth
    quoting — several of these APIs answer "not found" with a 404 and a useful
    JSON payload — so it is read rather than discarded. `error` is non-None
    only when nothing was learned at all, which is what forces "unavailable".
    """
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)
        return resp.status, resp.read().decode("utf-8", "replace"), None
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            body = ""
        return e.code, body, None
    except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
        return None, "", f"could not reach the service: {e}"
    except Exception as e:
        return None, "", f"unexpected failure: {e}"


def _unavailable(check: str, target: str, url: str, status: int | None, why: str,
                 reproduce: str) -> Finding:
    """
    The single place a failed lookup becomes a result.

    Funnelled through one function so no future edit can accidentally let an
    error path fall through to "clear".
    """
    return Finding(
        check, target, url, _now(), status, "unavailable", why,
        "COULD NOT CHECK. The source did not answer, so nothing is known either way — "
        "this is NOT a clean bill of health. Re-run the command below later.",
        reproduce)


def _declined(check: str, target: str, url: str, status: int | None, body: str,
              reproduce: str) -> Finding | None:
    """
    Guard for every source that answers with a JSON body even when it is
    refusing. `_fetch` deliberately keeps an HTTPError's body — several of these
    APIs answer "not found" with a 404 and a useful payload — but that left the
    status itself unread, so a 429 or a 502 whose body happened to parse fell
    straight through to the "clear" branch. Measured: Hudson Rock answering
    HTTP 429 {"message": "Too many requests"} was reported as CONFIRMED CLEAR,
    quoting the rate-limit text as its proof.

    Returns an `unavailable` Finding when the status is not a 200, and None
    when the caller may go on and interpret the body.
    """
    if status == 200:
        return None
    return _unavailable(
        check, target, url, status,
        f"HTTP {status}: the source answered with an error rather than a result "
        f"({(body or '')[:160]}).", reproduce)


def _not_checked(check: str, note: str) -> Finding:
    return Finding(check, "(none supplied)", "", _now(), None, "not_checked", "", note, "")


def _json(body: str):
    try:
        return json.loads(body)
    except Exception:
        return None


def _mask_password(pw: str) -> str:
    """Never store a full plaintext password lifted from a combo list."""
    if len(pw) <= 2:
        return "*" * len(pw)
    return pw[0] + "*" * (len(pw) - 2) + pw[-1]


# ── 1-3. Hudson Rock, beyond the email endpoint ──────────────────────────────
#
# The email lookup is already wired in elsewhere. These three cover the other
# identifiers the same corpus is indexed by. All share one response shape:
# a `message` that says "is not associated" when clean, and a `stealers` list
# when not — so one parser serves all three.

_HR_BASE = "https://cavalier.hudsonrock.com/api/json/v2/osint-tools"


def _hudson_rock(check: str, param: str, value: str, subject: str,
                 hit_interpretation: str, clear_interpretation: str) -> Finding:
    url = f"{_HR_BASE}/search-by-{param}?{param}={urllib.parse.quote(value)}"
    reproduce = f"curl -s '{url}'"

    status, body, err = _fetch(url)
    if err:
        return _unavailable(check, value, url, status, err, reproduce)

    data = _json(body)
    if data is None:
        # A non-JSON body means the endpoint refused the input outright — e.g.
        # the domain search answers free-mail providers with a bare 400 and the
        # text "Cannot complete search for that domain."
        return _unavailable(check, value, url, status,
                            f"HTTP {status}: {body[:200]}", reproduce)

    declined = _declined(check, value, url, status, body, reproduce)
    if declined:
        return declined

    if not isinstance(data, dict):
        return _unavailable(check, value, url, status,
                            f"The source answered in a shape this check does not "
                            f"recognise: {str(data)[:160]}", reproduce)

    stealers = data.get("stealers") or []
    if not stealers:
        return Finding(
            check, value, url, _now(), status, "clear",
            data.get("message", "No infection associated with this identifier."),
            clear_interpretation, reproduce,
            metadata={"stealers": 0})

    machines = [s.get("computer_name", "?") for s in stealers]
    dates = [str(s.get("date_compromised", ""))[:10] for s in stealers if s.get("date_compromised")]
    return Finding(
        check, value, url, _now(), status, "hit",
        f"{len(stealers)} infected machine(s) linked to this {subject} — "
        f"{', '.join(machines[:4])}; compromised {', '.join(dates[:4]) or 'date not given'}.",
        hit_interpretation, reproduce,
        metadata={"stealers": stealers[:5],
                  "stealer_count": len(stealers),
                  "total_user_services": data.get("total_user_services"),
                  "total_corporate_services": data.get("total_corporate_services")})


def check_infostealer_by_username(username: str) -> Finding:
    """Info-stealer exposure for a handle rather than an address."""
    if not username:
        return _not_checked("infostealer_username", "No username supplied.")
    return _hudson_rock(
        "infostealer_username", "username", username, "username",
        "CONFIRMED for this username: a computer infected by info-stealer malware had this "
        "handle saved on it, which means every credential in that browser was taken at once. "
        "CAUTION ON IDENTITY: a username is not a person. If this handle is a common word, the "
        "infected machine may belong to a stranger who chose the same name. Treat this as urgent "
        "only if the handle is distinctive or you recognise the machine name.",
        "CONFIRMED CLEAR by this dataset: no machine known to Hudson Rock's corpus had this "
        "username saved on it. Other stealer corpora are not covered by this answer.")


def check_infostealer_by_ip(ip: str) -> Finding:
    """
    Info-stealer exposure for an IP address.

    Kept deliberately weak in its wording. An IP is the least personal of all
    the identifiers here — dynamic allocation and carrier-grade NAT mean a hit
    routinely belongs to someone else entirely.
    """
    if not ip:
        return _not_checked("infostealer_ip", "No IP address supplied.")
    return _hudson_rock(
        "infostealer_ip", "ip", ip, "IP address",
        "THIS ADDRESS APPEARS IN STEALER LOGS — BUT THAT IS NOT THE SAME AS YOUR DEVICE. "
        "Home IP addresses are reassigned constantly and mobile carriers share one address "
        "between thousands of subscribers, so the infected machine was very likely someone "
        "else's. Use this only as a prompt to run a malware scan, never as proof of infection.",
        "CONFIRMED CLEAR by this dataset: this IP address does not appear in Hudson Rock's "
        "stealer logs. Since addresses rotate, this says little about your device either way.")


def check_employer_infostealer_exposure(domain: str) -> Finding:
    """
    Stealer exposure across a whole company — the user's employer, or a service
    they hold an account with.

    Answers a question the per-person checks cannot: whether the organisation
    holding your data is itself compromised at scale.
    """
    if not domain:
        return _not_checked("infostealer_domain", "No domain supplied.")

    domain = domain.strip().lower().lstrip("@")
    url = f"{_HR_BASE}/search-by-domain?domain={urllib.parse.quote(domain)}"
    reproduce = f"curl -s '{url}'"

    status, body, err = _fetch(url)
    if err:
        return _unavailable("infostealer_domain", domain, url, status, err, reproduce)

    data = _json(body)
    if data is None:
        # Free-mail providers are refused here by design (gmail.com -> HTTP 400).
        return _unavailable("infostealer_domain", domain, url, status,
                            f"HTTP {status}: {body[:200]} "
                            "(free email providers are not searchable by domain)", reproduce)

    declined = _declined("infostealer_domain", domain, url, status, body, reproduce)
    if declined:
        return declined

    if not isinstance(data, dict):
        return _unavailable("infostealer_domain", domain, url, status,
                            f"Unexpected response shape: {str(data)[:160]}", reproduce)

    total = data.get("total") or 0
    employees = data.get("employees") or 0
    users = data.get("users") or 0

    if total == 0:
        return Finding(
            "infostealer_domain", domain, url, _now(), status, "clear",
            "0 records associated with this domain.",
            "CONFIRMED CLEAR by this dataset: no stealer records reference this domain.",
            reproduce, metadata={"total": 0})

    urls = [u.get("url") for u in ((data.get("data") or {}).get("employees_urls") or [])][:5]
    return Finding(
        "infostealer_domain", domain, url, _now(), status, "hit",
        f"{total:,} stealer records reference {domain}: {employees:,} employee credentials and "
        f"{users:,} user credentials. Most-seen login URLs: {', '.join(u for u in urls if u) or 'none listed'}.",
        "CONFIRMED about the ORGANISATION, not about you personally. Credentials for this "
        "domain were harvested from infected machines at this scale. If you hold an account "
        "here, change that password and enable two-factor authentication. This finding does "
        "NOT say your individual account is among the records — only the per-identifier checks "
        "can say that.",
        reproduce,
        metadata={"total": total, "employees": employees, "users": users,
                  "third_parties": data.get("third_parties"), "top_urls": urls})


# ── 4. LeakCheck public API ──────────────────────────────────────────────────

# Numbers people type into forms to get past a required field. They are really
# in the corpus, so a hit on them is a true fact about the dataset and a
# meaningless fact about the user. Flagged rather than silently dropped.
_PLACEHOLDER_PHONE = re.compile(r"^(?:(\d)\1{6,})$|^(?:0*1?2345678\d*)$")


def _phone_is_placeholder(digits: str) -> bool:
    return bool(_PLACEHOLDER_PHONE.match(digits))


def _leakcheck_phone(raw: str) -> str:
    r"""
    One canonical form for an Indian mobile, whatever the user typed.

    This was `re.sub(r"\D", "", identifier)`, so the SAME number asked three
    different questions depending on formatting: "9876543210" queried
    9876543210, "+91 98765 43210" queried 919876543210, and "09876543210"
    queried 09876543210 — a string with a trunk prefix on the front that the
    corpus does not index, whose "Not found" was then reported as CONFIRMED
    CLEAR. The corpus is indexed country-code-first (verified in this module's
    header: 919876543210 -> found:80), so a recognisable Indian mobile is
    always asked about in that form. Anything else is passed through as typed.
    """
    digits = re.sub(r"\D", "", str(raw or ""))
    for prefix in ("0091", "091", "91", "0", ""):
        if prefix and not digits.startswith(prefix):
            continue
        rest = digits[len(prefix):]
        if len(rest) == 10 and rest[0] in "6789":
            return "91" + rest
    return digits


def check_leakcheck(identifier: str, kind: str = "auto") -> Finding:
    """
    Breach membership from LeakCheck's free public endpoint.

    Accepts an email, a phone number or a username, and names the breaches it
    found rather than only counting them. This is a different corpus from
    XposedOrNot, so it is reported separately: two independent datasets naming
    the same breach is much stronger evidence than either one alone.
    """
    if not identifier:
        return _not_checked("leakcheck_public", "No identifier supplied.")

    identifier = identifier.strip()
    if kind == "auto":
        if "@" in identifier:
            kind = "email"
        elif re.fullmatch(r"[\d\s+\-()]{7,20}", identifier):
            kind = "phone"
        else:
            kind = "username"

    query = _leakcheck_phone(identifier) if kind == "phone" else identifier
    url = f"https://leakcheck.io/api/public?check={urllib.parse.quote(query)}"
    reproduce = f"curl -s '{url}'"

    status, body, err = _fetch(url)
    if err:
        return _unavailable("leakcheck_public", identifier, url, status, err, reproduce)

    data = _json(body)
    if data is None:
        return _unavailable("leakcheck_public", identifier, url, status,
                            f"HTTP {status}: unparseable response {body[:200]}", reproduce)

    # A JSON array or scalar is not an answer this check can read, and calling
    # .get() on it raised AttributeError straight out of the check.
    if not isinstance(data, dict):
        return _unavailable("leakcheck_public", identifier, url, status,
                            f"The service answered in a shape this check does not "
                            f"recognise: {str(data)[:160]}", reproduce)

    if not data.get("success"):
        error = str(data.get("error", "")).lower()
        # ONLY the literal "not found" is an answer. "Invalid", "too many
        # requests" and anything else mean the lookup did not happen, and must
        # not be reported as a clean result.
        if "not found" in error:
            return Finding(
                "leakcheck_public", identifier, url, _now(), status, "clear",
                f'The service reports: {data.get("error")}.',
                "CONFIRMED CLEAR by this dataset: this identifier does not appear in any breach "
                "LeakCheck indexes. Other datasets may still hold it.",
                reproduce, metadata={"kind": kind})
        return _unavailable("leakcheck_public", identifier, url, status,
                            f'The service returned: {data.get("error")}', reproduce)

    found = data.get("found") or 0
    sources = data.get("sources") or []
    fields = data.get("fields") or []
    names = [f'{s.get("name")} ({s.get("date")})' for s in sources[:8]]

    placeholder = kind == "phone" and _phone_is_placeholder(query)
    caveat = ""
    if placeholder:
        caveat = (" NOTE: this number is a placeholder pattern that many people type into "
                  "required fields, so these records almost certainly belong to other people. "
                  "Treat this as noise, not as your exposure.")

    return Finding(
        "leakcheck_public", identifier, url, _now(), status, "hit",
        f"{found:,} record(s) across {len(sources)} named source(s): {'; '.join(names)}"
        f"{' …' if len(sources) > 8 else ''}. Field types exposed: {', '.join(fields[:12])}.",
        f"CONFIRMED by LeakCheck: this {kind} appears in the named breaches above, and the "
        f"listed field types were exposed alongside it. Each named source is a separate "
        f"incident you can cite by name in a DPDP s.12 erasure request to that company."
        f"{caveat}",
        reproduce,
        metadata={"kind": kind, "found": found, "sources": sources[:25],
                  "exposed_fields": fields, "placeholder_pattern": placeholder})


# ── 5. ProxyNova COMB ────────────────────────────────────────────────────────

def check_proxynova_credentials(email: str) -> Finding:
    """
    Plaintext password exposure in combination lists.

    Worse than breach membership: a combo-list entry means the password itself
    is circulating in the clear, not a hash someone still has to crack.

    THE WHOLE POINT OF THIS FUNCTION IS THE EXACT-MATCH PASS. The upstream API
    substring-matches, and will happily return ten thousand rows for an address
    that does not exist because some fragment of it appears in real addresses.
    Trusting its `count` would fabricate a breach. Only rows whose address is
    identical to the query are counted.
    """
    if not email or "@" not in email:
        return _not_checked("proxynova_combolist", "No email address supplied.")

    email = email.strip().lower()
    url = f"https://api.proxynova.com/comb?query={urllib.parse.quote(email)}"
    reproduce = (f"curl -s '{url}' | "
                 f"python3 -c \"import sys,json;d=json.load(sys.stdin);"
                 f"print([l for l in d['lines'] if l.split(':',1)[0].lower()=='{email}'])\"")

    status, body, err = _fetch(url)
    if err:
        return _unavailable("proxynova_combolist", email, url, status, err, reproduce)

    data = _json(body)
    if data is None:
        return _unavailable("proxynova_combolist", email, url, status,
                            f"HTTP {status}: unparseable response {body[:200]}", reproduce)

    declined = _declined("proxynova_combolist", email, url, status, body, reproduce)
    if declined:
        return declined

    if not isinstance(data, dict):
        return _unavailable("proxynova_combolist", email, url, status,
                            f"Unexpected response shape: {str(data)[:160]}", reproduce)

    lines = data.get("lines") or []
    raw_count = data.get("count") or 0

    exact = []
    for line in lines:
        addr, _, password = line.partition(":")
        if addr.strip().lower() == email:
            exact.append(password)

    if not exact:
        # The response is capped at 20 rows. If it came back full of substring
        # noise, a genuine match could be sitting on a page we never saw, so
        # this is inconclusive rather than clean.
        if len(lines) >= PROXYNOVA_ROW_CAP:
            return _unavailable(
                "proxynova_combolist", email, url, status,
                f"The API returned its maximum of {len(lines)} rows and every one was a "
                f"partial-string match on a different address, so an exact match cannot be "
                f"ruled in or out from this page of results.", reproduce)
        return Finding(
            "proxynova_combolist", email, url, _now(), status, "clear",
            f"{len(lines)} row(s) returned, none of which is this exact address "
            f"(the API's own count of {raw_count:,} counts partial-string matches on other "
            f"addresses and is not evidence about you).",
            "CONFIRMED CLEAR by this dataset: this exact address does not appear in the "
            "combination lists ProxyNova indexes. Other combo lists exist.",
            reproduce, metadata={"exact_matches": 0, "api_substring_count": raw_count})

    masked = [_mask_password(p) for p in exact[:6]]
    return Finding(
        "proxynova_combolist", email, url, _now(), status, "hit",
        f"{len(exact)} row(s) pair this exact address with a plaintext password. "
        f"Masked samples: {', '.join(masked)}.",
        "CONFIRMED, AND ACT TODAY: this address appears in a public combination list next to a "
        "password in the clear. It does not need cracking — anyone can copy it and try it "
        "everywhere you have reused it. Change that password on every site it was used, "
        "starting with email, then banking. Passwords are shown masked here on purpose; the "
        "full values are visible to anyone who runs the command below, which is the problem.",
        reproduce,
        metadata={"exact_matches": len(exact), "masked_passwords": masked,
                  "api_substring_count": raw_count})


# ── 6. Wayback Machine ───────────────────────────────────────────────────────

def check_wayback_archive(page_url: str) -> Finding:
    """
    Whether the Internet Archive holds a copy of a page about the user.

    This is the check that answers "I deleted that profile years ago". Deleting
    the original does not delete the archived copy, and the archived copy is
    served to anyone who asks. For a takedown the user needs to know it exists.
    """
    if not page_url:
        return _not_checked("wayback_archive", "No URL supplied.")

    target = page_url.strip().replace("https://", "").replace("http://", "")
    url = ("https://web.archive.org/cdx/search/cdx?url="
           f"{urllib.parse.quote(target)}&output=json&limit=20&collapse=timestamp:6")
    reproduce = f"curl -s '{url}'"

    status, body, err = _fetch(url)
    if err:
        return _unavailable("wayback_archive", target, url, status, err, reproduce)

    rows = _json(body)
    if rows is None:
        return _unavailable("wayback_archive", target, url, status,
                            f"HTTP {status}: unparseable response {body[:200]}", reproduce)

    declined = _declined("wayback_archive", target, url, status, body, reproduce)
    if declined:
        return declined

    # The CDX index answers with an array of rows. Anything else — an error
    # object, a scalar — is not an answer, and slicing it raised straight out
    # of the check (KeyError on rows[1:] for a dict body).
    if not isinstance(rows, list):
        return _unavailable("wayback_archive", target, url, status,
                            f"The index answered in a shape this check does not "
                            f"recognise: {str(rows)[:160]}", reproduce)

    # Row 0 is the column header, so captures only exist from row 1 onward.
    captures = rows[1:] if rows else []
    if not captures:
        return Finding(
            "wayback_archive", target, url, _now(), status, "clear",
            "The CDX index returned an empty result set for this URL.",
            "CONFIRMED CLEAR by this dataset: the Internet Archive holds no snapshot of this "
            "exact URL. That means it was never crawled — NOT that the page never existed.",
            reproduce, metadata={"captures": 0})

    stamps = [c[1] for c in captures if isinstance(c, list) and len(c) > 1]
    if not stamps:
        return _unavailable("wayback_archive", target, url, status,
                            "The index returned capture rows with no timestamps in them.",
                            reproduce)
    first, last = stamps[0], stamps[-1]

    def _fmt(t):
        return f"{t[0:4]}-{t[4:6]}-{t[6:8]}"

    return Finding(
        "wayback_archive", target, url, _now(), status, "hit",
        f"{len(captures)} archived snapshot(s), from {_fmt(first)} to {_fmt(last)}. "
        f"Live copy: https://web.archive.org/web/{last}/{target}",
        "CONFIRMED: a public, permanently-served copy of this page exists in the Internet "
        "Archive and is retrievable right now, whether or not the original is still online. "
        "Deleting your account at the source does NOT remove this. Removal needs a separate "
        "request to the Internet Archive at info@archive.org citing the exact URL.",
        reproduce,
        metadata={"captures": len(captures), "first": first, "last": last,
                  "snapshot_url": f"https://web.archive.org/web/{last}/{target}"})


# ── 7. GitHub, email to public account ───────────────────────────────────────

def check_github_email_exposure(email: str) -> Finding:
    """
    Whether an email address is published on a GitHub profile.

    Developers routinely expose a personal address here without realising it is
    searchable. Unauthenticated search allows 10 requests a minute; a 403 means
    the quota ran out, which is "could not check".
    """
    if not email or "@" not in email:
        return _not_checked("github_email_exposure", "No email address supplied.")

    email = email.strip()
    url = ("https://api.github.com/search/users?q="
           f"{urllib.parse.quote(email)}+in:email")
    reproduce = f"curl -s '{url}'"

    status, body, err = _fetch(url, {"Accept": "application/vnd.github+json"})
    if err:
        return _unavailable("github_email_exposure", email, url, status, err, reproduce)

    if status == 403 or status == 429:
        return _unavailable("github_email_exposure", email, url, status,
                            "GitHub rate-limited the unauthenticated search "
                            "(10 requests/minute).", reproduce)

    data = _json(body)
    if data is None or "total_count" not in (data or {}):
        return _unavailable("github_email_exposure", email, url, status,
                            f"HTTP {status}: unexpected response {body[:200]}", reproduce)

    total = data.get("total_count") or 0
    if total == 0:
        return Finding(
            "github_email_exposure", email, url, _now(), status, "clear",
            '"total_count": 0 — no public GitHub account carries this address.',
            "CONFIRMED CLEAR by this dataset: this address is not published on any GitHub "
            "profile. It could still be visible in commit metadata, which this does not cover.",
            reproduce, metadata={"total_count": 0})

    logins = [i.get("login") for i in (data.get("items") or []) if i.get("login")][:5]
    where = f' Profile: https://github.com/{logins[0]}' if logins else ""
    return Finding(
        "github_email_exposure", email, url, _now(), status, "hit",
        f'"total_count": {total} — public account(s): {", ".join(logins) or "not listed"}.{where}',
        "CONFIRMED: this email address is published in the public profile of the GitHub "
        "account(s) named above, where anyone can search it — including people building spam "
        "and phishing lists. If that account is yours, remove the address under Settings > "
        "Emails and enable 'Keep my email addresses private'. IF IT IS NOT YOURS, that is the "
        "more serious finding: someone else has put your address on their profile, which is "
        "worth reporting to GitHub.",
        reproduce, metadata={"total_count": total, "accounts": logins})


# ── 8. XposedOrNot breach catalogue ──────────────────────────────────────────

# The catalogue is a few hundred KB and identical for every user, so it is
# fetched once per process rather than once per service checked.
_BREACH_CATALOGUE: list[dict] | None = None


def _load_breach_catalogue() -> tuple[list[dict] | None, int | None, str]:
    global _BREACH_CATALOGUE
    url = "https://api.xposedornot.com/v1/breaches"
    if _BREACH_CATALOGUE is not None:
        return _BREACH_CATALOGUE, 200, ""

    status, body, err = _fetch(url)
    if err:
        return None, status, err
    if status != 200:
        return None, status, (f"HTTP {status}: the catalogue service answered with an "
                              f"error rather than a catalogue ({(body or '')[:160]}).")
    data = _json(body)
    if not isinstance(data, dict) or "exposedBreaches" not in data:
        return None, status, f"HTTP {status}: unexpected catalogue response"
    breaches = data.get("exposedBreaches") or []
    # An empty catalogue is not a catalogue. Caching it made every later service
    # check report "no entry for X among 0 catalogued breaches" under the words
    # CONFIRMED CLEAR — for the rest of the process, even after the service
    # recovered, because the cache is only ever filled once.
    if not breaches:
        return None, status, (f"HTTP {status}: the catalogue came back empty, which is "
                              f"an outage rather than a catalogue with nothing in it.")
    _BREACH_CATALOGUE = breaches
    return _BREACH_CATALOGUE, status, ""


def check_service_breach_history(service_domain: str) -> Finding:
    """
    Whether a named service the user has an account with has ever been breached.

    A deliberately different question from the rest of this file. Every other
    check asks "is this person in the data". This one asks "was this company
    breached at all", which is answerable for free and is exactly the fact a
    DPDP s.12 request needs to cite.

    The result is never phrased as a personal hit. The user having an account
    somewhere that was breached is not evidence they are in the dump, and the
    interpretation string refuses to imply otherwise.
    """
    if not service_domain:
        return _not_checked("service_breach_history", "No service domain supplied.")

    service_domain = service_domain.strip().lower().lstrip("@")
    url = "https://api.xposedornot.com/v1/breaches"
    reproduce = (f"curl -s '{url}' | python3 -c \"import sys,json;"
                 f"print([b for b in json.load(sys.stdin)['exposedBreaches'] "
                 f"if b.get('domain')=='{service_domain}'])\"")

    catalogue, status, err = _load_breach_catalogue()
    if catalogue is None:
        return _unavailable("service_breach_history", service_domain, url, status, err, reproduce)

    matches = [b for b in catalogue if (b.get("domain") or "").lower() == service_domain]
    if not matches:
        return Finding(
            "service_breach_history", service_domain, url, _now(), status, "clear",
            f"No entry for {service_domain} among {len(catalogue):,} catalogued breaches.",
            "CONFIRMED CLEAR by this dataset: XposedOrNot's catalogue records no breach of this "
            "service. Unreported and undiscovered breaches would not appear here.",
            reproduce, metadata={"catalogue_size": len(catalogue), "matches": 0})

    lines, records = [], 0
    for b in matches[:5]:
        records += b.get("exposedRecords") or 0
        lines.append(f'{b.get("breachID")} ({str(b.get("breachedDate"))[:10]}, '
                     f'{(b.get("exposedRecords") or 0):,} records, '
                     f'exposed: {", ".join((b.get("exposedData") or [])[:6])})')

    return Finding(
        "service_breach_history", service_domain, url, _now(), status, "hit",
        f"{len(matches)} catalogued breach(es) of {service_domain}: {'; '.join(lines)}.",
        "CONFIRMED ABOUT THE SERVICE — NOT ABOUT YOU. This company suffered the breach(es) "
        "listed above and the named field types were taken. This does NOT establish that your "
        "record was among them; only the per-identifier checks can do that. What it does give "
        "you is a dated, citable incident to name in a DPDP s.12 request asking this company "
        "what of yours it holds and to erase it.",
        reproduce,
        metadata={"matches": len(matches), "total_records": records,
                  "breaches": matches[:5]})


# ── 9. RDAP domain registration ──────────────────────────────────────────────

def check_domain_registration_exposure(domain: str) -> Finding:
    """
    What a personal domain's public registration record gives away.

    Only relevant to users who own a domain, but for those who do it is often
    the single largest leak of a home address and phone number, published
    deliberately and forgotten about.
    """
    if not domain:
        return _not_checked("domain_registration", "No domain supplied.")

    domain = domain.strip().lower().lstrip("@")
    url = f"https://rdap.org/domain/{urllib.parse.quote(domain)}"
    reproduce = f"curl -sL '{url}'"

    status, body, err = _fetch(url)
    if err:
        return _unavailable("domain_registration", domain, url, status, err, reproduce)

    if status == 404:
        return Finding(
            "domain_registration", domain, url, _now(), 404, "clear",
            "HTTP 404 — no registration record exists for this domain.",
            "CONFIRMED CLEAR: this domain is not registered, so it publishes nothing about you.",
            reproduce, metadata={"registered": False})

    data = _json(body)
    if data is None:
        return _unavailable("domain_registration", domain, url, status,
                            f"HTTP {status}: unparseable response {body[:200]}", reproduce)

    # Anything other than a 200 (the 404 "not registered" case is answered
    # above) is the registry declining. Reading an error body as a record with
    # no contact fields in it reported "the domain is registered but every
    # contact field is redacted" about a response that contained no record.
    declined = _declined("domain_registration", domain, url, status, body, reproduce)
    if declined:
        return declined

    if not isinstance(data, dict):
        return _unavailable("domain_registration", domain, url, status,
                            f"Unexpected response shape: {str(data)[:160]}", reproduce)

    # vCard entries are where any personal detail would sit. Most registrars
    # redact them now, so finding real values is the notable outcome.
    exposed: list[str] = []
    for ent in data.get("entities") or []:
        roles = ent.get("roles") or []
        vcard = (ent.get("vcardArray") or [None, []])[1]
        for item in vcard or []:
            if len(item) >= 4 and item[0] in ("fn", "email", "tel", "adr", "org"):
                value = item[3]
                text = " ".join(str(v) for v in value if v) if isinstance(value, list) else str(value)
                if text and "redacted" not in text.lower() and "privacy" not in text.lower():
                    exposed.append(f'{"/".join(roles) or "entity"}: {item[0]}={text}')

    if not exposed:
        return Finding(
            "domain_registration", domain, url, _now(), status, "clear",
            f'Domain is registered (handle {data.get("handle")}) but every contact field in '
            f"the RDAP record is redacted or behind a privacy service.",
            "CONFIRMED CLEAR on contact details: the domain is registered but the public record "
            "exposes no personal name, address, phone or email. This is the desired state.",
            reproduce, metadata={"registered": True, "exposed_fields": 0})

    return Finding(
        "domain_registration", domain, url, _now(), status, "hit",
        f"{len(exposed)} unredacted contact field(s) in the public RDAP record: "
        f"{'; '.join(exposed[:6])}.",
        "CONFIRMED: these personal details are published in the domain's registration record "
        "and are queryable by anyone, with no account needed. Ask your registrar to enable "
        "WHOIS/RDAP privacy — most offer it free — which replaces these values with proxies.",
        reproduce,
        metadata={"registered": True, "exposed_fields": len(exposed), "samples": exposed[:10]})


# ── 10. Certificate Transparency ─────────────────────────────────────────────

def check_certificate_transparency(domain: str, attempts: int = 3) -> Finding:
    """
    Subdomains published forever in Certificate Transparency logs.

    Every TLS certificate ever issued is logged publicly and permanently, which
    means internal-sounding hostnames a user never advertised (vpn., staging.,
    home.) are discoverable by anyone.

    crt.sh is retried because it returns HTTP 502 often — 2 of 3 calls during
    testing. A persistent 502 is reported as "unavailable", never as clean.
    """
    if not domain:
        return _not_checked("certificate_transparency", "No domain supplied.")

    domain = domain.strip().lower().lstrip("@")
    url = f"https://crt.sh/?q={urllib.parse.quote(domain)}&output=json"
    reproduce = f"curl -s '{url}'"

    status, body, err, data = None, "", None, None
    for attempt in range(attempts):
        if attempt:
            # crt.sh 502s under load. Retrying with no pause at all is three
            # requests in a few milliseconds at a service that has just said it
            # is overloaded, which makes the next answer less likely rather
            # than more. Back off between attempts.
            time.sleep(CRTSH_BACKOFF_S * attempt)
        status, body, err = _fetch(url)
        if err:
            continue
        data = _json(body)
        if data is not None:
            break

    if data is None:
        return _unavailable("certificate_transparency", domain, url, status,
                            err or f"HTTP {status}: crt.sh returned a non-JSON body "
                                   f"({body[:120]}) on {attempts} attempts.", reproduce)

    declined = _declined("certificate_transparency", domain, url, status, body, reproduce)
    if declined:
        return declined

    if not isinstance(data, list):
        return _unavailable("certificate_transparency", domain, url, status,
                            f"crt.sh answered in a shape this check does not recognise: "
                            f"{str(data)[:160]}", reproduce)

    if not data:
        return Finding(
            "certificate_transparency", domain, url, _now(), status, "clear",
            "crt.sh returned an empty array — no certificate has ever been issued for "
            "this domain.",
            "CONFIRMED CLEAR by this dataset: no TLS certificate naming this domain appears in "
            "the public Certificate Transparency logs.",
            reproduce, metadata={"certificates": 0})

    names: set[str] = set()
    for row in data:
        for name in str(row.get("name_value", "")).split("\n"):
            name = name.strip().lower()
            if name and not name.startswith("*"):
                names.add(name)

    sample = sorted(names)[:10]
    return Finding(
        "certificate_transparency", domain, url, _now(), status, "hit",
        f"{len(data):,} certificate record(s) naming {len(names)} distinct hostname(s). "
        f"Examples: {', '.join(sample)}.",
        "CONFIRMED: these hostnames are published permanently in public Certificate "
        "Transparency logs, which anyone can search. They cannot be withdrawn — a certificate, "
        "once logged, is logged forever. If any of these were meant to be private, the fix is "
        "to move them behind a wildcard certificate in future, not to try to remove the log "
        "entry. This reveals infrastructure names, not the content behind them.",
        reproduce,
        metadata={"records": len(data), "hostnames": sorted(names)[:50]})


# ── Convenience runner ───────────────────────────────────────────────────────

def run_all(email: str | None = None, username: str | None = None,
            phone: str | None = None, ip: str | None = None,
            domain: str | None = None, service_domain: str | None = None,
            profile_url: str | None = None) -> list[Finding]:
    """
    Every check that the supplied identifiers support.

    Checks whose identifier was not supplied return "not_checked" rather than
    being skipped silently, so a caller can always see what was not looked at.
    """
    out: list[Finding] = []
    out.append(check_leakcheck(email, "email") if email else _not_checked(
        "leakcheck_public", "No email supplied."))
    out.append(check_proxynova_credentials(email) if email else _not_checked(
        "proxynova_combolist", "No email supplied."))
    out.append(check_github_email_exposure(email) if email else _not_checked(
        "github_email_exposure", "No email supplied."))
    out.append(check_infostealer_by_username(username) if username else _not_checked(
        "infostealer_username", "No username supplied."))
    out.append(check_leakcheck(username, "username") if username else _not_checked(
        "leakcheck_public", "No username supplied."))
    out.append(check_leakcheck(phone, "phone") if phone else _not_checked(
        "leakcheck_public", "No phone supplied."))
    out.append(check_infostealer_by_ip(ip) if ip else _not_checked(
        "infostealer_ip", "No IP supplied."))
    out.append(check_employer_infostealer_exposure(domain) if domain else _not_checked(
        "infostealer_domain", "No domain supplied."))
    out.append(check_domain_registration_exposure(domain) if domain else _not_checked(
        "domain_registration", "No domain supplied."))
    out.append(check_certificate_transparency(domain) if domain else _not_checked(
        "certificate_transparency", "No domain supplied."))
    out.append(check_service_breach_history(service_domain) if service_domain else _not_checked(
        "service_breach_history", "No service domain supplied."))
    out.append(check_wayback_archive(profile_url) if profile_url else _not_checked(
        "wayback_archive", "No profile URL supplied."))
    return out


if __name__ == "__main__":
    # Reproducible self-test. The values below are deliberately chosen so that
    # the output demonstrates discrimination rather than just "it returned
    # something": each real identifier is paired with an invented one that
    # cannot exist, and the two must come back with different `result` values.
    import sys

    FAKE_EMAIL = "qqzzvvwwkkjjhhggffddss@qqzzvvwwkkjjhhggffddss.com"
    FAKE_USER = "qqzzvvwwkkjjhhggffddss99"

    def show(f: Finding):
        icon = {"hit": "HIT  ", "clear": "CLEAR", "unavailable": "UNAVL",
                "not_checked": "SKIP "}.get(f.result, "?????")
        print(f"[{icon}] {f.check:<28} target={f.target}")
        print(f"          http={f.http_status}  {f.endpoint[:96]}")
        if f.proof:
            print(f"          proof: {f.proof[:260]}")
        print()

    print("=" * 78)
    print("REAL IDENTIFIERS — these should produce hits")
    print("=" * 78)
    real = [
        check_leakcheck("test@example.com", "email"),
        check_proxynova_credentials("test@example.com"),
        check_infostealer_by_username("john"),
        check_leakcheck("919876543210", "phone"),
        check_github_email_exposure("torvalds@linux-foundation.org"),
        check_infostealer_by_ip("1.1.1.1"),
        check_employer_infostealer_exposure("infosys.com"),
        check_service_breach_history("adobe.com"),
        check_wayback_archive("github.com/torvalds"),
        check_domain_registration_exposure("example.com"),
        check_certificate_transparency("hudsonrock.com"),
    ]
    for f in real:
        show(f)

    print("=" * 78)
    print("INVENTED IDENTIFIERS — these MUST NOT produce hits")
    print("=" * 78)
    fake = [
        check_leakcheck(FAKE_EMAIL, "email"),
        check_proxynova_credentials(FAKE_EMAIL),
        check_infostealer_by_username(FAKE_USER),
        check_leakcheck("918888777766", "phone"),
        check_github_email_exposure(FAKE_EMAIL),
        check_infostealer_by_ip("203.0.113.77"),
        check_employer_infostealer_exposure("qqzzvvwwkkjjhhggffddss99-notreal.com"),
        check_service_breach_history("qqzzvvwwkkjjhhggffddss99-notreal.com"),
        check_wayback_archive(f"github.com/{FAKE_USER}"),
        check_domain_registration_exposure("qqzzvvwwkkjjhhggffddss99-notreal.com"),
        check_certificate_transparency("qqzzvvwwkkjjhhggffddss99-notreal.com"),
    ]
    for f in fake:
        show(f)

    print("=" * 78)
    print("DISCRIMINATION VERDICT (a source is only usable if real != invented)")
    print("=" * 78)
    bad = 0
    for r, k in zip(real, fake):
        if k.result == "hit":
            verdict = "FALSE POSITIVE — invented value reported as a hit"
            bad += 1
        elif r.result == "unavailable" or k.result == "unavailable":
            verdict = f"inconclusive this run (real={r.result}, invented={k.result})"
        elif r.result == "hit" and k.result == "clear":
            verdict = "DISCRIMINATES (real=hit, invented=clear)"
        else:
            verdict = f"real={r.result}, invented={k.result}"
        print(f"  {r.check:<28} {verdict}")

    print()
    print(f"False positives on invented identifiers: {bad}")
    sys.exit(1 if bad else 0)
