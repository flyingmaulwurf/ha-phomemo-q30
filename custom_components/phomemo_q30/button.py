"""The "Print label" button: prints the text of the "Label text" entity."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PhomemoConfigEntry
from .const import DOMAIN
from .printer import PhomemoPrinter


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PhomemoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([PrintLabelButton(entry.runtime_data)])


class PrintLabelButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "print_label"
    _attr_icon = "mdi:printer"

    def __init__(self, printer: PhomemoPrinter) -> None:
        self._printer = printer
        self._attr_unique_id = f"{printer.address}_print_label"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, printer.address)})

    async def async_press(self) -> None:
        text = self._printer.text.strip()
        if not text:
            raise ServiceValidationError("Type the label text into 'Label text' first")
        await self._printer.async_print_text(text)
