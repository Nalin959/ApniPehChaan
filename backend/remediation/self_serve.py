"""
self_serve.py — Get the user out without a lawyer, and without lying about it.

WHY THIS EXISTS
---------------
The rest of this project is built around the statutory route: find the exposure,
establish the legal basis, serve a notice, wait 30 days. That route works, and
for a credit bureau or a court record it is the only route there is. But it is
wildly disproportionate for the ordinary case, which is a marketing list or a
dormant profile with a delete button on it. Escalating those to a legal notice
wastes the user's month and teaches them the tool cries wolf.

So this module handles the other end of the scale: the removals that need no
lawyer, no waiting, and — in one genuine case — no user at all.

WHAT THIS CAN ACTUALLY AUTOMATE, AND WHAT IT CANNOT
---------------------------------------------------
Read this part before wiring anything up, because the honest boundary here is
narrow and the temptation to overstate it is strong.

CAN be automated, end to end, by this module:

  * RFC 8058 one-click unsubscribe. Marketing mail is required to carry a
    List-Unsubscribe header, and mail that opts into RFC 8058 also carries
    List-Unsubscribe-Post: List-Unsubscribe=One-Click. That combination is a
    standing, pre-authorised invitation to unsubscribe with a single unauthen-
    ticated POST. No login, no session, no credentials — the opaque token in
    the URL *is* the authorisation. This is the real thing, and it is the
    strongest automation in this file.

CANNOT be automated, and is deliberately not attempted:

  * Logging into a third-party service as the user and clicking "delete my
    account". Doing that needs the user's password and a live authenticated
    session for a site we do not control. To build it, this tool would have to
    ask people to hand over their credentials — a privacy product standing up a
    credential-harvesting flow, which is indefensible whatever the intent, and
    which would also break the moment the site ships MFA or changes a selector.
    It is not built here, it is not faked here, and no function in this module
    will ever claim an account was deleted when what actually happened is that
    a link was printed. `resolve_route(...).automation` says "deep_link" for
    exactly this reason: the *service* is self-serve, WE are not.

  * Anything on a site that has no deletion route at all. A court judgment, a
    statutory register, a credit bureau record — the playbook marks these
    `not_removable` and the honest answer is to say so, not to invent a form.

So for everything short of one-click unsubscribe, the deliverable is the thing
the user actually asked for: the EXACT deep link to the deletion page — the
settings URL, not the homepage — plus the ordered steps once they land there.

NOTHING HERE FIRES ON IMPORT
----------------------------
Unsubscribing is an outward, irreversible act against a third party: it tells a
sender something about the user, and it cannot be taken back. So no unsubscribe
happens on import, on construction, or as a side effect of planning one.
`plan_unsubscribe()` is pure and touches no network — call it, show the user
what would be sent and to whom, and only after they approve call
`unsubscribe_one_click()`, which is the single function in this file that
reaches out.

Route resolution and URL verification are read-only and safe to call freely.
"""

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone

from backend.agent import account_discovery as _ad
# The SSRF guard is imported, never reimplemented. An unsubscribe URL is
# attacker-supplied by definition — it arrives in a header of an email anyone
# could have sent — so it is precisely the input that must not be allowed to
# aim a POST at 127.0.0.1 or a cloud metadata endpoint. web_search.py already
# had that hole found and fixed, and importing it also installs the redirect
# handler that re-checks every hop, which matters here because the unsubscribe
# endpoint is free to 302 us anywhere it likes.
from backend.agent.web_search import is_safe_web_url

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
TIMEOUT = 15

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLAYBOOKS_PATH = os.path.join(PROJECT_ROOT, "data", "removal_playbooks.json")

# RFC 8058 §3.1 fixes the request body exactly. It is a constant, not a
# template, and that is a safety property worth stating out loud: there is no
# parameter anywhere in this module that can put the user's Aadhaar, PAN,
# password or card number into an outbound unsubscribe request, because the
# body never varies and nothing of the user's is ever appended to it. The only
# user-derived value transmitted is the opaque token the sender themselves put
# in the URL they mailed to the user.
ONE_CLICK_BODY = b"List-Unsubscribe=One-Click"
ONE_CLICK_CONTENT_TYPE = "application/x-www-form-urlencoded"

# Which playbook methods mean "the user can finish this themselves today".
_SELF_SERVE_METHODS = {"self_serve", "privacy_form"}
# Which mean there is nobody to ask, so no link will help.
_TERMINAL_METHODS = {"not_removable", "statutory_only"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── playbook loading ─────────────────────────────────────────────────────────
# tools.py already has load_playbooks()/find_playbook(), but it is NOT imported
# here. tools.py pulls in the recognizer, the resolver, the broker network and
# the notice generator at module scope, and it is the module that will import
# THIS one once the route resolver is wired in — importing it back would close
# a cycle. Re-reading a small JSON file is the cheaper mistake.

_playbooks_cache: dict | None = None


def load_playbooks(refresh: bool = False) -> dict:
    """The removal playbook table: how to actually get removed, per service."""
    global _playbooks_cache
    if _playbooks_cache is not None and not refresh:
        return _playbooks_cache
    try:
        with open(PLAYBOOKS_PATH) as f:
            _playbooks_cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _playbooks_cache = {"playbooks": [], "method_order": [], "method_info": {}}
    return _playbooks_cache


def _normalise_service(raw: str) -> str:
    """
    Reduce a service name or a domain to a comparable token.

    Callers hand this module whatever they happen to be holding: an exposure's
    source name ("Flickr"), a bare domain ("www.flickr.com"), or a full URL
    ("https://www.flickr.com/people/x"). All three must find the same playbook,
    so the host is extracted, www/m prefixes are dropped, and the public suffix
    is trimmed to leave the registrable name.
    """
    s = (raw or "").strip().lower()
    if not s:
        return ""
    if "://" in s:
        s = urllib.parse.urlparse(s).hostname or s
    s = s.split("/")[0]
    for prefix in ("www.", "m.", "in."):
        if s.startswith(prefix):
            s = s[len(prefix):]
    # Trim a trailing public suffix so "flickr.com" and "hirist.tech" both
    # reduce to their brand token. Two-part suffixes (.co.in, .gov.in) are
    # handled first so "dominos.co.in" does not reduce to "co".
    for suffix in (".co.in", ".gov.in", ".org.in", ".net.in", ".ac.in"):
        if s.endswith(suffix):
            return s[: -len(suffix)]
    if "." in s:
        s = s.rsplit(".", 1)[0]
    return s


# ── data returned to callers ─────────────────────────────────────────────────

@dataclass
class RemovalRoute:
    """The best available way out of one service, with its honest limits."""
    service: str
    matched: bool
    playbook_id: str
    method: str                 # self_serve | privacy_form | email_request | …
    method_label: str           # user-facing label from method_info
    method_why: str
    typical_time: str
    url: str
    is_deep_link: bool          # False means the URL is only a homepage
    steps: list[str] = field(default_factory=list)
    effort_minutes: int = 0
    escalation: str = ""
    legal_class: str = ""
    # What THIS TOOL can do, as opposed to what the service offers.
    automation: str = "none"    # one_click_post | deep_link | none
    confidence: str = "none"    # high | medium | none
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class UnsubscribePlan:
    """What an unsubscribe WOULD do. Produced without touching the network."""
    eligible: bool              # True only if a compliant one-click POST is possible
    action: str                 # one_click_post | open_link | send_mail | none
    target: str                 # the URL that would be POSTed, or opened, or mailed
    http_urls: list[str] = field(default_factory=list)
    mailto_urls: list[str] = field(default_factory=list)
    reason: str = ""
    reproduce: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class UnsubscribeOutcome:
    """What an unsubscribe actually did."""
    attempted: bool
    action: str
    target: str
    http_status: int | None
    succeeded: bool
    detail: str
    reproduce: str
    checked_at: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RemovalCheck:
    """Whether a profile that was deleted has actually gone."""
    url: str
    http_status: int | None
    still_present: bool
    removed: bool
    confidence: str             # high | low
    detail: str
    reproduce: str
    checked_at: str

    def to_dict(self) -> dict:
        return asdict(self)


# ── 1. one-click unsubscribe (RFC 2369 + RFC 8058) ───────────────────────────

def parse_list_unsubscribe(header: str) -> list[str]:
    """
    Pull the URIs out of a List-Unsubscribe header (RFC 2369 §3.2).

    The angle brackets are not decoration and are not optional — they are the
    only safe delimiter. Splitting the header on commas looks equivalent and is
    not: unsubscribe URLs routinely carry commas inside a base64 or JSON token,
    and a comma split would tear one URL into two malformed ones, then POST at
    whatever the first fragment happened to parse as.
    """
    return [m.group(1).strip() for m in re.finditer(r"<([^>]+)>", header or "")]


def supports_one_click(list_unsubscribe: str, list_unsubscribe_post: str | None) -> bool:
    """
    True only when the sender has opted into RFC 8058.

    This gate is the whole protocol. A List-Unsubscribe URL on its own (RFC
    2369) is a link for a human to click, and it may well be a GET that a link
    scanner or a prefetching proxy will hit by accident — which is exactly why
    RFC 8058 exists and why unsubscribing must never be inferred from the plain
    header. Only List-Unsubscribe-Post: List-Unsubscribe=One-Click is the
    sender saying "an unauthenticated POST from software is what I want".
    """
    if not list_unsubscribe or not list_unsubscribe_post:
        return False
    flat = re.sub(r"\s+", "", list_unsubscribe_post).lower()
    if "list-unsubscribe=one-click" not in flat:
        return False
    return any(u.lower().startswith(("http://", "https://"))
               for u in parse_list_unsubscribe(list_unsubscribe))


def _pick_http_target(uris: list[str]) -> str:
    """Prefer https, then http. An unsubscribe over plain http leaks the token."""
    https = [u for u in uris if u.lower().startswith("https://")]
    if https:
        return https[0]
    http = [u for u in uris if u.lower().startswith("http://")]
    return http[0] if http else ""


def plan_unsubscribe(list_unsubscribe: str,
                     list_unsubscribe_post: str | None = None) -> UnsubscribePlan:
    """
    Work out what unsubscribing would involve. Performs NO network I/O.

    Call this first, show the result to the user, and only call
    unsubscribe_one_click() once they have approved it.
    """
    uris = parse_list_unsubscribe(list_unsubscribe)
    http_urls = [u for u in uris if u.lower().startswith(("http://", "https://"))]
    mailto_urls = [u for u in uris if u.lower().startswith("mailto:")]

    if not uris:
        return UnsubscribePlan(
            eligible=False, action="none", target="",
            reason="No List-Unsubscribe header, or none that contained a URI in "
                   "angle brackets. There is no unsubscribe route in this mail.")

    target = _pick_http_target(http_urls)

    # An unsubscribe URL is attacker-controlled input. Refuse a private target
    # before it is ever shown to the user, let alone POSTed to.
    if target and not is_safe_web_url(target):
        return UnsubscribePlan(
            eligible=False, action="none", target=target,
            http_urls=http_urls, mailto_urls=mailto_urls,
            reason="The unsubscribe URL resolves to a loopback, private or reserved "
                   "address, so it was refused and nothing was sent. A genuine "
                   "sender's unsubscribe endpoint is on the public internet. (If "
                   "this fires on a host that is plainly public, suspect the "
                   "resolver rather than the sender — see the NAT64 note on "
                   "verify_removal — and open the link by hand.)")

    if supports_one_click(list_unsubscribe, list_unsubscribe_post) and target:
        return UnsubscribePlan(
            eligible=True, action="one_click_post", target=target,
            http_urls=http_urls, mailto_urls=mailto_urls,
            reason="The sender advertises RFC 8058 one-click unsubscribe. A single "
                   "POST completes it — no login, no reply, nothing further from you.",
            reproduce=f"curl -s -i -X POST -H 'Content-Type: {ONE_CLICK_CONTENT_TYPE}' "
                      f"--data '{ONE_CLICK_BODY.decode()}' '{target}'")

    if target:
        return UnsubscribePlan(
            eligible=False, action="open_link", target=target,
            http_urls=http_urls, mailto_urls=mailto_urls,
            reason="This mail carries an unsubscribe link but does NOT advertise "
                   "List-Unsubscribe-Post, so it is not one-click. It has to be "
                   "opened in a browser: POSTing to it unasked is outside the "
                   "standard, and the link may be a GET that confirms nothing.")

    if mailto_urls:
        return UnsubscribePlan(
            eligible=False, action="send_mail", target=mailto_urls[0],
            http_urls=http_urls, mailto_urls=mailto_urls,
            reason="The only unsubscribe route offered is by email. This module "
                   "does not send mail, so the address is handed back for the "
                   "mail client (or the statutory notice path) to use.")

    return UnsubscribePlan(
        eligible=False, action="none", target="",
        http_urls=http_urls, mailto_urls=mailto_urls,
        reason="The List-Unsubscribe header contained no usable http(s) or mailto URI.")


def unsubscribe_one_click(list_unsubscribe: str,
                          list_unsubscribe_post: str | None = None,
                          timeout: int = TIMEOUT) -> UnsubscribeOutcome:
    """
    Perform the RFC 8058 one-click unsubscribe. OUTWARD AND IRREVERSIBLE.

    This is the only function in this module that acts on the world, and the
    caller must only reach it after the user has approved the plan returned by
    plan_unsubscribe(). It refuses to POST unless the sender advertised
    List-Unsubscribe-Post, and it refuses any target that is not a public
    address.

    A 2xx means the sender accepted the request. It does not mean every list
    they run has dropped the address — that is the sender's obligation, not an
    observable fact — so the outcome says "accepted", never "erased".
    """
    plan = plan_unsubscribe(list_unsubscribe, list_unsubscribe_post)
    if not plan.eligible:
        # Not a failure: it is the correct, standard-respecting refusal. The
        # caller still gets the URL so the user can finish it by hand.
        return UnsubscribeOutcome(
            attempted=False, action=plan.action, target=plan.target,
            http_status=None, succeeded=False, detail=plan.reason,
            reproduce=plan.reproduce, checked_at=_now())

    req = urllib.request.Request(
        plan.target, data=ONE_CLICK_BODY, method="POST",
        headers={"Content-Type": ONE_CLICK_CONTENT_TYPE,
                 "User-Agent": UA,
                 "Content-Length": str(len(ONE_CLICK_BODY))})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        status = getattr(resp, "status", getattr(resp, "code", None))
        resp.read(2048)
        ok = status is not None and 200 <= status < 300
        detail = ("The sender accepted the unsubscribe request. Marketing mail "
                  "should stop; if it does not, that is fresh processing after "
                  "withdrawal of consent and escalates to a DPDP s.12 notice."
                  if ok else
                  f"The unsubscribe endpoint answered HTTP {status}, which is not "
                  f"an acceptance. Open the link by hand to finish it.")
    except urllib.error.HTTPError as e:
        status, ok = e.code, False
        detail = (f"The unsubscribe endpoint answered HTTP {e.code}. Some senders "
                  f"reject automated POSTs despite advertising one-click; open the "
                  f"link by hand.")
    except Exception as e:
        status, ok = None, False
        detail = (f"The unsubscribe endpoint could not be reached "
                  f"({type(e).__name__}). Nothing was changed; open the link by hand.")

    return UnsubscribeOutcome(
        attempted=True, action="one_click_post", target=plan.target,
        http_status=status, succeeded=ok, detail=detail,
        reproduce=plan.reproduce, checked_at=_now())


# ── 2. route resolution ──────────────────────────────────────────────────────

def _match_playbook(*names: str) -> tuple[dict | None, str]:
    """
    Find the playbook for a service. Returns (playbook, confidence).

    Exact id/service equality is "high". A substring match is "medium", because
    it is a guess that happens to be right most of the time and the user should
    be told which kind of answer they are getting.
    """
    pbs = load_playbooks().get("playbooks", [])
    tokens = [t for t in ((n or "").strip().lower() for n in names) if t]
    norms = [_normalise_service(n) for n in names]
    norms = [n for n in norms if n]

    for needle in tokens + norms:
        for pb in pbs:
            if needle in (pb["id"].lower(), pb["service"].lower()):
                return pb, "high"
    for needle in tokens + norms:
        for pb in pbs:
            if needle and (needle in pb["service"].lower() or pb["id"].lower() == needle):
                return pb, "medium"
    # Last resort: the playbook id appears inside the supplied name, which is
    # how "Naukri.com job portal" finds "naukri".
    for needle in tokens:
        for pb in pbs:
            if len(pb["id"]) >= 4 and pb["id"].lower() in needle:
                return pb, "medium"
    return None, "none"


def _is_deep_link(url: str) -> bool:
    """
    Does this URL point at a page, or merely at a front door?

    The user asked for the exact deletion link, so "we only have the homepage"
    is a fact the UI has to be able to state rather than paper over.
    """
    try:
        p = urllib.parse.urlparse(url)
    except Exception:
        return False
    return bool(p.path.strip("/") or p.query)


def resolve_route(service: str, *aliases: str) -> RemovalRoute:
    """
    Best available removal route for a service. Read-only; no network.

    `service` may be a display name ("Flickr"), a domain ("flickr.com") or a
    profile URL — all three resolve to the same playbook.
    """
    pb, confidence = _match_playbook(service, *aliases)
    info = load_playbooks().get("method_info", {})

    if pb is None:
        return RemovalRoute(
            service=service, matched=False, playbook_id="", method="",
            method_label="No playbook", method_why="", typical_time="",
            url="", is_deep_link=False, confidence="none", automation="none",
            note=("No removal playbook covers this service, so no deletion link can "
                  "be given for it. Guessing a settings URL would be worse than "
                  "saying nothing: a dead link wastes the user's time and implies "
                  "a route that may not exist. The statutory path still applies."))

    method = pb.get("method", "")
    mi = info.get(method, {})
    deep = _is_deep_link(pb.get("url", ""))

    if method in _SELF_SERVE_METHODS:
        automation = "deep_link"
        note = ("This service lets the user delete the data themselves. The agent "
                "cannot click it for them — that would need their password and a "
                "logged-in session on a site we do not control — so what is "
                "automated is finding the exact page and the order of the steps.")
        if not deep:
            note += (" Only the service homepage is known for this one; no deeper "
                     "settings URL has been verified, so follow the steps from there.")
    elif method in _TERMINAL_METHODS:
        automation = "none"
        note = ("There is no deletion route here at all — the record is a statutory "
                "or licensed one. The link is the source, not a way out of it.")
    elif method == "credential_rotation":
        automation = "none"
        note = ("Nothing can be erased here: the data came off the user's own "
                "machine, so there is no controller to serve. The work is rotating "
                "credentials and revoking sessions, urgently.")
    else:
        automation = "none"
        note = ("This one needs a written request to the service. The link is the "
                "page that route starts from — usually where the grievance-officer "
                "address is published, sometimes a settings page where the content "
                "can be stripped first. The agent can draft the request but cannot "
                "submit it on the user's behalf.")

    return RemovalRoute(
        service=pb.get("service", service), matched=True, playbook_id=pb.get("id", ""),
        method=method, method_label=mi.get("label", method),
        method_why=mi.get("why", ""), typical_time=mi.get("typical_time", ""),
        url=pb.get("url", ""), is_deep_link=deep,
        steps=list(pb.get("steps", [])), effort_minutes=pb.get("effort_minutes", 0),
        escalation=pb.get("escalation", ""), legal_class=pb.get("legal_class", ""),
        automation=automation, confidence=confidence, note=note)


def resolve_routes(services: list[str]) -> list[RemovalRoute]:
    """Resolve several services at once, self-serve routes first."""
    order = load_playbooks().get("method_order", [])

    def rank(r: RemovalRoute) -> tuple:
        try:
            return (0, order.index(r.method))
        except ValueError:
            return (1, 0)

    return sorted((resolve_route(s) for s in services), key=rank)


# ── 3. verifying the deletion actually happened ──────────────────────────────

def verify_removal(url: str, site: str = "", username: str = "",
                   timeout: int = _ad.TIMEOUT) -> RemovalCheck:
    """
    After a deletion, check whether the public profile has actually gone.

    account_discovery already solved the hard half of this and its rule is
    reused rather than rewritten: only a clean HTTP 200 counts as "the profile
    is still there", and every site in its SITES table was empirically tested
    against a username known to exist AND one known not to, so that a 404 from
    it really does mean gone.

    That empirical grounding is why confidence is reported. When `site` names a
    site from that table, the check runs through account_discovery's own
    checker and the answer is "high" confidence. For any other URL the status
    code is reported honestly but marked "low", because plenty of sites serve
    200 with a soft-404 or a login wall — and on this project a confident wrong
    answer is the failure mode that matters.
    """
    # Reuse the verified path wherever the site is one account_discovery knows.
    if site and site in _ad.SITES and username:
        hit, _body = _ad._check_one(site, _ad.SITES[site], username)
        return RemovalCheck(
            url=hit.url, http_status=hit.http_status, still_present=hit.exists,
            removed=not hit.exists, confidence="high",
            detail=("The profile still resolves, so the deletion has not taken "
                    "effect yet — some services queue it for days."
                    if hit.exists else
                    f"{site} no longer serves this profile (HTTP "
                    f"{hit.http_status}). This site was verified to return 404 "
                    f"for handles that do not exist, so this is a real removal."),
            reproduce=hit.reproduce, checked_at=hit.checked_at)

    # Fail closed: if the guard will not vouch for the destination, report
    # "unknown" — never "removed". still_present and removed are BOTH False
    # here on purpose, because a refusal is the absence of an answer, and this
    # project would rather say nothing than say something wrong.
    #
    # Known false refusal, worth recognising rather than debugging twice: on a
    # NAT64/DNS64 network the resolver synthesises IPv6 addresses in
    # 64:ff9b::/96, which Python's ipaddress reports as is_reserved, so
    # is_safe_web_url rejects perfectly public hosts (github.com, keybase.io,
    # soundcloud.com and wordpress.com all fail here). That is a bug in the
    # shared guard in web_search.py, not in this call — and it is not patched
    # around locally, because quietly loosening an SSRF check that another
    # module owns is how the hole gets reopened.
    if not is_safe_web_url(url):
        return RemovalCheck(
            url=url, http_status=None, still_present=False, removed=False,
            confidence="low",
            detail="The URL was refused as not-public by the shared SSRF guard, so "
                   "nothing was fetched and the removal is UNKNOWN — not confirmed "
                   "and not denied. On a NAT64 network this can misfire on a genuine "
                   "public host; check the URL by hand in that case.",
            reproduce=f"curl -sI '{url}'", checked_at=_now())

    reproduce = f"curl -sI -A '{UA[:24]}...' '{url}'"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        resp = urllib.request.urlopen(req, timeout=timeout)
        status = getattr(resp, "status", getattr(resp, "code", None))
        resp.read(512)
    except urllib.error.HTTPError as e:
        status = e.code
    except Exception:
        status = None

    still = status == 200
    if still:
        detail = ("The page still returns 200. That may mean the profile survives, "
                  "or it may be a login wall or a soft-404 — this host has not been "
                  "verified to distinguish the two, so treat it as unconfirmed.")
    elif status in (404, 410):
        detail = f"The page is gone (HTTP {status}), which is consistent with deletion."
    elif status is None:
        detail = "The page could not be fetched, which proves nothing either way."
    else:
        detail = (f"The page answered HTTP {status}. Not a 200, but not a clean 404 "
                  f"either — a block or a redirect, so the removal is unconfirmed.")

    return RemovalCheck(
        url=url, http_status=status, still_present=still,
        removed=status in (404, 410), confidence="low", detail=detail,
        reproduce=reproduce, checked_at=_now())


# ── demo ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Deliberately exercises ONLY the read-only half. No unsubscribe is sent
    # from here: that is an outward act and it needs a real user's approval on
    # a real message, not a demo block.
    print("=" * 74)
    print("ROUTE RESOLVER — what the agent can actually do per service")
    print("=" * 74)

    for name in ("Flickr", "flickr.com", "GitHub", "Naukri.com",
                 "https://www.behance.net/someone", "Truecaller",
                 "Indian Kanoon", "CIBIL / Experian / Equifax", "Instructables",
                 "infostealer", "Some Service That Does Not Exist"):
        r = resolve_route(name)
        print(f"\n  {name}")
        print(f"    method      : {r.method or '—'}  ({r.method_label})")
        print(f"    automation  : {r.automation}   confidence: {r.confidence}")
        print(f"    url         : {r.url or '—'}"
              f"{'' if r.is_deep_link or not r.url else '   [HOMEPAGE ONLY]'}")
        if r.steps:
            print(f"    first step  : {r.steps[0][:96]}")
        print(f"    note        : {r.note[:110]}…")

    print("\n" + "=" * 74)
    print("UNSUBSCRIBE PLANNER — dry run only, nothing is sent")
    print("=" * 74)

    cases = [
        ("RFC 8058 one-click",
         "<https://example.com/u/abc123>, <mailto:unsub@example.com>",
         "List-Unsubscribe=One-Click"),
        ("link only, no -Post header",
         "<https://example.com/u/abc123>", None),
        ("mailto only",
         "<mailto:unsub@example.com?subject=unsubscribe>", "List-Unsubscribe=One-Click"),
        ("SSRF attempt via one-click",
         "<http://127.0.0.1:8080/admin>", "List-Unsubscribe=One-Click"),
        ("no header at all", "", None),
    ]
    for label, lu, lup in cases:
        p = plan_unsubscribe(lu, lup)
        print(f"\n  {label}")
        print(f"    eligible : {p.eligible}    action: {p.action}")
        print(f"    target   : {p.target or '—'}")
        print(f"    reason   : {p.reason[:100]}…")

    print()
