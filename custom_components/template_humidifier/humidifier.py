"""Humidifier platform of the Template Humidifier integration."""

import logging
from typing import TYPE_CHECKING, cast, override

import voluptuous as vol
from homeassistant.components.humidifier import ENTITY_ID_FORMAT, HumidifierEntity
from homeassistant.components.humidifier.const import (
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    DOMAIN as HUMIDIFIER_DOMAIN,
)
from homeassistant.components.template import validators as template_validators
from homeassistant.components.template.template_entity import TemplateEntity
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_STATE,
    CONF_UNIQUE_ID,
)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers.entity_platform import (
    async_create_platform_config_not_supported_issue,
)
from homeassistant.helpers.script import async_validate_actions_config
from homeassistant.helpers.template import Template
from voluptuous.humanize import (
    humanize_error,  # pyright: ignore[reportUnknownVariableType]
)

from .const import (
    CONF_CURRENT_HUMIDITY,
    CONF_MAX_HUMIDITY,
    CONF_MIN_HUMIDITY,
    CONF_SET_HUMIDITY,
    CONF_TARGET_HUMIDITY,
    CONF_TARGET_HUMIDITY_STEP,
    CONF_TURN_OFF,
    CONF_TURN_ON,
    DEFAULT_NAME,
    DOMAIN,
    ENTITIES,
    SCRIPT_FIELDS,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.components.humidifier import HumidifierDeviceClass
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

_MAX_HUMIDITY = 100


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


class TemplateHumidifier(TemplateEntity, HumidifierEntity):
    """A humidifier or dehumidifier assembled from existing entities."""

    _attr_should_poll: bool = False
    _entity_id_format: str = ENTITY_ID_FORMAT
    _state_option: str | None = CONF_STATE

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        unique_id: str | None,
    ) -> None:
        """Initialize the humidifier."""
        TemplateEntity.__init__(self, hass, config, unique_id)
        # Home Assistant declares this attribute as ``str`` on Entity but as the
        # narrower enum on HumidifierEntity, which no annotation can satisfy.
        self._attr_device_class: HumidifierDeviceClass | None = cast(  # pyright: ignore[reportIncompatibleVariableOverride]
            "HumidifierDeviceClass", config[CONF_DEVICE_CLASS]
        )

        self.setup_state_template(
            "_attr_is_on",
            template_validators.boolean(
                self, CONF_STATE, none_on_unknown_unavailable=True
            ),
        )
        for option, attribute in (
            (CONF_CURRENT_HUMIDITY, "_attr_current_humidity"),
            (CONF_TARGET_HUMIDITY, "_attr_target_humidity"),
        ):
            self.setup_template(option, attribute, self._humidity_number(option))
        self._setup_setting(
            CONF_MIN_HUMIDITY,
            "_attr_min_humidity",
            self._humidity_number(CONF_MIN_HUMIDITY),
            DEFAULT_MIN_HUMIDITY,
        )
        self._setup_setting(
            CONF_MAX_HUMIDITY,
            "_attr_max_humidity",
            self._humidity_number(CONF_MAX_HUMIDITY),
            DEFAULT_MAX_HUMIDITY,
        )
        self._setup_setting(
            CONF_TARGET_HUMIDITY_STEP,
            "_attr_target_humidity_step",
            self._positive_number(CONF_TARGET_HUMIDITY_STEP),
            None,
        )

        name = self._attr_name or DEFAULT_NAME
        for field in SCRIPT_FIELDS:
            self.add_script(
                field, cast("list[ConfigType]", config[field]), name, DOMAIN
            )

    def _humidity_number(self, option: str) -> Callable[[object], float | int | None]:
        """Return a validator accepting numbers from 0 to 100."""
        return template_validators.number(
            self, option, 0, _MAX_HUMIDITY, none_on_unknown_unavailable=True
        )

    def _positive_number(self, option: str) -> Callable[[object], float | int | None]:
        """Return a validator accepting numbers above 0 up to 100."""
        convert = self._humidity_number(option)

        def validate(result: object) -> float | int | None:
            value = convert(result)
            if value is not None and value <= 0:
                template_validators.log_validation_result_error(
                    self, option, result, "expected a number greater than 0"
                )
                return None
            return value

        return validate

    def _setup_setting(
        self,
        option: str,
        attribute: str,
        validator: Callable[[object], float | int | None],
        default: float | None,
    ) -> None:
        """Track a capability template, reverting to a default when unusable."""

        @callback
        def update(result: object) -> None:
            value = None if isinstance(result, TemplateError) else result
            setattr(self, attribute, default if value is None else value)

        self.setup_template(
            option, attribute, validator, update, none_on_template_error=False
        )

    @override
    async def async_turn_on(self, **kwargs: object) -> None:
        """Run the ``turn_on`` actions."""
        await self.async_run_script(
            self._action_scripts[CONF_TURN_ON], context=self._context
        )

    @override
    async def async_turn_off(self, **kwargs: object) -> None:
        """Run the ``turn_off`` actions."""
        await self.async_run_script(
            self._action_scripts[CONF_TURN_OFF], context=self._context
        )

    @override
    async def async_set_humidity(self, humidity: int) -> None:
        """Run the ``set_humidity`` actions with the ``humidity`` variable."""
        await self.async_run_script(
            self._action_scripts[CONF_SET_HUMIDITY],
            run_variables={"humidity": humidity},
            context=self._context,
        )
