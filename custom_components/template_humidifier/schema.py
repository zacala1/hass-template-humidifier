"""Schema of one humidifier entity in the ``template_humidifier`` YAML."""

from typing import TYPE_CHECKING, Final, cast

import voluptuous as vol
from homeassistant.components.humidifier import DEVICE_CLASSES_SCHEMA
from homeassistant.components.humidifier.const import DOMAIN as HUMIDIFIER_DOMAIN
from homeassistant.components.template.const import CONF_AVAILABILITY
from homeassistant.components.template.schemas import (
    make_template_entity_base_schema,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_OPTIMISTIC,
    CONF_STATE,
    CONF_VARIABLES,
)
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_ACTION,
    CONF_CURRENT_HUMIDITY,
    CONF_MAX_HUMIDITY,
    CONF_MIN_HUMIDITY,
    CONF_MODE,
    CONF_MODES,
    CONF_SET_HUMIDITY,
    CONF_SET_MODE,
    CONF_TARGET_HUMIDITY,
    CONF_TARGET_HUMIDITY_STEP,
    CONF_TURN_OFF,
    CONF_TURN_ON,
    DEFAULT_NAME,
)

if TYPE_CHECKING:
    from homeassistant.helpers.template import Template
    from homeassistant.helpers.typing import ConfigType

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


def _modes(value: object) -> list[str] | Template:
    """Validate ``modes``: a non-empty list of unique names, or a template."""
    if isinstance(value, list | tuple):
        modes = [cv.string(item) for item in cast("list[object]", value)]
        if not modes:
            message = f"{CONF_MODES} must not be empty"
            raise vol.Invalid(message)
        if len(set(modes)) != len(modes):
            message = f"{CONF_MODES} must not contain duplicates"
            raise vol.Invalid(message)
        return modes

    template = cv.template(value)
    if template.is_static:
        message = f"{CONF_MODES} must be a list or a template that renders a list"
        raise vol.Invalid(message)
    return template


def _validate_mode(config: ConfigType) -> ConfigType:
    """Reject a current ``mode`` that has no ``modes`` to belong to."""
    if CONF_MODE in config and CONF_MODES not in config:
        message = f"{CONF_MODE} requires {CONF_MODES} and {CONF_SET_MODE}"
        raise vol.Invalid(message, path=[CONF_MODE])
    return config


_MODES_GROUP: Final = "modes"
_MODES_TOGETHER: Final = f"{CONF_MODES} and {CONF_SET_MODE} must be configured together"

HUMIDIFIER_YAML_SCHEMA: Final = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
            vol.Optional(CONF_STATE): cv.template,
            vol.Optional(CONF_CURRENT_HUMIDITY): cv.template,
            vol.Optional(CONF_TARGET_HUMIDITY): cv.template,
            vol.Optional(CONF_MIN_HUMIDITY): cv.template,
            vol.Optional(CONF_MAX_HUMIDITY): cv.template,
            vol.Optional(CONF_TARGET_HUMIDITY_STEP): cv.template,
            vol.Optional(CONF_AVAILABILITY): cv.template,
            vol.Required(CONF_TURN_ON): cv.SCRIPT_SCHEMA,
            vol.Required(CONF_TURN_OFF): cv.SCRIPT_SCHEMA,
            vol.Required(CONF_SET_HUMIDITY): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_MODE): cv.template,
            vol.Inclusive(CONF_MODES, _MODES_GROUP, msg=_MODES_TOGETHER): _modes,
            vol.Inclusive(
                CONF_SET_MODE, _MODES_GROUP, msg=_MODES_TOGETHER
            ): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_ACTION): cv.template,
            vol.Optional(CONF_OPTIMISTIC): cv.boolean,
            vol.Optional(CONF_VARIABLES): cv.SCRIPT_VARIABLES_SCHEMA,
        }
    ).extend(  # pyright: ignore[reportUnknownMemberType]
        make_template_entity_base_schema(  # pyright: ignore[reportAny]
            HUMIDIFIER_DOMAIN, DEFAULT_NAME
        ).schema
    ),
    _validate_limits,
    _validate_mode,
)
