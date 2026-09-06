from pathlib import Path

from driver_settlement import database
from driver_settlement.documents import extract_document
from driver_settlement.pipeline import reconcile_load


def _seed_load(db_path: Path, expected: float = 100.0):
    csv_path = db_path.parent / "loads.csv"
    csv_path.write_text(
        "load_id,driver,truck,customer,origin,destination,expected_reimbursement\n"
        f"LW-10001,Jane Doe,101,Acme,Ontario CA,Phoenix AZ,{expected:.2f}\n",
        encoding="utf-8",
    )
    database.import_load_board(csv_path, db_path)


def test_clean_packet_auto_clears(tmp_path):
    db_path = tmp_path / "test.db"
    _seed_load(db_path, 100.0)
    docs = [
        extract_document("BILL OF LADING / PROOF OF DELIVERY\nLOAD NUMBER: LW-10001\nDRIVER: Jane Doe\nRECEIVER SIGNATURE: J Smith", "bol.txt"),
        extract_document("DRIVER LOG / HOURS OF SERVICE\nLOAD NUMBER: LW-10001\nDRIVER: Jane Doe\nDUTY STATUS: COMPLETE", "log.txt"),
        extract_document("FUEL RECEIPT\nTEST FUEL\nLOAD NUMBER: LW-10001\nDRIVER: Jane Doe\nTOTAL: $100.00", "fuel.txt"),
    ]
    with database.connect(db_path) as conn:
        for doc in docs:
            database.insert_document(conn, doc)
        result = reconcile_load(conn, "LW-10001")
        conn.commit()
    assert result["status"] == "AUTO_CLEARED"
    assert result["actual_reimbursement"] == 100.0


def test_reimbursement_mismatch_goes_to_review(tmp_path):
    db_path = tmp_path / "test.db"
    _seed_load(db_path, 130.0)
    docs = [
        extract_document("BILL OF LADING / PROOF OF DELIVERY\nLOAD NUMBER: LW-10001\nDRIVER: Jane Doe\nRECEIVER SIGNATURE: J Smith", "bol.txt"),
        extract_document("DRIVER LOG / HOURS OF SERVICE\nLOAD NUMBER: LW-10001\nDRIVER: Jane Doe", "log.txt"),
        extract_document("FUEL RECEIPT\nTEST FUEL\nLOAD NUMBER: LW-10001\nDRIVER: Jane Doe\nTOTAL: $100.00", "fuel.txt"),
    ]
    with database.connect(db_path) as conn:
        for doc in docs:
            database.insert_document(conn, doc)
        result = reconcile_load(conn, "LW-10001")
        conn.commit()
    assert result["status"] == "REVIEW"
    assert any(item["code"] == "REIMBURSEMENT_MISMATCH" for item in result["exceptions"])
