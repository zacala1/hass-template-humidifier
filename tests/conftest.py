"""Shared fixtures for Template Humidifier tests."""

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_mock_service

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

pytest_plugins = ["pytest_homeassistant_custom_component"]

DOMAIN = "template_humidifier"
HUMIDIFIER_ID = "humidifier.living_room_dehumidifier"
POWER = "switch.dehumidifier_power"
HUMIDITY = "sensor.dehumidifier_humidity"
TARGET = "number.dehumidifier_target"

type EntityConfig = dict[str, Any]
type SetupIntegration = Callable[..., Awaitable[None]]


def entity_config(**overrides: Any) -> EntityConfig:  # noqa: ANN401
    """Return a complete, valid humidifier entity configuration."""
    config: EntityConfig = {
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


@pytest.fixture(autouse=True)
def _auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow Home Assistant to load the integration under test."""


@pytest.fixture
def sources(hass: HomeAssistant) -> None:
    """Create the source entities the default configuration reads."""
    hass.states.async_set(POWER, "off")
    hass.states.async_set(HUMIDITY, "57")
    hass.states.async_set(TARGET, "50")


@pytest.fixture
def setup_integration(hass: HomeAssistant, sources: None) -> SetupIntegration:
    """Return a coroutine that sets the integration up with the given entities."""

    async def _setup(*entities: EntityConfig, **section: Any) -> None:  # noqa: ANN401
        config = {DOMAIN: [{"humidifier": list(entities), **section}]}
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    return _setup


@pytest.fixture
def turn_on_calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Record ``test.turn_on`` calls."""
    return async_mock_service(hass, "test", "turn_on")


@pytest.fixture
def turn_off_calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Record ``test.turn_off`` calls."""
    return async_mock_service(hass, "test", "turn_off")


@pytest.fixture
def set_humidity_calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Record ``test.set_humidity`` calls."""
    return async_mock_service(hass, "test", "set_humidity")
