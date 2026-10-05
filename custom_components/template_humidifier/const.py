"""Constants for the Template Humidifier integration."""

from typing import Final

DOMAIN: Final = "template_humidifier"

CONF_HUMIDIFIER: Final = "humidifier"
CONF_CURRENT_HUMIDITY: Final = "current_humidity"
CONF_TARGET_HUMIDITY: Final = "target_humidity"
CONF_MIN_HUMIDITY: Final = "min_humidity"
CONF_MAX_HUMIDITY: Final = "max_humidity"
CONF_TARGET_HUMIDITY_STEP: Final = "target_humidity_step"
CONF_TURN_ON: Final = "turn_on"
CONF_TURN_OFF: Final = "turn_off"
CONF_SET_HUMIDITY: Final = "set_humidity"
CONF_MODE: Final = "mode"
CONF_MODES: Final = "modes"
CONF_SET_MODE: Final = "set_mode"
CONF_ACTION: Final = "action"

DEFAULT_NAME: Final = "Template Humidifier"

SCRIPT_FIELDS: Final = (CONF_TURN_ON, CONF_TURN_OFF, CONF_SET_HUMIDITY, CONF_SET_MODE)
ENTITIES: Final = "entities"
