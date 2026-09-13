# ApniPehChaan — Complete Project Handover & Architecture Guide

**Platform:** ApniPehChaan — Autonomous Sovereign Digital Identity Protection Agent  
**Author & Developer:** Nalin Sharma  
**Date:** September 13, 2026  
**Status:** Production Ready · 100% Free Tier · Zero False Positives · 334/334 Tests Passing  
**Live Production URL:** [https://sovereign-privacy-ai.vercel.app](https://sovereign-privacy-ai.vercel.app)  
**GitHub Repository:** [https://github.com/Nalin959/sovereign-privacy-ai.git](https://github.com/Nalin959/sovereign-privacy-ai.git)  

---

## 1. Executive Summary & Core Mandate

**ApniPehChaan** is an autonomous, privacy-preserving AI multi-agent system designed to discover where an individual's sensitive personal data is exposed across breach repositories, dark web paste dumps, infostealer logs, and open-web registries, and automatically execute statutory Right-to-be-Forgotten data erasure requests under:
- **India**: Digital Personal Data Protection (DPDP) Act 2023, Section 12 (Erasure) & Section 13 (Grievance Redressal).
- **European Union**: General Data Protection Regulation (GDPR), Article 17 (Right to Erasure).
- **California, USA**: California Consumer Privacy Act / CPRA, § 1798.105 (Consumer Deletion Right).

---

## 2. Core Architectural Guarantees

1. **Zero False Positives / Zero Collision Risk**:
   - The platform never attributes third-party breach records or stranger accounts using only a common legal name.
   - All lookups require **exact unique identifiers**: verified primary email, 10-digit Indian mobile, valid PAN/Aadhaar checksums, UPI ID, or declared account handles.
   - Guessed handles derived from email prefixes are strictly demoted to unconfirmed **candidates** that are excluded from the risk score and removal plan until explicit user confirmation.

2. **Unified 50/50 Half-Page Interface**:
   - Eliminated the redundant "Threat Scanner" tab and duplicate identity input vaults.
   - Designed a balanced **50% / 50% split** desktop layout:
     - **Left Column**: Sovereign Identity Profile with two-column input rows (Full Name, Email, Phone, City, Jurisdiction, Handles, Aadhaar/PAN, Accounts, Passwords).
     - **Right Column**: Cybernetic Live Threat Radar (`116px` concentric rings, sweeping radar beam, coordinate crosshairs, live status badge, and scan progress bar) seamlessly integrated with the streaming real-time Multi-Agent Swarm trace (`#agent-trace`).
   - Both columns use `align-items: stretch` so the cards maintain flush, equal height with zero blank whitespace.

3. **Dynamic Data Fiduciary Discovery for Arbitrary / Unknown Companies**:
   - Eliminated all static dictionaries and fake fallback emails (`privacy@<slug>.com`).
   - Powered by Google Gemini (with seamless Groq fallback), the **Legal Counsel Agent** dynamically investigates any arbitrary operating entity (e.g. *Zomato, Canva, Cred, Zepto, Swiggy*), extracting:
     - Registered corporate entity name (e.g., *Zomato Limited*, *Canva Pty Ltd*).
     - Official statutory Grievance Officer / DPO contact address.
     - Registered corporate headquarters.
     - Applicable statutory legal basis and 30-day compliance timeline.
   - If an entity is a raw dark-web dump (e.g., *Naz.API*, *Collection #1*), the agent correctly flags that no operating fiduciary exists and prescribes credential rotation rather than dispatching futile legal notices.

4. **100% Free & Keyless Breach Intelligence**:
   - Operates completely free of paid API keys:
     - **XposedOrNot**: Corporate data breaches and dark web paste dumps.
     - **Hudson Rock Cavalier**: Infostealer malware infections (identifying infected computer names, OS, and compromised credential timestamps).
     - **LeakCheck Public**: Phone number and email breach lookups (e.g., Indian leaks like Yatra).
     - **HaveIBeenPwned K-Anonymity**: SHA-1 5-character prefix matching done locally.
     - **DuckDuckGo / SearXNG**: Web profile verification with SSRF prevention and RFC 1918 loopback protections.

5. **Honest Evidence Policy**:
   - If an upstream breach API is rate-limited, times out, or errors, it is classified as `unavailable` / `could_not_check`.
   - The system **never reports a user as "CONFIRMED CLEAR" when a check could not be performed**.

6. **Human-in-the-Loop Removals & SHA-256 Cryptographic Audit Ledger**:
   - The AI agent drafts statutory notices autonomously but strictly halts at an approval gate. Outward legal notices are only dispatched upon explicit user selection.
   - Dispatched notices generate an immutable SHA-256 cryptographic compliance receipt tracked in the Compliance ledger.

---

## 3. UI Navigation & Page Structure

The top navigation consists of 5 streamlined sections:

| Navigation Item | Section ID | Core Purpose |
| :--- | :--- | :--- |
| **Privacy Agent** | `#section-agent` | Unified 50/50 hero grid: Sovereign Identity + Live Threat Radar & streaming multi-agent swarm activity, followed by the Threat Surface Matrix, Human Approval Gate, Candidates Panel, Removal Plan, and Exposure Ledger. |
| **Command Center** | `#section-dashboard` | Executive overview of privacy risk score, breach breakdown (Breaches, Infostealers, Brokers, Dark Web), quick action triggers, and security recommendations. |
| **Exposures** | `#section-exposures` | Filterable intelligence cards (`all`, `critical`, `high`, `medium`, `breach`, `infostealer`, `broker`, `indian`, `paste`). Zero false positives. |
| **Legal Studio** | `#section-legal` | Dual-mode remediation studio: Interactive AI Legal Chatbot (Gemini) with two-way synchronized fiduciary metadata alongside the live statutory notice draft preview. |
| **Compliance** | `#section-compliance` | 30-day statutory response deadline tracker, SHA-256 audit receipts ledger, and Monitored Indian Fiduciaries directory under the DPDP Act 2023. |

---

## 4. Collaborative Multi-Agent Swarm Architecture

The autonomous privacy engine operates via a trio of collaborative AI agents powered by **Google Gemini** (with **Groq** backup):

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
│ • Infostealer correlation   │  │ • GDPR Art. 17 evaluation   │ │   self-serve vs statutory)  │
│ • Credential stuffing risks │  │ • Dynamic DPO discovery     │  │ • Cryptographic receipts    │
│ • Dark web paste analysis   │  │ • Judicial exemption check  │  │ • Supervisory escalation     │
│ • Threat Surface Matrix     │  │ • Bespoke notice drafting   │  │ • Verification proofs       │
└─────────────────────────────┘  └─────────────────────────────┘  └─────────────────────────────┘
```

1. **Forensics Agent**:
   - Executes deterministic discovery across keyless APIs (`XposedOrNot`, `LeakCheck`, `Hudson Rock`, `Pwned Passwords`).
   - Evaluates leaked credential classes, hashes, and computer hostnames.
   - Generates the **AI Threat Surface & Attack-Vector Matrix** with compound attack scenarios (e.g., credential stuffing, SIM swap vulnerability, dark web profiling).

2. **Legal Counsel Agent**:
   - Dynamically analyzes corporate entities, discerning between operating Data Fiduciaries and unattributed dark-web leak dumps.
   - Automatically determines applicable legal grounds under DPDP Act 2023 s.12, GDPR Art. 17, or CCPA.
   - Verifies statutory exemptions (e.g. court filings and corporate registry MCA records cannot be deleted under DPDP).
   - Generates formal statutory erasure notices with statutory citations, grievance officer addresses, and non-compliance penalty schedules (up to ₹250 Crore under DPDP Schedule).

3. **Remediation Agent**:
   - Categorizes findings into 3-minute self-serve settings URLs vs formal legal notices.
   - Enforces the human-in-the-loop approval gate.
   - Tracks the 30-day compliance timeline and generates SHA-256 immutable audit receipts.

---

## 5. Technology Stack

- **Backend**: Python 3.11+, FastAPI, Uvicorn, WebSockets, asyncio, Pydantic.
- **AI Models**: Google Gemini (`google-genai` / `gemini-2.0-flash`), Groq API (`llama-3.3-70b-versatile`) as intelligent fallback.
- **Frontend**: Vanilla ES6+ JavaScript, Native WebSockets, Semantic HTML5, Vanilla CSS3 (Custom Design System, Glassmorphism, HSL color tokens).
- **Database / Memory**: SQLite local memory store (`privacy_memory.db`) with migration compatibility for Supabase PostgreSQL.
- **Testing**: `pytest` and comprehensive offline test suite in `test_system.py` (334 test cases).
- **Hosting / Deployment**: Vercel Production Serverless with Python Runtime, GitHub CI.

---

## 6. Verification & Test Suite Status

The platform includes an extensive test suite in `test_system.py`:

```bash
./.venv/bin/python test_system.py
```

### Test Suite Summary:
- **Total Tests**: **334 tests**
- **Passing**: **334 passed (100%)**
- **Execution Time**: ~10.6 seconds
- **Covered Subsystems**:
  1. Strict PII recognition & ground-truth validation (460 entities).
  2. Aadhaar vs. Indian Mobile collision prevention (0/5000 false positives, 3000/3000 true detections).
  3. Strict identity attribution gating (declared vs. guessed handles).
  4. Free breach intelligence parsers & rate-limit honest error handling.
  5. Empirical account discovery namespaces (26 verified platforms).
  6. Fiduciary directory & dynamic company discovery logic.
  7. AI Threat Surface analysis & attack-vector correlation.
  8. Multi-agent swarm tool suite registrations & event stream handling.

---

## 7. How to Run Locally & Live Demonstration

### Prerequisites
- Python 3.11+
- Virtual environment at `./.venv`

### Environment Setup (`.env`)
```bash
GEMINI_API_KEY="your-gemini-api-key"
GROQ_API_KEY="your-groq-api-key"
PORT=8000
```

### Launching the Application
```bash
cd /home/nalin/Hackathon
./.venv/bin/python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```
Open **`http://localhost:8000`** in your browser.

### Judge Demonstration Walkthrough

1. **Privacy Agent Hero Screen**:
   - Notice the clean **50/50 split** layout.
   - Enter Full Name (e.g. `Prabhat Sharma`), Email (e.g. `prabhatsharma76@yahoo.com`), Phone (`8826030870`), City (`Noida`), and Jurisdiction (`India (DPDP Act 2023)`).
   - Click **Deploy Privacy Agent**.
   - Watch the **Live Threat Radar** illuminate with active sweeping animations and dynamic progress updates while the **Swarm Activity Trace** streams reasoning from the Forensics, Legal Counsel, and Remediation agents in real time.

2. **AI Threat Surface Matrix**:
   - Review the generated **AI Threat Surface & Attack-Vector Matrix** showing correlated attack paths (e.g., Credential Stuffing, Dark Web Correlation).

3. **Exposures Intelligence**:
   - Navigate to **Exposures**.
   - Point out that **zero false positives** exist: only verified breach hits and confirmed accounts are displayed.

4. **AI Legal Studio**:
   - Navigate to **Legal Studio**.
   - Test the **AI Legal Chatbot**: type any company name (e.g., `Zomato` or `Canva`).
   - Notice the dynamic two-way sync: the legal recipient, statutory citation, and notice preview instantly adapt without static hardcoded assumptions.

5. **Compliance & Audit Receipts**:
   - Navigate to **Compliance**.
   - Inspect the 30-day statutory response timeline and cryptographically hashed SHA-256 audit ledger.

---

## 8. File Map & Project Organization

```
/home/nalin/Hackathon
├── backend/
│   ├── app.py                      # FastAPI application, WebSocket & REST endpoints
│   ├── config.py                   # Configuration and environment variables
│   ├── agent/
│   │   ├── multi_agent_swarm.py     # Collaborative Swarm: Forensics, Legal Counsel, Remediation
│   │   ├── orchestrator.py         # Swarm lifecycle coordinator & discovery execution
│   │   ├── fiduciary_directory.py   # Data Fiduciary statutory lookup & dynamic company resolution
│   │   ├── tools.py                # 22+ registered agent tools for analysis & drafting
│   │   ├── verifiers.py            # Free-tier intelligence verifiers (XposedOrNot, Hudson Rock, etc.)
│   │   ├── web_search.py           # SSRF-hardened open-web discovery engine
│   │   └── memory.py               # Session store, exposure ledger, user profile state
│   ├── pii/
│   │   ├── recognizer.py           # Strict PII recognizer with Verhoeff Aadhaar validation
│   │   └── resolver.py             # Attribution resolver & entity collision guards
│   ├── legal/
│   │   ├── notice_generator.py     # Statutory notice compiler (DPDP s.12/13, GDPR, CCPA)
│   │   ├── audit_trail.py          # Cryptographic SHA-256 compliance receipts
│   │   └── compliance_tracker.py   # 30-day response deadline monitor
│   └── scanners/                   # Modular scanner connectors
├── frontend/
│   ├── index.html                  # Main UI layout (50/50 Privacy Agent, Command Center, Exposures, Legal, Compliance)
│   ├── styles.css                  # Modern cyber-aesthetic styles, balanced grid, radar animation
│   └── app.js                      # Reactive frontend controller, WebSockets, two-way sync, RightsAdvisor
├── test_system.py                  # Full test suite (334 offline unit and integration tests)
├── vercel.json                     # Vercel production serverless deployment configuration
├── HANDOVER.md                     # Comprehensive handover and system status documentation (this file)
└── README.md                       # Project overview and quickstart guide
```

---

## 9. Conclusion

ApniPehChaan demonstrates that privacy protection can be **autonomous, legally rigorous, 100% free-tier, and visually stunning**. With zero false positives, dynamic data fiduciary discovery, and an integrated 50/50 Threat Radar swarm interface, the system is fully production-ready and deployed at **[https://sovereign-privacy-ai.vercel.app](https://sovereign-privacy-ai.vercel.app)**.
