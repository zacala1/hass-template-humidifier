"""YAML-first template humidifiers and dehumidifiers for Home Assistant."""

from typing import TYPE_CHECKING

from homeassistant.const import CONF_UNIQUE_ID, Platform
from homeassistant.helpers import discovery

from .const import CONF_HUMIDIFIER, DOMAIN, ENTITIES

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the humidifier platform for every validated section."""
    for section in config.get(DOMAIN, []):
        hass.async_create_task(
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
    return True
