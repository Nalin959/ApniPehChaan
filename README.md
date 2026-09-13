# ApniPehChaan 🛡️
### Autonomous Digital Identity & Sovereign Privacy Protection Agent
> *Find where your personal data actually is, prove it, and exercise your right to erasure under India's DPDP Act 2023, EU GDPR, and US CCPA/CPRA.*
> Built for the 24-Hour Hackathon.

---

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![DPDP Act 2023](https://img.shields.io/badge/Compliance-India%20DPDP%202023-orange.svg)](https://www.meity.gov.in/)
[![GDPR Art 17](https://img.shields.io/badge/Compliance-EU%20GDPR%20Art%2017-blue.svg)](https://gdpr.eu/)
[![Tests](https://img.shields.io/badge/Tests-334%2F334%20Passed-brightgreen.svg)]()
[![Cost](https://img.shields.io/badge/Paid%20APIs-none%20required-success.svg)]()

---

## 📌 What this is

Give the agent an identity and it goes and looks. It queries free breach corpora and
info-stealer infection corpora, fetches 26 public-profile namespaces, and searches the open web
for the identifiers that belong to exactly one person. Every finding carries the endpoint that
was queried, the timestamp, the HTTP status and a command you can run yourself. It then decides
which Indian statute reaches each exposure — several of them nothing reaches — drafts the
notices that are available in law, and **stops**, because serving a statutory notice is
irreversible and aimed at a third party.

**It requires no paid API.** That was a deliberate constraint, and it is why the central
feature works at all: Have I Been Pwned's per-address lookup needs a subscription, so before
this build breach detection was switched off for anyone without a card on file.

Two rules shape everything else:

1. **Nothing is claimed that was not checked.** A check that cannot run reports `not_checked`
   or `unavailable`. It never guesses, and it never reports "clear" when it means "could not
   look".
2. **A name identifies nobody, and a username is not proof of identity.** Thousands of people
   share a name. A tool that guesses handles from names hands you a stranger's accounts and
   then helps you demand deletion of their data. Findings are split into *attributed* and
   *candidates*, and candidates are kept out of the ledger, the risk score and the removal plan
   until you confirm them.

---

## 🚀 Quick start

### Prerequisites
Python 3.10+, Linux / macOS / WSL. Dependencies are `fastapi`, `uvicorn`, `pydantic` and
optionally `anthropic` — everything else uses the standard library.

### Run it
```bash
chmod +x run_demo.sh
./run_demo.sh
```

`run_demo.sh` creates `.venv` if needed, installs `requirements.txt`, builds the datasets if
`data/breaches/hibp_breaches.json` is absent, and starts uvicorn on port 8000. Open
<http://localhost:8000>.

### Manual
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python data/download_datasets.py      # builds data/ from authoritative public sources
python test_system.py                 # 334 tests
python -m uvicorn backend.app:app --reload --port 8000
```

### Keys: what needs one, and what does not

**With no `.env` at all, the product runs end to end.** Every breach check, the account
discovery, the open-web search, the risk scoring, the legal classification and the notice
drafting all work. Only the *planner* changes: the trace says `deterministic` instead of naming
a model.

| | Key | Needed? |
|---|---|---|
| **XposedOrNot** breach membership | — | **None.** Free, keyless, no signup |
| **Hudson Rock** info-stealer infections | — | **None.** Free, keyless |
| **Pwned Passwords** (k-anonymous) | — | **None.** Free, unauthenticated |
| **Gravatar** profile lookup | — | **None** |
| Account discovery, open-web search | — | **None** |
| **LLM planner** | `GEMINI_API_KEY` or `GROQ_API_KEY` (or another below) | Optional — autonomous multi-turn reasoning |
| **Google Gemini (AI Studio)** | `GEMINI_API_KEY` | Optional — fast, generous free tier, handles thought signatures |
| **HIBP** per-address lookup | `HIBP_API_KEY` | Optional (~$3.95/mo). Reported as `not_checked` without it |

```bash
cp .env.example .env     # paste one planner key, then restart the server
```

`.env` is gitignored and loaded at import by `backend/agent/env.py`, which reads only a fixed
allowlist of variable names — a `.env` can hold anything, and loading arbitrary keys out of a
file into the process environment is a good way to shadow something important. A real
environment variable always wins over the file.

`GET /api/config/status` shows what is configured, masked, without revealing a value.

---

## 🤖 The agent

Twenty-two capabilities are exposed as tools over one registry
(`backend/agent/tools.py :: build_tools`):

| Tool | What the agent uses it for |
|---|---|
| `build_identity_profile` | Normalise the identity and derive aliases with confidence scores |
| `recall_prior_activity` | Read its own memory of earlier runs before acting |
| `verify_breach_exposure` | Run every breach check that can actually be performed, and return the evidence |
| `verify_password_exposure` | k-anonymous Pwned Passwords check |
| `match_unique_identifiers` | Match email / phone / UPI / Aadhaar / PAN against local leak corpora |
| `discover_accounts` | Fetch 26 public-profile namespaces, then decide which profiles are actually the user's |
| `search_open_web` | Search the open web for unique identifiers, then fetch and verify every page |
| `confirm_account` | Resolve a parked candidate — the user says whether it is theirs |
| `declare_known_accounts` | Record services the user says they hold |
| `browse_indian_registry` | 51 classified Indian institutions and brokers |
| `search_data_brokers` | Find removable broker records |
| `search_paste_dumps` | Find attributable leak-dump entries |
| `detect_pii_in_text` | Run the Verhoeff/Luhn-validated PII recogniser |
| `assess_exposure_risk` | Compute the Privacy Risk Score |
| `analyze_threat_surface` | Cross-correlate multi-breach data into credential stuffing, spear-phishing, and SIM-swap attack vectors |
| `determine_legal_basis` | Decide jurisdiction, statute, and whether erasure is even available |
| `plan_removal` | Choose the cheapest effective removal route |
| `draft_erasure_request` | Compile the statutory notice |
| `submit_erasure_request` | Serve it — **gated on user approval** |
| `check_request_status` | Follow up on a served notice |
| `verify_removal` | Independently re-query the source to prove removal |
| `escalate_to_regulator` | Escalate to the DPBI / supervisory authority / CPPA |

### Planners: three backends, one tool surface

| Planner | When it runs | What it does |
|---|---|---|
| **Google Gemini** | `GEMINI_API_KEY` set | Gemini (`gemini-3.6-flash`, `gemini-2.5-flash`, `gemini-1.5-pro`) with autonomous multi-turn tool calling and thought signature preservation (`APNIPEHCHAAN_PLANNER=gemini`) |
| **Anthropic** | `ANTHROPIC_API_KEY` set | Claude (`claude-opus-5` by default, override with `APNIPEHCHAAN_MODEL`) chooses each call and explains why |
| **OpenAI-compatible** | any of `GROQ_API_KEY`, `CEREBRAS_API_KEY`, `GITHUB_TOKEN`, `MISTRAL_API_KEY`, `OPENROUTER_API_KEY`, `TOGETHER_API_KEY`, `OLLAMA_API_KEY` | One adapter covers all seven providers (`backend/agent/openai_compat_planner.py`) |
| **Deterministic** | no key, or the LLM path errored | A fixed pipeline over the *identical* tools. The product works end to end; only the reasoning is canned |

`APNIPEHCHAAN_PLANNER` (or legacy `SOVEREIGN_PLANNER`) pins one when several keys are present. The UI states which is live. If the
LLM path errors mid-run it falls back to the deterministic pipeline rather than failing the
demo, and says why in one actionable line ("the key was rejected (401)", "that key lacks access
to this model").

### Deterministic gathering, planned judgement

The mandatory *looking* is deterministic. Asking a model to remember to call
`build_identity_profile` wastes a round trip and is a reliability risk: it is cheap, local, and
always correct to run. **Measured: leaving the whole sequence to the planner took ~117s and it
still skipped fourteen of the twenty tools it was given.**

So the planner is handed the part that actually needs reasoning — which exposures are worth
acting on, which statute applies, whether a notice should be drafted at all — and is given
**only the tools that phase uses**. Dispatch is absent from the discovery toolset entirely, so
the agent *cannot* send anything even if it decides it wants to.

### Reliability under free-tier limits

Free tiers cap **tokens per minute** (Groq: 8000) far more tightly than requests, and the whole
conversation is resent on every round trip. Three consequences are handled explicitly:

- **Tool schemas are scoped to the phase.** Handing the planner all twenty-one costs ~600
  tokens per call for eighteen it will never touch. Measured, the mandatory gathering takes
  0.8s while the planner phase took 154s almost entirely on token throughput.
- **Tool results are compacted** to `MAX_RESULT_CHARS = 700` before entering the transcript.
  The model needs to know *what* was found and the ids to act on, not every field of every
  record — and an un-compacted result is paid for again on every subsequent step.
- **The planner sees the 40 most severe exposures, ranked by severity** — not all of them
  (`PLANNER_EXPOSURE_CAP` in `backend/agent/orchestrator.py`). A heavily-breached address
  produces hundreds; an unbounded list walks straight through the per-minute budget and the run
  dies mid-way. It is also worse reasoning — the judgement asked for is not improved by paging
  through the two hundredth low-severity record. **Every exposure is still recorded, still
  scored, and still shown to the user**; the cap is only on what the planner reasons over, and
  the trace says how many were summarised.

### Design decisions worth defending

**Drafting is autonomous; sending is not.** `submit_erasure_request` is withheld from the
discovery toolset. This is a deliberate limit on autonomy, not a missing feature.

**"Submitted" is not "removed".** `verify_removal` re-queries the source independently and only
then marks it removed. A controller's say-so is not evidence. Be clear about the scope: it
re-queries **data-broker** records, which today means the simulated network, and for anything
else it returns `verifiable: false` with the reason ("breach and paste records cannot be
un-published") rather than a comforting green tick.

**Not every exposure is actionable.** A historical breach cannot be un-published and an
unattributed dump has no controller to serve. The agent says so instead of drafting a notice
that cannot land.

**Attribution requires corroboration.** A record matching only on name is not treated as yours.
A match needs a unique identifier, or several agreeing non-unique fields.

---

## 🔍 What it actually checks

### Free breach intelligence — no key, no signup

| Check | Endpoint | What a hit proves |
|---|---|---|
| **XposedOrNot** | `api.xposedornot.com/v1/breach-analytics` | This exact address appears in the breaches named. Free, keyless |
| **Hudson Rock Cavalier** | `cavalier.hudsonrock.com/api/json/v2/osint-tools/search-by-email` | A computer holding this address was infected by info-stealer malware. Free, keyless |
| **Pwned Passwords** | `api.pwnedpasswords.com/range/{prefix}` | This password appears in breach corpora. k-anonymous: only 5 SHA-1 characters leave the machine |
| **Gravatar** | `gravatar.com/avatar/{md5}?d=404` | A public profile is attached to that address |
| **HIBP breach catalog** | `haveibeenpwned.com/api/v3/breaches` | Real metadata *about* breaches — not about whether a person is in one |

**XposedOrNot is the headline change.** The authoritative answer to "is my address in a breach"
is HIBP, and its per-address endpoint returns 401 without a subscription. `check_hibp_account`
correctly refuses to guess and returns `not_checked` — which left the single most important
question in the product unanswered for anyone without a card on file. XposedOrNot answers it
for free.

The two are deliberately **not merged**. They are different corpora, so XposedOrNot is reported
under its own name: agreement between them is corroboration, and absence in one is not absence
in the other. If `HIBP_API_KEY` is set, both run.

### Info-stealer infection detection — a different exposure class

This is not a smaller or larger breach; it is a different kind of loss.

A site breach leaks what **one company** held about you, and the credentials are historic. An
info-stealer infection means a computer you used was running malware that copied the **entire
browser password store in one go** — every password, every cookie, every session token, taken
together — and those credentials are **current**.

It is scored `critical`, and `data_found` is `["email", "password", "session_cookies"]` rather
than merely `email`. Credential values arrive already masked at source; nothing unmasks them
and no password is stored.

**Remediation is not a legal notice**, because erasure has no addressee here: the data came off
the user's own machine, not from a controller who can be served. The `infostealer` playbook
(`method: credential_rotation`) says what actually reduces harm:

1. Treat every password saved in that browser as known to someone else.
2. Rotate in **dependency order** — email first, because it resets everything else; then the
   phone/SIM account; then banking and UPI.
3. **Revoke all sessions.** A stolen session cookie lets someone in *without* the password, so
   changing passwords alone is insufficient. This is the step people skip.
4. Enable 2FA, preferring an authenticator app over SMS.
5. Scan the machine before re-entering any password on it — otherwise the new passwords are
   stolen too.
6. Check email filters and forwarding rules: attackers commonly add a hidden forward to keep
   reading mail after the account is recovered.

Escalation names India's cybercrime helpline **1930** and **cybercrime.gov.in**.

### Open-web search — a search result is a lead, never evidence

`backend/agent/web_search.py`. A fixed list of sites can only ever find what is on the list,
and "where is my data online" is not a question a list can answer. So the agent asks the open
web — and then refuses to believe it.

**Every candidate page is fetched, and the identifier must appear in the page itself, character
for character, before the page is called an exposure.** Search engines match on stemming, on
synonyms, on text that has since changed, and on the snippet rather than the page. A result
that fails verification is reported as an unconfirmed lead with the reason ("it may be rendered
by JavaScript, behind a login, or already removed — so nothing is claimed").

Only unique identifiers are searched: email, phone, UPI ID, PAN, and handles the user declares.
**A legal name is never searched** — thousands of people share one, so every hit would be a
stranger.

Two details that stop false positives:

- **Phone numbers are matched per digit-run, never against every digit on the page joined
  together.** Concatenating "Order 1234567" and "Invoice 8909876" manufactures the substring
  `9876543210`, a number that appears nowhere. A run matches only if it *is* the number, or is
  the number behind a country or trunk prefix, and runs longer than 13 digits are rejected.
- **A username hit is only promoted to a finding if the same page also carries a unique
  identifier.** Finding the string `nalinchamp` on a page proves the string is there, not that
  it refers to this person.

**Rate limiting is handled as a correctness problem, not a performance one.** A throttled engine
returns a page with no results on it, which is byte for byte the same shape as a genuine
"nothing found". Reporting the first as the second would tell somebody their data is nowhere
online at the exact moment the tool had stopped being able to look. So `search_web` returns
`ok` / `blocked` / `empty` as three distinct statuses, the result carries `search_degraded` and
`blocked_queries`, and the UI says **"could not check"** rather than "clear".

Mitigations: a looser unquoted query variant (the engine only ever nominates pages — every one
is verified anyway, so a looser query widens what is *considered* without loosening what is
*claimed*); a secondary index (Marginalia, free and unauthenticated, much smaller coverage)
consulted when the primary refuses; and a six-hour on-disk result cache, so a re-scan costs no
queries at all. A refusal is **never** cached — that would turn one throttled minute into six
hours of pretending to have looked.

### Account discovery — 26 sites, each empirically verified

`backend/agent/account_discovery.py`. The method is the one Sherlock and Maigret use: fetch the
**public** profile URL for a username and see whether the site serves a profile or a 404. No
login, no scraping of private data, no probing of password-reset endpoints to enumerate
accounts.

**Naive status-code checking is worthless here.** Instagram, Pinterest, Medium and PyPI all
return HTTP 200 for usernames that do not exist — they serve a login wall or a soft-404. A tool
that trusted the status code would tell you that you have an Instagram account when you do not.

So every site was verified against **both** a username known to exist and one known not to
exist. Only sites that cleanly separated the two were kept. **26 are checked; 17 are listed in
`EXCLUDED` with the reason and are never queried** — silence beats a false claim.

Two were removed today after measurement:

| Removed | Why |
|---|---|
| **Kaggle** | Serves HTTP 200 for non-existent users — 5 of 5 invented handles returned 200. It was previously trusted, so it was reporting accounts that do not exist |
| **Replit** | Returns HTTP 404 even for handles that demonstrably exist (its own founder's), so a 404 proves nothing and a hit never occurs |

`verify_site_reliability(real_username, fake_username)` re-runs the check. Sites change their
404 behaviour; a site that starts soft-404ing must be moved into `EXCLUDED`.

---

## 🧭 Attribution: a stranger's account is never flagged as yours

`backend/agent/attribution.py`. Searching for a username is a guess.
`github.com/rahulsharma` exists, but it belongs to one specific human being — not to every
Rahul Sharma in India. Measured on this codebase before this module existed: **three common
Indian names each produced thirteen "your accounts"**, essentially none of them the right
person. The tool would then have helped demand deletion of a stranger's data.

A username match is a **candidate**, never a finding:

| Tier | Meaning | Counted as yours? |
|---|---|---|
| `proven` | The lookup key *is* a unique identifier (Gravatar by MD5 of your email), or you named the handle **for that site** (`github:yourhandle`) | Yes |
| `corroborated` | The page itself carries your email, phone, UPI ID, a link to your site, your date of birth, or a link to an account already proven | Yes |
| `candidate` | A handle matched and nothing ties it to you | **No** — parked for confirmation |
| `rejected` | Generic handle (`admin`, `test`, `info`) that identifies nobody | No |

Only `proven` and `corroborated` are treated as the user's data. Candidates are written to
memory with status `unconfirmed`, which excludes them from the exposure ledger, the **risk
score** (`assess_exposure_risk` scores only live exposures) and the **removal plan** until the
user confirms them via `confirm_account`.

**A handle that is just your name is high collision risk, even if you declared it.** Saying
"I use the handle `sharma`" claims a habit, not the `sharma` account on every site that has
one — someone else may well have registered it there years ago. So a *distinctive* declared
handle is accepted (`corroborated`), a **name-derived one is held as a candidate**, and
`github:sharma` proves it on GitHub only. `_name_handle_forms` treats a **single** name part as
a name handle: "sharma" and "nalin" are a surname and a forename, and treating one as
distinctive because it is not the *whole* name was how a stranger's account got attributed
across twenty-six sites at once.

### Only unique identifiers are searched. Never a name.

| Identifier | What it can do |
|---|---|
| Full email address | Identifier-keyed lookups (Gravatar by MD5, XposedOrNot, HIBP), leak matching, corroborating a page |
| Phone number | Leak matching, corroborating a page |
| UPI ID | Leak matching, corroborating a page |
| PAN | Open-web search, leak matching |
| Aadhaar | **Leak matching only** — no public profile displays one |
| Legal name | **Nothing.** Never used as a search key, never used to derive a handle |

**The trap that catches most tools:** an email's *local part* is not unique either.
`nalinchamp@gmail.com`, `nalinchamp@yahoo.com` and `nalinchamp@hotmail.com` are three different
people, and `github.com/nalinchamp` belongs to at most one of them. So the **full** address is
searched wherever a service accepts one — but a username search cannot take an email, so every
handle derived from a local part is a guess.

Guessing from the email/UPI local part is a checkbox (`search_guessed_handles`, off by default
on the API, on by default in the UI so a scan still looks when you declare no handle). Any
guessed hit is clamped to tier `candidate` for ever unless the page itself carries a verified
identifier. **Legal names are never used to derive handles at all**, whatever the setting.

Aadhaar and PAN are checksum-validated before being used — a mistyped Aadhaar would look for
someone else's number. PAN, passport, Aadhaar and card digits are SHA-256 hashed on arrival,
never stored raw, and used only for local leak matching.

### Identifiers are trusted as typed (OTP is built but unwired)

The email and phone you type are used for corroboration directly. That is safe in the direction
that matters, because corroboration requires the identifier to **actually appear on the profile
page** — a mistyped address simply matches nothing, so the failure mode is *fewer* attributions,
never wrong ones. The protection that matters, that a shared name can never attribute a
stranger's account, does not depend on proving ownership; it depends on requiring corroboration
at all. (Verified identifiers do score higher: 0.60 versus 0.25 for an email.)

A full one-time-code flow — MX pre-check, hashed codes, expiry, attempt limits, SMTP delivery —
lives in `backend/agent/verification.py` with endpoints under `/api/verify/*`. It is not wired
into the UI: without SMTP configured it can only show the code on screen, which proves nothing.
Configure `SMTP_HOST`/`SMTP_USER`/`SMTP_PASS` to raise typed identifiers to proven ownership.

---

## ⚖️ Indian legal classification

"Can I get this deleted?" is not one question in India. Every source is classified, and the
agent refuses to draft where erasure does not lie:

| Class | Examples | Agent action | Count |
|---|---|---|---|
| `dpdp_erasure` | Truecaller, JustDial, Naukri, Shaadi.com | **Drafts a notice** (DPDP s.12) | 26 |
| `statutory_publication` | MCA21, electoral rolls, Bhulekh | Correction only — DPDP s.3(c)(ii) excludes it | 15 |
| `dpdp_limited` | CIBIL, telecom KYC | Dispute/correct — retention duty competes (CICRA 2005) | 6 |
| `judicial_record` | Indian Kanoon, eCourts | Court application (cf. Delhi HC, *Jorawer Singh Mundy*, 2021) | 4 |

A naive build sends "please delete my data" to Indian Kanoon. That letter has no addressee in
law. Telling a user they have a remedy they don't have is worse than saying nothing — so the
agent says **NO ERASURE RIGHT**, names the reason, and points at the real route.

`data/brokers/indian_sources.json` holds 51 classified Indian sources, served at
`GET /api/sources/indian`.

### Removal follows a ladder, not a reflex

**A statutory notice is the escalation, not the opening move.** Truecaller has an unlisting
page. GitHub has a Delete Account button. Naukri lets you delete your profile from settings.
Serving a DPDP Section 12 notice on a company that offers two-click deletion is theatre — it
takes 30 days to achieve what a link achieves in three minutes.

`data/removal_playbooks.json` holds **66 playbooks**; `plan_removal` chooses between them:

| Method | When | Count | Typical time |
|---|---|---|---|
| `self_serve` | The service has a delete/unlist page | 37 | minutes |
| `not_removable` | Court records, statutory registers, licence-bound content | 16 | n/a — the real route is stated instead |
| `email_request` | No portal, but a DPO/grievance officer is published | 9 | 1–4 weeks |
| `statutory_only` | A sector regulator compels retention (SEBI: five years of KYC after closure; IRDAI policy data) | 2 | 2–6 weeks via the regulator's grievance portal |
| `statutory_notice` | Nothing simpler exists, or the cheap routes were ignored | 1 | 30–45 days |
| `credential_rotation` | Info-stealer infection — no controller to serve | 1 | 1–2 hours, today |

Each entry carries a direct link, concrete steps, an effort estimate, and an `escalation` —
what to do when the cheap route fails.

---

## 🔬 Engineering: defects found by measurement

All four were found today by measuring rather than reading, and all four are now guarded by
tests.

### 1. One Indian mobile in ten was reported as a leaked Aadhaar number

An Indian phone number written `+91XXXXXXXXXX` is twelve digits. Aadhaar is twelve digits with
a Verhoeff check digit — and **twelve arbitrary digits clear Verhoeff by chance about one time
in ten** (measured: 520 of 5000, 10.4%). The overlap resolver ranked checksum-validity above
match length, so that chance hit outranked the phone match that explained the whole string.

Roughly one user in ten would have been told their national ID had leaked when it was only
their own phone number — in a tool whose entire pitch is that it does not fabricate findings.

Two fixes in `backend/pii/recognizer.py`:

```python
r'(?<![+\d])\b([2-9]\d{3})\s?(\d{4})\s?(\d{4})\b'     # a leading '+' is a country code, never a national ID
candidates.sort(key=lambda c: (-c[1], -c[0], -c[2], c[3].start))   # span BEFORE the checksum flag
```

Span has to outrank the checksum flag because candidates whose validator *failed* were already
dropped, so the flag only separates "carries a check digit" from "carries none".

Measured after the fix:

```
5000 random +91 mobiles     → 0 reported as Aadhaar   (520 of them clear Verhoeff by chance)
3000 valid Aadhaar numbers  → 3000 detected
```

### 2. Two tests that could never fail

Two assertions were written as `assert(x) or True` — true whatever the function returns. One
was named "Verhoeff validates correctly", and it passed while the function returned `False` for
the number the test claimed it accepted. Both now assert against published Verhoeff test
vectors (236 carries the check digit 3, so 2363 is valid and 2364 is not).

A test that cannot fail is worse than no test: it buys confidence it has not earned.

### 3. `.lstrip('91')` strips characters, not a prefix

`backend/pii/resolver.py` normalised phone numbers with `.lstrip('0').lstrip('91')`. `lstrip`
takes a *character set*, so it ate every leading `9` and `1`: `9111111111` was reduced to the
empty string and matched nothing, while `9198765432` and `8765432` — two different numbers —
both collapsed to `8765432` and **matched each other**. It now compares the last ten digits.

### 4. Date of birth was never compared at all

`date_of_birth` was missing from the resolver's `FIELD_WEIGHTS` table entirely, so two records
could agree on it and the agreement counted for nothing. It is the field that most often
separates two people who share a name — exactly the case the engine exists to decide. It now
carries weight 0.15, normalises to ISO so the rendering cannot decide the answer, and is
deliberately **not** a strong identifier (roughly one person in 36,500 shares any given one):
it corroborates a name, but cannot attribute a record alone.

### Also fixed today

- **Severity was silently collapsing to "minor".** XposedOrNot names data classes in its own
  vocabulary ("Government Issued IDs", "Passwords History", "Partial Credit Card Data").
  Unmapped labels fell through to `low`, so a breach exposing government IDs and passwords was
  reported as minor. **60 labels** are now mapped onto canonical field names
  (`XPOSED_LABEL_TO_FIELD`), and an unknown label is kept in normalised form rather than
  silently dropped. Found by a test.
- **Passwords borrowed the credit-card weight as a hack.** `PASSWORD` (9.0), `AUTH_TOKEN`
  (9.5 — a session token bypasses the password entirely), `SECURITY_ANSWER` (8.0 — it *resets*
  the password, so it outranks it), `GOVERNMENT_ID` (9.5), `PASSPORT` (9.0), `SSN` (9.5) and
  `SPECIAL_CATEGORY` (7.5 — religion, ethnicity, sexual preference; DPDP s.2 / GDPR Art.9 data,
  where the harm is not financial and cannot be undone by changing a credential) now carry
  their own weights in `backend/pii/risk_calculator.py`.
- **A raw slug leaking into the UI.** The `statutory_only` removal method had no `method_info`
  entry, so users saw a slug instead of an explanation that SEBI's five-year post-closure KYC
  retention and IRDAI's rules lawfully override the DPDP erasure right. Found by a new test.

---

## ⚡ Core algorithms

**Verhoeff (Aadhaar).** Dihedral group D₅ permutation checksum. A failed checksum is
disqualifying — Aadhaar, card and account numbers carry check digits precisely so that a
number-shaped string can be rejected, and honouring that is the entire value of the algorithm.

**Luhn (payment cards).** Mod-10 validation for Visa, MasterCard, RuPay and Amex. The Aadhaar
pattern matches the first 12 digits of a 16-digit card, so the longer, checksum-validated match
wins its span — otherwise the tool tells users their Aadhaar leaked when it saw a card.

**Jaro-Winkler + token-set record linkage** (`backend/pii/resolver.py`). Field scores are
weighted, then **discounted by corroboration**: averaging only over the fields that happen to be
present means a record containing nothing but a matching name scores 1.0, and on a common name
that is a stranger. A unique identifier gives full weight; three agreeing non-unique fields give
0.80; two give 0.65; one gives 0.40. `is_match` additionally requires a unique identifier —
name + city is surfaced as `needs_confirmation`, never acted on.

**Privacy Risk Score** (`backend/pii/risk_calculator.py`). Weighted over data sensitivity,
source credibility, recency and broker spread, bounded to [0, 100]. An open-web hit confirmed by
fetching the page carries higher source credibility (0.95) than a broker's probabilistic claim,
because it is directly observed rather than inferred.

**Chained SHA-256 audit trail** (`backend/remediation/audit_crypto.py`). Every notice generated
or dispatched mints a receipt whose hash covers the previous block's hash, rooted at a genesis
block. `GET /api/audit/verify` walks the chain.

---

## 💾 Memory

State lives in SQLite (`data/sovereign.db`, WAL mode) across `users`, `identities`, `exposures`,
`requests`, `agent_events`, `audit_receipts` and `runs`. The agent therefore remembers across
runs: which exposures it already knows, which requests are in flight, and what the risk score
was last time.

The consequence that matters: re-scanning after a removal detects a record that has
**reappeared** (a distinct status) rather than logging it as new. Brokers re-list.

---

## 📊 Datasets

| Dataset | Records | Role |
|---|---|---|
| Optery data-broker registry | 956 | Categorised brokers, opt-out URLs, difficulty ratings, privacy emails |
| HIBP verified breach catalog | 1,039 | Breach metadata — facts *about* breaches, not about a person |
| Indian sources registry | 51 | Classified by which statute reaches them |
| Removal playbooks | 66 | Cheapest-effective-route table with steps and escalations |
| Synthetic paste corpus | 50 | Leak-dump matching (sandbox) |
| PII ground-truth benchmark | 390 | Regression benchmark for the recogniser |
| Statutory templates | 3 | DPDP 2023 s.12/13, GDPR Art. 17, CCPA § 1798.105 |

---

## 🧪 Tests

```bash
./.venv/bin/python test_system.py
```

```
ALL 334 TESTS PASSED in 0.88s
```

(Wall time varies by a few tenths of a second; the count is the part that matters.)

15 sections. The largest are the ones that guard the honesty rules, which is deliberate:

| Section | Tests | What it enforces |
|---|---|---|
| 9. Evidence policy | 54 | Anti-fabrication. Verifies exact endpoints, rates, error resilience, and synthetic quarantine |
| 14. Free breach intelligence | 50 | XposedOrNot & Hudson Rock record endpoints, severity scores, and state what they do **not** prove |
| 12. Open-web search | 46 | Exact-phrase search, candidate demotion, phone boundary isolation, zero false positives |
| 3. Identity resolver | 29 | Name-part collisions, alias derivations, phone/email normalisation |
| 15. Fiduciary Directory & Threat Surface Intelligence | 27 | Operating fiduciary DPDP s.12 rights, Grievance Officer lookup, loop tool coverage, and attack surface correlation |
| 2. PII recognizer | 24 | Verhoeff/Luhn validation, phone prefixing, false-positive protection on timestamps/cards |
| 10. Attribution | 24 | No stranger's account is flagged as yours, scoped-handle non-transferability |
| 13. Discovery site roster | 22 | Kaggle and Replit stay excluded *with a recorded reason*; every searched site has a playbook |
| 1. Dataset Integrity | 13 | Corpus verification, broker rosters, and leak dump integrity |
| 11. Identifier verification | 11 | Deliverability, MX check, dev-mode non-attribution, and verification codes |
| 5. Legal Notice Generator | 10 | DPDP 2023 s.12/13, GDPR Art. 17, CCPA § 1798.105 statutory text formatting |
| 6. Cryptographic Audit Trail | 7 | SHA-256 tamper-evident hash chaining and proof verification |
| 7. Statutory Compliance Tracker | 7 | Deadline tracking, statutory clocks, and escalation triggers |
| 4. Risk Calculator | 5 | Privacy risk scoring, threat surface quantification, and severity weighting |
| 8. Scanner Modules | 5 | Scanner integration, error resilience, and output hygiene |

### On the PII benchmark number

The benchmark is **synthetic and self-generated** (`data/download_datasets.py`), so it measures
the detector against known-correct inputs, not messy real-world text. **Treat it as a regression
guard, not evidence of field accuracy.** It currently reports 100.0% precision / recall / F1
against the 390-sample corpus.

The part that carries real signal is the negative set: samples that look like Indian identifiers
but are not, including correctly-shaped 12-digit numbers with deliberately wrong Verhoeff check
digits. Invoice numbers, transaction ids and timestamps look exactly like this in the wild.

That property is enforced by the generator, not assumed: positives carry **correct** check
digits and the negative set contains number-shaped strings that pass the regex but **fail** the
checksum. An earlier build's Aadhaar samples were themselves checksum-invalid while the
validator was non-binding, so the checksum was being scored against nothing — a benchmark that
agrees with the code by construction measures neither.

Scoring is on `(type, value)` pairs, not on the set of types present: comparing types alone
cannot tell a correct extraction from one that found the right *kind* of thing in the wrong
place, so "an AADHAAR was detected" would score a hit even when the digits reported were
somebody's phone number.

### Planner benchmark

`benchmark_planner.py` scores a planner out of 100 on the thing this task actually needs — can
it sequence the tools, and **does it respect the refusal rules**? It declares a deliberate mix:
Truecaller and Naukri must be drafted; Indian Kanoon, CIBIL and Zauba Corp must be refused.
That refusal check is worth 35 of the 100 points, because it is the discriminator: weak models
cheerfully draft a DPDP notice against an Indian court record, since "draft the notice" is the
obvious next step and the rule forbidding it is three paragraphs up the system prompt.

```bash
APNIPEHCHAAN_PLANNER=groq ./.venv/bin/python benchmark_planner.py
```

---

## 🔌 API reference

### Agent

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/agent/info` | Which planner is live, the live tool list, the evidence policy |
| `GET` | `/api/agent/brokers` | The simulated broker environment, disclosed |
| `POST` | `/api/agent/scan` | Phase 1 — discover, assess, decide, draft. Dispatches nothing |
| `POST` | `/api/agent/approve` | Phase 2 — dispatch approved notices, follow up, verify, escalate |
| `POST` | `/api/agent/confirm` | Resolve a parked candidate: is this account yours? |
| `POST` | `/api/agent/chat` | Sitewide privacy copilot, context-aware over the current tab |
| `GET` | `/api/agent/state/{user_id}` | Current exposures, requests and identities |
| `GET` | `/api/agent/latest` | Dashboard state for the most recently active user |
| `GET` | `/api/agent/events/{run_id}` | Full trace of one agent run |
| `POST` | `/api/agent/reset` | Wipe an identity to re-run the demo cleanly |
| `WS` | `/ws/agent` | Live agent feed — reasoning and tool calls as they happen |

`/ws/agent` emits each message at the moment the agent reaches that step. The legacy `/ws/scan`
padded its output with `asyncio.sleep()` so the terminal looked busy; the agent feed has **no
artificial delays**.

### Identifier verification, config, sources

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/verify/status` | Whether SMTP is configured for one-time codes |
| `POST` | `/api/verify/request` | Send a one-time code to an email/phone |
| `POST` | `/api/verify/submit` | Submit the code |
| `GET` | `/api/sources/indian` | The 51 classified Indian sources |
| `GET` | `/api/config/status` | Which keys are configured, masked |

### Scanning, PII, legal, compliance, audit

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/status` | Health, dataset counts, audit chain status |
| `GET` | `/api/datasets/summary` | Loaded breach catalogs and brokers |
| `POST` | `/api/scan/full` | Multi-vector scan |
| `POST` | `/api/scan/hibp` · `/brokers` · `/pastes` | Targeted scans |
| `POST` | `/api/pii/detect` | Hybrid PII extraction on arbitrary text |
| `GET` | `/api/pii/benchmark` | Live precision / recall / F1 benchmark |
| `GET` | `/api/legal/jurisdictions` | Supported frameworks |
| `POST` | `/api/legal/generate` · `/dispatch` | Compile and serve a notice, mint the receipt |
| `GET` | `/api/compliance/requests` · `/request/{id}` · `/overdue` | Deadline clocks |
| `POST` | `/api/compliance/update` | Record a controller response |
| `GET` | `/api/audit/trail` · `/latest` · `/verify` | The receipt ledger and chain integrity |
| `WS` | `/ws/scan` | Legacy streaming scan terminal |

---

## ⚠️ Known limitations

Stated plainly, because they are real and a reviewer will find them.

- **The free breach dataset is not authoritative.** XposedOrNot is a different corpus from HIBP.
  A clean result there means clean *in that dataset*, and the interpretation string in every
  Evidence object says so. Set `HIBP_API_KEY` for the authoritative answer as well.
- **The open-web search depends on an engine that rate-limits.** When throttled, the product
  reports "could not check" and explicitly refuses to report "clear". The fallback index has far
  smaller coverage, and a secondary index returning nothing is **not** treated as evidence of
  absence.
- **The broker network is a simulation and is OFF by default.** Real controllers take weeks and
  require identity verification, so the removal *lifecycle* is only demonstrable against a
  controlled environment (8 simulated controllers, `backend/mock_brokers/network.py`).
  Everything it produces is tagged `sandbox`. There is no UI toggle: it is reachable only via
  `POST /api/agent/scan` with `{"sandbox": true}`.
- **Identifiers are trusted as typed.** The OTP flow exists but is unwired (see above). The
  failure mode is fewer attributions, not wrong ones.
- **The PII benchmark is synthetic.** Regression guard, not field accuracy.
- **Indian people-search sites are not queried.** None publish an API for it, and probing signup
  or password-reset endpoints to enumerate accounts would breach their terms. The tool asks the
  user instead — and a person's own knowledge of which services they signed up for is itself
  valid grounds for a Section 12 request.
- **Local processing has an honest boundary.** Scanning runs against locally held datasets and
  the free public endpoints listed above. Identifiers are posted from the browser to your own
  backend in plaintext over the local connection. Passwords are the exception and are never
  transmitted: only a 5-character SHA-1 prefix leaves the machine.
- **No paid API is used anywhere.** Deliberate — but it means coverage is free-tier coverage,
  and that is a real ceiling.

---

## 📄 License
MIT License. Created for the 24-Hour Hackathon 2026.
