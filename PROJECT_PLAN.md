# Template Humidifier for Home Assistant

## Project Planning & Requirements Specification

---

# 1. 프로젝트 개요

## 1.1 프로젝트명

**Template Humidifier**

Repository 이름 권장:

```text
hass-template-humidifier
```

Home Assistant Custom Integration Domain:

```text
template_humidifier
```

설치 경로:

```text
/config/custom_components/template_humidifier/
```

생성되는 Home Assistant Entity Domain:

```text
humidifier
```

예:

```text
humidifier.living_room_dehumidifier
humidifier.bedroom_humidifier
```

---

# 2. 프로젝트 목적

Home Assistant Core의 최신 `Template Integration`과 가능한 한 동일한 Configuration 스타일과 동작 모델을 사용하면서, Core Template이 제공하지 않는 `humidifier` Entity를 구현한다.

지원 대상은 다음 두 종류를 동등하게 포함한다.

```text
Humidifier
Dehumidifier
```

주요 사용 사례는 기존 Integration이 여러 Entity로 분리해서 제공하는 장치를 하나의 표준 `humidifier` Entity로 재구성하는 것이다.

예:

```text
switch.dehumidifier_power
sensor.dehumidifier_current_humidity
number.dehumidifier_target_humidity
select.dehumidifier_mode
binary_sensor.dehumidifier_compressor
```

↓

```text
humidifier.dehumidifier
├─ Power
├─ Current Humidity
├─ Target Humidity
├─ Target Humidity Step
├─ Mode
├─ Available Modes
└─ Action
```

본 프로젝트는 새로운 제습/가습 제어 알고리즘을 구현하는 것이 아니다.

**이미 Home Assistant에 존재하는 Entity를 표준 HumidifierEntity로 재구성하는 Template Adapter를 구현하는 것이 목적이다.**

---

# 3. 핵심 설계 원칙

## 3.1 Core Template 스타일

Configuration DSL은 최신 Home Assistant Core Template의 naming과 구조를 최대한 따른다.

다음과 같은 legacy naming은 기본 API로 사용하지 않는다.

```text
state_template
availability_template
current_humidity_template
target_humidity_template
turn_on_action
turn_off_action
set_target_humidity_action
```

대신:

```text
state
availability
current_humidity
target_humidity

turn_on
turn_off
set_humidity
set_mode
```

를 사용한다.

즉 다음 원칙을 따른다.

```text
Property → 실제 Entity property 이름
Command  → 실제 Entity action 이름
```

---

## 3.2 독립 Integration Domain

Home Assistant Core의:

```yaml
template:
```

domain을 override, patch 또는 monkey patch하지 않는다.

본 Integration은 독립적인:

```yaml
template_humidifier:
```

domain을 사용한다.

Configuration 구조만 Core Template과 동일하게 설계한다.

HACS 버전:

```yaml
template_humidifier:
  - humidifier:
      ...
```

향후 Home Assistant Core에 upstream될 경우 목표 구조:

```yaml
template:
  - humidifier:
      ...
```

즉 최종적으로 **최상위 domain만 변경하면 나머지 Configuration을 그대로 사용할 수 있는 구조**를 목표로 한다.

---

# 4. Configuration Architecture

사용자 Configuration은 Home Assistant의 표준:

```text
/config/configuration.yaml
```

을 통해 작성한다.

Custom Integration이 `configuration.yaml` 파일을 직접 열거나 자체 YAML parser를 구현하지 않는다.

구조:

```text
/config/configuration.yaml
        │
        ▼
Home Assistant YAML Loader
        │
        ├─ !include 처리
        ├─ packages 처리
        └─ YAML parsing
        │
        ▼
template_humidifier
Configuration Validation
        │
        ▼
TemplateHumidifier Entity 생성
```

---

# 5. 기본 Configuration Syntax

기본 사용법:

```yaml
template_humidifier:
  - humidifier:
      - name: "Living Room Dehumidifier"
        unique_id: living_room_dehumidifier

        device_class: dehumidifier

        state: >
          {{ is_state('switch.dehumidifier_power', 'on') }}

        current_humidity: >
          {{ states('sensor.dehumidifier_current_humidity') | float }}

        target_humidity: >
          {{ states('number.dehumidifier_target_humidity') | float }}

        min_humidity: 40
        max_humidity: 70
        target_humidity_step: 5

        availability: >
          {{
            has_value('switch.dehumidifier_power')
            and has_value('sensor.dehumidifier_current_humidity')
            and has_value('number.dehumidifier_target_humidity')
          }}

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
              entity_id: number.dehumidifier_target_humidity
            data:
              value: "{{ humidity }}"
```

결과:

```text
humidifier.living_room_dehumidifier
```

---

# 6. Include 지원

Home Assistant 기본 YAML include 방식을 그대로 지원해야 한다.

`configuration.yaml`:

```yaml
template_humidifier: !include template_humidifiers.yaml
```

`template_humidifiers.yaml`:

```yaml
- humidifier:
    - name: "Living Room Dehumidifier"
      unique_id: living_room_dehumidifier

      device_class: dehumidifier

      state: >
        {{ is_state('switch.dehumidifier_power', 'on') }}

      current_humidity: >
        {{ states('sensor.dehumidifier_humidity') | float }}

      target_humidity: >
        {{ states('number.dehumidifier_target') | float }}

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

Include 처리를 Integration 내부에서 별도로 구현하지 않는다.

---

# 7. Functional Requirements

---

## FR-001 — Humidifier Entity 생성

Integration은 Configuration 하나당 표준:

```text
HumidifierEntity
```

를 생성해야 한다.

결과 Entity Domain:

```text
humidifier
```

예:

```text
humidifier.living_room_dehumidifier
```

---

## FR-002 — Humidifier / Dehumidifier 지원

다음 `device_class`를 지원해야 한다.

```yaml
device_class: humidifier
```

```yaml
device_class: dehumidifier
```

내부적으로 Home Assistant의 표준 `HumidifierDeviceClass`를 사용해야 한다.

지원되지 않는 값은 Configuration validation 단계에서 거부해야 한다.

---

## FR-003 — State Template

다음을 지원해야 한다.

```yaml
state: >
  {{ is_state('switch.xxx', 'on') }}
```

Template 결과는 HumidifierEntity의:

```text
is_on
```

으로 매핑한다.

지원 결과:

```text
true
false
unknown
```

`unknown` 또는 유효하지 않은 결과가 Integration 전체 failure를 발생시켜서는 안 된다.

---

## FR-004 — Current Humidity

다음을 지원해야 한다.

```yaml
current_humidity: >
  {{ states('sensor.xxx') | float }}
```

HumidifierEntity의:

```text
current_humidity
```

으로 매핑한다.

지원 타입:

```text
int
float
None
```

잘못된 결과는 안전하게 `None`으로 처리해야 한다.

---

## FR-005 — Target Humidity

다음을 지원해야 한다.

```yaml
target_humidity: >
  {{ states('number.xxx') | float }}
```

HumidifierEntity의:

```text
target_humidity
```

로 매핑한다.

---

## FR-006 — Minimum Humidity

Static value를 지원해야 한다.

```yaml
min_humidity: 30
```

가능하면 Template도 지원한다.

```yaml
min_humidity: >
  {{ state_attr('number.xxx', 'min') | float }}
```

최종적으로:

```text
HumidifierEntity.min_humidity
```

로 매핑한다.

---

## FR-007 — Maximum Humidity

Static:

```yaml
max_humidity: 80
```

Template:

```yaml
max_humidity: >
  {{ state_attr('number.xxx', 'max') | float }}
```

지원.

---

## FR-008 — Target Humidity Step

다음을 지원해야 한다.

```yaml
target_humidity_step: 5
```

가능하면 Template도 지원한다.

```yaml
target_humidity_step: >
  {{ state_attr('number.xxx', 'step') | float }}
```

실제 HA UI에서 목표 습도 변경 단위에 반영되어야 한다.

---

# 8. Power Action Requirements

## FR-010 — Turn On

Configuration:

```yaml
turn_on:
  - action: switch.turn_on
    target:
      entity_id: switch.xxx
```

Home Assistant에서:

```text
humidifier.turn_on
```

이 호출되면 해당 action sequence를 실행해야 한다.

---

## FR-011 — Turn Off

Configuration:

```yaml
turn_off:
  - action: switch.turn_off
    target:
      entity_id: switch.xxx
```

Home Assistant에서:

```text
humidifier.turn_off
```

가 호출되면 해당 action sequence를 실행해야 한다.

---

## FR-012 — Toggle

별도의 사용자 Configuration 없이 HumidifierEntity의 표준 toggle 동작을 지원해야 한다.

```text
OFF → turn_on
ON  → turn_off
```

---

# 9. Target Humidity Action

## FR-020 — Set Humidity

Configuration:

```yaml
set_humidity:
  - action: number.set_value
    target:
      entity_id: number.xxx
    data:
      value: "{{ humidity }}"
```

Home Assistant에서:

```yaml
action: humidifier.set_humidity
target:
  entity_id: humidifier.xxx
data:
  humidity: 50
```

호출 시 Template action context에 다음 변수를 제공해야 한다.

```text
humidity
```

예:

```text
humidity = 50
```

---

# 10. Mode Requirements

## FR-030 — Current Mode

다음을 지원해야 한다.

```yaml
mode: >
  {{ states('select.dehumidifier_mode') }}
```

HumidifierEntity의:

```text
mode
```

로 매핑한다.

---

## FR-031 — Available Modes

Static list:

```yaml
modes:
  - auto
  - quiet
  - laundry
```

를 지원해야 한다.

가능하면 Template 기반 list도 지원한다.

예:

```yaml
modes: >
  {{ state_attr('select.dehumidifier_mode', 'options') }}
```

HumidifierEntity의:

```text
available_modes
```

로 매핑한다.

---

## FR-032 — Set Mode

Configuration:

```yaml
set_mode:
  - action: select.select_option
    target:
      entity_id: select.dehumidifier_mode
    data:
      option: "{{ mode }}"
```

호출 시 Template action context에:

```text
mode
```

변수를 제공해야 한다.

---

## FR-033 — Supported Features 자동 결정

사용자가 직접 bitmask를 설정하지 않는다.

다음 기능이 구성되면:

```text
modes
set_mode
```

Integration이 자동으로:

```text
HumidifierEntityFeature.MODES
```

를 활성화해야 한다.

Mode 기능이 구성되지 않았으면 mode feature를 노출하지 않는다.

---

# 11. Action Status

## FR-040 — Current Action

다음을 지원해야 한다.

```yaml
action: >
  {% if is_state('switch.dehumidifier_power', 'off') %}
    off
  {% elif is_state('binary_sensor.compressor', 'on') %}
    drying
  {% else %}
    idle
  {% endif %}
```

HumidifierEntity의:

```text
action
```

으로 매핑한다.

반환값은 현재 Home Assistant에서 정의하는 공식 `HumidifierAction` 값으로 변환한다.

예:

```text
off
idle
humidifying
drying
```

지원되지 않는 값은 warning을 기록하고 안전하게 `None` 처리한다.

---

# 12. Availability

## FR-050 — Availability Template

다음을 지원해야 한다.

```yaml
availability: >
  {{
    has_value('switch.xxx')
    and has_value('sensor.xxx')
  }}
```

false이면:

```text
humidifier.xxx = unavailable
```

이어야 한다.

Template rendering 오류가 Integration 전체 failure로 이어져서는 안 된다.

---

# 13. Common Template Properties

## FR-060 — Name

필수 또는 표준 Core Template 규칙에 맞는 name 처리를 제공한다.

```yaml
name: "Living Room Dehumidifier"
```

---

## FR-061 — Unique ID

지원:

```yaml
unique_id: living_room_dehumidifier
```

`unique_id`가 있으면 Entity Registry를 통해 다음 관리가 가능해야 한다.

```text
Rename
Area assignment
Disable
Entity ID customization
```

---

## FR-062 — Icon

지원 목표:

```yaml
icon: mdi:air-humidifier-off
```

Template icon 지원도 가능하면 구현한다.

```yaml
icon: >
  {% if is_state('switch.xxx', 'on') %}
    mdi:air-humidifier
  {% else %}
    mdi:air-humidifier-off
  {% endif %}
```

---

## FR-063 — Default Entity ID

최신 Core Template API와 호환 가능한 경우:

```yaml
default_entity_id: humidifier.living_room_dehumidifier
```

지원한다.

단 Home Assistant Core 버전 의존성이 큰 경우 MVP 이후 기능으로 분리할 수 있다.

---

# 14. Template Tracking

## FR-070 — State-based Template Tracking

Integration은 polling 방식으로 Template을 갱신해서는 안 된다.

예:

```yaml
current_humidity: >
  {{ states('sensor.room_humidity') }}
```

일 경우:

```text
sensor.room_humidity 변경
        ↓
Home Assistant state event
        ↓
Template re-render
        ↓
humidifier.xxx 갱신
```

형태로 동작해야 한다.

목표 IoT Class:

```text
local_push
```

---

# 15. Optimistic State

## FR-080 — Optimistic Power

다음과 같이 action은 있지만:

```yaml
turn_on:
turn_off:
```

`state`가 없는 경우 optimistic power state를 지원해야 한다.

```text
turn_on 실행
→ 내부 state = ON

turn_off 실행
→ 내부 state = OFF
```

---

## FR-081 — Optimistic Target Humidity

`set_humidity`는 있지만:

```yaml
target_humidity:
```

가 없는 경우 마지막 설정값을 기억한다.

예:

```text
set_humidity(50)
→ target_humidity = 50
```

---

## FR-082 — Optimistic Mode

`set_mode`는 있지만:

```yaml
mode:
```

가 없는 경우 마지막 설정 mode를 기억한다.

---

# 16. Restore State

## FR-090 — Optimistic State Restore

Home Assistant 재시작 시 optimistic 상태를 복원해야 한다.

복원 대상:

```text
Power state
Target humidity
Mode
```

우선순위:

```text
Template 결과
    ↓
Restored optimistic value
    ↓
Default
```

즉 실제 상태 Template이 존재하면 항상 실제 Template 결과를 우선한다.

---

# 17. Configuration Validation

## FR-100 — Device Class Validation

허용:

```text
humidifier
dehumidifier
```

그 외 값:

```text
Configuration Error
```

---

## FR-101 — Humidity Range Validation

다음은 invalid:

```yaml
min_humidity: 80
max_humidity: 40
```

Static value인 경우 Configuration load 단계에서 오류를 탐지한다.

---

## FR-102 — Step Validation

다음 값은 invalid:

```yaml
target_humidity_step: 0
```

조건:

```text
target_humidity_step > 0
```

---

## FR-103 — Action Validation

다음 Configuration들은 Home Assistant의 standard action/script schema를 이용해 validation한다.

```text
turn_on
turn_off
set_humidity
set_mode
```

가능한 한 자체 Action DSL을 만들지 않는다.

---

# 18. Error Handling Requirements

## NFR-001 — Integration Isolation

하나의 Template Entity rendering failure 때문에 전체 Integration이 중단되어서는 안 된다.

---

## NFR-002 — Invalid Sensor Value

다음 값들을 안전하게 처리해야 한다.

```text
unknown
unavailable
None
invalid numeric string
template rendering exception
```

예:

```text
current_humidity = None
```

등으로 처리한다.

---

## NFR-003 — No External I/O in Properties

HumidifierEntity property getter 내부에서:

```text
HTTP
MQTT
CoAP
Socket
Device API
```

등의 직접 I/O를 수행하지 않는다.

Template Humidifier는 Home Assistant State Machine에 이미 존재하는 상태만 이용한다.

---

# 19. Architecture

전체 데이터 흐름:

```text
┌────────────────────────────┐
│ Existing Integration       │
│                            │
│ LocalThings                │
│ ESPHome                    │
│ MQTT                       │
│ Tuya                       │
│ REST                       │
│ Modbus                     │
│ etc.                       │
└──────────────┬─────────────┘
               │
               ▼
┌────────────────────────────┐
│ Existing HA Entities       │
│                            │
│ switch.power               │
│ sensor.humidity            │
│ number.target_humidity     │
│ select.mode                │
│ binary_sensor.compressor   │
└──────────────┬─────────────┘
               │
               │ Template
               ▼
┌────────────────────────────┐
│ Template Humidifier        │
│                            │
│ Template tracking          │
│ Action execution           │
│ Validation                 │
│ Optimistic state           │
│ Restore state              │
└──────────────┬─────────────┘
               │
               ▼
┌────────────────────────────┐
│ HumidifierEntity           │
│                            │
│ humidifier.xxx             │
└────────────────────────────┘
```

---

# 20. Internal Entity Mapping

| Configuration          | HumidifierEntity       |
| ---------------------- | ---------------------- |
| `device_class`         | `device_class`         |
| `state`                | `is_on`                |
| `current_humidity`     | `current_humidity`     |
| `target_humidity`      | `target_humidity`      |
| `min_humidity`         | `min_humidity`         |
| `max_humidity`         | `max_humidity`         |
| `target_humidity_step` | `target_humidity_step` |
| `mode`                 | `mode`                 |
| `modes`                | `available_modes`      |
| `action`               | `action`               |
| `turn_on`              | `async_turn_on()`      |
| `turn_off`             | `async_turn_off()`     |
| `set_humidity`         | `async_set_humidity()` |
| `set_mode`             | `async_set_mode()`     |

---

# 21. Code Architecture

권장 구조:

```text
/
├─ custom_components/
│  └─ template_humidifier/
│     ├─ __init__.py
│     ├─ humidifier.py
│     ├─ config.py
│     ├─ const.py
│     ├─ helpers.py
│     ├─ manifest.json
│     ├─ services.yaml
│     ├─ strings.json
│     └─ translations/
│        └─ en.json
│
├─ tests/
│  ├─ conftest.py
│  ├─ test_config.py
│  ├─ test_humidifier.py
│  ├─ test_actions.py
│  ├─ test_optimistic.py
│  └─ test_restore.py
│
├─ .github/
│  └─ workflows/
│
├─ hacs.json
├─ pyproject.toml
├─ README.md
├─ LICENSE
└─ PROJECT_PLAN.md
```

---

# 22. Core Code Reference Strategy

Home Assistant Core Template 구현을 주 reference로 사용한다.

특히 기능 구조가 가장 가까운 Template Fan을 주요 reference로 한다.

개념 대응:

```text
Template Fan                     Template Humidifier

state                    →       state

percentage               →       target_humidity
set_percentage           →       set_humidity

preset_mode              →       mode
preset_modes             →       modes
set_preset_mode          →       set_mode

turn_on                  →       turn_on
turn_off                 →       turn_off
```

즉 Core Template Fan의:

```text
Template tracking
Action execution
Optimistic behavior
Restore behavior
Supported feature calculation
```

패턴을 가능한 범위에서 재사용한다.

---

# 23. Core 내부 API 의존성 정책

Home Assistant Core Template 내부 helper를 사용할 수 있지만 다음 원칙을 적용한다.

### 허용

안정적이고 현재 Core Template이 사용하는 공용 helper/API.

### 주의

```text
private API
internal implementation
undocumented helper
```

사용 시 최소 지원 Home Assistant 버전을 명확히 지정한다.

### 금지

Core module runtime monkey patch.

예:

```python
homeassistant.components.template.PLATFORMS.append(...)
```

금지.

Core Template schema runtime 수정 금지.

Core `template` integration shadowing 금지.

---

# 24. HACS Requirements

## FR-110 — HACS Installation

Custom Repository 방식으로 설치 가능해야 한다.

```text
HACS
→ Integrations
→ Custom repositories
→ Repository URL
→ Integration
```

설치 결과:

```text
/config/custom_components/template_humidifier/
```

---

## FR-111 — hacs.json

Repository root에 유효한:

```text
hacs.json
```

을 제공한다.

---

## FR-112 — manifest.json

최소:

```json
{
  "domain": "template_humidifier",
  "name": "Template Humidifier",
  "version": "0.1.0",
  "iot_class": "local_push"
}
```

형태를 갖는다.

실제 필드는 현재 Home Assistant manifest specification에 맞춘다.

---

# 25. Reload

## FR-120 — YAML Reload

최종적으로 Home Assistant 전체 restart 없이 Configuration을 reload할 수 있어야 한다.

목표 action:

```text
template_humidifier.reload
```

동작:

```text
configuration 변경
        ↓
Reload
        ↓
기존 Template Humidifier 제거
        ↓
새 Configuration validation
        ↓
Entity 재생성
```

MVP에서 구현 난도가 크게 증가할 경우 Phase 2로 이동 가능하다.

---

# 26. Variables

## FR-130 — Template Variables

Core Template과 유사한 variables 지원을 목표로 한다.

예:

```yaml
template_humidifier:
  - humidifier:
      - name: "Dehumidifier"

        variables:
          power_entity: switch.dehumidifier_power
          humidity_entity: sensor.dehumidifier_humidity
          target_entity: number.dehumidifier_target

        state: >
          {{ is_state(power_entity, 'on') }}

        current_humidity: >
          {{ states(humidity_entity) | float }}

        target_humidity: >
          {{ states(target_entity) | float }}
```

MVP 필수 항목은 아니며 Core Template과 자연스럽게 재사용 가능할 경우 구현한다.

---

# 27. Trigger-based Template

초기 버전에서는 **State-based Template을 우선 구현**한다.

MVP:

```text
State-based Template
```

지원.

향후:

```yaml
template_humidifier:
  - triggers:
      ...
    humidifier:
      ...
```

형태의 trigger-based Template 지원을 검토한다.

Trigger-based 구현 때문에 MVP 구조가 복잡해져서는 안 된다.

---

# 28. Non-Goals

초기 프로젝트에서는 다음을 구현하지 않는다.

## NG-001

새로운 가습/제습 PID 또는 hysteresis controller.

Generic Hygrostat 대체가 목적이 아니다.

## NG-002

Samsung/Tuya/ESPHome 등의 Device API 직접 연결.

## NG-003

MQTT broker 직접 접근.

## NG-004

Core `template:` integration override.

## NG-005

Core monkey patch.

## NG-006

별도의 proprietary Template language.

Jinja와 Home Assistant Action syntax를 그대로 사용한다.

## NG-007

초기 버전에서 GUI Config Flow를 필수 요구하지 않는다.

YAML-first Integration으로 개발한다.

---

# 29. MVP Scope

Version:

```text
0.1.0
```

MVP 필수 지원:

```text
✓ YAML configuration
✓ template_humidifier domain
✓ humidifier section

✓ name
✓ unique_id
✓ device_class

✓ state
✓ availability

✓ current_humidity
✓ target_humidity

✓ min_humidity
✓ max_humidity
✓ target_humidity_step

✓ turn_on
✓ turn_off
✓ set_humidity

✓ Humidifier
✓ Dehumidifier

✓ Template dependency tracking
✓ Entity update

✓ unavailable 처리
✓ invalid template 안전 처리

✓ HACS installation
```

MVP에서 반드시 필요한 핵심 use case:

```text
switch + sensor + number
        ↓
humidifier/dehumidifier
```

---

# 30. Version 0.2 Scope

추가:

```text
mode
modes
set_mode

action

supported_features 자동 계산

YAML reload
```

---

# 31. Version 0.3 Scope

추가:

```text
optimistic power
optimistic target humidity
optimistic mode

RestoreEntity
```

---

# 32. Version 0.4 Scope

Core Template parity 확장:

```text
variables
dynamic icon
default_entity_id

advanced availability

trigger-based template 검토
```

---

# 33. Version 1.0 완료 조건

다음 기능이 안정적이면 `1.0.0`으로 간주한다.

```text
Humidifier
Dehumidifier

Power
Current Humidity
Target Humidity
Humidity Range
Humidity Step

Mode
Modes
Action

Availability

Optimistic State
Restore State

Reload

Template dependency tracking

HACS installation

Automated tests
```

그리고 Configuration schema에 breaking change가 예정되어 있지 않아야 한다.

---

# 34. Test Requirements

테스트는 선택이 아니라 필수로 한다.

---

## TEST-001 State

```text
switch OFF
→ humidifier OFF

switch ON
→ humidifier ON
```

---

## TEST-002 Current Humidity

```text
sensor = 57
→ current_humidity = 57
```

---

## TEST-003 Target Humidity

```text
number = 50
→ target_humidity = 50
```

---

## TEST-004 Set Humidity

```text
humidifier.set_humidity(45)

→ configured set_humidity action
→ number.set_value(45)
```

---

## TEST-005 Turn On

```text
humidifier.turn_on

→ configured turn_on action
```

---

## TEST-006 Turn Off

```text
humidifier.turn_off

→ configured turn_off action
```

---

## TEST-007 Device Class

```yaml
device_class: dehumidifier
```

↓

```text
HumidifierDeviceClass.DEHUMIDIFIER
```

---

## TEST-008 Step

```yaml
target_humidity_step: 5
```

↓

```text
HA Entity = 5
```

---

## TEST-009 Availability

```text
source available
→ available

source unavailable
→ unavailable

source recovery
→ available
```

---

## TEST-010 Mode

```text
current mode = auto

modes =
auto
quiet
laundry
```

정상 노출.

---

## TEST-011 Set Mode

```text
humidifier.set_mode("quiet")

→ configured set_mode action
→ mode variable = "quiet"
```

---

## TEST-012 Action

Template:

```text
compressor ON
```

↓

```text
action = drying
```

---

## TEST-013 Invalid Template

다음 상황에서 Integration 전체가 crash하지 않아야 한다.

```text
unknown
unavailable
invalid number
invalid action
template exception
```

---

## TEST-014 Optimistic

state template 없이:

```text
turn_on
→ ON

turn_off
→ OFF
```

---

## TEST-015 Restore

```text
target humidity = 50
HA restart
→ target humidity = 50
```

---

# 35. CI Requirements

GitHub Actions에서 최소 다음을 실행한다.

```text
pytest
ruff
mypy
HACS validation
```

가능하면 Home Assistant custom component test framework를 사용한다.

지원 버전 matrix:

```text
Minimum supported HA
Latest stable HA
```

추가로 가능하다면:

```text
Latest beta HA
```

를 테스트하여 breaking change를 조기에 탐지한다.

---

# 36. Home Assistant Version Policy

초기 버전에서는 폭넓은 하위 호환성을 목표로 하지 않는다.

원칙:

> 최신 Home Assistant Core Template architecture와의 구조적 정합성을 오래된 HA 버전 지원보다 우선한다.

최소 지원 버전은 개발 시작 시점의 stable release를 기준으로 결정한다.

예:

```text
Home Assistant >= 2026.8
```

Core internal API 사용 여부에 따라 최소 버전을 명확하게 관리한다.

---

# 37. Example — Full Dehumidifier

최종 목표 Configuration:

```yaml
template_humidifier:
  - humidifier:
      - name: "Living Room Dehumidifier"
        unique_id: living_room_dehumidifier
        device_class: dehumidifier

        state: >
          {{ is_state('switch.dehumidifier_power', 'on') }}

        availability: >
          {{
            has_value('switch.dehumidifier_power')
            and has_value('sensor.dehumidifier_humidity')
            and has_value('number.dehumidifier_target')
          }}

        current_humidity: >
          {% set value = states('sensor.dehumidifier_humidity') %}
          {{ value | float if is_number(value) else none }}

        target_humidity: >
          {% set value = states('number.dehumidifier_target') %}
          {{ value | float if is_number(value) else none }}

        min_humidity: >
          {{ state_attr('number.dehumidifier_target', 'min') | float(30) }}

        max_humidity: >
          {{ state_attr('number.dehumidifier_target', 'max') | float(80) }}

        target_humidity_step: >
          {{ state_attr('number.dehumidifier_target', 'step') | float(5) }}

        mode: >
          {{ states('select.dehumidifier_mode') }}

        modes:
          - auto
          - quiet
          - laundry

        action: >
          {% if is_state('switch.dehumidifier_power', 'off') %}
            off
          {% elif is_state('binary_sensor.dehumidifier_compressor', 'on') %}
            drying
          {% else %}
            idle
          {% endif %}

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

        set_mode:
          - action: select.select_option
            target:
              entity_id: select.dehumidifier_mode
            data:
              option: "{{ mode }}"
```

---

# 38. Example — Simple Humidifier

```yaml
template_humidifier:
  - humidifier:
      - name: "Bedroom Humidifier"
        unique_id: bedroom_humidifier
        device_class: humidifier

        state: >
          {{ is_state('switch.humidifier_power', 'on') }}

        current_humidity: >
          {{ states('sensor.bedroom_humidity') | float }}

        target_humidity: >
          {{ states('number.humidifier_target') | float }}

        min_humidity: 30
        max_humidity: 70
        target_humidity_step: 5

        turn_on:
          - action: switch.turn_on
            target:
              entity_id: switch.humidifier_power

        turn_off:
          - action: switch.turn_off
            target:
              entity_id: switch.humidifier_power

        set_humidity:
          - action: number.set_value
            target:
              entity_id: number.humidifier_target
            data:
              value: "{{ humidity }}"
```

---

# 39. 최종 사용자 경험

설치:

```text
HACS
↓
Template Humidifier 설치
↓
HA 재시작
```

Configuration:

```yaml
template_humidifier:
  - humidifier:
      ...
```

결과:

```text
기존 Integration
      │
      ├─ switch
      ├─ sensor
      ├─ number
      └─ select
             │
             ▼
      Template Humidifier
             │
             ▼
       humidifier.xxx
             │
       ┌─────┼─────┐
       ▼     ▼     ▼
 Dashboard  Voice  Automation
```

사용자는 원본 Integration이 HumidifierEntity를 제대로 구현하지 않아도 기존 Entity들을 조합하여 표준 Home Assistant Humidifier/Dehumidifier 인터페이스를 만들 수 있어야 한다.

---

# 40. 프로젝트 최종 요구사항 요약

프로젝트는 반드시 다음 네 가지 원칙을 만족해야 한다.

### 1. Core-like Configuration

```yaml
template_humidifier:
  - humidifier:
```

루트를 제외하면 최신 Core Template과 최대한 동일한 Configuration 스타일을 사용한다.

### 2. Full HumidifierEntity

단순 전원 + 목표 습도 wrapper가 아니라 Home Assistant 표준 HumidifierEntity 기능을 가능한 한 모두 지원한다.

```text
Power
Current Humidity
Target Humidity
Range
Step
Mode
Modes
Action
Availability
```

### 3. Humidifier + Dehumidifier

두 종류를 동등하게 지원한다.

### 4. No Core Modification

다음을 하지 않는다.

```text
Core template override
Core monkey patch
Core schema modification
Custom YAML parser
```

독립 HACS Integration으로 구현한다.

---

# 41. 프로젝트 정의 한 문장

> **Template Humidifier는 Home Assistant Core Template의 최신 Configuration 및 Entity 구현 패턴을 따르면서, 기존 Home Assistant Entity들을 표준 Humidifier/Dehumidifier Entity로 재구성할 수 있게 하는 YAML-first HACS Custom Integration이다.**


---

# 42. 릴리즈 정책 추가 결정

- `0.1.0`은 MVP의 정식 목표 버전이다.
- 최초 공개 검증 버전은 `0.1.0b1`, 태그는 `v0.1.0b1`이다.
- 모든 베타/RC는 GitHub Pre-release로만 발행한다.
- 정식 릴리즈는 최종 검증과 프로젝트 소유자의 명시적 승인 이후에만 발행한다.
- 상세 정책은 `RELEASE_POLICY.md`를 따른다.

