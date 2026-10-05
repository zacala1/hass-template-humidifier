"""Shared fixtures for Template Humidifier tests."""

import importlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import pytest
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_mock_service

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall, State
    from homeassistant.helpers.typing import ConfigType

pytest_plugins = ["pytest_homeassistant_custom_component"]

# Home Assistant finds the integration through the ``custom_components`` package.
# Importing it here makes it resolve to this repository no matter which test
# module runs first, instead of depending on test collection order.
_ = importlib.import_module("custom_components.template_humidifier")

DOMAIN = "template_humidifier"
HUMIDIFIER_ID = "humidifier.living_room_dehumidifier"
POWER = "switch.dehumidifier_power"
HUMIDITY = "sensor.dehumidifier_humidity"
TARGET = "number.dehumidifier_target"
SELECT = "select.dehumidifier_mode"
COMPRESSOR = "binary_sensor.dehumidifier_compressor"

type SetupIntegration = Callable[..., Awaitable[None]]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow Home Assistant to load the integration under test."""
    assert enable_custom_integrations is None


def entity_config(**overrides: object) -> ConfigType:
    """Return a complete, valid humidifier entity configuration."""
    config: ConfigType = {
        "name": "Living Room Dehumidifier",
        "unique_id": "living_room_dehumidifier",
        "device_class": "dehumidifier",
        "state": f"{{{{ is_state('{POWER}', 'on') }}}}",
        "current_humidity": f"{{{{ states('{HUMIDITY}') }}}}",
        "target_humidity": f"{{{{ states('{TARGET}') }}}}",
        "min_humidity": 40,
        "max_humidity": 70,
        "target_humidity_step": 5,
        "turn_on": [{"action": "test.turn_on"}],
        "turn_off": [{"action": "test.turn_off"}],
        "set_humidity": [
            {"action": "test.set_humidity", "data": {"humidity": "{{ humidity }}"}}
        ],
    }
    config.update(overrides)
    return config


def mode_config(**overrides: object) -> ConfigType:
    """Return a valid configuration that also exposes modes."""
    return entity_config(
        **{
            "mode": f"{{{{ states('{SELECT}') }}}}",
            "modes": ["auto", "quiet", "laundry"],
            "set_mode": [{"action": "test.set_mode", "data": {"mode": "{{ mode }}"}}],
            **overrides,
        }
    )


def optimistic_config(*, with_modes: bool = False, **overrides: object) -> ConfigType:
    """Return a configuration with no ``state``, ``target_humidity`` or ``mode``.

    The power, the target humidity and the mode are then remembered from commands.
    """
    config = mode_config(**overrides) if with_modes else entity_config(**overrides)
    for key in {"state", "target_humidity", "mode"} - overrides.keys():
        _ = cast("object", config.pop(key, None))
    return config


def get_state(hass: HomeAssistant, entity_id: str = HUMIDIFIER_ID) -> State:
    """Return the state of an entity that must exist."""
    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    return state


@dataclass(frozen=True)
class Calls:
    """Service calls recorded for the three command scripts."""

    turn_on: list[ServiceCall]
    turn_off: list[ServiceCall]
    set_humidity: list[ServiceCall]
    set_mode: list[ServiceCall]


@pytest.fixture(autouse=True)
def sources(hass: HomeAssistant) -> None:
    """Create the source entities the default configuration reads."""
    hass.states.async_set(POWER, "off")
    hass.states.async_set(HUMIDITY, "57")
    hass.states.async_set(TARGET, "50")
    hass.states.async_set(SELECT, "auto", {"options": ["auto", "quiet", "laundry"]})
    hass.states.async_set(COMPRESSOR, "off")


@pytest.fixture(autouse=True)
def calls(hass: HomeAssistant) -> Calls:
    """Mock the services the default command scripts call."""
    return Calls(
        turn_on=async_mock_service(hass, "test", "turn_on"),
        turn_off=async_mock_service(hass, "test", "turn_off"),
        set_humidity=async_mock_service(hass, "test", "set_humidity"),
        set_mode=async_mock_service(hass, "test", "set_mode"),
    )


@pytest.fixture
def setup_integration(hass: HomeAssistant) -> SetupIntegration:
    """Return a coroutine that sets the integration up with the given entities."""

    async def _setup(*entities: ConfigType, **section: object) -> None:
        config: ConfigType = {DOMAIN: [{"humidifier": list(entities), **section}]}
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    return _setup
