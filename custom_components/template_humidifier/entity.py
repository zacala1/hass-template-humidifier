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
from homeassistant.const import CONF_DEVICE_CLASS, CONF_OPTIMISTIC, CONF_STATE
from homeassistant.core import callback
from homeassistant.exceptions import ServiceValidationError, TemplateError
from homeassistant.helpers.restore_state import RestoreEntity
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
from .restore import HumidifierExtraStoredData
from .validators import Validator, humidity_number, positive_number

if TYPE_CHECKING:
    from homeassistant.components.humidifier import HumidifierDeviceClass
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType


# The three Home Assistant bases declare several members differently; the same
# combination is used by Core's own template entities.
class TemplateHumidifier(  # pyright: ignore[reportIncompatibleVariableOverride]
    TemplateEntity, HumidifierEntity, RestoreEntity
):
    """A humidifier or dehumidifier assembled from existing entities."""

    _attr_should_poll: bool = False
    _optimistic_entity: bool = True
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
        self._attr_is_on: bool | None = None
        self._attr_target_humidity: float | None = None
        self._attr_mode: str | None = None
        self._attr_available_modes: list[str] | None = None
        # The power is optimistic when ``state`` is missing (Home Assistant
        # sets ``assumed_state``). The target and the mode are remembered from
        # commands when their template is missing; ``optimistic: true`` does
        # so for all of them.
        optimistic = config.get(CONF_OPTIMISTIC) is True
        self._optimistic_target: bool = optimistic or CONF_TARGET_HUMIDITY not in config
        self._optimistic_mode: bool = optimistic or CONF_MODE not in config

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

    def _setup_setting(
        self,
        option: str,
        attribute: str,
        validator: Validator,
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

    def _setup_humidity(self) -> None:
        """Track the humidity readings, limits and step."""
        for option, attribute in (
            (CONF_CURRENT_HUMIDITY, "_attr_current_humidity"),
            (CONF_TARGET_HUMIDITY, "_attr_target_humidity"),
        ):
            self.setup_template(option, attribute, humidity_number(self, option))
        self._setup_setting(
            CONF_MIN_HUMIDITY,
            "_attr_min_humidity",
            humidity_number(self, CONF_MIN_HUMIDITY),
            DEFAULT_MIN_HUMIDITY,
        )
        self._setup_setting(
            CONF_MAX_HUMIDITY,
            "_attr_max_humidity",
            humidity_number(self, CONF_MAX_HUMIDITY),
            DEFAULT_MAX_HUMIDITY,
        )
        self._setup_setting(
            CONF_TARGET_HUMIDITY_STEP,
            "_attr_target_humidity_step",
            positive_number(self, CONF_TARGET_HUMIDITY_STEP),
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
            self.setup_template(
                CONF_MODES,
                "_attr_available_modes",
                template_validators.list_of_strings(
                    self, CONF_MODES, none_on_unknown_unavailable=True
                ),
                self._update_modes,
                none_on_template_error=False,
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

    @callback
    def _update_modes(self, result: object) -> None:
        """Store the rendered list of modes, which is empty when unusable."""
        modes = None if isinstance(result, TemplateError) else result
        self._attr_available_modes = [] if modes is None else cast("list[str]", modes)
        if self._optimistic_mode and self._attr_mode not in self._attr_available_modes:
            self._attr_mode = None

    @override
    async def async_turn_on(self, **kwargs: object) -> None:
        """Run the ``turn_on`` actions."""
        await self.async_run_script(
            self._action_scripts[CONF_TURN_ON], context=self._context
        )
        if self._attr_assumed_state:
            self._attr_is_on = True
            self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: object) -> None:
        """Run the ``turn_off`` actions."""
        await self.async_run_script(
            self._action_scripts[CONF_TURN_OFF], context=self._context
        )
        if self._attr_assumed_state:
            self._attr_is_on = False
            self.async_write_ha_state()

    @override
    async def async_set_humidity(self, humidity: int) -> None:
        """Run the ``set_humidity`` actions with the ``humidity`` variable."""
        await self.async_run_script(
            self._action_scripts[CONF_SET_HUMIDITY],
            run_variables={"humidity": humidity},
            context=self._context,
        )
        if self._optimistic_target:
            self._attr_target_humidity = humidity
            self.async_write_ha_state()

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
        if self._optimistic_mode:
            self._attr_mode = mode
            self.async_write_ha_state()

    @property
    @override
    def extra_restore_state_data(self) -> HumidifierExtraStoredData:
        """Return the remembered values that a restart should bring back."""
        return HumidifierExtraStoredData(
            is_on=self._attr_is_on,
            target_humidity=self._attr_target_humidity,
            mode=self._attr_mode,
        )

    @override
    async def async_restore_last_state(self) -> None:
        """Bring back remembered values where no template has supplied one."""
        extra = await self.async_get_last_extra_data()
        if extra is None:
            return
        stored = HumidifierExtraStoredData.from_dict(extra.as_dict())

        if self._attr_assumed_state and self._attr_is_on is None:
            self._attr_is_on = stored.is_on
        target = stored.target_humidity
        if (
            self._optimistic_target
            and self._attr_target_humidity is None
            and target is not None
            and self.min_humidity <= target <= self.max_humidity
        ):
            self._attr_target_humidity = target
        # A modes template may not have rendered yet; it drops the mode again
        # if the list turns out not to contain it.
        modes = self.available_modes
        if (
            self._optimistic_mode
            and self._attr_mode is None
            and stored.mode is not None
            and (modes is None or stored.mode in modes)
        ):
            self._attr_mode = stored.mode
