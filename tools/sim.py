"""Play through the machine's controls on a desktop, with no hardware.

Run from the project folder with:  python -m tools.sim

Printed cards are saved to cache/last_print.png, so keep that open in an editor
tab to see them. Identities and the last card are saved to cache/state.json, as
they would be on the Pi.
"""

import os
import shutil
import sys

from swu_momir.data.cards import CACHE_PATH, load_tokens, load_units
from swu_momir.data.images import print_image_path
from swu_momir.state import (COLORS, SETUP_CURSOR, STATE_PATH, Button, Knob, Machine, PrintCard,
                             ShutDown)

LAST_PRINT_PATH = CACHE_PATH.with_name("last_print.png")
QUIT_KEYS = ("\x1b", "\x03")  # Esc and Ctrl-C

TURNS = {
    "q": (Knob.PLAYER, -1), "w": (Knob.PLAYER, 1),
    "e": (Knob.COST, -1), "r": (Knob.COST, 1),
    "t": (Knob.ARENA, -1), "y": (Knob.ARENA, 1),
    "u": (Knob.KEYWORD, -1), "i": (Knob.KEYWORD, 1),
}
PRESSES = {
    "o": Button.KEYWORD_PUSH,
    "p": Button.KEYWORD_HOLD,
    " ": Button.PRINT,
    "z": Button.UTILITY,
    "x": Button.UTILITY_DOUBLE,
    "c": Button.UTILITY_LONG,
}
LEGEND = """\
Knobs (left, right):  Player q w   Cost e r   Arena t y   Keyword u i
Keyword knob:         o push   p hold
Buttons:              Space Print   z Utility   x double-press   c long-press
Esc quits"""


def read_keys():
    """Yield one key at a time: instantly in a Windows console, otherwise from piped text."""
    if not sys.stdin.isatty():
        yield from sys.stdin.read().replace("\n", "")
        return

    import msvcrt

    while True:
        key = msvcrt.getwch()
        if key in ("\x00", "\xe0"):  # the first half of an arrow or function key
            msvcrt.getwch()
            continue
        yield key


def light(machine: Machine, name: str, label: str) -> str:
    """Return one light as text: [Vig] is lit, >Vig< is the setup cursor, and vig is dark."""
    is_lit = name in machine.lit_lights()
    if name == machine.cursor:
        return f">{label if is_lit else label.lower()}<"
    return f"[{label}]" if is_lit else f" {label.lower()} "


def frame(machine: Machine, status: str) -> str:
    """Return the whole front panel as text."""
    top_row = " ".join(light(machine, f"{color} x2", color[:3]) for color in COLORS)
    bottom_row = " ".join(light(machine, name, name[:3]) for name in SETUP_CURSOR)
    display = [f"| {row:<22} |" for row in machine.display_rows()]
    border = "+" + "-" * 24 + "+"
    return "\n".join([f"x2  {top_row}", f"    {bottom_row}", "", border, *display, border, "",
                      status, "", LEGEND])


def describe(card: dict) -> str:
    title = f"{card['name']}, {card['subtitle']}" if card.get("subtitle") else card["name"]
    if "cost" in card:
        details = f"cost {card['cost']}, {card['arena']}, {', '.join(card['aspects']) or 'no aspects'}"
    else:
        details = card["type"]
    return f"{title} ({card['id']}): {details}"


def show_print(card: dict) -> str:
    """Save the card's print file where it can be viewed, and return a status line."""
    source = print_image_path(card)
    temp_path = LAST_PRINT_PATH.with_name(LAST_PRINT_PATH.name + ".tmp")
    try:
        shutil.copyfile(source, temp_path)
        os.replace(temp_path, LAST_PRINT_PATH)
    except OSError as error:
        return f"Printed {describe(card)}, but could not show it ({error}). Try: python -m tools.prepare_images"
    return f"Printed {describe(card)}"


def main(state_path=STATE_PATH) -> None:
    machine = Machine(load_units(), load_tokens(), state_path)
    interactive = sys.stdin.isatty()
    if interactive:
        os.system("")  # lets the Windows console understand the clear-screen code below

    def draw(status: str) -> None:
        print(("\x1b[2J\x1b[H" if interactive else "\n") + frame(machine, status), flush=True)

    draw(f"Printed cards are saved to {LAST_PRINT_PATH}")
    for key in read_keys():
        if key in QUIT_KEYS:
            break
        key = key.lower()
        status = ""
        if key in TURNS:
            machine.turn(*TURNS[key])
        elif key in PRESSES:
            result = machine.press(PRESSES[key])
            if isinstance(result, PrintCard):
                status = show_print(result.card)
            elif isinstance(result, ShutDown):
                draw("The Pi would shut down now. Run the sim again to wake it.")
                break
        draw(status)


if __name__ == "__main__":
    main()
