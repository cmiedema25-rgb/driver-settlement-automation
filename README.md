# Driver Settlement Automation

A native Windows desktop application for trucking back offices. It processes the paperwork drivers return after completing a load — BOL/PODs, driver logs, fuel receipts, scale tickets, lumper receipts, tolls, parking, lodging and other reimbursable expenses — then OCRs the scans, classifies the documents, extracts load and expense data, matches them to the load board, reconciles reimbursement amounts, updates a SQLite settlement system of record and sends only exceptions to human review.

This is one working end-to-end application, not a collection of isolated demos.

## Windows executable

GitHub Actions builds a standalone:

```text
DriverSettlementAutomation.exe
```

The Windows build bundles the Python application and Tesseract OCR engine so a reviewer does not need Python or a separate OCR installation.

To get the executable from GitHub, open **Actions → Build Windows EXE → latest successful run → Artifacts → DriverSettlementAutomation-Windows**. The artifact includes the `.exe` and `SHA256.txt` checksum.

## What the desktop app actually does

```text
Completed driver load
        ↓
Paper envelope arrives at the company
        ↓
Scan BOL/POD + logs + receipts
        ↓
Select scans in DriverSettlementAutomation.exe
        ↓
OCR document text
        ↓
Classify document type
        ↓
Extract load / driver / vendor / date / amount
        ↓
Match paperwork to company load board
        ↓
Reconcile reimbursement and required paperwork
        ↓
Update settlement database
        ↓
AUTO_CLEARED or REVIEW with a specific exception
```

The desktop dashboard shows settlement status, expected versus scanned reimbursement totals, exception counts and an audit log of system actions.

## Skills demonstrated in one product

- OCR / computer vision document processing
- document classification
- structured field extraction
- workflow automation
- Python desktop application development
- SQLite / SQL system-of-record updates
- accounting-style reimbursement reconciliation
- anomaly and missing-document detection
- human-in-the-loop review routing
- audit logging
- test automation
- GitHub Actions CI/CD
- Windows executable packaging

## Supported paperwork

- Bill of Lading / Proof of Delivery
- driver log / hours-of-service paperwork
- fuel receipt
- scale ticket
- lumper receipt
- toll receipt
- parking receipt
- hotel / lodging receipt
- other expense receipt

Image scans and PDFs are supported. Text-based PDFs are read directly; image-only PDFs are rendered and OCRed.

## Real settlement rules

For every known load, the application checks:

1. A BOL/POD is present.
2. A receiver signature is present on the POD.
3. Driver logs are present.
4. Extracted load IDs match known company loads.
5. Extracted driver names match the assigned driver when the document contains a driver name.
6. The total of scanned reimbursable receipts matches the reimbursement amount submitted for settlement.

A clean packet is marked `AUTO_CLEARED`. Any inconsistent or incomplete packet becomes `REVIEW` and gets explicit exception records.

## Reproducible demonstration

The repo generates three realistic scan-like paperwork packets and runs them through the same OCR and settlement pipeline used by the desktop app.

```bash
python scripts/generate_demo_packet.py
python -m driver_settlement.verify
```

Expected business outcome:

| Load | Expected result |
|---|---|
| `LW-88214` | BOL, signature, log, fuel and scale paperwork agree. Auto-clears with **$329.22** in scanned reimbursable expenses. |
| `LW-88291` | Settlement submission expects **$344.72**, but the scanned receipt supports **$314.72**. Goes to review with a **$30.00 reimbursement mismatch**. |
| `LW-88302` | BOL exists but the receiver signature is missing. Goes to review for **missing POD signature**. |

Expected verification summary:

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

The demo deliberately contains failures. The project does not claim artificial 100% real-world document accuracy.

## Running from source

Requires Python 3.11+ and Tesseract OCR when not using the packaged Windows executable.

```bash
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate       # Windows

python -m pip install -e '.[dev]'
python app.py
```

## Using company data

Import a load-board CSV with:

```text
load_id,driver,truck,customer,origin,destination,expected_reimbursement
```

Then:

1. Open the desktop application.
2. Click **Import Load Board CSV**.
3. Click **Select Paperwork** and select the scanned packet files.
4. Optionally enter the load number written on the envelope if it is absent from the paperwork.
5. Click **Process Packet**.
6. Review the **Settlements**, **Exceptions**, and **Audit Log** tabs.

The application's SQLite database is stored under the user's local application-data directory rather than inside the executable.

## Data model

The SQLite system of record contains:

- `loads` — company load and settlement state
- `documents` — OCR output and structured document fields
- `exceptions` — unresolved settlement/document problems
- `audit_log` — trace of imports, processing decisions and settlement updates

## Security / accounting boundary

The application does not invent missing accounting values. Missing, inconsistent or unsupported paperwork is routed to review. The included product updates its own local SQLite system of record; a production TMS/accounting deployment can connect the validated settlement result to a controlled API adapter without changing the OCR/reconciliation workflow.

## Building the Windows executable locally

On a Windows machine with Chocolatey available:

```powershell
./scripts/build_windows.ps1
```

The output is:

```text
dist/DriverSettlementAutomation.exe
```

The same build runs automatically in `.github/workflows/build-windows.yml`.

## Verification

Linux CI runs unit tests plus the complete OCR workflow. Windows CI independently runs the tests and verification before PyInstaller is allowed to produce the executable.

```bash
python -m pytest -q
python -m driver_settlement.verify
```

## License

MIT
