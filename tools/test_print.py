#!/usr/bin/env python3
"""Standalone test: print a label on the Phomemo Q30 straight from this computer.

    python tools/test_print.py "Hello"                    # scan, pick the Q30 automatically
    python tools/test_print.py "Hello" AA:BB:CC:DD:EE:FF  # use a given BLE address

Needs: pip install bleak pillow   (use a venv, see README)
"""
import asyncio
import importlib.util
import pathlib
import sys

from bleak import BleakClient, BleakScanner

CHAR = "0000ff02-0000-1000-8000-00805f9b34fb"
LABEL_LENGTH_MM = 28  # along the feed direction
LABEL_WIDTH_MM = 12  # across the print head

spec = importlib.util.spec_from_file_location(
    "label", pathlib.Path(__file__).resolve().parent.parent / "custom_components/phomemo_q30/label.py"
)
label = importlib.util.module_from_spec(spec)
sys.modules["label"] = label
spec.loader.exec_module(label)


async def find_printer(address: str | None):
    """Scan over BLE and return a BLEDevice (never connect by bare address)."""
    print("Scanning BLE for 12 s ...")
    found = await BleakScanner.discover(timeout=12, return_adv=True)
    for addr, (dev, adv) in sorted(found.items()):
        print(f"   {addr}  rssi={adv.rssi:>4}  name={dev.name!r}  services={adv.service_uuids}")
    if address:
        match = [d for a, (d, _) in found.items() if a.upper() == address.upper()]
    else:
        match = [
            d for _, (d, adv) in found.items()
            if (d.name and any(k in d.name.upper() for k in ("Q30", "D30", "PHOMEMO")))
            or "0000ff00-0000-1000-8000-00805f9b34fb" in adv.service_uuids
        ]
    if not match:
        sys.exit(
            "\nThe printer was NOT found over BLE. Switch it on, make sure nothing else "
            "is connected to it, and compare the list above with its real name/address."
        )
    return match[0]


async def main(text: str, address: str | None) -> None:
    device = await find_printer(address)
    print("Using", device.address, device.name)

    geo = label.LabelGeometry.from_mm(LABEL_LENGTH_MM, LABEL_WIDTH_MM, 1, 1)
    job = label.encode(label.render_text(text, geo))

    async with BleakClient(device, timeout=20) as client:
        print("Connected")
        for part in job.parts():
            for i in range(0, len(part), 20):
                await client.write_gatt_char(CHAR, part[i : i + 20], response=False)
                await asyncio.sleep(0.01)
            await asyncio.sleep(0.1)
        print("Sent, waiting for the printer ...")
        await asyncio.sleep(4)
    print("Done")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "Test", sys.argv[2] if len(sys.argv) > 2 else None))
