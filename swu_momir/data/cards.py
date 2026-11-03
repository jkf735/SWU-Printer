"""Download units and tokens from SWU-DB and keep a local copy that works offline.

Refresh the cache with:  python -m swu_momir.data.cards

Each update downloads the cards, applies the fixes in
resources/card_corrections.json, and writes cache/cards.json, which is what the
rest of the program reads. A failed or suspicious update never touches the
existing cache, so the machine can always fall back on the last good copy.

Units and tokens are stored apart: only units can be rolled, and tokens are only
for token mode.
"""

import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

UNITS_URL = "https://api.swu-db.com/cards/search?q=type:unit%20not:reprint&format=json"
TOKENS_URL = "https://api.swu-db.com/cards/search?q=type:token&format=json"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_PATH = PROJECT_ROOT / "cache" / "cards.json"
CORRECTIONS_PATH = PROJECT_ROOT / "resources" / "card_corrections.json"

ASPECTS = {"Vigilance", "Command", "Aggression", "Cunning", "Heroism", "Villainy"}
ARENAS = {"Ground", "Space"}
# The keywords players can filter by. Their tags are checked by hand.
FILTER_KEYWORDS = ("Ambush", "Sentinel")

# A real update shouldn't lose many cards, so a big drop means a bad response.
MIN_KEPT_FRACTION = 0.9


class UpdateError(Exception):
    """The update couldn't be completed. The existing cache is unchanged."""


@dataclass
class CardList:
    cards: list[dict] = field(default_factory=list)
    reprints_merged: int = 0
    # Merged printings whose rules text isn't identical, usually wording changes.
    text_differs: list[str] = field(default_factory=list)
    # Records that couldn't be read, as "id: problem".
    rejected: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    # Corrections that changed nothing, usually because the API fixed the card.
    stale_corrections: list[str] = field(default_factory=list)
    # New units whose filter keyword tags need checking by hand.
    needs_review: list[str] = field(default_factory=list)


@dataclass
class UpdateResult:
    units: CardList
    tokens: CardList


def fetch_json(url: str, timeout: float = 20) -> dict:
    """Return the decoded search response from the API."""
    # Imported here because they load slowly on the Pi and only updates use them.
    import http.client
    import urllib.request

    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.load(response)
    except (OSError, http.client.HTTPException, ValueError) as error:
        raise UpdateError(f"could not download {url}: {error}") from error


def normalize_card(raw: dict) -> dict:
    """Convert one API record to our format. Raises if it can't be used in a pool."""
    aspects = raw.get("Aspects") or []  # the key is missing on some neutral units
    unknown = set(aspects) - ASPECTS
    if unknown:
        raise ValueError(f"unknown aspects {sorted(unknown)}")

    arena, = raw["Arenas"]
    if arena not in ARENAS:
        raise ValueError(f"unknown arena {arena!r}")

    return {
        "id": f"{raw['Set']}-{raw['Number']}",
        "set": raw["Set"],
        "number": raw["Number"],
        "name": raw["Name"].strip(),
        "subtitle": raw.get("Subtitle", "").strip(),
        "cost": int(raw["Cost"]),
        "aspects": aspects,  # double icons are listed twice
        "arena": arena,
        "power": int(raw["Power"]),
        "hp": int(raw["HP"]),
        "unique": raw["Unique"],
        "traits": raw.get("Traits") or [],
        "keywords": raw.get("Keywords") or [],
        "text": raw.get("FrontText", "").strip(),
        "image_url": raw["FrontArt"],
    }


def normalize_token(raw: dict) -> dict:
    """Convert one token record. Credit and Force tokens have no stats or arena."""
    return {
        "id": f"{raw['Set']}-{raw['Number']}",
        "set": raw["Set"],
        "number": raw["Number"],
        "name": raw["Name"].strip(),
        "type": raw["Type"],
        "power": int(raw["Power"]) if "Power" in raw else None,
        "hp": int(raw["HP"]) if "HP" in raw else None,
        "text": raw.get("FrontText", "").strip(),
        "image_url": raw["FrontArt"],
    }


def merge_records(records: list[dict], normalize, merge_key) -> CardList:
    """Return one card per distinct merge_key, sorted by id."""
    result = CardList()
    groups: dict[tuple, list[dict]] = {}
    for raw in records:
        try:
            card = normalize(raw)
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            label = f"{raw.get('Set')}-{raw.get('Number')} {raw.get('Name')}"
            result.rejected.append(f"{label}: {error!r}")
            continue
        groups.setdefault(merge_key(card), []).append(card)

    for printings in groups.values():
        printings.sort(key=lambda card: card["id"])
        card = {**printings[0], "printings": [p["id"] for p in printings]}
        result.cards.append(card)
        result.reprints_merged += len(printings) - 1
        if len({p["text"] for p in printings}) > 1:
            result.text_differs.append(f"{card['name']} ({', '.join(card['printings'])})")

    result.cards.sort(key=lambda card: card["id"])
    return result


def response_records(response: dict) -> list[dict]:
    """Return the records in a response, checking that all of them arrived."""
    records = response["data"]
    if response["total_cards"] != len(records):
        raise ValueError(f"expected {response['total_cards']} cards, got {len(records)}")
    return records


def unit_merge_key(card: dict) -> tuple:
    # not:reprint still returns the same unit several times, which would make it
    # more likely to be rolled. Text is left out because wording varies between
    # printings.
    return (card["name"], card["subtitle"], card["cost"], tuple(sorted(card["aspects"])),
            card["arena"], card["power"], card["hp"])


def token_merge_key(card: dict) -> tuple:
    # The same token is printed in many sets, but token mode should list it once.
    return (card["name"], card["type"], card["power"], card["hp"])


def normalize_units(response: dict) -> CardList:
    """Turn a unit search response into one record per distinct unit."""
    # The search also matches "Token Unit", which must never be rolled.
    records = [raw for raw in response_records(response) if raw.get("Type") == "Unit"]
    return merge_records(records, normalize_card, unit_merge_key)


def normalize_tokens(response: dict) -> CardList:
    """Turn a token search response into one record per distinct token."""
    return merge_records(response_records(response), normalize_token, token_merge_key)


def load_corrections(path: Path = CORRECTIONS_PATH) -> list[dict]:
    """Return the checked list of corrections. Raises UpdateError if it has a mistake."""
    try:
        with open(path, encoding="utf-8") as file:
            corrections = json.load(file)["corrections"]
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise UpdateError(f"could not read {path}: {error!r}") from error

    allowed = {"card", "name", "reason", "add_keywords", "remove_keywords"}
    seen = set()
    for entry in corrections:
        problem = None
        if set(entry) - allowed:
            problem = f"unknown fields {sorted(set(entry) - allowed)}"
        elif "card" not in entry or "reason" not in entry:
            problem = "needs both card and reason"
        elif not (entry.get("add_keywords") or entry.get("remove_keywords")):
            problem = "needs add_keywords or remove_keywords"
        elif entry["card"] in seen:
            problem = "listed more than once"
        if problem:
            raise UpdateError(f"bad entry in {path}: {entry}: {problem}")
        seen.add(entry["card"])
    return corrections


def apply_corrections(units: CardList, corrections: list[dict]) -> None:
    """Fix unit keyword tags in place, noting any correction that changed nothing."""
    by_printing = {printing: card for card in units.cards for printing in card["printings"]}
    for entry in corrections:
        label = f"{entry['card']} {entry.get('name', '')}".strip()
        card = by_printing.get(entry["card"])
        if card is None:
            units.stale_corrections.append(f"{label}: card not found")
            continue
        for keyword in entry.get("add_keywords", []):
            if keyword in card["keywords"]:
                units.stale_corrections.append(f"{label}: already has {keyword}")
            else:
                card["keywords"].append(keyword)
        for keyword in entry.get("remove_keywords", []):
            if keyword in card["keywords"]:
                card["keywords"].remove(keyword)
            else:
                units.stale_corrections.append(f"{label}: already lacks {keyword}")
        card["keywords"].sort()


def needs_keyword_review(card: dict) -> bool:
    """Return whether a filter keyword's tag can't be trusted without reading the card.

    A tagged card with the keyword on its own line is safe. Anything else that
    has the tag or mentions the keyword might only affect other units.
    """
    text = re.sub(r"\([^)]*\)", "", card["text"])  # reminder text mentions other keywords
    for keyword in FILTER_KEYWORDS:
        tagged = keyword in card["keywords"]
        on_own_line = re.search(rf"^\s*{keyword}\b", text, re.IGNORECASE | re.MULTILINE)
        mentioned = re.search(rf"\b{keyword}\b", text, re.IGNORECASE)
        if (tagged or mentioned) and not (tagged and on_own_line):
            return True
    return False


def load_cached(key: str, path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as file:
        return json.load(file)[key]


def load_units(path: Path = CACHE_PATH) -> list[dict]:
    """Return the cached units. Reads the local file only, never the network."""
    return load_cached("units", path)


def load_tokens(path: Path = CACHE_PATH) -> list[dict]:
    """Return the cached tokens. Reads the local file only, never the network."""
    return load_cached("tokens", path)


def save_cards(units: list[dict], tokens: list[dict], path: Path = CACHE_PATH) -> None:
    write_json_atomic({
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": [UNITS_URL, TOKENS_URL],
        "units": units,
        "tokens": tokens,
    }, path)


def write_json_atomic(document: dict, path: Path) -> None:
    """Write a JSON file in one step, so a power cut can't leave half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(document, file, ensure_ascii=False, indent=1)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temp_path, path)


def compare_to_cache(new: CardList, key: str, path: Path) -> None:
    """Fill in what changed. Raises UpdateError if the new list looks wrong."""
    try:
        previous = load_cached(key, path)
    except (OSError, KeyError, TypeError, ValueError):
        previous = []

    if not new.cards or len(new.cards) < len(previous) * MIN_KEPT_FRACTION:
        raise UpdateError(
            f"response has {len(new.cards)} usable {key} but the cache has {len(previous)}; "
            f"keeping the cache (delete {path} to accept this response)"
        )

    new_ids = {card["id"] for card in new.cards}
    old_ids = {card["id"] for card in previous}
    new.added = sorted(new_ids - old_ids)
    new.removed = sorted(old_ids - new_ids)


def update_cards(path: Path = CACHE_PATH, fetch=fetch_json,
                 corrections_path: Path = CORRECTIONS_PATH) -> UpdateResult:
    """Download, correct, check, and cache all cards. Raises UpdateError on failure."""
    corrections = load_corrections(corrections_path)
    units_response = fetch(UNITS_URL)
    tokens_response = fetch(TOKENS_URL)
    try:
        units = normalize_units(units_response)
        tokens = normalize_tokens(tokens_response)
    except (KeyError, TypeError, ValueError) as error:
        raise UpdateError(f"unexpected response from the API: {error!r}") from error

    apply_corrections(units, corrections)
    compare_to_cache(units, "units", path)
    compare_to_cache(tokens, "tokens", path)

    # With no earlier cache every card looks new, so there's nothing useful to flag.
    if len(units.added) < len(units.cards):
        added = set(units.added)
        units.needs_review = [f"{card['id']} {card['name']}" for card in units.cards
                              if card["id"] in added and needs_keyword_review(card)]

    save_cards(units.cards, tokens.cards, path)
    return UpdateResult(units, tokens)


def print_summary(label: str, cards: CardList) -> None:
    print(f"  {len(cards.cards)} {label}: added {len(cards.added)}, removed {len(cards.removed)}, "
          f"merged {cards.reprints_merged} reprints")
    for note in cards.text_differs:
        print(f"    merged despite different text: {note}")
    for note in cards.rejected:
        print(f"    rejected: {note}")
    for note in cards.stale_corrections:
        print(f"    correction no longer needed: {note}")
    for note in cards.needs_review:
        print(f"    check keyword tags, then update {CORRECTIONS_PATH.name} if needed: {note}")


def main() -> int:
    try:
        result = update_cards()
    except UpdateError as error:
        print(f"Update failed: {error}", file=sys.stderr)
        return 1

    print(f"Saved to {CACHE_PATH}")
    print_summary("units", result.units)
    print_summary("tokens", result.tokens)
    return 0


if __name__ == "__main__":
    sys.exit(main())
