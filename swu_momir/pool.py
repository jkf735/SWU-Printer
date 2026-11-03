"""The rules for which units a player can roll."""

import random
from dataclasses import dataclass, field

ALL_MODE = None  # the middle Player knob position: no identity filter
COST_PLUS = 9  # the 9 setting means 9 or more
PORG_ID = "LOF-254"  # printed as a joke when the pool is empty


@dataclass(frozen=True)
class Identity:
    aspects: dict[str, int] = field(default_factory=dict)  # e.g. {"Vigilance": 2, "Heroism": 1}
    neutral: bool = True

    def covers(self, unit: dict) -> bool:
        """Return whether this identity has every icon on the unit, counting doubles."""
        icons = unit["aspects"]
        if not icons:
            return self.neutral
        return all(self.aspects.get(icon, 0) >= icons.count(icon) for icon in icons)


def eligible_units(units: list[dict], identity: Identity | None, cost: int,
                   arena: str | None = None, keyword: str | None = None) -> list[dict]:
    """Return the units matching the current settings. None means no filter."""
    # Cost comes first because it rules out the most cards, and this runs on every knob turn.
    return [unit for unit in units
            if (unit["cost"] >= COST_PLUS if cost == COST_PLUS else unit["cost"] == cost)
            and (arena is None or unit["arena"] == arena)
            and (keyword is None or keyword in unit["keywords"])
            and (identity is ALL_MODE or identity.covers(unit))]


def roll(units: list[dict], pool: list[dict], rng=random) -> dict:
    """Return a random unit from the pool, or the Porg if the pool is empty."""
    if pool:
        return rng.choice(pool)
    return next(unit for unit in units if PORG_ID in unit["printings"])