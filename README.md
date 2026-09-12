# SovereignPrivacy AI 🛡️
### Autonomous Digital Identity & Sovereign Privacy Protection Agent
> *Reclaim your digital footprint under India's DPDP Act 2023, EU GDPR, and US CCPA/CPRA.*  
> Built for the 24-Hour Hackathon | Tailored for IDFC FIRST Bank & Data Privacy Leaders

---

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![DPDP Act 2023](https://img.shields.io/badge/Compliance-India%20DPDP%202023-orange.svg)](https://www.meity.gov.in/)
[![GDPR Art 17](https://img.shields.io/badge/Compliance-EU%20GDPR%20Art%2017-blue.svg)](https://gdpr.eu/)
[![Tests](https://img.shields.io/badge/Tests-67%2F67%20Passed-brightgreen.svg)]()
[![Precision](https://img.shields.io/badge/PII%20Precision-89.8%25-success.svg)]()
[![Zero-Knowledge](https://img.shields.io/badge/Architecture-Zero--Knowledge-purple.svg)]()

---

## 📌 Executive Summary

**SovereignPrivacy AI** is an autonomous, privacy-first personal agent designed to empower individuals to reclaim control over their personal data. In today's digital ecosystem, sensitive Personally Identifiable Information (PII) is constantly harvested, aggregated, and sold by hundreds of data brokers, or leaked on breach forums and dark-web paste sites.

While modern privacy legislation — specifically **India's Digital Personal Data Protection (DPDP) Act 2023** (Sections 11–13, 27), **EU GDPR Article 17** ("Right to Erasure / Right to be Forgotten"), and **US CCPA/CPRA** — guarantees statutory erasure rights, exercising these rights manually across hundreds of entities is slow, tedious, and difficult to audit.

**SovereignPrivacy AI** automates this entire pipeline locally and securely:
1. **Monitors Multi-Source Breaches**: Scans Have I Been Pwned (1,035+ verified breach databases), 956 Optery-indexed data brokers, and dark-web paste dumps.
2. **Indian Financial & Identity Precision**: Utilizes **Verhoeff algorithmic checksums** for 12-digit Aadhaar numbers, **Luhn algorithm** for financial cards, and strict regex for PAN (`[A-Z]{5}[0-9]{4}[A-Z]{1}`), UPI, IFSC, and Indian phone numbers.
3. **Jaro-Winkler Probabilistic Resolution**: Resolves identity links probabilistically to eradicate false positives.
4. **1-Click Statutory Legal Remediation**: Compiles legally sound erasure notices citing the exact statutory sections of DPDP 2023, GDPR, or CCPA.
5. **Chained Cryptographic Audit Trail**: Mints immutable SHA-256 digital proof-of-dispatch receipts.
6. **30-Day Statutory Compliance Tracker**: Tracks statutory response clocks with automated escalation to the **Data Protection Board of India (DPBI)**.

---

## 🏛️ System Architecture

```mermaid
flowchart TB
    subgraph UI ["User Interface (Obsidian Glassmorphism)"]
        Vault["Local Sovereign Vault\n(Client-Side SHA-256 Hashing)"]
        Radar["Live Threat Radar\n(WebSocket Terminal Stream)"]
        Exposure["Exposure Explorer\n(Risk Scoring 0-100)"]
        Legal["1-Click Legal Studio\n(DPDP / GDPR / CCPA)"]
        Tracker["Compliance Kanban\n(30-Day Deadline & DPBI Escalation)"]
        Lab["PII Accuracy Lab\n(Precision & Recall Benchmarks)"]
    end

    subgraph Backend ["FastAPI Core Agent Engine (Port 8000)"]
        API["REST & WebSocket Gateway"]
        
        subgraph Scanners ["Threat Intelligence"]
            HIBP["HIBP Breach Engine\n(1,035 Breaches)"]
            Broker["Optery Broker Scanner\n(956 Brokers)"]
            Paste["Dark Web Paste Scanner\n(50 Dumps)"]
        end
        
        subgraph Engine ["PII & Resolution Core"]
            Recognizer["Hybrid Recognizer\n(Verhoeff + Luhn + Regex)"]
            Resolver["Identity Resolver\n(Jaro-Winkler Metric)"]
            RiskCalc["Privacy Risk Scorer\n(Weighted Vulnerability)"]
        end
        
        subgraph Remediation ["Remediation Engine"]
            NoticeGen["Statutory Notice Generator\n(DPDP Sec 12/13, GDPR Art 17)"]
            AuditTrail["Chained SHA-256 Ledger\n(Digital Proof-of-Dispatch)"]
            Compliance["Statutory Deadline Tracker\n(Milestones & Escalation)"]
        end
    end

    subgraph Datasets ["Integrated Datasets"]
        D1[("Optery Brokers (956)")]
        D2[("HIBP Breaches (1,035)")]
        D3[("Synthetic Pastes (50)")]
        D4[("Ground Truth (380)")]
    end

    Vault -->|Zero-Knowledge Hash| API
    API --> Scanners
    Scanners --> Datasets
    Scanners --> Engine
    Engine --> RiskCalc
    RiskCalc --> Exposure
    Exposure --> NoticeGen
    NoticeGen --> AuditTrail
    AuditTrail --> Compliance
    Compliance --> Tracker
    API -.->|Real-time Logs| Radar
```

---

## ⚡ Key Innovations & Engineering Highlights

### 1. Verhoeff Algorithmic Aadhaar Verification
Naive regex matches any 12-digit number, causing countless false positives. SovereignPrivacy AI computes dihedral group $D_5$ permutations via the Verhoeff algorithm to validate genuine Indian Aadhaar numbers before tagging them as critical exposures.

### 2. Luhn Check for Financial Cards
Validates Visa, MasterCard, RuPay, and Amex credit/debit card numbers using mod-10 verification.

### 3. Jaro-Winkler Probabilistic Record Linkage
Calculates token set overlap and Jaro-Winkler string similarity ($0.0 \le \text{sim} \le 1.0$) across full names, emails, phone numbers, and cities:
- **Definite Match** ($\ge 0.85$): Confirmed personal exposure.
- **Probable Match** ($0.65 - 0.84$): High-probability match.
- **Possible Match** ($0.45 - 0.64$): Weak match requiring user confirmation.

### 4. Zero-Knowledge Local Architecture
User identifiers (Aadhaar, PAN, credentials) are processed locally and never transmitted unhashed to third-party endpoints. External breach checks leverage local catalog matching and k-anonymity SHA-1 prefixes.

### 5. Chained Cryptographic Proof-of-Dispatch
Every legal notice generated or dispatched creates an immutable audit block linking to the previous block's SHA-256 hash ($Block_N \to Block_{N-1}$), creating a tamper-evident audit trail suitable for court or regulatory proceedings.

---

## 📊 Datasets Integrated

| Dataset | Records | Source | Role |
| :--- | :--- | :--- | :--- |
| **Optery Data Broker Registry** | 956 | Optery Open Source | Categorized data brokers, opt-out URLs, difficulty ratings, privacy emails |
| **HIBP Verified Breaches** | 1,035 | Have I Been Pwned v3 | Verified corporate breach catalog with compromised PII data classes |
| **Dark-Web Paste Leaks** | 50 | Synthetic Corpus | Realistic dark-web paste dumps containing mixed Indian and global credentials |
| **PII Ground-Truth Benchmark** | 380 | Labeled Token Corpus | Evaluation benchmark for precision, recall, and F1 scoring |
| **Statutory Legal Templates** | 3 | Statutory Gazettes | India DPDP Act 2023 Sec 12/13, EU GDPR Art 17, US CCPA/CPRA § 1798.105 |

---

## 🧪 Benchmark & Test Results

All 67 tests in [`test_system.py`](test_system.py) run and pass in **0.08 seconds**:

```
════════════════════════════════════════════════════════════
  SovereignPrivacy AI — Automated Test Suite
════════════════════════════════════════════════════════════
  ✓ Optery brokers file loads (956 records)
  ✓ HIBP breaches file loads (1,035 records)
  ✓ Synthetic pastes file loads (50 dumps)
  ✓ Benchmark file loads (380 samples)
  ✓ Verhoeff algorithm validates Aadhaar correctly
  ✓ Rejects invalid Aadhaar numbers
  ✓ Detects PAN ([A-Z]{5}[0-9]{4}[A-Z]{1}), Phone, Email, UPI, IFSC
  ✓ PII Precision: 89.8%  (Target: ≥ 70%)
  ✓ PII Recall:    88.0%  (Target: ≥ 70%)
  ✓ PII F1 Score:  88.9%  (Target: ≥ 70%)
  ✓ Jaro-Winkler identity matching validated
  ✓ Privacy Risk Score [0, 100] bounded
  ✓ DPDP 2023 notice cites Sections 12 & 13
  ✓ GDPR notice cites Article 17 (30-day clock)
  ✓ CCPA notice cites § 1798.105 (45-day clock)
  ✓ Chained SHA-256 audit receipts verified
  ✓ 30-Day compliance scheduling & DPBI escalation verified
════════════════════════════════════════════════════════════
  ALL 67 TESTS PASSED in 0.08s
════════════════════════════════════════════════════════════
```

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- Linux / macOS / WSL

### 2. Setup & Run in One Command
```bash
git clone https://github.com/Nalin959/sovereign-privacy-ai.git
cd sovereign-privacy-ai
chmod +x run_demo.sh
./run_demo.sh
```

### 3. Manual Installation
```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download and verify datasets
python data/download_datasets.py

# Run test suite
python test_system.py

# Launch FastAPI server
uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## 🔌 API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/status` | System health, dataset counts, audit chain status |
| `GET` | `/api/datasets/summary` | Summary of loaded breach catalogs and data brokers |
| `POST` | `/api/scan/full` | Full multi-vector scan across HIBP, brokers, and dark web |
| `POST` | `/api/scan/hibp` | Targeted breach catalog query |
| `POST` | `/api/scan/brokers` | Search across 956 registered data brokers |
| `POST` | `/api/scan/pastes` | Scan dark-web paste leak corpus |
| `POST` | `/api/pii/detect` | Run hybrid PII extraction on arbitrary unstructured text |
| `GET` | `/api/pii/benchmark` | Execute live precision, recall, and F1 benchmark |
| `GET` | `/api/legal/jurisdictions` | List supported legal frameworks (DPDP, GDPR, CCPA) |
| `POST` | `/api/legal/generate` | Compile formal statutory legal notice with receipt hash |
| `POST` | `/api/legal/dispatch` | Dispatch notice, start 30-day clock, mint audit block |
| `GET` | `/api/compliance/requests` | List active erasure requests and countdown clocks |
| `GET` | `/api/audit/trail` | Return full cryptographic audit receipt ledger |
| `GET` | `/api/audit/verify` | Verify cryptographic SHA-256 chain integrity |
| `WS` | `/ws/scan` | Real-time WebSocket streaming terminal for live scan logs |

---

## 👥 Hackathon Presentation Pitch (Judged under IDFC FIRST Bank)

> *"Under Section 12 of India's DPDP Act 2023, every citizen has the statutory Right to Erasure. Yet with 950+ commercial data brokers scraping public records and dark-web leaks persisting, how can an individual realistically track and exercise this right?*  
>  
> *SovereignPrivacy AI is the zero-knowledge personal privacy agent. It monitors over 1,000 breaches and 956 data brokers, algorithmically verifies Indian identifiers like Aadhaar and PAN, scores overall privacy vulnerability, and generates legally airtight erasure notices with chained SHA-256 cryptographic audit receipts. When a company ignores the 30-day deadline, the agent escalates directly to the Data Protection Board of India."*

---

## 📄 License
MIT License. Created for the 24-Hour Hackathon 2026.
