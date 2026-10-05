"""Validators for the numbers a humidifier template renders."""

from typing import TYPE_CHECKING

from homeassistant.components.template import validators as template_validators

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.helpers.entity import Entity

type Validator = Callable[[object], float | int | None]

MAX_HUMIDITY = 100


def humidity_number(entity: Entity, option: str) -> Validator:
    """Return a validator accepting numbers from 0 to 100.

    ``unknown`` and ``unavailable`` become None without logging an error.
    """
    return template_validators.number(
        entity, option, 0, MAX_HUMIDITY, none_on_unknown_unavailable=True
    )


def positive_number(entity: Entity, option: str) -> Validator:
    """Return a validator accepting numbers above 0 up to 100."""
    convert = humidity_number(entity, option)

    def validate(result: object) -> float | int | None:
        value = convert(result)
        if value is not None and value <= 0:
            template_validators.log_validation_result_error(
                entity, option, result, "expected a number greater than 0"
            )
            return None
        return value

    return validate
