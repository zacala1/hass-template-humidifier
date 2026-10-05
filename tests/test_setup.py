"""YAML loading: includes, packages, error isolation, and legacy syntax."""

import json
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from homeassistant import config as hass_config
from homeassistant.const import STATE_OFF
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    patch_yaml_files,  # pyright: ignore[reportUnknownVariableType]
)

from .conftest import DOMAIN, HUMIDIFIER_ID, entity_config

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

ENTITY_YAML = """\
- humidifier:
    - name: "Living Room Dehumidifier"
      unique_id: living_room_dehumidifier
      device_class: dehumidifier
      state: "{{ is_state('switch.dehumidifier_power', 'on') }}"
      current_humidity: "{{ states('sensor.dehumidifier_humidity') }}"
      target_humidity: "{{ states('number.dehumidifier_target') }}"
      turn_on:
        - action: test.turn_on
      turn_off:
        - action: test.turn_off
      set_humidity:
        - action: test.set_humidity
          data:
            humidity: "{{ humidity }}"
"""


async def test_include_file_is_supported(hass: HomeAssistant) -> None:
    files = {
        hass_config.YAML_CONFIG_FILE: f"{DOMAIN}: !include humidifiers.yaml\n",
        "humidifiers.yaml": ENTITY_YAML,
    }
    with patch_yaml_files(files):
        config: ConfigType = await hass_config.async_hass_config_yaml(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            hass
        )

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    state = hass.states.get(HUMIDIFIER_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_packages_merge_into_one_list(hass: HomeAssistant) -> None:
    packages = {
        "pkg_a": {DOMAIN: [{"humidifier": [entity_config()]}]},
        "pkg_b": {
            DOMAIN: [
                {
                    "humidifier": [
                        entity_config(name="Bedroom Dehumidifier", unique_id="bedroom")
                    ]
                }
            ]
        },
    }
    config: ConfigType = {}
    _ = await hass_config.merge_packages_config(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        hass, config, packages
    )

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert hass.states.get(HUMIDIFIER_ID) is not None
    assert hass.states.get("humidifier.bedroom_dehumidifier") is not None


async def test_invalid_entity_does_not_block_other_sections(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    config = {
        DOMAIN: [
            {"humidifier": [entity_config(device_class="fan")]},
            {"humidifier": [entity_config(name="Bedroom", unique_id="bedroom")]},
        ]
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert hass.states.get("humidifier.bedroom") is not None
    assert hass.states.get(HUMIDIFIER_ID) is None
    assert "device_class" in caplog.text


async def test_all_sections_invalid_sets_up_without_entities(
    hass: HomeAssistant,
) -> None:
    config = {
        DOMAIN: [{"humidifier": [entity_config(min_humidity=90, max_humidity=10)]}]
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert not hass.states.async_entity_ids("humidifier")


async def test_invalid_script_skips_only_that_entity(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    broken = entity_config(
        name="Broken",
        unique_id="broken",
        turn_on=[{"device_id": "missing", "domain": "switch", "type": "turn_on"}],
    )
    config = {DOMAIN: [{"humidifier": [broken, entity_config()]}]}

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert hass.states.get(HUMIDIFIER_ID) is not None
    assert hass.states.get("humidifier.broken") is None
    assert "turn_on" in caplog.text


async def test_legacy_platform_syntax_is_reported(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    config = {"humidifier": [{"platform": DOMAIN, **entity_config()}]}

    assert await async_setup_component(hass, "humidifier", config)
    await hass.async_block_till_done()

    assert not hass.states.async_entity_ids("humidifier")
    assert "must be configured under its own template_humidifier key" in caplog.text
    issue = ir.async_get(hass).async_get_issue(
        "homeassistant",
        "platform_integration_no_support_humidifier_template_humidifier",
    )
    assert issue is not None


def test_manifest_matches_domain() -> None:
    manifest = cast(
        "dict[str, object]",
        json.loads(
            Path("custom_components/template_humidifier/manifest.json").read_text(
                "utf-8"
            )
        ),
    )

    assert manifest["domain"] == DOMAIN
    assert manifest["iot_class"] == "local_push"
    assert manifest["requirements"] == []
    assert "humidifier" in cast("list[str]", manifest["dependencies"])
    # Core template helpers are imported, but template itself must not be set up.
    assert "template" in cast("list[str]", manifest["after_dependencies"])
    assert "template" not in cast("list[str]", manifest["dependencies"])


async def test_labelled_domain_keys_are_supported(hass: HomeAssistant) -> None:
    config: ConfigType = {
        DOMAIN: [{"humidifier": [entity_config()]}],
        f"{DOMAIN} bedroom": [
            {"humidifier": [entity_config(name="Bedroom", unique_id="bedroom")]}
        ],
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert hass.states.get(HUMIDIFIER_ID) is not None
    assert hass.states.get("humidifier.bedroom") is not None


async def test_invalid_entity_does_not_drop_its_siblings_in_the_same_list(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    broken = entity_config(name="Broken", unique_id="broken", device_class="fan")
    config: ConfigType = {
        DOMAIN: [{"humidifier": [broken, entity_config(), _bedroom()]}]
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert hass.states.get(HUMIDIFIER_ID) is not None
    assert hass.states.get("humidifier.bedroom") is not None
    assert hass.states.get("humidifier.broken") is None
    assert "device_class" in caplog.text


async def test_invalid_section_shape_is_dropped_but_other_sections_load(
    hass: HomeAssistant,
) -> None:
    config: ConfigType = {
        DOMAIN: [
            {"humidifier": [entity_config()], "sensor": []},
            {"humidifier": [_bedroom()]},
        ]
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert hass.states.get(HUMIDIFIER_ID) is None
    assert hass.states.get("humidifier.bedroom") is not None


def _bedroom() -> ConfigType:
    return entity_config(name="Bedroom", unique_id="bedroom")


@pytest.mark.parametrize(
    ("extra", "expected"),
    [
        ({"default_entity_id": "humidifier.custom"}, "humidifier.custom"),
        ({"unique_id": "uid-1"}, "unique_id: uid-1"),
        ({"unique_id": None, "name": "Named One"}, "Named One"),
    ],
)
async def test_script_errors_name_the_entity_that_failed(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    extra: ConfigType,
    expected: str,
) -> None:
    config = entity_config(
        turn_off=[{"device_id": "missing", "domain": "switch", "type": "turn_off"}],
        **cast("dict[str, object]", extra),
    )
    if config.get("unique_id") is None:
        del config["unique_id"]

    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: [{"humidifier": [config]}]}
    )
    await hass.async_block_till_done()

    assert f"actions of {expected} failed to set up" in caplog.text
    assert not hass.states.async_entity_ids("humidifier")
