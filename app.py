from __future__ import annotations

import json
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from driver_settlement import database
from driver_settlement.pipeline import process_packet


def app_data_dir() -> Path:
    override = os.environ.get("DRIVER_SETTLEMENT_DATA")
    if override:
        root = Path(override)
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home()))
        root = base / "DriverSettlementAutomation"
    else:
        root = Path.home() / ".driver-settlement-automation"
    root.mkdir(parents=True, exist_ok=True)
    return root


DB_PATH = app_data_dir() / "settlements.db"


class DriverSettlementApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Driver Settlement Automation")
        self.geometry("1180x760")
        self.minsize(980, 650)
        self.packet_files: list[str] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        header = ttk.Frame(self, padding=12)
        header.pack(fill="x")
        ttk.Label(header, text="Driver Settlement Automation", font=("Segoe UI", 20, "bold")).pack(side="left")
        ttk.Label(header, text="BOL • Logs • Fuel • Scale • Lumper • Tolls • Expenses", font=("Segoe UI", 10)).pack(side="left", padx=18)

        controls = ttk.Frame(self, padding=(12, 0, 12, 8))
        controls.pack(fill="x")
        ttk.Button(controls, text="Import Load Board CSV", command=self.import_load_board).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Select Paperwork", command=self.select_paperwork).pack(side="left", padx=8)
        ttk.Button(controls, text="Process Packet", command=self.process_selected).pack(side="left", padx=8)
        ttk.Button(controls, text="Refresh", command=self.refresh).pack(side="left", padx=8)

        ttk.Label(controls, text="Envelope Load ID (optional):").pack(side="left", padx=(24, 6))
        self.load_id_var = tk.StringVar()
        ttk.Entry(controls, textvariable=self.load_id_var, width=18).pack(side="left")

        metrics = ttk.Frame(self, padding=(12, 4, 12, 8))
        metrics.pack(fill="x")
        self.metric_vars = {name: tk.StringVar(value="0") for name in ["Loads", "Auto-cleared", "Review", "Documents", "Exceptions", "Reimbursed"]}
        for label, var in self.metric_vars.items():
            box = ttk.LabelFrame(metrics, text=label, padding=8)
            box.pack(side="left", fill="x", expand=True, padx=4)
            ttk.Label(box, textvariable=var, font=("Segoe UI", 16, "bold")).pack()

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        loads_tab = ttk.Frame(notebook)
        exceptions_tab = ttk.Frame(notebook)
        files_tab = ttk.Frame(notebook)
        audit_tab = ttk.Frame(notebook)
        notebook.add(loads_tab, text="Settlements")
        notebook.add(exceptions_tab, text="Exceptions")
        notebook.add(files_tab, text="Selected Paperwork")
        notebook.add(audit_tab, text="Audit Log")

        columns = ("load", "driver", "customer", "route", "expected", "actual", "status", "exceptions")
        self.loads_tree = ttk.Treeview(loads_tab, columns=columns, show="headings")
        widths = {"load": 100, "driver": 150, "customer": 170, "route": 260, "expected": 100, "actual": 100, "status": 110, "exceptions": 90}
        for col in columns:
            self.loads_tree.heading(col, text=col.replace("_", " ").title())
            self.loads_tree.column(col, width=widths[col], anchor="w")
        self.loads_tree.pack(fill="both", expand=True)

        exc_cols = ("load", "severity", "code", "message")
        self.exceptions_tree = ttk.Treeview(exceptions_tab, columns=exc_cols, show="headings")
        for col in exc_cols:
            self.exceptions_tree.heading(col, text=col.title())
        self.exceptions_tree.column("load", width=100)
        self.exceptions_tree.column("severity", width=90)
        self.exceptions_tree.column("code", width=190)
        self.exceptions_tree.column("message", width=720)
        self.exceptions_tree.pack(fill="both", expand=True)

        self.files_list = tk.Listbox(files_tab, font=("Consolas", 10))
        self.files_list.pack(fill="both", expand=True)

        audit_cols = ("time", "event", "load", "details")
        self.audit_tree = ttk.Treeview(audit_tab, columns=audit_cols, show="headings")
        for col in audit_cols:
            self.audit_tree.heading(col, text=col.title())
        self.audit_tree.column("time", width=180)
        self.audit_tree.column("event", width=190)
        self.audit_tree.column("load", width=100)
        self.audit_tree.column("details", width=650)
        self.audit_tree.pack(fill="both", expand=True)

        self.status_var = tk.StringVar(value=f"Database: {DB_PATH}")
        ttk.Label(self, textvariable=self.status_var, relief="sunken", anchor="w").pack(fill="x", side="bottom")

    def import_load_board(self):
        path = filedialog.askopenfilename(title="Select load board CSV", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            count = database.import_load_board(path, DB_PATH)
            self.status_var.set(f"Imported {count} loads from {Path(path).name}")
            self.refresh()
        except Exception as exc:
            messagebox.showerror("Import failed", str(exc))

    def select_paperwork(self):
        paths = filedialog.askopenfilenames(
            title="Select scanned paperwork",
            filetypes=[
                ("Documents", "*.pdf *.png *.jpg *.jpeg *.tif *.tiff *.bmp *.webp *.txt"),
                ("All files", "*.*"),
            ],
        )
        if not paths:
            return
        self.packet_files = list(paths)
        self.files_list.delete(0, tk.END)
        for path in self.packet_files:
            self.files_list.insert(tk.END, path)
        self.status_var.set(f"Selected {len(self.packet_files)} document(s)")

    def process_selected(self):
        if not self.packet_files:
            messagebox.showwarning("No paperwork", "Select one or more scanned documents first.")
            return
        try:
            result = process_packet(self.packet_files, DB_PATH, self.load_id_var.get())
            load_results = result.get("loads", [])
            unmatched = result.get("unmatched_documents", [])
            summary = [f"Processed {len(result.get('documents', []))} document(s)."]
            for item in load_results:
                summary.append(f"{item['load_id']}: {item['status']} — receipts ${item['actual_reimbursement']:.2f}")
            if unmatched:
                summary.append(f"Unmatched documents: {len(unmatched)}")
            messagebox.showinfo("Packet processed", "\n".join(summary))
            self.status_var.set("Packet processing complete")
            self.refresh()
        except Exception as exc:
            messagebox.showerror("Processing failed", str(exc))

    def refresh(self):
        metrics = database.dashboard_metrics(DB_PATH)
        self.metric_vars["Loads"].set(str(metrics["loads"]))
        self.metric_vars["Auto-cleared"].set(str(metrics["auto_cleared"]))
        self.metric_vars["Review"].set(str(metrics["review"]))
        self.metric_vars["Documents"].set(str(metrics["documents"]))
        self.metric_vars["Exceptions"].set(str(metrics["exceptions"]))
        self.metric_vars["Reimbursed"].set(f"${metrics['actual_reimbursement']:,.2f}")

        for tree in (self.loads_tree, self.exceptions_tree, self.audit_tree):
            for item in tree.get_children():
                tree.delete(item)

        for row in database.dashboard_rows(DB_PATH):
            route = f"{row['origin']} → {row['destination']}"
            self.loads_tree.insert("", "end", values=(
                row["load_id"], row["driver"], row["customer"], route,
                f"${row['expected_reimbursement']:.2f}", f"${row['actual_reimbursement']:.2f}",
                row["status"], row["exception_count"],
            ))

        with database.connect(DB_PATH) as conn:
            for row in database.get_exceptions(conn):
                self.exceptions_tree.insert("", "end", values=(row["load_id"], row["severity"], row["code"], row["message"]))

        for row in database.audit_events(DB_PATH):
            details = row["details_json"]
            try:
                details = json.dumps(json.loads(details), sort_keys=True)
            except Exception:
                pass
            self.audit_tree.insert("", "end", values=(row["created_at"], row["event_type"], row["load_id"], details))


def main():
    if "--verify" in sys.argv or "--self-test" in sys.argv:
        from driver_settlement.verify import main as verify_main
        raise SystemExit(verify_main())
    app = DriverSettlementApp()
    app.mainloop()


if __name__ == "__main__":
    main()
