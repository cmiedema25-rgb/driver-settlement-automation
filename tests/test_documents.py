from driver_settlement.documents import classify_document, extract_document


def test_fuel_receipt_extraction():
    text = """FUEL RECEIPT
PILOT TRAVEL CENTER #328
LOAD NUMBER: LW-88214
DRIVER: Maria Santos
DATE: 2026-09-05
DIESEL: 82.4 GALLONS
TOTAL: $314.72
"""
    doc = extract_document(text, "fuel.png")
    assert doc["doc_type"] == "fuel_receipt"
    assert doc["load_id"] == "LW-88214"
    assert doc["driver"] == "Maria Santos"
    assert doc["amount"] == 314.72


def test_missing_signature_is_detected():
    text = """BILL OF LADING / PROOF OF DELIVERY
LOAD NUMBER: LW-88302
DRIVER: Elena Garcia
RECEIVER SIGNATURE: MISSING
"""
    doc = extract_document(text, "bol.png")
    assert doc["doc_type"] == "bol_pod"
    assert doc["fields"]["receiver_signature_present"] is False


def test_scale_ticket_classification():
    assert classify_document("CAT SCALE TICKET\nGROSS WEIGHT: 78,640 LB\nTOTAL: $14.50") == "scale_ticket"
