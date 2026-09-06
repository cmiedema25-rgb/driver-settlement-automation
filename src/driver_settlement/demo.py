from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


def _font(size: int = 34):
    for candidate in ["DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _write_scan(path: Path, title: str, lines: Iterable[str]) -> None:
    image = Image.new("RGB", (1700, 2200), "white")
    draw = ImageDraw.Draw(image)
    title_font = _font(46)
    body_font = _font(34)
    draw.text((100, 90), title, fill="black", font=title_font)
    y = 200
    for line in lines:
        draw.text((100, y), line, fill="black", font=body_font)
        y += 64
    image.save(path, quality=95)


def generate_demo_dataset(output_dir: str | Path) -> dict[str, object]:
    root = Path(output_dir)
    docs_dir = root / "paperwork"
    docs_dir.mkdir(parents=True, exist_ok=True)

    board = root / "loads.csv"
    rows = [
        {
            "load_id": "LW-88214",
            "driver": "Maria Santos",
            "truck": "2147",
            "customer": "Cascadia Foods",
            "origin": "Ontario, CA",
            "destination": "Phoenix, AZ",
            "expected_reimbursement": "329.22",
        },
        {
            "load_id": "LW-88291",
            "driver": "David Jones",
            "truck": "2189",
            "customer": "Northwind Retail",
            "origin": "Los Angeles, CA",
            "destination": "Las Vegas, NV",
            "expected_reimbursement": "344.72",
        },
        {
            "load_id": "LW-88302",
            "driver": "Elena Garcia",
            "truck": "2206",
            "customer": "Contoso Distribution",
            "origin": "San Bernardino, CA",
            "destination": "Tucson, AZ",
            "expected_reimbursement": "0.00",
        },
    ]
    with board.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    docs: list[Path] = []

    def scan(filename: str, title: str, lines: list[str]) -> None:
        path = docs_dir / filename
        _write_scan(path, title, lines)
        docs.append(path)

    scan(
        "LW-88214_bol.png",
        "BILL OF LADING / PROOF OF DELIVERY",
        [
            "LOAD NUMBER: LW-88214",
            "DRIVER: Maria Santos",
            "TRUCK: 2147",
            "SHIPPER: West Coast Produce",
            "CONSIGNEE: Cascadia Foods",
            "ORIGIN: Ontario, CA",
            "DESTINATION: Phoenix, AZ",
            "DELIVERED: 2026-09-05",
            "PIECES: 24 PALLETS",
            "RECEIVER SIGNATURE: J. Reed",
        ],
    )
    scan(
        "LW-88214_driver_log.png",
        "DRIVER LOG / HOURS OF SERVICE",
        [
            "LOAD NUMBER: LW-88214",
            "DRIVER: Maria Santos",
            "DATE: 2026-09-05",
            "ON DUTY: 2.25 HOURS",
            "DRIVING: 7.50 HOURS",
            "OFF DUTY: 4.25 HOURS",
            "DUTY STATUS: COMPLETE",
        ],
    )
    scan(
        "LW-88214_fuel.png",
        "FUEL RECEIPT",
        [
            "PILOT TRAVEL CENTER #328",
            "LOAD NUMBER: LW-88214",
            "DRIVER: Maria Santos",
            "DATE: 2026-09-05",
            "DIESEL: 82.4 GALLONS",
            "PRICE PER GALLON: 3.819",
            "TOTAL: $314.72",
        ],
    )
    scan(
        "LW-88214_scale.png",
        "CAT SCALE TICKET",
        [
            "CAT SCALE - QUARTZSITE AZ",
            "LOAD NUMBER: LW-88214",
            "DRIVER: Maria Santos",
            "DATE: 2026-09-05",
            "STEER AXLE: 11,880 LB",
            "DRIVE AXLE: 33,620 LB",
            "TRAILER AXLE: 33,140 LB",
            "GROSS WEIGHT: 78,640 LB",
            "TOTAL: $14.50",
        ],
    )

    scan(
        "LW-88291_bol.png",
        "BILL OF LADING / PROOF OF DELIVERY",
        [
            "LOAD NUMBER: LW-88291",
            "DRIVER: David Jones",
            "TRUCK: 2189",
            "SHIPPER: Pacific Dry Goods",
            "CONSIGNEE: Northwind Retail",
            "DELIVERED: 2026-09-05",
            "RECEIVER SIGNATURE: K. Thompson",
        ],
    )
    scan(
        "LW-88291_driver_log.png",
        "DRIVER LOG / HOURS OF SERVICE",
        [
            "LOAD NUMBER: LW-88291",
            "DRIVER: David Jones",
            "DATE: 2026-09-05",
            "DRIVING: 5.20 HOURS",
            "DUTY STATUS: COMPLETE",
        ],
    )
    scan(
        "LW-88291_fuel.png",
        "FUEL RECEIPT",
        [
            "LOVE'S TRAVEL STOP #291",
            "LOAD NUMBER: LW-88291",
            "DRIVER: David Jones",
            "DATE: 2026-09-05",
            "DIESEL: 80.0 GALLONS",
            "TOTAL: $314.72",
        ],
    )

    scan(
        "LW-88302_bol.png",
        "BILL OF LADING / PROOF OF DELIVERY",
        [
            "LOAD NUMBER: LW-88302",
            "DRIVER: Elena Garcia",
            "TRUCK: 2206",
            "SHIPPER: Inland Warehouse",
            "CONSIGNEE: Contoso Distribution",
            "DELIVERED: 2026-09-05",
            "RECEIVER SIGNATURE: MISSING",
        ],
    )
    scan(
        "LW-88302_driver_log.png",
        "DRIVER LOG / HOURS OF SERVICE",
        [
            "LOAD NUMBER: LW-88302",
            "DRIVER: Elena Garcia",
            "DATE: 2026-09-05",
            "DRIVING: 6.75 HOURS",
            "DUTY STATUS: COMPLETE",
        ],
    )

    return {"load_board": board, "documents": docs, "root": root}
