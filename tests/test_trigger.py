"""Humidifiers whose templates are rendered each time a trigger fires."""

from typing import TYPE_CHECKING

import pytest
from homeassistant.components.humidifier.const import (
    DOMAIN as HUMIDIFIER_DOMAIN,
    SERVICE_SET_HUMIDITY,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_MODE,
    EVENT_HOMEASSISTANT_START,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CoreState, State
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    async_mock_service,
    mock_restore_cache_with_extra_data,
)

from .conftest import (
    DOMAIN,
    HUMIDIFIER_ID,
    Calls,
    entity_config,
    get_state,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

EVENT = "humidifier_test_event"
TRIGGERS = [{"trigger": "event", "event_type": EVENT}]
TARGET_ENTITY = {ATTR_ENTITY_ID: HUMIDIFIER_ID}


def event_entity(**overrides: object) -> ConfigType:
    """An entity whose readings come from the data of the triggering event."""
    return entity_config(
        **{
            "state": "{{ trigger.event.data.on }}",
            "current_humidity": "{{ trigger.event.data.humidity }}",
            "target_humidity": "{{ trigger.event.data.target }}",
            **overrides,
        }
    )


def section(*entities: ConfigType, **extra: object) -> ConfigType:
    """A trigger based section holding ``entities``."""
    return {"triggers": TRIGGERS, "humidifier": list(entities), **extra}


async def setup(hass: HomeAssistant, *sections: ConfigType) -> None:
    """Set the integration up with the given sections."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: list(sections)})
    await hass.async_block_till_done()


async def fire(hass: HomeAssistant, **data: object) -> None:
    """Fire the event the triggers listen to and let everything settle."""
    hass.bus.async_fire(EVENT, data)
    await hass.async_block_till_done()


# --- rendering ---------------------------------------------------------------


async def test_entity_is_unknown_until_the_trigger_fires(hass: HomeAssistant) -> None:
    await setup(hass, section(event_entity()))

    state = get_state(hass)
    assert state.state == STATE_UNKNOWN
    assert "current_humidity" not in state.attributes


async def test_trigger_data_updates_the_entity(hass: HomeAssistant) -> None:
    await setup(hass, section(event_entity()))

    await fire(hass, on=True, humidity=57, target=50)
    state = get_state(hass)
    assert state.state == STATE_ON
    assert state.attributes["current_humidity"] == 57
    assert state.attributes["humidity"] == 50
    assert state.attributes["min_humidity"] == 40
    assert state.attributes["target_humidity_step"] == 5

    await fire(hass, on=False, humidity=61.5, target=45)
    state = get_state(hass)
    assert state.state == STATE_OFF
    assert state.attributes["current_humidity"] == 61.5
    assert state.attributes["humidity"] == 45


@pytest.mark.parametrize("value", ["unknown", "unavailable", "abc", 150, -3])
async def test_unusable_readings_become_none(
    hass: HomeAssistant, value: object
) -> None:
    await setup(hass, section(event_entity()))

    await fire(hass, on=True, humidity=value, target=value)

    state = get_state(hass)
    assert state.state == STATE_ON
    assert "current_humidity" not in state.attributes
    assert "humidity" not in state.attributes


async def test_limits_and_the_step_follow_the_trigger(hass: HomeAssistant) -> None:
    await setup(
        hass,
        section(
            event_entity(
                min_humidity="{{ trigger.event.data.low }}",
                max_humidity="{{ trigger.event.data.high }}",
                target_humidity_step="{{ trigger.event.data.step }}",
            )
        ),
    )

    await fire(hass, on=True, low=30, high=80, step=2.5)
    attributes = get_state(hass).attributes
    assert (attributes["min_humidity"], attributes["max_humidity"]) == (30, 80)
    assert attributes["target_humidity_step"] == 2.5

    await fire(hass, on=True, low="x", high=None, step=0)
    attributes = get_state(hass).attributes
    assert (attributes["min_humidity"], attributes["max_humidity"]) == (0, 100)
    assert "target_humidity_step" not in attributes


async def test_the_action_state_follows_the_trigger(hass: HomeAssistant) -> None:
    await setup(hass, section(event_entity(action="{{ trigger.event.data.doing }}")))

    await fire(hass, on=True, doing=" Drying ")
    assert get_state(hass).attributes["action"] == "drying"

    await fire(hass, on=True, doing="cooling")
    assert "action" not in get_state(hass).attributes


async def test_modes_follow_the_trigger(hass: HomeAssistant) -> None:
    await setup(
        hass,
        section(
            event_entity(
                modes="{{ trigger.event.data.options }}",
                mode="{{ trigger.event.data.mode }}",
                set_mode=[{"action": "test.set_mode"}],
            )
        ),
    )

    await fire(hass, on=True, options=["auto", "quiet"], mode="quiet")
    attributes = get_state(hass).attributes
    assert attributes["available_modes"] == ["auto", "quiet"]
    assert attributes["mode"] == "quiet"

    await fire(hass, on=True, options=["auto"], mode="quiet")
    attributes = get_state(hass).attributes
    assert attributes["available_modes"] == ["auto"]
    assert attributes["mode"] is None

    await fire(hass, on=True, options="auto", mode="auto")
    assert get_state(hass).attributes["available_modes"] == []


async def test_static_modes_work_with_a_mode_template(hass: HomeAssistant) -> None:
    await setup(
        hass,
        section(
            event_entity(
                modes=["auto", "quiet"],
                mode="{{ trigger.event.data.mode }}",
                set_mode=[{"action": "test.set_mode"}],
            )
        ),
    )

    await fire(hass, on=True, mode="quiet")

    assert get_state(hass).attributes["mode"] == "quiet"


async def test_one_event_updates_every_entity_of_the_section(
    hass: HomeAssistant,
) -> None:
    await setup(
        hass,
        section(
            event_entity(),
            event_entity(
                name="Bedroom",
                unique_id="bedroom",
                current_humidity="{{ trigger.event.data.humidity + 1 }}",
            ),
        ),
    )

    await fire(hass, on=True, humidity=50, target=45)

    assert get_state(hass).attributes["current_humidity"] == 50
    assert get_state(hass, "humidifier.bedroom").attributes["current_humidity"] == 51


# --- conditions, actions and variables ----------------------------------------


async def test_conditions_decide_whether_the_entity_updates(
    hass: HomeAssistant,
) -> None:
    await setup(
        hass,
        section(
            event_entity(),
            conditions=[
                {
                    "condition": "template",
                    "value_template": "{{ trigger.event.data.ok }}",
                }
            ],
        ),
    )

    await fire(hass, on=True, humidity=50, target=45, ok=False)
    assert get_state(hass).state == STATE_UNKNOWN

    await fire(hass, on=True, humidity=50, target=45, ok=True)
    assert get_state(hass).state == STATE_ON


async def test_actions_run_before_the_entity_renders(hass: HomeAssistant) -> None:
    calls = async_mock_service(hass, "test", "from_trigger")
    await setup(
        hass,
        section(
            event_entity(current_humidity="{{ doubled }}"),
            actions=[
                {"variables": {"doubled": "{{ trigger.event.data.humidity * 2 }}"}},
                {
                    "action": "test.from_trigger",
                    "data": {"seen": "{{ trigger.event.data.humidity }}"},
                },
            ],
        ),
    )

    await fire(hass, on=True, humidity=20, target=45)

    assert get_state(hass).attributes["current_humidity"] == 40
    assert [call.data["seen"] for call in calls] == [20]


async def test_section_variables_are_rendered_for_the_entities(
    hass: HomeAssistant,
) -> None:
    await setup(
        hass,
        section(
            event_entity(
                current_humidity="{{ trigger.event.data.humidity + offset }}",
                target_humidity="{{ trigger.event.data.target + offset }}",
            ),
            variables={"offset": 10},
        ),
    )

    await fire(hass, on=True, humidity=40, target=35)

    attributes = get_state(hass).attributes
    assert attributes["current_humidity"] == 50
    assert attributes["humidity"] == 45


async def test_entity_variables_win_over_section_variables(
    hass: HomeAssistant,
) -> None:
    await setup(
        hass,
        section(
            event_entity(
                variables={"offset": 20, "own": "{{ offset + 1 }}"},
                current_humidity="{{ trigger.event.data.humidity + own }}",
            ),
            variables={"offset": 10, "shared": 1},
        ),
    )

    await fire(hass, on=True, humidity=10, target=45)

    assert get_state(hass).attributes["current_humidity"] == 31


async def test_commands_run_with_the_variables_of_the_last_trigger(
    hass: HomeAssistant, calls: Calls
) -> None:
    await setup(
        hass,
        section(
            event_entity(
                variables={"label": "{{ trigger.event.data.label }}"},
                turn_on=[{"action": "test.turn_on", "data": {"label": "{{ label }}"}}],
            ),
            variables={"shared": "s"},
        ),
    )
    await fire(hass, on=False, humidity=50, target=45, label="from-event")

    _ = await hass.services.async_call(
        HUMIDIFIER_DOMAIN, SERVICE_TURN_ON, TARGET_ENTITY, blocking=True
    )

    assert calls.turn_on[0].data["label"] == "from-event"


async def test_set_humidity_runs_for_a_trigger_entity(
    hass: HomeAssistant, calls: Calls
) -> None:
    await setup(hass, section(event_entity()))
    await fire(hass, on=True, humidity=50, target=45)

    _ = await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {**TARGET_ENTITY, "humidity": 55},
        blocking=True,
    )

    assert calls.set_humidity[0].data["humidity"] == 55
    assert get_state(hass).attributes["humidity"] == 45


# --- availability and errors --------------------------------------------------


async def test_availability_follows_the_trigger(hass: HomeAssistant) -> None:
    await setup(
        hass,
        section(event_entity(availability="{{ trigger.event.data.ok }}")),
    )

    await fire(hass, on=True, humidity=50, target=45, ok=False)
    assert get_state(hass).state == STATE_UNAVAILABLE

    await fire(hass, on=True, humidity=50, target=45, ok=True)
    assert get_state(hass).state == STATE_ON


async def test_a_state_error_makes_the_entity_unavailable_until_it_recovers(
    hass: HomeAssistant,
) -> None:
    await setup(
        hass,
        section(event_entity(state="{{ 1 / trigger.event.data.divisor }}")),
    )

    await fire(hass, divisor=0, humidity=50, target=45)
    assert get_state(hass).state == STATE_UNAVAILABLE

    await fire(hass, divisor=1, humidity=50, target=45)
    assert get_state(hass).state == STATE_ON


async def test_a_reading_error_becomes_none(hass: HomeAssistant) -> None:
    await setup(
        hass,
        section(event_entity(current_humidity="{{ 1 / trigger.event.data.zero }}")),
    )

    await fire(hass, on=True, zero=0, target=45)

    state = get_state(hass)
    assert state.state == STATE_ON
    assert "current_humidity" not in state.attributes


# --- remembered values --------------------------------------------------------


async def test_the_power_is_remembered_when_there_is_no_state_template(
    hass: HomeAssistant,
) -> None:
    config = event_entity()
    del config["state"]
    await setup(hass, section(config))
    assert get_state(hass).attributes["assumed_state"] is True

    _ = await hass.services.async_call(
        HUMIDIFIER_DOMAIN, SERVICE_TURN_ON, TARGET_ENTITY, blocking=True
    )
    assert get_state(hass).state == STATE_ON

    await fire(hass, humidity=50, target=45)
    state = get_state(hass)
    assert state.state == STATE_ON
    assert state.attributes["current_humidity"] == 50


async def test_the_mode_is_remembered_when_there_is_no_mode_template(
    hass: HomeAssistant, calls: Calls
) -> None:
    await setup(
        hass,
        section(
            event_entity(
                modes=["auto", "quiet"], set_mode=[{"action": "test.set_mode"}]
            )
        ),
    )

    _ = await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        "set_mode",
        {**TARGET_ENTITY, ATTR_MODE: "quiet"},
        blocking=True,
    )
    await fire(hass, on=True, humidity=50, target=45)

    assert get_state(hass).attributes["mode"] == "quiet"
    assert len(calls.set_mode) == 1


async def test_remembered_values_are_restored_before_the_first_trigger(
    hass: HomeAssistant,
) -> None:
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(HUMIDIFIER_ID, STATE_ON),
                {"is_on": True, "target_humidity": 55.0, "mode": None},
            )
        ],
    )
    config = event_entity()
    del config["state"]
    del config["target_humidity"]
    await setup(hass, section(config))

    state = get_state(hass)
    assert state.state == STATE_ON
    assert state.attributes["humidity"] == 55


# --- registry and lifecycle --------------------------------------------------


async def test_unique_ids_get_the_section_prefix(hass: HomeAssistant) -> None:
    await setup(hass, section(event_entity(), unique_id="section"))

    registry = er.async_get(hass)
    assert (
        registry.async_get_entity_id(
            "humidifier", DOMAIN, "section-living_room_dehumidifier"
        )
        == HUMIDIFIER_ID
    )


async def test_triggers_attach_when_home_assistant_has_started(
    hass: HomeAssistant,
) -> None:
    hass.set_state(CoreState.not_running)
    await setup(hass, section(event_entity()))

    await fire(hass, on=True, humidity=50, target=45)
    assert get_state(hass).state == STATE_UNKNOWN

    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    await fire(hass, on=True, humidity=50, target=45)

    assert get_state(hass).state == STATE_ON


async def test_state_based_and_trigger_based_sections_work_together(
    hass: HomeAssistant,
) -> None:
    state_based = entity_config(name="Bedroom", unique_id="bedroom")
    await setup(hass, section(event_entity()), {"humidifier": [state_based]})

    await fire(hass, on=True, humidity=50, target=45)

    assert get_state(hass).state == STATE_ON
    assert get_state(hass, "humidifier.bedroom").state == STATE_OFF


async def test_an_invalid_trigger_drops_only_its_section(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    broken = {
        "triggers": [{"trigger": "no_such_trigger_platform"}],
        "humidifier": [event_entity(name="Broken", unique_id="broken")],
    }
    await setup(hass, broken, section(event_entity()))

    assert hass.states.get("humidifier.broken") is None
    assert get_state(hass).state == STATE_UNKNOWN
    assert "template_humidifier" in caplog.text


async def test_an_invalid_condition_drops_only_its_section(
    hass: HomeAssistant,
) -> None:
    broken = section(
        event_entity(name="Broken", unique_id="broken"),
        conditions=[{"condition": "device", "device_id": "missing", "domain": "x"}],
    )
    await setup(hass, broken, section(event_entity()))

    assert hass.states.get("humidifier.broken") is None
    assert get_state(hass).state == STATE_UNKNOWN
