"""Configuration validation for the ``template_humidifier`` domain.

The shape mirrors the modern Home Assistant ``template:`` integration: a list
of sections, each holding a ``humidifier`` list of entity definitions.
"""

from typing import TYPE_CHECKING, Final, cast

import voluptuous as vol
from homeassistant.components.humidifier import DEVICE_CLASSES_SCHEMA
from homeassistant.components.humidifier.const import DOMAIN as HUMIDIFIER_DOMAIN
from homeassistant.components.template.const import CONF_AVAILABILITY
from homeassistant.components.template.schemas import (
    make_template_entity_base_schema,
)
from homeassistant.config import (
    async_log_schema_error,  # pyright: ignore[reportUnknownVariableType]
    config_without_domain,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_STATE, CONF_UNIQUE_ID
from homeassistant.helpers import config_validation as cv
from homeassistant.setup import async_notify_setup_error

from .const import (
    CONF_CURRENT_HUMIDITY,
    CONF_HUMIDIFIER,
    CONF_MAX_HUMIDITY,
    CONF_MIN_HUMIDITY,
    CONF_SET_HUMIDITY,
    CONF_TARGET_HUMIDITY,
    CONF_TARGET_HUMIDITY_STEP,
    CONF_TURN_OFF,
    CONF_TURN_ON,
    DEFAULT_NAME,
    DOMAIN,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.template import Template
    from homeassistant.helpers.typing import ConfigType

# Home Assistant needs this hint to merge ``packages`` that each define
# ``template_humidifier`` instead of rejecting the duplicate key.
PACKAGE_MERGE_HINT: Final = "list"

_MAX_HUMIDITY: Final = 100


def _static_number(config: ConfigType, key: str) -> float | None:
    """Return the numeric value of a static option, or None for a template."""
    template = cast("Template | None", config.get(key))
    if template is None or not template.is_static:
        return None
    try:
        return float(template.template)
    except ValueError:
        message = f"{key} must be a number or a template, got {template.template!r}"
        raise vol.Invalid(message, path=[key]) from None


def _validate_limits(config: ConfigType) -> ConfigType:
    """Reject static humidity limits and steps that cannot work."""
    limits: dict[str, float] = {}
    for key in (CONF_MIN_HUMIDITY, CONF_MAX_HUMIDITY):
        if (value := _static_number(config, key)) is None:
            continue
        if not 0 <= value <= _MAX_HUMIDITY:
            message = f"{key} must be between 0 and {_MAX_HUMIDITY}, got {value:g}"
            raise vol.Invalid(message, path=[key])
        limits[key] = value

    minimum = limits.get(CONF_MIN_HUMIDITY)
    maximum = limits.get(CONF_MAX_HUMIDITY)
    if minimum is not None and maximum is not None and minimum > maximum:
        message = (
            f"{CONF_MIN_HUMIDITY} ({minimum:g}) must not be greater than "
            f"{CONF_MAX_HUMIDITY} ({maximum:g})"
        )
        raise vol.Invalid(message, path=[CONF_MIN_HUMIDITY])

    step = _static_number(config, CONF_TARGET_HUMIDITY_STEP)
    if step is not None and not 0 < step <= _MAX_HUMIDITY:
        message = (
            f"{CONF_TARGET_HUMIDITY_STEP} must be greater than 0 and at most "
            f"{_MAX_HUMIDITY}, got {step:g}"
        )
        raise vol.Invalid(message, path=[CONF_TARGET_HUMIDITY_STEP])

    return config


HUMIDIFIER_YAML_SCHEMA: Final = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
            vol.Required(CONF_STATE): cv.template,
            vol.Required(CONF_CURRENT_HUMIDITY): cv.template,
            vol.Required(CONF_TARGET_HUMIDITY): cv.template,
            vol.Optional(CONF_MIN_HUMIDITY): cv.template,
            vol.Optional(CONF_MAX_HUMIDITY): cv.template,
            vol.Optional(CONF_TARGET_HUMIDITY_STEP): cv.template,
            vol.Optional(CONF_AVAILABILITY): cv.template,
            vol.Required(CONF_TURN_ON): cv.SCRIPT_SCHEMA,
            vol.Required(CONF_TURN_OFF): cv.SCRIPT_SCHEMA,
            vol.Required(CONF_SET_HUMIDITY): cv.SCRIPT_SCHEMA,
        }
    ).extend(  # pyright: ignore[reportUnknownMemberType]
        make_template_entity_base_schema(  # pyright: ignore[reportAny]
            HUMIDIFIER_DOMAIN, DEFAULT_NAME
        ).schema
    ),
    _validate_limits,
)

CONFIG_SECTION_SCHEMA: Final = vol.Schema(
    {
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Required(CONF_HUMIDIFIER): vol.All(
            cv.ensure_list, [HUMIDIFIER_YAML_SCHEMA]
        ),
    }
)


def _is_domain_key(key: str) -> bool:
    """Return whether a top-level key belongs to this domain.

    Home Assistant allows ``template_humidifier:`` as well as labelled copies
    such as ``template_humidifier living_room:``.
    """
    return key == DOMAIN or (key.startswith(DOMAIN) and len(key.split()) > 1)


async def async_validate_config(hass: HomeAssistant, config: ConfigType) -> ConfigType:
    """Validate every section on its own so one mistake cannot hide the rest."""
    sections: list[ConfigType] = []
    found = False
    for key in config:
        if not _is_domain_key(key):
            continue
        found = True
        for section in cast(
            "list[ConfigType]", cv.ensure_list(cast("object", config[key]))
        ):
            try:
                sections.append(cast("ConfigType", CONFIG_SECTION_SCHEMA(section)))
            except vol.Invalid as err:
                async_log_schema_error(err, DOMAIN, section, hass)
                async_notify_setup_error(hass, DOMAIN)

    if not found:
        return config

    validated = config_without_domain(config, DOMAIN)
    validated[DOMAIN] = sections
    return validated
