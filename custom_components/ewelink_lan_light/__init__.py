"""eWeLink LAN Light: local-only control of eWeLink BL602 bulbs, no cloud."""
from __future__ import annotations

import probatio

from homeassistant.helpers import service

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_DEVICEID, CONF_DEVICEKEY, DOMAIN
from .device import EweLinkLanDevice

PLATFORMS = [Platform.LIGHT]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the colour-only action independently of loaded bulb entries."""
    channel = probatio.All(probatio.Coerce(int), probatio.Range(min=0, max=255))
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "prepare_color",
        entity_domain="light",
        schema={
            probatio.Exclusive("rgb_color", "colour_mode"): probatio.All(
                probatio.ExactSequence([channel, channel, channel]), list
            ),
            probatio.Exclusive("color_temp_kelvin", "colour_mode"): probatio.All(
                probatio.Coerce(int), probatio.Range(min=2000, max=6500)
            ),
            probatio.Required("brightness_pct"): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1, max=100)
            ),
        },
        func="async_prepare_color",
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    device = EweLinkLanDevice(
        hass, entry.data[CONF_HOST], entry.data[CONF_DEVICEID], entry.data[CONF_DEVICEKEY]
    )
    await device.async_start()
    entry.runtime_data = device
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_stop()
    return unloaded
