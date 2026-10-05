"""Configuration validation for the ``template_humidifier`` domain.

The shape mirrors the modern Home Assistant ``template:`` integration: a list of
sections, each holding a ``humidifier`` list of entity definitions. A section
can also have ``triggers`` (with ``conditions`` and ``actions``) and
``variables``.
"""

import logging
from typing import TYPE_CHECKING, Final, cast

import voluptuous as vol
from homeassistant.config import (
    async_log_schema_error,  # pyright: ignore[reportUnknownVariableType]
    config_without_domain,
)
from homeassistant.const import (
    CONF_ACTIONS,
    CONF_CONDITIONS,
    CONF_TRIGGERS,
    CONF_UNIQUE_ID,
    CONF_VARIABLES,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.condition import async_validate_conditions_config
from homeassistant.helpers.trigger import async_validate_trigger_config
from homeassistant.setup import async_notify_setup_error

from .const import CONF_HUMIDIFIER, DOMAIN
from .schema import HUMIDIFIER_YAML_SCHEMA

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

# Home Assistant needs this hint to merge ``packages`` that each define
# ``template_humidifier`` instead of rejecting the duplicate key.
PACKAGE_MERGE_HINT: Final = "list"


def _merge_section_variables(section: object) -> object:
    """Hand a state based section's ``variables`` down to each of its entities.

    The entity's own variables win. A trigger based section keeps them: they are
    rendered when the trigger fires, before its entities see them.
    """
    if not isinstance(section, dict):
        return section
    raw = cast("ConfigType", section)
    variables = raw.get(CONF_VARIABLES)
    if CONF_TRIGGERS in raw or not isinstance(variables, dict):
        return cast("object", section)

    del raw[CONF_VARIABLES]
    for entity in cast("list[object]", cv.ensure_list(raw.get(CONF_HUMIDIFIER))):
        if not isinstance(entity, dict):
            continue
        own = cast("ConfigType", entity).get(CONF_VARIABLES)
        if own is None:
            cast("ConfigType", entity)[CONF_VARIABLES] = variables
        elif isinstance(own, dict):
            cast("ConfigType", entity)[CONF_VARIABLES] = {**variables, **own}
    return cast("object", section)


def _require_triggers(section: ConfigType) -> ConfigType:
    """Reject ``conditions`` and ``actions`` that no trigger would ever run."""
    for key in (CONF_CONDITIONS, CONF_ACTIONS):
        if key in section and CONF_TRIGGERS not in section:
            message = f"{key} needs {CONF_TRIGGERS}"
            raise vol.Invalid(message, path=[key])
    return section


def _section_schema(entities: object) -> vol.All:
    """Return the schema of a section whose entities are checked by ``entities``."""
    return vol.All(
        _merge_section_variables,
        vol.Schema(
            {
                vol.Optional(CONF_UNIQUE_ID): cv.string,
                vol.Optional(CONF_VARIABLES): cv.SCRIPT_VARIABLES_SCHEMA,
                vol.Optional(CONF_TRIGGERS): cv.TRIGGER_SCHEMA,
                vol.Optional(CONF_CONDITIONS): cv.CONDITIONS_SCHEMA,
                vol.Optional(CONF_ACTIONS): cv.SCRIPT_SCHEMA,
                vol.Required(CONF_HUMIDIFIER): vol.All(cv.ensure_list, [entities]),
            }
        ),
        _require_triggers,
    )


CONFIG_SECTION_SCHEMA: Final = _section_schema(HUMIDIFIER_YAML_SCHEMA)

# The same section, but leaving the entities unvalidated so that each one can be
# checked (and dropped) on its own.
_SECTION_SHELL_SCHEMA: Final = _section_schema(dict)


def _is_domain_key(key: str) -> bool:
    """Return whether a top-level key belongs to this domain.

    Home Assistant allows ``template_humidifier:`` as well as labelled copies
    such as ``template_humidifier living_room:``.
    """
    return key == DOMAIN or (key.startswith(DOMAIN) and len(key.split()) > 1)


def _report(hass: HomeAssistant, err: vol.Invalid, config: ConfigType) -> None:
    async_log_schema_error(err, DOMAIN, config, hass)
    async_notify_setup_error(hass, DOMAIN)


async def _async_validate_section(
    hass: HomeAssistant, section: ConfigType
) -> ConfigType | None:
    """Validate a section, dropping only the entities that are invalid."""
    try:
        shell = cast("ConfigType", _SECTION_SHELL_SCHEMA(section))
    except vol.Invalid as err:
        _report(hass, err, section)
        return None

    try:
        if CONF_TRIGGERS in shell:
            shell[CONF_TRIGGERS] = await async_validate_trigger_config(
                hass, cast("list[ConfigType]", shell[CONF_TRIGGERS])
            )
        if CONF_CONDITIONS in shell:
            shell[CONF_CONDITIONS] = await async_validate_conditions_config(
                hass, cast("list[ConfigType]", shell[CONF_CONDITIONS])
            )
    except vol.Invalid as err:
        _report(hass, err, section)
        return None
    except HomeAssistantError as err:
        _LOGGER.error("Invalid %s section, skipping it: %s", DOMAIN, err)  # noqa: TRY400
        async_notify_setup_error(hass, DOMAIN)
        return None

    entities: list[ConfigType] = []
    for entity in cast("list[ConfigType]", shell[CONF_HUMIDIFIER]):
        try:
            entities.append(cast("ConfigType", HUMIDIFIER_YAML_SCHEMA(entity)))
        except vol.Invalid as err:
            _report(hass, err, entity)

    return {**shell, CONF_HUMIDIFIER: entities}


async def async_validate_config(hass: HomeAssistant, config: ConfigType) -> ConfigType:
    """Validate every entity on its own so one mistake cannot hide the rest."""
    sections: list[ConfigType] = []
    found = False
    for key in config:
        if not _is_domain_key(key):
            continue
        found = True
        raw_sections = cast(
            "list[ConfigType]", cv.ensure_list(cast("object", config[key]))
        )
        sections.extend(
            [
                section
                for raw in raw_sections
                if (section := await _async_validate_section(hass, raw)) is not None
            ]
        )

    if not found:
        return config

    validated_config = config_without_domain(config, DOMAIN)
    validated_config[DOMAIN] = sections
    return validated_config
