#!/usr/bin/env python3
"""Diagnostic: dump the Q30's GATT table, listen to notifications, try print variants.

    python tools/ble_probe.py "Hello" A      # variant A = what the web app sends (default)
    python tools/ble_probe.py "Hello" B      # variant B = Phomemo M110-family sequence
    python tools/ble_probe.py "Hello" C      # variant C = Phomemo M02-family sequence
    python tools/ble_probe.py "Hello" D      # variant D = like C, image split in 255-line blocks
    python tools/ble_probe.py "Hello" A 128  # optional 3rd arg: chunk size in bytes (default 20)
    python tools/ble_probe.py "Hello" E      # variant E = M110 start/end + 255-line blocks
    python tools/ble_probe.py "Hello" F      # variant F = like E, slow speed, M02 footer
    python tools/ble_probe.py "x" D black    # add "black": print a solid black block
    python tools/ble_probe.py "x" E black fast  # add "fast": 5 ms between BLE writes

Run from the repository root: python tools/ble_probe.py ...
"""
import asyncio
import sys

from bleak import BleakClient

from test_print import CHAR, find_printer, label

BLACK = "black" in sys.argv  # replace the image with a solid black block
DELAY = 0.005 if "fast" in sys.argv else 0.02  # seconds between BLE writes
args = [a for a in sys.argv[1:] if a not in ("black", "fast")]
TEXT = args[0] if len(args) > 0 else "Test"
VARIANT = (args[1] if len(args) > 1 else "A").upper()
CHUNK = int(args[2]) if len(args) > 2 else 20


def blocks(job) -> list[bytes]:
    """GS v 0 blocks of at most 255 lines each."""
    bpl = job.header[6] + job.header[7] * 256
    lines = len(job.data) // bpl
    out = []
    for start in range(0, lines, 255):
        n = min(255, lines - start)
        out.append(bytes([0x1D, 0x76, 0x30, 0x00, bpl % 256, bpl // 256, n % 256, n // 256]))
        out.append(job.data[start * bpl : (start + n) * bpl])
    return out


def build(job) -> list[bytes]:
    raster = job.header[2:]  # GS v 0 ... without ESC @
    if VARIANT == "A":  # web app
        return [job.header, job.data, job.footer]
    if VARIANT == "B":  # M110 family
        pre = bytes.fromhex("1b4e0d05" "1b4e040f" "1f110a")
        post = bytes.fromhex("1ff00500" "1ff00300")
        return [pre, raster, job.data, post]
    if VARIANT == "C":  # M02 family
        pre = bytes.fromhex("1b40" "1b6101" "1f110204")
        post = bytes.fromhex("1b6402" "1b6402" "1f1108" "1f110e" "1f1107" "1f1109")
        return [pre, raster, job.data, post]
    if VARIANT == "D":  # M02 family, image split into blocks of <= 255 lines
        pre = bytes.fromhex("1b40" "1b6101" "1f110204")
        post = bytes.fromhex("1b6402" "1b6402" "1f1108" "1f110e" "1f1107" "1f1109")
        bpl = job.header[6] + job.header[7] * 256
        lines = len(job.data) // bpl
        parts = [pre]
        for start in range(0, lines, 255):
            n = min(255, lines - start)
            parts.append(bytes([0x1D, 0x76, 0x30, 0x00, bpl % 256, bpl // 256, n % 256, n // 256]))
            parts.append(job.data[start * bpl : (start + n) * bpl])
        parts.append(post)
        return parts
    if VARIANT == "E":  # M110 family start/end + 255-line blocks
        pre = bytes.fromhex("1b4e0d05" "1b4e040f" "1f110a")
        post = bytes.fromhex("1ff00500" "1ff00300")
        return [pre, *blocks(job), post]
    if VARIANT == "F":  # E but with ESC @ first, slow speed, and the M02 footer
        pre = bytes.fromhex("1b40" "1b4e0d01" "1b4e040f" "1f110a")
        post = bytes.fromhex("1b6402" "1b6402" "1f1108" "1f110e" "1f1107" "1f1109")
        return [pre, *blocks(job), post]
    sys.exit("Variant must be A, B, C, D, E or F")


async def main() -> None:
    device = await find_printer(None)
    print("Using", device.address, device.name)
    geo = label.LabelGeometry.from_mm(28, 12, 1, 1)
    job = label.encode(label.render_text(TEXT, geo))
    if BLACK:
        job = label.PrintJob(job.header, b"\xff" * len(job.data), job.footer)
    parts = build(job)

    async with BleakClient(device, timeout=20) as client:
        print("\n=== GATT table ===")
        for svc in client.services:
            print(f"service {svc.uuid}")
            for ch in svc.characteristics:
                print(f"    char {ch.uuid}  props={ch.properties}")

        def on_notify(sender, data: bytearray) -> None:
            print(f"  <- notify {sender}: {bytes(data).hex()}")

        for svc in client.services:
            for ch in svc.characteristics:
                if "notify" in ch.properties or "indicate" in ch.properties:
                    try:
                        await client.start_notify(ch, on_notify)
                        print(f"subscribed to {ch.uuid}")
                    except Exception as err:  # noqa: BLE001
                        print(f"cannot subscribe {ch.uuid}: {err}")

        print(f"\n=== sending variant {VARIANT}, chunk {CHUNK} ===")
        for part in parts:
            for i in range(0, len(part), CHUNK):
                await client.write_gatt_char(CHAR, part[i : i + CHUNK], response=False)
                await asyncio.sleep(DELAY)
            await asyncio.sleep(0.1)
        print("sent, waiting 5 s for the printer / notifications ...")
        await asyncio.sleep(5)
    print("done")


asyncio.run(main())
