from __future__ import annotations

import csv
import os
import shutil
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import database
from .ocr import extract_text
from .pipeline import process_packet


def _font(size: int = 54):
    candidates = []
    if os.name == "nt":
        candidates.extend(
            [
                r"C:\Windows\Fonts\arial.ttf",
                r"C:\Windows\Fonts\calibri.ttf",
                r"C:\Windows\Fonts\segoeui.ttf",
            ]
        )
    candidates.extend(["DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"])
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _write_ocr_probe(path: Path) -> None:
    image = Image.new("RGB", (1600, 700), "white")
    draw = ImageDraw.Draw(image)
    font = _font()
    lines = ["FUEL RECEIPT", "TOTAL 25.00", "LOAD 10001"]
    y = 90
    for line in lines:
        draw.text((100, y), line, fill="black", font=font)
        y += 150
    image.save(path, dpi=(300, 300))


def _write_text_fixture(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="driver-settlement-selftest-"))
    try:
        # Verify that the OCR engine itself is callable from this environment/package.
        probe = root / "ocr_probe.png"
        _write_ocr_probe(probe)
        ocr_text = extract_text(probe).upper()
        ocr_ok = "FUEL" in ocr_text and ("25.00" in ocr_text or "25 00" in ocr_text)

        # Verify business logic with exact temporary document text so OCR variation
        # cannot create a false failure in reconciliation rules.
        load_board = root / "loads.csv"
        with load_board.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["load_id", "driver", "truck", "customer", "origin", "destination", "expected_reimbursement"])
            writer.writerow(["QA-10001", "Test Driver", "101", "Internal QA", "A", "B", "25.00"])

        bol = root / "bol.txt"
        log = root / "log.txt"
        receipt = root / "receipt.txt"
        _write_text_fixture(
            bol,
            "BILL OF LADING / PROOF OF DELIVERY\nLOAD NUMBER: QA-10001\nDRIVER: Test Driver\nRECEIVER SIGNATURE: QA Receiver\n",
        )
        _write_text_fixture(
            log,
            "DRIVER LOG / HOURS OF SERVICE\nLOAD NUMBER: QA-10001\nDRIVER: Test Driver\nDUTY STATUS: COMPLETE\n",
        )
        _write_text_fixture(
            receipt,
            "FUEL RECEIPT\nQA FUEL STATION\nLOAD NUMBER: QA-10001\nDRIVER: Test Driver\nTOTAL: $25.00\n",
        )

        db_path = root / "selftest.db"
        imported = database.import_load_board(load_board, db_path)
        result = process_packet([bol, log, receipt], db_path)
        rows = {row["load_id"]: row for row in database.dashboard_rows(db_path)}
        qa = rows.get("QA-10001", {})
        docs = result.get("documents", [])

        checks = [
            ("OCR engine available", ocr_ok),
            ("Load-board import", imported == 1),
            ("Document classification and extraction", len(docs) == 3 and {d["doc_type"] for d in docs} == {"bol_pod", "driver_log", "fuel_receipt"}),
            ("Load matching", all(d.get("load_id") == "QA-10001" for d in docs)),
            ("Settlement reconciliation", qa.get("status") == "AUTO_CLEARED"),
            ("SQLite persistence", abs(float(qa.get("actual_reimbursement", 0)) - 25.0) < 0.01),
            ("Audit logging", len(database.audit_events(db_path)) >= 5),
        ]

        print("DRIVER SETTLEMENT AUTOMATION - INTERNAL SELF-TEST")
        for label, passed in checks:
            dots = "." * max(2, 42 - len(label))
            print(f"{label} {dots} {'PASS' if passed else 'FAIL'}")

        return 0 if all(passed for _, passed in checks) else 1
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
