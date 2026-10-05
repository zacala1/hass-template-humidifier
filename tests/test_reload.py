"""The ``template_humidifier.reload`` action."""

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from homeassistant import config as hass_config
from homeassistant.const import SERVICE_RELOAD
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    patch_yaml_files,  # pyright: ignore[reportUnknownVariableType]
)

from .conftest import DOMAIN, HUMIDIFIER_ID, get_state

if TYPE_CHECKING:
    from homeassistant.core import Event, HomeAssistant

BEDROOM_ID = "humidifier.bedroom"


def _yaml(*entities: str) -> str:
    """Return a ``template_humidifier`` YAML document for the given entities."""
    body = "\n".join(entities)
    return f"{DOMAIN}:\n  - humidifier:\n{body}\n"


def _entity(name: str, unique_id: str, extra: str = "") -> str:
    return f"""\
      - name: "{name}"
        unique_id: {unique_id}
        device_class: dehumidifier
        state: "{{{{ is_state('switch.dehumidifier_power', 'on') }}}}"
        current_humidity: "{{{{ states('sensor.dehumidifier_humidity') }}}}"
        target_humidity: "{{{{ states('number.dehumidifier_target') }}}}"
        turn_on: [{{action: test.turn_on}}]
        turn_off: [{{action: test.turn_off}}]
        set_humidity: [{{action: test.set_humidity}}]
{extra}"""


def _assert_removed(hass: HomeAssistant, entity_id: str) -> None:
    """Assert that the integration no longer provides ``entity_id``.

    Home Assistant keeps the state of an entity that still has a registry entry
    and marks it unavailable and restored; only the registry entry can delete it.
    """
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unavailable"
    assert state.attributes["restored"] is True


async def _reload(hass: HomeAssistant, yaml: str | None) -> None:
    """Call the reload action with ``yaml`` as the new ``configuration.yaml``."""
    files = {} if yaml is None else {hass_config.YAML_CONFIG_FILE: yaml}
    with patch_yaml_files(files):
        _ = await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)
    await hass.async_block_till_done()


async def _setup(hass: HomeAssistant, *entities: str) -> None:
    with patch_yaml_files({hass_config.YAML_CONFIG_FILE: _yaml(*entities)}):
        config = await hass_config.async_hass_config_yaml(hass)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
    assert await async_setup_component(hass, DOMAIN, config)  # pyright: ignore[reportUnknownArgumentType]
    await hass.async_block_till_done()


async def test_reload_action_is_registered(hass: HomeAssistant) -> None:
    await _setup(hass, _entity("Living Room Dehumidifier", "living"))

    assert hass.services.has_service(DOMAIN, SERVICE_RELOAD)


async def test_reload_adds_changes_and_removes_entities(hass: HomeAssistant) -> None:
    await _setup(hass, _entity("Living Room Dehumidifier", "living"))
    assert get_state(hass).state == "off"

    await _reload(hass, _yaml(_entity("Bedroom", "bedroom")))

    assert get_state(hass, BEDROOM_ID).state == "off"
    _assert_removed(hass, HUMIDIFIER_ID)


async def test_reload_applies_changed_options(hass: HomeAssistant) -> None:
    await _setup(hass, _entity("Living Room Dehumidifier", "living"))
    assert "target_humidity_step" not in get_state(hass).attributes

    await _reload(
        hass,
        _yaml(
            _entity(
                "Living Room Dehumidifier",
                "living",
                "        target_humidity_step: 2.5\n",
            )
        ),
    )

    assert get_state(hass).attributes["target_humidity_step"] == 2.5


async def test_reload_keeps_the_registry_entry(hass: HomeAssistant) -> None:
    await _setup(hass, _entity("Living Room Dehumidifier", "living"))
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("humidifier", DOMAIN, "living")
    assert entity_id is not None
    _ = registry.async_update_entity(entity_id, new_entity_id="humidifier.renamed")

    await _reload(hass, _yaml(_entity("Living Room Dehumidifier", "living")))

    assert get_state(hass, "humidifier.renamed").state == "off"
    assert hass.states.get(HUMIDIFIER_ID) is None


async def test_reload_tracks_sources_after_reloading(hass: HomeAssistant) -> None:
    await _setup(hass, _entity("Living Room Dehumidifier", "living"))

    await _reload(hass, _yaml(_entity("Living Room Dehumidifier", "living")))
    hass.states.async_set("switch.dehumidifier_power", "on")
    await hass.async_block_till_done()

    assert get_state(hass).state == "on"


async def test_reload_without_the_domain_removes_all_entities(
    hass: HomeAssistant,
) -> None:
    await _setup(hass, _entity("Living Room Dehumidifier", "living"))

    await _reload(hass, "homeassistant:\n")

    _assert_removed(hass, HUMIDIFIER_ID)


async def test_reload_fires_an_event(hass: HomeAssistant) -> None:
    await _setup(hass, _entity("Living Room Dehumidifier", "living"))
    events: list[Event] = async_capture_events(hass, f"event_{DOMAIN}_reloaded")

    await _reload(hass, _yaml(_entity("Living Room Dehumidifier", "living")))

    assert len(events) == 1


async def test_reload_with_an_invalid_section_keeps_the_valid_ones(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    await _setup(hass, _entity("Living Room Dehumidifier", "living"))
    broken = _entity("Broken", "broken").replace(
        "device_class: dehumidifier", "device_class: fan"
    )

    await _reload(hass, _yaml(_entity("Bedroom", "bedroom"), broken))

    assert get_state(hass, BEDROOM_ID).state == "off"
    assert hass.states.get("humidifier.broken") is None
    assert "device_class" in caplog.text


async def test_failed_reload_leaves_existing_entities_untouched(
    hass: HomeAssistant,
) -> None:
    await _setup(hass, _entity("Living Room Dehumidifier", "living"))

    with pytest.raises(HomeAssistantError, match="reload"):
        await _reload(hass, "template_humidifier: [unclosed\n")

    assert get_state(hass).state == "off"


async def test_reload_applies_modes_added_later(hass: HomeAssistant) -> None:
    await _setup(hass, _entity("Living Room Dehumidifier", "living"))
    assert "available_modes" not in get_state(hass).attributes
    modes = (
        "        modes: [auto, quiet]\n"
        "        set_mode: [{action: test.set_mode}]\n"
        "        mode: \"{{ 'quiet' }}\"\n"
    )

    await _reload(hass, _yaml(_entity("Living Room Dehumidifier", "living", modes)))

    attributes = get_state(hass).attributes
    assert attributes["available_modes"] == ["auto", "quiet"]
    assert attributes["mode"] == "quiet"


async def test_reload_stops_when_the_configuration_cannot_be_processed(
    hass: HomeAssistant,
) -> None:
    await _setup(hass, _entity("Living Room Dehumidifier", "living"))
    events: list[Event] = async_capture_events(hass, f"event_{DOMAIN}_reloaded")

    with patch(
        "homeassistant.config.async_process_component_and_handle_errors",
        return_value=None,
    ):
        await _reload(hass, _yaml(_entity("Bedroom", "bedroom")))

    assert get_state(hass).state == "off"
    assert hass.states.get(BEDROOM_ID) is None
    assert not events
