from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from . import database
from .demo import generate_demo_dataset
from .pipeline import process_packet


def main() -> int:
    temp_root = Path(tempfile.mkdtemp(prefix="driver-settlement-verify-"))
    try:
        dataset = generate_demo_dataset(temp_root)
        db_path = temp_root / "verify.db"
        imported = database.import_load_board(dataset["load_board"], db_path)
        result = process_packet(dataset["documents"], db_path)

        rows = {row["load_id"]: row for row in database.dashboard_rows(db_path)}
        with database.connect(db_path) as conn:
            exceptions = database.get_exceptions(conn)

        checks = []

        def check(label: str, condition: bool):
            checks.append((label, bool(condition)))

        check("OCR + document classification", len(result["documents"]) == 9)
        check("Load matching", set(rows) == {"LW-88214", "LW-88291", "LW-88302"})
        check(
            "Clean settlement auto-clear",
            rows.get("LW-88214", {}).get("status") == "AUTO_CLEARED"
            and abs(float(rows.get("LW-88214", {}).get("actual_reimbursement", 0)) - 329.22) < 0.01,
        )
        mismatch_codes = {(row["load_id"], row["code"]) for row in exceptions}
        check("Expense mismatch detection", ("LW-88291", "REIMBURSEMENT_MISMATCH") in mismatch_codes)
        check("Missing POD signature detection", ("LW-88302", "MISSING_POD_SIGNATURE") in mismatch_codes)
        audit = database.audit_events(db_path)
        check("SQLite update + audit trail", imported == 3 and len(audit) >= 12)

        print("DRIVER SETTLEMENT AUTOMATION — END-TO-END VERIFICATION")
        for label, passed in checks:
            dots = "." * max(2, 38 - len(label))
            print(f"{label} {dots} {'PASS' if passed else 'FAIL'}")

        metrics = database.dashboard_metrics(db_path)
        print()
        print(f"Loads processed: {metrics['loads']}")
        print(f"Auto-cleared:    {metrics['auto_cleared']}")
        print(f"Needs review:    {metrics['review']}")
        print(f"Documents:       {metrics['documents']}")
        print(f"Exceptions:      {metrics['exceptions']}")

        return 0 if all(passed for _, passed in checks) else 1
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
