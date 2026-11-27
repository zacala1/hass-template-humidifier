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

Requires Home Assistant 2026.8.3 or newer. It is tested against 2026.8.3 (the
oldest supported) and 2026.9.4, and runs on 2026.11.3 with a real
dehumidifier. It reuses parts of Core's `template` integration, so a new Home
Assistant release can break it; see [Limitations](#limitations).

## Installation

### Marketplace (Home Assistant 2026.11 or newer)

1. Open **Marketplace**, choose **Add from a GitHub link**, and enter
   `https://github.com/zacala1/hass-template-humidifier`.
2. Open **Template Humidifier** and choose **Install**.
3. Add a `template_humidifier:` configuration and restart Home Assistant.

To receive pre-releases, choose **Include pre-releases** in the repository's
menu before installing or updating.

### HACS (older Home Assistant)

1. Add this repository as a custom repository of type **Integration**.
2. Download **Template Humidifier**.
3. To receive pre-releases, open the repository in HACS, choose
   **Redownload**, and enable **Show beta versions**.
4. Restart Home Assistant.

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
| `variables` | no | Values every template and action of the entity can use, see [Variables](#variables). |
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

### Variables

`variables` define values once and use them in every template and action of the
entity. A value can itself be a template.

```yaml
template_humidifier:
  - variables:
      prefix: dehumidifier
    humidifier:
      - name: "Living Room Dehumidifier"
        variables:
          power_entity: "switch.{{ prefix }}_power"
          target_entity: "number.{{ prefix }}_target"
        device_class: dehumidifier
        state: "{{ is_state(power_entity, 'on') }}"
        current_humidity: "{{ states('sensor.dehumidifier_humidity') }}"
        target_humidity: "{{ states(target_entity) }}"
        turn_on:
          - action: switch.turn_on
            target:
              entity_id: "{{ power_entity }}"
        turn_off:
          - action: switch.turn_off
            target:
              entity_id: "{{ power_entity }}"
        set_humidity:
          - action: number.set_value
            target:
              entity_id: "{{ target_entity }}"
            data:
              value: "{{ humidity }}"
```

Variables on the section are handed to every entity in it. An entity's own
variables win. They can be used in all templates, including `availability`,
`name` and `icon`, and in the actions.

A state based entity renders its variables when it starts and its templates use
those values; its actions get them rendered again every time they run. Use them
for entity IDs, names and constants rather than for values that change.

Variables are rendered before the entity has an entity ID, so they cannot use
`this`. An entity whose variables fail to render is skipped with an error in the
log; the other entities are not affected. Templates and actions can still use
`this`.

### Trigger based humidifiers

A section can have `triggers`. The entities of that section then update only
when a trigger fires, using the data of the trigger, in the same way as trigger
based entities of the `template:` integration.

```yaml
template_humidifier:
  - triggers:
      - trigger: mqtt
        topic: dehumidifier/state
    conditions:
      - condition: template
        value_template: "{{ trigger.payload_json is defined }}"
    actions:
      - variables:
          measured: "{{ trigger.payload_json.humidity }}"
    humidifier:
      - name: "Living Room Dehumidifier"
        unique_id: living_room_dehumidifier
        device_class: dehumidifier
        state: "{{ trigger.payload_json.power == 'on' }}"
        current_humidity: "{{ measured }}"
        turn_on:
          - action: mqtt.publish
            data:
              topic: dehumidifier/set
              payload: "on"
        turn_off:
          - action: mqtt.publish
            data:
              topic: dehumidifier/set
              payload: "off"
        set_humidity:
          - action: mqtt.publish
            data:
              topic: dehumidifier/target
              payload: "{{ humidity }}"
```

- `conditions` decide whether an update happens. `actions` run first, and the
  variables they define (for example with a `variables` step, as `measured` above)
  are available to the templates.
- `trigger` is available in the templates. The section's `variables` are rendered
  when the trigger fires and the entity's own `variables` after them. Do not name
  one `humidity` or `mode` if a command also needs the value it is given.
- Until the first trigger fires the entity is unknown. Nothing is rendered before
  that, and the triggers only start once Home Assistant has started.
- If the `state` template fails the entity becomes unavailable and recovers with
  the next trigger. A failing reading becomes missing.
- Commands run with the variables of the last trigger, so they can only use them
  after it has fired once. `set_humidity` and `set_mode` also get `humidity` and
  `mode`.
- [Remembered values](#remembered-values) work the same way and are restored
  before the first trigger.
- YAML reads an unquoted `on`, `off`, `yes` or `no` as a boolean, also as a key.
  Event data written as `on: true` is therefore not found as
  `trigger.event.data.on`. Use another name such as `power`, or quote the key
  (`"on": true`).
- The singular `trigger`, `condition` and `action` keys are not accepted; use
  `triggers`, `conditions` and `actions`. `conditions` and `actions` need
  `triggers`.

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

## Examples

Complete configurations you can copy and edit are in the [`examples`](examples)
folder. Replace the entity IDs with your own.

| File | What it shows |
| --- | --- |
| [`humidifier-simple.yaml`](examples/humidifier-simple.yaml) | The smallest useful humidifier: a switch, a sensor and a number. |
| [`dehumidifier-full.yaml`](examples/dehumidifier-full.yaml) | A dehumidifier built from five entities, with availability, limits and modes that follow the source entities, and `action`. |
| [`command-only-device.yaml`](examples/command-only-device.yaml) | A device that only accepts commands, such as one behind an infrared or radio hub. The entity remembers the last command. |
| [`mqtt-trigger.yaml`](examples/mqtt-trigger.yaml) | A trigger based dehumidifier that updates from MQTT messages. |
| [`shared-variables.yaml`](examples/shared-variables.yaml) | Two devices of one brand sharing section variables. |
| [`packages/bedroom_humidifier.yaml`](examples/packages/bedroom_humidifier.yaml) | One device per file with packages. |
| [`include/configuration.yaml`](examples/include/configuration.yaml) and [`include/template_humidifiers.yaml`](examples/include/template_humidifiers.yaml) | `!include` and the file it includes. |

The tests check every example against the schema and set them up to make sure each
entity is created, so they stay in step with the integration. The MQTT example is
only checked against the schema.

## Reloading

Call the `template_humidifier.reload` action (Developer tools > Actions) after
editing the YAML. It re-reads `configuration.yaml`, removes the existing entities
and creates them again. It fires the `event_template_humidifier_reloaded` event.

- The action only exists once Home Assistant has started with a
  `template_humidifier:` section, so adding the very first one needs a restart.
- An entity you remove from the YAML keeps its registry entry if it has a
  `unique_id`, and Home Assistant shows it as unavailable. Delete it from the
  entity settings. Entities without a `unique_id` disappear.
- Trigger based sections are detached and attached again, so a reload never
  leaves the old triggers running.
- If the YAML cannot be read, the action fails and nothing changes.

## Limitations

- `variables` are not live values. A state based entity renders them when it
  starts (its actions render them again on every run), and a trigger based
  section renders them when its trigger fires.
- It depends on parts of Core's `template` integration that Home Assistant may
  change, so a new Home Assistant release can need a new version of this
  integration.
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

The test plugin pins `pytest`, `pytest-cov` and some of Home Assistant's own
requirements, so `homeassistant`, `pytest-homeassistant-custom-component`,
`pytest` and `pytest-cov` are updated together, by hand, when the supported Home
Assistant version changes. Dependabot ignores them for that reason.

CI runs the tests on the locked Home Assistant version and on newer ones: the
latest stable release (pinned in `.github/workflows/validate.yml`, updated by
hand when a new one comes out) must pass, the newest release including betas
is informational. A weekly run catches Home Assistant changes between pushes.

Releases follow [RELEASE_POLICY.md](RELEASE_POLICY.md). The requirements, and
what has been built so far, are in [PROJECT_PLAN.md](PROJECT_PLAN.md).

## 한국어 안내

기존 `switch`, `sensor`, `number`, `select` 엔티티를 하나의 표준 가습기/제습기
(`humidifier`) 엔티티로 묶어 주는 통합입니다. 설정 방식은 최신 `template:`
통합과 같고 최상위 키만 `template_humidifier:`입니다.

- **예시:** `examples/` 폴더에 바로 고쳐 쓸 수 있는 설정이 있습니다(단순 가습기, 제습기 전체 기능,
  명령 전용 장치, MQTT 트리거, 공유 변수, 패키지, `!include`).
- **설치:** Home Assistant 2026.11 이상은 **Marketplace**에서 **Add from a GitHub
  link**로 이 레포 주소를 넣고 설치합니다. 그보다 오래된 버전은 HACS의 사용자 지정
  저장소(Integration)로 추가합니다. 직접 설치하려면 릴리즈의
  `template_humidifier.zip`을 `/config/custom_components/template_humidifier`에
  풉니다. 어느 방법이든 설정을 넣고 Home Assistant를 재시작하세요.
- **설정:** 위의 예시를 `configuration.yaml`에 넣으면 됩니다. 필수 항목은
  `device_class`와 `turn_on`, `turn_off`, `set_humidity`뿐이고 `state`,
  `current_humidity`, `target_humidity`는 선택입니다.
- **모드와 동작 상태:** `modes`와 `set_mode`를 함께 설정하면 모드를 지원합니다.
  `action`으로 가습/제습/대기/꺼짐 상태를 알려 줄 수 있습니다.
- **기억하는 값:** `state`, `target_humidity`, `mode` 템플릿을 생략하면 마지막
  명령값을 기억하고(`optimistic`) 재시작 후에도 복원합니다.
- **변수:** `variables`로 값을 한 번 정의해 모든 템플릿과 액션에서 씁니다. 변수에서는
  `this`를 쓸 수 없습니다.
- **트리거:** 섹션에 `triggers`를 두면 트리거가 발생할 때만 갱신됩니다. YAML에서
  따옴표 없는 `on`, `off`, `yes`, `no`는 불리언이므로 이벤트 데이터 키로 쓰지 마세요.
- **다시 불러오기:** 설정을 바꾼 뒤 `template_humidifier.reload` 동작을 실행하면
  재시작 없이 반영됩니다. 첫 `template_humidifier:` 섹션을 추가할 때만 재시작이
  필요합니다.
- **지원 버전:** Home Assistant 2026.8.3 이상이 필요합니다. 2026.8.3과 2026.9.4에서
  테스트하고, 2026.11.3에서 실제 제습기로 사용합니다. Core `template` 통합의 일부를
  재사용하므로 새 Home Assistant 버전에서는 이 통합의 새 버전이 필요할 수 있습니다.
