"""Restoring remembered power, target humidity and mode after a restart."""

from typing import TYPE_CHECKING, cast

import pytest
from custom_components.template_humidifier.restore import HumidifierExtraStoredData
from homeassistant.components.humidifier import DATA_COMPONENT
from homeassistant.components.humidifier.const import (
    DOMAIN as HUMIDIFIER_DOMAIN,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_MODE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_MODE,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import State
from pytest_homeassistant_custom_component.common import (
    mock_restore_cache,
    mock_restore_cache_with_extra_data,
)

from .conftest import (
    HUMIDIFIER_ID,
    SELECT,
    SetupIntegration,
    entity_config,
    get_state,
    mode_config,
    optimistic_config,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from custom_components.template_humidifier.entity import TemplateHumidifier
    from homeassistant.core import HomeAssistant

OPTIONS = "{{ state_attr('select.dehumidifier_mode', 'options') }}"
FULL = {"is_on": True, "target_humidity": 55.0, "mode": "quiet"}


def _restore(
    hass: HomeAssistant,
    extra: Mapping[str, object] | None,
    state: str = STATE_ON,
) -> None:
    """Pretend Home Assistant stopped with this entity in the given condition."""
    if extra is None:
        mock_restore_cache(hass, [State(HUMIDIFIER_ID, state)])
        return
    mock_restore_cache_with_extra_data(hass, [(State(HUMIDIFIER_ID, state), extra)])


async def test_restores_the_optimistic_power_target_and_mode(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    _restore(hass, FULL)

    await setup_integration(optimistic_config(with_modes=True))

    state = get_state(hass)
    assert state.state == STATE_ON
    assert state.attributes["humidity"] == 55
    assert state.attributes["mode"] == "quiet"


async def test_restores_an_off_entity(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    _restore(hass, {**FULL, "is_on": False}, STATE_OFF)

    await setup_integration(optimistic_config(with_modes=True))

    assert get_state(hass).state == STATE_OFF


async def test_restores_even_when_the_last_state_was_unavailable(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    _restore(hass, FULL, STATE_UNAVAILABLE)

    await setup_integration(optimistic_config(with_modes=True))

    assert get_state(hass).state == STATE_ON


async def test_templates_win_over_restored_values(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    _restore(hass, FULL)

    await setup_integration(mode_config())

    state = get_state(hass)
    assert state.state == STATE_OFF
    assert state.attributes["humidity"] == 50
    assert state.attributes["mode"] == "auto"


async def test_only_the_optimistic_properties_are_restored(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    config = entity_config()
    del config["target_humidity"]
    _restore(hass, FULL)

    await setup_integration(config)

    state = get_state(hass)
    assert state.state == STATE_OFF  # the state template decides
    assert state.attributes["humidity"] == 55  # remembered


async def test_a_rendered_template_beats_the_restored_value_when_optimistic(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    _restore(hass, FULL)

    await setup_integration(mode_config(optimistic=True))

    state = get_state(hass)
    assert state.state == STATE_OFF
    assert state.attributes["humidity"] == 50
    assert state.attributes["mode"] == "auto"


async def test_nothing_is_restored_without_stored_data(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    _restore(hass, None)

    await setup_integration(optimistic_config(with_modes=True))

    state = get_state(hass)
    assert state.state == STATE_UNKNOWN
    assert "humidity" not in state.attributes
    assert state.attributes["mode"] is None


@pytest.mark.parametrize(
    "extra",
    [
        {},
        {"unrelated": 1},
        {"is_on": "yes", "target_humidity": "55", "mode": 3},
        {"is_on": None, "target_humidity": True, "mode": None},
    ],
)
async def test_unusable_stored_data_is_ignored(
    hass: HomeAssistant, setup_integration: SetupIntegration, extra: dict[str, object]
) -> None:
    _restore(hass, extra)

    await setup_integration(optimistic_config(with_modes=True))

    state = get_state(hass)
    assert state.state == STATE_UNKNOWN
    assert "humidity" not in state.attributes
    assert state.attributes["mode"] is None


@pytest.mark.parametrize("target", [-1, 39, 71, 150, float("nan")])
async def test_a_restored_target_outside_the_limits_is_ignored(
    hass: HomeAssistant, setup_integration: SetupIntegration, target: float
) -> None:
    _restore(hass, {**FULL, "target_humidity": target})

    await setup_integration(optimistic_config(with_modes=True))

    assert "humidity" not in get_state(hass).attributes


@pytest.mark.parametrize("mode", ["turbo", "Quiet", ""])
async def test_a_restored_mode_that_is_not_available_is_ignored(
    hass: HomeAssistant, setup_integration: SetupIntegration, mode: str
) -> None:
    _restore(hass, {**FULL, "mode": mode})

    await setup_integration(optimistic_config(with_modes=True))

    assert get_state(hass).attributes["mode"] is None


async def test_a_restored_mode_is_checked_against_a_modes_template(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    _restore(hass, FULL)
    await setup_integration(optimistic_config(with_modes=True, modes=OPTIONS))
    assert get_state(hass).attributes["mode"] == "quiet"

    hass.states.async_set(SELECT, "auto", {"options": ["auto"]})
    await hass.async_block_till_done()

    assert get_state(hass).attributes["mode"] is None


async def test_a_restored_mode_missing_from_a_modes_template_is_dropped(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    hass.states.async_set(SELECT, "auto", {"options": ["auto", "laundry"]})
    _restore(hass, FULL)

    await setup_integration(optimistic_config(with_modes=True, modes=OPTIONS))

    assert get_state(hass).attributes["mode"] is None


async def test_the_entity_reports_what_to_store(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(optimistic_config(with_modes=True))
    entity_id = {ATTR_ENTITY_ID: HUMIDIFIER_ID}
    for service, data in (
        (SERVICE_TURN_ON, {}),
        (SERVICE_SET_HUMIDITY, {"humidity": 45}),
        (SERVICE_SET_MODE, {ATTR_MODE: "laundry"}),
    ):
        _ = await hass.services.async_call(
            HUMIDIFIER_DOMAIN, service, {**entity_id, **data}, blocking=True
        )

    entity = cast(
        "TemplateHumidifier | None",
        hass.data[DATA_COMPONENT].get_entity(HUMIDIFIER_ID),
    )
    assert entity is not None
    assert entity.extra_restore_state_data == HumidifierExtraStoredData(
        is_on=True, target_humidity=45, mode="laundry"
    )
    assert entity.extra_restore_state_data.as_dict() == {
        "is_on": True,
        "target_humidity": 45,
        "mode": "laundry",
    }


def test_stored_data_survives_a_round_trip() -> None:
    stored = HumidifierExtraStoredData(is_on=False, target_humidity=40, mode=None)

    assert HumidifierExtraStoredData.from_dict(stored.as_dict()) == stored


@pytest.mark.parametrize(
    ("restored", "expected"),
    [
        ({}, (None, None, None)),
        ({"is_on": "yes", "target_humidity": "55", "mode": 3}, (None, None, None)),
        ({"is_on": 1, "target_humidity": True, "mode": ["auto"]}, (None, None, None)),
        ({"is_on": True, "target_humidity": 55, "mode": "auto"}, (True, 55, "auto")),
        ({"is_on": False, "target_humidity": 40.5, "mode": ""}, (False, 40.5, "")),
    ],
)
def test_stored_data_keeps_only_values_of_the_expected_type(
    restored: dict[str, object],
    expected: tuple[bool | None, float | None, str | None],
) -> None:
    stored = HumidifierExtraStoredData.from_dict(restored)

    assert (stored.is_on, stored.target_humidity, stored.mode) == expected
