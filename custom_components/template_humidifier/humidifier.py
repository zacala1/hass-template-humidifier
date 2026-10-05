"""Humidifier platform of the Template Humidifier integration."""

import logging
from typing import TYPE_CHECKING, cast

import voluptuous as vol
from homeassistant.components.humidifier.const import DOMAIN as HUMIDIFIER_DOMAIN
from homeassistant.components.template.template_entity import TemplateEntity
from homeassistant.components.template.trigger_entity import TriggerEntity
from homeassistant.const import CONF_NAME, CONF_UNIQUE_ID
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers.entity_platform import (
    async_create_platform_config_not_supported_issue,
)
from homeassistant.helpers.script import async_validate_actions_config
from homeassistant.helpers.template import Template
from voluptuous.humanize import (
    humanize_error,  # pyright: ignore[reportUnknownVariableType]
)

from .const import DEFAULT_NAME, DOMAIN, ENTITIES, SCRIPT_FIELDS
from .entity import AbstractTemplateHumidifier

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

    from .coordinator import HumidifierTriggerCoordinator

_LOGGER = logging.getLogger(__name__)

COORDINATOR = "coordinator"


class StateHumidifier(  # pyright: ignore[reportUnsafeMultipleInheritance]
    TemplateEntity, AbstractTemplateHumidifier
):
    """A humidifier whose templates follow the state machine."""

    _attr_should_poll: bool = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        unique_id: str | None,
    ) -> None:
        """Initialize the humidifier."""
        TemplateEntity.__init__(self, hass, config, unique_id)
        AbstractTemplateHumidifier.__init__(
            self, self._attr_name or DEFAULT_NAME, config
        )


class TriggerHumidifier(  # pyright: ignore[reportUnsafeMultipleInheritance, reportIncompatibleVariableOverride]
    TriggerEntity, AbstractTemplateHumidifier
):
    """A humidifier whose templates are rendered each time a trigger fires."""

    domain: str = HUMIDIFIER_DOMAIN

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: HumidifierTriggerCoordinator,
        config: ConfigType,
    ) -> None:
        """Initialize the humidifier."""
        TriggerEntity.__init__(self, hass, coordinator, config)  # pyright: ignore[reportUnknownMemberType]
        rendered = cast("dict[str, object]", self._rendered)
        name = cast("str", rendered.get("name", DEFAULT_NAME))
        self._attr_name = name  # pyright: ignore[reportUnannotatedClassAttribute]
        AbstractTemplateHumidifier.__init__(self, name, config)


async def async_setup_platform(
    hass: HomeAssistant,
    _config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Create the entities of one validated section."""
    if discovery_info is None:
        async_create_platform_config_not_supported_issue(
            hass,
            DOMAIN,
            HUMIDIFIER_DOMAIN,
            yaml_config_under_integration_supported=True,
            logger=_LOGGER,
        )
        return

    coordinator = cast(
        "HumidifierTriggerCoordinator | None", discovery_info.get(COORDINATOR)
    )
    prefix = cast("str | None", discovery_info.get(CONF_UNIQUE_ID))
    entities: list[AbstractTemplateHumidifier] = []
    for entity_config in cast("list[ConfigType]", discovery_info[ENTITIES]):
        if (validated := await _async_validate_scripts(hass, entity_config)) is None:
            continue
        try:
            entities.append(_create_entity(hass, coordinator, prefix, validated))
        except TemplateError as err:
            # Variables are rendered while the entity is built, before it has
            # an entity ID, so one that uses ``this`` ends up here.
            _LOGGER.error(  # noqa: TRY400
                "%s could not be created, skipping it: %s",
                _describe(entity_config),
                err,
            )
    async_add_entities(entities)


def _create_entity(
    hass: HomeAssistant,
    coordinator: HumidifierTriggerCoordinator | None,
    prefix: str | None,
    config: ConfigType,
) -> AbstractTemplateHumidifier:
    """Build the state based or trigger based entity for ``config``."""
    if coordinator is not None:
        # The coordinator adds its own unique ID prefix.
        return TriggerHumidifier(hass, coordinator, config)
    unique_id = cast("str | None", config.get(CONF_UNIQUE_ID))
    if unique_id and prefix:
        unique_id = f"{prefix}-{unique_id}"
    return StateHumidifier(hass, config, unique_id)


async def _async_validate_scripts(
    hass: HomeAssistant, entity_config: ConfigType
) -> ConfigType | None:
    """Resolve the command scripts, or log why this entity cannot be created."""
    validated = dict(entity_config)
    for field in SCRIPT_FIELDS:
        if field not in entity_config:
            continue
        actions = cast("list[ConfigType]", entity_config[field])
        try:
            validated[field] = await async_validate_actions_config(hass, actions)
        except (vol.Invalid, HomeAssistantError) as err:
            reason = (
                humanize_error(actions, err)
                if isinstance(err, vol.Invalid)
                else str(err)
            )
            # A traceback would only add noise to what is a configuration error.
            _LOGGER.error(  # noqa: TRY400
                "The '%s' actions of %s failed to set up, skipping it: %s",
                field,
                _describe(entity_config),
                reason,
            )
            return None
    return validated


def _describe(config: ConfigType) -> str:
    """Return a human readable identifier for log messages."""
    if default_entity_id := cast("str | None", config.get("default_entity_id")):
        return default_entity_id
    if (unique_id := cast("str | None", config.get(CONF_UNIQUE_ID))) is not None:
        return f"unique_id: {unique_id}"
    name = cast("Template | None", config.get(CONF_NAME))
    return name.template if isinstance(name, Template) else DEFAULT_NAME
