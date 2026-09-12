#!/usr/bin/env python3
"""
download_datasets.py — Automated dataset builder for SovereignPrivacy AI.

Downloads real-world datasets:
  • Optery Data Broker Directory (956+ brokers)
  • HIBP Verified Breach Catalog (1,035+ breaches)

Generates synthetic datasets:
  • Dark-web paste corpus with Indian & international PII
  • Indian PII ground-truth benchmark for accuracy evaluation

Creates statutory legal templates for DPDP Act 2023, GDPR Art 17, CCPA.
"""

import json
import os
import random
import hashlib
import urllib.request
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def download_optery_brokers():
    """Download the Optery open-source data broker directory (956 brokers)."""
    url = "https://raw.githubusercontent.com/optery/optery-data-brokers-directory/master/data/data-brokers.json"
    dest = os.path.join(BASE_DIR, "brokers", "optery_brokers.json")
    print(f"[*] Downloading Optery data broker directory → {dest}")
    req = urllib.request.Request(url, headers={"User-Agent": "SovereignPrivacyAI/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            data = json.loads(raw)
            # Normalize and enrich
            brokers = []
            for entry in data:
                brokers.append({
                    "id": entry.get("id"),
                    "name": entry.get("title", "Unknown"),
                    "website": entry.get("website", ""),
                    "opt_out_url": entry.get("opt_out_url", ""),
                    "opt_out_guide": entry.get("opt_out_guide_url", ""),
                    "privacy_email": entry.get("email", ""),
                    "description": entry.get("description", ""),
                    "category": entry.get("type", "Unknown"),
                    "removal_tier": entry.get("optery_support_tier", "Unknown"),
                    "is_expanded_reach": entry.get("is_expanded_reach", False),
                })
            with open(dest, "w") as f:
                json.dump(brokers, f, indent=2)
            print(f"    ✓ Saved {len(brokers)} data brokers")
            return len(brokers)
    except Exception as e:
        print(f"    ✗ Failed to download Optery brokers: {e}")
        # Create minimal fallback
        _create_fallback_brokers(dest)
        return 0


def _create_fallback_brokers(dest):
    """Create a minimal fallback broker dataset if download fails."""
    brokers = [
        {"id": 1, "name": "Spokeo", "website": "https://www.spokeo.com", "opt_out_url": "https://www.spokeo.com/optout", "privacy_email": "privacy@spokeo.com", "category": "People Search", "removal_tier": "Easy", "description": "People search engine aggregating public records.", "opt_out_guide": "", "is_expanded_reach": False},
        {"id": 2, "name": "WhitePages", "website": "https://www.whitepages.com", "opt_out_url": "https://www.whitepages.com/suppression-requests", "privacy_email": "support@whitepages.com", "category": "People Search", "removal_tier": "Medium", "description": "Online phone book and people search directory.", "opt_out_guide": "", "is_expanded_reach": False},
        {"id": 3, "name": "BeenVerified", "website": "https://www.beenverified.com", "opt_out_url": "https://www.beenverified.com/app/optout/search", "privacy_email": "privacy@beenverified.com", "category": "Background Check", "removal_tier": "Medium", "description": "Background check and people search service.", "opt_out_guide": "", "is_expanded_reach": False},
        {"id": 4, "name": "Intelius", "website": "https://www.intelius.com", "opt_out_url": "https://www.intelius.com/optout", "privacy_email": "privacy@intelius.com", "category": "People Search", "removal_tier": "Hard", "description": "People search engine providing background data.", "opt_out_guide": "", "is_expanded_reach": False},
        {"id": 5, "name": "TruePeopleSearch", "website": "https://www.truepeoplesearch.com", "opt_out_url": "https://www.truepeoplesearch.com/removal", "privacy_email": "", "category": "People Search", "removal_tier": "Easy", "description": "Free people search engine.", "opt_out_guide": "", "is_expanded_reach": False},
    ]
    with open(dest, "w") as f:
        json.dump(brokers, f, indent=2)
    print(f"    ⚠ Created fallback with {len(brokers)} brokers")


def download_hibp_breaches():
    """Download verified breach catalog from HIBP API v3."""
    url = "https://haveibeenpwned.com/api/v3/breaches"
    dest = os.path.join(BASE_DIR, "breaches", "hibp_breaches.json")
    print(f"[*] Downloading HIBP verified breach catalog → {dest}")
    req = urllib.request.Request(url, headers={"User-Agent": "SovereignPrivacyAI/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            breaches = []
            for b in data:
                breaches.append({
                    "name": b.get("Name", ""),
                    "title": b.get("Title", ""),
                    "domain": b.get("Domain", ""),
                    "breach_date": b.get("BreachDate", ""),
                    "added_date": b.get("AddedDate", ""),
                    "pwn_count": b.get("PwnCount", 0),
                    "description": b.get("Description", ""),
                    "data_classes": b.get("DataClasses", []),
                    "is_verified": b.get("IsVerified", False),
                    "is_sensitive": b.get("IsSensitive", False),
                    "logo_path": b.get("LogoPath", ""),
                })
            with open(dest, "w") as f:
                json.dump(breaches, f, indent=2)
            print(f"    ✓ Saved {len(breaches)} verified breaches")
            return len(breaches)
    except Exception as e:
        print(f"    ✗ Failed to download HIBP breaches: {e}")
        return 0


def generate_synthetic_pastes():
    """Generate realistic synthetic dark-web paste/leak dumps for testing."""
    dest = os.path.join(BASE_DIR, "synthetic_pastes", "pastes_corpus.json")
    print(f"[*] Generating synthetic dark-web paste corpus → {dest}")

    indian_first = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Reyansh", "Sai", "Arnav", "Dhruv", "Kabir",
                    "Ananya", "Diya", "Myra", "Sara", "Aadhya", "Isha", "Kiara", "Riya", "Priya", "Neha"]
    indian_last = ["Sharma", "Verma", "Patel", "Gupta", "Singh", "Kumar", "Reddy", "Joshi", "Mehta", "Agarwal",
                   "Rao", "Iyer", "Nair", "Das", "Chatterjee", "Mukherjee", "Bose", "Ghosh", "Pillai", "Menon"]
    intl_first = ["James", "Emma", "Oliver", "Sophia", "Liam", "Charlotte", "Noah", "Amelia", "William", "Mia"]
    intl_last = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
    cities_in = ["Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai", "Kolkata", "Pune", "Ahmedabad", "Jaipur", "Lucknow"]
    cities_intl = ["New York", "London", "San Francisco", "Toronto", "Sydney", "Berlin", "Paris", "Tokyo", "Singapore", "Dubai"]
    banks = ["IDFC FIRST Bank", "SBI", "HDFC Bank", "ICICI Bank", "Axis Bank", "Kotak Mahindra", "PNB", "Bank of Baroda"]
    domains_mail = ["gmail.com", "yahoo.co.in", "outlook.com", "hotmail.com", "protonmail.com", "rediffmail.com"]

    def gen_aadhaar():
        """Generate a fake Aadhaar-like 12-digit number (not Verhoeff-valid intentionally for synthetic data)."""
        return f"{random.randint(2,9)}" + "".join([str(random.randint(0,9)) for _ in range(11)])

    def gen_pan():
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        # PAN format: [A-Z]{3}[PCHABFTGJL][A-Z][0-9]{4}[A-Z]
        type_chars = "PCHABFTGJL"
        return (random.choice(letters) + random.choice(letters) + random.choice(letters) +
                random.choice(type_chars) + random.choice(letters) +
                str(random.randint(1000,9999)) + random.choice(letters))

    def gen_phone_in():
        return f"+91 {random.choice(['9','8','7','6'])}{random.randint(100000000,999999999)}"

    def gen_phone_intl():
        return f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}"

    def gen_card():
        # Fake Visa-like card number
        prefix = "4" + "".join([str(random.randint(0,9)) for _ in range(14)])
        return prefix + str(random.randint(0,9))

    def gen_ifsc():
        bank_codes = ["IDFB", "SBIN", "HDFC", "ICIC", "UTIB", "KKBK", "PUNB", "BARB"]
        return random.choice(bank_codes) + "0" + "".join([str(random.randint(0,9)) for _ in range(5)])

    def gen_upi(first, last):
        handles = ["@okaxis", "@ybl", "@paytm", "@ibl", "@upi", "@sbi", "@icici"]
        return f"{first.lower()}.{last.lower()}{random.randint(1,99)}{random.choice(handles)}"

    def gen_voter_id():
        state_codes = ["DL", "MH", "KA", "TN", "WB", "UP", "RJ", "GJ", "AP", "KL"]
        return random.choice(state_codes) + "/" + str(random.randint(10,99)) + "/" + str(random.randint(100,999)) + "/" + str(random.randint(100000,999999))

    pastes = []

    # Type 1: SQL Dump leaks (Indian banking)
    for i in range(15):
        fn = random.choice(indian_first)
        ln = random.choice(indian_last)
        email = f"{fn.lower()}.{ln.lower()}{random.randint(1,99)}@{random.choice(domains_mail)}"
        city = random.choice(cities_in)
        phone = gen_phone_in()
        aadhaar = gen_aadhaar()
        pan = gen_pan()
        bank = random.choice(banks)
        ifsc = gen_ifsc()
        acct = "".join([str(random.randint(0,9)) for _ in range(12)])
        salary = random.randint(300000, 2500000)

        content = f"""-- Leaked SQL dump from {bank.lower().replace(' ','_')}_customers_{random.randint(2019,2024)}.sql
-- Table: customer_kyc
INSERT INTO customer_kyc VALUES ({i+1000}, '{fn} {ln}', '{email}', '{phone}',
'{aadhaar}', '{pan}', '{city}, India', '{bank}', '{ifsc}', '{acct}', {salary},
'{"Active" if random.random() > 0.2 else "Dormant"}', '{(datetime.now() - timedelta(days=random.randint(30,1800))).strftime("%Y-%m-%d")}');"""

        pastes.append({
            "id": f"paste_sql_{i+1:03d}",
            "type": "sql_dump",
            "source": f"dark_forum_{random.choice(['alpha','bravo','charlie','delta','echo'])}",
            "date_found": (datetime.now() - timedelta(days=random.randint(1,365))).isoformat(),
            "content": content,
            "ground_truth_pii": {
                "names": [f"{fn} {ln}"],
                "emails": [email],
                "phones": [phone],
                "aadhaar": [aadhaar],
                "pan": [pan],
                "addresses": [f"{city}, India"],
                "bank_accounts": [acct],
                "ifsc_codes": [ifsc],
            }
        })

    # Type 2: Combo lists (email:password)
    for i in range(10):
        entries = []
        gt_emails = []
        for _ in range(random.randint(3,8)):
            if random.random() > 0.4:
                fn = random.choice(indian_first)
                ln = random.choice(indian_last)
            else:
                fn = random.choice(intl_first)
                ln = random.choice(intl_last)
            email = f"{fn.lower()}{ln.lower()}{random.randint(1,999)}@{random.choice(domains_mail)}"
            pwd = hashlib.md5(f"{fn}{random.randint(0,9999)}".encode()).hexdigest()[:12]
            entries.append(f"{email}:{pwd}")
            gt_emails.append(email)

        pastes.append({
            "id": f"paste_combo_{i+1:03d}",
            "type": "combo_list",
            "source": f"pastebin_mirror_{random.randint(1,50)}",
            "date_found": (datetime.now() - timedelta(days=random.randint(1,200))).isoformat(),
            "content": "# Combo list — fresh dump\n" + "\n".join(entries),
            "ground_truth_pii": {
                "emails": gt_emails,
            }
        })

    # Type 3: Doxxing pastes (full Indian identity)
    for i in range(10):
        fn = random.choice(indian_first)
        ln = random.choice(indian_last)
        email = f"{fn.lower()}.{ln.lower()}@{random.choice(domains_mail)}"
        phone = gen_phone_in()
        aadhaar = gen_aadhaar()
        pan = gen_pan()
        city = random.choice(cities_in)
        voter = gen_voter_id()
        upi = gen_upi(fn, ln)
        card = gen_card()
        dob = f"{random.randint(1,28)}/{random.randint(1,12)}/{random.randint(1975,2002)}"

        content = f"""=== DOXX: {fn} {ln} ===
Full Name: {fn} {ln}
DOB: {dob}
Email: {email}
Phone: {phone}
Aadhaar: {aadhaar}
PAN: {pan}
Voter ID: {voter}
UPI: {upi}
Credit Card: {card}
Address: {random.randint(1,500)}, {random.choice(["MG Road","Park Street","Brigade Road","Anna Salai","Connaught Place","FC Road"])}, {city} - {random.randint(100000,999999)}
Father: {random.choice(indian_first)} {ln}
=== END DOXX ==="""

        pastes.append({
            "id": f"paste_doxx_{i+1:03d}",
            "type": "doxxing_paste",
            "source": f"telegram_leak_channel_{random.randint(1,20)}",
            "date_found": (datetime.now() - timedelta(days=random.randint(1,100))).isoformat(),
            "content": content,
            "ground_truth_pii": {
                "names": [f"{fn} {ln}"],
                "emails": [email],
                "phones": [phone],
                "aadhaar": [aadhaar],
                "pan": [pan],
                "voter_id": [voter],
                "upi": [upi],
                "credit_cards": [card],
                "addresses": [f"{city}"],
            }
        })

    # Type 4: International breach fragments
    for i in range(10):
        fn = random.choice(intl_first)
        ln = random.choice(intl_last)
        email = f"{fn.lower()}.{ln.lower()}{random.randint(1,99)}@{random.choice(['gmail.com','outlook.com','yahoo.com'])}"
        phone = gen_phone_intl()
        city = random.choice(cities_intl)
        ip = f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"

        content = f"""[BREACH] {fn} {ln}
Contact: {email} | {phone}
IP: {ip}
Location: {city}
Last Login: {(datetime.now() - timedelta(days=random.randint(1,365))).strftime("%Y-%m-%d %H:%M:%S")}"""

        pastes.append({
            "id": f"paste_intl_{i+1:03d}",
            "type": "breach_fragment",
            "source": f"darknet_market_{random.choice(['hydra','silk','agora','dream'])}",
            "date_found": (datetime.now() - timedelta(days=random.randint(1,300))).isoformat(),
            "content": content,
            "ground_truth_pii": {
                "names": [f"{fn} {ln}"],
                "emails": [email],
                "phones": [phone],
                "ip_addresses": [ip],
                "addresses": [city],
            }
        })

    # Type 5: CSV data broker scrapes
    for i in range(5):
        rows = []
        gt = {"names": [], "emails": [], "phones": [], "addresses": []}
        header = "full_name,email,phone,city,state"
        for _ in range(random.randint(4,10)):
            fn = random.choice(indian_first)
            ln = random.choice(indian_last)
            email = f"{fn.lower()}{ln.lower()}{random.randint(1,99)}@{random.choice(domains_mail)}"
            phone = gen_phone_in()
            city = random.choice(cities_in)
            rows.append(f"{fn} {ln},{email},{phone},{city},India")
            gt["names"].append(f"{fn} {ln}")
            gt["emails"].append(email)
            gt["phones"].append(phone)
            gt["addresses"].append(city)

        content = f"# Scraped from data broker site {random.randint(1,50)}\n{header}\n" + "\n".join(rows)
        pastes.append({
            "id": f"paste_csv_{i+1:03d}",
            "type": "csv_scrape",
            "source": f"broker_scrape_{random.choice(['spokeo','whitepages','truepeoplesearch','zabasearch'])}",
            "date_found": (datetime.now() - timedelta(days=random.randint(1,180))).isoformat(),
            "content": content,
            "ground_truth_pii": gt,
        })

    with open(dest, "w") as f:
        json.dump(pastes, f, indent=2)
    print(f"    ✓ Generated {len(pastes)} synthetic paste entries")
    return len(pastes)



# ── Check-digit helpers ───────────────────────────────────────────────────────
# The benchmark must exercise the checksum algorithms, not agree with them by
# construction. Positives therefore carry correct check digits, and the negative
# set contains number-shaped strings that pass the regex but FAIL the checksum —
# which is the only thing that actually tests false-positive suppression.

_VERHOEFF_D = [
    [0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],
    [3,4,0,1,2,8,9,5,6,7],[4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],
    [6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],[8,7,6,5,9,3,2,1,0,4],
    [9,8,7,6,5,4,3,2,1,0],
]
_VERHOEFF_P = [
    [0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],
    [8,9,1,6,0,4,3,5,2,7],[9,4,5,3,1,2,6,8,7,0],[4,2,8,6,5,7,3,9,0,1],
    [2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8],
]
_VERHOEFF_INV = [0,4,3,2,1,5,6,7,8,9]


def verhoeff_check_digit(number: str) -> str:
    """Return the Verhoeff check digit for a digit string."""
    c = 0
    for i, ch in enumerate(reversed(number + "0")):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(ch)]]
    return str(_VERHOEFF_INV[c])


def gen_valid_aadhaar() -> str:
    """A 12-digit Aadhaar-shaped number that satisfies Verhoeff (like a real one)."""
    body = str(random.randint(2, 9)) + "".join(str(random.randint(0, 9)) for _ in range(10))
    return body + verhoeff_check_digit(body)


def gen_checksum_failing_aadhaar() -> str:
    """Looks exactly like an Aadhaar but the check digit is wrong."""
    valid = gen_valid_aadhaar()
    wrong = str((int(valid[-1]) + random.randint(1, 9)) % 10)
    return valid[:-1] + wrong


def luhn_check_digit(partial: str) -> str:
    """Return the Luhn check digit for a partial card number.

    Counting from the right of the completed number, the check digit is
    position 1 and every even position is doubled — so the rightmost digit of
    `partial` (position 2) is the first one doubled.
    """
    total = 0
    for j, ch in enumerate(reversed(partial)):
        d = int(ch)
        if j % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return str((10 - total % 10) % 10)


def gen_valid_card(prefix: str) -> str:
    """A 16-digit card number that satisfies Luhn."""
    body = prefix + "".join(str(random.randint(0, 9)) for _ in range(15 - len(prefix)))
    return body + luhn_check_digit(body)


def generate_pii_benchmark():
    """Generate ground-truth PII benchmark for accuracy evaluation."""
    dest = os.path.join(BASE_DIR, "benchmarks", "pii_ground_truth.json")
    print(f"[*] Generating PII ground-truth benchmark → {dest}")

    samples = []

    # Valid Aadhaar numbers: correct Verhoeff check digit, as real ones have.
    for i in range(50):
        num = gen_valid_aadhaar()
        formatted = f"{num[:4]} {num[4:8]} {num[8:]}"
        samples.append({
            "id": f"aadhaar_{i+1:03d}",
            "text": f"My Aadhaar number is {formatted}",
            "expected_entities": [{"type": "AADHAAR", "value": num, "start": 23, "end": 23+len(formatted)}],
            "category": "aadhaar",
        })

    # Negatives. Half are rejected by the regex (leading 0/1); the other half are
    # the interesting ones — correctly shaped 12-digit strings with a bad check
    # digit, which only the Verhoeff algorithm can reject. Invoice numbers,
    # transaction ids and timestamps look exactly like this in the wild.
    for i in range(10):
        invalid = f"{random.choice([0,1])}" + "".join([str(random.randint(0,9)) for _ in range(11)])
        samples.append({
            "id": f"aadhaar_invalid_{i+1:03d}",
            "text": f"Invalid reference: {invalid}",
            "expected_entities": [],
            "category": "aadhaar_negative",
        })
    for i in range(20):
        failing = gen_checksum_failing_aadhaar()
        context = random.choice([
            f"Invoice reference {failing} dated today",
            f"Transaction id {failing} posted",
            f"Order number {failing} confirmed",
        ])
        samples.append({
            "id": f"aadhaar_checksum_fail_{i+1:03d}",
            "text": context,
            "expected_entities": [],
            "category": "aadhaar_negative",
        })

    # PAN numbers
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    type_chars = "PCHABFTGJL"
    for i in range(50):
        pan = (random.choice(letters) + random.choice(letters) + random.choice(letters) +
               random.choice(type_chars) + random.choice(letters) +
               str(random.randint(1000,9999)) + random.choice(letters))
        samples.append({
            "id": f"pan_{i+1:03d}",
            "text": f"PAN Card: {pan}",
            "expected_entities": [{"type": "PAN", "value": pan}],
            "category": "pan",
        })

    # Emails
    domains = ["gmail.com", "yahoo.co.in", "outlook.com", "company.org", "university.ac.in"]
    for i in range(50):
        name = random.choice(["aarav","priya","rahul","deepa","kiran","sanjay","meera","arjun","anita","vikram"])
        email = f"{name}.{random.choice(['sharma','patel','kumar','gupta'])}{random.randint(1,99)}@{random.choice(domains)}"
        samples.append({
            "id": f"email_{i+1:03d}",
            "text": f"Contact me at {email} for details.",
            "expected_entities": [{"type": "EMAIL", "value": email}],
            "category": "email",
        })

    # Indian phone numbers
    for i in range(50):
        prefix = random.choice(["9","8","7","6"])
        num = prefix + "".join([str(random.randint(0,9)) for _ in range(9)])
        formats = [
            f"+91{num}", f"+91 {num}", f"+91-{num}",
            f"91{num}", f"0{num}", num,
            f"+91 {num[:5]} {num[5:]}",
        ]
        formatted = random.choice(formats)
        samples.append({
            "id": f"phone_in_{i+1:03d}",
            "text": f"Call me at {formatted}",
            "expected_entities": [{"type": "PHONE_IN", "value": num}],
            "category": "phone_indian",
        })

    # Credit cards: synthetic but Luhn-valid, so the validator is genuinely tested.
    for i in range(30):
        card = gen_valid_card(random.choice(["4", "5", "37", "6011"]))
        formatted = " ".join([card[j:j+4] for j in range(0, len(card), 4)])
        samples.append({
            "id": f"card_{i+1:03d}",
            "text": f"Card ending in {formatted}",
            "expected_entities": [{"type": "CREDIT_CARD", "value": card}],
            "category": "credit_card",
        })

    # UPI IDs
    handles = ["@okaxis", "@ybl", "@paytm", "@ibl", "@upi", "@sbi"]
    for i in range(30):
        name = random.choice(["aarav","priya","rahul","deepa","kiran"])
        upi = f"{name}{random.randint(1,99)}{random.choice(handles)}"
        samples.append({
            "id": f"upi_{i+1:03d}",
            "text": f"Pay via UPI: {upi}",
            "expected_entities": [{"type": "UPI", "value": upi}],
            "category": "upi",
        })

    # IP Addresses
    for i in range(30):
        ip = f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
        samples.append({
            "id": f"ip_{i+1:03d}",
            "text": f"Login from IP {ip}",
            "expected_entities": [{"type": "IP_ADDRESS", "value": ip}],
            "category": "ip_address",
        })

    # IFSC Codes
    bank_codes = ["IDFB", "SBIN", "HDFC", "ICIC", "UTIB", "KKBK", "PUNB", "BARB"]
    for i in range(20):
        ifsc = random.choice(bank_codes) + "0" + "".join([str(random.randint(0,9)) for _ in range(6)])
        samples.append({
            "id": f"ifsc_{i+1:03d}",
            "text": f"IFSC code: {ifsc}",
            "expected_entities": [{"type": "IFSC", "value": ifsc}],
            "category": "ifsc",
        })

    # Mixed multi-entity texts
    for i in range(50):
        fn = random.choice(["Aarav", "Priya", "Rahul", "Ananya", "Kiran"])
        ln = random.choice(["Sharma", "Patel", "Kumar", "Gupta", "Singh"])
        email = f"{fn.lower()}.{ln.lower()}@gmail.com"
        phone = f"+91 {random.choice(['9','8','7'])}{random.randint(100000000,999999999)}"
        pan = (random.choice(letters) + random.choice(letters) + random.choice(letters) +
               random.choice(type_chars) + random.choice(letters) +
               str(random.randint(1000,9999)) + random.choice(letters))

        text = f"Customer {fn} {ln} (email: {email}, phone: {phone}) has PAN {pan}."
        samples.append({
            "id": f"mixed_{i+1:03d}",
            "text": text,
            "expected_entities": [
                {"type": "EMAIL", "value": email},
                {"type": "PHONE_IN", "value": phone.replace("+91 ", "").replace(" ", "")},
                {"type": "PAN", "value": pan},
            ],
            "category": "mixed",
        })

    random.shuffle(samples)
    with open(dest, "w") as f:
        json.dump(samples, f, indent=2)
    print(f"    ✓ Generated {len(samples)} ground-truth benchmark samples")
    return len(samples)


def create_legal_templates():
    """Create statutory legal notice templates for DPDP, GDPR, and CCPA."""
    templates_dir = os.path.join(BASE_DIR, "templates")
    print(f"[*] Creating statutory legal templates → {templates_dir}/")

    templates = {
        "dpdp_erasure_notice.txt": """NOTICE UNDER THE DIGITAL PERSONAL DATA PROTECTION ACT, 2023
(Sections 12 & 13 — Right to Erasure and Grievance Redressal)

Date: {{date}}
Reference: {{reference_id}}

To: The Data Protection Officer / Nodal Officer
{{company_name}}
{{company_address}}

Subject: Formal Request for Erasure of Personal Data under DPDP Act 2023

Dear Sir/Madam,

I, {{user_name}}, am writing to formally request the erasure (deletion) of my personal data held by your organisation, in exercise of my rights as a Data Principal under Section 12 of the Digital Personal Data Protection Act, 2023 (hereinafter "the Act").

IDENTIFICATION OF DATA PRINCIPAL:
• Full Name: {{user_name}}
• Email Address: {{user_email}}
• Phone Number: {{user_phone}}
• Additional Identifiers: {{additional_ids}}

PERSONAL DATA IDENTIFIED IN YOUR SYSTEMS:
{{detected_pii_summary}}

LEGAL BASIS FOR THIS REQUEST:
Under Section 12(1) of the DPDP Act 2023, a Data Principal has the right to request erasure of personal data that is no longer necessary for the purpose for which it was collected, or where the Data Principal has withdrawn consent under Section 6.

Furthermore, Section 11 grants Data Principals the right to access, correct, and erase their data, and Section 13 requires every Data Fiduciary to establish a grievance redressal mechanism.

STATUTORY TIMELINE:
As per the Act and rules framed thereunder, you are required to acknowledge this request within 48 hours and complete the erasure within 30 (thirty) calendar days of receipt of this notice. Failure to comply may result in a complaint to the Data Protection Board of India (DPBI) under Section 27.

REQUESTED ACTION:
1. Confirm receipt of this notice within 48 hours.
2. Identify and enumerate all personal data relating to me in your custody.
3. Permanently delete/erase all such personal data within 30 days.
4. Provide written confirmation of deletion, including any third parties to whom the data was shared.
5. Cease any further processing, sale, or transfer of my personal data.

Should you require any further verification of my identity, please contact me at the email or phone number provided above.

Yours faithfully,

{{user_name}}
{{user_email}}
{{user_phone}}

---
Digital Receipt Hash: {{receipt_hash}}
Generated by SovereignPrivacy AI Agent
""",

        "gdpr_art17_notice.txt": """REQUEST FOR ERASURE UNDER ARTICLE 17 OF THE
GENERAL DATA PROTECTION REGULATION (EU) 2016/679

Date: {{date}}
Reference: {{reference_id}}

To: The Data Protection Officer
{{company_name}}
{{company_address}}

Subject: Request for Erasure of Personal Data — Article 17 GDPR ("Right to be Forgotten")

Dear Data Protection Officer,

Pursuant to Article 17 of Regulation (EU) 2016/679 (the "General Data Protection Regulation" or "GDPR"), I am writing to request the erasure of all personal data relating to me that is currently processed by your organisation.

DATA SUBJECT IDENTIFICATION:
• Full Name: {{user_name}}
• Email: {{user_email}}
• Phone: {{user_phone}}
• Additional Identifiers: {{additional_ids}}

PERSONAL DATA IDENTIFIED:
{{detected_pii_summary}}

LEGAL GROUNDS (Article 17(1)):
(a) The personal data is no longer necessary for the purposes for which it was collected or processed.
(b) I withdraw my consent on which the processing was based (Article 6(1)(a) or Article 9(2)(a)), and there is no other legal ground for the processing.
(d) The personal data has been unlawfully processed.

Under Article 12(3) GDPR, you are required to respond to this request without undue delay and in any event within one month of receipt. This period may be extended by two further months where necessary, provided you inform me within the first month.

Under Article 17(2), where you have made the personal data public, you shall take reasonable steps to inform other controllers processing that data of my erasure request.

REQUESTED ACTIONS:
1. Confirm receipt of this request within 72 hours.
2. Erase all personal data relating to me within 30 calendar days.
3. Inform any third-party recipients of the erasure per Article 19.
4. Provide written confirmation of completed erasure.

Failure to comply may result in a complaint to the relevant Supervisory Authority under Article 77, and/or judicial remedy under Article 79.

Yours sincerely,

{{user_name}}
{{user_email}}

---
Digital Receipt Hash: {{receipt_hash}}
Generated by SovereignPrivacy AI Agent
""",

        "ccpa_deletion_notice.txt": """REQUEST TO DELETE PERSONAL INFORMATION
California Consumer Privacy Act (CCPA) / California Privacy Rights Act (CPRA)
Cal. Civ. Code §§ 1798.105, 1798.106

Date: {{date}}
Reference: {{reference_id}}

To: Privacy Department
{{company_name}}
{{company_address}}

Subject: Verified Request to Delete Personal Information — CCPA § 1798.105

Dear Privacy Officer,

I am a California consumer exercising my right to request deletion of my personal information under the California Consumer Privacy Act of 2018 (CCPA), as amended by the California Privacy Rights Act (CPRA), codified at California Civil Code § 1798.105.

CONSUMER IDENTIFICATION:
• Full Name: {{user_name}}
• Email: {{user_email}}
• Phone: {{user_phone}}
• Additional Identifiers: {{additional_ids}}

PERSONAL INFORMATION DETECTED:
{{detected_pii_summary}}

Under § 1798.105(a), a consumer has the right to request that a business delete any personal information about the consumer which the business has collected. Under § 1798.105(c), a business that receives a verifiable consumer request shall delete the consumer's personal information and direct any service providers to delete the information.

Under § 1798.130, you must respond to this request within 45 calendar days. You may extend this period once by an additional 45 days if reasonably necessary, provided you notify me of the extension.

Per SB 362 (the DELETE Act), you are also required to comply with the California Data Broker Registry obligations and honour deletion requests submitted through the State's centralised mechanism.

REQUESTED ACTIONS:
1. Confirm receipt within 10 business days.
2. Delete all personal information within 45 calendar days.
3. Direct all service providers and contractors to delete the information.
4. Provide written confirmation.

Failure to comply may result in enforcement action by the California Privacy Protection Agency (CPPA).

Respectfully,

{{user_name}}
{{user_email}}

---
Digital Receipt Hash: {{receipt_hash}}
Generated by SovereignPrivacy AI Agent
""",
    }

    for filename, content in templates.items():
        path = os.path.join(templates_dir, filename)
        with open(path, "w") as f:
            f.write(content.strip())
        print(f"    ✓ Created {filename}")

    print(f"    ✓ Created {len(templates)} statutory templates")
    return len(templates)


if __name__ == "__main__":
    print("=" * 60)
    print("  SovereignPrivacy AI — Dataset Builder")
    print("=" * 60)
    print()

    n_brokers = download_optery_brokers()
    n_breaches = download_hibp_breaches()
    n_pastes = generate_synthetic_pastes()
    n_benchmark = generate_pii_benchmark()
    n_templates = create_legal_templates()

    print()
    print("=" * 60)
    print("  Summary")
    print("=" * 60)
    print(f"  Data Brokers:      {n_brokers}")
    print(f"  HIBP Breaches:     {n_breaches}")
    print(f"  Synthetic Pastes:  {n_pastes}")
    print(f"  Benchmark Samples: {n_benchmark}")
    print(f"  Legal Templates:   {n_templates}")
    print("=" * 60)
