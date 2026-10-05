"""The template humidifier entity."""

from typing import TYPE_CHECKING, cast, override

from homeassistant.components.humidifier import ENTITY_ID_FORMAT, HumidifierEntity
from homeassistant.components.humidifier.const import (
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    HumidifierAction,
    HumidifierEntityFeature,
)
from homeassistant.components.template import validators as template_validators
from homeassistant.components.template.template_entity import TemplateEntity
from homeassistant.const import CONF_DEVICE_CLASS, CONF_STATE
from homeassistant.core import callback
from homeassistant.exceptions import ServiceValidationError, TemplateError
from homeassistant.helpers.template import Template

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
    DOMAIN,
    SCRIPT_FIELDS,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.components.humidifier import HumidifierDeviceClass
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

_MAX_HUMIDITY = 100

type _Validator = Callable[[object], float | int | None]


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
        self._attr_mode: str | None = None
        self._attr_available_modes: list[str] | None = None

        self.setup_state_template(
            "_attr_is_on",
            template_validators.boolean(
                self, CONF_STATE, none_on_unknown_unavailable=True
            ),
        )
        self._setup_humidity()
        self._setup_modes(config)
        self.setup_template(
            CONF_ACTION,
            "_attr_action",
            template_validators.strenum(
                self, CONF_ACTION, HumidifierAction, none_on_unknown_unavailable=True
            ),
        )

        name = self._attr_name or DEFAULT_NAME
        for field in SCRIPT_FIELDS:
            if field in config:
                self.add_script(
                    field, cast("list[ConfigType]", config[field]), name, DOMAIN
                )

    def _humidity_number(self, option: str) -> _Validator:
        """Return a validator accepting numbers from 0 to 100."""
        return template_validators.number(
            self, option, 0, _MAX_HUMIDITY, none_on_unknown_unavailable=True
        )

    def _positive_number(self, option: str) -> _Validator:
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
        validator: _Validator,
        default: float | list[str] | None,
    ) -> None:
        """Track a capability template, reverting to a default when unusable."""

        @callback
        def update(result: object) -> None:
            value = None if isinstance(result, TemplateError) else result
            setattr(self, attribute, default if value is None else value)

        self.setup_template(
            option, attribute, validator, update, none_on_template_error=False
        )

    def _setup_humidity(self) -> None:
        """Track the humidity readings, limits and step."""
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

    def _setup_modes(self, config: ConfigType) -> None:
        """Expose modes when ``modes`` and ``set_mode`` are configured."""
        modes = config.get(CONF_MODES)
        if modes is None:
            return

        # The attribute is declared by the HA base classes; annotating it again
        # here would conflict with Entity's plain ``int | None``.
        self._attr_supported_features |= HumidifierEntityFeature.MODES  # pyright: ignore[reportUnannotatedClassAttribute]
        if isinstance(modes, Template):
            # Registered before ``mode`` so a new list is in place before the
            # current mode is checked against it.
            self._setup_setting(
                CONF_MODES,
                "_attr_available_modes",
                cast(
                    "_Validator",
                    template_validators.list_of_strings(
                        self, CONF_MODES, none_on_unknown_unavailable=True
                    ),
                ),
                [],
            )
        else:
            self._attr_available_modes = cast("list[str]", modes)
        self.setup_template(
            CONF_MODE,
            "_attr_mode",
            template_validators.item_in_list(
                self, CONF_MODE, "available_modes", none_on_unknown_unavailable=True
            ),
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

    @override
    async def async_set_mode(self, mode: str) -> None:
        """Run the ``set_mode`` actions with the ``mode`` variable."""
        modes = self.available_modes or []
        if mode not in modes:
            message = (
                f"Mode {mode!r} is not available for {self.entity_id}, "
                f"expected one of: {', '.join(modes) or 'none'}"
            )
            raise ServiceValidationError(message)
        await self.async_run_script(
            self._action_scripts[CONF_SET_MODE],
            run_variables={"mode": mode},
            context=self._context,
        )
