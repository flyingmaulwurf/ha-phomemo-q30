"""Phomemo Q30 (and D30) label printer integration."""

from __future__ import annotations

from dataclasses import replace
from functools import partial
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_COPIES,
    ATTR_DEVICE_ID,
    ATTR_DITHER,
    ATTR_FONT,
    ATTR_FONT_SIZE,
    ATTR_LENGTH_MM,
    ATTR_PATH,
    ATTR_ROTATE,
    ATTR_TEXT,
    ATTR_WIDTH_MM,
    CONF_LABEL_HEIGHT_MM,
    CONF_LABEL_WIDTH_MM,
    CONF_MARGIN_X_MM,
    CONF_MARGIN_Y_MM,
    DEFAULT_LABEL_HEIGHT_MM,
    DEFAULT_LABEL_WIDTH_MM,
    DEFAULT_MARGIN_X_MM,
    DEFAULT_MARGIN_Y_MM,
    DOMAIN,
    SERVICE_PRINT_IMAGE,
    SERVICE_PRINT_TEXT,
)
from .label import DOTS_PER_MM, LabelGeometry, encode, render_image
from .printer import PhomemoPrinter

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.TEXT, Platform.BUTTON]

type PhomemoConfigEntry = ConfigEntry[PhomemoPrinter]

_COMMON = {
    vol.Optional(ATTR_DEVICE_ID): cv.string,
    vol.Optional(ATTR_COPIES, default=1): vol.All(vol.Coerce(int), vol.Range(1, 20)),
    # one-off label size, overrides the size set in the integration options
    vol.Optional(ATTR_LENGTH_MM): vol.All(vol.Coerce(float), vol.Range(5, 200)),
    vol.Optional(ATTR_WIDTH_MM): vol.All(vol.Coerce(float), vol.Range(5, 200)),
}
PRINT_TEXT_SCHEMA = vol.Schema(
    {
        **_COMMON,
        vol.Required(ATTR_TEXT): cv.string,
        vol.Optional(ATTR_FONT_SIZE, default=0): vol.All(
            vol.Coerce(int), vol.Range(0, 250)
        ),
        vol.Optional(ATTR_FONT): cv.string,
    }
)
PRINT_IMAGE_SCHEMA = vol.Schema(
    {
        **_COMMON,
        vol.Required(ATTR_PATH): cv.string,
        vol.Optional(ATTR_ROTATE, default=0): vol.All(
            vol.Coerce(int), vol.In([0, 90, 180, 270])
        ),
        vol.Optional(ATTR_DITHER, default=True): cv.boolean,
    }
)


def _geometry(entry: ConfigEntry) -> LabelGeometry:
    o = entry.options
    return LabelGeometry.from_mm(
        o.get(CONF_LABEL_WIDTH_MM, DEFAULT_LABEL_WIDTH_MM),
        o.get(CONF_LABEL_HEIGHT_MM, DEFAULT_LABEL_HEIGHT_MM),
        o.get(CONF_MARGIN_X_MM, DEFAULT_MARGIN_X_MM),
        o.get(CONF_MARGIN_Y_MM, DEFAULT_MARGIN_Y_MM),
    )


def _call_geometry(printer: PhomemoPrinter, data: dict[str, Any]) -> LabelGeometry:
    """Printer's label geometry, with optional per-call length/width in mm."""
    geo = printer.geometry
    if (length := data.get(ATTR_LENGTH_MM)) is not None:
        geo = replace(geo, width=round(length * DOTS_PER_MM))
    if (width := data.get(ATTR_WIDTH_MM)) is not None:
        geo = replace(geo, height=round(width * DOTS_PER_MM))
    return geo


def _resolve_printer(hass: HomeAssistant, device_id: str | None) -> PhomemoPrinter:
    entries = [
        e
        for e in hass.config_entries.async_entries(DOMAIN)
        if getattr(e, "runtime_data", None) is not None
    ]
    if device_id:
        device = dr.async_get(hass).async_get(device_id)
        if device is None:
            raise ServiceValidationError(f"Unknown device {device_id}")
        for entry in entries:
            if entry.entry_id in device.config_entries:
                return entry.runtime_data
        raise ServiceValidationError("The selected device is not a Phomemo printer")
    if len(entries) == 1:
        return entries[0].runtime_data
    if not entries:
        raise ServiceValidationError("No Phomemo printer is set up")
    raise ServiceValidationError("Several printers are set up, choose a device_id")


async def _print_text(hass: HomeAssistant, call: ServiceCall) -> None:
    printer = _resolve_printer(hass, call.data.get(ATTR_DEVICE_ID))
    await printer.async_print_text(
        call.data[ATTR_TEXT],
        geometry=_call_geometry(printer, call.data),
        font_size=call.data[ATTR_FONT_SIZE] or None,
        font_path=call.data.get(ATTR_FONT),
        copies=call.data[ATTR_COPIES],
    )


async def _print_image(hass: HomeAssistant, call: ServiceCall) -> None:
    printer = _resolve_printer(hass, call.data.get(ATTR_DEVICE_ID))
    path = call.data[ATTR_PATH]
    geometry = _call_geometry(printer, call.data)
    if not hass.config.is_allowed_path(path):
        raise ServiceValidationError(
            f"{path} is not allowed; add its folder to allowlist_external_dirs"
        )

    def build():
        try:
            img = render_image(path, geometry, rotate=call.data[ATTR_ROTATE])
        except OSError as err:
            raise HomeAssistantError(f"Cannot read image {path}: {err}") from err
        return encode(img, dither=call.data[ATTR_DITHER])

    job = await hass.async_add_executor_job(build)
    await printer.async_print(job, call.data[ATTR_COPIES])


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.services.async_register(
        DOMAIN, SERVICE_PRINT_TEXT, partial(_print_text, hass), schema=PRINT_TEXT_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PRINT_IMAGE,
        partial(_print_image, hass),
        schema=PRINT_IMAGE_SCHEMA,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PhomemoConfigEntry) -> bool:
    address = entry.data[CONF_ADDRESS]
    name = entry.data.get(CONF_NAME, address)
    entry.runtime_data = PhomemoPrinter(hass, address, name, _geometry(entry))

    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, address)},
        connections={(dr.CONNECTION_BLUETOOTH, address)},
        manufacturer="Phomemo",
        model="Q30",
        name=name,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    return True


async def _options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: PhomemoConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
