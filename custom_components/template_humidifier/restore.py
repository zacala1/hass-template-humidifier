"""Extra state stored so remembered values survive a restart."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Self, override

from homeassistant.helpers.restore_state import ExtraStoredData

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True, kw_only=True)
class HumidifierExtraStoredData(ExtraStoredData):
    """What a humidifier remembers from commands: power, target and mode."""

    is_on: bool | None
    target_humidity: float | None
    mode: str | None

    @override
    def as_dict(self) -> dict[str, object]:
        """Return the data in the form Home Assistant writes to storage."""
        return {
            "is_on": self.is_on,
            "target_humidity": self.target_humidity,
            "mode": self.mode,
        }

    @classmethod
    def from_dict(cls, restored: Mapping[str, object]) -> Self:
        """Rebuild the data, keeping only values of the expected type."""
        is_on = restored.get("is_on")
        target = restored.get("target_humidity")
        mode = restored.get("mode")
        return cls(
            is_on=is_on if isinstance(is_on, bool) else None,
            target_humidity=(
                target
                if isinstance(target, int | float) and not isinstance(target, bool)
                else None
            ),
            mode=mode if isinstance(mode, str) else None,
        )
