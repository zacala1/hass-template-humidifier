"""Coordinator that turns a section's triggers into entity updates."""

from typing import TYPE_CHECKING, override

from homeassistant.components.template.coordinator import TriggerUpdateCoordinator
from homeassistant.const import EVENT_HOMEASSISTANT_START, Platform
from homeassistant.core import CoreState
from homeassistant.helpers import discovery
from homeassistant.util.hass_dict import HassKey

from .const import CONF_HUMIDIFIER, DOMAIN, ENTITIES

if TYPE_CHECKING:
    from homeassistant.helpers.typing import ConfigType

DATA_COORDINATORS: HassKey[list[HumidifierTriggerCoordinator]] = HassKey(DOMAIN)


class HumidifierTriggerCoordinator(TriggerUpdateCoordinator):
    """Runs the triggers of one section and hands the results to its entities.

    Core's coordinator does the work; only the platform it loads differs, because
    its own ``async_setup`` can only load the platforms of the ``template``
    integration.
    """

    @override
    async def async_setup(self, hass_config: ConfigType) -> None:
        """Attach the triggers and create the entities."""
        if self.hass.state is CoreState.running:
            await self._attach_triggers()
        else:
            # The attribute belongs to Core's coordinator, which this extends.
            self._unsub_start = self.hass.bus.async_listen_once(  # pyright: ignore[reportUnannotatedClassAttribute]
                EVENT_HOMEASSISTANT_START, self._attach_triggers
            )

        _ = self.hass.async_create_task(
            discovery.async_load_platform(
                self.hass,
                Platform.HUMIDIFIER,
                DOMAIN,
                {"coordinator": self, ENTITIES: self.config[CONF_HUMIDIFIER]},
                hass_config,
            ),
            eager_start=True,
        )
