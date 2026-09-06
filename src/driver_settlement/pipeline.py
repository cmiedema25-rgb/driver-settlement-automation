from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from . import database
from .documents import EXPENSE_TYPES, extract_document
from .ocr import extract_text

REIMBURSEMENT_TOLERANCE = 0.02


def _same_person(a: str, b: str) -> bool:
    norm = lambda value: " ".join(value.lower().replace(".", "").split())
    return norm(a) == norm(b)


def _decode_fields(row: Any) -> dict[str, Any]:
    try:
        return json.loads(row["fields_json"])
    except Exception:
        return {}


def reconcile_load(conn, load_id: str) -> dict[str, Any]:
    load = database.get_load(conn, load_id)
    if load is None:
        return {"load_id": load_id, "status": "UNMATCHED", "exceptions": ["UNKNOWN_LOAD"]}

    database.clear_open_exceptions(conn, load_id)
    docs = database.load_documents(conn, load_id)
    doc_types = {row["doc_type"] for row in docs}
    expense_total = round(
        sum(float(row["amount"] or 0) for row in docs if row["doc_type"] in EXPENSE_TYPES),
        2,
    )

    issues: list[dict[str, str]] = []

    def issue(code: str, message: str, severity: str = "HIGH") -> None:
        issues.append({"code": code, "message": message, "severity": severity})
        database.add_exception(conn, load_id, code, message, severity)

    if "bol_pod" not in doc_types:
        issue("MISSING_BOL", "No Bill of Lading / Proof of Delivery document is attached.")
    if "driver_log" not in doc_types:
        issue("MISSING_DRIVER_LOG", "No driver log / hours-of-service document is attached.")

    bol_rows = [row for row in docs if row["doc_type"] == "bol_pod"]
    if bol_rows:
        signature_results = [_decode_fields(row).get("receiver_signature_present") for row in bol_rows]
        if not any(value is True for value in signature_results):
            issue("MISSING_POD_SIGNATURE", "BOL/POD was found, but no receiver signature was detected.")

    assigned_driver = str(load["driver"] or "").strip()
    for row in docs:
        extracted_driver = str(_decode_fields(row).get("driver") or "").strip()
        if assigned_driver and extracted_driver and not _same_person(assigned_driver, extracted_driver):
            issue(
                "DRIVER_MISMATCH",
                f"{row['filename']} names driver '{extracted_driver}', but load {load_id} is assigned to '{assigned_driver}'.",
            )

    expected = round(float(load["expected_reimbursement"] or 0), 2)
    difference = round(expense_total - expected, 2)
    if abs(difference) > REIMBURSEMENT_TOLERANCE:
        direction = "over" if difference > 0 else "under"
        issue(
            "REIMBURSEMENT_MISMATCH",
            (
                f"Scanned reimbursable receipts total ${expense_total:.2f}; settlement submission expects "
                f"${expected:.2f}. Receipts are ${abs(difference):.2f} {direction} the submitted amount."
            ),
        )

    docs_complete = "bol_pod" in doc_types and "driver_log" in doc_types and not any(
        i["code"] == "MISSING_POD_SIGNATURE" for i in issues
    )
    status = "AUTO_CLEARED" if not issues else "REVIEW"
    database.update_settlement(conn, load_id, expense_total, status, docs_complete)
    return {
        "load_id": load_id,
        "status": status,
        "expected_reimbursement": expected,
        "actual_reimbursement": expense_total,
        "difference": difference,
        "document_count": len(docs),
        "exceptions": issues,
    }


def process_packet(
    files: Iterable[str | Path],
    db_path: str | Path,
    packet_load_id: str | None = None,
) -> dict[str, Any]:
    packet_load_id = (packet_load_id or "").strip().upper() or None
    processed: list[dict[str, Any]] = []
    touched_loads: set[str] = set()
    unmatched: list[dict[str, Any]] = []

    with database.connect(db_path) as conn:
        for file_path in files:
            path = Path(file_path)
            text = extract_text(path)
            doc = extract_document(text, path.name)
            detected_load = doc.get("load_id")
            load_id = (detected_load or packet_load_id or "").upper() or None
            doc["load_id"] = load_id
            doc["fields"]["load_id"] = load_id
            doc["fields"]["detected_load_id"] = detected_load
            doc["fields"]["packet_load_id"] = packet_load_id

            if detected_load and packet_load_id and detected_load != packet_load_id:
                doc["fields"]["packet_load_conflict"] = True

            database.insert_document(conn, doc)
            processed.append(
                {
                    "filename": doc["filename"],
                    "doc_type": doc["doc_type"],
                    "load_id": load_id,
                    "driver": doc.get("driver"),
                    "vendor": doc.get("vendor"),
                    "amount": doc.get("amount"),
                }
            )

            if not load_id or database.get_load(conn, load_id) is None:
                database.add_exception(
                    conn,
                    load_id,
                    "UNKNOWN_LOAD",
                    f"Could not match {doc['filename']} to a known load.",
                    "HIGH",
                )
                unmatched.append(processed[-1])
                continue

            if detected_load and packet_load_id and detected_load != packet_load_id:
                database.add_exception(
                    conn,
                    load_id,
                    "PACKET_LOAD_CONFLICT",
                    f"{doc['filename']} says {detected_load}, but the envelope/packet was entered as {packet_load_id}.",
                    "CRITICAL",
                )
            touched_loads.add(load_id)

        results = [reconcile_load(conn, load_id) for load_id in sorted(touched_loads)]
        conn.commit()

    return {
        "documents": processed,
        "loads": results,
        "unmatched_documents": unmatched,
    }
