"""
web_search.py — Open-web exposure search.

WHY THIS EXISTS
---------------
account_discovery.py enumerates a fixed list of sites. That is fast and precise,
but it can only ever find what is on the list, and "where is my data online" is
not a question a list can answer. This module asks the open web instead: it puts
the identifiers that uniquely belong to one person into a search engine, then
goes and reads the pages that come back.

THE RULE THAT MAKES IT ACCURATE
-------------------------------
A search result is a claim by a search engine, not evidence. Engines match on
stemming, on synonyms, on text that has since changed, and on the snippet rather
than the page. So nothing here is reported on the strength of a result listing.

Every candidate page is FETCHED, and the identifier must appear in the page
itself, character for character, before the page is called an exposure:

    confirmed   the identifier was found in the page that was served
    unconfirmed the engine returned the page but the identifier was not in it

Only unique identifiers are searched — an email address, a phone number, a UPI
handle, a PAN, a declared username. A legal name is NEVER searched: thousands of
people share one, so every hit would be a stranger, which is precisely the
collision this tool exists to avoid.
"""

import concurrent.futures as cf
import hashlib
import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
TIMEOUT = 20              # fetching a result page, which may legitimately be slow
# Asking the search engine is a different budget. A throttling engine stalls the
# connection rather than refusing it, so the full page timeout was spent twice
# per attempt — one refused query cost 40s of waiting for an answer that was
# never coming. An engine that has not replied in this long is not going to.
SEARCH_TIMEOUT = 8
# The secondary index runs only when the primary has already refused, so it is
# not on the fast path and can be given room. It cold-starts slowly — the first
# query costs several seconds, later ones answer in about one — and an 8s budget
# cut it off mid-cold-start, turning a working fallback into a timeout.
FALLBACK_TIMEOUT = 25
MAX_RESULTS_PER_QUERY = 15
MAX_PAGES_VERIFIED = 60
THROTTLE_S = 2.5          # be a polite client of the search engine
# A throttled engine cannot answer, and an unanswered query is reported as
# "could not check" rather than "clear" — so a refusal is worth one short wait.
# It is NOT worth a long one: the honest partial answer is available
# immediately, and a scan that stalls for minutes per query to avoid saying
# "incomplete" has chosen slowness over the thing the delay was meant to buy.
# Each refused query costs at most the sum of these, and the unquoted variant
# below usually succeeds on the first pass anyway.
BLOCK_BACKOFF_S = (5,)

# Pages that will match any identifier for uninteresting reasons, or that cannot
# be verified because they render client-side.
_SKIP_HOSTS = {
    "duckduckgo.com", "google.com", "bing.com", "webcache.googleusercontent.com",
    "translate.google.com", "web.archive.org",
}

# Search results are cached on disk. Engines throttle an automated client hard,
# and a throttled search is a search that cannot answer — so the less often the
# same question is asked, the more often the tool can actually look. Re-scanning
# the same identity (a demo, a scheduled re-check) then costs no queries at all.
_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "web_cache")
CACHE_TTL_S = 6 * 60 * 60


def _cache_path(query: str) -> str:
    return os.path.join(_CACHE_DIR, hashlib.sha256(query.encode()).hexdigest()[:32] + ".json")


def _cache_get(query: str):
    try:
        path = _cache_path(query)
        if time.time() - os.path.getmtime(path) > CACHE_TTL_S:
            return None
        with open(path) as f:
            blob = json.load(f)
        return [tuple(x) for x in blob["results"]], blob["status"]
    except Exception:
        return None


def _cache_put(query: str, results, status: str):
    # Never cache a refusal: it says nothing about the query, and caching it
    # would turn one throttled minute into six hours of pretending to have
    # looked.
    if status == "blocked":
        return
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        with open(_cache_path(query), "w") as f:
            json.dump({"results": [list(r) for r in results], "status": status}, f)
    except Exception:
        pass


def _now():
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WebHit:
    query: str
    identifier: str
    identifier_type: str
    url: str
    domain: str
    title: str
    http_status: int | None
    confirmed: bool           # the identifier was found in the fetched page
    matched_text: str         # the surrounding text, as proof
    checked_at: str
    reproduce: str
    note: str = ""

    def to_dict(self):
        return asdict(self)


# ── search ──────────────────────────────────────────────────────────────────

def _ddg(query: str, endpoint: str) -> list[tuple[str, str]]:
    """Return (url, title) pairs from a DuckDuckGo HTML endpoint."""
    data = urllib.parse.urlencode({"q": query}).encode()
    req = urllib.request.Request(
        endpoint, data=data,
        headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"})
    body = urllib.request.urlopen(req, timeout=SEARCH_TIMEOUT).read(500_000).decode("utf-8", "ignore")

    out: list[tuple[str, str]] = []
    # html endpoint: <a class="result__a" href="URL">TITLE</a>
    for m in re.finditer(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', body, re.S):
        out.append((html.unescape(m.group(1)), _strip_tags(m.group(2))))
    if not out:
        # lite endpoint: plain anchors
        for m in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', body, re.S):
            out.append((html.unescape(m.group(1)), _strip_tags(m.group(2))))
    return out


def _marginalia(query: str) -> list[tuple[str, str]]:
    """
    Secondary index, used only when DuckDuckGo has refused.

    Marginalia is a small independent crawler with a free, unauthenticated JSON
    API. Its coverage is a fraction of a major engine's and it is sometimes slow
    to answer, so it is no substitute for the primary — but when the primary is
    throttling, a partial answer that can be verified beats no answer at all.
    """
    url = "https://api.marginalia.nu/public/search/" + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    body = urllib.request.urlopen(req, timeout=FALLBACK_TIMEOUT).read(400_000).decode("utf-8", "ignore")
    data = json.loads(body)
    return [(r.get("url", ""), _strip_tags(r.get("title", "")))
            for r in data.get("results", []) if r.get("url")]


def _strip_tags(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def _fallback_only(query: str) -> tuple[list[tuple[str, str]], str]:
    """Consult the secondary index alone, the primary having already refused."""
    try:
        alt = _marginalia(query.strip('"'))
    except Exception:
        alt = []
    clean = _dedupe(alt)
    if clean:
        _cache_put(query, clean, "ok")
        return clean, "ok"
    # The secondary returning nothing is not evidence of absence — its index is
    # a fraction of the web — so this stays "blocked", never "empty".
    return [], "blocked"


def _dedupe(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    clean: list[tuple[str, str]] = []
    seen: set[str] = set()
    for url, title in pairs:
        host = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
        if not host or any(host == sk or host.endswith("." + sk) for sk in _SKIP_HOSTS):
            continue
        key = url.split("#")[0]
        if key in seen:
            continue
        seen.add(key)
        clean.append((key, title))
        if len(clean) >= MAX_RESULTS_PER_QUERY:
            break
    return clean


def search_web(query: str, engine_state: dict | None = None) -> tuple[list[tuple[str, str]], str]:
    """
    Query the open web. Returns (results, status).

    status is "ok", "blocked" or "empty", and the caller MUST keep them apart.
    A rate-limited engine returns a page with no results on it, which is byte
    for byte the same shape as a genuine "nothing found". Reporting the first
    as the second would tell somebody their data is nowhere online at the exact
    moment the tool had stopped being able to look — the one failure a privacy
    scanner must never have. "Could not check" is a different answer from
    "clear", and this is where the two separate.
    """
    cached = _cache_get(query)
    if cached is not None:
        return cached

    # An exact-phrase query is throttled far more readily than a bare one, and a
    # throttled query cannot answer at all. Dropping the quotes costs nothing
    # here: the engine is only ever used to nominate pages, and every page is
    # then fetched and required to contain the identifier verbatim. A looser
    # query therefore widens what is considered without loosening what is
    # claimed — the extra results simply fail verification and are discarded.
    # Throttling is applied to the client, not to the question, so once the
    # primary has refused it will refuse every later query too — re-attempting
    # it costs a timeout apiece and buys nothing. What must NOT be skipped is
    # the secondary index: it is not throttled, and a primary refusal says
    # nothing about whether the secondary can answer THIS query. Skipping it
    # let one query the secondary happened not to cover suppress the rest of
    # the run, including queries it would have answered.
    if engine_state is not None and engine_state.get("blocked"):
        return _fallback_only(query)

    unquoted = query.strip('"')
    variants = [query] + ([unquoted] if unquoted != query else [])

    for backoff in (0,) + BLOCK_BACKOFF_S:
        if backoff:
            time.sleep(backoff)
        for variant in variants:
            results, status = _search_once(variant)
            if status != "blocked":
                _cache_put(query, results, status)
                return results, status

    if engine_state is not None:
        engine_state["blocked"] = True
    return [], "blocked"


def _search_once(query: str) -> tuple[list[tuple[str, str]], str]:
    """One pass over the endpoints. Returns (results, status); never raises."""
    blocked = False
    for endpoint in ("https://html.duckduckgo.com/html/",
                     "https://lite.duckduckgo.com/lite/"):
        try:
            hits = _ddg(query, endpoint)
        except urllib.error.HTTPError as e:
            # 202/429/403 is how DuckDuckGo throttles an automated client.
            if e.code in (202, 403, 429):
                blocked = True
            continue
        except Exception:
            continue

        clean: list[tuple[str, str]] = []
        seen: set[str] = set()
        for url, title in hits:
            host = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
            if not host or any(host == s or host.endswith("." + s) for s in _SKIP_HOSTS):
                continue
            key = url.split("#")[0]
            if key in seen:
                continue
            seen.add(key)
            clean.append((key, title))
            if len(clean) >= MAX_RESULTS_PER_QUERY:
                break
        if clean:
            return clean, "ok"

        # Every link pointed back at the engine: that is its anomaly page
        # ("please let us know: click here"), not a search with no results.
        if hits and all("duckduckgo.com" in u for u, _ in hits):
            blocked = True

    if blocked:
        # The primary refused. Ask the secondary index before giving up — it is
        # unthrottled, and anything it returns is verified on the page exactly
        # as a primary result would be, so coverage widens without the standard
        # of proof moving.
        try:
            # Quotes are a DuckDuckGo phrase operator; this index treats them as
            # literal characters and matches nothing. The identifier still has
            # to appear on the fetched page, so dropping them loosens the
            # question asked, never the answer accepted.
            alt = _marginalia(query.strip('"'))
        except Exception:
            alt = []
        clean = []
        seen = set()
        for url, title in alt:
            host = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
            if not host or any(host == sk or host.endswith("." + sk) for sk in _SKIP_HOSTS):
                continue
            key = url.split("#")[0]
            if key not in seen:
                seen.add(key)
                clean.append((key, title))
            if len(clean) >= MAX_RESULTS_PER_QUERY:
                break
        if clean:
            return clean, "ok"

    return [], ("blocked" if blocked else "empty")


# ── query construction ──────────────────────────────────────────────────────

def build_queries(profile: dict) -> list[tuple[str, str, str]]:
    """
    (query, identifier, identifier_type) for every UNIQUE identifier supplied.

    A legal name is deliberately absent — see the module docstring.
    """
    q: list[tuple[str, str, str]] = []
    seen: set[str] = set()

    def add(query: str, ident: str, kind: str):
        if query not in seen:
            seen.add(query)
            q.append((query, ident, kind))

    def split(raw) -> list[str]:
        return [x.strip() for x in re.split(r"[,\n;]+", str(raw or "")) if x.strip()]

    for addr in split(profile.get("email")) + split(profile.get("alt_emails")):
        if "@" in addr:
            add(f'"{addr.lower()}"', addr.lower(), "email")

    for raw in split(profile.get("phone")) + split(profile.get("alt_phones")):
        digits = "".join(c for c in raw if c.isdigit())[-10:]
        if len(digits) == 10:
            add(f'"{digits}"', digits, "phone")
            add(f'"+91{digits}"', digits, "phone")

    for upi in split(profile.get("upi_id")):
        if "@" in upi:
            add(f'"{upi.lower()}"', upi.lower(), "upi")

    for pan in split(profile.get("pan")):
        if len(pan) == 10:
            add(f'"{pan.upper()}"', pan.upper(), "pan")

    # Declared handles only. A handle the user claims is a thing they assert
    # ownership of; one we invented is not, and searching it finds strangers.
    for entry in split(profile.get("known_usernames")):
        handle = entry.split(":", 1)[1] if ":" in entry else entry
        if 3 <= len(handle) <= 39:
            add(f'"{handle}"', handle, "username")

    return q


# ── verification ────────────────────────────────────────────────────────────

def _normalise(s: str) -> str:
    return re.sub(r"[^a-z0-9@.]+", "", s.lower())


def verify_page(url: str, identifier: str, kind: str) -> tuple[bool, str, int | None, str]:
    """
    Fetch the page and look for the identifier in it.

    Returns (confirmed, matched_context, http_status, title).
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)
        status = resp.status
        raw = resp.read(400_000).decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return False, "", e.code, ""
    except Exception:
        return False, "", None, ""

    title_m = re.search(r"<title[^>]*>(.*?)</title>", raw, re.S | re.I)
    title = _strip_tags(title_m.group(1))[:200] if title_m else ""

    text = _strip_tags(re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw))

    # A phone number is written a dozen ways — 98765 43210, +91-9876543210,
    # (98765) 43210 — so it is compared on digits. But it must be compared
    # against each DIGIT RUN separately, never against every digit on the page
    # joined together: concatenating "Order 1234567" and "Invoice 8909876"
    # manufactures the substring 9876543210, a number that appears nowhere.
    # A run matches only if it IS the number, or is the number behind a country
    # or trunk prefix. A longer run is a different number that merely contains
    # these ten digits.
    if kind == "phone":
        # Candidate runs may contain the separators people actually type, so
        # "98765 43210" and "+91-98765-43210" are read as one number. The digit
        # count is then capped at 13: that cap is what stops a row of unrelated
        # figures ("1234567 8909876 543210") from merging into a single run long
        # enough to contain these ten digits by accident.
        for m in re.finditer(r"(?<![\d])\+?\d[\d\s\-().]{6,20}\d(?![\d])", text):
            digits = re.sub(r"\D", "", m.group(0))
            if len(digits) > 13:
                continue
            if digits == identifier or (
                    digits.endswith(identifier)
                    and digits[:-len(identifier)] in ("0", "91", "091", "0091")):
                i = m.start()
                return True, "…" + text[max(0, i - 60):i + len(m.group(0)) + 60].replace("\n", " ") + "…", status, title
        return False, "", status, title

    hay, needle = text.lower(), identifier.lower()
    i = hay.find(needle)
    if i >= 0:
        return True, "…" + text[max(0, i - 90):i + len(identifier) + 90].replace("\n", " ") + "…", status, title

    # Fall back to a punctuation-insensitive comparison.
    if _normalise(identifier) and _normalise(identifier) in _normalise(text):
        return True, "(matched ignoring punctuation and spacing)", status, title
    return False, "", status, title


def search_exposures(profile: dict, max_workers: int = 16,
                     max_pages: int = MAX_PAGES_VERIFIED) -> dict:
    """
    Search the open web for this identity, then prove or discard every result.
    """
    queries = build_queries(profile)
    if not queries:
        return {"queries": [], "confirmed": [], "unconfirmed": [], "searched": 0,
                "pages_fetched": 0,
                "note": ("No unique identifier was supplied. An open-web search needs "
                         "something that belongs to exactly one person — an email address, "
                         "a phone number, a UPI ID, a PAN or a handle you claim. A name is "
                         "shared by thousands and is never searched.")}

    # 1. Ask the web, remembering which queries the engine actually answered.
    found: list[tuple[str, str, str, str, str]] = []   # query, ident, kind, url, title
    blocked_queries: list[str] = []
    answered = 0
    engine_state: dict = {"blocked": False}
    for query, ident, kind in queries:
        results, status = search_web(query, engine_state)
        if status == "blocked":
            blocked_queries.append(query)
        else:
            answered += 1
        for url, title in results:
            found.append((query, ident, kind, url, title))
        if not engine_state["blocked"]:
            time.sleep(THROTTLE_S)

    # One page can answer for only one identifier; keep the first pairing.
    seen: set[tuple[str, str]] = set()
    todo: list[tuple[str, str, str, str, str]] = []
    for item in found:
        key = (item[3], item[1])
        if key not in seen:
            seen.add(key)
            todo.append(item)
    todo = todo[:max_pages]

    # 2. Go and read every page. The engine's claim is not evidence.
    def _one(item):
        query, ident, kind, url, title = item
        ok, ctx, status, page_title = verify_page(url, ident, kind)
        domain = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
        return WebHit(
            query=query, identifier=ident, identifier_type=kind, url=url, domain=domain,
            title=page_title or title, http_status=status, confirmed=ok,
            matched_text=ctx, checked_at=_now(),
            reproduce=f"curl -s -A '{UA[:24]}...' '{url}' | grep -i '{ident}'",
            note=("" if ok else
                  "The search engine returned this page, but the identifier was not present "
                  "in the HTML that was served. It may be rendered by JavaScript, behind a "
                  "login, or already removed — so nothing is claimed."))

    hits: list[WebHit] = []
    with cf.ThreadPoolExecutor(max_workers) as ex:
        hits.extend(ex.map(_one, todo))

    # A username is not a unique identifier. Finding the string "nalinchamp" on
    # a page proves the string is there, not that it refers to this person —
    # handles are reused by strangers across unrelated sites. So a username hit
    # is only promoted to a finding when the SAME page also carries an
    # identifier that belongs to exactly one person. Otherwise it is a lead the
    # user is asked to confirm, exactly as an unmatched alert would be.
    UNIQUE = {"email", "phone", "upi", "pan"}
    unique_pages = {h.url for h in hits if h.confirmed and h.identifier_type in UNIQUE}
    for h in hits:
        if h.confirmed and h.identifier_type == "username" and h.url not in unique_pages:
            h.confirmed = False
            h.note = ("The handle appears on this page, but nothing that belongs to only you "
                      "does. Usernames are reused by unrelated people, so this is shown for "
                      "your confirmation and is not counted as your data.")

    confirmed = [h.to_dict() for h in hits if h.confirmed]
    unconfirmed = [h.to_dict() for h in hits if not h.confirmed]
    return {
        "queries": [{"query": q, "identifier": i, "type": k} for q, i, k in queries],
        "searched": len(queries),
        "answered": answered,
        "blocked_queries": blocked_queries,
        # True when the engine refused some query. The caller must then say the
        # web could not be checked, NOT that nothing was found.
        "search_degraded": bool(blocked_queries),
        "complete": not blocked_queries,
        "pages_fetched": len(hits),
        "confirmed": confirmed,
        "unconfirmed": unconfirmed,
        "domains": sorted({h["domain"] for h in confirmed}),
        "coverage_note": (
            f"{len(blocked_queries)} of {len(queries)} search(es) were refused by the "
            f"search engine (rate limiting), so the open web was only partly checked. "
            f"A clean result here does NOT mean your data is absent — re-run to complete it."
            if blocked_queries else
            f"All {len(queries)} search(es) completed."),
        "method": ("Each unique identifier is searched as an exact phrase on the open web. "
                   "Every page returned is then fetched and the identifier must appear in it "
                   "verbatim before anything is reported — a search result on its own is "
                   "treated as a lead, never as a finding. Legal names are never searched."),
    }
