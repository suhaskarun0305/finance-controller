"""
Finance Controller — Ingestion Normalizer Module
=================================================

Normalizes raw incoming transaction, invoice, and settlement records prior
to ingestion and deduplication.

Normalization rules:
  1. Date Normalization: Parses ISO, slash/dash formats, timestamps into standard date/datetime objects.
  2. Currency Normalization: Cleans currency symbols/names ("inr", "Rs.", "₹") into uppercase ISO-4217 codes ("INR").
  3. Merchant Naming Normalization: Trim, case-fold, strip corporate suffixes (Pvt Ltd, Inc, LLC),
     remove punctuation, and standardize common abbreviation variants.
"""

import re
from datetime import date, datetime
from typing import Any, Dict


# ---------------------------------------------------------------------------
# Common Corporate Suffixes to Strip
# ---------------------------------------------------------------------------
SUFFIXES_PATTERN = re.compile(
    r"\b(pvt\.?\s*ltd\.?|private\s+limited|ltd\.?|limited|inc\.?|incorporated|llc\.?|corp\.?|corporation|co\.?|company)\b",
    re.IGNORECASE,
)

# Punctuation to remove
PUNCTUATION_PATTERN = re.compile(r"[.,()\-\[\]\"']+")

# Whitespace collapsing
WHITESPACE_PATTERN = re.compile(r"\s+")

# Common abbreviation replacements
ABBREVIATION_MAP = {
    "tech": "technologies",
    "techno": "technologies",
    "hc": "healthcare",
    "int": "international",
    "intl": "international",
    "soln": "solutions",
    "solns": "solutions",
    "sys": "systems",
}


def normalize_name(name: str | None) -> str:
    """
    Normalize merchant or counterparty name.

    Performs:
      - Lowercase case-folding
      - Punctuation removal
      - Suffix stripping (Pvt Ltd, Inc, Co, etc.)
      - Abbreviation expansion
      - Whitespace trimming and collapsing
    """
    if not name:
        return ""

    cleaned = name.strip().lower()

    # Remove corporate suffixes
    cleaned = SUFFIXES_PATTERN.sub("", cleaned)

    # Remove punctuation
    cleaned = PUNCTUATION_PATTERN.sub(" ", cleaned)

    # Collapse whitespace
    words = WHITESPACE_PATTERN.split(cleaned.strip())

    # Replace abbreviations
    normalized_words = [ABBREVIATION_MAP.get(w, w) for w in words if w]

    return " ".join(normalized_words)


def normalize_currency(currency_str: str | None) -> str:
    """
    Normalize currency codes into standard 3-letter ISO-4217 uppercase.

    Handles 'inr', 'Rs.', '₹', 'USD', '$', etc. Defaults to 'INR'.
    """
    if not currency_str:
        return "INR"

    curr = currency_str.strip().upper()

    if curr in ("RS", "RS.", "RUPEES", "INR", "₹"):
        return "INR"
    if curr in ("USD", "$", "DOLLAR", "DOLLARS"):
        return "USD"

    # Default fallback: return first 3 alphanumeric uppercase characters or 'INR'
    cleaned = re.sub(r"[^A-Z]", "", curr)
    return cleaned if len(cleaned) == 3 else "INR"


def normalize_date(val: Any) -> datetime:
    """
    Parses various date/time representations into a UTC datetime object.

    Supported inputs:
      - datetime / date objects
      - ISO-8601 strings ("2025-01-15", "2025-01-15T14:30:00Z")
      - Slash/dash string formats ("15/01/2025", "15-01-2025", "2025/01/15")
      - Unix numeric timestamps (seconds or milliseconds)

    Raises ValueError if input is missing or invalid.
    """
    if val is None or val == "":
        raise ValueError("Missing required date field")

    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime.combine(val, datetime.min.time())

    if isinstance(val, (int, float)):
        # Handle milliseconds vs seconds
        ts = val / 1000.0 if val > 1e11 else val
        return datetime.fromtimestamp(ts)

    if isinstance(val, str):
        s = val.strip()
        # ISO format
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            pass

        # Try common date formats
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y/%m/%d",
            "%d %b %Y",
            "%d %B %Y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue

    raise ValueError(f"Unable to parse date: {val!r}")


def normalize_record(raw_record: Dict[str, Any], record_type: str = "payment") -> Dict[str, Any]:
    """
    Normalizes a complete raw record dictionary.

    Returns a clean dictionary with normalized dates, currencies, and names.
    Raises ValueError for missing or invalid critical fields.
    """
    if not isinstance(raw_record, dict):
        raise ValueError("Raw record must be a dictionary")

    record = raw_record.copy()

    # Amount validation
    if "amount" not in record or record["amount"] is None or record["amount"] == "":
        raise ValueError("Missing required field: amount")
    try:
        record["amount"] = round(float(record["amount"]), 2)
        if record["amount"] <= 0:
            raise ValueError(f"Invalid amount: {record['amount']}")
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid numeric amount: {record.get('amount')!r}") from e

    # Currency normalization
    record["currency"] = normalize_currency(record.get("currency"))

    # Date normalization
    date_field = "payment_date" if record_type == "payment" else ("issue_date" if record_type == "invoice" else "settlement_date")
    raw_date = record.get(date_field) or record.get("date")
    record[date_field] = normalize_date(raw_date)

    # Name normalization
    if "payer_name" in record:
        record["normalized_payer_name"] = normalize_name(record["payer_name"])
    if "merchant_name" in record or "name" in record:
        record["normalized_merchant_name"] = normalize_name(record.get("merchant_name") or record.get("name"))

    return record
