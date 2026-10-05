"""Modes, ``set_mode`` and the ``action`` state of the template humidifier."""

from typing import TYPE_CHECKING

import pytest
from homeassistant.components.humidifier.const import (
    DOMAIN as HUMIDIFIER_DOMAIN,
    HumidifierEntityFeature,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_MODE, ATTR_SUPPORTED_FEATURES
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .conftest import (
    COMPRESSOR,
    HUMIDIFIER_ID,
    POWER,
    SELECT,
    Calls,
    SetupIntegration,
    entity_config,
    get_state,
    mode_config,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

SET_MODE = "set_mode"
TARGET_ENTITY = {ATTR_ENTITY_ID: HUMIDIFIER_ID}
OPTIONS = "{{ state_attr('select.dehumidifier_mode', 'options') }}"


async def _set_mode(hass: HomeAssistant, mode: str) -> None:
    _ = await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SET_MODE,
        {**TARGET_ENTITY, ATTR_MODE: mode},
        blocking=True,
    )


# --- supported features and attributes ---------------------------------------


async def test_modes_enable_the_modes_feature(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(mode_config())

    attributes = get_state(hass).attributes
    assert attributes[ATTR_SUPPORTED_FEATURES] == HumidifierEntityFeature.MODES
    assert attributes["available_modes"] == ["auto", "quiet", "laundry"]
    assert attributes["mode"] == "auto"


async def test_no_modes_means_no_modes_feature(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(entity_config())

    attributes = get_state(hass).attributes
    assert attributes[ATTR_SUPPORTED_FEATURES] == 0
    assert "available_modes" not in attributes
    assert "mode" not in attributes


async def test_current_mode_follows_the_template(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(mode_config())

    hass.states.async_set(SELECT, "quiet")
    await hass.async_block_till_done()

    assert get_state(hass).attributes["mode"] == "quiet"


@pytest.mark.parametrize("value", ["unknown", "unavailable", "turbo", "Auto", ""])
async def test_mode_outside_the_list_is_none(
    hass: HomeAssistant, setup_integration: SetupIntegration, value: str
) -> None:
    await setup_integration(mode_config())

    hass.states.async_set(SELECT, value)
    await hass.async_block_till_done()

    state = get_state(hass)
    assert state.attributes["mode"] is None
    assert state.state == "off"


async def test_modes_without_mode_template_have_unknown_mode(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    config = mode_config()
    del config["mode"]
    await setup_integration(config)

    attributes = get_state(hass).attributes
    assert attributes["mode"] is None
    assert attributes["available_modes"] == ["auto", "quiet", "laundry"]


async def test_mode_template_error_becomes_none(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(mode_config(mode="{{ nonsense() }}"))

    state = get_state(hass)
    assert state.attributes["mode"] is None
    assert state.state == "off"


# --- template modes ----------------------------------------------------------


async def test_modes_follow_a_template(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(mode_config(modes=OPTIONS))
    assert get_state(hass).attributes["available_modes"] == [
        "auto",
        "quiet",
        "laundry",
    ]

    hass.states.async_set(SELECT, "eco", {"options": ["eco", "boost"]})
    await hass.async_block_till_done()

    attributes = get_state(hass).attributes
    assert attributes["available_modes"] == ["eco", "boost"]
    assert attributes["mode"] == "eco"


@pytest.mark.parametrize("options", [None, [], "auto", "unavailable"])
async def test_unusable_template_modes_become_an_empty_list(
    hass: HomeAssistant, setup_integration: SetupIntegration, options: object
) -> None:
    hass.states.async_set(SELECT, "auto", {"options": options})
    await setup_integration(mode_config(modes=OPTIONS))

    attributes = get_state(hass).attributes
    assert attributes["available_modes"] == []
    assert attributes["mode"] is None
    assert attributes[ATTR_SUPPORTED_FEATURES] == HumidifierEntityFeature.MODES


async def test_template_modes_recover_after_an_outage(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(mode_config(modes=OPTIONS))

    _ = hass.states.async_remove(SELECT)
    await hass.async_block_till_done()
    assert get_state(hass).attributes["available_modes"] == []

    hass.states.async_set(SELECT, "quiet", {"options": ["auto", "quiet"]})
    await hass.async_block_till_done()

    attributes = get_state(hass).attributes
    assert attributes["available_modes"] == ["auto", "quiet"]
    assert attributes["mode"] == "quiet"


# --- set_mode -----------------------------------------------------------------


async def test_set_mode_runs_the_script_with_the_mode_variable(
    hass: HomeAssistant, setup_integration: SetupIntegration, calls: Calls
) -> None:
    await setup_integration(mode_config())

    await _set_mode(hass, "quiet")

    [call] = calls.set_mode
    assert call.data["mode"] == "quiet"


async def test_set_mode_accepts_a_template_mode(
    hass: HomeAssistant, setup_integration: SetupIntegration, calls: Calls
) -> None:
    await setup_integration(mode_config(modes=OPTIONS))

    await _set_mode(hass, "laundry")

    assert calls.set_mode[0].data["mode"] == "laundry"


@pytest.mark.parametrize("mode", ["turbo", "Quiet", ""])
async def test_set_mode_rejects_modes_that_are_not_available(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    calls: Calls,
    mode: str,
) -> None:
    await setup_integration(mode_config())

    with pytest.raises(ServiceValidationError, match="not available"):
        await _set_mode(hass, mode)

    assert not calls.set_mode


async def test_set_mode_is_not_supported_without_modes(
    hass: HomeAssistant, setup_integration: SetupIntegration, calls: Calls
) -> None:
    await setup_integration(entity_config())

    with pytest.raises(HomeAssistantError):
        await _set_mode(hass, "auto")

    assert not calls.set_mode


async def test_set_mode_failure_propagates_and_the_entity_keeps_working(
    hass: HomeAssistant, setup_integration: SetupIntegration, calls: Calls
) -> None:
    await setup_integration(mode_config(set_mode=[{"action": "test.missing"}]))

    with pytest.raises(HomeAssistantError):
        await _set_mode(hass, "quiet")

    _ = await hass.services.async_call(
        HUMIDIFIER_DOMAIN, "turn_off", TARGET_ENTITY, blocking=True
    )
    assert len(calls.turn_off) == 1
    assert get_state(hass).attributes["mode"] == "auto"


async def test_set_mode_does_not_assume_the_new_mode(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(mode_config())

    await _set_mode(hass, "quiet")

    assert get_state(hass).attributes["mode"] == "auto"


async def test_set_mode_script_gets_this_and_the_service_context(
    hass: HomeAssistant, setup_integration: SetupIntegration, calls: Calls
) -> None:
    from homeassistant.core import Context  # noqa: PLC0415

    await setup_integration(
        mode_config(
            set_mode=[
                {
                    "action": "test.set_mode",
                    "data": {"mode": "{{ mode }}", "entity": "{{ this.entity_id }}"},
                }
            ]
        )
    )
    context = Context()

    _ = await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SET_MODE,
        {**TARGET_ENTITY, ATTR_MODE: "quiet"},
        blocking=True,
        context=context,
    )

    [call] = calls.set_mode
    assert call.data["entity"] == HUMIDIFIER_ID
    assert call.context.id == context.id


# --- action -------------------------------------------------------------------

ACTION = (
    f"{{% if is_state('{POWER}', 'off') %}}off"
    f"{{% elif is_state('{COMPRESSOR}', 'on') %}}drying"
    "{% else %}idle{% endif %}"
)


async def test_action_follows_the_template(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(entity_config(action=ACTION))
    assert get_state(hass).attributes["action"] == "off"

    hass.states.async_set(POWER, "on")
    await hass.async_block_till_done()
    assert get_state(hass).attributes["action"] == "idle"

    hass.states.async_set(COMPRESSOR, "on")
    await hass.async_block_till_done()
    assert get_state(hass).attributes["action"] == "drying"


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("humidifying", "humidifying"),
        (" Drying ", "drying"),
        ("IDLE", "idle"),
    ],
)
async def test_action_is_normalised(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    template: str,
    expected: str,
) -> None:
    await setup_integration(
        entity_config(
            action=f"{{{{ '{template}' }}}}",
            state="{{ true }}",
        )
    )

    assert get_state(hass).attributes["action"] == expected


@pytest.mark.parametrize("value", ["unknown", "unavailable", "cooling", "", "1"])
async def test_unusable_action_is_dropped(
    hass: HomeAssistant, setup_integration: SetupIntegration, value: str
) -> None:
    hass.states.async_set(COMPRESSOR, value)
    await setup_integration(
        entity_config(action=f"{{{{ states('{COMPRESSOR}') }}}}", state="{{ true }}")
    )

    state = get_state(hass)
    assert "action" not in state.attributes
    assert state.state == "on"


async def test_action_template_error_is_dropped(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(entity_config(action="{{ nonsense() }}"))

    state = get_state(hass)
    assert "action" not in state.attributes
    assert state.state == "off"


async def test_action_is_off_while_the_entity_is_off(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(entity_config(action="{{ 'drying' }}"))

    assert get_state(hass).state == "off"
    assert get_state(hass).attributes["action"] == "off"
