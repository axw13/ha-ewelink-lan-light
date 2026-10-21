"""One bulb: serialised LAN commands plus push state from its mDNS broadcasts."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .protocol import parse_txt_state, send_command

_LOGGER = logging.getLogger(__name__)

SERVICE_TYPE = "_ewelink._tcp.local."
RETRIES = 4
RETRY_DELAY = 0.25


class EweLinkLanDevice:
    def __init__(self, hass: HomeAssistant, host: str, deviceid: str, devicekey: str) -> None:
        self.hass = hass
        self.host = host
        self.deviceid = deviceid
        self._devicekey = devicekey
        # The bulb's web server handles one request at a time.
        self._lock = asyncio.Lock()
        self._listeners: list[Callable[[dict], None]] = []
        self._browser = None
        self._last_seq: str | None = None
        self.state: dict | None = None
        self.push_state_seen = False

    # ---- commands -------------------------------------------------------
    async def async_send(self, command: str, data: dict) -> None:
        async with self._lock:
            last_err: Exception | None = None
            for attempt in range(RETRIES):
                try:
                    resp = await self.hass.async_add_executor_job(
                        send_command, self.host, self.deviceid, self._devicekey, command, data
                    )
                except OSError as err:  # includes URLError, resets, timeouts
                    last_err = err
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                if resp.get("error") != 0:
                    raise HomeAssistantError(
                        f"{self.host} rejected {command} {data}: error {resp.get('error')}"
                    )
                return
            raise HomeAssistantError(
                f"No valid reply from {self.host} ({last_err}). Check the IP and device key."
            )

    # ---- push state -----------------------------------------------------
    @callback
    def add_listener(self, cb: Callable[[dict], None]) -> Callable[[], None]:
        self._listeners.append(cb)
        if self.state is not None:
            cb(self.state)
        return lambda: self._listeners.remove(cb)

    @callback
    def handle_txt(self, properties: dict) -> None:
        """Process an mDNS TXT record set from this bulb."""
        seq = properties.get("seq") or properties.get(b"seq")
        seq = seq.decode() if isinstance(seq, bytes) else seq
        if seq is not None and seq == self._last_seq:
            return  # the bulb repeats each announcement several times
        state = parse_txt_state(self._devicekey, properties)
        if state is None:
            _LOGGER.debug("%s: could not decode mDNS state", self.deviceid)
            return
        self._last_seq = seq
        self.state = state
        self.push_state_seen = True
        for cb in list(self._listeners):
            cb(state)

    async def async_start(self) -> None:
        from homeassistant.components import zeroconf as ha_zeroconf
        from zeroconf import ServiceStateChange
        from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo

        zc = await ha_zeroconf.async_get_async_instance(self.hass)
        wanted = f"eWeLink_{self.deviceid}.{SERVICE_TYPE}"

        async def update(name: str) -> None:
            info = AsyncServiceInfo(SERVICE_TYPE, name)
            if not await info.async_request(zc.zeroconf, 3000) or not info.properties:
                return
            if info.properties.get(b"id", b"").decode() != self.deviceid:
                return
            addrs = info.parsed_addresses()
            if addrs and addrs[0] != self.host:
                _LOGGER.info("%s moved %s -> %s", self.deviceid, self.host, addrs[0])
                self.host = addrs[0]
            self.handle_txt(info.properties)

        def on_change(zeroconf, service_type, name, state_change) -> None:
            if name == wanted and state_change in (
                ServiceStateChange.Added,
                ServiceStateChange.Updated,
            ):
                self.hass.async_create_task(update(name))

        self._browser = AsyncServiceBrowser(zc.zeroconf, SERVICE_TYPE, handlers=[on_change])

    async def async_stop(self) -> None:
        if self._browser is not None:
            await self._browser.async_cancel()
            self._browser = None
