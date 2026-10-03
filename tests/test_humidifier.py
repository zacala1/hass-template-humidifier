"""State mapping and dependency tracking of the template humidifier."""

from typing import TYPE_CHECKING

import pytest
from homeassistant.components.humidifier import (
    DATA_COMPONENT,
    HumidifierDeviceClass,
)
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers import entity_registry as er

from .conftest import (
    DOMAIN,
    HUMIDIFIER_ID,
    HUMIDITY,
    POWER,
    TARGET,
    SetupIntegration,
    entity_config,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def test_creates_humidifier_entity(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(entity_config())

    state = hass.states.get(HUMIDIFIER_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["friendly_name"] == "Living Room Dehumidifier"
    assert state.attributes["device_class"] == HumidifierDeviceClass.DEHUMIDIFIER


async def test_maps_properties_to_attributes(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(entity_config())

    attributes = hass.states.get(HUMIDIFIER_ID).attributes  # type: ignore[union-attr]
    assert attributes["current_humidity"] == 57
    assert attributes["humidity"] == 50
    assert attributes["min_humidity"] == 40
    assert attributes["max_humidity"] == 70
    assert attributes["target_humidity_step"] == 5
    assert "available_modes" not in attributes
    assert "mode" not in attributes
    assert "action" not in attributes


async def test_humidifier_device_class(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(entity_config(device_class="humidifier"))

    state = hass.states.get(HUMIDIFIER_ID)
    assert state is not None
    assert state.attributes["device_class"] == HumidifierDeviceClass.HUMIDIFIER


async def test_tracks_source_state_changes(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(entity_config())

    hass.states.async_set(POWER, "on")
    hass.states.async_set(HUMIDITY, "61.5")
    hass.states.async_set(TARGET, "45")
    await hass.async_block_till_done()

    state = hass.states.get(HUMIDIFIER_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["current_humidity"] == 61.5
    assert state.attributes["humidity"] == 45

    hass.states.async_set(POWER, "off")
    await hass.async_block_till_done()

    state = hass.states.get(HUMIDIFIER_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_entity_does_not_poll(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(entity_config())

    entity = hass.data[DATA_COMPONENT].get_entity(HUMIDIFIER_ID)
    assert entity is not None
    assert entity.should_poll is False


@pytest.mark.parametrize(
    "value", ["unknown", "unavailable", "none", "abc", "-1", "101"]
)
async def test_invalid_current_humidity_becomes_none(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    value: str,
) -> None:
    await setup_integration(entity_config())

    hass.states.async_set(HUMIDITY, value)
    await hass.async_block_till_done()

    state = hass.states.get(HUMIDIFIER_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert "current_humidity" not in state.attributes


async def test_invalid_target_humidity_becomes_none(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(entity_config())

    hass.states.async_set(TARGET, "unavailable")
    await hass.async_block_till_done()

    state = hass.states.get(HUMIDIFIER_ID)
    assert state is not None
    assert "humidity" not in state.attributes
    assert state.attributes["current_humidity"] == 57


async def test_numeric_template_error_becomes_none(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(
        entity_config(current_humidity=f"{{{{ states('{HUMIDITY}') | float }}}}")
    )
    assert hass.states.get(HUMIDIFIER_ID).attributes["current_humidity"] == 57  # type: ignore[union-attr]

    hass.states.async_set(HUMIDITY, "unavailable")
    await hass.async_block_till_done()

    state = hass.states.get(HUMIDIFIER_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert "current_humidity" not in state.attributes


@pytest.mark.parametrize("value", ["unknown", "unavailable", "maybe"])
async def test_unusable_state_result_is_unknown(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    value: str,
) -> None:
    await setup_integration(entity_config(state=f"{{{{ states('{POWER}') }}}}"))

    hass.states.async_set(POWER, value)
    await hass.async_block_till_done()

    assert hass.states.get(HUMIDIFIER_ID).state == STATE_UNKNOWN  # type: ignore[union-attr]


async def test_state_template_error_makes_entity_unavailable_and_recovers(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(
        entity_config(state=f"{{{{ (states('{HUMIDITY}') | float) > 50 }}}}")
    )
    assert hass.states.get(HUMIDIFIER_ID).state == STATE_ON  # type: ignore[union-attr]

    hass.states.async_set(HUMIDITY, "unavailable")
    await hass.async_block_till_done()
    assert hass.states.get(HUMIDIFIER_ID).state == STATE_UNAVAILABLE  # type: ignore[union-attr]

    hass.states.async_set(HUMIDITY, "40")
    await hass.async_block_till_done()
    assert hass.states.get(HUMIDIFIER_ID).state == STATE_OFF  # type: ignore[union-attr]


async def test_limits_and_step_follow_templates(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    hass.states.async_set(TARGET, "50", {"min": 35, "max": 65, "step": 2.5})
    await setup_integration(
        entity_config(
            min_humidity="{{ state_attr('number.dehumidifier_target', 'min') }}",
            max_humidity="{{ state_attr('number.dehumidifier_target', 'max') }}",
            target_humidity_step=(
                "{{ state_attr('number.dehumidifier_target', 'step') }}"
            ),
        )
    )

    attributes = hass.states.get(HUMIDIFIER_ID).attributes  # type: ignore[union-attr]
    assert (attributes["min_humidity"], attributes["max_humidity"]) == (35, 65)
    assert attributes["target_humidity_step"] == 2.5

    hass.states.async_set(TARGET, "50", {"min": 30, "max": 80, "step": 5})
    await hass.async_block_till_done()

    attributes = hass.states.get(HUMIDIFIER_ID).attributes  # type: ignore[union-attr]
    assert (attributes["min_humidity"], attributes["max_humidity"]) == (30, 80)
    assert attributes["target_humidity_step"] == 5


async def test_unusable_limits_fall_back_to_defaults(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(
        entity_config(
            min_humidity="{{ state_attr('number.dehumidifier_target', 'min') }}",
            max_humidity=(
                "{{ state_attr('number.dehumidifier_target', 'max') | float }}"
            ),
            target_humidity_step="{{ 0 }}",
        )
    )

    attributes = hass.states.get(HUMIDIFIER_ID).attributes  # type: ignore[union-attr]
    assert attributes["min_humidity"] == 0
    assert attributes["max_humidity"] == 100
    assert "target_humidity_step" not in attributes


async def test_limits_default_when_omitted(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    config = entity_config()
    for key in ("min_humidity", "max_humidity", "target_humidity_step"):
        del config[key]
    await setup_integration(config)

    attributes = hass.states.get(HUMIDIFIER_ID).attributes  # type: ignore[union-attr]
    assert attributes["min_humidity"] == 0
    assert attributes["max_humidity"] == 100
    assert "target_humidity_step" not in attributes


async def test_unique_id_registers_entity_and_section_prefix(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(entity_config(), unique_id="section")

    registry = er.async_get(hass)
    assert (
        registry.async_get_entity_id(
            "humidifier", DOMAIN, "section-living_room_dehumidifier"
        )
        == HUMIDIFIER_ID
    )


async def test_unique_id_without_section_prefix(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(entity_config())

    registry = er.async_get(hass)
    assert (
        registry.async_get_entity_id("humidifier", DOMAIN, "living_room_dehumidifier")
        == HUMIDIFIER_ID
    )


async def test_entity_without_unique_id_is_not_registered(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    config = entity_config()
    del config["unique_id"]
    await setup_integration(config)

    assert hass.states.get(HUMIDIFIER_ID) is not None
    assert not er.async_get(hass).entities


async def test_default_entity_id_selects_entity_id(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(entity_config(default_entity_id="humidifier.bedroom"))

    state = hass.states.get("humidifier.bedroom")
    assert state is not None
    assert state.attributes["friendly_name"] == "Living Room Dehumidifier"
    assert hass.states.get(HUMIDIFIER_ID) is None


async def test_icon_and_picture_templates(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(
        entity_config(
            icon=(
                f"{{% if is_state('{POWER}', 'on') %}}mdi:air-humidifier"
                "{% else %}mdi:air-humidifier-off{% endif %}"
            ),
            picture="/local/dehumidifier.png",
        )
    )
    state = hass.states.get(HUMIDIFIER_ID)
    assert state is not None
    assert state.attributes["icon"] == "mdi:air-humidifier-off"
    assert state.attributes["entity_picture"] == "/local/dehumidifier.png"

    hass.states.async_set(POWER, "on")
    await hass.async_block_till_done()

    state = hass.states.get(HUMIDIFIER_ID)
    assert state is not None
    assert state.attributes["icon"] == "mdi:air-humidifier"


async def test_multiple_entities_are_independent(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    broken = entity_config(
        name="Broken",
        unique_id="broken",
        state="{{ 1 / 0 }}",
        current_humidity="{{ nonsense() }}",
    )
    await setup_integration(entity_config(), broken)

    good = hass.states.get(HUMIDIFIER_ID)
    bad = hass.states.get("humidifier.broken")
    assert good is not None
    assert good.state == STATE_OFF
    assert bad is not None
    assert bad.state == STATE_UNAVAILABLE


async def test_removing_entity_stops_tracking(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration(entity_config())
    registry = er.async_get(hass)
    registry.async_remove(HUMIDIFIER_ID)
    await hass.async_block_till_done()
    assert hass.states.get(HUMIDIFIER_ID) is None

    hass.states.async_set(POWER, "on")
    await hass.async_block_till_done()

    assert hass.states.get(HUMIDIFIER_ID) is None
