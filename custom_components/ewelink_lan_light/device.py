"""One bulb: serialised LAN commands plus state from the bulb itself.

State arrives two ways, both as the bulb's encrypted mDNS TXT record:
  * multicast announcements (instant, but multicast rarely crosses VLANs);
  * a unicast mDNS query we send every POLL_INTERVAL seconds (routable, so it
    works across VLANs and catches changes made by the app, BLE, a wall switch
    or anything else).
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import timedelta

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval

from .protocol import (
    MDNS_PORT,
    build_txt_query,
    parse_txt_state,
    send_command,
    txt_props_from_response,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_TYPE = "_ewelink._tcp.local."
RETRIES = 4
RETRY_DELAY = 0.25
POLL_INTERVAL = timedelta(seconds=10)
POLL_TIMEOUT = 2.0
MISS_LIMIT = 3  # consecutive missed polls before the light is marked unavailable


class _Reply(asyncio.DatagramProtocol):
    def __init__(self, fut: asyncio.Future) -> None:
        self._fut = fut

    def datagram_received(self, data: bytes, addr) -> None:
        if not self._fut.done():
            self._fut.set_result(data)


async def async_query_txt(host: str, deviceid: str) -> dict | None:
    """Ask the bulb directly for its TXT record; None if it did not answer."""
    loop = asyncio.get_running_loop()
    fut: asyncio.Future = loop.create_future()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: _Reply(fut), remote_addr=(host, MDNS_PORT)
    )
    try:
        transport.sendto(build_txt_query(deviceid))
        data = await asyncio.wait_for(fut, POLL_TIMEOUT)
    except (TimeoutError, OSError):
        return None
    finally:
        transport.close()
    return txt_props_from_response(data)


class EweLinkLanDevice:
    def __init__(self, hass: HomeAssistant, host: str, deviceid: str, devicekey: str) -> None:
        self.hass = hass
        self.host = host
        self.deviceid = deviceid
        self._devicekey = devicekey
        self._lock = asyncio.Lock()  # the bulb's web server handles one request at a time
        self._listeners: list[Callable[[], None]] = []
        self._browser = None
        self._unsub_poll: Callable[[], None] | None = None
        self._misses = 0
        self.state: dict | None = None
        self.push_state_seen = False

    @property
    def available(self) -> bool:
        # Until we have ever heard from the bulb we cannot tell "offline" from
        # "state unreadable on this network", so stay available (assumed state).
        return not (self.push_state_seen and self._misses >= MISS_LIMIT)

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

    # ---- state ----------------------------------------------------------
    @callback
    def add_listener(self, cb: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(cb)
        return lambda: self._listeners.remove(cb)

    @callback
    def _notify(self) -> None:
        for cb in list(self._listeners):
            cb()

    @callback
    def handle_txt(self, properties: dict) -> None:
        """Process a TXT record set (from multicast or from our own query)."""
        state = parse_txt_state(self._devicekey, properties)
        if state is None:
            _LOGGER.debug("%s: could not decode bulb state", self.deviceid)
            return
        self._misses = 0
        self.state = state
        self.push_state_seen = True
        self._notify()

    async def async_poll(self, _now=None) -> None:
        props = await async_query_txt(self.host, self.deviceid)
        if props is not None:
            self.handle_txt(props)
            return
        self._misses += 1
        if self._misses == MISS_LIMIT and self.push_state_seen:
            _LOGGER.warning("%s (%s) stopped answering", self.deviceid, self.host)
            self._notify()

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
        self._unsub_poll = async_track_time_interval(self.hass, self.async_poll, POLL_INTERVAL)
        self.hass.async_create_task(self.async_poll())  # first reading right away

    async def async_stop(self) -> None:
        if self._unsub_poll is not None:
            self._unsub_poll()
            self._unsub_poll = None
        if self._browser is not None:
            await self._browser.async_cancel()
            self._browser = None
