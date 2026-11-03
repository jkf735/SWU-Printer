"""What the machine is doing, and how it responds to the knobs and buttons.

This has no hardware in it. Drivers send events to turn() and press(), carry out
whatever press() returns, then show display_rows() and lit_lights().
"""

import json
import random
from dataclasses import dataclass, replace
from enum import Enum, auto
from pathlib import Path

from swu_momir.data.cards import CACHE_PATH, write_json_atomic
from swu_momir.pool import ALL_MODE, COST_PLUS, Identity, eligible_units, roll

STATE_PATH = CACHE_PATH.with_name("state.json")

PLAYERS = ("P1", "All", "P2")
ARENA_CHOICES = (None, "Ground", "Space")
KEYWORD_CHOICES = (None, "Ambush", "Sentinel")

COLORS = ("Vigilance", "Command", "Aggression", "Cunning")
ALIGNMENTS = ("Heroism", "Villainy")
NEUTRAL = "Neutral"
SETUP_CURSOR = (*COLORS, *ALIGNMENTS, NEUTRAL)  # left to right along the bottom row of lights
ALL_LIGHTS = frozenset((*SETUP_CURSOR, *(f"{color} x2" for color in COLORS)))


class Mode(Enum):
    NORMAL = auto()
    SETUP = auto()
    TOKEN = auto()
    SHUTDOWN = auto()


class Knob(Enum):
    PLAYER = auto()
    COST = auto()
    ARENA = auto()
    KEYWORD = auto()


class Button(Enum):
    PRINT = auto()
    UTILITY = auto()
    UTILITY_DOUBLE = auto()
    UTILITY_LONG = auto()
    KEYWORD_PUSH = auto()
    KEYWORD_HOLD = auto()


@dataclass(frozen=True)
class PrintCard:
    card: dict


@dataclass(frozen=True)
class ShutDown:
    pass


def cycle_aspect(identity: Identity, aspect: str) -> Identity:
    """Return the identity with one aspect moved to its next value."""
    if aspect == NEUTRAL:
        return replace(identity, neutral=not identity.neutral)
    choices = 3 if aspect in COLORS else 2  # colors go 0, 1, 2 and alignments go 0, 1
    aspects = {**identity.aspects, aspect: (identity.aspects.get(aspect, 0) + 1) % choices}
    return replace(identity, aspects={name: count for name, count in aspects.items() if count})


def clamp(value: int, top: int) -> int:
    return max(0, min(top, value))


class Machine:
    def __init__(self, units: list[dict], tokens: list[dict], path: Path = STATE_PATH, rng=random):
        self.units = units
        self.tokens = sorted(tokens, key=lambda token: token["name"])
        self.path = path
        self.rng = rng

        self.mode = Mode.NORMAL
        self.player_index = 0
        self.cost = 0
        self.arena_index = 0
        self.keyword_index = 0
        self.cursor_index = 0
        self.token_index = 0
        self.identities = {"P1": Identity(), "P2": Identity()}
        self.last_card = None
        self._load()

    @property
    def player(self) -> str:
        return PLAYERS[self.player_index]

    @property
    def arena(self) -> str | None:
        return ARENA_CHOICES[self.arena_index]

    @property
    def keyword(self) -> str | None:
        return KEYWORD_CHOICES[self.keyword_index]

    @property
    def identity(self) -> Identity | None:
        return ALL_MODE if self.player == "All" else self.identities[self.player]

    @property
    def cursor(self) -> str | None:
        """Return the aspect whose light should blink, if any."""
        return SETUP_CURSOR[self.cursor_index] if self.mode is Mode.SETUP else None

    def pool(self) -> list[dict]:
        return eligible_units(self.units, self.identity, self.cost, self.arena, self.keyword)

    def turn(self, knob: Knob, steps: int) -> None:
        """Handle a knob turn. Knobs stop at the ends of their ranges, unless they scroll a list."""
        if self.mode is Mode.NORMAL:
            if knob is Knob.PLAYER:
                player_index = clamp(self.player_index + steps, len(PLAYERS) - 1)
                if player_index != self.player_index:
                    # Filters are paid for per roll, so they don't carry over to the next player.
                    self.player_index = player_index
                    self.arena_index = 0
                    self.keyword_index = 0
            elif knob is Knob.COST:
                self.cost = clamp(self.cost + steps, COST_PLUS)
            elif knob is Knob.ARENA:
                self.arena_index = clamp(self.arena_index + steps, len(ARENA_CHOICES) - 1)
            elif knob is Knob.KEYWORD:
                self.keyword_index = clamp(self.keyword_index + steps, len(KEYWORD_CHOICES) - 1)
        elif self.mode is Mode.SETUP and knob is Knob.KEYWORD:
            self.cursor_index = (self.cursor_index + steps) % len(SETUP_CURSOR)
        elif self.mode is Mode.TOKEN and knob is Knob.COST:
            self.token_index = (self.token_index + steps) % len(self.tokens)

    def press(self, button: Button) -> PrintCard | ShutDown | None:
        """Handle a button press, returning anything the drivers need to carry out."""
        if self.mode is Mode.SHUTDOWN:
            return None
        if button is Button.UTILITY_LONG:
            self.mode = Mode.SHUTDOWN
            self._save()
            return ShutDown()
        if self.mode is Mode.NORMAL:
            return self._press_normal(button)
        if self.mode is Mode.SETUP:
            return self._press_setup(button)
        return self._press_token(button)

    def _press_normal(self, button: Button) -> PrintCard | None:
        if button is Button.PRINT:
            return self._print(roll(self.units, self.pool(), self.rng))
        if button is Button.UTILITY and self.last_card:
            return PrintCard(self.last_card)
        if button is Button.UTILITY_DOUBLE:
            self.mode = Mode.TOKEN
        elif button is Button.KEYWORD_HOLD and self.player != "All":
            self.mode = Mode.SETUP
            self.cursor_index = 0
        return None

    def _press_setup(self, button: Button) -> None:
        if button is Button.KEYWORD_PUSH:
            self.identities[self.player] = cycle_aspect(self.identity, self.cursor)
        elif button is Button.KEYWORD_HOLD:
            self.identities[self.player] = Identity()  # start over for a new game
        elif button in (Button.UTILITY, Button.UTILITY_DOUBLE):
            self.mode = Mode.NORMAL
            self._save()

    def _press_token(self, button: Button) -> PrintCard | None:
        if button is Button.PRINT:
            return self._print(self.tokens[self.token_index])
        if button in (Button.UTILITY, Button.UTILITY_DOUBLE):
            self.mode = Mode.NORMAL
        return None

    def _print(self, card: dict) -> PrintCard:
        self.last_card = card
        self._save()
        return PrintCard(card)

    def display_rows(self) -> tuple[str, str, str]:
        """Return the three rows of text for the display."""
        if self.mode is Mode.SHUTDOWN:
            return ("Shutting down", "", "")
        if self.mode is Mode.TOKEN:
            return ("Tokens", self.tokens[self.token_index]["name"],
                    f"{self.token_index + 1} of {len(self.tokens)}")
        if self.mode is Mode.SETUP:
            # The whole pool for the identity, since the knobs are busy with setup.
            total = sum(self.identity.covers(unit) for unit in self.units)
            return (f"{self.player} Setup", f"{self.cursor}: {self._cursor_value()}", f"Pool {total}")

        cost = f"{COST_PLUS}+" if self.cost == COST_PLUS else str(self.cost)
        filters = " ".join(part for part in (self.arena, self.keyword) if part) or "Any"
        return (f"{self.player:<12}Cost {cost}", filters, f"Pool {len(self.pool())}")

    def _cursor_value(self) -> str:
        if self.cursor == NEUTRAL:
            return "On" if self.identity.neutral else "Off"
        count = self.identity.aspects.get(self.cursor, 0)
        if self.cursor in ALIGNMENTS:
            return "On" if count else "Off"
        return str(count)

    def lit_lights(self) -> frozenset[str]:
        """Return the names of the lights to turn on, such as "Vigilance" or "Vigilance x2"."""
        identity = self.identity
        if identity is ALL_MODE:
            return ALL_LIGHTS
        lit = {NEUTRAL} if identity.neutral else set()
        for aspect, count in identity.aspects.items():
            lit.add(aspect)
            if count == 2:
                lit.add(f"{aspect} x2")
        return frozenset(lit)

    def _save(self) -> None:
        document = {
            "identities": {player: {"aspects": identity.aspects, "neutral": identity.neutral}
                           for player, identity in self.identities.items()},
            "last_card": self.last_card["id"] if self.last_card else None,
        }
        try:
            write_json_atomic(document, self.path)
        except OSError as error:
            # Losing saved settings is much better than stopping the game.
            print(f"Could not save {self.path}: {error}")

    def _load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as file:
                document = json.load(file)
            identities = {player: Identity(dict(saved["aspects"]), bool(saved["neutral"]))
                          for player, saved in document["identities"].items()}
            last_id = document["last_card"]
        except (OSError, AttributeError, KeyError, TypeError, ValueError):
            return  # first run, or an unreadable file: keep the defaults
        self.identities.update(identities)
        # A card's ID can change between updates, but its old ID stays in its printings.
        self.last_card = next((card for card in self.units + self.tokens
                               if last_id in card["printings"]), None)