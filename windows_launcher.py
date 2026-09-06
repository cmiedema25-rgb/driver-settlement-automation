"""Windows desktop entry point for packaged Driver Settlement Automation."""
from pathlib import Path
import os
import sys


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative


def main() -> None:
    # Keep writable application data outside the packaged executable.
    appdata = Path(os.getenv("LOCALAPPDATA", Path.home())) / "DriverSettlementAutomation"
    appdata.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("DRIVER_SETTLEMENT_DATA", str(appdata))

    # Import only after the writable data directory has been configured.
    from driver_settlement.app import launch
    launch(inbrowser=True, server_name="127.0.0.1")


if __name__ == "__main__":
    main()
