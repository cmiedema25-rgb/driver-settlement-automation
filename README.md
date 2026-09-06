# Driver Settlement Automation

A working document-automation system for trucking back offices. Scan a completed driver's paperwork packet — BOL/POD, driver logs, fuel receipts, scale tickets, lumper receipts, tolls and other reimbursable expenses — and the application OCRs the paperwork, classifies each document, extracts load and expense data, matches it to the company's load board, updates settlement records, and sends only exceptions to human review.

## What it proves

This is one end-to-end application, not a collection of disconnected demos. It combines OCR/computer vision, document classification, structured extraction, SQL/SQLite, workflow automation, reconciliation rules, exception detection, audit logging, a Gradio UI, automated tests and CI.

## Real workflow

```text
Driver finishes load
        ↓
Paperwork packet arrives
        ↓
Scan / upload BOL + logs + receipts
        ↓
OCR → classify → extract → match to load
        ↓
Reconcile receipts against expected reimbursement
        ↓
Update settlement database
        ↓
AUTO-CLEAR clean packets / REVIEW exceptions
```

## Quick start

Requires Python 3.11+ and Tesseract OCR.

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e '.[dev]'

# Create three realistic demo loads and scanned paperwork images
python scripts/generate_demo_packet.py

# Prove the full OCR → database → reconciliation workflow
python -m driver_settlement.verify

# Launch the operations dashboard
python app.py
```

The demo intentionally includes one clean packet, one $30 reimbursement mismatch, and one BOL with a missing receiver signature. A credible verification run should therefore show both automated success and human-review exceptions rather than an artificial 100% pass story.

## Expected verification outcome

```text
DRIVER SETTLEMENT AUTOMATION — END-TO-END VERIFICATION
OCR + document classification ........ PASS
Load matching ........................ PASS
Clean settlement auto-clear .......... PASS
Expense mismatch detection ........... PASS
Missing POD signature detection ...... PASS
SQLite update + audit trail .......... PASS

Loads processed: 3
Auto-cleared:    1
Needs review:    2
```

## Demo scenarios

| Load | Expected behavior |
|---|---|
| `LW-88214` | BOL + logs + fuel + scale documents agree. Settlement auto-clears at **$329.22**. |
| `LW-88291` | Submitted reimbursement is **$344.72**, but scanned fuel receipt is **$314.72**. The system flags a **$30.00 mismatch**. |
| `LW-88302` | BOL has no receiver signature. The system flags **missing proof of delivery**. |

## Application behavior

For each uploaded document the pipeline records:

- original filename
- OCR text
- detected document type
- load number
- driver name
- vendor
- date
- receipt amount
- extracted structured fields

For each load it then checks:

- BOL/POD present
- receiver signature present
- driver log present
- documents belong to a known load
- document driver matches assigned driver when available
- extracted reimbursable expenses match the amount submitted for settlement

Clean loads are automatically marked `AUTO_CLEARED`. Anything uncertain or inconsistent is marked `REVIEW` and an exception record explains why.

## Supported document types

- Bill of Lading / Proof of Delivery
- Driver log
- Fuel receipt
- Scale ticket
- Lumper receipt
- Toll receipt
- Parking receipt
- Hotel receipt
- Other expense receipt

## Project layout

```text
app.py                         Gradio operations dashboard
src/driver_settlement/
  database.py                  SQLite schema + system-of-record updates
  ocr.py                       image/PDF OCR
  documents.py                 classification + field extraction
  pipeline.py                  packet workflow + reconciliation
  demo.py                      reproducible realistic demo packet generator
  verify.py                    end-to-end verification command
scripts/generate_demo_packet.py
tests/
.github/workflows/ci.yml
```

## Using your own paperwork

1. Export a load board CSV with these columns:

```text
load_id,driver,truck,customer,origin,destination,expected_reimbursement
```

2. Launch `python app.py`.
3. Import the load board.
4. Upload one or more scanned images/PDFs from a driver's paperwork packet.
5. Enter the packet's load number if it is written only on the envelope; otherwise the extractor can use load IDs found on the paperwork.
6. Review the dashboard and exception queue.

## Safety and accounting boundary

The system never invents missing accounting data. Low-confidence or inconsistent packets go to review. The included workflow updates a local SQLite system of record; a production TMS/accounting integration should use the same validated settlement result through a controlled API adapter.

## Verification evidence

The strongest proof is the reproducible command:

```bash
python -m driver_settlement.verify
```

It generates scan-like paperwork images, runs real Tesseract OCR, processes the files through the same pipeline used by the UI, writes SQLite records, and checks the resulting settlement and exception states.

## License

MIT
