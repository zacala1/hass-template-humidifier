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

Requires Home Assistant 2026.8.3 or newer. This is a **pre-release**; see
[Limitations](#limitations).

## Installation

### HACS

1. Add this repository as a custom repository of type **Integration**.
2. Download **Template Humidifier**.
3. To receive pre-releases such as `0.3.0b1`, open the repository in HACS, choose
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
| `state` | no | Template that is true while the device is on. Without it the power is [remembered](#remembered-values). |
| `current_humidity` | no | Template rendering the measured humidity, 0 to 100. |
| `target_humidity` | no | Template rendering the target humidity, 0 to 100. Without it the target is remembered. |
| `turn_on`, `turn_off` | yes | Actions run by `humidifier.turn_on` and `humidifier.turn_off`. |
| `set_humidity` | yes | Actions run by `humidifier.set_humidity`. |
| `mode` | no | Template rendering the current mode. Needs `modes`. |
| `modes` | no | List of mode names, or a template rendering a list. Needs `set_mode`. |
| `set_mode` | no | Actions run by `humidifier.set_mode`. Needs `modes`. |
| `action` | no | Template rendering what the device is doing, see [Action](#action). |
| `optimistic` | no | `true` remembers every command result, `false` never assumes the power. See [Remembered values](#remembered-values). |
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
the requested value as `humidity` and `set_mode` the requested mode as `mode`.
Every action can use `this`, the entity itself.

### Modes

Configure `modes` and `set_mode` together and the entity supports modes. Without
them it does not expose any mode controls.

```yaml
        mode: "{{ states('select.dehumidifier_mode') }}"
        modes:
          - auto
          - quiet
          - laundry
        set_mode:
          - action: select.select_option
            target:
              entity_id: select.dehumidifier_mode
            data:
              option: "{{ mode }}"
```

`modes` can also be a template, for example
`"{{ state_attr('select.dehumidifier_mode', 'options') }}"`, so the list follows
the source entity. A `mode` that is not in the list is shown as missing, and a
`modes` template that does not render a list gives an empty list.

`humidifier.set_mode` rejects a mode that is not in the list before any of your
actions run. `mode` is optional; without it the current mode is not known.

### Action

`action` reports what the device is doing: `humidifying`, `drying`, `idle` or
`off`. Case and surrounding spaces are ignored and anything else is dropped with
an error in the log. Home Assistant shows `off` while the entity is off.

```yaml
        action: >
          {% if is_state('switch.dehumidifier_power', 'off') %}off
          {% elif is_state('binary_sensor.dehumidifier_compressor', 'on') %}drying
          {% else %}idle{% endif %}
```

### Remembered values

Some devices only accept commands and report nothing back. Leave out the
template and the entity remembers what you last told it:

| Missing | The entity remembers |
| --- | --- |
| `state` | `turn_on` and `turn_off`. The entity is shown as *assumed*; before any command its state is unknown. |
| `target_humidity` | the last `set_humidity` value |
| `mode` (with `modes`) | the last `set_mode` value |

A value is remembered only after its actions succeed. If they fail, the error
reaches you and nothing changes.

`optimistic: true` does the same for all three even when templates exist: the
command's value is shown at once and the template takes over the next time it
changes. `optimistic: false` stops the power from being assumed when `state` is
missing, so it stays unknown. The target and the mode are still remembered when
their templates are missing, because nothing else could provide them.

Remembered values survive restarts and reloads. A value from a template always
wins over a restored one. A restored target outside the current limits, or a
restored mode that is not in the list, is ignored. A remembered mode that
disappears from a `modes` template is dropped.

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
- A command only changes the entity when the value is remembered (see above).
  Otherwise the entity changes when the source entities change.
- Every entity is validated on its own, so one mistake does not stop the others,
  not even the ones in the same list. Errors are written to the log. A mistake in
  the shape of a section, such as an unknown key, drops that whole section.

### Moving from other formats

The legacy `humidifier:` / `platform:` style is not supported. Configuring it
logs an error and creates a repair issue pointing to the `template_humidifier:`
key. The old `*_template` option names and `friendly_name` are rejected like in
the modern `template:` integration; use `state`, `availability`, `name` and the
other names above.

## Reloading

Call the `template_humidifier.reload` action (Developer tools > Actions) after
editing the YAML. It re-reads `configuration.yaml`, removes the existing entities
and creates them again. It fires the `event_template_humidifier_reloaded` event.

- The action only exists once Home Assistant has started with a
  `template_humidifier:` section, so adding the very first one needs a restart.
- An entity you remove from the YAML keeps its registry entry if it has a
  `unique_id`, and Home Assistant shows it as unavailable. Delete it from the
  entity settings. Entities without a `unique_id` disappear.
- If the YAML cannot be read, the action fails and nothing changes.

## Limitations

- `variables` and trigger-based entities are not supported yet. They are
  rejected rather than ignored.
- With a `state` template and no `optimistic`, `turn_on` and `turn_off` do not
  change the entity by themselves; it follows the source entities.
- A `mode` template that was valid when it rendered is not checked again if only
  the `modes` template changes later; it is corrected the next time `mode`
  renders. A remembered mode is checked at once.

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
`configuration.yaml`에 넣고 Home Assistant를 재시작하면 됩니다. 모드
(`mode`/`modes`/`set_mode`)와 동작 상태(`action`)를 지원하고, 설정을 바꾼 뒤에는
`template_humidifier.reload` 동작으로 재시작 없이 다시 불러올 수 있습니다.
`state`, `target_humidity`, `mode` 템플릿을 생략하면 마지막 명령값을 기억하고
(`optimistic`), 재시작 후에도 복원합니다. 현재는 프리릴리즈입니다.
