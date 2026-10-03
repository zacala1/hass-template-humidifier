"""Command scripts executed through the standard humidifier services."""

import pytest
from homeassistant.components.humidifier import (
    ATTR_HUMIDITY,
    DOMAIN as HUMIDIFIER_DOMAIN,
    SERVICE_SET_HUMIDITY,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .conftest import HUMIDIFIER_ID, POWER, SetupIntegration, entity_config

TARGET_ENTITY = {ATTR_ENTITY_ID: HUMIDIFIER_ID}


async def test_turn_on_runs_configured_script(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    turn_on_calls: list[ServiceCall],
    turn_off_calls: list[ServiceCall],
) -> None:
    await setup_integration(entity_config())

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN, SERVICE_TURN_ON, TARGET_ENTITY, blocking=True
    )

    assert len(turn_on_calls) == 1
    assert not turn_off_calls


async def test_turn_off_runs_configured_script(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    turn_on_calls: list[ServiceCall],
    turn_off_calls: list[ServiceCall],
) -> None:
    await setup_integration(entity_config())

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN, SERVICE_TURN_OFF, TARGET_ENTITY, blocking=True
    )

    assert len(turn_off_calls) == 1
    assert not turn_on_calls


@pytest.mark.parametrize(
    ("power", "expect_on", "expect_off"),
    [("off", 1, 0), ("on", 0, 1)],
)
async def test_toggle_follows_current_state(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    turn_on_calls: list[ServiceCall],
    turn_off_calls: list[ServiceCall],
    power: str,
    expect_on: int,
    expect_off: int,
) -> None:
    await setup_integration(entity_config())
    hass.states.async_set(POWER, power)
    await hass.async_block_till_done()

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN, SERVICE_TOGGLE, TARGET_ENTITY, blocking=True
    )

    assert (len(turn_on_calls), len(turn_off_calls)) == (expect_on, expect_off)


async def test_set_humidity_exposes_humidity_variable(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    set_humidity_calls: list[ServiceCall],
) -> None:
    await setup_integration(entity_config())

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {**TARGET_ENTITY, ATTR_HUMIDITY: 45},
        blocking=True,
    )

    [call] = set_humidity_calls
    assert call.data["humidity"] == 45


async def test_scripts_receive_this_variable(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    turn_on_calls: list[ServiceCall],
) -> None:
    await setup_integration(
        entity_config(
            turn_on=[
                {
                    "action": "test.turn_on",
                    "data": {"entity": "{{ this.entity_id }}"},
                }
            ]
        )
    )

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN, SERVICE_TURN_ON, TARGET_ENTITY, blocking=True
    )

    assert turn_on_calls[0].data["entity"] == HUMIDIFIER_ID


async def test_scripts_run_in_the_service_call_context(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    turn_on_calls: list[ServiceCall],
) -> None:
    await setup_integration(entity_config())
    context = Context()

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_ON,
        TARGET_ENTITY,
        blocking=True,
        context=context,
    )

    assert turn_on_calls[0].context.id == context.id


async def test_script_can_use_multiple_steps_and_native_service_data(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    set_humidity_calls: list[ServiceCall],
    turn_on_calls: list[ServiceCall],
) -> None:
    await setup_integration(
        entity_config(
            set_humidity=[
                {"action": "test.turn_on"},
                {
                    "action": "test.set_humidity",
                    "data": {"humidity": "{{ humidity + 5 }}"},
                },
            ]
        )
    )

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {**TARGET_ENTITY, ATTR_HUMIDITY: 45},
        blocking=True,
    )

    assert len(turn_on_calls) == 1
    assert set_humidity_calls[0].data["humidity"] == 50


@pytest.mark.parametrize("humidity", [39, 71])
async def test_set_humidity_outside_range_is_rejected_before_script(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    set_humidity_calls: list[ServiceCall],
    humidity: int,
) -> None:
    await setup_integration(entity_config())

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_SET_HUMIDITY,
            {**TARGET_ENTITY, ATTR_HUMIDITY: humidity},
            blocking=True,
        )

    assert not set_humidity_calls


async def test_failed_script_propagates_and_entity_keeps_working(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    turn_off_calls: list[ServiceCall],
) -> None:
    await setup_integration(entity_config(turn_on=[{"action": "test.missing"}]))

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN, SERVICE_TURN_ON, TARGET_ENTITY, blocking=True
        )

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN, SERVICE_TURN_OFF, TARGET_ENTITY, blocking=True
    )
    assert len(turn_off_calls) == 1
    state = hass.states.get(HUMIDIFIER_ID)
    assert state is not None
    assert state.state == "off"


async def test_commands_do_not_assume_a_new_state(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    turn_on_calls: list[ServiceCall],
) -> None:
    await setup_integration(entity_config())

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN, SERVICE_TURN_ON, TARGET_ENTITY, blocking=True
    )

    state = hass.states.get(HUMIDIFIER_ID)
    assert state is not None
    assert state.state == "off"
    assert "assumed_state" not in state.attributes
