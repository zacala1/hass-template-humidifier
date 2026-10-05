"""Humidifier platform of the Template Humidifier integration."""

import logging
from typing import TYPE_CHECKING, cast

import voluptuous as vol
from homeassistant.components.humidifier.const import DOMAIN as HUMIDIFIER_DOMAIN
from homeassistant.const import CONF_NAME, CONF_UNIQUE_ID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import (
    async_create_platform_config_not_supported_issue,
)
from homeassistant.helpers.script import async_validate_actions_config
from homeassistant.helpers.template import Template
from voluptuous.humanize import (
    humanize_error,  # pyright: ignore[reportUnknownVariableType]
)

from .const import DEFAULT_NAME, DOMAIN, ENTITIES, SCRIPT_FIELDS
from .entity import TemplateHumidifier

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)


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

    prefix = cast("str | None", discovery_info.get(CONF_UNIQUE_ID))
    entities: list[TemplateHumidifier] = []
    for entity_config in cast("list[ConfigType]", discovery_info[ENTITIES]):
        if (validated := await _async_validate_scripts(hass, entity_config)) is None:
            continue
        unique_id = cast("str | None", validated.get(CONF_UNIQUE_ID))
        if unique_id and prefix:
            unique_id = f"{prefix}-{unique_id}"
        entities.append(TemplateHumidifier(hass, validated, unique_id))
    async_add_entities(entities)


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
