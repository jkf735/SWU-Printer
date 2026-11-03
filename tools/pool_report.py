"""Count the units each possible identity can roll at every setting.

Run from the project folder with:  python -m tools.pool_report

Prints a summary and writes every count to cache/pool_report.csv. An identity is
whatever setup allows, whether or not a real leader and base could give it.
"""

import csv
import statistics
from itertools import product

from swu_momir.data.cards import CACHE_PATH, load_units
from swu_momir.pool import COST_PLUS, Identity, eligible_units

ASPECTS_BY_LETTER = {"Y": "Cunning", "R": "Aggression", "B": "Vigilance", "G": "Command",
                     "H": "Heroism", "V": "Villainy"}
ARENAS = (None, "Ground", "Space")
KEYWORDS = (None, "Ambush", "Sentinel")
COSTS = range(COST_PLUS + 1)
TINY = 2  # pools this small or smaller get called out, along with empty ones


def all_identities() -> dict[str, Identity]:
    """Return every identity setup allows, by name like "YYBHN" (N means Neutral is on)."""
    identities = {}
    choices = [range(3)] * 4 + [range(2)] * 2 + [(True, False)]
    for *counts, neutral in product(*choices):
        by_letter = dict(zip(ASPECTS_BY_LETTER, counts))
        name = "".join(letter * count for letter, count in by_letter.items()) + ("N" if neutral else "")
        identities[name or "Nothing"] = Identity({ASPECTS_BY_LETTER[letter]: count
                                                  for letter, count in by_letter.items() if count},
                                                 neutral)
    return identities


def count_pools(units: list[dict], identities: dict[str, Identity]) -> dict[tuple, int]:
    """Return the pool size for each (identity name, cost, arena, keyword)."""
    return {(name, cost, arena, keyword): len(eligible_units(units, identity, cost, arena, keyword))
            for name, identity in identities.items()
            for cost in COSTS for arena in ARENAS for keyword in KEYWORDS}


def filter_label(arena: str | None, keyword: str | None) -> str:
    return " ".join(part for part in (arena, keyword) if part) or "No filter"


def cost_label(cost: int) -> str:
    return f"{COST_PLUS}+" if cost == COST_PLUS else str(cost)


def print_summary(pools: dict[tuple, int], identities: dict[str, Identity]) -> None:
    empty = sum(size == 0 for size in pools.values())
    tiny = sum(0 < size <= TINY for size in pools.values())
    print(f"{len(identities)} identities, {len(pools)} settings: "
          f"{empty} empty, {tiny} with {TINY} or fewer units\n")

    print("Median / largest pool across identities")
    print(f"{'':18}" + "".join(f"{cost_label(cost):>10}" for cost in COSTS))
    for arena in ARENAS:
        for keyword in KEYWORDS:
            cells = []
            for cost in COSTS:
                sizes = [pools[name, cost, arena, keyword] for name in identities]
                cells.append(f"{statistics.median(sizes):g}/{max(sizes)}")
            print(f"{filter_label(arena, keyword):18}" + "".join(f"{cell:>10}" for cell in cells))

    print("\nShare of identities with an empty pool")
    print(f"{'':18}" + "".join(f"{cost_label(cost):>6}" for cost in COSTS))
    for arena in ARENAS:
        for keyword in KEYWORDS:
            shares = [sum(pools[name, cost, arena, keyword] == 0 for name in identities) / len(identities)
                      for cost in COSTS]
            print(f"{filter_label(arena, keyword):18}" + "".join(f"{share:>6.0%}" for share in shares))


def write_csv(pools: dict[tuple, int]) -> None:
    path = CACHE_PATH.with_name("pool_report.csv")
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["identity", "cost", "arena", "keyword", "units"])
        for (name, cost, arena, keyword), size in pools.items():
            writer.writerow([name, cost_label(cost), arena or "Any", keyword or "None", size])
    print(f"\nEvery count is in {path}")


def main() -> None:
    identities = all_identities()
    pools = count_pools(load_units(), identities)
    print_summary(pools, identities)
    write_csv(pools)


if __name__ == "__main__":
    main()
