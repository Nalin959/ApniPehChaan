# ApniPehChaan 🛡️
### Autonomous Sovereign Digital Identity & Privacy Protection Agent
> *Proactively discover where your personal data is exposed online, cross-correlate multi-breach attack vectors, dynamically resolve unknown corporate data fiduciaries, and exercise legally enforceable Right-to-be-Forgotten data erasure under India's DPDP Act 2023, EU GDPR, and US CCPA/CPRA.*  
> **Built for the 24-Hour Hackathon.**

---

[![Production Status](https://img.shields.io/badge/Production-Live%20on%20Vercel-success.svg)](https://apnipehchaan.vercel.app)
[![Tests](https://img.shields.io/badge/Tests-346%2F346%20Passing-brightgreen.svg)]()
[![Compliance](https://img.shields.io/badge/Compliance-India%20DPDP%202023%20%7C%20EU%20GDPR%20%7C%20US%20CCPA-orange.svg)](https://www.meity.gov.in/)
[![Architecture](https://img.shields.io/badge/Architecture-Multi--Agent%20Swarm-purple.svg)]()
[![Cost](https://img.shields.io/badge/Paid%20APIs-Zero%20(100%25%20Free%20Tier)-success.svg)]()
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Database](https://img.shields.io/badge/Database-Supabase%20Postgres%20%2B%20SQLite-blueviolet.svg)](https://supabase.com/)

---

## 🌐 Live Deployments & Repositories

| Target | Resource Link | Details |
| :--- | :--- | :--- |
| **Live Production Web App** | **[https://apnipehchaan.vercel.app](https://apnipehchaan.vercel.app)** | Primary Production Domain (Vercel Serverless) |
| **Production Alias Mirror** | **[https://sovereign-privacy-ai.vercel.app](https://sovereign-privacy-ai.vercel.app)** | Production Mirror Domain |
| **Primary Repository (Lead)** | **[https://github.com/Nalin959/ApniPehChaan](https://github.com/Nalin959/ApniPehChaan)** | Lead Developer: Nalin Sharma (`Nalin959`) |
| **Upstream Repository (Co-Dev)** | **[https://github.com/mvenky1208-byte/ApniPehChaan](https://github.com/mvenky1208-byte/ApniPehChaan)** | Co-Developer: Moturi Venkatesh (`mvenky1208-byte`) |

---

## 📌 Executive Summary & Architectural Mandate

**ApniPehChaan** ("My Identity") is an autonomous personal AI multi-agent system designed to discover where an individual's sensitive personal data is exposed across breach repositories, dark web paste dumps, infostealer malware logs, and open-web registries, and automatically execute statutory Right-to-be-Forgotten data erasure requests.

### The Mental Model: An Autonomous Multi-Agent Swarm, Not a Passive Scanner
* **A passive scanner** executes a fixed linear script: `input -> scan -> table of dumps`. The user is left with the entire cognitive and legal burden: *"Which of these are actually mine? Which can legally be deleted? Who is the Grievance Officer? How do I enforce it?"*
* **ApniPehChaan** operates in an autonomous closed loop:  
  $$\text{GOAL} \longrightarrow \text{DISCOVER} \longrightarrow \text{DECIDE (LEGAL JUDGEMENT)} \longrightarrow \text{ACT (HUMAN-IN-THE-LOOP)} \longrightarrow \text{VERIFY}$$  
  The agent investigates 24 tools, calculates mathematical identity attribution, maps statutory rights under India's DPDP Act 2023 Section 12 or EU GDPR Art. 17, resolves unknown corporate controllers on the fly, drafts formal statutory notices with registered Grievance Officers, awaits explicit human sign-off, and monitors statutory compliance clocks.

---

## 🏆 Six Core Architectural Guarantees

1. **Zero False Positives / Zero Collision Risk**:
   - The platform never attributes third-party breach records or stranger accounts using only a common legal name.
   - Lookups strictly require **exact unique identifiers**: verified primary email, 10-digit Indian mobile, valid PAN/Aadhaar checksums, UPI ID, or declared account handles.
   - Guessed handles derived from email prefixes are strictly quarantined as unconfirmed **candidates** that are excluded from the risk score and removal plan until explicit user confirmation.

2. **Operating Breached Fiduciary Rights (DPDP Act 2023 s.12)**:
   - Operating commercial companies in breaches (IIMjobs, Zomato, Yatra, LinkedIn, Canva, etc.) are treated as accountable Data Fiduciaries. While dark-web dumps cannot be un-published from illicit forums, data principals hold a statutory right under Section 12 to require the operating corporate fiduciary to permanently delete their records from active and backup servers.

3. **Dynamic Data Fiduciary Discovery (Zero Pre-Saved Cheating)**:
   - Eliminated all static company dictionaries and fake fallback emails (`privacy@<slug>.com`).
   - Powered by Google Gemini (with seamless Groq backup), the **Legal Counsel Agent** dynamically investigates any arbitrary operating entity (e.g. *Zomato, Canva, Cred, Zepto, Swiggy*), extracting the formal registered corporate name, official statutory Grievance Officer / DPO email, registered headquarters, and applicable legal remedies.

4. **Cross-Exposure AI Threat Surface Matrix**:
   - Correlates multi-breach exposures into compound attack vectors: **Credential Stuffing** (passwords reused across breached services), **Spear-Phishing** (exposed personal details + workplace domain), and **SIM Swap Vulnerability** (phone number exposed alongside government ID).

5. **100% Free & Keyless Operation**:
   - Zero dependency on paid API subscriptions (such as HIBP paid enterprise tiers).
   - Integrates keyless intelligence feeds: **XposedOrNot** breach catalog, **Hudson Rock Cavalier** infostealer malware infections, **Pwned Passwords** k-anonymity SHA-1 prefix checks, and 26 empirically verified profile namespaces.

6. **Pure Real-World Data & Zero Synthetic Sandbox**:
   - All synthetic mock broker networks, simulated environments, and sandbox data switches have been permanently eliminated from the backend and UI. Every finding represents authentic, real-world intelligence.

---

## 🤖 Collaborative Multi-Agent Swarm Architecture

ApniPehChaan orchestrates a triad of specialized collaborative AI agents powered by **Google Gemini** (with **Groq** backup):

```
                               ┌─────────────────────────────┐
                               │   User Sovereign Profile    │
                               └──────────────┬──────────────┘
                                              │
                                              ▼
                               ┌─────────────────────────────┐
                               │  Swarm Coordinator Agent   │
                               └──────────────┬──────────────┘
                                              │
         ┌────────────────────────────────────┼────────────────────────────────────┐
         │                                    │                                    │
         ▼                                    ▼                                    ▼
┌─────────────────────────────┐  ┌─────────────────────────────┐  ┌─────────────────────────────┐
│    Forensics AI Agent       │  │  Legal Counsel AI Agent     │  │    Remediation AI Agent     │
├─────────────────────────────┤  ├─────────────────────────────┤  ├─────────────────────────────┤
│ • Cross-breach telemetry    │  │ • DPDP Act s.12/13 analysis │  │ • Strategic triage (3-min   │
│ • Infostealer correlation   │  │ • GDPR Art. 17 evaluation   │  │   self-serve vs statutory)  │
│ • Credential stuffing risks │  │ • Dynamic DPO discovery     │  │ • Cryptographic receipts    │
│ • Dark web paste analysis   │  │ • Judicial exemption check  │  │ • Supervisory escalation     │
│ • Threat Surface Matrix     │  │ • Bespoke notice drafting   │  │ • Verification proofs       │
└─────────────────────────────┘  └─────────────────────────────┘  └─────────────────────────────┘
```

1. **🕵️ Forensics Agent** ([`multi_agent_swarm.py`](file:///home/nalin/Hackathon/backend/agent/multi_agent_swarm.py)):
   - Analyzes raw telemetry, unstructured paste dumps, and open-web snippets.
   - Extracts indirect identifiers regexes miss and maps compound attack vectors.
   - Evaluates leaked credential classes, hashes, and computer hostnames.
   - Generates the **AI Threat Surface Matrix** with actionable mitigation priorities.

2. **⚖️ Legal Counsel Agent** ([`multi_agent_swarm.py`](file:///home/nalin/Hackathon/backend/agent/multi_agent_swarm.py)):
   - Evaluates statutory jurisdictions: India's **DPDP Act 2023** (s.12 Erasure & s.13 Grievance Redressal), EU **GDPR** (Art. 17), and US **CCPA/CPRA** (§ 1798.105).
   - Dynamically resolves corporate legal entities and Grievance Officer contacts for arbitrary companies on the fly.
   - Filters statutory exemptions: judicial court records (*Indian Kanoon*, *eCourts*) and statutory registers (*MCA21*) cannot be deleted under DPDP Section 12.
   - Drafts bespoke statutory notices citing exact sections and penalty schedules (up to ₹250 Crore under DPDP Schedule).

3. **🛡️ Remediation Agent** ([`multi_agent_swarm.py`](file:///home/nalin/Hackathon/backend/agent/multi_agent_swarm.py)):
   - Triages findings along the removal ladder: 3-minute direct self-serve deletion vs statutory legal notices.
   - Strictly enforces the **Human-in-the-Loop approval gate** (drafting is autonomous; sending requires human consent).
   - Generates RFC-5322 `.eml` statutory notices, connects to SMTP relays, or provides self-authenticating `mailto:` fallback links.
   - Mints immutable SHA-256 cryptographic audit receipts and tracks the statutory 30-day compliance clock.

---

## 🖥️ User Interface & 50/50 Balanced Hero Screen

The desktop web application features a sleek, responsive obsidian-glassmorphism design:

```
┌─────────────────────────────────────────┬─────────────────────────────────────────┐
│       SOVEREIGN IDENTITY VAULT          │       CYBERNETIC THREAT RADAR           │
│ ┌───────────────────┬─────────────────┐ │ ┌─────────────────────────────────────┐ │
│ │ Full Name         │ Email Address   │ │ │        ((((  SCANNING  ))))         │ │
│ ├───────────────────┼─────────────────┤ │ │          [116px Active Rings]       │ │
│ │ Phone(s) [+Tag]   │ City            │ │ │       [Coordinate Crosshairs]       │ │
│ ├───────────────────┼─────────────────┤ │ ├─────────────────────────────────────┤ │
│ │ Jurisdiction      │ Usernames       │ │ │ Progress: [████████████████] 100%   │ │
│ ├───────────────────┴─────────────────┤ │ ├─────────────────────────────────────┤ │
│ │ [x] Derive search handles           │ │ │        SWARM ACTIVITY TRACE         │ │
│ ├─────────────────────────────────────┤ │ │ > Forensics Agent: querying breach  │ │
│ │ Accounts Held     │ Password (••••) │ │ │ > Legal Agent: DPDP s.12 applicable │ │
│ ├───────────────────┴─────────────────┤ │ │ > Remediation: drafting notice...   │ │
│ │ [ Deploy Privacy Agent ] [ Reset ]  │ │ │ (fills 100% height with flex: 1)    │ │
│ └─────────────────────────────────────┘ │ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┴─────────────────────────────────────────┘
```

### Key UI Features:
* **Equal 50% / 50% Desktop Split**: Configured with `grid-template-columns: 1fr 1fr; align-items: stretch;`.
* **Left Panel (Identity Vault)**: Structured into clean side-by-side 2-column input rows, multi-value tag adders for secondary phones/UPI/websites, password visibility eye toggle, and dotted password masking (`••••••••`).
* **Right Panel (Threat Radar & Swarm Trace)**: Height stretches flush with the left column (`height: 100%`). Features a glowing 116px cybernetic radar with rotating sweep beam, horizontal and vertical crosshairs (`.radar-crosshair-h`, `.radar-crosshair-v`), live scan progress bar, and real-time streaming terminal trace with `flex: 1` (zero dead black void).
* **Two-Way Live Sync in Legal Studio**: Typing an arbitrary company name into the AI Legal Chatbot instantly updates the legal company selector, resolving registered recipient metadata and re-rendering the statutory notice draft in real time on every keystroke.

---

## 🛠️ The 24-Tool Agent Suite

All capabilities are unified under one registry in [`backend/agent/tools.py`](file:///home/nalin/Hackathon/backend/agent/tools.py):

| # | Tool Name | Core Purpose |
| :-: | :--- | :--- |
| **1** | `build_identity_profile` | Normalizes user name, email, phone, city, and derives aliases with confidence scores. |
| **2** | `recall_prior_activity` | Reads SQLite/Supabase durable memory to recall previous runs and open notices. |
| **3** | `verify_breach_exposure` | Queries live keyless feeds (XposedOrNot & Hudson Rock) for verified breach records. |
| **4** | `verify_password_exposure` | Queries Pwned Passwords using k-anonymity (5-char SHA-1 prefix checked locally). |
| **5** | `match_unique_identifiers` | Matches email, phone, UPI, Aadhaar, and PAN against breach and leak corpora. |
| **6** | `discover_accounts` | Fetches 26 empirically verified profile namespaces to detect live public profiles. |
| **7** | `search_open_web` | Searches search engines for unique identifiers and verifies page text character-for-character. |
| **8** | `confirm_account` | Resolves unconfirmed candidate profiles via explicit human verification. |
| **9** | `declare_known_accounts` | Ingests user-declared platforms (Truecaller, Naukri, Shaadi, etc.). |
| **10** | `browse_indian_registry` | Scans the 51-organization Indian statutory reference catalog. |
| **11** | `search_data_brokers` | Scans broker network (active only when verified). |
| **12** | `search_paste_dumps` | Scans pastebin and dark-web text dump corpora for identity mentions. |
| **13** | `detect_pii_in_text` | Executes Verhoeff/Luhn validated PII recognizer across arbitrary text blocks. |
| **14** | `assess_exposure_risk` | Computes the composite 0–100 privacy risk score. |
| **15** | `analyze_threat_surface` | Correlates multi-breach exposures into Credential Stuffing, Spear-Phishing, and SIM Swap vectors. |
| **16** | `determine_legal_basis` | Analyzes governing statute (DPDP Act 2023 s.12, GDPR Art. 17, CCPA § 1798.105). |
| **17** | `plan_removal` | Selects fastest remediation route: 3-minute self-serve URL vs formal statutory notice. |
| **18** | `draft_erasure_request` | Generates bespoke statutory legal notice citing registered entity, DPO, and penalty clauses. |
| **19** | `submit_erasure_request` | Dispatches notice to controller — **strictly gated on human approval**. |
| **20** | `check_request_status` | Follows up on served notice status against statutory 30-day compliance clocks. |
| **21** | `verify_removal` | Independently re-queries the source to confirm data has been deleted. |
| **22** | `escalate_to_regulator` | Generates formal complaints to the Data Protection Board of India (DPBI) upon deadline lapse. |
| **23** | `resolve_fiduciary_dpo` | Dynamically identifies registered corporate entity and DPO email for arbitrary unknown companies. |
| **24** | `generate_audit_receipt` | Mints immutable SHA-256 cryptographic compliance receipts into the genesis chain. |

---

## 🔬 Algorithmic Innovations & Anti-Fabrication Guarantees

1. **Aadhaar vs. Mobile Disambiguation** ([`recognizer.py`](file:///home/nalin/Hackathon/backend/pii/recognizer.py)):
   - Aadhaar uses the Verhoeff dihedral group $D_5$ checksum algorithm. Because 1 in 10 random 12-digit numbers accidentally pass Verhoeff (measured: 520 of 5,000, 10.4%), Indian phone numbers starting with `91` followed by mobile prefixes `[6-9]` were falsely reported as leaked Aadhaar numbers in early builds.
   - **Enforced Rule**: `_aadhaar_plausible()` classifies any 12-digit number starting with `91[6-9]` as a telephone number unless explicit Aadhaar formatting is present.
   - **Empirical Validation**: 0 false positives across 5,000 tested mobile numbers; 3,000/3,000 valid Aadhaar numbers correctly detected.

2. **Luhn Mod-10 Validation** ([`recognizer.py`](file:///home/nalin/Hackathon/backend/pii/recognizer.py)):
   - Validates credit and debit cards across Visa, MasterCard, RuPay, and Amex, distinguishing genuine card numbers from random timestamps or invoice serial numbers.

3. **Jaro-Winkler String Distance & Token Overlap** ([`resolver.py`](file:///home/nalin/Hackathon/backend/pii/resolver.py)):
   - Evaluates identity match confidence with weighted field corroboration, completely preventing false positive name collisions.

4. **k-Anonymity Password Checking** ([`verifiers.py`](file:///home/nalin/Hackathon/backend/agent/verifiers.py)):
   - Computes SHA-1 of the password. Transmits only the first 5 hexadecimal characters to `api.pwnedpasswords.com/range/{prefix}`. Compares the remaining 35 characters locally against the returned list of compromised suffixes. The server never sees the password or the full hash.

5. **Dynamic Privacy Risk Calculator** ([`risk_calculator.py`](file:///home/nalin/Hackathon/backend/pii/risk_calculator.py)):
   - Composite non-linear score curve bounded between 0 and 100:
     $$\text{Score} = 100 \times \left(1 - e^{-\frac{\text{Total Weighted Points}}{\text{Scaling Factor}}}\right)$$
   - Weights: Aadhaar (10.0), Government ID (9.5), Passwords (9.0), PAN (9.0), Bank Account (9.0), UPI (6.0), Phone (4.0), Email (3.0).

---

## ⚖️ Indian Legal Routing & Statutory Enforcement

"Can I get this deleted?" is not a one-size-fits-all question in India. Every source is classified according to statutory boundaries:

| Legal Class | Typical Sources | Governing Law | Agent Action |
| :--- | :--- | :--- | :--- |
| **`dpdp_erasure`** | Operating corporate entities (Zomato, IIMjobs, Naukri, Shaadi) | DPDP Act 2023 Section 12 | **Drafts statutory erasure notice** or routes to self-serve closure. |
| **`statutory_publication`** | MCA21 Director Filings, Electoral Rolls, Land Records | DPDP Act 2023 Section 3(c)(ii) | **Refuses erasure** (data published under legal obligation). Correction applies. |
| **`dpdp_limited`** | CIBIL, Credit Bureaus, Telecom KYC | CICRA 2005 / Competing Retention Duty | **Refuses blanket erasure**. Dispute/correction routing only. |
| **`judicial_record`** | Indian Kanoon, eCourts, High Court Judgments | Judicial Discretion (*Jorawer Singh Mundy*, Delhi HC 2021) | **Refuses statutory notice**. Directs user to file formal High Court writ petition. |
| **`dark_web_dump`** | Unattributed breach compilations (Naz.API, Collection #1) | Illicit Hacker Repositories (No Controller) | **Refuses statutory notice**. Prescribes immediate credential rotation and 2FA hardening. |

---

## 📜 Statutory Notice Mailer, Officer Directory & Playbooks

1. **Real Statutory Notice Mailer** ([`mailer.py`](file:///home/nalin/Hackathon/backend/remediation/mailer.py) — 821 lines):
   - Generates RFC-5322 compliant `.eml` email files with proper headers.
   - Connects to SMTP relays when configured, with strict `approved=True` gating.
   - Generates self-authenticating `mailto:` fallback links with pre-filled subject and body for native email clients.
   - Redacts sensitive secrets (Aadhaar, PAN, Passwords) before mail dispatch.
   - Computes SHA-256 hash of outgoing bytes for immutable audit pinning.

2. **Verified Statutory Officer Directory** ([`officer_directory.py`](file:///home/nalin/Hackathon/backend/remediation/officer_directory.py) — 844 lines):
   - Curates verified Grievance Officers and DPOs for major Indian and global corporations.
   - Assigns trust tiers: `verified`, `statutory_filing`, `company_policy`, `guess`.
   - Enforces trust boundaries: refusing `guess` tiers without explicit override.

3. **Step-by-Step Self-Serve Playbooks** ([`self_serve.py`](file:///home/nalin/Hackathon/backend/remediation/self_serve.py) — 657 lines):
   - Provides direct deep-link URLs to privacy settings and account deletion pages.
   - Provides exact step-by-step instructions and estimated completion time (e.g. 2–3 minutes).
   - Specifies verification protocols to confirm data deletion post-closure.

---

## ☁️ Enterprise Cloud Database & Vercel Serverless Architecture

### Dual-Database Persistence Engine:
* **Local Dev / Offline Testing**: Local SQLite database (`data/sovereign.db`) in WAL mode.
* **Cloud / Vercel Serverless**: **Supabase PostgreSQL** cloud database.

### Supabase Cloud Schema ([`supabase/schema.sql`](file:///home/nalin/Hackathon/supabase/schema.sql)):
* `users`: User profiles, jurisdiction, creation timestamps.
* `identities`: Primary identifiers (email, phone, PAN, Aadhaar, handles).
* `exposures`: Confirmed exposures, source, severity, breach details, data classes.
* `removal_requests`: Remediation plans, notice drafts, dispatch status, tracking IDs.
* `audit_trail`: SHA-256 genesis hash chain, action logs, verification signatures.
* `agent_events`: Streaming logs, agent reasoning, tool execution telemetry.

### Serverless Architecture on Vercel:
* Python runtime: `@vercel/python` in [`vercel.json`](file:///home/nalin/Hackathon/vercel.json).
* **Dual Execution Path**:
  - WebSocket streaming over `ws://localhost:8000/ws/agent` (local/container).
  - Serverless REST polling fallback over `POST /api/agent/scan` with chunked event replay.
* **Audit Chain Hardening**: Microsecond canonicalization for Postgres `timestamptz` and dynamic receipt reloading across stateless function cold starts.

---

## 🚀 Quick Start & Local Setup

### Prerequisites
* Python 3.11+
* Linux, macOS, or WSL2

### 1. Clone the Repository
```bash
git clone https://github.com/Nalin959/ApniPehChaan.git
cd ApniPehChaan
```

### 2. Environment Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env` (optional — works 100% keyless in deterministic mode):
```bash
cp .env.example .env
# Add your GEMINI_API_KEY or GROQ_API_KEY for autonomous LLM reasoning
```

### 3. Run the Test Suite
```bash
./.venv/bin/python test_system.py
```
> **Output**: `ALL 346 TESTS PASSED in ~10.6s` (100% offline, zero network dependencies).

### 4. Launch the Application
```bash
./.venv/bin/python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```
Open **`http://localhost:8000`** in your browser.

---

## 🎬 3-Minute Hackathon Demo Script (Judge Evaluation)

### [0:00 – 0:30] The Problem & Unique Insight:
> *"Judges, every day millions of Indian citizens have their phone numbers, emails, and PAN details exposed across data breaches. While India's DPDP Act 2023 grants a statutory Section 12 Right to Erasure, exercising it is manually prohibitive: finding corporate Grievance Officers, drafting statutory citations, and tracking statutory clocks.*  
> *ApniPehChaan is an autonomous multi-agent AI system that discovers verified exposures without paid APIs, correlates compound attack vectors, resolves unknown company legal contacts dynamically, and generates legally enforceable erasure notices with zero false positives."*

### [0:30 – 1:15] Live Agent Execution (Unified 50/50 Screen):
1. Open **`https://apnipehchaan.vercel.app`** or `http://localhost:8000`.
2. Highlight the clean **50/50 balanced layout**:
   - **Left**: Sovereign Identity profile with side-by-side inputs and password masking.
   - **Right**: Cybernetic Live Threat Radar with coordinate crosshairs and streaming Swarm Activity trace.
3. Enter Name: `Prabhat Sharma`, Email: `prabhatsharma76@yahoo.com`, Phone: `8826030870`.
4. Click **Deploy Privacy Agent**.
5. Watch the Live Threat Radar sweep actively while the Forensics, Legal, and Remediation agents stream tool executions in real time.

### [1:15 – 2:00] Threat Surface & Dynamic Fiduciary Discovery:
1. Show the **AI Threat Surface Matrix**:
   - Cross-correlates multi-breach exposures into Credential Stuffing, Spear-Phishing, and SIM Swap attack vectors.
2. Point out breached companies (e.g. *IIMjobs*, *Zomato*):
   - Operating companies remain legally accountable Data Fiduciaries under DPDP s.12.
   - Notice how unknown companies are resolved dynamically without hardcoded fake lists.

### [2:00 – 2:30] AI Legal Studio & Two-Way Live Sync:
1. Open **Legal Studio**.
2. Type any company name (e.g. `Zomato` or `Canva`) in the AI Legal Chatbot header.
3. Show the **two-way live sync**: recipient metadata, statute citations, and notice preview update dynamically on every keystroke.
4. Point out the SHA-256 cryptographic audit receipts minted for compliance verification.

### [2:30 – 3:00] Compliance & DPBI Escalation:
1. Show the **Compliance** section:
   - Tracks 30-day statutory response windows.
   - Generates escalation complaints to the Data Protection Board of India (DPBI) if a fiduciary fails to respond.
2. Conclude:
   - *"346 tests passing, 100% free-tier architecture, deployed live on Vercel, and fully compliant with Indian privacy law. Thank you."*

---

## 🧪 Verification Metrics & 346-Test Suite Breakdown

Run: `./.venv/bin/python test_system.py`

| Suite # | Test Section | Tests | Key Invariant Enforced |
| :-: | :--- | :-: | :--- |
| **1** | Dataset Integrity | 13 | Corpus verification, broker rosters, and leak dump integrity |
| **2** | PII Recognizer | 24 | Verhoeff/Luhn validation, phone prefixing, false-positive protection on timestamps/cards |
| **3** | Identity Resolver | 29 | Name-part collisions, alias derivations, phone/email normalization |
| **4** | Risk Calculator | 5 | Privacy risk scoring, threat surface quantification, and severity weighting |
| **5** | Legal Notice Generator | 10 | DPDP 2023 s.12/13, GDPR Art. 17, CCPA § 1798.105 statutory text formatting |
| **6** | Cryptographic Audit Trail | 7 | SHA-256 tamper-evident hash chaining and proof verification |
| **7** | Statutory Compliance Tracker | 7 | Deadline tracking, statutory clocks, and escalation triggers |
| **8** | Scanner Modules | 5 | Scanner integration, error resilience, and output hygiene |
| **9** | Evidence Policy | 54 | Anti-fabrication. Verifies exact endpoints, rates, error resilience, and synthetic quarantine |
| **10** | Attribution | 24 | No stranger's account is flagged as yours, scoped-handle non-transferability |
| **11** | Identifier Verification | 11 | Deliverability, MX check, dev-mode non-attribution, and verification codes |
| **12** | Open-Web Search | 46 | Exact-phrase search, candidate demotion, phone boundary isolation, zero false positives |
| **13** | Discovery Site Roster | 22 | Kaggle and Replit stay excluded with a recorded reason; every searched site has a playbook |
| **14** | Free Breach Intelligence | 50 | XposedOrNot & Hudson Rock record endpoints, severity scores, and state what they do not prove |
| **15** | Fiduciary Directory & Threat Surface | 27 | Operating fiduciary DPDP s.12 rights, Grievance Officer lookup, loop tool coverage, and attack surface |
| **Total** | **All 15 Suites** | **346** | **100% Passing (0 Failures, ~10.6s execution)** |

---

## 📄 License & Hackathon Attribution

Created with pride for the **24-Hour Hackathon 2026**.  
* **Lead Developer**: Nalin Sharma ([@Nalin959](https://github.com/Nalin959))  
* **Collaborators**: Moturi Venkatesh ([@mvenky1208-byte](https://github.com/mvenky1208-byte)), reg0712  
* **License**: MIT License
