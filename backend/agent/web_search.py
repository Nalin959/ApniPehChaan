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
import ipaddress
import json
import os
import queue
import re
import shlex
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
TIMEOUT = 20              # fetching a result page, which may legitimately be slow
# Asking the search engine is a different budget, and a MEASURED one. A
# throttled DuckDuckGo does not refuse the connection: it holds it open for
# exactly as long as the client is willing to wait and then serves a 202
# "anomaly" page. Measured on this machine: a request given 15s answered in
# 15.4s, and the same request given 30s answered in 30.3s — four times over,
# on both endpoints. The wait is therefore pure loss: whatever budget is set
# here is what a refusal costs, and nothing is learned by setting it higher.
SEARCH_TIMEOUT = 6
# The secondary index cold-starts slowly and its tail is long: measured 0.73s
# when it answered and 30.5s when it did not. Since it is consulted on the
# failure path — once per refused query — that tail was most of the stall. It
# keeps room for a cold start and no more; a slower answer is reported as
# "could not check", never as "nothing found".
FALLBACK_TIMEOUT = 8
MAX_RESULTS_PER_QUERY = 15
MAX_PAGES_VERIFIED = 60
# The engines are asked together, so the slowest one would otherwise set the
# pace for every query. Once the first engine has come back with something
# usable the rest are given this long to add to it, and then the query moves on.
# Measured on this machine: Bing's feed answers in 0.38-0.60s and Seznam in
# 0.73-1.09s, so this window is wide enough for both to land and narrow enough
# that a stalled engine cannot hold a query open for the full search budget.
MERGE_WINDOW_S = 1.5
# Queries are no longer run one after another (see search_exposures): waiting
# out one engine's silence before asking the next question is where a refused
# scan spent its minutes. THROTTLE_S is now a floor on the OUTBOUND RATE rather
# than a sleep in the loop — at most one query leaves this process every
# THROTTLE_S, however many are in flight — so politeness is preserved while the
# waiting overlaps instead of accumulating.
THROTTLE_S = 0.5
SEARCH_WORKERS = 6        # queries in flight at once, rate-limited by THROTTLE_S
# Retrying a refusal was measured to buy nothing. DuckDuckGo's throttle here is
# applied to the client and it is persistent — every probe over a ten-minute
# window was refused, each one stalling the full budget — so a backoff-and-retry
# pass costs the sleep plus another full round of timeouts to rediscover the
# same block. The honest partial answer ("could not check") is available
# immediately, and the on-disk cache means a re-run resumes rather than repeats.
# Kept as a knob: set it to (5,) to restore one retry pass.
BLOCK_BACKOFF_S = ()

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
# A SECOND, much longer window, used for one narrow purpose: when every engine
# has refused a query, yesterday's result list is still a perfectly good list of
# PAGES TO GO AND READ. Nothing is claimed on the strength of it — every page is
# fetched and required to contain the identifier right now, exactly as a live
# result would be — so a stale lead can only ever produce a fresh, verified
# finding. The query itself is still reported as refused, because it was: a
# stale list is not a search, and it must never turn into "the web is clean".
STALE_TTL_S = 24 * 60 * 60


def _cache_path(query: str) -> str:
    return os.path.join(_CACHE_DIR, hashlib.sha256(query.encode()).hexdigest()[:32] + ".json")


def _cache_get(query: str, ttl: float = CACHE_TTL_S):
    try:
        path = _cache_path(query)
        if time.time() - os.path.getmtime(path) > ttl:
            return None
        with open(path) as f:
            blob = json.load(f)
        return [tuple(x) for x in blob["results"]], blob["status"]
    except Exception:
        return None


def _stale_leads(query: str) -> list[tuple[str, str]]:
    """Pages a previous run found for this query, for verification only."""
    stale = _cache_get(query, STALE_TTL_S)
    return list(stale[0]) if stale and stale[0] else []


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
    # "checked" | "gone" | "unchecked" — see check_page. `confirmed is False`
    # means something different in each case, and the difference is the whole
    # reason this field exists: only "checked" licenses the word "clear".
    check_state: str = "checked"

    def to_dict(self):
        return asdict(self)


# ── search ────────────────────────────────────────────────────────────
#
# THE ENGINE LAYER IS A LIST, NOT A NAME
# --------------------------------------
# This module used to be DuckDuckGo plus one fallback, and when DuckDuckGo
# started refusing this machine there was nowhere else to go: measured, every
# probe over a ten-minute window came back 202 "anomaly", so every query in a
# scan was reported as refused and the open web went unchecked.
#
# The engines are now a registry. Each one declares how it is asked, how its
# answer is parsed, whether it needs a key, and — the part that matters for
# correctness — whether its silence may be believed. Adding an engine is one
# entry; a user who obtains one free API key gets a better index without
# touching any code, and a user with no keys at all still gets everything the
# keyless engines can do.
#
# MEASURED FROM THIS MACHINE (2026-09-13), which is why the list looks like it
# does:
#   duckduckgo html/lite  202 anomaly on every probe, every entry point,
#                         including the vqd JSON path — throttled, kept because
#                         the throttle is per-client and will lift
#   seznam.cz             200 in 0.73-1.09s, 15/15 under a burst, real results
#                         AND a real no-results page — the new workhorse
#   bing.com &format=rss  200 in 0.38-0.60s, 15/15 under a burst, genuine
#                         people-search coverage, but it answers an unmatched
#                         query with unrelated filler rather than with nothing
#   marginalia            timing out on this machine today (12.5s), kept
#   mojeek                403 after the first request; searx instances 403/429
#                         or a JS anti-bot page; yep/qwant 403; startpage,
#                         ecosia, brave-web, rightdao, stract all refused
#
# "authoritative" is the whole safety property. An engine is authoritative only
# if a genuine empty answer is DISTINGUISHABLE from a refusal — i.e. it serves a
# recognisable "no results" page. Only an authoritative engine may turn a query
# into "nothing found". Everything else can nominate pages and nothing more, so
# no amount of silence from a small index or a filler-serving feed can ever add
# up to "your data is not out there".


@dataclass(frozen=True)
class _Engine:
    name: str
    label: str
    url: str = ""
    # May a parsed, result-free answer from this engine be reported as
    # "searched, found nothing"? False for any engine whose empty answer cannot
    # be told apart from a refusal.
    authoritative: bool = False
    # Environment variables that must all be non-empty for this engine to be
    # used. Empty for the keyless ones. A missing key is not an error and is
    # never reported as a failed search — the engine is simply not consulted.
    env_keys: tuple[str, ...] = ()

    def available(self) -> bool:
        return all(os.environ.get(k) for k in self.env_keys)


# Keyless engines, always consulted. The name is historical — these are the
# endpoints _search_once asks directly — and is kept because the test suite
# stubs the seam by that name.
_ENDPOINTS = (
    _Engine("ddg_html", "DuckDuckGo", "https://html.duckduckgo.com/html/", authoritative=True),
    _Engine("ddg_lite", "DuckDuckGo Lite", "https://lite.duckduckgo.com/lite/", authoritative=True),
    _Engine("seznam", "Seznam", "https://search.seznam.cz/", authoritative=True),
    # NOT authoritative, and the reason is measured rather than cautious. Asked
    # for a string it has no match for, this feed does not return an empty
    # channel — it returns ten unrelated pages. '"webmaster@w3.org"' and
    # '"ABCPD1234E"' came back with the SAME ten Microsoft support pages. An
    # engine that cannot say "nothing" must never be allowed to mean it.
    _Engine("bing_rss", "Bing", "https://www.bing.com/search", authoritative=False),
)

# Engines behind a free API key. Each was probed without a key from this machine
# and answered with a proper authentication error, so the request shapes below
# are known to reach the right endpoint: Brave 422 (missing token), Serper 403
# ("Sign up for a free account"), Tavily 401, Google 403 (unregistered caller).
# Absent the key the engine is skipped silently and the keyless list above is
# exactly what runs — which is today's behaviour, unchanged.
_KEYED_ENGINES = (
    _Engine("brave", "Brave Search API", "https://api.search.brave.com/res/v1/web/search",
            authoritative=True, env_keys=("BRAVE_SEARCH_API_KEY",)),
    _Engine("serper", "Serper (Google)", "https://google.serper.dev/search",
            authoritative=True, env_keys=("SERPER_API_KEY",)),
    _Engine("google_cse", "Google Programmable Search",
            "https://www.googleapis.com/customsearch/v1",
            authoritative=True, env_keys=("GOOGLE_CSE_KEY", "GOOGLE_CSE_CX")),
    # An answer synthesiser over a search index rather than an index, so its
    # "no results" is not a statement about the web.
    _Engine("tavily", "Tavily", "https://api.tavily.com/search",
            authoritative=False, env_keys=("TAVILY_API_KEY",)),
)


def _active_engines() -> tuple[_Engine, ...]:
    """The engines that can be asked right now, keyless ones first."""
    return _ENDPOINTS + tuple(e for e in _KEYED_ENGINES if e.available())


def engine_status() -> list[dict]:
    """What the engine layer is made of — for diagnostics and the UI."""
    return [{"name": e.name, "label": e.label, "authoritative": e.authoritative,
             "needs_key": list(e.env_keys), "available": e.available()}
            for e in _ENDPOINTS + _KEYED_ENGINES]


class _Refused(Exception):
    """
    The engine declined to search.

    Deliberately distinct from searching and finding nothing. Everything in
    this module hangs off that distinction, so it is given a name rather than
    inferred from an empty list.
    """


class _Pacer:
    """
    A floor on the outbound query rate, shared across threads.

    Queries now overlap, so politeness can no longer be a sleep in the caller's
    loop. This hands out send slots THROTTLE_S apart: the waiting still
    happens, but alongside other queries' network time instead of on top of it.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self) -> None:
        interval = THROTTLE_S
        if interval <= 0:
            return
        with self._lock:
            due = max(time.monotonic(), self._next)
            self._next = due + interval
        delay = due - time.monotonic()
        if delay > 0:
            time.sleep(delay)


_PACER = _Pacer()
_local = threading.local()


def _race(tasks, budget: float):
    """
    Run tasks in parallel, yielding (result, error) as each finishes, and give
    the whole group at most `budget` seconds.

    The threads are daemons on purpose. The caller returns the moment it has an
    answer it can use, and a thread still waiting out a throttled engine must
    not then hold the process open behind it.
    """
    out: queue.Queue = queue.Queue()
    for task in tasks:
        def run(task=task):
            try:
                out.put((task(), None))
            except BaseException as exc:            # reported, never raised here
                out.put((None, exc))
        threading.Thread(target=run, daemon=True).start()

    deadline = time.monotonic() + budget
    for _ in tasks:
        try:
            yield out.get(timeout=max(0.0, deadline - time.monotonic()))
        except queue.Empty:
            return


def _http(url: str, *, data: bytes | None = None, headers: dict | None = None,
          timeout: float = SEARCH_TIMEOUT) -> tuple[int, str]:
    """One request to an engine. Returns (status, body); raises _Refused."""
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return getattr(resp, "status", getattr(resp, "code", 200)), \
            resp.read(500_000).decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        raise _Refused(f"{url} answered HTTP {e.code}") from e


def _ddg(query: str, endpoint) -> list[tuple[str, str]]:
    """
    Ask ONE engine and return the (url, title) pairs it nominated.

    Raises _Refused when the engine declined rather than searched. Telling
    those apart is this function's real job. A throttled DuckDuckGo answers
    202 with an ordinary-looking body, and urlopen does not raise on a 2xx — so
    the refusal has to be read off the response. Missing that read it as a page
    with no results on it, which is the one mistake this module cannot make.

    Every engine in the registry is asked through here, and the name is kept
    from when there was only one of them. That is deliberate rather than
    laziness: this is the single seam the offline test suite replaces, and a
    second, separately-named door would let a live network call slip into a test
    that believes it has stubbed the network out.
    """
    if isinstance(endpoint, str):                 # a bare DuckDuckGo URL
        endpoint = _Engine("ddg", "DuckDuckGo", endpoint, authoritative=True)
    handler = _PARSERS.get(endpoint.name) or _engine_ddg
    return handler(query, endpoint)


def _engine_ddg(query: str, engine: _Engine) -> list[tuple[str, str]]:
    """DuckDuckGo's scraped HTML endpoints."""
    status, body = _http(engine.url,
                         data=urllib.parse.urlencode({"q": query}).encode(),
                         headers={"Content-Type": "application/x-www-form-urlencoded"})
    if status in (202, 403, 429):
        raise _Refused(f"{engine.url} answered HTTP {status}")

    out: list[tuple[str, str]] = []
    # html endpoint: <a class="result__a" href="URL">TITLE</a>
    for m in re.finditer(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', body, re.S):
        out.append((html.unescape(m.group(1)), _strip_tags(m.group(2))))
    if not out:
        # lite endpoint: plain anchors
        for m in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', body, re.S):
            out.append((html.unescape(m.group(1)), _strip_tags(m.group(2))))

    # Every link pointing back at the engine is its anomaly page ("please let
    # us know: click here"), not a search with no results on it.
    if out and all("duckduckgo.com" in u for u, _ in out):
        raise _Refused(f"{engine.url} served its anomaly page")
    return out


def _engine_seznam(query: str, engine: _Engine) -> list[tuple[str, str]]:
    """
    Seznam's public result page.

    An independent European crawler that still answers an automated client:
    measured 15 requests in a row, all 200, 0.73-1.09s each, no throttling.

    It is treated as authoritative because its two answers are distinguishable.
    Every Seznam result page — including the one for a string that matches
    nothing — carries its `data-e-a` instrumentation attributes, and results are
    the anchors marked `data-e-a="heading"`. So a page with the attributes and
    no headings is a real "nothing found", while a page without them is not a
    result page at all and is refused rather than believed.
    """
    status, body = _http(engine.url + "?q=" + urllib.parse.quote(query))
    if status != 200 or "data-e-a=" not in body:
        raise _Refused(f"{engine.url} did not serve a result page (HTTP {status})")
    out: list[tuple[str, str]] = []
    for pat in (r'<a[^>]+data-e-a="heading"[^>]*?href="(https?://[^"]+)"[^>]*>(.*?)</a>',
                r'<a[^>]+href="(https?://[^"]+)"[^>]*?data-e-a="heading"[^>]*>(.*?)</a>'):
        for m in re.finditer(pat, body, re.S):
            out.append((html.unescape(m.group(1)), _strip_tags(m.group(2))))
        if out:
            break
    return out


def _engine_bing_rss(query: str, engine: _Engine) -> list[tuple[str, str]]:
    """
    Bing's RSS output — the one Bing entry point that is still parseable.

    Worth having: it is the only free engine reached from this machine with
    consumer people-search coverage. '"+919876543210"' came back with
    truecaller, tellows, telspy and spamcallcheck pages for that exact number,
    which is precisely the kind of exposure this tool exists to find and which
    the small independent indexes have no sight of at all.

    Two things had to be got right.

    `mkt=en-US` is load-bearing. Without it the feed guesses a market from the
    caller's address and answers a perfectly good query with pages from another
    country in another language — the same query returned Korean, Italian and
    Japanese filler on consecutive probes. With it, '"psf@python.org"' returns
    python.org.

    And it never says "nothing". Asked for a string it cannot match it returns
    ten unrelated popular pages rather than an empty channel — measured,
    '"webmaster@w3.org"' and '"ABCPD1234E"' returned the identical ten pages.
    That is a refusal wearing a result page's clothes, exactly like DuckDuckGo's
    anomaly page, and it is refused here on the same grounds: if not one result
    so much as mentions the thing that was asked about, this engine did not
    answer the question. Results that do pass are still only leads — every page
    is fetched and must contain the identifier before anything is reported.
    """
    status, body = _http(engine.url + "?q=" + urllib.parse.quote(query) + "&format=rss&mkt=en-US")
    if status != 200 or "<rss" not in body[:200]:
        raise _Refused(f"{engine.url} did not serve its feed (HTTP {status})")

    ident = query.strip('"')
    hits, filler = [], []
    for item in re.findall(r"<item>(.*?)</item>", body, re.S):
        def tag(name, _item=item):
            m = re.search(rf"<{name}>(.*?)</{name}>", _item, re.S)
            return html.unescape(m.group(1)).strip() if m else ""
        url, title, desc = tag("link"), _strip_tags(tag("title")), _strip_tags(tag("description"))
        if not url.startswith("http"):
            continue
        (hits if _mentions(ident, f"{url} {title} {desc}") else filler).append((url, title))
    if not hits:
        raise _Refused(f"{engine.url} answered with results unrelated to the query")
    return hits + filler


def _engine_brave(query: str, engine: _Engine) -> list[tuple[str, str]]:
    status, body = _http(
        engine.url + "?q=" + urllib.parse.quote(query) + "&count=20",
        headers={"Accept": "application/json",
                 "X-Subscription-Token": os.environ.get("BRAVE_SEARCH_API_KEY", "")})
    if status != 200:
        raise _Refused(f"{engine.url} answered HTTP {status}")
    data = json.loads(body)
    return [(r["url"], _strip_tags(r.get("title", "")))
            for r in data.get("web", {}).get("results", []) if r.get("url")]


def _engine_serper(query: str, engine: _Engine) -> list[tuple[str, str]]:
    status, body = _http(
        engine.url, data=json.dumps({"q": query, "num": 20}).encode(),
        headers={"Content-Type": "application/json",
                 "X-API-KEY": os.environ.get("SERPER_API_KEY", "")})
    if status != 200:
        raise _Refused(f"{engine.url} answered HTTP {status}")
    data = json.loads(body)
    return [(r["link"], _strip_tags(r.get("title", "")))
            for r in data.get("organic", []) if r.get("link")]


def _engine_google_cse(query: str, engine: _Engine) -> list[tuple[str, str]]:
    status, body = _http(engine.url + "?" + urllib.parse.urlencode({
        "key": os.environ.get("GOOGLE_CSE_KEY", ""),
        "cx": os.environ.get("GOOGLE_CSE_CX", ""),
        "q": query, "num": 10}), headers={"Accept": "application/json"})
    if status != 200:
        raise _Refused(f"{engine.url} answered HTTP {status}")
    data = json.loads(body)
    # Google reports "no match" by omitting `items` entirely, which is a real
    # empty answer and not a refusal — so an absent list is returned as one.
    return [(r["link"], _strip_tags(r.get("title", "")))
            for r in data.get("items", []) if r.get("link")]


def _engine_tavily(query: str, engine: _Engine) -> list[tuple[str, str]]:
    key = os.environ.get("TAVILY_API_KEY", "")
    status, body = _http(
        engine.url,
        data=json.dumps({"query": query, "api_key": key, "max_results": 20}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    if status != 200:
        raise _Refused(f"{engine.url} answered HTTP {status}")
    data = json.loads(body)
    return [(r["url"], _strip_tags(r.get("title", "")))
            for r in data.get("results", []) if r.get("url")]


_PARSERS = {
    "ddg_html": _engine_ddg, "ddg_lite": _engine_ddg,
    "seznam": _engine_seznam, "bing_rss": _engine_bing_rss,
    "brave": _engine_brave, "serper": _engine_serper,
    "google_cse": _engine_google_cse, "tavily": _engine_tavily,
}


def _mentions(ident: str, blob: str) -> bool:
    """
    Does this text so much as refer to the identifier?

    Used to tell an engine's answer from its filler, and to decide which pages
    are worth a fetch first. It is NEVER a standard of proof — passing this only
    earns a page the right to be downloaded and searched properly.
    """
    digits = re.sub(r"\D", "", ident)
    if len(digits) >= 8 and digits in re.sub(r"\D", "", blob):
        return True
    norm = _normalise(ident)
    return bool(norm) and norm in _normalise(blob)


def _marginalia(query: str) -> list[tuple[str, str]]:
    """
    Secondary index, used when DuckDuckGo has refused.

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


def _secondary(query: str) -> list[tuple[str, str]]:
    """
    Ask the secondary index. Never raises; returns [] when it cannot answer.

    Quotes are a DuckDuckGo phrase operator, and this index takes them as
    literal characters and matches nothing, so they are dropped. The identifier
    still has to appear on the fetched page, so that loosens the question
    asked, never the answer accepted.

    Asked at most once per query per search_web() call. Both query variants
    strip to the same secondary query, so without this memo one refused query
    paid this index's timeout twice over for an answer that cannot differ.
    """
    q = query.strip('"')
    memo = getattr(_local, "secondary", None)
    if memo is not None and q in memo:
        return memo[q]
    try:
        out = _marginalia(q)
    except Exception:
        out = []
    if memo is not None:
        memo[q] = out
    return out


def _strip_tags(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def _fallback_only(query: str) -> tuple[list[tuple[str, str]], str]:
    """Consult the secondary index alone, the primary having already refused."""
    clean = _dedupe(_secondary(query), query.strip('"'))
    if clean:
        _cache_put(query, clean, "ok")
        return clean, "ok"
    # The secondary returning nothing is not evidence of absence — its index is
    # a fraction of the web — so this stays "blocked", never "empty". What CAN
    # be salvaged is a previous run's list of pages: they are re-fetched and
    # re-checked from scratch, and the query is still counted as refused.
    return _stale_leads(query), "blocked"


def _dedupe(pairs: list[tuple[str, str]], ident: str = "") -> list[tuple[str, str]]:
    """
    Drop duplicates and useless hosts, and put the most promising pages first.

    The ordering matters because there is a cap on how many pages a scan will
    fetch. A result that already shows the identifier in its URL or title is far
    likelier to be a real exposure than one that merely came back in the same
    list, so those go to the front and get looked at while there is still
    budget. It changes which pages are READ, never which are believed.
    """
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
    if ident:
        clean.sort(key=lambda r: not _mentions(ident, f"{r[0]} {r[1]}"))
    return clean[:MAX_RESULTS_PER_QUERY]


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

    # Scopes the secondary index's memo to this one query (see _secondary).
    _local.secondary = {}
    try:
        # Throttling is applied to the client, not to the question, so once the
        # primary has refused it will refuse every later query too —
        # re-attempting it costs a timeout apiece and buys nothing. What must
        # NOT be skipped is the secondary index: it is not throttled, and a
        # primary refusal says nothing about whether the secondary can answer
        # THIS query. Skipping it let one query the secondary happened not to
        # cover suppress the rest of the run, including queries it would have
        # answered.
        if engine_state is not None and engine_state.get("blocked"):
            return _fallback_only(query)

        # An exact-phrase query is throttled far more readily than a bare one,
        # and a throttled query cannot answer at all. Dropping the quotes costs
        # nothing here: the engine is only ever used to nominate pages, and
        # every page is then fetched and required to contain the identifier
        # verbatim. A looser query therefore widens what is considered without
        # loosening what is claimed — the extra results simply fail
        # verification and are discarded.
        unquoted = query.strip('"')
        variants = [query] + ([unquoted] if unquoted != query else [])

        for backoff in (0,) + tuple(BLOCK_BACKOFF_S):
            if backoff:
                time.sleep(backoff)
            for variant in variants:
                results, status = _search_once(variant)
                if status != "blocked":
                    _cache_put(query, results, status)
                    return results, status

        if engine_state is not None:
            engine_state["blocked"] = True
        # Every engine refused. A previous run's page list is still worth
        # re-reading — see _stale_leads — and the query stays "blocked", so
        # this can add findings but can never add confidence.
        return _stale_leads(query), "blocked"
    finally:
        _local.secondary = None


def _search_once(query: str) -> tuple[list[tuple[str, str]], str]:
    """One pass over the engines. Returns (results, status); never raises."""
    _PACER.wait()

    # The engines are asked CONCURRENTLY. Asked in turn, a throttled engine
    # charged the full budget for each one over again, and measurement never
    # found one endpoint disagreeing with another about whether this client is
    # throttled: identical 202 anomaly pages, identical stall, on every probe.
    # Concurrency spends that budget once instead of once per engine, and it is
    # also what makes a long registry affordable — eight engines cost about what
    # the slowest one costs, not the sum.
    engines = _active_engines()
    merged: list[tuple[str, str]] = []
    answered_authority = False
    first_answer: float | None = None

    for res, err in _race([lambda e=e: (e, _ddg(query, e)) for e in engines],
                          SEARCH_TIMEOUT + 2):
        if err is not None:
            continue
        engine, hits = res
        answered_authority = answered_authority or engine.authoritative
        merged.extend(hits)
        # Results from several engines are pooled rather than raced for, because
        # their indexes barely overlap — Bing found this number on four people-
        # search sites that Seznam had never crawled. But a pool is only worth
        # the wait it costs, so once something usable is in hand the stragglers
        # get MERGE_WINDOW_S and no more.
        if merged:
            now = time.monotonic()
            first_answer = first_answer or now
            if now - first_answer > MERGE_WINDOW_S:
                break

    clean = _dedupe(merged, query.strip('"'))
    if clean:
        return clean, "ok"

    # Every engine that did not come back with a page it could parse counts as
    # a refusal — a timeout, an HTTP error, an anomaly page, a feed of filler
    # and the group deadline alike. None of them is evidence of absence, and the
    # single thing this module may never do is let one read as a clean result.
    if not answered_authority:
        # Nobody whose silence means anything has spoken. Ask the secondary
        # index before giving up — it is unthrottled, and anything it returns is
        # verified on the page exactly as a primary result would be, so coverage
        # widens without the standard of proof moving.
        clean = _dedupe(_secondary(query), query.strip('"'))
        if clean:
            return clean, "ok"

    # "empty" needs an engine that can actually say the word: one that served a
    # result page it could parse, with no results on it, AND whose empty page is
    # distinguishable from its refusal. Anything less is "could not check".
    return [], ("empty" if answered_authority else "blocked")


# ── query construction ──────────────────────────────────────────────────────

def indian_mobile(raw) -> str | None:
    """
    The ten digits of an Indian mobile number, or None when this is not one.

    Accepts the number bare, behind a trunk 0, or behind a +91 / 91 / 091 /
    0091 country code — which is exactly the set of prefixes the page matcher
    in verify_page understands, so every number this returns is a number that
    can actually be recognised again on a page.

    Everything else returns None and is never searched: landline and toll-free
    ranges (which start 1-5, are shared and published, and whose STD prefixes
    make "the last ten digits" a DIFFERENT number from the one written down),
    other countries' numbers, and anything of an unexpected length. The tool
    would rather not search a number than search a stranger's.
    """
    digits = re.sub(r"\D", "", str(raw or ""))
    for prefix in ("0091", "091", "91", "0", ""):
        if prefix and not digits.startswith(prefix):
            continue
        rest = digits[len(prefix):]
        if len(rest) == 10 and rest[0] in "6789":
            return rest
    return None


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

    # A phone number is searched only when it can actually be identified as
    # this user's. Taking the last ten digits of whatever was typed MANUFACTURES
    # an identifier: "011-2345 6789" became 1123456789, "1800 123 4567" became
    # 8001234567 and "+1 202 555 0173" became 2025550173 — three numbers
    # belonging to somebody else, searched as if they were the user's, and a
    # confirmed hit on one of them was then recorded as this user's exposure at
    # the highest confidence tier. A false identifier is worse than a missing
    # one, so a number that cannot be identified is not searched at all.
    for raw in split(profile.get("phone")) + split(profile.get("alt_phones")):
        mobile = indian_mobile(raw)
        if mobile:
            add(f'"{mobile}"', mobile, "phone")
            add(f'"+91{mobile}"', mobile, "phone")

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


_NAT64_PREFIX = ipaddress.ip_network("64:ff9b::/96")


def _unwrap_nat64(ip):
    """
    Return the real IPv4 address behind a NAT64 address.

    On a NAT64/DNS64 network — which is what this machine is on, and what many
    mobile networks in India are — the resolver synthesises an IPv6 address in
    64:ff9b::/96 for every IPv4-only host. Python's ipaddress reports that
    whole range as `is_reserved`, so the SSRF guard refused github.com,
    keybase.io, soundcloud.com and wordpress.com: four ordinary public sites out
    of twelve tested. It failed closed, so it was not a hole — but it silently
    stopped open-web verification from reading those pages at all, and a page
    that cannot be read produces no finding.

    Decoding the embedded IPv4 and judging THAT keeps the protection intact: a
    NAT64 address wrapping 127.0.0.1 or the cloud metadata address unwraps to
    exactly those and is still refused.
    """
    if ip.version == 6 and ip in _NAT64_PREFIX:
        return ipaddress.ip_address(int(ip) & 0xFFFFFFFF)
    return ip


def is_safe_web_url(url: str) -> bool:
    """
    Validates that a URL is a legitimate public web destination and not an
    internal/loopback address (SSRF mitigation).
    """
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return False
        # Block localhost / loopback / local network names
        if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0") or hostname.endswith(".local"):
            return False
        # If it is an IP literal, verify it is not private, loopback, or reserved
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                return False
        except ValueError:
            pass
        # If DNS resolves to a private IP, reject
        try:
            for *_, sockaddr in socket.getaddrinfo(hostname, None):
                ip = _unwrap_nat64(ipaddress.ip_address(sockaddr[0]))
                if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                    return False
        except Exception:
            # Offline test domain or unresolvable DNS
            pass
        return True
    except Exception:
        return False


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """
    Re-check every redirect hop against is_safe_web_url.

    Validating only the URL we were handed is not enough. urllib follows
    redirects by itself, so a page on a perfectly ordinary public domain can
    answer 302 with Location: http://127.0.0.1/admin and the fetch goes there
    unchecked. Demonstrated: the internal page's body came back as `confirmed`
    evidence, which both leaks it into the ledger and files the finding against
    the attacker's domain.

    The check therefore has to run on the destination of each hop, not just on
    the entry point.
    """

    max_redirections = 5

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not is_safe_web_url(newurl):
            raise urllib.error.HTTPError(
                newurl, code,
                "redirect to a non-public address was refused", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# Installed as the process default rather than used as a local opener, for two
# reasons. It keeps urllib.request.urlopen as the single seam the tests stub —
# swapping in a private opener silently bypassed those stubs and the phone
# matcher went untested again. And it extends the same redirect check to every
# other urllib caller in the app, which is the behaviour we want anyway.
urllib.request.install_opener(urllib.request.build_opener(_SafeRedirectHandler))


def verify_page(url: str, identifier: str, kind: str) -> tuple[bool, str, int | None, str]:
    """
    Fetch the page and look for the identifier in it.

    Returns (confirmed, matched_context, http_status, title). Kept at four
    values because that is what callers and the test suite unpack; anything
    that needs to know WHY a page was not confirmed calls check_page instead.
    """
    _state, confirmed, ctx, status, title, _why = check_page(url, identifier, kind)
    return confirmed, ctx, status, title


def check_page(url: str, identifier: str, kind: str
               ) -> tuple[str, bool, str, int | None, str, str]:
    """
    Fetch the page and look for the identifier in it, keeping "I looked and it
    was not there" apart from "I never got to look".

    Returns (state, confirmed, matched_context, http_status, title, reason).

    state is one of:
        checked    the page was served and read; `confirmed` is the answer
        gone       the server says there is no such page (404/410)
        unchecked  nothing was read — blocked, refused, timed out, unresolvable

    This distinction did not exist, and its absence was a bug of exactly the
    kind this module is built to prevent. A fetch that timed out, hit a
    Cloudflare interstitial, was refused with a 403 or could not be resolved
    came back indistinguishable from a clean page, and the hit was then
    annotated "the identifier was not present in the HTML that was served" —
    about a page where nothing whatsoever was served. Every site that blocks
    scrapers therefore read as checked-and-clear, which is the report saying
    "clean" about the places it is least able to see into.
    """
    if not is_safe_web_url(url):
        return ("unchecked", False, "", None, "",
                "the address did not resolve to a public web server, so it was not fetched")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)
        status = getattr(resp, "status", getattr(resp, "code", 200))
        raw = resp.read(400_000).decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            # A definite answer: the server says this page does not exist. It
            # is not a page that was read, so nothing is claimed about its
            # contents either — but it is not a check that was prevented.
            return ("gone", False, "", e.code, "",
                    f"the page no longer exists (HTTP {e.code})")
        return ("unchecked", False, "", e.code, "",
                f"the site refused the request (HTTP {e.code})")
    except Exception as exc:
        return ("unchecked", False, "", None, "",
                f"the page could not be fetched ({type(exc).__name__})")

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
                ctx = "…" + text[max(0, i - 60):i + len(m.group(0)) + 60].replace("\n", " ") + "…"
                return "checked", True, ctx, status, title, ""
        return "checked", False, "", status, title, ""

    hay, needle = text.lower(), identifier.lower()
    i = hay.find(needle)
    if i >= 0:
        ctx = "…" + text[max(0, i - 90):i + len(identifier) + 90].replace("\n", " ") + "…"
        return "checked", True, ctx, status, title, ""

    # Fall back to a punctuation-insensitive comparison.
    if _normalise(identifier) and _normalise(identifier) in _normalise(text):
        return ("checked", True, "(matched ignoring punctuation and spacing)",
                status, title, "")
    return "checked", False, "", status, title, ""


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
    engine_state: dict = {"blocked": False}

    def ask(query: str) -> tuple[list[tuple[str, str]], str]:
        try:
            return search_web(query, engine_state)
        except Exception:
            # A crash is not a clean sheet either. Anything that stops this
            # query from being answered is reported as unanswered.
            return [], "blocked"

    # The first query runs ALONE, as a probe. It is the one that discovers
    # whether the engine is answering at all, and firing the whole batch before
    # that is known would pay a full network timeout PER QUERY to rediscover a
    # single refusal — which is precisely where a throttled scan spent its
    # minutes. Once the answer is known the rest overlap: if the primary is
    # throttled they go straight to the secondary index, which is not
    # throttled, and if it is answering they are paced by THROTTLE_S at the
    # network layer, so the rate stays polite while the waiting stops
    # accumulating.
    answers: list[tuple[list[tuple[str, str]], str]] = [ask(queries[0][0])]
    if len(queries) > 1:
        with cf.ThreadPoolExecutor(min(len(queries) - 1, SEARCH_WORKERS)) as ex:
            answers.extend(ex.map(ask, [q for q, _, _ in queries[1:]]))

    found: list[tuple[str, str, str, str, str]] = []   # query, ident, kind, url, title
    blocked_queries: list[str] = []
    answered = 0
    for (query, ident, kind), (results, status) in zip(queries, answers):
        if status == "blocked":
            blocked_queries.append(query)
        else:
            answered += 1
        for url, title in results:
            found.append((query, ident, kind, url, title))

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
            reproduce=f"curl -s -A {shlex.quote(UA[:24] + '...')} {shlex.quote(url)} | grep -i {shlex.quote(ident)}",
            note=("" if ok else
                  "The search engine returned this page, but the identifier was not present "
                  "in the HTML that was served. It may be rendered by JavaScript, behind a "
                  "login, or already removed — so nothing is claimed."))

    hits: list[WebHit] = []
    if todo:
        with cf.ThreadPoolExecutor(min(len(todo), max_workers)) as ex:
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
