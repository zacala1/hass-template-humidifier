"""YAML-first template humidifiers and dehumidifiers for Home Assistant."""

from typing import TYPE_CHECKING, cast

from homeassistant import config as conf_util
from homeassistant.const import CONF_UNIQUE_ID, SERVICE_RELOAD, Platform
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import discovery
from homeassistant.helpers.reload import async_reload_integration_platforms
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.loader import async_get_integration

from .const import CONF_HUMIDIFIER, DOMAIN, ENTITIES

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall
    from homeassistant.helpers.typing import ConfigType


def _load_platforms(hass: HomeAssistant, config: ConfigType) -> None:
    """Set up the humidifier platform for every validated section."""
    for section in cast("list[ConfigType]", config.get(DOMAIN, [])):
        _ = hass.async_create_task(
            discovery.async_load_platform(
                hass,
                Platform.HUMIDIFIER,
                DOMAIN,
                {
                    CONF_UNIQUE_ID: section.get(CONF_UNIQUE_ID),
                    ENTITIES: section[CONF_HUMIDIFIER],
                },
                config,
            ),
            eager_start=True,
        )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration and its ``reload`` action."""
    _load_platforms(hass, config)

    async def reload_config(call: ServiceCall) -> None:
        """Re-read the YAML and rebuild every entity from it."""
        try:
            unprocessed = cast(
                "ConfigType",
                await conf_util.async_hass_config_yaml(hass),  # pyright: ignore[reportUnknownMemberType]
            )
        except HomeAssistantError as err:
            message = f"Error reloading template humidifiers: {err}"
            raise HomeAssistantError(message) from err

        integration = await async_get_integration(hass, DOMAIN)
        validated = await conf_util.async_process_component_and_handle_errors(
            hass, unprocessed, integration
        )
        if validated is None:
            return

        await async_reload_integration_platforms(hass, DOMAIN, [Platform.HUMIDIFIER])
        _load_platforms(hass, validated)
        hass.bus.async_fire(f"event_{DOMAIN}_reloaded", context=call.context)

    async_register_admin_service(hass, DOMAIN, SERVICE_RELOAD, reload_config)
    return True
