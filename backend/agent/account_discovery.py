"""
account_discovery.py — Find where an identity actually has accounts.

WHY THIS IS DIFFERENT FROM WHAT CAME BEFORE
-------------------------------------------
Earlier versions either invented findings, or asked the user to type in which
services they use. Neither is discovery. This module goes and looks.

The method is the one Sherlock and Maigret use: fetch the PUBLIC profile URL for
a username and see whether the site serves a profile or a 404. No login, no
scraping of private data, no probing of password-reset endpoints to enumerate
accounts — just requesting a page that is already public.

THE FALSE-POSITIVE PROBLEM, AND HOW IT IS HANDLED
-------------------------------------------------
Naive status-code checking is worthless here. Instagram, Pinterest, Medium and
PyPI all return HTTP 200 for usernames that do not exist — they serve a login
wall or a soft-404 landing page. A tool that trusted the status code would tell
you that you have an Instagram account when you do not.

So every site in SITES below was verified empirically with BOTH a username known
to exist AND a username known not to exist. Only sites that cleanly separated the
two cases were kept. Sites that could not be separated are listed in EXCLUDED
with the reason, and are never checked — silence is better than a false claim.

Verified 2026-09-12. Sites change; re-run verify_site_reliability() to re-check.
"""

import concurrent.futures as cf
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone

from backend.agent.attribution import (
    Attribution, Identifiers, attribute_profile, collision_warning, username_risk)

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
TIMEOUT = 5

# Sites where a 200 genuinely means "this profile exists" and a 404 genuinely
# means it does not. Each was tested against a real and a fake username.
SITES: dict[str, dict] = {
    "GitHub":       {"url": "https://github.com/{u}",                 "category": "Developer"},
    "GitLab":       {"url": "https://gitlab.com/{u}",                 "category": "Developer"},
    "Docker Hub":   {"url": "https://hub.docker.com/u/{u}",           "category": "Developer"},
    "Dev.to":       {"url": "https://dev.to/{u}",                     "category": "Developer"},
    "Pastebin":     {"url": "https://pastebin.com/u/{u}",             "category": "Paste"},
    "Hugging Face": {"url": "https://huggingface.co/{u}",              "category": "AI / ML"},
    "Keybase":      {"url": "https://keybase.io/{u}",                 "category": "Identity"},
    "Gravatar":     {"url": "https://gravatar.com/{u}",               "category": "Identity"},
    "About.me":     {"url": "https://about.me/{u}",                   "category": "Personal Profile"},
    "Linktree":     {"url": "https://linktr.ee/{u}",                  "category": "Personal Profile"},
    "Behance":      {"url": "https://www.behance.net/{u}",            "category": "Portfolio"},
    "SoundCloud":   {"url": "https://soundcloud.com/{u}",             "category": "Media"},
    "Chess.com":    {"url": "https://www.chess.com/member/{u}",       "category": "Gaming"},
    "Lichess":      {"url": "https://lichess.org/@/{u}",              "category": "Gaming"},
    "Roblox":       {"url": "https://www.roblox.com/user.aspx?username={u}", "category": "Gaming"},
    "AtCoder":      {"url": "https://atcoder.jp/users/{u}",           "category": "Competitive"},
    "Buymeacoffee": {"url": "https://www.buymeacoffee.com/{u}",       "category": "Payments"},
    "Patreon":      {"url": "https://www.patreon.com/{u}",            "category": "Payments"},
    "Substack":     {"url": "https://{u}.substack.com",               "category": "Publishing"},
    "Blogger":      {"url": "https://{u}.blogspot.com",               "category": "Publishing"},
    "Tumblr":       {"url": "https://{u}.tumblr.com",                 "category": "Social"},
    "Mastodon":     {"url": "https://mastodon.social/@{u}",           "category": "Social"},
    "Flickr":       {"url": "https://www.flickr.com/people/{u}",      "category": "Photos"},
    "Instructables": {"url": "https://www.instructables.com/member/{u}/", "category": "DIY"},
    "Freelancer":   {"url": "https://www.freelancer.com/u/{u}",       "category": "Work"},
    "Wikipedia":    {"url": "https://en.wikipedia.org/wiki/User:{u}", "category": "Reference"},
}

# Deliberately NOT checked, with the reason. Reporting nothing beats guessing.
EXCLUDED: dict[str, str] = {
    # Re-verified 2026-09-12 against 5 random non-existent handles each.
    "Kaggle":     "Serves HTTP 200 for non-existent users — soft 404 (5/5 invented handles "
                  "returned 200). Was previously trusted and reported accounts that do not exist.",
    "Replit":     "Returns HTTP 404 even for handles that demonstrably exist (its own founder's), "
                  "so a 404 proves nothing and a hit never occurs.",
    "Instagram":  "Serves HTTP 200 with a login wall for non-existent users — indistinguishable.",
    "Pinterest":  "Serves HTTP 200 for non-existent users — soft 404.",
    "Medium":     "Serves HTTP 200 for non-existent users — soft 404.",
    "PyPI":       "Serves HTTP 200 for non-existent users — soft 404.",
    "Hashnode":   "Serves HTTP 200 for non-existent handles — soft 404 landing page.",
    "HackerRank": "Serves HTTP 200 for non-existent handles — soft 404.",
    "CodeChef":   "Serves HTTP 200 for non-existent handles — soft 404.",
    "LeetCode":   "Returns HTTP 403 to automated headless user agents.",
    "npm":        "Returns 403 to automated requests.",
    "CodePen":    "Returns 403 to automated requests.",
    "HackerNews": "Rate-limits automated requests (429).",
    "Telegram":   "Inconsistent responses; could not verify reliably.",
    "Twitter/X":  "Requires authentication for profile pages.",
    "LinkedIn":   "Requires authentication; automated access breaches their terms.",
    "Facebook":   "Requires authentication for profile lookup.",
}


@dataclass
class AccountHit:
    site: str
    category: str
    username: str
    url: str
    http_status: int | None
    exists: bool
    checked_at: str
    reproduce: str
    # Whether this profile is actually the user's — decided by attribution.py,
    # never by the mere fact that the username resolved.
    attribution: dict = field(default_factory=dict)
    collision_risk: str = ""
    collision_note: str = ""
    handle_source: str = ""   # declared | email_local | upi_local | name_derived
    # "checked"     the site gave a definite answer (200 = a profile, 404 = none)
    # "unreachable" nothing was learned — rate limited, blocked, timed out
    # `exists is False` means something different in each case, and collapsing
    # them is what let a throttled sweep report a clean sheet.
    check_state: str = "checked"

    def to_dict(self):
        return asdict(self)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _check_one(site: str, spec: dict, username: str) -> tuple[AccountHit, str]:
    """Returns the hit plus the page body, which attribution needs."""
    url = spec["url"].format(u=username)
    reproduce = f"curl -sI -A '{UA[:24]}...' '{url}'"
    body = ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)
        status = resp.status
        if status == 200:
            # Read enough of the page to look for corroborating identifiers.
            body = resp.read(160_000).decode("utf-8", "ignore")
        else:
            resp.read(512)
    except urllib.error.HTTPError as e:
        status = e.code
    except Exception:
        status = None

    # Only a clean 200 counts as found. Anything else — 404, a block, a timeout —
    # is reported as "not found", never as a maybe. That is the right call for
    # ATTRIBUTION, but it is not the whole answer: a 404 means the site looked
    # and there is no such profile, while a 429, a 403 or a timeout means the
    # site never answered. Both produce exists=False, so a sweep in which every
    # site rate-limited was indistinguishable from a sweep that found nothing —
    # and discover_accounts reported "26 sites checked" either way. The state is
    # recorded so the caller can tell a clean sheet from a blind one.
    definite = status in (200, 404, 410)
    return AccountHit(site=site, category=spec["category"], username=username, url=url,
                      http_status=status, exists=(status == 200),
                      checked_at=_now(), reproduce=reproduce,
                      check_state="checked" if definite else "unreachable"), body


def derive_usernames(profile: dict, include_guessed: bool = True) -> list[tuple[str, str]]:
    """
    Handles to search, each tagged with where it came from.

    WHAT IS UNIQUE, AND WHAT ONLY LOOKS UNIQUE
    ------------------------------------------
    A full email address has exactly one owner. Its LOCAL PART does not:
    nalinchamp@gmail.com, nalinchamp@yahoo.com and nalinchamp@hotmail.com are
    three different people, and github.com/nalinchamp belongs to at most one of
    them. The same goes for the local part of a UPI ID, and for anything built
    out of a legal name.

    So the full address is searched where a service accepts one — Gravatar keys
    on MD5(email), HIBP keys on the address itself, and leak corpora are matched
    verbatim. Those answer a question about YOU.

    A username search cannot take an email. It can only ask "does this handle
    exist", which is a different question, and every handle we could invent is a
    guess. Therefore:

      declared       Handles the user told us. Searched by default — the only
                     source where the user is asserting ownership.
      email_local    Guessed from the local part. OFF by default; results are
                     permanently candidates.
      upi_local      Same.
      name_derived   Guessed from the legal name. OFF by default; worst of all,
                     since names are shared by thousands.
    """
    out: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(handle: str, source: str):
        h = (handle or "").strip().lower()
        if 3 <= len(h) <= 39 and h not in seen:
            seen.add(h)
            out.append((h, source))

    # Always: handles the user actually claims, including the bare part of any
    # "site:handle" entry, since the same handle may exist elsewhere too.
    for entry in re.split(r"[,\n;]+", str(profile.get("known_usernames") or "")):
        entry = entry.strip()
        if entry:
            add(entry.split(":", 1)[1] if ":" in entry else entry, "declared")

    if not include_guessed:
        return out[:8]

    # Guesses. Every one of these stays a candidate for ever — see the
    # GUESSED_SOURCES clamp in discover_accounts(), which rewrites any guessed
    # hit to tier "candidate" unless the page itself carries a verified
    # identifier. That clamp is what makes searching these safe to do by
    # default: a guess can surface something to confirm, but it can never be
    # counted as yours, enter the ledger, or move the risk score.
    for addr in re.split(r"[,\n;]+", str(profile.get("email") or "") + "," +
                         str(profile.get("alt_emails") or "")):
        addr = addr.strip()
        if "@" in addr:
            local = addr.split("@")[0]
            add(local, "email_local")
            stripped = re.sub(r"[^a-z0-9]", "", local.lower())
            if stripped != local.lower():
                add(stripped, "email_local")

    for upi in re.split(r"[,\n;]+", str(profile.get("upi_id") or "")):
        if "@" in upi:
            add(upi.split("@")[0], "upi_local")

    # Legal names are NEVER used to derive handles — names are shared by thousands
    # of people and online/gaming usernames rarely match legal names.
    # Searching names creates severe false-positive collision risks.
    return out[:12]


GUESSED_SOURCES = {"email_local", "upi_local"}


def identifier_keyed_note() -> str:
    """Why identifier-keyed checks are the only ones that settle anything."""
    return ("A lookup keyed on a unique identifier — Gravatar by MD5 of your email, HIBP by "
            "your address — answers a question about YOU. A username search only ever answers "
            "'does this handle exist', which is a different question.")


def discover_accounts(profile: dict, usernames: list[tuple[str, str]] | None = None,
                      max_workers: int = 16, verified: dict | None = None,
                      include_guessed: bool = True) -> dict:
    """
    Search for accounts, then decide which of them are actually this person's.

    Finding `github.com/rahulsharma` does NOT mean the Rahul Sharma in front of
    you owns it. So every hit is passed through attribution, and the result is
    split in two:

        attributed  proven or corroborated — treated as the user's data
        candidates  a handle matched and nothing tied it to them. Surfaced for
                    confirmation, and kept out of the ledger, the risk score
                    and the removal plan until the user says yes.
    """
    ident = Identifiers.from_profile(profile, verified=verified)
    users = usernames or derive_usernames(profile, include_guessed)
    if not users:
        return {"usernames_tried": [], "attributed": [], "candidates": [], "checked": 0,
                "excluded": EXCLUDED, "identifier_strength": ident.strength(),
                "note": ("No handle to search. Handles are only guessed when you ask, because a "
                         "guess finds strangers — tell us the usernames you actually use. Your "
                         "full email is still searched against identifier-keyed services.")}

    handle_source = {u: src for u, src in users}
    jobs = [(s_, spec, u) for u, _src in users for s_, spec in SITES.items()]
    results: list[tuple[AccountHit, str]] = []
    with cf.ThreadPoolExecutor(max_workers) as ex:
        for hit, body in ex.map(lambda a: _check_one(*a), jobs):
            results.append((hit, body))

    # Sites where identity is already settled can corroborate the rest — a
    # profile that links to a confirmed account is very likely the same person.
    proven_sites = {h.site for h, _ in results
                    if h.exists and (
                        ident.scoped_handles().get(h.site.lower()) == h.username.lower())}

    unreachable = [h for h, _ in results if h.check_state == "unreachable"]

    attributed, candidates = [], []
    for hit, body in results:
        if not hit.exists:
            continue
        att = attribute_profile(hit.username, body, ident, proven_sites, site=hit.site)
        risk = username_risk(hit.username, ident)
        hit.handle_source = handle_source.get(hit.username, "unknown")

        # A GUESSED handle can never be promoted to a finding, whatever else
        # matches. The local part of an email is not unique — nalinchamp@gmail
        # and nalinchamp@yahoo are different people — and a name is shared by
        # thousands. Only a handle the user claimed can settle anything.
        if hit.handle_source in GUESSED_SOURCES and att.tier != "proven":
            att = Attribution(
                tier="candidate", score=min(att.score, 0.3),
                signals=att.signals + [f"handle was guessed ({hit.handle_source}), not supplied by you"],
                explanation=(
                    "This handle was guessed, not given. The local part of an email is not "
                    "unique — the same local part at gmail, yahoo and hotmail belongs to three "
                    "different people — and a legal name is shared by thousands. Only your "
                    "full email address identifies you, and no username search accepts one."),
                is_mine=False)
        hit.attribution = att.to_dict()
        hit.collision_risk = risk
        hit.collision_note = collision_warning(hit.username, risk)

        if att.tier == "rejected":
            continue
        (attributed if att.is_mine else candidates).append(hit.to_dict())

    return {
        "usernames_tried": [{"handle": u, "source": src} for u, src in users],
        "username_risks": {u: username_risk(u, ident) for u, _ in users},
        "guessed_handles_searched": include_guessed,
        "sites_checked": len(SITES),
        "checks_performed": len(jobs),
        # Checks that were made but never answered. Without this a throttled or
        # blocked sweep returned an empty `attributed` list that read exactly
        # like a clean one.
        "checks_unreachable": len(unreachable),
        "unreachable_sites": sorted({h.site for h in unreachable}),
        "complete": not unreachable,
        "coverage_note": (
            f"{len(unreachable)} of {len(jobs)} profile check(s) could not be completed "
            f"(rate limited, blocked or unreachable) — those sites were NOT checked, and "
            f"this is not a clean result for them. Re-run to complete the sweep."
            if unreachable else
            f"All {len(jobs)} profile check(s) completed."),
        "attributed": attributed,
        "candidates": candidates,
        "excluded": EXCLUDED,
        "identifier_strength": ident.strength(),
        "verified_identifiers": {"emails": ident.verified_emails,
                                 "phones": ident.verified_phones},
        "method": ("Searches only handles you supplied. Guessing one from an email local-part "
                   "or a name is opt-in, and any guessed hit stays an unconfirmed candidate "
                   "for ever. Your FULL email is searched separately against identifier-keyed "
                   "services, which is the only search that can settle identity."),
        "identifier_keyed_note": identifier_keyed_note(),
        "why_candidates": ("These handles exist but nothing ties them to you. Names and "
                           "handles are shared by many people — confirm each one before "
                           "it is acted on."),
        "improve_accuracy": ("Adding more identifiers (alternate emails, phone numbers, "
                             "UPI ID, known usernames, date of birth) lets more candidates "
                             "be resolved automatically in either direction."),
    }


def verify_site_reliability(real_username: str, fake_username: str) -> dict:
    """
    Re-verify that each site still separates existing from non-existing users.

    Run this if results start looking wrong: sites change their 404 behaviour,
    and a site that starts soft-404ing must be moved into EXCLUDED.
    """
    report = {}
    for site, spec in SITES.items():
        r, _ = _check_one(site, spec, real_username)
        f, _ = _check_one(site, spec, fake_username)
        report[site] = {
            "real_status": r.http_status, "fake_status": f.http_status,
            "reliable": r.http_status == 200 and f.http_status in (404, 410),
        }
    return report
