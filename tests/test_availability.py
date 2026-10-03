"""Availability handling of the template humidifier."""

from typing import TYPE_CHECKING

from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE

from .conftest import (
    POWER,
    TARGET,
    SetupIntegration,
    entity_config,
    get_state,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

AVAILABILITY = f"{{{{ has_value('{POWER}') and has_value('{TARGET}') }}}}"


async def test_availability_follows_source_entities(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(entity_config(availability=AVAILABILITY))
    assert get_state(hass).state == STATE_OFF

    hass.states.async_set(POWER, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert get_state(hass).state == STATE_UNAVAILABLE

    hass.states.async_set(POWER, "off")
    await hass.async_block_till_done()
    assert get_state(hass).state == STATE_OFF


async def test_unavailable_when_source_is_missing_at_startup(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    _ = hass.states.async_remove(TARGET)

    await setup_integration(entity_config(availability=AVAILABILITY))

    assert get_state(hass).state == STATE_UNAVAILABLE

    hass.states.async_set(TARGET, "50")
    await hass.async_block_till_done()

    assert get_state(hass).state == STATE_OFF


async def test_availability_template_error_keeps_entity_available(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(entity_config(availability="{{ 1 / 0 }}"))

    assert get_state(hass).state == STATE_OFF
