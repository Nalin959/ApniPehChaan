# Implementation Plan — current problems, practicality, and what to do

Audited 2026-09-12 against the running build (12k lines, 20 agent tools, 149 tests passing).
**Revised after the planner work** — see the changelog at the end for what moved.

---

## The one problem that matters

**A realistic Indian user gets a completely empty screen.**

Measured, default settings, nothing declared:

```
Anjali Verma <anjali.verma1998@gmail.com> +91 9820145678
  findings          : 0
  candidates        : 0
  removal plan items: 0
  risk score        : 0
```

Every honesty fix was correct, and together they removed everything the product used
to display. Nothing is fabricated any more — and nothing is shown either.

The causes, in order of how much they cost:

| Cause | Why it returns nothing |
|---|---|
| HIBP needs a paid key | The single biggest source of real findings is switched off |
| Gravatar is rare in India | Works, but most Indian users have never made one |
| Handles are only searched if declared | Correct — but a first-time user declares nothing |
| Paste corpus is synthetic | `match_unique_identifiers` can never hit for a real person |

**But the product does work when the user tells it where they are.** Same user, seven
declared services:

```
PLAN: 3 self-serve | 0 notices | 2 not removable | ~50 min
  Naukri.com   → delete profile          Truecaller → unlisting page
  Shaadi.com   → delete (not hide)       JustDial   → grievance officer
  CIBIL        → dispute, cannot erase   Indian Kanoon → court application
```

That is real, correct, legally classified, and entirely unfabricated.

**So the fix is not more scanning. It is admitting what this product actually is:**
not a magic scanner that finds you, but a privacy remediation assistant that tells you
exactly how to get out of the places you already know you are — with the Indian legal
classification nobody else does.

---

## P0 — must fix before judging

### P0.1 First-run returns something useful (~2h)

The scan currently ends in silence. It should end in a next action.

- When discovery yields nothing, do not render an empty dashboard. Render a
  **guided intake**: "We checked everything that can identify you. To find more,
  tell us which services you use." with the 22-source Indian registry as tick-boxes
  grouped by category (Jobs · Matrimonial · Directories · Financial · Government).
- Ticking boxes feeds `declared_accounts` and re-runs. Two clicks to a real plan.
- Show what WAS checked and came back clean, so the emptiness reads as a result
  rather than a failure: "email checked against Gravatar ✓, HIBP (needs key) ⚠,
  50 leak records ✓ — nothing found."

**Files:** `frontend/index.html`, `frontend/app.js`, new `/api/sources/indian` render.
**Risk:** none — additive.

### P0.2 Set `HIBP_API_KEY` (~10 min, $3.95)

Highest value-per-minute change available. The integration is already written and
tested; it returns `not_checked` purely because no key is configured.

The catalog holds 23 Indian consumer breaches — BigBasket 24.5M, RailYatri 23.2M,
Domino's India 22.5M, IndiaMART 20.2M — plus 514 breaches over 1M records. A typical
Indian gmail address is plausibly in several. This turns the empty screen into real,
attributed, provable findings.

**Files:** none. `export HIBP_API_KEY=...`
**Risk:** none. Without it the product degrades exactly as it does today.

### ~~P0.3 Set `ANTHROPIC_API_KEY`~~ — **DONE, via Gemini instead**

Resolved without paying. The Anthropic account had no credit, so the planner now runs
on **Gemini 2.5→3.6 Flash free tier**. Confirmed working: a live run recorded
`mode=gemini, model=gemini-3.6-flash` with no fallback, and Gemini chose a *different*
tool order than the pipeline (it ran `declare_known_accounts` before the breach checks
— a sensible call it made on its own).

Three planner backends now exist, all driving the identical 20 tools:
`anthropic` · `gemini` · `openai_compat` (Groq, Cerebras, GitHub Models, Mistral,
OpenRouter, Together, Ollama) · plus the deterministic pipeline.

**NEW CONSTRAINT FOUND — this is the one that matters:**

```
quota: GenerateRequestsPerDayPerProjectPerModel-FreeTier   value=20
```

Twenty requests per day **per model**, and one agent run costs 15-20. A single model
therefore affords roughly ONE run per day. Mitigated by rotating across five Flash
models (each has its own allowance) for ~100 requests/day ≈ 5 runs — but that is still
tight for a rehearsal-plus-demo day.

Also measured, single tool-calling round trip:

| Model | Time | Note |
|---|---|---|
| **gemini-3.6-flash** | **3.1s** | default |
| gemini-flash-latest | 7.6s | |
| gemini-3.7-flash | 16.9s | |
| gemini-3.8-flash | 30.1s | and returns 503 under load |

The newest model is the wrong choice: 10x slower and capacity-throttled. `gemini-3.6-flash`
is the default.

**Remaining action:** get a free [Groq key](https://console.groq.com/keys) as a second
provider with an independent quota. One line in `.env`. Rehearse on
`SOVEREIGN_PLANNER=deterministic` and save the Gemini quota for the actual demo.

### P0.4 Commit the work (~5 min) — **now more urgent**

**23 files** uncommitted, including eight new modules: attribution, verification,
account discovery, removal playbooks, three planner backends, and the env loader.
A laptop hiccup loses all of it plus 149 tests.

`.env` is gitignored and chmod 600, so committing is safe.

---

## P1 — materially improves the demo

### P1.1 Retire or rewire the legacy tabs (~1.5h)

Five tabs (Command Center, Threat Scanner, Exposures, Legal Studio, Compliance) still
call six pre-agent endpoints — `api/scan/full`, `api/legal/generate`, `api/legal/dispatch`,
`api/compliance/*`. They bypass attribution entirely, so the Exposures tab can still show
speculative broker heuristics the agent would refuse to attribute.

A judge clicking around will find the inconsistency and it undercuts the honesty story.

**Options, cheapest first:**
1. Hide them behind a "Legacy (pre-agent)" section — 20 min, removes the contradiction.
2. Repoint Exposures at the agent ledger — ~1h, one source of truth.
3. Delete them — the PII Accuracy Lab tab was in fact removed on 2026-09-13 at the
   user's request; its evidence now lives in test_system.py.

**Recommendation:** option 1 now, option 2 if time allows. (Superseded: the
Accuracy Lab tab was removed; the test suite carries that evidence instead.)

### P1.2 Seed the leak corpus with the user's identifiers under a clear label (~1h)

`match_unique_identifiers` validates Aadhaar/PAN properly and searches 50 paste records,
but the corpus is synthetic and contains nobody real, so it can only ever return zero.
The capability is invisible.

**Do NOT fabricate.** Instead, gate it behind the existing sandbox toggle: when sandbox
is on, plant the user's identifiers in 1-2 leak records tagged `evidence_class: sandbox`,
so the validation-and-match path is demonstrable while staying labelled.

**Files:** `backend/mock_brokers/network.py` (or a new seeder), `backend/agent/tools.py`.

### P1.3 Onboarding line on the agent tab (~20 min)

Nothing tells a first-time user that declaring accounts is the high-value action. One
sentence above the form, plus making the "Usernames you actually use" and "Services you
hold an account with" fields visually primary.

---

## P2 — worth doing if time remains

| Item | Effort | Why |
|---|---|---|
| Re-enable OTP verification with real SMTP | 1h | Raises typed identifiers to proven ownership. Needs a Gmail app password. |
| Expand the verified discovery site list | 2h | 12 sites is thin. Each addition needs the real/fake reliability test — no shortcuts. |
| Broader Indian source registry | 1h | 22 sources covers the majority but misses regional portals. |
| Persist `not_mine` decisions across identities | 30 min | Currently per-user; a rejected handle re-appears for a different identity. |
| `/api/agent/export` — PDF of the plan | 1h | A judge-friendly artifact, and genuinely useful. |

---

## Explicitly NOT doing, and why

- **Scraping Truecaller / JustDial / Naukri to check membership.** No public API exists;
  probing signup or password-reset endpoints to enumerate accounts breaches their terms.
  The user is asked instead. This is a deliberate limit, not a missing feature.
- **Real dark-web feed.** Requires a paid data subscription. Pwned Passwords (free, real,
  k-anonymous) is what we can honestly offer; HIBP covers the rest for $3.95/mo.
- **Real broker removal.** Weeks of latency plus identity verification. The sandbox
  demonstrates the lifecycle and says so.
- **Widening the discovery list without the reliability test.** Instagram, Pinterest,
  Medium and PyPI all return HTTP 200 for usernames that do not exist. Adding sites
  without verifying both the positive and negative case reintroduces false positives —
  the exact bug this build spent the most effort eliminating.

---

## Honest scorecard against the judging criteria

| Criterion | State | Gap |
|---|---|---|
| Problem Understanding & Impact | **Strong** | DPDP framing, real Indian sources, correct legal classification |
| Innovation & Creativity | **Strong** | Legal-class refusals and the removal ladder are genuinely novel |
| Agentic AI Implementation | **At risk** | 20 tools, HITL gate, memory — but no API key means no live reasoning (P0.3) |
| Technical Implementation | **Strong** | 149 tests, real algorithms, honest evidence model |
| Solution Effectiveness & Usability | **Weak** | Empty first run (P0.1) is the single biggest hole |
| Demo & Presentation | **Good** | DEMO.md is current; needs P0.1 to avoid opening on an empty screen |

**Two changes carry most of the remaining value: P0.1 (guided intake) and P0.2 (HIBP key).**
Together they turn a technically honest but empty product into one that shows a real user
real findings and a real 50-minute plan to act on them.

---

## Suggested order

```
1. P0.4  commit                      5 min
2. P0.2  HIBP key                   10 min   ← biggest value per minute
3. P0.3  Anthropic key               5 min
4. P0.1  guided intake                2 h    ← biggest UX fix
5. P1.1  hide legacy tabs            20 min
6. P1.3  onboarding line             20 min
7. P1.2  sandbox leak seeding         1 h
```

Roughly four hours to close everything that materially affects judging.


---

## Changelog since the first draft

**Resolved**
- P0.3 — planner now runs live on Gemini free tier. No payment needed.

**New findings that change the plan**
- Gemini free tier is **20 requests/day/model**, not a rate limit you can wait out.
  Mitigated with model rotation (~5 runs/day), but plan rehearsals accordingly.
- `gemini-2.5-flash` is **retired for new keys** — Google returns 404 pointing at 3.6.
- Newest ≠ best: `gemini-3.8-flash` is 10x slower and 503s under load.
- A stale server process was serving pre-Gemini code for several minutes, showing
  "DETERMINISTIC PLANNER" long after the key worked. **Always restart after a config
  change** — the badge reads from the running process, not from `.env`.

**Built while diagnosing (not in the original plan)**
- `.env` loading with a startup banner naming the live planner
- Three-way planner routing with `SOVEREIGN_PLANNER` pinning
- Per-provider error messages: rejected key, unscoped org key, no credit, daily quota,
  503 capacity, model-not-found, unsupported tool calling
- Retry-with-backoff, distinguishing daily quota (skip model) from transient (retry)
- `benchmark_planner.py` — scores whether a model respects the legal refusal rules

**Unchanged and still the biggest gap: P0.1.** A realistic user still gets an empty
screen. The planner now reasons beautifully over nothing. That is the next thing to fix.
