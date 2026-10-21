"""Light entity: on/off, brightness, color temperature and RGB over the LAN.

Commands:  /zeroconf/switch (on/off) and /zeroconf/dimmable (everything else).
State:     decoded from the bulb's own mDNS broadcasts when they reach Home
           Assistant (so changes made from the phone app show up); until the
           first broadcast arrives the entity reports assumed state.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DEVICEID, DOMAIN
from .device import EweLinkLanDevice

MIN_KELVIN = 2000  # ct 0, warm end
MAX_KELVIN = 6500  # ct 100, cold end


def ha_to_br(brightness: int) -> int:
    """Home Assistant 1-255 -> bulb 1-100."""
    return max(1, min(100, round(brightness / 255 * 100)))


def br_to_ha(br: int) -> int:
    return max(1, min(255, round(br / 100 * 255)))


def kelvin_to_ct(kelvin: int) -> int:
    ct = round((kelvin - MIN_KELVIN) / (MAX_KELVIN - MIN_KELVIN) * 100)
    return max(0, min(100, ct))


def ct_to_kelvin(ct: int) -> int:
    return round(MIN_KELVIN + max(0, min(100, ct)) / 100 * (MAX_KELVIN - MIN_KELVIN))


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([EweLinkLanLight(entry)])


class EweLinkLanLight(LightEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_supported_color_modes = {ColorMode.COLOR_TEMP, ColorMode.RGB}
    _attr_min_color_temp_kelvin = MIN_KELVIN
    _attr_max_color_temp_kelvin = MAX_KELVIN

    def __init__(self, entry: ConfigEntry) -> None:
        self._device: EweLinkLanDevice = entry.runtime_data
        self._attr_unique_id = entry.data[CONF_DEVICEID]
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.data[CONF_DEVICEID])},
            "name": entry.title,
            "manufacturer": "eWeLink",
            "model": "BL602 CK0205PWM light",
        }
        self._attr_is_on = False
        self._attr_brightness = 255
        self._attr_color_mode = ColorMode.COLOR_TEMP
        self._attr_color_temp_kelvin = 4000
        self._attr_rgb_color = (255, 255, 255)

    @property
    def assumed_state(self) -> bool:
        return not self._device.push_state_seen

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._device.add_listener(self._handle_state))

    @callback
    def _handle_state(self, state: dict) -> None:
        self._attr_is_on = state.get("switch") == "on"
        # While off the bulb always reports ltype "white"; keep the last mode.
        if self._attr_is_on:
            ltype = state.get("ltype")
            if ltype == "color" and isinstance(state.get("color"), dict):
                c = state["color"]
                self._attr_color_mode = ColorMode.RGB
                self._attr_rgb_color = (c.get("r", 0), c.get("g", 0), c.get("b", 0))
                self._attr_brightness = br_to_ha(c.get("br", 100))
            elif ltype == "white" and isinstance(state.get("white"), dict):
                w = state["white"]
                self._attr_color_mode = ColorMode.COLOR_TEMP
                self._attr_color_temp_kelvin = ct_to_kelvin(w.get("ct", 50))
                self._attr_brightness = br_to_ha(w.get("br", 100))
        self.async_write_ha_state()

    def _dimmable_payload(self) -> dict:
        br = ha_to_br(self._attr_brightness)
        if self._attr_color_mode == ColorMode.RGB:
            r, g, b = self._attr_rgb_color
            return {"ltype": "color", "color": {"br": br, "r": r, "g": g, "b": b}}
        return {
            "ltype": "white",
            "white": {"br": br, "ct": kelvin_to_ct(self._attr_color_temp_kelvin)},
        }

    async def async_prepare_color(
        self,
        brightness_pct: int,
        rgb_color: list[int] | None = None,
        color_temp_kelvin: int | None = None,
    ) -> None:
        """Prepare RGB or white temperature without issuing a power command."""
        if (rgb_color is None) == (color_temp_kelvin is None):
            raise HomeAssistantError("Specify exactly one of rgb_color or color_temp_kelvin")
        if rgb_color is not None:
            r, g, b = rgb_color
            payload = {"ltype": "color", "color": {"br": brightness_pct, "r": r, "g": g, "b": b}}
        else:
            payload = {"ltype": "white", "white": {"br": brightness_pct, "ct": kelvin_to_ct(color_temp_kelvin)}}
        await self._device.async_send("dimmable", payload)
        self._attr_brightness = br_to_ha(brightness_pct)
        if rgb_color is not None:
            self._attr_rgb_color = tuple(rgb_color)
            self._attr_color_mode = ColorMode.RGB
        else:
            self._attr_color_temp_kelvin = color_temp_kelvin
            self._attr_color_mode = ColorMode.COLOR_TEMP
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        if ATTR_BRIGHTNESS in kwargs:
            self._attr_brightness = kwargs[ATTR_BRIGHTNESS]
        if ATTR_RGB_COLOR in kwargs:
            self._attr_rgb_color = tuple(kwargs[ATTR_RGB_COLOR])
            self._attr_color_mode = ColorMode.RGB
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            self._attr_color_temp_kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]
            self._attr_color_mode = ColorMode.COLOR_TEMP

        # Some lights only accept dimmable commands once they are on.
        if not self._attr_is_on:
            await self._device.async_send("switch", {"switch": "on"})
        if any(k in kwargs for k in (ATTR_BRIGHTNESS, ATTR_RGB_COLOR, ATTR_COLOR_TEMP_KELVIN)):
            await self._device.async_send("dimmable", self._dimmable_payload())

        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.async_send("switch", {"switch": "off"})
        self._attr_is_on = False
        self.async_write_ha_state()
