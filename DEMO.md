# 3-Minute Demo Script

> Supersedes the script in `HANDOVER.txt` §8 and the earlier version of this file.
> Both described a flow that synthesised breach membership. That is gone — the tool
> now only reports what it actually checked or what you declared.

## Before you start

```bash
./run_demo.sh          # or: .venv/bin/python -m uvicorn backend.app:app --port 8000
```

Open <http://localhost:8000> — **Privacy Agent** is the landing tab.

**Decide your mode first:**

| Mode | What you get | Use when |
|---|---|---|
| **Real-only** (default) | Live checks with reproducible proof + legal reasoning + refusals. No removal loop. | Default. Strongest on honesty and legal depth. |
| **+ Sandbox** (tick the box) | Everything above, plus the full dispatch → follow-up → verify → escalate lifecycle on synthetic records. | Last 30s, to show verification working. |

**Optional, big upgrade:** `export ANTHROPIC_API_KEY=sk-ant-...` flips the badge to
**LLM PLANNER · claude-opus-5** and streams Claude's actual reasoning. `export HIBP_API_KEY=...`
(~$3.95/mo) turns the breach check from *not checked* into a real verified result.

---

## 0:00 — The problem (25s)

> "India's DPDP Act gives you a right to erasure under Section 12. Exercising it means finding
> every company holding your data, working out which law applies to each, writing each notice,
> sending it, chasing it, and proving they actually deleted it. Nobody does that. The right
> exists on paper and goes unexercised.
>
> So we built an agent that does it. And it will not lie to you about what it found."

## 0:25 — Deploy (40s)

Fill in the form. **Use your own email** — the checks are real:

```
Name:      <your name>
Email:     <your real email>
City:      Mumbai
Accounts:  Truecaller, Naukri.com, Indian Kanoon, CIBIL
Password:  password123          ← safe to type, see below
```

Click **Deploy Privacy Agent**. Talk over the trace:

> "Every line appears when the agent actually gets there — nothing is animated."

**Point at the password line.** This is your first proof beat:

> "That password was checked against real breach corpora and came back compromised
> 2.2 million times. And it never left this machine — only the first five characters of
> its SHA-1 were sent. The match happened locally, so the server can't know what we checked.
> That's k-anonymity."

**Then point at what it refused to claim:**

> "Notice it says *one check could not run*. Breach membership for a specific address needs a
> paid HIBP subscription. We don't have one, so it says **not checked** rather than guessing.
> An earlier version of this invented that answer. We deleted it."

## 1:05 — Proof (30s)

Scroll to the **Exposure Ledger**. Every row has a "how we know" badge.

Click **show proof** on the Gravatar row:

```
check       gravatar
endpoint    https://www.gravatar.com/avatar/205e460b...?d=404
queried     2026-09-12T17:xx:xxZ
HTTP        200
evidence    HTTP 200 — an avatar is served for MD5 205e460b...
means       CONFIRMED: a public Gravatar profile exists for this address...
verify it   curl -sI 'https://www.gravatar.com/avatar/205e460b...?d=404'
```

> "Every claim carries the endpoint, the timestamp, the status code, and a command you can
> run yourself. Don't take our word for it — here's how to check."

*(If a judge is sceptical, run that curl in a terminal. It returns 200.)*

## 1:35 — The legal reasoning (45s)

This is the part nothing else does. Point at the `legal` lines:

```
Truecaller:    DPDP Act 2023 → request_erasure              ✓ drafted
Naukri.com:    DPDP Act 2023 → request_erasure              ✓ drafted
Indian Kanoon: NO ERASURE RIGHT (court record)              ✗ refused
CIBIL:         NO ERASURE RIGHT (CICRA retention duty)      ✗ refused
```

> "In India 'can I get this deleted?' isn't one question. Truecaller is commercial processing —
> Section 12 applies, so it drafts. Indian Kanoon is a court record; the DPDP Act doesn't reach
> judicial proceedings, so it refuses and tells you the real route is an application to the
> court that issued the judgment. CIBIL has a competing retention duty under CICRA 2005 — you
> can dispute and correct, but not erase.
>
> A naive build mails 'please delete my data' to a High Court judgment index. That letter has
> no addressee in law. Telling someone they have a remedy they don't have is worse than saying
> nothing."

## 2:20 — Approval gate (20s)

> "It drafted the notices and stopped. It cannot send them — dispatch is withheld from its
> toolset entirely during discovery. Serving a statutory notice is irreversible and aimed at a
> third party, so a human decides."

Expand a notice, show the real citation. Click **Approve & Dispatch Selected**.

## 2:40 — Close (20s)

If sandbox is on, let the removal loop run and land on:

> "It doesn't trust the controller's 'deleted'. It re-queries the source independently and only
> then marks it verified. LeadKart ignored the notice, so it escalated to the Data Protection
> Board of India under Section 27."

Otherwise close on the ledger:

> "Discover, prove, reason, act, verify — with a human on anything irreversible, and no claim
> the tool can't substantiate."

---

## Likely questions

**"Is the AI actually doing anything?"**
Two planners over one tool surface (16 tools). With a key, Claude picks each tool and its
reasoning is in the trace. Without one, a deterministic pipeline runs the same tools. The badge
says which. `GET /api/agent/info` returns the live tool list and the evidence policy.

**"How do I know you're not making these findings up?"**
Every row carries `evidence_class`: `verified` (a live endpoint returned a hit), `self_declared`
(you told us), or `sandbox` (synthetic, off by default, labelled). Click *show proof* for the
endpoint and a reproduce command. 14 tests in `test_system.py` §9 enforce this — including one
that fails if the old fabrication code ever returns.

**"Why can't you check Truecaller or JustDial directly?"**
They publish no API for it, and probing signup or password-reset endpoints to enumerate accounts
would breach their terms. So we ask you. You know which services you signed up for, and that
knowledge is itself valid grounds for a Section 12 request.

**"Why is the sandbox there at all?"**
Real controllers take weeks and require identity verification — you can't show a removal in
three minutes. The sandbox exists so the *lifecycle* is demonstrable. It's off by default and
everything it produces is tagged `sandbox`.

**"What about the credit card / Aadhaar detection?"**
Open the Accuracy Lab. 99.6% F1 on a synthetic benchmark — a regression guard, not field
accuracy, and the README says so. The meaningful part is the negative set: 20 correctly-shaped
12-digit numbers with deliberately wrong Verhoeff check digits, all rejected.

**"What breaks without network?"**
Live checks report `unavailable` and claim nothing. The LLM planner falls back to the
deterministic one. Nothing fabricates a result to fill the gap.
