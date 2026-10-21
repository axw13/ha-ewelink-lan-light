"""Config flow: ip + deviceid + devicekey, read from the bulb's own pairing API.

No cloud call is ever made. Validation sends an empty `switch` payload, which
changes nothing: a bulb with the right key replies error:400, one with the
wrong key drops the connection.
"""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_DEVICEID, CONF_DEVICEKEY, DOMAIN
from .protocol import check_credentials

_LOGGER = logging.getLogger(__name__)


def _schema(defaults: dict) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "")): str,
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Required(CONF_DEVICEID, default=defaults.get(CONF_DEVICEID, "")): str,
            vol.Required(CONF_DEVICEKEY, default=defaults.get(CONF_DEVICEKEY, "")): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
        }
    )


class EweLinkLanLightConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_DEVICEID].strip())
            self._abort_if_unique_id_configured()
            try:
                ok = await self.hass.async_add_executor_job(
                    check_credentials,
                    user_input[CONF_HOST].strip(),
                    user_input[CONF_DEVICEID].strip(),
                    user_input[CONF_DEVICEKEY].strip(),
                )
            except OSError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating bulb")
                errors["base"] = "unknown"
            else:
                if ok:
                    return self.async_create_entry(
                        title=user_input[CONF_NAME].strip() or user_input[CONF_DEVICEID],
                        data={k: v.strip() for k, v in user_input.items()},
                    )
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user", data_schema=_schema(user_input or {}), errors=errors
        )
