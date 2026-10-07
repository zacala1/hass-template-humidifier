"""The example configurations in ``examples/`` stay valid and create their entities."""

from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from custom_components.template_humidifier.config import CONFIG_SECTION_SCHEMA
from homeassistant.const import ATTR_ENTITY_ID, ATTR_MODE
from homeassistant.helpers import config_validation as cv
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml import (
    load_yaml,  # pyright: ignore[reportUnknownVariableType]
)
from pytest_homeassistant_custom_component.common import async_mock_service

from .conftest import DOMAIN, get_state

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = ROOT / "examples"
EXAMPLES = sorted(EXAMPLES_DIR.rglob("*.yaml"))
IDS = [path.relative_to(EXAMPLES_DIR).as_posix() for path in EXAMPLES]
# Its trigger needs the MQTT integration, which these tests do not set up.
NEEDS_MQTT = {"mqtt-trigger.yaml"}


def _sections(path: Path) -> list[ConfigType]:
    """Return the sections of an example, following any ``!include``."""
    raw = cast("object", load_yaml(path))
    if isinstance(raw, dict):
        raw = cast("object", cast("ConfigType", raw)[DOMAIN])
    return cast("list[ConfigType]", cv.ensure_list(raw))


def _entity_count(sections: list[ConfigType]) -> int:
    return sum(len(cast("list[object]", section["humidifier"])) for section in sections)


def test_the_examples_are_found() -> None:
    assert len(EXAMPLES) >= 8


@pytest.mark.parametrize("path", EXAMPLES, ids=IDS)
async def test_example_is_valid_configuration(path: Path) -> None:
    sections = _sections(path)

    assert sections
    for section in sections:
        validated = cast("ConfigType", CONFIG_SECTION_SCHEMA(section))
        assert validated["humidifier"]


@pytest.mark.parametrize("path", EXAMPLES, ids=IDS)
async def test_example_creates_every_entity(hass: HomeAssistant, path: Path) -> None:
    if path.name in NEEDS_MQTT:
        pytest.skip("needs the MQTT integration")
    sections = _sections(path)

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: sections})
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids("humidifier")) == _entity_count(sections)


def test_the_readme_lists_every_example() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for path in EXAMPLES:
        relative = path.relative_to(ROOT).as_posix()
        assert relative in readme, relative


# --- the templates of the main examples do what their comments say ------------


async def _set_up(hass: HomeAssistant, name: str) -> None:
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: _sections(EXAMPLES_DIR / name)}
    )
    await hass.async_block_till_done()


def _set_dehumidifier_sources(
    hass: HomeAssistant, target_attributes: dict[str, object]
) -> None:
    hass.states.async_set("switch.dehumidifier_power", "on")
    hass.states.async_set("sensor.dehumidifier_humidity", "54")
    hass.states.async_set("number.dehumidifier_target", "50", target_attributes)
    hass.states.async_set(
        "select.dehumidifier_mode",
        "quiet",
        {"options": ["auto", "quiet", "laundry"]},
    )
    hass.states.async_set("binary_sensor.dehumidifier_compressor", "on")


async def test_full_dehumidifier_follows_its_source_entities(
    hass: HomeAssistant,
) -> None:
    _set_dehumidifier_sources(hass, {"min": 35, "max": 75, "step": 2.5})
    await _set_up(hass, "dehumidifier-full.yaml")

    state = get_state(hass, "humidifier.living_room_dehumidifier")
    assert state.state == "on"
    assert state.attributes["current_humidity"] == 54
    assert state.attributes["humidity"] == 50
    assert (state.attributes["min_humidity"], state.attributes["max_humidity"]) == (
        35,
        75,
    )
    assert state.attributes["target_humidity_step"] == 2.5
    assert state.attributes["mode"] == "quiet"
    assert state.attributes["available_modes"] == ["auto", "quiet", "laundry"]
    assert state.attributes["action"] == "drying"


async def test_full_dehumidifier_uses_its_defaults_and_goes_unavailable(
    hass: HomeAssistant,
) -> None:
    _set_dehumidifier_sources(hass, {})
    await _set_up(hass, "dehumidifier-full.yaml")

    attributes = get_state(hass, "humidifier.living_room_dehumidifier").attributes
    assert (attributes["min_humidity"], attributes["max_humidity"]) == (30, 80)
    assert attributes["target_humidity_step"] == 5

    hass.states.async_set("sensor.dehumidifier_humidity", "unavailable")
    await hass.async_block_till_done()
    state = get_state(hass, "humidifier.living_room_dehumidifier")
    assert state.state == "unavailable"


async def test_full_dehumidifier_sends_its_commands_to_the_source_entities(
    hass: HomeAssistant,
) -> None:
    _set_dehumidifier_sources(hass, {})
    number = async_mock_service(hass, "number", "set_value")
    select = async_mock_service(hass, "select", "select_option")
    switch = async_mock_service(hass, "switch", "turn_off")
    await _set_up(hass, "dehumidifier-full.yaml")
    target = {ATTR_ENTITY_ID: "humidifier.living_room_dehumidifier"}

    for service, data in (
        ("set_humidity", {"humidity": 55}),
        ("set_mode", {ATTR_MODE: "laundry"}),
        ("turn_off", {}),
    ):
        _ = await hass.services.async_call(
            "humidifier", service, {**target, **data}, blocking=True
        )

    assert (number[0].data["entity_id"], number[0].data["value"]) == (
        ["number.dehumidifier_target"],
        55,
    )
    assert (select[0].data["entity_id"], select[0].data["option"]) == (
        ["select.dehumidifier_mode"],
        "laundry",
    )
    assert switch[0].data["entity_id"] == ["switch.dehumidifier_power"]


async def test_command_only_device_remembers_and_sends_commands(
    hass: HomeAssistant,
) -> None:
    sent = async_mock_service(hass, "remote", "send_command")
    hass.states.async_set("sensor.nursery_humidity", "47")
    await _set_up(hass, "command-only-device.yaml")
    target = {ATTR_ENTITY_ID: "humidifier.nursery_humidifier"}
    assert get_state(hass, "humidifier.nursery_humidifier").state == "unknown"

    for service, data in (
        ("turn_on", {}),
        ("set_humidity", {"humidity": 50}),
        ("set_mode", {ATTR_MODE: "high"}),
    ):
        _ = await hass.services.async_call(
            "humidifier", service, {**target, **data}, blocking=True
        )

    assert [call.data["command"] for call in sent] == [
        "power_on",
        "target_50",
        "mode_high",
    ]
    state = get_state(hass, "humidifier.nursery_humidifier")
    assert state.state == "on"
    assert state.attributes["humidity"] == 50
    assert state.attributes["mode"] == "high"
    assert state.attributes["current_humidity"] == 47


async def test_shared_variables_example_builds_the_right_entity_ids(
    hass: HomeAssistant,
) -> None:
    on = async_mock_service(hass, "switch", "turn_on")
    hass.states.async_set("switch.acme_bedroom_power", "on")
    hass.states.async_set("sensor.acme_bedroom_humidity", "61")
    hass.states.async_set("number.acme_bedroom_target", "45")
    hass.states.async_set("switch.acme_study_power", "off")
    await _set_up(hass, "shared-variables.yaml")

    bedroom = get_state(hass, "humidifier.bedroom_dehumidifier")
    assert bedroom.state == "on"
    assert bedroom.attributes["current_humidity"] == 61
    assert bedroom.attributes["humidity"] == 45
    assert get_state(hass, "humidifier.study_dehumidifier").state == "off"

    _ = await hass.services.async_call(
        "humidifier",
        "turn_on",
        {ATTR_ENTITY_ID: "humidifier.study_dehumidifier"},
        blocking=True,
    )
    assert on[0].data["entity_id"] == ["switch.acme_study_power"]
