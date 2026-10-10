"""Bluetooth LE transport for the Phomemo printer."""

from __future__ import annotations

import asyncio
import logging

from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import WRITE_CHAR_UUID
from .label import LabelGeometry, PrintJob, encode, render_text

_LOGGER = logging.getLogger(__name__)

CHUNK = 20  # bytes per BLE write (the tested, safe size for MTU 23)
CHUNK_DELAY = 0.005  # s between chunks (the printer acks every write; 5 ms was tested)
PART_DELAY = 0.05  # s between command blocks
SETTLE_DELAY = 2.0  # s to let the printer finish before disconnecting
BETWEEN_COPIES_DELAY = 2.0


class PhomemoPrinter:
    """One Phomemo printer, addressed by its Bluetooth MAC."""

    def __init__(
        self, hass: HomeAssistant, address: str, name: str, geometry: LabelGeometry
    ) -> None:
        self.hass = hass
        self.address = address
        self.name = name
        self.geometry = geometry
        self.text = ""  # text shown by the "Label text" entity, printed by the button
        self._lock = asyncio.Lock()

    async def async_print_text(
        self,
        text: str,
        *,
        geometry: LabelGeometry | None = None,
        font_size: int | None = None,
        font_path: str | None = None,
        copies: int = 1,
    ) -> None:
        """Render `text` (\\n = line break) onto a label and print it."""
        text = text.replace("\\n", "\n")
        geo = geometry or self.geometry

        def build() -> PrintJob:
            return encode(
                render_text(text, geo, font_size=font_size, font_path=font_path)
            )

        job = await self.hass.async_add_executor_job(build)
        await self.async_print(job, copies)

    async def async_print(self, job: PrintJob, copies: int = 1) -> None:
        """Connect, send the job `copies` times, disconnect."""
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise HomeAssistantError(
                f"Printer {self.name} ({self.address}) is not in Bluetooth range "
                "(is it switched on? is a Bluetooth adapter/proxy nearby?)"
            )

        async with self._lock:  # one print at a time per printer
            client = None
            try:
                client = await establish_connection(
                    BleakClientWithServiceCache, ble_device, self.name, max_attempts=3
                )
                _LOGGER.debug(
                    "Connected to %s, sending %s bytes x%s",
                    self.address, len(job.data), copies,
                )
                parts = job.parts()
                for copy in range(copies):
                    if copy:
                        await asyncio.sleep(BETWEEN_COPIES_DELAY)
                    for part in parts:
                        for i in range(0, len(part), CHUNK):
                            await client.write_gatt_char(
                                WRITE_CHAR_UUID, part[i : i + CHUNK], response=False
                            )
                            await asyncio.sleep(CHUNK_DELAY)
                        await asyncio.sleep(PART_DELAY)
                await asyncio.sleep(SETTLE_DELAY)
                _LOGGER.debug("Print job sent to %s", self.address)
            except (BleakError, TimeoutError, OSError) as err:
                raise HomeAssistantError(
                    f"Printing on {self.name} failed: {err}"
                ) from err
            finally:
                if client is not None:
                    try:
                        await client.disconnect()
                    except (BleakError, TimeoutError, OSError):
                        _LOGGER.debug("Error while disconnecting", exc_info=True)
