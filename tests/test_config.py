"""Configuration schema contract for the ``template_humidifier`` domain."""

from typing import TYPE_CHECKING, Any

import pytest
import voluptuous as vol
from custom_components.template_humidifier.config import CONFIG_SECTION_SCHEMA
from homeassistant.components.humidifier import HumidifierDeviceClass

from .conftest import EntityConfig, entity_config

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _validate(*entities: EntityConfig, **section: Any) -> dict[str, Any]:  # noqa: ANN401
    return CONFIG_SECTION_SCHEMA({"humidifier": list(entities), **section})


async def test_accepts_full_dehumidifier(hass: HomeAssistant) -> None:
    section = _validate(entity_config())

    [entity] = section["humidifier"]
    assert entity["device_class"] is HumidifierDeviceClass.DEHUMIDIFIER
    assert entity["unique_id"] == "living_room_dehumidifier"


async def test_accepts_humidifier_device_class(hass: HomeAssistant) -> None:
    [entity] = _validate(entity_config(device_class="humidifier"))["humidifier"]

    assert entity["device_class"] is HumidifierDeviceClass.HUMIDIFIER


async def test_device_class_is_case_insensitive(hass: HomeAssistant) -> None:
    [entity] = _validate(entity_config(device_class="Dehumidifier"))["humidifier"]

    assert entity["device_class"] is HumidifierDeviceClass.DEHUMIDIFIER


async def test_single_entity_mapping_is_wrapped_in_a_list(hass: HomeAssistant) -> None:
    section = CONFIG_SECTION_SCHEMA({"humidifier": entity_config()})

    assert len(section["humidifier"]) == 1


async def test_optional_core_keys_follow_core_template_defaults(
    hass: HomeAssistant,
) -> None:
    config = entity_config()
    del config["name"]
    del config["unique_id"]

    [entity] = _validate(config)["humidifier"]

    assert entity["name"].template == "Template Humidifier"
    assert "unique_id" not in entity


async def test_accepts_modern_core_common_keys(hass: HomeAssistant) -> None:
    [entity] = _validate(
        entity_config(
            default_entity_id="humidifier.bedroom",
            icon="mdi:air-humidifier",
            picture="/local/humidifier.png",
            availability="{{ true }}",
        )
    )["humidifier"]

    assert entity["default_entity_id"] == "humidifier.bedroom"
    assert entity["icon"].template == "mdi:air-humidifier"
    assert entity["picture"].template == "/local/humidifier.png"
    assert entity["availability"].template == "{{ true }}"


async def test_rejects_default_entity_id_of_another_domain(
    hass: HomeAssistant,
) -> None:
    with pytest.raises(vol.Invalid, match="default_entity_id"):
        _validate(entity_config(default_entity_id="sensor.bedroom"))


async def test_accepts_section_unique_id(hass: HomeAssistant) -> None:
    section = _validate(entity_config(), unique_id="section")

    assert section["unique_id"] == "section"


@pytest.mark.parametrize(
    "key",
    [
        "device_class",
        "state",
        "current_humidity",
        "target_humidity",
        "turn_on",
        "turn_off",
        "set_humidity",
    ],
)
async def test_rejects_missing_required_key(hass: HomeAssistant, key: str) -> None:
    config = entity_config()
    del config[key]

    with pytest.raises(vol.Invalid, match=key):
        _validate(config)


@pytest.mark.parametrize("device_class", ["fan", "heater", "", None, 3])
async def test_rejects_unknown_device_class(
    hass: HomeAssistant,
    device_class: object,
) -> None:
    with pytest.raises(vol.Invalid, match="device_class"):
        _validate(entity_config(device_class=device_class))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("mode", "{{ 'auto' }}"),
        ("modes", ["auto", "quiet"]),
        ("action", "{{ 'idle' }}"),
        ("set_mode", [{"action": "test.set_mode"}]),
        ("optimistic", True),
        ("variables", {"power": "switch.power"}),
        ("attributes", {"foo": "{{ 1 }}"}),
    ],
)
async def test_rejects_keys_that_are_not_supported_yet(
    hass: HomeAssistant,
    key: str,
    value: object,
) -> None:
    with pytest.raises(vol.Invalid, match=key):
        _validate(entity_config(**{key: value}))


@pytest.mark.parametrize(
    "key",
    [
        "state_template",
        "value_template",
        "availability_template",
        "current_humidity_template",
        "target_humidity_template",
        "turn_on_action",
        "turn_off_action",
        "set_target_humidity_action",
        "friendly_name",
    ],
)
async def test_rejects_legacy_key_names(hass: HomeAssistant, key: str) -> None:
    with pytest.raises(vol.Invalid, match=key):
        _validate(entity_config(**{key: "{{ true }}"}))


@pytest.mark.parametrize(
    ("section_key", "value"),
    [
        ("triggers", [{"trigger": "event", "event_type": "x"}]),
        ("variables", {"a": 1}),
        ("sensor", [{"name": "x", "state": "1"}]),
    ],
)
async def test_rejects_unsupported_section_keys(
    hass: HomeAssistant,
    section_key: str,
    value: object,
) -> None:
    with pytest.raises(vol.Invalid, match=section_key):
        _validate(entity_config(), **{section_key: value})


async def test_rejects_section_without_humidifier(hass: HomeAssistant) -> None:
    with pytest.raises(vol.Invalid, match="humidifier"):
        CONFIG_SECTION_SCHEMA({"unique_id": "only-an-id"})


@pytest.mark.parametrize(
    ("min_humidity", "max_humidity"),
    [(80, 40), (50.5, 50), ("80", "40")],
)
async def test_rejects_static_minimum_above_maximum(
    hass: HomeAssistant,
    min_humidity: object,
    max_humidity: object,
) -> None:
    with pytest.raises(vol.Invalid, match="min_humidity"):
        _validate(entity_config(min_humidity=min_humidity, max_humidity=max_humidity))


@pytest.mark.parametrize(
    ("min_humidity", "max_humidity"),
    [(50, 50), (0, 100), (30.5, 80.5), ("30", "80")],
)
async def test_accepts_static_numeric_range(
    hass: HomeAssistant,
    min_humidity: object,
    max_humidity: object,
) -> None:
    _validate(entity_config(min_humidity=min_humidity, max_humidity=max_humidity))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("min_humidity", -1),
        ("min_humidity", 101),
        ("max_humidity", -1),
        ("max_humidity", 101),
        ("min_humidity", "abc"),
        ("max_humidity", True),
    ],
)
async def test_rejects_static_limits_that_are_not_valid_humidity(
    hass: HomeAssistant,
    key: str,
    value: object,
) -> None:
    config = entity_config(min_humidity=0, max_humidity=100)
    config[key] = value

    with pytest.raises(vol.Invalid, match=key):
        _validate(config)


@pytest.mark.parametrize("step", [0, -5, 0.0, "abc", 101])
async def test_rejects_invalid_static_step(hass: HomeAssistant, step: object) -> None:
    with pytest.raises(vol.Invalid, match="target_humidity_step"):
        _validate(entity_config(target_humidity_step=step))


async def test_accepts_templates_for_limits_and_step(hass: HomeAssistant) -> None:
    [entity] = _validate(
        entity_config(
            min_humidity="{{ state_attr('number.t', 'min') }}",
            max_humidity="{{ state_attr('number.t', 'max') }}",
            target_humidity_step="{{ state_attr('number.t', 'step') }}",
        )
    )["humidifier"]

    assert not entity["min_humidity"].is_static
    assert not entity["max_humidity"].is_static
    assert not entity["target_humidity_step"].is_static


async def test_template_limit_is_not_compared_with_static_limit(
    hass: HomeAssistant,
) -> None:
    _validate(entity_config(min_humidity=90, max_humidity="{{ states('number.t') }}"))


async def test_rejects_malformed_template(hass: HomeAssistant) -> None:
    with pytest.raises(vol.Invalid, match="state"):
        _validate(entity_config(state="{{ is_state('a', 'on' }}"))


async def test_rejects_malformed_action(hass: HomeAssistant) -> None:
    with pytest.raises(vol.Invalid, match="turn_on"):
        _validate(entity_config(turn_on=[{"not_an_action": 1}]))
