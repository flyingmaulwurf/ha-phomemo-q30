"""The "Label text" entity: type the text here, then press "Print label"."""

from __future__ import annotations

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import PhomemoConfigEntry
from .const import DOMAIN
from .printer import PhomemoPrinter


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PhomemoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([LabelTextEntity(entry.runtime_data)])


class LabelTextEntity(TextEntity, RestoreEntity):
    """Holds the text of the next label (remembered across restarts)."""

    _attr_has_entity_name = True
    _attr_translation_key = "label_text"
    _attr_icon = "mdi:label-outline"
    _attr_mode = TextMode.TEXT
    _attr_native_min = 0
    _attr_native_max = 255

    def __init__(self, printer: PhomemoPrinter) -> None:
        self._printer = printer
        self._attr_unique_id = f"{printer.address}_label_text"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, printer.address)})

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None and last.state not in (
            "unknown",
            "unavailable",
        ):
            self._printer.text = last.state

    @property
    def native_value(self) -> str:
        return self._printer.text

    async def async_set_value(self, value: str) -> None:
        self._printer.text = value
        self.async_write_ha_state()
