#!/usr/bin/env python3
"""
test_system.py — SovereignPrivacy AI Automated Test Suite.

Tests all core components:
  1. Dataset integrity validation
  2. PII recognizer accuracy benchmark
  3. Identity resolver correctness
  4. Risk calculator bounds
  5. Legal notice generation
  6. Cryptographic audit chain integrity
  7. Statutory tracker lifecycle
"""

import json
import os
import urllib.error
import os
import sys
import time
from datetime import datetime

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# ── Colors ──
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
BOLD = '\033[1m'
RESET = '\033[0m'

passed = 0
failed = 0
total_time = 0


def test(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  {GREEN}✓{RESET} {name}")
        passed += 1
    else:
        print(f"  {RED}✗{RESET} {name} {RED}— {detail}{RESET}")
        failed += 1


def section(name):
    print(f"\n{BOLD}{CYAN}━━━ {name} ━━━{RESET}")


class _FakeResponse:
    """
    Stands in for what urlopen returns, so a test can serve a page or an API
    body without touching the network.

    Stubbing stops HERE and goes no deeper. Everything above this line — the
    parsing, the digit-run matching, the promotion rules, the clear/unavailable
    decision — is the product's own code running for real. Several tests in
    this file used to re-implement that logic in the test body instead, which
    meant they passed no matter what the product did: a copy of the matcher was
    being checked against a copy of the rules.
    """

    def __init__(self, body, status=200):
        self._body = body.encode() if isinstance(body, str) else body
        self.status = status

    def read(self, amount=None):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# Test Suite
# ═══════════════════════════════════════════════════════════════════════════════

def test_open_web_search():
    section("12. Open-web search (no false positives)")

    from backend.agent import web_search as ws

    # ── what gets searched ──
    q = ws.build_queries({"name": "Rahul Sharma", "email": "rahul@gmail.com",
                          "phone": "+91 98765 43210", "upi_id": "rahul@okaxis",
                          "pan": "ABCPD1234E", "known_usernames": "darkknight92"})
    qs = [x[0] for x in q]
    kinds = {x[2] for x in q}

    test("Email is searched as an exact phrase", '"rahul@gmail.com"' in qs)
    test("Phone is searched bare and with +91",
         '"9876543210"' in qs and '"+919876543210"' in qs)
    test("UPI ID is searched", '"rahul@okaxis"' in qs)
    test("PAN is searched", '"ABCPD1234E"' in qs)
    test("Declared handle is searched", '"darkknight92"' in qs)

    # The whole point: a name is shared by thousands, so it is never a query.
    test("Legal name is NEVER searched",
         not any("Rahul" in x or "Sharma" in x for x in qs), f"queries were {qs}")
    test("Only unique-identifier kinds are searched",
         kinds <= {"email", "phone", "upi", "pan", "username"}, f"kinds {kinds}")

    # A profile with nothing unique produces no search at all.
    empty = ws.build_queries({"name": "Rahul Sharma"})
    test("A name alone produces no query", empty == [], f"got {empty}")

    # ── the phone matcher, which is where a false positive would come from ──
    # These drive ws.verify_page itself. They used to paste the product's regex
    # and comparison into the test body and check THAT — so replacing
    # verify_page with a stub that matched every page still passed all nine,
    # including the four that assert a page does NOT match. Only the fetch is
    # stubbed now; the matching under test is the product's.
    import urllib.request as _urlreq
    _real_urlopen = _urlreq.urlopen
    _real_search_web = ws.search_web

    def _serve(text):
        page = f"<html><head><title>Result page</title></head><body>{text}</body></html>"
        return lambda req, timeout=None: _FakeResponse(page)

    def matches(text, ident="9876543210"):
        _urlreq.urlopen = _serve(text)
        confirmed, _ctx, _status, _title = ws.verify_page("https://page.test/x", ident, "phone")
        return confirmed

    try:
        test("Bare 10-digit mobile matches", matches("call 9876543210 now"))
        test("Spaced mobile matches (98765 43210)", matches("Mobile: 98765 43210"))
        test("+91 mobile matches", matches("call +919876543210"))
        test("Hyphenated +91 mobile matches", matches("call +91-98765-43210"))
        test("Trunk-prefixed mobile matches", matches("dial 09876543210"))

        # Digits from unrelated numbers must never be joined into a match.
        test("Digits split across unrelated numbers do NOT match",
             not matches("Order 1234567 placed. Invoice 8909876 total 543210 rupees."))
        test("A row of unrelated figures does NOT match",
             not matches("figures 1234567 8909876 543210 listed"))
        test("A longer number containing the digits does NOT match",
             not matches("Ref 129876543210456"))
        test("A non-country prefix does NOT match", not matches("txn 559876543210"))

        # A match must carry its own proof: the surrounding page text is what
        # the user is shown, and an empty context is an unevidenced claim.
        _urlreq.urlopen = _serve("reach me on 98765 43210 in the evening")
        ok, ctx, status, title = ws.verify_page("https://page.test/x", "9876543210", "phone")
        test("A confirmed phone hit quotes the surrounding page text",
             ok and "98765 43210" in ctx, f"context was {ctx!r}")
        test("A verified page records the HTTP status it was served with", status == 200,
             f"got {status}")
        test("A verified page records the page title", title == "Result page", f"got {title!r}")

        # ── a username is not unique, so a web hit on one is never a finding ──
        # Driven through search_exposures, so the UNIQUE/unique_pages promotion
        # rule under test is the product's own. The previous form of these three
        # pasted that loop into the test body and never called the product at
        # all: the gate they are named after was entirely untested.
        pages = {
            "https://example.com/a": "<title>A</title>Profile of jsmith. Nothing else here.",
            "https://example.com/b": "<title>B</title>jsmith — reach me at me@x.com any time.",
        }
        serp = {'"me@x.com"': [("https://example.com/b", "B")],
                '"jsmith"': [("https://example.com/a", "A"), ("https://example.com/b", "B")]}

        _urlreq.urlopen = lambda req, timeout=None: _FakeResponse(pages[req.full_url])
        ws.search_web = lambda q, engine_state=None: (serp.get(q, []), "ok")
        res = ws.search_exposures({"email": "me@x.com", "known_usernames": "jsmith"})
        by_url = {(h["url"], h["identifier_type"]): h
                  for h in res["confirmed"] + res["unconfirmed"]}

        test("Username alone on a page is NOT confirmed",
             by_url[("https://example.com/a", "username")]["confirmed"] is False)
        test("A unique identifier on a page IS confirmed",
             by_url[("https://example.com/b", "email")]["confirmed"] is True)
        test("Username IS confirmed when the same page carries a unique identifier",
             by_url[("https://example.com/b", "username")]["confirmed"] is True)
        # A demoted hit is not silently dropped — it is shown as a lead, and it
        # has to say why it is not being counted as the user's data.
        test("A demoted username hit explains why it is not counted",
             "not counted as your data"
             in by_url[("https://example.com/a", "username")]["note"],
             f'note was {by_url[("https://example.com/a", "username")]["note"]!r}')
    finally:
        _urlreq.urlopen = _real_urlopen
        ws.search_web = _real_search_web

    # ── a refused search must never read as a clean one ──
    # A rate-limited engine serves a page with no results on it, which is the
    # same shape as "nothing found". If those collapse together the tool tells
    # somebody their data is nowhere online precisely when it stopped looking.
    real = ws.search_web

    def fake(results, blocked):
        return lambda q, engine_state=None: (
            results, "blocked" if blocked else ("ok" if results else "empty"))

    try:
        ws.search_web = fake([], blocked=True)
        r = ws.search_exposures({"email": "someone@example.com"}, max_pages=0)
        test("A blocked search is flagged as degraded", r["search_degraded"] is True)
        test("A blocked search is not reported as complete", r["complete"] is False)
        test("A blocked search names the queries it could not run",
             r["blocked_queries"] == ['"someone@example.com"'], f"got {r['blocked_queries']}")
        test("A blocked search warns that clean does not mean absent",
             "does NOT mean" in r["coverage_note"])
        test("A blocked search confirms nothing", r["confirmed"] == [])

        # Throttling applies to the client, not to the question: once the engine
        # has refused, the rest of the run must fail fast rather than pay a
        # network timeout per query to rediscover the same block. Counted at
        # the network layer, which is what the timeouts are actually spent on.
        ws.search_web = real
        real_once = ws._search_once
        hits = {"n": 0}

        def blocked_once(q):
            hits["n"] += 1
            return [], "blocked"

        real_mg_2 = ws._marginalia
        mg_hits = {"n": 0}

        def mg_dead(q):
            mg_hits["n"] += 1
            raise TimeoutError("secondary down too")

        try:
            ws._search_once = blocked_once
            ws._marginalia = mg_dead
            ws.BLOCK_BACKOFF_S = ()          # no sleeping inside the test
            multi = ws.search_exposures(
                {"email": "a@b.com,c@d.com", "phone": "9876543210"}, max_pages=0)
            # Only the FIRST query may reach the PRIMARY. It tries the quoted
            # and unquoted form; later queries skip the throttled primary.
            test("A blocked run stops hitting the throttled primary",
                 hits["n"] <= 2, f"primary was called {hits['n']} times")
            # The secondary is NOT skipped — it is not throttled, and a primary
            # refusal says nothing about whether it can answer this query.
            # The first query's fallback lives inside _search_once, which is
            # stubbed here, so the count covers every query after the first.
            test("The secondary index is still tried for every later query",
                 mg_hits["n"] == multi["searched"] - 1,
                 f'secondary tried {mg_hits["n"]}x for {multi["searched"]} queries')
            test("Both engines failing reports every query as blocked",
                 len(multi["blocked_queries"]) == multi["searched"],
                 f'{len(multi["blocked_queries"])} of {multi["searched"]}')
            test("A short-circuited run is still flagged degraded",
                 multi["search_degraded"] is True)
        finally:
            ws._search_once = real_once
            ws._marginalia = real_mg_2
            ws.BLOCK_BACKOFF_S = (5,)

        ws.search_web = fake([], blocked=False)
        r2 = ws.search_exposures({"email": "someone@example.com"}, max_pages=0)
        test("A genuinely empty search is NOT flagged as degraded",
             r2["search_degraded"] is False)
        test("A genuinely empty search is reported as complete", r2["complete"] is True)
        test("A completed search says so", "completed" in r2["coverage_note"])
    finally:
        ws.search_web = real

    # ── the secondary index rescues a throttled primary ──
    # A refused primary used to end the search. A second, unthrottled index is
    # consulted before giving up, and anything it returns is verified on the
    # page exactly as a primary result would be — so coverage widens without
    # the standard of proof moving.
    real_ddg, real_mg = ws._ddg, ws._marginalia
    seen_q = {}
    try:
        def ddg_blocked(q, endpoint):
            raise urllib.error.HTTPError(endpoint, 202, "anomaly", None, None)

        def mg_ok(q):
            seen_q["q"] = q
            return [("https://example.org/page", "A page")]

        import urllib.error
        ws._ddg, ws._marginalia = ddg_blocked, mg_ok
        res, status = ws._search_once('"me@example.com"')
        test("A throttled primary falls back to the secondary index", status == "ok",
             f"status={status}")
        test("The fallback returns usable results",
             res == [("https://example.org/page", "A page")], f"got {res}")
        test("The fallback query drops the phrase quotes",
             seen_q.get("q") == "me@example.com", f'sent {seen_q.get("q")!r}')

        # If the secondary is down too, the run is still reported as blocked —
        # never as clean.
        def mg_down(q):
            raise TimeoutError("slow")
        ws._marginalia = mg_down
        res2, status2 = ws._search_once('"me@example.com"')
        test("Both engines down is reported as blocked, not clear", status2 == "blocked")
        test("Both engines down confirms nothing", res2 == [])
    finally:
        ws._ddg, ws._marginalia = real_ddg, real_mg

    # ── the result cache ──
    import shutil
    shutil.rmtree(ws._CACHE_DIR, ignore_errors=True)

    ws._cache_put("q-ok", [("https://a.test/1", "t")], "ok")
    got = ws._cache_get("q-ok")
    test("A successful search is cached", got is not None and got[1] == "ok")
    test("Cached results round-trip intact",
         got[0] == [("https://a.test/1", "t")], f"got {got}")

    # Caching a refusal would turn one throttled minute into hours of
    # pretending to have looked.
    ws._cache_put("q-blocked", [], "blocked")
    test("A BLOCKED search is never cached", ws._cache_get("q-blocked") is None)

    ws._cache_put("q-empty", [], "empty")
    test("A genuinely empty result IS cached",
         (ws._cache_get("q-empty") or (None, None))[1] == "empty")

    # An expired entry must be re-queried, not served stale.
    import os as _os, time as _t
    _os.utime(ws._cache_path("q-ok"), (_t.time() - ws.CACHE_TTL_S - 60,) * 2)
    test("An expired cache entry is ignored", ws._cache_get("q-ok") is None)
    shutil.rmtree(ws._CACHE_DIR, ignore_errors=True)


def test_free_intel():
    section("14. Free breach intelligence (no paid key)")

    from backend.agent import verifiers as v
    from backend.agent.tools import xposed_fields, _severity_of, XPOSED_LABEL_TO_FIELD

    # ── severity must survive the vocabulary change ──
    # XposedOrNot names data classes its own way. Unmapped labels fall through
    # to "low", which reported a breach of government IDs and passwords as
    # minor — the first version of this integration did exactly that.
    cases = [
        ("Email addresses;Usernames", "medium", ["email", "username"]),
        ("Email addresses;Passwords", "critical", ["email", "password"]),
        ("Email addresses;Government IDs", "critical", ["email", "government_id"]),
        ("Email addresses;Credit cards", "critical", ["email", "credit_card"]),
        ("['Email addresses', 'Religions']", "high", ["email", "religion"]),
    ]
    for raw, want_sev, want_fields in cases:
        got = xposed_fields(raw)
        test(f"Breach fields parsed: {raw[:34]}", got == want_fields, f"got {got}")
        test(f"Severity is {want_sev} for {want_fields[-1]}",
             _severity_of(got) == want_sev, f"got {_severity_of(got)}")

    test("A JSON-list form is parsed as well as a semicolon list",
         xposed_fields("['Email addresses', 'Passwords']") == ["email", "password"])
    test("An unknown label is kept, not dropped",
         xposed_fields("Quantum telepathy records") == ["quantum_telepathy_records"])
    # Asserting that four hand-picked keys exist in a dict declared in the same
    # repo proves nothing — it passed while 'Credit card details' and
    # 'Historical passwords', both emitted by the live catalogue, fell through
    # to "low". What must hold is the PROPERTY: nothing describing a credential
    # or a payment instrument may ever be scored as minor.
    LIVE_LABELS = [
        "Email addresses", "Passwords", "Names", "Usernames", "Phone numbers",
        "IP addresses", "Physical addresses", "Dates of birth", "Genders",
        "Geographic locations", "Social media profiles", "Device information",
        "Private messages", "Government IDs", "Government issued IDs",
        "Job titles", "Nationalities", "Security questions and answers",
        "Marital statuses", "Purchases", "Instant messenger identities",
        "Website activity", "Income levels", "Employers", "Ethnicities",
        "Passport numbers", "Religions", "Social security numbers",
        "Sexual preferences", "Browser user agent details", "Spoken languages",
        "Support tickets", "Partial credit card data", "Vehicle details",
        "Account balances", "Nationality", "Vehicle registration numbers",
        "Titles", "Academic records", "National IDs", "Financial transactions",
        "Customer support tickets", "Spouses names", "AI prompts", "Auth tokens",
        "Places of birth", "Bank account numbers", "Credit cards", "Browsers",
        "Occupations", "Licence plates", "Profile photos", "Mothers maiden names",
        "Passwords history", "Credit card details", "Historical passwords",
    ]
    SEVERE_WORDS = ("credit card", "debit card", "password", "bank account",
                    "auth token", "passport", "social security", "government",
                    "national id", "security question")
    mis_scored = []
    for label in LIVE_LABELS:
        fields = xposed_fields(label)
        sev = _severity_of(fields)
        if any(w in label.lower() for w in SEVERE_WORDS) and sev in ("low", "medium"):
            mis_scored.append(f"{label!r}->{fields}={sev}")
    test("No credential or payment label is ever scored low/medium",
         not mis_scored, f"mis-scored: {mis_scored}")

    # Every label the live catalogue emits must resolve to something the
    # severity table recognises, not to an unknown slug.
    from backend.agent.tools import SEVERITY_BY_FIELD as _SEV
    unknown = sorted({f for label in LIVE_LABELS for f in xposed_fields(label)
                      if f not in _SEV})
    test("Every live breach label maps to a known severity field",
         not unknown, f"unmapped: {unknown}")

    # ── severity is a rule, not a spelling ──
    # The test above picks four keys out of a dict that lives in this repo, so
    # it passes for as long as nobody deletes a line — while real severe labels
    # fall straight through to "low". The live XposedOrNot catalogue (783
    # breaches, 69 distinct data-class labels, read 2026-09-12) emits BOTH
    # 'Credit card details' and 'Historical passwords'. Neither was in the map,
    # so a card breach and a password dump were each scored as minor.
    #
    # These are the real strings, hardcoded so the suite stays offline. The
    # assertion is about the rule rather than the spelling: what it costs a
    # person to have this leaked cannot depend on which of two vocabularies the
    # upstream happened to use for it.
    LIVE_SEVERE_LABELS = [
        "Credit card details", "Credit cards", "Credit card CVV",
        "Partial credit card data", "Passwords", "Historical passwords",
        "Passwords history", "Password hints", "Password strengths",
        "Auth tokens", "Security questions and answers", "Government issued IDs",
        "Government IDs", "Partial government issued IDs", "National IDs",
        "Passport numbers", "Social security numbers", "Bank account numbers",
    ]
    for label in LIVE_SEVERE_LABELS:
        fields = xposed_fields(label)
        sev = _severity_of(fields)
        test(f"'{label}' is scored critical", sev == "critical",
             f"scored {sev} via {fields}")

    # The rule stated directly, so a label added upstream tomorrow cannot slip
    # past by being spelled differently from the ones enumerated above.
    demoted = [(lbl, _severity_of(xposed_fields(lbl))) for lbl in LIVE_SEVERE_LABELS
               if ("credit card" in lbl.lower() or "password" in lbl.lower())
               and _severity_of(xposed_fields(lbl)) == "low"]
    test("No credit-card or password label can ever score 'low'", not demoted,
         f"scored low: {demoted}")

    # ── the checks refuse to guess when given nothing ──
    test("XposedOrNot with no email is not_checked",
         v.check_xposedornot("").result == "not_checked")
    test("Infostealer check with no email is not_checked",
         v.check_infostealer("").result == "not_checked")

    # ── evidence discipline ──
    for fn in (v.check_xposedornot, v.check_infostealer):
        ev = fn("")
        test(f"{ev.check} states what it does not prove", len(ev.interpretation) > 10)

    # ── an upstream refusal is NOT a clean bill of health ──
    # These two checks are the only free answer the product has to "has my
    # address been breached", so a false CLEAR here is the worst output the tool
    # can produce: it tells somebody they are safe at the exact moment the
    # check stopped working. Both used to do it — an upstream body of
    # {"Error": "Rate limit exceeded"} was read as "no breaches found" and
    # reported under the words CONFIRMED CLEAR, quoting the rate-limit text as
    # its proof.
    #
    # Stubbed at _get, the one function in verifiers.py that touches the
    # network, so the decision being tested is the product's own.
    import urllib.error as _uerr
    _real_get = v._get
    seen_url = {}

    def _stub_get(body, status=200):
        def _get(url, headers=None):
            seen_url["url"] = url
            return _FakeResponse(json.dumps(body), status)
        return _get

    def _stub_http_error(code):
        def _get(url, headers=None):
            seen_url["url"] = url
            raise _uerr.HTTPError(url, code, "rate limited", None, None)
        return _get

    try:
        RATE_LIMIT = {"Error": "Rate limit exceeded"}

        v._get = _stub_get(RATE_LIMIT)
        ev = v.check_xposedornot("someone@example.com")
        test("A rate-limited XposedOrNot body is 'unavailable', not 'clear'",
             ev.result == "unavailable", f"result={ev.result}: {ev.interpretation[:70]}")
        test("A rate-limited XposedOrNot answer never says CONFIRMED CLEAR",
             "CONFIRMED CLEAR" not in ev.interpretation, ev.interpretation[:70])

        # The evidence must name the URL that was actually queried — an endpoint
        # field that merely EXISTS proves nothing, and a dataclass has one on
        # every instance ever constructed whether it was filled in or not.
        test("XposedOrNot records the exact endpoint it queried",
             ev.endpoint == seen_url["url"] and "xposedornot.com" in ev.endpoint,
             f"recorded {ev.endpoint!r}, queried {seen_url.get('url')!r}")
        test("The recorded endpoint carries the address that was looked up",
             "someone%40example.com" in ev.endpoint or "someone@example.com" in ev.endpoint,
             f"got {ev.endpoint!r}")

        # The genuine clean answer must still read as clean, or the fix above
        # has simply moved the lie to the other side.
        v._get = _stub_get({"Error": "Not found"})
        ev = v.check_xposedornot("someone@example.com")
        test("A genuine 'not found' from XposedOrNot IS clear",
             ev.result == "clear", f"result={ev.result}")

        v._get = _stub_http_error(429)
        ev = v.check_xposedornot("someone@example.com")
        test("An HTTP 429 from XposedOrNot is 'unavailable', not 'clear'",
             ev.result == "unavailable", f"result={ev.result}")

        v._get = _stub_get(RATE_LIMIT)
        ev = v.check_infostealer("someone@example.com")
        test("A rate-limited infostealer body is 'unavailable', not 'clear'",
             ev.result == "unavailable", f"result={ev.result}: {ev.interpretation[:70]}")
        test("A rate-limited infostealer answer never says CONFIRMED CLEAR",
             "CONFIRMED CLEAR" not in ev.interpretation, ev.interpretation[:70])
        test("Infostealer records the exact endpoint it queried",
             ev.endpoint == seen_url["url"] and "hudsonrock.com" in ev.endpoint,
             f"recorded {ev.endpoint!r}, queried {seen_url.get('url')!r}")

        v._get = _stub_http_error(429)
        ev = v.check_infostealer("someone@example.com")
        test("An HTTP 429 from the infostealer corpus is 'unavailable'",
             ev.result == "unavailable", f"result={ev.result}")

        v._get = _stub_get({"stealers": [], "message": "No results found"})
        ev = v.check_infostealer("someone@example.com")
        test("A genuine empty infostealer answer IS clear",
             ev.result == "clear", f"result={ev.result}")

        # And a real hit must still be reported as one.
        v._get = _stub_get({"stealers": [{"computer_name": "DESKTOP-9F2",
                                          "date_compromised": "2024-06-01T00:00:00Z"}]})
        ev = v.check_infostealer("someone@example.com")
        test("A reported infection IS a hit", ev.result == "hit", f"result={ev.result}")
        test("An infection tells the user to rotate credentials and revoke sessions",
             "sign out of all sessions" in ev.interpretation.lower()
             or "session" in ev.interpretation.lower(), ev.interpretation[:70])
    finally:
        v._get = _real_get


def test_site_roster():
    section("13. Discovery site roster")

    from backend.agent import account_discovery as ad

    test("Site roster is non-empty", len(ad.SITES) > 0)
    test("Every site has a URL template and category",
         all("{u}" in s["url"] and s.get("category") for s in ad.SITES.values()))

    # Measured 2026-09-12: five invented handles all returned HTTP 200 from
    # Kaggle, so a hit there proved nothing; Replit returned 404 even for
    # handles that exist, so it could never produce one.
    test("Kaggle is excluded (soft 404)", "Kaggle" not in ad.SITES)
    test("Kaggle exclusion records the reason", "Kaggle" in ad.EXCLUDED)
    test("Replit is excluded (never returns 200)", "Replit" not in ad.SITES)
    test("Replit exclusion records the reason", "Replit" in ad.EXCLUDED)
    test("No site is both checked and excluded",
         not (set(ad.SITES) & set(ad.EXCLUDED)),
         f"overlap {set(ad.SITES) & set(ad.EXCLUDED)}")

    # The bug that made scans report nothing: with no declared handle the
    # deriver returned an empty list, so zero sites were ever checked.
    handles = ad.derive_usernames({"email": "nalinchamp@gmail.com"})
    test("A handle is derived from an email when none is declared",
         [h for h, _ in handles] == ["nalinchamp"], f"got {handles}")
    test("A derived handle is tagged as a guess",
         all(src in ("email_local", "upi_local") for _, src in handles))
    test("Declared handles are still preferred",
         ad.derive_usernames({"known_usernames": "realhandle",
                              "email": "other@gmail.com"})[0][1] == "declared")
    test("A name never produces a handle",
         ad.derive_usernames({"name": "Nalin Sharma"}) == [])

    # Every site we search must have a removal playbook. Without one,
    # plan_removal falls through to "statutory_notice" — so adding a site and
    # forgetting its playbook makes the agent serve a 30-day legal notice on a
    # service that has a delete button, which is the escalation this product
    # explicitly exists to avoid.
    from backend.agent.tools import find_playbook
    missing = [site for site in ad.SITES if not find_playbook(site)]
    test("Every searched site has a removal playbook",
         not missing, f"no playbook for: {missing}")

    KNOWN_METHODS = {"self_serve", "privacy_form", "email_request", "statutory_notice",
                     "statutory_only", "not_removable", "credential_rotation"}
    import json as _json
    pbs = _json.load(open(os.path.join(PROJECT_ROOT, "data", "removal_playbooks.json")))["playbooks"]
    ids = [p["id"] for p in pbs]
    test("Playbook ids are unique", len(ids) == len(set(ids)),
         f"duplicates: {[i for i in ids if ids.count(i) > 1]}")
    test("Every playbook has a usable URL",
         all(p.get("url", "").startswith("http") for p in pbs))
    test("Every playbook has concrete steps",
         all(len(p.get("steps", [])) >= 2 for p in pbs))
    test("Every playbook declares a known method",
         all(p.get("method") in KNOWN_METHODS for p in pbs),
         f'bad: {sorted({p.get("method") for p in pbs} - KNOWN_METHODS)}')

    # Every method a playbook declares must have an entry in method_info, or
    # plan_removal shows the user a raw slug instead of an explanation.
    info = _json.load(open(os.path.join(PROJECT_ROOT, "data", "removal_playbooks.json")))["method_info"]
    missing_info = sorted({p["method"] for p in pbs} - set(info))
    test("Every method has a user-facing explanation", not missing_info,
         f"no method_info for: {missing_info}")

    # An info-stealer infection cannot be erased — the data came off the user's
    # own machine, so there is no controller to serve. The honest answer is not
    # "nothing to do": it is rotate everything, urgently.
    inf = find_playbook("infostealer")
    test("An info-stealer infection has a remediation playbook", inf is not None)
    test("It routes to credential rotation, not erasure",
         inf and inf["method"] == "credential_rotation")
    test("It tells the user to revoke sessions, not just change passwords",
         inf and any("session" in s.lower() for s in inf["steps"]))
    test("It gives an Indian incident-reporting route",
         inf and ("1930" in inf["escalation"] or "cybercrime.gov.in" in inf["escalation"]))

    # Wikipedia edits are CC BY-SA licensed and the licence requires the
    # attribution history be kept, so erasure genuinely does not lie there.
    wiki = find_playbook("Wikipedia")
    test("Wikipedia is marked not removable (licence requires attribution)",
         wiki and wiki["method"] == "not_removable")



def test_datasets():
    section("1. Dataset Integrity")

    # Optery brokers
    path = os.path.join(PROJECT_ROOT, "data", "brokers", "optery_brokers.json")
    try:
        with open(path) as f:
            brokers = json.load(f)
        test("Optery brokers file loads", True)
        test(f"Optery has ≥ 900 brokers ({len(brokers)})", len(brokers) >= 900)
        test("Broker has required fields", all(
            "name" in b and "website" in b and "category" in b for b in brokers[:10]
        ))
    except Exception as e:
        test("Optery brokers file loads", False, str(e))

    # HIBP breaches
    path = os.path.join(PROJECT_ROOT, "data", "breaches", "hibp_breaches.json")
    try:
        with open(path) as f:
            breaches = json.load(f)
        test("HIBP breaches file loads", True)
        test(f"HIBP has ≥ 1000 breaches ({len(breaches)})", len(breaches) >= 1000)
        test("Breach has required fields", all(
            "name" in b and "domain" in b and "data_classes" in b for b in breaches[:10]
        ))
    except Exception as e:
        test("HIBP breaches file loads", False, str(e))

    # Synthetic pastes
    path = os.path.join(PROJECT_ROOT, "data", "synthetic_pastes", "pastes_corpus.json")
    try:
        with open(path) as f:
            pastes = json.load(f)
        test("Synthetic pastes file loads", True)
        test(f"Pastes has ≥ 40 entries ({len(pastes)})", len(pastes) >= 40)
    except Exception as e:
        test("Synthetic pastes file loads", False, str(e))

    # Benchmark
    path = os.path.join(PROJECT_ROOT, "data", "benchmarks", "pii_ground_truth.json")
    try:
        with open(path) as f:
            samples = json.load(f)
        test("Benchmark file loads", True)
        test(f"Benchmark has ≥ 300 samples ({len(samples)})", len(samples) >= 300)
    except Exception as e:
        test("Benchmark file loads", False, str(e))

    # Legal templates
    templates_dir = os.path.join(PROJECT_ROOT, "data", "templates")
    for tpl in ["dpdp_erasure_notice.txt", "gdpr_art17_notice.txt", "ccpa_deletion_notice.txt"]:
        path = os.path.join(templates_dir, tpl)
        test(f"Template {tpl} exists", os.path.isfile(path))


def test_pii_recognizer():
    section("2. PII Recognizer")

    from backend.pii.recognizer import PIIRecognizer, verhoeff_validate, luhn_validate

    recognizer = PIIRecognizer()

    # Aadhaar detection. 2345 6789 0124 carries a correct Verhoeff check digit;
    # 2345 6789 0123 does not, and must now be rejected rather than downgraded.
    entities = recognizer.recognize("My Aadhaar is 2345 6789 0124")
    aadhaar_found = any(e.entity_type == "AADHAAR" for e in entities)
    test("Detects Aadhaar number", aadhaar_found)

    # ── Regression tests for defects found during the agentic rebuild ──

    # A failed Verhoeff checksum must disqualify, not merely lower confidence.
    bad = recognizer.recognize("Reference number 234567890123 on file")
    test("Rejects Aadhaar with bad checksum",
         not any(e.entity_type == "AADHAAR" for e in bad))

    # A timestamp-shaped 12-digit number must not be reported as a national ID.
    ts = recognizer.recognize("Transaction id 202609121633 posted")
    test("Timestamp is not misread as Aadhaar",
         not any(e.entity_type == "AADHAAR" for e in ts))

    # The Aadhaar pattern matches the first 12 digits of a 16-digit card. A card
    # must win its own span, or the tool tells users their Aadhaar leaked.
    card = recognizer.recognize("card 4111111111111111 on file")
    types = [e.entity_type for e in card]
    test("Payment card is not misread as Aadhaar",
         "CREDIT_CARD" in types and "AADHAAR" not in types)

    # A 10-digit run inside a longer number is not an Indian mobile number.
    inner = recognizer.recognize("Order number 809209727560 confirmed")
    test("No phone match inside a longer digit run",
         not any(e.entity_type == "PHONE_IN" for e in inner))

    # PAN encodes a holder-type character in position 4; ABCDE1234F is not valid.
    test("PAN holder-type character is enforced",
         not any(e.entity_type == "PAN" for e in recognizer.recognize("PAN ABCDE1234F"))
         and any(e.entity_type == "PAN" for e in recognizer.recognize("PAN ABCPE1234F")))

    # PAN detection
    entities = recognizer.recognize("PAN: ABCPD1234E")
    pan_found = any(e.entity_type == "PAN" for e in entities)
    test("Detects PAN card", pan_found)

    # Email detection
    entities = recognizer.recognize("Contact: aarav.sharma@gmail.com")
    email_found = any(e.entity_type == "EMAIL" for e in entities)
    test("Detects email address", email_found)

    # Indian phone
    entities = recognizer.recognize("Call +91 9876543210")
    phone_found = any(e.entity_type == "PHONE_IN" for e in entities)
    test("Detects Indian phone number", phone_found)

    # UPI
    entities = recognizer.recognize("Pay via aarav.sharma@ybl")
    upi_found = any(e.entity_type == "UPI" for e in entities)
    test("Detects UPI ID", upi_found)

    # IP Address
    entities = recognizer.recognize("Login from 192.168.1.100")
    ip_found = any(e.entity_type == "IP_ADDRESS" for e in entities)
    test("Detects IP address", ip_found)

    # IFSC
    entities = recognizer.recognize("IFSC: IDFB0012345")
    ifsc_found = any(e.entity_type == "IFSC" for e in entities)
    test("Detects IFSC code", ifsc_found)

    # Mixed text
    text = "Customer Aarav Sharma (email: aarav@gmail.com, phone: +91 9876543210) PAN ABCPD1234E"
    entities = recognizer.recognize(text)
    types = set(e.entity_type for e in entities)
    test("Multi-entity detection", len(types) >= 3, f"Found {types}")

    # Verhoeff algorithm. These assert against published test vectors: 236
    # carries the check digit 3, so 2363 is valid and 2364 is not. The previous
    # form of these two tests was `verhoeff_validate(...) or True`, which is
    # true whatever the function returns — both passed while the function was
    # returning False for the number the test name said it accepted.
    test("Verhoeff accepts a valid vector (2363)", verhoeff_validate("2363"))
    test("Verhoeff accepts a valid vector (123451)", verhoeff_validate("123451"))
    test("Verhoeff rejects a bad check digit (2364)", not verhoeff_validate("2364"))
    test("Verhoeff rejects a bad check digit (12345)", not verhoeff_validate("12345"))

    # A +91 mobile is twelve digits, and twelve digits clear Verhoeff by chance
    # about one time in ten. Ranking the checksum flag above match length let
    # that chance hit outrank the phone match, so roughly one Indian mobile in
    # ten was reported to its owner as a leaked Aadhaar number.
    for number in ("+918760560500", "+916513857105"):
        got = [e.entity_type for e in recognizer.recognize(f"Call me at {number}")]
        test(f"{number} is a phone, not an Aadhaar",
             "PHONE_IN" in got and "AADHAAR" not in got, f"got {got}")

    # The two cases above are both written "+91", and the lookbehind that
    # guards them keys on the plus sign. People write the country code without
    # it constantly — "919876543007", the form a contact export and a WhatsApp
    # link both use — and that form was never covered here. It is the same
    # twelve digits and the same one-in-ten chance of clearing Verhoeff, so it
    # produces the same false Aadhaar report, with nothing catching it.
    for number in ("919876543007", "918760560500"):
        got = [e.entity_type for e in recognizer.recognize(f"Call me on {number} anytime")]
        test(f"Bare-91 {number} is a phone, not an Aadhaar",
             "PHONE_IN" in got and "AADHAAR" not in got, f"got {got}")

    # Benchmark run
    benchmark_path = os.path.join(PROJECT_ROOT, "data", "benchmarks", "pii_ground_truth.json")
    with open(benchmark_path) as f:
        samples = json.load(f)

    # Scored on (type, value) pairs, not on the set of types present. Comparing
    # types alone cannot tell a correct extraction from one that found the right
    # KIND of thing in the wrong place — "an AADHAAR was detected" would score a
    # hit even when the digits reported were somebody's phone number.
    def _norm(v):
        return "".join(c for c in str(v).lower() if c.isalnum())

    tp, fp, fn = 0, 0, 0
    for sample in samples:
        detected = {(e.entity_type, _norm(e.value)) for e in recognizer.recognize(sample["text"])}
        expected = {(e["type"], _norm(e["value"])) for e in sample.get("expected_entities", [])}
        tp += len(expected & detected)
        fp += len(detected - expected)
        fn += len(expected - detected)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    # The thresholds were 70% while the recognizer was scoring 100 / 99.8 / 99.9.
    # Thirty points of slack is not a floor, it is a formality: every regression
    # short of halving the recognizer passed underneath it. These sit just below
    # the measured score — close enough that a real regression trips them,
    # far enough that a legitimate re-tuning of the recognizer has room to move.
    # Measured 2026-09-12: precision 100.0%, recall 99.8%, F1 99.9% over 460
    # ground-truth entities.
    test(f"Precision ≥ 97% ({precision*100:.1f}%)", precision >= 0.97,
         f"{fp} false positives against {tp} true")
    test(f"Recall ≥ 97% ({recall*100:.1f}%)", recall >= 0.97,
         f"{fn} entities missed against {tp} found")
    test(f"F1 Score ≥ 97% ({f1*100:.1f}%)", f1 >= 0.97)


def test_identity_resolver():
    section("3. Identity Resolver")

    from backend.pii.resolver import IdentityResolver, jaro_winkler_similarity

    resolver = IdentityResolver()

    # Exact match
    result = resolver.resolve(
        {"name": "Aarav Sharma", "email": "aarav@gmail.com", "phone": "+91 9876543210"},
        {"name": "Aarav Sharma", "email": "aarav@gmail.com", "phone": "9876543210"},
    )
    test("Exact match scores ≥ 0.90", result.overall_score >= 0.90, f"score={result.overall_score}")
    test("Exact match is 'definite'", result.confidence_label == "definite")

    # Partial match
    result = resolver.resolve(
        {"name": "Aarav Sharma", "email": "aarav@gmail.com"},
        {"name": "Aarav Kumar", "email": "aarav@gmail.com"},
    )
    test("Partial match is_match=True", result.is_match)

    # No match
    result = resolver.resolve(
        {"name": "Aarav Sharma", "email": "aarav@gmail.com"},
        {"name": "Bob Smith", "email": "bob@yahoo.com"},
    )
    test("Non-match scores < 0.45", result.overall_score < 0.45)


    # A record containing only a matching name scored 1.0 "definite" before this
    # fix. On a common name that is a stranger — and the agent would then serve a
    # legal notice about somebody else's record.
    name_only = resolver.resolve(
        {"name": "Aarav Sharma", "email": "aarav.sharma@example.com",
         "phone": "+919876543210", "city": "New Delhi"},
        {"name": "Aarav Sharma"})
    test("Name-only record is not a match", not name_only.is_match)
    test("Name-only record is not 'definite'", name_only.confidence_label != "definite")

    # A unique identifier on its own is still conclusive.
    email_only = resolver.resolve(
        {"name": "Aarav Sharma", "email": "aarav.sharma@example.com"},
        {"email": "aarav.sharma@example.com"})
    test("Unique identifier alone is a match", email_only.is_match)
    # Jaro-Winkler
    sim = jaro_winkler_similarity("Sharma", "Sharma")
    test("JW identical strings = 1.0", sim == 1.0)

    sim = jaro_winkler_similarity("Sharma", "Sharme")
    test("JW similar strings > 0.9", sim > 0.9, f"sim={sim}")

    sim = jaro_winkler_similarity("Sharma", "Zzzzzz")
    test("JW dissimilar strings < 0.5", sim < 0.5)

    # ── phone normalisation ──
    # This read .lstrip('0').lstrip('91'), which strips CHARACTERS, not a
    # prefix: it ate every leading 9 and 1. 9111111111 became the empty string
    # and matched nothing, and 9198765432 and 8765432 — two different numbers —
    # both collapsed to 8765432 and matched each other.
    n = resolver._normalize
    test("Phone keeps all ten digits", n("phone", "9876543210") == "9876543210")
    test("Phone strips +91 and spacing",
         n("phone", "+91 98765 43210") == "9876543210")
    test("Phone strips a 0 trunk prefix",
         n("phone", "0919876543210") == "9876543210")
    test("A number of leading 9s and 1s survives",
         n("phone", "9111111111") == "9111111111",
         f'got {n("phone", "9111111111")!r}')
    test("Two different numbers do NOT normalise alike",
         n("phone", "9198765432") != n("phone", "8765432"))

    # ── date of birth ──
    # date_of_birth was absent from FIELD_WEIGHTS, so it was never compared:
    # a record could agree or disagree on it and neither counted.
    test("DOB is a compared field", "date_of_birth" in resolver.FIELD_WEIGHTS)
    test("DOB is compared exactly, not fuzzily",
         "date_of_birth" in resolver.EXACT_FIELDS)
    test("DOB formats normalise alike",
         n("date_of_birth", "11/03/1994") == n("date_of_birth", "1994-03-11") == "1994-03-11")

    me = {"name": "Rahul Sharma", "email": "rahul.s@gmail.com", "phone": "9876543210",
          "city": "Mumbai", "date_of_birth": "1994-03-11"}
    same_name = {"name": "Rahul Sharma", "city": "Mumbai"}
    wrong_dob = {"name": "Rahul Sharma", "city": "Mumbai", "date_of_birth": "1988-01-02"}

    test("A disagreeing DOB lowers the score",
         resolver.resolve(me, wrong_dob).overall_score
         < resolver.resolve(me, same_name).overall_score)

    # This assertion used to be made against `wrong_dob` above, which carries no
    # unique identifier — so is_match was already False through has_unique, and
    # the DOB played no part in it. Deleting date_of_birth from FIELD_WEIGHTS
    # and EXACT_FIELDS entirely left the test still passing.
    #
    # Here the two records are identical but for the date of birth, and both
    # carry the same UPI ID, so has_unique is True either way. The DOB
    # comparison is then the only thing left that can decide the outcome.
    upi_me = {"name": "Rahul Sharma", "upi": "rahul@okaxis", "city": "Mumbai",
              "date_of_birth": "1994-03-11"}
    upi_same_dob = {"upi": "rahul@okaxis", "date_of_birth": "11/03/1994"}
    upi_wrong_dob = {"upi": "rahul@okaxis", "date_of_birth": "1988-01-02"}

    agreeing = resolver.resolve(upi_me, upi_same_dob)
    disagreeing = resolver.resolve(upi_me, upi_wrong_dob)

    test("The DOB control case has a unique identifier on both sides",
         agreeing.has_unique_identifier and disagreeing.has_unique_identifier,
         "the case cannot isolate DOB without one")
    test("An agreeing DOB alongside a unique identifier IS a match",
         agreeing.is_match, f"score={agreeing.overall_score}")
    test("A disagreeing DOB defeats the match despite the unique identifier",
         not disagreeing.is_match,
         f"score={disagreeing.overall_score}, matched={disagreeing.matched_fields}")
    test("The disagreeing DOB is recorded as an unmatched field",
         "date_of_birth" in disagreeing.unmatched_fields,
         f"unmatched={disagreeing.unmatched_fields}")

    # ── attribution needs something unique ──
    r_shared = resolver.resolve(me, same_name)
    test("A same-name, same-city stranger is NOT attributed", not r_shared.is_match)
    test("A same-name, same-city stranger is surfaced to confirm",
         r_shared.needs_confirmation)
    test("Shared attributes are not a unique identifier",
         not r_shared.has_unique_identifier)

    r_me = resolver.resolve(me, {"email": "rahul.s@gmail.com"})
    test("A unique identifier IS attributed", r_me.is_match)
    test("A unique identifier needs no confirmation", not r_me.needs_confirmation)
    test("A unique identifier is recorded as unique", r_me.has_unique_identifier)


def test_risk_calculator():
    section("4. Risk Calculator")

    from backend.pii.risk_calculator import RiskCalculator

    calc = RiskCalculator()

    # No exposures
    result = calc.calculate([], 0, 0)
    test("Zero exposures → Minimal risk", result.risk_level == "Minimal")
    test("Zero exposures → score = 0", result.overall_score == 0)

    # Critical exposures
    result = calc.calculate([
        {"entity_type": "AADHAAR", "source_type": "hibp_verified", "date_found": datetime.now().isoformat(), "value": "test"},
        {"entity_type": "PAN", "source_type": "dark_web_paste", "date_found": datetime.now().isoformat(), "value": "test"},
        {"entity_type": "CREDIT_CARD", "source_type": "hibp_verified", "date_found": datetime.now().isoformat(), "value": "test"},
    ], broker_matches=50, total_brokers_checked=956)
    test("Critical exposures → High/Critical", result.risk_level in ("High", "Critical"))
    test("Risk score 0–100 bounds", 0 <= result.overall_score <= 100)
    test("Has recommendations", len(result.recommendations) >= 1)


def test_legal_notices():
    section("5. Legal Notice Generator")

    from backend.remediation.notice_generator import NoticeGenerator

    gen = NoticeGenerator()

    # DPDP
    result = gen.generate("dpdp", "Aarav Sharma", "aarav@gmail.com", "+91 9876543210", "PAN: ABCPD1234E", "Acme Corp")
    test("DPDP notice generates", result["status"] == "generated")
    test("DPDP cites Section 12", "Section 12" in result["notice_text"])
    test("DPDP cites Section 13", "Section 13" in result["notice_text"])
    test("Has reference ID", len(result["reference_id"]) > 0)
    test("Has receipt hash", len(result["receipt_hash"]) == 64)

    # GDPR
    result = gen.generate("gdpr", "Emma Smith", "emma@outlook.com")
    test("GDPR notice generates", result["status"] == "generated")
    test("GDPR cites Article 17", "Article 17" in result["notice_text"])

    # CCPA
    result = gen.generate("ccpa", "James Miller", "james@yahoo.com")
    test("CCPA notice generates", result["status"] == "generated")
    test("CCPA cites § 1798.105", "1798.105" in result["notice_text"])

    # Jurisdictions list
    jurisdictions = gen.get_jurisdictions()
    test("3 jurisdictions available", len(jurisdictions) == 3)


def test_audit_trail():
    section("6. Cryptographic Audit Trail")

    from backend.remediation.audit_crypto import AuditTrail

    trail = AuditTrail()

    # Genesis exists
    test("Genesis receipt exists", trail.get_count() == 1)

    # Add receipts
    r1 = trail.add("TEST_ACTION_1", {"key": "value1"})
    r2 = trail.add("TEST_ACTION_2", {"key": "value2"})
    test("Can add receipts", trail.get_count() == 3)

    # Verify chain
    verify = trail.verify_chain()
    test("Chain is valid", verify["chain_valid"])
    test("No breaks", len(verify["breaks"]) == 0)

    # Verify individual receipt
    test("Receipt hash verifies", r1.verify())
    test("Receipt has SHA-256 hash (64 chars)", len(r1.hash) == 64)

    # Chain linkage
    test("R2 references R1", r2.previous_hash == r1.hash)


def test_statutory_tracker():
    section("7. Statutory Compliance Tracker")

    from backend.remediation.statutory_tracker import StatutoryTracker

    tracker = StatutoryTracker()

    # Create request
    req = tracker.create_request("dpdp", "Acme Corp", "dpo@acme.com", "Aarav", "aarav@gmail.com", "REF-001", "hash123")
    test("Request created", req["status"] == "dispatched")
    test("Has request ID", req["request_id"].startswith("REQ-"))
    test("Has 30-day deadline", req["deadline_days"] == 30)
    test("Has milestones", len(req["milestones"]) >= 5)

    # Update status
    updated = tracker.update_status(req["request_id"], "acknowledged", "Company responded")
    test("Status update works", updated["status"] == "acknowledged")

    # Summary
    summary = tracker.get_summary()
    test("Summary counts requests", summary["total_requests"] == 1)

    # CCPA request with 45-day deadline
    ccpa = tracker.create_request("ccpa", "BigTech Inc", "privacy@bigtech.com", "James", "james@yahoo.com", "REF-002", "hash456")
    test("CCPA has 45-day deadline", ccpa["deadline_days"] == 45)


def test_scanners():
    section("8. Scanner Modules")

    from backend.scanners.hibp_scanner import HIBPScanner
    from backend.scanners.broker_scanner import BrokerScanner
    from backend.scanners.paste_scanner import PasteScanner

    # HIBP
    hibp = HIBPScanner()
    test(f"HIBP loaded {hibp.get_breach_count()} breaches", hibp.get_breach_count() >= 1000)
    result = hibp.scan("test@000webhost.com")
    test("HIBP scan returns results", result["status"] == "complete")

    # Broker
    broker = BrokerScanner()
    test(f"Broker loaded {broker.get_broker_count()} brokers", broker.get_broker_count() >= 900)
    result = broker.scan("Aarav Sharma", "aarav@gmail.com", "+91 9876543210", "Delhi")
    test("Broker scan returns matches", result["stats"]["potential_matches"] > 0)

    # Paste
    paste = PasteScanner()
    test(f"Paste loaded {paste.get_paste_count()} entries", paste.get_paste_count() >= 40)


def test_evidence_policy():
    """
    Guards the single most important promise this product makes: it does not
    claim a source holds your data unless it actually checked, or you said so.

    An earlier build synthesised breach membership — it picked real breach
    names at random and told the user they were in them. If that ever comes
    back, these fail.
    """
    section("9. Evidence Policy (anti-fabrication guarantees)")

    import backend.agent.tools as _tools_mod
    from backend.agent import verifiers

    test("Fabricated breach membership helper is gone",
         not hasattr(_tools_mod, "_simulated_breach_membership"))

    src = open(os.path.join(PROJECT_ROOT, "backend", "agent", "tools.py")).read()
    test("tools.py contains no simulated-membership code",
         "_simulated_breach_membership" not in src)

    # Without a subscription key the tool must say "not checked", never guess.
    ev = verifiers.check_hibp_account("someone@example.com", api_key="")
    test("HIBP account check without a key returns not_checked",
         ev.result == "not_checked")
    test("HIBP account check without a key claims nothing",
         ev.result != "hit" and "NOT CHECKED" in ev.interpretation)

    # k-anonymity: only a 5-character SHA-1 prefix may ever be transmitted.
    # This used to build the URL in the test body and then assert things about
    # the string it had just built — the product was never called, so it would
    # have held just as well if check_password_pwned had sent the whole hash,
    # or the password itself. The URL asserted on is now the one the function
    # actually handed to the network layer.
    import hashlib as _h
    pw = "correct horse battery staple"
    full = _h.sha1(pw.encode()).hexdigest().upper()

    sent = {}
    _real_get = verifiers._get

    def _capture(url, headers=None):
        sent["url"] = url
        sent["headers"] = headers or {}
        # One matching suffix line, so the "hit" branch is the one exercised.
        return _FakeResponse(f"{full[5:]}:42\r\n0000000000000000000000000000000000A:1\r\n")

    try:
        verifiers._get = _capture
        ev = verifiers.check_password_pwned(pw)
    finally:
        verifiers._get = _real_get

    test("Password check transmits only a 5-char SHA-1 prefix",
         sent["url"] == f"https://api.pwnedpasswords.com/range/{full[:5]}",
         f'transmitted {sent.get("url")!r}')
    test("Password check never puts the full hash in the URL",
         full[5:] not in sent["url"], f'transmitted {sent.get("url")!r}')
    test("Password check never transmits the password itself",
         pw not in sent["url"] and not any(pw in str(x) for x in sent["headers"].values()))
    test("The recorded endpoint is the URL that was actually queried",
         ev.endpoint == sent["url"], f"recorded {ev.endpoint!r}")
    test("A suffix match is reported as a hit", ev.result == "hit", f"got {ev.result}")
    test("A hit quotes the breach count it was given",
         "42" in ev.proof, f"proof was {ev.proof!r}")
    # The raw secret must not travel back out in the evidence either.
    test("The evidence record never contains the password",
         pw not in str(ev.to_dict()))

    # Every Evidence record must be able to justify itself — and must carry the
    # VALUES it was built with, not merely have the keys. asdict() on a
    # dataclass always returns every declared field, so a key-presence check
    # alone passes for an instance whose endpoint and proof are both empty.
    e = verifiers.Evidence("t", "x", "http://e", "now", 200, "hit", "p", "i", "cmd")
    d = e.to_dict()
    test("Evidence carries endpoint, proof and interpretation",
         all(k in d for k in ("endpoint", "proof", "interpretation", "queried_at",
                              "http_status", "result", "reproduce")))
    test("Evidence round-trips the values it was built with",
         (d["endpoint"], d["proof"], d["interpretation"], d["http_status"],
          d["result"], d["reproduce"]) == ("http://e", "p", "i", 200, "hit", "cmd"),
         f"got {d}")
    test("Evidence with no metadata still serialises a dict, never None",
         d["metadata"] == {}, f'got {d["metadata"]!r}')

    # A blank input must not produce a finding.
    test("Empty email yields not_checked, not a finding",
         verifiers.check_gravatar("").result == "not_checked")
    test("Empty password yields not_checked, not a finding",
         verifiers.check_password_pwned("").result == "not_checked")

    # A domain-level breach fact must never be phrased as a personal finding.
    cat = [{"name": "Adobe", "domain": "adobe.com"}]
    dom = verifiers.check_email_domain_breached("someone@adobe.com", cat)
    test("Domain breach is flagged as a hit on the DOMAIN",
         dom.result == "hit")
    test("Domain breach explicitly disclaims personal membership",
         "does not prove" in dom.interpretation.lower())

    # Re-scanning must not mint a second notice for the same record — that
    # would serve a controller two identical demands.
    import tempfile as _tf
    from backend.agent.memory import Memory as _Mem
    with _tf.TemporaryDirectory() as _d:
        _m = _Mem(os.path.join(_d, "t.db"))
        _uid = _m.upsert_user({"email": "dupe@example.com"})
        _rid = _m.create_request(_uid, "exp_1", {"jurisdiction": "dpdp", "deadline_days": 30,
                                                 "status": "awaiting_approval"})
        test("Open request is found for an exposure",
             (_m.open_request_for("exp_1") or {}).get("id") == _rid)
        _m.update_request(_rid, status="completed")
        test("Completed request no longer blocks a new draft",
             _m.open_request_for("exp_1") is None)

    # ── Removal strategy: a legal notice is the escalation, not the default ──
    from backend.agent.tools import find_playbook, load_playbooks
    from backend.agent import account_discovery as _ad

    pbs = load_playbooks()
    test("Removal playbooks load", len(pbs.get("playbooks", [])) >= 15)

    # Services with a delete button must NOT be routed to a statutory notice.
    for svc in ("Truecaller", "Naukri.com", "GitHub", "Chess.com"):
        pb = find_playbook(svc)
        test(f"{svc} routes to self-serve, not a legal notice",
             pb is not None and pb["method"] == "self_serve")

    # Every self-serve playbook must give the user somewhere to go and something to do.
    ss = [x for x in pbs["playbooks"] if x["method"] == "self_serve"]
    test("Every self-serve playbook has a URL and steps",
         all(x.get("url") and x.get("steps") for x in ss))
    test("Most services are self-serve, not litigation",
         len(ss) > len([x for x in pbs["playbooks"] if x["method"] == "statutory_notice"]))

    # Court records and statutory registers must never be routed to self-serve.
    for svc in ("Indian Kanoon", "MCA21 / Director Registry"):
        pb = find_playbook(svc)
        test(f"{svc} is marked not removable",
             pb is not None and pb["method"] == "not_removable")

    # ── Account discovery: no false positives ──
    test("Discovery site list is non-empty", len(_ad.SITES) >= 10)
    test("Every discovery site has a URL template and category",
         all("{u}" in v["url"] and v.get("category") for v in _ad.SITES.values()))

    # Sites that soft-404 would produce false positives; they must be excluded.
    for bad in ("Instagram", "Pinterest", "Medium", "PyPI"):
        test(f"{bad} is excluded from discovery (soft 404)",
             bad in _ad.EXCLUDED and bad not in _ad.SITES)
    test("Every exclusion records a reason",
         all(isinstance(v, str) and len(v) > 20 for v in _ad.EXCLUDED.values()))

    # A handle derived from an email IS searched, because refusing to look meant
    # a user who supplied only an address had zero sites checked and was told
    # nothing was found. Accuracy is protected at ATTRIBUTION, not by declining
    # to search: a guessed handle is tagged, and the clamp in discover_accounts
    # holds it at tier "candidate" unless the page carries a verified
    # identifier, so it is never counted as the user's data.
    profile = {"name": "Nalin Sharma", "email": "nalinchamp@gmail.com"}

    derived = _ad.derive_usernames(profile)
    test("A handle IS derived when none is declared (scan must not be empty)",
         [h for h, _ in derived] == ["nalinchamp"], f"got {derived}")
    test("No handle derived from an empty profile", _ad.derive_usernames({}) == [])

    d = _ad.derive_usernames({**profile, "known_usernames": "darkknight92, github:realhandle"})
    sources = {h: src for h, src in d}
    test("Declared handles are searched", sources.get("darkknight92") == "declared")
    test("Site-scoped handle is searched by its bare handle",
         sources.get("realhandle") == "declared")
    test("Declared handles are listed before guesses",
         [src for _, src in d][:2] == ["declared", "declared"], f"got {d}")
    test("Email local-part is tagged as a guess, not as declared",
         sources.get("nalinchamp") == "email_local")
    test("Name-derived handle is never searched", "nalinsharma" not in sources)

    # Guesses are tagged so they can never be promoted to a finding.
    opt = _ad.derive_usernames(profile, include_guessed=True)
    opt_src = {h: src for h, src in opt}
    test("Guessed handles are produced", len(opt) > 0)
    test("Email local-part is tagged as a guess", opt_src.get("nalinchamp") == "email_local")
    test("Name is never used to derive handles (zero collision risk)",
         "name_derived" not in set(opt_src.values()) and "nalinsharma" not in opt_src)
    test("Every guessed source is in the permanent-candidate set",
         all(src in _ad.GUESSED_SOURCES for _, src in opt))
    test("Handle count is bounded", len(opt) <= 12)
    test("Derived handles are plausible", all(3 <= len(h) <= 39 for h, _ in opt))

    # Opting out must still be possible, and must still search what was declared.
    off = _ad.derive_usernames({**profile, "known_usernames": "darkknight92"},
                               include_guessed=False)
    test("Guessing can be turned off", all(src == "declared" for _, src in off))
    test("Turning guessing off keeps declared handles",
         [h for h, _ in off] == ["darkknight92"], f"got {off}")

    # The Indian registry is a directory, not a set of findings.
    indian = _tools_mod.load_indian_sources()
    test("Indian source registry loads", len(indian) >= 20)
    test("Every Indian source carries a legal classification",
         all(s_.get("legal_class") for s_ in indian))
    test("Registry includes non-servable classes",
         any(s_["legal_class"] in ("judicial_record", "statutory_publication")
             for s_ in indian))


def test_attribution():
    """
    Guards against the worst failure this tool can have: telling someone a
    stranger's account is theirs, and then helping them demand its deletion.

    Measured before this layer existed: three common Indian names each produced
    THIRTEEN "your accounts", essentially none of them the right person.
    """
    section("10. Attribution (no stranger's account flagged as yours)")

    from backend.agent.attribution import (
        Identifiers, attribute_profile, username_risk, GENERIC_HANDLES)

    common = {"name": "Rahul Sharma", "email": "rahul.sharma@gmail.com",
              "phone": "+91 9876543210"}
    ident = Identifiers.from_profile(common)

    # A bare username match is a guess, never a finding.
    a = attribute_profile("rahulsharma", "a generic profile page", ident, site="GitHub")
    test("Username-only match is NOT attributed", not a.is_mine)
    test("Username-only match is a candidate", a.tier == "candidate")

    # Name on the page is still not enough — that is what collides.
    a = attribute_profile("rahulsharma", "Profile of Rahul Sharma", ident, site="GitHub")
    test("Full name on page alone is NOT attributed", not a.is_mine)

    # An UNVERIFIED identifier cannot promote a candidate on its own.
    a = attribute_profile("rahulsharma", "mail: rahul.sharma@gmail.com", ident, site="GitHub")
    test("Unverified email on page is NOT conclusive", not a.is_mine)

    # A VERIFIED identifier settles it.
    vid = Identifiers.from_profile(common, verified={"emails": ["rahul.sharma@gmail.com"],
                                                     "phones": []})
    a = attribute_profile("rahulsharma", "mail: rahul.sharma@gmail.com", vid, site="GitHub")
    test("Verified email on page IS attributed", a.is_mine)
    test("Verified email yields 'corroborated'", a.tier == "corroborated")

    vph = Identifiers.from_profile(common, verified={"emails": [], "phones": ["9876543210"]})
    a = attribute_profile("rahulsharma", "call 9876543210", vph, site="GitHub")
    test("Verified phone on page IS attributed", a.is_mine)

    # Generic handles identify nobody.
    g = attribute_profile("admin", "anything", ident, site="GitHub")
    test("Generic handle is rejected outright", g.tier == "rejected")
    test("Generic handle list is populated", len(GENERIC_HANDLES) >= 10)

    # A declared handle is a claim about a habit, not about every namespace.
    bare = Identifiers.from_profile({**common, "known_usernames": "rahulsharma"})
    a = attribute_profile("rahulsharma", "page", bare, site="SoundCloud")
    test("Declared common-name handle is NOT auto-attributed", not a.is_mine)

    scoped = Identifiers.from_profile({**common, "known_usernames": "github:rahulsharma"})
    a = attribute_profile("rahulsharma", "page", scoped, site="GitHub")
    test("Site-scoped handle IS attributed on that site", a.is_mine and a.tier == "proven")
    a = attribute_profile("rahulsharma", "page", scoped, site="SoundCloud")
    test("Site-scoped handle does NOT carry to other sites", not a.is_mine)

    # A distinctive declared handle is safe to accept.
    dist = Identifiers.from_profile({"name": "Nalin Sharma", "email": "t@x.com",
                                     "known_usernames": "darkknight92"})
    a = attribute_profile("darkknight92", "page", dist, site="GitHub")
    test("Distinctive declared handle IS attributed", a.is_mine)

    # A handle that is only a PART of the name — a surname, a forename — is not
    # distinctive. Millions share a surname, and treating one as settled
    # attributed a stranger's account on every site at once.
    for handle, who in (("torvalds", "surname"), ("linus", "forename")):
        part = Identifiers.from_profile({"name": "Linus Torvalds", "email": "t@x.com",
                                         "known_usernames": handle})
        a = attribute_profile(handle, "page", part, site="Roblox")
        test(f"Declared {who} handle is NOT auto-attributed", not a.is_mine, f"{handle} -> {a.tier}")
        test(f"Declared {who} handle is flagged high collision risk",
             username_risk(handle, part) == "high")

    # Scoping it still settles that one site — the escape hatch must survive.
    scoped_part = Identifiers.from_profile({"name": "Linus Torvalds", "email": "t@x.com",
                                            "known_usernames": "github:torvalds"})
    a = attribute_profile("torvalds", "page", scoped_part, site="GitHub")
    test("A scoped name-part handle IS attributed on that site",
         a.is_mine and a.tier == "proven")
    a = attribute_profile("torvalds", "page", scoped_part, site="Roblox")
    test("A scoped name-part handle does NOT carry elsewhere", not a.is_mine)

    # Collision risk must flag name-derived handles.
    test("Name-derived handle is high collision risk",
         username_risk("rahulsharma", ident) == "high")
    test("Handle with digits is low collision risk",
         username_risk("rahulsharma92", ident) == "low")
    test("Generic handle is flagged generic",
         username_risk("admin", ident) == "generic")

    # Sensitive values are hashed, never stored raw.
    si = Identifiers.from_profile({**common, "pan": "ABCPE1234F", "passport": "Z1234567"})
    test("Sensitive identifiers are hashed, not stored raw",
         all(len(h) == 64 for h in si.sensitive_hashes.values()))
    test("Raw sensitive values are absent from the object",
         "ABCPE1234F" not in str(si.__dict__))


def test_verification():
    """An identifier is not attribution-grade until ownership is demonstrated."""
    section("11. Identifier verification")

    from backend.agent.verification import Verifier, check_mx, normalise_phone
    import tempfile

    # MX check is real and catches typos / non-mail domains.
    test("Real domain is deliverable", check_mx("gmail.com")["deliverable"] is True)
    test("Invented domain is not deliverable",
         check_mx("nonexistent-zzqq123.invalid")["deliverable"] is False)
    test("Null-MX domain is not deliverable", check_mx("example.com")["deliverable"] is False)

    with tempfile.TemporaryDirectory() as d:
        v = Verifier(os.path.join(d, "v.db"))
        uid = "usr_attrib_test"

        test("Malformed email is rejected",
             v.request_code(uid, "email", "not-an-email")["status"] == "invalid")
        test("Undeliverable domain is rejected before sending",
             v.request_code(uid, "email", "x@nonexistent-zzqq123.invalid")["status"]
             == "undeliverable")

        r = v.request_code(uid, "email", "someone@gmail.com")
        test("Code is issued for a deliverable address", r["status"] in ("sent", "dev_mode"))
        test("Wrong code is refused",
             v.submit_code(uid, "email", "someone@gmail.com", "000000")["status"] == "incorrect")
        ok = v.submit_code(uid, "email", "someone@gmail.com", r["dev_code"])
        test("Correct code verifies the identifier", ok["status"] == "verified")

        # dev_mode delivered nothing, so it must NOT count as proof of ownership.
        test("dev_mode is NOT attribution-grade", ok["attribution_grade"] is False)
        test("dev_mode identifier is excluded from attribution set",
             v.attribution_grade(uid)["emails"] == [])

        test("Phone normalisation keeps 10 digits",
             normalise_phone("+91 98765 43210") == "9876543210")


def test_fiduciary_and_threat_surface():
    """Fiduciary directory resolution, breached entity legal rights under DPDP s.12, and threat surface mapping."""
    section("15. Fiduciary Directory & Threat Surface Intelligence")

    from backend.agent.fiduciary_directory import get_fiduciary_contact, is_darkweb_dump
    from backend.agent.memory import Memory
    from backend.agent.tools import build_tools, ToolContext
    import tempfile

    # 1. Directory resolution
    ij = get_fiduciary_contact("IIMjobs")
    test("IIMjobs resolves to Info Edge", "Info Edge" in ij.get("company_name", ""))
    test("IIMjobs resolves Grievance email", ij.get("dpo_email") == "grievance@iimjobs.com")
    test("IIMjobs has self-serve settings URL", "settings" in ij.get("self_serve_url", ""))

    zm = get_fiduciary_contact("Zomato")
    test("Zomato resolves Grievance email", zm.get("dpo_email") == "grievance@zomato.com")
    test("Zomato has self-serve privacy URL", "privacy" in zm.get("self_serve_url", ""))

    li = get_fiduciary_contact("LinkedIn")
    test("LinkedIn resolves DPO email", li.get("dpo_email") == "linkedin_dpo@linkedin.com")

    # 2. Dark-web dump classification
    test("Collection #1 is classified as dark-web dump", is_darkweb_dump("Collection #1") is True)
    test("Naz.API is classified as dark-web dump", is_darkweb_dump("Naz.API") is True)
    test("Zomato is NOT classified as dark-web dump", is_darkweb_dump("Zomato") is False)
    test("IIMjobs is NOT classified as dark-web dump", is_darkweb_dump("IIMjobs") is False)

    # 3. Legal assessment on breached operating company vs darkweb dump
    with tempfile.TemporaryDirectory() as d:
        from backend.mock_brokers.network import BrokerNetwork
        mem = Memory(os.path.join(d, "mem.db"))
        net = BrokerNetwork()
        uid = "usr_fiduciary_test"
        ctx = ToolContext(memory=mem, network=net, user_id=uid, run_id="run_1",
                          profile={"name": "Test User", "email": "test@example.com", "phone": "9811223344", "country": "IN"},
                          emit=lambda *a, **k: None)
        tools = build_tools(ctx)

        # Record an operating company breach
        e1_id, _ = mem.record_exposure(uid, "run_1", {
            "source_name": "IIMjobs", "source_type": "breach", "source_id": "breach:iimjobs",
            "data_found": ["Email addresses", "Passwords", "Resumes"], "severity": "high"
        })
        # Record a dark web paste dump
        e2_id, _ = mem.record_exposure(uid, "run_1", {
            "source_name": "Collection #1", "source_type": "breach", "source_id": "breach:collection1",
            "data_found": ["Email addresses", "Passwords"], "severity": "critical"
        })

        b1 = tools["determine_legal_basis"](e1_id)
        test("Operating company breach has erasure_available=True", b1["erasure_available"] is True)
        test("Operating company breach cites DPDP Act 2023 s.12", "DPDP" in b1["statute"])
        test("Operating company breach action is request_erasure", b1["recommended_action"] == "request_erasure")

        b2 = tools["determine_legal_basis"](e2_id)
        test("Dark web dump has erasure_available=False", b2["erasure_available"] is False)
        test("Dark web dump recommends secure_accounts", b2["recommended_action"] == "secure_accounts")

        # Playbook resolution for operating company breach
        p1 = tools["plan_removal"](e1_id)
        test("IIMjobs provides self_serve playbook", p1["method"] == "self_serve")
        test("IIMjobs playbook contains direct URL", "iimjobs.com" in p1["url"])

        # Statutory notice drafting for operating company
        draft = tools["draft_erasure_request"](e1_id)
        test("Statutory notice can be drafted for operating company breach", "request_id" in draft)
        test("Statutory notice names Info Edge", "info edge" in draft.get("request_text", "").lower() or "iimjobs" in draft.get("broker", "").lower())

        # Refusal to draft for dark web dump
        draft2 = tools["draft_erasure_request"](e2_id)
        test("Statutory notice refused for dark web dump", "error" in draft2)

        # Threat surface correlation
        ts = tools["analyze_threat_surface"]()
        test("Threat surface analysis identifies attack vectors", len(ts["threat_vectors"]) >= 1)
        test("Credential stuffing vector detected", any(v["vector"] == "Credential Stuffing & Account Takeover" for v in ts["threat_vectors"]))
        test("Overall surface grade is computed", ts["overall_surface_grade"] in ("ELEVATED", "MODERATE", "CRITICAL"))

        # Tool suite coverage.
        #
        # Pinning an exact count breaks every time a capability is added, and it
        # never said WHICH tools had to exist — the number could stay at 22 with
        # the wrong 22. What matters is that each phase of the loop is covered,
        # so the required names are asserted and the count is only a floor.
        REQUIRED_TOOLS = {
            # gather
            "build_identity_profile", "recall_prior_activity", "verify_breach_exposure",
            "discover_accounts", "search_open_web", "match_unique_identifiers",
            # judge
            "assess_exposure_risk", "determine_legal_basis", "plan_removal",
            # act — every outward action, each of which must be approval-gated
            "draft_erasure_request", "submit_erasure_request", "self_serve_removal",
            # verify
            "check_request_status", "verify_removal", "confirm_removal",
            "escalate_to_regulator",
        }
        missing = sorted(REQUIRED_TOOLS - set(tools))
        test("Every phase of the agent loop has its tools registered",
             not missing, f"missing: {missing}")
        test("Agent tool suite registers at least 22 tools",
             len(tools) >= 22, f"got {len(tools)}")

        # Deterministic discovery integration with threat surface
        from backend.agent.orchestrator import _run_deterministic_discovery
        # Mock network-bound discovery tools to ensure test isolation and sub-second execution
        fast_tools = dict(tools)
        fast_tools["search_open_web"] = lambda: {"confirmed": [], "search_degraded": False, "pages_fetched": 0}
        fast_tools["browse_indian_registry"] = lambda: {"total_scanned": 0, "categories": {}}
        d_summary = _run_deterministic_discovery(ctx, fast_tools)
        test("Deterministic discovery includes threat surface intelligence", "Threat surface analysis" in d_summary)
        test("Deterministic discovery captures attack vectors in summary", "attack vector" in d_summary)


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"\n{BOLD}{'═' * 60}{RESET}")
    print(f"{BOLD}  SovereignPrivacy AI — Automated Test Suite{RESET}")
    print(f"{BOLD}{'═' * 60}{RESET}")

    start = time.time()

    test_datasets()
    test_pii_recognizer()
    test_identity_resolver()
    test_risk_calculator()
    test_legal_notices()
    test_audit_trail()
    test_statutory_tracker()
    test_scanners()
    test_evidence_policy()
    test_attribution()
    test_verification()
    test_open_web_search()
    test_free_intel()
    test_site_roster()
    test_fiduciary_and_threat_surface()

    elapsed = time.time() - start

    print(f"\n{BOLD}{'═' * 60}{RESET}")
    total = passed + failed
    if failed == 0:
        print(f"  {GREEN}{BOLD}ALL {total} TESTS PASSED{RESET} in {elapsed:.2f}s")
    else:
        print(f"  {GREEN}{passed} passed{RESET}  {RED}{failed} failed{RESET}  ({total} total) in {elapsed:.2f}s")

    print(f"{BOLD}{'═' * 60}{RESET}\n")

    sys.exit(1 if failed > 0 else 0)
