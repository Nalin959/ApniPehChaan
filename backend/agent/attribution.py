"""
attribution.py — Deciding whether a found account is actually YOURS.

THE PROBLEM
-----------
Searching for a username is a guess. `github.com/rahulsharma` exists, but it
belongs to one specific human being — not to every Rahul Sharma in India.
Measured on this codebase before this module existed: three common Indian names
each produced THIRTEEN "your accounts", and essentially none of them were.

Acting on that is not a cosmetic bug. It means telling someone their data is
somewhere it isn't, and then helping them demand deletion of a stranger's
account. A privacy tool that does that is worse than no tool.

THE RULE
--------
A username match is a CANDIDATE, never a finding. It becomes a finding only when
something independent ties it to this person.

THREE TIERS
-----------
  proven        The lookup key IS a unique identifier of the person. Querying
                Gravatar by MD5(email) asks about that exact address; HIBP by
                email likewise. There is no ambiguity to resolve.

  corroborated  A username matched AND the profile page itself carries something
                only this person would have there: their email, their phone,
                their UPI handle, a link to an account already proven, or their
                full name together with a second signal.

  candidate     A username matched and nothing corroborates it. Shown to the
                user as "is this you?" and EXCLUDED from the exposure ledger,
                the risk score and the removal plan until they say yes.

Only `proven` and `corroborated` are ever treated as the user's data.
"""

import hashlib
import re
from dataclasses import dataclass, field, asdict

# Handles so generic that finding one proves nothing at all.
GENERIC_HANDLES = {
    "admin", "test", "user", "info", "contact", "hello", "mail", "email",
    "support", "office", "me", "demo", "guest", "root", "null", "none",
}


@dataclass
class Identifiers:
    """Everything the user has given us that could tie an account to them.

    All optional. The more supplied, the fewer strangers get misattributed —
    that is the entire trade being offered, and it is stated in the UI.
    """
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    usernames: list[str] = field(default_factory=list)   # handles the user CONFIRMS are theirs
    full_name: str = ""
    date_of_birth: str = ""
    upi_ids: list[str] = field(default_factory=list)
    websites: list[str] = field(default_factory=list)
    city: str = ""
    # Identifiers whose OWNERSHIP has been proven by a delivered one-time code.
    # Only these carry full corroboration weight — an unverified address may be
    # a typo or somebody else's, and attributing accounts from it is exactly the
    # false-positive failure this whole layer exists to prevent.
    verified_emails: list[str] = field(default_factory=list)
    verified_phones: list[str] = field(default_factory=list)
    # Sensitive values are never stored or transmitted in the clear. They are
    # hashed on arrival and used only to match against local leak corpora.
    sensitive_hashes: dict = field(default_factory=dict)

    @staticmethod
    def _digits(v: str) -> str:
        return "".join(c for c in v if c.isdigit())

    @classmethod
    def from_profile(cls, p: dict, verified: dict | None = None) -> "Identifiers":
        def split(v):
            return [x.strip() for x in re.split(r"[,\n;]+", str(v or "")) if x.strip()]

        emails = [e.lower() for e in split(p.get("email", "")) + split(p.get("alt_emails", ""))]
        phones = [cls._digits(x)[-10:] for x in split(p.get("phone", "")) + split(p.get("alt_phones", ""))]
        ident = cls(
            emails=[e for e in dict.fromkeys(emails) if "@" in e],
            phones=[x for x in dict.fromkeys(phones) if len(x) == 10],
            # Accepts either "handle" or "site:handle". The scoped form is a
            # claim about one namespace; the bare form is a claim about a habit.
            usernames=[u.lower() for u in dict.fromkeys(split(p.get("known_usernames", "")))],
            full_name=(p.get("name") or "").strip(),
            date_of_birth=(p.get("date_of_birth") or "").strip(),
            upi_ids=[u.lower() for u in dict.fromkeys(split(p.get("upi_id", "")))],
            websites=[w.lower() for w in dict.fromkeys(split(p.get("websites", "")))],
            city=(p.get("city") or "").strip(),
        )
        ver = verified or {}
        ident.verified_emails = [normalise for normalise in
                                 (e.strip().lower() for e in ver.get("emails", [])) if normalise]
        ident.verified_phones = [v for v in
                                 ("".join(c for c in x if c.isdigit())[-10:]
                                  for x in ver.get("phones", [])) if len(v) == 10]

        # Hash-only intake. A privacy tool must not hold a raw card or passport
        # number, and neither is any use for matching a public profile anyway —
        # no profile page displays one. They are accepted solely so leaked-dump
        # matching can run locally against a digest.
        for key in ("pan", "passport", "card_last4", "aadhaar"):
            raw = (p.get(key) or "").strip()
            if raw:
                ident.sensitive_hashes[key] = hashlib.sha256(raw.encode()).hexdigest()
        return ident

    def scoped_handles(self) -> dict:
        """{site_lower: handle} from entries written as "site:handle"."""
        out = {}
        for entry in self.usernames:
            if ":" in entry:
                site, handle = entry.split(":", 1)
                if site.strip() and handle.strip():
                    out[site.strip().lower()] = handle.strip().lower()
        return out

    def bare_handles(self) -> set:
        """Handles declared without naming a site."""
        return {u for u in self.usernames if ":" not in u}

    def strength(self) -> int:
        """How many independent identifiers we hold. Drives how confident we can be."""
        return (len(self.emails) + len(self.phones) + len(self.usernames)
                + len(self.upi_ids) + len(self.websites)
                + (1 if self.date_of_birth else 0))


@dataclass
class Attribution:
    tier: str                 # proven | corroborated | candidate | rejected
    score: float              # 0.0 - 1.0
    signals: list             # what actually matched, human readable
    explanation: str
    is_mine: bool             # only true for proven / corroborated

    def to_dict(self):
        return asdict(self)


def _dob_variants(dob: str) -> list[str]:
    """Common renderings of a date of birth, for scanning page text."""
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", dob.strip())
    if not m:
        return [dob.strip()] if dob.strip() else []
    y, mo, d = m.groups()
    months = ["January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]
    name = months[int(mo) - 1]
    return [f"{y}-{mo}-{d}", f"{d}/{mo}/{y}", f"{d}-{mo}-{y}",
            f"{name} {int(d)}, {y}", f"{int(d)} {name} {y}"]


def attribute_profile(username: str, page_text: str, ident: Identifiers,
                      proven_sites: set | None = None, site: str = "") -> Attribution:
    """
    Decide whether a profile found by username search belongs to this person.

    `page_text` is the fetched profile page. Corroboration lives there: many
    profiles display an email, a phone, a personal site, or links to the same
    person's other accounts.
    """
    proven_sites = proven_sites or set()
    text = (page_text or "").lower()
    uname = (username or "").lower()
    signals: list[str] = []
    score = 0.0

    site_l = (site or "").strip().lower()
    scoped = ident.scoped_handles()
    bare = ident.bare_handles()

    # "github:rahulsharma" — a claim about this exact namespace. That settles it.
    if site_l and scoped.get(site_l) == uname:
        return Attribution(
            tier="proven", score=1.0,
            signals=[f"you confirmed '{username}' is your handle on {site}"],
            explanation="You named this handle for this site, so no inference is needed.",
            is_mine=True)

    # A bare declared handle is a claim about a habit, not about every namespace
    # on the internet. If the handle is distinctive, treating it as yours is
    # safe. If it is just your name with the punctuation removed, it is not —
    # somebody else may well have registered it here years ago.
    if uname in bare:
        risk = username_risk(username, ident)
        if risk in ("confirmed", "low", "medium"):
            return Attribution(
                tier="corroborated", score=0.85,
                signals=[f"'{username}' is a handle you use, and it is distinctive"],
                explanation=("You listed this handle and it is unusual enough that a match "
                             "here is very likely you."),
                is_mine=True)
        return Attribution(
            tier="candidate", score=0.45,
            signals=[f"'{username}' is a handle you use, but it is a common-name handle"],
            explanation=(f"You said you use '{username}', but it is your name — or a part of "
                         f"it, like a surname — used as a handle, and many people share it. "
                         f"Someone else may well hold it on {site or 'this site'}. Write it as "
                         f"'{site_l or 'site'}:{username}' to confirm it for this site."),
            is_mine=False)

    # A handle this generic identifies nobody.
    if uname in GENERIC_HANDLES or len(uname) <= 3:
        return Attribution(
            tier="rejected", score=0.0,
            signals=[f"'{username}' is a generic handle"],
            explanation=("This handle is too common to belong to anyone in particular. "
                         "Not attributed."),
            is_mine=False)

    # ── Corroborating signals found on the page itself ──────────────────────
    digits_only = re.sub(r"[^0-9]", "", text)

    for e in ident.emails:
        if not e or e not in text:
            continue
        if e in ident.verified_emails:
            signals.append(f"page contains your VERIFIED email address ({e})")
            score += 0.60
        else:
            signals.append(f"page contains an unverified email you gave ({e}) — "
                           f"verify it to make this conclusive")
            score += 0.25

    for ph in ident.phones:
        if not ph or ph not in digits_only:
            continue
        if ph in ident.verified_phones:
            signals.append(f"page contains your VERIFIED phone number (…{ph[-4:]})")
            score += 0.55
        else:
            signals.append(f"page contains an unverified number you gave (…{ph[-4:]}) — "
                           f"verify it to make this conclusive")
            score += 0.25

    for upi in ident.upi_ids:
        if upi and upi in text:
            signals.append(f"page contains your UPI ID ({upi})")
            score += 0.55

    for site in ident.websites:
        host = re.sub(r"^https?://", "", site).strip("/")
        if host and host in text:
            signals.append(f"page links to your site ({host})")
            score += 0.45

    for variant in _dob_variants(ident.date_of_birth):
        if variant and variant.lower() in text:
            signals.append(f"page shows your date of birth ({variant})")
            score += 0.35
            break

    # Cross-links to an account already proven to be theirs.
    for site in proven_sites:
        if site and site.lower() in text:
            signals.append(f"page links to your confirmed {site} profile")
            score += 0.30
            break

    # Name alone is weak — it is exactly what causes the misattribution — so it
    # can support a case but can never make one.
    name_hit = False
    if ident.full_name and len(ident.full_name.split()) >= 2:
        if ident.full_name.lower() in text:
            name_hit = True
            signals.append(f"page shows your full name ({ident.full_name})")
            score += 0.20
    if ident.city and ident.city.lower() in text and name_hit:
        signals.append(f"page mentions your city ({ident.city})")
        score += 0.15

    # ── Verdict ─────────────────────────────────────────────────────────────
    # Only a proven identifier settles it on its own. An unverified address
    # contributes, but cannot by itself promote a candidate to a finding.
    strong = any(s.startswith(("page contains your VERIFIED email",
                               "page contains your VERIFIED phone",
                               "page contains your UPI")) for s in signals)

    if strong or score >= 0.60:
        return Attribution(
            tier="corroborated", score=min(1.0, score), signals=signals,
            explanation=("The profile itself carries an identifier that is yours, so this "
                         "is attributed to you."),
            is_mine=True)

    if score > 0:
        return Attribution(
            tier="candidate", score=score, signals=signals,
            explanation=("Something matches, but nothing unique to you. Names and handles are "
                         "shared by many people — confirm before acting on this."),
            is_mine=False)

    return Attribution(
        tier="candidate", score=0.0,
        signals=[f"username '{username}' exists on this site"],
        explanation=("Only the handle matched. That is a guess, not evidence — this profile "
                     "may well belong to someone else with a similar name. Not counted as "
                     "yours until you confirm it."),
        is_mine=False)


def _name_handle_forms(full_name: str) -> set:
    """
    Every handle shape that is really just this person's legal name.

    A SINGLE name part counts. "torvalds", "sharma" and "nalin" are surnames and
    forenames, and a surname is shared by millions — treating one as distinctive
    because it is not the *whole* name was how a stranger's account got
    attributed on twenty-six sites at once. Parts of three characters or fewer
    are left out; they are caught as generic handles instead.
    """
    parts = [x.lower() for x in (full_name or "").split() if x.isalpha()]
    forms = {p for p in parts if len(p) > 3}
    if len(parts) >= 2:
        first, last = parts[0], parts[-1]
        forms |= {
            "".join(parts), ".".join(parts), "_".join(parts),
            first + last, f"{first}.{last}", f"{first}_{last}",
            first[0] + last, f"{first[0]}.{last}", f"{first[0]}_{last}",
            last + first, f"{last}.{first}", f"{last}_{first}",
            last + first[0],
        }
    return forms


def username_risk(username: str, ident: Identifiers) -> str:
    """
    How likely is this candidate handle to collide with other people?

    The subtle trap: it is tempting to treat "the handle equals the email
    local-part" as reassuring. It is not. Owning rahul.sharma@gmail.com tells
    you nothing about who owns github.com/rahulsharma — they are unrelated
    namespaces, and the second was probably claimed by a different Rahul Sharma
    years earlier. What actually predicts collision is whether the handle is
    just a common human name with the punctuation removed.
    """
    u = (username or "").lower()

    if u in ident.bare_handles() or u in ident.scoped_handles().values():
        # Declared — but a declared common-name handle still collides. Saying
        # "I use the handle torvalds" claims a habit, not the torvalds account
        # on every site that has one.
        if u in _name_handle_forms(ident.full_name):
            return "high"
        if any(c.isdigit() for c in u) or len(u) >= 12:
            return "low"
        return "medium"
    if u in GENERIC_HANDLES or len(u) <= 3:
        return "generic"

    if u in _name_handle_forms(ident.full_name):
        # Pure name handle. Shared by everyone with that name.
        return "high"

    # A handle carrying digits or an unusual token is far more personal.
    if any(c.isdigit() for c in u):
        return "low"
    if len(u) >= 12:
        return "low"
    return "medium"


def collision_warning(username: str, risk: str) -> str:
    """Plain-language note for the UI about why a handle may not be the user."""
    return {
        "confirmed": f"Candidate matching handle '{username}'. Confirm if this profile is yours.",
        "generic":   f"'{username}' is a generic handle — it identifies nobody in particular.",
        "high":      (f"'{username}' is your name (or part of it) used as a handle. Many "
                      f"people share it, so a match here may well be someone else. Write it "
                      f"as 'site:{username}' to claim it on one site."),
        "medium":    (f"'{username}' could belong to someone else with the same handle. "
                      f"Review profile link to verify if this account is actually yours."),
        "low":       (f"'{username}' is distinctive, but still requires your confirmation "
                      f"before being attributed to you."),
    }.get(risk, "")
