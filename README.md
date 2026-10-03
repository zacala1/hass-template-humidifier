# Template Humidifier

[![Validate](https://github.com/zacala1/hass-template-humidifier/actions/workflows/validate.yml/badge.svg)](https://github.com/zacala1/hass-template-humidifier/actions/workflows/validate.yml)

Build a standard Home Assistant **humidifier** or **dehumidifier** entity out of
entities you already have, using the same configuration style as the modern
`template:` integration.

Home Assistant's built-in template integration cannot create `humidifier`
entities. Many devices expose their power, humidity, target and mode as separate
`switch`, `sensor`, `number` and `select` entities. This integration combines
them into one entity that works with the humidifier card, voice assistants and
automations.

Requires Home Assistant 2026.8.3 or newer. This is a **pre-release** (`0.1.0b1`);
see [Limitations](#limitations).

## Installation

### HACS

1. Add this repository as a custom repository of type **Integration**.
2. Download **Template Humidifier**.
3. To receive pre-releases such as `0.1.0b1`, open the repository in HACS, choose
   **Redownload**, and enable **Show beta versions**.
4. Restart Home Assistant.

HACS cannot read private repositories. Until this repository is public, install
it manually.

### Manual

Download `template_humidifier.zip` from a GitHub release, extract it into
`/config/custom_components/template_humidifier`, and restart Home Assistant.
The archive contains the integration files at its root.

## Configuration

Configuration lives in `configuration.yaml` under the `template_humidifier:` key.
If you know the modern `template:` format, the structure is the same: a list of
sections, each with a `humidifier:` list of entities. Only the root key differs.

```yaml
template_humidifier:
  - humidifier:
      - name: "Living Room Dehumidifier"
        unique_id: living_room_dehumidifier
        device_class: dehumidifier

        state: "{{ is_state('switch.dehumidifier_power', 'on') }}"
        current_humidity: "{{ states('sensor.dehumidifier_humidity') }}"
        target_humidity: "{{ states('number.dehumidifier_target') }}"

        min_humidity: 40
        max_humidity: 70
        target_humidity_step: 5

        availability: >
          {{ has_value('switch.dehumidifier_power')
             and has_value('sensor.dehumidifier_humidity') }}

        turn_on:
          - action: switch.turn_on
            target:
              entity_id: switch.dehumidifier_power
        turn_off:
          - action: switch.turn_off
            target:
              entity_id: switch.dehumidifier_power
        set_humidity:
          - action: number.set_value
            target:
              entity_id: number.dehumidifier_target
            data:
              value: "{{ humidity }}"
```

This creates `humidifier.living_room_dehumidifier`.

`!include`, packages and labelled keys such as `template_humidifier living_room:`
work like they do for any other integration. For example:

```yaml
template_humidifier: !include template_humidifiers.yaml
```

### Options

| Option | Required | Description |
| --- | --- | --- |
| `device_class` | yes | `humidifier` or `dehumidifier`. |
| `state` | yes | Template that is true while the device is on. |
| `current_humidity` | yes | Template rendering the measured humidity, 0 to 100. |
| `target_humidity` | yes | Template rendering the target humidity, 0 to 100. |
| `turn_on`, `turn_off` | yes | Actions run by `humidifier.turn_on` and `humidifier.turn_off`. |
| `set_humidity` | yes | Actions run by `humidifier.set_humidity`. |
| `min_humidity` | no | Number or template, default `0`. |
| `max_humidity` | no | Number or template, default `100`. |
| `target_humidity_step` | no | Number or template greater than 0. Unset by default. |
| `availability` | no | Template; the entity is unavailable while it is false. |
| `name` | no | Template, default `Template Humidifier`. |
| `unique_id` | no | Needed to rename, move or disable the entity in the UI. |
| `default_entity_id` | no | Preferred entity ID, for example `humidifier.bedroom`. |
| `icon`, `picture` | no | Templates. |

A section may also have its own `unique_id`, which is used as a prefix for the
unique IDs of its entities.

Actions use the standard Home Assistant action syntax. `set_humidity` receives
the requested value as `humidity`. Every action can use `this`, the entity itself.

### Behaviour

- Templates are tracked through the state machine. Nothing is polled.
- A humidity that is `unknown`, `unavailable`, not a number or outside 0 to 100
  is shown as missing instead of causing an error.
- If the `state` template raises an error the entity becomes unavailable and
  recovers when the template renders again. A failing `availability` template
  leaves the entity available.
- Limits and steps that are numbers are checked when the configuration loads:
  `min_humidity` must not be greater than `max_humidity`, and the step must be
  greater than 0.
- `humidifier.set_humidity` rejects values outside the entity's range before any
  of your actions run.
- Commands do not guess the new state. The entity changes when the source
  entities change.
- Each section is validated on its own, so one mistake does not stop the others.
  Errors are written to the log.

### Moving from other formats

The legacy `humidifier:` / `platform:` style is not supported. Configuring it
logs an error and creates a repair issue pointing to the `template_humidifier:`
key. The old `*_template` option names and `friendly_name` are rejected like in
the modern `template:` integration; use `state`, `availability`, `name` and the
other names above.

## Limitations

- Changes to the YAML need a Home Assistant restart. There is no reload action yet.
- `mode`, `modes`, `set_mode`, `action`, `optimistic`, `variables`, restoring
  state and trigger-based entities are not supported yet. They are rejected
  rather than ignored.
- `state`, `current_humidity` and `target_humidity` are required.

## Development

Home Assistant's test plugin needs Linux. On Windows use WSL.

```bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run basedpyright
uv run pytest --cov --cov-branch
uv run python scripts/build_release.py
```

Releases follow [RELEASE_POLICY.md](RELEASE_POLICY.md). The full requirements are
in [PROJECT_PLAN.md](PROJECT_PLAN.md).

## 한국어 안내

기존 `switch`, `sensor`, `number`, `select` 엔티티를 하나의 표준 가습기/제습기
(`humidifier`) 엔티티로 묶어 주는 통합입니다. 설정 방식은 최신 `template:`
통합과 같고 최상위 키만 `template_humidifier:`입니다. 위의 예시를 그대로
`configuration.yaml`에 넣고 Home Assistant를 재시작하면 됩니다. 현재는
프리릴리즈이며 설정을 바꾸면 재시작이 필요합니다. 모드, 동작 상태,
낙관적 상태, 재로드는 아직 지원하지 않습니다.
