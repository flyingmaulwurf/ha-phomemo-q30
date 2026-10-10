"""Config flow for the Phomemo Q30 integration."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_LABEL_HEIGHT_MM,
    CONF_LABEL_WIDTH_MM,
    CONF_MARGIN_X_MM,
    CONF_MARGIN_Y_MM,
    DEFAULT_LABEL_HEIGHT_MM,
    DEFAULT_LABEL_WIDTH_MM,
    DEFAULT_MARGIN_X_MM,
    DEFAULT_MARGIN_Y_MM,
    DOMAIN,
    SERVICE_UUID,
)


def _mm(minimum: float, maximum: float) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=0.5,
            unit_of_measurement="mm",
            mode=NumberSelectorMode.BOX,
        )
    )


def _label_schema(defaults: dict[str, Any]) -> dict[vol.Marker, Any]:
    return {
        vol.Required(CONF_LABEL_WIDTH_MM, default=defaults[CONF_LABEL_WIDTH_MM]): _mm(5, 200),
        vol.Required(CONF_LABEL_HEIGHT_MM, default=defaults[CONF_LABEL_HEIGHT_MM]): _mm(5, 200),
        vol.Required(CONF_MARGIN_X_MM, default=defaults[CONF_MARGIN_X_MM]): _mm(0, 50),
        vol.Required(CONF_MARGIN_Y_MM, default=defaults[CONF_MARGIN_Y_MM]): _mm(0, 50),
    }


_DEFAULTS = {
    CONF_LABEL_WIDTH_MM: DEFAULT_LABEL_WIDTH_MM,
    CONF_LABEL_HEIGHT_MM: DEFAULT_LABEL_HEIGHT_MM,
    CONF_MARGIN_X_MM: DEFAULT_MARGIN_X_MM,
    CONF_MARGIN_Y_MM: DEFAULT_MARGIN_Y_MM,
}


def _normalize_address(value: str) -> str | None:
    """'aa:bb:cc:dd:ee:ff', 'AA-BB-CC-DD-EE-FF' or 'aabbccddeeff' -> 'AA:BB:CC:DD:EE:FF'."""
    hexdigits = re.sub(r"[^0-9A-Fa-f]", "", value or "")
    if len(hexdigits) != 12 or re.search(r"[^0-9A-Fa-f:\-\s]", value):
        return None
    hexdigits = hexdigits.upper()
    return ":".join(hexdigits[i : i + 2] for i in range(0, 12, 2))


def _is_phomemo(info: BluetoothServiceInfoBleak) -> bool:
    name = (info.name or "").upper()
    return (
        SERVICE_UUID in info.service_uuids
        or "PHOMEMO" in name
        or "Q30" in name
        or "D30" in name
    )


class PhomemoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery: BluetoothServiceInfoBleak | None = None
        self._devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery = discovery_info
        self.context["title_placeholders"] = {
            "name": discovery_info.name or discovery_info.address
        }
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._discovery is not None
        name = self._discovery.name or self._discovery.address
        if user_input is not None:
            return self.async_create_entry(
                title=name,
                data={CONF_ADDRESS: self._discovery.address, CONF_NAME: name},
                options=user_input,
            )
        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(_label_schema(_DEFAULTS)),
            description_placeholders={"name": name},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            address = _normalize_address(user_input[CONF_ADDRESS])
            if address is None:
                errors[CONF_ADDRESS] = "invalid_address"
            else:
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()
                info = self._devices.get(address)
                name = (info.name if info else None) or "Q30"
                options = {k: v for k, v in user_input.items() if k != CONF_ADDRESS}
                return self.async_create_entry(
                    title=name,
                    data={CONF_ADDRESS: address, CONF_NAME: name},
                    options=options,
                )

        configured = self._async_current_ids()
        all_devices = {
            info.address: info
            for info in async_discovered_service_info(self.hass, False)
            if info.address not in configured
        }
        likely = {a: i for a, i in all_devices.items() if _is_phomemo(i)}
        # Only printers when any is found, otherwise every nearby device; strongest first.
        self._devices = likely or all_devices
        ordered = sorted(self._devices.values(), key=lambda i: i.rssi, reverse=True)
        options = [
            SelectOptionDict(
                value=info.address,
                label=f"{info.name or 'unknown'} ({info.address}, {info.rssi} dBm)",
            )
            for info in ordered
        ]
        schema = {
            vol.Required(CONF_ADDRESS): SelectSelector(
                SelectSelectorConfig(
                    options=options,
                    custom_value=True,  # lets you type or paste a Bluetooth address
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            **_label_schema(_DEFAULTS),
        }
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(schema), errors=errors
        )

    @staticmethod
    def async_get_options_flow(config_entry) -> PhomemoOptionsFlow:
        return PhomemoOptionsFlow()


class PhomemoOptionsFlow(OptionsFlow):
    """Change label size / margins later."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = {**_DEFAULTS, **self.config_entry.options}
        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(_label_schema(current))
        )
