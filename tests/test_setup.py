"""YAML loading: includes, packages, error isolation, and legacy syntax."""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from homeassistant import config as hass_config
from homeassistant.const import STATE_OFF
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import patch_yaml_files

from .conftest import DOMAIN, HUMIDIFIER_ID, SetupIntegration, entity_config

if TYPE_CHECKING:
    import pytest
    from homeassistant.core import HomeAssistant

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


async def test_include_file_is_supported(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    files = {
        hass_config.YAML_CONFIG_FILE: f"{DOMAIN}: !include humidifiers.yaml\n",
        "humidifiers.yaml": ENTITY_YAML,
    }
    with patch_yaml_files(files):
        config = await hass_config.async_hass_config_yaml(hass)

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    state = hass.states.get(HUMIDIFIER_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_packages_merge_into_one_list(hass: HomeAssistant, sources: None) -> None:
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
    config: dict[str, Any] = {}
    await hass_config.merge_packages_config(hass, config, packages)

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert hass.states.get(HUMIDIFIER_ID) is not None
    assert hass.states.get("humidifier.bedroom_dehumidifier") is not None


async def test_invalid_entity_does_not_block_other_sections(
    hass: HomeAssistant,
    sources: None,
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
    hass: HomeAssistant, sources: None
) -> None:
    config = {
        DOMAIN: [{"humidifier": [entity_config(min_humidity=90, max_humidity=10)]}]
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert not hass.states.async_entity_ids("humidifier")


async def test_invalid_script_skips_only_that_entity(
    hass: HomeAssistant,
    sources: None,
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
    sources: None,
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
    manifest = json.loads(
        Path("custom_components/template_humidifier/manifest.json").read_text("utf-8")
    )

    assert manifest["domain"] == DOMAIN
    assert manifest["iot_class"] == "local_push"
    assert manifest["requirements"] == []
    assert "humidifier" in manifest["dependencies"]
