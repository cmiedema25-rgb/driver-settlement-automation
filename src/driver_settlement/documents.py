from __future__ import annotations

import re
from pathlib import Path
from typing import Any

EXPENSE_TYPES = {
    "fuel_receipt",
    "scale_ticket",
    "lumper_receipt",
    "toll_receipt",
    "parking_receipt",
    "hotel_receipt",
    "other_expense",
}


def _clean(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def classify_document(text: str) -> str:
    t = text.upper()
    rules = [
        ("bol_pod", ["BILL OF LADING", "PROOF OF DELIVERY", "RECEIVER SIGNATURE"]),
        ("driver_log", ["DRIVER LOG", "HOURS OF SERVICE", "DUTY STATUS"]),
        ("fuel_receipt", ["FUEL RECEIPT", "GALLONS", "DIESEL"]),
        ("scale_ticket", ["SCALE TICKET", "CAT SCALE", "STEER AXLE", "GROSS WEIGHT"]),
        ("lumper_receipt", ["LUMPER", "UNLOADING SERVICE"]),
        ("toll_receipt", ["TOLL RECEIPT", "TOLL ROAD", "TURNPIKE"]),
        ("parking_receipt", ["PARKING RECEIPT", "TRUCK PARKING"]),
        ("hotel_receipt", ["HOTEL RECEIPT", "LODGING"]),
    ]
    for doc_type, keywords in rules:
        if any(keyword in t for keyword in keywords):
            return doc_type
    if "RECEIPT" in t or "TOTAL" in t or "AMOUNT" in t:
        return "other_expense"
    return "unknown"


def _first_match(patterns: list[str], text: str, flags: int = re.IGNORECASE | re.MULTILINE) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            value = match.group(1).strip(" :#-\t")
            if value:
                return value
    return None


def extract_load_id(text: str) -> str | None:
    value = _first_match(
        [
            r"\bLOAD\s*(?:NUMBER|NO\.?|#)?\s*[:#-]?\s*([A-Z]{1,5}-?\d{4,10})\b",
            r"\b(LW-?\d{4,10})\b",
        ],
        text,
    )
    return value.upper() if value else None


def extract_driver(text: str) -> str | None:
    value = _first_match(
        [r"^\s*DRIVER\s*(?:NAME)?\s*[:#-]\s*([^\n]+)$"],
        text,
    )
    if not value:
        return None
    value = re.sub(r"\s{2,}.*$", "", value).strip()
    return value[:80]


def extract_date(text: str) -> str | None:
    value = _first_match(
        [
            r"\b(?:DATE|DELIVERED|DELIVERY DATE|TRANSACTION DATE)\s*[:#-]?\s*(\d{4}-\d{2}-\d{2})\b",
            r"\b(?:DATE|DELIVERED|DELIVERY DATE|TRANSACTION DATE)\s*[:#-]?\s*(\d{1,2}/\d{1,2}/\d{2,4})\b",
        ],
        text,
    )
    return value


def extract_amount(text: str) -> float | None:
    patterns = [
        r"(?:GRAND\s+TOTAL|TOTAL\s+DUE|TOTAL|AMOUNT\s+DUE|AMOUNT|CHARGE)\s*[:$ ]+\$?\s*([0-9][0-9,]*\.\d{2})",
        r"\$\s*([0-9][0-9,]*\.\d{2})\s*(?:TOTAL|USD)?\b",
    ]
    value = _first_match(patterns, text)
    if value is None:
        return None
    try:
        return round(float(value.replace(",", "")), 2)
    except ValueError:
        return None


def extract_vendor(text: str, doc_type: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if doc_type not in EXPENSE_TYPES or not lines:
        return None
    stop = {
        "FUEL RECEIPT",
        "SCALE TICKET",
        "LUMPER RECEIPT",
        "TOLL RECEIPT",
        "PARKING RECEIPT",
        "HOTEL RECEIPT",
        "RECEIPT",
    }
    for line in lines[:4]:
        upper = line.upper()
        if upper in stop or upper.startswith("LOAD ") or upper.startswith("DRIVER "):
            continue
        if len(line) <= 80:
            return line
    return None


def receiver_signature_present(text: str) -> bool | None:
    if "RECEIVER SIGNATURE" not in text.upper() and "PROOF OF DELIVERY" not in text.upper():
        return None
    value = _first_match([r"RECEIVER\s+SIGNATURE\s*[:#-]\s*([^\n]+)"], text)
    if value is None:
        return False
    normalized = value.upper().strip(" ._-")
    return normalized not in {"", "MISSING", "NONE", "N/A", "NA", "NOT SIGNED", "UNSIGNED"}


def extract_document(text: str, filename: str | Path) -> dict[str, Any]:
    text = _clean(text)
    doc_type = classify_document(text)
    load_id = extract_load_id(text)
    driver = extract_driver(text)
    amount = extract_amount(text) if doc_type in EXPENSE_TYPES else None
    vendor = extract_vendor(text, doc_type)
    date = extract_date(text)
    fields: dict[str, Any] = {
        "load_id": load_id,
        "driver": driver,
    }
    if doc_type == "bol_pod":
        fields["receiver_signature_present"] = receiver_signature_present(text)
    if doc_type in EXPENSE_TYPES:
        fields["reimbursable"] = True
    return {
        "filename": Path(filename).name,
        "doc_type": doc_type,
        "load_id": load_id,
        "driver": driver,
        "vendor": vendor,
        "date": date,
        "amount": amount,
        "fields": fields,
        "ocr_text": text,
    }
