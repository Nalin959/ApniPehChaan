# 3-Minute Demo Script

> Replaces the script in `HANDOVER.txt` §8, which no longer works: it used the PAN
> `ABCDE1234F` (structurally invalid — position 4 must be a holder-type character, so it is
> correctly rejected) and an email whose domain matches no breach, so the breach panel
> showed zero.

## Before you start

```bash
./run_demo.sh                 # or: .venv/bin/python -m uvicorn backend.app:app --port 8000
```

Open <http://localhost:8000> — the **Privacy Agent** tab is the landing tab.

- If `ANTHROPIC_API_KEY` is set, the badge reads **LLM PLANNER · claude-opus-5** and Claude's
  reasoning streams into the trace. If not, it reads **DETERMINISTIC PLANNER** and the product
  still works end to end. Either is demoable — just don't claim the LLM is driving when it isn't.
- Re-running with the same identity? Click **Reset this identity** first.

---

## 0:00 — The problem (25s)

> "India's DPDP Act gives you a right to erasure under Section 12. In practice you'd have to
> find every company holding your data, identify the right legal basis for each, write each
> notice, send it, chase it, and then somehow prove they actually deleted it. Nobody does that.
> The right exists on paper and goes unexercised.
>
> So we built an agent that does it."

## 0:25 — Deploy the agent (35s)

Type an identity. **Use the judge's own name** — records are seeded from whatever you type,
so this works for anyone:

```
Name:  Kavya Reddy
Email: kavya.reddy@example.com
Phone: +91 9900112233
City:  Hyderabad
```

Click **Deploy Privacy Agent**. Talk over the streaming trace:

> "It's recalling what it already knows about this identity, deriving aliases, then searching
> three surfaces. Every line appears when the agent actually gets there — nothing here is a
> scripted animation."

**Point at the `legal` lines.** This is the moment that separates this from a scanner:

> "It's picking a different statute per controller — GDPR for the EU broker, DPDP for the
> Indian ones, CCPA for the US one. And notice what it does with the breach records: it says
> erasure isn't available against a breach corpus. It won't draft a notice that can't land."

## 1:00 — The approval gate (25s)

> "It drafted four notices and stopped. It cannot send them — dispatch is withheld from its
> toolset entirely during discovery."

Expand one notice. Show the real statutory citation.

> "Serving a legal notice is irreversible and it's aimed at a third party. The agent decides
> *what* to send; a human decides *whether*. That's a deliberate limit on autonomy."

Click **Approve & Dispatch Selected**.

## 1:25 — Dispatch, chase, verify (55s)

Let the trace run. Call out three beats:

1. **Follow-up** — "DataFind Global didn't complete on first contact. The agent chased it."
2. **Verification** — "This is the important one. It's not trusting the controller's word.
   It re-queries the source independently and confirms the record is actually gone."
3. **Escalation** — "LeadMarket Pro never responded. The agent escalated it to the Data
   Protection Board of India under Section 27."

> "Two verified removals, one escalated. And the risk score moved — it's driven by what's
> still live, so it falls as records actually come down."

## 2:20 — Close (25s)

Show the exposure ledger with `✓ VERIFIED` badges.

> "Discover, decide, act, verify — with a human holding the trigger on anything irreversible.
>
> One disclosure: removal runs against a controlled broker network, because real brokers take
> weeks and need identity verification. That's stated in the UI. Everything being judged —
> the planning, the legal reasoning, the drafting, the dispatch, the follow-up, the
> verification — is real."

---

## Likely questions

**"Is the AI actually doing anything, or is it scripted?"**
Two planners over one tool surface. With a key set, Claude picks each tool and its reasoning
is in the trace. Without one, a deterministic pipeline runs the same tools. The badge says
which. `/api/agent/info` shows the tool list.

**"Why not let it send automatically?"**
Because it's irreversible and aimed at a third party. A false attribution would serve a legal
notice about someone else's record. We autonomised discovery and drafting, not dispatch.

**"How do you know it's the right person's record?"**
A name alone isn't enough — names aren't unique. A match needs a unique identifier (email,
phone) or several agreeing non-unique fields. A name-only record scores 0.40 and is rejected.
`test_system.py` has the regression test.

**"Is the data real?"**
The 1,035 HIBP breaches and 956 Optery brokers are real records. Breach *membership* is
simulated for the demo identity — a real check needs the paid HIBP API. The broker network
is simulated and labelled as such.

**"That 99.6% benchmark looks too good."**
It's synthetic and self-generated — a regression guard, not field accuracy, and the README
says so. The meaningful part is the negative set: 20 correctly-shaped 12-digit numbers with
bad Verhoeff check digits, all rejected. The previous 89.8% was measured against a benchmark
whose Aadhaar samples were themselves checksum-invalid while the validator wasn't enforcing.

**"What breaks if the network drops?"**
Nothing. Everything runs locally; the LLM path falls back to the deterministic planner.
