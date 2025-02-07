from typing import Any

import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN, CONF_PORT, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL


@config_entries.HANDLERS.register(DOMAIN)
class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = validate_config(user_input)
            if not errors:
                return self.async_create_entry(title="Pulsar", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PORT): str,
                    vol.Optional(
                        CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL
                    ): int,
                }
            ),
            errors=errors,
        )


def validate_config(user_input: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}

    if not user_input.get(CONF_PORT):
        errors["port"] = "invalid_port"

    update_interval = user_input.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    if update_interval <= 0:
        errors["update_interval"] = "invalid_update_interval"

    return errors