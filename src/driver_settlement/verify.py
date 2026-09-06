from __future__ import annotations

import csv
import shutil
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import database
from .ocr import extract_text
from .pipeline import process_packet


def _font(size: int = 30):
    for candidate in ["DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _write_test_scan(path: Path, lines: list[str]) -> None:
    image = Image.new("RGB", (1500, 1800), "white")
    draw = ImageDraw.Draw(image)
    font = _font()
    y = 80
    for line in lines:
        draw.text((80, y), line, fill="black", font=font)
        y += 58
    image.save(path)


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="driver-settlement-selftest-"))
    try:
        load_board = root / "loads.csv"
        with load_board.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["load_id", "driver", "truck", "customer", "origin", "destination", "expected_reimbursement"])
            writer.writerow(["QA-10001", "Test Driver", "101", "Internal QA", "A", "B", "25.00"])

        bol = root / "bol.png"
        log = root / "log.png"
        receipt = root / "receipt.png"
        _write_test_scan(
            bol,
            [
                "BILL OF LADING / PROOF OF DELIVERY",
                "LOAD NUMBER: QA-10001",
                "DRIVER: Test Driver",
                "RECEIVER SIGNATURE: QA Receiver",
            ],
        )
        _write_test_scan(
            log,
            [
                "DRIVER LOG / HOURS OF SERVICE",
                "LOAD NUMBER: QA-10001",
                "DRIVER: Test Driver",
                "DUTY STATUS: COMPLETE",
            ],
        )
        _write_test_scan(
            receipt,
            [
                "FUEL RECEIPT",
                "QA FUEL STATION",
                "LOAD NUMBER: QA-10001",
                "DRIVER: Test Driver",
                "TOTAL: $25.00",
            ],
        )

        ocr_probe = extract_text(receipt)
        db_path = root / "selftest.db"
        imported = database.import_load_board(load_board, db_path)
        result = process_packet([bol, log, receipt], db_path)
        rows = {row["load_id"]: row for row in database.dashboard_rows(db_path)}
        qa = rows.get("QA-10001", {})

        checks = [
            ("OCR engine", "QA-10001" in ocr_probe.upper()),
            ("Load-board import", imported == 1),
            ("Document classification and extraction", len(result.get("documents", [])) == 3),
            ("Load matching", "QA-10001" in rows),
            ("Settlement reconciliation", qa.get("status") == "AUTO_CLEARED"),
            ("SQLite persistence", abs(float(qa.get("actual_reimbursement", 0)) - 25.0) < 0.01),
            ("Audit logging", len(database.audit_events(db_path)) >= 5),
        ]

        print("DRIVER SETTLEMENT AUTOMATION — INTERNAL SELF-TEST")
        for label, passed in checks:
            dots = "." * max(2, 42 - len(label))
            print(f"{label} {dots} {'PASS' if passed else 'FAIL'}")

        return 0 if all(passed for _, passed in checks) else 1
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
