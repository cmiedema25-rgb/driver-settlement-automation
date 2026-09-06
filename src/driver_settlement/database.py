from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS loads (
    load_id TEXT PRIMARY KEY,
    driver TEXT NOT NULL,
    truck TEXT,
    customer TEXT,
    origin TEXT,
    destination TEXT,
    expected_reimbursement REAL NOT NULL DEFAULT 0,
    actual_reimbursement REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'PENDING',
    docs_complete INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    load_id TEXT,
    filename TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    vendor TEXT,
    document_date TEXT,
    amount REAL,
    fields_json TEXT NOT NULL,
    ocr_text TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS exceptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    load_id TEXT,
    code TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolved INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    load_id TEXT,
    details_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def import_load_board(csv_path: str | Path, db_path: str | Path) -> int:
    required = {
        "load_id",
        "driver",
        "truck",
        "customer",
        "origin",
        "destination",
        "expected_reimbursement",
    }
    count = 0
    with open(csv_path, newline="", encoding="utf-8-sig") as fh, connect(db_path) as conn:
        reader = csv.DictReader(fh)
        fields = set(reader.fieldnames or [])
        missing = required - fields
        if missing:
            raise ValueError(f"Load board is missing required columns: {sorted(missing)}")
        for row in reader:
            load_id = (row.get("load_id") or "").strip().upper()
            if not load_id:
                continue
            conn.execute(
                """
                INSERT INTO loads (
                    load_id, driver, truck, customer, origin, destination,
                    expected_reimbursement, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(load_id) DO UPDATE SET
                    driver=excluded.driver,
                    truck=excluded.truck,
                    customer=excluded.customer,
                    origin=excluded.origin,
                    destination=excluded.destination,
                    expected_reimbursement=excluded.expected_reimbursement,
                    updated_at=excluded.updated_at
                """,
                (
                    load_id,
                    (row.get("driver") or "").strip(),
                    (row.get("truck") or "").strip(),
                    (row.get("customer") or "").strip(),
                    (row.get("origin") or "").strip(),
                    (row.get("destination") or "").strip(),
                    float(row.get("expected_reimbursement") or 0),
                    utc_now(),
                ),
            )
            audit(conn, "LOAD_IMPORTED", load_id, {"source": str(csv_path)})
            count += 1
        conn.commit()
    return count


def audit(conn: sqlite3.Connection, event_type: str, load_id: str | None, details: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO audit_log(event_type, load_id, details_json, created_at) VALUES (?, ?, ?, ?)",
        (event_type, load_id, json.dumps(details, sort_keys=True), utc_now()),
    )


def get_load(conn: sqlite3.Connection, load_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM loads WHERE load_id = ?", (load_id.upper(),)).fetchone()


def insert_document(conn: sqlite3.Connection, document: dict[str, Any]) -> int:
    cur = conn.execute(
        """
        INSERT INTO documents(
            load_id, filename, doc_type, vendor, document_date, amount,
            fields_json, ocr_text, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            document.get("load_id"),
            document["filename"],
            document["doc_type"],
            document.get("vendor"),
            document.get("date"),
            document.get("amount"),
            json.dumps(document.get("fields", {}), sort_keys=True),
            document.get("ocr_text", ""),
            utc_now(),
        ),
    )
    audit(
        conn,
        "DOCUMENT_PROCESSED",
        document.get("load_id"),
        {
            "filename": document["filename"],
            "doc_type": document["doc_type"],
            "amount": document.get("amount"),
        },
    )
    return int(cur.lastrowid)


def load_documents(conn: sqlite3.Connection, load_id: str) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM documents WHERE load_id = ? ORDER BY id", (load_id.upper(),)))


def clear_open_exceptions(conn: sqlite3.Connection, load_id: str) -> None:
    conn.execute("DELETE FROM exceptions WHERE load_id = ? AND resolved = 0", (load_id.upper(),))


def add_exception(
    conn: sqlite3.Connection,
    load_id: str | None,
    code: str,
    message: str,
    severity: str = "HIGH",
) -> None:
    conn.execute(
        "INSERT INTO exceptions(load_id, code, severity, message, created_at) VALUES (?, ?, ?, ?, ?)",
        (load_id, code, severity, message, utc_now()),
    )
    audit(conn, "EXCEPTION_CREATED", load_id, {"code": code, "severity": severity, "message": message})


def update_settlement(
    conn: sqlite3.Connection,
    load_id: str,
    actual_reimbursement: float,
    status: str,
    docs_complete: bool,
) -> None:
    conn.execute(
        """
        UPDATE loads
        SET actual_reimbursement = ?, status = ?, docs_complete = ?, updated_at = ?
        WHERE load_id = ?
        """,
        (round(actual_reimbursement, 2), status, int(docs_complete), utc_now(), load_id.upper()),
    )
    audit(
        conn,
        "SETTLEMENT_UPDATED",
        load_id.upper(),
        {
            "actual_reimbursement": round(actual_reimbursement, 2),
            "status": status,
            "docs_complete": docs_complete,
        },
    )


def get_exceptions(conn: sqlite3.Connection, load_id: str | None = None) -> list[sqlite3.Row]:
    if load_id:
        return list(
            conn.execute(
                "SELECT * FROM exceptions WHERE load_id = ? AND resolved = 0 ORDER BY id",
                (load_id.upper(),),
            )
        )
    return list(conn.execute("SELECT * FROM exceptions WHERE resolved = 0 ORDER BY id"))


def dashboard_rows(db_path: str | Path) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                l.load_id, l.driver, l.customer, l.origin, l.destination,
                l.expected_reimbursement, l.actual_reimbursement,
                l.status, l.docs_complete,
                COUNT(e.id) AS exception_count
            FROM loads l
            LEFT JOIN exceptions e ON e.load_id = l.load_id AND e.resolved = 0
            GROUP BY l.load_id
            ORDER BY CASE l.status WHEN 'REVIEW' THEN 0 WHEN 'PENDING' THEN 1 ELSE 2 END, l.load_id
            """
        ).fetchall()
        return [dict(r) for r in rows]


def dashboard_metrics(db_path: str | Path) -> dict[str, Any]:
    with connect(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM loads").fetchone()[0]
        auto = conn.execute("SELECT COUNT(*) FROM loads WHERE status = 'AUTO_CLEARED'").fetchone()[0]
        review = conn.execute("SELECT COUNT(*) FROM loads WHERE status = 'REVIEW'").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM loads WHERE status = 'PENDING'").fetchone()[0]
        docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        exceptions = conn.execute("SELECT COUNT(*) FROM exceptions WHERE resolved = 0").fetchone()[0]
        reimbursement = conn.execute("SELECT COALESCE(SUM(actual_reimbursement), 0) FROM loads").fetchone()[0]
        return {
            "loads": total,
            "auto_cleared": auto,
            "review": review,
            "pending": pending,
            "documents": docs,
            "exceptions": exceptions,
            "actual_reimbursement": round(float(reimbursement), 2),
        }


def audit_events(db_path: str | Path, limit: int = 100) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
