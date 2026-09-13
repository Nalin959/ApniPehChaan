# ApniPehChaan — Presentation & Demo Guide

## Track: Digital Identity & Sovereign Privacy Protection
> **Mission**: Build proactive personal agents that actively monitor web data leaks, handle automated right-to-be-forgotten legal requests, and protect individual privacy against invasive data-scraping networks.

**One line:** give it your identity, and an agent goes and looks — free breach corpora,
info-stealer infection corpora, 26 public-profile namespaces and the open web — proves every
finding against a live endpoint, decides which Indian statute actually applies to each one,
drafts the notices, and stops for your approval before serving anything.

**It costs nothing to run.** No paid API is called anywhere in the product. That was a
deliberate constraint, and it is the reason the central feature works at all — see the 1:10
beat of the script below.

---

## 🏆 Alignment with the judging criteria

| Criterion | What to point at |
|---|---|
| **1. Problem Understanding & Impact** | India's DPDP Act 2023 grants a statutory right to erasure (s.12) and grievance redressal (s.13). Exercising it means identifying which of hundreds of entities hold you, knowing which of them the right even reaches, and proving deletion afterwards. The tool's hardest design constraint comes from the problem: **a name identifies nobody**, so a privacy tool that guesses from names helps you demand deletion of a stranger's records. Every attribution rule in the build exists because of that. |
| **2. Innovation & Creativity** | **Breach detection that is free.** HIBP's per-address lookup needs a paid key; XposedOrNot and Hudson Rock answer for free, so the product's central question works with no card on file. **Info-stealer detection** — a whole exposure class nothing else in the field surfaces, with remediation that is credential rotation, not a legal notice. **Search-result-as-lead**: the open-web search fetches every page and requires the identifier verbatim before reporting it. **Legal refusal engine**: distinguishes commercial processing from court records and statutory registers. |
| **3. Agentic AI Implementation** | 21 tools over one registry; the planner is given only the tools its phase needs, and `submit_erasure_request` is absent from the discovery toolset entirely, so the agent *cannot* dispatch. Memory in SQLite means a re-scan detects a record that has **reappeared** rather than logging it as new. Any of three planner backends drives the identical tools; the badge says which is live. |
| **4. Technical Implementation** | Four real defects found and fixed by measurement today — see **The engineering story** below. Every exposure carries an endpoint, a timestamp, an HTTP status and a `curl` you can run. **All 260 tests pass** (`./.venv/bin/python test_system.py`). |
| **5. Solution Effectiveness & Usability** | The removal ladder picks the cheapest route that works: a delete link beats a 30-day statutory notice. Unattributed candidates are held out of the ledger, the risk score *and* the removal plan until you confirm them. When a check cannot run, it says **"could not check"** and never "clear". |
| **6. Demo & Presentation** | The trace is live — every line appears when the agent reaches that step, with no `asyncio.sleep()` padding. Every proof panel carries a reproduce command a sceptical judge can paste into a terminal. |

---

## Before you start

```bash
./run_demo.sh          # or: .venv/bin/python -m uvicorn backend.app:app --port 8000
```

Open <http://localhost:8000> — **Privacy Agent** is the landing tab.

**Keys are optional.** With no `.env` at all the product runs end to end: every breach
check, the account discovery, the open-web search, the legal reasoning and the drafting all
work, and the trace says `deterministic` instead of naming a model. A free
`GROQ_API_KEY` in `.env` makes the planner an LLM and the trace shows its actual
reasoning — worth 30 seconds of setup before you present.

**Use a real, well-used email address** — ideally an old one. The free breach corpora only
have something to say if the address is actually in them. Test yours before the room is
watching:

```bash
curl -s 'https://api.xposedornot.com/v1/breach-analytics?email=YOUR@EMAIL' | head -c 400
```

---

## 3-minute script

### 0:00 — The problem (25s)

> "Under Section 12 of India's DPDP Act, every citizen has a statutory right to erasure.
> Exercising it means finding which of hundreds of entities hold your data, knowing which of
> them that right even reaches — it doesn't reach a court judgment or a statutory register —
> drafting the notice, and then proving the data actually went.
>
> Most tools that try this fail the same way: they guess your username from your legal name.
> Thousands of people share a name, so what they hand you is a stranger's accounts, and then
> they help you demand deletion of a stranger's data. That is worse than no tool. Everything
> in this build is shaped by refusing to do that."

### 0:25 — Deploy, and watch it actually look (45s)

Fill the form:

```
Full name:         <your name>
Email:             <a real, old email address>
Phone:             <your 10-digit mobile>
Usernames you use: <a handle you actually use>
Services:          Truecaller, Naukri.com, Indian Kanoon, CIBIL
Password:          password123
```

Click **Deploy Privacy Agent**.

> "Every line appears when the agent gets there — nothing is animated."

**Point at the password line first.** It is the fastest proof beat:

> "That password was checked against real breach corpora and came back compromised. It never
> left this machine: only the first five characters of its SHA-1 were sent, the API returned
> every hash sharing that prefix, and the match happened locally. The server cannot know
> which password we checked. That's k-anonymity."

### 1:10 — The headline change: breach detection, for free (30s)

**Point at the breach lines.**

> "Until this morning this was the one thing the tool could not do. The authoritative answer
> to 'is my address in a breach' is Have I Been Pwned, and per-address lookups need a paid
> subscription. Without one we refused to guess — so the single most important feature was
> switched off for anyone without a card on file.
>
> It now runs on XposedOrNot, which is free and needs no key. We kept it as its own named
> dataset rather than merging it into HIBP, because they are different corpora: where they
> agree that is corroboration, and absence in one is not absence in the other. If you *do*
> set `HIBP_API_KEY`, both run."

**Then the one nobody else has** — if the address has a hit, this is your best 20 seconds of
the whole demo:

> "This one is different in kind. A breach leaks what one company held about you. An
> info-stealer infection means a computer you used was running malware that copied the entire
> browser password store in one go — every password, every cookie, every session token, taken
> together. And these credentials are *current*, not historic.
>
> That's Hudson Rock's free infection corpus. Note what the remediation says: it does **not**
> draft a legal notice, because there is no controller to serve — the data came off your own
> machine. It says rotate in dependency order, email first because it resets everything else,
> then your SIM account, then banking and UPI. And it insists you revoke all sessions, because
> a stolen session cookie walks straight past your new password."

*(No hit? Say so, and use it: "Clear in that corpus — and notice it says clear **in that
dataset**, not clear everywhere. That distinction is enforced in the code.")*

### 1:40 — Proof, and what it refuses to claim (25s)

Scroll to the **Exposure Ledger**. Every row carries an evidence badge saying how it is
known. Click **show proof** on any row:

```
check       gravatar
endpoint    https://www.gravatar.com/avatar/205e460b...?d=404
queried     <timestamp>
HTTP        200
evidence    HTTP 200 — an avatar is served for MD5 205e460b...
means       CONFIRMED: a public Gravatar profile exists for this address
verify it   curl -sI 'https://www.gravatar.com/avatar/205e460b...?d=404'
```

> "Endpoint, timestamp, status code, and a command you can run yourself. Don't take our word
> for it."

If the open-web search was rate-limited, **point at it** — the failure is the feature:

> "The engine throttled us, so it says the web could **not be checked**. It specifically
> refuses to say 'clear'. A rate-limited engine returns a page with nothing on it, which is
> byte for byte identical to a genuine 'nothing found' — and reporting the first as the second
> would tell someone their data is nowhere online at the exact moment the tool had stopped
> being able to look. That is the one failure a privacy scanner must never have."

### 2:05 — The legal reasoning (35s)

This is the part nothing else does. Point at the `legal` lines:

```
Truecaller:    DPDP Act 2023 → request_erasure              ✓ drafted
Naukri.com:    DPDP Act 2023 → request_erasure              ✓ drafted
Indian Kanoon: NO ERASURE RIGHT (court record)              ✗ refused
CIBIL:         NO ERASURE RIGHT (CICRA retention duty)      ✗ refused
```

> "In India 'can I get this deleted?' is not one question. Truecaller is commercial
> processing — Section 12 applies, so it drafts. Indian Kanoon is a court record; the DPDP Act
> does not reach judicial proceedings, so it refuses and names the real route, an application
> to the court that issued the judgment. CIBIL has a competing retention duty under CICRA
> 2005 — you can dispute and correct, but not erase.
>
> A naive build mails 'please delete my data' to a High Court judgment index. That letter has
> no addressee in law. Telling someone they have a remedy they don't have is worse than saying
> nothing."

### 2:40 — The approval gate, and close (20s)

> "It drafted the notices and stopped. It *cannot* send them — dispatch is withheld from its
> toolset entirely during discovery, so this is a limit on the agent's autonomy, not a missing
> button. Serving a statutory notice is irreversible and aimed at a third party, so a human
> decides."

Expand a notice to show the real citation, then click **Approve & Dispatch Selected**.

> "Discover, prove, reason, act, verify — a human on anything irreversible, and no claim the
> tool cannot substantiate."

---

## The engineering story

This is the strongest material for **Technical Implementation**. Four real defects, all found
by measuring rather than by reading, all fixed today, all now guarded by tests.

### 1. One Indian mobile in ten was being reported as a leaked Aadhaar number

An Indian phone number written `+91XXXXXXXXXX` is twelve digits. Aadhaar is twelve digits with
a Verhoeff check digit — and twelve arbitrary digits clear Verhoeff **by chance about one time
in ten**. The recognizer's overlap resolver ranked checksum-validity above match length, so
that chance hit outranked the phone match that explained the whole string.

Roughly one user in ten would have been told their national ID had leaked when it was only
their own phone number — in a tool whose entire pitch is that it does not fabricate findings.

Two fixes: a negative lookbehind so a leading `+` marks a telephone country code and never a
national ID, and span before checksum in the sort key (candidates whose validator failed are
already dropped, so the flag only separates "carries a check digit" from "carries none").

Measured after the fix, reproducible in about 30 seconds:

```
5000 random +91 mobiles          → 0 reported as Aadhaar
   of those, 520 (10.4%) clear Verhoeff by chance
3000 valid Aadhaar numbers       → 3000 detected
```

Guarded by `test_system.py` §2: `+918760560500 is a phone, not an Aadhaar`.

### 2. Two tests that could never fail

Two assertions were written as `assert(x) or True` — true whatever the function returns. One
was named "Verhoeff validates correctly", and it had been passing while the function returned
`False` for the number the test claimed it accepted. Both now assert against published Verhoeff
test vectors (236 carries the check digit 3, so 2363 is valid and 2364 is not).

> If you want one line for this slide: *a test that cannot fail is worse than no test, because
> it buys confidence it has not earned.*

### 3. `.lstrip('91')` strips characters, not a prefix

The identity resolver normalised phone numbers with `.lstrip('0').lstrip('91')`. `lstrip` takes
a *character set*, so it ate every leading `9` and `1`: `9111111111` was reduced to the empty
string and matched nothing, while `9198765432` and `8765432` — two different numbers — both
collapsed to `8765432` and matched each other. It now compares the last ten digits, which is
what identifies an Indian mobile however it was written.

### 4. Date of birth was never compared at all

`date_of_birth` was missing from the resolver's `FIELD_WEIGHTS` table entirely, so two records
could agree on it and the agreement counted for nothing. It is the field that most often
separates two people who share a name — precisely the case the engine exists to decide. It now
carries weight 0.15, is normalised to ISO so the format cannot decide the answer, and is
explicitly **not** a strong identifier (about one person in 36,500 shares any given one), so it
corroborates a name but cannot attribute a record alone.

### Two more, if you have time

- **Severity was silently collapsing to "minor".** XposedOrNot names data classes in its own
  vocabulary ("Government Issued IDs", "Passwords History"). Unmapped labels fell through to
  `low`, so a breach exposing government IDs and passwords was reported as minor. 60 labels are
  now mapped onto canonical field names. Found by a test.
- **A slug leaking into the UI.** The `statutory_only` removal method had no `method_info`
  entry, so the interface showed users a raw slug instead of explaining that SEBI's five-year
  post-closure KYC retention and IRDAI's rules lawfully override the DPDP erasure right.

### Measurement drove the site roster too

Account discovery checks 26 public-profile namespaces; 17 more are listed with a reason and
never queried. Every one was tested against a handle known to exist *and* one known not to.

Two were removed today after measurement:

- **Kaggle** — returned HTTP 200 for 5 of 5 invented handles. It was previously trusted, so it
  was reporting accounts that do not exist.
- **Replit** — returns HTTP 404 even for handles that demonstrably exist (its own founder's),
  so a 404 proves nothing and a hit can never occur.

> "Instagram, Pinterest, Medium and PyPI all serve HTTP 200 for usernames that don't exist —
> a login wall or a soft-404. A tool that trusted the status code would tell you that you have
> an Instagram account when you don't. So silence beats a false claim: they are excluded, with
> the reason written down."

---

## Likely questions

**"Is the AI actually doing anything, or is this a script?"**
21 tools in one registry. With a planner key, the model chooses each call in the judgement and
remediation phases and its reasoning streams to the UI; with no key a deterministic pipeline
drives the identical tools. The badge says which. `GET /api/agent/info` returns the live tool
list and the evidence policy.

Be precise about the split, because it is a deliberate design decision worth defending: the
mandatory *gathering* is deterministic — asking a model to remember to call
`build_identity_profile` wastes a round trip and is a reliability risk. The planner is given
the part that actually needs reasoning: which exposures are worth acting on, which statute
applies, and whether a notice should be drafted at all. Measured, leaving the whole sequence to
the planner took ~117s and it still skipped fourteen of the twenty tools it was given.

**"How do I know you're not making the findings up?"**
Every row carries an `evidence_class`: `verified` (a live endpoint returned a hit),
`self_declared` (you told us), `candidate` (held back for your confirmation), or `sandbox`
(synthetic, off by default, labelled). Click *show proof* for the endpoint and a reproduce
command. §9 of `test_system.py` is 47 tests enforcing this, including one that fails if the
old fabrication code ever returns.

**"What stops it flagging someone else's account as mine?"**
A username match is never proof of identity. It becomes a finding only if the page itself
carries something that belongs to exactly one person — your email, your phone, your UPI ID, a
link to an account already proven. Otherwise it is parked as a **candidate**, kept out of the
ledger, the risk score and the removal plan until you confirm it.

A handle that is just your name or surname is high collision risk and is never auto-attributed,
*even if you declared it*: saying "I use the handle `sharma`" claims a habit, not the `sharma`
account on every site that has one. Write `github:sharma` to claim one namespace outright.
Legal names are never used to derive handles at all, and never searched.

**"Why is Kaggle in the excluded list when it's a real site?"**
Because we measured it and it fails the test that matters. See above.

**"You're using a free breach dataset. Is it as good as HIBP?"**
No, and the product does not claim it is. XposedOrNot is a different corpus, reported under its
own name, and "clear" there means clear in *that* dataset. HIBP is still called when a key is
present. The honest framing: free-tier coverage is a real limitation, and merging the two into
one confident answer would have hidden it.

**"Why can't you check Truecaller or JustDial directly?"**
No Indian people-search site publishes an API for it, and probing signup or password-reset
endpoints to enumerate accounts would breach their terms. So the tool asks you — you know which
services you signed up for, and that knowledge is itself valid grounds for a Section 12 request.

**"What about the credit card / Aadhaar detection?"**
Run `./.venv/bin/python test_system.py`. The PII benchmark is **synthetic and
self-generated**, so treat it as a regression guard rather than an external
accuracy claim — its value is that it fails loudly when a detector regresses.
(The in-UI Accuracy Lab tab was removed; the suite is the source of truth.)

**"What breaks with no network?"**
Live checks report `unavailable` and claim nothing. The LLM planner falls back to the
deterministic pipeline. Nothing fabricates a result to fill the gap.

---

## Known limits — say these before a judge finds them

- **The free breach dataset is not authoritative.** XposedOrNot is a different corpus from
  HIBP. A clean result there means clean in that dataset only.
- **The open-web search depends on an engine that rate-limits.** When throttled, the product
  reports "could not check" and explicitly refuses to report "clear". There is a fallback index
  (Marginalia) with far smaller coverage, and results are cached for six hours so a re-run
  costs no queries — but a partial answer stays labelled partial.
- **Typed identifiers are trusted as typed.** A full one-time-code flow exists in
  `backend/agent/verification.py` but is not wired into the UI. This is safe in the direction
  that matters: corroboration requires the identifier to actually appear on the page, so a
  mistyped address matches nothing and the failure mode is *fewer* attributions, never wrong
  ones.
- **The broker network is a simulation, and it is off by default.** Real controllers take weeks
  and require identity verification, so the removal *lifecycle* is only demonstrable against a
  controlled environment. Everything it produces is tagged `sandbox`. There is no toggle in the
  UI — it is reachable only by `POST /api/agent/scan` with `{"sandbox": true}`, so you cannot
  turn it on by accident mid-demo. If you want to show the full removal loop, call the API
  directly and rehearse it first.
- **The PII benchmark is synthetic.** It measures the detector against known-correct inputs,
  not messy real-world text.
- **No paid API is used anywhere.** Deliberate — but it means coverage is free-tier coverage,
  and that is a real ceiling, not a rounding error.
