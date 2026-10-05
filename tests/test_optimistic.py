"""Power, target humidity and mode remembered from commands."""

from typing import TYPE_CHECKING

import pytest
from homeassistant.components.humidifier.const import (
    DOMAIN as HUMIDIFIER_DOMAIN,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_MODE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_MODE,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .conftest import (
    HUMIDIFIER_ID,
    POWER,
    SELECT,
    TARGET,
    Calls,
    SetupIntegration,
    entity_config,
    get_state,
    mode_config,
    optimistic_config,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

TARGET_ENTITY = {ATTR_ENTITY_ID: HUMIDIFIER_ID}
OPTIONS = "{{ state_attr('select.dehumidifier_mode', 'options') }}"


async def _call(hass: HomeAssistant, service: str, **data: object) -> None:
    _ = await hass.services.async_call(
        HUMIDIFIER_DOMAIN, service, {**TARGET_ENTITY, **data}, blocking=True
    )


# --- power ---------------------------------------------------------------------


async def test_missing_state_template_makes_the_power_optimistic(
    hass: HomeAssistant, setup_integration: SetupIntegration, calls: Calls
) -> None:
    await setup_integration(optimistic_config())
    state = get_state(hass)
    assert state.state == STATE_UNKNOWN
    assert state.attributes["assumed_state"] is True

    await _call(hass, SERVICE_TURN_ON)
    assert get_state(hass).state == STATE_ON
    assert len(calls.turn_on) == 1

    await _call(hass, SERVICE_TURN_OFF)
    assert get_state(hass).state == STATE_OFF
    assert len(calls.turn_off) == 1


async def test_toggle_from_an_unknown_state_turns_on(
    hass: HomeAssistant, setup_integration: SetupIntegration, calls: Calls
) -> None:
    await setup_integration(optimistic_config())

    await _call(hass, SERVICE_TOGGLE)
    assert get_state(hass).state == STATE_ON
    await _call(hass, SERVICE_TOGGLE)
    assert get_state(hass).state == STATE_OFF

    assert (len(calls.turn_on), len(calls.turn_off)) == (1, 1)


@pytest.mark.parametrize(
    ("service", "failing"),
    [(SERVICE_TURN_ON, "turn_on"), (SERVICE_TURN_OFF, "turn_off")],
)
async def test_failed_command_leaves_the_optimistic_power_unchanged(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    service: str,
    failing: str,
) -> None:
    config = optimistic_config()
    config[failing] = [{"action": "test.missing"}]
    await setup_integration(config)

    with pytest.raises(HomeAssistantError):
        await _call(hass, service)

    assert get_state(hass).state == STATE_UNKNOWN


async def test_a_state_template_means_the_power_is_not_assumed(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(entity_config())

    assert "assumed_state" not in get_state(hass).attributes


async def test_optimistic_true_overrides_a_state_template_until_it_changes(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(entity_config(optimistic=True))
    assert get_state(hass).attributes["assumed_state"] is True
    assert get_state(hass).state == STATE_OFF

    await _call(hass, SERVICE_TURN_ON)
    assert get_state(hass).state == STATE_ON

    hass.states.async_set(POWER, "on")
    await hass.async_block_till_done()
    assert get_state(hass).state == STATE_ON

    hass.states.async_set(POWER, "off")
    await hass.async_block_till_done()
    assert get_state(hass).state == STATE_OFF


async def test_optimistic_false_keeps_the_power_unknown_without_a_template(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(optimistic_config(optimistic=False))

    await _call(hass, SERVICE_TURN_ON)

    state = get_state(hass)
    assert state.state == STATE_UNKNOWN
    assert "assumed_state" not in state.attributes


# --- target humidity -----------------------------------------------------------


async def test_target_humidity_is_remembered_without_a_template(
    hass: HomeAssistant, setup_integration: SetupIntegration, calls: Calls
) -> None:
    await setup_integration(optimistic_config())
    assert "humidity" not in get_state(hass).attributes

    await _call(hass, SERVICE_SET_HUMIDITY, humidity=45)
    assert get_state(hass).attributes["humidity"] == 45

    await _call(hass, SERVICE_SET_HUMIDITY, humidity=60)
    assert get_state(hass).attributes["humidity"] == 60
    assert [call.data["humidity"] for call in calls.set_humidity] == [45, 60]


async def test_rejected_set_humidity_keeps_the_previous_target(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(optimistic_config())
    await _call(hass, SERVICE_SET_HUMIDITY, humidity=45)

    with pytest.raises(ServiceValidationError):
        await _call(hass, SERVICE_SET_HUMIDITY, humidity=99)

    assert get_state(hass).attributes["humidity"] == 45


async def test_failed_set_humidity_does_not_change_the_target(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(
        optimistic_config(set_humidity=[{"action": "test.missing"}])
    )

    with pytest.raises(HomeAssistantError):
        await _call(hass, SERVICE_SET_HUMIDITY, humidity=45)

    assert "humidity" not in get_state(hass).attributes


async def test_optimistic_true_applies_to_a_target_template_until_it_changes(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(entity_config(optimistic=True))
    assert get_state(hass).attributes["humidity"] == 50

    await _call(hass, SERVICE_SET_HUMIDITY, humidity=45)
    assert get_state(hass).attributes["humidity"] == 45

    hass.states.async_set(TARGET, "55")
    await hass.async_block_till_done()
    assert get_state(hass).attributes["humidity"] == 55


async def test_current_humidity_is_optional(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    config = entity_config()
    del config["current_humidity"]
    await setup_integration(config)

    state = get_state(hass)
    assert "current_humidity" not in state.attributes
    assert state.state == STATE_OFF


# --- mode ----------------------------------------------------------------------


async def test_mode_is_remembered_without_a_template(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(optimistic_config(with_modes=True))
    assert get_state(hass).attributes["mode"] is None

    await _call(hass, SERVICE_SET_MODE, **{ATTR_MODE: "quiet"})

    assert get_state(hass).attributes["mode"] == "quiet"


async def test_unavailable_mode_does_not_change_the_remembered_mode(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(optimistic_config(with_modes=True))
    await _call(hass, SERVICE_SET_MODE, **{ATTR_MODE: "quiet"})

    with pytest.raises(ServiceValidationError):
        await _call(hass, SERVICE_SET_MODE, **{ATTR_MODE: "turbo"})

    assert get_state(hass).attributes["mode"] == "quiet"


async def test_failed_set_mode_does_not_change_the_mode(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(
        optimistic_config(with_modes=True, set_mode=[{"action": "test.missing"}])
    )

    with pytest.raises(HomeAssistantError):
        await _call(hass, SERVICE_SET_MODE, **{ATTR_MODE: "quiet"})

    assert get_state(hass).attributes["mode"] is None


async def test_optimistic_true_applies_to_a_mode_template_until_it_changes(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(mode_config(optimistic=True))
    assert get_state(hass).attributes["mode"] == "auto"

    await _call(hass, SERVICE_SET_MODE, **{ATTR_MODE: "quiet"})
    assert get_state(hass).attributes["mode"] == "quiet"

    hass.states.async_set(SELECT, "laundry", {"options": ["auto", "quiet", "laundry"]})
    await hass.async_block_till_done()
    assert get_state(hass).attributes["mode"] == "laundry"


async def test_remembered_mode_follows_a_modes_template(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(optimistic_config(with_modes=True, modes=OPTIONS))
    await _call(hass, SERVICE_SET_MODE, **{ATTR_MODE: "laundry"})
    assert get_state(hass).attributes["mode"] == "laundry"

    hass.states.async_set(SELECT, "auto", {"options": ["auto", "quiet"]})
    await hass.async_block_till_done()
    assert get_state(hass).attributes["mode"] is None

    hass.states.async_set(SELECT, "auto", {"options": ["auto", "quiet", "laundry"]})
    await hass.async_block_till_done()
    assert get_state(hass).attributes["mode"] is None
