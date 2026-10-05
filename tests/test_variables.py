"""``variables`` on entities and on sections of state based humidifiers."""

from typing import TYPE_CHECKING

from homeassistant.components.humidifier.const import (
    DOMAIN as HUMIDIFIER_DOMAIN,
    SERVICE_SET_HUMIDITY,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_MODE,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.setup import async_setup_component

from .conftest import (
    DOMAIN,
    HUMIDIFIER_ID,
    HUMIDITY,
    POWER,
    SELECT,
    Calls,
    SetupIntegration,
    entity_config,
    get_state,
    mode_config,
)

if TYPE_CHECKING:
    import pytest
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

TARGET_ENTITY = {ATTR_ENTITY_ID: HUMIDIFIER_ID}


async def test_entity_variables_are_available_in_every_template(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    hass.states.async_set(SELECT, "quiet", {"options": ["auto", "quiet"]})
    await setup_integration(
        mode_config(
            variables={
                "power": POWER,
                "humidity": HUMIDITY,
                "mode_entity": SELECT,
                "label": "Dehumidifier",
            },
            state="{{ is_state(power, 'off') }}",
            current_humidity="{{ states(humidity) }}",
            mode="{{ states(mode_entity) }}",
            modes="{{ state_attr(mode_entity, 'options') }}",
            availability="{{ has_value(power) }}",
            action="{{ 'idle' if is_state(power, 'off') else 'off' }}",
            name="{{ label }} two",
            icon="{{ 'mdi:air-humidifier' if is_state(power, 'off') else 'mdi:off' }}",
        )
    )

    state = get_state(hass, "humidifier.dehumidifier_two")
    assert state.state == STATE_ON
    assert state.attributes["current_humidity"] == 57
    assert state.attributes["mode"] == "quiet"
    assert state.attributes["available_modes"] == ["auto", "quiet"]
    assert state.attributes["action"] == "idle"
    assert state.attributes["icon"] == "mdi:air-humidifier"
    assert state.attributes["friendly_name"] == "Dehumidifier two"


async def test_entity_variables_are_available_in_the_actions(
    hass: HomeAssistant, setup_integration: SetupIntegration, calls: Calls
) -> None:
    await setup_integration(
        mode_config(
            variables={"factor": 3, "label": "x"},
            turn_on=[{"action": "test.turn_on", "data": {"label": "{{ label }}"}}],
            set_humidity=[
                {
                    "action": "test.set_humidity",
                    "data": {"humidity": "{{ humidity * factor }}"},
                }
            ],
            set_mode=[
                {"action": "test.set_mode", "data": {"mode": "{{ mode ~ label }}"}}
            ],
        )
    )
    for service, data in (
        (SERVICE_TURN_ON, {}),
        (SERVICE_SET_HUMIDITY, {"humidity": 45}),
        ("set_mode", {ATTR_MODE: "quiet"}),
    ):
        _ = await hass.services.async_call(
            HUMIDIFIER_DOMAIN, service, {**TARGET_ENTITY, **data}, blocking=True
        )

    assert calls.turn_on[0].data["label"] == "x"
    assert calls.set_humidity[0].data["humidity"] == 135
    assert calls.set_mode[0].data["mode"] == "quietx"


async def test_variables_can_be_templates(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(
        entity_config(
            variables={"base": "{{ 40 + 10 }}", "kind": "{{ 'idle' }}"},
            target_humidity="{{ base }}",
            action="{{ kind }}",
            state="{{ true }}",
        )
    )

    state = get_state(hass)
    assert state.attributes["humidity"] == 50
    assert state.attributes["action"] == "idle"


async def test_section_variables_are_handed_to_every_entity(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(
        entity_config(target_humidity="{{ shared }}"),
        entity_config(
            name="Bedroom", unique_id="bedroom", target_humidity="{{ shared + 1 }}"
        ),
        variables={"shared": 45},
    )

    assert get_state(hass).attributes["humidity"] == 45
    assert get_state(hass, "humidifier.bedroom").attributes["humidity"] == 46


async def test_entity_variables_win_over_section_variables(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(
        entity_config(
            variables={"shared": 50},
            target_humidity="{{ shared + extra }}",
        ),
        variables={"shared": 45, "extra": 1},
    )

    assert get_state(hass).attributes["humidity"] == 51


async def test_section_variables_reach_the_actions(
    hass: HomeAssistant, setup_integration: SetupIntegration, calls: Calls
) -> None:
    await setup_integration(
        entity_config(
            turn_on=[{"action": "test.turn_on", "data": {"v": "{{ shared }}"}}]
        ),
        variables={"shared": "from-section"},
    )

    _ = await hass.services.async_call(
        HUMIDIFIER_DOMAIN, SERVICE_TURN_ON, TARGET_ENTITY, blocking=True
    )

    assert calls.turn_on[0].data["v"] == "from-section"


async def test_an_undefined_variable_leaves_the_state_unknown(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await setup_integration(entity_config(state="{{ missing_variable }}"))

    assert get_state(hass).state == STATE_UNKNOWN
    assert "state" in caplog.text


async def test_a_variable_that_cannot_render_skips_only_its_entity(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    # Variables are rendered before the entity has an entity ID, so ``this`` is
    # not available to them.
    broken = entity_config(
        name="Broken", unique_id="broken", variables={"me": "{{ this.entity_id }}"}
    )
    config: ConfigType = {
        DOMAIN: [{"humidifier": [broken, entity_config()]}],
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert hass.states.get("humidifier.broken") is None
    assert get_state(hass).state == "off"
    assert "unique_id: broken could not be created" in caplog.text


async def test_invalid_entity_variables_drop_only_that_entity(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    broken = entity_config(name="Broken", unique_id="broken", variables="not a mapping")
    config: ConfigType = {DOMAIN: [{"humidifier": [broken, entity_config()]}]}

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert hass.states.get("humidifier.broken") is None
    assert get_state(hass).state == "off"
    assert "variables" in caplog.text


async def test_invalid_section_variables_drop_the_section(hass: HomeAssistant) -> None:
    config: ConfigType = {
        DOMAIN: [
            {"humidifier": [entity_config()], "variables": ["not", "a", "mapping"]},
            {"humidifier": [entity_config(name="Bedroom", unique_id="bedroom")]},
        ]
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert hass.states.get(HUMIDIFIER_ID) is None
    assert get_state(hass, "humidifier.bedroom").state == "off"
